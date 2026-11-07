# -*- coding: utf-8 -*-
"""新角度笔记生成器（零出图成本）
复用已生成但**从未发布过**的图（姿态素材/实物图），做成与旧笔记完全不同的内容角度。
用法：python _新角度.py <recipe名>
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.expanduser("~/.pi/agent/skills/xhs-courseware-post/scripts"))
from PIL import Image  # noqa: E402
import prep_post as PP  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
STAGE_ROOT = r"C:\Users\hua\tools\xiaohongshu-mcp\upload"

# ======== 配方：每个课题只用「旧笔记没用过」的图 ========
RECIPES = {
    "小象洗澡_姿态参考": dict(
        topic="小象洗澡",
        cover="范画成品",
        slots=["素材_坐姿", "素材_趴着", "素材_用鼻子", "素材_洗澡", "素材_池塘", "素材_河马"],
        cover_tail="小象6个动态参考",
        title="4-6岁创意美术｜小象6个姿态参考",
        tags=["少儿美术", "创意美术", "美术课件", "美术老师", "幼儿美术",
              "4到6岁", "备课素材", "美术教案", "美术机构", "课件分享"],
        content="""上《小象洗澡》这节创意美术课，最卡的一步不是配色，是孩子不知道大象的动作怎么画。

我把课上要用的 6 个动态参考整理出来了，可以直接投屏或打印：

🐘 坐姿——三条腿的折叠关系
🐘 趴着——肚子压在地上的形
🐘 用鼻子——鼻子卷起来的弧线
🐘 洗澡——喷水那一下的动势
🐘 池塘——脚踩在水里的位置
🐘 河马——同框时的体量对比

抓形的小窍门：大象身体按「头 : 身 : 腿 ≈ 1 : 2 : 1」去分块，先定三个大块再抠细节，孩子照着画不容易跑偏。

配色建议：灰蓝身体 + 暖橙背景，留白做水花。

#少儿美术 #创意美术 #美术课件 #美术老师 #幼儿美术 #备课素材""",
    ),
    "小松鼠藏松果_姿态参考": dict(
        topic="小松鼠藏松果",
        cover="范画成品",
        slots=["素材_吃松果", "素材_坐姿", "素材_藏松果", "素材_跳树", "素材_松树林", "素材_小老鼠"],
        cover_tail="小松鼠6个动态参考",
        title="4-6岁创意美术｜小松鼠6个动态",
        tags=["少儿美术", "创意美术", "美术课件", "美术老师", "幼儿美术",
              "4到6岁", "备课素材", "美术教案", "美术机构", "课件分享"],
        content="""画小松鼠，孩子最容易翻车的不是身体，是那条比自己还高的火尾巴。

我把课上要用的 6 个动态参考整理出来了，可以直接投屏或打印：

🐿 吃松果——两只前爪抱住的姿势
🐿 坐姿——尾巴从身后绕上头顶的弧线
🐿 藏松果——低头埋东西的形
🐿 跳树——跃起那一瞬间的伸展
🐿 松树林——同框中树干的粗细关系
🐿 小老鼠——容易和小松鼠弄混的对比图

尾巴的小诀窍：先画一条从屁股到头顶的大弧线定长度，再往内加一层层蓬松的短线，尾巴就不会画成一根棍子。

配色建议：红棕身体 + 奶油色肚皮，背景低饱和黄绿，尾巴尖压一点深咖啡。

#少儿美术 #创意美术 #美术课件 #美术老师 #幼儿美术 #备课素材""",
    ),
}


F_TITLE = "C:/Windows/Fonts/msyhbd.ttc"
GREEN = (119, 166, 90)
ORANGE = (249, 166, 5)
INK = (53, 66, 83)
CREAM = (250, 247, 240)


def poster_cover(src, dst, big, small, w=1080, h=1440):
    """海报式封面：图铺满上半部，下半部色块 + 大字标题。"""
    from PIL import ImageDraw, ImageFont
    im = Image.open(src).convert("RGB")
    # 图缩到满宽，顶部对齐
    iw = w
    ih = int(round(im.height * (iw / im.width)))
    im = im.resize((iw, ih), Image.LANCZOS)
    canvas = Image.new("RGB", (w, h), CREAM)
    if ih > h:                      # 图太高就裁
        im = im.crop((0, 0, w, h))
        canvas.paste(im, (0, 0))
    else:
        canvas.paste(im, (0, 0))
        band_y = ih
        ImageDraw.Draw(canvas).rectangle((0, band_y, w, h), fill=GREEN)
        d = ImageDraw.Draw(canvas)
        # 大字
        band_h = h - band_y
        f1 = ImageFont.truetype(F_TITLE, 120)
        f2 = ImageFont.truetype(F_TITLE, 58)
        gap = 40
        block = 120 + gap + 58
        top = band_y + max(60, (band_h - block) // 2)
        bb = d.textbbox((0, 0), big, font=f1)
        d.text(((w - (bb[2] - bb[0])) / 2 - bb[0], top), big, font=f1, fill=(255, 255, 255))
        bb2 = d.textbbox((0, 0), small, font=f2)
        d.text(((w - (bb2[2] - bb2[0])) / 2 - bb2[0], top + 120 + gap), small, font=f2, fill=ORANGE)
    canvas.save(dst, quality=93)
    return canvas.size


def img_path(topic, slot):
    d = os.path.join(ROOT, "项目", topic + "-4-6岁")
    for p in (os.path.join(d, "img_sell", slot + ".jpg"), os.path.join(d, "img", slot + ".png")):
        if os.path.exists(p):
            return p
    return None


def stage_dir(key):
    h = hashlib.md5(("xhs:" + key).encode("utf-8")).hexdigest()[:8]
    d = os.path.join(STAGE_ROOT, "deck_" + h)
    os.makedirs(d, exist_ok=True)
    return d


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "小象洗澡_姿态参考"
    r = RECIPES[key]
    topic = r["topic"]

    # 1) 校验图都在
    miss = [s for s in [r["cover"]] + r["slots"] if not img_path(topic, s)]
    if miss:
        print("✗ 缺图:", miss)
        return 1

    # 2) 转存到纯 ASCII 目录
    sd = stage_dir(key)
    picked, dsts = [], []
    # 封面：成品补成 3:4
    cv = os.path.join(sd, "01_cover.jpg")
    big = topic
    small = r.get("cover_tail", "")
    sz = poster_cover(img_path(topic, r["cover"]), cv, big, small)
    dsts.append(cv)
    picked.append(r["cover"])
    print("封面(海报式)", r["cover"], "->", sz, "|", big, "/", small)
    # 内容图
    for i, s in enumerate(r["slots"], start=2):
        dst = os.path.join(sd, "%02d.jpg" % i)
        sz = PP.save_plain(img_path(topic, s), dst)
        dsts.append(dst)
        picked.append(s)
        print("  %02d %s %s" % (i, s, sz))

    # 3) 字数校验（镜像服务端算法）
    n = PP.title_len(r["title"]) if hasattr(PP, "title_len") else len(r["title"])
    print("标题: %s (%s 字)" % (r["title"], n))

    # 4) 写 post.json
    post = dict(
        project=os.path.join(ROOT, "项目", topic + "-4-6岁", "project.json"),
        name=r.get("name", key),
        age="4-6岁",
        brand="绘课工坊",
        title=r["title"],
        title_alt=[],
        content=r["content"],
        tags=r["tags"],
        images=dsts,
        visibility="仅自己可见",
        _prep={"slots": picked, "kind": "新角度/" + key},
    )
    out = os.path.join(ROOT, "项目", topic + "-4-6岁", "post_新角度.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(post, f, ensure_ascii=False, indent=2)
    print("草稿 ->", out)
    print("图片 %d 张 | 正文 %d 字 | 标签 %d 个" % (len(dsts), len(r["content"]), len(r["tags"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
