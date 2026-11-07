# -*- coding: utf-8 -*-
"""第二批新题材：冬季/圣诞季（2026-10-17）
复用 make_新题材.py 的 steps() 与 STYLE_DRAW，保证同一只手。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from make_新题材 import STYLE_DRAW, steps, REF  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TOPICS = [
    dict(
        name="堆雪人",
        theme=dict(primary="5B9BD5", dark="2E5F94", light="D6E8F7", accent="C0392B",
                   text="2F4550", cream="FAF7F0", grey="595959"),
        lock=("LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion "
              "changes: one chubby snowman standing in the middle of a snowy field, facing the viewer; his "
              "body is built from TWO round white snowballs, a big one at the bottom and a smaller one on top "
              "for the head. He wears a red knitted beanie with a white pom-pom on top, and a red-and-green "
              "striped scarf around his neck with one end hanging down on the left. He has TWO thin brown "
              "stick arms stretched out to both sides, each ending in three little twigs, an orange carrot "
              "nose pointing to the left, two small round black eyes, a small dotted black smile, and THREE "
              "small black round stones as buttons down the front of his body. Around him: white snowy ground "
              "with a soft blue shadow under the snowman, falling snowflakes in the air, a small dark-green "
              "pine tree with snow on it at the lower right, and two small snow mounds at the left. A soft "
              "pale-blue winter sky fills the background. Canvas aspect 3:2 landscape, paper centred, nothing "
              "cropped by the frame edge."),
        c3=("The two snowballs are left clean white, the beanie is filled with solid red with a white "
            "pom-pom, the scarf is filled with red and green stripes, the carrot nose with orange, the stick "
            "arms, the eyes and the stone buttons with black, and the small pine tree with dark green."),
        c4=("A soft pale blue-grey is added along the lower-left of both snowballs to give them roundness, a "
            "darker red on the shaded side of the beanie, a darker green on the shaded side of the pine tree, "
            "and darker red and green on the shaded parts of the scarf."),
        c5=("The sky is filled with a soft pale blue, the snowy ground is left white with a light blue shadow "
            "under the snowman and along the drifts, and small white snowflakes are dotted across the whole "
            "picture."),
    ),
    dict(
        name="圣诞树",
        theme=dict(primary="2E7D4F", dark="14432A", light="D8EBE0", accent="C0392B",
                   text="2F4550", cream="FAF7F0", grey="595959"),
        lock=("LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion "
              "changes: one Christmas tree standing in the centre of a snowy field, facing the viewer; the "
              "tree is built from THREE stacked triangles of dark green, the biggest at the bottom and the "
              "smallest on top, with a straight brown trunk below. ONE bright yellow five-pointed star sits "
              "on the very top of the tree. A single strand of small round yellow fairy lights loops down "
              "across the tree in wide zig-zags. FIVE round baubles hang on the branches - one red, one "
              "yellow, one blue, one red and one yellow - and a few small white dots of snow sit on the "
              "branches. On the ground at the lower right there is ONE red square gift box tied with a gold "
              "ribbon and a bow. Around it: white snow covering the ground, small snowflakes falling, and a "
              "deep navy-blue night sky behind with 6-7 small white four-pointed stars. Canvas aspect 3:2 "
              "landscape, paper centred, nothing cropped by the frame edge."),
        c3=("The three triangles of the tree are filled with a solid dark green, the trunk with brown, the "
            "star with bright yellow, the five baubles with red, yellow and blue, and the gift box with red."),
        c4=("A darker green is added along the lower edge of each triangle, a deeper red, yellow and blue on "
            "the shaded side of each bauble, a darker yellow at the base of the star, and a darker red on the "
            "shaded side of the gift box."),
        c5=("The night sky is filled with a deep navy blue, the 6-7 stars and the falling snowflakes with "
            "white, the snowy ground is left white with a light blue shadow under the tree, the fairy-light "
            "strand is painted bright yellow, and the gift ribbon and bow are painted gold."),
    ),
]


def main():
    base = json.load(open(REF, encoding="utf-8"))
    for t in TOPICS:
        d = dict(base)
        d["meta"] = dict(base["meta"])
        d["meta"]["name"] = "《%s》4-6岁课件" % t["name"]
        d["meta"]["brand"] = "绘课工坊"
        d["meta"]["theme"] = t["theme"]
        d["lock"] = t["lock"]
        imgs = steps(t["lock"], t["c3"], t["c4"], t["c5"])
        d["images"] = [dict(model="gpt-image-2", quality="high", aspect="1536x1024", **im) for im in imgs]
        d["chain"] = dict(order=[i["slot"] for i in imgs], auto_ref_prev=True, anchor="范画成品",
                          note="链条正向：成品(设计基准) → 步骤1 → … → 步骤5")
        d["pages"] = []
        out = os.path.join(ROOT, "项目", t["name"] + "-4-6岁")
        os.makedirs(out, exist_ok=True)
        p = os.path.join(out, "project.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print("✓", t["name"], "->", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
