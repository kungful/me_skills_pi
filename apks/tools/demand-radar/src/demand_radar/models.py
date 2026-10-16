"""数据模型"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class Item:
    """一条原始素材（一条评论 / 一个帖子 / 一屏文字）"""

    source: str                      # 采集器名，如 appstore / hackernews / android_screen
    ext_id: str                      # 源内唯一 id
    db_id: int = 0                   # 入库后的主键（仅内存用）
    title: str = ""
    body: str = ""
    url: str = ""
    author: str = ""
    lang: str = "zh"
    ts: str = ""                     # 事件时间 ISO8601
    weight: float = 1.0              # 源权重
    heat: float = 0.0                # 源自带热度（点赞/评分等，已归一化 0-1）
    prior: float = 0.45              # 源先验：这条素材本身隐含多少"需求意图"（0-1）
    meta: Dict[str, Any] = field(default_factory=dict)

    # ---- 评分结果 ----
    pain: float = 0.0
    pay: float = 0.0
    urgency: float = 0.0
    demand: float = 0.0
    signals: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return f"{self.title}\n{self.body}".strip()

    @property
    def key_id(self) -> int:
        return self.db_id or id(self)

    def dedupe_key(self) -> str:
        if self.ext_id:
            return f"{self.source}:{self.ext_id}"
        h = hashlib.sha1(self.text.encode("utf-8", "ignore")).hexdigest()[:20]
        return f"{self.source}:{h}"

    def to_row(self) -> Dict[str, Any]:
        d = asdict(self)
        d["text_hash"] = hashlib.sha1(self.text.encode("utf-8", "ignore")).hexdigest()[:24]
        for k in ("meta", "signals", "keywords", "categories"):
            d[k] = json.dumps(d[k], ensure_ascii=False)
        return d


@dataclass
class Topic:
    """聚合后的需求主题"""

    slug: str
    label: str
    keywords: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    item_ids: List[int] = field(default_factory=list)
    sources: Dict[str, int] = field(default_factory=dict)
    authors: int = 0
    score: float = 0.0
    pain: float = 0.0
    pay: float = 0.0
    urgency: float = 0.0
    diversity: float = 0.0
    heat: float = 0.0
    first_seen: str = ""
    last_seen: str = ""
    money: str = ""
    validation: List[str] = field(default_factory=list)
    samples: List[Dict[str, str]] = field(default_factory=list)
