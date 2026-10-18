#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_wiring_diagram.py —— 生成「太阳网自动控制器（散装模块版，不做 PCB）」接线图

输出：SunNet-Android/接线手册/*.svg 和 *.png
      1-总览 / 2-电源 / 3-电机 / 4-安全链 / 5-传感器与面板

坐标全部是设计单位（px）。PNG 用 SCALE 倍放大以便打印/看手机。
图上的引脚号必须与 pcbsun-esp32s3/include/board.h 的 PCBSUN_SCATTER 分支一致，
回归闸门：pcbsun-esp32s3/test/host_sim/scatter_main.cpp
"""
import os

SCALE = 2
FONT = "C:/Windows/Fonts/msyh.ttc"
FONTB = "C:/Windows/Fonts/msyhbd.ttc"
SVG_FONT = "'Microsoft YaHei','SimHei',sans-serif"

# 线色（全图统一，看图就认色）
RED   = "#d32f2f"   # +12V
ORG   = "#ef6c00"   # +5V
PUR   = "#7b1fa2"   # +3V3
BLK   = "#212121"   # GND
GRN   = "#2e7d32"   # 信号 1
BLU   = "#1565c0"   # 信号 2
GRAY  = "#78909c"   # 说明/机械

PALETTE = [RED, ORG, PUR, BLK, GRN, BLU, GRAY]

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL = True
except Exception:
    _PIL = False


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Fig:
    def __init__(self, w, h, title):
        self.w, self.h, self.title = w, h, title
        self.svg = []
        self._fonts = {}
        if _PIL:
            self.img = Image.new("RGB", (w * SCALE, h * SCALE), "#ffffff")
            self.d = ImageDraw.Draw(self.img)

    # ---------- 字体 ----------
    def _f(self, size, bold=False):
        key = (size, bold)
        if key not in self._fonts:
            if _PIL:
                self._fonts[key] = ImageFont.truetype(FONTB if bold else FONT, size * SCALE)
            else:
                self._fonts[key] = None
        return self._fonts[key]

    # ---------- 基本图元 ----------
    def rect(self, x, y, w, h, fill="#ffffff", stroke="#455a64", width=2, r=10, dash=None):
        if _PIL:
            if r > 0:
                self.d.rounded_rectangle([x * SCALE, y * SCALE, (x + w) * SCALE, (y + h) * SCALE],
                                         radius=r * SCALE, fill=fill, outline=stroke, width=width * SCALE)
            else:
                self.d.rectangle([x * SCALE, y * SCALE, (x + w) * SCALE, (y + h) * SCALE],
                                 fill=fill, outline=stroke, width=width * SCALE)
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" '
                        f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"{da}/>')

    def text(self, x, y, s, size=15, color="#111111", anchor="lt", bold=False, italic=False):
        if _PIL:
            a = {"lt": "la", "lm": "lm", "ct": "ma", "cm": "mm", "rt": "ra", "rm": "rm"}.get(anchor, "la")
            self.d.text((x * SCALE, y * SCALE), s, font=self._f(size, bold), fill=color, anchor=a)
        amap = {"lt": "start", "lm": "start", "ct": "middle", "cm": "middle", "rt": "end", "rm": "end"}
        dy = {"lt": size * 0.95, "lm": size * 0.36, "ct": size * 0.95, "cm": size * 0.36,
              "rt": size * 0.95, "rm": size * 0.36}.get(anchor, size)
        st = f' font-style="italic"' if italic else ""
        w = ' font-weight="bold"' if bold else ""
        self.svg.append(f'<text x="{x}" y="{y + dy}" font-family="{SVG_FONT}" font-size="{size}"'
                        f' fill="{color}" text-anchor="{amap}"{w}{st}>{esc(s)}</text>')

    def line(self, pts, color, width=3, dash=None):
        if _PIL:
            if dash:
                self._dashed(pts, color, width, dash)
            else:
                self.d.line([(p[0] * SCALE, p[1] * SCALE) for p in pts], fill=color,
                            width=width * SCALE, joint="curve")
        p = " ".join(f"{a},{b}" for a, b in pts)
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.svg.append(f'<polyline points="{p}" fill="none" stroke="{color}" '
                        f'stroke-width="{width}" stroke-linejoin="round"{da}/>')

    def _dashed(self, pts, color, width, dash):
        import math
        on = float(str(dash).split(",")[0]) if "," in str(dash) else 8.0
        off = on * 0.65
        for i in range(len(pts) - 1):
            (x1, y1), (x2, y2) = pts[i], pts[i + 1]
            L = math.hypot(x2 - x1, y2 - y1)
            if L <= 0:
                continue
            ux, uy = (x2 - x1) / L, (y2 - y1) / L
            t = 0.0
            while t < L:
                e = min(t + on, L)
                self.d.line([((x1 + ux * t) * SCALE, (y1 + uy * t) * SCALE),
                             ((x1 + ux * e) * SCALE, (y1 + uy * e) * SCALE)],
                            fill=color, width=width * SCALE)
                t = e + off

    def circle(self, x, y, r, fill="#ffffff", stroke="#455a64", width=2):
        if _PIL:
            self.d.ellipse([(x - r) * SCALE, (y - r) * SCALE, (x + r) * SCALE, (y + r) * SCALE],
                           fill=fill, outline=stroke, width=width * SCALE)
        self.svg.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" '
                        f'stroke-width="{width}"/>')

    def label(self, x, y, s, color="#ffffff", size=12, pad=3):
        """给线加个小牌子（白底）"""
        w = max(14, len(s) * size * 0.78 + pad * 2)
        h = size * 1.45
        self.rect(x - w / 2, y - h / 2, w, h, fill="#ffffff", stroke=color, width=1.2, r=4)
        self.text(x, y, s, size=size, color=color, anchor="cm", bold=True)

    # ---------- 模块 ----------
    def module(self, x, y, w, h, title, terms=None, color="#37474f", fill="#f5f7fa",
               sub=None, bar=30):
        terms = terms or {}
        self.rect(x, y, w, h, fill=fill, stroke=color, width=2, r=10)
        self.rect(x, y, w, bar, fill=color, stroke=color, width=2, r=8)
        self.rect(x, y + bar - 8, w, 8, fill=color, stroke=color, width=0, r=0)
        self.text(x + w / 2, y + bar / 2, title, size=14, color="#ffffff", anchor="cm", bold=True)
        if sub:
            self.text(x + w / 2, y + bar + 8, sub, size=11, color="#546e7a", anchor="ct")
        out = {}
        for side, names in terms.items():
            out[side] = []
            n = len(names)
            for i, nm in enumerate(names):
                if side in ("l", "r"):
                    ty = y + bar + (h - bar) * (i + 1) / (n + 1)
                    tx = x if side == "l" else x + w
                    out[side].append(((tx, ty), nm))
                    self.circle(tx, ty, 6, fill="#fffde7", stroke=color, width=2)
                    if side == "l":
                        self.text(tx + 11, ty, nm, size=12, color="#263238", anchor="lm")
                    else:
                        self.text(tx - 11, ty, nm, size=12, color="#263238", anchor="rm")
                else:
                    tx = x + w * (i + 1) / (n + 1)
                    ty = y if side == "t" else y + h
                    out[side].append(((tx, ty), nm))
                    self.circle(tx, ty, 6, fill="#fffde7", stroke=color, width=2)
                    if side == "t":
                        self.text(tx, ty - 12, nm, size=12, color="#263238", anchor="cm")
                    else:
                        self.text(tx, ty + 12, nm, size=12, color="#263238", anchor="ct")
        return out

    def wire(self, pts, color, width=3, dash=None, label=None, lx=None, ly=None):
        self.line(pts, color, width=width, dash=dash)
        if label:
            mx = lx if lx is not None else (pts[0][0] + pts[-1][0]) / 2
            my = ly if ly is not None else (pts[0][1] + pts[-1][1]) / 2
            self.label(mx, my, label, color=color)

    def heading(self, x, y, s, size=20):
        self.text(x, y, s, size=size, color="#102027", bold=True)

    def note(self, x, y, w, lines, title="注意", color="#e65100", fill="#fff8e1"):
        h = 26 + len(lines) * 21
        self.rect(x, y, w, h, fill=fill, stroke=color, width=2, r=8)
        self.text(x + 12, y + 6, title, size=15, color=color, bold=True)
        for i, ln in enumerate(lines):
            self.text(x + 12, y + 30 + i * 21, ln, size=13.5, color="#4e342e")
        return y + h

    def save(self, path_noext):
        os.makedirs(os.path.dirname(path_noext), exist_ok=True)
        head = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}">\n'
                f'<rect width="{self.w}" height="{self.h}" fill="#ffffff"/>\n')
        with open(path_noext + ".svg", "w", encoding="utf-8") as f:
            f.write(head + "\n".join(self.svg) + "\n</svg>\n")
        if _PIL:
            self.img.save(path_noext + ".png")
        print("  ->", path_noext + ".svg / .png")


# ============================================================================
# 图 1 —— 总览
# ============================================================================
def fig_overview(out):
    f = Fig(1780, 1120, "总览")
    f.heading(40, 26, "太阳网自动控制器 · 散装模块版 【总览】")
    f.text(40, 58, "全部用现成模块 + 端子接线，不用画 PCB。细接线看第 2~5 张图。",
           size=14, color="#546e7a")

    # --- 电源链 ---
    mains = f.module(40, 120, 150, 90, "市电 220V", {"r": ["L", "N"]}, color="#455a64")
    psu = f.module(250, 110, 200, 110, "12V / 3A 电源适配器", {"l": ["L", "N"], "r": ["+12V", "GND"]},
                   color="#455a64", sub="输出 ≥3A")
    fuse = f.module(510, 135, 130, 60, "3A 保险丝", {"l": ["IN"], "r": ["OUT"]}, color="#455a64")
    f.rect(690, 120, 20, 90, fill=BLK, stroke=BLK, width=0, r=2)  # 母线

    f.wire([(190, 165), (250, 165)], BLK)
    f.wire([(450, 148), (510, 158)], RED)
    f.wire([(390, 180), (510, 172)], BLK)
    f.wire([(640, 165), (700, 165)], RED)

    # --- 母线分两路 ---
    mos = f.module(760, 60, 230, 110, "MOS 触发开关模块", {"l": ["VIN+", "VIN-"], "r": ["VOUT+", "VOUT-"]},
                   color="#00695c", sub="高电平触发（SIG）")
    lm = f.module(760, 230, 230, 110, "LM2596 降压模块", {"l": ["IN+", "IN-"], "r": ["OUT+", "OUT-"]},
                  color="#00695c", sub="12V → 5.0V")
    f.wire([(700, 165), (730, 165), (730, 100), (760, 100)], RED)
    f.wire([(700, 165), (730, 165), (730, 270), (760, 270)], RED)

    drv = f.module(1060, 60, 240, 120, "DRV8871 电机驱动模块", {"l": ["VM", "GND"], "r": ["OUT1", "OUT2"]},
                   color="#00695c", sub="IN1/IN2 控方向")
    motor = f.module(1370, 70, 170, 100, "直流减速电机", {"l": ["+", "-"]}, color="#37474f",
                     sub="收网/展开")
    f.wire([(990, 100), (1060, 100)], RED)
    f.wire([(1300, 95), (1330, 95), (1330, 105), (1370, 105)], RED)
    f.wire([(1300, 115), (1345, 115), (1345, 135), (1370, 135)], BLU)

    esp = f.module(600, 470, 360, 300, "ESP32-S3-DevKitC-1", {"r": ["5V", "GND"], "l": ["3V3", "GND"]},
                   color="#1a237e", sub="N16R8 双 Type-C", bar=34)
    (esp5v, _), (espg2, _) = esp["r"]
    f.wire([(990, 305), (1040, 305), (1040, 620), (960, 620)], ORG, label="+5V", lx=1010, ly=470)

    # 控制信号（用一束箭头表示，细节看后面）
    f.wire([(830, 170), (830, 220), (830, 300), (810, 470)], GRN, width=4, dash="10,7",
           label="IO4/IO5/IO6 → 电机", lx=1000, ly=380)

    # --- 安全链 / 传感器 两个框 ---
    f.rect(60, 470, 480, 470, fill="#fbfbfd", stroke="#90a4ae", width=2, r=12, dash="8,6")
    f.text(80, 484, "安全链（干接点，低=触发）　→ 第 4 张图", size=15, color="#37474f", bold=True)
    safty = [
        ("限位 A（展开终点）", "NO→IO7　COM→GND"),
        ("限位 B（收网终点）", "NO→IO11　COM→GND"),
        ("急停按钮（常闭 NC）", "3V3→COM　NC→IO12"),
        ("手动/自动 旋钮", "COM→IO13　手动档→GND"),
    ]
    for i, (a, b) in enumerate(safty):
        yy = 530 + i * 78
        f.rect(80, yy, 440, 60, fill="#ffffff", stroke="#cfd8dc", width=1.5, r=8)
        f.text(96, yy + 10, a, size=14, color="#102027", bold=True)
        f.text(96, yy + 33, b, size=13, color="#455a64")

    f.rect(1020, 470, 700, 470, fill="#fbfbfd", stroke="#90a4ae", width=2, r=12, dash="8,6")
    f.text(1040, 484, "传感器 + 面板　→ 第 5 张图", size=15, color="#37474f", bold=True)
    sens = [
        ("光照模块 AO", "VCC→3V3　AO→IO1"),
        ("雨滴模块 AO", "VCC→3V3(必须)　AO→IO2"),
        ("风速开关", "一→IO14　二→GND"),
        ("设定点电位器", "两端 3V3/GND　中点→IO3"),
        ("按键 ×3", "一端 GND　另一端 IO21/IO38/IO39"),
        ("指示灯 ×2", "IO47/IO48 →1k→ LED → GND"),
    ]
    for i, (a, b) in enumerate(sens):
        yy = 522 + i * 58
        f.rect(1040, yy, 660, 46, fill="#ffffff", stroke="#cfd8dc", width=1.5, r=8)
        f.text(1054, yy + 6, a, size=13.5, color="#102027", bold=True)
        f.text(1240, yy + 7, b, size=13, color="#455a64")

    f.wire([(600, 560), (560, 560), (560, 700), (542, 700)], GRN, width=3, dash="10,7")
    f.wire([(960, 560), (990, 560), (990, 700), (1018, 700)], GRN, width=3, dash="10,7")

    # --- 公共地 ---
    f.wire([(40, 990), (1740, 990)], BLK, width=6)
    f.label(890, 990, "公共地 GND（所有模块的 GND 都要连到这里）", color=BLK, size=14)
    for xx in (100, 300, 700, 830, 1100, 1400, 1700):
        f.wire([(xx, 990), (xx, 1005)], BLK, width=3)
    f.text(40, 1020, "※ 地线必须“一点共地”：ESP32、MOS、DRV8871、LM2596、所有传感器/开关的 GND 全部接在一起，"
                     "否则信号会乱跳。", size=13, color="#b71c1c")

    f.note(40, 1050, 1700, [
        "① 先只接电源部分（第 2 张图），用万用表确认 +12V 和 +5V 都对，再插 ESP32。",
        "② 所有模块的模拟输出只能 3.3V：光敏/雨滴模块一律用 3.3V 供电，不要用 5V。",
        "③ 任何接线/改线之前，先拔掉 12V 电源。",
    ], title="※ 三步安全顺序")
    f.save(os.path.join(out, "1-总览"))


# ============================================================================
# 图 2 —— 电源
# ============================================================================
def fig_power(out):
    f = Fig(1700, 1000, "电源")
    f.heading(40, 26, "第 2 张 · 电源怎么接（先接这张，接完先量电压）")

    psu = f.module(50, 140, 220, 140, "12V 电源适配器", {"r": ["+12V", "GND"]}, color="#455a64",
                   sub="≥3A，带插头")
    fuse = f.module(360, 165, 150, 90, "保险丝座", {"l": ["IN"], "r": ["OUT"]}, color="#455a64",
                    sub="3A 保险管")
    f.wire([(270, 195), (360, 195)], RED)
    f.wire([(270, 235), (330, 235), (330, 300), (1290, 300)], BLK, dash="9,6")

    # 分配端子排
    tb = f.rect(600, 100, 260, 230, fill="#e8f5e9", stroke="#2e7d32", width=2, r=10)
    f.text(730, 108, "接线端子排（中线）", size=14, color="#1b5e20", anchor="ct", bold=True)
    f.text(620, 136, "+12V 排", size=13, color=RED, bold=True)
    f.text(620, 236, "GND 排", size=13, color=BLK, bold=True)
    f.wire([(600, 170), (860, 170)], RED, width=5)
    f.wire([(600, 260), (860, 260)], BLK, width=5)
    for i in range(4):
        xx = 660 + i * 62
        f.circle(xx, 170, 7, fill="#fff", stroke=RED, width=2)
        f.circle(xx, 260, 7, fill="#fff", stroke=BLK, width=2)
    f.wire([(510, 195), (600, 170)], RED, label="+12V", lx=552, ly=178)

    lm = f.module(980, 90, 280, 210, "LM2596S 降压模块", {"l": ["IN+", "IN-"], "r": ["OUT+", "OUT-"]},
                  color="#00695c", sub="拧电位器调到 5.0V")
    f.wire([(860, 170), (900, 170), (900, 140), (980, 140)], RED)
    f.wire([(860, 260), (930, 260), (930, 250), (980, 250)], BLK)

    esp = f.module(1360, 110, 300, 170, "ESP32-S3 开发板", {"l": ["5V", "GND"]}, color="#1a237e",
                   sub="只接这两个，先别插 USB")
    f.wire([(1260, 155), (1360, 155)], ORG, label="+5V", lx=1310, ly=142)
    f.wire([(1260, 235), (1320, 235), (1320, 300), (1290, 300)], BLK)

    mos = f.module(980, 400, 280, 150, "MOS 开关模块", {"l": ["VIN+", "VIN-"]}, color="#00695c",
                   sub="母线电从这里过")
    f.wire([(860, 170), (920, 170), (920, 470), (980, 470)], RED)
    f.wire([(860, 260), (960, 260), (960, 510), (980, 510)], BLK)

    o = f.note(50, 430, 860, [
        "① 把 12V 适配器、保险丝、端子排、LM2596 先接好，ESP32 先不插。",
        "② 万用表直流档：端子排 +12V 排 对 GND 排 应显示 12V 左右（±0.5V）。",
        "③ 拧 LM2596 上的蓝色电位器，让 OUT+ 对 OUT- 正好 5.0V（4.9~5.1 都行）。",
        "④ 确认后再把 LM2596 的 OUT+ → ESP32 的 5V，OUT- → ESP32 的 GND。",
        "⑤ 保险丝必须装在 +12V 这一根上（靠近电源那端），不要装在地线上。",
    ], title="※ 上电顺序（一定按这个来）")

    f.note(50, 620, 860, [
        "· 电源正负极千万别接反：反接会瞬间烧掉模块。接完再量一遍。",
        "· 12V 适配器电流要 ≥3A（电机启动电流大，1A 的会“打嗝”）。",
        "· 用 USB 给 ESP32 烧程序时，把 12V 电源关掉。",
        "· 户外用请换 12V/5A 防水电源（IP67），并加直流防雷器。",
    ], title="常见错误", color="#b71c1c", fill="#ffebee")

    f.text(1080, 470, "线色约定：", size=14, color="#37474f", bold=True)
    for i, (c, t) in enumerate([(RED, "红 = +12V"), (ORG, "橙 = +5V"), (BLK, "黑 = GND")]):
        f.wire([(1080, 505 + i * 34), (1130, 505 + i * 34)], c, width=5)
        f.text(1140, 505 + i * 34 - 9, t, size=13.5, color="#37474f")
    f.save(os.path.join(out, "2-电源"))


# ============================================================================
# 图 3 —— 电机
# ============================================================================
def fig_motor(out):
    f = Fig(1700, 1000, "电机")
    f.heading(40, 26, "第 3 张 · 电机怎么接（母线高边开关 + DRV8871）")

    esp = f.module(50, 220, 300, 380, "ESP32-S3 开发板", {"l": ["GND"], "r": ["IO4", "IO5", "IO6", "GND"]},
                   color="#1a237e", sub="只列出用到的脚")
    (gnd_l, _) = esp["l"][0]
    (io4, _), (io5, _), (io6, _), (gnd_r, _) = esp["r"]

    f.wire([(gnd_l[0] - 60, gnd_l[1]), (gnd_l[0], gnd_l[1])], BLK, width=4)

    mos = f.module(560, 110, 300, 240, "MOS 触发开关模块", {"l": ["VIN+", "VIN-"], "r": ["VOUT+", "VOUT-"],
                                                           "t": ["SIG"]},
                   color="#00695c", sub="高电平触发，15A")
    (sig_t, _) = mos["t"][0]
    f.wire([(560, 170), (500, 170), (500, 90), (460, 90)], RED, width=5)
    f.label(505, 120, "+12V 来自端子排", color=RED, size=12)
    f.wire([(560, 300), (520, 300), (520, 380), (300, 380)], BLK, width=4)
    f.wire([(io6[0], io6[1]), (520, io6[1]), (520, 118), (sig_t[0], sig_t[1])], GRN, width=3,
           label="IO6 = 母线使能", lx=470, ly=io6[1] - 46)

    drv = f.module(1000, 110, 300, 300, "DRV8871 模块",
                   {"l": ["VM", "GND"], "r": ["OUT1", "OUT2"], "t": ["IN1", "IN2"]},
                   color="#00695c", sub="方向由 IN1/IN2 决定")
    f.wire([(860, 190), (930, 190), (930, 190), (1000, 190)], RED, width=5)
    f.wire([(860, 320), (940, 320), (940, 300), (1000, 300)], BLK, width=4)
    in1, in2 = drv["t"]
    f.wire([(io4[0], io4[1]), (900, io4[1]), (900, 70), (in1[0][0], in1[0][1])], GRN, width=3,
           label="IO4 → IN1", lx=895, ly=io4[1] - 46)
    f.wire([(io5[0], io5[1]), (960, io5[1]), (960, 90), (in2[0][0], in2[0][1])], BLU, width=3,
           label="IO5 → IN2", lx=1000, ly=io5[1] - 46)
    f.wire([(gnd_r[0], gnd_r[1]), (960, gnd_r[1]), (960, 360), (940, 360), (940, 320)], BLK, width=3)

    mot = f.module(1400, 190, 220, 140, "电机（网机）", {"l": ["+", "-"]}, color="#37474f")
    f.wire([(1300, 210), (1350, 210), (1350, 230), (1400, 230)], RED, width=5)
    f.wire([(1300, 250), (1375, 250), (1375, 290), (1400, 290)], BLU, width=5)
    f.text(1440, 350, "换向 = IN1/IN2 电平互换", size=12.5, color="#546e7a", anchor="ct")

    f.note(50, 660, 780, [
        "· IO6（MOT_EN）不拉高，电机永远不转——这是母线的“总闸”。",
        "· MOS 模块的 SIG 若 3.3V 触发不灵（有的模块要 5V），加一级电平转换：",
        "   IO6 →1k→ S8050 基极，发射极→GND，集电极→MOS SIG，SIG 再经 10k 上拉到 5V。",
        "· DRV8871 的 IN1/IN2 是 3.3V 逻辑，可直接接。",
        "· 电机线两根无极性（接反只是方向相反，换线或改 limitAStopsCw 都行）。",
    ], title="要点")

    f.note(870, 640, 780, [
        "① 先把 IO6 悬空、12V 上电：用万用表量 DRV8871 的 VM 对 GND 应该是 0V（母线被 MOS 断开）。",
        "② 手机连上热点，点 JOG CW/CCW：VM 应出现 12V，电机转；松手后 VM 回 0V。",
        "③ 空载跑一次全程，确认限位 A/B 都能让电机停。",
        "④ 再挂上真网跑，量一下电机电流，据此设 set stallMa。",
    ], title="联调步骤", color="#1b5e20", fill="#e8f5e9")
    f.save(os.path.join(out, "3-电机"))


# ============================================================================
# 图 4 —— 安全链
# ============================================================================
def fig_safety(out):
    f = Fig(1700, 1080, "安全链")
    f.heading(40, 26, "第 4 张 · 安全链：限位 / 急停 / 手动自动（干接点，低=触发）")
    f.text(40, 60, "散装版没有板上的 10k 上拉，固件已改用芯片内部上拉/下拉 —— 所以你不用外接任何电阻。",
           size=13.5, color="#00695c")

    esp = f.module(60, 420, 300, 330, "ESP32-S3 开发板",
                   {"l": ["3V3", "GND"], "r": ["IO7", "IO11", "IO12", "IO13"]}, color="#1a237e")
    e3v3, egnd = esp["l"][0][0], esp["l"][1][0]
    tio7, tio11, tio12, tio13 = [esp["r"][i][0] for i in range(4)]
    f.wire([(e3v3[0] - 70, e3v3[1]), (e3v3[0], e3v3[1])], PUR, width=4)
    f.wire([(egnd[0] - 70, egnd[1]), (egnd[0], egnd[1])], BLK, width=4)
    f.label(30, e3v3[1] - 22, "3V3", color=PUR, size=12)
    f.label(30, egnd[1] - 22, "GND", color=BLK, size=12)
    f.wire([(320, 700), (1640, 700)], BLK, width=5)
    f.label(980, 700, "GND 公共地", color=BLK, size=13)
    f.wire([(320, 560), (400, 560), (400, 96), (1200, 96)], PUR, width=4)
    f.label(830, 96, "3V3（只给急停用）", color=PUR, size=13)

    # 限位 A
    la = f.module(700, 150, 340, 150, "限位开关 A（展开终点）", {"l": ["NO 常开", "COM 公共"], "r": []},
                  color="#b71c1c", sub="V-156-1C25 长柄滚轮")
    f.wire([(700, 205), (620, 205), (620, 500), (360, 500)], GRN, width=3, label="→ IO7", lx=520, ly=460)
    f.wire([(700, 245), (660, 245), (660, 700)], BLK, width=3)

    # 限位 B
    lb = f.module(700, 330, 340, 150, "限位开关 B（收网终点）", {"l": ["NO 常开", "COM 公共"], "r": []},
                  color="#b71c1c")
    f.wire([(700, 385), (600, 385), (600, 540), (360, 540)], GRN, width=3, label="→ IO11", lx=500, ly=500)
    f.wire([(700, 425), (665, 425), (665, 700)], BLK, width=3)

    # 急停
    es = f.module(700, 510, 340, 160, "急停按钮（必须用常闭 NC）", {"l": ["COM 公共", "NC 常闭"], "r": []},
                  color="#b71c1c", sub="22mm 蘑菇头，一常闭")
    f.wire([(700, 565), (640, 565), (640, 96)], PUR, width=3, label="← 3V3", lx=560, ly=130)
    f.wire([(700, 605), (560, 605), (560, 580), (360, 580)], GRN, width=3, label="→ IO12", lx=470, ly=590)

    # 旋钮
    kn = f.module(700, 700, 340, 160, "手动 / 自动 旋钮开关", {"l": ["COM 公共", "手动档", "自动档"], "r": []},
                  color="#4a148c", sub="2 档拨动 或 3 档旋钮")
    f.wire([(700, 755), (540, 755), (540, 620), (360, 620)], GRN, width=3, label="→ IO13", lx=450, ly=630)
    f.wire([(700, 795), (660, 795), (660, 700)], BLK, width=3)
    f.wire([(700, 835), (680, 835)], GRAY, width=3, dash="7,5")
    f.text(676, 850, "自动档：不接（悬空）", size=12.5, color=GRAY, anchor="ct")

    f.note(60, 800, 600, [
        "· 限位开关用 NO（常开）触点；触发（压下）时才闭合到 GND，固件读成“触发”。",
        "· 每个限位开关有三只脚：COM / NO / NC。请用 COM 和 NO，NC 空着。",
        "· 急停必须用 NC（常闭）：3V3→COM，NC→IO12。正常是高电平，",
        "  按下 或 线断 都变低 = 急停 → 失效安全（这也是为什么要接 3V3 而不是 GND）。",
        "· 旋钮：公共端→IO13，手动档→GND，自动档留空。",
    ], title="接线要点")

    f.note(60, 1085 - 260, 1540, [
        "· 上电后如果立刻报 fault/estop：多半是急停没接或接错（它默认“断线=急停”）。",
        "  临时可以先 set hwEstopEnabled 0 跳过，但正式使用一定要接好。",
        "· 没装限位就先 set limitEnabled 0 旁路；但旁路后 deploy/stow 会被固件拒绝（没有终点不准盲走）。",
        "· 限位和急停都是长线，户外建议用屏蔽线，屏蔽层一端接 GND。",
    ], title="排错", color="#b71c1c", fill="#ffebee")
    f.save(os.path.join(out, "4-安全链"))


# ============================================================================
# 图 5 —— 传感器与面板
# ============================================================================
def fig_sensors(out):
    f = Fig(1780, 1180, "传感器")
    f.heading(40, 26, "第 5 张 · 传感器 + 面板怎么接")
    f.text(40, 60, "★ 光敏模块、雨滴模块的 VCC 一定要用 3V3，不能用 5V（5V 会让 AO 输出 5V，烧 ADC 脚）。",
           size=14, color="#b71c1c", bold=True)

    esp = f.module(60, 380, 300, 470, "ESP32-S3 开发板",
                   {"l": ["3V3", "GND"], "r": ["IO1", "IO2", "IO3", "IO14", "IO21", "IO38", "IO39",
                                               "IO47", "IO48"]}, color="#1a237e",
                   sub="右列只列出用到的脚")
    (v3, _), (g3, _) = esp["l"]
    R = {n: p for p, n in esp["r"]}
    f.wire([(v3[0] - 80, v3[1]), (v3[0], v3[1])], PUR, width=5)
    f.label(28, v3[1] - 22, "3V3", color=PUR, size=13)
    f.wire([(g3[0] - 80, g3[1]), (g3[0], g3[1])], BLK, width=5)
    f.label(28, g3[1] - 22, "GND", color=BLK, size=13)
    f.wire([(380, 900), (1740, 900)], BLK, width=6)
    f.label(1050, 900, "公共地 GND", color=BLK, size=14)
    f.wire([(360, 430), (430, 430), (430, 240), (1500, 240)], PUR, width=4)
    f.label(960, 240, "3V3 电源轨（给传感器用）", color=PUR, size=13)

    # 光照
    li = f.module(760, 120, 380, 130, "光敏电阻模块（3.3V）", {"l": ["VCC", "GND", "AO"]}, color="#ef6c00",
                  sub="只用 AO，DO 不用")
    f.wire([(760, 175), (700, 175), (700, 240)], PUR, width=3)
    f.wire([(760, 205), (720, 205), (720, 900)], BLK, width=3)
    f.wire([(760, 235), (660, 235), (660, 480), (360, 480)], GRN, width=3, label="→ IO1", lx=590, ly=500)

    # 雨
    ra = f.module(760, 290, 380, 130, "雨滴模块 YL-83（3.3V！）", {"l": ["VCC", "GND", "AO"]}, color="#ef6c00",
                  sub="AO 模拟量；户外建议加热型")
    f.wire([(760, 345), (710, 345), (710, 240)], PUR, width=3)
    f.wire([(760, 375), (730, 375), (730, 900)], BLK, width=3)
    f.wire([(760, 405), (680, 405), (680, 520), (360, 520)], GRN, width=3, label="→ IO2", lx=610, ly=540)

    # 风
    wi = f.module(760, 460, 380, 120, "风速开关（干接点）", {"l": ["线1", "线2"]}, color="#ef6c00",
                  sub="风杯式/风压式，两线无极性")
    f.wire([(760, 510), (640, 510), (640, 560), (360, 560)], GRN, width=3, label="→ IO14", lx=580, ly=580)
    f.wire([(760, 550), (740, 550), (740, 900)], BLK, width=3)

    # 电位器
    po = f.module(760, 620, 380, 140, "10k 多圈电位器", {"l": ["脚1 (端)", "脚2 (中点)", "脚3 (端)"]},
                  color="#ef6c00", sub="当“光照设定点”用")
    f.wire([(760, 675), (660, 675), (660, 240)], PUR, width=3)
    f.wire([(760, 715), (620, 715), (620, 600), (360, 600)], GRN, width=3, label="→ IO3", lx=560, ly=620)
    f.wire([(760, 755), (700, 755), (700, 900)], BLK, width=3)

    # 按键
    f.rect(1180, 120, 560, 300, fill="#fbfbfd", stroke="#90a4ae", width=2, r=10, dash="8,6")
    f.text(1200, 132, "面板三键（12×12 轻触带帽）", size=15, color="#37474f", bold=True)
    for i, (nm, io) in enumerate([("MODE 模式/急停", "IO21"), ("CW 展开", "IO38"), ("CCW 收网", "IO39")]):
        yy = 176 + i * 74
        f.rect(1200, yy, 520, 58, fill="#ffffff", stroke="#cfd8dc", width=1.5, r=8)
        f.circle(1230, yy + 29, 10, fill="#eeeeee", stroke="#607d8b", width=2)
        f.text(1252, yy + 20, nm, size=14, color="#102027", bold=True)
        f.text(1420, yy + 21, "一脚→GND　另一脚→" + io, size=13, color="#455a64")
    f.text(1200, 398, "按键按下 = 把 IO 拉到 GND = 固件识别为“按下”", size=12.5, color="#546e7a")

    # LED
    f.rect(1180, 440, 560, 220, fill="#fbfbfd", stroke="#90a4ae", width=2, r=10, dash="8,6")
    f.text(1200, 452, "指示灯（可选，不接也能用）", size=15, color="#37474f", bold=True)
    for i, (nm, io) in enumerate([("LED1 运行/故障", "IO47"), ("LED2 电机动作", "IO48")]):
        yy = 496 + i * 76
        f.wire([(1200, yy + 30), (1260, yy + 30)], GRN, width=3)
        f.text(1200, yy + 4, io, size=13, color="#102027", bold=True)
        f.rect(1260, yy + 20, 60, 20, fill="#fffde7", stroke="#455a64", width=1.5, r=3)
        f.text(1290, yy + 30, "1kΩ", size=12, color="#37474f", anchor="cm")
        f.wire([(1320, yy + 30), (1380, yy + 30)], GRN, width=3)
        f.circle(1396, yy + 30, 15, fill="#ffcdd2", stroke="#b71c1c", width=2)
        f.text(1396, yy + 30, "LED", size=11, color="#b71c1c", anchor="cm", bold=True)
        f.wire([(1411, yy + 30), (1470, yy + 30), (1470, 900)], BLK, width=3)
        f.text(1500, yy + 21, "长脚(+) 朝左，短脚(-) 朝右", size=12.5, color="#546e7a")
    f.text(1200, 630, "LED 必须串 1kΩ 电阻，否则会烧掉 IO 口。", size=13, color="#b71c1c")

    f.note(760, 800, 980, [
        "· 光敏/雨滴模块一般是 4 脚：VCC / GND / DO / AO。我们只用 VCC、GND、AO，DO 空着。",
        "· 雨滴模块的探头（那块小板）不要长期露天裸放，会氧化；户外改用带加热的雨雪传感器。",
        "· 风速开关要装在没有遮挡、也不会被网自己挡住的地方。",
        "· 电位器装反了没关系，只是“光越强越展开”变成反的；用 set thUp/thDown 也能改成绝对阈值。",
        "· 接完在网页/App 里看 state：light/pot/rain 的 raw 应该在 0~4095 中间，不是 0 也不是 4095。",
    ], title="要点", color="#1b5e20", fill="#e8f5e9")
    f.save(os.path.join(out, "5-传感器与面板"))


def main():
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "接线手册")
    print("输出目录:", out)
    fig_overview(out)
    fig_power(out)
    fig_motor(out)
    fig_safety(out)
    fig_sensors(out)
    print("完成")


if __name__ == "__main__":
    main()
