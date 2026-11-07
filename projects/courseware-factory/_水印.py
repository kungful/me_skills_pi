# -*- coding: utf-8 -*-
"""绘课工坊 · 图片水印工具

用途：发布用图打水印防白嫖，同时保留无水印原图在本地。

设计原则
1. 永不改动原图：只读 src，写出到 dst。
2. 两套产物分开存：
     原图无水印/  ← 干净版，本地备份、自己复用、卖课件交付
     发布带水印/  ← 上传小红书用
3. 水印分三层，肉眼不挡内容但截图裁切都不好使：
     - 斜向平铺半透明文字（主防线，裁掉一角也没用）
     - 右下角品牌 + 小红书号（识别来源）
     - 底部极淡通栏（防止只截上半部分）

命令行
    python _水印.py <源目录或单图> [--out 输出目录]
    python _水印.py 项目/人怎么画-4-6岁/原图无水印
"""
import os
import sys
import glob
import argparse

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BRAND = "绘课工坊"
XHS_ID = "小红书 49788519703"
FONT = "C:/Windows/Fonts/msyh.ttc"
FONT_BD = "C:/Windows/Fonts/msyhbd.ttc"

INK = (58, 70, 82)
DGREEN = (74, 110, 55)


def font(size, bold=False):
    return ImageFont.truetype(FONT_BD if bold else FONT, size)


def _tile_watermark(base, text, size, alpha, angle=28, gap_x=None, gap_y=None, offset=False):
    """斜向平铺：画在一张透明大图上旋转后贴回，避免逐字旋转的锯齿。"""
    w, h = base.size
    ft = font(size, bold=True)
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    tw = int(probe.textlength(text, font=ft))
    # 密集平铺：横向 1.5 倍字宽、纵向 3.2 倍字号
    gap_x = gap_x or int(tw * 1.5)
    gap_y = gap_y or int(size * 3.2)

    # 旋转后需要更大的画布才能铺满
    diag = int((w ** 2 + h ** 2) ** 0.5) + 2 * size
    layer = Image.new("RGBA", (diag, diag), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    y = 0
    row = 0
    # 深绿字 + 白描边：浅底靠字显形，深底靠描边显形，两头都能看见
    fill_c = (74, 110, 55, alpha)
    stroke_c = (255, 255, 255, max(24, alpha // 2))
    start_x = int(gap_x * 0.5) if offset else 0
    while y < diag:
        x = start_x - gap_x if row % 2 else start_x
        while x < diag:
            d.text((x, y), text, font=ft, fill=fill_c,
                   stroke_width=1, stroke_fill=stroke_c)
            x += gap_x
        y += gap_y
        row += 1

    layer = layer.rotate(angle, resample=Image.BICUBIC, expand=False)
    left = (diag - w) // 2
    top = (diag - h) // 2
    layer = layer.crop((left, top, left + w, top + h))
    base.alpha_composite(layer)


def add_watermark(src, dst, brand=BRAND, xhs_id=XHS_ID):
    im = Image.open(src).convert("RGB")
    w, h = im.size

    # 水印字号随图缩放，1080 宽对应 46px
    unit = w / 1080.0
    base = im.convert("RGBA")

    # --- 第一层：正向斜铺（主防线，密但淡）---
    usz = max(18, int(46 * unit))
    _tile_watermark(base, brand, usz, alpha=42, angle=26)

    # --- 第二层：反向斜铺，错位叠加 ---
    # 两层交叉后，抹掉哪一层都还剩另一层，残留纹理也接不上
    _tile_watermark(base, brand, usz, alpha=30, angle=-26, offset=True)

    d = ImageDraw.Draw(base)

    # --- 第三层：底部横向连续条（半透明，只压底部，防止只截上半部分）---
    # 右侧留出小红书号的位置，避免两层文字撞在一起
    fs3 = font(max(13, int(24 * unit)), bold=True)
    fs = font(max(12, int(22 * unit)))
    tag = xhs_id
    reserve = int(d.textlength(tag, font=fs)) + int(56 * unit)
    ly = h - int(40 * unit)
    lx = int(16 * unit)
    unit_txt = brand + "  ·  "
    step = int(d.textlength(unit_txt, font=fs3))
    while lx < w - reserve:
        d.text((lx, ly), unit_txt, font=fs3, fill=(255, 255, 255, 96),
               stroke_width=1, stroke_fill=(74, 110, 55, 72))
        lx += step

    # --- 第四层：右上角品牌标识（半透明底牌；放右边是为了不压住左上角的阶段标）---
    ft = font(max(16, int(30 * unit)), bold=True)
    pad = int(22 * unit)
    tw = d.textlength(brand, font=ft)
    bx2 = w - pad - int(26 * unit)
    box = [bx2 - tw, pad, bx2, pad + int(54 * unit)]
    d.rounded_rectangle(box, radius=int(10 * unit), fill=(255, 255, 255, 140),
                        outline=(74, 110, 55, 150), width=2)
    d.text((bx2 - tw + int(13 * unit), pad + int(11 * unit)), brand, font=ft,
           fill=(74, 110, 55, 235))

    # --- 第五层：右下角小红书号（半透明，与底部连续条同一行）---
    tw2 = d.textlength(tag, font=fs)
    x2 = w - tw2 - int(20 * unit)
    y2 = h - int(34 * unit)
    d.text((x2, y2), tag, font=fs, fill=(255, 255, 255, 160),
           stroke_width=1, stroke_fill=(58, 70, 82, 135))

    out = base.convert("RGB")
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    out.save(dst, quality=92, subsampling=1)
    return dst


def collect(src):
    if os.path.isdir(src):
        exts = ("*.jpg", "*.jpeg", "*.png", "*.webp")
        files = []
        for e in exts:
            files += glob.glob(os.path.join(src, e))
        return sorted(files)
    return [src]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="源目录或单张图片")
    ap.add_argument("--out", help="输出目录（默认：源目录同级 发布带水印/）")
    ap.add_argument("--suffix", default="", help="输出文件名后缀")
    a = ap.parse_args()

    files = collect(a.src)
    if not files:
        print("没有找到图片:", a.src)
        return 1

    if a.out:
        outdir = a.out
    elif os.path.isdir(a.src):
        outdir = os.path.join(os.path.dirname(os.path.abspath(a.src)), "发布带水印")
    else:
        outdir = os.path.join(os.path.dirname(os.path.abspath(a.src)), "发布带水印")
    os.makedirs(outdir, exist_ok=True)

    for p in files:
        stem = os.path.splitext(os.path.basename(p))[0]
        dst = os.path.join(outdir, stem + a.suffix + ".jpg")
        add_watermark(p, dst)
        print("  %-28s -> %s" % (os.path.basename(p), dst))

    print("\n共 %d 张，输出目录: %s" % (len(files), outdir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
