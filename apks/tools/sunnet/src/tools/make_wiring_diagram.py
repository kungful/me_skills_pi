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

RED   = "#d32f2f"   # +12V
ORG   = "#ef6c00"   # +5V
PUR   = "#7b1fa2"   # +3V3
BLK   = "#212121"   # GND
GRN   = "#2e7d32"   # 信号 1
BLU   = "#1565c0"   # 信号 2
GRAY  = "#78909c"   # 说明/机械

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL = True
except Exception:
    _PIL = False


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Fig:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.svg = []
        self._fonts = {}
        if _PIL:
            self.img = Image.new("RGB", (w * SCALE, h * SCALE), "#ffffff")
            self.d = ImageDraw.Draw(self.img)

    def _f(self, size, bold=False):
        key = (size, bold)
        if key not in self._fonts:
            self._fonts[key] = ImageFont.truetype(FONTB if bold else FONT, size * SCALE) if _PIL else None
        return self._fonts[key]

    # ---------- 基本图元 ----------
    def rect(self, x, y, w, h, fill="#ffffff", stroke="#455a64", width=2, r=10, dash=None):
        xi, yi, wi, hi = (int(round(v)) for v in (x, y, w, h))
        r = int(round(r))
        width = max(1, int(round(width)))
        if _PIL:
            if r > 0:
                self.d.rounded_rectangle([xi * SCALE, yi * SCALE, (xi + wi) * SCALE, (yi + hi) * SCALE],
                                         radius=r * SCALE, fill=fill, outline=stroke, width=width * SCALE)
            else:
                self.d.rectangle([xi * SCALE, yi * SCALE, (xi + wi) * SCALE, (yi + hi) * SCALE],
                                 fill=fill, outline=stroke, width=width * SCALE)
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" '
                        f'stroke="{stroke}" stroke-width="{width}"{da}/>')

    def text(self, x, y, s, size=15, color="#111111", anchor="lt", bold=False):
        if _PIL:
            a = {"lt": "la", "lm": "lm", "ct": "ma", "cm": "mm", "rt": "ra", "rm": "rm"}.get(anchor, "la")
            self.d.text((x * SCALE, y * SCALE), s, font=self._f(size, bold), fill=color, anchor=a)
        amap = {"lt": "start", "lm": "start", "ct": "middle", "cm": "middle", "rt": "end", "rm": "end"}
        dy = {"lt": size * 0.95, "lm": size * 0.36, "ct": size * 0.95, "cm": size * 0.36,
              "rt": size * 0.95, "rm": size * 0.36}.get(anchor, size)
        w = ' font-weight="bold"' if bold else ""
        self.svg.append(f'<text x="{x}" y="{y + dy}" font-family="{SVG_FONT}" font-size="{size}" '
                        f'fill="{color}" text-anchor="{amap}"{w}>{esc(s)}</text>')

    def line(self, pts, color, width=3, dash=None):
        width = max(1, int(round(width)))
        if _PIL:
            if dash:
                self._dashed(pts, color, width, dash)
            else:
                self.d.line([(p[0] * SCALE, p[1] * SCALE) for p in pts], fill=color,
                            width=width * SCALE, joint="curve")
        p = " ".join(f"{a},{b}" for a, b in pts)
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.svg.append(f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="{width}" '
                        f'stroke-linejoin="round"{da}/>')

    def _dashed(self, pts, color, width, dash):
        import math
        on = float(str(dash).split(",")[0]) if "," in str(dash) else 8.0
        off = on * 0.7
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
                             ((x1 + ux * e) * SCALE, (y1 + uy * e) * SCALE)], fill=color, width=width * SCALE)
                t = e + off

    def circle(self, x, y, r, fill="#ffffff", stroke="#455a64", width=2):
        r = int(round(r))
        width = max(1, int(round(width)))
        if _PIL:
            self.d.ellipse([(x - r) * SCALE, (y - r) * SCALE, (x + r) * SCALE, (y + r) * SCALE],
                           fill=fill, outline=stroke, width=width * SCALE)
        self.svg.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" '
                        f'stroke-width="{width}"/>')

    def label(self, x, y, s, color="#ffffff", size=12, pad=4):
        w = max(16, len(s) * size * 0.80 + pad * 2)
        h = size * 1.5
        self.rect(x - w / 2, y - h / 2, w, h, fill="#ffffff", stroke=color, width=1.2, r=4)
        self.text(x, y, s, size=size, color=color, anchor="cm", bold=True)

    # ---------- 模块 ----------
    def module(self, x, y, w, h, title, terms=None, color="#37474f", fill="#f5f7fa", sub=None, bar=30):
        terms = terms or {}
        self.rect(x, y, w, h, fill=fill, stroke=color, width=2, r=10)
        self.rect(x, y, w, bar, fill=color, stroke=color, width=1, r=8)
        self.rect(x, y + bar - 9, w, 10, fill=color, stroke=color, width=0, r=0)
        self.text(x + w / 2, y + bar / 2, title, size=14, color="#ffffff", anchor="cm", bold=True)
        if sub:
            self.text(x + w / 2, y + bar + 6, sub, size=11, color="#546e7a", anchor="ct")
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

    def heading(self, x, y, s, size=21):
        self.text(x, y, s, size=size, color="#102027", bold=True)

    def note(self, x, y, w, lines, title="注意", color="#e65100", fill="#fff8e1", size=13.5):
        h = 30 + len(lines) * 21
        self.rect(x, y, w, h, fill=fill, stroke=color, width=2, r=8)
        self.text(x + 12, y + 8, title, size=15, color=color, bold=True)
        for i, ln in enumerate(lines):
            self.text(x + 12, y + 34 + i * 21, ln, size=size, color="#4e342e")
        return y + h

    def gnd_bus(self, x1, x2, y, label="公共地 GND（所有模块的 GND 都要连到这里）"):
        self.line([(x1, y), (x2, y)], BLK, width=6)
        self.label((x1 + x2) / 2, y - 24, label, color=BLK, size=13)

    def save(self, path_noext):
        os.makedirs(os.path.dirname(path_noext), exist_ok=True)
        head = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}">\n<rect width="{self.w}" height="{self.h}" fill="#ffffff"/>\n')
        with open(path_noext + ".svg", "w", encoding="utf-8") as f:
            f.write(head + "\n".join(self.svg) + "\n</svg>\n")
        if _PIL:
            self.img.save(path_noext + ".png")
        print("  ->", os.path.basename(path_noext) + ".svg / .png")


# ============================================================================
# 图 1 —— 总览
# ============================================================================
def fig_overview(out):
    f = Fig(1780, 1210)
    f.heading(40, 26, "太阳网自动控制器 · 散装模块版 【总览】")
    f.text(40, 60, "全部用现成模块 + 端子接线，不用画 PCB。每一步的细接线看第 2~5 张图。",
           size=14, color="#546e7a")

    f.module(40, 120, 150, 90, "市电 220V", {"r": ["L", "N"]}, color="#455a64")
    f.module(250, 110, 200, 110, "12V / 3A 电源适配器", {"l": ["L", "N"], "r": ["+12V", "GND"]},
             color="#455a64", sub="输出 ≥3A")
    f.module(510, 135, 130, 60, "3A 保险丝", {"l": ["IN"], "r": ["OUT"]}, color="#455a64", bar=26)
    f.rect(688, 120, 16, 90, fill=BLK, stroke=BLK, width=0, r=3)
    f.wire([(190, 170), (250, 167)], RED, width=4)
    f.wire([(190, 190), (250, 193)], BLK, width=3)
    f.wire([(450, 167), (510, 152)], RED, width=5)
    f.wire([(450, 193), (490, 193)], BLK, width=3)
    f.label(560, 196, "→ 公共地 GND", color=BLK, size=11)
    f.wire([(640, 152), (688, 165)], RED, width=5)

    f.module(760, 60, 230, 110, "MOS 触发开关模块", {"l": ["VIN+", "VIN-"], "r": ["VOUT+", "VOUT-"]},
             color="#00695c", sub="母线总闸，高电平触发")
    f.module(760, 230, 230, 110, "LM2596 降压模块", {"l": ["IN+", "IN-"], "r": ["OUT+", "OUT-"]},
             color="#00695c", sub="12V → 5.0V")
    f.wire([(704, 167), (730, 167), (730, 117), (760, 117)], RED, width=5)
    f.wire([(704, 167), (730, 167), (730, 287), (760, 287)], RED, width=5)
    f.wire([(760, 143), (720, 143)], BLK, width=3)
    f.label(650, 143, "→ 公共地", color=BLK, size=11)
    f.wire([(760, 313), (715, 313)], BLK, width=3)
    f.label(645, 313, "→ 公共地", color=BLK, size=11)

    f.module(1060, 60, 240, 120, "DRV8871 电机驱动模块", {"l": ["VM", "GND"], "r": ["OUT1", "OUT2"]},
             color="#00695c", sub="IN1/IN2 控方向")
    f.module(1370, 70, 170, 100, "直流减速电机", {"l": ["+", "-"]}, color="#37474f", sub="收网 / 展开")
    f.wire([(990, 117), (1030, 117), (1030, 120), (1060, 120)], RED, width=5)
    f.wire([(990, 143), (1020, 143), (1020, 150), (1060, 150)], BLK, width=3)
    f.wire([(1300, 120), (1335, 120), (1335, 123), (1370, 123)], RED, width=5)
    f.wire([(1300, 150), (1352, 150), (1352, 147), (1370, 147)], BLU, width=5)

    f.module(600, 480, 360, 300, "ESP32-S3-DevKitC-1", {"r": ["5V", "GND"], "l": ["3V3", "GND"]},
             color="#1a237e", sub="N16R8 双 Type-C", bar=34)
    f.wire([(990, 287), (1005, 287), (1005, 602), (960, 602)], ORG, width=5, label="+5V", lx=1005, ly=450)
    f.wire([(960, 691), (975, 691), (975, 960)], BLK, width=4)
    f.wire([(700, 480), (700, 240)], GRN, width=4, dash="11,7")
    f.text(694, 254, "↑ 控制线（IO4 / IO5 / IO6、母线使能）去电机 → 第 3 张图", size=12.5, color=GRN, anchor="rt")

    f.rect(60, 480, 480, 460, fill="#fbfbfd", stroke="#90a4ae", width=2, r=12, dash="8,6")
    f.text(80, 494, "安全链（干接点，低 = 触发）　→ 第 4 张图", size=15, color="#37474f", bold=True)
    for i, (a, b) in enumerate([("限位 A（展开终点）", "NO → IO7　　　COM → GND"),
                                ("限位 B（收网终点）", "NO → IO11　　 COM → GND"),
                                ("急停按钮（常闭 NC）", "3V3 → COM　　 NC → IO12"),
                                ("手动 / 自动 旋钮", "COM → IO13　　手动档 → GND")]):
        yy = 535 + i * 82
        f.rect(80, yy, 440, 62, fill="#ffffff", stroke="#cfd8dc", width=1.5, r=8)
        f.text(96, yy + 10, a, size=14, color="#102027", bold=True)
        f.text(96, yy + 34, b, size=13, color="#455a64")

    f.rect(1020, 480, 700, 460, fill="#fbfbfd", stroke="#90a4ae", width=2, r=12, dash="8,6")
    f.text(1040, 494, "传感器 + 面板　→ 第 5 张图", size=15, color="#37474f", bold=True)
    for i, (a, b) in enumerate([("光照模块 AO", "VCC → 3V3　　AO → IO1"),
                                ("雨滴模块 AO", "VCC → 3V3（必须）　AO → IO2"),
                                ("风速开关", "一线 → IO14　　另一线 → GND"),
                                ("设定点电位器", "两端 3V3/GND　中点 → IO3"),
                                ("按键 ×3", "一脚 GND　　另一脚 IO21 / IO38 / IO39"),
                                ("指示灯 ×2", "IO47 / IO48 → 1kΩ → LED → GND")]):
        yy = 532 + i * 62
        f.rect(1040, yy, 660, 48, fill="#ffffff", stroke="#cfd8dc", width=1.5, r=8)
        f.text(1054, yy + 7, a, size=13.5, color="#102027", bold=True)
        f.text(1240, yy + 8, b, size=13, color="#455a64")

    f.wire([(600, 640), (560, 640), (560, 700), (542, 700)], GRN, width=3, dash="11,7")
    f.wire([(960, 640), (980, 640), (980, 700), (1018, 700)], GRN, width=3, dash="11,7")

    f.gnd_bus(60, 1720, 985, "公共地 GND —— ESP32 / MOS / DRV8871 / LM2596 / 所有传感器开关的 GND 都接到这里")
    f.wire([(300, 940), (300, 985)], BLK, width=4)
    f.wire([(1370, 940), (1370, 985)], BLK, width=4)

    f.note(40, 1040, 1700, [
        "① 先只接电源部分（第 2 张图），用万用表确认 +12V 和 +5V 都对，再插 ESP32。",
        "② 所有模块的模拟输出只能 3.3V：光敏 / 雨滴模块一律用 3.3V 供电，不要用 5V。",
        "③ 任何接线、改线之前，先拔掉 12V 电源；接完先用万用表量一遍再上电。",
    ], title="※ 三步安全顺序")
    f.save(os.path.join(out, "1-总览"))


# ============================================================================
# 图 2 —— 电源
# ============================================================================
def fig_power(out):
    f = Fig(1700, 745)
    f.heading(40, 26, "第 2 张 · 电源怎么接（先接这张，接完先量电压）")

    f.module(50, 140, 220, 140, "12V 电源适配器", {"r": ["+12V", "GND"]}, color="#455a64", sub="≥3A")
    f.module(360, 165, 150, 90, "保险丝座", {"l": ["IN"], "r": ["OUT"]}, color="#455a64", sub="3A 保险管")
    f.wire([(270, 195), (360, 195)], RED, width=5)
    f.wire([(270, 235), (330, 235), (330, 300), (1330, 300), (1330, 265)], BLK, width=4)

    f.rect(600, 100, 260, 230, fill="#e8f5e9", stroke="#2e7d32", width=2, r=10)
    f.text(730, 110, "接线端子排（中线）", size=14, color="#1b5e20", anchor="ct", bold=True)
    f.text(618, 136, "+12V 排", size=13, color=RED, bold=True)
    f.text(618, 236, "GND 排", size=13, color=BLK, bold=True)
    f.wire([(600, 170), (860, 170)], RED, width=5)
    f.wire([(600, 260), (860, 260)], BLK, width=5)
    for i in range(4):
        xx = 660 + i * 62
        f.circle(xx, 170, 7, fill="#fff", stroke=RED, width=2)
        f.circle(xx, 260, 7, fill="#fff", stroke=BLK, width=2)
    f.wire([(510, 195), (560, 195), (560, 170), (600, 170)], RED, width=5, label="+12V", lx=545, ly=182)

    f.module(980, 90, 280, 210, "LM2596S 降压模块", {"l": ["IN+", "IN-"], "r": ["OUT+", "OUT-"]},
             color="#00695c", sub="先空载调到 5.0V")
    f.wire([(860, 170), (900, 170), (900, 140), (980, 140)], RED, width=5)
    f.wire([(860, 260), (930, 260), (930, 250), (980, 250)], BLK, width=4)

    f.module(1360, 110, 300, 170, "ESP32-S3 开发板", {"l": ["5V", "GND"]}, color="#1a237e",
             sub="先别插 USB")
    f.wire([(1260, 155), (1360, 155)], ORG, width=5, label="+5V", lx=1310, ly=142)
    f.wire([(1260, 235), (1330, 235), (1330, 265)], BLK, width=4)

    f.module(980, 400, 280, 140, "MOS 开关模块", {"l": ["VIN+", "VIN-"]}, color="#00695c",
             sub="母线电从这里过")
    f.wire([(860, 170), (920, 170), (920, 460), (980, 460)], RED, width=5)
    f.wire([(860, 260), (960, 260), (960, 500), (980, 500)], BLK, width=4)

    f.note(50, 400, 880, [
        "① 把 12V 适配器、保险丝、端子排、LM2596 先接好，ESP32 先不插。",
        "② 万用表直流档：端子排 +12V 排 对 GND 排 应显示 12V 左右（±0.5V）。",
        "③ 拧 LM2596 上的蓝色电位器，让 OUT+ 对 OUT- 正好 5.0V（4.9~5.1 都行）。",
        "④ 确认后再把 LM2596 的 OUT+ → ESP32 的 5V，OUT- → ESP32 的 GND。",
        "⑤ 保险丝必须装在 +12V 这一根上（靠近电源那端），不要装在地线上。",
    ], title="※ 上电顺序（一定按这个来）")

    f.note(50, 660 - 115, 880, [
        "· 电源正负极千万别接反：反接会瞬间烧掉模块。接完再量一遍。",
        "· 12V 适配器电流要 ≥3A（电机启动电流大，1A 的会“打嗝”）。",
        "· 用 USB 给 ESP32 烧程序时，把 12V 电源关掉。",
        "· 户外用请换 12V/5A 防水电源（IP67），并加直流防雷器。",
    ], title="常见错误", color="#b71c1c", fill="#ffebee")

    f.text(1330, 330, "线色约定：", size=14, color="#37474f", bold=True)
    for i, (c, t) in enumerate([(RED, "红 = +12V"), (ORG, "橙 = +5V"), (BLK, "黑 = GND")]):
        f.wire([(1330, 368 + i * 34), (1385, 368 + i * 34)], c, width=5)
        f.text(1396, 368 + i * 34 - 9, t, size=13.5, color="#37474f")
    f.save(os.path.join(out, "2-电源"))


# ============================================================================
# 图 3 —— 电机
# ============================================================================
def fig_motor(out):
    f = Fig(1720, 1090)
    f.heading(40, 26, "第 3 张 · 电机怎么接（母线高边开关 + DRV8871）")

    esp = f.module(40, 280, 290, 400, "ESP32-S3 开发板", {"r": ["IO6", "IO4", "IO5", "GND"]},
                   color="#1a237e", sub="只列出用到的脚")
    io6 = esp["r"][0][0]
    io4 = esp["r"][1][0]
    io5 = esp["r"][2][0]
    gnd = esp["r"][3][0]

    mos = f.module(540, 120, 320, 240, "MOS 触发开关模块", {"l": ["VIN+", "VIN-", "SIG"], "r": ["VOUT+", "VOUT-"]},
                   color="#00695c", sub="高电平触发，15A")
    vinp = mos["l"][0][0]
    vinm = mos["l"][1][0]
    sig = mos["l"][2][0]
    voutp = mos["r"][0][0]
    voutm = mos["r"][1][0]

    drv = f.module(980, 110, 320, 340, "DRV8871 模块", {"l": ["VM", "GND", "IN1", "IN2"], "r": ["OUT1", "OUT2"]},
                   color="#00695c", sub="IN1/IN2 决定方向")
    vm = drv["l"][0][0]
    dgnd = drv["l"][1][0]
    in1 = drv["l"][2][0]
    in2 = drv["l"][3][0]
    o1 = drv["r"][0][0]
    o2 = drv["r"][1][0]

    mot = f.module(1400, 180, 220, 150, "电机（网机）", {"l": ["+", "-"]}, color="#37474f")
    mp = mot["l"][0][0]
    mn = mot["l"][1][0]

    f.wire([(460, vinp[1]), (540, vinp[1])], RED, width=5)
    f.label(500, vinp[1] - 30, "+12V ← 端子排", color=RED, size=12)
    f.wire([(540, vinm[1]), (500, vinm[1]), (500, 700)], BLK, width=4)
    f.wire([(860, voutp[1]), (920, voutp[1]), (920, vm[1]), (980, vm[1])], RED, width=5)
    f.wire([(860, voutm[1]), (950, voutm[1]), (950, dgnd[1]), (980, dgnd[1])], BLK, width=4)
    f.wire([(io6[0], io6[1]), (480, io6[1]), (480, sig[1]), (540, sig[1])], GRN, width=3,
           label="IO6 = 母线使能", lx=430, ly=io6[1] - 34)
    f.wire([(io4[0], io4[1]), (900, io4[1]), (900, in1[1]), (980, in1[1])], GRN, width=3,
           label="IO4 → IN1", lx=780, ly=io4[1] - 22)
    f.wire([(io5[0], io5[1]), (940, io5[1]), (940, in2[1]), (980, in2[1])], BLU, width=3,
           label="IO5 → IN2", lx=790, ly=io5[1] + 22)
    f.wire([(gnd[0], gnd[1]), (700, gnd[1]), (700, 700)], BLK, width=4)
    f.wire([(1300, o1[1]), (1345, o1[1]), (1345, mp[1]), (1400, mp[1])], RED, width=5)
    f.wire([(1300, o2[1]), (1370, o2[1]), (1370, mn[1]), (1400, mn[1])], BLU, width=5)
    f.text(1510, 350, "换向 = IN1/IN2 电平互换", size=12.5, color="#546e7a", anchor="cm")
    f.text(1510, 372, "接反只是方向相反，不烧", size=12, color="#90a4ae", anchor="cm")

    f.gnd_bus(40, 1700, 700, "公共地 GND")

    f.note(40, 745, 800, [
        "· IO6（MOT_EN）不拉高，电机永远不转——这是母线电的“总闸”。",
        "· MOS 模块若 3.3V 触发不灵（有的要 5V），加一级电平转换：",
        "   IO6 →1kΩ→ S8050 基极；发射极→GND；集电极→MOS 的 SIG；",
        "   SIG 再经 10kΩ 上拉到 +5V。",
        "· DRV8871 的 IN1/IN2 是 3.3V 逻辑，可直接接。",
    ], title="要点", color="#1b5e20", fill="#e8f5e9")

    f.note(880, 745, 800, [
        "① IO6 先悬空、只上 12V：量 DRV8871 的 VM 对 GND 应为 0V（母线被 MOS 断开）。",
        "② 连上热点，App 里点 JOG CW / CCW：VM 应出现 12V、电机转；松手后 VM 回 0V。",
        "③ 空载跑一次全程，确认限位 A / B 都能让电机停住。",
        "④ 再挂上真网跑，量一下电机电流，据此设 set stallMa（建议 800~1200）。",
    ], title="联调步骤", color="#0d47a1", fill="#e3f2fd")
    f.save(os.path.join(out, "3-电机"))


# ============================================================================
# 图 4 —— 安全链
# ============================================================================
def fig_safety(out):
    f = Fig(1780, 1280)
    f.heading(40, 26, "第 4 张 · 安全链：限位 / 急停 / 手动自动（干接点，低 = 触发）")
    f.text(40, 60, "散装版没有板上的 10k 上拉电阻，固件已改用芯片内部上拉/下拉 —— 所以你不用外接任何电阻。",
           size=13.5, color="#00695c")

    esp = f.module(60, 380, 300, 420, "ESP32-S3 开发板", {"l": ["3V3", "GND"], "r": ["IO7", "IO11", "IO12", "IO13"]},
                   color="#1a237e")
    v3 = esp["l"][0][0]
    eg = esp["l"][1][0]
    R = {n: p for p, n in esp["r"]}

    fa = f.module(760, 140, 360, 150, "限位开关 A（展开终点）", {"l": ["NO 常开", "COM 公共"]},
                  color="#b71c1c", sub="V-156-1C25 长柄滚轮")
    a_no, a_com = fa["l"][0][0], fa["l"][1][0]
    fb = f.module(760, 330, 360, 150, "限位开关 B（收网终点）", {"l": ["NO 常开", "COM 公共"]},
                  color="#b71c1c")
    b_no, b_com = fb["l"][0][0], fb["l"][1][0]
    fe = f.module(760, 520, 360, 150, "急停按钮（必须用常闭 NC）", {"l": ["COM 公共", "NC 常闭"]},
                  color="#b71c1c", sub="22mm 蘑菇头，一常闭")
    e_com, e_nc = fe["l"][0][0], fe["l"][1][0]
    fk = f.module(760, 710, 360, 170, "手动 / 自动 旋钮开关", {"l": ["COM 公共", "手动档", "自动档"]},
                  color="#4a148c", sub="2 档拨动 或 3 档旋钮")
    k_com, k_man, k_auto = fk["l"][0][0], fk["l"][1][0], fk["l"][2][0]

    # 3V3 轨（只给急停）
    f.wire([(v3[0], v3[1]), (20, v3[1]), (20, 100), (1000, 100)], PUR, width=5)
    f.label(600, 100, "3V3（只给急停用）", color=PUR, size=13)
    f.wire([(e_com[0], e_com[1]), (700, e_com[1]), (700, 100)], PUR, width=3)
    f.label(700, 350, "← 3V3", color=PUR, size=12)

    f.gnd_bus(20, 1740, 1000, "公共地 GND")
    f.wire([(eg[0], eg[1]), (42, eg[1]), (42, 1000)], BLK, width=4)

    f.wire([(R["IO7"][0], R["IO7"][1]), (740, R["IO7"][1]), (740, a_no[1]), (a_no[0], a_no[1])],
           GRN, width=3, label="→ IO7", lx=560, ly=R["IO7"][1] - 20)
    f.wire([(a_com[0], a_com[1]), (730, a_com[1]), (730, 1000)], BLK, width=3)
    f.wire([(R["IO11"][0], R["IO11"][1]), (690, R["IO11"][1]), (690, b_no[1]), (b_no[0], b_no[1])],
           GRN, width=3, label="→ IO11", lx=560, ly=R["IO11"][1] - 20)
    f.wire([(b_com[0], b_com[1]), (680, b_com[1]), (680, 1000)], BLK, width=3)
    f.wire([(R["IO12"][0], R["IO12"][1]), (670, R["IO12"][1]), (670, e_nc[1]), (e_nc[0], e_nc[1])],
           GRN, width=3, label="→ IO12", lx=560, ly=R["IO12"][1] - 20)
    f.wire([(R["IO13"][0], R["IO13"][1]), (650, R["IO13"][1]), (650, k_com[1]), (k_com[0], k_com[1])],
           GRN, width=3, label="→ IO13", lx=560, ly=R["IO13"][1] - 20)
    f.wire([(k_man[0], k_man[1]), (640, k_man[1]), (640, 1000)], BLK, width=3)
    f.wire([(k_auto[0], k_auto[1]), (600, k_auto[1])], GRAY, width=3, dash="7,5")
    f.text(585, k_auto[1] + 16, "自动档：不接（悬空 = 内部上拉 = 自动）", size=12.5, color=GRAY, anchor="rt")

    f.note(60, 1045, 800, [
        "· 限位开关用 NO（常开）：压下才闭合到 GND，固件读成“触发”。",
        "· 开关上标着 COM / NO / NC 三只脚，用 COM 和 NO，NC 空着。",
        "· 急停必须用 NC（常闭）：3V3→COM，NC→IO12。正常是高电平；",
        "  按下 或 线断 都变低 = 急停 → 失效安全（所以它要接 3V3，不是 GND）。",
        "· 旋钮：COM→IO13，手动档→GND，自动档留空。",
    ], title="接线要点")

    f.note(890, 1045, 830, [
        "· 一上电就报 fault/estop：多半是急停没接或接错（它默认“断线=急停”）。",
        "  临时可 set hwEstopEnabled 0 跳过，正式使用一定要接好。",
        "· 没装限位就先 set limitEnabled 0 旁路；旁路后 deploy/stow 会被固件拒绝",
        "  （没有终点不准盲走）。",
        "· 限位/急停是长线，户外用屏蔽线，屏蔽层只在 ESP32 这一端接 GND。",
    ], title="排错", color="#b71c1c", fill="#ffebee")
    f.save(os.path.join(out, "4-安全链"))


# ============================================================================
# 图 5 —— 传感器与面板
# ============================================================================
def fig_sensors(out):
    f = Fig(1780, 1190)
    f.heading(40, 26, "第 5 张 · 传感器 + 面板怎么接")
    f.text(40, 60, "★ 光敏模块、雨滴模块的 VCC 一定要接 3V3，不能接 5V（5V 会让 AO 输出 5V，烧掉 ADC 脚）。",
           size=14, color="#b71c1c", bold=True)

    order = ["IO1", "IO2", "IO14", "IO3", "IO21", "IO38", "IO39", "IO47", "IO48"]
    esp = f.module(60, 380, 300, 470, "ESP32-S3 开发板", {"l": ["3V3", "GND"], "r": order},
                   color="#1a237e", sub="右列只列出用到的脚")
    v3 = esp["l"][0][0]
    eg = esp["l"][1][0]
    R = {n: p for p, n in esp["r"]}

    li = f.module(760, 120, 380, 130, "光敏电阻模块（3.3V）", {"l": ["VCC", "GND", "AO"]}, color="#ef6c00",
                  sub="只用 AO，DO 不用")
    ra = f.module(760, 300, 380, 130, "雨滴模块 YL-83（3.3V！）", {"l": ["VCC", "GND", "AO"]}, color="#ef6c00",
                  sub="AO 模拟量；户外建议加热型")
    wi = f.module(760, 480, 380, 120, "风速开关（干接点）", {"l": ["线 1", "线 2"]}, color="#ef6c00",
                  sub="风杯式 / 风压式，两线无极性")
    po = f.module(760, 650, 380, 140, "10k 多圈电位器", {"l": ["脚1 (端)", "脚2 (中点)", "脚3 (端)"]},
                  color="#ef6c00", sub="当“光照设定点”用")

    # 3V3 电源轨（只到传感器那一列）
    f.wire([(v3[0], v3[1]), (20, v3[1]), (20, 240), (700, 240)], PUR, width=5)
    f.label(470, 240, "3V3 电源轨（给传感器用）", color=PUR, size=13)
    f.wire([(700, 240), (700, 675)], PUR, width=4)
    for lv in (li["l"][0][0], ra["l"][0][0], po["l"][0][0]):
        f.wire([(700, lv[1]), (lv[0], lv[1])], PUR, width=3)

    f.wire([(li["l"][2][0][0], li["l"][2][0][1]), (680, li["l"][2][0][1]), (680, R["IO1"][1]), R["IO1"]],
           GRN, width=3, label="→ IO1", lx=530, ly=R["IO1"][1] - 20)
    f.wire([(ra["l"][2][0][0], ra["l"][2][0][1]), (650, ra["l"][2][0][1]), (650, R["IO2"][1]), R["IO2"]],
           GRN, width=3, label="→ IO2", lx=530, ly=R["IO2"][1] - 20)
    f.wire([(wi["l"][0][0][0], wi["l"][0][0][1]), (620, wi["l"][0][0][1]), (620, R["IO14"][1]), R["IO14"]],
           GRN, width=3, label="→ IO14", lx=520, ly=R["IO14"][1] - 20)
    f.wire([(po["l"][1][0][0], po["l"][1][0][1]), (590, po["l"][1][0][1]), (590, R["IO3"][1]), R["IO3"]],
           GRN, width=3, label="→ IO3", lx=520, ly=R["IO3"][1] + 20)

    f.gnd_bus(20, 1740, 880, "公共地 GND")
    f.wire([(eg[0], eg[1]), (42, eg[1]), (42, 880)], BLK, width=4)
    for lv, xv in ((li["l"][1][0], 720), (ra["l"][1][0], 710),
                   (wi["l"][1][0], 735), (po["l"][2][0], 725)):
        f.wire([(lv[0], lv[1]), (xv, lv[1]), (xv, 880)], BLK, width=3)

    # 面板三键
    f.rect(1180, 120, 560, 300, fill="#fbfbfd", stroke="#90a4ae", width=2, r=10, dash="8,6")
    f.text(1200, 132, "面板三键（12×12 轻触带帽）", size=15, color="#37474f", bold=True)
    for i, (nm, io) in enumerate([("MODE 模式 / 急停", "IO21"), ("CW 展开", "IO38"), ("CCW 收网", "IO39")]):
        yy = 178 + i * 74
        f.rect(1200, yy, 520, 58, fill="#ffffff", stroke="#cfd8dc", width=1.5, r=8)
        f.circle(1230, yy + 29, 11, fill="#eeeeee", stroke="#607d8b", width=2)
        f.text(1252, yy + 20, nm, size=14, color="#102027", bold=True)
        f.text(1420, yy + 21, "一脚 → GND　　另一脚 → " + io, size=13, color="#455a64")
    f.text(1200, 400, "按键按下 = 把这个 IO 拉到 GND = 固件识别为“按下”", size=12.5, color="#546e7a")

    # LED
    f.rect(1180, 440, 560, 210, fill="#fbfbfd", stroke="#90a4ae", width=2, r=10, dash="8,6")
    f.text(1200, 452, "指示灯（可选，不接也能用）", size=15, color="#37474f", bold=True)
    for i, (nm, io) in enumerate([("LED1 运行 / 故障", "IO47"), ("LED2 电机动作", "IO48")]):
        yy = 500 + i * 74
        f.text(1200, yy + 20, io, size=13, color="#102027", bold=True)
        f.text(1200, yy - 4, nm, size=11, color="#78909c")
        f.wire([(1268, yy + 30), (1310, yy + 30)], GRN, width=3)
        f.rect(1310, yy + 20, 62, 20, fill="#fffde7", stroke="#455a64", width=1.5, r=3)
        f.text(1341, yy + 30, "1kΩ", size=12, color="#37474f", anchor="cm")
        f.wire([(1372, yy + 30), (1420, yy + 30)], GRN, width=3)
        f.circle(1436, yy + 30, 15, fill="#ffcdd2", stroke="#b71c1c", width=2)
        f.text(1436, yy + 30, "LED", size=11, color="#b71c1c", anchor="cm", bold=True)
        f.wire([(1451, yy + 30), (1520, yy + 30), (1520, 880)], BLK, width=3)
        f.text(1545, yy + 21, "长脚(+) 朝左，短脚(-) 朝右", size=12.5, color="#546e7a")
    f.text(1200, 628, "LED 必须串 1kΩ 电阻，否则会烧掉 IO 口。", size=13, color="#b71c1c")

    f.note(60, 940, 1660, [
        "· 光敏 / 雨滴模块一般是 4 脚：VCC / GND / DO / AO。我们只用 VCC、GND、AO，DO 空着。",
        "· 雨滴模块那块裸露的探头小板不要长期露天放，会氧化；户外改用带加热的雨雪传感器。",
        "· 风速开关要装在没有遮挡、也不会被网自己挡住的地方；电位器装反只是方向反，可用 set thUp/thDown 兜。",
        "· 接完在网页 / App 里看 state：light / pot / rain 的 raw 应在 0~4095 中间，不是 0 也不是 4095。",
        "· 表里的 IOxx 就是板上丝印的 4 / 5 / 6 …（有的板印 IO4、GPIO4，都是同一个脚）。",
    ], title="要点", color="#1b5e20", fill="#e8f5e9")
    f.save(os.path.join(out, "5-传感器与面板"))


def fig_wind_pulse(out):
    f = Fig(1600, 1150)
    f.heading(40, 26, "第 6 张 · 风速计（脉冲型，读真 m/s）")
    f.text(40, 60, "把“风”从“有风/无风”开关升级成真实风速。只有脉冲输出（集电极开路/NPN）的风速计能直接接。",
           size=13.5, color="#1b5e20")

    esp = f.module(60, 320, 320, 400, "ESP32-S3 开发板", {"l": ["3V3", "GND"], "r": ["IO14"]},
                   color="#1a237e", sub="右列只列出用到的脚")
    v3 = esp["l"][0][0]
    eg = esp["l"][1][0]
    io14 = esp["r"][0][0]

    ws = f.module(760, 140, 400, 240, "三杯式风速计（脉冲输出）",
                  {"l": ["电源+ 红", "GND 黑", "脉冲 黄/绿"]}, color="#00695c",
                  sub="写 0-70m/s、脉冲输出的那种")
    wv = ws["l"][0][0]
    wg = ws["l"][1][0]
    wp = ws["l"][2][0]

    pw = f.module(1180, 150, 300, 100, "端子排 / 电源", {"l": ["+12V", "GND"]}, color="#455a64",
                  sub="按风速计铭牌选 5V / 12V / 24V")
    pv = pw["l"][0][0]
    pg = pw["l"][1][0]

    # 脉冲信号 → IO14
    f.wire([(wp[0], wp[1]), (620, wp[1]), (620, io14[1]), (io14[0], io14[1])], GRN, width=3,
           label="脉冲 → IO14", lx=740, ly=wp[1] - 22)
    # 3V3 上拉轨 + 4.7k 上拉电阻
    f.wire([(v3[0], v3[1]), (20, v3[1]), (20, 230), (690, 230)], PUR, width=4)
    f.label(200, 230, "3V3", color=PUR, size=13)
    f.wire([(690, 230), (690, 262)], PUR, width=3)
    f.rect(672, 262, 36, 46, fill="#fffde7", stroke="#455a64", width=2, r=4)
    f.text(690, 285, "4.7k", size=11.5, color="#37474f", anchor="cm", bold=True)
    f.wire([(690, 308), (690, wp[1])], PUR, width=3)
    f.text(710, 318, "上拉电阻：把信号拉到 3.3V，低速时也稳", size=12, color="#546e7a")
    # 电源
    f.wire([(wv[0], wv[1]), (1120, wv[1]), (1120, pv[1]), (pv[0], pv[1])], RED, width=4)
    f.wire([(wg[0], wg[1]), (720, wg[1]), (720, 790)], BLK, width=3)
    f.wire([(pg[0], pg[1]), (1090, pg[1]), (1090, 790)], BLK, width=3)
    f.wire([(eg[0], eg[1]), (30, eg[1]), (30, 790)], BLK, width=4)
    f.gnd_bus(20, 1520, 790, "公共地 GND")

    f.note(40, 835, 740, [
        "① 先用万用表确认你的风速计是哪种输出：",
        "   不转时量 信号对 GND ≈ 3.3V，手转风杯时被拉低 → **集电极开路/NPN**，可直按上图接；",
        "   若量到 5V 或 12V 的电压脉冲 → **电压输出型**，必须分压或加光耦隔离才能进 GPIO，",
        "   否则会直接烧掉 ESP32 的 IO。",
        "② 风速计供电电压看铭牌（常见 12V/24V），**不要用 ESP32 的 3V3 去带**。",
        "③ 长线（>5m）建议：信号线用屏蔽线，屏蔽层只在 ESP32 这头接 GND，,",
        "   并在风速计那头加 100nF 对地。",
    ], title="接线前必看（很重要）", color="#b71c1c", fill="#ffebee")

    f.note(800, 835, 760, [
        "① 接线前：set windMode 0（先保开关量），接完再 set windMode 1，",
        "   状态页会多出 wind.hz / wind.mps / wind.pulses。",
        "② 标定：找个风稳的时候，看一眼 wind.hz（比如 12.3），",
        "   再看手机天气/附近气象站的风速（比如 9.0 m/s）；",
        "   windMpsPerHz = 9.0 ÷ 12.3 × 100 ≈ 73 → set windMpsPerHz 73。",
        "   多测两次取平均；标定完设 windStartMps / windStopMps / windEmergMps。",
    ], title="换上去后怎么调", color="#0d47a1", fill="#e3f2fd")
    f.save(os.path.join(out, "6-风速计(脉冲)"))


def main():
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "接线手册")
    print("输出目录:", out)
    fig_overview(out)
    fig_power(out)
    fig_motor(out)
    fig_safety(out)
    fig_sensors(out)
    fig_wind_pulse(out)
    print("完成")


if __name__ == "__main__":
    main()
