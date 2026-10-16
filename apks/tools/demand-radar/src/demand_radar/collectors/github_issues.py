"""GitHub Issues —— 开发者在公开场合说"我要这个功能"

这类需求的优势：需求描述精确、可验证、有真实使用者在等。
"""
from __future__ import annotations

from typing import Iterable

from .base import Collector, get

API = "https://api.github.com/search/issues"


class GithubIssues(Collector):
    name = "github_issues"
    weight = 1.0

    def _headers(self) -> dict:
        tok = (self.cfg.get("token") or "").strip()
        h = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if tok:
            h["Authorization"] = f"Bearer {tok}"
        return h

    def fetch(self) -> Iterable:
        queries = self.cfg.get("queries") or []
        per = int(self.cfg.get("per_query", 30))
        for q in queries:
            r = get(
                API,
                params={"q": q, "per_page": per, "sort": "created", "order": "desc"},
                headers=self._headers(),
                sleep=2.2,   # 未认证时限额 10 次/分钟
            )
            if not r:
                self.note(f"查询失败（可能是速率限制）：{q}")
                continue
            try:
                rows = (r.json() or {}).get("items") or []
            except Exception:
                continue
            for it in rows:
                title = (it.get("title") or "").strip()
                body = (it.get("body") or "")
                if not title:
                    continue
                yield self.make(
                    ext_id=f"gh:{it.get('id')}",
                    title=title,
                    body=body[:2500],
                    url=it.get("html_url") or "",
                    author=((it.get("user") or {}).get("login")) or "",
                    lang="en",
                    ts=it.get("created_at") or "",
                    prior=0.75,
                    heat=min(1.0, float((it.get("reactions") or {}).get("total_count") or 0) / 50
                             + float(it.get("comments") or 0) / 50
                             + 0.15),
                    meta={
                        "repo": "/".join((it.get("repository_url") or "").split("/")[-2:]),
                        "comments": it.get("comments"),
                        "labels": [l.get("name") for l in (it.get("labels") or [])][:5],
                        "query": q,
                    },
                )
