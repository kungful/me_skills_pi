# -*- coding: utf-8 -*-
"""生成《糖葫芦》4-6岁课件 project.json（全新图，不复用任何旧课件）。

结构沿用 26 页标准链条，内容全部重写。
"""
import json, os, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = r"C:\Users\hua\Documents\备份代码\小红书卖课件"
TPL = os.path.join(ROOT, "项目", "爆米花蹦蹦跳-4-6岁", "project.json")
OUT = os.path.join(ROOT, "项目", "糖葫芦-4-6岁")

with open(TPL, encoding="utf-8") as f:
    tpl = json.load(f)

CH_STYLE = tpl["images"][0]["style"]
REAL_STYLE = tpl["images"][6]["style"]
STROKE = tpl["common"]["stroke"]

LOCK = (
    "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of "
    "completion changes: ONE long thin bamboo skewer runs DIAGONALLY from the LOWER RIGHT "
    "to the UPPER LEFT across the paper; FIVE round hawthorn berries are threaded on it in a "
    "single row, each berry a near-perfect CIRCLE of almost the same size, the bottom berry "
    "slightly the largest and the top berry slightly smaller; every berry wears a smooth glossy "
    "sugar shell with ONE bold white highlight arc on its UPPER LEFT and a thin glossy drip at "
    "the bottom of the lowest berry; a few tiny white sesame seeds stick to the sugar; the skewer "
    "sticks out about two berry-widths above the top berry and its pointed tip points DOWN to the "
    "lower right; ONE small kraft-paper bag with a folded rim sits at the LOWER RIGHT and holds the "
    "skewer end; a few small pale-blue snowflake dots and one short white breath-puff swirl float "
    "in the empty paper around the upper area; the whole subject fills the paper from edge to edge "
    "while the corners stay empty. "
)

FINISH = (
    "THIS IS THE FINISHED MASTER ARTWORK of the lesson, drawn at its very best. Everything is "
    "complete: all five hawthorn berries are filled flat tomato-red with a slightly deeper red "
    "crescent on their lower right, the sugar shell of every berry is painted with a thin warm "
    "apricot-orange glaze and carries ONE bold pure-white highlight arc on the upper left plus one "
    "small white highlight dot near the bottom, the lowest berry has one thin glossy sugar drip; "
    "the bamboo skewer is flat pale-yellow with a short white highlight and a sharp pointed tip; the "
    "kraft-paper bag is flat warm brown with a darker folded rim and a small white highlight on its "
    "edge; tiny white sesame seeds sit on the sugar of every berry; one short white breath-puff "
    "swirl curls in the upper left and five small pale-blue snowflake dots are scattered through the "
    "empty paper, with three thin curved sugar-thread arcs trailing off the bottom berry. A soft flat "
    "grey-blue shadow sits under the bag and under the lowest berry. Large calm areas of bare "
    "off-white paper remain around the subject so the picture breathes. The whole picture is "
    "finished, balanced, shiny and delicious."
)

STEP1 = (
    "THIS IS STEP 1 OF 5, the very first construction sketch, and it is DRAWN ONLY IN LIGHT GREY "
    "PENCIL - no marker, no ink, no colour anywhere on the paper. Faint thin pencil construction "
    "lines only: five circles of almost the same size arranged in one rising diagonal row from the "
    "lower right to the upper left; one long straight line for the bamboo skewer passing through the "
    "centre of all five circles and sticking out at both ends; a small trapezoid with a folded top "
    "edge at the lower right for the kraft-paper bag; a few tiny dots for sesame seeds; one short "
    "spiral for the breath puff; five tiny star shapes for the snowflakes. Construction lines only, "
    "all strokes light, thin and faint, nothing filled in, no shading at all."
)

STEP2 = (
    "THIS IS STEP 2 OF 5. The pencil construction lines are now traced over with the thick solid "
    "black marker line, and NOTHING is coloured in yet - the paper stays bare white apart from the "
    "black outlines. Trace the five round berry outlines, the straight bamboo skewer, the pointed "
    "skewer tip, the kraft-paper bag and its folded rim, the sesame dots, the breath-puff swirl and "
    "the five snowflakes. Add one small curved highlight guide arc on the upper left of every berry. "
    "Every line is crisp, unbroken and slightly wobbly by hand. No colour, no shading yet."
)

STEP3 = (
    "THIS IS STEP 3 OF 5 - COLOUR BLOCKING ONLY, MATTE AND FLAT. Fill all five berries with FLAT "
    "TOMATO RED - a deep warm true red, absolutely NOT orange - and add one deeper dark-red crescent "
    "on the lower right of each berry. Fill the bamboo skewer flat pale yellow. Fill the kraft-paper "
    "bag flat warm brown and its folded rim a slightly darker brown. CRITICAL: do NOT draw ANY white "
    "highlight, white arc, white dot, glossy shine, reflection or sugar glint - every berry must be "
    "one single flat red area with NO white marks inside it. Do NOT draw the sesame seeds, do NOT "
    "draw or colour the snowflakes, do not paint the breath puff, no shadows on the paper. Ignore any "
    "shine you may see in the reference - this stage has no shine at all. This stage must look like a "
    "flat colouring-book page that has just been filled in with red."
)

STEP4 = (
    "THIS IS STEP 4 OF 5. The colour is already down and flat; now the shine and the decoration go "
    "on - this step is what makes the picture look glossy and appetising. Paint every highlight arc "
    "pure white, add one small pure-white highlight dot near the bottom of every berry, one white "
    "highlight on the bamboo skewer and one white highlight on the edge of the kraft-paper bag. Make "
    "the sugar drip at the bottom berry white with a thin outline. Draw the sesame seeds as tiny "
    "white ovals with a light grey outline. Paint the breath-puff swirl white and the five snowflakes "
    "pale sky blue. Nothing else changes - the outlines and the flat colours stay exactly as they are."
)

IMAGES = [
    {"slot": "范画成品", "batch": "chain", "prompt": FINISH},
    {"slot": "范画步骤1_起形", "batch": "chain", "prompt": STEP1},
    {"slot": "范画步骤2_勾线", "batch": "chain", "prompt": STEP2},
    {"slot": "范画步骤3_铺色", "batch": "chain", "prompt": STEP3,
     "refs": ["范画步骤2_勾线"], "ref_prev": False},
    {"slot": "范画步骤4_装饰高光", "batch": "chain", "prompt": STEP4},
    {"slot": "范画步骤5_加背景", "batch": "chain", "prompt": "", "alias": "范画成品"},

    {"slot": "实物_糖葫芦", "batch": "real", "prompt":
        "One real candied hawthorn skewer (tanghulu) lying diagonally on a clean light wooden board, "
        "five glossy red hawthorn berries coated in a thin transparent caramelized sugar shell, tiny "
        "white sesame seeds stuck on the sugar, a pale bamboo skewer with a pointed tip, bright soft "
        "daylight from the upper left, a few small sugar shards on the board, top-down view, extremely "
        "clear detail of the shiny sugar coating."},
    {"slot": "实物_山楂", "batch": "real", "prompt":
        "A small pile of fresh raw hawthorn berries in a shallow wooden bowl on a clean light wooden "
        "table, round deep-red fruit with tiny pale dots and short green stems, one berry cut in half "
        "showing pale flesh and seeds, bright soft daylight from the left, top-down view, crisp "
        "natural detail."},
    {"slot": "实物_材料工具", "batch": "real", "prompt":
        "A neat flat-lay of candied-hawthorn making materials on a clean light wooden table: a small "
        "pile of fresh red hawthorn berries, a bundle of thin bamboo skewers, a small white bowl of "
        "sugar, a little steel pot, two kraft-paper bags, a black fineliner pen and three red markers, "
        "bright soft daylight, top-down view, clean simple background, high detail."},

    {"slot": "素材_糖葫芦串", "batch": "photo", "prompt":
        "Several candied hawthorn skewers standing upright in a straw bale at a winter street stall, "
        "glossy red sugar shells catching the cold daylight, thin white paper wrappers, shallow depth "
        "of field, no people, no text, horizontal composition."},
    {"slot": "素材_糖衣特写", "batch": "photo", "prompt":
        "Extreme close-up macro photograph of the transparent caramelized sugar shell on a candied "
        "hawthorn berry, golden glassy surface with white sesame seeds, tiny air bubbles inside the "
        "sugar, cold bright daylight creating sharp white reflections, shallow depth of field, no "
        "text."},
    {"slot": "素材_山楂特写", "batch": "photo", "prompt":
        "Extreme close-up macro photograph of one fresh hawthorn berry, deep red skin with fine pale "
        "dots and a short green stem, a few more berries softly blurred behind, soft natural daylight, "
        "high detail, no text."},
    {"slot": "素材_冬天街景", "batch": "photo", "prompt":
        "A quiet northern-China winter street with a small candied hawthorn stall, red skewers glowing "
        "against grey-blue snow, bare branches with a thin layer of snow, soft overcast daylight, no "
        "recognisable faces, no text, horizontal composition."},
    {"slot": "素材_小纸袋", "batch": "photo", "prompt":
        "Two candied hawthorn skewers in a small kraft-paper bag standing on a snow-dusted wooden "
        "ledge, glossy red sugar shells, thin white paper wrap, soft cold daylight, shallow depth of "
        "field, no text."},
    {"slot": "素材_雪", "batch": "photo", "prompt":
        "Close-up of fresh snow resting on a dark bare branch, a few tiny ice crystals, soft "
        "blue-white winter light, blurred pale background, high detail, no text."},
    {"slot": "素材_小朋友拿着", "batch": "photo", "prompt":
        "A child's hand wearing a red knitted mitten holding one candied hawthorn skewer against a "
        "softly blurred snowy background, glossy red sugar shell, no visible face, warm winter "
        "clothing, natural daylight, shallow depth of field, no text."},
]

# 补齐 style / 模型等公共字段
for im in IMAGES:
    im.setdefault("style", CH_STYLE if im["batch"] == "chain" else REAL_STYLE)
    im["model"] = "gpt-image-2.5"
    im["quality"] = "high"
    im["aspect"] = "1536x1024"
    im.setdefault("refs", [])
    im.setdefault("ref_prev", im["batch"] == "chain" and im["slot"] not in ("范画成品", "范画步骤1_起形"))
    im["lock"] = im["batch"] == "chain"

PAGES = [
    {"type": "cover", "title": "《糖葫芦》", "subtitle": "《冬日暖食主题》  马克笔 4-6岁",
     "slogan": ["一节课 · 一套课件 · 直接上课",
                "实物观察 + 范画全过程 + 26 页排好版",
                "红红的山楂，亮亮的糖衣，孩子一看就想画"],
     "image": "范画成品", "uses": ["范画成品"]},

    {"type": "intro", "title": "课 程 介 绍", "chapter": "课程介绍", "image": "范画成品",
     "cards": [
         {"head": "课程目标", "items": [
             "1.观察真实的山楂和糖葫芦，了解外形特征，学会用圆形和直线概括。",
             "2.学习红色系的深浅变化，用高光表现糖衣的亮。",
             "3.练习“一串”的排列规律，控制大小和间距。"]},
         {"head": "课程重难点", "items": [
             "1.五颗山楂大小接近、串在同一条斜线上。",
             "2.糖衣高光的位置（左上）和形状（短弧）。",
             "3.红色平涂不出格、不发脏。"]},
         {"head": "教学安排", "items": [
             "1.课程导入    2.主题知识    3.实物观察",
             "4.绘画知识    5.参考素材    6.范画步骤    7.分享总结"]}],
     "uses": ["范画成品"]},

    {"type": "knowing", "title": "我们今天可以知道：", "chapter": "课程介绍", "items": [
        "1、山楂的外形特征和味道。",
        "2、糖衣为什么会变脆、会发亮。",
        "3、认识真实的糖葫芦，观察糖衣和芝麻。",
        "4、红色同类色的深浅变化。",
        "5、一幅完整作品的创作步骤。"], "uses": []},

    {"type": "quiz", "title": "考 一 考", "chapter": "课程引导",
     "question": "糖葫芦外面那层亮亮的壳，是用什么做的？",
     "images": ["素材_糖衣特写", "素材_山楂特写"],
     "answer": "揭晓：是白糖熬成的糖浆！糖浆裹上山楂，一遇冷就变成脆脆的糖壳。",
     "uses": ["素材_糖衣特写", "素材_山楂特写"]},

    {"type": "knowledge", "title": "秘密一：山楂是酸酸的", "chapter": "课程引导",
     "image": "素材_山楂特写",
     "lines": ["山楂小小一颗，比乒乓球还小一点，",
               "咬一口又酸又面，酸得人眯眼睛。",
               "所以裹上一层糖，酸甜搭配才好吃。"],
     "uses": ["素材_山楂特写"]},

    {"type": "knowledge", "title": "秘密二：糖衣是怎么变脆的？", "chapter": "课程引导",
     "image": "素材_糖衣特写",
     "lines": ["白糖加水熬成糖浆，趁热裹在山楂上，",
               "一遇到冷空气就凝固，变成透明的脆壳。",
               "糖壳越薄越亮，咬下去“咔嚓”一声。"],
     "uses": ["素材_糖衣特写"]},

    {"type": "knowledge", "title": "秘密三：为什么冬天才吃糖葫芦？", "chapter": "课程引导",
     "image": "素材_冬天街景",
     "lines": ["北方冬天冷，糖浆裹上去很快就冻住，",
               "不会化、不粘手，所以成了冬天的味道。",
               "现在一年四季都有，冬天吃最有感觉。"],
     "uses": ["素材_冬天街景"]},

    {"type": "real_object", "title": "看一看：真实的糖葫芦长什么样？", "chapter": "实物观察",
     "image": "实物_糖葫芦", "image2": "实物_山楂", "img_h": 3.05, "img2_h": 1.15,
     "task_head": "观察小任务",
     "tasks": [
         {"tag": "看形状", "text": "五颗山楂都是圆圆的，差不多一样大。"},
         {"tag": "看排列", "text": "一颗挨一颗，串在一根竹签上。"},
         {"tag": "看糖衣", "text": "糖壳透明发亮，能看见里面的红。"},
         {"tag": "看芝麻", "text": "糖衣上粘着白白的小芝麻。"},
         {"tag": "摸一摸", "text": "糖壳硬硬的、滑滑的，山楂有一点软。"}],
     "uses": ["实物_糖葫芦", "实物_山楂"]},

    {"type": "materials", "title": "摸一摸：我们要用到哪些材料？", "chapter": "实物观察",
     "image": "实物_材料工具",
     "schemes": [{"head": "方案A 马克笔", "items": [
         "半生熟镜面宣纸", "黑色勾线笔",
         "红色系马克笔（大红 / 深红 / 橙红）",
         "白色高光笔", "牛皮纸色马克笔", "铅笔、橡皮"]}],
     "uses": ["实物_材料工具"]},

    {"type": "observe_tags", "title": "糖葫芦的外形有什么特点呢？", "chapter": "课程引导",
     "image": "素材_糖葫芦串",
     "tags": ["圆圆的果子", "亮亮的糖壳", "一根竹签", "红得有深有浅", "白芝麻点点", "牛皮纸小袋"],
     "uses": ["素材_糖葫芦串"]},

    {"type": "parts_diagram", "title": "糖葫芦是由哪些部分组成的呢？", "chapter": "课程引导",
     "figure_note": "圆形 + 直线 = 一串糖葫芦",
     "figure": {
         "berry5": [3.15, 2.45, 0.72, 0.72],
         "berry4": [3.36, 3.05, 0.78, 0.78],
         "berry3": [3.58, 3.68, 0.84, 0.84],
         "berry2": [3.79, 4.32, 0.90, 0.90],
         "berry1": [4.00, 4.98, 0.96, 0.96],
         "bag": [4.62, 5.80, 1.55, 0.32]},
     "parts": [
         {"name": "山楂果", "desc": "五个小圆"},
         {"name": "糖衣", "desc": "亮亮的壳"},
         {"name": "竹签", "desc": "一根直线"},
         {"name": "芝麻", "desc": "白色小点"},
         {"name": "纸袋", "desc": "装住下边"}],
     "uses": []},

    {"type": "poses", "title": "糖葫芦都有哪些不同的样子呢？", "chapter": "课程引导",
     "items": [
         {"image": "素材_糖葫芦串", "label": "竖着插"},
         {"image": "素材_小纸袋", "label": "装纸袋"},
         {"image": "素材_小朋友拿着", "label": "拿在手里"}],
     "uses": ["素材_糖葫芦串", "素材_小纸袋", "素材_小朋友拿着"]},

    {"type": "idea_list", "title": "糖葫芦还会出现在哪里呢？", "chapter": "课程引导",
     "image": "素材_冬天街景",
     "list_head": "想一想，还可以怎么画？",
     "items": ["插在草垛上", "装进小纸袋", "和好朋友一人一串",
               "靠着一只小雪人", "挂在小店的玻璃柜里"],
     "uses": ["素材_冬天街景"]},

    {"type": "color_swatches", "title": "同类色小知识 —— 红色家族", "chapter": "绘画知识",
     "swatches": [
         {"hex": "FF8A80", "name": "浅粉红", "use": "糖衣亮部"},
         {"hex": "E8452C", "name": "山楂红", "use": "果子固有色"},
         {"hex": "B32E1C", "name": "深红", "use": "暗面和果柄"},
         {"hex": "F6A623", "name": "糖色橙", "use": "糖衣透光"}],
     "note_head": "画糖葫芦的时候，不要只用一种红：",
     "note": "先用山楂红平涂，再用深红压暗面和缝隙，最后用浅粉红和白色高光提亮糖壳，果子立刻又亮又脆。",
     "uses": []},

    {"type": "text_page", "title": "涂色不脏的四个小技巧", "chapter": "绘画知识",
     "lines": [
         "① 先描边再填色：贴着黑线里面涂，不涂出格。",
         "② 平涂要一次涂满：来回涂太多遍，纸会起毛、颜色发脏。",
         "③ 高光最后画：白色高光笔点在左上角，糖衣才亮。",
         "④ 留白也是画面：果子之间留一点白纸，画面才透气。"],
     "uses": []},

    {"type": "refs", "chapter": "参考素材", "images": ["素材_糖葫芦串", "素材_糖衣特写"],
     "uses": ["素材_糖葫芦串", "素材_糖衣特写"]},
    {"type": "refs", "chapter": "参考素材", "images": ["素材_山楂特写", "素材_雪"],
     "uses": ["素材_山楂特写", "素材_雪"]},
    {"type": "refs", "chapter": "参考素材", "images": ["实物_糖葫芦", "素材_小朋友拿着"],
     "uses": ["实物_糖葫芦", "素材_小朋友拿着"]},

    {"type": "tools_dual", "title": "工 具 介 绍", "chapter": "范画过程", "title_W": 4.0,
     "schemes": [{"head": "方案A · 马克笔（推荐）", "tools": [
         {"no": "1", "name": "半生熟镜面宣纸", "desc": "纸上有纹理，颜色更柔和"},
         {"no": "2", "name": "黑色勾线笔", "desc": "勾轮廓、画竹签"},
         {"no": "3", "name": "红色系马克笔", "desc": "大红、深红、橙红各一支"},
         {"no": "4", "name": "白色高光笔", "desc": "点糖衣的高光"},
         {"no": "5", "name": "牛皮纸色马克笔", "desc": "画小纸袋"}]}],
     "uses": []},

    {"type": "step", "title": "步骤一：起 形", "chapter": "范画过程",
     "image": "范画步骤1_起形",
     "text": "先用铅笔轻轻画五个一样大的圆，排成一条斜线，像一串小灯笼；再从下往上画一根长长的竹签。",
     "tips": ["先定最下面一颗的位置，再往上排", "五颗圆要差不多大，间距要均匀",
              "铅笔线画轻一点，画错可以擦"],
     "uses": ["范画步骤1_起形"]},
    {"type": "step", "title": "步骤二：勾 线", "chapter": "范画过程",
     "image": "范画步骤2_勾线",
     "text": "用黑色勾线笔沿铅笔线描一遍，竹签要画成一条直直的实线，再给小纸袋勾出折边。",
     "tips": ["果子的圆要画得饱满，不要画成椭圆", "竹签穿过每一颗的中心",
              "先不要上色，保持画面干净"],
     "uses": ["范画步骤2_勾线"]},
    {"type": "step", "title": "步骤三：铺 色", "chapter": "范画过程",
     "image": "范画步骤3_铺色",
     "text": "五颗山楂全部涂成山楂红，纸袋涂牛皮纸色，竹签涂浅浅的米黄，颜色一定要平涂涂满。",
     "tips": ["贴着黑线里面涂，别涂出格", "果子之间留一点白，不要糊成一片",
              "纸袋用浅棕，不要比果子还重"],
     "uses": ["范画步骤3_铺色"]},
    {"type": "step", "title": "步骤四：装饰高光", "chapter": "范画过程",
     "image": "范画步骤4_装饰高光",
     "text": "每一颗山楂的左上角点一道白色高光，糖衣立刻亮起来；再撒上白芝麻，画几片淡蓝的小雪花。",
     "tips": ["高光画成小弧线，比圆点更像糖壳", "芝麻三点两点就够，不要撒满",
              "雪花用淡蓝，轻轻画在空白处"],
     "uses": ["范画步骤4_装饰高光"]},
    {"type": "step", "title": "步骤五：加背景", "chapter": "范画过程",
     "image": "范画步骤5_加背景",
     "text": "在果子下面加上淡淡的影子，纸袋旁边画一小口白色的呼气，再看一看：红的更红，白的更白。",
     "tips": ["影子要淡，用浅灰蓝", "背景的东西画小一点，别抢主角",
              "最后检查有没有漏涂的地方"],
     "uses": ["范画步骤5_加背景"]},

    {"type": "final_dual", "title": "范 画 成 品", "chapter": "范画过程",
     "hint": "这就是步骤五完成后的画面（成品与最后一步是同一张作品）",
     "items": [{"image": "范画成品", "label": "学 生 作 品"}],
     "note": "完整画面要有：五颗一样大的圆 + 一条直竹签 + 亮亮的糖衣高光 + 适当的留白。别忘记写上作品名称、签上名字哦！",
     "uses": ["范画成品"]},

    {"type": "share_summary", "chapter": "分享表达",
     "share_head": "分 享 表 达", "summary_head": "课 后 总 结",
     "share": ["1、糖葫芦的糖衣为什么会发亮？",
               "2、你画的五颗山楂，用了哪几种红？"],
     "summary": [
         "1、本节课先观察真实的糖葫芦和山楂，了解外形特征，学习用圆形和直线概括“一串”的形体，让孩子学会先看再画。",
         "2、通过糖衣高光和红色深浅，让孩子理解“亮”和“暗”是怎么画出来的，提高画面表现力。",
         "3、通过大小和间距的控制，让孩子感受排列的节奏感，完成一幅颜色饱满、干净透亮的作品。"],
     "uses": [], "title": "分享表达 + 课后总结"},
]

data = {
    "meta": {
        "name": "《糖葫芦》4-6岁课件",
        "age": "4-6岁",
        "brand": "绘课工坊",
        "brand_en": "Art Education for Kids",
        "theme": {"primary": "D93A2B", "dark": "8F2318", "light": "FFE3DC",
                  "accent": "F6A623", "text": "3B4A57", "cream": "FAF7F0", "grey": "595959"},
        "photo_note": "全部图片由 AI 生成（gpt-image-2.5），保证对题 + 可商用 + 风格统一",
    },
    "lock": LOCK,
    "common": {"stroke": STROKE},
    "images": IMAGES,
    "chain": {
        "order": ["范画成品", "范画步骤1_起形", "范画步骤2_勾线",
                  "范画步骤3_铺色", "范画步骤4_装饰高光", "范画步骤5_加背景"],
        "auto_ref_prev": True,
        "anchor": "范画成品",
        "note": "正向：成品(设计基准) → 起形(纯铅笔) → 勾线 → 铺色 → 装饰高光 → 加背景(=成品副本)",
    },
    "pages": PAGES,
}

os.makedirs(OUT, exist_ok=True)
for sub in ("img", "img_sell", "out"):
    os.makedirs(os.path.join(OUT, sub), exist_ok=True)
dst = os.path.join(OUT, "project.json")
with open(dst, "w", encoding="utf-8", newline="\n") as f:
    json.dump(data, f, ensure_ascii=False, indent=1)
print("写入", dst, "|", len(PAGES), "页 |", len(IMAGES), "图")
