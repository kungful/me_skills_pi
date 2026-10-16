#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CPE140Ctrl 真机 UI 驱动：按文字找控件 -> 点 -> 截图。"""
import io
import re
import subprocess
import sys
import time

ADB = "C:/Users/hua/AppData/Local/Android/Sdk/platform-tools/adb.exe"
PKG = "com.picpe.cpe140"
SHOTS = "C:/Users/hua/Documents/备份代码/CPE140Ctrl/shots"


def sh(*a, **kw):
    return subprocess.run([ADB] + list(a), capture_output=True, **kw)


def dump():
    subprocess.run([ADB, "shell", "rm", "-f", "/sdcard/ui.xml"], capture_output=True)
    sh("shell", "uiautomator", "dump", "/sdcard/ui.xml")
    subprocess.run([ADB, "pull", "/sdcard/ui.xml", "C:/tmptest/ui.xml"],
                   capture_output=True)
    return io.open("C:/tmptest/ui.xml", encoding="utf-8").read()


def nodes(xml):
    out = []
    for m in re.finditer(r'<node[^>]*?text="([^"]*)"[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml):
        t = m.group(1)
        x = (int(m.group(2)) + int(m.group(4))) // 2
        y = (int(m.group(3)) + int(m.group(5))) // 2
        if t.strip():
            out.append((t, x, y))
    return out


def find(xml, text, exact=False):
    for t, x, y in nodes(xml):
        if (t == text) if exact else (text in t):
            return x, y
    raise SystemExit("找不到控件: " + text)


def tap(x, y, wait=3.0):
    sh("shell", "input", "tap", str(x), str(y))
    time.sleep(wait)


def shot(name, wait=0.6):
    time.sleep(wait)
    sh("shell", "screencap", "-p", "/sdcard/s.png")
    subprocess.run([ADB, "pull", "/sdcard/s.png", SHOTS + "/" + name],
                   capture_output=True)
    print("  shot ->", name)


def tap_text(text, wait=3.0, tries=3):
    x = y = None
    for i in range(tries):
        try:
            x, y = find(dump(), text)
            break
        except SystemExit:
            time.sleep(2)
    if x is None:
        raise SystemExit("dump 里一直找不到: " + text)
    print("  tap %r at (%d,%d)" % (text, x, y))
    tap(x, y, wait)


def output_text(xml):
    """取最大的那个 TextView 文本（输出区）。"""
    best = ""
    for m in re.finditer(r'<node[^>]*?text="([^"]*)"[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*?/>', xml):
        t = m.group(1)
        if len(t) > len(best):
            best = t
    return best


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        tap_text(arg)
        shot("t_" + re.sub(r"[^\w]+", "_", arg) + ".png")
