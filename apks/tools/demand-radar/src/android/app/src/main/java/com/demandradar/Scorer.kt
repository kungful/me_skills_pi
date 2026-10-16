package com.demandradar

import java.util.concurrent.TimeUnit
import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.max
import kotlin.math.min

/**
 * 需求打分与主题聚合引擎（手机端，算法与电脑端 demand_radar/score.py 一致）
 *
 * 单条素材 demand(0-100)：
 *   0.52*痛点信号 + 0.16*付费意愿 + 0.12*源先验 + 0.12*热度 + 0.08*命中领域词
 *   × 源权重 × 文本质量
 * 主题分(0-100)：痛点/证据/多样性/付费/新鲜度/趋势，再过两道闸门
 */
object Scorer {

    private val PAY_TAGS = setOf("付费意愿", "预算明确", "价格询问")
    private val URGENCY_TAGS = setOf("紧迫")

    const val MAX_ITEM_SCORE = 100.0

    fun clamp(x: Double, lo: Double = 0.0, hi: Double = 1.0) = max(lo, min(hi, x))

    // ------------------------------------------------------------ 单条打分

    fun scoreItem(it: Item, lex: Lexicon): Item {
        val text = it.text
        if (text.isBlank()) {
            it.demand = 0.0
            return it
        }

        val signals = ArrayList<String>()
        val perTag = HashMap<String, Double>()
        for ((tag, frag, w) in lex.painHits(text)) {
            signals.add("$tag:$frag")
            perTag[tag] = max(perTag[tag] ?: 0.0, w)
        }

        val signalSum = perTag.values.sum()
        val paySum = perTag.entries.filter { it.key in PAY_TAGS }.sumOf { it.value }
        val urg = perTag.entries.filter { it.key in URGENCY_TAGS }.maxOfOrNull { it.value } ?: 0.0

        val doms = lex.domainMatches(text)
        it.keywords = doms.map { it.first }
        it.categories = doms.map { it.second.cat }.distinct().take(3)
        it.lang = if (text.take(400).count { it.code in 0x4E00..0x9FFF } >= 8) "zh" else "en"

        // 太短的信息量低
        val n = text.length
        val quality = if (n >= 60) 1.0 else if (n >= 25) 0.85 else 0.6

        val prior = lex.sourcePrior(it.source, it.prior)
        it.prior = prior

        val explicit = painFromTags(perTag)
        val implicit = prior * 80.0

        val base = clamp(signalSum / 7.0)
        val payR = clamp(paySum / 4.0)
        val heat = clamp(it.heat)
        val domBonus = if (doms.isNotEmpty()) 0.08 else 0.0

        var raw = 0.52 * base + 0.16 * payR + 0.12 * prior + 0.12 * heat + domBonus
        // 没痛点信号、源先验又不高的（登录页/热榜/屏幕残渣）只是背景噪音
        if (signalSum <= 0.0 && prior < 0.6) raw *= 0.35

        it.pain = round2(max(explicit, implicit))
        it.pay = round2(payR * 100)
        it.urgency = round2(clamp(urg / 1.5) * 100)
        it.demand = round2(clamp(raw) * MAX_ITEM_SCORE * clamp(it.weight, 0.5, 1.6) * quality)
        it.signals = signals.take(8)
        return it
    }

    private fun painFromTags(perTag: Map<String, Double>): Double {
        if (perTag.isEmpty()) return 0.0
        val s = perTag.values.sum()
        val kinds = perTag.size
        return clamp(s / 6.0 * 0.75 + kinds / 4.0 * 0.25) * 100
    }

    // ------------------------------------------------------------ 主题聚合

    fun buildTopics(items: List<Item>, lex: Lexicon, now: Long = System.currentTimeMillis()): List<Topic> {
        val buckets = LinkedHashMap<String, MutableList<Item>>()
        val bucketDom = HashMap<String, Pair<String, Domain>>()
        val longtail = ArrayList<Item>()

        for (it in items) {
            if (it.demand < lex.minItemScore) continue
            val doms = lex.domainMatches(it.text).filter { !lex.isGeneric(it.first) }
            if (doms.isNotEmpty()) {
                val (kw, dom) = doms.first()
                val canon = dom.canonical
                buckets.getOrPut("dom::$canon") { ArrayList() }.add(it)
                bucketDom["dom::$canon"] = canon to dom
            } else {
                // 手机端没有分词器：认不出领域的统一进「零散信号」，不硬造主题
                longtail.add(it)
            }
        }

        val topics = ArrayList<Topic>()
        for ((bkey, group) in buckets) {
            topics.add(makeTopic(bkey, group, bucketDom[bkey], lex, now))
        }
        if (longtail.isNotEmpty()) {
            topics.add(makeTopic("term::长尾信号", longtail.take(200), null, lex, now, isLongtail = true))
        }

        topics.sortByDescending { it.score }
        // 零散长尾是待归类池子，不是机会，永远排最后
        val out = topics.filter { !it.slug.endsWith("长尾信号") } + topics.filter { it.slug.endsWith("长尾信号") }
        out.forEachIndexed { i, t -> t.rank = i + 1 }
        return out
    }

    private fun makeTopic(
        bkey: String,
        groupIn: List<Item>,
        dom: Pair<String, Domain>?,
        lex: Lexicon,
        now: Long,
        isLongtail: Boolean = false,
    ): Topic {
        val group = groupIn.sortedByDescending { it.demand }
        val cats = group.flatMap { it.categories }.groupingBy { it }.eachCount()
        val primaryCat = cats.maxByOrNull { it.value }?.key ?: "通用"

        val kwCount = HashMap<String, Int>()
        for (it in group) for (k in it.keywords.take(6)) if (!lex.isGeneric(k)) kwCount[k] = (kwCount[k] ?: 0) + 1
        dom?.let { kwCount[it.first] = (kwCount[it.first] ?: 0) + group.size }
        val keywords = kwCount.entries.sortedByDescending { it.value }.map { it.key }.take(8)

        val sources = group.groupingBy { it.source }.eachCount()
        val n = group.size
        val named = group.count { it.author.isNotBlank() }
        val unnamed = n - named
        // 很多源天然没作者（搜索联想/热榜），缺失部分按一半权重估算独立人
        val authors = max(1, named + Math.round(unnamed * 0.5).toInt())

        val pain = group.sumOf { it.pain } / n / 100
        val pay = group.sumOf { it.pay } / n / 100
        val urg = group.sumOf { it.urgency } / n / 100
        val heat = group.sumOf { clamp(it.heat) } / n

        val evidence = clamp(ln(1.0 + n) / ln(31.0))
        val div = 0.6 * clamp(sources.size / 3.0) + 0.4 * clamp(authors / 12.0)

        val stamps = group.map { it.ts }.filter { it > 0 }
        val firstSeen = stamps.minOrNull() ?: 0L
        val lastSeen = stamps.maxOrNull() ?: 0L
        val ageDays = if (stamps.isEmpty()) 30.0 else dayDiff(now, lastSeen)
        val recency = exp(-max(0.0, ageDays) / 21.0)

        val recent = stamps.count { dayDiff(now, it) <= 7 }
        val prev = stamps.count { dayDiff(now, it) in 7.01..14.0 }
        val growth = if (recent + prev > 0) (recent - prev).toDouble() / (prev + recent) else 0.0
        val trend = 1.0 + 0.3 * clamp(growth, -0.5, 1.0)

        val raw = 0.38 * pain + 0.20 * pay + 0.09 * urg + 0.13 * evidence +
            0.11 * div + 0.05 * heat + 0.04 * recency
        val gateSignal = 0.30 + 0.70 * clamp(pain / 0.5)      // 没需求信号的不值得看
        val gateEvidence = 0.45 + 0.55 * evidence             // 只有一两条证据的先当待验证
        var score = clamp(raw) * 100 * gateSignal * gateEvidence * trend
        if (dom?.second?.isBlueOcean == true) score *= 1.08   // 蓝海加成
        score = min(100.0, score)

        val label: String
        if (isLongtail) {
            label = "零散需求信号 · 待归类"
            score = min(score, 25.0)
        } else if (dom != null) {
            label = "${dom.first} · $primaryCat"
        } else {
            label = "${bkey.substringAfter("::")} · 长尾"
        }

        val slug = bkey.replace(Regex("[^\\w\\u4e00-\\u9fff]+"), "-").take(60)
        val sampleTerm = keywords.firstOrNull() ?: ""
        val samples = group.take(4).map {
            Sample(it.source, it.author, it.url, it.ts, snippet(it.text, sampleTerm, 110), it.demand)
        }

        val mat = dom?.second?.mat ?: 1
        val money = "[${MAT_LABEL[mat] ?: ""}] " + lex.moneyFor(listOfNotNull(dom), listOf(primaryCat))

        return Topic(
            slug = slug,
            label = label,
            keywords = keywords,
            categories = cats.entries.sortedByDescending { it.value }.map { it.key }.take(3),
            itemIds = group.map { it.keyId },
            sources = sources,
            authors = authors,
            score = round1(score),
            pain = round1(pain * 100),
            pay = round1(pay * 100),
            urgency = round1(urg * 100),
            diversity = round1(div * 100),
            heat = round1(heat * 100),
            firstSeen = firstSeen,
            lastSeen = lastSeen,
            money = money,
            validation = lex.playbook.take(3),
            samples = samples,
        )
    }

    /** 证据太少的先当待验证，不进入主榜 */
    fun filterTopics(topics: List<Topic>, minItems: Int, minScore: Double = 0.0): List<Topic> =
        topics.filter { it.itemIds.size >= minItems && it.score >= minScore }.sortedByDescending { it.score }

    // ------------------------------------------------------------ 小工具

    private fun dayDiff(a: Long, b: Long): Double =
        (a - b).toDouble() / TimeUnit.DAYS.toMillis(1).toDouble()

    private fun round1(x: Double) = Math.round(x * 10.0) / 10.0
    private fun round2(x: Double) = Math.round(x * 100.0) / 100.0

    fun snippet(text: String, term: String = "", width: Int = 90): String {
        val t = text.replace("\n", " ").replace(Regex("[ \\t\\u00a0\\u3000]+"), " ").trim()
        if (term.isNotEmpty()) {
            val i = t.lowercase().indexOf(term.lowercase())
            if (i > 0) {
                val start = max(0, i - width / 3)
                return (if (start > 0) "…" else "") + t.substring(start, min(t.length, start + width)).trim() + "…"
            }
        }
        return t.take(width).trim() + if (t.length > width) "…" else ""
    }
}
