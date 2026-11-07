# -*- coding: utf-8 -*-
"""生成《糖葫芦》课件的商品素材：主图 3:4 + 详情长图 + 上架文案。

产物在 项目/糖葫芦-4-6岁/商品素材/
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')
ROOT = r"C:\Users\hua\Documents\备份代码\小红书卖课件\项目\糖葫芦-4-6岁"
OUT = os.path.join(ROOT, "商品素材")
os.makedirs(OUT, exist_ok=True)

W = 1080
CREAM = (250, 247, 240)
RED = (217, 58, 43)
DARK = (143, 35, 24)
TEXT = (59, 74, 87)
GREY = (120, 120, 120)
WHITE = (255, 255, 255)
FONT = "C:/Windows/Fonts/msyh.ttc"
FONT_BD = "C:/Windows/Fonts/msyhbd.ttc"


def f(size, bold=False):
    return ImageFont.truetype(FONT_BD if bold else FONT, size)


def center(d, y, text, size, color=TEXT, bold=False):
    ft = f(size, bold)
    tw = d.textlength(text, font=ft)
    d.text(((W - tw) / 2, y), text, font=ft, fill=color)


def rounded(d, box, r, fill):
    d.rounded_rectangle(box, radius=r, fill=fill)


def load(p, w, h=None):
    im = Image.open(p).convert("RGB")
    if h is None:
        h = int(im.height * w / im.width)
    return im.resize((w, h), Image.LANCZOS)


def cover_34(p, w, h):
    """等比填满 w x h 后居中裁切"""
    im = Image.open(p).convert("RGB")
    s = max(w / im.width, h / im.height)
    im = im.resize((int(im.width * s + 0.5), int(im.height * s + 0.5)), Image.LANCZOS)
    x = (im.width - w) // 2
    y = (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


COVER = os.path.join(ROOT, "img_sell", "范画成品.jpg")
REAL = os.path.join(ROOT, "img_sell", "实物_糖葫芦.jpg")
SUGAR = os.path.join(ROOT, "img_sell", "素材_糖衣特写.jpg")

# ---------------- 主图 3:4 ----------------
H = 1440
im = Image.new("RGB", (W, H), CREAM)
d = ImageDraw.Draw(im)

rounded(d, (0, 0, W, 196), 0, RED)
center(d, 40, "《糖葫芦》4-6岁", 58, WHITE, True)
center(d, 120, "创意美术课件 · 26页", 40, (255, 235, 225))

art = cover_34(COVER, 960, 720)
im.paste(art, (60, 236))
d.rounded_rectangle((60, 236, 1020, 956), radius=18, outline=(230, 220, 205), width=3)

tags = ["26 页全套", "实物观察", "投屏即上课"]
tw = 280
for i, t in enumerate(tags):
    x = 60 + i * (tw + 20)
    rounded(d, (x, 990, x + tw, 1070), 40, (255, 227, 221))
    ft = f(34, True)
    d.text((x + (tw - d.textlength(t, font=ft)) / 2, 1008), t, font=ft, fill=DARK)

lines = [
    ("从观察 → 范画 5 步 → 成品", 40, TEXT, True),
    ("PPTX + PDF 双交付 · 可编辑 · 可商用", 32, GREY, False),
]
center(d, 1120, lines[0][0], lines[0][1], lines[0][2], lines[0][3])
center(d, 1180, lines[1][0], lines[1][1], lines[1][2], lines[1][3])

rounded(d, (60, 1268, 1020, 1388), 20, WHITE)
center(d, 1292, "绘课工坊 · 原创少儿美术课件", 34, RED, True)
im.save(os.path.join(OUT, "商品主图_3x4.jpg"), quality=94)
print("主图 OK")

# ---------------- 详情长图 ----------------
seg = []
# 1 头图
seg.append(im.resize((W, int(H * 1.0)), Image.LANCZOS))

pad = 48
# 2 卖点
blk = Image.new("RGB", (W, 460), WHITE)
bd = ImageDraw.Draw(blk)
center(bd, 42, "这套课件解决什么问题", 44, DARK, True)
pts = [
    "① 26 页排好版，投屏就能讲，不用自己拼图排版",
    "② 实物观察页用真实糖葫芦，孩子有东西可看",
    "③ 范画 5 步拆解，4-6 岁照着画也能画出来",
    "④ PPTX 可改字改图，PDF 直接发给家长",
]
for i, t in enumerate(pts):
    bd.text((90, 130 + i * 74), t, font=f(32), fill=TEXT)
seg.append(blk)

# 3 页面缩略图 2x2
prev = [
    ("out/preview/08.png", "实物观察"),
    ("out/preview/20.png", "范画步骤"),
    ("out/preview/14.png", "色彩知识"),
    ("out/preview/25.png", "成品展示"),
]
blk2 = Image.new("RGB", (W, 1000), CREAM)
bd2 = ImageDraw.Draw(blk2)
center(bd2, 30, "内含页面（共 26 页）", 44, DARK, True)
tw2, th2 = 470, 264
for i, (rel, label) in enumerate(prev):
    x = 40 + (i % 2) * (tw2 + 60)
    y = 120 + (i // 2) * (th2 + 120)
    thumb = load(os.path.join(ROOT, rel), tw2, th2)
    blk2.paste(thumb, (x, y))
    bd2.rectangle((x, y, x + tw2, y + th2), outline=(225, 215, 200), width=2)
    ft = f(28, True)
    bd2.text((x + (tw2 - bd2.textlength(label, font=ft)) / 2, y + th2 + 18), label, font=ft, fill=GREY)
seg.append(blk2)

# 4 交付说明
blk3 = Image.new("RGB", (W, 620), WHITE)
bd3 = ImageDraw.Draw(blk3)
center(bd3, 40, "你会收到", 44, DARK, True)
items = [
    ("①", "《糖葫芦》26 页 PPTX 源文件（可编辑）"),
    ("②", "同名 PDF（直接投屏 / 发家长）"),
    ("③", "16 张高清配图（可单独做海报）"),
    ("④", "课程目标 + 重难点 + 课后总结，文案已写好"),
]
for i, (n, t) in enumerate(items):
    bd3.text((90, 140 + i * 88), n + "  " + t, font=f(32), fill=TEXT)
center(bd3, 520, "拍下后发网盘链接 · 虚拟商品不退不换", 26, GREY)
seg.append(blk3)

# 5 底部
blk4 = Image.new("RGB", (W, 240), RED)
bd4 = ImageDraw.Draw(blk4)
center(bd4, 50, "绘课工坊", 52, WHITE, True)
center(bd4, 130, "少儿美术课件 · 一节课一套 · 拿来就能上", 30, (255, 235, 225))
seg.append(blk4)

total = sum(s.height for s in seg)
long = Image.new("RGB", (W, total), CREAM)
y = 0
for s in seg:
    long.paste(s, (0, y))
    y += s.height
long.save(os.path.join(OUT, "商品详情长图.jpg"), quality=92)
print("详情图 OK", long.size)
