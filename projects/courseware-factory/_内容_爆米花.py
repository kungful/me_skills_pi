# -*- coding: utf-8 -*-
"""把《爆米花蹦蹦跳》的内容写进 project.json（只做范画链 6 张，其余页先不动）。"""
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PJ = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  "项目", "爆米花蹦蹦跳-4-6岁", "project.json")
j = json.load(open(PJ, encoding="utf-8"))

# ---------------- 主题 ----------------
j["meta"]["name"] = "《爆米花蹦蹦跳》4-6岁课件"
j["meta"]["brand"] = "绘课工坊"          # TODO 上架前换成你的机构名
j["meta"]["theme"] = {
    "primary": "E8452C",   # 番茄红（爆米花桶条纹）
    "dark": "B32E1C",
    "light": "FFE9C7",
    "accent": "FFC93C",    # 黄油黄（爆米花）
    "text": "3B4A57",
    "cream": "FAF7F0",
    "grey": "595959",
}

PAPER = ("A top-down flat photograph of one sheet of off-white rice paper on a light wooden desk, "
         "even soft daylight, the paper fills the whole frame, visible paper texture, mild realistic "
         "paper shadow. Children's art class illustration, hand-drawn, flat poster colours, thick clean "
         "outlines, no signature, no watermark.")

# ---------------- 构图锁 ----------------
j["lock"] = (
    "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
    "one chubby red-and-white VERTICALLY STRIPED popcorn paper bucket sits in the LOWER LEFT of the paper, "
    "tilted with its mouth facing up and to the RIGHT, with a bold tomato-red rolled rim; "
    "SIX fluffy anthropomorphic popcorn puffs burst up out of the bucket along a rising diagonal towards the "
    "UPPER RIGHT, the outermost puff reaching the top right corner; every puff is a soft bumpy cloud made of "
    "three or four rounded lobes, each with two big round black eyes, a small smiling mouth, two pink cheek dots "
    "and two tiny stick arms and feet; the LARGEST puff sits in the middle of the diagonal and wears a tiny "
    "white chef's hat; ONE small puff sits on the LEFT rim of the bucket with its legs dangling; "
    "four small unpopped yellow corn kernels lie scattered flat on the paper around the base of the bucket; "
    "ONE small hand-drawn speech bubble holding the word POP! floats in the UPPER LEFT; "
    "the whole burst fills the paper edge to edge while the corners stay empty. "
)

# ---------------- 线条 / 颜色 / 装饰 语言 ----------------
j["common"]["stroke"] = (
    "LINE, COLOUR AND DECORATION LANGUAGE - one single clean hand is used for the whole sequence, the finished "
    "artwork and every step alike, with no variation whatsoever.\n"
    "(1) OUTLINE: every contour is ONE clean, confident, CONTINUOUS SOLID LINE of even medium thickness, drawn "
    "with a broad-tip children's MARKER pen. The line runs unbroken from start to finish; edges are crisp and "
    "clearly defined, like a hand-drawn clean outline, with only a slight natural wobble that shows a child drew "
    "it by hand. No hairy or fuzzy broken edges, no contour that frays into short furry strokes, no dashes or "
    "dotted outlines, no sketchy doubled lines, no overshooting strokes, no thin scratched pencil texture, no "
    "crayon rubbing or smudging, no colour bleeding across the outline.\n"
    "(2) COLOUR: high-saturation flat poster colour, sitting flat INSIDE its outline, evenly covered edge to edge. "
    "Never a gradient, never grainy, never blended, never airbrushed. The palette is bold and cheerful and the "
    "colours must CLASH happily: butter-yellow, tomato red, sky blue, coral pink and pure white, on the bare "
    "off-white paper. Never muted, never muddy, never grey, never beige-toned, never washed-out pastel.\n"
    "(3) HIGHLIGHTS: every rounded volume carries ONE or TWO pure WHITE highlight dots or a short white arc - "
    "this is what makes the picture look shiny and appetising. Never omit the highlights.\n"
    "(4) DECORATION: at least TWO of these decorative vocabularies must appear somewhere in the picture - "
    "vertical stripes, polka dots, small four-point star sparkles, curved speed arcs, thick-and-thin hatching "
    "inside a shape.\n"
    "(5) LIGHT: the light comes from the UPPER LEFT; every object casts one simple FLAT grey-blue shadow on the "
    "paper, drawn as a solid flat shape, never a blur and never a gradient.\n"
    "EXCEPTION - step 1 only: that stage is the initial light pencil scaffolding - loose light-grey pencil "
    "construction lines, thin and faint, simple circles, ovals and blocky shapes, no marker and no colour at all. "
    "From step 2 onward, and in the finished artwork, the drawing is in the clean marker language described above."
)

# ---------------- 范画链 6 张 ----------------
# 槽位改名：涂黑 → 铺色（爆米花没有涂黑这一步）
RENAME = {"范画步骤3_涂黑": "范画步骤3_铺色",
          "范画步骤4_上色": "范画步骤4_装饰高光"}

PROMPTS = {
    "范画成品": (
        "THIS IS THE FINISHED MASTER ARTWORK of the lesson, drawn at its very best. Everything is complete: "
        "the bucket is filled flat white with five bold tomato-red vertical stripes and a red rolled rim, the six "
        "popcorn puffs are filled flat butter-yellow with a pale cream underside and TWO pure-white highlight dots "
        "each, the largest puff wears a white chef's hat, all eyes are solid black with one white glint, cheeks are "
        "coral pink, and the six small unpopped kernels are flat butter-yellow with a white highlight. "
        "Decorative layer complete: tiny sky-blue four-point star sparkles, small coral polka dots and pale yellow "
        "dots are scattered through the empty paper, three curved speed arcs trail behind the burst of puffs, and "
        "the speech bubble in the upper left holds the word POP! drawn in thick solid black marker letters with a "
        "white highlight on each letter. A soft flat grey-blue shadow sits under the bucket and under every puff. "
        "Large calm areas of bare off-white paper remain between the puffs so the picture breathes. "
        "The whole picture is finished, balanced, cheerful and bursting with energy."
    ),
    "范画步骤1_起形": (
        "THIS IS STEP 1 OF 5, the very first construction sketch, and it is DRAWN ONLY IN LIGHT GREY PENCIL - no "
        "marker, no ink, no colour anywhere on the paper. Faint thin pencil construction lines only: at the lower "
        "left a small trapezoid for the bucket with a long oval on top for its rim; from the rim a rising diagonal "
        "of SIX cloud shapes made of three or four overlapping circles each, getting smaller towards the top right "
        "corner; on every cloud two small circles for the eyes, one small oval for the mouth, and four tiny "
        "sausage shapes for the arms and feet; one small rectangle on the head of the biggest cloud for the "
        "chef's hat; one small circle with a tail for the speech bubble in the upper left; four tiny ovals for the "
        "kernels near the base. Construction lines only, all strokes light, thin and faint, no details filled in, "
        "no eyes drawn in, no shading at all."
    ),
    "范画步骤2_勾线": (
        "THIS IS STEP 2 OF 5. The pencil construction lines are now traced over with the thick solid black marker "
        "line, and NOTHING is coloured in yet - the paper stays bare white apart from the black outlines. Trace the "
        "bucket and its rim, the five vertical stripe lines on the bucket, the six bumpy cloud outlines of the "
        "puffs, the chef's hat, the eyes, the smiles, the tiny arms and feet, the four kernels, the speech bubble "
        "and the letters of the word POP!. Also add the three curved speed arcs behind the burst. Every line is "
        "crisp, unbroken and slightly wobbly by hand. No colour, no shading, no highlights yet."
    ),
    "范画步骤3_铺色": (
        "THIS IS STEP 3 OF 5. Flat colour is now laid in, and it stays completely flat - no gradients, no blending, "
        "no shading. Fill the bucket flat white and paint its five vertical stripes flat tomato red, then fill the "
        "rolled rim flat tomato red. Fill all six popcorn puffs flat butter-yellow, leaving the pale cream "
        "underside of each puff unpainted. Fill the four kernels flat butter-yellow. Leave the chef's hat white. "
        "Leave the speech bubble and the word POP! plain black on bare paper. Skip every highlight and every "
        "decorative sparkle for now - they belong to the next step."
    ),
    "范画步骤4_装饰高光": (
        "THIS IS STEP 4 OF 5. The colour is already down and flat; now the decoration and the highlights go on - "
        "this step is what makes the picture look shiny and alive. Add TWO pure-white highlight dots to every "
        "popcorn puff, a white highlight on the chef's hat, coral pink cheek dots on all six faces, one white "
        "glint in every black eye, a small white highlight on each of the four kernels and a short white arc on "
        "the left side of the bucket. Then begin the decorative vocabulary: scatter tiny sky-blue four-point star "
        "sparkles, small coral polka dots and pale yellow dots through the empty paper around the burst. Nothing "
        "else changes - the outlines and the flat colours stay exactly as they are."
    ),
    "范画步骤5_加背景": "",   # alias = 成品
}

for im in j["images"]:
    s = im["slot"]
    if s in RENAME:
        im["slot"] = RENAME[s]

for im in j["images"]:
    s = im["slot"]
    if s not in PROMPTS:
        continue
    im["style"] = PAPER
    if s == "范画步骤1_起形":
        im["anchor"] = False      # 起形是纯铅笔稿，不能看到成品（会漏色）
        im["refs"] = []
        im["ref_prev"] = False
    elif s == "范画步骤5_加背景":
        im["alias"] = "范画成品"
    else:
        im["ref_prev"] = True
        if s == "范画成品":
            im["refs"] = []
            im["ref_prev"] = False
    im["prompt"] = PROMPTS[s]

# ---------------- 链条顺序 ----------------
j["chain"] = {
    "order": ["范画成品", "范画步骤1_起形", "范画步骤2_勾线",
              "范画步骤3_铺色", "范画步骤4_装饰高光", "范画步骤5_加背景"],
    "auto_ref_prev": True,
    "anchor": "范画成品",
    "note": "正向：成品(设计基准，无参考) → 起形(纯铅笔，不看成品) → 勾线 → 铺色 → 装饰高光 → 加背景(=成品副本)",
}

# ---------------- 页面文案 ----------------
STEPS = {
    20: ("步骤一：起 形",
         "先用铅笔轻轻画出爆米花桶和往上蹦的六个云朵形——一个圆挨一个圆，越往上越小，再点上圆圆的眼睛。"),
    21: ("步骤二：勾 线",
         "用黑色勾线笔沿铅笔线描一遍，别忘了桶上的五条竖条纹、小厨师帽，还有左边那个“POP!”气泡。"),
    22: ("步骤三：铺 色",
         "桶身留白、条纹涂成大红色，爆米花全部涂成黄油黄，底部留一条浅奶白当暗面，颜色一定要涂平涂满。"),
    23: ("步骤四：装饰高光",
         "每一颗爆米花点上两粒白色高光，加上粉腮红，再撒上蓝色小星星和彩色圆点——这一步最出效果！"),
    24: ("步骤五：加背景",
         "在空的地方画上三条速度弧线，给桶和爆米花加上淡淡的灰蓝影子，整幅画就蹦起来啦！"),
}
for n, p in enumerate(j["pages"], 1):
    if n in STEPS:
        p["title"], p["text"] = STEPS[n]
        p["text"] = [STEPS[n][1]]

# 步骤页 uses 跟着改名
for p in j["pages"]:
    if p.get("uses"):
        p["uses"] = [RENAME.get(u, u) for u in p["uses"]]

for p in j["pages"]:
    if p["type"] == "cover":
        p["title"] = "《爆米花蹦蹦跳》"
        p["uses"] = ["01_封面主视觉"]
    if p["type"] == "share_summary":
        p["title"] = "分享表达 + 课后总结"

json.dump(j, open(PJ, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("写入完成：%s" % PJ)
print("chain:", j["chain"]["order"])
for im in j["images"]:
    if im.get("batch") == "chain":
        print("  %-18s refs=%s prev=%s anchor=%s alias=%s plen=%d" % (
            im["slot"], im.get("refs"), im.get("ref_prev"),
            im.get("anchor", True), im.get("alias"), len(im["prompt"])))
