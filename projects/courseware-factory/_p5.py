THEME = {
    "树叶逃跑啦":     ("E8452C", "B32E1C", "FFE9C7", "FFC93C"),
    "把秋天装进罐子": ("E07A2F", "A9501A", "FFF1D6", "3E8FB0"),
    "路灯下的小猫":   ("2554A8", "16305F", "E8F0FA", "FFD93C"),
    "蚂蚁搬月亮":     ("2A3E8E", "16225C", "ECEFFA", "FFD93C"),
    "黑白小甲虫的花园": ("1B1B1B", "000000", "F2F2F2", "4CAF50"),
    "棉签点彩大树":   ("E8873A", "A85A1C", "FFF3DC", "4A8B3B"),
    "纸杯长颈鹿":     ("F2B12E", "B8791A", "FFF6DF", "A0622A"),
    "会翻跟头的西瓜": ("2E8B3D", "1B5A26", "FFF0E2", "E8452C"),
    "秋日小画合集":   ("D9542B", "9E3418", "FFF1DD", "6C4BB6"),
}

CHAIN_SLOTS = ["范画成品", "范画步骤1_起形", "范画步骤2_勾线",
               "范画步骤3_铺色", "范画步骤4_装饰高光", "范画步骤5_加背景"]
STEP_TIPS = ["线条要轻，画错了可以擦掉",
             "先想好每样东西放在纸的哪个位置，再动笔",
             "涂色要涂到边，不要留下小空白"]

TPL = os.path.join(ROOT, "项目", "爆米花蹦蹦跳-4-6岁", "project.json")
tpl = json.load(open(TPL, encoding="utf-8"))


def build(name, spec):
    p = json.loads(json.dumps(tpl))          # deep copy
    d = os.path.join(ROOT, "项目", name + "-4-6岁")
    if not os.path.isdir(d):
        sys.exit("缺目录: " + d)

    pri, dk, lt, ac = THEME[name]
    p["meta"]["name"] = "《%s》4-6岁课件" % name
    p["meta"]["theme"].update(primary=pri, dark=dk, light=lt, accent=ac)
    p["meta"]["content_status"] = "范画链已出图；课件内页文案待精修，无人购买前不导出 PDF"

    p["lock"] = spec["lock"]
    p["common"]["stroke"] = STROKE.format(palette=spec["palette"],
                                          deco=spec["deco"], light=spec["light"])

    # ---- 图片槽位 -------------------------------------------------------
    real_names = ["实物_材料工具", "实物_" + spec["real2"][0], "实物_" + spec["real2"][1]]
    photo_names = ["素材_" + s for s in spec["scenes"]]
    ri = pi = 0
    for im in p["images"]:
        im["style"] = PAPER
        if im["batch"] == "chain":
            continue
        if im["batch"] == "real":
            old = im["slot"]
            im["slot"] = real_names[ri]; ri += 1
        elif im["batch"] == "photo":
            im["slot"] = photo_names[pi]; pi += 1
        im["prompt"] = ("【改我】%s —— %s：一张信息清晰的实物/素材参考图，"
                        "白底或干净背景，四角无杂物，用于 4-6 岁课堂观察环节。" % (name, im["slot"]))
    assert ri == 3 and pi == 7, (ri, pi)

    # ---- 范画链提示词 ---------------------------------------------------
    texts = [spec["finish"], spec["s1"], spec["s2"], spec["s3"], spec["s4"], None]
    for im, tx in zip([x for x in p["images"] if x["batch"] == "chain"], texts):
        if tx:
            im["prompt"] = tx
    # 步骤5 = 成品副本，零成本
    for x in p["images"]:
        if x["slot"] == "范画步骤5_加背景":
            x.pop("prompt", None)
            x["alias"] = "范画成品"

    # ---- 步骤页 ---------------------------------------------------------
    steps = [pg for pg in p["pages"] if pg.get("type") == "step"]
    assert len(steps) == 5, len(steps)
    for pg, slot, (t, txt) in zip(steps, CHAIN_SLOTS[1:], list(spec["pages"].values())):
        pg["title"] = t
        pg["image"] = slot
        pg["uses"] = [slot]
        pg["text"] = [txt]
        pg["tips"] = list(STEP_TIPS)
    for pg in p["pages"]:
        if pg.get("type") == "cover":
            pg["title"] = "《%s》" % name
            pg["subtitle"] = "《创意美术主题》  马克笔 4-6岁"

    json.dump(p, open(os.path.join(d, "project.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("[ok] %-18s -> %s" % (name, d))
    print("     配色 %s  %s" % (pri, spec["formula"]))


for _n, _s in SPECS.items():
    build(_n, _s)
print("\n共写入 %d 个课题" % len(SPECS))
