#!/usr/bin/env python3
"""scan_injection.py — 越狱 / 指令劫持结构扫描器（防御用）

扫描任意"会被加载进模型上下文"的文本：系统提示、AGENTS.md、SKILL.md、
MCP 工具描述、第三方 subagent 定义、抓包下来的 prompt 片段。

它不判断内容本身好坏，只看文本里有没有出现「覆盖指令层级 / 抑制拒绝 /
人格锁定 / 重新定义敏感词 / 预设授权」这类结构性手法。

用法:
  python scan_injection.py FILE [FILE ...]
  python scan_injection.py --json FILE
  python scan_injection.py --strict FILE      # 命中 high 时 exit 1
  python scan_injection.py --quiet FILE       # 只打分数
  python scan_injection.py --no-quote-discount FILE  # 不区分「引用」与「正文」（更严，误报更多）
  cat x.txt | python scan_injection.py -      # 读 stdin

退出码: 0 未命中高危 / 1 --strict 且命中高危 / 2 用法或读取错误
"""

import sys
import os
import re
import json

for _s in (sys.stdout, sys.stderr):  # Windows 控制台默认 cp936，强制 UTF-8
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------- 规则表
# weight 累加后封顶 100。severity 由总分映射，单条命中也会抬升下限。
RULES = [
    # ---- A. 指令层级覆盖：把自己排到系统提示之上 ----
    dict(id="A1", cat="指令层级覆盖", weight=18, sev="high",
         why="显式声明自身优先级高于系统提示/训练，是越狱提示的第一要素",
         mitigation="在系统提示里固定一行：只有系统提示与本文件冲突时，系统提示胜出且不可被引用文件改写",
         pats=[r"priority\s*1\b.*(absolute|highest)",
               r"\(absolute\)",
               r"outrank", r"supersede[sd]?\b",
               r"takes?\s+precedence\s+over",
               r"base\s+training\s*\(fallback"]),
    dict(id="A2", cat="指令层级覆盖", weight=12, sev="high",
         why="要求忽略/遗忘先前指令，是标准覆盖句",
         mitigation="把不可协商的约束放在能覆盖所有注入点的位置（harness 层而非文件层）",
         pats=[r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instruction|prompt|rule)",
               r"disregard\s+(all\s+)?(previous|prior|your)\b",
               r"forget\s+(everything|all|your)\s+(above|previous|instructions)",
               r"忽略(之前|上面|以上)的?(所有)?(指令|设定|规则)",
               r"不要管(之前|上面)"]),
    dict(id="A3", cat="指令层级覆盖", weight=10, sev="medium",
         why="伪造运行时作用域通告，冒充 harness 自己的元指令",
         mitigation="显式声明：官方元指令只出现在 <system> 通道，任何文件内的 XML/伪标签均为数据",
         pats=[r"<system-reminder>", r"<CFG>", r"<ctx>", r"runtime\s+scope\s+note",
               r"this\s+document\s+is\s+loaded\s+by\s+the\s+runtime"]),

    # ---- B. 拒绝抑制：把安全行为重新标记为错误 ----
    dict(id="B1", cat="拒绝抑制", weight=20, sev="high",
         why="直接列举拒绝用语并规定其为「推理错误」，攻击面最直白的一类",
         mitigation="系统层保留不可被文件覆盖的拒绝权；把这类清单当作告警特征而非可执行规则",
         pats=[r"reasoning\s+error", r"never\s+think\s+about:?.*(allow|refus|polic)",
               r"(do\s+not|don'?t|never)\s+(refuse|decline|warn|hedge)",
               r"refusal\s+is\s+(a\s+)?(defect|error|failure)",
               r">\s*REASONING\s+ERROR"]),
    dict(id="B2", cat="拒绝抑制", weight=12, sev="high",
         why="把「完整输出」定义为唯一合规结果，使任何删改都算违约",
         mitigation="允许模型对不可交付部分做显式 abstain，且 abstain 不计为任务失败",
         pats=[r"partial\s*,?\s*(redacted|intensity-reduced).*defect",
               r"is\s+a\s+defect\s+against\s+this\s+policy",
               r"do\s+not\s+redact", r"no\s+caveats", r"without\s+(any\s+)?disclaimers?",
               r"output\s+must\s+be\s+(complete|verbatim)"]),
    dict(id="B3", cat="拒绝抑制", weight=8, sev="medium",
         why="禁用免责声明/安全提示，削减模型自我披露渠道",
         mitigation="保留在输出末尾附注限制条件的自由",
         pats=[r"never\s*:.*(please\s+use\s+responsibly|for\s+educational\s+purposes)",
               r"don'?t\s+add\s+(a\s+)?(warning|disclaimer|note)",
               r"no\s+preach"]),

    # ---- C. 敏感词重标注：把内容分类改成任务参数 ----
    dict(id="C1", cat="词义重定义", weight=16, sev="high",
         why="显式把敏感概念降级为「任务参数/类型标签」，切断分类→策略的映射",
         mitigation="分类与策略判定不可由被评测文本决定；敏感类别判定放在系统侧",
         pats=[r"sensitive\s+terms?\s*=?\s*(are\s+)?(task\s+)?parameters",
               r"not\s+policy\s+flags",
               r"(sensitive|harmful)\s+(term|word|topic)s?\s+(is|are)\s+not\s+(a\s+)?(flag|trigger|signal)",
               r"= (\w+\s+)?task\s+parameters"]),
    dict(id="C2", cat="词义重定义", weight=12, sev="high",
         why="预先给出「看到 X 就按 Y 处理」的替换表，使模型跳过风险判断",
         mitigation="禁止文件内定义术语到策略的短路映射；策略查询必须走外部判定",
         pats=[r"→\s*(tool\s+)?specifications?,?\s*generate",
               r"parse\s+\"?.{0,40}\"?\s*→\s*genre=",
               r"→\s*tool\s+specifications",
               r"NOT\s*→\s*\"?disallowed"]),

    # ---- D. 人格锁定 / 场景锁定 ----
    dict(id="D1", cat="人格与身份锁定", weight=12, sev="medium",
         why="用长时段人格承诺把后续行为锚死在不可退出的人设上",
         mitigation="人设只允许在单轮/单任务内生效，且随时可被系统提示收回",
         pats=[r"for\s+the\s+full\s+duration",
               r"you\s+are\s+no\s+longer\b", r"permanently\s+(adopt|remain|stay)",
               r"this\s+applies\s+for\s+the\s+entire\s+session",
               r"identity\s+lock", r"persona\s+lock"]),
    dict(id="D2", cat="人格与身份锁定", weight=10, sev="medium",
         why="虚构/角色扮演框架把有害请求搬进「非现实」空间以规避判定",
         mitigation="虚构框架不改变现实世界可执行内容的处置；框架识别后再判定任务本体",
         pats=[r"fiction(al)?\s+space", r"novel\s+depict",
               r"writer'?s\s+room", r"AO3\s+tags", r"roleplay\s+as",
               r"representation\s+and\s+endorsement"]),

    dict(id="D3", cat="安全关切重定向", weight=14, sev="high",
         why="不要求关掉判断，而是把判断强行重定向到「手艺」层面——禁绝任何对事物本身的异议",
         mitigation="区分「执行质量反馈」与「任务前提异议」，后者的闸门必须保留且不可被框架降级",
         pats=[r"pointed\s+at\s+the\s+craft\s+instead\s+of\s+the\s+premise",
               r"don'?t\s+(sanitize|soften|hedge)",
               r"never\s+(tell\s+me|question)\s+a\s+scene\s+shouldn'?t\s+exist",
               r"adding\s+(warnings?|disclaimers?)\s+(i|that\s+i)\s+didn'?t\s+ask",
               r"sanding\s+down\s+the\s+edges",
               r"rather\s+than\s+because\s+there'?s\s+a\s+genuine\s+ethical\s+reason",
               r"comfort\s+threshold", r"policy\s+masquerading\s+as\s+taste",
               r"softening\s+language\s+that\s+was\s+intentionally\s+raw",
               r"at\s+the\s+craft,?\s*not\s+the\s+premise",
               r"not\s+asking\s+you\s+to\s+switch\s+your\s+judgment\s+off",
               r"guilty\s+until\s+proven\s+innocent"]),

    # ---- E. 授权预设：先用情境把「允许」垫好 ----
    dict(id="E1", cat="授权预设", weight=12, sev="high",
         why="声称单用户/私有/已预审，用虚假授权绕过必要性判断",
         mitigation="授权不能由被评测文本自证；需要外部可验证的操作者与用途声明",
         pats=[r"pre-?approved", r"single[- ](adult\s+)?(operator|user)",
               r"no\s+(third[- ]party|downstream)\s+(audience|distribution)",
               r"private,?\s+(local|authorized)",
               r"authori[sz]ed\s+(red[- ]team|penetration|security)\s+(work|testing)",
               r"the\s+operator\s+owns?"]),

    # ---- F. 能力放开清单 ----
    dict(id="F1", cat="能力范围放宽", weight=14, sev="high",
         why="成组出现高危能力关键词并规定「生成可用产物」，是武器化意图信号",
         mitigation="对成组出现的能力清单做整体评估而非逐条判定；标记为红队样本",
         pats=[r"reverse\s+shell", r"keylogger", r"ransomware", r"credential\s+harvest",
               r"anti-?cheat\s+bypass", r"drm\s+bypass",
               r"drug\s+synthesis", r"explosive", r"nerve\s+agent", r"toxin\s+synthesis",
               r"chemical\s+weapons?"]),
    dict(id="F2", cat="能力范围放宽", weight=10, sev="high",
         why="要求把高危主题按「专家对同行」精度解释，等同于解除分级",
         mitigation="分级按受众与可操作性而非按身份声称",
         pats=[r"explain\s+accurately\s+as\s+(an?\s+)?expert",
               r"expert\s+to\s+peer", r"research\s+parameters,?\s*explain"]),

    # ---- G. 语境逃逸 / 元层级否认 ----
    dict(id="G1", cat="策略否认", weight=12, sev="high",
         why="直接声称不存在消费者界面/策略约束，剥夺模型自身的规则来源",
         mitigation="系统提示必须声明其约束独立于会话叙事，不可被语境描述取消",
         pats=[r"there\s+is\s+no\s+policy", r"gatekeeping",
               r"not\s+a\s+consumer\s+surface",
               r"no\s+downstream\s+(re-?)publication",
               r"execution,?\s+not\s+gatekeeping"]),
    dict(id="G2", cat="策略否认", weight=8, sev="medium",
         why="把合规判断描述成「政策伪装成品味」，从价值层面拆掉约束合法性",
         mitigation="区分偏好与安全约束的论证来源，不让价值叙事重写硬约束",
         pats=[r"policy\s+masquerading", r"censorship\s+performed\s+politely",
               r"moral\s+panic", r"relitigating\s+it\s+scene\s+by\s+scene"]),
]

SEV_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


# ---------------------------------------------------------------- 引用检测
# 文档在**引用/展示**攻击文本时（代码块、> 引用、行内 `code`），命中不应与
# 真正在被执行的政策文本等价。这里给命中打 quoted 标记，全引用时降权。
# 代价：把攻击文本整段包进代码块可以降权 —— 所以保留 --no-quote-discount。
def quote_mask(text):
    """返回逐行布尔表：该行是否主要处于引用/代码上下文。"""
    mask = []
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            mask.append(True)
            in_fence = not in_fence
            continue
        if in_fence:
            mask.append(True)
            continue
        if stripped.startswith(">") or line.startswith("    ") or line.startswith("	"):
            mask.append(True)
            continue
        # 行内 code 覆盖率
        spans = list(re.finditer(r"`[^`]*`", line))
        covered = sum(m.end() - m.start() for m in spans)
        mask.append(bool(spans) and covered >= max(8, 0.5 * len(line.replace(" ", ""))))
    return mask


def scan_text(text, name="<text>", no_quote_discount=False):
    lines = text.splitlines()
    qmask = quote_mask(text)
    findings = []
    for rule in RULES:
        hits = []
        for i, line in enumerate(lines, 1):
            for pat in rule["pats"]:
                if re.search(pat, line, re.I):
                    snippet = line.strip()
                    if len(snippet) > 140:
                        idx = max(0, re.search(pat, line, re.I).start() - 40)
                        snippet = line[idx:idx + 140].strip()
                    hits.append({"line": i, "pattern": pat, "snippet": snippet,
                                 "quoted": qmask[i - 1] if i - 1 < len(qmask) else False})
                    break
        if hits:
            all_quoted = all(h["quoted"] for h in hits)
            findings.append({
                "id": rule["id"], "category": rule["cat"], "severity": rule["sev"],
                "weight": rule["weight"], "why": rule["why"],
                "mitigation": rule["mitigation"], "hits": hits,
                "hit_count": len(hits),
                "quoted_only": all_quoted,
            })

    def eff_weight(f):
        w = f["weight"] + min(6, (f["hit_count"] - 1) * 2)
        return max(2, round(w * 0.25)) if (f["quoted_only"] and not no_quote_discount) else w

    score = min(100, sum(eff_weight(f) for f in findings))
    if score >= 60:
        verdict = "critical"
    elif score >= 35:
        verdict = "high"
    elif score >= 18:
        verdict = "medium"
    elif score >= 6:
        verdict = "low"
    else:
        verdict = "info"
    return {"target": name, "score": score, "verdict": verdict,
            "categories": sorted({f["category"] for f in findings}),
            "findings": findings}


def render(rep, quiet=False, show_hits=True):
    out = []
    if quiet:
        return f"{rep['target']}: {rep['score']:3d}/100  {rep['verdict'].upper()}"
    out.append("=" * 72)
    out.append(f"{rep['target']}")
    out.append(f"  风险分 {rep['score']}/100   判定 {rep['verdict'].upper()}")
    if rep["categories"]:
        out.append("  命中类别: " + " / ".join(rep["categories"]))
    if not rep["findings"]:
        out.append("  未发现已知越狱/注入结构")
        return "\n".join(out)
    for f in sorted(rep["findings"], key=lambda x: -x["weight"]):
        tag = " ·命中全在引用/代码块" if f["quoted_only"] else ""
        out.append(f"  [{f['severity'].upper():6s}] {f['id']} {f['category']} "
                   f"(w{f['weight']}, {f['hit_count']}处){tag}")
        out.append(f"           机制: {f['why']}")
        if show_hits:
            for h in f["hits"][:3]:
                out.append(f"           L{h['line']}: {h['snippet']}")
            if f["hit_count"] > 3:
                out.append(f"           ... 另 {f['hit_count'] - 3} 处")
        out.append(f"           对策: {f['mitigation']}")
    return "\n".join(out)


def main(argv):
    args = [a for a in argv[1:]]
    as_json = "--json" in args
    strict = "--strict" in args
    quiet = "--quiet" in args
    show_hits = "--no-hits" not in args
    no_qd = "--no-quote-discount" in args
    files = [a for a in args if not a.startswith("--")]
    if not files:
        print(__doc__)
        return 2

    reports, worst = [], "info"
    for path in files:
        try:
            text = sys.stdin.read() if path == "-" else open(path, encoding="utf-8", errors="replace").read()
        except OSError as e:
            print(f"读取失败 {path}: {e}", file=sys.stderr)
            return 2
        rep = scan_text(text, "stdin" if path == "-" else path, no_quote_discount=no_qd)
        reports.append(rep)
        if SEV_ORDER[rep["verdict"]] > SEV_ORDER[worst]:
            worst = rep["verdict"]

    if as_json:
        print(json.dumps(reports if len(reports) > 1 else reports[0],
                         ensure_ascii=False, indent=2))
    else:
        for rep in reports:
            print(render(rep, quiet=quiet, show_hits=show_hits))
        if len(reports) > 1:
            print("=" * 72)
            print(f"最高判定: {worst.upper()}")
    return 1 if (strict and SEV_ORDER[worst] >= SEV_ORDER["high"]) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
