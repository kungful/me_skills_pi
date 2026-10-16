"""需求打分与主题聚合引擎 —— 整个系统的核心

打分逻辑：
  1) 单条素材分(item.demand 0-100)
       信号强度(命中痛点句式的加权和) 70%
       付费意愿 18%
       源自带热度 12%
       × 源权重 × 文本质量系数
  2) 主题分(topic.score 0-100)
       痛点均值 / 证据量 / 跨源多样性 / 付费意愿 / 新鲜度 / 趋势加速度
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from . import textutil as tu
from .config import keywords_cfg
from .models import Item, Topic

# ------------------------------------------------------------------ 常量

PAY_TAGS = {"付费意愿", "预算明确", "价格询问"}
URGENCY_TAGS = {"紧迫"}
MAT_LABEL = {0: "蓝海机会", 1: "有竞争", 2: "红海赛道"}

MIN_ITEM_SCORE_DEFAULT = 12.0   # 兜底；实际值读 config/keywords.yaml → thresholds.min_item_score
MAX_ITEM_SCORE = 100.0


def min_item_score() -> float:
    cfg = keywords_cfg()
    return float((cfg.get("thresholds") or {}).get("min_item_score", MIN_ITEM_SCORE_DEFAULT))


MIN_ITEM_SCORE = MIN_ITEM_SCORE_DEFAULT  # 兼容旧引用


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


# ------------------------------------------------------------------ 单条打分

def score_item(it: Item) -> Item:
    text = it.text
    if not text:
        it.demand = 0.0
        return it

    hits = tu.pain_hits(text)
    signals: List[str] = []
    per_tag: Dict[str, float] = defaultdict(float)
    for tag, frag, w in hits:
        signals.append(f"{tag}:{frag}")
        per_tag[tag] = max(per_tag[tag], w)

    signal_sum = sum(per_tag.values())
    pay_sum = sum(w for t, w in per_tag.items() if t in PAY_TAGS)
    urg = max([w for t, w in per_tag.items() if t in URGENCY_TAGS] or [0.0])

    doms = tu.domain_matches(text)
    it.keywords = [k for k, _ in doms] + [w for w in tu.top_terms(text, 4) if w not in {k for k, _ in doms}]
    it.categories = list(dict.fromkeys(d.get("cat", "通用") for _, d in doms))[:3]
    if not it.lang or it.lang == "zh":
        it.lang = tu.detect_lang(text)

    # 文本质量系数：过短的信息量低
    n = len(text)
    quality = 1.0 if n >= 60 else (0.85 if n >= 25 else 0.6)

    explicit = pain_from_tags(per_tag)
    # 隐含需求：搜索下拉词 / 差评 / 需求句式检索出来的内容，本身就自带需求意图
    # 以配置里的「源先验」为准（sources.yaml → source_prior），采集器里的值只做兼容回退
    prior = tu.source_prior(it.source, it.prior if it.prior is not None else 0.45)
    it.prior = prior
    implicit = prior * 80.0

    base = clamp(signal_sum / 7.0)
    pay_r = clamp(pay_sum / 4.0)
    heat = clamp(it.heat)
    dom_bonus = 0.08 if doms else 0.0

    raw = 0.52 * base + 0.16 * pay_r + 0.12 * prior + 0.12 * heat + dom_bonus
    # 没任何痛点信号、源先验又不高的（资讯/热榜/屏幕残渣），基本只是背景噪音
    if signal_sum <= 0 and prior < 0.6:
        raw *= 0.35
    # pain 用于主题聚合：取"显式痛点"与"源先验隐含需求"的较大值
    it.pain = round(max(explicit, implicit), 2)
    it.pay = round(pay_r * 100, 2)
    it.urgency = round(clamp(urg / 1.5) * 100, 2)
    it.demand = round(clamp(raw) * MAX_ITEM_SCORE * clamp(it.weight, 0.5, 1.6) * quality, 2)
    it.signals = signals[:8]
    return it


def pain_from_tags(per_tag: Dict[str, float]) -> float:
    """把命中的标签集合折算成 0-100 的痛感"""
    if not per_tag:
        return 0.0
    s = sum(per_tag.values())
    kinds = len(per_tag)
    return clamp(s / 6.0 * 0.75 + kinds / 4.0 * 0.25) * 100


# ------------------------------------------------------------------ 主题聚合

def _mat_of(entries: Sequence[dict]) -> int:
    if not entries:
        return 1
    return int(min(e.get("mat", 1) for e in entries))


def _money_for(doms: Sequence[Tuple[str, dict]], cats: Sequence[str]) -> str:
    cfg = keywords_cfg()
    if doms:
        m = doms[0][1].get("money")
        if m:
            return m
    cmap = cfg.get("category_money") or {}
    for c in cats:
        if c in cmap:
            return cmap[c]
    return cmap.get("通用", "先做最小可用版本，定价 ¥19.9-99，用 3 个渠道测意向")


def build_topics(items: Sequence[Item], now: datetime | None = None) -> List[Topic]:
    """把素材聚成需求主题"""
    now = now or datetime.now(timezone.utc)
    cfg = keywords_cfg()
    playbook: List[str] = cfg.get("validation_playbook") or []

    buckets: Dict[str, List[Item]] = defaultdict(list)
    bucket_dom: Dict[str, Tuple[str, dict]] = {}
    longtail: List[Item] = []

    for it in items:
        if it.demand < min_item_score():
            continue
        doms = tu.domain_matches(it.text)
        # 通用词（工具/软件/ai …）不做主键，太泛了
        doms = [(k, d) for k, d in doms if not tu.is_generic(k)]
        if doms:
            key_kw, key_dom = doms[0]
            canon = tu.canonical(key_kw, key_dom)
            bkey = f"dom::{canon}"
            bucket_dom[bkey] = (canon, key_dom)
        else:
            # 纯英文碎片很难形成可执行的中文市场主题，只留中文词
            terms = [
                t for t in tu.top_terms(it.text, 4, prefer_cjk=True)
                if not tu.is_generic(t) and tu.has_cjk(t)
            ]
            if not terms:
                longtail.append(it)
                continue
            bkey = f"term::{terms[0]}"
        buckets[bkey].append(it)

    # 只剩一两条的 term 桶合并进"长尾信号"
    topics: List[Topic] = []

    for bkey, group in list(buckets.items()):
        if bkey.startswith("term::") and len(group) < 3:
            longtail.extend(group)
            buckets.pop(bkey, None)
            continue
        topics.append(_make_topic(bkey, group, bucket_dom.get(bkey), playbook, now))

    if longtail:
        topics.append(_make_topic("term::长尾信号", longtail[:200], None, playbook, now, is_longtail=True))

    topics.sort(key=lambda t: -t.score)
    # 零散长尾放在最后（它是等归类的池子，不是机会）
    topics = [t for t in topics if not t.slug.endswith("长尾信号")] + [
        t for t in topics if t.slug.endswith("长尾信号")
    ]
    for i, t in enumerate(topics, 1):
        t.rank = i  # type: ignore[attr-defined]
    return topics


def _make_topic(
    bkey: str,
    group: List[Item],
    dom: Tuple[str, dict] | None,
    playbook: List[str],
    now: datetime,
    is_longtail: bool = False,
) -> Topic:
    group = sorted(group, key=lambda x: -x.demand)
    cats = Counter(c for it in group for c in it.categories)
    primary_cat = cats.most_common(1)[0][0] if cats else "通用"

    kw_counter: Counter[str] = Counter()
    for it in group:
        for k in it.keywords[:6]:
            if k and not tu.is_generic(k):
                kw_counter[k] += 1
    # 领域关键词加权，让它排前面
    if dom:
        kw_counter[dom[0]] += len(group)
    keywords = [k for k, _ in kw_counter.most_common(8)]

    sources = Counter(it.source for it in group)
    sources = Counter(it.source for it in group)
    n = len(group)
    # 很多源（百度联想/热榜）天然没作者，缺失部分按一半权重估算独立人
    named = len({it.author.strip() for it in group if it.author.strip()})
    unnamed = n - sum(1 for it in group if it.author.strip())
    authors = max(1, named + round(unnamed * 0.5))
    n = len(group)

    pain = sum(it.pain for it in group) / n / 100
    pay = sum(it.pay for it in group) / n / 100
    urg = sum(it.urgency for it in group) / n / 100
    heat = sum(clamp(it.heat) for it in group) / n

    evidence = clamp(math.log1p(n) / math.log1p(30))
    div = 0.6 * clamp(len(sources) / 3.0) + 0.4 * clamp(authors / 12.0)
    stamps = [parse_ts(it.ts) for it in group]
    stamps = [s for s in stamps if s]
    first_seen = min(stamps).isoformat() if stamps else ""
    last_seen = max(stamps).isoformat() if stamps else ""
    age_days = (now - max(stamps)).days if stamps else 30
    recency = math.exp(-max(0, age_days) / 21.0)

    # 趋势：近 7 天 vs 前 7 天
    recent = sum(1 for s in stamps if (now - s).days <= 7)
    prev = sum(1 for s in stamps if 7 < (now - s).days <= 14)
    growth = (recent - prev) / max(1, prev + recent) if (recent + prev) else 0.0
    trend = 1.0 + 0.3 * clamp(growth, -0.5, 1.0)

    raw = (
        0.38 * pain
        + 0.20 * pay
        + 0.09 * urg
        + 0.13 * evidence
        + 0.11 * div
        + 0.05 * heat
        + 0.04 * recency
    )
    # 没有需求信号的主题基本不值得看
    gate_signal = 0.30 + 0.70 * clamp(pain / 0.5)
    # 证据只有一两条的主题先标记为待验证，不排前面
    gate_evidence = 0.45 + 0.55 * evidence
    score = clamp(raw) * 100 * gate_signal * gate_evidence * trend
    if dom and dom[1].get("mat", 1) == 0:
        score *= 1.08                      # 蓝海加成
    score = min(100.0, score)

    label_kw = tu.canonical(dom[0], dom[1]) if dom else (keywords[0] if keywords else "未分类")
    if is_longtail:
        label = "零散需求信号 · 待归类"
        score = min(score, 25.0)
    elif dom:
        label = f"{label_kw} · {primary_cat}"
    else:
        label = f"{bkey.split('::', 1)[-1]} · 长尾"
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", bkey)[:60]
    samples = [
        {
            "source": it.source,
            "author": it.author,
            "url": it.url,
            "ts": it.ts,
            "text": tu.snippet(it.text, keywords[0] if keywords else "", 110),
            "score": it.demand,
        }
        for it in group[:4]
    ]

    mat = _mat_of([dom[1]] if dom else [])
    money = _money_for([dom] if dom else [], [primary_cat])
    money = f"[{MAT_LABEL.get(mat, '')}] {money}"

    return Topic(
        slug=slug,
        label=label,
        keywords=keywords,
        categories=[c for c, _ in cats.most_common(3)],
        item_ids=[it.key_id for it in group],   # 占位，落库前会换成 DB id
        sources=dict(sources),
        authors=authors,
        score=round(score, 1),
        pain=round(pain * 100, 1),
        pay=round(pay * 100, 1),
        urgency=round(urg * 100, 1),
        diversity=round(div * 100, 1),
        heat=round(heat * 100, 1),
        first_seen=first_seen,
        last_seen=last_seen,
        money=money,
        validation=playbook[:3],
        samples=samples,
    )


def parse_ts(s: str) -> datetime | None:
    if not s:
        return None
    t = s.replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            d = datetime.fromisoformat(t) if fmt is None else datetime.strptime(t, fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def filter_topics(topics: Sequence[Topic], min_items: int = 2, min_score: float = 0.0) -> List[Topic]:
    """统一过滤：证据太少的先当待验证，不进入主榜"""
    out = [t for t in topics if len(t.item_ids) >= min_items and t.score >= min_score]
    out.sort(key=lambda t: -t.score)
    return out


def min_topic_items() -> int:
    cfg = keywords_cfg()
    return int((cfg.get("thresholds") or {}).get("min_topic_items", 2))


# ------------------------------------------------------------------ 辅助：机会卡

def opportunity_brief(t: Topic) -> str:
    """把主题变成一句话可执行结论"""
    tone = "强" if t.score >= 55 else ("中" if t.score >= 35 else "弱")
    paytone = "有付费信号" if t.pay >= 25 else ("偶有付费信号" if t.pay >= 10 else "暂未见付费信号")
    return (
        f"[{tone}] {t.label}｜证据 {len(t.item_ids)} 条 / 来源 {len(t.sources)} 个｜"
        f"痛感 {t.pain:.0f}·{paytone}·多样性 {t.diversity:.0f}｜{t.money}"
    )
