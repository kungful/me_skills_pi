"""百度搜索下拉词 —— 最真实的需求信号
用户真的在搜什么，就说明市场真的缺什么。
"""
from __future__ import annotations

from typing import Iterable, List

from ..config import keywords_cfg
from .base import Collector, get

API = "https://www.baidu.com/sugrec"


class BaiduSuggest(Collector):
    name = "baidu_sug"
    weight = 1.25

    def _seeds(self) -> List[str]:
        seeds: List[str] = list(self.cfg.get("seeds") or [])
        if not seeds:
            # 用领域词典自动生成种子词
            for dom in (keywords_cfg().get("domains") or []):
                k = dom.get("k") or []
                if k:
                    seeds.append(str(k[0]))
        extra = self.cfg.get("extra_seeds") or []
        seeds.extend(str(x) for x in extra)
        # 去重保序
        seen, out = set(), []
        for s in seeds:
            if s and s not in seen:
                seen.add(s)
                out.append(s)
        return out[: int(self.cfg.get("max_seeds", 60))]

    def fetch(self) -> Iterable:
        limit = int(self.cfg.get("suggestions_per_seed", 8))
        for seed in self._seeds():
            r = get(API, params={"prod": "pc", "wd": seed}, sleep=0.7)
            if not r:
                self.note(f"种子失败：{seed}")
                continue
            try:
                data = r.json()
            except Exception:
                continue
            g = data.get("g") or []
            for i, row in enumerate(g[:limit]):
                q = (row.get("q") or "").strip()
                if not q:
                    continue
                yield self.make(
                    ext_id=f"sug:{seed}:{q}",
                    title=q,
                    body=f"搜索联想词，种子「{seed}」排位 {i + 1}",
                    url=f"https://www.baidu.com/s?wd={q}",
                    heat=min(1.0, 0.9 - i * 0.08),
                    prior=0.75,
                    meta={"seed": seed, "rank": i + 1, "kind": "search_suggestion"},
                )
