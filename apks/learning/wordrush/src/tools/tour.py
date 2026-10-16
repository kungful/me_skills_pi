#!/usr/bin/env python3
"""把 WordRush 的每个二级页面都打开一遍，检查有没有崩溃。

    python tools/tour.py
"""
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smoke import ADB, PKG, dump, find, fatal, nodes, run, tap, top_activity, clear_log  # noqa

ENTRIES = ["关卡地图", "词库", "错题本", "成就", "我的进度"]


def back():
    run("shell", "input", "keyevent", "KEYCODE_BACK")
    time.sleep(1.2)


def main():
    run("shell", "input", "keyevent", "KEYCODE_WAKEUP")
    run("shell", "wm", "dismiss-keyguard")
    run("shell", "svc", "power", "stayon", "true")
    run("shell", "am", "force-stop", PKG)
    clear_log()
    run("shell", "am", "start", "-n", f"{PKG}/.ui.HomeActivity")
    time.sleep(3)

    problems = []
    for name in ENTRIES:
        xml = dump()
        n = find(xml, text=name)
        # 卡片里的标题可能不是可点节点，找它所在的可点卡片
        if not n:
            print(f"✗ 首页找不到「{name}」")
            problems.append(name)
            continue
        if n.get("clickable") != "true":
            # 用文字下方一点的位置点卡片
            n = dict(n, cy=n["cy"] + 30)
        tap(n)
        time.sleep(2.0)
        act = top_activity()
        print(f"-> {name:6s}  {act}")
        if not act.startswith(PKG):
            problems.append(f"{name} 没打开 (top={act})")
            continue
        hits = fatal()
        if hits:
            problems.append(f"{name} 崩溃")
            for h in hits[:5]:
                print("   ", h)
            clear_log()
        # 页面里随便点两下，看看有没有暗雷
        for _ in range(2):
            xml = dump()
            cands = [x for x in nodes(xml)
                     if x.get("clickable") == "true" and x["cy"] > 400 and x["cx"] > 80]
            if cands:
                tap(cands[len(cands) // 2])
                time.sleep(1.2)
        hits = fatal()
        if hits:
            problems.append(f"{name} 交互后崩溃")
            for h in hits[:5]:
                print("   ", h)
            clear_log()
        # 退出可能弹出的对话框
        xml = dump()
        if find(xml, text="取消") or find(xml, text="关闭"):
            back()
        back()
        time.sleep(0.8)
        if not top_activity().startswith(PKG):
            run("shell", "am", "start", "-n", f"{PKG}/.ui.HomeActivity")
            time.sleep(2.0)

    print("\n== 结果 ==")
    print("  全部通过" if not problems else "  问题: " + "; ".join(problems))


if __name__ == "__main__":
    main()
