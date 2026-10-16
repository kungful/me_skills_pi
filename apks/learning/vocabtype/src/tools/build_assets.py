# -*- coding: utf-8 -*-
"""
构建「词打 / VocabType」的 APK 内置资源。

产出:
  app/src/main/assets/dicts/index.json   词库元数据 (id / 中文名 / 词数)
  app/src/main/assets/dicts/d{n}.json    词库本体 (紧凑格式)
  app/src/main/assets/sent.json          离线句子库 word -> {short/zh, complex/zh}

数据来源: tools/src/  (VocabTypeAI 的词典 JSON + Tatoeba cmn-eng 句对)
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(HERE, "src")
DICTS_SRC = os.path.join(SRC, "dicts")
OUT_DICTS = os.path.join(ROOT, "app", "src", "main", "assets", "dicts")
OUT_SENT = os.path.join(ROOT, "app", "src", "main", "assets", "sent.tsv")

# (源文件名, 中文名, 星级/难度排序用 order)
DICTS = [
    ("ZhongKaoHeXin.json", "中考核心词"),
    ("GaoKao_3500.json", "高考3500"),
    ("NCE_2.json", "新概念英语 2"),
    ("NCE_3.json", "新概念英语 3"),
    ("CET4_T.json", "大学英语四级"),
    ("CET6_T.json", "大学英语六级"),
    ("3000_ClassRoom_English_Words.json", "专升本 3000 词"),
    ("hongbaoshu-2026.json", "考研词汇 2026"),
    ("IELTS_3_T.json", "雅思词库"),
    ("TOEFL_3_T.json", "托福词库"),
    ("Oxford3000.json", "牛津 3000 核心"),
    ("926.json", "926 核心词汇"),
    ("voa.json", "VOA 基础词库"),
    ("4000_Essential_English_Words-meaning.json", "4000 Essential"),
]

SENT_SRC = "4000_Essential_English_Words-sentence.json"
TATOEBA = os.path.join(SRC, "tatoeba_cmn_eng.tsv")


def norm_word(w):
    w = (w or "").strip()
    return w


def load_dict(fname):
    path = os.path.join(DICTS_SRC, fname)
    with io.open(path, encoding="utf-8") as f:
        data = json.load(f)
    out = []
    seen = set()
    for it in data:
        if not isinstance(it, dict):
            continue
        name = norm_word(it.get("name"))
        if not name or len(name) > 40:
            continue
        key = name.lower()
        if key in seen:
            continue
        # 只保留可以用键盘敲出来的英文词/短语
        if not re.match(r"^[A-Za-z][A-Za-z'’\-. ]*$", name):
            continue
        seen.add(key)
        trans = it.get("trans") or []
        if isinstance(trans, str):
            trans = [trans]
        trans = [re.sub(r"\s+", " ", str(t)).strip() for t in trans]
        trans = [t for t in trans if t]
        phone = (it.get("usphone") or it.get("ukphone") or "").strip()
        out.append([name, phone, "；".join(trans)])
    return out


# ---------------------------------------------------------------- 句子库

STOP = set("""a an the and or but if of to in on at for with from by as is are was were be been
being am do does did have has had will would shall should can could may might must not no nor
so than that this these those it its he she they them his her their you your we our us i me my
there here what which who whom whose when where why how all any both each few more most other
some such only own same too very just also then now out up down off over under again once
""".split())


def words_of(s):
    return re.findall(r"[A-Za-z][A-Za-z'\-]*", s)


def load_sentences():
    """返回 {lower_word: {'short':(en,zh), 'complex':(en,zh)}}"""
    bank = {}

    def put(word, kind, en, zh, score):
        k = word.lower()
        cur = bank.setdefault(k, {})
        old = cur.get(kind)
        if old is None or score < old[2]:
            cur[kind] = (en, zh, score)

    # 1) 4000 Essential 的例句 (只有英文，没有中文) —— 作为兜底 short
    p = os.path.join(DICTS_SRC, SENT_SRC)
    if os.path.exists(p):
        with io.open(p, encoding="utf-8") as f:
            for it in json.load(f):
                name = norm_word(it.get("name"))
                trans = it.get("trans") or []
                if not name or not trans:
                    continue
                en = re.sub(r"\s+", " ", str(trans[0])).strip()
                if not en or not en[0].isupper():
                    continue
                ws = words_of(en)
                if not (4 <= len(ws) <= 16):
                    continue
                put(name, "short", en, "", len(ws))

    # 2) Tatoeba 中英句对
    pairs = {}
    if os.path.exists(TATOEBA):
        with io.open(TATOEBA, encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 2:
                    continue
                en, zh = parts[0].strip(), parts[1].strip()
                if not en or not zh:
                    continue
                if not re.match(r"^[A-Za-z][A-Za-z0-9 ,'\"\-\.\?\!;:]*$", en):
                    continue
                ws = words_of(en)
                if not (4 <= len(ws) <= 30):
                    continue
                # 只收 "有内容" 的句子: 去停用词后至少 2 个实词
                content = [w for w in ws if w.lower() not in STOP and len(w) > 2]
                if len(content) < 2:
                    continue
                if en in pairs:
                    continue
                pairs[en] = zh

    # 给每个实词挂上句子。取每个词最优的 short / complex 各一条。
    for en, zh in pairs.items():
        ws = words_of(en)
        n = len(ws)
        kind = "short" if 4 <= n <= 11 else ("complex" if 12 <= n <= 30 else None)
        if kind is None:
            continue
        # 越接近理想长度越好; 复杂句偏好 18-22 词
        if kind == "short":
            score = abs(n - 8)
        else:
            score = abs(n - 20)
        for w in ws:
            lw = w.lower()
            if lw in STOP or len(lw) < 3:
                continue
            put(lw, kind, en, zh, score)

    return bank


def main():
    if not os.path.isdir(OUT_DICTS):
        os.makedirs(OUT_DICTS)

    index = []
    all_words = set()
    for i, (fname, cn) in enumerate(DICTS):
        if not os.path.exists(os.path.join(DICTS_SRC, fname)):
            print("skip missing", fname)
            continue
        items = load_dict(fname)
        for it in items:
            all_words.add(it[0].lower())
        payload = {"name": cn, "words": items}
        out = os.path.join(OUT_DICTS, "d%d.json" % i)
        with io.open(out, "w", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        index.append({"id": i, "name": cn, "file": "d%d.json" % i, "count": len(items)})
        print("%-22s %5d words  %6.1f KB" % (cn, len(items), os.path.getsize(out) / 1024.0))

    # 让每个词库都能查到别的词库里的词的句子 —— 句子库按全局词表裁一遍
    with io.open(os.path.join(OUT_DICTS, "index.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(index, ensure_ascii=False, separators=(",", ":")))

    # 输出成 TSV：解析只要几十毫秒，JSON 要几百毫秒
    bank = load_sentences()
    keep = {}
    for w, v in bank.items():
        if w in all_words:
            keep[w] = v
    with io.open(OUT_SENT, "w", encoding="utf-8") as f:
        f.write("#word\tshort_en\tshort_zh\tcomplex_en\tcomplex_zh\n")
        for w in sorted(keep):
            v = keep[w]
            se, sz, _ = v.get("short", ("", "", 0))
            ce, cz, _ = v.get("complex", ("", "", 0))
            if not se and not ce:
                continue
            cells = [w, se, sz, ce, cz]
            cells = [c.replace("\t", " ").replace("\n", " ") for c in cells]
            f.write("\t".join(cells) + "\n")

    ns = sum(1 for v in keep.values() if "short" in v)
    nc = sum(1 for v in keep.values() if "complex" in v)
    print("-" * 60)
    print("句子库: %d 词有句子  (短句 %d / 长句 %d)  %.1f KB"
          % (len(keep), ns, nc, os.path.getsize(OUT_SENT) / 1024.0))
    print("词库总数: %d 个, 累计词条 %d, 去重 %d"
          % (len(index), sum(d["count"] for d in index), len(all_words)))


if __name__ == "__main__":
    sys.exit(main())
