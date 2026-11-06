# -*- coding: utf-8 -*-
"""水印 + 原图备份 + 版权存证（防白嫖）。

为什么要它：
  · 课件成品图发到小红书/商品页，不放水印就是给同行送素材；
  · 原图必须留档（md5 + 尺寸 + 时间），被盗用/被反咬时手里有东西；
  · 水印要覆盖全图，裁边也裁不掉；但不能重到影响点击率。

用法（一般由 prep_post.py 调用）：
    from watermark import mark_file, backup_originals
    backup_originals(project_dir, [(slot, src), ...], deck="《糖葫芦》4-6岁课件", brand="绘课工坊")
    mark_file("01_cover.jpg", "绘课工坊 · 原创课件", wm_id="49788519703")
"""
import hashlib
import json
import os
import time

from PIL import Image, ImageDraw, ImageFont

FONT_BD = "C:/Windows/Fonts/msyhbd.ttc"
FONT_RG = "C:/Windows/Fonts/msyh.ttc"


def _font(size, bold=True):
    for p in ((FONT_BD, FONT_RG) if bold else (FONT_RG, FONT_BD)):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _md5(p, chunk=1 << 20):
    h = hashlib.md5()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def tile(im, text, opacity=0.10, size=None, angle=-30):
    """全图平铺半透明文字（旋转 -30°），裁边也裁不掉。"""
    if not text:
        return im
    W, H = im.size
    fs = size or max(20, int(W * 0.032))
    font = _font(fs)
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = int(probe.textlength(text, font=font))
    gap_x = max(tw + int(fs * 2.2), int(W * 0.30))
    gap_y = max(int(fs * 4.2), int(H * 0.12))

    layer = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    a = int(255 * max(0.0, min(0.6, opacity)))
    for y in range(-gap_y, H * 2, gap_y):
        for x in range(-gap_x, W * 2, gap_x):
            d.text((x, y), text, font=font,
                   fill=(255, 255, 255, a),
                   stroke_width=1, stroke_fill=(0, 0, 0, int(a * 0.55)))
    layer = layer.rotate(angle, resample=Image.BICUBIC)
    left = (W * 2 - W) // 2
    top = (H * 2 - H) // 2
    layer = layer.crop((left, top, left + W, top + H))
    base = im.convert("RGBA")
    base.alpha_composite(layer)
    return base.convert("RGB")


def corner(im, text, sub=None):
    """右下角品牌条：清晰、不可裁（发布图是完整图，不裁切）。"""
    if not text:
        return im
    W, H = im.size
    fs = max(18, int(W * 0.021))
    font = _font(fs, True)
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = int(probe.textlength(text, font=font))
    if sub:
        fs2 = max(14, int(fs * 0.78))
        f2 = _font(fs2, False)
        tw2 = int(probe.textlength(sub, font=f2))
    else:
        f2 = None
        tw2 = 0
    pad = int(fs * 0.75)
    bw = max(tw, tw2) + pad * 2
    bh = fs + (fs2 + 6 if sub else 0) + pad * 2
    x = W - bw - int(W * 0.018)
    y = H - bh - int(H * 0.014)
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((x, y, x + bw, y + bh), radius=bh // 3, fill=(0, 0, 0, 96))
    d.text((x + pad, y + pad - 2), text, font=font, fill=(255, 255, 255, 238))
    if f2:
        d.text((x + pad, y + pad + fs + 4), sub, font=f2, fill=(255, 255, 255, 190))
    base = im.convert("RGBA")
    base.alpha_composite(layer)
    return base.convert("RGB")


def mark_image(im, main_text, sub_text=None, opacity=0.10, size=None):
    im = tile(im, main_text, opacity=opacity, size=size)
    return corner(im, main_text, sub_text)


def mark_file(path, main_text, sub_text=None, opacity=0.10, size=None, quality=92):
    im = Image.open(path).convert("RGB")
    out = mark_image(im, main_text, sub_text, opacity=opacity, size=size)
    out.save(path, quality=quality, subsampling=0)
    return out.size


def backup_originals(project_dir, items, deck="", brand="", extra=None):
    """把本次用到的原图复制到 <项目>/img_orig/，并写 manifest。

    items: [(slot, abs_path), ...]
    返回 manifest 路径；重复的 md5 不会重复复制。
    """
    outdir = os.path.join(project_dir, "img_orig")
    os.makedirs(outdir, exist_ok=True)
    man_path = os.path.join(outdir, "manifest.json")
    if os.path.exists(man_path):
        try:
            with open(man_path, encoding="utf-8") as f:
                man = json.load(f)
        except Exception:
            man = {}
    else:
        man = {}
    man.setdefault("deck", deck)
    man.setdefault("brand", brand)
    man.setdefault("created_at", time.strftime("%Y-%m-%dT%H:%M:%S"))
    man.setdefault("images", {})
    if extra:
        man.update(extra)

    for slot, src in items:
        if not src or not os.path.exists(src):
            continue
        h = _md5(src)
        ext = os.path.splitext(src)[1].lower() or ".jpg"
        dst = os.path.join(outdir, slot + ext)
        if not os.path.exists(dst) or _md5(dst) != h:
            with open(src, "rb") as fi, open(dst, "wb") as fo:
                fo.write(fi.read())
        try:
            with Image.open(dst) as im:
                wh = list(im.size)
        except Exception:
            wh = []
        man["images"][slot] = {
            "file": "img_orig/" + os.path.basename(dst),
            "md5": h,
            "size": wh,
            "bytes": os.path.getsize(dst),
            "src_mtime": time.strftime("%Y-%m-%dT%H:%M:%S",
                                       time.localtime(os.path.getmtime(src))),
        }
    man["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(man_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    return man_path


def add_publish_record(project_dir, note_id, title, image_md5, when=None):
    """把一次发布登记进存证 manifest（证明这组图何时发过）。"""
    man_path = os.path.join(project_dir, "img_orig", "manifest.json")
    if not os.path.exists(man_path):
        return None
    with open(man_path, encoding="utf-8") as f:
        man = json.load(f)
    man.setdefault("published", []).append({
        "note_id": note_id,
        "title": title,
        "at": when or time.strftime("%Y-%m-%dT%H:%M:%S"),
        "image_md5": list(image_md5),
    })
    with open(man_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    return man_path
