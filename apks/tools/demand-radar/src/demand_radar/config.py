"""需求雷达 · 全局配置与路径"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
REPORT_DIR = ROOT / "reports"
SCREEN_DIR = DATA_DIR / "screens"
LOG_DIR = DATA_DIR / "logs"

DB_PATH = DATA_DIR / "demand.db"

for _d in (DATA_DIR, REPORT_DIR, SCREEN_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=8)
def _load_yaml(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def sources_cfg() -> Dict[str, Any]:
    """采集源配置（改完 yaml 后需新进程或用 reload() 生效）"""
    return _load_yaml(str(CONFIG_DIR / "sources.yaml"))


def keywords_cfg() -> Dict[str, Any]:
    """识别词典配置"""
    return _load_yaml(str(CONFIG_DIR / "keywords.yaml"))


def reload_cfg() -> None:
    _load_yaml.cache_clear()


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)
