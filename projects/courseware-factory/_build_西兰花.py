# -*- coding: utf-8 -*-
"""新建《西兰花出逃》4-6岁课件：16 个槽位（6 chain + 10 real/photo）+ 26 页。

选题依据：选题器 2026-11-07 12:33 第一名（92.6 分 PASS），
爆款依据《创意少儿美术课件～西兰花派对》20886 赞 / 15751 藏，
配方 = 马克笔平涂撞色（粗黑实线 + 高饱和平涂 + 内部填花纹 + 白高光）。

跑完：
  python 工厂/pipeline.py 项目/西兰花出逃-4-6岁/project.json --batch chain --no-ui
  python 工厂/pipeline.py 项目/西兰花出逃-4-6岁/project.json --batch real --no-ui
  python 工厂/pipeline.py 项目/西兰花出逃-4-6岁/project.json --batch photo --no-ui
  python 工厂/preflight.py 项目/西兰花出逃-4-6岁/project.json
  python 工厂/builder.py 项目/西兰花出逃-4-6岁/project.json --no-ui
  python 工厂/exporter.py 项目/西兰花出逃-4-6岁/project.json
  python 工厂/layout_check.py 项目/西兰花出逃-4-6岁/project.json
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "项目", "西兰花出逃-4-6岁")
PJ = os.path.join(ROOT, "project.json")

PAPER_STYLE = ("A top-down flat photograph of one sheet of off-white rice paper on a light wooden desk, "
               "even soft daylight, the paper fills the whole frame, visible paper texture, mild realistic "
               "paper shadow. Children's art class illustration, hand-drawn, flat colours, thick clean "
               "outlines, no text, no signature, no watermark.")

REAL_STYLE = ("Professional real-world photography, sharp focus, natural daylight, high detail, "
              "realistic colours, horizontal composition, no text, no watermark.")

STROKE = (
    "LINE AND STROKE LANGUAGE - one single clean hand is used for the whole sequence, the finished artwork "
    "and every step alike, with no variation whatsoever: every contour is ONE clean, confident, CONTINUOUS "
    "SOLID LINE of even medium thickness, drawn with a broad-tip children's MARKER pen. The line runs "
    "unbroken from start to finish; the edges are crisp and clearly defined all the way along, like a "
    "hand-drawn clean outline, with only a slight natural wobble that shows a child drew it by hand. "
    "Clean solid line means: NO hairy or fuzzy broken edges, NO contour that frays or splits into short "
    "furry strokes, NO dashes or dotted outlines, NO sketchy doubled lines, NO overshooting strokes beyond "
    "the corners, NO thin scratched pencil texture, NO crayon rubbing or smudging, and NO colour bleeding "
    "across the outline. Any dark area is filled with FLAT SOLID marker colour, evenly covered edge to "
    "edge, with at most one or two tiny white highlight dots; never a gradient, never grainy, never "
    "blended or airbrushed. Every colour sits flat INSIDE its outline and never crosses the line. "
    "PATTERN LANGUAGE - the big shapes are not left empty: inside the floret bumps there are TWO kinds of "
    "simple hand-drawn decoration, white polka dots and dark-green spirals, plus a few short straight "
    "hatch strokes on the leaves. The decoration is drawn with the same marker, big and simple, never "
    "tiny or fussy, and it always stays inside its own shape."
)

LOCK = (
    "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
    "ONE cheerful broccoli character stands in the centre of the sheet, seen from the front, walking to "
    "the RIGHT. Its head is a big cloud of FIVE large round floret bumps of different sizes, tightly "
    "touching each other, sitting on ONE short thick pale-green stalk below. The stalk carries a simple "
    "face: two big round black eyes with a small white highlight dot in each, and one wide open smiling "
    "mouth. TWO large pointed green leaves spread out at the sides of the bottom of the stalk. TWO short "
    "thin stick legs, one leg stepping forward, with two simple oval shoes. A small round cloth bundle "
    "with white polka dots hangs on a short stick over its LEFT shoulder. On the upper LEFT there is ONE "
    "plate, only its lower half is visible. The bottom of the sheet is a straight light wooden counter "
    "edge, the wall behind it is plain warm cream. HARD RULE: the florets are FIVE SEPARATE LARGE ROUND "
    "BUMPS of different sizes, NOT one single round ball and NOT a chain of small beads. Canvas aspect "
    "3:2 landscape, paper centred, nothing cropped by the frame edge."
)

BRAND = "绘课工坊"

IMAGES = [
    # ---------- chain：成品（锚点，无参考） ----------
    dict(slot="范画成品", batch="chain", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", refs=[], ref_prev=False, lock=True, style=PAPER_STYLE,
         prompt=(
             "THIS IS THE FINISHED MASTER ARTWORK of the lesson, drawn at its very best. Everything is "
             "complete and fully coloured flat with markers. The five floret bumps of the head are filled "
             "with a solid bright yellow-green; a deep forest green is painted along the lower edge of "
             "each bump and in the gaps between the bumps, so every bump reads separately. Inside the "
             "bumps there are big white polka dots and a few dark-green spirals. The stalk is a solid pale "
             "green with the face drawn in black, the two leaves are medium green with short dark hatch "
             "strokes. The two shoes and the round cloth bundle are coral red; the bundle is covered with "
             "big white polka dots and hangs on a short brown stick over the left shoulder. The plate is "
             "white with three short blue-grey stripes. The wall behind is a flat warm cream with THREE "
             "short light-orange motion lines behind the character showing it is walking away, and the "
             "bottom of the sheet is a flat light-brown wooden counter edge. White gel-pen highlight dots "
             "sit on the upper side of two or three floret bumps and on the shoes. The picture is finished, "
             "balanced, cheerful and loud in colour.")),
    # ---------- chain：步骤1 起形（挂成品，做减法） ----------
    dict(slot="范画步骤1_起形", batch="chain", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", refs=["范画成品"], ref_prev=False, lock=True, style=PAPER_STYLE,
         prompt=(
             "THIS IS STEP 1 OF 5. Take the REFERENCE ARTWORK and reduce it to a light grey PENCIL "
             "CONSTRUCTION SKETCH - geometry absolutely identical to the reference, nothing added, nothing "
             "moved, nothing removed: the same five round floret bumps in the same positions, the same "
             "short thick stalk, the same two eyes and mouth, the same two side leaves, the same two legs "
             "and shoes, the same round bundle on the stick, the same half plate. Remove every colour, "
             "remove the thick black outline, remove the polka dots and spirals, and leave only faint thin "
             "LIGHT GREY pencil lines with a few soft construction marks. The background must stay almost "
             "bare white paper: only a very faint straight pencil line for the counter edge. No colour, no "
             "ink, no marker anywhere.")),
    # ---------- chain：步骤2 勾线 ----------
    dict(slot="范画步骤2_勾线", batch="chain", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", refs=[], ref_prev=True, lock=True, style=PAPER_STYLE,
         prompt=(
             "THIS IS STEP 2 OF 5. Continue from the reference sketch and keep the identical composition. "
             "The grey pencil scaffold is now traced into a clean, confident BLACK MARKER OUTLINE drawing: "
             "every floret bump, the stalk, both eyes, the open smiling mouth, the two leaves, the two legs "
             "and the two shoes, the round bundle and its stick, and the half plate are outlined in thick "
             "black. A few large white polka dots and two or three spirals are drawn inside the floret "
             "bumps as empty black outlines only. NO colour is filled in yet: the drawing is pure black "
             "line on white paper and the pencil construction lines are gone. The background stays bare "
             "white paper apart from one straight thin black line for the counter edge.")),
    # ---------- chain：步骤3 涂色（背景必须留白） ----------
    dict(slot="范画步骤3_涂色", batch="chain", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", refs=[], ref_prev=True, lock=True, style=PAPER_STYLE,
         prompt=(
             "THIS IS STEP 3 OF 5. Keep the identical composition and the same black outline. Now the FLAT "
             "COLOURS are filled in with a broad-tip marker, evenly and solidly inside the outlines: the "
             "five floret bumps are filled bright yellow-green, the stalk pale green, the two leaves medium "
             "green, the two shoes coral red, the round bundle coral red, and the plate white with three "
             "short blue-grey stripes. The face stays black line only. No shading, no gradient, no texture "
             "yet - just clean flat blocks of colour. HARD RULE: in this step the wall and the background "
             "MUST stay pure blank white paper. Do NOT paint the wall cream. Do NOT paint the counter. "
             "Only the broccoli, its bundle, its shoes and the plate get colour.")),
    # ---------- chain：步骤4 加深（+ 内部花纹） ----------
    dict(slot="范画步骤4_加深", batch="chain", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", refs=[], ref_prev=True, lock=True, style=PAPER_STYLE,
         prompt=(
             "THIS IS STEP 4 OF 5. Keep the identical composition. Now add the DARKER TONE on top of the "
             "flat colours AND the interior pattern. A deep forest green is pressed along the lower edge "
             "of each of the five floret bumps and into the gaps between them, so that every bump pops out; "
             "a deeper green goes along one side of the stalk and the lower half of the two leaves, and the "
             "lower side of the shoes and the bundle get a deeper red. Then the inside decoration is added "
             "with the same markers: big WHITE POLKA DOTS on two or three bumps and two or three DARK-GREEN "
             "SPIRALS on the other bumps, plus three or four short dark hatch strokes on each leaf. HARD "
             "RULE: the wall and the background stay pure blank white paper in this step - still no cream "
             "wall, no wooden counter, no shadow.")),
    # ---------- chain：步骤5 = 成品别名 ----------
    dict(slot="范画步骤5_加背景", batch="chain", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", refs=[], ref_prev=True, lock=True, style=PAPER_STYLE, alias="范画成品",
         prompt=(
             "THIS IS STEP 5 OF 5, the final stage. Keep the identical composition and everything already "
             "painted. Now fill in the BACKGROUND of the picture, finishing the artwork exactly as described "
             "in the finished artwork: the wall behind is filled with a flat warm cream, three short "
             "light-orange motion lines are added behind the character, the bottom of the sheet is filled "
             "with a flat light-brown wooden counter edge, the plate gets its blue-grey stripes, and white "
             "gel-pen highlight dots are added on the upper side of two or three floret bumps.")),

    # ---------- real：实物观察 ----------
    dict(slot="实物_西兰花", batch="real", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", refs=[], ref_prev=False, lock=False, style=REAL_STYLE,
         prompt=(
             "One fresh raw head of broccoli standing upright on a plain white ceramic plate on a light "
             "wooden kitchen counter, its dense yellow-green floret head clearly made of many small round "
             "bumps, a short thick pale-green stalk with two small leaves at the bottom, soft natural "
             "window daylight from the left, gentle shadow to the right, plain pale background, eye-level "
             "wide shot, extremely sharp detail of the floret bumps, no text.")),
    dict(slot="实物_花球特写", batch="real", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", refs=[], ref_prev=False, lock=False, style=REAL_STYLE,
         prompt=(
             "Extreme close-up macro photograph of a fresh broccoli floret head, showing hundreds of tiny "
             "round green buds packed tightly together like a hill of small beads, one bud in sharp focus "
             "with the others melting into a soft shallow depth of field, fine water droplets catching the "
             "light, cool fresh green colour, clean out-of-focus pale background, no text.")),
    dict(slot="实物_材料工具", batch="real", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", refs=[], ref_prev=False, lock=False, style=REAL_STYLE,
         prompt=(
             "A neat flat-lay of children's art-class materials on a clean light wooden table: a blank sheet "
             "of off-white drawing paper, a black fineliner pen, three broad-tip markers in bright "
             "yellow-green, medium green and deep forest green, one coral-red marker, a white gel "
             "highlighter pen, a grey pencil and an eraser, bright soft daylight, top-down view, clean "
             "simple background, high detail. HARD RULE: the sheet of paper must be completely BLANK - no "
             "drawing, no sketch, no picture, no broccoli, no animal anywhere on it.")),

    # ---------- photo：素材 ----------
    dict(slot="素材_西兰花全身", batch="photo", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", refs=[], ref_prev=False, lock=False, style=REAL_STYLE,
         prompt=(
             "A whole fresh broccoli head photographed against a plain warm cream background, studio soft "
             "lighting, the yellow-green floret head on top and the thick pale-green stalk with two spread "
             "leaves at the bottom, the whole vegetable in frame, three-quarter view, sharp detail on every "
             "bump, subtle soft shadow, no people, no text.")),
    dict(slot="素材_菜梗切面", batch="photo", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", refs=[], ref_prev=False, lock=False, style=REAL_STYLE,
         prompt=(
             "Close-up photograph of a broccoli stalk cut cleanly across, the pale-green cross-section "
             "facing the camera and showing a light core ringed by small dots in a rough circle, one whole "
             "broccoli head lying beside it, on a light wooden cutting board, natural daylight, crisp detail "
             "of the cut surface, no text.")),
    dict(slot="素材_西兰花田", batch="photo", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", refs=[], ref_prev=False, lock=False, style=REAL_STYLE,
         prompt=(
             "A real broccoli field in daytime: rows of broccoli plants growing in dark soil, each plant a "
             "rosette of large blue-green leaves with a compact green floret head forming in the centre, low "
             "afternoon sunlight, shallow depth of field down the row, a few soft clouds in the sky, no "
             "people, no text.")),
    dict(slot="素材_盘子里的西兰花", batch="photo", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", refs=[], ref_prev=False, lock=False, style=REAL_STYLE,
         prompt=(
             "A fresh broccoli head sitting on a plain white round plate on a light wooden kitchen counter, "
             "photographed from slightly above at eye level, the plate only partly in frame at the left, "
             "warm morning light through a window, a soft shadow to the right, clean simple kitchen "
             "background with a plain cream wall, no people, no text.")),
    dict(slot="素材_小朋友闻菜", batch="photo", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", refs=[], ref_prev=False, lock=False, style=REAL_STYLE,
         prompt=(
             "A child's two small hands holding one fresh broccoli head above a white plate on a wooden "
             "kitchen counter, no face and no body in frame, only the hands and forearms in a rolled-up "
             "sleeve, warm natural window light, shallow depth of field, cosy everyday kitchen background, "
             "no text.")),
    dict(slot="素材_菜市场", batch="photo", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", refs=[], ref_prev=False, lock=False, style=REAL_STYLE,
         prompt=(
             "A real vegetable market stall in the morning: a shallow wooden crate piled with fresh "
             "broccoli heads in front, a few red tomatoes and orange carrots and a white mushroom beside "
             "them, green leaves and paper price tags out of focus behind, soft daylight falling from the "
             "left, colourful and lively, shallow depth of field, no text, no watermark.")),
    dict(slot="素材_花球小森林", batch="photo", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", refs=[], ref_prev=False, lock=False, style=REAL_STYLE,
         prompt=(
             "Five fresh broccoli heads of different sizes standing upright in a row on a light wooden "
             "table like a little row of green trees, plain warm cream wall behind, soft even daylight, "
             "each head clearly a different height, sharp detail on the bumps and stalks, simple playful "
             "still life, no text.")),
    dict(slot="素材_西兰花叶子", batch="photo", model="gpt-image-2.5", quality="high",
         aspect="1536x1024", refs=[], ref_prev=False, lock=False, style=REAL_STYLE,
         prompt=(
             "Close-up photograph of the large blue-green broccoli leaves beside a broccoli stalk, showing "
             "the pale thick midrib and the slightly wavy edge with a few water droplets, the floret head "
             "softly blurred behind, natural daylight, fresh and crisp, clean pale background, no text.")),
]

PAGES = [
    dict(type="cover", title="《西兰花出逃》", subtitle="《厨房里的小故事》  马克笔 4-6岁",
         slogan=["一节课 · 一套课件 · 直接上课",
                 "实物观察 + 范画全过程 + 26 页排好版",
                 "一棵不想被吃掉的西兰花，踮脚溜出了盘子"],
         image="范画成品", uses=["范画成品"]),
    dict(type="intro", title="课 程 介 绍", chapter="课程介绍", image="范画成品",
         cards=[dict(head="课程目标", items=[
                   "1.观察真实西兰花，认识“一团小球 + 一根粗梗”的外形，学会用圆和长条概括。",
                   "2.学习亮黄绿和深墨绿两种绿的用法，画出花球的亮面和暗面。",
                   "3.学会在花球里加波点和螺旋，让画面有花纹、不单调。"]),
                dict(head="课程重难点", items=[
                   "1.花球是一堆大小不同的圆，不要画成一个圆球。",
                   "2.花球要压着梗，梗要短而粗，两条腿要细。",
                   "3.表情画在梗上，眼睛要大，笑容要张开。"]),
                dict(head="教学安排", items=[
                   "1.课程导入    2.主题知识    3.实物观察",
                   "4.绘画知识    5.参考素材    6.范画步骤    7.分享总结"])],
         uses=["范画成品"]),
    dict(type="knowing", title="我们今天可以知道：", chapter="课程介绍",
         items=["1、西兰花的花球是一颗颗小球挨在一起长的。",
                "2、它的梗为什么又短又粗。",
                "3、它在菜园里是怎么长大的。",
                "4、绿色也分深浅：亮黄绿和深墨绿。",
                "5、一幅有故事的画要一步步怎么画。"],
         uses=[]),
    dict(type="quiz", title="考 一 考", chapter="课程引导",
         question="西兰花上面那一团一团的小球，其实是它的什么？",
         images=["实物_花球特写", "素材_菜梗切面"],
         answer="揭晓：那些小球是它还没开的花苞。我们吃的西兰花，其实是一大把没来得及开的小花。",
         uses=["实物_花球特写", "素材_菜梗切面"]),
    dict(type="knowledge", title="秘密一：花球为什么一粒一粒的？", chapter="课程引导",
         image="实物_花球特写", lines=[
             "西兰花的花球不是一整个圆球，",
             "是一颗颗小花苞紧紧挤在一起，像一群小圆球排排坐。",
             "所以画的时候，要画很多大小不同的圆。"],
         uses=["实物_花球特写"]),
    dict(type="knowledge", title="秘密二：它的梗为什么这么粗？", chapter="课程引导",
         image="素材_菜梗切面", lines=[
             "粗粗的梗要托住上面一大团花球，",
             "切开梗，里面是一圈一圈的小圆点。",
             "画画时梗要画得短而粗，画面才站得住。"],
         uses=["素材_菜梗切面"]),
    dict(type="knowledge", title="秘密三：西兰花是从哪里长出来的？", chapter="课程引导",
         image="素材_西兰花田", lines=[
             "一颗小苗种在土里，叶子一层层张开，",
             "过几个月，中间就冒出一小团绿色的花球。",
             "花球越长越大，就成了我们看见的这一颗。"],
         uses=["素材_西兰花田"]),
    dict(type="real_object", title="看一看：真实的西兰花长什么样？", chapter="实物观察",
         image="实物_西兰花", image2="实物_花球特写", img_h=3.05, img2_h=1.15,
         task_head="观察小任务",
         tasks=[dict(tag="看形状", text="上面一大团小球，下面一根粗梗。"),
                dict(tag="看肌理", text="小球一粒一粒，摸上去有小颗粒。"),
                dict(tag="看颜色", text="外面亮黄绿，缝里是深墨绿。"),
                dict(tag="看叶子", text="梗两边各伸出一片大叶子。"),
                dict(tag="摸一摸", text="凉凉的、硬硬的，梗最硬。")],
         uses=["实物_西兰花", "实物_花球特写"]),
    dict(type="materials", title="摸一摸：我们要用到哪些材料？", chapter="实物观察",
         image="实物_材料工具",
         schemes=[dict(head="方案A 马克笔", items=[
                   "160g 白卡纸（或半生熟宣纸）",
                   "黑色勾线笔",
                   "亮黄绿 / 草绿 / 深墨绿马克笔",
                   "番茄红马克笔（画包袱和鞋子）",
                   "白色高光笔",
                   "铅笔、橡皮"])],
         uses=["实物_材料工具"]),
    dict(type="observe_tags", title="西兰花的外形有什么特点呢？", chapter="课程引导",
         image="素材_西兰花全身",
         tags=["上面一团小球", "下面一根粗梗", "梗边两片大叶", "亮绿压深绿", "一粒一粒排着", "顶上一个尖尖"],
         uses=["素材_西兰花全身"]),
    dict(type="parts_diagram", title="西兰花是由哪些部分组成的呢？", chapter="课程引导",
         figure_note="一团小圆 + 一根粗梗 + 两片叶子 = 一棵西兰花",
         shapes=[dict(kind="oval", x=2.45, y=3.50, w=1.25, h=1.15, fill="9CCC65"),
                 dict(kind="oval", x=4.55, y=3.50, w=1.25, h=1.15, fill="9CCC65"),
                 dict(kind="oval", x=3.45, y=2.95, w=1.35, h=1.30, fill="9CCC65"),
                 dict(kind="oval", x=2.80, y=3.02, w=0.85, h=0.80, fill="B5D96A"),
                 dict(kind="oval", x=4.60, y=3.02, w=0.85, h=0.80, fill="B5D96A"),
                 dict(kind="rect", x=3.55, y=4.60, w=1.05, h=1.10, fill="CFE8B8"),
                 dict(kind="oval", x=2.35, y=5.25, w=1.55, h=0.55, fill="3E8E41"),
                 dict(kind="oval", x=4.25, y=5.25, w=1.55, h=0.55, fill="3E8E41"),
                 dict(kind="rect", x=3.72, y=5.70, w=0.20, h=0.42, fill="1B5E20"),
                 dict(kind="rect", x=4.20, y=5.70, w=0.20, h=0.42, fill="1B5E20"),
                 dict(kind="oval", x=3.50, y=6.06, w=0.62, h=0.26, fill="E4572E"),
                 dict(kind="oval", x=4.02, y=6.06, w=0.62, h=0.26, fill="E4572E")],
         parts=[dict(name="花球", desc="一堆大小不同的圆"),
                dict(name="梗", desc="一根短而粗的竖条"),
                dict(name="叶子", desc="梗边两片大椭圆"),
                dict(name="腿和鞋", desc="两条细腿加小圆鞋"),
                dict(name="小包袱", desc="肩上扛一个圆包袱")],
         uses=[]),
    dict(type="poses", title="西兰花都有哪些不同的样子呢？", chapter="课程引导",
         items=[dict(image="素材_西兰花全身", label="站着的"),
                dict(image="素材_盘子里的西兰花", label="躺在盘里"),
                dict(image="素材_小朋友闻菜", label="手里捧着")],
         uses=["素材_西兰花全身", "素材_盘子里的西兰花", "素材_小朋友闻菜"]),
    dict(type="idea_list", title="西兰花还会溜到哪里玩呢？", chapter="课程引导",
         image="素材_菜市场", list_head="想一想，还可以怎么画？",
         items=["从盘子里溜下桌，躲到桌子底下",
                "跑到菜市场，和番茄手拉手",
                "撑一片大叶子当伞去淋雨",
                "戴上花球帽子去参加舞会",
                "站在菜篮边上回头偷偷看"],
         uses=["素材_菜市场"]),
    dict(type="color_swatches", title="同类色小知识 —— 绿色家族", chapter="绘画知识",
         swatches=[dict(hex="9CCC65", name="亮黄绿", use="花球的受光面和高光"),
                   dict(hex="3E8E41", name="草绿", use="花球的固有色"),
                   dict(hex="1B5E20", name="深墨绿", use="暗面和小球之间的缝"),
                   dict(hex="E4572E", name="番茄红", use="包袱和鞋子")],
         note_head="画西兰花的时候，不要只用一种绿：",
         note="先用草绿把整团花球平涂，再用深墨绿压花球的下半和粒与粒的缝，最后用亮黄绿在靠上的小球上刷几笔；包袱和鞋子用番茄红，一冷一暖，画面立刻就跳出来了。",
         uses=[]),
    dict(type="text_page", title="涂色不脏的四个小技巧", chapter="绘画知识",
         lines=["① 先描边再填色：贴着黑线里面涂，不涂出格。",
                "② 从浅到深：先草绿平涂，再深绿压暗，最后亮绿提亮。",
                "③ 粒与粒之间留一条深绿的缝，花球才有颗粒感。",
                "④ 高光最后点：白色点在小球的上半，画面才亮。"],
         uses=[]),
    dict(type="refs", chapter="参考素材",
         images=["素材_西兰花全身", "素材_花球小森林"],
         uses=["素材_西兰花全身", "素材_花球小森林"]),
    dict(type="refs", chapter="参考素材",
         images=["素材_菜梗切面", "素材_西兰花叶子"],
         uses=["素材_菜梗切面", "素材_西兰花叶子"]),
    dict(type="refs", chapter="参考素材",
         images=["实物_西兰花", "素材_菜市场"],
         uses=["实物_西兰花", "素材_菜市场"]),
    dict(type="tools_dual", title="工 具 介 绍", chapter="范画过程", title_W=4.0,
         schemes=[dict(head="方案A · 马克笔（推荐）",
                       tools=[dict(no="1", name="160g 白卡纸", desc="纸厚一点，涂两遍也不起毛"),
                              dict(no="2", name="黑色勾线笔", desc="勾轮廓、画表情和两条腿"),
                              dict(no="3", name="绿色系马克笔", desc="亮黄绿、草绿、深墨绿各一支"),
                              dict(no="4", name="番茄红马克笔", desc="画包袱和鞋子，撞色用"),
                              dict(no="5", name="白色高光笔", desc="点花球高光和波点")])],
         uses=[]),
    dict(type="step", title="步骤一：起 形", chapter="范画过程", image="范画步骤1_起形",
         text="先用铅笔轻轻画一团小球：中间一个大圆，左右各一个大圆，上面再补两个小圆，五个圆挤在一起；下面接一根短粗的梗，梗边画两片大叶子，再画两条细腿和小鞋。",
         tips=["先画中间最大的那个圆，再往两边加", "五个圆要挤紧，不要分开", "铅笔线画轻一点，画错可以擦"],
         uses=["范画步骤1_起形"]),
    dict(type="step", title="步骤二：勾 线", chapter="范画过程", image="范画步骤2_勾线",
         text="用黑色勾线笔把每个球的边描出来，圆要画得饱满；再勾出梗的两条边、叶子的尖、两条细腿和小鞋；最后在梗上画两个大眼睛和一个张开笑的嘴巴。",
         tips=["球的边要圆，不要画成方块", "两个眼睛一样大，眼珠都往右看", "嘴巴画大一点，才像在笑"],
         uses=["范画步骤2_勾线"]),
    dict(type="step", title="步骤三：涂 色", chapter="范画过程", image="范画步骤3_涂色",
         text="五个花球全部涂亮黄绿，梗涂浅绿，两片叶子涂草绿，小鞋和包袱涂番茄红，盘子留白。颜色一定平涂涂满，不要留白点。",
         tips=["贴着黑线里面涂，别涂出格", "五个球先都涂完，再回头补", "背景先空着，留到最后一步"],
         uses=["范画步骤3_涂色"]),
    dict(type="step", title="步骤四：加 深", chapter="范画过程", image="范画步骤4_加深",
         text="用深墨绿沿着每个球的下边压一道，球和球之间的缝也压深；梗的一侧、叶子的下半加深；然后在球里加白色波点和深绿螺旋。",
         tips=["深色只压下边，不要整块涂黑", "波点大小不一样更自然", "螺旋画两三个就够，不要满屏"],
         uses=["范画步骤4_加深"]),
    dict(type="step", title="步骤五：加背景", chapter="范画过程", image="范画步骤5_加背景",
         text="用浅米黄把墙面涂满，桌沿涂一条浅木色；在小包袱后面画三条短短的橙色弧线，表示它正在跑；最后用白色高光笔点在两三个花球的上半和鞋子上。",
         tips=["墙面涂匀，不要留白斑", "动线要短，三条就够", "高光最后点，画面一下就亮了"],
         uses=["范画步骤5_加背景"]),
    dict(type="final_dual", title="范 画 成 品", chapter="范画过程",
         hint="这就是步骤五完成后的画面（成品与最后一步是同一张作品）",
         items=[dict(image="范画成品", label="学 生 作 品")],
         note="完整画面要有：五个挤在一起的花球 + 一根短粗的梗 + 两片大叶子 + 一双大眼睛 + 扛在肩上的小包袱 + 三条动线。别忘记写上作品名称、签上名字哦！",
         uses=["范画成品"]),
    dict(type="share_summary", chapter="分享表达", title="分享表达 + 课后总结",
         share_head="分 享 表 达", summary_head="课 后 总 结",
         share=["1、西兰花的花球为什么是一粒一粒的？",
                "2、你画的西兰花，用了哪三种绿？"],
         summary=["1、本节课先观察真实的西兰花和切面，认识“一团小球 + 一根粗梗 + 两片叶子”的外形，学习用圆和长条概括，让孩子养成先看再画的习惯。",
                  "2、通过亮黄绿提亮、深墨绿压暗，让孩子理解同一种颜色也能分出亮面和暗面，提高画面的体积感。",
                  "3、通过在花球里加波点和螺旋，让孩子体会“形状 + 花纹”的组合方法，最后用动线和小包袱讲一个小故事，完成一幅构图饱满、颜色响亮、有情节的作品。"],
         uses=[]),
]


def main():
    os.makedirs(ROOT, exist_ok=True)
    p = {
        "meta": {
            "name": "《西兰花出逃》4-6岁课件",
            "age": "4-6岁",
            "brand": BRAND,
            "brand_en": "Art Education for Kids",
            "theme": {"primary": "3E8E41", "dark": "14432A", "light": "E4F2D8",
                      "accent": "E4572E", "text": "2F4550", "cream": "FAF7F0", "grey": "595959"},
            "photo_note": "全部图片由 AI 生成，保证画风 + 版权 + 场景统一",
            "selection": {"title": "西兰花出逃", "score": 92.6,
                          "preset": "marker_flat", "source": "选题器 2026-11-07_123333 第 1 名"},
        },
        "lock": LOCK,
        "common": {"stroke": STROKE, "style_preset": "marker_flat"},
        "images": IMAGES,
        "chain": {"order": ["范画成品", "范画步骤1_起形", "范画步骤2_勾线",
                            "范画步骤3_涂色", "范画步骤4_加深", "范画步骤5_加背景"],
                  "auto_ref_prev": True, "anchor": "范画成品",
                  "note": "参考图链：成品(设计基准) → 步骤1 → … → 步骤5"},
        "pages": PAGES,
    }
    json.dump(p, open(PJ, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    slots = [i["slot"] for i in p["images"]]
    used = set()
    for pg in p["pages"]:
        used |= set(pg.get("uses") or [])
    print("images:", len(slots), "pages:", len(p["pages"]))
    print("重复槽位:", [s for s in slots if slots.count(s) > 1] or "无")
    print("页面引用但缺槽位:", sorted(used - set(slots)) or "无")
    print("有槽位但没被页面用到:", sorted(set(slots) - used) or "无")
    print("brand:", p["meta"]["brand"])


if __name__ == "__main__":
    main()
