# -*- coding: utf-8 -*-
"""生成小红书账号视觉三件套（头像 + 背景图）。
不调用任何付费出图 API，本地 PIL 绘制，免费。
用法：python 做账号视觉.py
输出：账号改造/avatar_*.png 背景图.png
"""
import os
import sys
from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "账号改造")
os.makedirs(OUT, exist_ok=True)

FB = "C:/Windows/Fonts/msyhbd.ttc"   # 微软雅黑 Bold
FR = "C:/Windows/Fonts/msyh.ttc"     # 微软雅黑 Regular

# 取自课件母版 theme
GREEN = (119, 166, 90)    # #77A65A
DARKGREEN = (87, 139, 24)  # #578B18
ORANGE = (249, 166, 5)     # #F9A605
INK = (53, 66, 83)         # #354253
CREAM = (250, 247, 240)


def fit_font(path, text, max_w, max_h, start=600):
    """二分找最大字号，使 text 装进 max_w x max_h"""
    lo, hi = 10, start
    best = lo
    while lo <= hi:
        mid = (lo + hi) // 2
        f = ImageFont.truetype(path, mid)
        bbox = f.getbbox(text)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if w <= max_w and h <= max_h:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return ImageFont.truetype(path, best)


def draw_center(d, xy_box, text, font, fill):
    x0, y0, x1, y1 = xy_box
    bbox = font.getbbox(text)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = x0 + (x1 - x0 - w) / 2 - bbox[0]
    y = y0 + (y1 - y0 - h) / 2 - bbox[1]
    d.text((x, y), text, font=font, fill=fill)


def avatar(bg, text, fg, accent=None, name="avatar.png", size=1080):
    im = Image.new("RGB", (size, size), bg)
    d = ImageDraw.Draw(im)
    pad = int(size * 0.16)
    box = (pad, pad, size - pad, size - pad)
    f = fit_font(FB, text, box[2] - box[0], box[3] - box[1])
    draw_center(d, box, text, f, fg)
    if accent:  # 右下角小圆点，做点缀
        r = int(size * 0.055)
        cx, cy = int(size * 0.80), int(size * 0.80)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=accent)
    p = os.path.join(OUT, name)
    im.save(p, quality=95)
    print("  头像 ->", p, im.size)
    return p


def banner(name="背景图.png", w=1080, h=1920):
    """内容放在中间的'安全带'，无论平台怎么裁都留得住"""
    im = Image.new("RGB", (w, h), CREAM)
    d = ImageDraw.Draw(im)
    # 顶部一条主色带
    d.rectangle((0, 0, w, int(h * 0.045)), fill=GREEN)
    cy = h // 2
    # 主标题
    t1 = "绘课工坊"
    f1 = fit_font(FB, t1, int(w * 0.62), int(h * 0.070))
    draw_center(d, (0, cy - int(h * 0.10), w, cy - int(h * 0.02)), t1, f1, INK)
    # 副标题
    t2 = "3-12岁少儿创意美术课件"
    f2 = fit_font(FR, t2, int(w * 0.72), int(h * 0.032))
    draw_center(d, (0, cy + int(h * 0.005), w, cy + int(h * 0.045)), t2, f2, DARKGREEN)
    # 第三条
    t3 = "26页完整课件 · PPTX可编辑 + PDF可打印"
    f3 = fit_font(FR, t3, int(w * 0.74), int(h * 0.026))
    draw_center(d, (0, cy + int(h * 0.055), w, cy + int(h * 0.090)), t3, f3, INK)
    # 装饰小圆点
    for i, c in enumerate([GREEN, ORANGE, INK]):
        r = int(w * 0.012)
        cx = int(w * 0.5) + (i - 1) * int(w * 0.055)
        d.ellipse((cx - r, cy + int(h * 0.115) - r, cx + r, cy + int(h * 0.115) + r), fill=c)
    p = os.path.join(OUT, name)
    im.save(p, quality=95)
    print("  背景 ->", p, im.size)
    return p


if __name__ == "__main__":
    print("输出目录:", OUT)
    avatar(GREEN, "绘课", (255, 255, 255), accent=ORANGE, name="avatar_1_绿底绘课.png")
    avatar(CREAM, "绘课工坊", INK, accent=ORANGE, name="avatar_2_米底绘课工坊.png")
    avatar(INK, "绘课", ORANGE, name="avatar_3_深蓝绘课.png")
    avatar(ORANGE, "绘课工坊", INK, name="avatar_4_橙底绘课工坊.png")
    banner()
    print("完成")
