# -*- coding: utf-8 -*-
"""课件工厂 · 排版自检（装配完 / 导出后跑；抓「文字溢出、遮挡、缺图、空白页」）

`preflight.py` 管的是**图**（对不对题、链条是否一致），这个管的是**版式**：
图再好，文字跑出卡片压到下一块、或者卡片高 4.2 英寸只装 3 行字，一样是废品。

它做四件事：
  1. 越界：任何 shape 超出页面边界 → FAIL
  2. 文字溢出：按字号/字宽/行距估算文本框所需高度，超过框高 12% → WARN（P2 那种第 3 条跑到卡外，就是它）
  3. 缺图占位：shape 里出现「【待生成】」→ FAIL
  4. 空页：整页只有标题/页码（<3 个内容块）→ WARN
外加把 preview/*.png 拼成几张**接触印样**，让人一屏扫完（排版这种事最终还是眼睛说了算）。

用法：
    python 工厂/layout_check.py 项目/<课题>/project.json
    python 工厂/layout_check.py 项目/<课题>/project.json --sheet off
    python 工厂/layout_check.py 项目/<课题>/project.json --json r.json

退出码：0 干净 / 1 有 FAIL / 2 只有 WARN
"""
import argparse
import json
import math
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from project import Project  # noqa: E402

EMU = 914400.0
TOL = 0.06          # 英寸级容差（PowerPoint 会自己做一点吸附）
OVERFLOW_RATIO = 1.12


def visual_width(t):
    """中文按 1 个字宽，ASCII 按 0.55（够用来估行数）。"""
    return sum(1.0 if ord(c) > 127 else 0.55 for c in t)


def est_height(tf, W):
    """估算 text_frame 在宽 W（英寸）下需要多高（英寸）。"""
    total = 0.0
    for para in tf.paragraphs:
        size = None
        for r in para.runs:
            if r.font.size:
                size = r.font.size.pt
                break
        size = size or 18.0
        txt = para.text or ""
        # 空段落也给一行高度
        per_line = max(1.0, (W * 72.0) / (size * 1.0))
        lines = max(1, int(math.ceil(visual_width(txt) / per_line)))
        total += lines * size * 1.35 / 72.0
        total += 6 / 72.0                    # 段后距（renderers 里默认 space_after=6）
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--json", default="")
    ap.add_argument("--sheet", default="auto", help="auto=出到 out/_排版检查/，off=不出")
    a = ap.parse_args()

    proj = Project(a.project)
    pptx = proj.pptx()
    if not os.path.exists(pptx):
        print("[x] 还没装配 pptx：%s\n    先跑：python 工厂/builder.py %s" % (pptx, a.project))
        return 1

    from pptx import Presentation
    prs = Presentation(pptx)
    SW, SH = prs.slide_width / EMU, prs.slide_height / EMU

    items = []
    for idx, slide in enumerate(prs.slides, 1):
        blocks = 0
        for sh in slide.shapes:
            try:
                L, T = sh.left / EMU, sh.top / EMU
                W, H = sh.width / EMU, sh.height / EMU
            except TypeError:
                continue
            if sh.has_text_frame and sh.text_frame.text.strip():
                blocks += 1
            if sh.shape_type == 13 or hasattr(sh, "image"):     # 图片
                blocks += 1

            # 1) 越界
            if L < -TOL or T < -TOL or L + W > SW + TOL or T + H > SH + TOL:
                bleed = max(-L, -T, (L + W) - SW, (T + H) - SH)
                # 小幅出血（装饰用）只提示；超过 0.6" 或者尺寸很大，才算真错
                lvl = "WARN" if (bleed <= 0.6 and W * H <= 1.6) else "FAIL"
                items.append((lvl, idx, "越界" if lvl == "FAIL" else "出血",
                              "shape %.2f,%.2f %.2fx%.2f 超出页面 %.1fx%.1f（超出 %.2f\"）"
                              % (L, T, W, H, SW, SH, bleed)))

            # 3) 缺图占位
            if sh.has_text_frame and "【待生成】" in sh.text_frame.text:
                items.append(("FAIL", idx, "缺图", sh.text_frame.text.strip()[:40]))

            # 2) 文字溢出
            if sh.has_text_frame and sh.text_frame.text.strip() and W > 0.5 and H > 0.2:
                need = est_height(sh.text_frame, W)
                if need > H * OVERFLOW_RATIO:
                    preview = sh.text_frame.text.strip().replace("\n", " / ")[:26]
                    items.append(("WARN", idx, "文字溢出",
                                  "需要 %.2f\" 只有 %.2f\" ｜ %s" % (need, H, preview)))

        if blocks < 3:
            items.append(("WARN", idx, "空页", "只有 %d 个内容块（漏内容/漏图？）" % blocks))

    # 汇总
    print("=" * 78)
    print("排版自检：%s  |  %d 页  |  画布 %.1fx%.1f" % (proj.name, len(prs.slides), SW, SH))
    print("=" * 78)
    for lvl in ("FAIL", "WARN"):
        rows = [r for r in items if r[0] == lvl]
        if not rows:
            continue
        print("\n[%s] %d 条" % (lvl, len(rows)))
        for _l, pg, kind, msg in rows:
            print("  %s P%-2d %-6s %s" % ("✗" if lvl == "FAIL" else "!", pg, kind, msg))
    if not items:
        print("\n[干净] 没有越界 / 溢出 / 缺图 / 空页")

    nf = sum(1 for r in items if r[0] == "FAIL")
    nw = sum(1 for r in items if r[0] == "WARN")
    print("\n" + "-" * 78)
    print("结论：%d FAIL / %d WARN" % (nf, nw))
    if nf:
        print("→ FAIL 是硬伤（文字跑出页面/缺图），改 project.json 文案或 renderers 再重装配。")
    elif nw:
        print("→ 溢出是估算值，可能偏保守：打开对应页看一眼再决定要不要压短文案。")
    else:
        print("→ 可以出交付包。")

    # 接触印样（复用 exporter 的 preview）
    if a.sheet != "off":
        pv = proj.preview_dir
        pngs = sorted(f for f in os.listdir(pv) if f.endswith(".png")) if os.path.isdir(pv) else []
        if pngs:
            from PIL import Image, ImageDraw, ImageFont
            out_dir = os.path.join(proj.out_dir, "_排版检查")
            os.makedirs(out_dir, exist_ok=True)
            try:
                f = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 22)
            except Exception:
                f = ImageFont.load_default()
            bad = {r[1] for r in items}
            W, H, LAB, COLS, ROWS = 740, 417, 26, 2, 3
            per = COLS * ROWS
            for g in range(0, len(pngs), per):
                chunk = pngs[g:g + per]
                bg = Image.new("RGB", (W * COLS, (H + LAB) * ROWS), (238, 238, 238))
                d = ImageDraw.Draw(bg)
                for i, name in enumerate(chunk):
                    pg = int(os.path.splitext(name)[0])
                    im = Image.open(os.path.join(pv, name)).convert("RGB").resize((W, H), Image.LANCZOS)
                    x, y = (i % COLS) * W, (i // COLS) * (H + LAB)
                    bg.paste(im, (x, y + LAB))
                    d.text((x + 8, y + 2), "P%d%s" % (pg, "  ← 有问题" if pg in bad else ""),
                           font=f, fill=(200, 30, 30) if pg in bad else (60, 60, 60))
                n = g // per + 1
                p = os.path.join(out_dir, "排版_%d.jpg" % n)
                bg.save(p, quality=90)
                print("接触印样：%s" % p)

    if a.json:
        json.dump(dict(deck=proj.name, pages=len(prs.slides), items=items),
                  open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("报告：%s" % a.json)

    if nf:
        return 1
    if nw:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
