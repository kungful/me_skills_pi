#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
VocabType 有道在线发音 —— 真机验收
用法:  python tools/voice_check.py

检查项
  1. 点顶栏 PLAY  → uid 网络计数是否增加（说明真的去下了音频）
  2. 设置页「发音缓存」条数 / 体积 是否变化
  3. 预下载当前词库：进度是否推进、缓存是否变大
  4. 播放期间 dumpsys audio 里有没有本 App 的活跃播放
  5. logcat 有没有异常
"""
import re
import subprocess
import sys
import time

ADB = r"C:\Users\hua\Documents\platform-tools\adb.exe"
DEV = ["-s", sys.argv[1] if len(sys.argv) > 1 else "192.168.31.200:43297"]
PKG = "com.vocabtype.app"


def sh(*a, timeout=120):
    return subprocess.run([ADB] + DEV + list(a), capture_output=True, timeout=timeout).stdout


def text(*a):
    return sh(*a).decode("utf8", "replace")


def dump():
    sh("shell", "uiautomator dump /sdcard/u.xml")
    return text("shell", "cat /sdcard/u.xml")


def nodes(x):
    out = {}
    for m in re.finditer(r"<node[^>]*>", x):
        t = m.group(0)

        def g(k):
            mm = re.search(k + r'="([^"]*)"', t)
            return mm.group(1) if mm else ""
        b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', t)
        if not b:
            continue
        e = dict(text=g("text"), desc=g("content-desc"), cls=g("class"),
                 bounds=tuple(int(v) for v in b.groups()))
        rid = g("resource-id")
        if rid:
            out[rid.split("/")[-1]] = e
        out.setdefault("_all", []).append(e)
    return out


def alln(x):
    return nodes(x).get("_all", [])


def ct(b):
    return (b[0] + b[2]) // 2, (b[1] + b[3]) // 2


def tap(rid, x=None):
    x = x if x is not None else dump()
    n = nodes(x).get(rid)
    if not n:
        print("  ! 找不到 %s" % rid)
        return False
    px, py = ct(n["bounds"])
    sh("shell", "input", "tap", str(px), str(py))
    return True


def tapxy(px, py):
    sh("shell", "input", "tap", str(px), str(py))


def rx_bytes():
    o = text("shell", "dumpsys netstats detail")
    for line in o.splitlines():
        m = re.match(r"\s*10386\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$", line)
        if m:
            return int(m.group(1)), int(m.group(3))
    return -1, -1


def cache_line(x=None):
    """设置页里 '123 条 / 1.2 MB' 那一行"""
    for e in alln(x if x is not None else dump()):
        if re.search(r"^\d+ 条 / [\d.]+ MB$", e["text"] or ""):
            return e["text"]
    return None


def scroll_to(kw, tries=8):
    for _ in range(tries):
        x = dump()
        if any(kw in (e["text"] or "") for e in alln(x)):
            return x
        sh("shell", "input", "swipe", "630", "1900", "630", "900", "250")
        time.sleep(0.9)
    return dump()


def audio_playing():
    o = text("shell", "dumpsys audio")
    hits = [l.strip() for l in o.splitlines()
            if "started" in l and PKG in l]
    if not hits:
        hits = [l.strip() for l in o.splitlines()
                if re.search(r"state:started", l)]
    return hits[:3]


def main():
    print("=" * 64)
    print("0) 设备状态")
    print("  " + text("shell", "dumpsys window | grep -m1 mDreamingLockscreen").strip())
    sh("shell", "am", "start", "-n", PKG + "/.ui.MainActivity")
    time.sleep(3.5)
    x = dump()
    n = nodes(x)
    tv = next((e for e in alln(x) if e["desc"].startswith("VT|")), None)
    print("  当前目标: %s" % (tv["desc"] if tv else "?"))
    print("  打字区   : %s" % (n.get("typeView", {}).get("bounds")))

    print("=" * 64)
    print("1) 点 PLAY → 看网络计数")
    r0, t0 = rx_bytes()
    print("  播放前 rx=%d tx=%d" % (r0, t0))
    if not tv:
        print("  ! 读不到目标词，跳过")
    tap("btnPlay", x)
    time.sleep(0.4)
    print("  播放中 dumpsys audio: %s" % (audio_playing() or "（没抓到活跃播放）"))
    time.sleep(4)
    r1, t1 = rx_bytes()
    print("  播放后 rx=%d tx=%d   →  rx 增加 %d B" % (r1, t1, r1 - r0))

    print("=" * 64)
    print("2) 设置页「发音缓存」")
    tap("btnSettings")
    time.sleep(2.2)
    xs = scroll_to("发音缓存")
    before = cache_line(xs)
    print("  当前: %s" % before)

    print("=" * 64)
    print("3) 预下载当前词库")
    go = None
    for e in alln(xs):
        if e["text"] == "预下载当前词库":
            go = e
            break
    if go:
        tapxy(*ct(go["bounds"]))
        for i in range(24):
            time.sleep(2)
            line = cache_line()
            if line:
                print("    [%2ds] %s" % ((i + 1) * 2, line))
                if re.match(r"^\d+ 条", line) and i > 2:
                    break
        r2, _ = rx_bytes()
        print("  预下载后 rx=%d（本轮 +%d B）" % (r2, r2 - r1))
        print("  结束状态: %s" % cache_line())
    else:
        print("  ! 找不到「预下载当前词库」按钮")

    print("=" * 64)
    print("4) logcat 异常")
    log = text("logcat", "-d", "-t", "600")
    bad = [l for l in log.splitlines()
           if re.search(r"FATAL|AndroidRuntime|MediaPlayer.*error|E MediaPlayer", l)]
    print("  " + ("\n  ".join(bad[-10:]) if bad else "无"))
    print("=" * 64)


if __name__ == "__main__":
    main()
