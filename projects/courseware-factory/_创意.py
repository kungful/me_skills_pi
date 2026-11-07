# -*- coding: utf-8 -*-
"""创意内容生成器（零出图成本，只做图片合成）
形式A：N步画法网格封面  —— 成品 + 步骤，拼成信息量最大的封面
形式B：主题课单六宫格封面 —— 6 套成品拼成课单
用法：python _创意.py <recipe名>
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.expanduser("~/.pi/agent/skills/xhs-courseware-post/scripts"))
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
import prep_post as PP  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
STAGE_ROOT = r"C:\Users\hua\tools\xiaohongshu-mcp\upload"

F = "C:/Windows/Fonts/msyhbd.ttc"
GREEN = (119, 166, 90)
ORANGE = (249, 166, 5)
CREAM = (250, 247, 240)
WHITE = (255, 255, 255)
INK = (60, 70, 80)
GRAY = (232, 231, 226)


def autofit(im, bw, bh):
    r = min(bw / im.width, bh / im.height)
    return im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)


def grid_cover(items, dst, title, sub, cols, rows, header=210, lab_h=62):
    """items: [(图片路径, 标签)]，拼成 3:4 网格封面。"""
    W, H = 1080, 1440
    cv = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(cv)
    d.rectangle((0, 0, W, header), fill=GREEN)
    f1 = ImageFont.truetype(F, 88 if len(title) <= 12 else 74)
    b = d.textbbox((0, 0), title, font=f1)
    d.text(((W - (b[2] - b[0])) / 2 - b[0], 26), title, font=f1, fill=WHITE)
    f2 = ImageFont.truetype(F, 46)
    b2 = d.textbbox((0, 0), sub, font=f2)
    d.text(((W - (b2[2] - b2[0])) / 2 - b2[0], header - 74), sub, font=f2, fill=ORANGE)

    gw = W // cols
    gh = (H - header) // rows
    fl = ImageFont.truetype(F, 38)
    for i, (p, lab) in enumerate(items):
        r, c = divmod(i, cols)
        x0, y0 = c * gw, header + r * gh
        d.rectangle((x0 + 8, y0 + 8, x0 + gw - 8, y0 + gh - 8), fill=WHITE)   # 白卡片
        im = autofit(Image.open(p).convert("RGB"), gw - 40, gh - lab_h - 32)
        cv.paste(im, (x0 + (gw - im.width) // 2, y0 + 16 + (gh - lab_h - 32 - im.height) // 2))
        bt = d.textbbox((0, 0), lab, font=fl)
        d.text((x0 + (gw - (bt[2] - bt[0])) / 2 - bt[0], y0 + gh - lab_h), lab, font=fl, fill=INK)
        d.rectangle((x0 + 8, y0 + 8, x0 + gw - 8, y0 + gh - 8), outline=GRAY, width=3)
    cv.save(dst, quality=93)
    return cv.size


def step_items(topic, steps):
    d = os.path.join(ROOT, "项目", topic + "-4-6岁", "img")
    items = [(os.path.join(d, "范画成品.png"), "成品")]
    for i, s in enumerate(steps, start=1):
        items.append((os.path.join(d, s[0]), "%s%s" % ("①②③④⑤⑥⑦"[i - 1], s[1])))
    return items


def cat_courses(courses, d, out):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    r = autofit(Image.open(os.path.join(d, "范画成品.png")).convert("RGB"), 1080, 1440)
    cv = Image.new("RGB", (1080, 1440), CREAM)
    cv.paste(r, ((1080 - r.width) // 2, (1440 - r.height) // 2))
    cv.save(out, quality=92)
    return cv.size


def stage(key):
    h = hashlib.md5(("xhs:" + key).encode("utf-8")).hexdigest()[:8]
    p = os.path.join(STAGE_ROOT, "deck_" + h)
    os.makedirs(p, exist_ok=True)
    return p


# ================= 配方 =================
STEPS_YEZI = [("范画步骤1_起形.png", "起形"), ("范画步骤2_勾线.png", "勾线"),
              ("范画步骤3_铺色.png", "铺色"), ("范画步骤4_装饰高光.png", "装饰"),
              ("范画步骤5_加背景.png", "背景")]

# 新题材统一用这套步骤名
STEPS_STD = [("范画步骤1_起形.png", "起形"), ("范画步骤2_勾线.png", "勾线"),
             ("范画步骤3_涂色.png", "涂色"), ("范画步骤4_加深.png", "加深"),
             ("范画步骤5_加背景.png", "背景")]

RECIPES = {
    "树叶5步画法": dict(
        kind="A", topic="树叶逃跑啦",
        title="5步画出逃跑的树叶｜4-6岁",
        cover_title="树叶逃跑啦", cover_sub="成品 + 5 步画法",
        steps=STEPS_YEZI,
        content="""一片叶子，怎么会"逃跑"？这是《树叶逃跑啦》这节创意美术课的题眼。

5 步拆给你看：

① 起形——先定一片大叶子，别画正，稍微倾斜才像在飞
② 勾线——主脉要粗、支脉要细，叶子的"骨头"立起来
③ 铺色——从深到浅，秋天的颜色不要调匀，越"脏"越像真叶子
④ 装饰——叶尖点一点橘黄，边缘留一圈亮线
⑤ 背景——用打圈的方式画风，叶子就"跑"起来了

老师提示：孩子最容易把叶子画成对称的"船"，提醒他"叶子是被风吹歪的"，一下就活了。

4-6岁都能画出来，投屏就能上。

#少儿美术 #创意美术 #美术课件 #美术老师 #幼儿美术""",
    ),
    "秋冬6节课课单": dict(
        kind="B",
        title="4-6岁｜秋冬6节课主题课单",
        cover_title="秋冬 6 节课", cover_sub="4-6岁创意美术 · 主题课单",
        courses=["树叶逃跑啦", "把秋天装进罐子", "棉签点彩大树",
                 "落叶小画布", "冬日黄昏", "撒盐画雪花"],
        content="""幼儿园秋冬这一季，用这 6 节课刚好排满——从落叶到初雪，材料一次备齐。

🍂 树叶逃跑啦 —— 借形想象，一片叶子怎么"跑"
🍂 把秋天装进罐子 —— 前后遮挡，练习"装"的空间感
🍂 棉签点彩大树 —— 点彩法，练耐心和色彩的深浅
🍂 落叶小画布 —— 落叶拼贴 + 添画，材料最省的一节
🍂 冬日黄昏 —— 冷暖对比，橙红天空配蓝紫雪地
❄️ 撒盐画雪花 —— 撒盐肌理，孩子最兴奋的一节

每节都是 4-6 岁可以独立完成、一节课出作品的难度。
材料以水粉、油画棒、落叶、盐、棉签为主，家里和画室都能做。

#少儿美术 #创意美术 #美术课件 #美术老师 #幼儿美术 #秋冬主题""",
    ),
    # ============ 新题材（2026-10-16 新出图）============
    "万圣节南瓜灯": dict(
        kind="A", topic="万圣节南瓜灯", steps=STEPS_STD,
        title="4-6岁创意美术｜万圣节南瓜灯",
        cover_title="万圣节南瓜灯", cover_sub="成品 + 5 步画法",
        content="""万圣节这节课，孩子一进教室就兴奋——因为南瓜灯会"发光"。

6 步拆给你看：

① 起形——一个大圆定南瓜，别画圆，压扁一点更像真南瓜
② 勾线——加上南瓜棱和顶上的藤，眼睛两个三角形，嘴巴画锯齿
③ 涂色——南瓜铺橘色，草地铺绿色，天空先留白
④ 加深——南瓜右侧压一层深橘，体积感立刻出来
⑤ 背景——深蓝夜空 + 弯月 + 星星 + 两只小幽灵

老师提示：眼睛和嘴巴里的暖黄色一定要"亮"，跟深蓝夜空一比，发光的感觉马上就对了。孩子最爱画的就是这一步。

4-6岁都能独立完成，一节课出作品。万圣节前上正合适。

#少儿美术 #创意美术 #美术课件 #美术老师 #幼儿美术 #万圣节""",
    ),
    "会变形的云": dict(
        kind="A", topic="会变形的云", steps=STEPS_STD,
        title="4-6岁创意美术｜会变形的云",
        cover_title="会变形的云", cover_sub="成品 + 5 步画法",
        content="""这节课不教画得像，教孩子"敢想"。

一朵云，可以变成什么？小兔子？小船？冰淇淋？

6 步画《会变形的云》：

① 起形——先画一朵大大的云，就画在画面中间
② 勾线——给云加两只长耳朵和一条小尾巴，它就成了兔子
③ 涂色——草地铺绿色，云留白（云本来就是白的）
④ 加深——云的下面压一层浅灰蓝，云就"胖"起来了
⑤ 背景——天空铺天蓝色，加上太阳和两朵小云

老师提示：
· 先让孩子说"这朵云像什么"，再动笔。想象画最怕直接给答案
· 云不要画成一条线，要用一圈一圈的弧线堆出来，才有蓬松感

4-6岁最好上的一节想象力课。

#少儿美术 #创意美术 #美术课件 #美术老师 #幼儿美术 #想象力""",
    ),
    # ============ 第二批（2026-10-17）============
    "堆雪人": dict(
        kind="A", topic="堆雪人", steps=STEPS_STD,
        title="4-6岁创意美术｜堆雪人",
        cover_title="堆雪人", cover_sub="成品 + 5 步画法",
        content="""冬天第一节美术课，就上《堆雪人》——孩子对雪人有天然的亲切感。

6 步拆给你看：

① 起形——两个圆定雪人，下面大上面小，先把大小定下来再画细节
② 勾线——围巾、帽子、树枝手臂、三颗小纽扣，一次勾完
③ 涂色——帽子围巾涂红，胡萝卜鼻子涂橙，小松树涂绿，雪人留白
④ 加深——雪球左侧压一层浅蓝灰，雪人立刻"鼓"起来了（这步最关键）
⑤ 背景——天空铺淡蓝，雪地留白，撒上小雪花点点

老师提示：
· 雪人是白的，孩子会不知道往哪涂色——告诉他"白的地方不涂，只涂影子"，一下就懂
· 雪花不要画太大，小点点撒开才像下雪

4-6岁都能独立完成，材料只要马克笔和纸。

#少儿美术 #创意美术 #美术课件 #美术老师 #幼儿美术 #冬天主题""",
    ),
    "小刺猬背果子": dict(
        kind="A", topic="小刺猬背果子", steps=STEPS_STD,
        title="4-6岁创意美术｜小刺猬背果子",
        cover_title="小刺猬背果子", cover_sub="成品 + 5 步画法",
        content="""秋天的课，孩子最喜欢这只"背着果子的小刺猬"。

6 步拆给你看：

① 起形——一个大半圆是身体，左边加个尖尖的鼻子
② 勾线——背上画一排排小三角当刺，果子先画成圆
③ 涂色——脸涂奶油色，刺涂棕色，苹果涂红色
④ 加深——刺的下面压深棕，苹果右侧压深红
⑤ 背景——草地、落叶、一朵红蘑菇

老师提示：
· 刺不要画成"板栗"，要一排一排往斜后方倒，才有那种毛扎扎的感觉
· 先画刺再放果子，果子是"插"上去的，顺序反了会乱

4-6岁都能画出来，材料只要马克笔和纸。

#少儿美术 #创意美术 #美术课件 #美术老师 #幼儿美术 #秋天主题""",
    ),
}


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else list(RECIPES)[0]
    r = RECIPES[key]
    sd = stage(key)
    dsts = []

    if r["kind"] == "A":
        items = step_items(r["topic"], r["steps"])
        miss = [p for p, _ in items if not os.path.exists(p)]
        if miss:
            print("✗ 缺图:", miss)
            return 1
        cvp = os.path.join(sd, "01_cover.jpg")
        print("封面(网格)", grid_cover(items, cvp, r["cover_title"], r["cover_sub"], 2, 3), r["cover_title"])
        dsts.append(cvp)
        # 内容：成品 + 各步骤大图
        for i, (p, lab) in enumerate(items, start=2):
            dst = os.path.join(sd, "%02d.jpg" % i)
            print("  %02d %s %s" % (i, lab, PP.save_plain(p, dst)))
            dsts.append(dst)
    else:
        items = []
        for c in r["courses"]:
            p = os.path.join(ROOT, "项目", c + "-4-6岁", "img", "范画成品.png")
            if not os.path.exists(p):
                print("✗ 缺图:", p)
                return 1
            items.append((p, c))
        cvp = os.path.join(sd, "01_cover.jpg")
        print("封面(六宫格)", grid_cover(items, cvp, r["cover_title"], r["cover_sub"], 2, 3), r["cover_title"])
        dsts.append(cvp)
        for i, (p, c) in enumerate(items, start=2):
            dst = os.path.join(sd, "%02d.jpg" % i)
            print("  %02d %s %s" % (i, c, PP.save_plain(p, dst)))
            dsts.append(dst)

    post = dict(
        project=os.path.join(ROOT, "项目", (r.get("topic") or "合集") + ".json"),
        name=key, age="4-6岁", brand="绘课工坊",
        title=r["title"], title_alt=[], content=r["content"],
        tags=["少儿美术", "创意美术", "美术课件", "美术老师", "幼儿美术",
              "4到6岁", "备课素材", "美术教案", "美术机构", "课件分享"],
        images=dsts, visibility="仅自己可见",
        _prep={"kind": "创意/" + key, "slots": [os.path.basename(p) for p in dsts]},
    )
    out = os.path.join(ROOT, "创意内容", key + ".json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(post, f, ensure_ascii=False, indent=2)
    print("草稿 ->", out)
    print("图片 %d 张 | 正文 %d 字" % (len(dsts), len(r["content"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
