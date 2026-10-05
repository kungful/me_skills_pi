# -*- coding: utf-8 -*-
"""把 post.json 发到小红书，并且**发完自己核实**（不靠"success"两个字）。

用法：
    python publish_post.py <post.json>                 # 按 post.json 里的 visibility 发
    python publish_post.py <post.json> --visibility public
    python publish_post.py <post.json> --dry-run       # 只校验，不发

默认拦三道：
  · 正文里还有【】占位符  -> 拒绝（说明文案没写完）
  · 我主页已有同标题笔记  -> 拒绝（防重复发布）
  · 超小红书硬性上限      -> 拒绝
要强行发加 --force。
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xhs  # noqa: E402
from xhs import utf8_stdout  # noqa: E402

VIS = {"tmp": "仅自己可见", "public": "公开可见", "friends": "仅互关好友可见"}


def link(note):
    if not note:
        return ""
    u = "https://www.xiaohongshu.com/explore/" + str(note["id"])
    if note.get("xsec_token"):
        u += "?xsec_token=%s&xsec_source=pc_user" % note["xsec_token"]
    return u


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("post", help="prep_post.py 生成的 post.json")
    ap.add_argument("--visibility", choices=list(VIS) + list(VIS.values()))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="无视占位符/重复标题检查")
    ap.add_argument("--allow-dup", action="store_true", help="允许同标题重复发布")
    ap.add_argument("--original", action="store_true", help="声明原创")
    a = ap.parse_args()

    with open(a.post, encoding="utf-8") as f:
        post = json.load(f)

    visibility = post.get("visibility") or "仅自己可见"
    if a.visibility:
        visibility = VIS.get(a.visibility, a.visibility)

    print("标题:", post.get("title"))
    print("规则:", xhs.rule_summary(post))
    print("可见:", visibility)

    fatal = xhs.validate(post)
    if fatal:
        print()
        print("✗ 校验不通过：")
        for p in fatal:
            print("   -", p)
        if not a.force:
            return 2
        print("  （--force：仍然继续）")

    body = post.get("content") or ""
    if "【" in body or "】" in body:
        print()
        print("✗ 正文里还有【】占位符，文案没写完：")
        for line in body.splitlines():
            if "【" in line:
                print("   ", line.strip()[:70])
        if not (a.force or a.dry_run):
            return 2

    # 服务端活着吗
    h = xhs.health()
    if not h:
        print("✗ 连不上 MCP 服务（%s）。先启动：" % xhs.BASE)
        print("   C:\\Users\\hua\\tools\\xiaohongshu-mcp\\启动MCP.cmd")
        return 2
    st = xhs.login_status()
    d = st.get("data") or st
    if not (d.get("is_logged_in") or d.get("data", {}).get("is_logged_in")):
        print("✗ 未登录（或登录状态接口异常）:", json.dumps(st, ensure_ascii=False)[:200])
        print("   登录：C:\\Users\\hua\\tools\\xiaohongshu-mcp\\xiaohongshu-login.exe")
        return 2
    print("登录: OK")

    before = xhs.my_notes()
    titles = [n["title"] for n in before]
    print("发布前我的笔记数:", len(before))

    if post.get("title") in titles and not (a.allow_dup or a.force):
        print()
        print("✗ 我主页已经有同标题笔记，拒绝重复发布：", post["title"])
        print("   要再发一条加 --allow-dup（内容不同的话建议改标题）")
        return 2

    if a.dry_run:
        print()
        print("--dry-run：校验通过，没有真的发。")
        return 0

    print()
    print("发布中…（上传 %d 张图，通常 1-2 分钟，不要打断）" % len(post.get("images") or []))
    t0 = time.time()
    r = xhs.publish(post["title"], post["content"], post["images"],
                    tags=post.get("tags"), visibility=visibility, is_original=a.original)
    dt = time.time() - t0
    print("耗时 %.0fs  success=%s  message=%s" % (dt, r.get("success"), r.get("message")))

    if not r.get("success"):
        print("✗ 发布失败:", json.dumps(r, ensure_ascii=False)[:600])
        return 1

    # ---- 核实：不是看接口返回，而是回主页看笔记是不是真多了 ----
    print()
    print("核实中（重新拉我的主页）…")
    after = xhs.my_notes()
    new = [n for n in after if n["id"] not in {b["id"] for b in before}]
    hit = [n for n in after if n["title"] == post["title"]]
    print("发布后我的笔记数:", len(after), "（+%d）" % (len(after) - len(before)))
    if new:
        for n in new:
            print("  新增: %s  [%s]" % (n["title"], n["type"]))
            print("        %s" % link(n))
    elif hit:
        print("  ! 没检测到新增，但已存在同标题笔记（可能是刷新延迟）:", hit[0]["id"])
    else:
        print("  ! 主页没看到这条笔记 —— 可能发布被平台拦截，去创作中心确认")
    print()
    print("✓ 完成。可见范围:", visibility)
    if visibility != "公开可见":
        print("  想给大家看：python %s %s --visibility public"
              % (os.path.basename(__file__), a.post))
    return 0


if __name__ == "__main__":
    sys.exit(main())
