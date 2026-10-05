# -*- coding: utf-8 -*-
"""小红书 MCP（HTTP API）薄封装 + 小红书硬性规则校验。

本地跑着 xiaohongshu-mcp 的话，直接打它的 HTTP API 就行 —— 不走 MCP 客户端，
所以**没有 60 秒单请求超时**（发布要 1~2 分钟，走 MCP 会在提交那一刻被掐断）。
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("XHS_MCP_BASE", "http://127.0.0.1:18060")

# ---- 小红书硬性上限（超了发布页会报错，这里前置拦掉）----
TITLE_MAX = 20        # 标题字数
CONTENT_MAX = 1000    # 正文字数
TAGS_MAX = 10         # 话题标签数（服务端超过会自动截断前 10 个）
IMAGES_MAX = 18       # 图文图片数


def utf8_stdout():
    """Windows 控制台默认 GBK，打印中文/emoji 会炸。"""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def calc_title_len(s):
    """复刻服务端 xhsutil.CalcTitleLength：非 ASCII 算 2 字节，ASCII 算 1，最后 (n+1)//2。

    注意按 UTF-16 码元算（emoji 占 2 个码元），跟 Go 的 utf16.Encode 一致。
    """
    raw = s.encode("utf-16-le")
    n = 0
    for i in range(0, len(raw), 2):
        unit = int.from_bytes(raw[i:i + 2], "little")
        n += 2 if unit > 127 else 1
    return (n + 1) // 2


def is_ascii_path(p):
    return all(ord(c) < 128 for c in p)


def call(path, payload=None, method=None, timeout=600, qs=None):
    url = BASE + path
    if qs:
        url += "?" + urllib.parse.urlencode(qs)
    data, headers = None, {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
        method = method or "POST"
    req = urllib.request.Request(url, data=data, headers=headers, method=method or "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return json.loads(body)
        except Exception:
            return {"success": False, "message": "HTTP %s: %s" % (e.code, body[:300])}
    except Exception as e:
        return {"success": False, "message": "%s: %s" % (type(e).__name__, e)}


# ---------------- 接口 ----------------
def health():
    return call("/health", timeout=15)


def login_status(timeout=120):
    """注意：这个接口要拉起浏览器校验，通常 10 秒以上，别用短超时判死活。"""
    return call("/api/v1/login/status", timeout=timeout)


def my_profile(timeout=300):
    """我的主页：data.data.userBasicInfo / interactions / feeds"""
    return call("/api/v1/user/me", timeout=timeout)


def my_notes(timeout=300):
    r = my_profile(timeout=timeout)
    if not r.get("success"):
        return []
    inner = r.get("data", {}).get("data", {}) or {}
    out = []
    for f in inner.get("feeds", []) or []:
        c = f.get("noteCard", {}) or {}
        out.append({
            "id": f.get("id"),
            "xsec_token": f.get("xsecToken"),
            "title": c.get("displayTitle") or "",
            "type": c.get("type") or "",
        })
    return out


def publish(title, content, images, tags=None, visibility=None, is_original=False,
            schedule_at=None, products=None, timeout=900):
    payload = {"title": title, "content": content, "images": list(images)}
    if tags:
        payload["tags"] = list(tags)
    if visibility:
        payload["visibility"] = visibility
    if is_original:
        payload["is_original"] = True
    if schedule_at:
        payload["schedule_at"] = schedule_at
    if products:
        payload["products"] = list(products)
    return call("/api/v1/publish", payload, timeout=timeout)


def feed_detail(feed_id, xsec_token, load_all_comments=False, timeout=300):
    return call("/api/v1/feeds/detail",
                {"feed_id": feed_id, "xsec_token": xsec_token,
                 "load_all_comments": bool(load_all_comments)}, timeout=timeout)


def search_feeds(keyword, timeout=300):
    return call("/api/v1/feeds/list", timeout=timeout) if not keyword else \
        call("/api/v1/feeds/search", qs={"keyword": keyword}, timeout=timeout)


def unread_count(timeout=180):
    """返回嵌套的 data.data.{mentions,likes,connections,unread}"""
    return call("/api/v1/notifications/unread", timeout=timeout)


def notifications(tab="", limit=20, timeout=300):
    return call("/api/v1/notifications/list", {"tab": tab, "limit": limit}, timeout=timeout)


def reply_notification(comment_id, content, timeout=300):
    return call("/api/v1/notifications/reply",
                {"comment_id": comment_id, "content": content}, timeout=timeout)


def like_notification(comment_id, unlike=False, timeout=300):
    return call("/api/v1/notifications/like",
                {"comment_id": comment_id, "unlike": unlike}, timeout=timeout)


def post_comment(feed_id, xsec_token, content, timeout=300):
    return call("/api/v1/feeds/comment",
                {"feed_id": feed_id, "xsec_token": xsec_token, "content": content},
                timeout=timeout)


def reply_comment(feed_id, xsec_token, comment_id, content, user_id="", timeout=300):
    body = {"feed_id": feed_id, "xsec_token": xsec_token,
            "comment_id": comment_id, "content": content}
    if user_id:
        body["user_id"] = user_id
    return call("/api/v1/feeds/comment/reply", body, timeout=timeout)


# ---------------- 校验 ----------------
def validate(post):
    """发布前把能拦的都拦掉，返回问题列表（空 = 可以发）。"""
    problems = []
    title = post.get("title") or ""
    content = post.get("content") or ""
    tags = post.get("tags") or []
    images = post.get("images") or []

    if not title.strip():
        problems.append("标题是空的")
    n = calc_title_len(title)
    if n > TITLE_MAX:
        problems.append("标题 %d 字，超过上限 %d（按小红书算法：汉字=1，ASCII=0.5）" % (n, TITLE_MAX))
    if len(content) > CONTENT_MAX:
        problems.append("正文 %d 字，超过上限 %d" % (len(content), CONTENT_MAX))
    if len(tags) > TAGS_MAX:
        problems.append("标签 %d 个，超过上限 %d（服务端会截断，但建议自己先删）" % (len(tags), TAGS_MAX))
    if not images:
        problems.append("没有图片")
    if len(images) > IMAGES_MAX:
        problems.append("图片 %d 张，超过上限 %d" % (len(images), IMAGES_MAX))
    for p in images:
        if not is_ascii_path(p):
            problems.append("图片路径含中文/非 ASCII 字符（已知翻车点）: %s" % p)
        if not os.path.exists(p):
            problems.append("图片不存在: %s" % p)
    seen = set()
    for p in images:
        if p in seen:
            problems.append("同一张图重复出现: %s" % p)
        seen.add(p)
    return problems


def rule_summary(post):
    title = post.get("title") or ""
    return "标题 %d/%d 字 · 正文 %d/%d 字 · 标签 %d/%d 个 · 图片 %d 张" % (
        calc_title_len(title), TITLE_MAX, len(post.get("content") or ""), CONTENT_MAX,
        len(post.get("tags") or []), TAGS_MAX, len(post.get("images") or []))
