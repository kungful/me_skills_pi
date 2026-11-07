# -*- coding: utf-8 -*-
"""把所有课题的"带标题封面"拼成一张总览图，方便一眼过一遍。"""
import glob, os, sys
from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.abspath(__file__))
F = "C:/Windows/Fonts/msyh.ttc"
W = 300
PAD = 14


def main():
    items = []
    for d in sorted(glob.glob(os.path.join(ROOT, "项目", "*-4-6岁"))):
        p = os.path.join(d, "封面候选", "带标题封面.jpg")
        if not os.path.exists(p):
            p = os.path.join(d, "封面候选", "A_四宫格_带标题.jpg")
        if os.path.exists(p):
            items.append((os.path.basename(d).replace("-4-6岁", ""), p))
    if not items:
        sys.exit("没有封面")
    cols = 5
    rows = (len(items) + cols - 1) // cols
    tw = W * 4 // 3
    th = W
    sheet = Image.new("RGB", (cols * (tw + PAD) + PAD, rows * (th + PAD + 34) + PAD), (250, 248, 245))
    dr = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(F, 22)
    for i, (name, p) in enumerate(items):
        im = Image.open(p).convert("RGB")
        im.thumbnail((tw, th))
        x = PAD + (i % cols) * (tw + PAD) + (tw - im.width) // 2
        y = PAD + (i // cols) * (th + PAD + 34) + (th - im.height) // 2
        sheet.paste(im, (x, y))
        dr.text((PAD + (i % cols) * (tw + PAD), y + th + 2), "%d %s" % (i + 1, name),
                font=f, fill=(30, 30, 30))
    out = os.path.join(ROOT, "_封面总览.jpg")
    sheet.save(out, quality=88)
    print("->", out, sheet.size, "%d 个课题" % len(items))


if __name__ == "__main__":
    main()
