# -*- coding: utf-8 -*-
"""第三轮 5 个新课题 -> project.json（只跑范画链）。

机制与前两轮 14 个课题全部不重样：
真落叶当画布 / 花生壳实物当身体 / 厚涂肌理渐变风景 / 花草边框蔓延 / 一纸六组技法对比。
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

# --- 厚涂风景专用（冬日黄昏）：没有描边，靠色块和剪影 -------------------------
STROKE_THICK = (
    "PAINT LANGUAGE - THIS THEME IS A THICKLY PAINTED LANDSCAPE (厚涂肌理风景), the language of a loaded "
    "flat brush on watercolour paper, and this REPLACES the usual marker outline language completely.\n"
    "(1) NO OUTLINE: there is no marker outline anywhere. Not one single line draws the edge of anything. "
    "Every shape is defined purely by where one block of paint stops and the next begins.\n"
    "(2) THICK MATTE PAINT: broad flat brush strokes of opaque matte paint, each stroke visibly a stroke - "
    "the bristle tracks, the slightly dry scratchy edges where the brush ran out of paint, and the paper "
    "tooth showing through thinly in places. Generously loaded, confident, unblended strokes. Never airbrushed, "
    "never glossy, never smooth vector shapes.\n"
    "(3) SKY GRADIENT: the sky is painted in broad horizontal bands that soften into one another, stepping "
    "smoothly from {sky} - three or four steps, band edges blurred by dragging a dry brush across the seam.\n"
    "(4) SILHOUETTE: everything standing on the ground is a FLAT SOLID DARK SILHOUETTE with no interior "
    "detail at all, except the few windows which are cut out in bright glowing yellow.\n"
    "(5) GLOW: {light}\n"
    "EXCEPTION - step 1 only: loose light-grey PENCIL construction lines only - the horizon line, the hill "
    "line, simple blocky outlines of the tree, the house and the path. Thin and faint, no paint at all."
)

SPECS = {}
_ = SPECS.__setitem__

# =====================================================================
# 1. 落叶小画布 —— 爆款：秋天最美的画布是落叶 4000赞
# =====================================================================
_("落叶小画布", dict(
    formula="真落叶当画布 + 反向绘画（秋天最美的画布是落叶 4000赞）",
    palette="terracotta orange, cobalt blue, magenta pink, lime green, sunflower yellow and cream",
    deco="bold diagonal stripes, concentric rings, polka dots, zig-zag chevrons, wavy scale rows and a grid "
         "of small squares, plus small flying dots in the empty paper and short dashes along the leaf stalks",
    light="the light comes from the UPPER LEFT; every leaf casts one small soft FLAT grey-blue shadow on the "
          "paper, drawn as a solid flat shape",
    stroke_extra=(
        "TECHNIQUE OVERRIDE - this theme paints ONTO REAL DRY LEAVES, and this overrides (2) COLOUR: the six "
        "leaves in the picture are REAL pressed dry autumn leaves lying on the paper, and the patterns are "
        "painted directly onto their surfaces. Each leaf must keep its own real dry botanical texture: the "
        "visible raised vein network, the slightly curled and wavy edge with a dry brittle rim, the tiny "
        "uneven patches where the pigment has flaked, and its own thin stalk. The paint on the leaf surface "
        "sits on top of the leaf as an opaque matte acrylic-marker layer that follows the leaf's curve, so the "
        "raised veins read faintly through the paint and the pattern is very slightly broken where the veins "
        "lift. The leaf silhouettes are organic and unequal - each a genuinely different species: a wide maple "
        "leaf, a slim willow leaf, a round ginkgo fan, a pointed oak leaf, an oval beech leaf and one small "
        "heart-shaped leaf. The paper around them stays completely bare except for the small soft shadows."),
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "SIX real dry autumn leaves of clearly different species and sizes lie scattered across the off-white "
        "paper in a loose, well-spaced scatter - a wide maple leaf at the upper left, a long slim willow leaf "
        "across the top right, a round ginkgo fan at the middle left, a pointed oak leaf in the centre, an oval "
        "beech leaf at the lower right and a small heart-shaped leaf tucked at the bottom left. Each leaf has "
        "been turned into a tiny canvas: the maple leaf carries bold diagonal stripes, the willow leaf carries "
        "a row of concentric rings, the ginkgo fan carries polka dots, the oak leaf carries a zig-zag chevron, "
        "the beech leaf carries wavy scale rows and the heart-shaped leaf carries a grid of small squares. "
        "THREE of the leaves also carry a tiny cute face - two big round black eyes with a white glint, a small "
        "smiling mouth and two pink cheek dots. Every leaf keeps its real dry texture, its veins, its curled "
        "edge and its thin stalk. The background is completely bare off-white paper apart from a scatter of "
        "small painted dots and short dashes between the leaves and one small flat shadow under each leaf."),
    finish=(
        "The finished artwork: six real pressed dry autumn leaves of six different species lying scattered on "
        "bare off-white paper, each leaf used as a tiny canvas and painted on its surface with a different "
        "system of bold high-saturation patterns - diagonal stripes, concentric rings, polka dots, zig-zag "
        "chevrons, wavy scales and a small square grid - with tiny cute faces on three of them. The real dry "
        "leaf texture, raised veins, curled brittle edges and thin stalks are all still clearly readable under "
        "and around the paint. Small painted dots and dashes float between the leaves and each leaf casts one "
        "small soft flat shadow. Bright, bold, playful, completely finished, nothing left unfinished."),
    s1=(
        "THIS IS STEP 1 OF 5 - the light pencil scaffolding, and NOTHING else. In faint thin light-grey pencil "
        "outline, one at a time, where each of the six real leaves will be placed: a wide maple silhouette at "
        "the upper left, a long slim willow shape at the top right, a round ginkgo fan at the middle left, a "
        "pointed oak shape in the centre, an oval beech shape at the lower right and a small heart shape at the "
        "bottom left. Inside three of the outlines draw two light circles for the eyes and one small oval for a "
        "mouth. Simple, loose, faint construction lines only - no colour, no marker, no pattern, no shading."),
    s2=(
        "THIS IS STEP 2 OF 5 - the base colour on the leaves. Now paint a flat opaque base colour over the "
        "whole surface of each real dry leaf, following its exact outline: terracotta orange on the maple leaf, "
        "cobalt blue on the willow leaf, magenta pink on the ginkgo fan, lime green on the oak leaf, sunflower "
        "yellow on the beech leaf and cream on the small heart-shaped leaf. The paint sits on top of the leaf "
        "and stays inside the leaf edge; the raised veins underneath are allowed to read faintly through the "
        "paint. No pattern yet, no faces yet - only these six flat base colours."),
    s3=(
        "THIS IS STEP 3 OF 5 - the pattern painting, the step that turns each leaf into a tiny canvas. Keep "
        "every base colour exactly as it is and now paint one different pattern system onto each leaf surface "
        "with a clean opaque marker: bold diagonal stripes across the maple leaf, a row of concentric rings "
        "across the willow leaf, evenly spaced polka dots on the ginkgo fan, a zig-zag chevron band down the "
        "oak leaf, rows of wavy scales on the beech leaf and a grid of small squares on the heart-shaped leaf. "
        "Each pattern follows the curve of its leaf and stays inside the leaf edge. No faces yet, no dots in "
        "the background."),
    s4=(
        "THIS IS STEP 4 OF 5 - the faces and the highlights, the step that makes it come alive. On the three "
        "chosen leaves draw the tiny cute faces in clean black marker: two big round black eyes each with a "
        "white glint, a small open smiling mouth and two pink cheek dots. Then add one or two pure white "
        "highlight dots or a short white arc along the curl of every leaf, and a short white dashes line along "
        "each leaf stalk. Scatter small painted dots and short dashes in the bare paper between the leaves. "
        "Nothing else changes - the base colours and the patterns stay exactly as they are."),
    pages={20: ("步骤一：摆叶子", "先把六片落叶在纸上摆一摆，比一比谁的形状不一样，再用铅笔轻轻描一圈。"),
           21: ("步骤二：涂底色", "每片叶子先涂一层底色：橙、蓝、粉、绿、黄、奶油色，一片一个颜色。"),
           22: ("步骤三：画花纹", "叶子就是小画布！条纹、圆圈、点点、折线、波浪、方格，一片叶子一种花纹。"),
           23: ("步骤四：加表情高光", "挑三片叶子画上大眼睛和腮红，每片叶子边沿点一点白高光。"),
           24: ("步骤五：加背景", "叶子之间撒一些小圆点和小短线，每片叶子底下加一小块影子，画面就满了。")},
    real2=["真实的落叶", "丙烯马克笔"],
    scenes=["落叶特写", "叶脉纹理", "捡落叶", "秋天的树", "多种叶子摆一排", "颜料和笔", "小朋友画叶子"],
))

# =====================================================================
# 2. 花生壳小鸡 —— 爆款：花生壳创意贴画 5505赞
# =====================================================================
_("花生壳小鸡", dict(
    formula="实物壳当身体 + 涂鸦添画（花生壳创意贴画 5505赞）",
    palette="sunflower yellow, grass green, carrot orange, tomato red and sky blue",
    deco="short double-line grass tufts along the bottom, small five-petal flowers, straight sun rays, and "
         "short dash marks as tiny footprints in the empty paper",
    light="the light comes from the UPPER LEFT; every chick and every peanut shell casts one small soft FLAT "
          "grey-blue shadow on the paper, drawn as a solid flat shape",
    stroke_extra=(
        "TECHNIQUE OVERRIDE - this theme glues REAL PEANUT SHELLS onto the paper, and this overrides (2) "
        "COLOUR: the five little chicks in the picture each have a REAL WHOLE PEANUT IN ITS SHELL as their "
        "body. Each peanut must be a genuine peanut shell - an elongated rounded pod with the natural "
        "honeycomb network of raised bumpy ribs all over its surface, in warm beige and light chestnut with "
        "soft natural shading between the bumps, and one end showing the slightly pointed tip where it grew. "
        "The shells keep their own real three-dimensional bumpy texture and are NOT repainted in flat poster "
        "colour. Everything else on each chick - the eyes, the beak, the legs, the wings - and the sun, the "
        "grass and the flowers are drawn in the clean crisp marker-line language on top of and around the "
        "shells."),
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "FIVE little chicks stand in a loose diagonal line running from the lower left up to the upper right, "
        "each one small and round. Every chick's BODY is one REAL PEANUT in its shell, standing upright and "
        "showing its natural bumpy honeycomb texture; on each peanut the face is drawn in clean marker - two "
        "small round black eyes with a white glint, a tiny orange triangular beak and two pink cheek dots - "
        "plus one small rounded wing shape on the side and two thin orange legs with three toes each standing "
        "on the ground. One big smiling sun with straight rays sits in the upper left corner, drawn as a "
        "complete circle with a happy face. A low band of grass tufts runs across the bottom of the paper, "
        "with three small five-petal flowers among it - one red, one pink and one blue. A small group of three "
        "loose empty peanut shells lies at the lower right corner, and a few short footprint dashes walk "
        "between the chicks. The rest of the paper stays bare off-white with one small flat shadow under each "
        "chick and each loose shell."),
    finish=(
        "The finished artwork: five little chicks in a diagonal line, each one's body a real whole peanut in "
        "its shell with its natural bumpy honeycomb texture in warm beige and chestnut, wearing clean marker-"
        "drawn faces (two round black eyes with white glints, a tiny orange beak, pink cheek dots), a rounded "
        "wing, and two thin orange legs with three toes each. A big smiling sun with straight rays in the upper "
        "left, a low band of double-line grass tufts across the bottom with one red, one pink and one blue "
        "five-petal flower, three loose empty peanut shells at the lower right, a few footprint dashes between "
        "the chicks and one small flat shadow under everything. Bright, bold, cheerful, completely finished, "
        "nothing left unfinished."),
    s1=(
        "THIS IS STEP 1 OF 5 - the light pencil scaffolding, and NOTHING else. In faint thin light-grey pencil "
        "draw five small upright oval shapes in a loose diagonal line from the lower left to the upper right "
        "where the five peanuts will stand; draw a light circle with straight rays in the upper left corner "
        "for the sun; draw two light circles for the eyes and a small triangle for the beak on each oval; draw "
        "two short vertical lines under each oval for the legs; draw a low wavy line across the bottom for the "
        "grass band; and draw three small oval shapes at the lower right for the loose peanut shells. Simple, "
        "loose, faint construction lines only - no colour, no marker, no peanuts yet."),
    s2=(
        "THIS IS STEP 2 OF 5 - the glued peanut shells. Keep every pencil guide exactly where it is and now "
        "fix the REAL peanut shells in place: glue one whole peanut in its shell upright onto each of the five "
        "oval positions so that it becomes the chick's body, and glue the three loose empty peanut shells at "
        "the lower right. Every peanut must show its genuine natural honeycomb bumpy texture in warm beige and "
        "light chestnut with soft natural shading between the bumps, and must keep its own real three-"
        "dimensional shell look - do not repaint the shells in flat colour. No drawn faces, no sun colour, no "
        "grass yet."),
    s3=(
        "THIS IS STEP 3 OF 5 - the marker drawing. Nothing about the glued peanut shells changes. With the "
        "clean black marker draw each chick's face on top of its peanut: two small round black eyes with a "
        "white glint, a tiny orange triangular beak, two pink cheek dots, and one small rounded wing shape on "
        "the side. Draw the two thin orange legs with three toes on each chick standing on the ground. Then "
        "draw the big sun with a happy smiling face and straight rays in the upper left, and the low double-"
        "line grass tufts in a band across the bottom with one red, one pink and one blue five-petal flower "
        "among them. Clean crisp marker lines only - no flat colour filling yet apart from the beak, the legs "
        "and the flower petals."),
    s4=(
        "THIS IS STEP 4 OF 5 - the colour and the highlights, the step that makes it come alive. Colour the "
        "sun bright sunflower yellow with a warm yellow halo, colour the grass band grass green with a few "
        "darker green blades, and finish the three five-petal flowers in tomato red, magenta pink and sky blue "
        "with tiny yellow centres. Add one or two pure white highlight dots or a short white arc to every "
        "chick's eye and to the sun. Scatter a few short footprint dash marks between the chicks and a few "
        "small flying dots in the bare paper. Nothing else changes - the peanut shells, the faces and the "
        "geometry stay exactly as they are."),
    pages={20: ("步骤一：摆一摆", "铅笔先定位置：五只小鸡斜着排一排，左上角留一个太阳，底下留一条草地。"),
           21: ("步骤二：贴花生壳", "把整个花生壳贴在纸上当小鸡的身体——壳上的小坑坑就是它最好的羽毛。"),
           22: ("步骤三：画小鸡", "黑笔在花生上画眼睛、小尖嘴、腮红和一只小翅膀，再画两条细细的腿。"),
           23: ("步骤四：涂色高光", "太阳涂黄色、草地涂绿色，小花涂红粉蓝，眼睛和太阳都点白高光。"),
           24: ("步骤五：加背景", "地上撒小脚印，空中点小飞点，右下角摆三个空花生壳，画面就热闹了。")},
    real2=["带壳的花生", "白乳胶"],
    scenes=["花生壳特写", "带壳花生", "小鸡", "草地和野花", "太阳", "小朋友贴花生", "胶水和画笔"],
))

# =====================================================================
# 3. 冬日黄昏 —— 爆款：丙烯马克笔·冬日黄昏 4400赞
# =====================================================================
_("冬日黄昏", dict(
    formula="厚涂肌理 + 渐变天空 + 黑色剪影（冬日黄昏 4400赞）",
    palette="deep violet blue, purple, bright lemon yellow, glowing amber and flat black",
    deco="dry-brush scratchy band edges in the sky, fine bare branch lines on the tree silhouette, a curl of "
         "smoke from the chimney, and short black grass tufts along the very bottom edge",
    light="a wide wedge of bright lemon-yellow light pours out of the sky at the horizon and sweeps "
          "diagonally down to the lower right foreground, where the snow field catches it and glows; "
          "everything else falls into the deep violet-blue dusk",
    stroke=STROKE_THICK,
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "a wide winter dusk landscape. The SKY takes the upper two thirds and is painted in broad horizontal "
        "bands stepping smoothly from deep violet blue at the very top, to purple in the middle, to bright "
        "lemon yellow at the horizon. A low rolling hill line cuts across the picture just above the middle. "
        "On the LEFT stands one tall bare tree, a flat solid dark silhouette with a clean trunk and a fine "
        "network of bare winter branches spreading wide. On the lower LEFT beside it a small house silhouette "
        "with a steep roof, one chimney with a thin curl of smoke rising, and THREE windows cut out in bright "
        "glowing yellow. The ground is a snowy field of flat white with two or three pale blue shadow bands; "
        "a bright yellow glowing road sweeps diagonally from the house door down towards the lower right "
        "foreground, widening as it comes forward. Three short black grass tufts and one small snow-covered "
        "fence post stand along the very bottom edge, all in flat black silhouette."),
    sky="deep violet blue at the top, purple in the middle and bright lemon yellow at the horizon",
    finish=(
        "The finished artwork: a wide winter dusk landscape painted thickly with a loaded flat brush - a sky "
        "of broad horizontal bands stepping from deep violet blue through purple to bright lemon yellow at the "
        "horizon with softly dragged band edges, a low hill line, a tall bare tree in flat dark silhouette "
        "with a fine network of branches on the left, a small house silhouette with a chimney and a thin curl "
        "of smoke and three windows glowing bright yellow, a snowy white field with pale blue shadow bands, "
        "and a bright yellow glowing road sweeping diagonally down to the lower right foreground. Three black "
        "grass tufts and one small fence post sit along the bottom. No outlines anywhere, visible brush "
        "texture, dry scratchy edges, fully finished and rich."),
    s1=(
        "THIS IS STEP 1 OF 5 - the light pencil scaffolding, and NOTHING else. In faint thin light-grey pencil "
        "draw one horizontal line for the horizon about two thirds down, one low rolling hill line just above "
        "it, the simple blocky outline of a tall bare tree on the left with its branch pattern, the small "
        "blocky outline of a house with a roof and a chimney on the lower left, three small rectangles for its "
        "windows, and two long sweeping lines for the road running diagonally from the house down to the lower "
        "right. Simple, loose, faint construction lines only - no paint, no colour, no shading."),
    s2=(
        "THIS IS STEP 2 OF 5 - the sky. With a loaded flat brush paint the whole upper two thirds in broad "
        "horizontally swept bands that soften into one another: deep violet blue across the very top, "
        "tightening into purple through the middle, and bright lemon yellow along the horizon, letting each "
        "band edge blur where a dry brush dragged across the seam, leaving the visible bristle tracks and the "
        "paper tooth showing thinly in places. Three or four broad bands are enough. Nothing else is painted "
        "in this step - the tree, the house, the hill and the ground stay bare paper."),
    s3=(
        "THIS IS STEP 3 OF 5 - the silhouettes. Load a dark brush and paint the ground line-up as FLAT SOLID "
        "DARK SILHOUETTES with no interior detail at all: the low rolling hill line just above the horizon, "
        "the tall bare tree on the left with its trunk and its fine spreading network of bare winter branches, "
        "the small house on the lower left with its steep roof and chimney, three long black grass tufts and "
        "one small snow-covered fence post along the very bottom edge. Then cut THREE windows out of the house "
        "silhouette in bright glowing yellow and add a thin curl of pale grey smoke rising from the chimney. "
        "Nothing is outlined - the shapes are pure flat painted silhouette."),
    s4=(
        "THIS IS STEP 4 OF 5 - the snow and the glow, the step that makes the picture warm. Paint the snowy "
        "field along the bottom in flat white with two or three broad pale blue shadow bands swept across it. "
        "Then paint the glowing road: a wide wedge of bright lemon-yellow and glowing amber light sweeping "
        "diagonally from the house door down to the lower right foreground and widening as it comes forward, "
        "painted with two or three bold unblended strokes. Let the far end of the glow blur into the yellow of "
        "the horizon. Nothing else changes - the sky bands and the silhouettes stay exactly as they are."),
    pages={20: ("步骤一：起 形", "先用铅笔轻轻分出天和地，再画上左边的树、左下的小房子和一条斜斜的路。"),
           21: ("步骤二：铺天空", "大笔横扫：上面深蓝、中间紫色、地平线亮黄色，一笔一笔往下压，边界轻轻晕开。"),
           22: ("步骤三：画剪影", "换深色，把山线、大树、小房子、草丛全部涂成黑黑的剪影，房子留三扇黄窗户。"),
           23: ("步骤四：画雪地光带", "雪地涂白色加两道淡蓝影子，再从房子门口拉出一条黄色的光，越往前越宽。"),
           24: ("步骤五：加背景", "烟囱加上一缕青烟，光带边缘用干笔扫几下，冷暖一撞，冬日的黄昏就出来了。")},
    real2=["黄昏的天空", "平头画笔"],
    scenes=["冬日黄昏", "雪地夕阳", "冬天的树", "雪中小屋", "紫色晚霞", "颜料和画笔", "雪地脚印"],
))

# =====================================================================
# 4. 墙边的花 —— 爆款：墙边的花正在肆意生长 94343赞
# =====================================================================
_("墙边的花", dict(
    formula="花草沿纸边蔓延 + 中心留白（墙边的花肆意生长 94343赞）",
    palette="coral pink, sunflower yellow, violet purple, leaf green, sky blue and cream",
    deco="a row of small brick lines along the wall, tiny four-petal blossoms tucked into the vine curls, "
         "short curved stems with paired leaves, and small flying dots and sparkles drifting in the empty "
         "middle of the paper",
    light="the light comes from the UPPER LEFT; the wall and every flower stem cast one simple FLAT grey-blue "
          "shadow on the paper, drawn as a solid flat shape",
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "a low stone wall runs in a straight band along the bottom edge of the paper, drawn with clean "
        "rectangular brick lines and a simple flat top surface. From behind the wall, flowers and grass grow "
        "UPWARD and OUTWARD so that they climb and fill ALL FOUR EDGES of the sheet: along the left edge two "
        "tall daisies lean inward, along the right edge three tulips and a curling vine rise up, across the "
        "top edge a loose garland of leaves and small blossoms droops down from the corners, and along both "
        "bottom corners dense grass blades and round-leaved plants spread out over the wall. The middle of the "
        "sheet is deliberately left a large calm EMPTY off-white space, broken only by ONE small white "
        "butterfly hovering in it and a few tiny drifting dots and sparkles. The flowers are large and clearly "
        "readable - six-petal daisies with round yellow centres, tulip bells, small five-petal blossoms and "
        "one round-headed poppy - each on its own clean curved green stem with paired leaves. Nothing is "
        "placed in the centre; the flowers only ever live around the rim of the picture."),
    finish=(
        "The finished artwork: a low brick-lined stone wall along the bottom edge, with tall daisies leaning in "
        "from the left, tulips and a curling vine rising on the right, a loose garland of leaves and small "
        "blossoms drooping from the two top corners, and dense grass with round-leaved plants spreading over "
        "the wall at both bottom corners - so that all four edges of the sheet are full of flowers and green, "
        "while the middle of the paper is left as a large calm empty off-white space holding one small white "
        "butterfly and a few drifting dots. Bright, bold, joyful, completely finished, nothing left unfinished."),
    s1=(
        "THIS IS STEP 1 OF 5 - the light pencil scaffolding, and NOTHING else. In faint thin light-grey pencil "
        "draw the straight low wall band across the bottom edge with a line for its flat top, then light "
        "circles and shapes for where the flowers will grow - two tall daisies leaning in from the left, three "
        "tulip bells and one curl of vine on the right, a loose garland of small leaf and blossom shapes along "
        "the top two corners, and dense grass tufts in both bottom corners. Draw one light small butterfly "
        "shape in the exact centre of the sheet. Leave the middle of the paper empty. Simple, loose, faint "
        "construction lines only - no marker, no colour, no detail."),
    s2=(
        "THIS IS STEP 2 OF 5 - the marker drawing. Trace the whole picture in clean black marker: the wall band "
        "with its clean rectangular brick lines and flat top, every flower stem as one clean continuous curved "
        "line, every daisy, tulip, poppy and small blossom outlined, every leaf outlined with its centre vein, "
        "the grass tufts as clean pointed blades, and the small butterfly in the middle. Every contour is one "
        "confident continuous solid line with only a slight hand-drawn wobble. Nothing else is added in this "
        "step - no colour at all, no fill, no dots."),
    s3=(
        "THIS IS STEP 3 OF 5 - the colour. Fill every shape with flat high-saturation poster colour, edge to "
        "edge inside its outline: the daisies cream white with round sunflower-yellow centres, the tulips coral "
        "pink and violet purple, the poppy tomato red with a dark centre, the small blossoms sunflower yellow "
        "and sky blue, every stem and leaf leaf green, the vine violet purple, and the wall in a soft warm "
        "grey-blue with slightly darker brick lines. Keep the middle of the paper completely empty white "
        "except for the butterfly. Flat even colour only - no gradient, no shading."),
    s4=(
        "THIS IS STEP 4 OF 5 - decoration and highlights, the step that makes it come alive. Add one or two "
        "pure white highlight dots or a short white arc to every flower centre, to the tulip bells, to the "
        "poppy head and to the butterfly. Tuck tiny four-petal blossoms and short curls into the vine and into "
        "the grass tufts, and add small yellow pollen dots in the middle of each daisy. Finally scatter a few "
        "small flying dots and tiny four-point sparkles drifting in the empty middle of the paper around the "
        "butterfly. Nothing else changes - the layout, the empty centre and the colour stay exactly as they "
        "are."),
    pages={20: ("步骤一：起 形", "铅笔先画底下一条矮墙，再把花的位置定在纸的四边，中间空着留给蝴蝶。"),
           21: ("步骤二：勾 线", "黑笔从墙开始描，花茎一笔画到底，每一片叶子和花瓣都描清楚。"),
           22: ("步骤三：铺 色", "花心涂黄、花瓣涂粉紫红、叶子和花茎涂绿，墙面涂淡灰蓝，中间一定留白。"),
           23: ("步骤四：装饰高光", "每个花心点白高光，藤蔓里塞几朵小花，四周点缀小飞点和星星。"),
           24: ("步骤五：加背景", "只在墙下加一块灰蓝影子，中间那只小蝴蝶让它自己飞——留白就是这幅画最贵的地方。")},
    real2=["真实的砖墙", "院子里的花"],
    scenes=["墙面和花", "雏菊特写", "郁金香", "院墙边的花草", "蝴蝶", "绿叶和藤蔓", "小朋友画花"],
))

# =====================================================================
# 5. 小草六种画法 —— 爆款：草丛的6种不同画法 116216赞
# =====================================================================
_("小草六种画法", dict(
    formula="一纸六组技法对比（草丛的6种不同画法 116216赞）",
    palette="leaf green, deep pine green, lime green, sunflower yellow, sky blue and coral pink",
    deco="two or three different green families used side by side, open white gaps left between the six "
         "clumps, tiny flower heads and small flying dots scattered to show the scale of the grass, and a row "
         "of short dashes marking the ground line under each clump",
    light="the light comes from the UPPER LEFT; each grass clump casts one short simple FLAT grey-blue shadow "
          "on the paper, drawn as a solid flat shape",
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "the sheet is loosely divided into SIX clearly separated areas with open bare-paper gaps between them, "
        "and each area holds ONE clump of grass drawn in a completely different technique, always growing up "
        "from a short ground line:\n"
        "1 - upper left: a dense fan of straight upright blades of even length, all rising from one point.\n"
        "2 - top centre: blades all bending to the right as if blown by wind, with three short curved wind "
        "lines behind them.\n"
        "3 - upper right: blades that end in tight spiral curls, like a spring.\n"
        "4 - lower left: tall pointed blades of clearly different heights with small seed heads on top.\n"
        "5 - bottom centre: a soft rounded tuft made of many short arched strokes, with small dots between.\n"
        "6 - lower right: grass drawn as outlined shapes then filled with a different green, showing the "
        "outline-and-fill method.\n"
        "One big smiling sun in the top right corner and one small five-petal flower beside the bottom left "
        "clump show how tall the grass is. Nothing else is on the sheet - the six clumps stay separate and the "
        "bare paper gaps between them are wide and clean."),
    finish=(
        "The finished artwork: six separate clumps of grass filling the sheet in a loose six-way arrangement, "
        "each clump drawn in a completely different technique - an upright fan, wind-bent blades with wind "
        "lines, blades ending in spiral curls, tall pointed blades with seed heads, a soft rounded tuft of "
        "short arched strokes with dots, and an outlined-and-filled clump. Each clump grows from its own short "
        "ground line and casts one short flat grey-blue shadow, and the bare paper gaps between the six clumps "
        "stay wide and clean. Different green families are used side by side, one big smiling sun in the top "
        "right corner and one small five-petal flower beside the bottom left clump. Bright, bold, clear, "
        "completely finished, nothing left unfinished."),
    s1=(
        "THIS IS STEP 1 OF 5 - the light pencil scaffolding, and NOTHING else. In faint thin light-grey pencil "
        "sketch the six clump positions as six light bundles of simple lines: a fan of straight upright lines "
        "in the upper left, a bundle of short straight lines tilted to the right in the top centre, a bundle "
        "of lines with light curls at their tips in the upper right, a row of lines of clearly different "
        "heights with light small ovals on top in the lower left, a low rounded bundle of tiny arched lines in "
        "the bottom centre and a bundle of simple outlined blade shapes in the lower right. Add a light circle "
        "for the sun in the top right corner and a light circle for one little flower at the bottom left. "
        "Simple, loose, faint construction lines only - no colour, no marker, no detail."),
    s2=(
        "THIS IS STEP 2 OF 5 - the first three clumps in marker. Keep every pencil guide exactly where it is "
        "and draw the upper three clumps with the clean black marker: in the upper left a dense even fan of "
        "straight upright blades all rising from one point; in the top centre a bundle of blades all bending to "
        "the right as if blown by wind, with three short curved wind lines behind them; in the upper right "
        "blades that end in tight spiral curls like a spring. Every blade is one clean confident continuous "
        "line with only a slight hand-drawn wobble. Leave the lower three clumps as faint pencil only - no "
        "colour at all yet."),
    s3=(
        "THIS IS STEP 3 OF 5 - the lower three clumps in marker. Nothing about the upper three clumps changes. "
        "Now draw the lower three with the same clean marker: in the lower left tall pointed blades of clearly "
        "different heights with small seed heads on top; in the bottom centre a soft rounded tuft made of many "
        "short arched strokes with small dots between them; in the lower right grass drawn as clean outlined "
        "blade shapes, each with its own closed outline all the way round and its centre vein drawn in. Draw "
        "the big smiling sun in the top right corner with straight rays, and the one small five-petal flower "
        "beside the bottom left clump. Still no colour filling."),
    s4=(
        "THIS IS STEP 4 OF 5 - the colour, the highlights and the ground lines. Now fill each clump with a "
        "DIFFERENT green family so the six methods read as six separate studies: a fresh leaf green for the "
        "upright fan, a deeper pine green for the wind-bent blades, a bright lime green with a pale yellow "
        "tint for the spiral curls, a mid green with darker tips for the tall pointed blades, a soft mint "
        "green for the rounded tuft, and a two-tone green with a paler centre for the outlined clump. Colour "
        "the sun bright sunflower yellow with straight rays, the little flower coral pink with a yellow "
        "centre, and add small sky-blue flying dots. Add one or two pure white highlight dots to the seed "
        "heads, the flower and the sun, and a row of short dashes as the ground line under each clump. "
        "Nothing else changes - the gaps between the clumps stay bare paper."),
    pages={20: ("步骤一：起 形", "铅笔先把纸分成六块，每块画一丛小草的位置，头顶留一个太阳。"),
           21: ("步骤二：画前三丛", "黑笔先画三丛：站得笔直的、被风吹歪的、卷卷的，一丛一个样子。"),
           22: ("步骤三：画后三丛", "继续画另外三丛：有草籽的高草、胖胖的圆草丛、先勾线再涂色的草。"),
           23: ("步骤四：六种绿铺色", "六丛草用六种不一样的绿，太阳涂黄，旁边加一朵小花做身高对比。"),
           24: ("步骤五：加背景", "每丛草底下加一排小短线和一小块影子——一张纸就学会了六种画草的方法。")},
    real2=["真实的草丛", "马克笔绿色系"],
    scenes=["草丛特写", "风吹草", "草籽穗", "草地上的小花", "花园的草", "绿色马克笔", "小朋友画草"],
))

THEME = {
    "落叶小画布":   ("C4501F", "7A2E12", "FFF4E2", "2E8B8B"),
    "花生壳小鸡":   ("F2B12E", "B8791A", "FFF8E3", "6BBF4A"),
    "冬日黄昏":     ("1F3A7A", "0E1B3D", "FFD93C", "8E4FBF"),
    "墙边的花":     ("4A8B3B", "24521C", "FFF6E0", "E8557F"),
    "小草六种画法": ("3E8B4A", "1F5C2C", "F3F7EC", "F2B12E"),
}

SLOTS_DEFAULT = ["范画成品", "范画步骤1_起形", "范画步骤2_勾线",
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
    p["meta"]["formula"] = spec["formula"]

    p["lock"] = spec["lock"]
    st = spec.get("stroke") or STROKE
    if spec.get("stroke_extra"):
        st = st + "\n" + spec["stroke_extra"]
    p["common"]["stroke"] = st.format(palette=spec["palette"], deco=spec["deco"],
                                      light=spec["light"], sky=spec.get("sky", ""))

    slots = spec.get("slots") or SLOTS_DEFAULT

    # ---- 图片槽位 -------------------------------------------------------
    real_names = ["实物_材料工具", "实物_" + spec["real2"][0], "实物_" + spec["real2"][1]]
    photo_names = ["素材_" + s for s in spec["scenes"]]
    ri = pi = 0
    for im in p["images"]:
        im["style"] = PAPER
        if im["batch"] == "chain":
            continue
        if im["batch"] == "real":
            im["slot"] = real_names[ri]; ri += 1
        elif im["batch"] == "photo":
            im["slot"] = photo_names[pi]; pi += 1
        im["prompt"] = ("【改我】%s —— %s：一张信息清晰的实物/素材参考图，"
                        "白底或干净背景，四角无杂物，用于 4-6 岁课堂观察环节。" % (name, im["slot"]))
    assert ri == 3 and pi == 7, (ri, pi)

    # ---- 范画链提示词 ---------------------------------------------------
    texts = [spec["finish"], spec["s1"], spec["s2"], spec["s3"], spec["s4"], None]
    for im, tx, sl in zip([x for x in p["images"] if x["batch"] == "chain"], texts, slots):
        im["slot"] = sl
        if tx:
            im["prompt"] = tx
    # 步骤5 = 成品副本，零成本
    for x in p["images"]:
        if x["slot"] == slots[5]:
            x.pop("prompt", None)
            x["alias"] = "范画成品"

    # ---- 步骤页 ---------------------------------------------------------
    steps = [pg for pg in p["pages"] if pg.get("type") == "step"]
    assert len(steps) == 5, len(steps)
    for pg, slot, (t, txt) in zip(steps, slots[1:], list(spec["pages"].values())):
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
    print("[ok] %-14s -> %s" % (name, d))
    print("     配色 %s  %s" % (pri, spec["formula"]))


for _n, _s in SPECS.items():
    build(_n, _s)
print("\n共写入 %d 个课题" % len(SPECS))
