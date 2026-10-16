"""SQLite 存储层"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .config import DB_PATH
from .models import Item

_LOCK = threading.Lock()

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS items (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  source       TEXT NOT NULL,
  ext_id       TEXT NOT NULL,
  text_hash    TEXT,
  url          TEXT DEFAULT '',
  title        TEXT DEFAULT '',
  body         TEXT DEFAULT '',
  author       TEXT DEFAULT '',
  lang         TEXT DEFAULT 'zh',
  ts           TEXT DEFAULT '',
  collected_at TEXT,
  weight       REAL DEFAULT 1.0,
  heat         REAL DEFAULT 0.0,
  prior        REAL DEFAULT 0.45,
  meta         TEXT DEFAULT '{}',
  pain         REAL DEFAULT 0.0,
  pay          REAL DEFAULT 0.0,
  urgency      REAL DEFAULT 0.0,
  demand       REAL DEFAULT 0.0,
  signals      TEXT DEFAULT '[]',
  keywords     TEXT DEFAULT '[]',
  categories   TEXT DEFAULT '[]',
  UNIQUE(source, ext_id)
);
CREATE INDEX IF NOT EXISTS idx_items_demand ON items(demand DESC);
CREATE INDEX IF NOT EXISTS idx_items_ts     ON items(ts DESC);
CREATE INDEX IF NOT EXISTS idx_items_source ON items(source);

CREATE TABLE IF NOT EXISTS topics (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  slug        TEXT UNIQUE,
  label       TEXT,
  keywords    TEXT DEFAULT '[]',
  categories  TEXT DEFAULT '[]',
  item_count  INTEGER DEFAULT 0,
  sources     TEXT DEFAULT '{}',
  authors     INTEGER DEFAULT 0,
  score       REAL DEFAULT 0,
  pain        REAL DEFAULT 0,
  pay         REAL DEFAULT 0,
  urgency     REAL DEFAULT 0,
  diversity   REAL DEFAULT 0,
  heat        REAL DEFAULT 0,
  first_seen  TEXT DEFAULT '',
  last_seen   TEXT DEFAULT '',
  money       TEXT DEFAULT '',
  validation  TEXT DEFAULT '[]',
  samples     TEXT DEFAULT '[]',
  updated_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_topics_score ON topics(score DESC);

CREATE TABLE IF NOT EXISTS topic_items (
  topic_id INTEGER,
  item_id  INTEGER,
  relevance REAL DEFAULT 0,
  PRIMARY KEY (topic_id, item_id)
);

CREATE TABLE IF NOT EXISTS screens (
  hash  TEXT PRIMARY KEY,
  ts    TEXT,
  app   TEXT,
  title TEXT,
  text  TEXT
);

CREATE TABLE IF NOT EXISTS runs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at  TEXT,
  finished_at TEXT,
  stats       TEXT DEFAULT '{}',
  notes       TEXT DEFAULT ''
);
"""


def _migrate(con: sqlite3.Connection) -> None:
    """轻量迁移：老库补新增字段"""
    cols = {r["name"] for r in con.execute("PRAGMA table_info(items)")}
    if cols and "prior" not in cols:
        con.execute("ALTER TABLE items ADD COLUMN prior REAL DEFAULT 0.45")
    tcols = {r["name"] for r in con.execute("PRAGMA table_info(topics)")}
    if tcols and "diversity" not in tcols:
        con.execute("ALTER TABLE topics ADD COLUMN diversity REAL DEFAULT 0")


def connect(path: Path | str = DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    _migrate(con)
    return con


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def upsert_items(con: sqlite3.Connection, items: Iterable[Item]) -> int:
    """写入条目，按 (source, ext_id) 去重；已存在则更新评分字段。返回新增数"""
    rows = [it.to_row() for it in items]
    if not rows:
        return 0
    cols = [
        "source", "ext_id", "text_hash", "url", "title", "body", "author", "lang", "ts",
        "collected_at", "weight", "heat", "prior", "meta", "pain", "pay", "urgency", "demand",
        "signals", "keywords", "categories",
    ]
    added = 0
    with _LOCK, con:
        for r in rows:
            r.setdefault("collected_at", now_iso())
            sql = (
                f"INSERT INTO items ({','.join(cols)}) VALUES ({','.join('?' * len(cols))}) "
                "ON CONFLICT(source, ext_id) DO UPDATE SET "
                "pain=excluded.pain, pay=excluded.pay, urgency=excluded.urgency, "
                "demand=excluded.demand, signals=excluded.signals, keywords=excluded.keywords, "
                "categories=excluded.categories, heat=MAX(items.heat, excluded.heat), "
                "prior=excluded.prior, weight=excluded.weight, "
                "title=CASE WHEN excluded.title<>'' THEN excluded.title ELSE items.title END, "
                "body=CASE WHEN length(excluded.body)>length(items.body) THEN excluded.body ELSE items.body END"
            )
            cur = con.execute(sql, [r.get(c) for c in cols])
            if cur.lastrowid and cur.rowcount == 1:
                pass
            added += 1
    return added


def count_new_estimate(con: sqlite3.Connection, items: List[Item]) -> int:
    keys = [(it.source, it.ext_id) for it in items]
    n = 0
    for s, e in keys:
        row = con.execute("SELECT 1 FROM items WHERE source=? AND ext_id=? LIMIT 1", (s, e)).fetchone()
        if not row:
            n += 1
    return n


def fetch_items(
    con: sqlite3.Connection,
    where: str = "1=1",
    params: Sequence | tuple = (),
    limit: int = 5000,
) -> List[sqlite3.Row]:
    return list(con.execute(f"SELECT * FROM items WHERE {where} ORDER BY demand DESC LIMIT ?", (*params, limit)))


def fetch_items_since(con: sqlite3.Connection, days: int, limit: int = 20000) -> List[sqlite3.Row]:
    cut = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    return list(
        con.execute(
            "SELECT * FROM items WHERE (ts='' OR substr(ts,1,10)>=?) ORDER BY demand DESC LIMIT ?",
            (cut, limit),
        )
    )


def clear_topics(con: sqlite3.Connection) -> None:
    with _LOCK, con:
        con.execute("DELETE FROM topic_items")
        con.execute("DELETE FROM topics")


def save_topics(con: sqlite3.Connection, topics: List[Any]) -> None:
    import hashlib

    with _LOCK, con:
        for t in topics:
            con.execute(
                """INSERT INTO topics
                   (slug,label,keywords,categories,item_count,sources,authors,score,pain,pay,
                    urgency,diversity,heat,first_seen,last_seen,money,validation,samples,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(slug) DO UPDATE SET
                     label=excluded.label, keywords=excluded.keywords, categories=excluded.categories,
                     item_count=excluded.item_count, sources=excluded.sources, authors=excluded.authors,
                     score=excluded.score, pain=excluded.pain, pay=excluded.pay, urgency=excluded.urgency,
                     diversity=excluded.diversity, heat=excluded.heat, first_seen=excluded.first_seen,
                     last_seen=excluded.last_seen, money=excluded.money, validation=excluded.validation,
                     samples=excluded.samples, updated_at=excluded.updated_at""",
                (
                    t.slug, t.label,
                    json.dumps(t.keywords, ensure_ascii=False),
                    json.dumps(t.categories, ensure_ascii=False),
                    len(t.item_ids), json.dumps(t.sources, ensure_ascii=False), t.authors,
                    t.score, t.pain, t.pay, t.urgency, t.diversity, t.heat,
                    t.first_seen, t.last_seen, t.money,
                    json.dumps(t.validation, ensure_ascii=False),
                    json.dumps(t.samples, ensure_ascii=False),
                    now_iso(),
                ),
            )
            tid = con.execute("SELECT id FROM topics WHERE slug=?", (t.slug,)).fetchone()["id"]
            con.execute("DELETE FROM topic_items WHERE topic_id=?", (tid,))
            con.executemany(
                "INSERT OR IGNORE INTO topic_items(topic_id,item_id,relevance) VALUES (?,?,?)",
                [(tid, iid, 1.0) for iid in t.item_ids],
            )


def load_topics(con: sqlite3.Connection, limit: int = 60) -> List[Dict[str, Any]]:
    rows = con.execute("SELECT * FROM topics ORDER BY score DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("keywords", "categories", "sources", "validation", "samples"):
            try:
                d[k] = json.loads(d.get(k) or "[]")
            except Exception:
                d[k] = []
        out.append(d)
    return out


def topic_evidence(con: sqlite3.Connection, topic_id: int, limit: int = 8) -> List[sqlite3.Row]:
    return list(
        con.execute(
            """SELECT i.* FROM topic_items ti JOIN items i ON i.id=ti.item_id
               WHERE ti.topic_id=? ORDER BY i.demand DESC LIMIT ?""",
            (topic_id, limit),
        )
    )


def seen_screen(con: sqlite3.Connection, h: str, window: int = 400) -> bool:
    """判断屏幕哈希是否最近采集过"""
    row = con.execute("SELECT ts FROM screens WHERE hash=?", (h,)).fetchone()
    if row:
        return True
    n = con.execute("SELECT COUNT(*) c FROM screens").fetchone()["c"]
    if n > window * 2:
        with _LOCK, con:
            con.execute(
                "DELETE FROM screens WHERE hash IN (SELECT hash FROM screens ORDER BY ts ASC LIMIT ?)",
                (n - window,),
            )
    return False


def record_screen(con: sqlite3.Connection, h: str, app: str, title: str, text: str) -> None:
    with _LOCK, con:
        con.execute(
            "INSERT OR REPLACE INTO screens(hash,ts,app,title,text) VALUES (?,?,?,?,?)",
            (h, now_iso(), app, title, text),
        )


def start_run(con: sqlite3.Connection) -> int:
    with _LOCK, con:
        cur = con.execute("INSERT INTO runs(started_at,stats) VALUES (?, '{}')", (now_iso(),))
        return int(cur.lastrowid)


def finish_run(con: sqlite3.Connection, run_id: int, stats: Dict[str, Any], notes: str = "") -> None:
    with _LOCK, con:
        con.execute(
            "UPDATE runs SET finished_at=?, stats=?, notes=? WHERE id=?",
            (now_iso(), json.dumps(stats, ensure_ascii=False), notes, run_id),
        )


def stats(con: sqlite3.Connection) -> Dict[str, Any]:
    g = lambda q: con.execute(q).fetchone()[0]  # noqa: E731
    return {
        "items": g("SELECT COUNT(*) FROM items"),
        "topics": g("SELECT COUNT(*) FROM topics"),
        "screens": g("SELECT COUNT(*) FROM screens"),
        "last_run": (con.execute("SELECT finished_at FROM runs ORDER BY id DESC LIMIT 1").fetchone() or [None])[0],
        "by_source": {
            r["source"]: r["c"]
            for r in con.execute("SELECT source, COUNT(*) c FROM items GROUP BY source ORDER BY c DESC")
        },
    }
