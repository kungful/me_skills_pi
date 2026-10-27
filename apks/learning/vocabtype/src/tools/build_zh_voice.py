#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
把中文释义用微软神经语音预合成成 mp3，打包进 assets/zh/。

为什么这么做：手机上常有 Clash / v2ray 用 fake-ip 接管 DNS，
把 speech.platform.bing.com 指向 198.18.x.x，WebSocket 的 TLS 直接被掐
（SSLHandshakeException: connection closed），在线合成永远失败。
在电脑上合成好再打包，音质稳定且不依赖手机网络。

用法:
  python tools/build_zh_voice.py            # 默认合成当前词库(d0)
  python tools/build_zh_voice.py --all      # 所有词库（很慢，体积大）
  python tools/build_zh_voice.py --limit 50 # 只做前 50 条（测试用）
"""
import argparse
import asyncio
import glob
import hashlib
import io
import json
import os
import re
import sys
import time

DICT_DIR = os.path.join("app", "src", "main", "assets", "dicts")
OUT_DIR = os.path.join("app", "src", "main", "assets", "zh")
VOICE = "zh-CN-XiaoxiaoNeural"
CONCURRENCY = 16

# 和 App 里 Speaker.zhSpeech() 必须完全一致，否则查不到
def zh_speech(s: str) -> str:
    t = s or ""
    t = re.sub(r"[a-zA-Z]{1,6}\.\s*", " ", t)
    t = re.sub(r"[（(\[【].{0,20}?[)）\]】]", " ", t)
    t = re.sub(r"[；;·•/\\|｜、]+", "，", t)
    t = re.sub(r"[：:]+", " ", t)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"^[，。、\s]+", "", t)
    t = re.sub(r"[，。、\s]+$", "", t)
    return t.strip()[:180]


def key_of(text: str) -> str:
    """和 Voice.keyOf() 的中文分支对齐（只按内容，音色固定）"""
    return hashlib.sha1(("z|" + text.strip().lower()).encode("utf-8")).hexdigest()


def collect(use_all: bool, limit: int):
    files = sorted(glob.glob(os.path.join(DICT_DIR, "d*.json")))
    if not use_all:
        files = [os.path.join(DICT_DIR, "d0.json")]
    seen = {}
    for f in files:
        if not os.path.exists(f):
            continue
        try:
            d = json.load(io.open(f, encoding="utf-8"))
        except Exception:
            continue
        for w in d.get("words", []):
            if len(w) > 2 and w[2]:
                t = zh_speech(w[2])
                if t and t not in seen:
                    seen[t] = True
                    if limit and len(seen) >= limit:
                        return list(seen)
    return list(seen)


async def synth(text, sem, done_counter, total):
    import edge_tts
    async with sem:
        try:
            buf = b""
            async for ch in edge_tts.Communicate(text, VOICE).stream():
                if ch["type"] == "audio":
                    buf += ch["data"]
            if len(buf) > 512:
                path = os.path.join(OUT_DIR, key_of(text) + ".mp3")
                with open(path, "wb") as fp:
                    fp.write(buf)
                done_counter[0] += 1
                if done_counter[0] % 50 == 0:
                    print("  %d / %d" % (done_counter[0], total), flush=True)
                return True
        except Exception as e:
            print("  ! %s: %s" % (text[:12], str(e)[:60]), flush=True)
        return False


async def main_async(texts):
    sem = asyncio.Semaphore(CONCURRENCY)
    done = [0]
    t0 = time.time()
    await asyncio.gather(*[synth(t, sem, done, len(texts)) for t in texts])
    print("完成 %d / %d，用时 %.1fs" % (done[0], len(texts), time.time() - t0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    texts = collect(args.all, args.limit)
    # 跳过已有
    todo = [t for t in texts
            if not os.path.exists(os.path.join(OUT_DIR, key_of(t) + ".mp3"))]
    print("待合成 %d 条（已有 %d 条）" % (len(todo), len(texts) - len(todo)))
    if not todo:
        print_manifest()
        return
    asyncio.run(main_async(todo))
    print_manifest()


def print_manifest():
    files = glob.glob(os.path.join(OUT_DIR, "*.mp3"))
    total = sum(os.path.getsize(f) for f in files)
    print("assets/zh: %d 个文件，%.1f MB" % (len(files), total / 1048576))


if __name__ == "__main__":
    main()
