# -*- coding: utf-8 -*-
"""百度网盘 · 网页版 API 上传（绕开开放平台的上传权限限制）。

为什么需要它：开放平台 xpan/file 的 create 步骤返回 errno 31500，
老 PCS 接口返回 31064 file is not authorized —— 都是「应用没有上传写权限」；
但同一 token 的 share 接口正常。而网页版上传接口（api/precreate + d.pcs.baidu.com
superfile2 + api/create）走的是 BDUSS cookie，不看开放平台的应用权限。

⚠️ 2026-11-07 实测：直接用浏览器上传器更稳（playwright setInputFiles，input 带 multiple），
本脚本作为无浏览器时的备选。两者都用网页版接口。

用法：
  python 工厂/baidu_web_upload.py <本地目录> <网盘目标目录>
  python 工厂/baidu_web_upload.py <本地目录> <网盘目标目录> --dry

依赖：C:/Users/hua/.baidu_pan_cookies.json（浏览器登录态，由 playwright 抽取；cookie 会过期，
      过期后重新抽取：playwright 里 page.context().cookies() 写到这个文件）
"""
import hashlib
import io
import json
import os
import re
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8")

COOKIE_FILE = r"C:\Users\hua\.baidu_pan_cookies.json"
CHUNK = 4 * 1024 * 1024
PAN = "https://pan.baidu.com"
PCS = "https://d.pcs.baidu.com"
WEB_COMMON = {"app_id": "250528", "channel": "chunlei", "web": "1", "clienttype": "0"}


def load_cookies():
    jar = requests.cookies.RequestsCookieJar()
    for c in json.load(io.open(COOKIE_FILE, encoding="utf-8")):
        jar.set(c["name"], c["value"], domain=c["domain"], path=c.get("path", "/"))
    return jar


def get_bdstoken(jar):
    """网页版接口必须带 bdstoken，否则 create 返回 errno 404。
    从网盘首页 HTML 里正则抓（注意：不是 window.locals.userInfo.bdstoken）。"""
    r = requests.get(PAN + "/disk/main", cookies=jar, timeout=30)
    m = re.search(r'bdstoken["\s:=]+([A-Za-z0-9]+)', r.text)
    if not m:
        raise RuntimeError("没抓到 bdstoken（cookie 可能已过期）")
    return m.group(1)


def md5_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def md5_block(data):
    return hashlib.md5(data).hexdigest()


def mkdir(jar, path, token):
    r = requests.post(PAN + "/api/create", cookies=jar,
                      params=dict(WEB_COMMON, bdstoken=token, isdir="1", rtype="1"),
                      data={"path": path, "isdir": "1", "block_list": "[]"}, timeout=30)
    try:
        return r.json()
    except Exception:
        return {"raw": r.text[:200]}


def upload_one(jar, local, remote, target_dir, token):
    size = os.path.getsize(local)
    blocks = []
    with open(local, "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            blocks.append(md5_block(b))
    if not blocks:
        blocks = [md5_block(b"")]
    bl = json.dumps(blocks)
    mtime = str(int(time.time()))

    pre = requests.post(PAN + "/api/precreate", cookies=jar,
                        params=dict(WEB_COMMON, bdstoken=token, rtype="1"),
                        data={"path": remote, "size": str(size), "isdir": "0",
                              "autoinit": "1", "block_list": bl, "rtype": "1",
                              "target_path": target_dir, "local_mtime": mtime},
                        timeout=60).json()
    if pre.get("errno") not in (0, None):
        return {"ok": False, "stage": "precreate", "resp": pre}

    uploadid = pre.get("uploadid", "")
    if pre.get("return_type") != 1:
        seq = 0
        with open(local, "rb") as f:
            while True:
                b = f.read(CHUNK)
                if not b:
                    break
                r = requests.post(
                    PCS + "/rest/2.0/pcs/superfile2",
                    params={"method": "upload", "type": "tmpfile", "path": remote,
                            "uploadid": uploadid, "partseq": str(seq)},
                    cookies=jar, files={"file": (os.path.basename(local), b)}, timeout=600)
                if r.status_code >= 400:
                    return {"ok": False, "stage": "upload partseq=%d" % seq,
                            "resp": {"http": r.status_code, "body": r.text[:200]}}
                seq += 1

    cr = requests.post(PAN + "/api/create", cookies=jar,
                       params=dict(WEB_COMMON, bdstoken=token, isdir="0", rtype="1"),
                       data={"path": remote, "size": str(size), "isdir": "0",
                             "block_list": bl, "uploadid": uploadid, "rtype": "1",
                             "target_path": target_dir, "local_mtime": mtime},
                       timeout=60)
    try:
        cj = cr.json()
    except Exception:
        cj = {"raw": cr.text[:300]}
    if cj.get("errno") not in (0, None):
        return {"ok": False, "stage": "create", "resp": cj}
    return {"ok": True, "path": remote, "fs_id": cj.get("fs_id"), "uploadid": uploadid}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    local_dir, remote_dir = sys.argv[1], sys.argv[2]
    dry = "--dry" in sys.argv
    jar = load_cookies()
    token = get_bdstoken(jar)
    print("  bdstoken:", token[:8] + "…")

    # 目录
    parts = [p for p in remote_dir.split("/") if p]
    cur = ""
    for p in parts:
        cur += "/" + p
        r = mkdir(jar, cur, token)
        print("  dir  %-40s errno=%s" % (cur, r.get("errno")))

    files = []
    for root, _, names in os.walk(local_dir):
        for n in names:
            full = os.path.join(root, n)
            rel = os.path.relpath(full, local_dir).replace("\\", "/")
            files.append((rel, full))
    files.sort()
    print("  待传 %d 个文件" % len(files))
    if dry:
        for rel, full in files:
            print("   -", rel, os.path.getsize(full))
        return 0

    bad = []
    for i, (rel, full) in enumerate(files, 1):
        remote = remote_dir.rstrip("/") + "/" + rel
        target = remote.rsplit("/", 1)[0]
        print("  [%2d/%2d] %-32s" % (i, len(files), rel), end="", flush=True)
        r = upload_one(jar, full, remote, target, token)
        if r.get("ok"):
            print(" OK")
        else:
            print(" FAIL", json.dumps(r, ensure_ascii=False)[:160])
            bad.append(rel)
    if bad:
        print("\n[x] %d 个文件失败：%s" % (len(bad), bad))
        return 4
    print("\n[ok] 全部上传完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
