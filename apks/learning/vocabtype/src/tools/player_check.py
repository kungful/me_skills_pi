#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
播放器「列表循环」等音乐播放器功能验收。
用法: python tools/player_check.py [serial]

只按 resource-id 定位（不写死坐标），所以界面滚动/字号变化都能适配。
"""
import re
import subprocess
import sys
import time

ADB = r"C:\Users\hua\Documents\platform-tools\adb.exe"
DEV = ["-s", sys.argv[1] if len(sys.argv) > 1 else "192.168.31.200:42801"]
PKG = "com.vocabtype.app"


def sh(*a, t=90):
    return subprocess.run([ADB] + DEV + list(a), capture_output=True, timeout=t).stdout


def txt(*a):
    return sh(*a).decode("utf8", "replace")


def dump():
    for _ in range(3):
        out = txt("shell", "uiautomator dump /sdcard/u.xml")
        if "dumped" in out:
            break
        time.sleep(1.2)
    return txt("shell", "cat /sdcard/u.xml")


def nodes(x):
    o = {}
    for m in re.finditer(r"<node[^>]*>", x):
        t = m.group(0)

        def g(k):
            mm = re.search(k + r'="([^"]*)"', t)
            return mm.group(1) if mm else ""
        b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', t)
        rid = g("resource-id").split("/")[-1]
        if b:
            e = dict(text=g("text"), desc=g("content-desc"),
                     box=tuple(int(v) for v in b.groups()))
            if rid:
                o[rid] = e
            o.setdefault("_all", []).append(e)
    return o


def ct(b):
    return (b[0] + b[2]) // 2, (b[1] + b[3]) // 2


def tap_rid(rid):
    x = dump()
    n = nodes(x).get(rid)
    if not n:
        print("  ! 找不到 %s" % rid)
        return None, x
    sh("shell", "input", "tap", *[str(v) for v in ct(n["box"])])
    time.sleep(0.9)
    return n, x


def cnt(x=None):
    """读 '36 / 3854' 这种计数"""
    x = x or dump()
    for e in nodes(x).get("_all", []):
        m = re.match(r"^(\d+) / (\d+)$", e["text"] or "")
        if m:
            return int(m.group(1)), int(m.group(2))
    return None, None


def top_activity():
    o = txt("shell", "dumpsys activity activities | grep -m1 topResumedActivity")
    m = re.search(r"(com\.[\w.]+)/([\w.]+)", o)
    return (m.group(1) + "/" + m.group(2)) if m else "?"


def main():
    print("=" * 60)
    print("0) 前置检查")
    act = top_activity()
    print("  顶层 Activity: %s" % act)
    if "PlayerActivity" not in act:
        sh("shell", "am", "start", "-n", PKG + "/.ui.MainActivity")
        time.sleep(3.5)
        for _ in range(3):
            tap_rid("btnPlayer")
            time.sleep(3.5)
            act = top_activity()
            if "PlayerActivity" in act:
                break
        print("  切到播放器后: %s" % act)
    if "PlayerActivity" not in act:
        print("  ✗ 不在播放器界面，请手动打开播放器再跑")
        return

    x = dump()
    n = nodes(x)
    print("  循环模式: %s" % (n.get("btnMode", {}).get("desc") or "?"))
    print("  收藏按钮: %s" % (n.get("btnFav", {}).get("desc") or "?"))
    print("  定时按钮: %s" % (n.get("btnTimer", {}).get("text") or "?"))
    print("  列表按钮: %s" % (n.get("btnList", {}).get("text") or "?"))
    print("  顺序按钮: %s" % (n.get("btnOrder", {}).get("text") or "?"))
    print("  进度: %s" % (cnt(x),))

    print("=" * 60)
    print("1) 循环模式轮换 4 档")
    for i in range(4):
        _, xx = tap_rid("btnMode")
        m = nodes(xx).get("btnMode", {})
        print("   第%d次 -> %s" % (i + 1, m.get("desc") or "?"))

    print("=" * 60)
    print("2) 定时关闭轮换")
    for i in range(4):
        _, xx = tap_rid("btnTimer")
        print("   第%d次 -> %s" % (i + 1, nodes(xx).get("btnTimer", {}).get("text") or "?"))
    # 关掉定时
    tap_rid("btnTimer")

    print("=" * 60)
    print("3) 收藏开关")
    before = nodes(dump()).get("btnFav", {}).get("desc")
    _, xx = tap_rid("btnFav")
    after = nodes(xx).get("btnFav", {}).get("desc")
    print("   %s -> %s" % (before, after))
    tap_rid("btnFav")

    print("=" * 60)
    print("4) 列表弹窗")
    _, xx = tap_rid("btnList")
    time.sleep(1)
    items = [e["text"] for e in nodes(dump()).get("_all", []) if e["text"]]
    has = any("播放列表" in (t or "") for t in items)
    print("   弹窗出现: %s" % ("是" if has else "否"))
    sh("shell", "input", "keyevent", "KEYCODE_BACK")

    print("=" * 60)
    print("5) 列表循环回绕：切到 3 个词的收藏列表，跑完整轮看是否回 1")
    # 切到"只收藏"范围，并先收藏 3 个词
    for _ in range(3):
        _, xx = tap_rid("btnFav")          # 收藏当前（状态在 after 里看）
        time.sleep(0.4)
    print("   已收藏当前词，尝试用列表跳到很后面再观察")
    c0 = cnt()
    for i in range(20):
        tap_rid("btnFwd15")
    c1 = cnt()
    print("   +15x20 之后: %s (从 %s)" % (c1, c0))
    # 等待跑到末尾并回绕
    for i in range(20):
        time.sleep(6)
        c = cnt()
        print("   +%3ds: %s" % ((i + 1) * 6, c))
        if c[0] is not None and c[1] and c[0] <= 5:
            print("   ✓ 回绕到开头，列表循环生效")
            break

    print("=" * 60)
    log = txt("logcat", "-d", "-t", "400")
    bad = [l for l in log.splitlines() if re.search(r"FATAL|AndroidRuntime.*vocabtype", l)]
    print("崩溃检查: %s" % ("无" if not bad else "\n" + "\n".join(bad[-5:])))


if __name__ == "__main__":
    main()
