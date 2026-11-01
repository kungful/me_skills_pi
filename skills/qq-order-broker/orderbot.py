#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
orderbot.py —— QQ 群 / 频道「找单 → 评估 → 对接 → 交付」流水线

分工：
  · 上游 ../qq-desktop-control/qq_ctl.py 负责唯一会留痕迹的部分（鼠标键盘、截图、限流）
  · 本文件只做：读屏（OCR）→ 打分（caps.json）→ 草稿（templates.json）→ 订单库落盘 → 交付骨架

红线（写死，不要改着玩）：
  1. 读屏用 OCR（纯像素，零副作用），不用 Ctrl+A/Ctrl+C（上游实测不可靠且污染剪贴板）
  2. 任何对外发送默认演练，必须显式 --arm
  3. 发送前必须 OCR 校验会话标题；校验不过就中止，宁可失败也不发错人
  4. 所有发送走 qq_ctl.Guard 限流（3s/20 每小时/120 每天），不提供覆盖开关
  5. 命中 caps.json 的 banned → 只允许 decline 模板

用法见 SKILL.md，或 python orderbot.py -h
"""
import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ORDERS = os.path.join(HERE, "orders")
SHOTS = os.path.join(HERE, "shots")
SEEN = os.path.join(ORDERS, "seen.json")

# 上游技能目录（只依赖它，不改它）
QQ_DIR = os.environ.get("QQ_DESKTOP_SKILL") or os.path.normpath(
    os.path.join(HERE, "..", "qq-desktop-control"))

STATUSES = ["candidate", "contacted", "qualified", "quoted",
            "accepted", "delivering", "delivered", "paid", "dead"]
STAGE_OK = {
    "ask":     ["candidate", "contacted"],
    "qualify": ["contacted", "qualified"],
    "quote":   ["qualified", "quoted"],
    "accept":  ["quoted", "accepted"],
    "progress": ["accepted", "delivering"],
    "deliver": ["delivering", "delivered"],
    "chase":   ["delivered", "paid"],
    "decline": STATUSES,
    "decline_banned": STATUSES,
    "close":   ["paid", "dead"],
}

# OCR 会把每个汉字拆成独立 word，这里把 CJK 之间的空格吃掉
CJK = r"\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uff00-\uffef"

NOISE = [
    r"^\d{1,2}\s*[:：]\s*\d{1,2}$",
    r"^\d{1,2}\s*[-/月]\s*\d{1,2}\s*日?$",
    r"^(昨天|今天|前天|星期[一二三四五六日天]|周[一二三四五六日天])\s*\d{0,2}\s*[:：]?\s*\d{0,2}$",
    r"^[0-9\s\-/:：.,，。]+$",
    r"^.{1,2}$",
]
NOISE_RE = [re.compile(p) for p in NOISE]

# 「这像不像一个需求」的意图词（区别于只是聊技术、发牢骚）
INTENT = ["求", "需要", "招", "有偿", "接单", "外包", "多少钱", "报价", "预算", "报酬", "酬劳", "谁帮", "找人", "单子", "活",
          "帮做", "帮我做", "能不能做", "可以做吗", "谁会", "找个", "找个人",
          "需求", "做个", "写个", "搞个", "付费", "重金", "有偿求", "接不接",
          "急", "什么时候", "工期", "私聊", "加我", "扣1", "详聊"]

PRICE_RE = re.compile(r"(\d{2,6})\s*(?:元|块|rmb|RMB|k|K|w|W|千|万)")
BUDGET_NUM_RE = re.compile(r"(?:预算|报酬|酬劳|价格|有偿|费用)\D{0,4}(\d{2,6})")

DEADLINE_KW = ["今天", "明天", "后天", "本周", "这周", "月底", "前", "急", "尽快", "马上", "截止", "工期", "天之内"]
BUDGET_KW = ["预算", "多少钱", "报价", "价格", "费用", "报酬", "¥", "元", "k", "w块", "付费", "有偿"]
FORMAT_KW = ["源码", "文档", "成品", "docx", "xlsx", "pdf", "apk", "代码", "文件", "发我", "交付", "远程"]
INPUT_KW = ["链接", "附件", "文件", "截图", "资料", "素材", "发你", "在群文件", "网盘"]


# ------------------------------------------------------------------ 基础工具
def jload(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def jdump(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


CAPS = jload(os.path.join(HERE, "caps.json"), {})
TPL = jload(os.path.join(HERE, "templates.json"), {})


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def norm(t):
    t = re.sub(r"\s+", "", t or "")
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", t)


def fingerprint(text):
    return hashlib.sha1(norm(text)[:80].encode("utf-8")).hexdigest()[:16]


def fmt(tpl, **kw):
    """模板渲染：{slot} 替换，缺的槽位保留原样便于发现。"""
    return re.sub(r"\{(\w+)\}", lambda m: str(kw.get(m.group(1), m.group(0))), tpl)


# ------------------------------------------------------------------ OCR 读屏
_ENGINE = None


def _engine():
    global _ENGINE
    if _ENGINE is None:
        from winsdk.windows.media.ocr import OcrEngine
        langs = list(OcrEngine.available_recognizer_languages)
        if not langs:
            raise RuntimeError("系统没装 OCR 语言包（需要 设置→时间和语言→语言→中文 OCR）")
        _ENGINE = OcrEngine.try_create_from_language(langs[0])
        if _ENGINE is None:
            raise RuntimeError("OCR 引擎创建失败（语言包缺失）")
    return _ENGINE


def ocr_lines(img_path):
    """返回 [{t,x,y,x2,y2}]，像素坐标。纯像素读取，不动鼠标键盘。"""
    import asyncio
    from winsdk.windows.graphics.imaging import BitmapDecoder
    from winsdk.windows.storage import StorageFile, FileAccessMode

    async def run(p):
        f = await StorageFile.get_file_from_path_async(p)
        s = await f.open_async(FileAccessMode.READ)
        d = await BitmapDecoder.create_async(s)
        bmp = await d.get_software_bitmap_async()
        r = await _engine().recognize_async(bmp)
        out = []
        for ln in r.lines:
            ws = list(ln.words)
            if not ws:
                continue
            txt = " ".join(w.text for w in ws)
            txt = re.sub(r"(?<=[%s])\s+(?=[%s])" % (CJK, CJK), "", txt)
            txt = re.sub(r"\s+(?=[，。、；：？！）】」』])", "", txt)
            rects = [w.bounding_rect for w in ws]
            out.append({
                "t": txt.strip(),
                "x": min(r.x for r in rects),
                "y": min(r.y for r in rects),
                "x2": max(r.x + r.width for r in rects),
                "y2": max(r.y + r.height for r in rects),
            })
        return out

    return asyncio.run(run(os.path.abspath(img_path)))


def img_size(path):
    from PIL import Image
    with Image.open(path) as im:
        return im.size


def lines_to_blocks(lines, w, h, x_min=None, y_min=0.07, x_max=1.0, y_max=0.93):
    """把 OCR 行按垂直间距聚成「气泡块」，顺手丢掉时间戳/UI 噪声。"""
    if x_min is None:
        x_min = detect_chat_left(lines, w, h)
    gap_max = max(12.0, 0.020 * h)      # 气泡内行距 vs 气泡间留白
    keep = []
    for l in lines:
        if not l["t"]:
            continue
        cy = (l["y"] + l["y2"]) / 2 / h
        cx = (l["x"] + l["x2"]) / 2 / w
        if not (y_min <= cy <= y_max and x_min <= cx <= x_max):
            continue
        if any(r.match(l["t"]) for r in NOISE_RE):
            continue
        keep.append(l)
    keep.sort(key=lambda l: (l["y"], l["x"]))

    blocks, cur = [], []
    for l in keep:
        if cur:
            gap = l["y"] - cur[-1]["y2"]
            if gap > gap_max:
                blocks.append(cur)
                cur = []
        cur.append(l)
    if cur:
        blocks.append(cur)

    out = []
    for b in blocks:
        text = "\n".join(x["t"] for x in b)
        if len(norm(text)) < 8:
            continue
        out.append({"text": text, "y": b[0]["y"] / h, "x": b[0]["x"] / w})
    return out


def detect_chat_left(lines, w, h):
    """用「会话标题的 x」推断聊天面板左边界，从而把左侧会话列表整列滤掉。
    主窗口里标题在聊天区左上，独立聊天窗口同理；找不到就退回 0.03。"""
    cands = [l for l in lines
             if l["y"] < 0.09 * h and l["x"] > 0.22 * w
             and len(norm(l["t"])) >= 2
             and not any(r.match(l["t"]) for r in NOISE_RE)]
    if not cands:
        return 0.03
    left = min(l["x"] for l in cands)
    return max(0.03, min(0.85, left / w * 0.97))


def enter_verified(q, target, quiet=False):
    """进会话 + 用 OCR 校验标题。校验不过直接抛错（不发错人）。"""
    q.goto(target, verify=False)          # 上游 read_header 是空实现，这里自己校验
    time.sleep(0.5)
    shot = q.shot(os.path.join(SHOTS, "enter_%s.png" % datetime.now().strftime("%H%M%S")))
    lines = ocr_lines(shot)
    w, h = img_size(shot)

    def region(x0):
        keep = [l["t"] for l in lines
                if l["y"] < 0.10 * h and (l["x"] + l["x2"]) / 2 > x0 * w]
        return norm("".join(keep))

    head = region(0.24) or region(0.01)
    want = norm(target)
    ok = bool(want and head and (want in head or head in want))
    if not ok and want and head:
        import difflib
        ok = difflib.SequenceMatcher(None, want, head).ratio() >= 0.7
    if not quiet:
        print("  标题校验: target=%r head=%r -> %s" % (target, head, "OK" if ok else "MISMATCH"))
    if not ok:
        raise RuntimeError(
            "会话标题校验失败（target=%r, 屏幕标题=%r）。已中止，未发任何东西。\n"
            "对策：确认群名/昵称写全，或先手动点进该会话再用 --no-verify 收尾。"
            % (target, head))
    return shot


# ------------------------------------------------------------------ 打分
def infer_questions(text):
    low = text.lower()
    qs = []
    if not any(k in low for k in INPUT_KW):
        qs.append("要处理的素材/文件在哪，什么格式")
    if not any(k in low for k in DEADLINE_KW):
        qs.append("什么时候要")
    if not any(k in low for k in BUDGET_KW):
        qs.append("预算大概多少")
    if not any(k in low for k in FORMAT_KW):
        qs.append("交付要什么形式（源码/文档/成品文件）")
    if not any(k in text for k in ["验收", "算做完", "标准", "要求"]):
        qs.append("怎么算做完（验收标准）")
    return qs


def price_hint(text):
    """从需求原文里抠客户自报的价，避免给出离谱报价。"""
    m = BUDGET_NUM_RE.search(text) or PRICE_RE.search(text)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(0)[-1].lower()
    if unit in ("k", "千"):
        n *= 1000
    elif unit in ("w", "万"):
        n *= 10000
    return n if 20 <= n <= 200000 else None


def score_text(text):
    low = text.lower()
    veto = [b for b in CAPS.get("banned", []) if any(k.lower() in low for k in b["kw"])]
    half = [h for h in CAPS.get("half", []) if any(k.lower() in low for k in h["kw"])]
    intent = [k for k in INTENT if k in low or k in text]

    hits = []
    for c in CAPS.get("can", []):
        ks = [k for k in c["kw"] if k.lower() in low]
        if ks:
            hits.append({
                "tag": c["tag"], "matched": ks[:5], "price": c["price"],
                "eta": c["eta"], "deliver": c.get("deliver", []),
                "w": c.get("w", 1), "note": c.get("note", ""),
            })
    hits.sort(key=lambda h: (len(h["matched"]), h["w"]), reverse=True)

    raw = sum(min(len(h["matched"]), 3) * h["w"] for h in hits) + (2 if intent else 0)
    if veto:
        verdict = "decline"
    elif raw >= 5 and intent:
        verdict = "take"
    elif raw >= 2:
        verdict = "careful"
    else:
        verdict = "skip"

    price = [CAPS.get("min_price", 80), CAPS.get("min_price", 80)]
    eta = [1, 3]
    if hits:
        price = [max(h["price"][0] for h in hits), max(h["price"][1] for h in hits)]
        eta = [max(h["eta"][0] for h in hits), max(h["eta"][1] for h in hits)]

    hint = price_hint(text)
    if hint:
        # 有客户报价就贴着报，别把自己的下限当上限用
        price = [max(CAPS.get("min_price", 80), int(hint * 0.95)), int(hint * 1.5)]

    return {
        "verdict": verdict, "score": round(raw, 1), "intent": intent[:5],
        "hits": hits, "veto": veto, "half": half, "price_hint": hint,
        "price": price, "eta": eta, "questions": infer_questions(text),
    }


# ------------------------------------------------------------------ 订单库
def order_path(oid):
    return os.path.join(ORDERS, oid + ".json")


def load_orders():
    out = []
    for p in sorted(glob.glob(os.path.join(ORDERS, "*.json"))):
        if os.path.basename(p) == "seen.json":
            continue
        o = jload(p, None)
        if o:
            out.append(o)
    return out


def get_order(oid):
    o = jload(order_path(oid), None)
    if not o:
        raise SystemExit("没有这个单：%s（用 list 看）" % oid)
    return o


def save_order(o):
    o["updated"] = now()
    jdump(order_path(o["id"]), o)


def new_order(source, text, sc, img=None):
    seen = jload(SEEN, {})
    fp = fingerprint(text)
    oid = "%s-%s" % (datetime.now().strftime("%y%m%d"), fp[:4])
    o = {
        "id": oid, "created": now(), "updated": now(), "status": "candidate",
        "source": source, "contact": None, "target_chat": source,
        "raw": text, "fp": fp, "shot": img,
        "tags": [h["tag"] for h in sc["hits"][:3]],
        "score": sc["score"], "verdict": sc["verdict"],
        "price": sc["price"], "price_hint": sc.get("price_hint"),
        "eta": sc["eta"], "questions": sc["questions"],
        "veto": [v["why"] for v in sc["veto"]],
        "half": [h["tag"] for h in sc["half"]],
        "quoted": None, "notes": [], "files": [], "history": [
            {"ts": now(), "act": "created", "detail": "score=%s verdict=%s"
             % (sc["score"], sc["verdict"])}
        ],
    }
    seen[fp] = oid
    jdump(SEEN, seen)
    save_order(o)
    return o


def touch(o, act, detail=""):
    o.setdefault("history", []).append({"ts": now(), "act": act, "detail": detail})


# ------------------------------------------------------------------ 命令
def cmd_scan(a):
    from qq_ctl import QQ
    os.makedirs(SHOTS, exist_ok=True)

    if a.img:
        img = os.path.abspath(a.img)
        source = a.source or os.path.basename(img)
        return _scan_img(img, source, a)
    targets = [t.strip() for t in (a.target or "").split(",") if t.strip()]
    q = QQ(dry_run=True)                        # 只截图，不点击不输入聊天内容
    made = []
    for t in (targets or [None]):
        enter_verified(q, t) if t else None
        img = q.shot(os.path.join(SHOTS, "scan_%s.png" % datetime.now().strftime("%Y%m%d_%H%M%S")))
        made += _scan_img(img, t or "当前会话", a)
    return made


def _scan_img(img, source, a):

    lines = ocr_lines(img)
    w, h = img_size(img)
    blocks = lines_to_blocks(lines, w, h, x_min=a.x_min, y_min=a.y_min,
                             x_max=a.x_max, y_max=a.y_max)
    seen = jload(SEEN, {})
    made, dup = [], 0
    for b in blocks:
        sc = score_text(b["text"])
        if sc["verdict"] == "skip" and not a.all:
            continue
        fp = fingerprint(b["text"])
        if fp in seen:
            dup += 1
            continue
        made.append(new_order(source, b["text"], sc, os.path.basename(img)))

    print("截图/读屏: %s  (%d 行 → %d 块，新增 %d，重复 %d)"
          % (img, len(lines), len(blocks), len(made), dup))
    for o in made:
        print("\n[%s] %s  score=%s  %s" % (o["id"], o["verdict"], o["score"], " / ".join(o["tags"]) or "-"))
        for ln in o["raw"].splitlines()[:4]:
            print("   | " + ln)
    if made:
        print("\n下一步：python orderbot.py verdict %s" % made[0]["id"])
    return made


def cmd_read(a):
    from qq_ctl import QQ
    if a.img:
        img, src = os.path.abspath(a.img), a.img
    else:
        q = QQ(dry_run=True)
        if a.target:
            enter_verified(q, a.target)
        img = q.shot(os.path.join(SHOTS, "read_%s.png" % datetime.now().strftime("%H%M%S")))
        src = a.target or "当前会话"
    lines = ocr_lines(img)
    w, h = img_size(img)
    blocks = lines_to_blocks(lines, w, h, y_min=a.y_min, y_max=a.y_max)
    print("== %s ==（%d 块，OCR 读屏，未触碰键盘/剪贴板）" % (src, len(blocks)))
    for b in blocks:
        print("-" * 8)
        print(b["text"])
    return blocks


def cmd_triage(a):
    """一条命令走完：扫描 → 判定 → 生成第一句话术到 orders/<id>/ask.txt。不发任何消息。"""
    made = cmd_scan(a)
    if not made:
        return []
    rows = []
    for o in made:
        sc = score_text(o["raw"])
        ask = None
        if sc["verdict"] in ("take", "careful"):
            ask = cmd_draft(argparse.Namespace(
                id=o["id"], stage="ask", force=True, accept=None))
        d = os.path.join(ORDERS, o["id"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "ask.txt"), "w", encoding="utf-8") as f:
            f.write(ask[0] if ask else "【不接】%s" % "；".join(v["why"] for v in sc["veto"]))
        rows.append((o, sc))
    print("\n════ 待人工过一眼（每条都已备好第一句话）════")
    for o, sc in rows:
        print("[%s] %s score=%s  %s  → 草稿 orders/%s/ask.txt"
              % (o["id"], sc["verdict"], sc["score"],
                 "/".join(o["tags"]) or "-", o["id"]))
    print("\n发第一条：python orderbot.py send <id> --stage ask --to 客户昵称 --arm")
    return rows


def cmd_layout(a):
    lines = ocr_lines(os.path.abspath(a.img))
    w, h = img_size(os.path.abspath(a.img))
    cols = 40
    hist = [0] * cols
    for l in lines:
        c = min(cols - 1, int((l["x"] + l["x2"]) / 2 / w * cols))
        hist[c] += 1
    print("img=%dx%d lines=%d" % (w, h, len(lines)))
    for i in range(0, cols, 2):
        print("x=%.2f  %-4d %s" % (i / cols, hist[i], "#" * min(hist[i], 40)))
    print("→ 找到「一边有字一边空」的那条分界，把它当 --x-min 传给 scan 可去掉侧栏噪声")


def cmd_list(a):
    os_ = load_orders()
    if a.status:
        want = set(a.status.split(","))
        os_ = [o for o in os_ if o["status"] in want]
    if a.verdict:
        os_ = [o for o in os_ if o["verdict"] == a.verdict]
    if not os_:
        print("（空）")
        return
    print("%-12s %-10s %-9s %5s %-22s %s" % ("id", "status", "verdict", "score", "tags", "raw"))
    for o in sorted(os_, key=lambda x: x["created"], reverse=True):
        raw = o["raw"].replace("\n", " ")[:44]
        print("%-12s %-10s %-9s %5s %-22s %s"
              % (o["id"], o["status"], o["verdict"], o["score"],
                 "/".join(o["tags"])[:22] or "-", raw))


def cmd_show(a):
    o = get_order(a.id)
    print(json.dumps(o, ensure_ascii=False, indent=2))


def cmd_verdict(a):
    o = get_order(a.id)
    sc = score_text(o["raw"])
    print("单号: %s   来源: %s   状态: %s" % (o["id"], o["source"], o["status"]))
    print("原文:\n" + o["raw"])
    print("\n判定: %s  (score=%s)" % (sc["verdict"].upper(), sc["score"]))
    if sc["veto"]:
        print("✗ 红线命中:")
        for v in sc["veto"]:
            print("   - %s ← %s" % (v["why"], "、".join(v["kw"])))
        print("   → 只能发 decline_banned，不讨论、不议价。")
    if sc["half"]:
        print("! 需先确认（不能直接接）:")
        for h in sc["half"]:
            print("   - %s：%s" % (h["tag"], h["why"]))
    if sc["hits"]:
        print("✓ 能力匹配:")
        for h in sc["hits"][:4]:
            print("   - %-14s 命中:%s  报价 %d–%d  工期 %s–%s 天 %s"
                  % (h["tag"], "/".join(h["matched"][:4]), h["price"][0], h["price"][1],
                     h["eta"][0], h["eta"][1], ("· " + h["note"]) if h["note"] else ""))
        if sc.get("price_hint"):
            print("客户自报价: %d → 建议报价 %d–%d（贴着走，别硬抬也别贱卖）"
                  % (sc["price_hint"], sc["price"][0], sc["price"][1]))
        else:
            print("建议报价: %d–%d（先要问诊，别一上来就报死价）"
                  % (sc["price"][0], sc["price"][1]))
        print("建议工期: %s–%s 天" % (sc["eta"][0], sc["eta"][1]))
    else:
        print("✓ 能力匹配: 无 —— 不在能力范围内，别硬接")
    if sc["questions"]:
        print("必问:")
        for q in sc["questions"][:4]:
            print("   ? " + q)
    print("\n风控提醒:")
    for r in CAPS.get("red_flags", [])[:4]:
        print("   · " + r)


def _deliver_slots(o, sc):
    d = (sc["hits"][0]["deliver"] if sc["hits"] else []) + ["使用说明"]
    return d[0], (d[1] if len(d) > 1 else "使用说明")


def cmd_draft(a):
    o = get_order(a.id)
    sc = score_text(o["raw"])
    stage = a.stage
    if stage in ("decline", "decline_banned") and not sc["veto"] and a.stage != "decline":
        print("（提示：这条没命中红线，确认要按红线回复的话加 --force 也行，但更建议 decline）")
    tpl = TPL.get(stage)
    if not tpl:
        raise SystemExit("没有这个阶段: %s（可用: %s）" % (stage, ", ".join(TPL.keys())))
    if o["status"] not in STAGE_OK.get(stage, STATUSES) and not a.force:
        raise SystemExit("状态 %s 不适合发 stage=%s（跳过步骤容易扯皮）。确认要发加 --force。"
                         % (o["status"], stage))

    d1, d2 = _deliver_slots(o, sc)
    price = o.get("quoted") or sc["price"][1]
    deposit = int(round(price * 0.5 / 10.0)) * 10
    qs = sc["questions"] or ["具体要什么", "什么时候要"]
    body = fmt(
        tpl["body"],
        source=o["source"], title=(o["tags"][0] if o["tags"] else "这个需求"),
        tags=" / ".join(o["tags"]) or "（先确认）",
        q1=qs[0], q2=(qs[1] if len(qs) > 1 else "交付要什么形式"),
        what=o["raw"].replace("\n", " ")[:60], input="?", deadline="?",
        budget="?", accept=a.accept or "（按上面聊定的验收点）", format="?",
        price=price, price_lo=sc["price"][0], price_hi=sc["price"][1],
        range_note="" if o.get("quoted") else
        "（区间 %d–%d，你情况说清后我取一个数，不来回改）" % (sc["price"][0], sc["price"][1]),
        deliver1=d1, deliver2=d2, revise=1, eta="%s–%s 天" % tuple(sc["eta"]),
        deposit=deposit, balance=price - deposit, sync="每天",
        progress="（写一句实际进度）", files=o["files"] or "（附件）",
        checklist="② 两处要看：能不能跑通、结果对不对；",
    )
    print("── stage=%s  →  %s ──" % (stage, o.get("target_chat") or o["source"]))
    print(body)
    print("── 发送: python orderbot.py send %s --stage %s [--arm] ──" % (o["id"], stage))
    return body, stage


def cmd_send(a):
    from qq_ctl import QQ
    o = get_order(a.id)
    sc = score_text(o["raw"])

    if a.text:
        text, stage = a.text, (a.stage or "custom")
    else:
        if not a.stage:
            raise SystemExit("要么给 --stage，要么给 --text")
        text, stage = cmd_draft(argparse.Namespace(
            id=o["id"], stage=a.stage, force=a.force, accept=getattr(a, "accept", None)))

    if sc["veto"] and stage not in ("decline", "decline_banned"):
        raise SystemExit("这条命中红线（%s），只允许 decline_banned。"
                         % "；".join(v["why"] for v in sc["veto"]))

    target = a.to or o.get("contact") or o.get("target_chat") or o["source"]
    if target == o["source"] and a.to is None:
        print("! 默认发到来源会话「%s」。群里回复容易刷屏/被踢，建议 --to 客户昵称走私聊。" % target)

    if not a.arm:
        print("══ 演练（未发送）══  目标: %s\n%s\n══ 真发加 --arm ══" % (target, text))
        touch(o, "dryrun", "stage=%s target=%s" % (stage, target))
        save_order(o)
        return

    q = QQ(dry_run=False)                  # 内部 Guard 限流生效：3s/20 每小时/120 每天
    if not a.no_verify:
        enter_verified(q, target)
    q.send(text)                           # target=None → 发到当前（已被校验的）会话
    shot = q.shot(os.path.join(SHOTS, "sent_%s.png" % datetime.now().strftime("%H%M%S")))
    touch(o, "sent", "stage=%s target=%s shot=%s" % (stage, target, os.path.basename(shot)))
    o["sent_log"] = o.get("sent_log", []) + [{"ts": now(), "stage": stage, "target": target, "text": text}]

    nxt = {"ask": "contacted", "qualify": "qualified", "quote": "quoted",
           "accept": "accepted", "progress": "delivering", "deliver": "delivered",
           "chase": "paid", "decline": "dead", "decline_banned": "dead",
           "close": "paid"}.get(stage)
    if nxt and not a.keep_status:
        o["status"] = nxt
        touch(o, "status", "→ %s（send %s 自动推进）" % (nxt, stage))
    save_order(o)
    print("已发送 → %s（stage=%s，状态 %s）" % (target, stage, o["status"]))
    print("存证截图: %s" % shot)


def cmd_status(a):
    o = get_order(a.id)
    if a.to not in STATUSES:
        raise SystemExit("未知状态 %r，可用: %s" % (a.to, ", ".join(STATUSES)))
    old = o["status"]
    o["status"] = a.to
    if a.contact:
        o["contact"] = a.contact
    if a.quoted:
        o["quoted"] = a.quoted
    if a.note:
        o["notes"].append({"ts": now(), "text": a.note})
    touch(o, "status", "%s → %s %s" % (old, a.to, a.note or ""))
    save_order(o)
    print("%s: %s → %s" % (o["id"], old, a.to))


def cmd_deliver(a):
    o = get_order(a.id)
    d = os.path.join(ORDERS, o["id"], "deliver")
    os.makedirs(d, exist_ok=True)
    copied = []
    for pat in a.files or []:
        for src in glob.glob(pat):
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(d, os.path.basename(src)))
                copied.append(os.path.basename(src))
    o["files"] = sorted(set(o.get("files", []) + copied))
    sc = score_text(o["raw"])
    handoff = os.path.join(ORDERS, o["id"], "handoff.md")
    if not os.path.exists(handoff) or a.force:
        with open(handoff, "w", encoding="utf-8") as f:
            f.write(HANDOFF.format(
                id=o["id"], source=o["source"], raw=o["raw"],
                tags=" / ".join(o["tags"]), price=o.get("quoted") or sc["price"][1],
                files="\n".join("- `%s`" % x for x in o["files"]) or "- （待填）",
            ))
    touch(o, "deliver", "files=%d dir=%s" % (len(copied), d))
    if o["status"] in ("accepted", "delivering"):
        o["status"] = "delivered"
        touch(o, "status", "→ delivered（deliver 自动推进）")
    save_order(o)
    print("交付包: %s\n交付说明: %s\n文件: %s" % (d, handoff, ", ".join(o["files"]) or "（空）"))
    print("提醒：交付前自己跑一遍，README 里写清「怎么运行 / 依赖 / 已知限制」。")


HANDOFF = """# 交付说明 {id}

- 来源：{source}
- 能力标签：{tags}
- 成交价：{price}（定金/尾款按聊天记录）
- 原始需求：
```
{raw}
```

## 交付物
{files}

## 怎么用
1. （环境/依赖）
2. （运行命令）
3. （预期输出）

## 验收点（对着客户的要求逐条勾）
- [ ] 
- [ ] 

## 已知限制（提前说清，避免售后扯皮）
- 

## 售后
- 一次免费修改范围：与原始需求一致的部分
- 超出范围：另行报价
"""


def cmd_stats(a):
    os_ = load_orders()
    print("订单总数: %d" % len(os_))
    for s in STATUSES:
        n = len([o for o in os_ if o["status"] == s])
        if n:
            print("  %-10s %d" % (s, n))
    money = sum((o.get("quoted") or 0) for o in os_ if o["status"] in ("paid",))
    print("已成交金额: %s 元" % (money or 0))
    print("判定分布: " + ", ".join("%s=%d" % (v, len([o for o in os_ if o["verdict"] == v]))
                                  for v in ("take", "careful", "decline")))
    from qq_ctl import Guard
    print("发送配额: %s" % Guard().stats())


def cmd_watch(a):
    from qq_ctl import QQ
    seen_before = set(jload(SEEN, {}).keys())
    for r in range(a.rounds):
        print("\n=== 第 %d 轮 %s ===" % (r + 1, now()))
        try:
            cmd_scan(argparse.Namespace(
                target=a.target, source=None, img=None, all=False,
                x_min=a.x_min, y_min=a.y_min, x_max=1.0, y_max=0.93))
        except Exception as e:
            print("扫描失败（不退出，等下一轮）: %s" % e)
        if a.rounds > 1 and r + 1 < a.rounds:
            print("等 %d 秒…（Ctrl+C 退出，或 orderbot.py stop）" % a.interval)
            time.sleep(a.interval)


def cmd_stop(a):
    from qq_ctl import STOP_FLAG
    open(STOP_FLAG, "w").close()
    print("已停手：%s" % STOP_FLAG)


def cmd_resume(a):
    from qq_ctl import STOP_FLAG
    if os.path.exists(STOP_FLAG):
        os.remove(STOP_FLAG)
    print("已解除。")


# ------------------------------------------------------------------ CLI
def main():
    ap = argparse.ArgumentParser(description="QQ 找单 → 评估 → 对接 → 交付")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("scan", help="读屏找单（默认只读，不点不输入）")
    p.add_argument("--target", help="先进哪个群/频道/会话")
    p.add_argument("--img", help="离线识别一张截图（不碰 QQ）")
    p.add_argument("--source", help="来源标签（配合 --img）")
    p.add_argument("--all", action="store_true", help="连 skip 级噪声也入队")
    p.add_argument("--x-min", type=float, default=None, help="聊天区左边界（默认按标题自动识别）")
    p.add_argument("--y-min", type=float, default=0.07)
    p.add_argument("--x-max", type=float, default=1.0)
    p.add_argument("--y-max", type=float, default=0.93)

    p = sub.add_parser("read", help="读会话聊天文本（只读，用于看客户回复）")
    p.add_argument("--target", help="先进哪个会话")
    p.add_argument("--img")
    p.add_argument("--y-min", type=float, default=0.07)
    p.add_argument("--y-max", type=float, default=0.93)

    p = sub.add_parser("triage", help="扫描+判定+生成第一句（不发消息）")
    p.add_argument("--target", help="群/频道，多个用逗号分隔")
    p.add_argument("--img")
    p.add_argument("--source")
    p.add_argument("--all", action="store_true")
    p.add_argument("--x-min", type=float, default=None)
    p.add_argument("--y-min", type=float, default=0.07)
    p.add_argument("--x-max", type=float, default=1.0)
    p.add_argument("--y-max", type=float, default=0.93)

    p = sub.add_parser("layout", help="看截图的列分布，用来校准 --x-min")
    p.add_argument("--img", required=True)

    p = sub.add_parser("list", help="列订单")
    p.add_argument("--status")
    p.add_argument("--verdict")

    p = sub.add_parser("show", help="看一条订单全量 JSON")
    p.add_argument("id")

    p = sub.add_parser("verdict", help="能力评估 + 建议报价 + 必问项")
    p.add_argument("id")

    p = sub.add_parser("draft", help="渲染话术草稿（不发送）")
    p.add_argument("id")
    p.add_argument("--stage", required=True, choices=list(TPL.keys()))
    p.add_argument("--accept", help="填进模板的验收标准（accept 阶段用）")
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("send", help="发送（默认演练，--arm 才真发）")
    p.add_argument("id")
    p.add_argument("--stage", choices=list(TPL.keys()))
    p.add_argument("--text")
    p.add_argument("--to", help="发给谁（默认订单 contact/target_chat）")
    p.add_argument("--arm", action="store_true")
    p.add_argument("--no-verify", action="store_true", help="跳过标题校验（不推荐）")
    p.add_argument("--force", action="store_true")
    p.add_argument("--keep-status", action="store_true")

    p = sub.add_parser("status", help="改状态")
    p.add_argument("id")
    p.add_argument("to")
    p.add_argument("--note")
    p.add_argument("--contact", help="记录客户昵称（之后 --to 默认用它）")
    p.add_argument("--quoted", type=int, help="成交价")

    p = sub.add_parser("deliver", help="建交付包 + 生成 handoff.md")
    p.add_argument("id")
    p.add_argument("--files", nargs="*", help="要归档的文件（支持通配符）")
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("stats", help="统计/额度")
    p = sub.add_parser("watch", help="定时轮询新单（只读，不发消息）")
    p.add_argument("--target")
    p.add_argument("--interval", type=int, default=900)
    p.add_argument("--rounds", type=int, default=1)
    p.add_argument("--x-min", type=float, default=None)
    p.add_argument("--y-min", type=float, default=0.07)

    sub.add_parser("stop", help="放 STOP 文件，所有发送立即失败")
    sub.add_parser("resume", help="解除 stop")

    a = ap.parse_args()
    if a.cmd in ("scan", "send", "watch") and not os.path.isdir(QQ_DIR):
        raise SystemExit("找不到上游技能目录: %s（设 QQ_DESKTOP_SKILL 环境变量指过去）" % QQ_DIR)
    sys.path.insert(0, QQ_DIR)
    os.makedirs(ORDERS, exist_ok=True)
    os.makedirs(SHOTS, exist_ok=True)

    fn = {"triage": cmd_triage, "read": cmd_read, "scan": cmd_scan, "layout": cmd_layout, "list": cmd_list, "show": cmd_show,
          "verdict": cmd_verdict, "draft": cmd_draft, "send": cmd_send,
          "status": cmd_status, "deliver": cmd_deliver, "stats": cmd_stats,
          "watch": cmd_watch, "stop": cmd_stop, "resume": cmd_resume}[a.cmd]
    fn(a)


if __name__ == "__main__":
    main()
