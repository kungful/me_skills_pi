#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 ic_launcher.png —— 直角三角形意象：
橙色=对边 蓝色=邻边 绿色=斜边，右下直角标记，左下角画角弧。
纯 PIL 绘制，无网络 / 无字体依赖。"""
from PIL import Image, ImageDraw
import os

SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
BG      = (14, 17, 22, 255)
OPP     = (255, 180, 58, 255)    # 对边 → 琥珀
ADJ     = (69, 200, 255, 255)    # 邻边 → 冰蓝
HYP     = (74, 222, 128, 255)    # 斜边 → 绿
DIM     = (122, 137, 156, 255)
GRID    = (34, 44, 56, 255)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

A = (13.0, 84.0)     # 左下：参考角
C = (84.0, 84.0)     # 右下：直角
B = (84.0, 22.0)     # 右上

for dpi, S in SIZES.items():
    img = Image.new("RGBA", (S, S), BG)
    d = ImageDraw.Draw(img)
    u = S / 100.0

    def P(p):
        return (p[0] * u, p[1] * u)

    # 背景网格（淡）
    step = 12
    for g in range(step, 100, step):
        d.line([(g * u, 0), (g * u, S)], fill=GRID, width=max(1, int(u)))
        d.line([(0, g * u), (S, g * u)], fill=GRID, width=max(1, int(u)))

    lw = max(2, int(6.5 * u))

    # 兜底圆角底板
    d.rounded_rectangle([3 * u, 3 * u, 97 * u, 97 * u], radius=18 * u, outline=(40, 52, 66, 255), width=max(1, int(u)))

    # 邻边 (底) 蓝
    d.line([P(A), P(C)], fill=ADJ, width=lw)
    # 对边 (右) 橙
    d.line([P(C), P(B)], fill=OPP, width=lw)
    # 斜边 绿
    d.line([P(A), P(B)], fill=HYP, width=lw)

    # 直角标记
    sq = 13 * u
    d.line([(C[0] * u - sq, C[1] * u), (C[0] * u - sq, C[1] * u - sq)], fill=DIM, width=max(1, int(2.4 * u)))
    d.line([(C[0] * u - sq, C[1] * u - sq), (C[0] * u, C[1] * u - sq)], fill=DIM, width=max(1, int(2.4 * u)))

    # 左下角弧
    r = 30 * u
    d.arc([A[0] * u, A[1] * u - r, A[0] * u + 2 * r, A[1] * u + r],
          start=270, end=323, fill=(255, 255, 255, 210), width=max(2, int(3.4 * u)))

    # 三个顶点小圆
    for p, c in ((A, (255, 255, 255, 235)), (B, (255, 255, 255, 235)), (C, DIM)):
        rr = 3.2 * u
        d.ellipse([p[0] * u - rr, p[1] * u - rr, p[0] * u + rr, p[1] * u + rr], fill=c)

    out = os.path.join(ROOT, "app", "res", "mipmap-" + dpi, "ic_launcher.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out)
    print("wrote", out, S)
