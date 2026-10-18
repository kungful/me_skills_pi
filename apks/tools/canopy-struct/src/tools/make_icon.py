#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 ic_launcher.png —— 棚架受力分析：墨底 + 青绿三角桁架 + 风箭头。

纯 PIL，无网络无字体。4 倍超采样后 LANCZOS 缩回，边缘干净。
"""
from PIL import Image, ImageDraw
import math, os

SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
SS = 4

BG    = (11, 16, 20, 255)
STEEL = (150, 172, 186, 255)
TEAL  = (68, 199, 169, 255)
WIND  = (238, 176, 74, 255)
GROUND= (44, 60, 70, 255)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def render(px):
    u = px / 100.0
    im = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, px - 1, px - 1], radius=int(px * 0.22), fill=BG)

    def L(x, y, w=2.6, col=STEEL):
        d.line([x * u, y * u, None, None] if False else [x * u, y * u, x * u, y * u], fill=col)
    def line(p1, p2, w=3.0, col=STEEL):
        d.line([p1[0] * u, p1[1] * u, p2[0] * u, p2[1] * u],
               fill=col, width=max(1, int(round(w * u))))

    # 地面
    line((8, 84), (92, 84), 3.2, GROUND)
    # 墙（左侧竖线 + 斜纹）
    line((16, 84), (16, 40), 4.0, GROUND)
    # 立柱
    line((22, 80), (22, 34), 4.2, STEEL)
    line((66, 80), (66, 34), 4.2, STEEL)
    # 挑梁（水平） + 上斜拉（三角）
    line((22, 34), (74, 34), 3.6, STEEL)
    line((22, 16), (74, 34), 2.6, TEAL)
    line((66, 34), (74, 34), 3.6, STEEL)
    # 纵向连线
    line((22, 34), (66, 34), 2.0, (96, 116, 128, 255))
    # 基础
    d.rectangle([16 * u, 80 * u, 28 * u, 88 * u], fill=(70, 90, 100, 255))
    d.rectangle([60 * u, 80 * u, 72 * u, 88 * u], fill=(70, 90, 100, 255))
    # 风箭头（右上朝下压）
    aw = max(2, int(2.6 * u))
    for k in range(3):
        yy = (20 + k * 11)
        x1 = (62 - k * 9) * u
        x2 = (94 - k * 9) * u
        d.line([x1, yy * u, x2, yy * u], fill=WIND, width=aw)
        d.polygon([(x2, yy * u), (x2 - 5 * u, (yy - 3.2) * u), (x2 - 5 * u, (yy + 3.2) * u)], fill=WIND)
    return im


for dpi, S in SIZES.items():
    img = render(S * SS).resize((S, S), Image.LANCZOS)
    out = os.path.join(ROOT, "res", "mipmap-" + dpi, "ic_launcher.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out)
    print("wrote", out, S)
