# -*- coding: utf-8 -*-
"""课件 project.json -> 小红书图文笔记草稿 post.json

做五件事（2026-11 起「成品流」策略）：
  0. 先查发布台账：课题发过 / 图用过的直接拒绝（--next 自动挑未发课题）
  1. 选图只给成品：封面成品 + 从成品裁的局部特写 + 知识素材/实物/材料；
     **默认不发步骤图**（步骤图暴露模板、画面也最差），要发加 --with-steps
  2. 把图复制到纯 ASCII 暂存目录（中文路径是已知翻车点）
  3. 封面补成 3:4（首页瀑布流按 3:4 裁切，3:2 横图会被切掉两边）
  4. 从课件数据生成标题/正文/标签草稿（含 AIGC 声明 + 购买引导，两处【】待人工改）

用法：
    python prep_post.py 项目/小象洗澡-4-6岁/project.json
    python prep_post.py <project.json> --slug xiaoxiang --cap 9
    python prep_post.py <project.json> --with-steps      # 老策略：也发范画步骤
    python prep_post.py <project.json> --details 0       # 不裁成品细节图
"""
import argparse
import hashlib
import io
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xhs import calc_title_len, TITLE_MAX, TAGS_MAX, utf8_stdout  # noqa: E402
import published  # noqa: E402

try:
    from PIL import Image
except ImportError:
    print("需要 Pillow：pip install pillow")
    raise

STAGE_ROOT = os.environ.get("XHS_POST_STAGE", r"C:\Users\hua\tools\xiaohongshu-mcp\upload")
JUNK = ("-", "—", "·", " ", "\u3000")

# ---------------- 文案策略（2026-11）----------------
# 1) 必须写明 AI 生成：小红书对 AIGC 内容要求声明，且能挡掉「AI 画的还卖钱」的举报
# 2) 必须留购买引导：先卖课件（低客单），再卖做课件的工具（高客单）
# 3) CTA 只能引导「评论区 / 私信 / 主页」，绝对不能出现微信、QQ、电话、外链
AI_DISCLOSURE = ("🤖 说明：本套课件画面由 AI 生成，课题设计、教学流程与文字由人工编排校对，"
                 "介意的老师慎拍。")
CTA_DECK = "· 单套课件 / 系列课包（多套打包更划算），主页合集里挑，评论区扣「课题名」我私你"
CTA_CUSTOM = "· 没找到想上的课题？点题就行，我按你的主题出图、出整套课件"
CTA_TOOL = ("· 想自己批量出这种课件（AI 出图 + 自动排版 + 一键导 PPTX/PDF）的老师，"
            "私信「工具」")


def md5(p, chunk=1 << 20):
    h = hashlib.md5()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def resolve_slot(pdir, slot):
    """跟 工厂/project.py 的 img_path 同一套规则：img_sell 优先，其次 img。"""
    for sub in ("img_sell", "img"):
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            p = os.path.join(pdir, sub, slot + ext)
            if os.path.exists(p):
                return p
        base = os.path.join(pdir, sub)
        if os.path.isdir(base):
            for f in sorted(os.listdir(base)):
                stem, ext = os.path.splitext(f)
                if stem == slot and ext.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                    return os.path.join(base, f)
    return None


def clean(s):
    for j in JUNK:
        s = s.replace(j, "")
    return (s or "").strip()


# ---------------- 选图 ----------------
def pick_slots(data, cap, with_steps=False):
    """返回 (选中的 slot 列表, 说明, 被丢掉的)。规则完全由 pages[].type + uses 驱动。

    默认「成品流」：不选 step 页的图。步骤图只证明「这是套模板」，成品图才让人想买。
    """
    pages = data.get("pages", [])
    slots_have = {im["slot"] for im in data.get("images", [])}
    picked, why = [], {}

    def add(slot, reason):
        if slot and slot in slots_have and slot not in picked:
            picked.append(slot)
            why[slot] = reason

    by_type = {}
    for pg in pages:
        by_type.setdefault(pg.get("type"), []).append(pg)

    # 1) 封面 = 成品（没有成品就退到 intro/cover 页用的图）
    final = next((s for s in slots_have if "成品" in s), None)
    if not final:
        for pg in by_type.get("final_dual", []) + by_type.get("intro", []) + by_type.get("cover", []):
            if pg.get("uses"):
                final = pg["uses"][0]
                break
    add(final, "封面：范画成品（先给人看画成什么样）")

    # 2) 其它成品图（final_dual 页 / 名字里带「成品」的槽）—— 不发步骤，只多给几个成品视角
    finals = []
    for pg in by_type.get("final_dual", []):
        finals += list(pg.get("uses", []))
    for s in sorted(slots_have):
        if "成品" in s:
            finals.append(s)
    for s in finals:
        add(s, "成品多角度：给人看画成什么样")

    # 2b) 范画步骤：只有显式 --with-steps 才发（老策略）
    steps = [pg["uses"][0] for pg in by_type.get("step", []) if pg.get("uses")]
    if with_steps:
        for s in steps:
            add(s, "范画步骤")

    # 3) 知识页素材：最多取 2 张，特写优先（近景细节比远景更有点击欲）
    know = [pg["uses"][0] for pg in by_type.get("knowledge", []) if pg.get("uses")]
    if know:
        close = [s for s in know if "面部" in s or "特写" in s]
        for s in (close + [s for s in know if s not in close])[:2]:
            add(s, "观察素材：近景细节")

    # 4) 实物观察页（真东西，卖点）
    real = []
    for pg in by_type.get("real_object", []):
        real += list(pg.get("uses", []))
    for s in real:
        add(s, "实物观察：真实的东西")

    # 5) 材料工具页
    mat = []
    for pg in by_type.get("materials", []):
        mat += list(pg.get("uses", []))
    for s in mat:
        add(s, "材料工具：要用什么")

    # 超上限就从最不重要的开始丢（材料 -> 实物 -> 知识素材 -> 多余成品/步骤），封面永远保留
    drop_plan = (list(reversed(mat)) + list(reversed(real)) + list(know)
                 + list(reversed(finals)) + list(reversed(steps)))
    dropped = []
    for d in drop_plan:
        if len(picked) <= cap:
            break
        if d in picked and d != final:
            picked.remove(d)
            dropped.append(d)
    return picked, why, dropped


# ---------------- 出图 ----------------
def border_bg(im):
    """取四边一圈像素的中位色，用来补边，接缝看不出来。"""
    import statistics
    w, h = im.size
    px = im.load()
    edge = []
    for x in range(0, w, max(1, w // 200)):
        edge.append(px[x, 0])
        edge.append(px[x, h - 1])
    for y in range(0, h, max(1, h // 200)):
        edge.append(px[0, y])
        edge.append(px[w - 1, y])
    return tuple(int(statistics.median(c[i] for c in edge)) for i in range(3))


def save_cover(src, dst, target_w=1080, target_h=1440, quality=92):
    """把封面补成 3:4。返回 (是否补边, 原尺寸, 新尺寸)"""
    im = Image.open(src).convert("RGB")
    w, h = im.size
    ratio = target_w / target_h
    if abs(w / h - ratio) < 0.01:
        im.save(dst, quality=quality)
        return False, (w, h), im.size
    tw, th = w, int(round(w / ratio))
    if th < h:
        th, tw = h, int(round(h * ratio))
    canvas = Image.new("RGB", (tw, th), border_bg(im))
    canvas.paste(im, ((tw - w) // 2, (th - h) // 2))
    canvas = canvas.resize((target_w, target_h), Image.LANCZOS)
    canvas.save(dst, quality=quality)
    return True, (w, h), canvas.size


def save_plain(src, dst, quality=92):
    im = Image.open(src).convert("RGB")
    try:
        from PIL import ImageOps
        im = ImageOps.exif_transpose(im)
    except Exception:
        pass
    im.save(dst, quality=quality)
    return im.size


# 从成品图上取局部的位置（相对坐标），按索引轮着用
DETAIL_ZONES = [(0.50, 0.44), (0.30, 0.66), (0.72, 0.34), (0.50, 0.80)]


def save_detail(src, dst, i, target_w=1080, target_h=1440, quality=92):
    """从成品图上裁一块 3:4 细节特写放大。

    这是「没有步骤图也要凑够 6-9 张」的正解：放大成品里的主体/局部，
    既有信息量又不暴露模板结构。裁切框始终 3:4，不会触发平台再裁。
    """
    im = Image.open(src).convert("RGB")
    w, h = im.size
    cx, cy = DETAIL_ZONES[i % len(DETAIL_ZONES)]
    cw = int(w * 0.62)
    ch = int(round(cw * target_h / target_w))
    if ch > h * 0.92:
        ch = int(h * 0.92)
        cw = int(round(ch * target_w / target_h))
    x = min(max(int(cx * w - cw / 2), 0), w - cw)
    y = min(max(int(cy * h - ch / 2), 0), h - ch)
    crop = im.crop((x, y, x + cw, y + ch)).resize((target_w, target_h), Image.LANCZOS)
    crop.save(dst, quality=quality)
    return crop.size


# ---------------- 文案 ----------------
def build_copy(data, n_pages, brand, with_steps=False):
    meta = data.get("meta", {})
    name = meta.get("name") or ""
    short = name.replace("《", "").replace("》", "")
    age = meta.get("age") or ""
    # 名字里通常带着年龄和「课件」后缀（《小象洗澡》4-6岁课件），都要剥掉，
    # 否则会拼出《小象洗澡46岁》这种标题（去掉 - 之后数字粘一起）
    if age:
        short = short.replace(age, "")
    for suf in ("创意美术课件", "美术课件", "课件", "PPT", "pptx"):
        if short.endswith(suf):
            short = short[: -len(suf)]
    short = clean(short) or clean(name)
    pages = data.get("pages", [])
    by = {}
    for pg in pages:
        by.setdefault(pg.get("type"), []).append(pg)

    # ---- 标题候选 ----
    t_base = "《%s》%s创意美术课件" % (short, age)
    cands = [t_base + "%d页" % n_pages, t_base, "《%s》创意美术课件｜%d页" % (short, n_pages)]
    cands = [t for i, t in enumerate(cands) if t not in cands[:i] and calc_title_len(t) <= TITLE_MAX]
    title = cands[0]

    # ---- 正文（成品流 + AIGC 声明 + 购买引导）----
    L = []
    L.append("【钩子：一句话写《%s》成品画面的细节，再加一句“一节课孩子能画成这样” —— 别写“这是一套课件”】" % short)
    L.append("")
    L.append("🖼 图上就是成品：%s孩子一节课能画出来的样子。" % age)
    L.append("· 画材：马克笔为主，不用准备稀罕材料")
    L.append("· 上课：%d页全部排好版，投屏就能讲，不用自己再排版" % n_pages)
    L.append("")
    L.append("📚 这套里有什么（共%d页）" % n_pages)

    km = [clean(pg.get("title", "")).replace("秘密", "") for pg in by.get("knowledge", [])]
    km = [k.lstrip("一二三四五：: ") for k in km]
    if km:
        L.append("· 小知识：%s" % " ｜ ".join(km))
    for pg in by.get("real_object", []):
        L.append("· 实物观察：%s" % clean(pg.get("title", "")).lstrip("看一看：摸一摸："))
    for pg in by.get("materials", []):
        L.append("· 材料工具：%s" % clean(pg.get("title", "")).lstrip("看一看：摸一摸："))
    obs = [clean(pg.get("title", "")) for pg in by.get("observe_tags", [])]
    poses = [clean(pg.get("title", "")) for pg in by.get("poses", [])]
    ideas = [clean(pg.get("title", "")) for pg in by.get("idea_list", [])]
    if obs or poses or ideas:
        L.append("· 观察与联想：外形特点 / 组成部分 / 各种样子 / 还会出现在哪里")
    # 「·」在这里是列举分隔符，不是多余符号，先换成顿号再 clean（clean 会把它吃掉）
    c = [clean(pg.get("title", "").replace("·", "，")).replace("同类色小知识", "").strip("，—- ")
         for pg in by.get("color_swatches", [])]
    c += [clean(pg.get("title", "").replace("·", "，")) for pg in by.get("contrast_blank", [])]
    if c:
        L.append("· 色彩小知识：%s" % "、".join([x for x in c if x]))
    steps = [clean(pg.get("title", "")).split("：")[-1] for pg in by.get("step", [])]
    steps = [s for s in steps if s]
    if steps and with_steps:
        L.append("· 范画%d步：%s" % (len(steps), " → ".join(steps)))
    elif steps:
        L.append("· 完整流程：从观察到动手到成品，一节课走完（成品见第 1 张）")
    if by.get("share_summary"):
        L.append("· 分享总结页")
    L.append("")

    items = []
    for pg in by.get("knowing", []):
        items += list(pg.get("items", []))
    if items:
        L.append("✅ 孩子这节课能学到（课件里写好的教学目标）")
        L += ["· " + clean(i).lstrip("1234567890、.（） ") for i in items]
        L.append("")

    L.append("🎨 这个课题好上的地方")
    L.append("【写 2-3 条：形体好不好抓形 / 实物观察是不是真东西 / 颜色挑不挑笔 —— 家长最关心孩子能不能画出来】")
    L.append("")
    L.append("👩‍🏫 适合 %s，幼儿园 / 机构 / 家庭都能上，一节课的完整流程。" % age)
    L.append("")
    L.append(AI_DISCLOSURE)
    L.append("")
    L.append("🛒 想要这套（或者别的课题）")
    L.append(CTA_DECK)
    L.append(CTA_CUSTOM)
    L.append(CTA_TOOL)
    L.append("")
    L.append("📎 %s" % brand)

    tags = ["少儿美术", "创意美术", "美术课件", "美术老师", "AI绘画"]
    if age:
        tags.append(age.replace("-", "到"))
    tags += ["幼儿美术", "马克笔", "课件分享", "美术机构", "美术教案"]
    out = []
    for t in tags:
        if t and t not in out:
            out.append(t)
    return title, cands[1:], "\n".join(L), out[:TAGS_MAX]


# ---------------- 主流程 ----------------
def main():
    utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?", help="课件 project.json 路径（或加 --next 自动挑未发课题）")
    ap.add_argument("--next", action="store_true", help="自动挑一个还没发过的课题")
    ap.add_argument("--allow-repeat", action="store_true",
                    help="允许重发已发课题 / 已用过的图（默认拒绝）")
    ap.add_argument("--slug", help="暂存目录名（纯英文），默认按拼音/哈希生成")
    ap.add_argument("--cap", type=int, default=9, help="最多发几张图（默认 9，不含细节图）")
    ap.add_argument("--with-steps", action="store_true",
                    help="老策略：把范画步骤图也发出去（默认不发）")
    ap.add_argument("--details", type=int, default=2,
                    help="从成品图裁几张局部特写（默认 2，0=不裁）")
    ap.add_argument("--stage", default=STAGE_ROOT, help="图片暂存根目录（必须纯 ASCII）")
    ap.add_argument("--out", help="post.json 输出路径，默认写到课件目录下")
    ap.add_argument("--brand", help="覆盖 meta.brand")
    ap.add_argument("--allow-placeholder-brand", action="store_true",
                    help="课件品牌名还是占位符时也继续（默认拒绝）")
    a = ap.parse_args()

    if a.next:
        un = published.unused_decks()
        if not un:
            print("⚠️ 所有课件都发过了。要么做新课题，要么 --allow-repeat 重发。")
            return 3
        a.project = un[0][1]
        print("→ 自动挑未发课题:", un[0][0])
    if not a.project:
        print("✗ 需要 project.json 路径，或加 --next")
        return 2

    pj = os.path.abspath(a.project)
    pdir = os.path.dirname(pj)
    with open(pj, encoding="utf-8") as f:
        data = json.load(f)

    meta = data.get("meta", {})
    brand = a.brand or meta.get("brand") or ""
    name = meta.get("name") or os.path.basename(pdir)
    n_pages = len(data.get("pages", []))

    print("=" * 72)
    print("课件:", name, "|", n_pages, "页 |", len(data.get("images", [])), "张图")
    print("品牌:", brand)

    # 红线 1：品牌名还是占位符
    if "你的机构名" in brand and not a.allow_placeholder_brand:
        print()
        print("✗ 拒绝继续：meta.brand 还是占位符 %r" % brand)
        print("  这是 skill 的红线 —— 品牌名会印在每一页页脚。先改 project.json：")
        print("    改完重跑 工厂/builder.py + 工厂/exporter.py 重出 pptx/pdf")
        print("  （确实要先发帖、课件还没定稿，加 --allow-placeholder-brand）")
        return 2

    # 台账：同一课题不重复发（用户明确要求：不能每次都是同一只大象）
    led = published.load()
    dk, rec = published.find_deck(led, name, meta.get("age", ""))
    if rec and rec.get("notes"):
        print()
        print("✗ 这个课题已经发过了：%s（%d 篇）" % (rec.get("name", name), len(rec["notes"])))
        for n in rec["notes"][:5]:
            print("   · %s  %s" % (n.get("at", "")[:10], n.get("title", "")))
            print("     https://www.xiaohongshu.com/explore/%s" % n.get("id", ""))
        un = published.unused_decks()
        if un:
            print("\n还没发过的课题（用 --next 自动挑下一个）：")
            for nm, _pj in un:
                print("   + %s" % nm)
        if not a.allow_repeat:
            print("\n（确实要重发加 --allow-repeat；但建议换课题，别让粉丝反复看到同一张图）")
            return 3
        print("\n--allow-repeat：继续，但这次必须换图/换文案")

    # 选图
    picked, why, dropped = pick_slots(data, a.cap, with_steps=a.with_steps)
    print()
    print("--- 选图 %d 张 ---" % len(picked))
    srcs, reasons, seen_md5 = [], [], {}
    dup = []
    for slot in picked:
        p = resolve_slot(pdir, slot)
        if not p:
            print("  ! 找不到图:", slot)
            continue
        h = md5(p)
        if h in seen_md5:
            print("  - 跳过重复图 %s（与 %s 内容完全相同 md5=%s）" % (slot, seen_md5[h], h[:8]))
            continue
        seen_md5[h] = slot
        seen = published.image_seen(led, h)
        if seen:
            dup.append((slot, seen))
            print("  x %-18s 这张图已在《%s》里发过（%s）" %
                  (slot, seen.get("deck", "?"), h[:8]))
            continue
        srcs.append((slot, p, why.get(slot, "")))
        print("  + %-18s %-26s %s" % (slot, why.get(slot, ""), os.path.basename(p)))
    if dup and not a.allow_repeat:
        print()
        print("✗ 拒绝：《%s》里有 %d 张图已经发布过。同一张图不能反复发。" % (name, len(dup)))
        print("   换一个课题：python prep_post.py --next")
        print("   （确实要用这批图加 --allow-repeat）")
        return 3
    if not srcs:
        print("✗ 一张可用图都没有：全被台账拦了（或图缺失）")
        return 3
    if dropped:
        print("  超上限被丢:", ", ".join(dropped))

    # 暂存到 ASCII 目录
    slug = a.slug or "deck_" + hashlib.md5(name.encode("utf-8")).hexdigest()[:8]
    if not all(ord(c) < 128 for c in a.stage):
        print("✗ 暂存目录必须纯 ASCII:", a.stage)
        return 2
    stage = os.path.join(a.stage, slug)
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    os.makedirs(stage, exist_ok=True)

    images = []
    print()
    print("--- 写入", stage, "---")
    # 01 封面（成品补成 3:4）
    cover_slot, cover_src, _r = srcs[0]
    dst = os.path.join(stage, "01_cover.jpg")
    padded, old, new = save_cover(cover_src, dst)
    cover_note = "补成 3:4 %s -> %s" % ("x".join(map(str, old)), "x".join(map(str, new))) if padded \
        else "本来就是 3:4，不补边"
    print("  01 %-18s %s" % (cover_slot, cover_note))
    images.append(dst)

    # 02.. 从成品裁的局部特写（代替步骤图，凑够图数又不暴露模板）
    for k in range(max(0, a.details)):
        if len(images) >= 18:
            break
        dst = os.path.join(stage, "%02d_detail%d.jpg" % (len(images) + 1, k + 1))
        size = save_detail(cover_src, dst, k)
        print("  %02d %-18s 成品局部特写 %s" % (len(images) + 1, "detail%d" % (k + 1),
                                          "x".join(map(str, size))))
        images.append(dst)

    # 剩下的图（素材 / 实物 / 材料 / 可选步骤）
    for slot, src, _r in srcs[1:]:
        dst = os.path.join(stage, "%02d.jpg" % (len(images) + 1))
        size = save_plain(src, dst)
        print("  %02d %-18s %s" % (len(images) + 1, slot, "x".join(map(str, size))))
        images.append(dst)

    # 台账第二道：成品图 md5（补边/裁切后的实际发布文件才是会被粉丝看到的那张）
    hit_imgs = []
    for p in images:
        h = md5(p)
        seen = published.image_seen(led, h)
        if seen:
            hit_imgs.append((os.path.basename(p), seen, h))
    if hit_imgs and not a.allow_repeat:
        print()
        print("✗ 拒绝：最终成品图里已有发布过的：")
        for nm, seen, h in hit_imgs:
            print("   %s -> 《%s》(%s)" % (nm, seen.get("deck", "?"), h[:8]))
        print("   换课题：python prep_post.py --next；确实要发加 --allow-repeat")
        return 3

    # 文案
    title, alt, content, tags = build_copy(data, n_pages, brand, with_steps=a.with_steps)
    post = {
        "project": pj,
        "name": name,
        "age": meta.get("age", ""),
        "brand": brand,
        "title": title,
        "title_alt": alt,
        "content": content,
        "tags": tags,
        "images": images,
        "visibility": "仅自己可见",
        "_prep": {
            "slots": [s for s, _p, _r in srcs],
            "reasons": [r for _s, _p, r in srcs],
            "dropped": dropped,
            "details": max(0, a.details),
            "with_steps": bool(a.with_steps),
            "image_md5": [md5(p) for p in images],
            "need_edit": ["开头钩子（【钩子…】那行）", "好上的地方（【写 2-3 条…】那一段）"],
            "must_keep": ["AIGC 声明（AI_DISCLOSURE 那段，删了容易被举报/限流）",
                          "购买引导（CTA_DECK / CTA_CUSTOM / CTA_TOOL）"],
        },
    }
    outp = a.out or os.path.join(pdir, "post.json")
    with open(outp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(post, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 72)
    print("标题:", title, "(%d/%d 字)" % (calc_title_len(title), TITLE_MAX))
    for t in alt:
        print("  备选:", t, "(%d 字)" % calc_title_len(t))
    print("正文: %d 字" % len(content))
    print("标签: %d 个  %s" % (len(tags), " ".join("#" + t for t in tags)))
    print("图片: %d 张" % len(images))
    print("可见: %s（草稿默认仅自己可见，试跑安全）" % post["visibility"])
    print()
    print("⚠️ 发布前必须改两处（正文里带【】的占位）：")
    for x in post["_prep"]["need_edit"]:
        print("   -", x)
    print("   这两段别删：AIGC 声明、购买引导（见 post.json 的 _prep.must_keep）")
    print("   改完可以直接发：python publish_post.py", outp)
    un = published.unused_decks()
    if un:
        print()
        print("还没发过的课题 %d 个（下一个用 --next）：" % len(un))
        for nm, _pj in un[:8]:
            print("   + %s" % nm)
    print("草稿 ->", outp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
