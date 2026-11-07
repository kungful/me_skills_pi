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
    ap.add_argument("--record", default="",
                    help="手动兜底：网盘里已手工上传并分享好，把链接传进来只做记账（不联网）")
    ap.add_argument("--link-pwd", default="", help="配合 --record：4 位提取码")
    ap.add_argument("--keep-old", action="store_true",
                    help="保留网盘上的同名旧文件夹（默认会先移进回收站再重建，避免旧文件残留在链接里）")
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

    # ★★ 铁律：一个子文件夹只能装**一套**课件。
    # 混进第二个 PDF，就等于买家付一套的钱拿到一套库 —— 这是这个项目唯一致命的错误。
    pdfs = [r[0] for r in files if r[0].lower().endswith(".pdf")]
    if len(pdfs) != 1:
        print("[x] 拒绝上传：交付包里必须**恰好 1 个** PDF，现在 %d 个：" % len(pdfs))
        for x in pdfs:
            print("      -", x)
        print("    一套课件 = 一个子文件夹 = 一条链接。多套合传 = 买一套拿走全部。")
        return 2
    if pdfs[0][:-4] != name:
        print("[x] 拒绝上传：PDF 名「%s」与课题文件夹名「%s」不一致。" % (pdfs[0][:-4], name))
        print("    链接里的命名必须能对上商品页，否则卖家发错、买家收错。")
        return 2
    bad_words = ("合集", "全套", "打包", "all-", "bundle", "系列")
    if any(w in name for w in bad_words):
        print("[x] 拒绝上传：文件夹名「%s」含合集/打包字样。一套一链接，别做合集。" % name)
        return 2
    if len(files) > 40:
        print("[x] 拒绝上传：%d 个文件偏多了（单套应约 17 个）。是不是把两套拼一起了？" % len(files))
        return 2

    remote_deck = "%s/%s" % (a.remote_root.rstrip("/"), name)
    pwd = a.pwd or rand_pwd()
    print("课题      : %s" % name)
    print("本地包    : %s" % pack)
    print("文件      : %d 个 / %.1f MB" % (len(files), total / 1e6))
    print("远端目录  : %s/   （一个文件夹 = 一条链接）" % remote_deck)
    print("有效期    : %s   提取码: %s" % ("永久" if a.period == 0 else "%d 天" % a.period, pwd))
    for rel, _full, size in files:
        print("   %-42s %6.2f MB" % (rel, size / 1e6))
    # ---- 手动兜底路径：链接已在网盘网页版手工建好，这里只记账（仍校验"一套只有1个PDF"）----
    if a.record:
        link = a.record.strip()
        if not (link.startswith("https://pan.baidu.com/s/") or link.startswith("https://pan.baidu.com/share/")):
            print("[x] 不像百度网盘分享链接：%s" % link)
            return 2
        pwd = a.link_pwd or a.pwd
        rec = dict(deck=name, link=link, pwd=pwd, period=a.period, remote=remote_deck,
                   shareid=None, fsid=None, source="manual",
                   files=[f[0] for f in files], total_mb=round(total / 1e6, 2),
                   at=time.strftime("%Y-%m-%d %H:%M:%S"))
        json.dump(rec, open(os.path.join(pack, "分享链接.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        led = os.path.join(ROOT, "交付台账.json")
        allrec = json.load(open(led, encoding="utf-8")) if os.path.exists(led) else {}
        allrec[name] = rec
        json.dump(allrec, open(led, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("✅ 已记账（手动上传）")
        print("   课题：%s" % name)
        print("   链接：%s" % link)
        print("   提取码：%s" % (pwd or "（无）"))
        print("   记录：%s" % os.path.join(pack, "分享链接.json"))
        print("   提醒：确认网盘上该文件夹里**只有这 1 个 PDF**（一套一链接）。")
        return 0

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

    # 0) 旧文件夹先整个清掉（进回收站）——不然上版的旧文件会残在链接里，买家看到两份
    lst0 = json.loads(nd.file_list(a.remote_root, num=500, raw=True))
    old = [it for it in (lst0.get("list") or []) if it.get("server_filename") == name]
    if old and not a.keep_old:
        print("  旧文件夹已存在 → 移进回收站后重建（保证链接里只有这一套的新版）")
        r = nd.file_del(json.dumps([remote_deck], ensure_ascii=False), async_mode=0)
        print("  del  %-28s %s" % (remote_deck, str(r)[:80].replace("\n", " ")))
    elif old:
        print("  [!] --keep-old：保留旧文件夹，旧版残留文件不会被清掉")

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

    # 3) 建链接前再核一遍：远端该文件夹里的文件数必须与本地一致
    lst_chk = json.loads(nd.file_list(remote_deck, num=500, raw=True))
    n_pdf = sum(1 for it in (lst_chk.get("list") or [])
                if str(it.get("server_filename", "")).lower().endswith(".pdf"))
    if n_pdf != 1:
        print("[x] 远端 %s 里有 %d 个 PDF（应该正好 1 个），不建链接。" % (remote_deck, n_pdf))
        print("    先人工看一眼网盘，这一套的链接不能把别的课件带出去。")
        return 4

    # 4) 找远端文件夹 fsid → 建分享
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
