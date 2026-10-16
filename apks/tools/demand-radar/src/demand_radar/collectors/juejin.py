"""掘金推荐流/热榜 —— 中文技术圈的真实痛点讨论"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from .base import Collector, post

API = "https://api.juejin.cn/recommend_api/v1/article/recommend_all_feed"

CATEGORIES = [
    ("6809637769959178254", "后端"),
    ("6809637767543259144", "前端"),
    ("6809637772874219534", "Android"),
    ("6809637771511070734", "iOS"),
    ("6809637773935378440", "人工智能"),
]


class Juejin(Collector):
    name = "juejin"
    weight = 0.9

    def fetch(self) -> Iterable:
        limit = int(self.cfg.get("per_feed", 20))
        # 用 sort_type=200（热度）拉几个分类
        for cate_id, cname in CATEGORIES:
            r = post(
                API,
                json_body={
                    "id_type": 2,
                    "client_type": 2608,
                    "sort_type": 200,
                    "cursor": "0",
                    "limit": limit,
                },
                sleep=1.0,
            )
            if not r:
                self.note(f"请求失败：{cname}")
                continue
            try:
                rows = (r.json() or {}).get("data") or []
            except Exception:
                continue
            for row in rows:
                ii = row.get("item_info") or {}
                ai = ii.get("article_info") or {}
                title = (ai.get("title") or "").strip()
                if not title:
                    continue
                aid = ai.get("article_id") or title
                tags = [t.get("tag_name") for t in (ii.get("tags") or []) if t.get("tag_name")]
                yield self.make(
                    ext_id=f"jj:{aid}",
                    title=title,
                    body=(ai.get("brief_content") or "")[:800],
                    url=f"https://juejin.cn/post/{aid}",
                    author=(ii.get("author_user_info") or {}).get("user_name", ""),
                    ts=_ts(ai.get("ctime")),
                    prior=0.35,
                    heat=min(1.0, float(ai.get("view_count") or 0) / 50000
                             + float(ai.get("digg_count") or 0) / 1000),
                    meta={
                        "category": cname,
                        "tags": tags[:5],
                        "digg": ai.get("digg_count"),
                        "comments": ai.get("comment_count"),
                        "views": ai.get("view_count"),
                    },
                )


def _ts(v) -> str:
    try:
        return datetime.fromtimestamp(int(v), tz=timezone.utc).isoformat() if v else ""
    except Exception:
        return ""
