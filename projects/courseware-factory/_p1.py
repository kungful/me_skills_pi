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
