"""百度热搜榜 —— 趋势/风口信号"""
from __future__ import annotations

from typing import Iterable, List

from .base import Collector, get

API = "https://top.baidu.com/api/board"

TAB_CN = {
    "realtime": "实时热点",
    "novel": "小说榜",
    "movie": "电影榜",
    "teleplay": "电视剧榜",
    "car": "汽车榜",
    "game": "游戏榜",
    "city": "城市榜",
}


class BaiduHot(Collector):
    name = "baidu_hot"
    weight = 1.0

    def fetch(self) -> Iterable:
        tabs: List[str] = self.cfg.get("tabs") or ["realtime"]
        out = []
        for tab in tabs:
            r = get(API, params={"platform": "wise", "tab": tab}, sleep=1.2)
            if not r:
                self.note(f"{tab}: 请求失败")
                continue
            try:
                data = r.json()
            except Exception:
                self.note(f"{tab}: JSON 解析失败")
                continue
            cards = (data.get("data") or {}).get("cards") or []
            for card in cards:
                for wrap in card.get("content") or []:
                    for row in wrap.get("content") or []:
                        word = (row.get("word") or "").strip()
                        if not word:
                            continue
                        hot = float(row.get("hotScore") or row.get("hot") or 0)
                        desc = row.get("desc") or ""
                        yield self.make(
                            ext_id=f"baidu:{tab}:{row.get('url') or word}",
                            title=word,
                            body=f"[{TAB_CN.get(tab, tab)}] {desc} {row.get('hotTag') or ''}".strip(),
                            url=row.get("url") or "",
                            ts="",
                            heat=min(1.0, hot / 3_000_000) if hot else 0.35,
                            prior=0.25,
                            meta={"tab": tab, "rank": row.get("index")},
                        )
