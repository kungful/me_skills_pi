#!/usr/bin/env python3
"""生成订阅猎手图标：深色底 + 雷达/准星 + 三个节点连线（"猎" 的意象）。"""
import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "res")
SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}

BG = (11, 16, 23, 255)
RING = (61, 220, 151, 255)
RING_SOFT = (61, 220, 151, 110)
ACCENT = (90, 200, 250, 255)
WHITE = (232, 244, 240, 255)


def draw(size, ss=4):
    s = size * ss
    img = Image.new("RGBA", (s, s), BG)
    d = ImageDraw.Draw(img, "RGBA")

    cx = cy = s / 2
    # 外环
    r = s * 0.335
    w = max(1, int(s * 0.030))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=RING, width=w)
    # 内环（虚化）
    r2 = s * 0.205
    d.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], outline=RING_SOFT, width=max(1, int(s * 0.018)))

    # 十字准星（留中心空缺）
    for ang in (0,):
        pass
    tick = s * 0.055
    for (x1, y1, x2, y2) in (
        (cx, cy - r - tick * 0.2, cx, cy - r + tick),
        (cx, cy + r - tick, cx, cy + r + tick * 0.2),
        (cx - r - tick * 0.2, cy, cx - r + tick, cy),
        (cx + r - tick, cy, cx + r + tick * 0.2, cy),
    ):
        d.line([x1, y1, x2, y2], fill=RING, width=max(1, int(s * 0.026)))

    # 三个节点 + 连线（三角）
    pts = [(cx, cy - s * 0.155), (cx - s * 0.150, cy + s * 0.105), (cx + s * 0.150, cy + s * 0.105)]
    for i in range(3):
        a, b = pts[i], pts[(i + 1) % 3]
        d.line([a, b], fill=ACCENT, width=max(1, int(s * 0.020)))
    rr = s * 0.042
    for i, p in enumerate(pts):
        col = WHITE if i == 0 else ACCENT
        d.ellipse([p[0] - rr, p[1] - rr, p[0] + rr, p[1] + rr], fill=col)
    # 中心亮点
    rc = s * 0.030
    d.ellipse([cx - rc, cy - rc, cx + rc, cy + rc], fill=WHITE)

    return img.resize((size, size), Image.LANCZOS)


def main():
    for bucket, px in SIZES.items():
        out = os.path.join(RES, "mipmap-%s" % bucket, "ic_launcher.png")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        draw(px).save(out, "PNG")
        print("icon ->", out)


if __name__ == "__main__":
    main()
