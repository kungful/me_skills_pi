# -*- coding: utf-8 -*-
"""批量把 9 个新课题写进各自 project.json（本轮只跑范画链 6 张）。

每个课题挂一条小红书爆款公式（都带赞数背书），公共线条语言沿用《爆米花蹦蹦跳》
那套已经跑通过的 DNA，只替换「配色 / 装饰语汇 / 光 / 构图锁 / 四步提示词」。
"""
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))

PAPER = ("A top-down flat photograph of one sheet of off-white rice paper on a light wooden desk, "
         "even soft daylight, the paper fills the whole frame, visible paper texture, mild realistic "
         "paper shadow. Children's art class illustration, hand-drawn, flat poster colours, thick clean "
         "outlines, no signature, no watermark, no text.")

STROKE = (
    "LINE, COLOUR AND DECORATION LANGUAGE - one single clean hand is used for the whole sequence, the "
    "finished artwork and every step alike, with no variation whatsoever.\n"
    "(1) OUTLINE: every contour is ONE clean, confident, CONTINUOUS SOLID LINE of even medium thickness, drawn "
    "with a broad-tip children's MARKER pen. The line runs unbroken from start to finish; edges are crisp and "
    "clearly defined, like a hand-drawn clean outline, with only a slight natural wobble that shows a child drew "
    "it by hand. No hairy or fuzzy broken edges, no contour that frays into short furry strokes, no dashes or "
    "dotted outlines, no sketchy doubled lines, no overshooting strokes, no thin scratched pencil texture, no "
    "crayon rubbing or smudging, no colour bleeding across the outline.\n"
    "(2) COLOUR: high-saturation flat poster colour, sitting flat INSIDE its outline, evenly covered edge to "
    "edge. Never a gradient, never grainy, never blended, never airbrushed. The palette is BOLD and cheerful and "
    "the colours must CLASH happily: {palette}, on the bare off-white paper. Never muted, never muddy, never "
    "grey, never beige-toned, never washed-out pastel.\n"
    "(3) HIGHLIGHTS: every rounded volume carries ONE or TWO pure WHITE highlight dots or a short white arc - "
    "this is what makes the picture look shiny. Never omit the highlights on anything round.\n"
    "(4) DECORATION: at least TWO of these decorative vocabularies must appear somewhere in the picture - "
    "{deco}.\n"
    "(5) LIGHT: {light}\n"
    "EXCEPTION - step 1 only: that stage is the initial light pencil scaffolding - loose light-grey pencil "
    "construction lines, thin and faint, simple circles, ovals and blocky shapes, no marker and no colour at "
    "all. From step 2 onward, and in the finished artwork, the drawing is in the clean marker language above."
)

SPECS = {}
_ = SPECS.__setitem__
_("树叶逃跑啦", dict(
    formula="拟人+集体出逃（胡萝卜出逃 3199赞 / 瓜子逃跑啦 1239赞）",
    palette="maple red, amber yellow, pumpkin orange, coral pink and leaf green",
    deco="one clean leaf vein line with short side branches, curved speed arcs behind the running leaves, "
         "small flying dots and short hatch lines inside the leaf shapes",
    light="the light comes from the UPPER LEFT; every leaf and every speck casts one simple FLAT grey-blue "
          "shadow on the paper, drawn as a solid flat shape",
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion "
        "changes: FIVE anthropomorphic autumn leaves run in single file from the LOWER LEFT towards the UPPER "
        "RIGHT, all caught mid-stride; each leaf has TWO big round black eyes with a white glint, a small open "
        "smiling mouth, two pink cheek dots, two little stick arms swinging and two little legs running; every "
        "leaf is a DIFFERENT species and a DIFFERENT colour - a big maple leaf in the lead, then an oval beech "
        "leaf, then a pointed oak leaf, then a round ginkgo fan leaf, and smallest at the back a long willow "
        "leaf; the leading maple leaf is leaping, both legs off the ground; behind the last leaf a loose bundle "
        "of grey-blue curved WIND lines chases them; THREE tiny leaves are blown up into the air on the right; "
        "a simple flat pale-yellow GROUND line runs along the bottom; a small friendly sun with a smiling face "
        "sits in the UPPER LEFT corner; the running line of leaves fills the paper diagonally while the two "
        "lower corners stay empty. "),
    finish=(
        "THIS IS THE FINISHED MASTER ARTWORK of the lesson, drawn at its very best. Everything is complete: the "
        "five leaves are flat-filled in five different bold colours (maple in maple red, beech in amber yellow, "
        "oak in pumpkin orange, ginkgo in coral pink, willow in leaf green), each with a single clean vein line "
        "and a white highlight arc; all eyes are solid black with one white glint and the cheeks are coral pink; "
        "the three airborne leaves are flat-filled too; the wind bundle is drawn in grey-blue with white "
        "sparkle tips; the ground line is flat pale yellow. Decorative layer complete: small flying dots, tiny "
        "four-point star sparkles and short speed arcs trail the runners, and one or two short hatch lines sit "
        "inside each leaf. A soft flat grey-blue shadow lies under every leaf that touches the ground. Large "
        "calm areas of bare off-white paper remain in the two lower corners so the picture breathes. Finished, "
        "joyful, full of motion."),
    s1=(
        "THIS IS STEP 1 OF 5, the very first construction sketch, and it is DRAWN ONLY IN LIGHT GREY PENCIL - no "
        "marker, no ink, no colour anywhere. Faint thin pencil construction lines only: five loose leaf "
        "silhouettes spaced along one rising diagonal from the lower left to the upper right, each built from a "
        "simple oval or a fan of arcs; inside every leaf two small circles for the eyes, one small oval for the "
        "mouth and four tiny sausage shapes for the arms and legs; three or four long sweeping curves behind the "
        "last leaf for the wind; three tiny leaf outlines floating on the right; one straight line near the "
        "bottom for the ground; one circle with short rays in the upper left for the sun. Construction lines "
        "only, all strokes light, thin and faint, nothing filled in, no colour."),
    s2=(
        "THIS IS STEP 2 OF 5. The pencil construction lines are now traced over with the thick solid black "
        "marker line, and NOTHING is coloured in yet - the paper stays bare white apart from the black outlines. "
        "Trace every leaf outline, the vein line down the middle of each leaf, all ten eyes, the five mouths, "
        "the tiny arms and legs, the three airborne leaves, the sweeping wind curves, the ground line and the "
        "smiling sun. Every line is crisp, unbroken and slightly wobbly by hand. No colour, no shading, no "
        "highlights yet."),
    s3=(
        "THIS IS STEP 3 OF 5. Flat colour is now laid in, and it stays completely flat - no gradients, no "
        "blending, no shading. Fill the maple leaf flat maple red, the beech leaf flat amber yellow, the oak "
        "leaf flat pumpkin orange, the ginkgo leaf flat coral pink and the willow leaf flat leaf green; fill the "
        "three airborne leaves flat amber yellow and coral pink; fill the sun flat amber yellow and the ground "
        "strip flat pale yellow. Leave the wind curves and every eye plain black on bare paper. Skip every "
        "highlight and every decorative dot for now - they belong to the next step."),
    s4=(
        "THIS IS STEP 4 OF 5. The colour is already down and flat; now the decoration and the highlights go on - "
        "this step is what makes the picture look alive. Add a short white highlight arc to every leaf, a white "
        "glint in every black eye, coral pink cheek dots on all five faces and a white highlight dot on the sun. "
        "Then the decorative vocabulary: draw short speed arcs behind the runners, scatter small coral dots and "
        "tiny four-point star sparkles through the empty paper, and add one or two short hatch lines inside each "
        "leaf. Nothing else changes - the outlines and the flat colours stay exactly as they are."),
    pages={20: ("步骤一：起 形", "先用铅笔轻轻画出五片排成一队的叶子，从下往上一片比一片小，再点上眼睛和细细的小腿。"),
           21: ("步骤二：勾 线", "用黑色勾线笔把每片叶子描一遍，中间加一条叶脉线，后面画上追着它们的风。"),
           22: ("步骤三：铺 色", "五片叶子涂成五种不同的秋色：枫叶红、银杏黄、橡树橙、心形粉、柳叶绿。"),
           23: ("步骤四：装饰高光", "每片叶子加一条白色高光、点一粒眼睛高光，身后补上速度线和彩色小圆点。"),
           24: ("步骤五：加背景", "画上淡黄的草地线、天上飞的小叶子，再给碰地的叶子加上灰蓝影子。")},
    real2=["秋天的落叶", "枫叶和银杏叶"],
    scenes=["赛跑", "跳跃", "面部特写", "树林", "小狗", "风", "太阳"],
))

_("把秋天装进罐子", dict(
    formula="容器隐喻（把秋天装进画里 11604赞 / 盒装蔬菜 2534赞）",
    palette="amber yellow, chestnut brown, maple red, soft sky blue and leaf green",
    deco="polka dots and small four-point star sparkles floating out of the jar, one short horizontal white "
         "highlight band on the glass, and short hatch lines on the acorns",
    light="the light comes from the UPPER LEFT; the jar and everything inside it casts one simple FLAT "
          "grey-blue shadow on the paper, drawn as a solid flat shape",
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "ONE tall clear glass JAR stands UPRIGHT in the CENTRE of the paper, drawn with a simple black outline, "
        "a lid rim at the top and two short vertical white highlight bands on the glass; inside the jar an "
        "autumn harvest is stacked from the bottom up - two big maple leaves lying flat at the bottom, then "
        "three acorns and one pine cone in the middle, then three more small leaves near the neck; OUTSIDE the "
        "jar FOUR small leaves and one tiny acorn float up and out to the upper right, carried by two long "
        "curved wind lines; a simple flat pale-yellow table line runs behind the jar along the bottom of the "
        "paper; one small tuft of grass sits on each side of the jar base; the harvest fills the middle of the "
        "paper while the four corners stay empty. "),
    finish=(
        "THIS IS THE FINISHED MASTER ARTWORK of the lesson, drawn at its very best. Everything is complete: the "
        "jar is filled flat soft sky blue with white highlight bands and a flat chestnut-brown lid; the two "
        "maple leaves at the bottom are flat maple red, the acorns are flat chestnut brown with flat "
        "amber-yellow caps, the pine cone is flat chestnut brown with a white cross-hatch, the small leaves near "
        "the neck are flat amber yellow and leaf green, and the flying leaves are flat maple red and amber "
        "yellow. Decorative layer complete: coral polka dots and small four-point star sparkles float out of the "
        "jar towards the upper right, the wind lines are drawn in grey-blue with white sparkle tips, short hatch "
        "lines sit on the acorns, and the tufts of grass are flat leaf green with white highlight arcs. A soft "
        "flat grey-blue shadow lies under the jar and under the flying leaves. Large calm areas of bare "
        "off-white paper remain in the upper left and the two lower corners so the picture breathes. Finished, "
        "cosy and clearly seasonal."),
    s1=(
        "THIS IS STEP 1 OF 5, the very first construction sketch, and it is DRAWN ONLY IN LIGHT GREY PENCIL - no "
        "marker, no ink, no colour anywhere. Faint thin pencil construction lines only: one tall rounded "
        "rectangle in the centre for the jar with a short oval lid on top and a shallow oval for its base; "
        "inside the jar two big leaf silhouettes at the bottom, three small ovals for the acorns and one "
        "triangle for the pine cone; outside the jar to the upper right four small leaf outlines and one tiny "
        "oval for the flying acorn, with two long sweeping curves for the wind; one straight line across the "
        "bottom for the table; two small scribbles for the tufts of grass. Construction lines only, all strokes "
        "light, thin and faint, nothing filled in, no colour."),
    s2=(
        "THIS IS STEP 2 OF 5. The pencil construction lines are now traced over with the thick solid black "
        "marker line, and NOTHING is coloured in yet - the paper stays bare white apart from the black outlines. "
        "Trace the jar outline, its lid and its base oval, then every leaf, acorn and pine cone inside the jar, "
        "the flying pieces outside it, the two sweeping wind curves, the table line and the two tufts of grass. "
        "Add the two short vertical highlight bands on the glass as clean open shapes. Every line is crisp, "
        "unbroken and slightly wobbly by hand. No colour, no shading, no highlights yet."),
    s3=(
        "THIS IS STEP 3 OF 5. Flat colour is now laid in, and it stays completely flat - no gradients, no "
        "blending, no shading. Fill the whole jar flat soft sky blue, fill its lid flat chestnut brown, fill the "
        "two leaves at the bottom flat maple red, the three acorns flat chestnut brown with flat amber-yellow "
        "caps, the pine cone flat chestnut brown and the small leaves inside flat amber yellow and leaf green; "
        "fill the four flying leaves flat maple red and amber yellow and the table strip flat pale yellow. "
        "Leave the glass highlight bands and every outline plain white and black on bare paper. Skip every "
        "sparkle and every dot for now - they belong to the next step."),
    s4=(
        "THIS IS STEP 4 OF 5. The colour is already down and flat; now the decoration and the highlights go on - "
        "this step is what makes the picture look shiny. Add white highlight arcs to every leaf, a white "
        "highlight dot to every acorn and to the pine cone, and paint the two vertical highlight bands on the "
        "glass bright white. Then the decorative vocabulary: draw the two wind curves in grey-blue with white "
        "sparkle tips, scatter coral polka dots and small four-point star sparkles so they stream out of the jar "
        "towards the upper right, and add a white cross-hatch on the pine cone and short hatch lines on the "
        "acorns. Paint the tufts of grass flat leaf green with white highlight arcs. Nothing else changes."),
    pages={20: ("步骤一：起 形", "先画一个高高的圆角长方形当罐子，里面分三层：底层大叶子、中间橡果和松果、上面小叶子。"),
           21: ("步骤二：勾 线", "用黑色勾线笔描出罐子、盖子，再把里面每一样东西和飞出来的叶子都描一遍。"),
           22: ("步骤三：铺 色", "罐子涂淡蓝，盖子涂栗棕，叶子涂枫叶红和琥珀黄，橡果点上深棕的帽子。"),
           23: ("步骤四：装饰高光", "玻璃上留两条白高光，每片叶子和橡果都点白高光，再撒小圆点和小星星。"),
           24: ("步骤五：加背景", "画上淡黄的桌面线，给罐子和飞出去的叶子添上灰蓝影子。")},
    real2=["真实的玻璃罐", "秋叶和橡果"],
    scenes=["抱罐子", "装罐子", "面部特写", "秋天的公园", "松鼠", "松果", "窗台"],
))

_("路灯下的小猫", dict(
    formula="一道光锥把画面切成明暗两半（路灯下的街景 2554赞）",
    palette="bright lemon yellow, deep prussian blue, flat black and a touch of coral pink",
    deco="a row of tiny bare-paper window squares on the dark houses, small white star dots in the night sky, "
         "and short hatch lines inside the light beam",
    light="the ONE light source is the lamp at the upper right; the beam cuts the paper hard into a warm yellow "
          "lit wedge and a cold deep-blue night, and every object casts one simple FLAT black-blue shadow away "
          "from the lamp",
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "a street lamp head sits at the TOP RIGHT and throws ONE wide straight-edged WEDGE OF LIGHT diagonally "
        "down to the LOWER LEFT, splitting the whole paper into a warm lit triangle and the cold night around "
        "it; inside the lit wedge, on a simple flat ground line, ONE small cat sits upright with its tail "
        "curled, looking up at the lamp, with two big round black eyes with a white glint, a pink nose, "
        "whiskers and pink cheek dots; outside the wedge in the dark night there are THREE simple little houses "
        "with triangle roofs and tiny square windows, and ONE crescent moon with a white star in the UPPER "
        "LEFT; a low garden hedge crosses the lower right corner; the wedge edge is a hard, perfectly straight "
        "line; the two lower corners stay calm and empty. "),
    finish=(
        "THIS IS THE FINISHED MASTER ARTWORK of the lesson, drawn at its very best. Everything is complete: the "
        "whole lit wedge is filled flat bright lemon yellow, the night is filled flat deep prussian blue, the "
        "lamp post and lamp head are flat black with a white highlight dot on the bulb, the cat is flat white "
        "with coral-pink inner ears, a coral-pink nose and a coral-pink collar, the three houses are flat black "
        "silhouettes with small bare-paper window squares, the moon is flat white, and the hedge is flat deep "
        "prussian blue with a white highlight arc. Decorative layer complete: small white star dots are "
        "scattered across the night sky, short hatch lines sit inside the yellow wedge, and a soft flat "
        "black-blue shadow runs away from the lamp under the cat and under the houses. Large calm areas of flat "
        "colour remain in the two lower corners so the picture breathes. Finished, quiet and full of "
        "atmosphere."),
    s1=(
        "THIS IS STEP 1 OF 5, the very first construction sketch, and it is DRAWN ONLY IN LIGHT GREY PENCIL - no "
        "marker, no ink, no colour anywhere. Faint thin pencil construction lines only: two long straight lines "
        "from the upper right corner down to the lower left, marking the two edges of the light beam; a tall "
        "thin rectangle for the lamp post with a small trapezoid lamp head at the top right; one small rounded "
        "shape with two ears for the cat inside the wedge, with two tiny circles for the eyes and a curved line "
        "for the tail; three simple house shapes with triangle roofs and small squares for windows; one circle "
        "with a bite taken out for the crescent moon; one wavy line across the lower right for the hedge; one "
        "straight line for the ground. Construction lines only, all strokes light and faint, no colour."),
    s2=(
        "THIS IS STEP 2 OF 5. The pencil construction lines are now traced over with the thick solid black "
        "marker line, and NOTHING is coloured in yet - the paper stays bare white apart from the black outlines. "
        "Draw the two straight beam edges cleanly, trace the lamp post and lamp head, the cat with its ears, "
        "eyes, nose, whiskers and curled tail, the three houses with their roofs and window squares, the "
        "crescent moon, the hedge and the ground line. Every line is crisp, unbroken and slightly wobbly by "
        "hand. No colour, no shading, no highlights yet."),
    s3=(
        "THIS IS STEP 3 OF 5. Flat colour is now laid in, and it stays completely flat - no gradients, no "
        "blending, no shading, no soft glow. Fill the whole wedge of light flat bright lemon yellow right up to "
        "its hard straight edges, fill everything outside the wedge flat deep prussian blue, fill the lamp post "
        "and lamp head flat black, fill the cat flat white, its inner ears and nose and collar flat coral pink, "
        "the three houses flat black and the crescent moon flat white. Leave the window squares and every "
        "highlight as bare paper for now. Skip every star dot - it belongs to the next step."),
    s4=(
        "THIS IS STEP 4 OF 5. The colour is already down and flat; now the decoration and the highlights go on - "
        "this step is what makes the picture glow. Add a white highlight dot on the lamp bulb, a white glint in "
        "each of the cat's black eyes, coral pink cheek dots on the cat, and a white highlight arc on the hedge "
        "and on the cat's back. Then the decorative vocabulary: leave the little window squares bare paper "
        "white, scatter small white star dots across the deep blue night sky, and add short hatch lines inside "
        "the yellow wedge. Nothing else changes - the outlines, the hard beam edges and the flat colours stay "
        "exactly as they are."),
    pages={20: ("步骤一：起 形", "先从右上角向左下画两条直线，把纸分成亮和暗两块，这就是灯光罩到的地方。"),
           21: ("步骤二：勾 线", "用黑笔描出台灯、灯下的小猫、暗处的三座小房子和一个月亮。"),
           22: ("步骤三：铺 色", "灯罩到的地方全部涂柠檬黄，外面全部涂深蓝，房子和灯杆涂黑，小猫留白。"),
           23: ("步骤四：装饰高光", "灯泡点白高光，小猫眼睛点白点，暗处撒白色小星星，亮处加短排线。"),
           24: ("步骤五：加背景", "窗子留成白色小方块，给小猫和房子加上紧贴物体的黑蓝影子。")},
    real2=["真实的路灯", "夜晚的街道"],
    scenes=["坐着的小猫", "仰头的小猫", "猫脸特写", "夜晚小巷", "月亮", "小房子", "灌木丛"],
))
_("蚂蚁搬月亮", dict(
    formula="蚂蚁搬X（蚂蚁搬秋梨 1666赞 / 蚂蚁搬木瓜 1533赞）",
    palette="deep night blue, bright lemon yellow, leafy green and a touch of coral pink",
    deco="tiny white star dots and four-point sparkles in the night sky, short hatch lines running along the "
         "moon, and small ant footprints dotted on the ground",
    light="the ONLY light source is the glowing crescent moon the ants are carrying; it makes a flat "
          "pale-yellow pool of light on the ground under the little procession and every ant casts one simple "
          "FLAT dark-blue shadow",
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "ONE long glowing CRESCENT MOON is being carried shoulder-high across the paper by a line of FIVE small "
        "black ants that march on a rising diagonal from the LOWER LEFT to the UPPER RIGHT; every ant is a "
        "simple figure of three round body segments with six thin legs, two antennae ending in a ball, two big "
        "round black eyes with a white glint, a small smiling mouth and pink cheek dots, all looking happy and "
        "proud; the ant at the very front leads the way and holds a small leaf flag; the ant at the very back "
        "is the smallest and is running to catch up; under the moon a flat pale-yellow pool of light lies on "
        "the flat ground; a simple flat dark-blue ground line runs along the bottom; in the UPPER LEFT a round "
        "ant hill with a little arched doorway; a few small white stars are scattered in the dark sky; the "
        "procession fills the middle diagonal of the paper while the four corners stay calm and empty. "),
    finish=(
        "THIS IS THE FINISHED MASTER ARTWORK of the lesson, drawn at its very best. Everything is complete: the "
        "crescent moon is filled flat bright lemon yellow with a white highlight along its outer curve, and one "
        "flat pale-yellow pool of light is painted on the ground beneath it; all five ants are flat black with "
        "white highlight dots on their round bodies; the leaf flag is flat leafy green; the ground line and the "
        "ant hill are flat deep night blue and the night sky is left as bare off-white paper. Decorative layer "
        "complete: small white star dots and four-point sparkles are scattered through the night sky, short "
        "hatch lines run along the inside of the crescent, and small ant footprints are dotted along the "
        "ground. A soft flat dark-blue shadow lies under every ant and under the moon. Large calm areas of bare "
        "off-white paper remain in all four corners so the picture breathes. Finished, warm, funny and full of "
        "story."),
    s1=(
        "THIS IS STEP 1 OF 5, the very first construction sketch, and it is DRAWN ONLY IN LIGHT GREY PENCIL - no "
        "marker, no ink, no colour anywhere. Faint thin pencil construction lines only: one big crescent shape "
        "made from two overlapping arcs across the middle of the paper; below it five small ant figures spaced "
        "along one rising diagonal, each built from three small circles, with six tiny lines for the legs, two "
        "lines with a ball for the antennae, two small circles for the eyes and a small curve for the mouth; "
        "one tiny leaf shape held by the leading ant; one low arc along the bottom for the ground; one small "
        "mound with an arched doorway in the upper left; and a handful of tiny dots for the stars. Construction "
        "lines only, all strokes light and faint, nothing filled in, no colour."),
    s2=(
        "THIS IS STEP 2 OF 5. The pencil construction lines are now traced over with the thick solid black "
        "marker line, and NOTHING is coloured in yet - the paper stays bare white apart from the black outlines. "
        "Trace the big crescent and its two tips, then all five ants with their three body segments, six legs, "
        "antennae, eyes and smiles, the little leaf flag, the ground line, the ant hill with its arched doorway "
        "and every star dot. Every line is crisp, unbroken and slightly wobbly by hand. No colour, no shading, "
        "no highlights yet."),
    s3=(
        "THIS IS STEP 3 OF 5. Flat colour is now laid in, and it stays completely flat - no gradients, no "
        "blending, no glow, no shading. Fill the crescent moon flat bright lemon yellow, fill one flat "
        "pale-yellow pool of light on the ground directly under the moon, fill all five ants and their legs "
        "flat black, fill the little leaf flag flat leafy green, fill the ground line and the ant hill flat "
        "deep night blue. Leave the sky, the stars and every highlight as bare paper for now. Skip every "
        "sparkle - it belongs to the next step."),
    s4=(
        "THIS IS STEP 4 OF 5. The colour is already down and flat; now the decoration and the highlights go on - "
        "this step is what makes the picture shine. Add a long white highlight arc along the outer curve of the "
        "crescent moon, a white highlight dot on each of the three round segments of every ant, a white glint "
        "in every ant eye and coral pink cheek dots on all five faces. Then the decorative vocabulary: scatter "
        "small white star dots and four-point sparkles through the bare night sky, add short hatch lines running "
        "along the inside of the crescent, and dot small ant footprints along the flat ground. Nothing else "
        "changes."),
    pages={20: ("步骤一：起 形", "先画一弯大月亮，下面排五只小蚂蚁，每只蚂蚁用三个圆串起来，从下往上走。"),
           21: ("步骤二：勾 线", "黑笔描出月亮、五只蚂蚁的腿和触角，还有蚂蚁洞和小星星。"),
           22: ("步骤三：铺 色", "月亮涂柠檬黄，蚂蚁全部涂黑，地上留一块淡黄的光斑，蚂蚁洞涂深蓝。"),
           23: ("步骤四：装饰高光", "月亮外圈留一条白高光，每只蚂蚁身上点白点、眼睛点白点，天上撒白星星。"),
           24: ("步骤五：加背景", "给每只蚂蚁和月亮加上深蓝影子，地上点一串小脚印，画就活了。")},
    real2=["真实的蚂蚁", "月亮和夜空"],
    scenes=["搬东西", "排队走", "蚂蚁特写", "夜晚草地", "月亮", "小石子", "树叶"],
))

_("黑白小甲虫的花园", dict(
    formula="黑白主体 + 四周高饱和彩色环绕（植物甲虫 4717赞）",
    palette="pure black and white for the beetle, surrounded by vivid leaf green, sunflower yellow, pumpkin "
            "orange and magenta pink",
    deco="vertical stripes, polka dots and a small checker grid on the beetle's shell, plus spiral lines and "
         "waved lines on the surrounding plants",
    light="the light comes from the UPPER LEFT; the beetle and every flower cast one simple FLAT grey-blue "
          "shadow on the paper, drawn as a solid flat shape",
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "ONE big round BEETLE sits in the very CENTRE of the paper, seen from above, built from a large oval "
        "body, a smaller round head with two big round eyes with a white glint, a friendly smiling mouth, two "
        "antennae ending in small balls, and six short legs stepping out to the sides; the beetle's body is "
        "divided by two clean lines into THREE equal sections that will later hold patterns instead of colour; "
        "around the beetle, filling all four corners and the whole margin, SIX groups of simple garden plants "
        "grow - two broad leaves, two round flowers with fat petals, one tall stem with a bud and one clump of "
        "grass - arranged so the paper is full from edge to edge with the plants while the middle stays calm "
        "around the beetle; a simple flat ground line runs across the bottom; the beetle is by far the biggest "
        "thing on the paper. "),
    finish=(
        "THIS IS THE FINISHED MASTER ARTWORK of the lesson, drawn at its very best. Everything is complete: the "
        "beetle is NOT coloured at all - it stays pure black and white, its body filled with pattern instead "
        "of colour, one section in clean vertical stripes, one section in large polka dots and the third "
        "section in a small checker grid, all solid black on white paper, with white highlight arcs on its "
        "shoulders and a white glint in each eye. Everything AROUND the beetle is high-saturation flat colour: "
        "the broad leaves flat vivid leaf green, the round flowers flat sunflower yellow and magenta pink with "
        "flat pumpkin-orange centres, the tall stem and bud flat pumpkin orange, the grass clump flat leaf "
        "green, all with white highlight dots. Decorative layer complete: spiral lines on the broad leaves, "
        "waved lines on the grass, and small white dots scattered around the flowers. A soft flat grey-blue "
        "shadow lies under the beetle and under every plant. Large calm areas of bare off-white paper remain "
        "between the plants so the picture breathes, and the strong black-and-white beetle in the middle stands "
        "out against all that colour."),
    s1=(
        "THIS IS STEP 1 OF 5, the very first construction sketch, and it is DRAWN ONLY IN LIGHT GREY PENCIL - no "
        "marker, no ink, no colour anywhere. Faint thin pencil construction lines only: one big oval in the "
        "centre for the beetle's body, split by two light lines into three sections; a smaller circle above it "
        "for the head with two small circles for the eyes, a curve for the mouth and two lines with a ball for "
        "the antennae; six short double lines stepping out from the body for the legs; around the beetle, six "
        "loose groups of simple shapes for the garden plants - two long leaf outlines, two round flowers with "
        "fat petal loops, one tall stem with a small bud, and one scribble for the grass clump; one straight "
        "line across the bottom for the ground. Construction lines only, all strokes light and faint, no "
        "colour."),
    s2=(
        "THIS IS STEP 2 OF 5. The pencil construction lines are now traced over with the thick solid black "
        "marker line, and NOTHING is coloured in yet - the paper stays bare white apart from the black outlines. "
        "Trace the beetle's body and its three sections, the head, the eyes, the mouth, the antennae and all "
        "six legs, then every leaf, flower, petal, stem, bud and blade of grass around it, and finally the "
        "ground line. Every line is crisp, unbroken and slightly wobbly by hand. No colour, no shading, no "
        "highlights yet."),
    s3=(
        "THIS IS STEP 3 OF 5. Flat colour is now laid in, and it stays completely flat - no gradients, no "
        "blending, no shading. IMPORTANT: the beetle itself gets NO colour at all, it stays pure white with "
        "black outlines; colour only the garden around it. Fill the broad leaves flat vivid leaf green, the two "
        "round flowers flat sunflower yellow and magenta pink with flat pumpkin-orange centres, the tall stem "
        "and the bud flat pumpkin orange, and the grass clump flat leaf green. Leave the beetle, its head and "
        "its six legs completely unpainted white. Skip every pattern, every highlight and every dot for now - "
        "they belong to the next step."),
    s4=(
        "THIS IS STEP 4 OF 5. The colour is already down and flat; now the decoration and the highlights go on - "
        "this step is what makes the picture look alive. On the beetle: fill one body section with clean solid "
        "black VERTICAL STRIPES, one section with large solid black POLKA DOTS and the third section with a "
        "small solid black CHECKER GRID, then add white highlight arcs on the beetle's shoulders and a white "
        "glint in each black eye. On the garden: draw a spiral line on each broad leaf, draw waved lines on the "
        "grass, add a white highlight dot to every flower centre and every petal, and scatter a few small white "
        "dots around the flowers. Nothing else changes."),
    pages={20: ("步骤一：起 形", "先在纸中间画一个椭圆当甲虫身体，上面加一个小圆当头，旁边伸出六条腿。"),
           21: ("步骤二：勾 线", "黑笔描出甲虫和四周的花、叶子、草，注意甲虫要画得最大。"),
           22: ("步骤三：铺 色", "甲虫先不要涂色！只把周围的花和叶子涂成高饱和的绿、黄、橙、玫红。"),
           23: ("步骤四：装饰高光", "甲虫身上画竖条纹、圆点和小格子，再点白高光——黑白配彩色最出效果。"),
           24: ("步骤五：加背景", "叶子加螺旋线，草加波浪线，最后给甲虫和花都加上灰蓝影子。")},
    real2=["真实的甲虫", "花园里的花"],
    scenes=["甲虫特写", "甲虫爬行", "花园全景", "叶子", "瓢虫", "小花", "草地"],
))

_("棉签点彩大树", dict(
    formula="点彩 + 中心留白（秋天的树 6453赞 / 小雏菊 4509赞）",
    palette="sunflower yellow, pumpkin orange, maple red and deep leafy green, on bare off-white paper",
    deco="dense dot clusters of three sizes forming the whole tree crown, small white dots mixed in as light, "
         "and short waved lines on the branches",
    light="the light comes from the UPPER LEFT; the tree and the little fox cast one simple FLAT grey-blue "
          "shadow on the ground, drawn as a solid flat shape",
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "ONE tall tree grows from the LOWER LEFT of the paper, its thick trunk and four heavy branches drawn in "
        "bold black lines, its whole crown built out of DENSE CLUSTERS OF DOTS instead of solid colour, and the "
        "crown spreads over the top and down the right side of the paper like a frame; in the CENTRE of the "
        "paper, in the middle of the crown, there is a large calm EMPTY AREA of bare white paper shaped like a "
        "soft window, and inside that empty area ONE small round fox sits on the ground looking up at the tree, "
        "built from simple round shapes with two big black eyes with a white glint, a white-tipped tail, coral "
        "pink cheek dots and a small smile; a simple flat ground line runs across the bottom; three small "
        "leaves fall through the empty centre from the crown; the crown fills the top, left and right margins "
        "while the centre and the two lower corners stay calm. "),
    finish=(
        "THIS IS THE FINISHED MASTER ARTWORK of the lesson, drawn at its very best. Everything is complete: the "
        "trunk and the four branches are bold solid black with two short waved lines and a white highlight arc "
        "on the left of the trunk; the whole crown is built from DENSE CLUSTERS OF SMALL SOLID DOTS in three "
        "sizes, in sunflower yellow, pumpkin orange, maple red and deep leafy green, packed tightly so the "
        "crown reads as a mass of autumn colour, with a few small white dots mixed in as light; the three "
        "falling leaves are flat maple red and pumpkin orange with white highlight arcs; the little fox is flat "
        "pumpkin orange with a white chest, a white-tipped tail, a black nose and coral pink cheek dots; the "
        "ground line is flat deep leafy green. Decorative layer complete: small white dots sit among the crown "
        "dots, and short waved lines run along the branches. A soft flat grey-blue shadow lies under the tree "
        "and under the fox. The large calm EMPTY AREA of bare off-white paper in the centre of the crown stays "
        "completely empty apart from the single fox, so the eye goes straight to it."),
    s1=(
        "THIS IS STEP 1 OF 5, the very first construction sketch, and it is DRAWN ONLY IN LIGHT GREY PENCIL - no "
        "marker, no ink, no colour anywhere. Faint thin pencil construction lines only: one thick tapering "
        "trunk rising from the lower left with four heavy branch lines forking out of it; around and above the "
        "branches five or six large loose cloud outlines marking where the crown clusters will go, arranged to "
        "leave a big EMPTY GAP in the very centre of the paper; inside that gap one small round fox built from "
        "a circle for the head, a rounded body, two triangle ears, two small circles for the eyes, a curve for "
        "the tail and four tiny legs; three small leaf outlines drifting down through the centre; one straight "
        "line across the bottom for the ground. Construction lines only, all strokes light and faint, no "
        "colour."),
    s2=(
        "THIS IS STEP 2 OF 5. The pencil construction lines are now traced over with the thick solid black "
        "marker line, and NOTHING is coloured in yet - the paper stays bare white apart from the black outlines. "
        "Trace the trunk and all four heavy branches, draw the outline of each crown cluster as a simple lumpy "
        "cloud edge, then the little fox with its ears, eyes, nose, tail and legs, the three falling leaves and "
        "the ground line. Keep the big centre gap open and empty. Every line is crisp, unbroken and slightly "
        "wobbly by hand. No colour, no shading, no highlights yet."),
    s3=(
        "THIS IS STEP 3 OF 5. Flat colour is now laid in, and it stays completely flat - no gradients, no "
        "blending, no shading. Fill the trunk and the four branches flat black; fill the little fox flat "
        "pumpkin orange leaving a white chest and a white tail tip; fill the three falling leaves flat maple "
        "red and pumpkin orange; fill the ground strip flat deep leafy green. The crown clusters are NOT filled "
        "with flat colour yet - for now just block out each crown cluster with one flat layer of medium "
        "sunflower-yellow colour so the shape reads clearly. Leave the big centre gap and the two lower corners "
        "as bare paper. Skip the dots themselves and every highlight - they belong to the next step."),
    s4=(
        "THIS IS STEP 4 OF 5. The colour is already down; now the decoration and the highlights go on - this "
        "step is what makes the picture look rich. Turn each crown cluster into DENSE CLUSTERS OF SMALL SOLID "
        "DOTS in three different sizes, dotting sunflower yellow, pumpkin orange, maple red and deep leafy "
        "green tightly together until the crown reads as a mass of autumn colour; mix a few small white dots in "
        "among them as light. Add a white highlight arc on the left of the trunk, white highlight arcs on the "
        "three falling leaves, a white highlight dot on the fox's head, coral pink cheek dots on its face, and "
        "short waved lines along the branches. Leave the big centre gap completely empty. Nothing else "
        "changes."),
    pages={20: ("步骤一：起 形", "先画一棵粗壮的树，树冠用几个大云朵形圈出来，中间故意留一块空白。"),
           21: ("步骤二：勾 线", "黑笔描出树干、四根粗树枝，空白的地方画一只抬头看树的小狐狸。"),
           22: ("步骤三：铺 色", "树干涂黑，小狐狸涂南瓜橙，先用一层黄色铺满每个树冠区块。"),
           23: ("步骤四：装饰高光", "用大中小三种圆点把树冠点满黄橙红绿，混进白色点点当光，再补高光。"),
           24: ("步骤五：加背景", "画上草地线，给树和小狐狸加上灰蓝影子，中间那块空白千万不要填。")},
    real2=["真实的梧桐叶", "秋天的树皮"],
    scenes=["抬头看树", "落叶", "小狐狸特写", "秋天的树林", "松果", "小鸟", "草地"],
))
_("纸杯长颈鹿", dict(
    formula="半立体 / 3D 错视（这样的3D长颈鹿 5648赞）",
    palette="sunflower yellow, chestnut brown and pure white, with leaf green and pale sky blue accents",
    deco="large polka dot patches on the giraffe, a leaf pattern over the whole tree top, and short hatch "
         "lines along the shading side of the standing cup",
    light="the light comes from the UPPER LEFT; the giraffe body and the standing cup both cast one simple "
          "FLAT grey-blue shadow on the paper, and the cup casts a longer second shadow to the right so it "
          "clearly stands UP off the paper",
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "a children's drawing of a giraffe is painted on ONE sheet of off-white paper; the giraffe's body, four "
        "legs and tail are drawn flat on the paper in the LOWER RIGHT of the sheet, facing left; where the neck "
        "should be there is NOTHING drawn on the paper - instead a REAL small yellow paper CUP stands upright "
        "on the paper at that spot, upside down, as the giraffe's neck and head, with two small paper ears and "
        "two little paper horns attached to the top of the cup and two big round black eyes and a smiling mouth "
        "painted on the side of the cup, so the giraffe appears to poke its head up out of the flat drawing; a "
        "simple flat green tree with a leafy top stands in the LOWER LEFT and the giraffe reaches towards it; "
        "the paper sheet fills the whole frame with the light wooden desk just visible at the edges; the two "
        "upper corners stay calm and empty. "),
    finish=(
        "THIS IS THE FINISHED MASTER ARTWORK of the lesson, drawn at its very best. Everything is complete: the "
        "giraffe's flat body and four legs are covered in flat sunflower yellow with large flat chestnut-brown "
        "POLKA DOT patches, the hooves are flat chestnut brown and the painted tail ends in a flat brown tuft; "
        "the real paper cup standing on the paper is painted flat sunflower yellow with the same flat "
        "chestnut-brown polka dot patches, its two paper ears and horns are flat chestnut brown, and it carries "
        "two big round black eyes with a white glint, coral pink cheek dots and a wide smiling mouth; the tree "
        "in the lower left is flat chestnut brown with a flat leaf-green leafy top covered in small white dots; "
        "the ground is a flat pale-yellow strip. Decorative layer complete: short hatch lines run along the "
        "shading side of the cup, a leaf pattern and small dots fill the tree top, and a soft flat grey-blue "
        "shadow lies under the giraffe while a clearer, longer one lies under the standing cup. Large calm "
        "areas of bare off-white paper remain in the upper corners. The finished picture clearly shows a flat "
        "drawing that has been given a real, standing 3D neck and head."),
    s1=(
        "THIS IS STEP 1 OF 5, the very first construction sketch, and it is DRAWN ONLY IN LIGHT GREY PENCIL - no "
        "marker, no ink, no colour anywhere. Faint thin pencil construction lines only: in the lower right a "
        "loose rounded body shape with four simple leg lines and a short tail; at the shoulders two short marks "
        "showing where the neck will be attached later, plus a light grey circle the size of the cup base so it "
        "is clear where the cup will stand; in the lower left a simple trunk with a lumpy round tree top; one "
        "straight line across the bottom for the ground. NOTHING is drawn where the neck and the head should "
        "be - that space stays empty because the real paper cup will go there. Construction lines only, all "
        "strokes light and faint, no colour."),
    s2=(
        "THIS IS STEP 2 OF 5. The pencil construction lines are now traced over with the thick solid black "
        "marker line, and NOTHING is coloured in yet - the paper stays bare white apart from the black outlines. "
        "Trace the giraffe's body, all four legs, the hooves and the tail, then the tree trunk, the lumpy tree "
        "top and the ground line. Draw the round polka-dot patch outlines on the body and the leaf shapes on "
        "the tree top as clean open shapes. Leave the neck area completely EMPTY - do not draw a neck or a head "
        "on the paper at all. Every line is crisp, unbroken and slightly wobbly by hand. No colour, no shading, "
        "no highlights yet."),
    s3=(
        "THIS IS STEP 3 OF 5. Flat colour is now laid in, and it stays completely flat - no gradients, no "
        "blending, no shading. Fill the giraffe's body and all four legs flat sunflower yellow, fill every "
        "polka-dot patch, all four hooves and the tail tuft flat chestnut brown; fill the tree trunk flat "
        "chestnut brown and the tree top flat leaf green; fill the ground strip flat pale yellow. The neck area "
        "on the paper stays completely EMPTY and unpainted - the upright paper cup will be placed there. Skip "
        "every highlight and every small dot for now - they belong to the next step."),
    s4=(
        "THIS IS STEP 4 OF 5. The colour is already down and flat; now the decoration and the highlights go on - "
        "this step is what makes the picture look finished. Add a white highlight arc to every chestnut-brown "
        "polka-dot patch on the body, a white highlight on each hoof, and scatter small white dots and tiny "
        "leaf shapes across the tree top. Add short hatch lines along the shading side of the tree trunk. The "
        "neck area on the paper is still left empty, because in the final artwork a real painted paper cup "
        "stands there as the giraffe's 3D neck. Nothing else changes."),
    pages={20: ("步骤一：起 形", "先在纸的右下画长颈鹿的身体和四条腿——脖子和头的位置要空出来，留给纸杯。"),
           21: ("步骤二：勾 线", "黑笔描出身体、腿和左边的树，身上画满大小不同的斑点圈。"),
           22: ("步骤三：铺 色", "身体涂柠檬黄、斑点涂栗棕，树冠涂草绿，脖子那块千万不要画。"),
           23: ("步骤四：装饰高光", "每个斑点点白高光，树冠撒白点和小叶子，这是平面部分最后一步。"),
           24: ("步骤五：加背景", "把涂好的纸杯倒扣粘进空位置，画上眼睛和嘴——长颈鹿的头就从纸里立起来了！")},
    real2=["真实的纸杯", "长颈鹿的斑纹"],
    scenes=["长颈鹿站立", "低头吃树叶", "面部特写", "草原", "长颈鹿的腿", "树叶", "木夹子"],
))

_("会翻跟头的西瓜", dict(
    formula="半立体剪贴 + 红绿撞色（翻转大西瓜 4010赞）",
    palette="watermelon red, deep leaf green, flat black and pure white",
    deco="large flat black watermelon seeds, a white zig-zag stripe along the rind, and small coral polka dots "
         "on the cheeks",
    light="the light comes from the UPPER LEFT; the big watermelon and the cut-out slice both cast one simple "
          "FLAT grey-blue shadow, and the cut-out slice casts a longer shadow to the right so it clearly lifts "
          "off the paper",
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "ONE big round anthropomorphic WATERMELON sits in the CENTRE of the paper, seen from the front, with a "
        "deep green rind at the bottom, a wide watermelon-red band across its middle and a smaller green top, "
        "two big round black eyes with a white glint, a wide happy open mouth, two pink cheek dots, two little "
        "stick arms thrown up in the air and two little legs; it is caught mid-somersault, so its whole body is "
        "tilted and there are two curved grey speed arcs spinning around it; beside it, standing up along the "
        "LEFT edge of the paper, there is ONE SEPARATE flat paper SLICE of watermelon that has been cut out and "
        "bent away from the paper so it clearly lifts off the page as a half-3D pop-up, its rind curling "
        "towards the viewer; a simple flat pale-yellow ground line runs along the bottom and a small green vine "
        "with two leaves curls in the lower right corner; the two upper corners stay calm and empty. "),
    finish=(
        "THIS IS THE FINISHED MASTER ARTWORK of the lesson, drawn at its very best. Everything is complete: the "
        "big watermelon is flat-filled with a deep leaf-green rind, a wide watermelon-red middle band and a "
        "smaller green top, with a white zig-zag stripe along the rind edge; its eyes are solid black with a "
        "white glint, its cheeks are coral pink, its mouth is open in a happy shout and its arms and legs are "
        "flat black. The separate cut-out watermelon slice beside it is flat watermelon red with a flat "
        "deep-green rind and is filled with large flat black SEEDS, and it really is bent up off the paper, so "
        "it casts a longer flat grey-blue shadow to the right. Decorative layer complete: large flat black "
        "seeds are dotted across the watermelon-red band, two short grey speed arcs spin around the "
        "somersaulting melon, small coral polka dots sit on the cheeks, and a flat green vine with two leaves "
        "curls in the lower right. Large calm areas of bare off-white paper remain in the upper corners. "
        "Finished, bouncy and full of energy."),
    s1=(
        "THIS IS STEP 1 OF 5, the very first construction sketch, and it is DRAWN ONLY IN LIGHT GREY PENCIL - no "
        "marker, no ink, no colour anywhere. Faint thin pencil construction lines only: one big circle, tilted "
        "slightly to the right, in the centre of the paper, with two light curved lines across it marking the "
        "green bottom, the wide red middle band and the small green top; two small circles for the eyes, a wide "
        "open curve for the mouth and two tiny circles for the cheeks; four small sausage shapes for the two "
        "arms thrown up and the two legs; two long curved lines sweeping around the melon for the speed arcs; "
        "beside it on the left a long thin crescent outline for the separate watermelon slice; one straight line "
        "across the bottom for the ground; one curly line with two small leaf shapes in the lower right for the "
        "vine. Construction lines only, all strokes light and faint, no colour."),
    s2=(
        "THIS IS STEP 2 OF 5. The pencil construction lines are now traced over with the thick solid black "
        "marker line, and NOTHING is coloured in yet - the paper stays bare white apart from the black outlines. "
        "Trace the big tilted melon and its two band dividing lines, the eyes, the mouth, the cheeks, the two "
        "arms and two legs, then the two sweeping speed arcs, the separate crescent slice beside it, the ground "
        "line and the curly vine with its two leaves. Draw the individual seed shapes on the red band as clean "
        "open teardrops. Every line is crisp, unbroken and slightly wobbly by hand. No colour, no shading, no "
        "highlights yet."),
    s3=(
        "THIS IS STEP 3 OF 5. Flat colour is now laid in, and it stays completely flat - no gradients, no "
        "blending, no shading. Fill the bottom rind and the small top of the big melon flat deep leaf green, "
        "fill the wide middle band flat watermelon red, fill the two arms and two legs flat black, fill the "
        "cheeks flat coral pink and leave the eyes solid black. Fill the separate cut-out slice flat watermelon "
        "red with a flat deep-green rind. Fill the ground strip flat pale yellow and the little vine and its two "
        "leaves flat deep leaf green. Leave every highlight, the rind zig-zag and the seeds as bare paper for "
        "now - they belong to the next step."),
    s4=(
        "THIS IS STEP 4 OF 5. The colour is already down and flat; now the decoration and the highlights go on - "
        "this step is what makes the picture look juicy. Fill every teardrop seed shape with solid flat black, "
        "draw the white zig-zag stripe along the rind edge, add a white highlight arc to the green rind and to "
        "each arm and leg, a white glint in each black eye and a white highlight dot on each cheek. Then the "
        "decorative vocabulary: draw the two speed arcs in grey with white sparkle tips, scatter a few small "
        "coral polka dots around the cheeks, and add a white highlight arc on the vine leaves. Nothing else "
        "changes."),
    pages={20: ("步骤一：起 形", "先在纸中间画一个大圆，稍微斜一点，像正在翻跟头；旁边画一块单独的小西瓜。"),
           21: ("步骤二：勾 线", "黑笔描出西瓜、两只眼睛和嘴巴，中间横着画两条线分出绿皮和红瓤。"),
           22: ("步骤三：铺 色", "上下绿皮涂深绿，中间瓜瓤涂西瓜红，旁边那块小西瓜也涂红，藤和叶子涂绿。"),
           23: ("步骤四：装饰高光", "红瓤上画一颗颗黑籽，绿皮上留一条白色锯齿纹，每块都点白高光。"),
           24: ("步骤五：加背景", "画上草地线，把旁边那块小西瓜剪下来、折起来立住——它就真的翘出纸面了！")},
    real2=["真实的西瓜", "西瓜籽和瓜皮"],
    scenes=["翻跟头", "大笑", "西瓜特写", "夏天的桌子", "小蚂蚁", "西瓜藤", "水果刀"],
))

_("秋日小画合集", dict(
    formula="九宫格 / 合集（丙烯马克笔小合集 46311赞 / 夏日合集 2614赞）",
    palette="maple red, amber yellow, pumpkin orange, chestnut brown, deep leafy green and violet purple",
    deco="one clean highlight arc or dot on every single little item, polka dots and short hatching inside "
         "each mini picture, and small four-point star sparkles in the gaps",
    light="the light comes from the UPPER LEFT; every little item casts one simple FLAT grey-blue shadow "
          "inside its own square",
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "the paper is divided by a clean hand-drawn GRID of four lines into NINE equal squares, three across "
        "and three down, drawn with a slight hand wobble; in each of the nine squares sits ONE simple autumn "
        "object, centred and drawn large enough to fill its square, with a little empty margin all round: top "
        "row - a maple leaf, an acorn with its cap, a pine cone; middle row - a spotted mushroom, a curled "
        "hedgehog, a shiny chestnut; bottom row - an open umbrella, a round pumpkin with a stalk, a small round "
        "bird; every object is drawn in the same clean bold line, each one has two tiny eyes with a white "
        "glint and pink cheek dots so the whole grid looks friendly and alive. The grid fills the entire paper "
        "edge to edge with only a narrow bare margin around the outside. "),
    finish=(
        "THIS IS THE FINISHED MASTER ARTWORK of the lesson, drawn at its very best. Everything is complete: all "
        "nine little pictures are flat-filled in high-saturation colour - the maple leaf in maple red, the "
        "acorn in chestnut brown with an amber-yellow cap, the pine cone in chestnut brown, the mushroom in "
        "maple red with a white spotted cap, the hedgehog in chestnut brown with pumpkin-orange spines, the "
        "chestnut in chestnut brown, the umbrella in violet purple and maple red with a pumpkin-orange handle, "
        "the pumpkin in pumpkin orange with a deep-green stalk, and the little bird in amber yellow with a "
        "violet-purple wing. Every one of the nine carries a small black eye with a white glint, coral pink "
        "cheek dots and one white highlight arc or dot. Decorative layer complete: polka dots, short hatch "
        "lines and small four-point star sparkles are scattered inside the nine squares, and a soft flat "
        "grey-blue shadow sits under every object inside its square. The four grid lines stay clean and black "
        "and the narrow bare margin around the whole grid is left empty. Finished, dense, bright and clearly a "
        "complete little collection."),
    s1=(
        "THIS IS STEP 1 OF 5, the very first construction sketch, and it is DRAWN ONLY IN LIGHT GREY PENCIL - no "
        "marker, no ink, no colour anywhere. Faint thin pencil construction lines only: four straight lines "
        "crossing the paper to make a three-by-three grid of nine squares; inside each square one loose simple "
        "outline - a pointed maple leaf, an oval acorn with a cap, a triangle pine cone, a dome mushroom with a "
        "stem, a half-circle hedgehog with short spike marks, a round chestnut, an open umbrella shape, a round "
        "pumpkin with a short stalk, and a small round bird with a beak and a wing. Add two tiny eye circles to "
        "each object. Construction lines only, all strokes light, thin and faint, nothing filled in, no "
        "colour."),
    s2=(
        "THIS IS STEP 2 OF 5. The pencil construction lines are now traced over with the thick solid black "
        "marker line, and NOTHING is coloured in yet - the paper stays bare white apart from the black outlines. "
        "Draw the four grid lines cleanly, then trace all nine objects in order and add their two small eye "
        "circles, a tiny smiling mouth and two pink-cheek-sized cheek circles to each one. Every line is crisp, "
        "unbroken and slightly wobbly by hand. No colour, no shading, no highlights yet."),
    s3=(
        "THIS IS STEP 3 OF 5. Flat colour is now laid in, and it stays completely flat - no gradients, no "
        "blending, no shading. Work square by square and fill each object with one flat colour: the maple leaf "
        "maple red, the acorn chestnut brown with an amber-yellow cap, the pine cone chestnut brown, the "
        "mushroom maple red with a bare-white spotted cap, the hedgehog chestnut brown with pumpkin-orange "
        "spines, the chestnut chestnut brown, the umbrella violet purple and maple red with a pumpkin-orange "
        "handle, the pumpkin pumpkin orange with a deep-green stalk, and the little bird amber yellow with a "
        "violet-purple wing. Leave the grid lines and every highlight as bare paper for now. Skip every dot and "
        "every sparkle - they belong to the next step."),
    s4=(
        "THIS IS STEP 4 OF 5. The colour is already down and flat; now the decoration and the highlights go on - "
        "this step is what makes the whole grid come alive. Add one white highlight arc or dot to every single "
        "one of the nine objects, a white glint in every black eye and coral pink cheek dots on every face. "
        "Then the decorative vocabulary: draw polka dots on the mushroom cap and the pumpkin, short hatch lines "
        "inside the maple leaf and the umbrella, and scatter small four-point star sparkles in the empty "
        "corners of the squares. Nothing else changes - the grid lines and the flat colours stay exactly as "
        "they are."),
    pages={20: ("步骤一：起 形", "先用铅笔把纸分成九格，每格里轻轻画一个小东西：叶子、橡果、松果、蘑菇、刺猬……"),
           21: ("步骤二：勾 线", "黑笔把格子线和九样东西全部描一遍，每样都点上眼睛和腮红。"),
           22: ("步骤三：铺 色", "一格一种颜色，红色、黄色、橙色、棕色、绿色、紫色全部用上，越热闹越好看。"),
           23: ("步骤四：装饰高光", "九样东西每样都加白高光，蘑菇和南瓜点圆点，叶子和雨伞加短排线。"),
           24: ("步骤五：加背景", "格子四角撒小星星，每样东西下面加一小块灰蓝影子，一张纸就是九幅小画。")},
    real2=["真实的松果", "秋天的野果子"],
    scenes=["捡树叶", "摆小画", "刺猬特写", "秋天的公园", "小篮子", "橡果", "蘑菇"],
))
THEME = {
    "树叶逃跑啦":     ("E8452C", "B32E1C", "FFE9C7", "FFC93C"),
    "把秋天装进罐子": ("E07A2F", "A9501A", "FFF1D6", "3E8FB0"),
    "路灯下的小猫":   ("2554A8", "16305F", "E8F0FA", "FFD93C"),
    "蚂蚁搬月亮":     ("2A3E8E", "16225C", "ECEFFA", "FFD93C"),
    "黑白小甲虫的花园": ("1B1B1B", "000000", "F2F2F2", "4CAF50"),
    "棉签点彩大树":   ("E8873A", "A85A1C", "FFF3DC", "4A8B3B"),
    "纸杯长颈鹿":     ("F2B12E", "B8791A", "FFF6DF", "A0622A"),
    "会翻跟头的西瓜": ("2E8B3D", "1B5A26", "FFF0E2", "E8452C"),
    "秋日小画合集":   ("D9542B", "9E3418", "FFF1DD", "6C4BB6"),
}

CHAIN_SLOTS = ["范画成品", "范画步骤1_起形", "范画步骤2_勾线",
               "范画步骤3_铺色", "范画步骤4_装饰高光", "范画步骤5_加背景"]
STEP_TIPS = ["线条要轻，画错了可以擦掉",
             "先想好每样东西放在纸的哪个位置，再动笔",
             "涂色要涂到边，不要留下小空白"]

TPL = os.path.join(ROOT, "项目", "爆米花蹦蹦跳-4-6岁", "project.json")
tpl = json.load(open(TPL, encoding="utf-8"))


def build(name, spec):
    p = json.loads(json.dumps(tpl))          # deep copy
    d = os.path.join(ROOT, "项目", name + "-4-6岁")
    if not os.path.isdir(d):
        sys.exit("缺目录: " + d)

    pri, dk, lt, ac = THEME[name]
    p["meta"]["name"] = "《%s》4-6岁课件" % name
    p["meta"]["theme"].update(primary=pri, dark=dk, light=lt, accent=ac)
    p["meta"]["content_status"] = "范画链已出图；课件内页文案待精修，无人购买前不导出 PDF"

    p["lock"] = spec["lock"]
    p["common"]["stroke"] = STROKE.format(palette=spec["palette"],
                                          deco=spec["deco"], light=spec["light"])

    # ---- 图片槽位 -------------------------------------------------------
    real_names = ["实物_材料工具", "实物_" + spec["real2"][0], "实物_" + spec["real2"][1]]
    photo_names = ["素材_" + s for s in spec["scenes"]]
    ri = pi = 0
    for im in p["images"]:
        im["style"] = PAPER
        if im["batch"] == "chain":
            continue
        if im["batch"] == "real":
            old = im["slot"]
            im["slot"] = real_names[ri]; ri += 1
        elif im["batch"] == "photo":
            im["slot"] = photo_names[pi]; pi += 1
        im["prompt"] = ("【改我】%s —— %s：一张信息清晰的实物/素材参考图，"
                        "白底或干净背景，四角无杂物，用于 4-6 岁课堂观察环节。" % (name, im["slot"]))
    assert ri == 3 and pi == 7, (ri, pi)

    # ---- 范画链提示词 ---------------------------------------------------
    texts = [spec["finish"], spec["s1"], spec["s2"], spec["s3"], spec["s4"], None]
    for im, tx in zip([x for x in p["images"] if x["batch"] == "chain"], texts):
        if tx:
            im["prompt"] = tx
    # 步骤5 = 成品副本，零成本
    for x in p["images"]:
        if x["slot"] == "范画步骤5_加背景":
            x.pop("prompt", None)
            x["alias"] = "范画成品"

    # ---- 步骤页 ---------------------------------------------------------
    steps = [pg for pg in p["pages"] if pg.get("type") == "step"]
    assert len(steps) == 5, len(steps)
    for pg, slot, (t, txt) in zip(steps, CHAIN_SLOTS[1:], list(spec["pages"].values())):
        pg["title"] = t
        pg["image"] = slot
        pg["uses"] = [slot]
        pg["text"] = [txt]
        pg["tips"] = list(STEP_TIPS)
    for pg in p["pages"]:
        if pg.get("type") == "cover":
            pg["title"] = "《%s》" % name
            pg["subtitle"] = "《创意美术主题》  马克笔 4-6岁"

    json.dump(p, open(os.path.join(d, "project.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("[ok] %-18s -> %s" % (name, d))
    print("     配色 %s  %s" % (pri, spec["formula"]))


for _n, _s in SPECS.items():
    build(_n, _s)
print("\n共写入 %d 个课题" % len(SPECS))
