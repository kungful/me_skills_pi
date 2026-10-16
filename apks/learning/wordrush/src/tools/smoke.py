#!/usr/bin/env python3
"""WordRush 冒烟测试：用 adb 在真机上自动点一遍，任何崩溃都会被抓出来。

    python tools/smoke.py [轮数]

它只做三件事：dump 界面 -> 点一个合理的位置 -> 检查 logcat 有没有 FATAL。
用来在没有人工操作的情况下验证「所有页面 + 所有题型」都不会崩。
"""
import os
import random
import re
import subprocess
import sys
import time

ADB = os.environ.get("ADB", os.path.expanduser("~/Documents/platform-tools/adb.exe"))
if not os.path.exists(ADB):
    ADB = "adb"

PKG = "com.wordrush.app"


def run(*args, binary=False):
    p = subprocess.run([ADB] + list(args), capture_output=True)
    if binary:
        return p.stdout
    return p.stdout.decode("utf-8", "replace").strip()


def dump():
    # uiautomator 偶尔会抽风，重试几次
    for _ in range(4):
        run("shell", "uiautomator", "dump", "/sdcard/ui.xml")
        xml = run("shell", "cat", "/sdcard/ui.xml")
        if "<hierarchy" in xml:
            return xml
        time.sleep(0.6)
    return ""


NODE = re.compile(r"<node ([^>]*?)/?>")


def nodes(xml):
    out = []
    for m in NODE.finditer(xml):
        attrs = dict(re.findall(r'([a-zA-Z-]+)="([^"]*)"', m.group(1)))
        b = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", attrs.get("bounds", ""))
        if not b:
            continue
        x1, y1, x2, y2 = map(int, b.groups())
        attrs["cx"] = (x1 + x2) // 2
        attrs["cy"] = (y1 + y2) // 2
        attrs["top"] = y1
        out.append(attrs)
    return out


def find(xml, **kw):
    for n in nodes(xml):
        if all(n.get(k, "") == v for k, v in kw.items()):
            return n
    return None


def tap(n):
    run("shell", "input", "tap", str(n["cx"]), str(n["cy"]))


def top_activity():
    out = run("shell", "dumpsys", "activity", "activities")
    m = re.search(r"topResumedActivity=ActivityRecord\{\S+ \S+ (\S+) ", out)
    return m.group(1) if m else "?"


def fatal():
    out = run("logcat", "-d", "-t", "600")
    hits = [l for l in out.splitlines() if "FATAL" in l or "AndroidRuntime: Process:" in l]
    return hits


def clear_log():
    run("logcat", "-c")


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    random.seed(7)
    crashes = []

    print("== 唤醒并启动 ==")
    run("shell", "input", "keyevent", "KEYCODE_WAKEUP")
    run("shell", "wm", "dismiss-keyguard")
    run("shell", "svc", "power", "stayon", "true")
    run("shell", "am", "force-stop", PKG)
    clear_log()
    run("shell", "am", "start", "-n", f"{PKG}/.ui.HomeActivity")
    time.sleep(3)

    seen = {}

    for i in range(rounds):
        xml = dump()
        if not xml:
            print(f"[{i}] dump 失败")
            continue
        act = top_activity()
        seen[act] = seen.get(act, 0) + 1

        if act.endswith("HomeActivity") and i == 0:
            n = find(xml, text="开始挑战") or find(xml, text="继续加练")
            if n:
                print("-> 点【开始挑战】")
                tap(n)
                time.sleep(2.2)
                continue

        # 结算层：点「再来一轮 / 返回」
        n = find(xml, text="再来一轮") or find(xml, text="返回")
        if n and act.endswith("PlayActivity"):
            print(f"[{i}] 结算页 -> 点 {n['text']}")
            tap(n)
            time.sleep(2.0)
            continue

        # 答题页：只点上半部分之外的、可点的元素，避开左上角关闭按钮
        cands = [
            x for x in nodes(xml)
            if x.get("clickable") == "true" and x["cy"] > 380 and x["cx"] > 90
        ]
        if not cands:
            print(f"[{i}] {act} 没有可点元素")
            time.sleep(1.0)
            continue
        # 优先点字母键和选项，尽量往题目区域中间走
        cands.sort(key=lambda x: (abs(x["cx"] - 630) + abs(x["cy"] - 1700)))
        pick = cands[random.randrange(min(3, len(cands)))]
        tap(pick)
        time.sleep(1.35)

        hits = fatal()
        if hits:
            crashes.append((i, act, hits[:6]))
            print(f"!! 第 {i} 轮崩溃 @ {act}")
            for h in hits[:6]:
                print("   ", h)
            clear_log()
            run("shell", "am", "start", "-n", f"{PKG}/.ui.HomeActivity")
            time.sleep(2.5)

    print("\n== 访问过的页面 ==")
    for k, v in seen.items():
        print(f"  {v:4d}x {k}")

    print("\n== 崩溃 ==")
    if not crashes:
        print("  无 ")
    else:
        for i, act, hits in crashes:
            print(f"  第 {i} 轮 @ {act}")
            for h in hits:
                print("    ", h)


if __name__ == "__main__":
    main()
