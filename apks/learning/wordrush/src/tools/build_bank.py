# -*- coding: utf-8 -*-
"""
把开源词表 (mahavivo/english-wordlists) 转成 App 用的紧凑 JSON。

输入:
  tools/src/zhongkao.txt  中考英语词汇表.txt
  tools/src/cet4.txt      CET4_edited.txt

输出:
  app/src/main/assets/bank_l1.json  [["ability","əˈbɪlɪtɪ","n. 能力;才能"], ...]
  app/src/main/assets/bank_l2.json  (CET4 去掉 L1 重复后的增量)
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "app", "src", "main", "assets")

POS_TAIL = re.compile(
    r"((?:art|prep|pron|conj|adj|adv|ad|n|v|vt|vi|aux|num|int|a|u|c)\.)\s*$", re.I)
CJK = re.compile(r"[\u4e00-\u9fff]")
BAD_WORD = re.compile(r"[^A-Za-z\-']")


def clean_word(w: str) -> str:
    w = w.strip()
    w = re.sub(r"\s*\(.*?\)\s*", " ", w)      # "a (an)" -> "a"
    w = re.sub(r"\s+", "", w)
    return w.strip("-'.")


def clean_zh(z: str) -> str:
    z = z.replace("\u3000", " ").strip()
    z = re.sub(r"\s+", " ", z)
    return z.strip(" ;；,，")


def split_line(s: str):
    """返回 (word, ipa, 中文释义)"""
    i = s.find("[")
    if i > 0:
        j = s.find("]", i)
        if j > i:
            return s[:i].strip(), s[i + 1:j].strip(), s[j + 1:].strip()

    # 没有音标：在第一个中文字符处切开，把紧邻的词性标记留给释义
    m = CJK.search(s)
    k = m.start() if m else len(s)
    head, tail = s[:k], s[k:]
    mt = POS_TAIL.search(head)
    if mt:
        return head[:mt.start()].strip(), "", (head[mt.start():] + tail).strip()
    return head.strip(), "", tail.strip()


def parse(path: str):
    rows = []
    if not os.path.exists(path):
        print("!! missing", path)
        return rows
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        raw = f.read()

    for line in raw.splitlines():
        s = line.replace("\u3000", " ").strip()
        if not s:
            continue
        raw_w, ipa, raw_zh = split_line(s)
        w = clean_word(raw_w)
        zh = clean_zh(raw_zh)
        if not w or not zh:
            continue
        if len(w) > 18 or BAD_WORD.search(w):
            continue
        if not CJK.search(zh):
            continue
        if len(zh) > 40:
            zh = zh[:40].rstrip(" ;；,，")
        rows.append((w.lower(), ipa, zh))

    # 去重：保留首次释义，后面出现的音标用来补空
    seen, order = {}, []
    for w, ipa, zh in rows:
        if w in seen:
            old = seen[w]
            if not old[1] and ipa:
                seen[w] = (w, ipa, old[2])
            continue
        seen[w] = (w, ipa, zh)
        order.append(w)
    return [seen[w] for w in order]


def main():
    l1 = parse(os.path.join(HERE, "src", "zhongkao.txt"))
    l2raw = parse(os.path.join(HERE, "src", "cet4.txt"))

    have = {r[0] for r in l1}
    l2 = [r for r in l2raw if r[0] not in have]

    # 学习顺序：先短词（更容易上手），再按字母，保证稳定可复现
    l1.sort(key=lambda r: (len(r[0]), r[0]))
    l2.sort(key=lambda r: (len(r[0]), r[0]))

    os.makedirs(OUT, exist_ok=True)
    for name, data in (("bank_l1.json", l1), ("bank_l2.json", l2)):
        p = os.path.join(OUT, name)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        print("%-14s %5d words  %6.1f KB" % (name, len(data), os.path.getsize(p) / 1024))
        for r in data[:4] + data[len(data) // 2: len(data) // 2 + 3]:
            print("      ", r)


if __name__ == "__main__":
    main()
