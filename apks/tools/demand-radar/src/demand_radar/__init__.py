"""需求雷达 · 自动挖掘市场需求的赚钱系统"""
from __future__ import annotations

import sys

# Windows 控制台默认 GBK，强制切 UTF-8，避免中文/emoji 打印报错
if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

__version__ = "1.0.0"
