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
