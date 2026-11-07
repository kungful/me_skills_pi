# -*- coding: utf-8 -*-
"""
课件工厂 · 页面渲染器库
project.json 里每页写 {"type": "step", ...}，builder 按类型调用对应渲染器。
新增版式 = 在这里加一个函数 + 注册到 RENDERERS。
"""
from engine import SW, SH, MARGIN
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.dml.color import RGBColor

RENDERERS = {}
def renderer(name):
    def deco(fn):
        RENDERERS[name] = fn
        return fn
    return deco


# ============ 通用零件 ============
def card(d, s, L, T, W, H, fill=None, line=None, lw=1.5, radius=0.06, dash=False):
    return d.rect(s, L, T, W, H, fill=fill if fill is not None else d.WHITE,
                  line=line if line is not None else d.LIGHT, lw=lw,
                  shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=radius, dash=dash)

def head_chip(d, s, L, T, text, fill=None, W=None):
    w = W if W else 0.32 * len(text) + 0.75
    return d.rect(s, L, T, w, 0.44, fill=fill if fill is not None else d.PRIMARY,
                  shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.3, text=text, size=13)

def tip_block(d, s, L, T, W, H, main, notes, main_size=14, note_size=12):
    """大图右侧的说明卡：正文 + 橙色短线 + 要点列表"""
    card(d, s, L, T, W, H)
    d.text(s, L + 0.35, T + 0.30, W - 0.7, 1.5, [[(main, dict(size=main_size, color=d.TEXT))]], spacing=1.45)
    d.rect(s, L + 0.35, T + 1.75, 1.5, 0.06, fill=d.ACCENT)
    if notes:
        d.text(s, L + 0.35, T + 2.00, W - 0.7, H - 2.3,
               [[('\u00b7 ' + t, dict(size=note_size, color=d.GREY))] for t in notes], spacing=1.4)


# ============ 1. 封面 ============
@renderer('cover')
def r_cover(d, s, p, ctx):
    d.rect(s, 0, 0, SW, 0.14, fill=d.PRIMARY)
    d.rect(s, SW - 6.4, 0, 6.4, SH, fill=RGBColor(0xF2, 0xF0, 0xE6))
    d.pic(s, ctx.P(p['image']), SW - 6.15, 0.75, 5.6, 5.6, missing=p['image'])
    d.text(s, 0.85, 1.55, 6.2, 1.4, [[(p['title'], dict(size=42, bold=True, color=d.DARK))]])
    d.text(s, 0.90, 3.05, 6.2, 0.5, [[(p['subtitle'], dict(size=17, color=d.TEXT))]])
    d.rect(s, 0.90, 3.75, 1.5, 0.07, fill=d.ACCENT)
    d.text(s, 0.90, 4.05, 6.0, 1.2, [[(t, dict(size=15, color=d.GREY))] for t in p.get('slogan', [])],
           spacing=1.4)
    d.text(s, 0.90, 6.35, 6.0, 0.5,
           [[(d.brand + '   |   ' + d.brand_en, dict(size=11, color=d.PRIMARY))]])


# ============ 2. 课程介绍（卡片 + 课效展示） ============
@renderer('intro')
def r_intro(d, s, p, ctx):
    d.title_bar(s, p.get('title', '课 程 介 绍'), L=MARGIN, W=4.4)
    cards = p['cards']
    W1, GAP = 4.05, 0.28
    for i, c in enumerate(cards):
        L = MARGIN + (W1 + GAP) * (i % 2)
        T = 1.95 if i < 2 else 4.35
        H = 2.15 if i < 2 else 1.90
        card(d, s, L, T, W1, H)
        head_chip(d, s, L + 0.28, T + 0.20, c['head'])
        d.text(s, L + 0.30, T + 0.78, W1 - 0.6, H - 0.9,
               [[(t, dict(size=12, color=d.TEXT))] for t in c['items']], spacing=1.35)
    if p.get('image'):
        LX = MARGIN + 2 * (W1 + GAP)
        card(d, s, LX, 1.95, SW - LX - MARGIN, 4.30)
        head_chip(d, s, LX + 0.28, 2.15, p.get('image_head', '课效展示'), fill=d.ACCENT)
        d.pic(s, ctx.P(p['image']), LX + 0.30, 2.75, SW - LX - 1.22, 3.30, missing=p['image'])


# ============ 3. 我们今天可以知道 ============
@renderer('knowing')
def r_knowing(d, s, p, ctx):
    d.deco(s)
    d.title_bar(s, p.get('title', '我们今天可以知道：'), L=1.10, W=6.6)
    items = p['items']
    n = len(items)
    h = min(0.78, (4.6 / n) - 0.14)
    step = h + 0.14
    top = 2.02 + max(0, (4.4 - n * step) / 2)
    for i, t in enumerate(items):
        y = top + i * step
        card(d, s, 1.30, y, 9.6, h, lw=1.25, radius=0.12)
        d.oval(s, 1.55, y + (h - 0.50) / 2, 0.50, 0.50, fill=d.PRIMARY)
        d.rect(s, 1.55, y + (h - 0.50) / 2, 0.50, 0.50, fill=d.PRIMARY,
               shape=MSO_SHAPE.OVAL, text=str(i + 1), size=15)
        d.text(s, 2.28, y, 8.3, h, [[(t, dict(size=16, color=d.TEXT))]], anchor=MSO_ANCHOR.MIDDLE)


# ============ 4. 考一考（两图 VS） ============
@renderer('quiz')
def r_quiz(d, s, p, ctx):
    d.title_bar(s, p.get('title', '考 一 考'),
                L=p.get('title_L', 5.35), W=p.get('title_W', 2.6), fill=d.ACCENT)
    d.text(s, 1.0, 1.95, 11.3, 0.6, [[(p['question'], dict(size=19, bold=True, color=d.DARK))]],
           align=PP_ALIGN.CENTER)
    imgs = p['images']
    d.pic(s, ctx.P(imgs[0]), 1.6, 2.85, 4.4, 3.0, missing=imgs[0])
    d.pic(s, ctx.P(imgs[1]), 7.3, 2.85, 4.4, 3.0, missing=imgs[1])
    d.rect(s, 6.20, 4.05, 0.95, 0.75, fill=d.ACCENT, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
           radius=0.25, text='VS', size=20)
    if p.get('answer'):
        d.text(s, 1.6, 6.00, 10.1, 0.5, [[(p['answer'], dict(size=15, color=d.GREY))]], align=PP_ALIGN.CENTER)


# ============ 5. 主题知识（大图 + 文字卡） ============
@renderer('knowledge')
def r_knowledge(d, s, p, ctx):
    d.title_bar(s, p['title'], L=MARGIN, W=p.get('title_W', 8.2))
    d.pic(s, ctx.P(p['image']), MARGIN, 1.95, p.get('img_w', 7.1), 4.35, missing=p['image'])
    L = MARGIN + p.get('img_w', 7.1) + 0.32
    W = SW - L - MARGIN
    card(d, s, L, 2.35, W, 3.5)
    d.text(s, L + 0.40, 2.75, W - 0.8, 2.8,
           [[(t, dict(size=16, color=d.TEXT))] for t in p['lines']], spacing=1.5)


# ============ 6. 实物观察（大图 + 小图 + 任务表） ============
@renderer('real_object')
def r_real_object(d, s, p, ctx):
    d.title_bar(s, p['title'], L=MARGIN, W=p.get('title_W', 8.6))
    d.pic(s, ctx.P(p['image']), MARGIN, 1.95, 7.4, p.get('img_h', 3.05), missing=p['image'])
    if p.get('image2'):
        d.pic(s, ctx.P(p['image2']), MARGIN, 1.95 + p.get('img_h', 3.05) + 0.15, 7.4,
              p.get('img2_h', 1.15), missing=p['image2'])
    L, W = 8.25, SW - 8.25 - 0.62
    card(d, s, L, 1.95, W, 4.35)
    d.text(s, L + 0.30, 2.15, W - 0.5, 0.4,
           [[(p.get('task_head', '观察小任务'), dict(size=14, bold=True, color=d.PRIMARY))]])
    tasks = p['tasks']
    step = min(0.72, 3.9 / len(tasks))
    for i, t in enumerate(tasks):
        y = 2.62 + i * step
        d.rect(s, L + 0.30, y, 1.12, step - 0.16, fill=d.PRIMARY,
               shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.25, text=t['tag'], size=12)
        d.text(s, L + 1.55, y - 0.02, W - 1.9, step, [[(t['text'], dict(size=11, color=d.GREY))]], spacing=1.25)


# ============ 7. 材料双方案 ============
@renderer('materials')
def r_materials(d, s, p, ctx):
    d.title_bar(s, p['title'], L=MARGIN, W=p.get('title_W', 8.6))
    d.pic(s, ctx.P(p['image']), MARGIN, 1.95, 7.4, 4.35, missing=p['image'])
    L, W = 8.25, SW - 8.25 - 0.62
    ns = len(p['schemes'])
    ch = 4.35 if ns == 1 else 2.05
    for i, sc in enumerate(p['schemes']):
        T = 1.95 + i * 2.30
        c = d.PRIMARY if i == 0 else d.ACCENT
        card(d, s, L, T, W, ch, line=c, lw=1.75)
        head_chip(d, s, L + 0.30, T + 0.17, sc['head'], fill=c, W=2.6)
        d.text(s, L + 0.30, T + 0.70, W - 0.6, ch - 0.85,
               [[('\u00b7 ' + t, dict(size=11, color=d.TEXT))] for t in sc['items']], spacing=1.3)


# ============ 8. 外形观察（图 + 标签网格） ============
@renderer('observe_tags')
def r_observe_tags(d, s, p, ctx):
    d.title_bar(s, p['title'], L=MARGIN, W=p.get('title_W', 8.6))
    d.pic(s, ctx.P(p['image']), MARGIN, 1.95, 6.4, 4.35, missing=p['image'])
    tags = p['tags']
    cols = p.get('cols', 2)
    x0 = MARGIN + 6.4 + 0.33
    cw = (SW - x0 - MARGIN - 0.17 * (cols - 1)) / cols
    for i, t in enumerate(tags):
        x = x0 + (i % cols) * (cw + 0.17)
        y = 2.15 + (i // cols) * 0.95
        d.rect(s, x, y, cw, 0.75, fill=d.WHITE, line=d.PRIMARY, lw=1.5,
               shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.2, text=t, size=15, tcolor=d.DARK)


# ============ 9. 形体拆解（矢量绘制） ============
@renderer('parts_diagram')
def r_parts(d, s, p, ctx):
    d.title_bar(s, p['title'], L=MARGIN, W=p.get('title_W', 8.6))
    card(d, s, MARGIN, 1.95, 6.85, 4.35, line=d.LIGHT, radius=0.05)
    # 说明文字先占位，图形统一从 y=2.42 开始，避免压在文字上（老版就用 oval 画到 2.10，直接遮住这行）
    d.text(s, MARGIN, 2.02, 6.85, 0.34,
           [[(p.get('figure_note', ''), dict(size=12, bold=True, color=d.PRIMARY))]],
           align=PP_ALIGN.CENTER)

    shapes = p.get('shapes')
    if shapes:
        # 新格式：真图形（三角形/方块/圆/五角星）——「三个三角形叠成树」用椭圆画什么都不像
        KIND = {'tri': MSO_SHAPE.ISOSCELES_TRIANGLE, 'rect': MSO_SHAPE.RECTANGLE,
                'oval': MSO_SHAPE.OVAL, 'star5': MSO_SHAPE.STAR_5_POINT}
        for sp in shapes:
            d.rect(s, sp['x'], sp['y'], sp['w'], sp['h'],
                   fill=RGBColor.from_string(sp['fill']) if sp.get('fill') else None,
                   line=RGBColor.from_string(sp['line']) if sp.get('line') else d.PRIMARY,
                   lw=sp.get('lw', 2.0),
                   shape=KIND.get(sp.get('kind', 'oval'), MSO_SHAPE.OVAL))
    else:
        # 老格式：figure 里全当椭圆（糖葫芦那套 berry1..5 靠这个，别删）
        for k, v in (p.get('figure') or {}).items():
            d.oval(s, v[0], v[1], v[2], v[3], fill=None, line=d.PRIMARY, lw=2.0)

    parts = p['parts']
    step = min(0.82, 4.1 / len(parts))
    for i, pt in enumerate(parts):
        y = 2.15 + i * step
        d.rect(s, 7.90, y, 1.85, step - 0.16, fill=d.PRIMARY,
               shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.22, text=pt['name'], size=14)
        d.text(s, 9.92, y, 3.0, step, [[(pt['desc'], dict(size=14, color=d.TEXT))]],
               anchor=MSO_ANCHOR.MIDDLE)


# ============ 10. 姿态多图 ============
@renderer('poses')
def r_poses(d, s, p, ctx):
    d.title_bar(s, p['title'], L=MARGIN, W=p.get('title_W', 7.6))
    items = p['items']
    n = len(items)
    W = (SW - 2 * MARGIN - 0.24 * (n - 1)) / n
    for i, it in enumerate(items):
        x = MARGIN + i * (W + 0.24)
        d.pic(s, ctx.P(it['image']), x, 1.95, W, 3.55, missing=it['image'])
        d.rect(s, x + (W - 1.80) / 2, 5.70, 1.80, 0.55, fill=d.WHITE, line=d.PRIMARY, lw=1.5,
               shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.3, text=it['label'], size=14, tcolor=d.DARK)


# ============ 11. 联想创想 ============
@renderer('idea_list')
def r_idea(d, s, p, ctx):
    d.title_bar(s, p['title'], L=MARGIN, W=p.get('title_W', 7.0))
    d.pic(s, ctx.P(p['image']), MARGIN, 1.95, 7.0, 4.35, missing=p['image'])
    L, W = 8.05, SW - 8.05 - 0.62
    d.text(s, L, 2.05, W, 0.4, [[(p.get('list_head', ''), dict(size=14, bold=True, color=d.PRIMARY))]])
    step = min(0.80, 4.0 / len(p['items']))
    for i, t in enumerate(p['items']):
        y = 2.58 + i * step
        card(d, s, L, y, W, step - 0.14, lw=1.25, radius=0.2)
        d.text(s, L + 0.30, y, W - 0.6, step - 0.14, [[('\u00b7 ' + t, dict(size=14, color=d.TEXT))]],
               anchor=MSO_ANCHOR.MIDDLE)


# ============ 12. 色卡（同类色） ============
@renderer('color_swatches')
def r_color(d, s, p, ctx):
    d.title_bar(s, p['title'], L=MARGIN, W=p.get('title_W', 7.0))
    sw = p['swatches']
    n = len(sw)
    W = (SW - 2 * MARGIN - 0.27 * (n - 1)) / n
    for i, c in enumerate(sw):
        x = MARGIN + i * (W + 0.27)
        d.rect(s, x, 2.15, W, 2.15, fill=RGBColor.from_string(c['hex'].lstrip('#')),
               shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
        d.text(s, x, 4.45, W, 0.9, [[(c['name'], dict(size=15, bold=True, color=d.TEXT))],
                                    [(c['use'], dict(size=12, color=d.GREY))]],
               align=PP_ALIGN.CENTER, spacing=1.3)
    card(d, s, MARGIN, 5.45, SW - 2 * MARGIN, 1.15, radius=0.08)
    d.text(s, MARGIN + 0.38, 5.62, SW - 2 * MARGIN - 0.76, 0.85,
           [[(p['note_head'], dict(size=15, bold=True, color=d.DARK))],
            [(p['note'], dict(size=14, color=d.TEXT))]], spacing=1.4)


# ============ 13. 黑白对比与留白（矢量示意） ============
@renderer('contrast_blank')
def r_contrast(d, s, p, ctx):
    d.title_bar(s, p['title'], L=MARGIN, W=p.get('title_W', 7.0))
    card(d, s, MARGIN, 2.15, 5.60, 3.90)
    f = p['figure']
    # 可选的大尾巴（松鼠这类动物用；没有 tail 的课件渲染结果与以前完全一致，向后兼容）
    if f.get('tail'):
        d.oval(s, f['tail'][0], f['tail'][1], f['tail'][2], f['tail'][3], fill=d.WHITE, line=d.PRIMARY, lw=2.0)
    d.oval(s, f['body'][0], f['body'][1], f['body'][2], f['body'][3], fill=d.WHITE, line=d.PRIMARY, lw=2.0)
    d.oval(s, f['head'][0], f['head'][1], f['head'][2], f['head'][3], fill=d.WHITE, line=d.PRIMARY, lw=2.0)
    for e in f['eyes']:
        d.oval(s, e[0], e[1], e[2], e[3], fill=RGBColor(0x22, 0x22, 0x22))
    for lg in f['legs']:
        d.rect(s, lg[0], lg[1], lg[2], lg[3], fill=RGBColor(0x22, 0x22, 0x22),
               shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.45)
    d.text(s, MARGIN, 6.10, 5.60, 0.4, [[(p['figure_note'], dict(size=12, color=d.GREY))]],
           align=PP_ALIGN.CENTER)
    L2 = 6.55
    card(d, s, L2, 2.15, SW - L2 - MARGIN, 3.90)
    for i, t in enumerate(p['tips']):
        y = 2.50 + i * (3.4 / len(p['tips']))
        d.text(s, L2 + 0.35, y, 0.5, 0.5, [[(t['no'], dict(size=18, bold=True, color=d.ACCENT))]])
        d.text(s, L2 + 0.95, y + 0.02, 4.9, 0.75, [[(t['text'], dict(size=14, color=d.TEXT))]], spacing=1.3)


# ============ 14. 参考素材（两图） ============
@renderer('refs')
def r_refs(d, s, p, ctx):
    head = p.get('head', '素 材 参 考')
    d.rect(s, MARGIN, 1.02, 3.1, 0.66, fill=d.LIGHT,
           shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.28, text=head, size=19, tcolor=d.DARK)
    d.text(s, 4.0, 1.18, 8.7, 0.4,
           [[(p.get('hint', '观察真实的照片，注意外形特点、姿势和颜色的变化。'),
              dict(size=13, color=d.GREY))]])
    imgs = p['images']
    n = len(imgs)
    W = (SW - 2 * MARGIN - 0.23 * (n - 1)) / n
    for i, im in enumerate(imgs):
        x = MARGIN + i * (W + 0.23)
        d.pic(s, ctx.P(im), x, 2.00, W, 4.30, missing=im)


# ============ 15. 工具介绍（双方案并列） ============
@renderer('tools_dual')
def r_tools(d, s, p, ctx):
    d.title_bar(s, p['title'], L=MARGIN, W=p.get('title_W', 7.2))
    n = len(p['schemes'])
    W = (SW - 2 * MARGIN - 0.37 * (n - 1)) / n
    for i, sc in enumerate(p['schemes']):
        L = MARGIN + i * (W + 0.37)
        c = d.PRIMARY if i == 0 else d.ACCENT
        d.rect(s, L, 1.02, W, 0.62, fill=c, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.28,
               text=sc['head'], size=17)
        tools = sc['tools']
        step = min(1.20, 4.6 / len(tools))
        for j, t in enumerate(tools):
            y = 1.95 + j * step
            card(d, s, L, y, W, step - 0.18, lw=1.25, radius=0.14)
            d.oval(s, L + 0.24, y + (step - 0.18 - 0.50) / 2, 0.50, 0.50, fill=c)
            d.rect(s, L + 0.24, y + (step - 0.18 - 0.50) / 2, 0.50, 0.50, fill=c,
                   shape=MSO_SHAPE.OVAL, text=t['no'], size=14)
            d.text(s, L + 0.92, y + 0.14, W - 1.3, 0.4,
                   [[(t['name'], dict(size=15, bold=True, color=d.DARK))]])
            d.text(s, L + 0.92, y + 0.56, W - 1.2, 0.4, [[(t['desc'], dict(size=12, color=d.GREY))]])


# ============ 16. 绘画步骤（核心页） ============
@renderer('step')
def r_step(d, s, p, ctx):
    d.title_bar(s, p['title'], L=MARGIN, W=p.get('title_W', 4.0))
    iw = p.get('img_w', 7.5)
    d.pic(s, ctx.P(p['image']), MARGIN, 2.00, iw, 4.30, missing=p['image'])
    L = MARGIN + iw + 0.23
    W = SW - L - MARGIN
    tip_block(d, s, L, 2.00, W, 4.30, p['text'], p.get('tips', []))


# ============ 17. 成品双风格对照 ============
@renderer('final_dual')
def r_final(d, s, p, ctx):
    d.title_bar(s, p['title'], L=MARGIN, W=p.get('title_W', 4.0))
    d.text(s, 4.90, 1.18, 7.8, 0.4, [[(p.get('hint', ''), dict(size=13, color=d.GREY))]])
    items = p['items']
    n = len(items)
    W = (SW - 2 * MARGIN - 0.20 * (n - 1)) / n
    for i, it in enumerate(items):
        x = MARGIN + i * (W + 0.20)
        c = d.PRIMARY if i == 0 else d.ACCENT
        d.pic(s, ctx.P(it['image']), x, 1.95, W, 3.55, missing=it['image'])
        d.rect(s, x + (W - 1.75) / 2, 5.60, 1.75, 0.50, fill=c,
               shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.3, text=it['label'], size=14)
    card(d, s, MARGIN, 6.25, SW - 2 * MARGIN, 0.62, lw=1.25, radius=0.15)
    d.text(s, MARGIN + 0.33, 6.36, SW - 2 * MARGIN - 0.66, 0.4,
           [[(p['note'], dict(size=12, color=d.ACCENT))]], anchor=MSO_ANCHOR.MIDDLE)


# ============ 18. 分享表达 + 课后总结 ============
@renderer('share_summary')
def r_share(d, s, p, ctx):
    d.rect(s, MARGIN, 1.05, SW - 2 * MARGIN, 2.35, fill=d.LIGHT,
           shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
    d.text(s, 1.20, 1.35, 11.0, 0.5, [[(p.get('share_head', '分 享 表 达'), dict(size=22, bold=True, color=d.DARK))]])
    d.text(s, 1.20, 2.00, 11.0, 1.2, [[(t, dict(size=16, color=d.TEXT))] for t in p['share']], spacing=1.5)
    card(d, s, MARGIN, 3.70, SW - 2 * MARGIN, 2.85)
    d.text(s, 1.20, 3.95, 11.0, 0.5, [[(p.get('summary_head', '课 后 总 结'), dict(size=22, bold=True, color=d.DARK))]])
    d.text(s, 1.20, 4.60, 11.0, 2.0, [[(t, dict(size=13, color=d.GREY))] for t in p['summary']],
           spacing=1.45, space_after=8)


# ============ 通用兜底：纯文本页 ============
@renderer('text_page')
def r_text_page(d, s, p, ctx):
    d.title_bar(s, p.get('title', ''), L=MARGIN, W=p.get('title_W', 7.6))
    # 卡片高度跟行数走并垂直居中：固定 4.2 高装 4 行字会剩一大片空白，看着像漏了图
    n = max(1, len(p['lines']))
    H = min(4.20, 0.75 + 0.40 * n)
    T = 1.95 + (4.35 - H) / 2
    card(d, s, MARGIN, T, SW - 2 * MARGIN, H)
    d.text(s, MARGIN + 0.5, T + 0.36, SW - 2 * MARGIN - 1.0, H - 0.66,
           [[(t, dict(size=16, color=d.TEXT))] for t in p['lines']], spacing=1.6)
