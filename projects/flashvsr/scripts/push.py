#!/usr/bin/env python3
"""把本地代码推到容器里，强制 LF 行尾（Windows 的 CRLF 会把 bash 脚本搞坏）。

用法：
    python scripts/push.py            # 推全部
    python scripts/push.py some.sh    # 额外推一些文件到 /root/build/

目录布局两套都支持（自动找文件）：
    扁平版：  ./app.py  ./simple.html  ./push.py           （老的本地开发目录）
    仓库版：  ./app/app.py  ./scripts/push.py               （本仓库 projects/flashvsr/）

环境变量 XGC_INST 指定实例 id（同 xr.py）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xr

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE) if os.path.basename(HERE) in ("scripts", "app") else HERE

# (文件名, 容器内路径)
PAIRS = [
    ("01_env.sh", "/root/build/01_env.sh"),
    ("02_weights.sh", "/root/build/02_weights.sh"),
    ("03_smoke.sh", "/root/build/03_smoke.sh"),
    ("04_weights.sh", "/root/build/04_weights.sh"),
    ("flashvsr-webui.sh", "/root/build/flashvsr-webui.sh"),
    ("restart_webui.sh", "/root/build/restart_webui.sh"),
    ("dl.py", "/root/app/dl.py"),
    ("app.py", "/root/app/app.py"),
    ("uploader.py", "/root/app/uploader.py"),
    ("simple.html", "/root/app/simple.html"),
]


def find(name):
    for d in (ROOT, HERE, os.path.join(ROOT, "app"), os.path.join(ROOT, "scripts")):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    return None


def main(extra):
    s = xr.sftp()
    missing = []
    for name, remote in PAIRS:
        local = find(name)
        if not local:
            missing.append(name)
            continue
        data = open(local, "rb").read().replace(b"\r\n", b"\n")
        with s.file(remote, "wb") as f:
            f.write(data)
        print("%-22s -> %-30s %d bytes" % (name, remote, len(data)))
    for arg in extra:
        local = find(os.path.basename(arg)) or arg
        data = open(local, "rb").read().replace(b"\r\n", b"\n")
        with s.file("/root/build/" + os.path.basename(arg), "wb") as f:
            f.write(data)
        print("extra %-16s -> /root/build/%s" % (os.path.basename(arg), os.path.basename(arg)))
    xr.run("chmod +x /root/build/*.sh 2>/dev/null; mkdir -p /root/app /root/build")
    if missing:
        print("!! 本机没找到（跳过）：%s" % ", ".join(missing))
    print("done")


if __name__ == "__main__":
    main(sys.argv[1:])
