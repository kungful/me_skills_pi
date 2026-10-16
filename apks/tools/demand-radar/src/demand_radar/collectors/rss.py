"""通用 RSS / Atom 采集器（中文科技与独立开发者媒体）"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Iterable, List

from .base import Collector, get

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}


class Rss(Collector):
    name = "rss"
    weight = 0.8

    def fetch(self) -> Iterable:
        feeds: List[dict] = self.cfg.get("feeds") or []
        per_feed = int(self.cfg.get("per_feed", 25))
        for f in feeds:
            if f.get("enabled") is False:
                continue
            name, url = f.get("name") or "rss", f.get("url")
            if not url:
                continue
            r = get(url, sleep=1.0, allow_html=False)
            if not r:
                self.note(f"源失败：{name}")
                continue
            try:
                root = ET.fromstring(r.content)
            except Exception:
                self.note(f"XML 解析失败：{name}")
                continue
            items = root.iter("item")
            is_atom = False
            if not list(root.iter("item")):
                items = root.iter("{http://www.w3.org/2005/Atom}entry")
                is_atom = True
            n = 0
            for node in items:
                if n >= per_feed:
                    break
                n += 1
                title = _txt(node, "title")
                link = _txt(node, "link")
                if not link and is_atom:
                    for ln in node.findall("atom:link", NS):
                        if ln.get("rel") in (None, "alternate"):
                            link = ln.get("href") or ""
                            break
                body = _txt(node, "description") or _txt(node, "summary") or _txt(node, "content")
                body = _txt(node, "encoded") or body
                date = _txt(node, "pubDate") or _txt(node, "updated") or _txt(node, "published")
                author = _txt(node, "creator") or _txt(node, "author")
                if not title:
                    continue
                yield self.make(
                    ext_id=f"rss:{name}:{link or title}",
                    title=re.sub(r"\s+", " ", title).strip(),
                    body=re.sub(r"\s+", " ", body or "").strip()[:1500],
                    url=link,
                    author=author,
                    ts=_iso(date),
                    lang="zh",
                    heat=0.3,
                    prior=0.3,
                    meta={"feed": name},
                )


def _txt(node, tag: str) -> str:
    for t in (tag, f"{{{NS.get('dc')}}}{tag}", f"{{{NS.get('content')}}}{tag}"):
        el = node.find(t)
        if el is not None and (el.text or ""):
            return el.text or ""
    return ""


def _iso(s: str) -> str:
    if not s:
        return ""
    from email.utils import parsedate_to_datetime

    try:
        return parsedate_to_datetime(s).isoformat()
    except Exception:
        pass
    try:
        from datetime import datetime

        return datetime.fromisoformat(s.replace("Z", "+00:00")).isoformat()
    except Exception:
        return ""
