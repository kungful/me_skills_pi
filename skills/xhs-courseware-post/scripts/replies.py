# -*- coding: utf-8 -*-
"""看通知 / 看笔记评论 / 回复评论 —— 一条龙的最后一段。

用法：
    python replies.py unread                          # 未读数
    python replies.py list [--tab mentions|likes|connections] [--limit 20]
    python replies.py reply --id <comment_id> --text "谢谢喜欢～"
    python replies.py like  --id <comment_id> [--unlike]
    python replies.py note-comments <feed_id> [--token <xsec_token>]
    python replies.py stats                           # 粉丝/赞藏/笔记数

⚠️ 评论里**不要出现微信/QQ/电话/外链** —— 小红书把站外引流当违规，轻则限流重则封号。
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xhs  # noqa: E402
from xhs import utf8_stdout  # noqa: E402


def ts(t):
    try:
        return datetime.datetime.fromtimestamp(int(t)).strftime("%m-%d %H:%M")
    except Exception:
        return str(t)


def inner(resp):
    """返回 data.data（这服务端老是把结果嵌两层）"""
    return ((resp or {}).get("data") or {}).get("data") or {}


def comment_text(item):
    for key in ("comment", "content", "text"):
        v = item.get(key)
        if isinstance(v, dict):
            v = v.get("content") or v.get("text")
        if v:
            return str(v)
    return ""


def comment_id(item):
    c = item.get("comment")
    if isinstance(c, dict) and c.get("id"):
        return c["id"]
    return item.get("id")


def cmd_unread(a):
    d = inner(xhs.unread_count())
    if not d:
        print("拿不到未读数（服务没起？）")
        return 1
    print("未读: 评论@ %s  赞和收藏 %s  新增关注 %s  合计 %s"
          % (d.get("mentions"), d.get("likes"), d.get("connections"), d.get("unread")))
    return 0


def cmd_list(a):
    r = xhs.notifications(tab=a.tab, limit=a.limit)
    d = inner(r)
    items = d.get("items") or []
    print("tab=%s  共 %d 条（filtered=%s）" % (d.get("tab"), len(items), d.get("filtered")))
    if not items:
        print("（没有新通知）")
    for it in items:
        frm = it.get("from") or {}
        line = "[%s] %-12s %s  %s" % (ts(it.get("time")), frm.get("nickname", "?"),
                                      it.get("title", ""), comment_text(it))
        print(line.strip())
        if it.get("feed_title"):
            print("     笔记:", it["feed_title"])
        print("     id=%s  user_id=%s" % (comment_id(it), frm.get("user_id", "")))
    return 0


def cmd_reply(a):
    if not a.text:
        print("要带 --text")
        return 2
    bad = [w for w in ("微信", "wx", "vx", "加我", "QQ", "http", "电话", "号码") if w.lower() in a.text.lower()]
    if bad:
        print("✗ 回复里出现站外引流词 %s —— 小红书会判违规，删掉再发" % bad)
        return 2
    r = xhs.reply_notification(a.id, a.text)
    print("success=%s  %s" % (r.get("success"), r.get("message")))
    return 0 if r.get("success") else 1


def cmd_like(a):
    r = xhs.like_notification(a.id, unlike=a.unlike)
    print("success=%s  %s" % (r.get("success"), r.get("message")))
    return 0 if r.get("success") else 1


def cmd_note_comments(a):
    r = xhs.feed_detail(a.feed_id, a.token, load_all_comments=True)
    if not r.get("success"):
        print("失败:", json.dumps(r, ensure_ascii=False)[:300])
        return 1
    d = inner(r)
    cs = d.get("comments") or d.get("commentList") or []
    print("笔记:", d.get("title") or (d.get("noteCard") or {}).get("displayTitle", ""))
    print("评论 %d 条" % len(cs))
    for c in cs:
        u = c.get("user") or c.get("userInfo") or {}
        print("  [%s] %-14s %s" % (ts(c.get("time") or c.get("createTime")),
                                   u.get("nickname", "?"), c.get("content") or c.get("text") or ""))
        print("       comment_id=%s user_id=%s" % (c.get("id"), u.get("userId") or u.get("user_id")))
    if not cs:
        print("（还没有人评论；有人评论时这里会列出来，再按自己的节奏回）")
    return 0


def cmd_stats(a):
    p = xhs.my_profile()
    d = inner(p)
    b = d.get("userBasicInfo") or {}
    print("账号:", b.get("nickname"), "| 小红书号:", b.get("redId"), "| 简介:", repr(b.get("desc")))
    for i in d.get("interactions") or []:
        print("  %s: %s" % (i.get("name"), i.get("count")))
    feeds = d.get("feeds") or []
    print("公开笔记:", len(feeds))
    for f in feeds[:5]:
        c = f.get("noteCard") or {}
        print("  -", c.get("displayTitle"))
    return 0


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("unread")
    p.set_defaults(func=cmd_unread)

    p = sub.add_parser("list")
    p.add_argument("--tab", default="mentions")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("reply")
    p.add_argument("--id", required=True)
    p.add_argument("--text", required=True)
    p.set_defaults(func=cmd_reply)

    p = sub.add_parser("like")
    p.add_argument("--id", required=True)
    p.add_argument("--unlike", action="store_true")
    p.set_defaults(func=cmd_like)

    p = sub.add_parser("note-comments")
    p.add_argument("feed_id")
    p.add_argument("--token", default="")
    p.set_defaults(func=cmd_note_comments)

    p = sub.add_parser("stats"); p.set_defaults(func=cmd_stats)

    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
