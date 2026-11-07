# -*- coding: utf-8 -*-
"""《孩子画的人，为什么没有身体？》阶段对照图 —— 卡片合成

输入：项目/人怎么画-4-6岁/原图无水印/阶段*.png（grsai 出的无水印原图）
输出：
    成品无水印/01..07.jpg   ← 干净版，本地备份 / 自己复用
    成品带水印/01..07.jpg   ← 上传小红书（由 _水印.py 生成）

用法：python _阶段对照.py
"""
import glob
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.join(ROOT, "项目", "人怎么画-4-6岁")
SRC = os.path.join(PROJ, "原图无水印")
CLEAN = os.path.join(PROJ, "成品无水印")
WMSET = os.path.join(PROJ, "成品带水印")

W, H = 1080, 1440
F = "C:/Windows/Fonts/msyhbd.ttc"
GREEN = (119, 166, 90)
DGREEN = (74, 110, 55)
ORANGE = (249, 166, 5)
CREAM = (250, 247, 240)
INK = (58, 70, 82)
SUB = (120, 132, 145)


def font(sz):
    return ImageFont.truetype(F, sz)


def wrap(d, text, f, maxw):
    out, cur = [], ""
    for ch in text:
        if ch == "\n":
            out.append(cur)
            cur = ""
            continue
        if d.textlength(cur + ch, font=f) <= maxw:
            cur += ch
        else:
            out.append(cur)
            cur = ch
    if cur:
        out.append(cur)
    return out


def crop_to(im, w, h, bias=0.42):
    """按目标比例裁剪（bias 控制保留上部还是下部，0=保上，1=保下）"""
    iw, ih = im.size
    target = w / h
    if iw / ih > target:                     # 图更宽 → 裁左右
        nw = int(ih * target)
        x = (iw - nw) // 2
        box = (x, 0, x + nw, ih)
    else:                                    # 图更高 → 裁上下
        nh = int(iw / target)
        y = int((ih - nh) * bias)
        box = (0, y, iw, y + nh)
    return im.crop(box).resize((w, h), Image.LANCZOS)



def trim_white(im, sat_thresh=34, pad=0.10):
    """自动裁掉纸面空白：用「饱和度」找蜡笔笔画，而不是用亮度。

    纸是中性灰白（饱和度极低），蜡笔颜色饱和度高，两者能干净分开；
    亮度法会被纸面阴影/渐变骗到，整张都判成有内容。
    """
    from PIL import ImageChops
    r, g, b = im.split()
    mx = ImageChops.lighter(ImageChops.lighter(r, g), b)
    mn = ImageChops.darker(ImageChops.darker(r, g), b)
    sat = ImageChops.subtract(mx, mn)
    mask = sat.point(lambda v: 255 if v > sat_thresh else 0)
    bb = mask.getbbox()
    if not bb:
        return im
    x1, y1, x2, y2 = bb
    w, h = im.size
    px, py = int((x2 - x1) * pad), int((y2 - y1) * pad)
    x1, y1 = max(0, x1 - px), max(0, y1 - py)
    x2, y2 = min(w, x2 + px), min(h, y2 + py)
    return im.crop((x1, y1, x2, y2))


def fit_to(im, w, h, bg=(247, 247, 247)):
    """整张适配（不裁切）：等比缩到框内，四周留底色。儿童画是白纸，留边不违和。"""
    iw, ih = im.size
    sc = min(w / iw, h / ih)
    nw, nh = max(1, int(iw * sc)), max(1, int(ih * sc))
    im2 = im.resize((nw, nh), Image.LANCZOS)
    box = Image.new("RGB", (w, h), bg)
    box.paste(im2, ((w - nw) // 2, (h - nh) // 2))
    return box


# ---------------- 封面：满版图 + 底部绿块压标题 ----------------
def cover(path, img_path, kicker, title, sub, idx, total):
    cv = Image.new("RGB", (W, H), CREAM)
    im = Image.open(img_path).convert("RGB")
    # 上部分放图，下部分留文字区（高度算好，避免标题圧到页脚）
    band_y = 880
    cv.paste(fit_to(trim_white(im), W, band_y), (0, 0))

    d = ImageDraw.Draw(cv)
    d.rectangle((0, band_y, W, H), fill=GREEN)
    d.rectangle((90, band_y + 48, 250, band_y + 60), fill=ORANGE)

    y = band_y + 72
    for ln in kicker.split("\n"):
        d.text((90, y), ln, font=font(42), fill=(255, 255, 255))
        y += 54

    y += 8
    for ln in title.split("\n"):
        for w in wrap(d, ln, font(88), W - 180):
            d.text((90, y), w, font=font(88), fill=(255, 255, 255))
            y += 112

    y += 10
    for ln in wrap(d, sub, font(42), W - 180):
        d.text((90, y), ln, font=font(42), fill=(240, 240, 240))
        y += 58

    d.text((90, H - 112), "绘课工坊", font=font(34), fill=(255, 255, 255))
    d.text((W - 190, H - 112), "%d / %d" % (idx, total), font=font(34), fill=(255, 255, 255))
    cv.save(path, quality=94, subsampling=1)
    return cv.size


# ---------------- 阶段图卡：顶部绿带 + 大图 + 一句结论 ----------------
def stage_card(path, img_path, kicker, title, sub, note, idx, total, bias=0.5):
    cv = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(cv)

    tl = []
    for ln in (title + "\n" + sub).split("\n"):
        tl += wrap(d, ln, font(78), W - 180) if ln else [""]
    band = 180 + len(tl) * 94

    d.rectangle((0, 0, W, band), fill=GREEN)
    d.text((90, 54), kicker, font=font(40), fill=(255, 255, 255))
    y = 116
    for ln in tl:
        d.text((90, y), ln, font=font(78), fill=(255, 255, 255))
        y += 94
    d.rectangle((0, band, W, band + 12), fill=ORANGE)

    # 图片区
    top = band + 12
    bottom = H - 260                       # 底部留给 note + footer
    ih = bottom - top
    im = trim_white(Image.open(img_path).convert("RGB"))
    cv.paste(fit_to(im, W, ih), (0, top))

    # note 白底条
    d.rectangle((0, bottom, W, H - 110), fill=CREAM)
    ny = bottom + 30
    for ln in wrap(d, note, font(42), W - 180):
        d.text((90, ny), ln, font=font(42), fill=DGREEN)
        ny += 58

    d.text((90, H - 112), "绘课工坊", font=font(34), fill=SUB)
    d.text((W - 190, H - 112), "%d / %d" % (idx, total), font=font(34), fill=SUB)
    cv.save(path, quality=94, subsampling=1)
    return cv.size


# ---------------- 文字卡（沿用主账号版式）----------------
def text_card(path, kicker, title, sub, lines, idx, total):
    cv = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(cv)
    tl = []
    for ln in (title + "\n" + sub).split("\n"):
        tl += wrap(d, ln, font(84), W - 180) if ln else [""]
    band = 190 + len(tl) * 100
    d.rectangle((0, 0, W, band), fill=GREEN)
    d.text((90, 58), kicker, font=font(42), fill=(255, 255, 255))
    y = 126
    for ln in tl:
        d.text((90, y), ln, font=font(84), fill=(255, 255, 255))
        y += 100
    d.rectangle((0, band, W, band + 12), fill=ORANGE)

    maxw = W - 180
    lh = 1.42
    h = sum(pad + len(wrap(d, t, font(sz), maxw)) * int(sz * lh) for t, sz, c, pad in lines)
    y = band + 12 + max(60, (H - 150 - (band + 12) - h) // 2)
    for t, sz, c, pad in lines:
        f = font(sz)
        y += pad
        for ln in wrap(d, t, f, maxw):
            d.text((90, y), ln, font=f, fill=c)
            y += int(sz * lh)
    d.text((90, H - 112), "绘课工坊", font=font(34), fill=SUB)
    d.text((W - 190, H - 112), "%d / %d" % (idx, total), font=font(34), fill=SUB)
    cv.save(path, quality=94, subsampling=1)
    return cv.size


def main():
    os.makedirs(CLEAN, exist_ok=True)
    os.makedirs(WMSET, exist_ok=True)

    p1 = os.path.join(SRC, "阶段1_头足人.png")
    p2 = os.path.join(SRC, "阶段2_有身体.png")
    p3 = os.path.join(SRC, "阶段3_有手指.png")
    p4 = os.path.join(SRC, "阶段4_有基底线.png")
    for p in (p1, p2, p3, p4):
        if not os.path.exists(p):
            print("缺图:", p)
            return 1

    total = 7
    jobs = [
        lambda out: cover(out, p1, "4-6岁 · 人的画法",
                          "孩子画的人\n为什么没有身体？",
                          "先看完这4张，再决定要不要纠正他。", 1, total),
        lambda out: stage_card(out, p1, "阶段① 3-4岁",
                               "只有一个大脑袋", "+两条腿",
                               "不是偷懒。他只画「最重要」的部分。",
                               2, total, bias=0.55),
        lambda out: stage_card(out, p2, "阶段② 4-5岁",
                               "身体长出来了", "手是火柴棍",
                               "手先出现，手指后长。别急着催。",
                               3, total, bias=0.52),
        lambda out: stage_card(out, p3, "阶段③ 5-6岁",
                               "手指画成一排", "人还飘在纸上",
                               "手指是他数出来的，不是看出来的。",
                               4, total, bias=0.52),
        lambda out: stage_card(out, p4, "阶段④ 6-7岁",
                               "脚下有地了", "人才真正站稳",
                               "基底线一出现，就开始懂空间了。",
                               5, total, bias=0.88),
        lambda out: text_card(out, "所以别做这件事",
                              "别替他画", "也别纠正「没身体」",
                              [("他不是画错，", 50, INK, 40),
                               ("是还没走到那一步。", 50, DGREEN, 40),
                               ("你能做的是三件小事：", 46, INK, 60),
                               ("一、问他「这个人在干什么」", 48, DGREEN, 30),
                               ("二、让他把同一个人再画三张", 48, DGREEN, 20),
                               ("三、只说画里有什么，不说像不像", 48, DGREEN, 20)],
                              6, total),
        lambda out: text_card(out, "一句话总结",
                              "先认阶段", "再谈指导",
                              [("孩子比不过的从来不是同龄人，", 46, INK, 50),
                               ("是他还没走到的那个阶段。", 52, DGREEN, 0),
                               ("这4张对照图，建议存下来。", 44, SUB, 60)],
                              7, total),
    ]

    names = ["01_封面", "02_阶段1_头足人", "03_阶段2_有身体",
             "04_阶段3_有手指", "05_阶段4_有基底线", "06_别做这件事", "07_总结"]
    for job, nm in zip(jobs, names):
        out = os.path.join(CLEAN, nm + ".jpg")
        sz = job(out)
        print("  %-24s %s" % (nm, sz))

    # 带水印版
    print("\n加水印…")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "_水印.py"), CLEAN,
                        "--out", WMSET], capture_output=True, text=True, encoding="utf-8")
    print(r.stdout.strip()[-400:] if r.stdout else r.stderr[-400:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
