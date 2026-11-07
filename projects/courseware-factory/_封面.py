# -*- coding: utf-8 -*-
"""生成课题封面候选（A 四宫格 / B 实物对照 / C 桌面实拍），1024x1024。

用法：
  python _封面.py                 # 全部课题，每个 3 张
  python _封面.py 树叶逃跑啦       # 只做指定课题
  python _封面.py --force         # 已存在也重做
每个课题用自己 img/范画成品.png 当参考图，保证"画的跟封面一致"。
"""
import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = r"C:/Users/hua/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"
GRSAI = os.path.expanduser("~/.pi/agent/skills/grsai-image-2-5/scripts/grsai.py")
MODEL, QUALITY, ASPECT = "gpt-image-2.5", "high", "1024x1024"
NO_TEXT = ("No text anywhere, no letters, no words, no numbers, no logo, no watermark, no signature. "
           "Bright cheerful high-saturation colours, clean appetising look, sharp focus, professional "
           "product photography.")

HAND = ("a small child's hand and forearm ONLY - no face, no head, no body, no arm above the elbow - ")

# 每课题：画的是啥 / 真实实物 / 马克笔颜色
COVERS = {
    "树叶逃跑啦": dict(
        draw="five anthropomorphic autumn leaves of different shapes and bold colours running in single file "
             "along a rising diagonal, each with two big round black eyes, a smiling mouth, pink cheek dots, "
             "little running legs and a white highlight arc, chased by loose grey-blue wind lines",
        real="a handful of freshly gathered real autumn leaves - a red maple leaf, a yellow ginkgo leaf and an "
             "orange oak leaf - laid on the table",
        colors="maple red, amber yellow, pumpkin orange, coral pink, leaf green and black"),
    "把秋天装进罐子": dict(
        draw="a tall clear glass jar standing upright and filled with flat-painted autumn leaves, three acorns "
             "and a pine cone, with four small leaves and one acorn floating up out of the jar towards the "
             "top right on two wind lines",
        real="a real clear glass jar with a metal lid, a handful of real acorns and one real pine cone on the "
             "table",
        colors="amber yellow, chestnut brown, maple red, sky blue, leaf green and black"),
    "路灯下的小猫": dict(
        draw="a street lamp head at the top right throwing one hard straight-edged wedge of lemon-yellow light "
             "diagonally down to the lower left across a deep prussian-blue night, with a small white cat with "
             "pink cheeks sitting inside the light and three black little houses with white windows and a "
             "crescent moon outside it",
        real="a real small desk lamp switched on in a dim room, casting one hard-edged triangle of warm light "
             "across the dark table",
        colors="bright lemon yellow, deep prussian blue, black, white, coral pink and grey"),
    "蚂蚁搬月亮": dict(
        draw="five small flat-black ants marching in a line along a rising diagonal, all carrying one big "
             "glowing lemon-yellow crescent moon shoulder-high, with a small green leaf flag at the front, a "
             "pale-yellow pool of light on the ground and white star dots in the night sky",
        real="a row of real black raisins lined up on the table like little ants, next to a crescent-shaped "
             "piece of pale yellow melon",
        colors="deep night blue, bright lemon yellow, leafy green, black, white and coral pink"),
    "黑白小甲虫的花园": dict(
        draw="one big round black-and-white beetle in the centre of the paper, its body filled with clean "
             "black vertical stripes, polka dots and a small checker grid instead of colour, surrounded by "
             "vivid green leaves and flat sunflower-yellow, magenta-pink and pumpkin-orange flowers",
        real="a real glossy black-and-white patterned beetle figurine standing on a real green leaf next to "
             "one real yellow flower",
        colors="pure black, white, vivid leaf green, sunflower yellow, pumpkin orange and magenta pink"),
    "棉签点彩大树": dict(
        draw="a tree with a thick solid black trunk and four heavy branches, its whole crown made of densely "
             "dotted clusters of sunflower-yellow, pumpkin-orange, maple-red and deep-green dots, with a "
             "large calm empty white space in the middle of the crown where one small orange fox sits looking "
             "up at the tree",
        real="a bundle of real white cotton swabs lying on the table next to a small real saucer of yellow, "
             "orange and red paint",
        colors="sunflower yellow, pumpkin orange, maple red, deep leafy green, black and white"),
    "纸杯长颈鹿": dict(
        draw="a flat children's marker drawing of a giraffe body with four legs and large polka-dot patches, "
             "where the neck and head is a REAL plain yellow paper cup standing upside-down on the paper with "
             "two paper ears, two paper horns and big round black eyes drawn on the side of the cup",
        real="two or three real plain yellow paper cups standing upright on the table, with a real pair of "
             "scissors and a glue stick",
        colors="sunflower yellow, chestnut brown, white, leaf green, sky blue and black"),
    "会翻跟头的西瓜": dict(
        draw="one big round watermelon with big black eyes, a wide happy open mouth and pink cheeks, tilted "
             "over mid-somersault with two grey speed arcs spinning around it, plus a separate cut-out paper "
             "watermelon slice standing up off the paper with flat black seeds",
        real="half a real juicy watermelon and one real triangular slice of watermelon with black seeds, on "
             "the light wooden table",
        colors="watermelon red, deep leaf green, black, white, coral pink and pale yellow"),
    "秋日小画合集": dict(
        draw="a hand-drawn three-by-three grid of nine small squares on one sheet of paper, each square "
             "holding one simple flat-coloured autumn object with tiny eyes and a white highlight - a maple "
             "leaf, an acorn, a pine cone, a red mushroom, a small hedgehog, a chestnut, an open umbrella, a "
             "round pumpkin and a little round bird",
        real="a real collection of autumn treasures arranged on the table - a pine cone, two acorns, a "
             "chestnut, a small mushroom and a handful of real autumn leaves",
        colors="maple red, amber yellow, pumpkin orange, chestnut brown, deep leafy green, violet purple and "
                "black"),
}

HEAD = ("A square promotional cover image for a children's art class course, flat overhead view, warm soft "
        "daylight from the upper left, photographed on a light wooden classroom table. It is a REAL "
        "photograph of real paper and real objects.\n\n")
DRAW = ("the finished children's marker drawing on off-white paper: {draw}; laid flat on the paper, crisp "
        "and sharp, visible paper texture and a soft flat shadow.\n\n")


def a_prompt(c):
    return HEAD + \
        "A four-panel collage arranged as a 2x2 grid with thin clean white gaps between the panels.\n\n" + \
        "Panel 1 (top left): " + DRAW.format(**c) + \
        "Panel 2 (top right): a real macro photograph of " + c["real"] + ".\n\n" + \
        ("Panel 3 (bottom left): a real top-down photograph of the drawing tools laid out neatly in a row on "
         "the wooden table - six chunky children's marker pens in " + c["colors"] +
         ", one glue stick, one small pair of scissors, and three sheets of coloured card.\n\n") + \
        ("Panel 4 (bottom right): a real photograph of " + HAND +
         "holding a thick black marker pen, caught in the middle of colouring the drawing, the pen tip "
         "touching the paper.\n\n") + NO_TEXT


def b_prompt(c):
    return HEAD + \
        ("On the LEFT half: a real photograph of " + c["real"] + ".\n\n") + \
        ("On the RIGHT half: the very same subject as " + DRAW.format(**c)) + \
        ("In the bottom left corner " + HAND + "reaches in and touches the real object.\n\n"
         "The two halves sit side by side so the viewer instantly reads \"real object, then drawing\".\n\n") + \
        NO_TEXT


def c_prompt(c):
    return HEAD + \
        ("In the centre lies a slightly curled sheet of off-white paper carrying " + DRAW.format(**c)) + \
        ("Around the paper, casually scattered in a natural real mess: six chunky children's marker pens with "
         "their caps off in " + c["colors"] + ", one glue stick, one small pair of scissors, two sheets of "
         "coloured card, and " + c["real"] + ".\n\n") + \
        ("A real photograph of " + HAND + "entering from the bottom right holding a thick black marker pen, "
         "resting on the paper as if the drawing was just finished. Real shadows, warm natural light.\n\n") + \
        NO_TEXT


CAND = [("A_四宫格", a_prompt), ("B_实物对照", b_prompt), ("C_桌面实拍", c_prompt)]

# ---- 旧课件（已画完，只补封面）---------------------------------------
COVERS.update({
    "大熊猫吃竹子": dict(
        draw="a chubby giant panda cub sitting facing the viewer, holding one bamboo stalk diagonally "
             "across its chest with both front paws and three slender green leaves sprouting at the top, "
             "with big black eye patches, a small smile and pink cheeks",
        real="a bundle of real fresh bamboo stalks with slender green leaves, plus two real bamboo shoots",
        colors="leaf green, sunflower yellow, black, white, coral pink and sky blue"),
    "小兔子吃萝卜": dict(
        draw="a chubby white rabbit sitting facing the viewer with two long upright ears with soft pink "
             "inner ears, holding one bright orange carrot with a leafy green top diagonally across its "
             "chest, a small fluffy white tail, pink cheeks and whiskers",
        real="two real fresh carrots with their green leafy tops still on",
        colors="pumpkin orange, leaf green, white, coral pink, sunflower yellow and black"),
    "小松鼠藏松果": dict(
        draw="a chubby little red squirrel sitting upright facing the viewer with a very large fluffy "
             "tail curving up behind it, holding one pine cone in front of its chest with both little "
             "paws, a cream belly patch and pale pink cheeks",
        real="three real pine cones and a small pile of real pine needles",
        colors="chestnut brown, amber yellow, chestnut red, cream, leaf green and black"),
    "小象洗澡": dict(
        draw="a chubby little grey baby elephant sitting in shallow pond water facing the viewer, with "
             "two huge round floppy ears, a short stubby trunk curled down, four thick stumpy legs and a "
             "short tail, its trunk holding one bright green lotus pod with small round holes on top",
        real="a real shallow basin of water with a real green lotus pod and two real lotus leaves floating in it",
        colors="sky blue, sunflower yellow, leaf green, soft grey, coral pink and black"),
})


# ---- 第二轮 5 个新课题 ------------------------------------------------
COVERS.update({
    "手指印仙人掌": dict(
        draw="one big happy saguaro cactus in a terracotta flowerpot, its whole green body and all three "
             "rounded arms clearly built from many overlapping finger-print dabs in two greens, a hot pink "
             "flower with a sunny yellow centre on top, two big round black eyes with white glints, pink "
             "cheek dots, short fine marker spines all over, and a row of zig-zag triangles on the pot rim",
        real="a real small potted cactus on the table next to a saucer of green finger paint and a sheet of "
             "paper already covered in green finger-print dabs",
        colors="cactus green, deep pine green, hot pink, sunny yellow, terracotta orange and black"),
    "保鲜袋拓印花海": dict(
        draw="a wide rolling hill of blossoms printed with a scrunched plastic bag, made of five overlapping "
             "cloudy colour masses - magenta pink, coral orange, violet purple, sunny yellow and pink - each "
             "carrying small four-petal marker flowers with green stems and leaves, with one tall sunflower "
             "standing at the crest and two white butterflies and a bee above it",
        real="a real scrunched-up plastic bag smeared with paint lying on a paint-covered paper plate next to "
             "a real paint tray",
        colors="magenta pink, coral orange, violet purple, sunny yellow, leaf green and black"),
    "线描青花瓷瓶": dict(
        draw="a pure blue line drawing of one tall blue-and-white porcelain vase carrying a big stylised "
             "lotus blossom, a lotus-petal band around the belly, wave-fret borders at the neck and foot, "
             "rows of spiral curls and a diagonal cross-hatch lattice, filled entirely with blue line patterns "
             "and with no colour filling at all, plus three reeds on the left and two small patterned cups on "
             "the right",
        real="a real blue-and-white porcelain vase standing on the table beside a white paper sheet already "
             "carrying blue line-work and one single blue marker pen",
        colors="deep cobalt blue and white only"),
    "撕纸小怪兽": dict(
        draw="one big friendly monster built from torn coloured paper - a tangerine torn-paper body with "
             "three violet polka dots, a violet oval head topped by a zig-zag crown of five lime-green torn "
             "paper spikes, three round eyes in a row with black pupils and white glints, a wide marker-drawn "
             "smile with two white teeth and a coral pink tongue, and two chunky lime-green torn-paper arms "
             "raised in the air",
        real="a real small pile of hand-torn coloured craft paper pieces with ragged white fibre fringes on "
             "the table, next to a real glue stick",
        colors="violet purple, hot magenta, bright tangerine, lime green, sunflower yellow and black"),
    "松果猫头鹰": dict(
        draw="a round friendly owl perched on a branch, with a cream-white head and two ear tufts, two very "
             "big round amber-yellow eyes with black pupils and white glints, a small orange beak, a "
             "scallop-scaled cream chest, TWO real pine cones forming its wings and a third smaller pine cone "
             "as the belly with their natural woody scale texture clearly readable, two chestnut feet, "
             "leaf-and-berry sprigs on the branch and a tiny crescent moon",
        real="three real pine cones of different sizes and a real small twig with green leaves lying on the "
             "table",
        colors="pinecone brown, warm chestnut, cream white, amber yellow, leaf green and black"),
})


# ---- 第三轮 5 个新课题 ------------------------------------------------
COVERS.update({
    "落叶小画布": dict(
        draw="six real pressed dry autumn leaves of six different species scattered across the bare paper, "
             "each leaf used as a tiny canvas and painted on its surface with a different bold high-saturation "
             "pattern - bold diagonal stripes, concentric rings, polka dots, a zig-zag chevron, rows of wavy "
             "scales and a grid of small squares - with tiny cute faces drawn on three of them",
        real="a handful of real pressed dry autumn leaves of different shapes lying on the table next to four "
             "chunky acrylic marker pens",
        colors="terracotta orange, cobalt blue, magenta pink, lime green, sunflower yellow and cream"),
    "花生壳小鸡": dict(
        draw="five little chicks in a loose diagonal line, each chick's body a real whole peanut in its shell "
             "with its natural bumpy honeycomb texture, each wearing marker-drawn round black eyes with white "
             "glints, a tiny orange triangular beak, pink cheek dots, a rounded wing and two thin orange legs, "
             "with a big smiling sun in the upper left, a band of grass with three five-petal flowers along "
             "the bottom and three loose empty peanut shells at the lower right",
        real="a small pile of real whole peanuts in their shells on the table next to one empty split shell and "
             "a glue stick",
        colors="sunflower yellow, grass green, carrot orange, tomato red and sky blue"),
    "冬日黄昏": dict(
        draw="a wide winter dusk landscape painted thickly with a loaded flat brush - a sky of broad "
             "horizontal bands stepping from deep violet blue through purple to bright lemon yellow at the "
             "horizon, a tall bare tree in flat dark silhouette with a fine network of branches on the left, a "
             "small house silhouette with a chimney, a curl of smoke and three windows glowing bright yellow, "
             "a snowy white field with pale blue shadow bands and a bright yellow glowing road sweeping "
             "diagonally down to the lower right, with no outlines anywhere and clearly visible brush texture",
        real="a real flat bristle brush loaded with deep blue and bright yellow paint lying on a paint-smeared "
             "palette next to a sheet of white watercolour paper",
        colors="deep violet blue, purple, bright lemon yellow, glowing amber and flat black"),
    "墙边的花": dict(
        draw="a low brick-lined stone wall along the bottom edge of the paper, with tall daisies leaning in "
             "from the left, tulips and a curling vine rising on the right, a loose garland of leaves and "
             "small blossoms drooping from the two top corners and dense grass with round-leaved plants "
             "spreading over the wall at both bottom corners, so that all four edges are full of flowers and "
             "green while the middle of the sheet is left as a large calm empty white space holding one small "
             "white butterfly",
        real="a handful of real freshly picked daisies and tulips with their green stems lying on the table "
             "beside a short section of real brick wall",
        colors="coral pink, sunflower yellow, violet purple, leaf green, sky blue and cream"),
    "小草六种画法": dict(
        draw="six separate clumps of grass filling the sheet in a loose six-way arrangement, each clump drawn "
             "in a completely different technique - an upright fan of straight even blades, wind-bent blades "
             "with curved wind lines, blades ending in tight spiral curls, tall pointed blades with seed "
             "heads, a soft rounded tuft of short arched strokes with dots, and an outlined-and-filled clump - "
             "each in a visibly different green, with a big smiling sun in the top right corner and one small "
             "five-petal flower beside the bottom left clump",
        real="six chunky green marker pens of visibly different greens lying in a neat row on the table next to "
             "a small real tuft of grass",
        colors="leaf green, deep pine green, lime green, sunflower yellow, sky blue and coral pink"),
})


# ---- 第四轮 5 个新课题 ------------------------------------------------
COVERS.update({
    "撒盐画雪花": dict(
        draw="one big pale six-armed snowflake floating in the centre of a deep wet night wash of indigo, "
             "prussian blue and violet, with five smaller snowflakes of different sizes around it, the whole "
             "night broken up by hundreds of pale starburst salt crystals blooming out of the wash, fine "
             "white marker snowflake arms with short side-branches, small white sparkle dots and a lighter "
             "snowdrift line along the bottom",
        real="a small dish of real table salt on the table next to a still-wet watercolour painting with salt "
             "crystals blooming in it",
        colors="deep night indigo, prussian blue, violet, teal and white"),
    "毛线小鱼": dict(
        draw="one big cheerful fish wound all over with tight parallel rows of tomato red and sunny yellow "
             "yarn, with turquoise and violet card tail and fins sticking out beyond the body, a big round "
             "white paper eye with a black pupil and a white glint, a smiling marker mouth and three yarn "
             "whiskers, plus three smaller fish - a coiled turquoise yarn disc, a lime green one and a violet "
             "one - swimming around it among five wavy marker water lines, scattered bubbles and two bunches "
             "of green waterweed",
        real="several balls of real coloured yarn on the table next to a pair of scissors and a part-wound "
             "yarn fish body",
        colors="tomato red, sunny yellow, turquoise, violet, lime green and cream"),
    "蒙德里安的花瓶": dict(
        draw="one tall hand-drawn vase whose whole interior is a strict Mondrian grid of thick and thin "
             "straight black bars crossing at exact right angles, with the cells filled with flat primary "
             "red, primary yellow, primary blue and white, three loose wobbly hand-drawn flowers rising "
             "from its mouth on curved green stems, a small separate red-yellow-blue grid patch floating to "
             "the right and a straight black table line with tick marks",
        real="a real paint set with only red, yellow and blue tubes open on the table next to a ruler and a "
             "black marker pen",
        colors="pure primary red, pure primary yellow, pure primary blue, white and black"),
    "刮画蘑菇城堡": dict(
        draw="a cheerful mushroom castle scratched out of a solid black board - three mushrooms of clearly "
             "different heights, each cap carrying a different scratched pattern (rows of dots, chevrons and "
             "a square grid) with star sparkles, each stem with an arched door and two round cross-mullioned "
             "windows and a wisp of smoke from a chimney on the tallest cap, a wavy ground line with short "
             "scratched grass strokes and three small mushrooms along the bottom, and a scatter of scratched "
             "star sparkles with one thin crescent moon in the untouched black upper half",
        real="a real black scratch board with a wooden stylus lying on it, part of a mushroom already "
             "scratched open to reveal bright rainbow foil colour underneath",
        colors="rainbow foil showing magenta, orange, yellow, green, cyan and violet"),
    "对折印蝴蝶": dict(
        draw="one big butterfly opened flat and filling the sheet, perfectly mirror-symmetrical about the "
             "vertical fold line down its body, each wing carrying soft pressed-paint blots in mirrored "
             "positions - magenta pink nearest the body, tangerine orange in the middle, turquoise at the "
             "outer tip, lemon yellow near the top edge and violet near the bottom edge - each blot spread "
             "with irregular feathered edges, a faint darker rim and delicate radiating spurs, with a sliver "
             "of bare paper down the fold line, a slim black marker body of three stacked segments with two "
             "long curled antennae and six thin legs",
        real="a real folded sheet of paper lying half-open with wet paint blots pressed inside it, next to a "
             "small watercolour set",
        colors="magenta pink, tangerine orange, lemon yellow, turquoise, violet and crimson"),
})


def run(job):
    topic, name, prompt, ref, out, log = job
    p = os.path.join(os.path.dirname(log), "_prompt.txt")
    open(p, "w", encoding="utf-8").write(prompt)
    cmd = [PY, GRSAI, "gen", "-p", p, "-r", ref, "--model", MODEL, "--quality", QUALITY,
           "--aspect", ASPECT, "--timeout", "2400", "--out", out]
    with open(log, "w", encoding="utf-8") as f:
        rc = subprocess.call(cmd, stdout=f, stderr=subprocess.STDOUT)
    ok = os.path.exists(out)
    print(("[ok] " if ok else "[失败] ") + topic + " / " + name, flush=True)
    return ok


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    cands = CAND
    for a in sys.argv:
        if a.startswith("--cands="):
            want = a.split("=", 1)[1].upper().split(",")
            cands = [c for c in CAND if c[0][0] in want]
    topics = args or list(COVERS)
    jobs = []
    for t in topics:
        c = dict(COVERS[t])
        d = os.path.join(ROOT, "项目", t + "-4-6岁")
        ref = os.path.join(d, "img", "范画成品.png")
        if not os.path.exists(ref):
            print("[跳过] %s 还没有范画成品" % t)
            continue
        outd = os.path.join(d, "封面候选")
        os.makedirs(outd, exist_ok=True)
        for name, fn in cands:
            out = os.path.join(outd, name + ".png")
            txt = os.path.join(outd, name + ".txt")
            open(txt, "w", encoding="utf-8").write(fn(c))
            if os.path.exists(out) and not force:
                print("[已有] %s / %s" % (t, name))
                continue
            jobs.append((t, name, fn(c), ref, out, os.path.join(outd, "_log_%s.txt" % name)))
    print("\n待生成 %d 张，预计 ¥%.2f\n" % (len(jobs), len(jobs) * 0.03))
    if not jobs:
        return
    with ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(run, jobs))
    print("\n完成。")


if __name__ == "__main__":
    main()
