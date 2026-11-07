# -*- coding: utf-8 -*-
"""选题.py —— 课件工厂的「第 0 步」：选主题 + 自检。

为什么要有它：以前做课件是「想到一个题就开做」，等于闭门造车。
小红书同赛道跑量的题是有规律的（见 参考/爆款攻略.md），所以选题必须
**先有爆款证据 → 再出候选 → 再自检 → 最后才定稿**。

两种定稿方式（对应「人工筛选 / 全自动」）：
    --mode auto   全自动（默认）：按评分取第 1 名，不需要人盯着
    --mode pick   人工：弹一个本地小窗口，把候选（含依据/评分/自检）摆给人选，
                  点一下就定稿，窗口自动关闭 → 接着进课件生产

用法：
    python 工厂/选题.py                       # 出候选 + 自检 + 全自动定稿
    python 工厂/选题.py --mode pick           # 弹窗人工选
    python 工厂/选题.py --n 10 --age 6-8岁     # 10 个候选，偏向 6-8 岁
    python 工厂/选题.py --list                # 只列候选，不定稿、不建项目
    python 工厂/选题.py --go                  # 定稿后直接建脚手架（进生产流程）
    python 工厂/选题.py --use 3               # 直接选第 3 个（脚本/复现用）

产出：
    选题/<时间戳>/候选.json     全部候选 + 评分 + 自检 + 依据
    选题/<时间戳>/候选.md       人读版（也可直接发给用户看）
    选题/最新.json              软链式的「最近一次」副本
    选题结果.json               定稿记录（课题名/年龄/配方/为什么/依据），可回溯

不花钱：纯本地数据 + 规则评分，不调任何绘图/视觉模型。
"""
import argparse
import glob
import json
import math
import os
import re
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "参考", "爆款库", "index.json")
PICK_DIR = os.path.join(ROOT, "选题")
RESULT = os.path.join(ROOT, "选题结果.json")
AGGS = ["3-6岁", "4-6岁", "5-7岁", "6-8岁", "7-9岁"]


# ============================================================ 1. 爆款配方
# 与 参考/爆款攻略.md 第三节的 6 个配方一一对应；fit = AI 可生成性（15 分制）
PRESETS = {
    "marker_flat": dict(
        cn="马克笔平涂撞色", fit=15, material="马克笔+黑勾线笔+白高光笔",
        formula="实物→几何化简形→粗黑勾边平涂→内部填花纹→白高光提亮",
        points=["粗黑实线描边 + 高饱和平涂（无渐变、无莫兰迪）",
                "主体内部填 2 种以上装饰语汇（波点/条纹/网格/螺旋）",
                "白色高光点提亮 2~3 处，撞色用 3 个主色"]),
    "collage_mixed": dict(
        cn="综合材料拓印拼贴", fit=11, material="真树叶/保鲜袋/海绵印章+水粉",
        formula="自然实物→垫纸拓印留肌理→同形多色排成一列→剪贴高光点睛",
        points=["拓印颗粒肌理要像「真做过」，不要画成插画",
                "同一母题重复排成一行/一圈，形成节奏",
                "留一处剪贴纸边和轻微投影，制造真实感"]),
    "darkline_doodle": dict(
        cn="黑白线描×单色底", fit=14, material="黑卡纸/单色圆底+白高光笔",
        formula="实物→几何化轮廓→黑白线描+点线面填满→单色圆底衬色→粗黑标题",
        points=["全图黑白线描，只用点/线/面纹理填满",
                "加一个暖色点缀打破单调",
                "单色圆底衬在主体后方，形成强反差"]),
    "gradient_dot": dict(
        cn="点彩晕染梦幻", fit=13, material="水粉/丙烯+棉签+海绵+旧牙刷",
        formula="名画主题→渐变晕染铺底→圆头笔点画主体→亮色小花点睛→弹洒星光",
        points=["蓝绿渐变晕染铺底，不留纯白",
                "主体用点画法，笔触可见、不勾死线",
                "旧牙刷弹洒白色星点，边缘要散"]),
    "clay_relief": dict(
        cn="黏土半立体手工", fit=10, material="超轻黏土+彩卡纸+马克笔",
        formula="主题→卡纸拼贴底→黏土搓球堆叠体积→平涂五官+粉腮→实物道具",
        points=["黏土要有真实体积、真实投影",
                "五官马克笔平涂，脸颊加粉色腮红",
                "边缘保留一点手工的不完美，别太像 3D 渲染"]),
    "chalk_board": dict(
        cn="黑板粉笔", fit=12, material="黑板绿底+白色/彩色粉笔",
        formula="深色底→白线描主体→同类实物简形排列→点线面纹理→角落手写主题词",
        points=["黑板绿底 + 白粉笔单线勾勒",
                "粉末感、轻微飞白，不要锐利矢量边",
                "角落手写主题词（版式层再补印刷体标题）"]),
}

# ============================================================ 2. 题材库
# (类别, 复杂度 1简单/2中/3难)。只放「AI 能稳定画出来 + 4~9 岁能上手」的题材。
THEMES = {
    # 动物
    "小兔子": ("动物", 1), "小猫": ("动物", 1), "小狗": ("动物", 1), "小鸟": ("动物", 1),
    "小鱼": ("动物", 1), "蝴蝶": ("动物", 1), "小刺猬": ("动物", 2), "小松鼠": ("动物", 2),
    "大熊猫": ("动物", 2), "大象": ("动物", 1), "长颈鹿": ("动物", 1), "河马": ("动物", 2),
    "水母": ("动物", 2), "螃蟹": ("动物", 1), "蜗牛": ("动物", 1), "蚂蚁": ("动物", 2),
    "毛毛虫": ("动物", 1), "瓢虫": ("动物", 1), "甲虫": ("动物", 2), "青蛙": ("动物", 1),
    "鸭子": ("动物", 1), "企鹅": ("动物", 1), "鲸鱼": ("动物", 2), "猫头鹰": ("动物", 2),
    "章鱼": ("动物", 1), "海马": ("动物", 2), "狐狸": ("动物", 2), "小羊": ("动物", 1),
    "小鸡": ("动物", 1), "恐龙": ("动物", 2), "狮子": ("动物", 2), "老虎": ("动物", 2),
    # 食物
    "西瓜": ("食物", 1), "胡萝卜": ("食物", 1), "西兰花": ("食物", 2), "玉米": ("食物", 1),
    "南瓜": ("食物", 1), "草莓": ("食物", 1), "葡萄": ("食物", 1), "柠檬": ("食物", 2),
    "蘑菇": ("食物", 1), "松果": ("食物", 2), "爆米花": ("食物", 2), "糖葫芦": ("食物", 2),
    "冰淇淋": ("食物", 1), "蛋糕": ("食物", 1), "麦穗": ("食物", 3), "稻草人": ("食物", 3),
    # 自然
    "树叶": ("自然", 1), "枫叶": ("自然", 1), "雪花": ("自然", 1), "云": ("自然", 1),
    "彩虹": ("自然", 1), "向日葵": ("自然", 1), "蒲公英": ("自然", 2), "绣球花": ("自然", 3),
    "莲花": ("自然", 3), "仙人掌": ("自然", 1), "竹子": ("自然", 2), "笋": ("自然", 1),
    "雪山": ("自然", 3), "海浪": ("自然", 3), "星星": ("自然", 1), "月亮": ("自然", 1),
    # 器物 / 场景
    "雨伞": ("器物", 1), "风筝": ("器物", 2), "气球": ("器物", 1), "小房子": ("器物", 2),
    "灯塔": ("器物", 3), "小船": ("器物", 2), "花瓶": ("器物", 2), "青花瓷": ("器物", 3),
    "茶壶": ("器物", 2), "纸箱": ("器物", 1), "蛋糕盘": ("器物", 2), "蒲扇": ("器物", 2),
    "路灯": ("器物", 2), "小推车": ("器物", 2), "帐篷": ("器物", 2), "闹钟": ("器物", 2),
    # 节令
    "春天": ("节令", 2), "夏天": ("节令", 2), "秋天": ("节令", 2), "冬天": ("节令", 2),
    "新年": ("节令", 2), "万圣节": ("节令", 2), "圣诞": ("节令", 2), "中秋": ("节令", 3),
}

# (模板, 情境, 适用类别, 复杂度加成)  —— {t}=题材
SCENES = [
    ("{t}出逃", "出逃", {"食物", "器物", "动物"}, 0),
    ("{t}派对", "派对", {"食物", "动物", "自然"}, 0),
    ("会翻跟头的{t}", "翻跟头", {"食物", "动物", "器物"}, 1),
    ("会变形的{t}", "变形", {"自然", "器物"}, 1),
    ("{t}去旅行", "旅行", {"动物", "食物", "器物"}, 0),
    ("{t}搬家", "搬家", {"动物", "食物"}, 0),
    ("{t}藏在哪里", "藏", {"动物", "食物"}, 1),
    ("{t}洗澡", "洗澡", {"动物", "食物"}, 0),
    ("小{t}背果子", "背果子", {"动物"}, 1),
    ("路灯下的{t}", "路灯下", {"动物", "器物"}, 2),
    ("{t}的秋天", "秋天", {"自然", "食物", "器物"}, 1),
    ("{t}的舞会", "舞会", {"自然", "食物", "动物"}, 1),
    ("{t}大冒险", "大冒险", {"动物", "器物"}, 1),
    ("{t}排排队", "排队", {"食物", "动物", "器物"}, 0),
    ("{t}开花啦", "开花", {"自然", "食物"}, 0),
    ("{t}晒太阳", "晒太阳", {"动物", "食物"}, 0),
    ("{t}的雨伞", "雨", {"动物", "食物", "自然"}, 1),
    ("{t}杂技团", "杂技", {"动物", "食物", "器物"}, 2),
]

# 材料 → 配方（爆款攻略里验证过的组合，只写有据可依的）
MATERIAL_HINT = {
    "树叶": "collage_mixed", "枫叶": "collage_mixed", "绣球花": "collage_mixed",
    "蒲公英": "collage_mixed", "雪花": "collage_mixed", "莲花": "gradient_dot",
    "雪山": "gradient_dot", "海浪": "gradient_dot", "云": "gradient_dot",
    "彩虹": "gradient_dot", "星星": "darkline_doodle", "月亮": "darkline_doodle",
    "青花瓷": "darkline_doodle", "花瓶": "darkline_doodle", "甲虫": "darkline_doodle",
    "水母": "collage_mixed", "章鱼": "collage_mixed", "小羊": "clay_relief",
    "蘑菇": "clay_relief", "仙人掌": "clay_relief", "南瓜": "clay_relief",
    "万圣节": "chalk_board", "圣诞": "chalk_board", "新年": "chalk_board",
    "中秋": "chalk_board", "灯塔": "chalk_board", "路灯": "chalk_board",
    "西瓜": "marker_flat", "胡萝卜": "marker_flat", "西兰花": "marker_flat",
    # 手工/拓印类器材本身就是材料，走综合材料或黏土
    "蛋糕盘": "collage_mixed", "蒲扇": "collage_mixed", "纸箱": "collage_mixed",
    "风筝": "collage_mixed", "气球": "marker_flat", "雨伞": "marker_flat",
    "毛毛虫": "collage_mixed", "小鸡": "clay_relief", "小熊": "clay_relief",
    "爆米花": "collage_mixed", "松果": "collage_mixed", "糖果": "marker_flat",
}

# 没有显式映射时，按类别轮换配方 —— 避免所有候选都变「马克笔平涂」。
# 列表里重复的项 = 更高的出现权重（例如动物大多还是马克笔，少数黏土）
CAT_PRESET = {
    "动物": ["marker_flat", "marker_flat", "clay_relief"],
    "食物": ["marker_flat", "marker_flat", "collage_mixed"],
    "自然": ["collage_mixed", "gradient_dot", "darkline_doodle"],
    "器物": ["marker_flat", "darkline_doodle", "marker_flat"],
    "节令": ["collage_mixed", "chalk_board", "collage_mixed"],
}

# 铁律（参考/爆款攻略.md 第二节），候选必须至少命中 2 条
IRON_RULES = [
    ("实物→几何化简形", "题材是真实存在的物/景，能先看实物再简化"),
    ("粗黑实线+平涂+白高光", "画面用粗黑勾线、平涂撞色、白色高光"),
    ("高饱和撞色·白卡底", "白卡纸打底 + 2~3 个高饱和主色撞色"),
    ("拟人化", "两个大圆眼+表情+小手小脚+一件道具"),
    ("2种以上装饰语汇", "波点/条纹/网格/放射线/螺旋/点线面填充"),
    ("一处意料之外", "剖面房间/立体翘起/可动纸条/超现实巨物"),
    ("图上加字", "手写标题/英文副标/红印章（版式层补）"),
]


# 题材词后面跟这些字时，说明它是更长的词（「蛋糕盘」不是「蛋糕」），不算命中证据
STOP_SUFFIX = set("盘盒纸杯托袋皮夹板刀片瓶罐笼箱桶勺叉")


def theme_hit(theme, title):
    """题材词是否真的作为这个题材出现在标题里。"""
    i = title.find(theme)
    if i < 0:
        return False
    j = i + len(theme)
    if j < len(title) and title[j] in STOP_SUFFIX:
        return False
    return True


# ============================================================ 3. 数据加载
def load_library():
    if not os.path.exists(LIB):
        sys.exit("没有爆款库：%s\n先跑 `python 挖爆款.py` 抓一轮（约 5 分钟），再来选题。" % LIB)
    with open(LIB, encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for x in data:
        t = (x.get("title") or "").strip()
        if not t:
            continue
        out.append({
            "title": t,
            "likes": int(x.get("likes") or 0),
            "collects": int(x.get("collects") or 0),
            "kw": x.get("kw") or "",
        })
    out.sort(key=lambda z: -z["likes"])
    return out


def load_done():
    """已做过的课题名（项目目录 + 发布台账），选题不能重复。"""
    names = []
    for d in glob.glob(os.path.join(ROOT, "项目", "*")):
        if not os.path.isdir(d):
            continue
        b = os.path.basename(d).replace("《", "").replace("》", "")
        b = re.sub(r"-\d+-\d+岁$", "", b)
        names.append(b)
    led = os.path.join(ROOT, "发布台账.json")
    if os.path.exists(led):
        try:
            with open(led, encoding="utf-8") as f:
                for k in (json.load(f).get("decks") or {}):
                    names.append(re.sub(r"-\d+-\d+岁$", "", k))
        except Exception:
            pass
    # ★ 必须过滤空串：`"" in theme` 恒为 True，会让「题材做过」判定全线误判
    names = [x.strip() for x in names if x.strip()]
    return sorted(set(names))


def bigrams(s):
    s = re.sub(r"[《》\s\-—]", "", s)
    if len(s) < 2:
        return {s}
    return {s[i:i + 2] for i in range(len(s) - 1)}


def similar(a, b):
    A, B = bigrams(a), bigrams(b)
    if not A or not B:
        return 0.0
    return len(A & B) / max(1, len(A | B))


def age_for(complexity, prefer=None, offset=0):
    """题材复杂度 → 年龄段。用户的「不拘泥于某个年龄段」在这里体现：
    简单题给 4-6，中题给 5-7/6-8，难题给 6-8/7-9，不是全部卡在 4-6 岁。"""
    table = {1: ["4-6岁", "3-6岁"], 2: ["4-6岁", "6-8岁"], 3: ["6-8岁", "7-9岁"]}
    complexity = max(1, min(3, complexity))
    opts = table.get(complexity, ["4-6岁"])
    # --age 只是「偏好」：一半候选顺着它，另一半按题材自然难度铺开
    if prefer and prefer in AGGS and offset % 2 == 0:
        return prefer
    return opts[offset % len(opts)]


# ============================================================ 4. 候选生成
def build_candidates(n=8, prefer_age=None, exclude_na=False):
    lib = load_library()
    done = load_done()
    hits = {}          # 题材 -> [lib entries]
    for kw in THEMES:
        hs = [x for x in lib if theme_hit(kw, x["title"])]
        if hs:
            hits[kw] = hs

    cands, seen = [], set()
    dup_filtered = 0
    for theme, (cat, cx) in THEMES.items():
        if theme not in hits:
            continue                     # 没有爆款证据的题材不生成（宁缺勿滥）
        ev = sorted(hits[theme], key=lambda z: -z["likes"])[:3]
        # 这个题材是不是已经做过（做过再出同题就是重复劳动）
        theme_done = any(theme in d or d in theme for d in done)
        for s_idx, (tpl, scene, cats, add) in enumerate(SCENES):
            if cat not in cats:
                continue
            name = tpl.format(t=theme)
            name = re.sub(r"小(小)", r"\1", name)
            if len(name) < 3 or len(name) > 12:
                continue
            if name in seen or name in done:
                dup_filtered += 1
                continue
            # 与已做课题、与爆款标题原件 的相似度
            simmax = max([similar(name, d) for d in done] or [0.0])
            # 爆款标题里已经用过这个题目（如「3-6岁：胡萝卜出逃」）→ 直接跳过，换个情境
            # （学套路可以，拄题目不行；跳过之后同题材会自然落到下一个情境上）
            exact_boom = next((x for x in lib if name in x["title"]), None)
            if exact_boom:
                dup_filtered += 1
                continue
            if simmax >= 0.5:
                dup_filtered += 1
                continue
            preset = (MATERIAL_HINT.get(theme) or MATERIAL_HINT.get(scene)
                      or CAT_PRESET.get(cat, ["marker_flat"])[s_idx % 3])
            cxc = min(3, cx + add)
            if add >= 2 and preset == "marker_flat":
                preset = "darkline_doodle"
            cands.append(score_candidate(name, theme, cat, cxc, scene, ev, preset,
                                         simmax, exact_boom, prefer_age,
                                         offset=s_idx, theme_done=theme_done))
            seen.add(name)

    cands.sort(key=lambda c: -c["score"])
    if not cands:
        sys.exit("没生成出候选：爆款库里没有命中题材库的标题。先跑 `python 挖爆款.py`。")

    # 挑选：分数优先，但强制多样性 ——
    # ① 同一题材最多 1 个（否则 8 个候选全是「西兰花」，这是实际踩到的）
    # ② 同一类别不超过一半　③ 年龄段不挤死（用户明确要求不拘泥年龄段）
    picked = []
    plans = [
        (1, max(2, n // 2), max(2, int(n * 0.6))),
        (2, max(3, int(n * 0.7)), n),
        (9, n, n),
    ]
    for theme_cap, cat_cap, age_cap in plans:
        if len(picked) >= n:
            break
        per_theme, per_cat, per_age, per_scene = {}, {}, {}, {}
        for c in picked:
            per_theme[c["theme"]] = per_theme.get(c["theme"], 0) + 1
            per_cat[c["category"]] = per_cat.get(c["category"], 0) + 1
            per_age[c["age"]] = per_age.get(c["age"], 0) + 1
            per_scene[c["scene"]] = per_scene.get(c["scene"], 0) + 1
        for c in cands:
            if len(picked) >= n:
                break
            if c in picked:
                continue
            if per_theme.get(c["theme"], 0) >= theme_cap:
                continue
            # 「蛋糕」与「蛋糕盘」这种题材词重叠，也算重复
            if any(c["theme"] in p or p in c["theme"] for p in per_theme):
                continue
            if per_cat.get(c["category"], 0) >= cat_cap:
                continue
            if per_age.get(c["age"], 0) >= age_cap:
                continue
            # 同一情境最多 2 个（别让 8 个候选里 5 个都是「出逃」）
            if per_scene.get(c["scene"], 0) >= 2:
                continue
            picked.append(c)
            per_theme[c["theme"]] = per_theme.get(c["theme"], 0) + 1
            per_cat[c["category"]] = per_cat.get(c["category"], 0) + 1
            per_age[c["age"]] = per_age.get(c["age"], 0) + 1
            per_scene[c["scene"]] = per_scene.get(c["scene"], 0) + 1
    # 年龄还是单一？从后面找一个不同年龄的换掉末位
    if len(picked) >= 4 and len(set(c["age"] for c in picked)) < 2:
        for c in cands:
            if c not in picked and c["age"] != picked[0]["age"]:
                picked[-1] = c
                break

    picked.sort(key=lambda c: -c["score"])
    out = picked[:n]
    for i, c in enumerate(out, 1):
        c["id"] = i
        c["dup_filtered"] = dup_filtered
    return out, len(lib), done


def score_candidate(name, theme, cat, cx, scene, ev, preset, simmax, exact_boom,
                    prefer_age, offset=0, theme_done=False):
    P = PRESETS[preset]
    top = ev[0]
    # ① 赛道证据 40：最高赞取对数归一（10 万赞 ≈ 满分）+ 收藏率加成
    #    收藏/点赞 高 = 观众想「学着做」，这正是卖课件要的信号；纯观赏型笔记收藏率极低
    like_score = 40.0 * math.log10(1 + top["likes"]) / math.log10(100001)
    learn = 8.0 * min(1.0, (top["collects"] / max(1, top["likes"])) / 0.6)
    heat = round(min(40.0, like_score * 0.8 + learn + (4.0 if exact_boom else 0)), 1)
    # ② 新鲜度 20：题材做过就别再做，与已做题目越像分越低
    fresh = 20.0 if not theme_done else 8.0
    fresh = round(fresh * (1.0 - min(0.6, simmax)), 1)
    # ③ 配方可生成性 15
    fit = P["fit"]
    # ④ 卖点 15：拟人(情境动词) + 装饰语汇 + 意料之外
    sell = 5.0
    sell += 4.0 if scene in ("出逃", "派对", "翻跟头", "变形", "旅行", "大冒险", "舞会", "杂技") else 2.0
    sell += 3.0 if cx <= 2 else 1.0          # 简单题更好出效果
    sell += 3.0 if preset != "marker_flat" else 2.0
    sell = round(min(15.0, sell), 1)
    # ⑤ 年龄适配 10
    age = age_for(1 if cx <= 1 else (2 if cx == 2 else 3), prefer_age, offset)
    age_ok = 10.0 if (prefer_age and age == prefer_age) else 8.0

    score = round(heat + fresh + fit + sell + age_ok, 1)
    cx_cn = {1: "简单", 2: "适中", 3: "偏难"}[min(3, max(1, cx))]
    ctr = top["collects"] / max(1, top["likes"])
    why = ("「%s」在同赛道最高 %d 赞 / %d 藏（收藏率 %.0f%%%s）；配方「%s」+ 情境「%s」，难度%s，%s"
           % (theme, top["likes"], top["collects"], ctr * 100,
              "，观众想学着做" if ctr >= 0.5 else "",
              P["cn"], scene, cx_cn,
              "AI 出图稳定" if P["fit"] >= 13 else "要加「像真做过」提示"))
    return {
        "name": name, "theme": theme, "category": cat, "age": age,
        "scene": scene,
        "preset": preset, "preset_cn": P["cn"], "material": P["material"],
        "formula": P["formula"], "points": P["points"],
        "difficulty": cx_cn, "theme_done": theme_done,
        "why": why, "score": score,
        "breakdown": {"赛道证据": heat, "新鲜度": fresh, "配方适配": fit,
                      "卖点": sell, "年龄": age_ok},
        "evidence": [{"title": e["title"][:40], "likes": e["likes"],
                      "collects": e["collects"]} for e in ev],
        "exact_boom": bool(exact_boom),
        "boom_title": (exact_boom or {}).get("title", "")[:30],
    }


# ============================================================ 5. 自检
def selfcheck(c, done):
    """返回 [(name, level, detail)]。FAIL = 不能进下一步，WARN = 能做但要留意。"""
    out = []
    # ① 有据可依：必须引到真实爆款，最高赞太低说明赛道没验证过
    top = c["evidence"][0]["likes"] if c["evidence"] else 0
    if top >= 1000:
        out.append(("爆款有据", "PASS", "最高 %d 赞" % top))
    elif top >= 300:
        out.append(("爆款有据", "WARN", "最高仅 %d 赞，赛道验证偏弱" % top))
    else:
        out.append(("爆款有据", "FAIL", "最高 %d 赞，等于没有证据" % top))

    # ② 不与已做课题重复
    sim = max([similar(c["name"], d) for d in done] or [0.0])
    if sim < 0.34:
        out.append(("不重复", "PASS", "与已做 %d 套无近题" % len(done)))
    elif sim < 0.5:
        out.append(("不重复", "WARN", "与已做课题相似度 %.2f" % sim))
    else:
        out.append(("不重复", "FAIL", "与已做课题撞车（%.2f）" % sim))

    # ③ 不照抄爆款标题（可以学套路，不能抄题目）
    if c["exact_boom"]:
        out.append(("非照抄", "WARN", "爆款里已有同题《%s》，建议换情境" % c.get("boom_title", "…")))
    else:
        out.append(("非照抄", "PASS", "题目是新的组合"))

    # ④ 名字长度（封面/文件夹/标题都用它）
    if 4 <= len(c["name"]) <= 10:
        out.append(("题目长度", "PASS", "%d 字" % len(c["name"])))
    else:
        out.append(("题目长度", "WARN", "%d 字，封面排版可能挤" % len(c["name"])))

    # ⑤ 配方可生成性（是不是需要真材料实拍才像）
    if c["preset"] in ("marker_flat", "darkline_doodle", "gradient_dot"):
        out.append(("可出图", "PASS", c["preset_cn"] + "，AI 稳定"))
    else:
        out.append(("可出图", "WARN", c["preset_cn"] + "，要加「像真做过」提示"))

    # ⑥ 年龄合法 + 难度匹配
    if c["age"] in AGGS:
        out.append(("年龄段", "PASS", c["age"] + "（" + c.get("difficulty", "适中") + "）"))
    else:
        out.append(("年龄段", "FAIL", "非法年龄 %s" % c["age"]))

    # ⑦ 铁律覆盖（按配方与情境推断，不假装能看图判断）
    hit = []
    if c["theme"] in THEMES:
        hit.append("实物→几何化简形")
    hit.append("粗黑实线+平涂+白高光")
    hit.append("高饱和撞色·白卡底")
    if c["preset"] != "marker_flat" or any(w in c["name"] for w in ("出逃", "派对", "洗澡", "背", "藏", "晒")):
        hit.append("拟人化")
    hit.append("2种以上装饰语汇")
    if c["preset"] in ("collage_mixed", "clay_relief", "chalk_board"):
        hit.append("一处意料之外")
    if len(hit) >= 4:
        out.append(("爆款铁律", "PASS", "命中 %d/7 条" % len(hit)))
    elif len(hit) >= 2:
        out.append(("爆款铁律", "WARN", "只命中 %d/7 条" % len(hit)))
    else:
        out.append(("爆款铁律", "FAIL", "命中不足"))
    c["iron_rules"] = hit
    c["checks"] = [{"name": a, "level": b, "detail": d} for a, b, d in out]
    c["verdict"] = "FAIL" if any(x[1] == "FAIL" for x in out) else (
        "WARN" if any(x[1] == "WARN" for x in out) else "PASS")
    return c


# ============================================================ 6. 落盘
def save_candidates(cands, libn, done, n_dup):
    ts = time.strftime("%Y%m%d_%H%M%S")
    d = os.path.join(PICK_DIR, ts)
    os.makedirs(d, exist_ok=True)
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "library_n": libn, "done_n": len(done), "dup_filtered": n_dup,
        "candidates": cands,
    }
    for p in (os.path.join(d, "候选.json"), os.path.join(PICK_DIR, "最新.json")):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    md = ["# 选题候选 · %s" % payload["generated_at"], "",
          "爆款库 %d 条 / 已做 %d 套 / 本次去重 %d 个" % (libn, len(done), n_dup), ""]
    for c in cands:
        md.append("## %d. 《%s》 · %s · %s · %.1f 分" % (
            c["id"], c["name"], c["age"], c["preset_cn"], c["score"]))
        md.append("- 为什么能卖：" + c["why"])
        md.append("- 画面公式：" + c["formula"])
        md.append("- 出图要点：" + "；".join(c["points"]))
        md.append("- 爆款依据：" + " / ".join("《%s》%d赞%d藏" % (e["title"], e["likes"], e["collects"])
                                          for e in c["evidence"]))
        md.append("- 自检：" + "　".join("%s%s:%s" % ("✕" if x["level"] == "FAIL" else
                                                   "!" if x["level"] == "WARN" else "✓",
                                                   x["name"], x["detail"]) for x in c["checks"]))
        md.append("- 评分拆解：" + " / ".join("%s %.1f" % kv for kv in c["breakdown"].items()))
        md.append("")
    with open(os.path.join(d, "候选.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    return d, payload


def write_result(c, mode, how, extra=None):
    rec = {
        "picked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": mode, "how": how,
        "name": c["name"], "age": c["age"], "preset": c["preset"],
        "preset_cn": c["preset_cn"], "score": c["score"],
        "why": c["why"], "formula": c["formula"], "points": c["points"],
        "evidence": c["evidence"], "checks": c["checks"], "iron_rules": c["iron_rules"],
        "breakdown": c["breakdown"],
    }
    if extra:
        rec.update(extra)
    hist = []
    if os.path.exists(RESULT):
        try:
            with open(RESULT, encoding="utf-8") as f:
                old = json.load(f)
            hist = old.get("history") or ([] if "name" in old else [old])
        except Exception:
            hist = []
    hist.append(rec)
    with open(RESULT, "w", encoding="utf-8") as f:
        json.dump({"latest": rec, "history": hist[-50:]}, f, ensure_ascii=False, indent=2)
    return rec


# ============================================================ 7. 人工选择（本地弹窗）
def open_browser(url):
    """优先用 Edge/Chrome 的 --app 模式：无地址栏的小窗，window.close() 能真正关掉。
    找不到就用默认浏览器开标签页（关不掉，但页面会提示手动关）。"""
    import subprocess
    if os.environ.get("PICKUI_NO_BROWSER") == "1":
        return "no-browser"
    for exe in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"):
        if not os.path.exists(exe):
            continue
        prof = os.path.join(PICK_DIR, ".pick_profile")
        os.makedirs(prof, exist_ok=True)
        try:
            subprocess.Popen([exe, "--app=" + url, "--window-size=1180,900",
                              "--window-position=120,60", "--user-data-dir=" + prof,
                              "--no-first-run", "--no-default-browser-check"],
                             close_fds=True)
            return "app:" + os.path.basename(exe)
        except Exception:
            continue
    import webbrowser
    webbrowser.open(url)
    return "tab"


def serve_pick(cands, payload_meta, port=None, timeout=900):
    """起一个小服务给人工选。选完写回结果并退出。"""
    web = os.path.join(ROOT, "工厂", "web", "pick.html")
    state = {"choice": None, "t0": time.time(), "stop": False}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            b = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            try:
                self.wfile.write(b)
            except Exception:
                pass

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            if u.path in ("/", "/index.html"):
                with open(web, "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            if u.path == "/api/candidates":
                return self._send(200, {"candidates": cands, "library_n": payload_meta["library_n"],
                                        "dup_filtered": payload_meta.get("dup_filtered", 0)})
            return self._send(404, {"ok": False})

        def do_POST(self):
            u = urllib.parse.urlparse(self.path)
            if u.path != "/api/pick":
                return self._send(404, {"ok": False})
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                body = {}
            idx = int(body.get("id") or 1)
            c = next((x for x in cands if x["id"] == idx), cands[0])
            state["choice"] = (c, "auto-button" if body.get("auto") else "human-click")
            self._send(200, {"ok": True})

    # 找空端口（别撞审图台 8777）
    base = int(port or os.environ.get("PICKUI_PORT") or 8781)
    srv = None
    for p in range(base, base + 12):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", p), H)
            port = p
            break
        except OSError:
            continue
    if srv is None:
        sys.exit("找不到空闲端口启动选题台（试过 %d~%d）" % (base, base + 11))

    url = "http://127.0.0.1:%d" % port
    print("\n[选题台] %s  ← 在弹窗里点一个课题（超时 %d 秒自动回退全自动）" % (url, timeout))
    how = open_browser(url)
    srv.timeout = 1
    t0 = time.time()
    # 不用 serve_forever：每轮只处理一个连接（ThreadingHTTPServer 会把长请求丢线程），
    # 这样「收到选择」能立刻跳出循环，而不是等 shutdown 事件。
    while time.time() - t0 < timeout and not state["choice"]:
        srv.handle_request()
    srv.server_close()

    if state["choice"]:
        c, human = state["choice"]
        print("[选题台] 已选择：%s（%s）" % (c["name"], human))
        return c, human
    print("[选题台] 等太久没人点，回退全自动：%s" % cands[0]["name"])
    return cands[0], "timeout-fallback"


# ============================================================ 8. 建脚手架
def make_project(c):
    import subprocess
    py = sys.executable
    npp = os.path.join(ROOT, "工厂", "new_project.py")
    r = subprocess.run([py, npp, c["name"], "--age", c["age"]],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((r.stdout or "").strip())
    if r.returncode != 0:
        print((r.stderr or "").strip())
        return None
    d = os.path.join(ROOT, "项目", "%s-%s" % (c["name"], c["age"]))
    pj = os.path.join(d, "project.json")
    if not os.path.exists(pj):
        return None
    with open(pj, encoding="utf-8") as f:
        data = json.load(f)
    rec = json.load(open(RESULT, encoding="utf-8")).get("latest") or {}
    data.setdefault("meta", {})["selection"] = rec
    data.setdefault("common", {})["style_preset"] = c["preset"]
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("已把选题记录写进 project.json（meta.selection / common.style_preset=%s）" % c["preset"])
    return pj


# ============================================================ 9. main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8, help="候选数量（默认 8）")
    ap.add_argument("--age", default="", help="偏好年龄段：3-6岁/4-6岁/5-7岁/6-8岁/7-9岁")
    ap.add_argument("--mode", default="auto", choices=["auto", "pick"],
                    help="auto=全自动（默认） pick=弹窗人工选")
    ap.add_argument("--use", type=int, default=0, help="直接选第 N 个候选（1 起）")
    ap.add_argument("--list", action="store_true", help="只列候选，不定稿")
    ap.add_argument("--go", action="store_true", help="定稿后直接建项目脚手架（进生产流程）")
    ap.add_argument("--timeout", type=int, default=900, help="人工选择超时秒数")
    ap.add_argument("--port", type=int, default=0, help="选题台端口")
    ap.add_argument("--json", default="", help="把候选结果另存一份 JSON")
    a = ap.parse_args()

    prefer = a.age if a.age in AGGS else ""
    if a.age and not prefer:
        print("！年龄 '%s' 不在 %s 里，已忽略" % (a.age, "/".join(AGGS)))

    print("== 1/3 读爆款库 + 生成候选 ==")
    cands, libn, done = build_candidates(a.n, prefer)
    cands = [selfcheck(c, done) for c in cands]
    # 自检后重排：PASS → WARN → FAIL（分数仍是主序），让第一张牌就是能用的
    rank = {"PASS": 0, "WARN": 1, "FAIL": 2}
    cands.sort(key=lambda c: (rank.get(c["verdict"], 2), -c["score"]))
    for i, c in enumerate(cands, 1):
        c["id"] = i
    n_dup = cands[0]["dup_filtered"] if cands else 0
    d, payload = save_candidates(cands, libn, done, n_dup)

    print("   爆款库 %d 条 / 已做 %d 套 / 去重 %d 个 → 候选 %d 个"
          % (libn, len(done), n_dup, len(cands)))
    print("== 2/3 自检 ==")
    for c in cands:
        bad = [x for x in c["checks"] if x["level"] != "PASS"]
        print("  %2d. %-14s %-7s %-10s %5.1f分  %s  %s" % (
            c["id"], "《%s》" % c["name"], c["age"], c["preset_cn"], c["score"],
            c["verdict"], ("；".join("%s:%s" % (x["name"], x["detail"]) for x in bad) or "全部通过")))
    print("   明细 → %s" % os.path.join(d, "候选.md"))

    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print("   JSON → %s" % a.json)

    if a.list:
        return 0

    print("== 3/3 定稿 ==")
    if a.use:
        if not (1 <= a.use <= len(cands)):
            sys.exit("--use %d 超出范围（1~%d）" % (a.use, len(cands)))
        c = cands[a.use - 1]
        if c["verdict"] == "FAIL":
            print("   ！第 %d 个自检 FAIL，改用第一个通过的" % a.use)
            c = next(x for x in cands if x["verdict"] != "FAIL")
            how = "use-%d-fallback" % a.use
        else:
            how = "use-%d" % a.use
    elif a.mode == "pick":
        ok = [x for x in cands if x["verdict"] != "FAIL"] or cands
        c, how = serve_pick(ok, payload, a.port or None, a.timeout)
    else:
        c = next((x for x in cands if x["verdict"] != "FAIL"), cands[0])
        how = "auto-top1"

    rec = write_result(c, a.mode, how, {"candidate_dir": os.path.basename(d)})
    print("   定稿：《%s》 · %s · %s · %.1f 分（%s）"
          % (c["name"], c["age"], c["preset_cn"], c["score"], how))
    print("   记录 → %s" % RESULT)

    if a.go:
        print("\n== 进入课件生产流程 ==")
        pj = make_project(c)
        if pj:
            print("\n下一步（先报参数再花钱）：")
            print("  python 工厂/pipeline.py \"%s\" --list" % os.path.relpath(pj, ROOT))
            print("  python 工厂/pipeline.py \"%s\" --batch chain" % os.path.relpath(pj, ROOT))
    else:
        print("\n要继续做课件就加 --go，或手动：")
        print("  python 工厂/new_project.py \"%s\" --age %s" % (c["name"], c["age"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
