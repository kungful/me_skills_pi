#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 ic_launcher.png —— 茶叶军师：帅印（金环）+ 交叉令旗（两片茶叶）。

无网络、无字体依赖，纯 PIL 画。
整张图先按 4 倍尺寸画，最后 LANCZOS 缩回目标尺寸 —— 这样边缘干净不糊。
叶子轮廓用 sin 曲线生成（两端收尖、腰部饱满），比椭圆更像茶叶。
"""
from PIL import Image, ImageDraw
import math
import os

SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
SS = 4  # 超采样倍数

BG = (13, 18, 16, 255)
GOLD = (200, 162, 74, 255)
LEAF = (124, 176, 136, 255)
LEAF_D = (74, 122, 92, 255)
VEIN = (44, 78, 60, 255)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

LEAF_L = 0.60   # 叶长（相对尺寸）
LEAF_W = 0.168  # 叶宽
ANGLE = 42      # 交叉角度


def rounded(size, radius, fill):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=fill)
    return im


def leaf_layer(px, u):
    """在 px×px 透明画布上画一片横向叶子。u = 图标边长（所有尺寸相对它取）。"""
    im = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = px / 2.0
    L = u * LEAF_L
    W = u * LEAF_W
    edge = max(1, int(u * 0.007))
    N = 160

    top, bot = [], []
    for i in range(N + 1):
        t = i / N
        x = c - L / 2 + t * L
        y = (W / 2.0) * (math.sin(math.pi * t) ** 0.62)
        top.append((x, c - y))
        bot.append((x, c + y))
    d.polygon(top + bot[::-1], fill=LEAF, outline=LEAF_D, width=edge)

    # 叶柄
    d.line([(c - L / 2 - u * 0.040, c), (c - L / 2 + u * 0.01, c)],
           fill=LEAF_D, width=max(2, int(u * 0.016)))
    # 主脉
    d.line([(c - L / 2 + u * 0.012, c), (c + L / 2 - u * 0.014, c)],
           fill=VEIN, width=max(2, int(u * 0.013)))
    # 侧脉（小尺寸画上去只会变噪点，直接省掉）
    for t in (() if u < 96 else  (0.26, 0.42, 0.58, 0.74)):
        x = c - L / 2 + t * L
        y = (W / 2.0) * (math.sin(math.pi * t) ** 0.62)
        d.line([(x, c), (x + L * 0.115, c - y * 0.70)], fill=VEIN, width=max(1, int(u * 0.008)))
        d.line([(x, c), (x + L * 0.115, c + y * 0.70)], fill=VEIN, width=max(1, int(u * 0.008)))
    return im


def render(px):
    """按 px×px 画整张图。"""
    canvas = rounded(px, int(px * 0.22), BG)

    # 帅印金环
    ring = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    pad = px * 0.075
    ImageDraw.Draw(ring).ellipse([pad, pad, px - pad, px - pad], outline=GOLD,
                                 width=max(2, int(px * 0.034)))
    canvas = Image.alpha_composite(canvas, ring)

    # 交叉的两片茶叶（像两杆交叉的令旗）
    big = px * 2
    base = leaf_layer(big, px)
    for ang in (-ANGLE, ANGLE):
        rot = base.rotate(ang, resample=Image.BICUBIC, center=(big / 2.0, big / 2.0))
        off = big / 2.0 - px / 2.0
        canvas = Image.alpha_composite(canvas, rot.crop((off, off, off + px, off + px)))

    # 正中金点（印钮）
    d = ImageDraw.Draw(canvas)
    r = px * 0.050
    d.ellipse([px / 2 - r, px / 2 - r, px / 2 + r, px / 2 + r], fill=GOLD)
    d.ellipse([px / 2 - r, px / 2 - r, px / 2 + r, px / 2 + r], outline=(150, 118, 48, 255),
              width=max(1, int(px * 0.006)))
    return canvas


for dpi, S in SIZES.items():
    img = render(S * SS).resize((S, S), Image.LANCZOS)
    out = os.path.join(ROOT, "res", "mipmap-" + dpi, "ic_launcher.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out)
    print("wrote", out, S)
