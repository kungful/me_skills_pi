#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 ic_launcher.png（太阳 + 遮阳网）——无网络、无字体依赖，纯 PIL 画。"""
from PIL import Image, ImageDraw
import os, math

SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
BG = (13, 17, 23, 255)
SUN = (242, 166, 59, 255)
NET = (47, 129, 247, 255)
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

for dpi, S in SIZES.items():
    img = Image.new("RGBA", (S, S), BG)
    d = ImageDraw.Draw(img)
    c = S / 2.0
    # 太阳
    r = S * 0.17
    d.ellipse([c - r, c - r * 1.12, c + r, c + r * 0.88], fill=SUN)
    # 光芒
    for i in range(8):
        a = math.radians(i * 45)
        x0 = c + math.cos(a) * r * 1.5
        y0 = c - S * 0.012 + math.sin(a) * r * 1.5
        x1 = c + math.cos(a) * r * 2.05
        y1 = c - S * 0.012 + math.sin(a) * r * 2.05
        d.line([x0, y0, x1, y1], fill=SUN, width=max(2, int(S * 0.028)))
    # 遮阳网（网格）
    m = S * 0.13
    top = c + S * 0.16
    bot = S - m
    lw = max(1, int(S * 0.026))
    d.rectangle([m, top, S - m, bot], outline=NET, width=lw)
    n = 4
    for i in range(1, n):
        y = top + (bot - top) * i / n
        d.line([m, y, S - m, y], fill=NET, width=max(1, lw - 1))
    for i in range(1, n + 1):
        x = m + (S - 2 * m) * i / (n + 1)
        d.line([x, top, x, bot], fill=NET, width=max(1, lw - 1))

    out = os.path.join(ROOT, "res", "mipmap-" + dpi, "ic_launcher.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out)
    print("wrote", out, S)
