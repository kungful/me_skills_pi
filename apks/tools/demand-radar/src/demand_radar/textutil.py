"""文本处理：清洗 / 分词 / 关键词抽取 / 痛点信号匹配"""
from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from functools import lru_cache
from typing import Dict, List, Sequence, Tuple

from .config import keywords_cfg, sources_cfg

try:
    import jieba
    import jieba.analyse

    jieba.setLogLevel(60)
    _HAS_JIEBA = True
except Exception:  # pragma: no cover
    _HAS_JIEBA = False


# ---------------------------------------------------------------- 清洗

_TAG_RE = re.compile(r"<[^>]{1,200}>")
_WS_RE = re.compile(r"[ \t\u00a0\u3000]+")
_NL_RE = re.compile(r"\n{2,}")
# 常见无意义营销噪音
_NOISE_RE = re.compile(
    r"(点击(查看|下载|了解)更多|扫码关注|长按识别|关注公众号|转载请|版权归|"
    r"\b(read more|click here|subscribe now)\b)",
    re.I,
)
_CJK = re.compile(r"[\u4e00-\u9fff]")

# 无障碍/网页取下来的 UI 噪音：资源 ID、类名、按钮状态后缀
_ID_RE = re.compile(r"^(?:[A-Za-z0-9_\-+/=]{16,}|O1CN\w+|pic\w{16,})$")
_CLASS_RE = re.compile(
    r"^(?:(?:android|androidx|com|org|java|kotlin)\.[\w.$]+|"
    r"[\w.$]*(?:WebView|Layout|RecyclerView|ViewGroup|ImageView|TextView|ViewPager|Fragment|DecorView))$"
)
_CHROME_RE = re.compile(r"(?:[，,]?\s*(?:已选中|未选中状态|选中状态|未读消息数\d+|按钮|可点击))+$")
_UI_LABELS = {
    "首页", "推荐", "关注", "消息", "我", "返回", "取消", "确定", "完成", "搜索", "更多",
    "分享", "评论", "点赞", "收藏", "转发", "设置", "登录", "注册", "同意", "允许", "拒绝",
    "下一步", "跳过", "关闭", "全部", "综合", "视频", "图文", "用户", "直播", "已选中",
    "未选中状态", "加载中", "下拉刷新", "查看更多", "暂无数据", "没有更多了",
}


def strip_ui_noise(text: str) -> str:
    """剔除无障碍/网页抓下来的控件噪音，留下真正有信息量的正文"""
    out: List[str] = []
    for raw in text.split("\n"):
        s = raw.strip()
        if not s:
            continue
        s = _CHROME_RE.sub("", s).strip()
        s = re.sub(r"^pic(?=\S)", "", s)      # 图片的 alt 前缀，后面的正文要留
        if not s or s in _UI_LABELS:
            continue
        if _ID_RE.match(s) or _CLASS_RE.match(s):
            continue
        if not _CJK.search(s) and not re.search(r"[A-Za-z]{3,}", s):
            continue
        out.append(s)
    return "\n".join(out)


def clean(text: str) -> str:
    if not text:
        return ""
    t = html.unescape(str(text))
    t = _TAG_RE.sub(" ", t)
    t = t.replace("\r", "\n")
    t = _NOISE_RE.sub(" ", t)
    # 去掉控制字符（保留换行）
    t = "".join(ch if (ch == "\n" or unicodedata.category(ch)[0] != "C") else " " for ch in t)
    t = _WS_RE.sub(" ", t)
    t = _NL_RE.sub("\n", t)
    return strip_ui_noise(t).strip()


def detect_lang(text: str) -> str:
    cjk = len(_CJK.findall(text[:400]))
    return "zh" if cjk >= 8 else "en"


def has_cjk(s: str) -> bool:
    return bool(_CJK.search(s))


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()[:24]


# ---------------------------------------------------------------- 词典装载

@lru_cache(maxsize=1)
def _prior_map() -> Dict[str, float]:
    return {
        str(k): float(v)
        for k, v in ((sources_cfg().get("source_prior") or {})).items()
    }


def source_prior(source: str, fallback: float = 0.45) -> float:
    """源先验：这条素材本身隐含多少「需求意图」（配置在 sources.yaml）"""
    return min(1.0, max(0.0, _prior_map().get(source, fallback)))


@lru_cache(maxsize=1)
def _generic_set() -> set:
    return {str(x).lower() for x in (keywords_cfg().get("generic_primary") or [])}


def is_generic(kw: str) -> bool:
    """是否为过于泛化的通用词（不能单独作为需求主题）"""
    return kw.lower() in _generic_set()


_ASCII_KW = re.compile(r"^[a-z0-9][a-z0-9 +#._-]*$")


def _kw_hit(kw: str, low: str) -> bool:
    """关键词命中判定：纯英文词按词边界匹配，避免 ai 命中 email"""
    if _ASCII_KW.match(kw):
        return re.search(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])", low) is not None
    return kw in low


@lru_cache(maxsize=1)
def _lexicon() -> Tuple[List[Tuple[str, dict]], List[Tuple[str, dict]]]:
    """返回 (领域词表[(kw, entry)], 痛点模式[(compiled, {w,tag})])"""
    cfg = keywords_cfg()
    kws: List[Tuple[str, dict]] = []
    for dom in cfg.get("domains") or []:
        for k in dom.get("k") or []:
            kws.append((str(k).lower(), dom))
    # 长词优先，避免 "记账" 抢掉 "记账app"
    kws.sort(key=lambda x: -len(x[0]))

    pains: List[Tuple[re.Pattern, dict]] = []
    for p in cfg.get("pain_patterns") or []:
        try:
            pains.append((re.compile(p["re"], re.I), {"w": float(p.get("w", 1)), "tag": p.get("tag", "信号")}))
        except re.error:
            continue
    return kws, pains


def domain_matches(text: str, limit: int = 6) -> List[Tuple[str, dict]]:
    """返回命中的领域词：具体词优先，通用词排最后"""
    low = text.lower()
    hits: List[Tuple[str, dict]] = []
    covered: List[str] = []
    for kw, entry in _lexicon()[0]:
        if _kw_hit(kw, low):
            # 若已被更长的命中词覆盖（"记账app" 覆盖 "记账"），跳过
            if any(kw in c for c in covered):
                continue
            covered.append(kw)
            hits.append((kw, entry))
    # 先按"是否通用"，再按长度（越长越具体），最后按成熟度
    hits.sort(key=lambda x: (is_generic(x[0]), -len(x[0]), x[1].get("mat", 1)))
    return hits[:limit]


def canonical(kw: str, entry: dict) -> str:
    """领域词的标准名（取词典第一个别名，主题标签更干净）"""
    ks = entry.get("k") or []
    return str(ks[0]) if ks else kw


def pain_hits(text: str) -> List[Tuple[str, str, float]]:
    """返回 [(tag, 命中片段, 权重)]"""
    out: List[Tuple[str, str, float]] = []
    for rx, meta in _lexicon()[1]:
        m = rx.search(text)
        if m:
            out.append((meta["tag"], m.group(0)[:24], meta["w"]))
    return out


# ---------------------------------------------------------------- 分词 / 关键词

_ASCII_WORD = re.compile(r"[a-zA-Z][a-zA-Z0-9+#._-]{2,}")
_STOP = set(
    """的 了 是 我 你 他 她 它 们 这 那 有 在 和 与 也 就 都 而 及 或 一个 什么 怎么 如何 为什么
不是 没有 可以 但是 因为 所以 如果 已经 自己 现在 时候 非常 真的 觉得 知道 感觉 大家 我们 你们
他们 这个 那个 一些 很多 比较 还是 只是 应该 需要 可能 一定 就是 这样 那样 然后 而且 不过 其实
东西 事情 问题 情况 方法 方式 时候 地方 一个 一样 一直 之后 之前 之前 目前 现在
""".split()
)

_EN_STOP = set(
    """a an the is are was were be been being am to of in on at for and or but if then than this that these those
with without within into onto from by as it its it's i you he she they we me my mine your yours our theirs their
them us him her his not no nor do does did done doing can could would should shall will may might must have has
had having very just even much more most less least only also too own same other another such any all both few
many some each every either neither when where which what who whom whose why how there here their them then
because while about after before during between through above below up down out off over under again further once
like get got make made use used using need needs want wants one two three lot really thing things stuff way ways
don't didn't doesn't isn't aren't wasn't weren't couldn't wouldn't shouldn't can't won't s t re ve ll d m
""".split()
) | _STOP


def tokenize(text: str) -> List[str]:
    tokens: List[str] = []
    if _HAS_JIEBA and _CJK.search(text):
        for w in jieba.cut(text):
            w = w.strip()
            if len(w) >= 2 and w.lower() not in _STOP:
                tokens.append(w.lower())
    tokens.extend(m.lower() for m in _ASCII_WORD.findall(text))
    return [t for t in tokens if t not in _STOP]


def top_terms(text: str, k: int = 6, prefer_cjk: bool = False) -> List[str]:
    """通用关键词（jieba TF-IDF / 词频兜底），用于领域词之外的簇标识"""
    if not text.strip():
        return []
    words: List[str] = []
    if _HAS_JIEBA:
        try:
            words = [w for w in jieba.analyse.extract_tags(text, topK=k * 3) if w.lower() not in _STOP]
        except Exception:
            words = []
    if not words:
        from collections import Counter

        words = [w for w, _ in Counter(tokenize(text)).most_common(k * 2)]
    if prefer_cjk:
        cjk = [w for w in words if _CJK.search(w)]
        if cjk:
            words = cjk
    # 太短的英文碎片没意义
    words = [w for w in words if not (_ASCII_WORD.fullmatch(w) and len(w) < 4)]
    return words[:k]


def similarity(a: Sequence[str], b: Sequence[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def jaccard(a: Sequence[str], b: Sequence[str]) -> float:
    return similarity(a, b)


def snippet(text: str, term: str = "", width: int = 90) -> str:
    """截取包含关键词的一小段，用于报告展示"""
    t = _WS_RE.sub(" ", text.replace("\n", " "))
    if term:
        i = t.lower().find(term.lower())
        if i > 0:
            start = max(0, i - width // 3)
            return ("…" if start else "") + t[start : start + width].strip() + "…"
    return t[:width].strip() + ("…" if len(t) > width else "")
