# -*- coding: utf-8 -*-
"""看爆款.py —— 让视觉模型把爆款封面「拆解成结构化标签」，产出风格库。

当前对话模型看不到图，所以走外部视觉模型（复用 工厂/photos.py 的 provider 配置）。
每张图输出一段 JSON 标签 → 存 tags.json → 本地聚合成 <汇总.md>。

用法：
    python 看爆款.py                 # 全部封面（跳过已看过的）
    python 看爆款.py --imgs 3        # 每篇看 3 张（封面 + 前 2 张）
    python 看爆款.py --top 20        # 只分析榜单前 20
    python 看爆款.py --sheet         # 额外做「9 图联看」找共性

成本：~¥0.0015/张，40 篇 × 3 张 ≈ ¥0.2
"""
import argparse
import base64
import glob
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "工厂"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LIB = os.path.join(HERE, "参考", "爆款库")

PROMPT = """这是一张小红书「少儿美术 / 创意美术课件」爆款笔记的配图（通常是范画成品或步骤图）。
请拆解它的**可复制的视觉套路**，只输出一个 JSON 对象，不要任何解释、不要 markdown 代码块：

{
  "画面主体": "20字内，画的是什么",
  "画风": "从这些里选并补充：扁平卡通风/写实插画/涂鸦手绘/拼贴/水墨/厚涂/线描/拓印/综合材料/水粉/半立体手工",
  "笔触质感": "如：粗黑实线描边+平涂、铅笔淡彩、干刷肌理、指印点画…",
  "材料": ["马克笔","彩卡纸","黏土","水粉","棉签","树叶","海绵印章","保鲜袋","吸管"等，真实推断],
  "配色": "主色3个以内 + 一句风格判断（高饱和撞色/莫兰迪低饱和/同色系渐变/黑底高亮…）",
  "构图": "如：满构图居中、大留白、S形、三分法、留白+呼应",
  "背景处理": "如：纯色卡纸、渐变晕染、色块拼贴、无背景、文字环绕",
  "文字元素": "有/无；有的话描述字体感觉和内容位置",
  "画面里有几个主体元素": "数字",
  "复杂度给4-6岁小孩": "简单/适中/偏难 + 一句理由",
  "最抓眼的那一点": "一眼让人想点进来的是什么",
  "可复用创作公式": "一句能直接套到别的课题上的公式，如『实物照片→几何化简形→厚涂+高光→贴一个可动小机关』"
}"""


def vcfg():
    p = os.path.join(os.path.expanduser("~"), ".pi", "agent", "models.json")
    d = json.load(open(p, encoding="utf-8"))
    for _n, pr in (d.get("providers") or {}).items():
        if not (pr.get("apiKey") and pr.get("baseUrl")):
            continue
        vis = [m["id"] for m in (pr.get("models") or []) if "image" in (m.get("input") or [])]
        if vis:
            return pr["baseUrl"].rstrip("/"), pr["apiKey"], os.environ.get("VISION_MODEL") or vis[0]
    return None


UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36")


def ask(cfg, images, prompt, timeout=180):
    """images: [本地路径]；一张或多张一起问"""
    base, key, model = cfg
    content = [{"type": "text", "text": prompt}]
    for pth in images:
        from PIL import Image
        im = Image.open(pth).convert("RGB")
        im.thumbnail((768, 768))
        b = io.BytesIO()
        im.save(b, "JPEG", quality=80)
        content.append({"type": "image_url", "image_url": {
            "url": "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()}})
    body = json.dumps({"model": model, "max_tokens": 3000,
                       "messages": [{"role": "user", "content": content}]}).encode()
    req = urllib.request.Request(base + "/chat/completions", data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + key,
        "Accept": "application/json", "User-Agent": UA})
    j = json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())
    return (j["choices"][0]["message"]["content"] or "").strip()


def parse_json(t):
    t = re.sub(r"^```(?:json)?|```$", "", t.strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--imgs", type=int, default=1)
    ap.add_argument("--top", type=int, default=0)
    ap.add_argument("--sheet", action="store_true")
    args = ap.parse_args()

    cfg = vcfg()
    if not cfg:
        print("没有可用的视觉模型（models.json 里找不到支持 image 输入的 provider）")
        return 1
    print("视觉模型: %s" % cfg[2])

    folders = sorted(glob.glob(os.path.join(LIB, "*")))
    folders = [f for f in folders if os.path.isdir(f)]
    if args.top:
        folders = folders[:args.top]

    for i, fd in enumerate(folders, 1):
        imgs = (sorted(glob.glob(os.path.join(fd, "cover.jpg")))
                + sorted(glob.glob(os.path.join(fd, "[0-9][0-9].jpg"))))[:max(1, args.imgs)]
        if not imgs:
            print("  %02d. 无图，跳过" % i)
            continue
        tout = os.path.join(fd, "tags.json")
        if os.path.exists(tout):
            print("  %02d. 已看过，跳过" % i)
            continue
        try:
            t = ask(cfg, imgs, PROMPT)
            obj = parse_json(t)
            if obj is None:
                obj = {"_raw": t}
        except Exception as e:
            print("  %02d. [x] %s" % (i, str(e)[:100]))
            time.sleep(2)
            continue
        obj["_folder"] = os.path.basename(fd)
        obj["_imgs"] = [os.path.basename(p) for p in imgs]
        with open(tout, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        print("  %02d. %s | %s | %s" % (i, obj.get("画风", "?")[:14],
                                        str(obj.get("材料", "?"))[:34],
                                        str(obj.get("最抓眼的那一点", ""))[:30]))
        time.sleep(1)

    # ---------- 聚合 ----------
    rows = []
    for fd in folders:
        tp = os.path.join(fd, "tags.json")
        mp = os.path.join(fd, "meta.json")
        if not os.path.exists(tp):
            continue
        tag = json.load(open(tp, encoding="utf-8"))
        meta = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}
        rows.append((meta, tag))

    def freq(key, split_material=False):
        c = {}
        for _m, t in rows:
            v = t.get(key, "")
            if split_material:
                items = v if isinstance(v, list) else re.split(r"[，,、/ ]+", str(v))
            else:
                items = [str(v)]
            for it in items:
                it = str(it).strip()
                if it and len(it) < 30:
                    c[it] = c.get(it, 0) + 1
        return sorted(c.items(), key=lambda kv: -kv[1])

    out = os.path.join(LIB, "爆款风格汇总.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("# 少儿美术课件 · 爆款画面风格汇总\n\n")
        f.write("来源：小红书同赛道高赞笔记 %d 篇，视觉模型逐张拆解封面。\n\n" % len(rows))
        for key, sm in [("画风", False), ("笔触质感", False), ("材料", True),
                        ("配色", False), ("构图", False), ("背景处理", False),
                        ("文字元素", False), ("复杂度给4-6岁小孩", False),
                        ("可复用创作公式", False)]:
            f.write("## %s\n\n" % key)
            for v, c in freq(key, sm)[:18]:
                f.write("- `%d` %s\n" % (c, v))
            f.write("\n")
        f.write("## 逐篇明细\n\n")
        for m, t in rows:
            f.write("### %s　%d赞 @%s\n\n" % (m.get("title", "?"), m.get("likes", 0), m.get("author", "")))
            for k in ("画面主体", "画风", "笔触质感", "材料", "配色", "构图", "背景处理",
                      "文字元素", "画面里有几个主体元素", "复杂度给4-6岁小孩",
                      "最抓眼的那一点", "可复用创作公式"):
                if t.get(k):
                    f.write("- **%s**：%s\n" % (k, t[k]))
            f.write("\n")
    print("\n汇总 → %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
