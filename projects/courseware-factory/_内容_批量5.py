# -*- coding: utf-8 -*-
"""批量把 5 个新课题写进各自 project.json（本轮只跑范画链 5+1 张）。

每个课题挂一条新一轮小红书爆款公式（都带赞数背书），机制与上一轮完全不重样：
手指拓印 / 塑料袋拓印 / 纯线描不涂色 / 撕纸拼贴 / 自然材料拼贴。
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

# --- 线描专用：整张画只有蓝色线条，一点颜色都不涂 --------------------------
STROKE_LINE = (
    "LINE LANGUAGE - THIS THEME IS A PURE LINE DRAWING (线描): the whole sequence, every step and the finished "
    "artwork are drawn with ONE single blue marker only, and there is NO colour filling of any kind anywhere.\n"
    "(1) NO FILL: absolutely no flat colour blocks, no painted areas, no grey shading, no gradient, no "
    "airbrushed tone. Everything that is not a line stays as the bare off-white paper. The picture must read as "
    "clean blue line-work on white paper, like blue-and-white porcelain (青花瓷).\n"
    "(2) LINE: a single confident deep-cobalt-blue marker, medium thickness, used for every contour, and a "
    "THINNER stroke of the SAME blue for the fine surface patterns. Contours are continuous and crisp with only "
    "a slight hand-drawn wobble. No black, no grey, no other hue, no pencil visible. Never fuzzy or frayed, no "
    "dashes, no doubled sketchy lines, no smudging.\n"
    "(3) PATTERN FILLING: the interior of every shape is filled in with dense BLUE LINE PATTERNS instead of "
    "colour: {deco}. The patterns follow the form of the object - curved lines bend with the vase, small "
    "patterns cluster in the wide parts and thin out on the narrow parts. Line weight stays even and the "
    "patterns stay strictly inside their contour.\n"
    "(4) DENSITY: the pattern must read as rich and full, covering most of each shape's interior, with clean "
    "bare-paper gaps left for breathing room - never a solid blue block.\n"
    "(5) LIGHT: {light}\n"
    "EXCEPTION - step 1 only: loose light-grey PENCIL construction lines, thin and faint, simple ovals and "
    "blocky shapes, no marker at all."
)

# --- 撕纸拼贴专用：撕出来的毛边纸块，贴平，再用马克笔添画 -------------------
STROKE_TORN = (
    "MATERIAL LANGUAGE - THIS THEME IS A TORN-PAPER COLLAGE (撕纸拼贴) finished with marker drawing, and this "
    "texture must be visible in every stage.\n"
    "(1) TORN PAPER SHAPES: the large masses of the picture are separate pieces of coloured paper that have "
    "been TORN by hand, not cut. Their outline is therefore slightly irregular and softly fibrous, with a "
    "narrow ragged white fibre fringe along the edge - this ragged edge is essential, it is what proves the "
    "paper was torn. Never a straight scissor-cut edge, never a perfectly smooth vector outline.\n"
    "(2) COLLAGE DEPTH: every paper piece sits flat and slightly raised, casting ONE simple soft grey FLAT "
    "drop shadow onto the paper below, so the layers read clearly as glued-down pieces of paper.\n"
    "(3) MARKER DETAIL: on top of the torn paper, the face, the limbs and all small details are drawn with a "
    "clean broad-tip black MARKER - one confident continuous solid line, crisp and clearly defined with only a "
    "slight natural hand-drawn wobble. No fuzzy edges, no dashes, no doubled sketchy lines.\n"
    "(4) COLOUR: the torn paper pieces are bold high-saturation craft-paper colours that CLASH happily: "
    "{palette}. Flat and even, never printed with gradients or patterns, never muted, never muddy.\n"
    "(5) DECORATION: at least TWO of these - {deco}.\n"
    "(6) LIGHT: {light}\n"
    "EXCEPTION - step 1 only: a light-grey pencil sketch of where each torn piece will go, plus the loose "
    "pencil drawing of the face, thin and faint, no colour at all."
)

SPECS = {}
_ = SPECS.__setitem__

# =====================================================================
# 1. 手指印仙人掌 —— 爆款：手指仙人掌 3921赞 / 卡纸立体仙人掌 3122赞
# =====================================================================
_("手指印仙人掌", dict(
    formula="手指拓印 + 添画（手指仙人掌 3921赞 / 卡纸立体仙人掌 3122赞）",
    palette="cactus green, deep pine green, hot pink, sunny yellow and terracotta orange",
    deco="short fine marker strokes as cactus spines, tiny white spike dots along every rib, small yellow "
         "star flowers, and a row of simple zig-zag triangle patterns around the flowerpot rim",
    light="the light comes from the UPPER LEFT; the pot and the cactus cast one simple FLAT grey-blue shadow "
          "on the paper, drawn as a solid flat shape",
    stroke_extra=(
        "TECHNIQUE OVERRIDE - this theme is a FINGERPRINT painting, and this overrides (2) COLOUR: the green "
        "body of the cactus is built from many overlapping FINGERPRINT DABS of green paint. Each dab is a soft "
        "rounded oval with a slightly uneven, softly feathered edge and a faintly uneven ink density - real "
        "finger-paint texture, matte, with the individual prints still readable as separate overlapping "
        "cushions. Layer two greens: a lighter green for the topmost prints and a deeper pine green for the "
        "prints underneath. The prints tile the body and the arms completely, leaving no white gaps, while the "
        "outer silhouette still stays inside the pencil shape from step 1. The flowerpot, the face, the spines "
        "and every small detail stay in the clean crisp marker-line language."),
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "ONE big cheerful saguaro cactus stands in a terracotta flowerpot, placed slightly LEFT of centre and "
        "filling most of the paper. The cactus body is a tall upright oval; it has THREE arms made of the same "
        "rounded oval shape - two growing out on the LEFT and one on the RIGHT, each arm bending upward. On the "
        "very top of the head sits one big HOT PINK cactus flower with five round petals and a sunny yellow "
        "centre, and a smaller half-open yellow flower buds on the right arm. The cactus has a happy face in "
        "the upper third of its body: TWO big round black eyes each with a white glint, a small open smiling "
        "mouth, and two pink cheek dots. The pot is a simple wide trapezoid with a thick rim band, decorated "
        "with the zig-zag triangle row. Around the base of the pot lie five small pebbles and one tiny "
        "sprouting seedling. The background stays bare off-white paper with only the flat shadow."),
    finish=(
        "The finished artwork: one big fingerprint-painted saguaro cactus in a decorated terracotta pot, the "
        "green body clearly built from many overlapping finger-print dabs in two greens, three rounded arms, a "
        "hot pink flower with a yellow centre on top, a happy face with big black eyes and pink cheeks, short "
        "fine marker spines all over the body and arms, zig-zag triangles on the pot rim, white highlight dots "
        "on every print ridge, five pebbles and a seedling at the base, and one flat grey-blue shadow on the "
        "bare paper. Bright, bold, joyful, completely finished, nothing left unfinished or sketchy."),
    s1=(
        "THIS IS STEP 1 OF 5 - the light pencil scaffolding, and NOTHING else. In faint thin light-grey pencil "
        "draw a wide trapezoid flowerpot with a thick rim band at the bottom centre-left, a tall upright oval "
        "for the cactus body above it, three rounded oval arms (two on the left, one on the right, each bending "
        "upward), and a small five-petal circle for the flower on top. Draw two light circles where the eyes "
        "will go and one small oval for the mouth. Simple, loose, faint construction shapes only - no marker, "
        "no colour, no detail, no texture, no shading."),
    s2=(
        "THIS IS STEP 2 OF 5 - the fingerprint body. Keep every pencil line exactly where it is and now print "
        "the green body: load a fingertip with green paint and press it down over and over, print by print, to "
        "tile the whole tall body and all three arms with overlapping rounded dabs. Use a lighter fresh green "
        "for the newest prints on top and a deeper pine green for the prints underneath them, so the body "
        "gains a real hand-printed cushion texture with two greens. Print right up to the pencil outline - the "
        "prints must cover the body and arms completely with no bare white gaps - but do not print over the "
        "face area, and do not print outside the pencil silhouette. No flower, no pot colour, no spines, no "
        "details yet."),
    s3=(
        "THIS IS STEP 3 OF 5 - the marker drawing. Nothing about the green printed body changes. With the "
        "clean black marker draw the flowerpot outline, its thick rim band and the zig-zag triangle row along "
        "the rim. Then draw the cactus face: two big round black eyes painted solid black and each carrying a "
        "white glint, a small open smiling mouth, and two pink cheek dots. Then the spines: short fine black "
        "marker strokes and small white spike dots along every rib of the body and the arms. No colour fill "
        "anywhere else, no flower colour yet."),
    s4=(
        "THIS IS STEP 4 OF 5 - decoration and highlights, the step that makes it come alive. Colour the hot "
        "pink flower with its sunny yellow centre and add the small yellow bud on the right arm. Colour the "
        "flowerpot terracotta orange with a deeper orange rim band, leaving the zig-zag pattern visible. Add "
        "one or two pure white highlight dots or a short white arc to every rounded print ridge, to the pot rim "
        "and to the flower petals. Scatter a few small yellow star flowers and tiny white sparkles in the empty "
        "paper around the cactus. Nothing else changes - the printed body, the face and the spines stay exactly "
        "as they are."),
    pages={20: ("步骤一：起 形", "先用铅笔轻轻画出花盆、胖胖的仙人掌身体和两只小胳膊，头顶留一个圆给小花。"),
           21: ("步骤二：手指印", "手指蘸绿色颜料，一个印一个印地按满仙人掌的身体，深浅两种绿叠着印更好看。"),
           22: ("步骤三：勾线添画", "黑笔画出花盆和锯齿花纹，再点上大眼睛、小嘴巴和腮红，最后加短短的刺。"),
           23: ("步骤四：装饰高光", "给小花涂粉色、花盆涂橙色，每个印子鼓起来的地方点一小点白高光。"),
           24: ("步骤五：加背景", "周围撒几朵黄色小星星，花盆底下加一块灰蓝影子，画面就站稳了。")},
    real2=["真实的仙人掌", "花盆和颜料"],
    scenes=["手指蘸颜料", "按手印", "阳台上的仙人掌", "仙人掌开花", "多肉植物", "小花花", "颜料盘"],
))

# =====================================================================
# 2. 保鲜袋拓印花海 —— 爆款：保鲜袋拓印秋日花海 2088赞 / 树叶拓印瓢虫 1988赞
# =====================================================================
_("保鲜袋拓印花海", dict(
    formula="塑料袋拓印 + 添画（保鲜袋拓印花海 2088赞 / 树叶拓印瓢虫 1988赞）",
    palette="magenta pink, coral orange, violet purple, sunny yellow and leaf green",
    deco="small four-petal flower shapes drawn over the prints, short curved stems with two leaves, tiny "
         "flying dots and short hatch lines in the empty flower gaps",
    light="the light comes from the UPPER LEFT; the hill and the flower mass cast one simple FLAT grey-blue "
          "shadow on the paper, drawn as a solid flat shape",
    stroke_extra=(
        "TECHNIQUE OVERRIDE - this theme is a PLASTIC-BAG PRINTING (拓印), and this overrides (2) COLOUR: the "
        "big masses of blossom are produced by dabbing a scrunched-up plastic bag loaded with paint, so their "
        "surface is a soft cloudy print made of many small overlapping paint dabs with irregular, slightly "
        "fuzzy edges and softly varying ink density - a genuine stamped, dappled, almost cloudy texture, matte "
        "and never perfectly even. Each colour of blossom is printed as its own cloud-shaped mass of dabs. The "
        "overall silhouette of each mass is a simple readable shape from step 1, and the masses overlap so that "
        "later colours print partly over earlier ones. The hill, the stems, the leaves and the petals drawn on "
        "top stay in the clean crisp marker-line language."),
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "a wide sweeping hill of blossoms fills the lower two thirds of the paper - one continuous field of "
        "flowers rolling in a soft curve from the left edge up to a gentle crest at the RIGHT and back down to "
        "the right edge. The flower field is built as FIVE big overlapping cloud-shaped masses, each in one "
        "bold colour: magenta pink at the lower left, coral orange next to it, violet purple in the middle, "
        "sunny yellow towards the right, and a smaller pink mass filling the right end; small four-petal flowers "
        "are drawn in marker on top of each printed mass with clean green stems and two leaves each. A single "
        "tall sunflower with a big round yellow head and brown seed-dotted centre stands at the crest of the "
        "hill, taller than everything else, with two big green leaves on its stem. Two small white butterflies "
        "hover above the left end and one little bee above the right end. The upper third of the paper stays "
        "bare off-white with a few flying dots and sparkles, and one flat grey-blue shadow runs under the foot "
        "of the hill."),
    finish=(
        "The finished artwork: a wide rolling hill of blossoms printed with a scrunched plastic bag, showing "
        "five overlapping cloudy colour masses (magenta pink, coral orange, violet purple, sunny yellow, pink) "
        "with soft stamped dappled texture, each mass carrying small four-petal marker flowers with green stems "
        "and leaves, one tall sunflower with a big yellow head and brown dotted centre standing at the crest, "
        "two white butterflies and one bee in the bare upper paper, scattered dots and sparkles, and one flat "
        "grey-blue shadow under the hill. Bright, bold, joyful, completely finished, nothing left unfinished "
        "or sketchy."),
    s1=(
        "THIS IS STEP 1 OF 5 - the light pencil scaffolding, and NOTHING else. In faint thin light-grey pencil "
        "draw the sweeping curve of the hill across the lower two thirds of the paper, then divide it into five "
        "overlapping cloud-shaped blobs of roughly equal size that follow the curve of the hill. Draw one tall "
        "vertical line at the crest for the sunflower stem, a light circle for its head, and two light leaf "
        "ovals on the stem. Lightly mark three small circles in the upper paper where the butterflies and the "
        "bee will go. Simple, loose, faint construction shapes only - no marker, no colour, no texture."),
    s2=(
        "THIS IS STEP 2 OF 5 - the plastic-bag printing. Keep every pencil line exactly where it is. Now, one "
        "colour at a time, dab a scrunched-up plastic bag loaded with paint over the pencil blobs to fill each "
        "cloud mass with a soft dappled print of overlapping paint dabs, with irregular slightly fuzzy edges and "
        "gently varying ink density, overlapping the neighbouring mass a little: magenta pink in the lower left "
        "cloud, coral orange next, violet purple in the middle, sunny yellow towards the right, and pink in the "
        "right-hand cloud. Fill each mass completely with printed texture, out to its pencil boundary and no "
        "further. Leave the tall sunflower stem, the butterflies and the bee untouched - they come later. No "
        "marker lines or small flowers yet."),
    s3=(
        "THIS IS STEP 3 OF 5 - the marker drawing on top of the print. Nothing about the printed colour masses "
        "changes. With the clean marker draw the small four-petal flowers over the printed masses - about seven "
        "of them spread across the hill, each with clean green stems and two small green leaves. Draw the tall "
        "sunflower at the crest: a big round yellow head with a brown centre filled with small seed dots, and "
        "two big green leaves on its stem. Draw the two white butterflies and the small striped bee in the bare "
        "upper paper. Clean marker line-work only, no new printed texture."),
    s4=(
        "THIS IS STEP 4 OF 5 - decoration and highlights, the step that makes it come alive. Give every drawn "
        "flower a bright yellow or white centre dot, put one or two pure white highlight dots or a short white "
        "arc on the sunflower head, on both butterfly wings and on the bee. Add short curved hatch lines inside "
        "a few flower centres. Scatter small flying dots and a few tiny four-point sparkles through the empty "
        "upper paper and into the gaps between the colour masses. Nothing else changes - the prints, the stems "
        "and the silhouettes stay exactly as they are."),
    pages={20: ("步骤一：起 形", "铅笔先把小山坡的弧线画出来，再分成五个圆滚滚的花丛，顶上留一根高高的向日葵。"),
           21: ("步骤二：塑料袋拓印", "保鲜袋揉一揉蘸上颜料，一按一按把五个花丛印满，颜色压着颜色最好看。"),
           22: ("步骤三：添画小花", "黑笔在印好的花丛上画小花瓣，加上绿色的花茎和两片叶子，山顶画大向日葵。"),
           23: ("步骤四：装饰高光", "花心点黄点，向日葵和蝴蝶加白高光，空白处撒小飞点和星星。"),
           24: ("步骤五：加背景", "花丛底下加一条灰蓝影子，画面立刻站稳，一片花海就完成了。")},
    real2=["真实的鲜花", "保鲜袋和颜料"],
    scenes=["塑料袋蘸颜料", "按压拓印", "秋天的花海", "向日葵", "蝴蝶采蜜", "颜料盘", "小朋友印花"],
)) 

# =====================================================================
# 3. 线描青花瓷瓶 —— 爆款：青花瓷线描瓶子 1734赞 / 线描蔬菜写生合集 4075赞
# =====================================================================
_("线描青花瓷瓶", dict(
    formula="纯线描 + 图案填充（青花瓷线描瓶子 1734赞 / 线描蔬菜写生 4075赞）",
    palette="deep cobalt blue only, on bare off-white paper - no second colour",
    deco="a band of repeated lotus-petal outlines around the belly, rows of small spiral curls, a wave-fret "
         "border band at the neck and the foot, a diagonal cross-hatch lattice behind the big flower, and "
         "small dotted speckle clusters filling the leftover corners",
    light="drawing only - there is no shadow and no shading; the only tonal difference comes from how densely "
          "the blue line patterns are packed inside each shape",
    stroke=STROKE_LINE,
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "ONE tall elegant Chinese porcelain vase (青花瓷) stands centred on the paper, drawn in blue line-work "
        "only. The vase has a narrow neck, a softly swelling round belly and a small flared foot, with a clean "
        "horizontal band at the neck and another at the foot. Inside the belly a big stylised lotus flower "
        "blooms with three open petals and a rounded seed pod, flanked by two curling blue-green leaves rendered "
        "purely as blue outlines with vein lines. The belly also carries the band of repeated lotus-petal "
        "outlines running around the widest part, a wave-fret border band, rows of small spiral curls and a "
        "diagonal cross-hatch lattice in the remaining space. To the LEFT of the vase stand three tall thin "
        "reeds, and to the RIGHT two small round cups with the same blue patterns; one tiny white butterfly "
        "hovers above the vase mouth. The background is completely bare off-white paper - no table, no wall, no "
        "shadow, no horizon line."),
    finish=(
        "The finished artwork: a pure blue line drawing of one tall elegant blue-and-white porcelain vase with "
        "a big stylised lotus blossom, curling leaf outlines with veins, a lotus-petal band around the belly, "
        "wave-fret border bands at the neck and foot, rows of spiral curls and a diagonal cross-hatch lattice "
        "filling the interior, plus three thin reeds on the left, two small patterned cups on the right and one "
        "tiny butterfly above the mouth. Everything is one cobalt blue marker line on bare off-white paper, "
        "there is no colour filling at all, the patterns are dense and rich, the line work is crisp and clean, "
        "and the bare paper is used as breathing room. Completely finished, nothing left sketchy."),
    s1=(
        "THIS IS STEP 1 OF 5 - the light pencil scaffolding, and NOTHING else. In faint thin light-grey pencil "
        "draw the outline of one tall vase: a narrow neck, a softly swelling round belly, a small flared foot, "
        "with a light line across the neck and another across the foot for the border bands. Draw a light "
        "circle for the lotus flower inside the belly and three light petal shapes around it. Draw three thin "
        "vertical lines for the reeds on the left, two small ovals for the cups on the right, and a small cross "
        "shape for the butterfly above the vase mouth. Simple, loose, faint construction shapes only - no "
        "marker, no blue, no pattern, no colour."),
    s2=(
        "THIS IS STEP 2 OF 5 - the blue contour drawing. Trace the whole vase, the reeds, the two cups and the "
        "butterfly with the clean deep-cobalt-blue marker, in one confident continuous crisp line of even "
        "medium thickness with only a slight hand-drawn wobble. Draw the lotus flower and its two leaves as "
        "clean blue outlines inside the belly, and draw the border band lines across the neck and the foot. "
        "Every pencil line becomes a clean blue line; nothing else is added yet. No pattern filling, no "
        "hatching, no fill of any kind - the interior stays bare paper."),
    s3=(
        "THIS IS STEP 3 OF 5 - the pattern drawing, the step that makes the vase read as porcelain. Keep every "
        "contour exactly as it is and now fill the interiors with dense BLUE LINE PATTERNS using a thinner "
        "stroke of the same blue: the band of repeated lotus-petal outlines running around the widest part of "
        "the belly, a wave-fret border band at the neck and another at the foot, rows of small spiral curls "
        "filling the shoulder and the base, a diagonal cross-hatch lattice packed behind the big lotus flower, "
        "and short vein lines inside the two leaves. Add the same lotus-petal band and spiral curls to the two "
        "small cups. The patterns must bend and follow the swelling form of the vase and stay strictly inside "
        "their contour, leaving clean bare-paper gaps between pattern groups."),
    s4=(
        "THIS IS STEP 4 OF 5 - deepening the line work. Still blue lines only, no colour fill anywhere. "
        "Strengthen and thicken the main outer contour of the vase, the lotus flower and the rim bands so the "
        "big shapes read clearly. Add small dotted speckle clusters and a few tiny star crosses in the "
        "remaining bare corners inside the belly and in the empty paper beside the vase. Add the wing pattern "
        "lines to the butterfly. Check the density: the patterns should look rich and full with clean bare "
        "paper breathing room, never a solid blue block. Nothing else changes."),
    pages={20: ("步骤一：起 形", "铅笔轻轻画出花瓶的瓶口、圆肚子和小底座，肚里留一个圆给大莲花。"),
           21: ("步骤二：勾 线", "蓝笔把花瓶和旁边的小杯子、芦苇、蝴蝶全部描一遍，线条要一口气画完。"),
           22: ("步骤三：画花纹", "细蓝笔在肚子上画莲瓣纹、波浪纹和小卷卷，莲花后面加斜格子，越密越像瓷器。"),
           23: ("步骤四：加深", "把花瓶外轮廓和莲花描粗一点，空的地方点上小点和小星星，花纹疏密就出来了。"),
           24: ("步骤五：加背景", "什么都不涂，只在旁边加几只小蝴蝶和飘落的花瓣，留白就是青花瓷的气质。")},
    real2=["真实的青花瓷瓶", "蓝色马克笔"],
    scenes=["青花瓷花瓶", "瓷器花纹特写", "莲花", "中国传统纹样", "芦苇", "蓝色颜料", "小朋友画线描"],
))

# =====================================================================
# 4. 撕纸小怪兽 —— 爆款：撕纸技巧 15816赞 / 超轻粘土多巴胺怪兽 6387赞
# =====================================================================
_("撕纸小怪兽", dict(
    formula="撕纸拼贴 + 添画（撕纸技巧 15816赞 / 多巴胺怪兽画框 6387赞）",
    palette="violet purple, hot magenta, bright tangerine, lime green and sunflower yellow",
    deco="a zig-zag crown of triangle spikes along the top of the head, three big round polka dots on the "
         "body, a row of short vertical dashes as fur along the sides, and small four-point star sparkles in "
         "the empty paper",
    light="the light comes from the UPPER LEFT; every torn paper piece casts ONE simple soft grey FLAT drop "
          "shadow onto the paper beneath it, so the layers read as glued-down paper",
    stroke=STROKE_TORN,
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "ONE big friendly monster stands planted in the middle of the paper, filling most of the sheet, made of "
        "torn paper pieces. The body is one large tangerine rectangle of torn paper with softly ragged edges; "
        "on top of it sit three big round polka dots of violet purple torn paper. The head is a big violet "
        "purple torn paper oval resting on the body, and along the top of the head a zig-zag crown of FIVE "
        "triangle spikes is cut from lime green torn paper. The monster has THREE round eyes in a row - one big "
        "hot magenta eye in the centre drawn with marker, a smaller lime green eye on the left and a smaller "
        "sunflower yellow eye on the right - each with a solid black pupil and a white glint. Below the eyes a "
        "wide open smiling mouth is drawn in marker with two small white teeth and a coral pink tongue. Two "
        "chunky torn-paper arms of lime green stick out to the left and right, held up in the air, each ending "
        "in three marker-drawn claw fingers, and two short violet purple torn-paper legs stand at the bottom. "
        "The background stays bare off-white paper apart from a few star sparkles and the flat drop shadows."),
    finish=(
        "The finished artwork: one big friendly monster built from torn coloured paper - a tangerine torn-paper "
        "body with three violet polka dots, a violet oval head topped by a zig-zag crown of five lime-green "
        "torn-paper spikes, three round eyes in a row (magenta, lime, yellow) with black pupils and white "
        "glints, a wide marker-drawn smile with two white teeth and a coral pink tongue, two chunky lime-green "
        "torn-paper arms raised in the air with three claw fingers each, and two short violet legs. Every paper "
        "piece shows its soft ragged white fibre fringe and casts one flat grey drop shadow, the marker details "
        "are clean and crisp, and a few four-point star sparkles float in the bare paper. Bright, bold, playful, "
        "completely finished, nothing left unfinished or sketchy."),
    s1=(
        "THIS IS STEP 1 OF 5 - the light pencil scaffolding, and NOTHING else. In faint thin light-grey pencil "
        "sketch where each torn paper piece will go: a large rectangle for the body in the middle, a big oval "
        "for the head above it, a zig-zag row of five triangle spikes along the top of the head, three circles "
        "in a row for the eyes, a wide oval for the mouth, two chunky rectangles for the raised arms and two "
        "short rectangles for the legs. Simple, loose, faint construction shapes only - no colour, no marker, "
        "no paper, no texture, no shading."),
    s2=(
        "THIS IS STEP 2 OF 5 - the torn paper collage. Keep every pencil guide exactly where it is and now tear "
        "the paper pieces by hand and glue them down: a large TANGERINE torn-paper rectangle for the body, a "
        "large VIOLET PURPLE torn-paper oval for the head, three LIME GREEN torn-paper triangle spikes forming "
        "a zig-zag crown along the top of the head, two chunky LIME GREEN torn-paper arms raised at the sides "
        "and two short VIOLET PURPLE torn-paper legs at the bottom. Every piece must show a softly ragged, "
        "irregular torn edge with a narrow white fibre fringe - never a straight cut edge - and each piece must "
        "sit flat on the paper casting one simple flat grey drop shadow onto the layer below it. Do not add any "
        "marker drawing, no eyes, no mouth, no dots yet."),
    s3=(
        "THIS IS STEP 3 OF 5 - the marker drawing on the collage. Nothing about the torn and glued paper pieces "
        "changes. With the clean black marker draw the face on the violet head: three round eyes in a row - a "
        "big magenta eye in the centre, a smaller lime green eye on the left and a smaller sunflower yellow eye "
        "on the right - each with a solid black pupil and a white glint, then a wide open smiling mouth with "
        "two small white teeth and a coral pink tongue. Draw three claw fingers at the end of each raised arm. "
        "Clean crisp marker lines only, on top of the paper - no new paper pieces, no colouring outside the "
        "eyes and the mouth."),
    s4=(
        "THIS IS STEP 4 OF 5 - decoration and highlights, the step that makes it come alive. Add three big hot "
        "magenta torn-paper polka dots to the tangerine body, a row of short vertical black marker dashes as fur "
        "along both sides of the body, and a row of short black dashes along the arms. Put one or two pure "
        "white highlight dots or a short white arc on every eye and on each polka dot. Scatter small four-point "
        "star sparkles in the empty paper around the monster. Nothing else changes - the paper pieces, the "
        "ragged torn edges and the drop shadows stay exactly as they are."),
    pages={20: ("步骤一：起 形", "铅笔先画好怪兽的身体、大脑袋、头上的三角尖尖和举起来的两只胳膊。"),
           21: ("步骤二：撕纸拼贴", "用手撕出彩纸块（撕出来的毛边最好看），一块块贴上去，记得压出小影子。"),
           22: ("步骤三：勾线添画", "黑笔在脑袋上画三只大眼睛和哈哈大笑的嘴巴，胳膊上加三根手指。"),
           23: ("步骤四：装饰高光", "身体贴三个大圆点，边上加短毛毛，眼睛和圆点都点上白高光。"),
           24: ("步骤五：加背景", "周围撒几颗小星星，撕纸的毛边和小影子就是它最可爱的地方。")},
    real2=["真实的彩纸", "剪刀和胶棒"],
    scenes=["撕纸的手", "彩色卡纸", "拼贴画", "怪兽表情", "手工作品展示", "胶棒", "小朋友撕纸"],
))

# =====================================================================
# 5. 松果猫头鹰 —— 爆款：捡松果DIY猫头鹰 8545赞
# =====================================================================
_("松果猫头鹰", dict(
    formula="自然材料拼贴 + 添画（捡松果DIY猫头鹰 8545赞）",
    palette="pinecone brown, warm chestnut, cream white, leaf green and amber yellow",
    deco="rows of overlapping scallop half-circles as feather scales, short fine dot clusters inside each "
         "scale, a small V-shaped chest pattern, and tiny leaf-and-berry sprigs filling the bare corners",
    light="the light comes from the UPPER LEFT; the owl and the branch cast one simple FLAT grey-blue shadow "
          "on the paper, drawn as a solid flat shape",
    stroke_extra=(
        "TECHNIQUE OVERRIDE - this theme is a NATURAL-MATERIAL COLLAGE, and this overrides (2) COLOUR: the "
        "owl's wings and lower body are REAL PINE CONES, shown as two clearly recognisable pine cones with the "
        "natural overlapping woody scale texture - each scale a small rounded woody plate with a slightly uneven "
        "raised edge and a soft natural shadow between the scales, in warm pinecone brown and chestnut with "
        "lighter amber highlights on the scale tips. The pine cones keep their own natural material texture and "
        "are NOT repainted in flat poster colour. The head, the face, the eyes, the chest, the feet and the "
        "branch are drawn in the clean crisp marker-line language, and the small leaves and berries stuck "
        "around them are simple flat paper shapes with clean edges."),
    lock=(
        "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "ONE round friendly owl perches in the centre of the paper on a single horizontal branch, filling most "
        "of the sheet. The owl's head is a big round cream-white shape with two ear tufts of three small "
        "triangle feathers each; it has TWO very big round amber-yellow eyes, each with a solid black pupil and "
        "one white glint, a small orange triangular beak between them and a light chestnut heart-shaped face "
        "disc. The chest below the head is cream white with rows of overlapping scallop feather scales. The two "
        "wings, tucked along the left and right sides of the body, are TWO REAL PINE CONES held at a slight "
        "angle, their natural woody scales clearly readable; the lower belly between them is a third smaller "
        "pine cone. Two little chestnut feet with three toes each grip the branch, and a short tail of three "
        "feathers hangs below. The branch runs across the paper with two small leaf-and-berry sprigs branching "
        "off it, and three small flying dots plus a tiny crescent moon shape sit in the bare upper paper."),
    finish=(
        "The finished artwork: a round friendly owl perched on a branch, built from natural materials and "
        "drawing - a cream-white head with ear tufts and a heart-shaped chestnut face disc, two very big round "
        "amber-yellow eyes with black pupils and white glints, a small orange beak, a cream-white chest covered "
        "in overlapping scallop feather scales, and TWO REAL PINE CONES forming the wings with a third smaller "
        "pine cone as the belly, their natural woody scale texture clearly readable in browns and chestnuts "
        "with amber highlights. Two chestnut feet grip the branch, three tail feathers hang below, leaf-and-"
        "berry sprigs branch off the branch, three small flying dots and a tiny crescent moon float in the bare "
        "paper, and one flat grey-blue shadow grounds the scene. Bright, warm, completely finished, nothing "
        "left unfinished or sketchy."),
    s1=(
        "THIS IS STEP 1 OF 5 - the light pencil scaffolding, and NOTHING else. In faint thin light-grey pencil "
        "draw one horizontal branch across the paper, a big round circle for the owl's head above it, a rounded "
        "oval for the body, two pointed oval shapes on the left and right of the body where the pine-cone wings "
        "will go, a smaller oval between them for the belly, two light circles for the big eyes and a small "
        "triangle for the beak. Add three light lines for the tail below. Simple, loose, faint construction "
        "shapes only - no marker, no colour, no texture, no shading."),
    s2=(
        "THIS IS STEP 2 OF 5 - the marker drawing of the owl. Keep every pencil line exactly where it is and "
        "now draw the owl in clean marker lines: the round head outline, the two ear tufts made of three small "
        "triangle feathers each, two very big round eyes with solid black pupils and a white glint, the small "
        "orange triangular beak, the heart-shaped face disc around the eyes, the cream-white body and the rows "
        "of overlapping scallop feather scales across the chest, two little chestnut feet with three toes each "
        "gripping the branch, and a short tail of three feathers. Clean crisp marker lines only - no pine "
        "cones, no leaf sprigs, no background yet, and no colour outside the pupils, the beak and the face "
        "disc."),
    s3=(
        "THIS IS STEP 3 OF 5 - the colour. Fill the head cream white with a light chestnut heart-shaped face "
        "disc, keep the two big eyes bright amber yellow around their solid black pupils, colour the beak "
        "orange, colour the chest cream white and leave the scallop scale lines visible as clean outlines. "
        "Colour the feet and the tail chestnut brown and the branch a warm brown with two darker bark line "
        "strokes. Flat poster colour inside the outlines only, evenly covered, no gradient, no shading. Leave "
        "the two pine-cone wing areas as bare paper for now - they are added in the next step."),
    s4=(
        "THIS IS STEP 4 OF 5 - the natural-material collage and the highlights. Glue TWO REAL PINE CONES onto "
        "the left and right wing areas, held at a slight angle, and a THIRD smaller pine cone between them as "
        "the lower belly - each pine cone must show its natural overlapping woody scales with slightly uneven "
        "raised edges and soft natural shadows between the scales, in warm pinecone brown and chestnut with "
        "lighter amber highlights on the scale tips, keeping its own material texture and NOT repainted in flat "
        "poster colour. Add two small leaf-and-berry sprigs branching off the branch. Then add one or two pure "
        "white highlight dots or a short white arc to every big eye, to the beak and to the head. Nothing else "
        "changes."),
    pages={20: ("步骤一：起 形", "铅笔画出树干、圆圆的大脑袋、胖身体，两边留两个位置给松果翅膀。"),
           21: ("步骤二：勾 线", "黑笔先画猫头鹰：耳朵、两只大圆眼睛、小尖嘴、胸前一片片小羽毛。"),
           22: ("步骤三：铺 色", "脸上浅棕色、胸前奶白色、眼睛琥珀黄、嘴巴橙色，树干涂棕色。"),
           23: ("步骤四：贴松果", "把真松果贴在两边当翅膀、下面一个当肚子，再点上白高光，羽毛就毛茸茸了。"),
           24: ("步骤五：加背景", "树枝上加小叶片和小果子，空白处点小飞点和一个小月亮，猫头鹰就活了。")},
    real2=["真实的松果", "树枝和小果子"],
    scenes=["捡松果", "松果特写", "猫头鹰", "树林里的树枝", "小叶片和浆果", "秋天的树林", "手工作品展示"],
))

THEME = {
    "手指印仙人掌":   ("3E8B4A", "1F5C2C", "F4F1E4", "E8557F"),
    "保鲜袋拓印花海": ("D9455F", "8E2A44", "FFF3E8", "6C4BB6"),
    "线描青花瓷瓶":   ("1B3F8B", "0E2557", "F5F8FF", "D9542B"),
    "撕纸小怪兽":     ("6C4BB6", "3A2560", "FFF1DD", "E8873A"),
    "松果猫头鹰":     ("8A5A2B", "573516", "FDF3DF", "4A8B3B"),
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
    p["common"]["stroke"] = st.format(palette=spec["palette"],
                                      deco=spec["deco"], light=spec["light"])

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
    print("[ok] %-18s -> %s" % (name, d))
    print("     配色 %s  %s" % (pri, spec["formula"]))
    print("     步骤名 %s" % " / ".join(slots[1:]))


for _n, _s in SPECS.items():
    build(_n, _s)
print("\n共写入 %d 个课题" % len(SPECS))
