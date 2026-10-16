"""安卓手机读屏采集器（USB 调试）

原理：
  1) adb 读取当前前台 App 的 UI 层级（uiautomator dump）→ 拿到屏幕上的全部文字
  2) 文字太少（Flutter/Canvas 类界面）时，截图 + Windows 自带 OCR 兜底
  3) 按"整屏"和"单条长文本"两个粒度产出素材，供需求引擎打分

两种用法：
  A. 人机协作（推荐，默认）：你自己正常刷手机，工具在后台把看到的需求自动入库
  B. 自动翻页（auto_swipe，默认关闭）：无人值守自动上滑。⚠ 有账号风控风险，自行评估

合规提醒：只采集你自己账号在当前屏幕上看到的公开内容，低频、自用、不对外分发。
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from ..config import SCREEN_DIR
from .base import Collector


def find_adb() -> str:
    """自动找 adb：PATH → Android SDK 常见安装位置"""
    found = shutil.which("adb")
    if found:
        return found
    cands: List[Path] = []
    for env in ("ANDROID_HOME", "ANDROID_SDK_ROOT", "LOCALAPPDATA", "USERPROFILE"):
        v = os.environ.get(env)
        if not v:
            continue
        p = Path(v)
        cands += [p / "platform-tools" / "adb.exe", p / "Android" / "Sdk" / "platform-tools" / "adb.exe"]
    cands += [
        Path("C:/Program Files/Android/Sdk/platform-tools/adb.exe"),
        Path("/c/Android/Sdk/platform-tools/adb.exe"),
    ]
    for c in cands:
        try:
            if c.is_file():
                return str(c)
        except OSError:
            continue
    return "adb"


ADB = find_adb()

_FOCUS_RE = re.compile(r"Window\{[^}]*?\s(u0\s+)?([a-zA-Z0-9_.]+)/([a-zA-Z0-9_.$]+)")
_PKG_RE = re.compile(r"mCurrentFocus=Window\{[^}]*?\s([a-zA-Z0-9_.]+)/")
_ACT_RE = re.compile(r"mCurrentFocus=Window\{[^}]*?\s[a-zA-Z0-9_.]+/([a-zA-Z0-9_.$]+)")

# 桌面 / 系统界面 / 输入法：这些屏幕没有需求信息，直接不采
_DENY_PKG = re.compile(
    r"launcher|systemui|com\.android\.|com\.vivo\.|com\.bbk\.|com\.iQOO\.|com\.qualcomm\.|"
    r"inputmethod|packageinstaller|permissioncontroller|providers\.settings|\.settings$|"
    r"com\.google\.android\.|keyguard|\.updater$|\.deskclock$|\.contacts$",
    re.I,
)


def adb(args: List[str], timeout: int = 25, binary: bool = False, serial: str = ""):
    """执行 adb 命令（Windows 下不经过 shell，避免路径被转换）

    serial 非空时会带 -s，避免 USB 与无线同时连着时报 "more than one device"。
    """
    cmd = [ADB] + (["-s", serial] if serial else []) + list(args)
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0,
        )
    except FileNotFoundError:
        raise RuntimeError(f"找不到 adb（试过 {ADB}），请安装 platform-tools 或设置 ANDROID_HOME")
    except subprocess.TimeoutExpired:
        return b"" if binary else ""
    if binary:
        return p.stdout
    return p.stdout.decode("utf-8", "ignore")


class AndroidScreen(Collector):
    name = "android_screen"
    weight = 1.3

    def __init__(self, cfg=None):
        super().__init__(cfg)
        self._size: Optional[Tuple[int, int]] = None
        self._device_checked = False
        self._device_ok = False
        self._serial: str = str(self.cfg.get("serial") or "")

    # ---------------------------------------------------------- 设备
    def _a(self, args: List[str], **kw):
        """带选中设备的 adb 调用"""
        return adb(args, serial=self._serial, **kw)

    def devices(self, include_wireless: bool = True) -> List[str]:
        try:
            out = adb(["devices"])
        except Exception as e:  # noqa: BLE001
            self.note(str(e))
            return []
        devs = []
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                s = parts[0]
                if include_wireless or ":" not in s:
                    devs.append(s)
        return devs

    def available(self) -> bool:
        if not self._device_checked:
            self._device_checked = True
            devs = self.devices()
            # 指定了 serial 就优先用它；否则优先无线（不用插线的那台）
            if self._serial and self._serial not in devs:
                self._serial = ""
            if not self._serial and devs:
                self._serial = next((d for d in devs if ":" in d), devs[0])
            self._device_ok = bool(devs)
            if not devs:
                self.note("没有检测到已授权的安卓设备（插上手机并允许 USB 调试即可）")
        return self._device_ok

    def refresh_device(self) -> bool:
        self._device_checked = False
        return self.available()

    def screen_size(self) -> Tuple[int, int]:
        if self._size:
            return self._size
        out = self._a(["shell", "wm", "size"])
        m = re.search(r"(\d+)x(\d+)", out or "")
        self._size = (int(m.group(1)), int(m.group(2))) if m else (1080, 2400)
        return self._size

    def foreground(self) -> Tuple[str, str]:
        """返回 (包名, Activity)"""
        for cmd in (
            ["shell", "dumpsys", "window", "displays"],
            ["shell", "dumpsys", "window"],
            ["shell", "dumpsys", "activity", "activities"],
        ):
            out = self._a(cmd)
            m = _FOCUS_RE.search(out or "") or _PKG_RE.search(out or "")
            if m:
                groups = m.groups()
                return groups[-2], groups[-1]
        return "", ""

    # ---------------------------------------------------------- 取文字
    def dump_ui_text(self) -> str:
        """uiautomator dump 取屏幕文字"""
        remote = "/sdcard/_demand_radar_dump.xml"
        self._a(["shell", "uiautomator", "dump", remote])
        xml = self._a(["exec-out", "cat", remote], timeout=25)
        if not xml or "<hierarchy" not in xml:
            return ""
        texts: List[str] = []
        for m in re.finditer(r'(?:text|content-desc)="([^"]{2,})"', xml):
            t = m.group(1).strip()
            if t and t not in texts:
                texts.append(t)
        return "\n".join(texts)

    def screenshot(self, path: Path) -> bool:
        raw = self._a(["exec-out", "screencap", "-p"], timeout=40, binary=True)
        if not raw or len(raw) < 1000:
            return False
        path.write_bytes(raw)
        return True

    def ocr(self, image: Path) -> str:
        """调用 Windows 自带 OCR"""
        ps1 = Path(__file__).resolve().parent.parent / "ocr_win.ps1"
        if not ps1.exists() or sys.platform != "win32":
            return ""
        try:
            p = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1), str(image)],
                capture_output=True,
                timeout=60,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return p.stdout.decode("utf-8", "ignore").strip()
        except Exception as e:  # noqa: BLE001
            self.note(f"OCR 失败：{e}")
            return ""

    def capture_once(self) -> Optional[dict]:
        """抓取当前这一屏，返回 {pkg, act, app, text, source} """
        pkg, act = self.foreground()
        # 桌面/系统界面/输入法 没有需求信息，直接跳过
        if pkg and _DENY_PKG.search(pkg) and not self.cfg.get("allow_system_apps"):
            return {"skipped": True, "pkg": pkg, "reason": "system-ui", "app": pkg}
        only = self.cfg.get("only_listed_apps", True)
        apps: Dict[str, str] = self.cfg.get("apps") or {}
        if only and pkg and pkg not in apps:
            return {"skipped": True, "pkg": pkg, "reason": "app-not-monitored", "app": pkg}

        text = self.dump_ui_text()
        method = "uiautomator"
        if len(text) < int(self.cfg.get("ocr_min_chars", 40)) and self.cfg.get("ocr_fallback", True):
            img = SCREEN_DIR / "_latest.png"
            if self.screenshot(img):
                ocr_text = self.ocr(img)
                if len(ocr_text) > len(text):
                    text = ocr_text
                    method = "ocr"
                if not self.cfg.get("save_screenshots"):
                    try:
                        img.unlink()
                    except OSError:
                        pass
        if not text.strip():
            return None
        return {
            "pkg": pkg,
            "act": act,
            "app": apps.get(pkg, pkg or "unknown"),
            "text": text,
            "method": method,
        }

    # ---------------------------------------------------------- 产出
    def _split_lines(self, text: str, min_len: int = 30) -> List[str]:
        out = []
        for line in text.split("\n"):
            line = line.strip()
            if len(line) >= min_len:
                out.append(line)
        return out

    def emit_screen(self, cap: dict) -> List:
        text: str = cap["text"]
        h = hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()[:20]
        items = [
            self.make(
                ext_id=f"as-ui:{cap['pkg']}:{h}",
                title=f"{cap['app']} 屏幕内容",
                body=text[:4000],
                url="",
                author=f"screen:{cap['app']}",
                ts="",
                heat=0.55,
                prior=0.5,
                meta={"pkg": cap["pkg"], "activity": cap["act"], "method": cap["method"], "kind": "screen"},
            )
        ]
        # 长文本节点单独成条目，提升单条信号的分辨率
        for i, line in enumerate(self._split_lines(text)[: int(self.cfg.get("max_node_items", 10))]):
            ih = hashlib.sha1(line.encode("utf-8", "ignore")).hexdigest()[:16]
            items.append(
                self.make(
                    ext_id=f"as-node:{cap['pkg']}:{ih}",
                    title=f"{cap['app']} · 单条",
                    body=line,
                    author=f"screen:{cap['app']}",
                    heat=0.5,
                    prior=0.5,
                    meta={"pkg": cap["pkg"], "kind": "node", "idx": i},
                )
            )
        return items

    def fetch(self) -> Iterable:
        listen = float(self.cfg.get("listen_seconds") or 0)
        if self.cfg.get("auto_swipe"):
            yield from self._auto_swipe_loop()
            return
        if listen <= 0:
            cap = self.capture_once()
            if cap and not cap.get("skipped"):
                yield from self.emit_screen(cap)
            return
        # 有界监听：listen 秒内不断抓屏（同一屏自动去重）
        deadline = time.time() + listen
        seen = set()
        while time.time() < deadline:
            cap = self.capture_once()
            if cap and not cap.get("skipped"):
                key = hashlib.sha1(cap["text"].encode("utf-8", "ignore")).hexdigest()[:16]
                if key not in seen:
                    seen.add(key)
                    yield from self.emit_screen(cap)
            time.sleep(float(self.cfg.get("poll_seconds", 4.0)))

    def _auto_swipe_loop(self) -> Iterable:
        """⚠ 自动上滑翻页（无人值守）。请自行评估账号风控风险。"""
        w, h = self.screen_size()
        x, y1, y2 = w // 2, int(h * 0.75), int(h * 0.3)
        times = int(self.cfg.get("auto_swipe_times", 10))
        for i in range(times):
            cap = self.capture_once()
            if cap and not cap.get("skipped"):
                yield from self.emit_screen(cap)
            adb(["shell", "input", "swipe", str(x), str(y1), str(x), str(y2), "500"], serial=self._serial)
            time.sleep(2.0 + (i % 3))
