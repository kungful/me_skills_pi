# -*- coding: utf-8 -*-
"""把课题的图打包成小红书可发布的纯 ASCII 目录。
  01_cover.jpg  封面（四宫格 + 主题色标题带）1080x1440
  02.jpg        实物对照 1080x1440
  03..07.jpg    范画成品 + 步骤1-4 1536x1024
用法：python _打包.py 课题名 [...]
"""
import hashlib, json, os, sys
from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
UPLOAD = r"C:\Users\hua\tools\xiaohongshu-mcp\upload"
F_TITLE = "C:/Windows/Fonts/STXINGKA.TTF"
F_SUB = "C:/Windows/Fonts/msyh.ttc"
W, H = 1080, 1440
BAND = 300
CREAM = (250, 247, 240)


def stage_dir(topic):
    h = hashlib.md5(("xhs:" + topic).encode("utf-8")).hexdigest()[:8]
    d = os.path.join(UPLOAD, "deck_" + h)
    os.makedirs(d, exist_ok=True)
    return d


def to34(src, dst):
    """方形/任意比例 -> 1080x1440（缩放后居中放在米色底上）"""
    im = Image.open(src).convert("RGB")
    s = min(W / im.width, H / im.height)
    im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    bg = Image.new("RGB", (W, H), CREAM)
    bg.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
    bg.save(dst, quality=92)
    return dst


def cover(src, dst, topic, sub, color):
    im = Image.open(src).convert("RGB")
    im = im.resize((W, W), Image.LANCZOS)
    bg = Image.new("RGB", (W, H), CREAM)
    bg.paste(im, (0, BAND))
    d = ImageDraw.Draw(bg)
    d.rectangle([0, 0, W, BAND], fill=color)
    ft = ImageFont.truetype(F_TITLE, 148)
    fs = ImageFont.truetype(F_SUB, 42)
    txt = topic
    bb = d.textbbox((0, 0), txt, font=ft)
    d.text(((W - (bb[2] - bb[0])) / 2 - bb[0], 34), txt, font=ft, fill=(255, 255, 255))
    bb = d.textbbox((0, 0), sub, font=fs)
    d.text(((W - (bb[2] - bb[0])) / 2 - bb[0], BAND - 74), sub, font=fs,
           fill=(255, 255, 255, 230))
    d.rectangle([0, H - 56, W, H], fill=(255, 255, 255))
    fb = ImageFont.truetype(F_SUB, 32)
    brand = "绘课工坊 · 原创少儿美术课件"
    bb = d.textbbox((0, 0), brand, font=fb)
    d.text(((W - (bb[2] - bb[0])) / 2 - bb[0], H - 46), brand, font=fb, fill=(120, 120, 120))
    bg.save(dst, quality=92)
    return dst


def flat(src, dst, size=(1536, 1024)):
    im = Image.open(src).convert("RGB").resize(size, Image.LANCZOS)
    im.save(dst, quality=92)
    return dst


def _step(img, n):
    """按序号找步骤图（各课题槽位命名不同：起形/勾线/铺色·涂色·涂黑/装饰高光·上色·加深）"""
    import glob
    g = sorted(glob.glob(os.path.join(img, "范画步骤%d_*.png" % n)))
    return g[0] if g else None


def pack(topic):
    d = os.path.join(ROOT, "项目", topic + "-4-6岁")
    pj = json.load(open(os.path.join(d, "project.json"), encoding="utf-8"))
    th = pj["meta"]["theme"]
    color = tuple(int(th["primary"][i:i + 2], 16) for i in (0, 2, 4))
    out = stage_dir(topic)
    a = os.path.join(d, "封面候选", "A_四宫格.png")
    b = os.path.join(d, "封面候选", "B_实物对照.png")
    c = os.path.join(d, "封面候选", "C_桌面实拍.png")
    img = os.path.join(d, "img")
    # 封面选哪张：默认 A；如需改，在 封面候选/_use 里写 A/B/C 任意一个字母
    cands = {"A": a, "B": b, "C": c}
    use = "A"
    mk = os.path.join(d, "封面候选", "_use")
    if os.path.exists(mk):
        use = open(mk, encoding="utf-8").read().strip()[:1].upper() or "A"
    if not os.path.exists(cands.get(use, "")):
        use = "A" if os.path.exists(a) else "B" if os.path.exists(b) else "C"
    # 封面缺失时用范画成品顶替（本地合成带标题封面，不花钱）
    cover_src = cands[use] if os.path.exists(cands.get(use, "")) else os.path.join(img, "范画成品.png")
    has_b = os.path.exists(b) and use != "B"
    need = [cover_src, os.path.join(img, "范画成品.png")] + [_step(img, i) for i in (1, 2, 3, 4)]
    miss = ["?" if x is None else os.path.basename(x) for x in need if not x or not os.path.exists(x)]
    if miss:
        print("[缺图] %s -> %s" % (topic, miss))
        return None
    cover(cover_src, os.path.join(out, "01_cover.jpg"), topic,
          "4-6岁创意美术课件 · 马克笔 · 26页", color)
    cover(cover_src, os.path.join(d, "封面候选", "带标题封面.jpg"), topic,
          "4-6岁创意美术课件 · 马克笔 · 26页", color)
    n = 2
    if has_b:
        to34(b, os.path.join(out, "%02d.jpg" % n)); n += 1
    else:
        print("      （无实物对照图，跳过 02）")
    flat(os.path.join(img, "范画成品.png"), os.path.join(out, "%02d.jpg" % n)); n += 1
    for i in (1, 2, 3, 4):
        flat(_step(img, i), os.path.join(out, "%02d.jpg" % n)); n += 1
    print("[打包] %-16s -> %s  (%d 张)" % (topic, out, n - 1))
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    topics = args or [x for x in sorted(os.listdir(os.path.join(ROOT, "项目")))
                      if x.endswith("-4-6岁")]
    for t in topics:
        t = t.replace("-4-6岁", "")
        pack(t)
