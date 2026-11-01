#!/usr/bin/env python3
"""多线程 + 断点续传下载器（HF 机房链路会频繁 SSL EOF，必须无限重试 + 重算偏移）。

用法: dl.py <url> <outfile> [线程数]

每个 chunk 落在 <outfile>.partN。任何一次连接中断，重试时都会用当前文件大小重算
Range 起点，所以不会重复写入、也不会漏字节。可随时 Ctrl-C / 重跑，已下载部分保留。
"""
import os
import ssl
import sys
import threading
import time
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124"}
CTX = ssl.create_default_context()
MAX_ATTEMPTS = 3000


def total_size(url):
    req = urllib.request.Request(url, headers=dict(UA, Range="bytes=0-0"))
    r = urllib.request.urlopen(req, timeout=60, context=CTX)
    cr = r.headers.get("Content-Range")
    r.close()
    if not cr or "/" not in cr:
        raise RuntimeError("服务端不支持 Range: %r" % cr)
    return int(cr.split("/")[-1])


def grab(url, path, start, end, idx):
    want = end - start + 1
    attempt = 0
    idle = 0
    while True:
        have = os.path.getsize(path) if os.path.exists(path) else 0
        if have >= want:
            return True
        h = dict(UA)
        h["Range"] = "bytes=%d-%d" % (start + have, end)
        before = have
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60, context=CTX)
            if r.status not in (200, 206):
                raise RuntimeError("HTTP %s" % r.status)
            with open(path, "ab") as f:
                while True:
                    b = r.read(1 << 16)
                    if not b:
                        break
                    f.write(b)
        except Exception as e:
            pass
        after = os.path.getsize(path) if os.path.exists(path) else 0
        if after > before:
            idle = 0
        else:
            idle += 1
        attempt += 1
        if idle > 40:
            print("  chunk%d 连续 40 次无进展，放弃" % idx, flush=True)
            return False
        if attempt > MAX_ATTEMPTS:
            return False
        time.sleep(0.3 if after > before else min(1 + idle, 10))


def main():
    url, out = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 16
    if not os.path.dirname(out) == "":
        os.makedirs(os.path.dirname(out), exist_ok=True)
    total = total_size(url)
    if os.path.exists(out) and os.path.getsize(out) == total:
        print("已完整 %s" % out, flush=True)
        return 0
    print("== %s  %.2f GB  %d 线程  %s" % (os.path.basename(out), total / 1e9, n,
                                           time.strftime("%H:%M:%S")), flush=True)
    step = total // n
    spans = [(i * step, (total - 1) if i == n - 1 else (i + 1) * step - 1) for i in range(n)]
    parts = ["%s.part%d" % (out, i) for i in range(n)]
    t0 = time.time()
    ok = [None] * n

    def work(i):
        ok[i] = grab(url, parts[i], spans[i][0], spans[i][1], i)

    th = [threading.Thread(target=work, args=(i,), daemon=True) for i in range(n)]
    [t.start() for t in th]
    last = -1
    while any(t.is_alive() for t in th):
        got = sum(os.path.getsize(p) for p in parts if os.path.exists(p))
        pct = 100.0 * got / total
        if pct - last >= 1.0 or pct == 100.0:
            el = max(time.time() - t0, 1e-9)
            eta = (total - got) / max(got / el, 1)
            print("   %5.1f%%  %.2f/%.2f GB  %.2f MB/s  ETA %.0f min"
                  % (pct, got / 1e9, total / 1e9, got / 1048576 / el, eta / 60), flush=True)
            last = pct
        time.sleep(20)
    got = sum(os.path.getsize(p) for p in parts if os.path.exists(p))
    if got != total:
        print("!! 未完成 %d/%d，part 文件保留可续传" % (got, total), flush=True)
        return 2
    with open(out, "wb") as f:
        for p in parts:
            with open(p, "rb") as g:
                while True:
                    b = g.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
    for p in parts:
        os.remove(p)
    print("== DONE %s %.2f GB 用时 %.0f min" % (out, total / 1e9, (time.time() - t0) / 60), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
