# -*- coding: utf-8 -*-
"""新建 3 个创意题材的 project.json（每个 6 张：范画成品 + 步骤1~5）
风格段落直接复用已有 29 套的 STYLE_DRAW / common.stroke，保证同一只手。
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "项目", "小象洗澡-4-6岁", "project.json")

STYLE_DRAW = ("A top-down flat photograph of one sheet of off-white rice paper on a light wooden desk, "
              "even soft daylight, the paper fills the whole frame, visible paper texture, mild realistic "
              "paper shadow. Children's art class illustration, hand-drawn, flat colours, thick clean outlines, "
              "no text, no signature, no watermark.")


def steps(lock_subject, c3, c4, c5):
    """生成 成品 + 步骤1~5 的 6 条 prompt。lock_subject 用一句话点明主角特征。"""
    return [
        dict(slot="范画成品", batch="chain", prompt=(
            "THIS IS THE FINISHED MASTER ARTWORK of the lesson, drawn at its very best. Everything is complete: "
            + c3 + " " + c4 + " " + c5 +
            " The whole picture is finished, balanced and cheerful."),
            style=STYLE_DRAW, refs=[], ref_prev=False, lock=True),

        dict(slot="范画步骤1_起形", batch="chain", prompt=(
            "THIS IS STEP 1 OF 5, the very first construction sketch, and it is DRAWN ONLY IN LIGHT GREY PENCIL "
            "- no marker, no ink, no colour whatsoever anywhere on the paper. Faint thin pencil construction "
            "lines only, the big shapes of the subject blocked in as simple circles and ovals, with no details, "
            "no eyes and no shading at all. " + lock_subject),
            style=STYLE_DRAW, refs=[], ref_prev=False, lock=True),

        dict(slot="范画步骤2_勾线", batch="chain", prompt=(
            "THIS IS STEP 2 OF 5. Continue from the reference sketch and keep the identical composition. The "
            "pencil scaffold is now traced into a clean, confident BLACK MARKER OUTLINE drawing, with all the "
            "face details and small shapes added in black. NO colour is filled in yet: the drawing is pure "
            "black outline on white paper, and the pencil construction lines are gone. " + lock_subject),
            style=STYLE_DRAW, refs=[], ref_prev=True, lock=True),

        dict(slot="范画步骤3_涂色", batch="chain", prompt=(
            "THIS IS STEP 3 OF 5. Keep the identical composition and the same black outline. Now the FLAT "
            "COLOURS are filled in with a broad-tip marker, evenly and solidly inside the outlines, leaving the "
            "sky and the background still blank white paper. No shading, no gradient, no texture yet - just "
            "clean flat blocks of colour. " + c3),
            style=STYLE_DRAW, refs=[], ref_prev=True, lock=True),

        dict(slot="范画步骤4_加深", batch="chain", prompt=(
            "THIS IS STEP 4 OF 5. Keep the identical composition. Now add the DARKER TONE on top of the flat "
            "colours: a second, darker shade of each colour is laid along one side of every shape to give it "
            "volume, plus a few simple short strokes for texture. The background is still blank white paper. "
            + c4),
            style=STYLE_DRAW, refs=[], ref_prev=True, lock=True),

        dict(slot="范画步骤5_加背景", batch="chain", prompt=(
            "THIS IS STEP 5 OF 5, the final stage. Keep the identical composition and everything already "
            "painted. Now fill in the BACKGROUND of the picture, finishing the artwork exactly as described in "
            "the finished artwork. " + c5),
            style=STYLE_DRAW, refs=[], ref_prev=True, lock=True),
    ]


TOPICS = [
    dict(
        name="万圣节南瓜灯",
        theme=dict(primary="E8862B", dark="7A3E12", light="FBDDBB", accent="2E3A69",
                   text="3A2A1A", cream="FAF7F0", grey="595959"),
        lock=("LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion "
              "changes: one big round chubby jack-o'-lantern pumpkin sitting on a patch of grass at the lower "
              "centre, facing the viewer; the pumpkin is wider than it is tall with 4 gentle vertical ribs and "
              "a short thick dark-brown stalk on top with ONE curly green tendril spiralling up to the right. "
              "Its face is carved out of the front and glows warm yellow from inside - TWO big triangles for "
              "the eyes and ONE wide zig-zag mouth with two square teeth. Behind and above the pumpkin: a deep "
              "navy-blue night sky with a big round pale-yellow crescent moon at the upper right, 5-6 small "
              "white four-pointed stars, and a bare black tree silhouette with three thin branches along the "
              "left edge. Two small friendly white ghosts with simple round eyes float in the sky, one at the "
              "upper left and one at the middle right. Canvas aspect 3:2 landscape, paper centred, nothing "
              "cropped by the frame edge."),
        c3=("The pumpkin body is a solid bright orange with a slightly darker orange on the ribs and the "
            "carved openings left as clean openings."),
        c4=("A deeper burnt-orange tone is added along the right side of every pumpkin rib and under the "
            "pumpkin, and a warm glowing yellow-orange is painted inside the two triangle eyes and the "
            "zig-zag mouth."),
        c5=("The sky is filled with a deep navy blue, the crescent moon with pale yellow, the stars and the "
            "two little ghosts with white, the grass with two tones of green, and the tree silhouette with "
            "solid black - the warm yellow glow spills slightly onto the grass in front of the pumpkin."),
    ),
    dict(
        name="会变形的云",
        theme=dict(primary="5B9BD5", dark="2E5F94", light="CFE4F5", accent="F2A93B",
                   text="2F4550", cream="FAF7F0", grey="595959"),
        lock=("LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion "
              "changes: one BIG fluffy white cloud in the upper centre whose outline has turned into the shape "
              "of a sitting bunny - a round billowy cloud body with TWO long cloud ears standing up at its top "
              "right and a small round cloud tail at its left; the cloud-bunny is soft and billowy, built from "
              "overlapping rounded lobes. Around it: two small plain white clouds, one at the middle left and "
              "one at the middle right. A bright yellow sun with 8 short triangular rays sits in the upper "
              "right corner. Below, one big rolling green grassy hill fills the lower third of the frame with a "
              "few simple tufts of grass and 3 tiny pink flowers. Clear light-blue sky fills everything else. "
              "Canvas aspect 3:2 landscape, paper centred, nothing cropped by the frame edge."),
        c3=("The big bunny-shaped cloud and the two small clouds are left clean white, and the grassy hill is "
            "filled with a solid medium green."),
        c4=("A soft pale grey-blue is added along the underside and the inner curves of the cloud lobes to "
            "give the clouds volume, and a darker green is added along the lower edge of the hill."),
        c5=("The whole sky is filled with a clear light blue, the sun with bright yellow and its rays with "
            "orange, the flowers with small pink dots and yellow centres, and the grass tufts with a darker "
            "green."),
    ),
    dict(
        name="小刺猬背果子",
        theme=dict(primary="8B6B4A", dark="4A3524", light="E8DCCB", accent="C0392B",
                   text="3A2E24", cream="FAF7F0", grey="595959"),
        lock=("LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion "
              "changes: one round chubby little hedgehog standing in the centre of the picture on the grass, "
              "facing the viewer and turned slightly to the left, with a soft cream-coloured face, a small "
              "dark pointed nose, two round black eyes, two tiny round ears and a small smile; its whole back "
              "is covered with neat rows of brown pointed quills. THREE round red apples and ONE round orange "
              "fruit are speared on the quills along its back - one apple near the head, one in the middle, "
              "one at the back, with the orange fruit between them. Around it: green autumn grass with a few "
              "small yellow and orange fallen leaves, ONE red-capped mushroom with white dots at the lower "
              "right, and two small round orange berries at the lower left. A soft pale-blue sky band runs "
              "along the very top edge with one small white cloud. Canvas aspect 3:2 landscape, paper centred, "
              "nothing cropped by the frame edge."),
        c3=("The hedgehog's face is a solid cream colour, its quills are filled with a medium brown, the "
            "three apples are solid red, the orange fruit is orange, and the grass is a solid medium green."),
        c4=("A darker brown is added along the lower edge of the quill rows and along the hedgehog's belly, "
            "a deeper red on the shaded side of each apple, and a darker green along the base of the grass."),
        c5=("The sky band is filled with a soft pale blue with one white cloud, the mushroom cap with red and "
            "white dots, its stalk with cream, the fallen leaves with yellow and orange, and the berries with "
            "orange - a small soft shadow is added under the hedgehog."),
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
        d["images"] = [dict(model="gpt-image-2.5", quality="high", aspect="1536x1024", **im) for im in imgs]
        d["chain"] = dict(order=[i["slot"] for i in imgs], auto_ref_prev=True, anchor="范画成品",
                          note="链条正向：成品(设计基准) → 步骤1 → … → 步骤5")
        d["pages"] = []
        out = os.path.join(ROOT, "项目", t["name"] + "-4-6岁")
        os.makedirs(out, exist_ok=True)
        p = os.path.join(out, "project.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print("✓", t["name"], "->", p, "| %d 张" % len(d["images"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
