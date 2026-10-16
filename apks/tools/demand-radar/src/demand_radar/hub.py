"""调度中枢：采集 → 打分 → 聚合 → 报告"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from . import db
from . import score as scorer
from . import textutil as tu
from .collectors import build
from .config import SCREEN_DIR, sources_cfg
from .models import Item


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ------------------------------------------------------------------ 采集

def collect(
    only: Sequence[str] | None = None,
    *,
    quiet: bool = False,
    listen_seconds: float = 0.0,
) -> Dict[str, Any]:
    cfg = sources_cfg()
    g = cfg.get("global") or {}
    cols = build(cfg.get("sources") or {}, list(only) if only else None)
    if not cols:
        _log("没有启用的采集源（检查 config/sources.yaml）")
        return {"collectors": {}, "items": 0}

    con = db.connect()
    run_id = db.start_run(con)
    total_cap = int(g.get("max_total_items", 800))
    report: Dict[str, Any] = {}
    all_items: List[Item] = []
    t0 = time.time()

    for c in cols:
        if isinstance(c, type(None)):
            continue
        if listen_seconds and c.name == "android_screen":
            c.cfg["listen_seconds"] = listen_seconds
        if not quiet:
            _log(f"采集：{c.name} …")
        items = c.run()
        for it in items:
            scorer.score_item(it)
        n = db.upsert_items(con, items)
        all_items.extend(items)
        report[c.name] = {"fetched": len(items), "notes": c.notes[:5]}
        if not quiet:
            extra = f"  ⚠ {c.notes[0]}" if c.notes else ""
            _log(f"  └ {len(items)} 条{extra}")
        if len(all_items) >= total_cap:
            _log(f"达到单次上限 {total_cap} 条，停止采集")
            break

    # 记录屏幕（供去重与人工复核）
    for it in all_items:
        if it.source == "android_screen" and it.meta.get("kind") == "screen":
            db.record_screen(con, it.ext_id, it.meta.get("pkg", ""), it.title, it.body)

    stats = {k: v["fetched"] for k, v in report.items()}
    db.finish_run(con, run_id, {"collected": stats, "elapsed": round(time.time() - t0, 1)})
    if not quiet:
        _log(f"采集完成：{len(all_items)} 条，用时 {time.time() - t0:.1f}s")
    report["items"] = len(all_items)
    report["run_id"] = run_id
    return report


# ------------------------------------------------------------------ 打分/聚合

def load_models(con, days: int = 90, limit: int = 20000) -> List[Item]:
    rows = db.fetch_items_since(con, days, limit)
    out: List[Item] = []
    for r in rows:
        it = Item(
            source=r["source"],
            ext_id=r["ext_id"],
            title=r["title"] or "",
            body=r["body"] or "",
            url=r["url"] or "",
            author=r["author"] or "",
            lang=r["lang"] or "zh",
            ts=r["ts"] or "",
            weight=float(r["weight"] or 1.0),
            heat=float(r["heat"] or 0.0),
            prior=float(r["prior"] if r["prior"] is not None else 0.45),
        )
        it.db_id = int(r["id"])
        it.pain = float(r["pain"] or 0)
        it.pay = float(r["pay"] or 0)
        it.urgency = float(r["urgency"] or 0)
        it.demand = float(r["demand"] or 0)
        it.signals = json.loads(r["signals"] or "[]")
        it.keywords = json.loads(r["keywords"] or "[]")
        it.categories = json.loads(r["categories"] or "[]")
        out.append(it)
    return out


def analyze(days: int = 90, quiet: bool = False) -> List[Any]:
    con = db.connect()
    cfg = sources_cfg()
    days = int((cfg.get("global") or {}).get("recency_days", days))

    rows = db.fetch_items_since(con, days, 20000)
    if not rows:
        _log("库里还没有数据，先运行 collect")
        return []

    # 重新打分（词典更新后能立刻生效）
    models: List[Item] = []
    for r in rows:
        it = Item(
            source=r["source"], ext_id=r["ext_id"], title=r["title"] or "", body=r["body"] or "",
            url=r["url"] or "", author=r["author"] or "", lang=r["lang"] or "zh", ts=r["ts"] or "",
            weight=float(r["weight"] or 1.0), heat=float(r["heat"] or 0.0),
            prior=float(r["prior"] if r["prior"] is not None else 0.45),
        )
        scorer.score_item(it)
        it.db_id = int(r["id"])
        models.append(it)

    with con:
        con.executemany(
            "UPDATE items SET demand=?,pain=?,pay=?,urgency=?,signals=?,keywords=?,categories=?,"
            "prior=? WHERE id=?",
            [
                (
                    it.demand, it.pain, it.pay, it.urgency,
                    json.dumps(it.signals, ensure_ascii=False),
                    json.dumps(it.keywords, ensure_ascii=False),
                    json.dumps(it.categories, ensure_ascii=False),
                    it.prior,
                    it.db_id,
                )
                for it in models
            ],
        )

    topics = scorer.build_topics(models)
    # 过滤掉证据太少的主题
    min_items = int((cfg.get("global") or {}).get("min_topic_items", scorer.min_topic_items()))
    topics = scorer.filter_topics(topics, min_items)
    db.clear_topics(con)
    db.save_topics(con, topics)
    if not quiet:
        _log(f"聚合完成：{len(models)} 条素材 → {len(topics)} 个需求主题")
    return topics


# ------------------------------------------------------------------ 一键全流程

def run_all(only: Sequence[str] | None = None, days: int = 90, quiet: bool = False) -> Dict[str, Any]:
    from . import report as rp

    c = collect(only, quiet=quiet)
    topics = analyze(days, quiet=quiet)
    files = rp.write_reports(topics) if topics else {}
    if not quiet and files:
        _log(f"报告已生成：{files.get('md')}")
    return {"collect": c, "topics": len(topics), "reports": files}


# ------------------------------------------------------------------ 手机监听

def watch(interval: float = 4.0, duration: float = 0.0, only_apps: Sequence[str] | None = None) -> None:
    """监听模式：你刷手机，它自动把屏幕上的需求存进库。

    Ctrl+C 结束；结束后自动做一次聚合分析。
    """
    from .collectors.android_screen import AndroidScreen

    cfg = (sources_cfg().get("sources") or {}).get("android_screen") or {}
    cfg = dict(cfg)
    cfg["only_listed_apps"] = True
    cfg["poll_seconds"] = interval
    col = AndroidScreen(cfg)

    if not col.refresh_device():
        _log("未检测到手机。请插上 USB、开启「开发者选项 → USB 调试」并允许本机调试。")
        _log("提示：如果手机弹窗没出现，试试 adb kill-server && adb devices")
        return

    pkg, act = col.foreground()
    _log(f"已连接设备，当前前台：{pkg or '未知'}")
    _log("开始监听屏幕（你正常刷手机即可，Ctrl+C 结束）…")

    con = db.connect()
    t0 = time.time()
    seen = set()
    saved = 0
    skipped: Dict[str, int] = {}
    last_state = ""
    misses = 0
    try:
        while True:
            if duration and time.time() - t0 > duration:
                break
            cap = col.capture_once()
            if cap and not cap.get("skipped"):
                import hashlib

                h = hashlib.sha1(cap["text"].encode("utf-8", "ignore")).hexdigest()[:20]
                if h not in seen:
                    seen.add(h)
                    items = col.emit_screen(cap)
                    for it in items:
                        scorer.score_item(it)
                    db.upsert_items(con, items)
                    db.record_screen(con, h, cap["pkg"], cap["app"], cap["text"])
                    top = max((i.demand for i in items), default=0)
                    flag = "  ★需求信号" if top >= 25 else ""
                    _log(f"  [{cap['app']}] 抓到一屏 {len(items)} 条（最高分 {top:.0f}）{flag}")
                    saved += 1
                    last_state = ""
                else:
                    last_state = ""
            else:
                reason = (cap or {}).get("reason", "no-text")
                skipped[reason] = skipped.get(reason, 0) + 1
                if reason == "app-not-monitored":
                    p = (cap or {}).get("pkg") or "?"
                    tip = (
                        f"当前 App（{p}）不在监听名单，已跳过。要采它："
                        f"config/sources.yaml → android_screen → apps 里加上「{p}: 名字」。"
                    )
                elif reason == "system-ui":
                    tip = "当前在桌面/系统界面，已跳过。请打开小红书/闲鱼/抖音等具体内容页。"
                else:
                    tip = "这一屏没抓到文字，已跳过。"
                if tip != last_state:
                    _log(tip)
                    last_state = tip
                if reason == "no-text":
                    misses += 1
                    if misses in (5, 20, 60):
                        _log("连续多次没抓到文字，手机可能已断开或屏幕已锁。")
                        _log("排查：adb kill-server && adb devices（或点亮屏幕后重试）")
                else:
                    misses = 0
            time.sleep(interval)
    except KeyboardInterrupt:
        _log("收到中断，停止监听")
    finally:
        _log(f"监听结束，共采集 {saved} 屏")
        if skipped:
            parts = "、".join(f"{k}×{v}" for k, v in skipped.items())
            _log(f"  跳过统计：{parts}")
        if saved:
            analyze(quiet=False)
        elif skipped.get("app-not-monitored"):
            _log("没采到东西：全程停留在未监听的 App。先把要采的 App 加进 apps 名单。")
        elif skipped:
            _log("没采到东西：可能是页面以图片为主，或一直在系统界面。")


def phone_status() -> Dict[str, Any]:
    from .collectors.android_screen import AndroidScreen

    col = AndroidScreen({"apps": {}})
    devs = col.devices()
    info: Dict[str, Any] = {"devices": devs, "connected": bool(devs), "wireless": any(":" in d for d in devs)}
    if devs:
        # 走 collector 自己的 _a()，它会带上 -s，避免 USB+无线同时连着时报错
        col.available()                       # 触发选定设备
        info["serial"] = col._serial          # noqa: SLF001
        info["brand"] = col._a(["shell", "getprop", "ro.product.brand"]).strip()
        info["android"] = col._a(["shell", "getprop", "ro.build.version.release"]).strip()
        info["size"] = "x".join(map(str, col.screen_size()))
    return info
