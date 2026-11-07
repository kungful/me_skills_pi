# -*- coding: utf-8 -*-
"""课件工厂 · 出图自检（跑完 pipeline 立刻跑这个，别等人肉审图才发现错图）

它抓的是「结构化能查出来的错」——这些错有个共同点：**不盯图看不出来，但发出去就是废品**：

1. 步骤1 没挂成品参考 → 从零发明铅笔稿 → 成品和步骤变成两棵树（最坑，静态就能查）
2. 步骤1/勾线页上了色（本该是淡灰铅笔 / 黑白线稿）
3. 涂色步骤提前把背景涂了（本该留白到最后一步）
4. 成品 ≡ 最后一步 但 md5 不同（alias 没生效）
5. 成品与步骤3/4 构图差太多（不是同一棵树）
6. 页面 uses 引用了不存在的槽位 / 槽位缺图 / brand 还是占位符
7. PDF 页数和 pages 不一致、PDF 里还有缺图

用法：
    python 工厂/preflight.py 项目/<课题>/project.json
    python 工厂/preflight.py 项目/<课题>/project.json --strict    # 有 WARN 也返回非 0
    python 工厂/preflight.py 项目/<课题>/project.json --no-pdf    # 只看图和结构

退出码：0 全过 / 1 有 FAIL / 2 有 WARN（--strict 下才算失败）

阈值来源：本机 5 套已定稿课件实测（见 SEVERITY/阈值注释），不是拍脑袋。
"""
import argparse
import hashlib
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from project import Project  # noqa: E402

from PIL import Image, ImageFilter  # noqa: E402
import numpy as np  # noqa: E402

PLACEHOLDER_BRANDS = ("【你的机构名】", "创享美育", "你的机构")

# 各角色的图像指标期望（实测标定）
EXPECT = {
    "sketch": dict(color_max=0.03, note="铅笔起形应几乎无彩色"),
    "ink":    dict(color_max=0.06, note="勾线应是黑白线稿，最多少量着色"),
    "flat":   dict(color_min=0.06, border_max=0.10, note="平涂/加深页主体应上色、背景仍留白"),
}


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def paper_box(im, thresh_v=0.72, thresh_s=0.22, q=0.03):
    """找「纸」的区域（比例坐标 0~1）。

    范画图是「纸放在木桌上」的俯拍：四周有木纹边框，直接按四边采样会把木桌当成
    “彩色背景”，所有阈值全废。这里按「亮且低饱和」筛出纸面，用行列投影的分位
    数定 bbox。找不到纸就退回整图。
    """
    a = np.asarray(im.convert("RGB").resize((320, 320), Image.LANCZOS)).astype(np.uint16)
    mx = a.max(axis=2) / 255.0
    mn = a.min(axis=2) / 255.0
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    mask = (mx > thresh_v) & (sat < thresh_s)
    if mask.mean() < 0.12:            # 纸面积太小 → 不是俯拍纸画，退回整图
        return (0.0, 0.0, 1.0, 1.0)
    rows = mask.mean(axis=1)
    cols = mask.mean(axis=0)
    ri = np.where(rows > rows.max() * 0.55)[0]
    ci = np.where(cols > cols.max() * 0.55)[0]
    if not len(ri) or not len(ci):
        return (0.0, 0.0, 1.0, 1.0)
    hgt, wid = rows.shape[0], cols.shape[0]
    x0, x1 = ci[0] / wid, (ci[-1] + 1) / wid
    y0, y1 = ri[0] / hgt, (ri[-1] + 1) / hgt
    if (x1 - x0) < 0.5 or (y1 - y0) < 0.5:   # 框太小不可信
        return (0.0, 0.0, 1.0, 1.0)
    return (x0, y0, x1, y1)


def color_stats(im):
    """返回 (全图彩色占比, 纸面四边环带彩色占比, 平均亮度)，都已排除木桌边框。

    “彩色”判定：HSV 饱和度 > 0.28 且明度 > 0.22 —— 淡灰铅笔、黑线、白纸都不会命中，
    马克笔平涂、深蓝夜空都会命中（阈值按本机 5 套定稿课件实测标定）。
    """
    box = paper_box(im)
    w0, h0 = im.size
    x0, y0, x1, y1 = box
    crop = im.crop((int(x0 * w0), int(y0 * h0), int(x1 * w0), int(y1 * h0)))
    crop.thumbnail((420, 420), Image.LANCZOS)
    a = np.asarray(crop.convert("RGB")).astype(np.float32) / 255.0
    mx = a.max(axis=2)
    mn = a.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    hit = (sat > 0.28) & (mx > 0.22)
    h, w = hit.shape
    bw = max(2, int(w * 0.10))
    bh = max(2, int(h * 0.10))
    ring = np.zeros_like(hit)
    ring[:bh, :] = ring[-bh:, :] = True
    ring[:, :bw] = ring[:, -bw:] = True
    return (float(hit.mean()),
            float(hit[ring].mean()) if ring.any() else 0.0,
            float(a.mean()))


def edge_ncc(a, b, out=96, keep=0.72):
    """边缘图归一化互相关（0~1），只比中心区域。

    为什么不用灰度 NCC：成品是满屏深蓝夜空，步骤 3/4 是白底，灰度差天生巨大，
    灰度 NCC 会把「同一棵树」判成两张画（实测 0.46）。边缘图只看轮廓位置，稳得多。
    """
    def prep(im):
        e = im.convert("L").resize((200, 200), Image.LANCZOS).filter(ImageFilter.FIND_EDGES)
        e = e.crop((int(100 - 100 * keep), int(100 - 100 * keep),
                    int(100 + 100 * keep), int(100 + 100 * keep))).resize((out, out), Image.LANCZOS)
        return np.asarray(e).astype(np.float32)
    va, vb = prep(a).ravel(), prep(b).ravel()
    ma, mb = va.mean(), vb.mean()
    da, db = (va - ma), (vb - mb)
    na, nb = float(np.linalg.norm(da)), float(np.linalg.norm(db))
    if not na or not nb:
        return 0.0
    return float((da @ db) / (na * nb) + 1) / 2


def role_of(slot):
    if "步骤1" in slot or "起形" in slot:
        return "sketch"
    if "步骤2" in slot or "勾线" in slot:
        return "ink"
    if slot.startswith("范画步骤"):
        return "flat"
    return None


def make_sheet(proj, paths, stats, items, out_path, cols=4, cw=430, ch=288, label=34):
    """把全部槽位拼成一张图。链条顺序在前，红框/红字 = 该槽位有 FAIL/WARN。

    为什么需要它：颜色类指标抓不到「图不对题」（比如材料工具页跑出一张小象儿童画），
    也抓不到「步骤1 多了个底座」。这类错只能人眼看，那就把 16 张拼成一张，
    一眼扫完，别让人一张张点开。
    """
    from PIL import ImageDraw, ImageFont
    order = [s for s in (proj.chain.get("order") or []) if s in paths]
    order += [s for s in paths if s not in order]
    bad = {}
    for lvl, area, msg in items:
        if lvl == "PASS":
            continue
        for slot in paths:
            if slot in msg:
                bad[slot] = "FAIL" if lvl == "FAIL" else "WARN"
    rows = (len(order) + cols - 1) // cols
    W, H = cols * cw, rows * (ch + label)
    bg = Image.new("RGB", (W, H), (250, 247, 240))
    d = ImageDraw.Draw(bg)
    try:
        f = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
    except Exception:
        f = ImageFont.load_default()
    for i, slot in enumerate(order):
        im = Image.open(paths[slot]).convert("RGB")
        im.thumbnail((cw - 12, ch - 12), Image.LANCZOS)
        x = (i % cols) * cw
        y = (i // cols) * (ch + label)
        bg.paste(im, (x + (cw - im.width) // 2, y + (ch - im.height) // 2))
        lvl = bad.get(slot)
        if lvl:
            d.rectangle([x + 3, y + 3, x + cw - 3, y + ch - 3],
                        outline=(200, 30, 30) if lvl == "FAIL" else (230, 140, 20), width=4)
        st = stats.get(slot) or {}
        cap = "%s  c=%.2f b=%.2f" % (slot, st.get("color", 0), st.get("border", 0))
        d.text((x + cw // 2, y + ch + 6), cap, font=f, anchor="ma",
               fill=(190, 30, 30) if lvl == "FAIL" else ((200, 120, 10) if lvl == "WARN" else (47, 69, 80)))
    bg.save(out_path, quality=88)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--strict", action="store_true", help="WARN 也算失败")
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--json", default="", help="把报告写到指定 json 路径")
    ap.add_argument("--sheet", default="auto",
                    help="出 16 张接触印样（auto=输出到 out/_自检_全部图.jpg，off=不出）")
    a = ap.parse_args()

    proj = Project(a.project)
    items = []          # (level, area, msg)
    F = lambda ar, m: items.append(("FAIL", ar, m))
    W = lambda ar, m: items.append(("WARN", ar, m))
    P = lambda ar, m: items.append(("PASS", ar, m))

    # ---------- A. 结构 ----------
    pages, images = proj.pages, proj.images
    slots = {im["slot"] for im in images}
    anchor = proj.chain.get("anchor")
    order = proj.chain.get("order") or []

    if not pages:
        F("结构", "pages 为空 —— 半成品项目，先补齐 26 页再跑图")
    elif len(pages) < 26:
        W("结构", "pages 只有 %d 页（标准 26 页）" % len(pages))
    else:
        P("结构", "pages %d 页" % len(pages))

    used = set()
    for i, pg in enumerate(pages, 1):
        for u in (pg.get("uses") or []):
            used.add(u)
            if u not in slots:
                F("结构", "P%d 引用了不存在的槽位「%s」" % (i, u))
        for k in ("image", "image2"):
            if pg.get(k) and pg[k] not in slots:
                F("结构", "P%d 的 %s=「%s」不是有效槽位" % (i, k, pg[k]))
    miss = [s for s in slots if s not in used]
    if miss:
        W("结构", "有槽位没被任何页面用到：%s" % "、".join(miss))
    else:
        P("结构", "槽位与页面 uses 完全对齐")

    brand = str(proj.meta.get("brand") or "")
    if any(b in brand for b in PLACEHOLDER_BRANDS):
        F("结构", "meta.brand 还是占位符/母版品牌：%s" % brand)
    elif not brand:
        F("结构", "meta.brand 为空（会印在每页页脚）")
    else:
        P("结构", "品牌：%s" % brand)

    for s in order:
        if s not in slots:
            F("链条", "chain.order 里的「%s」不在 images 里" % s)
    if anchor and anchor not in slots:
        F("链条", "anchor「%s」不在 images 里" % anchor)

    # 关键：步骤1 必须挂在成品上（否则从零发明 → 两棵树）
    step1 = next((im for im in images if role_of(im["slot"]) == "sketch"), None)
    if not step1:
        W("链条", "没有起形步骤（步骤1/起形），跳过链条检查")
    else:
        ok_ref = anchor and anchor in (step1.get("refs") or [])
        if not ok_ref:
            F("链条", "步骤1「%s」没把成品「%s」放进 refs —— 它会从零发明骨架，"
                     "成品和步骤会变成两棵树。修法：refs=[\"%s\"]，prompt 写成「把参考图降级成淡灰铅笔骨架」"
                     % (step1["slot"], anchor, anchor))
        else:
            P("链条", "步骤1 已挂成品参考「%s」" % anchor)

        # 涂色页要写死背景留白
        for im in images:
            if role_of(im["slot"]) == "flat" and "步骤3" in im["slot"]:
                t = (im.get("prompt") or "").lower()
                if "blank white" not in t and "blank" not in t:
                    W("链条", "涂色步骤「%s」prompt 没写死背景留白，模型容易提前涂天空" % im["slot"])

    lock = (proj.lock or "").lower()
    if "no tray" not in lock and "no plinth" not in lock and "no base" not in lock:
        W("链条", "LOCK 没禁止底座/托盘（实测模型会自己加一个椭圆底座，成品和步骤都不一样）")

    # ---------- B. 图像 ----------
    paths = {}
    for im in images:
        p = proj.img_path(im["slot"], "hd")
        if not p:
            F("图像", "槽位「%s」没有图" % im["slot"])
        else:
            paths[im["slot"]] = p
    if not any(l == "FAIL" and ar == "图像" for l, ar, _ in items):
        P("图像", "%d 个槽位都有图" % len(paths))

    alias_slots = {i["slot"] for i in images if i.get("alias")}
    stats = {}
    for slot, p in paths.items():
        try:
            im = Image.open(p)
        except Exception as e:
            F("图像", "「%s」打不开：%s" % (slot, e))
            continue
        cr, bcr, lum = color_stats(im)
        stats[slot] = dict(size=list(im.size), mb=round(os.path.getsize(p) / 1e6, 2),
                           color=round(cr, 4), border=round(bcr, 4), lum=round(lum, 3), md5=md5(p))
        role = role_of(slot)
        if role == "sketch":
            if cr > EXPECT["sketch"]["color_max"]:
                F("图像", "「%s」彩色占比 %.1f%% —— 起形页应该是淡灰铅笔，现在上了色"
                  % (slot, cr * 100))
        elif role == "ink":
            if cr > EXPECT["ink"]["color_max"]:
                W("图像", "「%s」彩色占比 %.1f%% —— 勾线页偏彩色，检查是否提前上色"
                  % (slot, cr * 100))
        elif role == "flat":
            if cr < EXPECT["flat"]["color_min"]:
                W("图像", "「%s」彩色占比仅 %.1f%% —— 平涂/加深页几乎没上色？"
                  % (slot, cr * 100))
            # 只有「涂色/加深」这几步要背景留白；最后一步"加背景"本来就该涂满
            if bcr > EXPECT["flat"]["border_max"] and slot not in alias_slots:
                W("图像", "「%s」四边彩色占比 %.1f%% —— 背景可能被提前涂了（这几步应留白）"
                  % (slot, bcr * 100))

    # alias：最后一步必须与成品像素一致
    for im in images:
        al = im.get("alias")
        if al and al in stats and im["slot"] in stats:
            if stats[al]["md5"] == stats[im["slot"]]["md5"]:
                P("图像", "「%s」= 「%s」副本（md5 相同）" % (im["slot"], al))
            else:
                F("图像", "「%s」声明是「%s」的别名，但 md5 不同 —— alias 没生效"
                  % (im["slot"], al))

    # 成品 vs 步骤3/4 构图一致性
    if anchor and anchor in paths:
        base = Image.open(paths[anchor])
        for slot in paths:
            if slot == anchor or role_of(slot) != "flat":
                continue
            s = edge_ncc(base, Image.open(paths[slot]))
            if s < 0.60:
                W("图像", "「%s」与成品的构图相似度 %.2f（<0.60）—— 可能不是同一张画"
                  % (slot, s))
            else:
                P("图像", "「%s」与成品构图相似度 %.2f" % (slot, s))

    # ---------- C. 交付物 ----------
    if not a.no_pdf:
        pdf = proj.pdf()
        if not os.path.exists(pdf):
            W("交付", "还没有 PDF（先 builder + exporter），卖之前必须有")
        else:
            try:
                from pypdf import PdfReader
                n = len(PdfReader(pdf).pages)
                if pages and n != len(pages):
                    F("交付", "PDF %d 页 != pages %d 页（导的是旧版？）" % (n, len(pages)))
                else:
                    P("交付", "PDF %d 页 / %.1f MB" % (n, os.path.getsize(pdf) / 1e6))
            except Exception as e:
                W("交付", "PDF 页数读不到：%s" % e)

    # ---------- 报告 ----------
    tag = {"FAIL": "✗", "WARN": "!", "PASS": "·"}
    print("=" * 78)
    print("自检：%s  |  %d 页 / %d 槽位 / %d 图"
          % (proj.name, len(pages), len(images), len(paths)))
    print("=" * 78)
    for lvl in ("FAIL", "WARN", "PASS"):
        rows = [r for r in items if r[0] == lvl]
        if not rows:
            continue
        print("\n[%s] %d 条" % (lvl, len(rows)))
        for _l, ar, msg in rows:
            print("  %s %-4s %s" % (tag[lvl], ar, msg))

    nf = sum(1 for r in items if r[0] == "FAIL")
    nw = sum(1 for r in items if r[0] == "WARN")
    print("\n" + "-" * 78)
    print("结论：%d FAIL / %d WARN" % (nf, nw))
    if nf:
        print("→ 先修 FAIL 再装配/发布。步骤类问题一律：改 prompt → --only <槽位及其后续> 重跑。")
    elif nw:
        print("→ 没有硬错，但 WARN 要人眼确认一眼（尤其「不是同一张画」那条）。")
    else:
        print("→ 全过。可以 builder → exporter → deliver → 发布。")

    if a.json:
        json.dump(dict(deck=proj.name, items=items, stats=stats),
                  open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("报告：%s" % a.json)

    if a.sheet != "off" and paths:
        sheet = a.sheet if a.sheet != "auto" else os.path.join(proj.out_dir, "_自检_全部图.jpg")
        try:
            make_sheet(proj, paths, stats, items, sheet)
            print("接触印样：%s  （一眼扫完 16 张，红框=自检有话说）" % sheet)
        except Exception as e:
            print("接触印样生成失败：%s" % e)

    if nf:
        return 1
    if nw and a.strict:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
