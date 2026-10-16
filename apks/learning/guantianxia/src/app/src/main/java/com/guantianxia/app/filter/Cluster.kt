package com.guantianxia.app.filter

import java.util.concurrent.TimeUnit

/**
 * 事件归组 + 热度 —— 思路来自 AIHOT（https://github.com/KKKKhazix/AIHOT ，MIT）。
 *
 * 原站的做法（见 `docs/grouping.md`）分两步：
 *   1. **召回**：用文字重合度或向量，从最近两周的资料里捞候选（`recall.ts` 的
 *      `lexicalSimilarity` 是字符二元组的 交集/较小集合，门槛 0.25）；
 *   2. **判定**：把这些候选交给大模型判断关系是 SAME_OCCURRENCE / SAME_STORY /
 *      UNRELATED（`relate.ts`）。
 *
 * 手机上没有大模型，所以只照搬第一步是不够的 —— 实测那样会把毫不相干的英文新闻
 * 聚成一堆（"in/on/th" 这种高频二元组人人都重合）。这里在召回之上补三条离线可判的硬约束，
 * 把「判定」这一步近似出来：
 *
 *   1. **同分类才归组**（体育不可能和政治是同一件事）；
 *   2. **稀有二元组**：先统计每个二元组在最近窗口内的文档频率，滤掉人人都有的噪声，
 *      只留 [DF_LO, DF_HI] 区间的；
 *   3. **必须共享实体名**：专有名词（Margaret Hamilton / Claude）、中文连续 3 字以上、
 *      数字（GPT-6 / 5.5）。同一件事必然共享，这件事是「换了个说法」的报道也能聚上，
 *      而 SimHash 那种标题指纹是抓不到的。
 *
 * 热度照搬 `hot.ts`：heat = Σ 0.5^(距今天数/24h)，48 小时内每个来源只计一次，
 * 参与方 ≥ 2 才进热点榜。
 */
object Cluster {

    /** 稀有二元组的重合率门槛（对 min 取比值） */
    const val MIN_SIM = 0.50

    /** 至少共享几个稀有二元组 */
    const val MIN_SHARED_GRAMS = 3

    /** 至少共享一个实体名 */
    const val MIN_SHARED_ENTITIES = 1

    /** 文档频率区间：太低是错别字/罕见串，太高是 "in/on/th" 这类噪声 */
    const val DF_LO = 0.004
    const val DF_HI = 0.20

    /** 归组与热度窗口：48 小时 */
    const val WINDOW_HOURS = 48

    /** 热度半衰期：24 小时 */
    const val HALF_LIFE_HOURS = 24.0

    /** 至少几个独立来源报道才算热点（AIHOT MIN_PARTICIPANTS） */
    const val MIN_PARTICIPANTS = 2

    /** 「旧文不刷屏」：超过 48 小时的报道不推送（AIHOT 同款规则） */
    const val FRESH_HOURS = 48

    const val HOUR_MS = 3600_000L
    val WINDOW_MS: Long = TimeUnit.HOURS.toMillis(WINDOW_HOURS.toLong())

    /** 事件里存实体集合的分隔符 */
    const val SEP = '\u0001'

    // ---------------------------------------------------------------- 基础算子

    /** 字符二元组（去掉空白和标点），中文不需要分词 */
    fun bigrams(s: String): Set<String> {
        val sb = StringBuilder(s.length)
        for (c in s) {
            if (c.isLetterOrDigit()) sb.append(c.lowercaseChar())
        }
        if (sb.length < 2) return emptySet()
        val out = HashSet<String>(sb.length * 2)
        for (i in 0 until sb.length - 1) out.add(sb.substring(i, i + 2))
        return out
    }

    /**
     * 交集 / min(|a|,|b|)。
     * 用 min 而不是并集：同一件事的报道标题长短差很多，Jaccard 会把它们判成不相关。
     */
    fun similarity(a: Set<String>, b: Set<String>): Double {
        if (a.isEmpty() || b.isEmpty()) return 0.0
        val small = if (a.size <= b.size) a else b
        val big = if (a.size <= b.size) b else a
        var inter = 0
        for (g in small) if (big.contains(g)) inter++
        return inter.toDouble() / small.size
    }

    private val STOP_EN = setOf(
        "The", "This", "That", "New", "Why", "How", "What", "When", "After", "From",
        "With", "And", "But", "For", "Its", "His", "Her", "You", "Are", "Was", "Not",
        "All", "One", "Two", "Best", "Top", "More", "Most", "Over", "Only", "Just",
        "Can", "Will", "Has", "Had", "Who", "Says", "Say", "Now", "Day", "Year",
        "First", "Last", "Next", "Still", "Even", "About", "Into", "Out", "Off"
    )

    private val WORD = Regex("[A-Za-z][A-Za-z0-9.\\-]{2,}")
    private val NUMBER = Regex("\\d+(?:\\.\\d+)?")

    /**
     * 实体名：专有名词 / 中文连续 3 字以上 / 数字。
     * 「同一件事」必然共享其中之一，这是最有效的离线判据。
     */
    fun entities(title: String): MutableSet<String> {
        val out = HashSet<String>(8)
        // 专有名词：首字母大写且不全是常见词
        for (m in WORD.findAll(title)) {
            val w = m.value
            if (w.length < 4) continue
            if (!w[0].isUpperCase()) continue
            if (STOP_EN.contains(w)) continue
            out.add(w.lowercase())
        }
        // 中文连续片段（≥3 字）
        var i = 0
        while (i < title.length) {
            if (isCjk(title[i])) {
                var j = i
                while (j < title.length && isCjk(title[j])) j++
                if (j - i >= 3) out.add(title.substring(i, j))
                i = j
            } else {
                i++
            }
        }
        // 数字：型号/版本/金额
        for (m in NUMBER.findAll(title)) {
            if (m.value.length >= 2) out.add(m.value)
        }
        return out
    }

    private fun isCjk(c: Char): Boolean = c.code in 0x4E00..0x9FFF

    /**
     * 文档频率剖面：先看一遍窗口内所有标题，才知道哪些二元组是「人人都有的噪声」。
     */
    class Profile(val total: Int, private val df: HashMap<String, Int>) {

        fun isRare(gram: String): Boolean {
            if (total <= 0) return true
            val ratio = (df[gram] ?: 0).toDouble() / total
            return ratio in DF_LO..DF_HI
        }

        /** 只留稀有二元组；全被滤掉时退回原集合（短标题不至于完全没法归组） */
        fun rare(grams: Set<String>): Set<String> {
            if (grams.isEmpty()) return grams
            val out = HashSet<String>(grams.size)
            for (g in grams) if (isRare(g)) out.add(g)
            return if (out.isEmpty()) grams else out
        }
    }

    /** 收集阶段：把窗口内所有标题喂进来，才知道哪些二元组是噪声 */
    class ProfileBuilder {
        private val df = HashMap<String, Int>()
        private var n = 0

        fun add(title: String) {
            n++
            for (g in bigrams(title)) df[g] = (df[g] ?: 0) + 1
        }

        fun build(): Profile = Profile(n, df)
    }

    // ---------------------------------------------------------------- 归组判定

    /**
     * 两条报道算不算同一件事。
     * 三条硬约束缺一不可：同分类、稀有二元组重合够多、共享实体名。
     */
    fun matches(
        catA: String, gramsA: Set<String>, entsA: Set<String>,
        catB: String, gramsB: Set<String>, entsB: Set<String>
    ): Boolean {
        if (catA != catB) return false
        if (gramsA.isEmpty() || gramsB.isEmpty()) return false

        // 1) 共享实体名（最有力的一条）
        if (entsA.isEmpty() || entsB.isEmpty()) return false
        var sharedEnt = 0
        val smallE = if (entsA.size <= entsB.size) entsA else entsB
        val bigE = if (entsA.size <= entsB.size) entsB else entsA
        for (e in smallE) if (bigE.contains(e)) {
            sharedEnt++
            if (sharedEnt >= MIN_SHARED_ENTITIES) break
        }
        if (sharedEnt < MIN_SHARED_ENTITIES) return false

        // 2) 稀有二元组重合数量 + 重合率
        val small = if (gramsA.size <= gramsB.size) gramsA else gramsB
        val big = if (gramsA.size <= gramsB.size) gramsB else gramsA
        var shared = 0
        for (g in small) if (big.contains(g)) shared++
        if (shared < MIN_SHARED_GRAMS) return false
        return shared.toDouble() / small.size >= MIN_SIM
    }

    // ---------------------------------------------------------------- 热度

    /**
     * 热度：每个来源在窗口内只按它最近一次报道算，按 24 小时半衰期衰减。
     * 报道它的来源越多、越新，分越高。
     */
    fun heat(times: List<Long>, now: Long): Double {
        var h = 0.0
        for (t in times) {
            val hours = (now - t).toDouble() / HOUR_MS
            if (hours <= 0) {
                h += 1.0
            } else if (hours < WINDOW_HOURS) {
                h += Math.pow(0.5, hours / HALF_LIFE_HOURS)
            }
        }
        return h
    }

    /** 热度换算成界面上那个 10 倍刻度（AIHOT 的 heatIndex） */
    fun heatIndex(heat: Double): Double = Math.round(heat * 100) / 10.0

    /** 是否算「新鲜」：用于「旧文不刷屏」 */
    fun isFresh(publishedAt: Long, now: Long): Boolean =
        publishedAt <= 0L || now - publishedAt <= TimeUnit.HOURS.toMillis(FRESH_HOURS.toLong())

    fun joinEnts(ents: Collection<String>): String = ents.joinToString(SEP.toString())

    fun splitEnts(s: String?): MutableSet<String> {
        if (s.isNullOrEmpty()) return HashSet()
        return s.split(SEP).filterTo(HashSet()) { it.isNotEmpty() }
    }
}
