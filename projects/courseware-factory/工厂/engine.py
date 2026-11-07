# -*- coding: utf-8 -*-
"""
课件工厂 · 版式引擎
母版级组件：顶栏品牌 / 章节标签 / 页码 / 圆角标题条 / 装饰 / 色卡 / 矢量图形
配色与结构对齐《跳伞的小浣熊》母版
"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from pptx.oxml import parse_xml
from PIL import Image

SW, SH = 13.3333, 7.5          # 16:9，与母版一致
BAR_H, MARGIN = 0.62, 0.62
FONT = '微软雅黑'

DEFAULT_THEME = dict(primary='77A65A', dark='578B18', light='BED0B5',
                     accent='F9A605', text='354253', cream='FAF7F0', grey='595959')


def rgb(h):
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _ea(run, name):
    rPr = run._r.get_or_add_rPr()
    for tag in ('a:ea', 'a:cs'):
        el = rPr.find(qn(tag))
        if el is None:
            el = parse_xml('<%s xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
                           'typeface="%s"/>' % (tag, name))
            rPr.append(el)
        else:
            el.set('typeface', name)


def style(run, size=18, bold=False, color=None, font=FONT, italic=False):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if color is not None:
        run.font.color.rgb = color
    run.font.name = font
    _ea(run, font)
    return run


class Deck:
    """一页一个 Deck 实例，主题由 project.json 注入"""

    def __init__(self, theme=None, brand='美育', brand_en='Art Education for Kids'):
        t = dict(DEFAULT_THEME); t.update(theme or {})
        self.T = {k: rgb(v) for k, v in t.items()}
        self.brand, self.brand_en = brand, brand_en
        self.prs = Presentation()
        self.prs.slide_width = Inches(SW)
        self.prs.slide_height = Inches(SH)
        self.blank = self.prs.slide_layouts[6]
        self.page_no = 0

    # ---------- 颜色快捷 ----------
    @property
    def PRIMARY(self): return self.T['primary']
    @property
    def DARK(self):    return self.T['dark']
    @property
    def LIGHT(self):   return self.T['light']
    @property
    def ACCENT(self):  return self.T['accent']
    @property
    def TEXT(self):    return self.T['text']
    @property
    def CREAM(self):   return self.T['cream']
    @property
    def GREY(self):    return self.T['grey']
    WHITE = RGBColor(0xFF, 0xFF, 0xFF)
    GREY_L = RGBColor(0xE6, 0xE6, 0xE6)

    # ---------- 基础图形 ----------
    def rect(self, s, L, T, W, H, fill=None, line=None, shape=MSO_SHAPE.RECTANGLE,
             lw=1.0, radius=None, text=None, size=14, bold=True, tcolor=None,
             align=PP_ALIGN.CENTER, dash=False):
        sh = s.shapes.add_shape(shape, Inches(L), Inches(T), Inches(W), Inches(H))
        if fill is None:
            sh.fill.background()
        else:
            sh.fill.solid(); sh.fill.fore_color.rgb = fill
        if line is None:
            sh.line.fill.background()
        else:
            sh.line.color.rgb = line; sh.line.width = Pt(lw)
            if dash:
                sh.line.dash_style = 4
        sh.shadow.inherit = False
        if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
            sh.adjustments[0] = radius
        tf = sh.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = Inches(0.10)
        tf.margin_top = tf.margin_bottom = Inches(0.04)
        if text is not None:
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = tf.paragraphs[0]; p.alignment = align
            style(p.add_run(), size=size, bold=bold,
                  color=tcolor if tcolor is not None else self.WHITE).text = text
        return sh

    def oval(self, s, L, T, W, H, fill=None, line=None, lw=2.0):
        return self.rect(s, L, T, W, H, fill=fill, line=line, lw=lw, shape=MSO_SHAPE.OVAL)

    def text(self, s, L, T, W, H, lines, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
             spacing=1.15, space_after=6, color=None):
        tb = s.shapes.add_textbox(Inches(L), Inches(T), Inches(W), Inches(H))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = anchor
        tf.margin_left = tf.margin_right = Emu(0)
        tf.margin_top = tf.margin_bottom = Emu(0)
        if isinstance(lines, str):
            lines = [lines]
        for i, item in enumerate(lines):
            runs = [item] if isinstance(item, (tuple, str)) else list(item)
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            p.line_spacing = spacing
            p.space_after = Pt(space_after)
            for r in runs:
                t, kw = r if isinstance(r, tuple) else (r, {})
                kw = dict(kw)
                if 'color' not in kw and color is not None:
                    kw['color'] = color
                style(p.add_run(), **kw).text = t
        return tb

    def pic(self, s, path, L, T, W, H, border=None, missing=None):
        """等比缩放居中到框内；缺图则画占位框"""
        if not path or not os.path.exists(path):
            return self.rect(s, L, T, W, H, fill=RGBColor(0xF2, 0xF2, 0xF2),
                             line=RGBColor(0xBF, 0xBF, 0xBF), shape=MSO_SHAPE.ROUNDED_RECTANGLE,
                             radius=0.04, lw=1.2, dash=True,
                             text='【待生成】' + (missing or os.path.basename(str(path))),
                             size=12, bold=False, tcolor=RGBColor(0x8C, 0x8C, 0x8C))
        iw, ih = Image.open(path).size
        bar, iar = W / H, iw / ih
        w, h = (W, W / iar) if iar >= bar else (H * iar, H)
        pic = s.shapes.add_picture(path, Inches(L + (W - w) / 2), Inches(T + (H - h) / 2),
                                   Inches(w), Inches(h))
        if border is not None:
            pic.line.color.rgb = border; pic.line.width = Pt(2)
        return pic

    # ---------- 页面骨架 ----------
    def page(self, chapter=None, bg=None, show_bar=True, page_label=True, auto=True):
        s = self.prs.slides.add_slide(self.blank)
        fill = s.background.fill
        fill.solid(); fill.fore_color.rgb = bg if bg is not None else self.CREAM
        if show_bar:
            self.rect(s, 0, 0, SW, BAR_H, fill=self.WHITE)
            self.rect(s, 0, BAR_H - 0.02, SW, 0.02, fill=self.GREY_L)
            self.text(s, SW - 5.2, 0.10, 4.6, 0.45,
                      [[(self.brand, dict(size=12, bold=True, color=self.PRIMARY)),
                        ('   |   ' + self.brand_en, dict(size=9, color=self.GREY))]],
                      align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)
        if chapter:
            self.rect(s, MARGIN, SH - 0.60, 1.34, 0.34, fill=self.PRIMARY,
                      shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.3,
                      text=chapter, size=12)
        if auto:
            self.page_no += 1
        if page_label and auto:
            self.text(s, SW - 1.6, SH - 0.56, 1.0, 0.3,
                      [[('%d页' % self.page_no, dict(size=11, color=self.GREY))]], align=PP_ALIGN.RIGHT)
        return s

    def title_bar(self, s, text, L=None, W=7.6, T=1.02, H=0.66, fill=None, size=19):
        return self.rect(s, MARGIN if L is None else L, T, W, H,
                         fill=fill if fill is not None else self.LIGHT,
                         shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.28,
                         text=text, size=size, tcolor=self.DARK)

    def deco(self, s):
        self.oval(s, SW - 0.95, 0.85, 0.16, 0.16, fill=self.ACCENT)
        self.oval(s, SW - 1.24, 1.12, 0.10, 0.10, fill=self.PRIMARY)
        # 装饰圆放在页面内：原来用 x=-0.35 做出血，导出后是被裁掉一半的绿块，像漏图
        self.oval(s, SW - 1.72, SH - 1.28, 0.86, 0.86, fill=self.LIGHT)

    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.prs.save(path)
        return path
