# -*- coding: utf-8 -*-
"""发布台账：保证「一个课题只发一次、一张图不重复出现」。

为什么要有：同样的成品图反复发，粉丝一眼就认出来（"怎么又是这只大象"），
平台也会判重复/低质。所以发布前必须先查台账，查完再生成草稿。

台账默认位置：<项目根>/发布台账.json，结构：
{
  "decks": {
    "<norm 课题名>": {
      "name": "小象洗澡-4-6岁",
      "age": "4-6岁",
      "notes": [{"id": "...", "title": "...", "at": "2026-11-01T10:00:00"}],
      "image_md5": ["...", "..."]
    }
  },
  "images": {"<md5>": {"deck": "小象洗澡-4-6岁", "slot": "范画成品", "at": "..."}}
}

命令：
    python published.py --sync          # 从我的主页把已有笔记拉进台账（初始化）
    python published.py --list          # 已发课题 / 未发课题
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DEFAULT_ROOT = r"C:\Users\hua\Documents\备份代码\小红书卖课件"
LEDGER_NAME = "发布台账.json"

# 只有这些词出现在标题里才说明是「课件发布」；生活/技术笔记不算
DECK_HINTS = ("课件", "创意美术", "美术课")

_RE_AGE = re.compile(r"\d+\s*-\s*\d+\s*岁|\d+\s*到\s*\d+\s*岁|\d+\s*岁")


def ledger_path(root=None):
    root = root or os.environ.get("XHS_PROJECT_ROOT") or DEFAULT_ROOT
    return os.path.join(root, LEDGER_NAME)


def load(path=None):
    p = path or ledger_path()
    if not os.path.exists(p):
        return {"decks": {}, "images": {}, "_path": p}
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    d.setdefault("decks", {})
    d.setdefault("images", {})
    d["_path"] = p
    return d


def save(d):
    p = d.pop("_path", None) or ledger_path()
    d["_path"] = p
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)
    return p


def norm(s):
    """课题名归一化：去《》/年龄/页数/通用后缀/标点/空白，用来跨标题匹配。"""
    s = s or ""
    s = re.sub(r"\d+\s*页", "", s)
    s = re.sub(r"\d+\s*[pP](?![a-zA-Z])", "", s)
    s = s.replace("《", "").replace("》", "")
    s = _RE_AGE.sub("", s)
    for w in ("创意美术课件", "美术课件", "课件", "创意美术", "少儿美术", "幼儿美术",
              "原创", "分享", "PPT", "pptx"):
        s = s.replace(w, "")
    s = re.sub(r"[\s·・\-—_！!？?，,。.：:｜|、/\\()（）\[\]【】]+", "", s)
    s = re.sub(r"\d+$", "", s)
    return s.strip().lower()


def deck_key(name, age=""):
    return norm(str(name) + str(age or ""))


def is_deck_title(title):
    return any(h in (title or "") for h in DECK_HINTS)


def find_deck(d, name, age=""):
    """按归一化名字找已发记录，返回 (key, rec) 或 (None, None)。"""
    k = deck_key(name, age)
    if not k:
        return None, None
    if k in d["decks"]:
        return k, d["decks"][k]
    # 容错：标题里只写了课题名、没写年龄
    base = norm(name)
    for kk, rec in d["decks"].items():
        if kk and (kk == base or base == norm(rec.get("name", ""))):
            return kk, rec
    return None, None


def image_seen(d, md5):
    return d["images"].get(md5)


def note_ids(d):
    out = set()
    for rec in d["decks"].values():
        for n in rec.get("notes", []):
            if n.get("id"):
                out.add(n["id"])
    return out


def add_note(d, name, age, title, note_id, md5s=None, slugs=None, path=None):
    """发布成功后登记（同一 note_id 幂等）。"""
    k = deck_key(name, age) or norm(name)
    rec = d["decks"].setdefault(k, {
        "name": name,
        "age": age,
        "notes": [],
        "image_md5": [],
    })
    if not rec.get("name"):
        rec["name"] = name
    if age and not rec.get("age"):
        rec["age"] = age
    if note_id and note_id not in {n.get("id") for n in rec["notes"]}:
        rec["notes"].append({
            "id": note_id,
            "title": title,
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    md5s = md5s or []
    slugs = slugs or []
    for i, h in enumerate(md5s):
        if not h:
            continue
        if h not in rec["image_md5"]:
            rec["image_md5"].append(h)
        d["images"].setdefault(h, {
            "deck": name,
            "slot": slugs[i] if i < len(slugs) else "",
            "at": now,
        })
    return k


def sync_from_notes(d, notes):
    """把主页笔记标题补进台账（历史数据没有图片 md5，只能按课题名去重）。"""
    added = 0
    for n in notes or []:
        title = n.get("title") or ""
        if not is_deck_title(title):
            continue
        m = re.search(r"《([^》]+)》", title)
        name = (m.group(1) if m else title)
        age = (_RE_AGE.search(title).group(0) if _RE_AGE.search(title) else "")
        k = deck_key(name, age) or norm(name)
        if not k:
            continue
        if n.get("id") in note_ids(d):
            continue
        rec = d["decks"].setdefault(k, {"name": name, "age": age, "notes": [], "image_md5": []})
        rec["notes"].append({
            "id": n.get("id"),
            "title": title,
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        added += 1
    return added


def project_root(path_hint=None):
    if path_hint:
        return os.path.dirname(os.path.abspath(path_hint)) if path_hint.endswith(".json") else path_hint
    return os.environ.get("XHS_PROJECT_ROOT") or DEFAULT_ROOT


def unused_decks(root=None):
    """扫 项目/*/project.json，返回没发过的 [(项目目录名, project.json 路径)]。"""
    root = root or DEFAULT_ROOT
    pdir = os.path.join(root, "项目")
    d = load()
    out = []
    if not os.path.isdir(pdir):
        return out
    for name in sorted(os.listdir(pdir)):
        pj = os.path.join(pdir, name, "project.json")
        if not os.path.exists(pj):
            continue
        try:
            with open(pj, encoding="utf-8") as f:
                data = json.load(f)
            meta = data.get("meta", {})
            nm = meta.get("name") or name
            age = meta.get("age") or ""
        except Exception:
            nm, age = name, ""
        k, rec = find_deck(d, nm, age)
        if rec and rec.get("notes"):
            continue
        out.append((name, pj))
    return out


def md5_file(p, chunk=1 << 20):
    h = hashlib.md5()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--sync", action="store_true", help="从我的主页抓笔记初始化台账")
    ap.add_argument("--list", action="store_true", help="列出已发 / 未发课题")
    a = ap.parse_args()

    d = load()
    if a.sync:
        import xhs
        notes = xhs.my_notes(timeout=300)
        n = sync_from_notes(d, notes)
        p = save(d)
        print("主页笔记 %d 条，新增进台账 %d 条 -> %s" % (len(notes), n, p))
    if a.list or not (a.sync):
        print("台账:", d.get("_path"))
        used = [(k, len(r.get("notes", []))) for k, r in d["decks"].items() if r.get("notes")]
        print("已发课题 %d 个:" % len(used))
        for k, n in used:
            print("  - %s  (%d 篇)" % (k, n))
        un = unused_decks()
        print("未发课题 %d 个:" % len(un))
        for name, _pj in un:
            print("  + %s" % name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
