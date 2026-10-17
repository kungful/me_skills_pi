#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 ic_launcher.png —— 直角三角形意象：
蓝色=邻边 橙色=对边 绿色=斜边，直角标记 + 参考角弧 + 三个顶点。
纯 PIL 绘制（4 倍超采样再缩小，边缘干净），无网络 / 无字体依赖。"""
from PIL import Image, ImageDraw
import os

SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
SS = 4                                   # 超采样倍数

BG    = (14, 17, 22, 255)     # 和 App 背景一致
TILE  = (22, 28, 37, 255)
OPP   = (255, 180, 58, 255)   # 对边 → 琥珀
ADJ   = (69, 200, 255, 255)   # 邻边 → 冰蓝
HYP   = (74, 222, 128, 255)   # 斜边 → 绿
DIM   = (122, 137, 156, 255)
WHITE = (240, 245, 250, 255)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 单位坐标系 100×100：A 是参考角，C 是直角，B 是另一个锐角顶点
A = (20.0, 78.0)
C = (80.0, 78.0)
B = (80.0, 26.0)


def render(S):
    n = S * SS
    u = n / 100.0
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def P(p):
        return (p[0] * u, p[1] * u)

    # 圆角底板
    d.rounded_rectangle([2 * u, 2 * u, 98 * u, 98 * u],
                        radius=23 * u, fill=TILE, outline=(38, 48, 62, 255),
                        width=max(1, round(1.1 * u)))

    lw = round(9 * u)
    # 邻边（底，蓝）· 对边（右，橙）· 斜边（绿）
    d.line([P(A), P(C)], fill=ADJ, width=lw)
    d.line([P(C), P(B)], fill=OPP, width=lw)
    d.line([P(A), P(B)], fill=HYP, width=lw)

    # 直角标记（C 点，往左上方的小方块）
    sq = 15 * u
    d.line([(C[0] * u - sq, C[1] * u), (C[0] * u - sq, C[1] * u - sq), (C[0] * u, C[1] * u - sq)],
           fill=DIM, width=max(1, round(2.6 * u)), joint="curve")

    # 参考角弧：以 A 为圆心，从 AC 方向（0°=正右）扫到 AB 方向
    # 小尺寸下弧不好认，就不画了
    import math
    if S >= 72:
        r = 30 * u
        th = math.degrees(math.atan2(A[1] - B[1], B[0] - A[0]))     # AB 与水平夹角
        d.arc([A[0] * u - r, A[1] * u - r, A[0] * u + r, A[1] * u + r],
              start=360 - th, end=360, fill=(255, 255, 255, 225), width=max(2, round(3.2 * u)))

    # 顶点
    for p, col, rr in ((A, WHITE, 4.0), (B, WHITE, 4.0), (C, DIM, 3.6)):
        d.ellipse([p[0] * u - rr * u, p[1] * u - rr * u,
                   p[0] * u + rr * u, p[1] * u + rr * u], fill=col)

    return img.resize((S, S), Image.LANCZOS)


for dpi, S in SIZES.items():
    out = os.path.join(ROOT, "app", "res", "mipmap-" + dpi, "ic_launcher.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    render(S).save(out)
    print("wrote", out, S)
