"""采集器注册表"""
from __future__ import annotations

from typing import Any, Dict, List

from .android_screen import AndroidScreen
from .appstore import AppStore
from .baidu_hot import BaiduHot
from .baidu_sug import BaiduSuggest
from .base import Collector, get, session
from .douyin_hot import DouyinHot
from .github_issues import GithubIssues
from .hackernews import HackerNews
from .juejin import Juejin
from .rss import Rss
from .weibo import Weibo

CLASSES = [
    AndroidScreen,   # 手机读屏（权重最高）
    AppStore,
    BaiduSuggest,
    HackerNews,
    Weibo,
    BaiduHot,
    GithubIssues,
    DouyinHot,
    Juejin,
    Rss,
]

REGISTRY: Dict[str, type] = {c.name: c for c in CLASSES}


def build(sources: Dict[str, Any], only: List[str] | None = None) -> List[Collector]:
    """按配置实例化采集器"""
    out: List[Collector] = []
    for name, cls in REGISTRY.items():
        cfg = sources.get(name) or {}
        if only and name not in only:
            continue
        if not cfg.get("enabled", False):
            continue
        out.append(cls(cfg))
    return out


def all_names() -> List[str]:
    return list(REGISTRY.keys())


__all__ = ["Collector", "REGISTRY", "build", "all_names", "get", "session", "CLASSES"]
