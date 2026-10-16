#!/usr/bin/env python3
"""三条支线流程各走一遍，确认参数传递没问题。

    1. 关卡地图 -> 进第 1 关 -> 答题到结算
    2. 词库 -> 练这一批 -> 答题
    3. 错题本 -> 攻克错题 -> 答题
"""
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smoke import PKG, clear_log, dump, fatal, find, nodes, run, tap, top_activity  # noqa

random.seed(11)


def home():
    run("shell", "am", "force-stop", PKG)
    run("shell", "am", "start", "-n", f"{PKG}/.ui.HomeActivity")
    time.sleep(2.5)


def answer(times=14, label=""):
    """在答题页瞎点，直到结算或点完次数"""
    for i in range(times):
        xml = dump()
        if not xml:
            continue
        n = find(xml, text="再来一轮")
        if n:
            print(f"   {label} 到达结算页（第 {i} 轮）")
            return "result"
        if find(xml, text="返回") and top_activity().endswith("PlayActivity"):
            print(f"   {label} 到达结算页")
            return "result"
        cands = [x for x in nodes(xml)
                 if x.get("clickable") == "true" and x["cy"] > 380 and x["cx"] > 90]
        if not cands:
            time.sleep(1.0)
            continue
        cands.sort(key=lambda x: abs(x["cx"] - 630) + abs(x["cy"] - 1700))
        tap(cands[random.randrange(min(3, len(cands)))])
        time.sleep(1.3)
    return "timeout"


def entry(name, offset=30):
    xml = dump()
    n = find(xml, text=name)
    if not n:
        print(f"✗ 找不到「{name}」")
        return False
    if n.get("clickable") != "true":
        n = dict(n, cy=n["cy"] + offset)
    tap(n)
    time.sleep(2.0)
    return True


def main():
    run("shell", "input", "keyevent", "KEYCODE_WAKEUP")
    run("shell", "wm", "dismiss-keyguard")
    run("shell", "svc", "power", "stayon", "true")
    bad = []

    # ---------- 1. 关卡地图 -> 第 1 关 ----------
    print("== 1. 关卡地图 ==")
    home()
    entry("关卡地图")
    print("   top =", top_activity())
    xml = dump()
    first = find(xml, text="1")
    if first:
        tap(first)
        time.sleep(2.2)
        act = top_activity()
        print("   点第 1 关 ->", act)
        if act.endswith("PlayActivity"):
            r = answer(16, "关卡")
            print("   结果:", r)
        else:
            bad.append("第 1 关没进答题页")
    else:
        bad.append("地图上没有关卡格子")

    # ---------- 2. 词库 -> 练这一批 ----------
    print("== 2. 词库 ==")
    home()
    entry("词库")
    entry("练这一批（最多 20 词）")
    act = top_activity()
    print("   练这一批 ->", act)
    if act.endswith("PlayActivity"):
        print("   结果:", answer(16, "词库练习"))
        xml = dump()
        n = find(xml, text="返回")
        if n:
            tap(n)
            time.sleep(1.5)
    else:
        bad.append("词库练习没进答题页 (top=%s)" % act)

    # ---------- 3. 错题本 ----------
    print("== 3. 错题本 ==")
    home()
    entry("错题本")
    entry("攻克错题（20 词）")
    act = top_activity()
    print("   攻克错题 ->", act)
    if act.endswith("PlayActivity"):
        print("   结果:", answer(16, "错题"))
        xml = dump()
        n = find(xml, text="返回")
        if n:
            tap(n)
            time.sleep(1.5)
    elif act.endswith("WrongActivity"):
        print("   （错题本是空的，跳过）")
    else:
        bad.append("错题练习没进答题页 (top=%s)" % act)

    hits = fatal()
    if hits:
        bad.append("有崩溃")
        for h in hits[:8]:
            print(h)

    print("\n== 结果 ==")
    print("  全部通过" if not bad else "  问题: " + "; ".join(bad))


if __name__ == "__main__":
    main()
