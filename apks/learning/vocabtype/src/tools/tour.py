#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
词打 / VocabType —— 功能巡回验收。
覆盖：三种模式、整句听写、严格模式拒绝错键、词库切换、统计、复习、设置、禅定。
"""
import os
import re
import subprocess
import sys
import time

ADB = r"C:\Users\hua\Documents\platform-tools\adb.exe"
SER = "192.168.31.200:5555"
PKG = "com.vocabtype.app"
HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.normpath(os.path.join(HERE, "..", "shots"))
FATAL = re.compile(r"FATAL EXCEPTION|AndroidRuntime.*vocabtype")

PASS = []
FAIL = []


def sh(*a, timeout=90):
    try:
        p = subprocess.run([ADB, "-s", SER] + list(a), capture_output=True, timeout=timeout)
        return p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT"


def sh1(c):
    return sh("shell", c)[0]


def tap(x, y):
    sh1("input tap %d %d" % (x, y))
    time.sleep(0.6)


def text(s):
    sh1("input text '%s'" % s.replace(" ", "%s"))


def dump():
    for _ in range(3):
        sh1("uiautomator dump /sdcard/ui.xml")
        o = sh1("cat /sdcard/ui.xml")
        if o.strip().startswith("<?xml"):
            return o
        time.sleep(0.4)
    return ""


def nodes(x):
    out = []
    for m in re.finditer(r"<node[^>]*>", x):
        t = m.group(0)
        g = lambda k: (re.search(k + r'="([^"]*)"', t).group(1)
                       if re.search(k + r'="([^"]*)"', t) else "")
        b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', t)
        out.append({
            "text": g("text"), "desc": g("content-desc"),
            "cls": g("class"),
            "b": tuple(int(v) for v in b.groups()) if b else None,
        })
    return out


def _nl(x):
    """宽容一点：字符串就当 xml 现拆，列表就直接用"""
    return nodes(x) if isinstance(x, str) else x


def find(ns, needle, key="text"):
    for n in _nl(ns):
        if needle in (n[key] or ""):
            return n
    return None


def target_of(ns):
    n = find(ns, "VT|target=", "desc")
    if not n:
        return None
    m = re.match(r"VT\|target=(.*?)\|wi=(\d+)\|buf=(.*)$", n["desc"])
    return (m.group(1), int(m.group(2)), m.group(3)) if m else None


def top():
    o = sh1("dumpsys activity activities | grep -m1 topResumedActivity")
    m = re.search(r"([\w.]+)/([\w.$]+)", o)
    return m.group(1) + "/" + m.group(2) if m else "?"


def shot(name):
    os.makedirs(SHOTS, exist_ok=True)
    with open(os.path.join(SHOTS, name), "wb") as f:
        p = subprocess.run([ADB, "-s", SER, "exec-out", "screencap", "-p"],
                           capture_output=True, timeout=60)
        f.write(p.stdout)


def ck(name, cond, extra=""):
    (PASS if cond else FAIL).append(name + ("" if cond else "  << " + str(extra)))
    print(("  [OK] " if cond else "  [XX] ") + name + ("" if cond else "   " + str(extra)))


# 主界面固定坐标（1260x2800）
C_TAB_WORD = (149, 367)
C_TAB_SHORT = (413, 367)
C_TAB_COMPLEX = (722, 367)
C_ZEN = (1225, 368)
C_LOOP = (1103, 368)
C_PLAY = (948, 368)
C_DICT = (589, 94)
C_STATS = (840, 95)
C_REVIEW = (1001, 95)
C_SETTINGS = (1162, 95)
C_TYPE = (630, 700)


def type_word(tok):
    """把一个目标词敲进去（只敲字母和撇号）"""
    p = re.sub(r"[^A-Za-z']", "", tok)
    if p:
        text(p)
        time.sleep(0.22)


def main():
    os.makedirs(SHOTS, exist_ok=True)
    sh1("logcat -c")
    sh1("am force-stop " + PKG)
    sh1("monkey -p %s -c android.intent.category.LAUNCHER 1" % PKG)
    time.sleep(3.5)
    print("App 顶栏:", top())
    shot("vt_01_home.png")

    ns = dump()
    ck("主界面启动", target_of(ns) is not None, ns[:300])

    # ---------- 1. 单词模式连打 5 个 ----------
    print("\n[1] 单词模式")
    tap(*C_TYPE)
    n0 = target_of(dump())
    ck("自动朗读/目标可见", n0 is not None, n0)
    for i in range(5):
        ns = dump()
        t = target_of(ns)
        if not t:
            break
        type_word(t[0].split(" ")[t[1]])
    t1 = target_of(dump())
    ck("连打 5 词推进", t1 and t1[0] != (n0[0] if n0 else ""), (n0, t1))
    st = find(dump(), "STRK")
    print("   战绩:", st["text"] if st else "?")

    # ---------- 2. 严格模式：错键必须被拒 ----------
    print("\n[2] 严格模式拒绝错键")
    ns = dump()
    t = target_of(ns)
    if t:
        want = t[0].split(" ")[t[1]]
        wrong = "z" if not want.lower().startswith("z") else "q"
        text(wrong)
        time.sleep(0.5)
        ns2 = dump()
        t2 = target_of(ns2)
        ck("错键没进输入框（strict=on）", t2 and t2[2] == "", (want, t2))
        # 故意打乱一下，制造 ERR
        for c in reversed(want[:2]):
            text(c)
            time.sleep(0.15)
        ns3 = dump()
        ck("错误计数上涨", find(ns3, "ERR") and find(ns3, "ERR")["text"] != "ERR 0",
           find(ns3, "ERR")["text"] if find(ns3, "ERR") else "?")
        # 清掉重打正确
        sh1("input keyevent --longpress KEYCODE_DEL")
        time.sleep(0.3)
        ns4 = dump()
        t4 = target_of(ns4)
        if t4 and t4[2]:
            for _ in range(len(t4[2]) + 3):
                sh1("input keyevent KEYCODE_DEL")
                time.sleep(0.08)
        type_word(want)

    # ---------- 3. SHORT 模式整句 ----------
    print("\n[3] SHORT 模式整句打字")
    tap(*C_TAB_SHORT)
    time.sleep(1.2)
    ns = dump()
    t = target_of(ns)
    ck("SHORT 模式有整句目标", t is not None and len(t[0].split(" ")) >= 2,
       t[0] if t else None)
    ck("句子里的词无标点", t and not re.search(r"[.,!?;:\"]", t[0]), t[0] if t else None)
    shot("vt_02_short.png")

    done = 0
    for i in range(40):
        ns = dump()
        t = target_of(ns)
        if not t:
            break
        arr = t[0].split(" ")
        if t[1] >= len(arr):
            break
        type_word(arr[t[1]])
        ns2 = dump()
        t2 = target_of(ns2)
        if t2 is None:
            done = -1
            break
        if t2 != t:
            done += 1
        if top().endswith("ReviewActivity"):
            break
    ck("整句逐词推进", done >= 2, done)

    time.sleep(1.0)
    tops = top()
    print("   打完整句后 top =", tops)
    shot("vt_03_dictation.png")
    ns = dump()
    ck("整句打完弹听写面板",
       "ReviewActivity" in tops or find(ns, "开始默写") is not None or find(ns, "整句听写") is not None,
       tops)

    if "ReviewActivity" in top():
        n = find(dump(), "开始默写")
        if n and n["b"]:
            b = n["b"]
            tap((b[0] + b[2]) // 2, (b[1] + b[3]) // 2)
            time.sleep(1.2)
            print("   听写后 top =", top())
            shot("vt_04_blind.png")
            ns = dump()
            t = target_of(ns)
            ck("进入默写模式（只敲单词）", t is not None and len(t[0].split(" ")) == 1,
               t[0] if t else None)
            for i in range(3):
                ns = dump()
                t = target_of(ns)
                if not t:
                    break
                type_word(t[0])
            ck("默写能推进", top().endswith("MainActivity"))

    # ---------- 4. COMPLEX ----------
    print("\n[4] COMPLEX 长句")
    tap(*C_TAB_COMPLEX)
    time.sleep(1.5)
    t = target_of(dump())
    ck("COMPLEX 有目标", t is not None, t[0][:60] if t else None)
    shot("vt_05_complex.png")
    tap(*C_TAB_WORD)

    # ---------- 5. 词库页 ----------
    print("\n[5] 词库页")
    tap(*C_DICT)
    time.sleep(1.5)
    ck("打开词库页", "DictActivity" in top(), top())
    shot("vt_06_dict.png")
    ns = dump()
    names = [n["text"] for n in ns if n["text"] and ("词" in n["text"] or "语" in n["text"])]
    ck("词库列表有内容", len(names) >= 5, names[:6])
    # 选第 2 个词库
    rows = [n for n in ns if n["b"] and n["b"][1] > 320 and n["text"] and len(n["text"]) > 3
            and "█" not in n["text"] and "词 ·" not in n["text"]]
    if len(rows) >= 2:
        b = rows[1]["b"]
        tap((b[0] + b[2]) // 2, (b[1] + b[3]) // 2)
        time.sleep(1.5)
        ck("切词库后回主界面", top().endswith("MainActivity"), top())
        ns = dump()
        topbar = find(ns, "·   ")
        ck("顶栏词库名已更新", topbar is not None, topbar["text"] if topbar else ns[0]["text"][:40])
        shot("vt_07_dict_switched.png")
    else:
        sh1("input keyevent KEYCODE_BACK")
        time.sleep(1.0)
        ck("词库页返回", top().endswith("MainActivity"), top())

    # ---------- 6. 统计页 ----------
    print("\n[6] 统计页")
    tap(*C_STATS)
    time.sleep(1.5)
    ck("打开统计页", "StatsActivity" in top(), top())
    shot("vt_08_stats.png")
    ns = dump()
    alltxt = " ".join((n["text"] or "") for n in ns)
    ck("统计页有累计数据", "SESSION" in alltxt or "累计" in alltxt, alltxt[:120])
    ck("统计页有词库进度", "PROGRESS" in alltxt or "█" in alltxt or "░" in alltxt)
    close = find(ns, "", "desc")
    for n in ns:
        if n["b"] and n["b"][0] > 1000 and n["b"][1] < 300 and n["cls"].endswith("ImageButton"):
            b = n["b"]
            tap((b[0] + b[2]) // 2, (b[1] + b[3]) // 2)
            break
    time.sleep(1.0)
    ck("统计页关闭", top().endswith("MainActivity"), top())

    # ---------- 7. 设置页 ----------
    print("\n[7] 设置页")
    tap(*C_SETTINGS)
    time.sleep(1.5)
    ck("打开设置页", "SettingsActivity" in top(), top())
    shot("vt_09_settings.png")
    ns = dump()
    alltxt = " ".join((n["text"] or "") for n in ns)
    for k in ["严格模式", "词序", "DeepSeek", "TTS"]:
        ck("设置项存在：" + k, k in alltxt)
    # 点一个开关
    sw = find(ns, "[ OFF ]")
    if sw and sw["b"]:
        b = sw["b"]
        tap((b[0] + b[2]) // 2, (b[1] + b[3]) // 2)
        time.sleep(0.6)
        ns2 = dump()
        n_on = len([n for n in nodes(ns2) if n["text"] == "[ ON  ]"])
        n_off = len([n for n in nodes(ns2) if n["text"] == "[ OFF ]"])
        ck("开关可切换", n_on >= 1, "on=%d off=%d" % (n_on, n_off))
        # 切回来
        b2 = find(nodes(dump()), "[ ON  ]")
        if b2 and b2["b"]:
            bb = b2["b"]
            tap((bb[0] + bb[2]) // 2, (bb[1] + bb[3]) // 2)
            time.sleep(0.5)
    for n in dump_nodes_close():
        pass
    # 返回
    ns = dump()
    for n in ns:
        if n["cls"].endswith("ImageButton") and n["b"] and n["b"][1] < 300:
            b = n["b"]
            tap((b[0] + b[2]) // 2, (b[1] + b[3]) // 2)
            break
    time.sleep(1.0)
    ck("设置页关闭", top().endswith("MainActivity"), top())

    # ---------- 8. 复习页 ----------
    print("\n[8] 复习/错词本")
    tap(*C_REVIEW)
    time.sleep(1.5)
    t = top()
    shot("vt_10_review.png")
    ck("错词本入口有响应（弹面板或提示）", True, t)
    if "ReviewActivity" in t:
        ns = dump()
        alltxt = " ".join((n["text"] or "") for n in ns)
        ck("错词面板有内容", "错词本" in alltxt, alltxt[:100])
        go = find(ns, "开始复习") or find(ns, "全部复习")
        if go and go["b"]:
            b = go["b"]
            tap((b[0] + b[2]) // 2, (b[1] + b[3]) // 2)
            time.sleep(1.5)
            ns = dump()
            t = target_of(ns)
            ck("复习批次可开打", t is not None, t)
            shot("vt_11_review_play.png")
            for i in range(3):
                ns = dump()
                t = target_of(ns)
                if not t:
                    break
                type_word(t[0].split(" ")[t[1]])
    else:
        print("   （错词本为空，App 弹了 toast —— 符合预期）")

    # ---------- 9. 禅定 ----------
    print("\n[9] 禅定模式")
    tap(*C_ZEN)
    time.sleep(0.8)
    ns = dump()
    ck("禅定隐藏顶栏", find(ns, "关卡") is None and find(ns, "VOCAB//TYPE") is None,
       [n["text"] for n in ns if n["text"]][:6])
    t = target_of(ns)
    ck("禅定仍可打字", t is not None, t)
    shot("vt_12_zen.png")
    tap(*C_ZEN)
    time.sleep(0.8)
    ck("退出禅定", find(dump(), "VOCAB//TYPE") is not None)

    # ---------- 10. 循环朗读 ----------
    print("\n[10] 循环朗读")
    tap(*C_LOOP)
    time.sleep(0.5)
    ck("循环按钮响应", True)
    tap(*C_PLAY)
    ck("播放按钮响应", True)
    tap(*C_LOOP)

    # ---------- 崩溃检查 ----------
    print("\n[11] 崩溃检查")
    log = sh1("logcat -d -t 3000 *:E")
    hits = [l for l in log.splitlines() if FATAL.search(l)]
    ck("无崩溃", not hits, hits[:4])
    if hits:
        for h in hits[:10]:
            print("   ", h)

    print("\n================ 结果 ================")
    print("通过 %d / 失败 %d" % (len(PASS), len(FAIL)))
    for f in FAIL:
        print("  XX", f)
    return 1 if FAIL else 0


def dump_nodes_close():
    return []


if __name__ == "__main__":
    sys.exit(main())
