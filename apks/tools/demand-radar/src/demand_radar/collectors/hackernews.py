"""Hacker News（Algolia 公开 API）—— 英文世界里"我愿意付钱"的原始需求最密集的评论区"""
from __future__ import annotations

import re
from typing import Iterable

from .base import Collector, get

API = "https://hn.algolia.com/api/v1/search_by_date"

_TAG_RE = re.compile(r"<[^>]+>")
_ENT = {"&#x27;": "'", "&quot;": '"', "&amp;": "&", "&gt;": ">", "&lt;": "<", "&#x2F;": "/"}


def _clean_html(s: str) -> str:
    s = _TAG_RE.sub(" ", s or "")
    for k, v in _ENT.items():
        s = s.replace(k, v)
    return re.sub(r"\s+", " ", s).strip()


class HackerNews(Collector):
    name = "hackernews"
    weight = 1.15

    def fetch(self) -> Iterable:
        queries = self.cfg.get("queries") or ['"I wish there was"']
        tags = ",".join(self.cfg.get("tags") or ["comment"])
        per = int(self.cfg.get("per_query", 30))
        seen = set()
        for q in queries:
            r = get(
                API,
                params={"query": q, "tags": tags, "hitsPerPage": per},
                sleep=1.1,
            )
            if not r:
                self.note(f"查询失败：{q}")
                continue
            try:
                hits = (r.json() or {}).get("hits") or []
            except Exception:
                continue
            for h in hits:
                oid = h.get("objectID")
                if not oid or oid in seen:
                    continue
                seen.add(oid)
                body = _clean_html(h.get("comment_text") or h.get("story_text") or "")
                if len(body) < 40:
                    continue
                title = h.get("story_title") or h.get("title") or ""
                yield self.make(
                    ext_id=f"hn:{oid}",
                    title=title,
                    body=body[:2000],
                    url=f"https://news.ycombinator.com/item?id={oid}",
                    author=h.get("author") or "",
                    lang="en",
                    ts=h.get("created_at") or "",
                    heat=min(1.0, float(h.get("points") or 0) / 300 + 0.15),
                    prior=0.8,
                    meta={"query": q, "story_id": h.get("story_id")},
                )
