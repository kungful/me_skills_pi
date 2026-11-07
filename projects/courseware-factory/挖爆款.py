# -*- coding: utf-8 -*-
"""挖爆款.py —— 从小红书抓「少儿美术课件」赛道的爆款笔记，建本地参考库。

为什么要它：课件模板僵硬的根因是**闭门造车**。先看别人什么画风/封面/标题在跑量，
再回头改出图 prompt，才有依据。

用法：
    python 挖爆款.py                    # 默认 6 个关键词，抓爆款 top40，下封面
    python 挖爆款.py --top 60 --imgs 3  # 抓更多、每篇多下几张图
    python 挖爆款.py --detail 60        # 连正文+评论一起抓（慢，~15s/篇）
    python 挖爆款.py --dry              # 只搜索，不下载（快，验证关键词）

产出：
    参考/爆款库/<rank>_<点赞>_<标题>/
        cover.jpg / 02.jpg ...   图片
        meta.json                标题/正文/标签/互动/评论
    参考/爆款库/index.json       全量结构化数据
    参考/爆款库/爆款清单.md      人读清单（按点赞排序）
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:18060"
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "参考", "爆款库")

KEYWORDS = [
    "少儿美术课件",
    "创意美术课件ppt",
    "幼儿创意美术课件",
    "儿童创意美术课",
    "4-6岁创意美术",
    "美术课件 范画",
]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36")


# ---------- 基础 HTTP ----------

def _get(path, **params):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return json.loads(urllib.request.urlopen(req, timeout=90).read())


def _post(path, payload):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"User-Agent": UA, "Content-Type": "application/json"},
        method="POST",
    )
    return json.loads(urllib.request.urlopen(req, timeout=120).read())


def health():
    _get("/health")


# ---------- 工具 ----------

def n(s):
    """'1.4万' -> 14000 ; '8986' -> 8986"""
    if s is None:
        return 0
    s = str(s).strip()
    if not s:
        return 0
    if s.endswith("万"):
        try:
            return int(float(s[:-1]) * 10000)
        except ValueError:
            return 0
    s = re.sub(r"[^\d]", "", s)
    return int(s) if s else 0


def slug(t, limit=18):
    t = re.sub(r"[\\/:*?\"<>|\s]+", "_", t or "untitled")
    t = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]", "", t)
    return t[:limit].strip("_") or "untitled"


def download(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 2048:
        return True
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.xiaohongshu.com/"})
    for attempt in range(3):
        try:
            data = urllib.request.urlopen(req, timeout=120).read()
            if len(data) < 1024:
                raise IOError("too small %d" % len(data))
            tmp = dest + ".part"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, dest)
            return True
        except Exception as e:
            if attempt == 2:
                print("      [x] 图下载失败 %s" % str(e)[:80])
                return False
            time.sleep(3)


def to_jpg(src, dst):
    """webp -> jpg，方便人和视觉模型看。PIL 缺失就直接改名拷贝。"""
    try:
        from PIL import Image
    except ImportError:
        if not os.path.exists(dst):
            os.replace(src, dst)
        return
    try:
        im = Image.open(src)
        im = im.convert("RGB")
        maxw = 1440
        if im.width > maxw:
            im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
        im.save(dst, "JPEG", quality=90)
        os.remove(src)
    except Exception as e:
        print("      [!] 转 jpg 失败(%s)，保留原图" % str(e)[:60])


# ---------- 抓取 ----------

def search_all(keywords, per_kw=20, pause=8):
    """多关键词搜索 + 去重。返回 {id: feed}"""
    pool = {}
    for kw in keywords:
        try:
            d = _get("/api/v1/feeds/search", keyword=kw, sort_by="popularity_descending")
            feeds = (d.get("data") or {}).get("feeds") or []
        except Exception as e:
            print("  [x] 搜索失败 %s: %s" % (kw, str(e)[:80]))
            time.sleep(pause)
            continue
        new = 0
        for f in feeds:
            fid = f.get("id")
            if not fid or fid in pool:
                continue
            nc = f.get("noteCard") or {}
            ii = nc.get("interactInfo") or {}
            cover = ((nc.get("cover") or {}).get("urlDefault")
                     or (nc.get("cover") or {}).get("urlPre") or "")
            pool[fid] = {
                "id": fid,
                "xsec_token": f.get("xsecToken", ""),
                "title": nc.get("displayTitle") or "",
                "author": ((nc.get("user") or {}).get("nickname") or ""),
                "author_id": ((nc.get("user") or {}).get("userId") or ""),
                "likes": n(ii.get("likedCount")),
                "collects": n(ii.get("collectedCount")),
                "comments": n(ii.get("commentCount")),
                "shares": n(ii.get("sharedCount")),
                "cover_url": cover,
                "kw": kw,
            }
            new += 1
        print("  [%s] +%d 条（累计 %d）" % (kw, new, len(pool)))
        time.sleep(pause)
    return pool


def detail(fid, tok):
    d = _post("/api/v1/feeds/detail", {"feed_id": fid, "xsec_token": tok})
    payload = (d.get("data") or {}).get("data") or {}
    note = payload.get("note") or {}
    cmts = ((payload.get("comments") or {}).get("list")) or []
    return note, cmts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=40, help="按点赞取前 N 篇")
    ap.add_argument("--imgs", type=int, default=2, help="每篇下载几张图（1=只封面）")
    ap.add_argument("--detail", type=int, default=0, help="对前 N 篇抓正文+评论（慢）")
    ap.add_argument("--detail-pause", type=float, default=6.0)
    ap.add_argument("--keywords", default="", help="逗号分隔，覆盖默认")
    ap.add_argument("--dry", action="store_true", help="只搜索不下载")
    args = ap.parse_args()

    health()
    kws = [k.strip() for k in args.keywords.split(",") if k.strip()] or KEYWORDS

    print("== 1/3 搜索 %d 个关键词 ==" % len(kws))
    pool = search_all(kws)
    if not pool:
        print("没搜到东西，检查 MCP 是否在跑 + 是否已登录")
        return 1

    ranked = sorted(pool.values(), key=lambda x: -x["likes"])
    print("\n== 2/3 爆款榜（按点赞）==")
    for i, x in enumerate(ranked[:20], 1):
        print("  %2d. %6d赞 %5d藏 %4d评  %s  @%s" % (
            i, x["likes"], x["collects"], x["comments"], x["title"][:26], x["author"][:12]))

    if args.dry:
        return 0

    os.makedirs(OUT, exist_ok=True)
    picked = ranked[:args.top]
    print("\n== 3/3 抓取前 %d 篇（详情前 %d 篇）==" % (len(picked), args.detail))

    for i, x in enumerate(picked, 1):
        folder = os.path.join(OUT, "%02d_%d_%s" % (i, x["likes"], slug(x["title"])))
        os.makedirs(folder, exist_ok=True)
        x["folder"] = os.path.basename(folder)
        meta_path = os.path.join(folder, "meta.json")
        note = None
        cmts = []

        if i <= args.detail or not os.path.exists(meta_path):
            try:
                note, cmts = detail(x["id"], x["xsec_token"])
            except Exception as e:
                print("  [x] %02d 详情失败: %s" % (i, str(e)[:80]))

        if note:
            x["title"] = note.get("title") or x["title"]
            x["desc"] = note.get("desc") or ""
            x["images"] = [im.get("urlDefault") or im.get("urlPre")
                           for im in (note.get("imageList") or [])]
        else:
            x.setdefault("images", [])

        # 下载封面 + 前几张
        urls = ([x.get("cover_url")] if x.get("cover_url") else []) + (x.get("images") or [])
        urls = [u for u in urls if u]
        seen = set()
        got = 0
        for j, u in enumerate(urls):
            key = u.split("!")[0]
            if key in seen:
                continue
            seen.add(key)
            name = "cover" if got == 0 else "%02d" % (got + 1)
            raw = os.path.join(folder, name + ".raw")
            dst = os.path.join(folder, name + ".jpg")
            if download(u, raw):
                to_jpg(raw, dst)
                got += 1
            if got >= max(1, args.imgs):
                break

        x["comments_top"] = [c.get("content", "") for c in cmts[:12]]
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(x, f, ensure_ascii=False, indent=2)
        print("  %02d. [%d图] %s" % (i, got, x["title"][:34]))
        time.sleep(args.detail_pause)

    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as f:
        json.dump(ranked, f, ensure_ascii=False, indent=2)

    with open(os.path.join(OUT, "爆款清单.md"), "w", encoding="utf-8") as f:
        f.write("# 少儿美术课件 · 小红书爆款榜\n\n")
        f.write("抓取时间：%s　共 %d 篇（关键词 %d 个）\n\n" % (
            time.strftime("%Y-%m-%d %H:%M"), len(ranked), len(kws)))
        f.write("| # | 赞 | 藏 | 评 | 标题 | 作者 | 图 |\n|---|---|---|---|---|---|---|\n")
        for i, x in enumerate(ranked, 1):
            f.write("| %d | %d | %d | %d | %s | %s | %s |\n" % (
                i, x["likes"], x["collects"], x["comments"],
                x["title"].replace("|", "/"), x["author"], x.get("folder", "")))
        f.write("\n## 标题词频（帮起标题）\n\n")
        words = {}
        for x in ranked:
            for w in re.findall(r"[\u4e00-\u9fa5]{2,4}", x["title"]):
                words[w] = words.get(w, 0) + 1
        top = sorted(words.items(), key=lambda kv: -kv[1])[:40]
        f.write("、".join("%s(%d)" % w for w in top) + "\n")
    print("\n完成 → %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
