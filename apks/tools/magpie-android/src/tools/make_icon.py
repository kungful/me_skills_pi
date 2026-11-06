#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成 Magpie 的自适应前图标（各 dpi 的 ic_launcher.png）：深色底 + 一只喜鹊剪影。"""
import os
from PIL import Image, ImageDraw

SIZES = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}

BG = (17, 17, 20, 255)
BIRD = (235, 238, 242, 255)
ACCENT = (255, 176, 59, 255)


def draw(size):
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(s * 0.22)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=r, fill=BG)

    # 身体
    d.ellipse([s * 0.26, s * 0.34, s * 0.72, s * 0.72], fill=BIRD)
    # 头
    d.ellipse([s * 0.58, s * 0.24, s * 0.82, s * 0.48], fill=BIRD)
    # 喙
    d.polygon([(s * 0.80, s * 0.33), (s * 0.98, s * 0.37), (s * 0.80, s * 0.42)], fill=ACCENT)
    # 尾巴
    d.polygon([(s * 0.30, s * 0.52), (s * 0.04, s * 0.86), (s * 0.34, s * 0.70)], fill=BIRD)
    # 眼
    er = max(1, int(s * 0.028))
    cx, cy = s * 0.72, s * 0.335
    d.ellipse([cx - er, cy - er, cx + er, cy + er], fill=BG)
    return img


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for dpi, px in SIZES.items():
        out = os.path.join(root, "res", "mipmap-" + dpi)
        os.makedirs(out, exist_ok=True)
        draw(px).save(os.path.join(out, "ic_launcher.png"))
        print("icon ->", os.path.join(out, "ic_launcher.png"), px)


if __name__ == "__main__":
    main()
