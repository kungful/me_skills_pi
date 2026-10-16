"""抖音热榜 —— 趋势信号"""
from __future__ import annotations

from typing import Iterable

from .base import Collector, get

API = "https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/word/"


class DouyinHot(Collector):
    name = "douyin_hot"
    weight = 0.95

    def fetch(self) -> Iterable:
        r = get(API, sleep=1.0, headers={"Referer": "https://www.douyin.com/"})
        if not r:
            self.note("请求失败")
            return
        try:
            rows = (r.json() or {}).get("word_list") or []
        except Exception:
            self.note("JSON 解析失败")
            return
        for i, row in enumerate(rows):
            word = (row.get("word") or "").strip()
            if not word:
                continue
            hv = float(row.get("hot_value") or 0)
            yield self.make(
                ext_id=f"dy:{word}",
                title=word,
                body="抖音热榜",
                url=f"https://www.douyin.com/search/{word}",
                heat=min(1.0, hv / 12_000_000) if hv else 0.3,
                prior=0.25,
                meta={"rank": i + 1, "hot_value": hv},
            )
