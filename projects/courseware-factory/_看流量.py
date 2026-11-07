# -*- coding: utf-8 -*-
"""看流量.py —— 拉取我主页所有课件笔记的 点赞/收藏/评论，存快照 + 打印排行。
用法：
  python _看流量.py            # 拉一次，存快照
  python _看流量.py --diff     # 拉一次，并和上一次快照比增量
免费：只读接口，不消耗生成额度。
"""
import csv, importlib.util, json, os, sys, time, datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.abspath(__file__))
HIST = os.path.join(ROOT, "参考", "流量")
SNAP = os.path.join(HIST, "快照.jsonl")

spec = importlib.util.spec_from_file_location(
    "x", r"C:/Users/hua/.pi/agent/skills/xhs-courseware-post/scripts/xhs.py")
X = importlib.util.module_from_spec(spec)
spec.loader.exec_module(X)


def num(v):
    try:
        return int(str(v).replace("+", "").replace("万", "0000") or 0)
    except Exception:
        return 0


def fetch():
    notes = X.my_notes()
    rows = []
    for i, n in enumerate(notes):
        if "课件" not in (n.get("title") or ""):
            continue
        try:
            r = X.feed_detail(n["id"], n.get("xsec_token", ""))
            info = (((r.get("data") or {}).get("data") or {}).get("note") or {}).get("interactInfo") or {}
        except Exception as e:
            print("  ! %s 取数失败: %s" % (n["title"][:14], str(e)[:60]))
            info = {}
        rows.append({
            "title": n["title"], "id": n["id"], "token": n.get("xsec_token", ""),
            "like": num(info.get("likedCount")), "collect": num(info.get("collectedCount")),
            "comment": num(info.get("commentCount")), "share": num(info.get("sharedCount")),
        })
        time.sleep(0.6)
    return rows


def main():
    os.makedirs(HIST, exist_ok=True)
    rows = fetch()
    if not rows:
        sys.exit("没抓到课件笔记")
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    rows.sort(key=lambda r: (-r["like"], -r["collect"], -r["comment"]))
    print("\n%s  共 %d 条课件笔记" % (ts, len(rows)))
    print("%-30s %6s %6s %6s %6s  %s" % ("标题", "赞", "藏", "评", "分享", "合计"))
    print("-" * 78)
    for r in rows:
        print("%-30s %6d %6d %6d %6d  %6d"
              % (r["title"][:28], r["like"], r["collect"], r["comment"], r["share"],
                 r["like"] + r["collect"] + r["comment"]))
    t = sum(r["like"] for r in rows), sum(r["collect"] for r in rows), sum(r["comment"] for r in rows)
    print("-" * 78)
    print("%-30s %6d %6d %6d         %6d" % ("合计", t[0], t[1], t[2], sum(t)))

    prev = None
    if os.path.exists(SNAP):
        for line in open(SNAP, encoding="utf-8"):
            try:
                prev = json.loads(line)
            except Exception:
                pass
    with open(SNAP, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": ts, "rows": rows}, ensure_ascii=False) + "\n")
    with open(os.path.join(HIST, "流量.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["时间", "标题", "点赞", "收藏", "评论", "分享", "合计"])
        for r in rows:
            w.writerow([ts, r["title"], r["like"], r["collect"], r["comment"], r["share"],
                        r["like"] + r["collect"] + r["comment"]])

    if prev and "--diff" in sys.argv:
        old = {r["title"]: r for r in prev["rows"]}
        print("\n相对 %s 的增量：" % prev["ts"])
        for r in rows:
            o = old.get(r["title"])
            if not o:
                print("  [新] %s" % r["title"][:28])
                continue
            d = (r["like"] - o["like"], r["collect"] - o["collect"], r["comment"] - o["comment"])
            if any(d):
                print("  %-28s 赞+%d 藏+%d 评+%d" % (r["title"][:28], d[0], d[1], d[2]))
    print("\n快照: %s" % SNAP)


if __name__ == "__main__":
    main()
