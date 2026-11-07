# -*- coding: utf-8 -*-
"""把「圣诞树-4-6岁」从半成品（6 张 chain）补成完整 26 页 / 16 图课件。

原先只有 chain 6 张、pages=0。这里补：
  1) 10 个 real/photo 槽位（真实摄影素材，AI 生成）
  2) 26 页 pages 结构（沿用《糖葫芦》母版数据骨架，内容全部改写为圣诞树）
  3) 步骤5 加 alias → 直接复用成品（省一张图 + 像素级一致）
跑完再走: pipeline.py --batch chain / real / photo → builder.py → exporter.py
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "项目", "圣诞树-4-6岁")
PJ = os.path.join(ROOT, "project.json")

REAL_STYLE = ("Professional real-world photography, sharp focus, natural daylight, high detail, "
              "realistic colours, horizontal composition, no text, no watermark.")

TREE_LOCK = ("one Christmas tree standing in the centre of a snowy field, facing the viewer; "
             "the tree is built from THREE stacked triangles of dark green, the biggest at the bottom "
             "and the smallest on top, with a straight brown trunk below; ONE bright yellow five-pointed "
             "star sits on the very top; one strand of small round yellow fairy lights loops down across "
             "the tree in wide zig-zags; FIVE round baubles hang on the branches - red, yellow, blue, red "
             "and yellow; a few small white dots of snow sit on the branches; ONE red square gift box with "
             "a gold ribbon and bow on the ground at the lower right; white snow covering the ground, small "
             "snowflakes falling, deep navy-blue night sky with 6-7 small white four-pointed stars")

NEW_IMAGES = [
    dict(slot="实物_圣诞树", batch="real", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", style=REAL_STYLE, refs=[], ref_prev=False, lock=False,
         prompt="One real decorated Christmas tree standing outdoors on fresh white snow, dark green "
                "pine branches with dense needles, a golden five-pointed star on the very top, a few red "
                "and blue glass baubles with a warm sheen, one string of tiny warm-white fairy lights wound "
                "through the branches, soft cold winter daylight, piles of snow at the base, blurred pale "
                "winter background, eye-level wide shot, extremely clear needle and bauble detail."),
    dict(slot="实物_装饰球", batch="real", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", style=REAL_STYLE, refs=[], ref_prev=False, lock=False,
         prompt="A small group of real Christmas baubles resting on a clean light wooden table: one glossy "
                "red, one golden yellow, one deep blue, each with a thin metallic cap and a short hanging "
                "loop, glossy painted surfaces with crisp white window reflections, one red bauble slightly "
                "out of focus behind, soft window daylight from the left, top-down view, crisp macro detail."),
    dict(slot="实物_材料工具", batch="real", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", style=REAL_STYLE, refs=[], ref_prev=False, lock=False,
         prompt="A neat flat-lay of children's art-class materials on a clean light wooden table: a sheet of "
                "off-white drawing paper, a black fineliner pen, three broad-tip markers in dark green, bright "
                "yellow and tomato red, one blue marker, a white gel highlighter pen, a grey pencil and an "
                "eraser, a small plate of white paper snowflake confetti, bright soft daylight, top-down view, "
                "clean simple background, high detail."),
    dict(slot="素材_圣诞树全身", batch="photo", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", style=REAL_STYLE, refs=[], ref_prev=False, lock=False,
         prompt="A fully decorated real Christmas tree in a warm living room corner, deep green branches, "
                "red and gold baubles, a glowing golden star on top, warm fairy lights, a knitted tree skirt "
                "with two wrapped gifts beside it, soft evening window light, whole tree in frame, no people, "
                "no text, horizontal composition."),
    dict(slot="素材_装饰球特写", batch="photo", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", style=REAL_STYLE, refs=[], ref_prev=False, lock=False,
         prompt="Extreme close-up macro photograph of one glossy red Christmas bauble hanging on a real pine "
                "branch, its mirror-like surface reflecting warm fairy lights, dusted with a few snow crystals, "
                "green needles sharply detailed, shallow depth of field, no text."),
    dict(slot="素材_树顶星星", batch="photo", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", style=REAL_STYLE, refs=[], ref_prev=False, lock=False,
         prompt="Close-up of a golden five-pointed star tree topper glowing warmly on the tip of a real "
                "Christmas tree, dark green needles around it, soft bokeh fairy lights in the background, "
                "gentle warm glow spilling onto the branches, shallow depth of field, no text."),
    dict(slot="素材_礼物脚下", batch="photo", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", style=REAL_STYLE, refs=[], ref_prev=False, lock=False,
         prompt="Three wrapped gift boxes stacked at the foot of a real Christmas tree on a red knitted tree "
                "skirt, red kraft paper with a gold ribbon and a neat bow, white snow-flake patterned wrapping, "
                "pine needles and a few baubles visible above, warm indoor light, shallow depth of field, no text."),
    dict(slot="素材_小朋友装饰", batch="photo", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", style=REAL_STYLE, refs=[], ref_prev=False, lock=False,
         prompt="A child's hand in a red knitted mitten hooking a red glass bauble onto a real pine branch of a "
                "Christmas tree, warm fairy lights glowing behind the branches, no face visible, cosy winter "
                "clothing, soft warm indoor light, shallow depth of field, no text."),
    dict(slot="素材_夜景灯光", batch="photo", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", style=REAL_STYLE, refs=[], ref_prev=False, lock=False,
         prompt="A real Christmas tree standing outdoors at night on fresh snow, covered in warm white fairy "
                "lights, a glowing golden star on top, deep navy-blue night sky with a few faint stars, small "
                "snowflakes falling and catching the light, soft blue shadows on the snow, wide shot, no text."),
    dict(slot="素材_松枝雪", batch="photo", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", style=REAL_STYLE, refs=[], ref_prev=False, lock=False,
         prompt="Close-up of fresh white snow resting on dark green pine needles and one small pine cone, a few "
                "tiny ice crystals catching the light, blurred pale blue winter background, high detail, no text."),
]

PAGES = [
    dict(type="cover", title="《圣诞树》", subtitle="《冬日节日主题》  马克笔 4-6岁",
         slogan=["一节课 · 一套课件 · 直接上课",
                 "实物观察 + 范画全过程 + 26 页排好版",
                 "一棵绿绿的树，一颗亮亮的星，孩子一节课就画完"],
         image="范画成品", uses=["范画成品"]),
    dict(type="intro", title="课 程 介 绍", chapter="课程介绍", image="范画成品",
         cards=[dict(head="课程目标", items=[
                   "1.观察真实的圣诞树，了解松枝、彩球、星星的外形特点，学会用三角形和小圆概括。",
                   "2.学习绿色系的深浅变化，用深绿压暗、亮绿提亮，画出树的层次。",
                   "3.学习“大—中—小”三层堆叠的顺序，把画面撑满又不乱。"]),
                dict(head="课程重难点", items=[
                   "1.三个三角形下宽上窄，一层压一层，边角要露出来。",
                   "2.树顶的星星要正、要亮，是整张画的“眼睛”。",
                   "3.彩球左右分开挂，不要挤成一堆。"]),
                dict(head="教学安排", items=[
                   "1.课程导入    2.主题知识    3.实物观察",
                   "4.绘画知识    5.参考素材    6.范画步骤    7.分享总结"])],
         uses=["范画成品"]),
    dict(type="knowing", title="我们今天可以知道：", chapter="课程介绍",
         items=["1、圣诞树的形状是怎么堆出来的。",
                "2、松树为什么冬天还是绿的。",
                "3、树上的彩球、灯串、星星都是什么。",
                "4、绿色同类色的深浅变化。",
                "5、一幅完整作品的创作步骤。"],
         uses=[]),
    dict(type="quiz", title="考 一 考", chapter="课程引导",
         question="圣诞树最上面那颗亮亮的星星，你知道它叫什么吗？",
         images=["素材_树顶星星", "素材_装饰球特写"],
         answer="揭晓：它叫“伯利恒之星”，也叫圣诞星。传说它指引人们找到了刚出生的小宝宝，所以每年都要把它挂在最高处。",
         uses=["素材_树顶星星", "素材_装饰球特写"]),
    dict(type="knowledge", title="秘密一：松树冬天为什么不落叶？", chapter="课程引导",
         image="素材_松枝雪", lines=[
             "松树的叶子是细细的针，外面有一层蜡，",
             "水分散得慢，所以大雪压着也还是绿的。",
             "这就是为什么别的树光秃秃，它还能挂彩球。"],
         uses=["素材_松枝雪"]),
    dict(type="knowledge", title="秘密二：树上挂的彩球是干什么的？", chapter="课程引导",
         image="素材_装饰球特写", lines=[
             "很早以前，人们把苹果挂在树上表示丰收，",
             "后来苹果换成了圆圆的玻璃球，红、黄、蓝都有。",
             "球越亮，灯一照就越像一颗颗小果子。"],
         uses=["素材_装饰球特写"]),
    dict(type="knowledge", title="秘密三：礼物为什么放在树下面？", chapter="课程引导",
         image="素材_礼物脚下", lines=[
             "树下面铺一块布，礼物一层层摞起来，",
             "大大小小的方盒子，系着金色的丝带和蝴蝶结。",
             "盒子是方的，球是圆的，方和圆摆在一起最好看。"],
         uses=["素材_礼物脚下"]),
    dict(type="real_object", title="看一看：真实的圣诞树长什么样？", chapter="实物观察",
         image="实物_圣诞树", image2="实物_装饰球", img_h=3.05, img2_h=1.15,
         task_head="观察小任务",
         tasks=[dict(tag="看形状", text="整棵树是一个大大的三角形，下面最宽。"),
                dict(tag="看分层", text="叶子一层一层往下垂，像三层小裙子。"),
                dict(tag="看颜色", text="松针是深绿的，越往里越黑。"),
                dict(tag="看挂饰", text="彩球圆圆的，表面亮得能照出影子。"),
                dict(tag="摸一摸", text="针叶有点扎手，彩球滑滑凉凉的。")],
         uses=["实物_圣诞树", "实物_装饰球"]),
    dict(type="materials", title="摸一摸：我们要用到哪些材料？", chapter="实物观察",
         image="实物_材料工具",
         schemes=[dict(head="方案A 马克笔", items=[
                   "半生熟镜面宣纸（或 160g 白卡）",
                   "黑色勾线笔",
                   "绿色系马克笔（深绿 / 草绿 / 亮黄绿）",
                   "红色、黄色、蓝色马克笔各一支",
                   "白色高光笔",
                   "铅笔、橡皮"])],
         uses=["实物_材料工具"]),
    dict(type="observe_tags", title="圣诞树的外形有什么特点呢？", chapter="课程引导",
         image="素材_圣诞树全身",
         tags=["上尖下宽的三角", "一层压一层", "深绿配亮黄", "圆圆的彩球", "树顶一颗星", "脚下小礼物"],
         uses=["素材_圣诞树全身"]),
    dict(type="parts_diagram", title="圣诞树是由哪些部分组成的呢？", chapter="课程引导",
         figure_note="三个三角形 + 一个小圆 = 一棵圣诞树",
         figure={"tree3": [2.55, 4.85, 3.10, 1.05],
                 "tree2": [2.95, 3.75, 2.30, 1.00],
                 "tree1": [3.40, 2.70, 1.40, 0.95],
                 "star": [3.85, 2.10, 0.50, 0.50],
                 "gift": [4.75, 5.75, 1.25, 0.45]},
         parts=[dict(name="树身", desc="三个三角形"),
                dict(name="树干", desc="一条短竖线"),
                dict(name="星星", desc="五角小黄星"),
                dict(name="彩球", desc="五个小圆"),
                dict(name="礼物", desc="一个小方块")],
         uses=[]),
    dict(type="poses", title="圣诞树都有哪些不同的样子呢？", chapter="课程引导",
         items=[dict(image="素材_圣诞树全身", label="整棵树"),
                dict(image="素材_礼物脚下", label="脚下礼物"),
                dict(image="素材_小朋友装饰", label="伸手挂球")],
         uses=["素材_圣诞树全身", "素材_礼物脚下", "素材_小朋友装饰"]),
    dict(type="idea_list", title="圣诞树还会出现在哪里呢？", chapter="课程引导",
         image="素材_夜景灯光", list_head="想一想，还可以怎么画？",
         items=["站在雪地里，天上飘着雪",
                "窗外是一棵树，屋里暖暖的黄光",
                "树上住着一只小猫",
                "礼物堆得比树还高",
                "小朋友围着树转圈唱歌"],
         uses=["素材_夜景灯光"]),
    dict(type="color_swatches", title="同类色小知识 —— 绿色家族", chapter="绘画知识",
         swatches=[dict(hex="9CCC65", name="亮黄绿", use="受光面和高光"),
                   dict(hex="3E8E41", name="草绿", use="树身固有色"),
                   dict(hex="1B5E20", name="深墨绿", use="暗面和层与层的缝"),
                   dict(hex="F6C544", name="星星黄", use="树顶星星和灯串")],
         note_head="画圣诞树的时候，不要只用一种绿：",
         note="先用草绿把三个三角形平涂，再用深墨绿压每一层的下边和缝，最后用亮黄绿在靠外的边角刷几笔，树一下就有了光。",
         uses=[]),
    dict(type="text_page", title="涂色不脏的四个小技巧", chapter="绘画知识",
         lines=["① 先描边再填色：贴着黑线里面涂，不涂出格。",
                "② 从浅到深：先草绿平涂，再深绿压暗，最后亮绿提亮。",
                "③ 缝要留着：层与层之间留一条深绿的缝，树才有层次。",
                "④ 星星和高光最后画：白色和黄色点在最上面，画面才亮。"],
         uses=[]),
    dict(type="refs", chapter="参考素材",
         images=["素材_圣诞树全身", "素材_装饰球特写"],
         uses=["素材_圣诞树全身", "素材_装饰球特写"]),
    dict(type="refs", chapter="参考素材",
         images=["素材_树顶星星", "素材_松枝雪"],
         uses=["素材_树顶星星", "素材_松枝雪"]),
    dict(type="refs", chapter="参考素材",
         images=["实物_圣诞树", "素材_小朋友装饰"],
         uses=["实物_圣诞树", "素材_小朋友装饰"]),
    dict(type="tools_dual", title="工 具 介 绍", chapter="范画过程", title_W=4.0,
         schemes=[dict(head="方案A · 马克笔（推荐）",
                       tools=[dict(no="1", name="半生熟镜面宣纸", desc="纸有纹理，颜色更柔和"),
                              dict(no="2", name="黑色勾线笔", desc="勾轮廓、画树干和丝带"),
                              dict(no="3", name="绿色系马克笔", desc="深绿、草绿、亮黄绿各一支"),
                              dict(no="4", name="红黄蓝马克笔", desc="画彩球和礼物盒"),
                              dict(no="5", name="白色高光笔", desc="点彩球高光和雪")])],
         uses=[]),
    dict(type="step", title="步骤一：起 形", chapter="范画过程", image="范画步骤1_起形",
         text="先用铅笔轻轻画三个三角形，下面最大、中间中等、上面最小，一层压一层；再在下面画一根短短的树干，树顶画一颗五角星。",
         tips=["先定最下面那个三角形，再往上收", "三个三角形要左右对称，别歪", "铅笔线画轻一点，画错可以擦"],
         uses=["范画步骤1_起形"]),
    dict(type="step", title="步骤二：勾 线", chapter="范画过程", image="范画步骤2_勾线",
         text="用黑色勾线笔沿铅笔线描一遍，三个三角形的边要画得直、画得挺；再勾出彩球的圆、礼物盒的方和灯串的波浪线。",
         tips=["三角形的尖角要尖，不要画圆了", "彩球的圆要饱满，不要画成椭圆", "先不要上色，保持画面干净"],
         uses=["范画步骤2_勾线"]),
    dict(type="step", title="步骤三：涂 色", chapter="范画过程", image="范画步骤3_涂色",
         text="三个三角形全部涂草绿，树干涂棕色，星星涂亮黄，五个彩球分别涂红、黄、蓝、红、黄，礼物盒涂红色，颜色一定平涂涂满。",
         tips=["贴着黑线里面涂，别涂出格", "彩球之间留一点白，不要糊成一片", "背景先空着，留到最后一步"],
         uses=["范画步骤3_涂色"]),
    dict(type="step", title="步骤四：加 深", chapter="范画过程", image="范画步骤4_加深",
         text="用深墨绿沿着每个三角形的下边和层与层的缝压一道，彩球的暗面也加深，星星底下加一点深黄，树立刻鼓起来了。",
         tips=["深色只压一边，不要整块涂黑", "缝要顺着三角形的边画，不要横着涂", "彩球的暗面在右下，高光在左上"],
         uses=["范画步骤4_加深"]),
    dict(type="step", title="步骤五：加背景", chapter="范画过程", image="范画步骤5_加背景",
         text="用深蓝把夜空涂满，点上白色的小星星和飘落的雪花；树下的雪地留白，只在树根处加一道淡蓝的影子；灯串涂亮黄，丝带涂金色。",
         tips=["深蓝要涂匀，别留白斑", "雪花大小不一才像真的", "最后检查有没有漏涂的地方"],
         uses=["范画步骤5_加背景"]),
    dict(type="final_dual", title="范 画 成 品", chapter="范画过程",
         hint="这就是步骤五完成后的画面（成品与最后一步是同一张作品）",
         items=[dict(image="范画成品", label="学 生 作 品")],
         note="完整画面要有：三个上尖下宽的三角形 + 一颗亮亮的星星 + 五个彩球 + 一个礼物盒 + 深蓝夜空和雪地。别忘记写上作品名称、签上名字哦！",
         uses=["范画成品"]),
    dict(type="share_summary", chapter="分享表达", title="分享表达 + 课后总结",
         share_head="分 享 表 达", summary_head="课 后 总 结",
         share=["1、为什么圣诞树下面是宽的、上面是尖的？",
                "2、你画的树用了哪三种绿？"],
         summary=["1、本节课先观察真实的圣诞树和彩球，了解形状和层次，学习用三角形和小圆概括“一棵树”的形体，让孩子养成先看再画的习惯。",
                  "2、通过深绿压暗、亮绿提亮，让孩子理解同一种颜色也能分出亮面和暗面，提高画面的体积感。",
                  "3、通过“大—中—小”三层堆叠和彩球左右分布，让孩子感受画面的秩序和节奏，完成一幅构图饱满、颜色响亮、有节日气氛的作品。"],
         uses=[]),
]


def main():
    p = json.load(open(PJ, encoding="utf-8"))
    have = {i["slot"] for i in p["images"]}
    added = 0
    for im in NEW_IMAGES:
        if im["slot"] not in have:
            p["images"].append(im)
            added += 1

    # 步骤5 = 成品别名（像素级一致，省一张图）
    for im in p["images"]:
        if im["slot"] == "范画步骤5_加背景":
            im["alias"] = "范画成品"

    p["pages"] = PAGES
    json.dump(p, open(PJ, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("images:", len(p["images"]), "(+%d)" % added)
    print("pages :", len(p["pages"]))
    used = set()
    for pg in p["pages"]:
        used |= set(pg.get("uses") or [])
    slots = {i["slot"] for i in p["images"]}
    print("页面引用但缺槽位:", sorted(used - slots) or "无")
    print("有槽位但没被页面用到:", sorted(slots - used) or "无")


if __name__ == "__main__":
    main()
