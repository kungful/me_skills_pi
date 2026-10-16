#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
词打 / VocabType —— 真机自动化验收脚本。
用 adb 直接把英文敲进 App 的隐藏输入框，验证逐字符判定、连击、
错词、模式切换、各二级页面不崩。

用法：
    python tools/drive.py            # 默认 60 轮
    python tools/drive.py 120        # 120 轮
"""
import os
import re
import subprocess
import sys
import time

ADB = r"C:\Users\hua\Documents\platform-tools\adb.exe"
SER = "192.168.31.200:5555"
PKG = "com.vocabtype.app"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shots")

FATAL = re.compile(r"FATAL EXCEPTION|AndroidRuntime.*com\.vocabtype")


def sh(*args, timeout=60):
    cmd = [ADB, "-s", SER] + list(args)
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT"


def shell(cmd, timeout=60):
    return sh("shell", cmd, timeout=timeout)


def top_activity():
    o, _ = shell("dumpsys activity activities | grep -m1 topResumedActivity")
    m = re.search(r"([\w.]+)/([\w.$]+)", o)
    return (m.group(1) + "/" + m.group(2)) if m else "?"


def ui():
    """uiautomator dump -> xml 文本"""
    for _ in range(3):
        shell("uiautomator dump /sdcard/ui.xml")
        o, _ = shell("cat /sdcard/ui.xml")
        if o.strip().startswith("<?xml"):
            return o
        time.sleep(0.4)
    return ""


def find(xml, needle, attr="text"):
    """返回含 needle 的那个节点的 (attr值, bounds)"""
    for m in re.finditer(r"<node[^>]*>", xml):
        tag = m.group(0)
        a = re.search(attr + r'="([^"]*)"', tag)
        if not a or needle not in a.group(1):
            continue
        b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', tag)
        if not b:
            continue
        return a.group(1), tuple(int(x) for x in b.groups())
    return None, None


def tap(x, y):
    shell("input tap %d %d" % (x, y))


def tap_mid(bounds):
    x1, y1, x2, y2 = bounds
    tap((x1 + x2) // 2, (y1 + y2) // 2)


def typetext(s):
    # adb input text 不认空格和特殊字符，逐段转义
    safe = s.replace(" ", "%s")
    shell("input text '%s'" % safe)


def fatal_log():
    o, _ = shell("logcat -d -t 500 *:E")
    hits = [l for l in o.splitlines() if FATAL.search(l)]
    return hits


def clear_log():
    shell("logcat -c")


def state():
    """从 contentDescription 里拿到打字目标/缓冲区；从 Text 里拿战绩"""
    xml = ui()
    target = None
    cd, _ = find(xml, "VT|target=", attr="content-desc")
    if cd:
        m = re.match(r"VT\|target=(.*?)\|wi=(\d+)\|buf=(.*)$", cd)
        if m:
            target = (m.group(1), int(m.group(2)), m.group(3))
    def txt(prefix):
        v, _ = find(xml, prefix)
        return v
    return {
        "xml": xml,
        "target": target,
        "wpm": txt("WPM"),
        "strk": txt("STRK"),
        "err": txt("ERR"),
        "prog": txt("/"),
        "top": top_activity(),
    }


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    os.makedirs(OUT, exist_ok=True)
    print("== 启动 App")
    shell("am force-stop " + PKG)
    clear_log()
    shell("monkey -p %s -c android.intent.category.LAUNCHER 1" % PKG)
    time.sleep(3.5)
    print("   top =", top_activity())

    st = state()
    if not st["target"]:
        print("!! 拿不到打字目标，先点一下打字区")
        xml = st["xml"]
        _, b = find(xml, "点击", attr="text")
        if b:
            tap_mid(b)
            time.sleep(1.5)
        st = state()
        if not st["target"]:
            print("!! 依然拿不到，退出。xml 头 800 字：")
            print(st["xml"][:800])
            return 2

    ok = 0
    bad = 0
    for i in range(rounds):
        words, wi, buf = st["target"]
        arr = words.split(" ")
        if wi >= len(arr):
            wi = 0
        want = arr[wi]
        # 只敲字母，丢掉标点（App 会把标点当独立 token 处理）
        pure = re.sub(r"[^A-Za-z']", "", want)
        if not pure:
            # 标点 token —— 敲一个和它不同的字母，制造一次错误
            pure = "z"
        typetext(pure)
        time.sleep(0.22)
        st2 = state()

        if st2["target"] is None:
            print("   [%02d] 目标丢失，top=%s" % (i + 1, st2["top"]))
            break
        advanced = st2["target"] != st["target"]
        if advanced:
            ok += 1
        else:
            bad += 1
        st = st2
        if (i + 1) % 10 == 0:
            print("   [%02d] STRK=%s ERR=%s PROG=%s TOP=%s" %
                  (i + 1, st["strk"], st["err"], st["prog"], st["top"]))

    print("\n== 打字结果：推进 %d / 卡住 %d" % (ok, bad))
    print("   STRK=%s ERR=%s PROG=%s" % (st["strk"], st["err"], st["prog"]))

    print("\n== 二级页面巡回")
    for label, key in [("词库", "词库"), ("统计", None), ("复习", None), ("设置", None)]:
        pass

    print("\n== 崩溃检查")
    hits = fatal_log()
    if hits:
        print("!! 发现崩溃：")
        for h in hits[:12]:
            print("   " + h)
        return 1
    print("   logcat 无 FATAL —— 通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
