"""微博搜索（需自己登录后的 Cookie）—— 中文真人发牢骚最集中的地方

⚠ 合规提醒：
  - 必须使用你本人账号的 cookie，只做关键词检索
  - 保持低频（>= 3 秒/请求），不要批量抓取用户隐私数据
  - 采集结果仅用于趋势分析，不要对外分发原始数据
"""
from __future__ import annotations

import re
from typing import Iterable

from .base import Collector, get

API = "https://m.weibo.cn/api/container/getIndex"

_TAG_RE = re.compile(r"<[^>]+>")


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", s or "")).strip()


class Weibo(Collector):
    name = "weibo"
    weight = 1.1

    def available(self) -> bool:
        if not (self.cfg.get("cookie") or "").strip():
            self.note("未配置 cookie，跳过")
            return False
        return True

    def fetch(self) -> Iterable:
        cookie = self.cfg["cookie"].strip()
        headers = {
            "Cookie": cookie,
            "Referer": "https://m.weibo.cn/",
            "X-Requested-With": "XMLHttpRequest",
            "MWeibo-Pwa": "1",
        }
        per = int(self.cfg.get("per_query", 20))
        for q in self.cfg.get("queries") or []:
            r = get(
                API,
                params={
                    "containerid": f"100103type=1&q={q}",
                    "page_type": "searchall",
                },
                headers=headers,
                sleep=3.0,
            )
            if not r:
                self.note(f"查询失败：{q}")
                continue
            try:
                cards = ((r.json() or {}).get("data") or {}).get("cards") or []
            except Exception:
                continue
            n = 0
            for card in cards:
                for grp in card.get("card_group") or [card]:
                    mblog = grp.get("mblog")
                    if not mblog:
                        continue
                    n += 1
                    if n > per:
                        break
                    text = _clean(mblog.get("text"))
                    if len(text) < 8:
                        continue
                    uid = mblog.get("user") or {}
                    yield self.make(
                        ext_id=f"wb:{mblog.get('id')}",
                        title="",
                        body=text[:1500],
                        url=f"https://m.weibo.cn/detail/{mblog.get('id')}",
                        author=uid.get("screen_name") or "",
                        ts=mblog.get("created_at") or "",
                        heat=min(1.0, float(mblog.get("reposts_count") or 0) / 100 + 0.25),
                        prior=0.7,
                        meta={"query": q, "comments": mblog.get("comments_count")},
                    )
