# -*- coding: utf-8 -*-
"""课件工厂 · 网盘交付（一个课件 = 一个子文件夹 = 一条独立分享链接）

为什么这么做：所有课件放在同一个链接里，买家买一套就能看见全套 → 等于白送。
所以每套课件单独一个子文件夹（PDF + 原图/），单独一条带提取码的链接，
收款后只发那一条。

远端结构：
    /课件/<课题>/                 ← 这一个文件夹 = 一条分享链接
        <课题>.pdf
        原图/01_范画成品.jpg ...

用法（必须用它自己的 venv python，靠它复用 baidu-netdisk-mcp 的 API 层）：
    C:/Users/hua/Documents/备份代码/baidu-netdisk-xianyu/baidu-netdisk-mcp/.venv/Scripts/python.exe \
        工厂/netdisk_publish.py 项目/圣诞树-4-6岁/project.json --dry
    ... 工厂/netdisk_publish.py 项目/圣诞树-4-6岁/project.json --period 0

产出：项目/<课件>/交付/<名>/分享链接.json（链接 / 提取码 / 文件清单 / 时间）
      同时更新 发布台账 之外的「交付台账」：交付台账.json
"""
import argparse
import json
import os
import random
import re
import string
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MCP_DIR = r"C:/Users/hua/Documents/备份代码/baidu-netdisk-xianyu/baidu-netdisk-mcp"


def load_env():
    """把网盘 MCP 的 .env 读进环境（不依赖 MCP 进程）。"""
    for p in (os.path.join(MCP_DIR, ".env"),
              os.path.join(os.path.dirname(MCP_DIR), ".env")):
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def rand_pwd(n=4):
    pool = string.ascii_lowercase + string.digits
    return "".join(random.choice(pool) for _ in range(n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", help="project.json 路径")
    ap.add_argument("--remote-root", default="/课件", help="网盘根目录（默认 /课件）")
    ap.add_argument("--period", type=int, default=0, choices=[0, 1, 7, 30], help="有效期天数，0=永久")
    ap.add_argument("--pwd", default="", help="4 位提取码，默认随机")
    ap.add_argument("--dry", action="store_true", help="只打印计划，不联网")
    a = ap.parse_args()

    sys.path.insert(0, ROOT)
    sys.path.insert(0, os.path.join(ROOT, "工厂"))
    from project import Project
    proj = Project(a.project)
    name = proj.name.replace("《", "").replace("》", "")
    pack = os.path.join(proj.dir, "交付", name)
    if not os.path.isdir(pack):
        print("[x] 还没有交付包：%s" % pack)
        print("    先跑：python 工厂/deliver.py %s --zip" % a.project)
        return 2

    files = []
    for base, _dirs, fs in os.walk(pack):
        for f in sorted(fs):
            if f == "manifest.json" or f == "分享链接.json":
                continue
            full = os.path.join(base, f)
            rel = os.path.relpath(full, pack).replace("\\", "/")
            files.append((rel, full, os.path.getsize(full)))
    files.sort(key=lambda x: (0 if x[0].endswith(".pdf") else 1, x[0]))
    total = sum(f[2] for f in files)

    remote_deck = "%s/%s" % (a.remote_root.rstrip("/"), name)
    pwd = a.pwd or rand_pwd()
    print("课题      : %s" % name)
    print("本地包    : %s" % pack)
    print("文件      : %d 个 / %.1f MB" % (len(files), total / 1e6))
    print("远端目录  : %s/   （一个文件夹 = 一条链接）" % remote_deck)
    print("有效期    : %s   提取码: %s" % ("永久" if a.period == 0 else "%d 天" % a.period, pwd))
    for rel, _full, size in files:
        print("   %-42s %6.2f MB" % (rel, size / 1e6))
    if a.dry:
        print("\n[dry] 未联网。去掉 --dry 才会真的上传 + 建分享。")
        return 0

    load_env()
    token = (os.environ.get("BAIDU_NETDISK_ACCESS_TOKEN") or "").strip()
    if not token:
        print("\n[x] BAIDU_NETDISK_ACCESS_TOKEN 为空。")
        print("    去 https://pan.baidu.com/union/console/applist 建应用 → OAuth 授权 →")
        print("    把回调地址里的 access_token 填进：")
        print("    %s/.env" % MCP_DIR)
        print("    （只填 Token 一栏，然后重跑本命令）")
        return 3

    sys.path.insert(0, MCP_DIR)
    import server as nd  # noqa: E402  （复用它的 _api / 上传 / 分享实现）

    # 1) 建目录（已存在会返回 -7，忽略）
    for d in (a.remote_root, remote_deck, remote_deck + "/原图"):
        r = nd.make_dir(d, rtype=1)
        print("  dir  %-28s %s" % (d, r[:80].replace("\n", " ")))

    # 2) 上传
    ok_files = []
    for i, (rel, full, size) in enumerate(files, 1):
        rdir = remote_deck + "/原图" if rel.startswith("原图/") else remote_deck
        rname = os.path.basename(rel)
        print("  [%2d/%2d] %-34s ..." % (i, len(files), rel), end="", flush=True)
        r = nd.file_upload_local(full, rdir, rname, rtype=3)
        good = '"error"' not in r
        print(" %s" % ("OK" if good else "FAIL " + r[:120]))
        if good:
            ok_files.append(rel)

    if len(ok_files) != len(files):
        print("\n[!] 有 %d 个文件没传成功，先不建分享（避免发出残缺链接）"
              % (len(files) - len(ok_files)))
        return 4

    # 3) 找远端文件夹 fsid → 建分享
    lst = json.loads(nd.file_list(a.remote_root, num=500, raw=True))
    fsid = None
    for it in (lst.get("list") or []):
        if it.get("server_filename") == name:
            fsid = it.get("fs_id")
            break
    if not fsid:
        print("[x] 在 %s 里找不到文件夹 %s" % (a.remote_root, name))
        return 5
    r = nd.file_sharelink_set(json.dumps([str(fsid)]), period=a.period, pwd=pwd, raw=True)
    data = json.loads(r) if r.strip().startswith("{") else {}
    link = data.get("link") or data.get("shortlink") or ""
    if not link:
        print("[x] 建分享失败：%s" % r[:300])
        return 6

    rec = dict(deck=name, link=link, pwd=pwd, period=a.period,
               remote=remote_deck, shareid=data.get("shareid"), fsid=fsid,
               files=[f[0] for f in files], total_mb=round(total / 1e6, 2),
               at=time.strftime("%Y-%m-%d %H:%M:%S"))
    json.dump(rec, open(os.path.join(pack, "分享链接.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    led = os.path.join(ROOT, "交付台账.json")
    allrec = json.load(open(led, encoding="utf-8")) if os.path.exists(led) else {}
    allrec[name] = rec
    json.dump(allrec, open(led, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("\n✅ 交付链接：%s" % link)
    print("   提取码：%s" % pwd)
    print("   （这条链接只含《%s》一套，别的课件不会露出去）" % name)
    print("   记录：%s" % os.path.join(pack, "分享链接.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
