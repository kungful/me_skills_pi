#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
qq_ctl.py - QQ NT (Windows) 外部 GUI 自动化核心库

设计原则（重要，改动前先读 SKILL.md 的"风险真相"）：
  1. 只用 OS 公开接口：窗口消息 / SendInput 鼠标键盘 / 剪贴板。
     不注入 DLL、不 ReadProcessMemory、不 Hook、不驱动、不碰协议。
  2. 所有动作前可 dry_run，真发必须显式 arm。
  3. 频率硬限流：任何高频批量动作都会被拒。
  4. 一切落日志，出问题能复盘。

依赖：pywin32, pillow (可选: pyperclip)
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import random
import re
import sys
import time
from datetime import datetime, date

try:
    import win32api
    import win32clipboard
    import win32con
    import win32gui
    import win32process
except ImportError:
    sys.exit("需要 pywin32:  pip install pywin32")

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(HERE, "logs")
STATE_PATH = os.path.join(HERE, "state.json")
STOP_FLAG = os.path.join(HERE, "STOP")          # 存在此文件 = 立刻停手

# ---------------------------------------------------------------- DPI / 环境
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)   # PER_MONITOR_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32
# SendInput 结构体（比 mouse_event / keybd_event 更原生，走同一条输入栈）
ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wt.DWORD), ("wParamL", wt.WORD), ("wParamH", wt.WORD)]


class _INPUTunion(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("union", _INPUTunion)]


INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008
MOUSEEVENTF_MOVE, MOUSEEVENTF_ABSOLUTE = 0x0001, 0x8000
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP = 0x0008, 0x0010
MOUSEEVENTF_WHEEL = 0x0800

# ---------------------------------------------------------------- 基础输入层


def _send(*inputs):
    n = len(inputs)
    arr = (INPUT * n)(*inputs)
    sent = user32.SendInput(n, ctypes.byref(arr), ctypes.sizeof(INPUT))
    if sent != n:
        raise OSError("SendInput 被拦截或失败: %d/%d (err=%d)"
                      % (sent, n, ctypes.get_last_error()))


def _mouse_input(flags, dx=0, dy=0, data=0):
    return INPUT(type=INPUT_MOUSE, union=_INPUTunion(
        mi=MOUSEINPUT(dx=dx, dy=dy, mouseData=data, dwFlags=flags, time=0, dwExtraInfo=0)))


def _key_input(vk=0, scan=0, flags=0):
    return INPUT(type=INPUT_KEYBOARD, union=_INPUTunion(
        ki=KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)))


def human_delay(lo=0.05, hi=0.18):
    """人类节奏抖动。不是"反检测"，是让自动化不会因为过快而误点/丢键。"""
    time.sleep(random.uniform(lo, hi))


# ---- 鼠标
def cursor_pos():
    return win32gui.GetCursorPos()


def move_to(x, y, duration=None):
    """贝塞尔曲线移动：避免瞬移导致的 hover 未触发（UI 没反应过来就点击）。"""
    sx, sy = cursor_pos()
    x, y = int(x), int(y)
    dist = ((x - sx) ** 2 + (y - sy) ** 2) ** 0.5
    if dist < 2:
        win32api.SetCursorPos((x, y))
        return
    if duration is None:
        duration = min(0.65, 0.12 + dist / 2600.0)
    steps = max(6, min(40, int(dist / 18)))
    # 控制点偏移，形成自然弧度
    cx1 = sx + (x - sx) * 0.33 + random.uniform(-dist * 0.06, dist * 0.06)
    cy1 = sy + (y - sy) * 0.33 + random.uniform(-dist * 0.06, dist * 0.06)
    cx2 = sx + (x - sx) * 0.66 + random.uniform(-dist * 0.06, dist * 0.06)
    cy2 = sy + (y - sy) * 0.66 + random.uniform(-dist * 0.06, dist * 0.06)
    for i in range(1, steps + 1):
        t = i / steps
        mt = 1 - t
        px = mt**3 * sx + 3 * mt**2 * t * cx1 + 3 * mt * t**2 * cx2 + t**3 * x
        py = mt**3 * sy + 3 * mt**2 * t * cy1 + 3 * mt * t**2 * cy2 + t**3 * y
        win32api.SetCursorPos((int(px), int(py)))
        time.sleep(duration / steps)


def click(x=None, y=None, button="left", double=False, human=True):
    if x is not None:
        move_to(x, y)
        if human:
            human_delay(0.04, 0.12)
    down, up = ((MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP) if button == "left"
                else (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP))
    for _ in range(2 if double else 1):
        _send(_mouse_input(down))
        time.sleep(random.uniform(0.04, 0.09))
        _send(_mouse_input(up))
        if double:
            time.sleep(random.uniform(0.06, 0.12))


def scroll(amount, x=None, y=None):
    if x is not None:
        move_to(x, y)
        human_delay(0.03, 0.08)
    for _ in range(abs(amount)):
        _send(_mouse_input(MOUSEEVENTF_WHEEL, data=120 if amount > 0 else -120))
        time.sleep(random.uniform(0.03, 0.07))


# ---- 键盘
VK = {"ctrl": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B,
      "enter": 0x0D, "esc": 0x1B, "tab": 0x09, "space": 0x20,
      "back": 0x08, "del": 0x2E, "home": 0x24, "end": 0x23,
      "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
      "pgup": 0x21, "pgdn": 0x22, "f1": 0x70, "f2": 0x71, "f3": 0x72}


def key_down(k):
    vk = VK.get(k.lower(), ord(k.upper()) if len(k) == 1 else 0)
    _send(_key_input(vk=vk))


def key_up(k):
    vk = VK.get(k.lower(), ord(k.upper()) if len(k) == 1 else 0)
    _send(_key_input(vk=vk, flags=KEYEVENTF_KEYUP))


def hotkey(*keys, hold=0.04):
    for k in keys:
        key_down(k)
        time.sleep(hold)
    for k in reversed(keys):
        key_up(k)
        time.sleep(0.02)


def type_text(text, mode="auto", wpm_jitter=True):
    """输入文本。
    mode='clipboard' : 剪贴板 + Ctrl+V（中文/frü 混合最可靠，IME 无关）
    mode='unicode'   : SendInput KEYEVENTF_UNICODE 逐字（不污染剪贴板）
    mode='auto'      : 纯 ASCII 用 unicode 通道，含非 ASCII 走剪贴板
    """
    pure_ascii = all(ord(c) < 128 for c in text)
    if mode == "auto":
        mode = "unicode" if pure_ascii else "clipboard"

    if mode == "clipboard":
        old = get_clipboard()
        set_clipboard(text)
        human_delay(0.05, 0.12)
        hotkey("ctrl", "v")
        human_delay(0.12, 0.25)
        # 恢复原剪贴板，避免污染用户
        try:
            if old is not None:
                set_clipboard(old)
        except Exception:
            pass
        return

    for ch in text:
        code = ord(ch)
        if code > 0xFFFF:                     # 补充平面 -> 代理对
            code -= 0x10000
            for u in (0xD800 + (code >> 10), 0xDC00 + (code & 0x3FF)):
                _send(_key_input(scan=u, flags=KEYEVENTF_UNICODE))
                _send(_key_input(scan=u, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
        else:
            _send(_key_input(scan=code, flags=KEYEVENTF_UNICODE))
            _send(_key_input(scan=code, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
        if wpm_jitter:
            time.sleep(random.uniform(0.018, 0.055))


def get_clipboard():
    try:
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            return None
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        return None


def set_clipboard(text, tries=8):
    for i in range(tries):
        try:
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
            finally:
                win32clipboard.CloseClipboard()
            return True
        except Exception:
            time.sleep(0.08 * (i + 1))
    return False


# ---------------------------------------------------------------- 窗口层
def find_qq_windows():
    """返回 QQ 主窗口候选。QQ NT 主窗口类名 Chrome_WidgetWin_1、标题 'QQ'。"""
    out = []

    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        cls = win32gui.GetClassName(hwnd)
        title = win32gui.GetWindowText(hwnd)
        if cls != "Chrome_WidgetWin_1":
            return
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        # 进程名必须是 QQ.exe，排除 Chrome / 微信小程序容器
        try:
            import psutil
            pname = psutil.Process(pid).name().lower()
        except Exception:
            pname = ""
        r = win32gui.GetWindowRect(hwnd)
        w, h = r[2] - r[0], r[3] - r[1]
        if w < 400 or h < 300:
            return
        if title.strip() in ("QQ", "") or pname == "qq.exe":
            out.append({"hwnd": hwnd, "title": title, "pid": pid,
                        "proc": pname, "rect": r, "size": (w, h)})

    win32gui.EnumWindows(cb, [])
    out.sort(key=lambda d: -(d["size"][0] * d["size"][1]))
    return out


def force_foreground(hwnd, timeout=1.2):
    """抢焦点。Windows 有前台锁定，用 AttachThreadInput 解。"""
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.25)
    if win32gui.GetForegroundWindow() == hwnd:
        return True
    t1 = win32api.GetCurrentThreadId()
    fg = win32gui.GetForegroundWindow()
    t2 = win32process.GetWindowThreadProcessId(fg)[0] if fg else 0
    t3 = win32process.GetWindowThreadProcessId(hwnd)[0]
    attached = []
    for t in (t2, t3):
        if t and t != t1:
            try:
                win32process.AttachThreadInput(t1, t, True)
                attached.append(t)
            except Exception:
                pass
    try:
        win32gui.SetForegroundWindow(hwnd)
        win32gui.BringWindowToTop(hwnd)
        win32gui.SetActiveWindow(hwnd)
    except Exception:
        pass
    finally:
        for t in attached:
            try:
                win32process.AttachThreadInput(t1, t, False)
            except Exception:
                pass
    deadline = time.time() + timeout
    while time.time() < deadline:
        if win32gui.GetForegroundWindow() == hwnd:
            return True
        time.sleep(0.05)
    return False


# ---------------------------------------------------------------- 限流 / 状态
class Guard:
    """硬性安全阀。这是"最保险"的实质，比任何伪装都有效。"""

    def __init__(self, min_interval=3.0, hourly=20, daily=120):
        self.min_interval = min_interval
        self.hourly = hourly
        self.daily = daily
        self.state = self._load()

    def _load(self):
        s = {"sends": [], "last_send": 0}
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                s.update(json.load(f))
        except Exception:
            pass
        return s

    def _save(self):
        try:
            with open(STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.state, f)
        except Exception:
            pass

    def check_stop(self):
        if os.path.exists(STOP_FLAG):
            raise RuntimeError("检测到 STOP 文件，已停止。删除 %s 后重试。" % STOP_FLAG)
        if win32api.GetAsyncKeyState(win32con.VK_ESCAPE) & 0x8000:
            raise RuntimeError("检测到 Esc 按下，人工中止。")

    def before_send(self, target):
        self.check_stop()
        now = time.time()
        since = now - self.state.get("last_send", 0)
        if since < self.min_interval:
            need = self.min_interval - since
            time.sleep(need)          # 宁可等，不要顶风上
        sends = [t for t in self.state.get("sends", []) if now - t < 86400]
        last_hour = [t for t in sends if now - t < 3600]
        if len(last_hour) >= self.hourly:
            raise RuntimeError("本小时已达 %d 条上限（%s）。停手。" % (self.hourly, target))
        if len(sends) >= self.daily:
            raise RuntimeError("本日已达 %d 条上限。停手。" % self.daily)
        sends.append(now)
        self.state["sends"] = sends
        self.state["last_send"] = now
        self._save()

    def stats(self):
        now = time.time()
        sends = self.state.get("sends", [])
        return {"last_1h": len([t for t in sends if now - t < 3600]),
                "last_24h": len([t for t in sends if now - t < 86400]),
                "hourly_cap": self.hourly, "daily_cap": self.daily}


# ---------------------------------------------------------------- QQ 客户端
class QQ:
    # 基准窗口 1070x720 下实测的控件位置（比例制，窗口缩放自动适配）
    REL = {
        "search":    (0.147, 0.056),   # 左上搜索框
        "conv_head": (0.168, 0.147),   # 会话列表第一行
        "conv_row":  0.056,            # 会话行高（占窗口高度）
        "conv_x":    0.168,            # 会话行中心 x
        "chat":      (0.654, 0.420),   # 聊天内容区
        "input":     (0.560, 0.778),   # 输入框
        "send_btn":  (0.920, 0.963),   # 发送按钮
    }

    def __init__(self, dry_run=True, guard=None, log=True):
        self.dry_run = dry_run
        self.guard = guard or Guard()
        self.log_enabled = log
        self.hwnd = None
        self.rect = None
        self._discover()

    # ---- 基础设施
    def _discover(self):
        wins = find_qq_windows()
        if not wins:
            raise RuntimeError("没找到 QQ 主窗口，先把 QQ 登录并打开。")
        self.hwnd = wins[0]["hwnd"]
        self.rect = wins[0]["rect"]
        return wins[0]

    def log(self, action, **kw):
        rec = {"ts": datetime.now().isoformat(timespec="seconds"),
               "action": action, "dry_run": self.dry_run, **kw}
        line = json.dumps(rec, ensure_ascii=False)
        print("[qq]", line)
        if self.log_enabled:
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(os.path.join(LOG_DIR, datetime.now().strftime("%Y-%m-%d") + ".jsonl"),
                      "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def refresh(self):
        r = win32gui.GetWindowRect(self.hwnd)
        if not win32gui.IsWindowVisible(self.hwnd):
            raise RuntimeError("QQ 窗口不可见（已最小化到托盘？）")
        self.rect = r
        return r

    def geom(self):
        l, t, r, b = self.refresh()
        return {"rect": (l, t, r, b), "w": r - l, "h": b - t}

    def pt(self, key, dy=0.0):
        """相对窗口的坐标 -> 屏幕绝对坐标"""
        self.refresh()
        l, t, r, b = self.rect
        w, h = r - l, b - t
        if isinstance(key, str):
            rx, ry = self.REL[key]
        else:
            rx, ry = key
        return int(l + rx * w), int(t + (ry + dy) * h)

    def conv_pt(self, index):
        """会话列表第 index 行（0 起）中心点"""
        self.refresh()
        l, t, r, b = self.rect
        w, h = r - l, b - t
        y = self.REL["conv_head"][1] + index * self.REL["conv_row"]
        return int(l + self.REL["conv_x"] * w), int(t + y * h)

    def focus(self):
        ok = force_foreground(self.hwnd)
        if not ok:
            raise RuntimeError("无法把 QQ 提到前台（可能被其它全屏程序挡住）。")
        time.sleep(0.12)
        return ok

    def shot(self, path=None):
        from PIL import ImageGrab
        self.refresh()
        img = ImageGrab.grab(bbox=self.rect, all_screens=True)
        if path is None:
            path = os.path.join(HERE, "shots", time.strftime("shot_%H%M%S.png"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img.save(path)
        return path

    # ---- 导航
    def goto(self, conv, verify=True, max_scroll=6):
        """按名字进入会话：搜索框输入 -> 回车 -> 校验。
        不走坐标点列表（列表顺序会变），走搜索最稳。"""
        self.focus()
        sx, sy = self.pt("search")
        click(sx, sy)
        human_delay(0.1, 0.2)
        hotkey("ctrl", "a")
        hotkey("del")
        human_delay(0.05, 0.12)
        type_text(conv)
        time.sleep(0.7)          # 等搜索结果刷新
        hotkey("enter")
        time.sleep(0.75)
        self.log("goto", target=conv, verified=None)

        if verify:
            title = self.read_header()
            ok = bool(title and (conv in title or title in conv))
            self.log("goto_verify", target=conv, header=title, ok=ok)
            if not ok:
                raise RuntimeError("进入的会话不是「%s」（当前标题: %r）。已中止，未发任何东西。"
                                   % (conv, title))
        return True

    def read_header(self):
        """读当前会话标题：点聊天区 -> Ctrl+A/Ctrl+C 太脏，改用标题区域截图 OCR 不可用，
        这里用无障碍兜底：从窗口标题拿不到。退化为返回 None 由调用方决定。
        更可靠的做法见 read_messages()。"""
        return None

    # ---- 读消息
    def read_messages(self, max_chars=4000):
        """读当前会话最近消息（纯 GUI 路径，不碰协议）。
        实测可行：点击聊天区 -> Ctrl+A -> Ctrl+C -> 读剪贴板。
        注意：会临时占用剪贴板，结束后恢复。"""
        self.focus()
        cx, cy = self.pt("chat")
        click(cx, cy)
        human_delay(0.1, 0.2)
        old = get_clipboard()
        set_clipboard("")
        hotkey("ctrl", "a")
        time.sleep(0.15)
        hotkey("ctrl", "c")
        time.sleep(0.45)
        text = get_clipboard() or ""
        try:
            hotkey("right")          # 取消选区，避免误触
        except Exception:
            pass
        if old is not None:
            set_clipboard(old)
        text = text.strip()[:max_chars]
        self.log("read_messages", chars=len(text),
                 preview=text[:80].replace("\n", " "))
        return text

    # ---- 发送
    def send(self, text, target=None, verify_clear=True):
        """发消息。target 给定时先 goto 过去。"""
        if not text or not text.strip():
            raise ValueError("空消息不发。")
        if target:
            self.goto(target)
        self.guard.before_send(target or "current")

        self.focus()
        ix, iy = self.pt("input")
        click(ix, iy)
        human_delay(0.12, 0.25)

        # 清空残留草稿（实测里输入框会有旧草稿，不清就会串味）
        if verify_clear:
            hotkey("ctrl", "a")
            human_delay(0.05, 0.1)
            hotkey("del")
            human_delay(0.05, 0.1)

        type_text(text)
        human_delay(0.2, 0.45)

        if self.dry_run:
            shot = self.shot()
            self.log("send_dryrun", target=target, text=text, shot=shot)
            # 撤回：把刚输入的内容清掉，绝不留草稿
            hotkey("ctrl", "a")
            hotkey("del")
            return {"dry_run": True, "target": target, "text": text, "shot": shot}

        hotkey("enter")
        time.sleep(0.35)
        shot = self.shot()
        self.log("send", target=target, text=text, shot=shot)
        return {"dry_run": False, "target": target, "text": text, "shot": shot}


# ---------------------------------------------------------------- CLI
def _cli():
    import argparse
    ap = argparse.ArgumentParser(description="QQ NT 外部 GUI 自动化（只控鼠标键盘）")
    ap.add_argument("--arm", action="store_true",
                    help="真正发送。不加此参数 = 演练模式（只输入不回车，会清掉草稿）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("probe", help="探测窗口/几何/状态")
    sub.add_parser("shot", help="截图当前 QQ 窗口")
    p = sub.add_parser("read", help="读当前会话最近消息")
    p.add_argument("--target", help="先进入该会话")
    p.add_argument("--max-chars", type=int, default=4000)
    p = sub.add_parser("goto", help="进入会话并校验")
    p.add_argument("target")
    p = sub.add_parser("send", help="发消息")
    p.add_argument("text")
    p.add_argument("--target", help="先进入该会话")
    sub.add_parser("stop", help="放置 STOP 文件，立刻停手")
    sub.add_parser("resume", help="移除 STOP 文件")

    a = ap.parse_args()
    if a.cmd == "stop":
        open(STOP_FLAG, "w").close()
        print("已放置 STOP 文件：所有后续操作会立刻报错停止。")
        return
    if a.cmd == "resume":
        if os.path.exists(STOP_FLAG):
            os.remove(STOP_FLAG)
        print("已移除 STOP 文件。")
        return

    q = QQ(dry_run=not a.arm)
    if a.cmd == "probe":
        g = q.geom()
        pts = {k: q.pt(k) for k in ("search", "chat", "input", "send_btn")}
        print(json.dumps({"window": g, "points": pts, "dry_run": q.dry_run,
                          "guard": q.guard.stats()}, ensure_ascii=False, indent=2))
    elif a.cmd == "shot":
        print(q.shot())
    elif a.cmd == "goto":
        q.goto(a.target)
        print("ok, shot:", q.shot())
    elif a.cmd == "read":
        if a.target:
            q.goto(a.target)
        print(q.read_messages(a.max_chars))
    elif a.cmd == "send":
        print(json.dumps(q.send(a.text, a.target), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _cli()
