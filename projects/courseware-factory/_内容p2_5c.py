
THEME = {
    "撒盐画雪花":   ("27408F", "14245E", "E8EDFB", "35B3C8"),
    "毛线小鱼":     ("1E8FA8", "0D5A6E", "EAF7FA", "E8452C"),
    "蒙德里安的花瓶": ("D02128", "101010", "FAF6EC", "1B4FA8"),
    "刮画蘑菇城堡": ("141414", "000000", "F2E9D8", "D0216B"),
    "对折印蝴蝶":   ("C42C7A", "7A1747", "FDF2F8", "E8873A"),
}

SLOTS_DEFAULT = ["范画成品", "范画步骤1_起形", "范画步骤2_勾线",
                 "范画步骤3_铺色", "范画步骤4_装饰高光", "范画步骤5_加背景"]
STEP_TIPS = ["线条要轻，画错了可以擦掉",
             "先想好每样东西放在纸的哪个位置，再动笔",
             "颜色要涂到边，不要留下小空白"]

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
    p["meta"]["formula"] = spec["formula"]

    p["lock"] = spec["lock"]
    st = spec.get("stroke") or STROKE_SALT
    if spec.get("stroke_extra"):
        st = st + "\n" + spec["stroke_extra"]
    p["common"]["stroke"] = st.format(palette=spec["palette"], deco=spec["deco"],
                                      light=spec["light"], sky=spec.get("sky", ""))

    slots = spec.get("slots") or SLOTS_DEFAULT

    real_names = ["实物_材料工具", "实物_" + spec["real2"][0], "实物_" + spec["real2"][1]]
    photo_names = ["素材_" + s for s in spec["scenes"]]
    ri = pi = 0
    for im in p["images"]:
        im["style"] = PAPER
        if im["batch"] == "chain":
            continue
        if im["batch"] == "real":
            im["slot"] = real_names[ri]; ri += 1
        elif im["batch"] == "photo":
            im["slot"] = photo_names[pi]; pi += 1
        im["prompt"] = ("【改我】%s —— %s：一张信息清晰的实物/素材参考图，"
                        "白底或干净背景，四角无杂物，用于 4-6 岁课堂观察环节。" % (name, im["slot"]))
    assert ri == 3 and pi == 7, (ri, pi)

    texts = [spec["finish"], spec["s1"], spec["s2"], spec["s3"], spec["s4"], None]
    for im, tx, sl in zip([x for x in p["images"] if x["batch"] == "chain"], texts, slots):
        im["slot"] = sl
        if tx:
            im["prompt"] = tx
    for x in p["images"]:
        if x["slot"] == slots[5]:
            x.pop("prompt", None)
            x["alias"] = "范画成品"

    steps = [pg for pg in p["pages"] if pg.get("type") == "step"]
    assert len(steps) == 5, len(steps)
    for pg, slot, (t, txt) in zip(steps, slots[1:], list(spec["pages"].values())):
        pg["title"] = t
        pg["image"] = slot
        pg["uses"] = [slot]
        pg["text"] = [txt]
        pg["tips"] = list(STEP_TIPS)
    for pg in p["pages"]:
        if pg.get("type") == "cover":
            pg["title"] = "《%s》" % name
            pg["subtitle"] = "《创意美术主题》  综合材料 4-6岁"

    json.dump(p, open(os.path.join(d, "project.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("[ok] %-14s -> %s" % (name, d))
    print("     配色 %s  %s" % (pri, spec["formula"]))


for _n, _s in SPECS.items():
    build(_n, _s)
print("\n共写入 %d 个课题" % len(SPECS))
