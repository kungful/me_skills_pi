# -*- coding: utf-8 -*-
"""第四轮 5 个新课题 -> project.json（只跑范画链）。

媒介语言全部另起炉灶：盐画 / 毛线 / 蒙德里安几何 / 刮画 / 对称对印。
"""
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))

PAPER = ("A top-down flat photograph of one sheet of off-white rice paper on a light wooden desk, "
         "even soft daylight, the paper fills the whole frame, visible paper texture, mild realistic "
         "paper shadow. Children's art class illustration, hand-drawn, no signature, no watermark, "
         "no text.")

# ---------------- 1. 撒盐画：水彩湿画 + 盐粒晶花 ------------------------------
STROKE_SALT = (
    "MATERIAL LANGUAGE - THIS THEME IS A WATERCOLOUR SALT PAINTING (撒盐画) and this replaces the usual "
    "marker language completely for the painted areas.\n"
    "(1) WET WASH: the large colour areas are painted with a WET watercolour wash - the pigment is uneven, "
    "the edges of a wash grade from strong to almost nothing, and where two washes meet they bleed into each "
    "other and make a slightly darker soft seam. The painted areas have no outline around them at all.\n"
    "(2) SALT CRYSTALS: while the wash was still wet, fine table SALT was sprinkled over it, and the salt "
    "drank the pigment away leaving a scatter of small pale STARBURST crystal marks - tiny light-centred "
    "spikes with slightly darker pigment ridges around them, like frost blooming on glass. These crystal "
    "marks are the signature of the technique and MUST be clearly visible across every large wash.\n"
    "(3) MARKER DETAILS: all the small crisp details - the snowflake arms, the tiny stars, the dots - are "
    "drawn ON TOP of the dry wash with a clean fine marker line, one confident continuous stroke, crisp and "
    "clearly defined. No fuzzy edges, no dashes, no doubled sketchy lines.\n"
    "(4) PALETTE: {palette}. Deep enough to let the pale salt crystals read clearly against it. Never muddy, "
    "never grey, never washed-out pastel.\n"
    "(5) DECORATION: at least TWO of these - {deco}.\n"
    "(6) LIGHT: {light}\n"
    "EXCEPTION - step 1 only: loose light-grey PENCIL construction lines only, thin and faint - the snowflake "
    "arms and the small circles. No colour, no marker, no paint at all."
)

# ---------------- 2. 毛线画：毛线当线条 --------------------------------------
STROKE_YARN = (
    "MATERIAL LANGUAGE - THIS THEME IS A YARN PICTURE (毛线画): the big shapes are made from REAL YARN "
    "glued down onto the paper, and this replaces the usual flat marker fill.\n"
    "(1) YARN LINES: every large mass and every thick line is REAL YARN pressed onto the paper and glued - "
    "it is round in cross-section, so it reads as a slightly raised soft cord with a visible twist running "
    "along its length, a gentle cord shadow beneath it and a few fibres standing up along its edge. The yarn "
    "is laid in tight parallel rows, wound in a spiral, or coiled into a flat disc, and the individual winds "
    "are clearly countable.\n"
    "(2) TORN AND CUT PAPER: the fins, the tail and the small decorative shapes are simple flat pieces of "
    "coloured card glued flat with clean edges, sitting slightly raised with one soft flat shadow.\n"
    "(3) MARKER DETAIL: the eyes, the mouth, the water bubbles and the small details are drawn with a clean "
    "broad-tip black MARKER - one confident continuous solid line, crisp and clearly defined. No fuzzy "
    "edges, no dashes, no doubled sketchy lines.\n"
    "(4) COLOUR: the yarn and the card are bold high-saturation craft colours that clash happily: "
    "{palette}. Never muted, never muddy, never grey.\n"
    "(5) DECORATION: at least TWO of these - {deco}.\n"
    "(6) LIGHT: {light}\n"
    "EXCEPTION - step 1 only: a light-grey pencil sketch of where each yarn coil and each card piece will "
    "go, thin and faint, no colour and no yarn at all."
)

# ---------------- 3. 蒙德里安：黑粗线 + 三原色 --------------------------------
STROKE_MONDRIAN = (
    "PAINTING LANGUAGE - THIS THEME IS A MONDRIAN PICTURE (蒙德里安式几何绘画) and this replaces all the "
    "usual line and colour language.\n"
    "(1) THE GRID: the composition is built from straight horizontal and vertical BLACK BARS of clearly "
    "different thickness - a few very thick and heavy, some medium, some thin - crossing each other at exact "
    "right angles and running right to the edge of the shape they fill. The bars are solid flat black with "
    "clean machine-straight edges and crisp corners; they never wobble, never taper and never smudge.\n"
    "(2) THE CELLS: every rectangle enclosed by the bars is filled with ONE flat even coat of a single "
    "colour - pure primary red, pure primary yellow, pure primary blue, or pure white. Never two colours in "
    "one cell, never a gradient, never a pattern inside a cell, never a shadow. The paint is flat and matte "
    "and covers the cell edge to edge.\n"
    "(3) THE DRAWING: the child-drawn subject on top of and around the grid is drawn with ONE clean "
    "confident black marker line of even medium thickness, crisp and clearly defined with only a slight "
    "hand-drawn wobble. No fuzzy edges, no dashes, no doubled sketchy lines.\n"
    "(4) CONTRAST: the strict flat geometry of the grid must sit beside the loose hand-drawn subject so that "
    "the two languages are clearly different - that contrast is the whole point.\n"
    "(5) DECORATION: {deco}.\n"
    "(6) LIGHT: {light}\n"
    "EXCEPTION - step 1 only: loose light-grey PENCIL construction lines - the outer shape, the grid "
    "divisions and the subject - thin and faint, no black, no colour at all."
)

# ---------------- 4. 刮画：黑纸刮出彩色 --------------------------------------
STROKE_SCRATCH = (
    "MATERIAL LANGUAGE - THIS THEME IS A SCRATCH-ART PICTURE (刮画) made on a sheet of glossy BLACK scratch "
    "paper with a wooden stylus, and this replaces all the usual paper and marker language.\n"
    "(1) THE BLACK GROUND: the whole sheet is a solid velvety BLACK scratch board. Anything that has not "
    "been scratched away stays pure dense black with a soft matte sheen - the black is not ink on white "
    "paper, it is the paper itself, and it fills every part of the frame that the drawing does not occupy.\n"
    "(2) SCRATCHED LINES: everything drawn has been SCRATCHED through the black layer, so each line is a "
    "narrow groove revealing the bright colour underneath. Every scratched line has slightly rough, scraped, "
    "brittle edges with a faint ridge of black dust along it - this is essential, it is what proves the line "
    "was scratched and not drawn. Lines are crisp, confident and continuous, of clearly varying thickness.\n"
    "(3) THE COLOUR UNDERNEATH: the revealed colour is bright and multi-hued - each scratched stroke may "
    "show a different hue along its length, {palette}, because the board is printed with rainbow foil "
    "underneath the black.\n"
    "(4) NO FILL: nothing is flooded with colour; the picture is made purely of scratched lines and "
    "scratched texture on black, with the untouched black ground carrying the negative space. Hatched and "
    "cross-hatched scratched areas are used to make darker tonal patches.\n"
    "(5) DECORATION: at least TWO of these - {deco}.\n"
    "(6) LIGHT: {light}\n"
    "EXCEPTION - step 1 only: a light chalk-white construction sketch traced thinly onto the black board - "
    "the mushroom caps, the stems, the windows, the ground line - faint and loose, no scratched colour yet."
)

# ---------------- 5. 对折对印：镜像压印 --------------------------------------
STROKE_MIRROR = (
    "MATERIAL LANGUAGE - THIS THEME IS A FOLD-AND-PRINT PICTURE (对折对印): the wings were painted on one "
    "half of a folded sheet, the sheet was closed and pressed, and opening it produced a perfectly mirrored "
    "print on the other half, which was then finished with marker drawing.\n"
    "(1) PERFECT MIRROR: every blob of colour on the left wing has an EXACT mirror-image twin on the right "
    "wing, the same shape flipped, the same size, the same distance from the centre line. The two halves obey "
    "mirror symmetry perfectly about the vertical fold line.\n"
    "(2) PRINTED BLOTS: each colour patch is a soft organically spreading printed stain - the pigment has "
    "crept outward from where it was pressed, so patch edges are gently irregular, feathered and slightly "
    "translucent, with a faint darker rim where the stain stopped and a few delicate radiating spurs where "
    "the pigment pushed into the paper fibres. Blots sometimes overlap and mix into a third colour at the "
    "join. This is a pressed-paint texture, never a drawn shape.\n"
    "(3) MARKER FINISHING: the body, the antennae, the legs and all small crisp details are drawn after the "
    "print with ONE clean confident black marker line of even medium thickness, crisp and clearly defined "
    "with only a slight hand-drawn wobble. No fuzzy edges, no dashes, no doubled sketchy lines.\n"
    "(4) GAPS: the printed halves do not touch in places - there is a visible sliver of bare paper running "
    "down the fold line itself, plus small unpainted gaps, which is exactly what a real fold-and-print looks "
    "like.\n"
    "(5) PALETTE: {palette}, bright and translucent. Never muddy, never grey.\n"
    "(6) DECORATION: at least TWO of these - {deco}.\n"
    "(7) LIGHT: {light}\n"
    "EXCEPTION - step 1 only: a faint light-grey PENCIL fold line down the exact centre of the sheet and a "
    "loose outline of the butterfly on the left half only, thin and faint, no colour at all."
)

SPECS = {}
_ = SPECS.__setitem__

# =====================================================================
# 1. 撒盐画雪花 —— 爆款：3岁撒盐画绝美雪花 1149赞 / 撒盐法蒲公英 459赞
# =====================================================================
_("撒盐画雪花", dict(
    formula="盐粒吸色 + 水彩湿画（撒盐画雪花 1149赞 / 撒盐法蒲公英 459赞）",
    palette="deep night indigo, prussian blue, violet, teal and a little magenta",
    deco="pale crystal starbursts blooming in every wash, small white sparkle dots, and fine marker snowflake "
         "arms with short side-branches",
    light="the light comes from the UPPER LEFT; each snowflake is rimmed on its upper left with a soft pale "
          "halo of lift-off, and casts one soft flat shadow on the paper",
    stroke=STROKE_SALT,
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "the whole sheet is covered by one continuous deep WET night wash in deep night indigo, prussian blue "
        "and violet, with the wash grading darker at the very top and edges and lighter in the middle, and "
        "salt crystals scattered densely all over it. In the centre floats ONE big six-armed snowflake, drawn "
        "with fine marker lines and covered in pale crystal starbursts, its six arms each carrying two short "
        "side-branches and a small diamond at the tip. Around it float FIVE smaller snowflakes of clearly "
        "different sizes - one hexagonal, one five-armed, one made of small dots, one a simple star and one "
        "very tiny one - all in the same pale lift-off white. A scatter of small white sparkle dots and a few "
        "short marker star crosses fill the empty night between them. The bottom edge of the paper carries a "
        "low soft snowdrift line, lighter than the sky."),
    finish=(
        "The finished artwork: one big pale six-armed snowflake floating in the centre of a deep wet night "
        "wash of indigo, prussian blue and violet, with five smaller snowflakes of different sizes around it, "
        "and the whole night broken up by hundreds of pale starburst salt crystals blooming out of the wash. "
        "Fine marker snowflake arms with short side-branches, small white sparkle dots and short star crosses, "
        "a lighter snowdrift line along the bottom, and one soft flat shadow under each snowflake. Rich, "
        "magical, completely finished, nothing left unfinished."),
    s1=(
        "THIS IS STEP 1 OF 5 - the light pencil scaffolding, and NOTHING else. In faint thin light-grey pencil "
        "draw one big six-armed snowflake in the centre, each arm with two short side-branches and a small "
        "diamond tip; then draw five smaller light snowflake outlines of clearly different sizes and shapes "
        "around it - a hexagon, a five-armed star, a ring of small dots, a simple star and one tiny one. Draw "
        "one light wavy line across the bottom for the snowdrift. Simple, loose, faint construction lines "
        "only - no colour, no paint, no salt, no marker."),
    s2=(
        "THIS IS STEP 2 OF 5 - the wet night wash. With a big soft brush paint the whole sheet with one "
        "continuous wet watercolour wash in deep night indigo, prussian blue and violet, letting the colours "
        "bleed into each other and leaving the wash grading darker at the very top and edges and lighter "
        "through the middle, with the pale snowflake shapes still readable as lift-off areas. The wash must "
        "stay WET and uneven, with soft bleeding edges and no outline anywhere. Do not paint any marker "
        "lines, do not draw the snowflake details, and do not add the salt yet."),
    s3=(
        "THIS IS STEP 3 OF 5 - the salt. While the wash is still visibly WET, sprinkle fine table salt "
        "liberally across the whole painted night and let it sink in: the salt drinks the pigment away and "
        "leaves a dense scatter of small pale STARBURST crystal marks - tiny light-centred spikes with "
        "slightly darker pigment ridges around them, like frost blooming on glass. Spread the crystals all "
        "across the night, some clustered tightly and some alone, and let them break the wash up beautifully. "
        "Do not brush or touch the salt. Nothing else is added in this step."),
    s4=(
        "THIS IS STEP 4 OF 5 - the marker details on top of the dry wash. Now take the fine marker and draw "
        "the snowflakes in clean pale white marker lines: the big central snowflake's six arms with two short "
        "side-branches and a small diamond tip on each, and the five smaller snowflakes in their own "
        "different styles - a hexagon, a five-armed star, a ring of small dots, a simple star and one tiny "
        "snowflake. Add small white sparkle dots and short star crosses across the night between them. Then "
        "paint the low snowdrift band lighter along the bottom edge. Nothing else changes - the wash and the "
        "salt crystals stay exactly as they are."),
    pages={20: ("步骤一：起 形", "铅笔先画中间一片大雪花的六根枝条，再在四周点上五片大小不一样的雪花。"),
           21: ("步骤二：铺夜空", "大笔蘸深蓝和紫色，把整张纸涂湿，颜色让它自己化开，上面深、中间浅。"),
           22: ("步骤三：撒 盐", "趁颜料还湿，手指捏盐往上一撒——盐会把颜色喝掉，留下一颗颗亮晶晶的小花。"),
           23: ("步骤四：画雪花", "颜料干透后，用白色笔把六根枝条和两边小枝描清楚，四周撒小白点。"),
           24: ("步骤五：加背景", "底下加一条浅色的雪坡，每片雪花留一点淡淡的光，夜空就亮起来了。")},
    real2=["真实的盐粒", "水彩颜料"],
    scenes=["盐粒特写", "水彩和盐", "雪花形状", "下雪的夜晚", "窗上的冰花", "深蓝夜空", "小朋友撒盐"],
))

# =====================================================================
# 2. 毛线小鱼 —— 爆款：毛线+纸壳彩色小鱼 3705赞 / 蛋糕盘毛线水母 1085赞
# =====================================================================
_("毛线小鱼", dict(
    formula="毛线当线条（毛线+纸壳小鱼 3705赞 / 蛋糕盘毛线水母 1085赞）",
    palette="tomato red, sunny yellow, turquoise, violet, lime green and cream",
    deco="tight parallel yarn rows, a coiled yarn disc, short yarn dashes as small fish, and marker bubbles "
         "and wavy water lines",
    light="the light comes from the UPPER LEFT; every yarn coil and every card piece sits slightly raised and "
          "casts one soft FLAT grey-blue shadow on the paper below it",
    stroke=STROKE_YARN,
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "ONE big cheerful fish fills the centre of the paper, facing left, its whole body wound over with REAL "
        "YARN - tight parallel rows of tomato red and sunny yellow yarn following the curve of the body, with "
        "the winds clearly countable. Its large tail fin and its top and bottom fins are flat pieces of "
        "coloured card glued on - turquoise and violet - and they stick out clearly beyond the yarn body. It "
        "has one very big round white paper eye with a solid black pupil and a white glint, a small smiling "
        "marker mouth, and three short yarn whiskers beside the mouth. THREE much smaller fish swim around it "
        "- one above to the left made of a coiled turquoise yarn disc, one below to the right in lime green, "
        "and the smallest behind the tail in violet. The water is made of marker only: five wavy horizontal "
        "water lines across the background, a scatter of small round bubbles rising in twos and threes, and "
        "two small bunches of green waterweed along the bottom edge."),
    finish=(
        "The finished artwork: one big cheerful fish wound all over with tight parallel rows of tomato red and "
        "sunny yellow yarn, with turquoise and violet card tail and fins sticking out beyond the body, a big "
        "round white paper eye with a black pupil and white glint, a smiling marker mouth and three yarn "
        "whiskers. Three smaller fish - a coiled turquoise yarn disc, a lime green one and a violet one - swim "
        "around it, with five wavy marker water lines, scattered bubbles and two bunches of waterweed. Every "
        "yarn coil sits raised with its own cord shadow, the card fins cast flat shadows, and the whole "
        "picture is bright, bold and completely finished."),
    s1=(
        "THIS IS STEP 1 OF 5 - the light pencil scaffolding, and NOTHING else. In faint thin light-grey pencil "
        "draw one big fish outline in the centre facing left - a rounded body, a wide tail fin and a top and "
        "bottom fin; draw a big light circle for its eye; then draw three small light fish outlines around it "
        "- one up to the left, one down to the right and one small one behind the tail. Draw five light wavy "
        "lines across the paper for the water and two light tufts along the bottom for the waterweed. Simple, "
        "loose, faint construction lines only - no yarn, no colour, no marker."),
    s2=(
        "THIS IS STEP 2 OF 5 - the yarn body. Keep every pencil guide exactly where it is and now lay the REAL "
        "YARN: wind tight parallel rows of tomato red and sunny yellow yarn across the whole body of the big "
        "fish, following the curve of the body from nose to tail, pressing each wind down so the rows sit "
        "side by side and the individual winds are clearly countable - the yarn is a raised round cord with a "
        "visible twist, a soft cord shadow beneath it and a few fibres standing up along its edge. Fill the "
        "whole body to its outline. Leave the big eye circle as bare paper, and do not add the fins, the other "
        "fish or the water yet."),
    s3=(
        "THIS IS STEP 3 OF 5 - the fins and the small fish. Nothing about the wound yarn body changes. Now "
        "glue the flat card fins onto the big fish: a wide turquoise tail fin, a violet top fin and a "
        "turquoise bottom fin, each a simple flat card piece with clean edges sticking out clearly beyond the "
        "yarn body and casting its own soft flat shadow. Then build the three small fish: the upper left one "
        "as a tight coiled disc of turquoise yarn wound round and round in a spiral, the lower right one as a "
        "small lime green yarn body wound in parallel rows with a small card tail, and the smallest one behind "
        "the tail as a short violet yarn fish. No marker drawing yet."),
    s4=(
        "THIS IS STEP 4 OF 5 - the marker details, the step that makes it come alive. With the clean black "
        "marker draw the big fish's eye as one very big round white paper circle with a solid black pupil and "
        "a white glint, plus a small smiling mouth line and three short whisker strokes beside it. Give each "
        "small fish a small round eye and a tiny smile, and draw a short fin line on each. Then draw the "
        "water: five wavy horizontal marker water lines across the background, a scatter of small round "
        "bubbles rising in twos and threes, and two small bunches of green waterweed along the bottom edge. "
        "Nothing else changes - the yarn, the card and the layout stay exactly as they are."),
    pages={20: ("步骤一：起 形", "铅笔先画一条大鱼的身体、尾巴和上下鳍，再在周围画三条小鱼和几道水波。"),
           21: ("步骤二：绕 毛 线", "毛线一圈一圈挨着绕，把大鱼的身体绕满——数一数绕了多少圈！"),
           22: ("步骤三：贴鳍和小鱼", "卡纸剪出尾巴和鳍贴上去，再用毛线卷成一个小圆盘当小鱼的身体。"),
           23: ("步骤四：画眼睛添画", "黑笔画大眼睛和小嘴巴，加三道胡须，再画水波、泡泡和水草。"),
           24: ("步骤五：加背景", "每条鱼底下加一小块影子，泡泡点一点白高光，水里的鱼就游动了。")},
    real2=["真实的毛线", "彩色卡纸"],
    scenes=["毛线团", "毛线绕线的手", "鱼缸里的鱼", "小丑鱼特写", "鱼鳍和鱼鳞", "水和泡泡", "小朋友绕毛线"],
))

# =====================================================================
# 3. 蒙德里安的花瓶 —— 爆款：蒙德里安的瓶子 478赞 / 红黄蓝的构成
# =====================================================================
_("蒙德里安的花瓶", dict(
    formula="艺术流派改编 + 黑粗线三原色格子（蒙德里安的瓶子 478赞 / 红黄蓝的构成）",
    palette="pure primary red, pure primary yellow, pure primary blue, pure white and flat black",
    deco="black grid bars of clearly different thicknesses crossing at exact right angles, one small grid "
         "block repeated as a little patch in the background, and short black tick marks along the table line",
    light="the light comes from the UPPER LEFT; the vase and the flowers cast one simple FLAT grey-blue "
          "shadow on the table line, drawn as a solid flat shape",
    stroke=STROKE_MONDRIAN,
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "the clean silhouette outline of ONE tall vase stands centred on the paper, and its whole interior is "
        "divided by straight BLACK BARS of clearly different thicknesses crossing at exact right angles into "
        "rectangular cells of very different sizes, every cell filled with one flat coat of pure primary red, "
        "pure primary yellow, pure primary blue or pure white - never a pattern, never a gradient. The vase "
        "has a narrow neck, a round belly and a small foot, and the grid inside it follows the outside shape "
        "without breaking out. From the vase mouth rise THREE flowers, and these are drawn in the opposite "
        "language: loose, hand-drawn, wobbly black marker lines - one big round daisy with a dotted centre, "
        "one tulip bell and one small five-petal blossom, each on its own curved stem with two simple leaves. "
        "To the RIGHT of the vase floats one small separate patch of the same black-bar grid with three cells "
        "filled red, yellow and blue. A single straight black table line runs across the paper behind the "
        "vase foot with short black tick marks along it, and the rest of the sheet stays bare off-white."),
    finish=(
        "The finished artwork: one tall hand-drawn vase whose whole interior is a strict Mondrian grid of "
        "thick and thin straight black bars crossing at right angles, the cells filled with flat primary red, "
        "primary yellow, primary blue and white; three loose hand-drawn wobbly flowers - a big daisy with a "
        "dotted centre, a tulip and a small five-petal blossom - rising from the mouth on curved green stems "
        "with simple leaves; a small separate red-yellow-blue grid patch floating to the right; a straight "
        "black table line with tick marks; and one flat grey-blue shadow under the vase. The strict geometry "
        "and the loose hand drawing sit side by side in clear contrast. Completely finished, crisp and bold."),
    s1=(
        "THIS IS STEP 1 OF 5 - the light pencil scaffolding, and NOTHING else. In faint thin light-grey pencil "
        "draw the clean silhouette of one tall vase - narrow neck, round belly, small foot - then divide its "
        "interior with light straight horizontal and vertical lines into rectangles of clearly different "
        "sizes, at exact right angles. Draw light circles for three flowers rising from the mouth, one curved "
        "line for each stem and two ovals for the leaves. Draw one light small square divided into three at "
        "the right of the vase and one light straight line across the paper for the table. Simple, loose, "
        "faint construction lines only - no black, no colour, no grid yet."),
    s2=(
        "THIS IS STEP 2 OF 5 - the black bars. Now draw the grid with solid flat black bars: trace every "
        "division inside the vase in black, but make the bars of clearly DIFFERENT thicknesses - a few very "
        "thick and heavy, some medium and some thin - crossing each other at exact right angles and running "
        "right up to the vase outline. The bars have clean machine-straight edges and crisp corners and never "
        "wobble. Also draw the small three-cell grid patch to the right of the vase in the same black bars, "
        "and the straight black table line with its short tick marks. Leave every cell empty for now."),
    s3=(
        "THIS IS STEP 3 OF 5 - the primary colour cells. Fill every rectangle enclosed by the bars on the vase "
        "with ONE flat even coat of a single colour: pure primary red, pure primary yellow, pure primary blue "
        "or pure white, one colour per cell and no colour used twice in a row, spreading the three colours and "
        "the white generously across the vase. Flat matte paint, edge to edge, covering the cell completely - "
        "never a gradient, never a pattern inside a cell, never a shadow. Fill the three cells of the small "
        "grid patch to the right in red, yellow and blue too. Nothing else is painted in this step - the "
        "flowers and the leaves stay bare paper."),
    s4=(
        "THIS IS STEP 4 OF 5 - the flowers, in the opposite language. Now, on purpose, switch hands: draw the "
        "three flowers rising from the vase mouth with loose, wobbly, hand-drawn black marker lines - one big "
        "round daisy with a ring of small dots for its centre, one tulip bell and one small five-petal "
        "blossom - each on its own curved stem with two simple leaves. Keep the strokes deliberately uneven "
        "and childish, quite different from the strict grid bars below. Colour the petals with flat primary "
        "red and yellow and the stems and leaves with a simple green, then add one or two pure white highlight "
        "dots to the flower centres and to the vase. Nothing else changes."),
    pages={20: ("步骤一：起 形", "铅笔先画一个高高的花瓶，再用直尺轻轻把瓶身分成大大小小的方格。"),
           21: ("步骤二：画黑格子", "黑笔把格子线描出来——有的粗有的细，全部横平竖直，一格都不能歪。"),
           22: ("步骤三：涂三原色", "格子里只准涂红、黄、蓝和白，一格一个颜色，涂平涂满。"),
           23: ("步骤四：画花", "换一种画法：花朵故意画得歪歪扭扭，和规规矩矩的格子形成对比。"),
           24: ("步骤五：加背景", "右边加一小块红黄蓝格子，底下画一条桌沿，花瓶底下加一块影子。")},
    real2=["蒙德里安的作品", "直尺和黑笔"],
    scenes=["蒙德里安画作", "红黄蓝三原色", "几何格子", "花瓶和花", "雏菊", "郁金香", "小朋友用直尺"],
))

# =====================================================================
# 4. 刮画蘑菇城堡 —— 爆款：闪闪刮画蘑菇城堡 398赞
# =====================================================================
_("刮画蘑菇城堡", dict(
    formula="刮画（黑纸刮出彩色）（闪闪刮画蘑菇城堡 398赞）",
    palette="rainbow foil showing magenta, orange, yellow, green, cyan and violet along the scratched strokes",
    deco="hatched and cross-hatched scratched shading patches, small scratched star sparkles, and short "
         "scratched grass strokes along the ground line",
    light="the light comes from the UPPER LEFT; the dark side of every mushroom cap and the underside of "
          "every roof is shaded with denser scratched hatching, so the forms read three-dimensionally "
          "against the black",
    stroke=STROKE_SCRATCH,
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "on a solid black scratch board, a cheerful MUSHROOM CASTLE stands centred on a low ground line. The "
        "castle is built from THREE big mushrooms of clearly different heights - a tall central mushroom with "
        "a wide domed cap, a medium one on the left with a rounder cap and a small one on the right - and "
        "each mushroom cap carries a different scratched pattern (rows of dots, a chevron zig-zag and a grid "
        "of small squares) with a few small scratched star sparkles on it. Each mushroom stem has a small "
        "arched door at its base and TWO little round windows with cross mullions above the door, and the "
        "tallest one has a thin wavy wisp of scratched smoke rising from a tiny chimney on its cap. A low "
        "wavy ground line runs across the bottom with short scratched grass strokes standing up from it, and "
        "three small mushrooms grow along the ground at the left and right. The upper half of the board is "
        "left as untouched black night, broken only by a scatter of small scratched star sparkles and one "
        "thin scratched crescent moon. Everything drawn is scratched through the black and every scratched "
        "line shows bright rainbow foil colour underneath."),
    finish=(
        "The finished artwork: a cheerful mushroom castle scratched out of a solid black board - three "
        "mushrooms of different heights, each cap carrying a different scratched pattern (dots, chevrons and "
        "a square grid) and star sparkles, each stem with an arched door and two round cross-mullioned "
        "windows, and a thin wisp of smoke from a chimney on the tallest cap. A wavy ground line with short "
        "scratched grass strokes runs across the bottom with three small mushrooms along it, and the black "
        "upper half carries a scatter of scratched star sparkles and one thin crescent moon. Every line is a "
        "scratched groove with rough scraped edges revealing bright rainbow foil colour, dense hatched "
        "shading shapes the dark sides, and the untouched black ground carries all the negative space. "
        "Magical, completely finished, nothing left unfinished."),
    s1=(
        "THIS IS STEP 1 OF 5 - the chalk scaffold only. On the black scratch board, in faint thin chalk-white "
        "line, sketch exactly where everything will go: three mushroom outlines of clearly different heights "
        "across the middle - a tall wide-capped one in the centre, a medium rounder one on the left and a "
        "small one on the right; a small arched door and two small round windows at the base of each stem; a "
        "tiny chimney on the tallest cap; a wavy ground line across the bottom; and three small light "
        "mushroom outlines along that line. Faint, thin and loose - nothing has been scratched yet, there is "
        "no colour and no detail at all."),
    s2=(
        "THIS IS STEP 2 OF 5 - the main scratched contours. Now scratch the big shapes through the black layer "
        "with the stylus: the full outline of all three mushroom caps and their stems, the small mushrooms "
        "along the ground line, the arched doors and the round windows with their cross mullions, the tiny "
        "chimney, and the wavy ground line itself with short grass strokes standing up from it. Every "
        "scratched line is a clean confident continuous groove revealing bright rainbow foil colour beneath, "
        "with slightly rough scraped edges, and the line thickness varies clearly between the outlines and "
        "the small details. Nothing is filled in yet and no patterns are added."),
    s3=(
        "THIS IS STEP 3 OF 5 - the patterns and the shading. Keep every scratched contour exactly where it is "
        "and add the pattern work: give each of the three caps a different scratched pattern - rows of dots "
        "on the tall central cap, a chevron zig-zag band on the left cap and a grid of small squares on the "
        "right cap. Then shade the forms: fill the dark side of every cap, the underside of every cap rim and "
        "the shaded side of every stem with dense parallel hatched scratched lines, and cross-hatch the "
        "deepest parts more heavily so they read almost black again. Scratch a few star sparkles on the caps. "
        "No night sky yet, no smoke yet."),
    s4=(
        "THIS IS STEP 4 OF 5 - the night sky and the finishing scratches, the step that makes it come alive. "
        "Add the thin wavy wisp of scratched smoke rising from the tiny chimney on the tallest cap with two "
        "small curls. Then scratch the night: a scatter of small star sparkles of clearly different sizes "
        "across the whole black upper half, several drawn as four-point crosses and several as simple dots, "
        "plus one thin scratched crescent moon in the upper right. Add a few short scratched sparkle marks "
        "between the mushrooms near the ground. Nothing else changes - the black ground around everything "
        "stays untouched black."),
    pages={20: ("步骤一：起 形", "黑纸不好画，先用粉笔轻轻勾出三个大蘑菇、门窗和一条地面线。"),
           21: ("步骤二：刮大形", "竹签刮出蘑菇的外形、门窗和地面线——刮开黑色，底下是彩色！"),
           22: ("步骤三：刮花纹阴影", "每个蘑菇盖刮一种花纹，再排线刮出暗面，蘑菇一下子就鼓起来了。"),
           23: ("步骤四：刮夜空", "烟囱刮出一缕烟，天上刮小星星和一个月亮，黑的地方留着不刮。"),
           24: ("步骤五：加背景", "地面上刮几丛小草，蘑菇之间补几颗小亮点，闪闪的蘑菇城堡就完成了。")},
    real2=["真实的蘑菇", "刮画竹签"],
    scenes=["蘑菇特写", "森林里的蘑菇", "蘑菇伞盖花纹", "刮画工具", "黑色刮画纸", "夜空星星", "小朋友刮画"],
))

# =====================================================================
# 5. 对折印蝴蝶 —— 爆款：对称的美 564赞
# =====================================================================
_("对折印蝴蝶", dict(
    formula="对折对印 + 镜像对称（小学美术《对称的美》564赞）",
    palette="magenta pink, tangerine orange, lemon yellow, turquoise, violet and a little crimson",
    deco="soft printed stain spurs radiating from each blot edge, a few overlapping blots mixing into a third "
         "colour, and small black marker dots and short dashes along the wing edges",
    light="the light comes from the UPPER LEFT; the butterfly casts one simple FLAT grey-blue shadow on the "
          "paper and nobody is holding anything",
    stroke=STROKE_MIRROR,
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "ONE big butterfly fills the centre of the paper, opened flat, and it is PERFECTLY MIRROR-SYMMETRICAL "
        "about the vertical line down its own body. The left and right wings are the same shape in mirror "
        "image, and the colour on them is a set of soft pressed-paint blots: three large overlapping blots in "
        "each wing arranged in the same mirrored order - a magenta pink blot nearest the body, a tangerine "
        "orange one in the middle and a turquoise one towards the outer tip - plus a lemon yellow blot near "
        "the top edge and a violet one near the bottom edge, each blot with its exact twin on the other wing. "
        "The blots spread softly with irregular feathered edges, faint darker rims and delicate radiating "
        "spurs, and where two blots overlap they mix into a third colour. A narrow sliver of bare paper runs "
        "down the centre fold line between the two wings. The butterfly's body is a slim black marker shape of "
        "three stacked segments with two long antennae curving up and ending in small curls, and six thin "
        "black legs. Small black marker dots and short dashes run along the outer edges of all four wings, "
        "mirrored exactly. The rest of the sheet stays bare off-white paper apart from the butterfly's single "
        "soft flat shadow."),
    finish=(
        "The finished artwork: one big butterfly opened flat and filling the sheet, perfectly mirror-"
        "symmetrical about the vertical fold line down its body. Each wing carries the same set of soft "
        "pressed-paint blots in mirrored positions - magenta pink nearest the body, tangerine orange in the "
        "middle, turquoise at the outer tip, lemon yellow near the top edge and violet near the bottom edge - "
        "each blot spreading with irregular feathered edges, a faint darker rim and delicate radiating spurs, "
        "with overlaps mixing into a third colour. A sliver of bare paper runs down the fold line. A slim "
        "black marker body of three stacked segments with two long curled antennae and six thin legs, and "
        "small black dots and short dashes mirrored exactly along all four wing edges. Bright, translucent, "
        "completely finished, nothing left unfinished."),
    s1=(
        "THIS IS STEP 1 OF 5 - the light pencil scaffolding, and NOTHING else. In faint thin light-grey pencil "
        "draw one straight vertical FOLD LINE down the exact centre of the sheet. On the LEFT half only, draw "
        "a large butterfly wing outline - a big rounded upper wing and a smaller rounded lower wing - plus "
        "three light circles and two light ovals inside it where the blots will go. Draw a slim light "
        "three-segment body shape straddling the fold line, two light curved antennae and six thin light leg "
        "lines. Leave the right half completely empty - it will be produced by the fold. Simple, loose, faint "
        "construction lines only - no colour, no marker."),
    s2=(
        "THIS IS STEP 2 OF 5 - the fold and print. This is the printed step: load a brush with wet paint and "
        "place the blots ONLY on the LEFT wing inside the pencil circles - a large magenta pink blot nearest "
        "the body, a large tangerine orange blot in the middle and a large turquoise blot towards the outer "
        "tip, plus a lemon yellow blot near the top edge and a violet one near the bottom edge - then fold "
        "the sheet closed along the centre line and press it flat so that the paint transfers and produces an "
        "exactly mirrored copy of every blot on the RIGHT wing. Open the sheet: both wings now carry the same "
        "set of soft spreading blots with irregular feathered edges, faint darker rims and delicate radiating "
        "spurs, overlapping into third colours where they meet, with a narrow sliver of bare paper left along "
        "the fold line. Do not add any marker drawing yet."),
    s3=(
        "THIS IS STEP 3 OF 5 - the marker finishing. Nothing about the printed blots changes. With the clean "
        "black marker draw the butterfly: the slim body of three stacked segments sitting exactly on the fold "
        "line, two long antennae curving up from the head and ending in small curls, and six thin legs "
        "stepping out to the sides. Draw the outer edge of all four wings as one clean confident continuous "
        "line following the printed blot silhouette. Keep the left and right sides exactly mirrored. Clean "
        "crisp marker lines only - no new paint."),
    s4=(
        "THIS IS STEP 4 OF 5 - the edge decoration and highlights, the step that makes it come alive. Run "
        "small black marker dots and short dashes along the outer edges of all four wings, mirroring each "
        "dot exactly on the other side, and add a small black ring around the two small clear patches inside "
        "each wing. Then add a few pure white highlight dots and short white arcs on the printed blots, again "
        "mirrored exactly. Scatter three small flying dots of magenta and yellow paint in the bare paper "
        "around the butterfly. Nothing else changes - the printed blots, the fold line and the layout stay "
        "exactly as they are."),
    pages={20: ("步骤一：起 形", "铅笔在纸的中间画一条竖线，只在左半边画出蝴蝶的翅膀和几个圆点。"),
           21: ("步骤二：对折对印", "左翅膀涂上湿湿的颜料，把纸对折压一压，打开——右翅膀自己长出来了！"),
           22: ("步骤三：勾身体", "黑笔画出身体、触角和六条腿，再沿着印出来的色块描一圈翅膀边。"),
           23: ("步骤四：点装饰高光", "翅膀边上点小圆点和小短线，色块上点白高光，左右两边要一模一样。"),
           24: ("步骤五：加背景", "周围撒几点颜料小点，蝴蝶底下加一块影子——对称的蝴蝶就飞起来了。")},
    real2=["真实的蝴蝶", "水彩颜料和折纸"],
    scenes=["蝴蝶翅膀对称", "蝴蝶特写", "对折压印的手", "水彩颜料盘", "花园里的蝴蝶", "漂亮的翅膀花纹", "小朋友打开对折纸"],
))
