"""App Store —— 差评就是"未被满足的需求"清单

思路：
  1) 用 iTunes Search API 按关键词找到相关 App
  2) 抓这些 App 的低分评论（抱怨）/ 全部评论里的"要是能…就好了"
  3) 只保留命中痛点句式的评论，避免噪音
"""
from __future__ import annotations

from typing import Dict, Iterable, List

from .. import textutil as tu
from .base import Collector, get

SEARCH = "https://itunes.apple.com/search"
REVIEWS = "https://itunes.apple.com/{cc}/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json"
LOOKUP = "https://itunes.apple.com/lookup"


class AppStore(Collector):
    name = "appstore"
    weight = 1.2

    def fetch(self) -> Iterable:
        terms: List[str] = self.cfg.get("search_terms") or []
        countries: List[str] = self.cfg.get("countries") or ["cn"]
        per_term = int(self.cfg.get("apps_per_term", 5))
        pages = int(self.cfg.get("review_pages", 1))
        max_rating = int(self.cfg.get("max_rating", 3))
        keep_all = bool(self.cfg.get("extract_wishes_from_all", True))

        for cc in countries:
            for term in terms:
                apps = self._search(term, cc, per_term)
                for app in apps:
                    yield from self._reviews(app, cc, pages, max_rating, keep_all, term)

    # ------------------------------------------------------------ 搜索
    def _search(self, term: str, cc: str, limit: int) -> List[Dict]:
        r = get(
            SEARCH,
            params={"term": term, "country": cc, "entity": "software", "limit": limit},
            sleep=1.1,
        )
        if not r:
            self.note(f"搜索失败：{term}/{cc}")
            return []
        try:
            res = (r.json() or {}).get("results") or []
        except Exception:
            return []
        out = []
        for a in res:
            if a.get("trackId"):
                out.append(
                    {
                        "id": a["trackId"],
                        "name": a.get("trackName") or "",
                        "seller": a.get("sellerName") or "",
                        "rating": a.get("averageUserRating"),
                        "rating_count": a.get("userRatingCount"),
                    }
                )
        return out

    # ------------------------------------------------------------ 评论
    def _reviews(
        self, app: Dict, cc: str, pages: int, max_rating: int, keep_all: bool, term: str
    ) -> Iterable:
        for page in range(1, pages + 1):
            url = REVIEWS.format(cc=cc, page=page, app_id=app["id"])
            r = get(url, sleep=1.2)
            if not r:
                break
            try:
                entries = ((r.json() or {}).get("feed") or {}).get("entry") or []
            except Exception:
                break
            if isinstance(entries, dict):
                entries = [entries]
            for e in entries:
                rating = _dig(e, "im:rating")
                if not rating:          # 第一条通常是 App 自身信息
                    continue
                try:
                    rating_i = int(rating)
                except Exception:
                    continue
                title = _lbl(e.get("title"))
                content = _lbl(e.get("content")) or ""
                body = f"{title}。{content}".strip()
                if len(body) < 10:
                    continue

                hits = tu.pain_hits(body)
                # 低分 = 抱怨；高分 = 只在提到"要是…就好了"时保留
                if rating_i <= max_rating:
                    pass
                elif keep_all and hits:
                    pass
                elif hits and any(t in ("求开发", "求方案", "付费意愿", "替代需求") for t, _, _ in hits):
                    pass
                else:
                    continue

                yield self.make(
                    ext_id=f"as:{cc}:{app['id']}:{_lbl(e.get('id')) or abs(hash(body))}",
                    title=f"[{app['name']}] {title}",
                    body=content[:1500],
                    url=_lbl((e.get("link") or {}).get("attributes", {}).get("href")) or f"https://apps.apple.com/{cc}/app/id{app['id']}",
                    author=_lbl((e.get("author") or {}).get("name")),
                    lang="zh" if cc in ("cn", "tw", "hk") else "en",
                    ts=_lbl(e.get("updated")) or "",
                    heat=min(1.0, (6 - rating_i) / 5.0 * 0.7 + 0.15),
                    prior=0.6 if rating_i <= max_rating else 0.7,
                    meta={
                        "app_id": app["id"],
                        "app": app["name"],
                        "rating": rating_i,
                        "country": cc,
                        "search_term": term,
                        "platform": "iOS",
                        "is_complaint": rating_i <= max_rating,
                    },
                )
            break  # 只翻第一页：Apple 对评论 RSS 限流较严


def _lbl(v) -> str:
    """iTunes JSON 的 label 包装"""
    if isinstance(v, dict):
        v = v.get("label", "")
    return str(v or "").strip()


def _dig(entry: dict, key: str) -> str:
    for k in (key, key.replace("im:", "im:")):
        if k in entry:
            return _lbl(entry[k])
    # 有些字段是 list
    return ""
