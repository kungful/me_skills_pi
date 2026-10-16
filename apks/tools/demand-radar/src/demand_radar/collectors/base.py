"""采集器基类与 HTTP 工具"""
from __future__ import annotations

import random
import time
from typing import Any, Dict, Iterable, List, Optional

import requests

from ..models import Item

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

_session: Optional[requests.Session] = None


def session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update(
            {
                "User-Agent": UA,
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept": "application/json, text/plain, text/xml, */*",
            }
        )
        _session = s
    return _session


def get(
    url: str,
    *,
    params: Dict[str, Any] | None = None,
    headers: Dict[str, str] | None = None,
    timeout: int = 20,
    retries: int = 2,
    sleep: float = 0.8,
    allow_html: bool = False,
) -> Optional[requests.Response]:
    """带重试与礼貌间隔的 GET；失败返回 None（不抛异常，保证单源故障不中断全局）"""
    for attempt in range(retries + 1):
        try:
            r = session().get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code == 200:
                if not allow_html and "text/html" in (r.headers.get("Content-Type") or "") and "json" not in url:
                    # 有些接口返回 html 说明被挡了
                    if not (r.text or "").lstrip().startswith(("{", "<?xml", "<rss")):
                        return None
                return r
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(sleep * (attempt + 1) * 2 + random.random())
                continue
            return None
        except Exception:
            time.sleep(sleep * (attempt + 1) + random.random() * 0.5)
    return None


def post(
    url: str,
    *,
    json_body: Dict[str, Any] | None = None,
    params: Dict[str, Any] | None = None,
    headers: Dict[str, str] | None = None,
    timeout: int = 20,
    retries: int = 2,
    sleep: float = 0.8,
) -> Optional[requests.Response]:
    """带重试的 POST（返回 None 表示失败）"""
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    for attempt in range(retries + 1):
        try:
            r = session().post(url, json=json_body, params=params, headers=h, timeout=timeout)
            if r.status_code == 200:
                return r
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(sleep * (attempt + 1) * 2 + random.random())
                continue
            return None
        except Exception:
            time.sleep(sleep * (attempt + 1) + random.random() * 0.5)
    return None


class Collector:
    """所有采集器的基类

    子类实现 fetch() -> Iterable[Item]
    """

    name: str = "base"
    weight: float = 1.0
    enabled: bool = True

    def __init__(self, cfg: Dict[str, Any] | None = None) -> None:
        self.cfg: Dict[str, Any] = cfg or {}
        self.weight = float(self.cfg.get("weight", self.weight))
        self.max_items = int(self.cfg.get("max_items", 100))
        self.notes: List[str] = []

    # ---- 生命周期 ----
    def available(self) -> bool:
        """前置条件是否满足（如手机是否连着）"""
        return True

    def fetch(self) -> Iterable[Item]:  # pragma: no cover
        raise NotImplementedError

    # ---- 工具 ----
    def make(self, ext_id: str, **kw: Any) -> Item:
        kw.setdefault("source", self.name)
        kw.setdefault("weight", self.weight)
        return Item(ext_id=str(ext_id), **kw)

    def note(self, msg: str) -> None:
        self.notes.append(msg)

    def run(self) -> List[Item]:
        if not self.enabled:
            return []
        if not self.available():
            self.note("跳过：前置条件不满足")
            return []
        try:
            items = list(self.fetch())
        except Exception as e:  # noqa: BLE001
            self.note(f"异常：{type(e).__name__}: {e}")
            return []
        seen = set()
        out = []
        for it in items:
            k = it.dedupe_key()
            if k in seen:
                continue
            seen.add(k)
            out.append(it)
            if len(out) >= self.max_items:
                break
        return out
