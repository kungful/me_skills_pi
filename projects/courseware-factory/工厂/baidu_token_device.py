# -*- coding: utf-8 -*-
"""百度网盘开放平台 · 设备码模式授权拿 access_token（不需要回调地址）。

用法：
  python 工厂/baidu_token_device.py            # 授权 + 写 .env
  python 工厂/baidu_token_device.py --poll-only # 只用已有 device_code 轮询

流程（文档：使用入门/接入授权/设备码模式授权）：
  1) GET https://openapi.baidu.com/oauth/2.0/device/code
        ?response_type=device_code&client_id=<AppKey>&scope=basic,netdisk
     → device_code / user_code / verification_url(二维码地址)
  2) 用户在浏览器里打开 verification_url（可扫码）登录并授权
  3) 轮询 https://openapi.baidu.com/oauth/2.0/token
        ?grant_type=device_token&code=<device_code>&client_id&client_secret
     → access_token(30天) / refresh_token(单次有效)

写回：C:/Users/hua/Documents/备份代码/baidu-netdisk-xianyu/baidu-netdisk-mcp/.env
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

ENV_PATH = r"C:\Users\hua\Documents\备份代码\baidu-netdisk-xianyu\baidu-netdisk-mcp\.env"
SCOPE = "basic,netdisk"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "pan.baidu.com"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        # 轮询 token 时「未授权」是 400，必须读 body，不能抛异常
        body = e.read().decode("utf-8", "replace")
        try:
            return json.loads(body)
        except Exception:
            return {"error": "http %s" % e.code, "body": body[:200]}


def read_env():
    conf = {}
    if os.path.exists(ENV_PATH):
        for line in open(ENV_PATH, encoding="utf-8", errors="replace"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            conf[k.strip()] = v.strip()
    return conf


def write_env(conf):
    order = ["BAIDU_APP_KEY", "BAIDU_SECRET_KEY", "BAIDU_REDIRECT_URI", "BAIDU_NETDISK_ACCESS_TOKEN"]
    lines = []
    for k in order:
        if k in conf:
            lines.append("%s=%s" % (k, conf[k]))
    for k, v in conf.items():
        if k not in order:
            lines.append("%s=%s" % (k, v))
    os.makedirs(os.path.dirname(ENV_PATH), exist_ok=True)
    open(ENV_PATH, "w", encoding="utf-8").write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--poll-only", action="store_true")
    ap.add_argument("--device-code", default="")
    args = ap.parse_args()

    conf = read_env()
    key = conf.get("BAIDU_APP_KEY", "").strip()
    secret = conf.get("BAIDU_SECRET_KEY", "").strip()
    if not key or not secret:
        print("[x] .env 里缺 BAIDU_APP_KEY / BAIDU_SECRET_KEY")
        print("    在开放平台控制台创建应用后，把 AppKey / SecretKey 填进：")
        print("   ", ENV_PATH)
        return 2

    device_code = args.device_code
    if not device_code and not args.poll_only:
        q = urllib.parse.urlencode({"response_type": "device_code", "client_id": key, "scope": SCOPE})
        d = get("https://openapi.baidu.com/oauth/2.0/device/code?" + q)
        print("[授权] device_code 接口返回:", json.dumps(d, ensure_ascii=False)[:300])
        if d.get("code") not in (0, "0", None) and "device_code" not in d:
            return 1
        device_code = d.get("device_code", "")
        print()
        print("  用户码 (user_code):", d.get("user_code"))
        print("  授权链接          :", d.get("verification_url"))
        print("  在浏览器打开上面的链接，登录并同意授权（也可扫二维码）")
        print("  下面会自动轮询，每 5 秒一次，最多等 10 分钟…")
        print()

    if not device_code:
        print("[x] 没有 device_code")
        return 2

    q = urllib.parse.urlencode({"grant_type": "device_token", "code": device_code,
                                "client_id": key, "client_secret": secret})
    url = "https://openapi.baidu.com/oauth/2.0/token?" + q
    deadline = time.time() + 600
    while time.time() < deadline:
        r = get(url)
        if "access_token" in r:
            print("[ok] 拿到 access_token，有效期 %s 秒" % r.get("expires_in"))
            conf["BAIDU_APP_KEY"] = key
            conf["BAIDU_SECRET_KEY"] = secret
            conf["BAIDU_NETDISK_ACCESS_TOKEN"] = r["access_token"]
            if r.get("refresh_token"):
                conf["BAIDU_REFRESH_TOKEN"] = r["refresh_token"]
            write_env(conf)
            print("[ok] 已写入", ENV_PATH)
            # 自检：调一次 uinfo
            u = get("https://pan.baidu.com/rest/2.0/xpan/nas?method=uinfo&access_token="
                    + urllib.parse.quote(r["access_token"]))
            print("[自检] uinfo:", json.dumps(u, ensure_ascii=False)[:200])
            return 0
        print("   等待授权中…", json.dumps(r, ensure_ascii=False)[:120])
        time.sleep(5)
    print("[x] 超时未授权")
    return 1


if __name__ == "__main__":
    sys.exit(main())
