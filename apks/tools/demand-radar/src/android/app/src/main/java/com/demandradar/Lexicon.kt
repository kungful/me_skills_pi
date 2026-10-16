package com.demandradar

import android.content.Context
import org.json.JSONObject
import java.util.regex.Pattern

/** 一个需求领域（赛道） */
class Domain(
    val keys: List<String>,
    val cat: String,
    val money: String?,
    val mat: Int,
) {
    /** 标准名：取词典第一个别名，标签更干净 */
    val canonical: String get() = keys.firstOrNull() ?: "未分类"
    val isBlueOcean: Boolean get() = mat == 0
}

/** 痛点信号 */
class Pain(val pattern: Pattern, val tag: String, val weight: Double)

/**
 * 词典：与电脑端 config/keywords.yaml 完全同源（由 tools/export_keywords 生成 JSON）。
 * 打分完全不需要分词器，所以手机端可以 1:1 复刻电脑端的算法。
 */
class Lexicon private constructor(private val json: JSONObject) {

    val generic: Set<String> =
        json.optJSONArray("generic_primary").toStringList().map { it.lowercase() }.toSet()

    val pains: List<Pain> = buildList {
        val arr = json.optJSONArray("pain_patterns") ?: return@buildList
        for (i in 0 until arr.length()) {
            val o = arr.optJSONObject(i) ?: continue
            val re = o.optString("re")
            if (re.isEmpty()) continue
            try {
                add(Pain(Pattern.compile(re, Pattern.CASE_INSENSITIVE), o.optString("tag", "信号"), o.optDouble("w", 1.0)))
            } catch (_: Exception) {
                // 个别 PCRE 语法 Java 不认，跳过即可
            }
        }
    }

    val domains: List<Domain> = buildList {
        val arr = json.optJSONArray("domains") ?: return@buildList
        for (i in 0 until arr.length()) {
            val o = arr.optJSONObject(i) ?: continue
            val keys = o.optJSONArray("k").toStringList()
            if (keys.isEmpty()) continue
            add(Domain(keys, o.optString("cat", "通用"), o.optString("money").ifEmpty { null }, o.optInt("mat", 1)))
        }
    }

    /** (小写关键词, 领域)，长词在前，避免「记账」抢掉「记账app」 */
    private val index: List<Pair<String, Domain>> =
        domains.flatMap { d -> d.keys.map { it.lowercase() to d } }.sortedByDescending { it.first.length }

    val priors: Map<String, Double> = json.optJSONObject("source_prior").toStringDoubleMap()
    val money: Map<String, String> = json.optJSONObject("category_money").toStringStringMap()
    val apps: Map<String, String> = json.optJSONObject("apps").toStringStringMap()
    val playbook: List<String> = json.optJSONArray("validation_playbook").toStringList()
    val minTopicItems: Int = json.optJSONObject("thresholds")?.optInt("min_topic_items", 2) ?: 2
    val minItemScore: Double =
        json.optJSONObject("thresholds")?.optDouble("min_item_score", 12.0) ?: 12.0

    // ---------------------------------------------------------------- 匹配

    fun isGeneric(kw: String) = kw.lowercase() in generic

    fun sourcePrior(source: String, fallback: Double = 0.45) = priors[source] ?: fallback

    private fun hit(kw: String, low: String): Boolean =
        if (ASCII_KW.matcher(kw).matches()) {
            Pattern.compile("(?<![a-z0-9])" + Pattern.quote(kw) + "(?![a-z0-9])").matcher(low).find()
        } else {
            low.contains(kw)
        }

    /** 命中的领域：具体词优先，通用词排最后 */
    fun domainMatches(text: String, limit: Int = 6): List<Pair<String, Domain>> {
        val low = text.lowercase()
        val hits = ArrayList<Pair<String, Domain>>()
        val covered = ArrayList<String>()
        for ((kw, dom) in index) {
            if (!hit(kw, low)) continue
            if (covered.any { it.contains(kw) }) continue  // 「记账app」已覆盖「记账」
            covered.add(kw)
            hits.add(kw to dom)
        }
        hits.sortWith(
            compareBy({ isGeneric(it.first) }, { -it.first.length }, { it.second.mat }),
        )
        return hits.take(limit)
    }

    fun painHits(text: String): List<Triple<String, String, Double>> {
        val out = ArrayList<Triple<String, String, Double>>()
        for (p in pains) {
            val m = p.pattern.matcher(text)
            if (m.find()) {
                val frag = m.group().take(24)
                out.add(Triple(p.tag, frag, p.weight))
            }
        }
        return out
    }

    /** 话题的变现建议 */
    fun moneyFor(doms: List<Pair<String, Domain>>, cats: List<String>): String {
        doms.firstOrNull()?.second?.money?.let { return it }
        for (c in cats) money[c]?.let { return it }
        return money["通用"] ?: "先做最小可用版本，定价 ¥19.9-99，3 个渠道测意向"
    }

    companion object {
        private val ASCII_KW = Pattern.compile("^[a-z0-9][a-z0-9 +#._-]*$")

        @Volatile private var inst: Lexicon? = null

        fun get(ctx: Context): Lexicon = inst ?: synchronized(this) {
            inst ?: run {
                val text = ctx.assets.open("keywords.json").use { it.readBytes().decodeToString() }
                Lexicon(JSONObject(text)).also { inst = it }
            }
        }
    }
}

// ---------------------------------------------------------------- JSON 小工具

private fun org.json.JSONArray?.toStringList(): List<String> {
    if (this == null) return emptyList()
    val out = ArrayList<String>(length())
    for (i in 0 until length()) {
        val s = optString(i, "")
        if (s.isNotEmpty()) out.add(s)
    }
    return out
}

private fun org.json.JSONObject?.toStringStringMap(): Map<String, String> {
    if (this == null) return emptyMap()
    val out = HashMap<String, String>()
    for (k in keys()) out[k] = optString(k, "")
    return out
}

private fun org.json.JSONObject?.toStringDoubleMap(): Map<String, Double> {
    if (this == null) return emptyMap()
    val out = HashMap<String, Double>()
    for (k in keys()) out[k] = optDouble(k, 0.0)
    return out
}
