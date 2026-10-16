package com.guantianxia.app.filter

import com.guantianxia.app.data.Category
import com.guantianxia.app.data.FeedSource

/**
 * 「重大新闻」判定 —— 和垃圾过滤是两件事：
 * JunkFilter 决定「要不要入库」，Importance 决定「值不值得打扰用户」。
 *
 * 只看标题（标题最能说明事件等级），分三档关键词加权，
 * 再叠加源信誉和质量分，最后跟阈值比。
 */
object Importance {

    /** 一档：级别最高，几乎都是头条 */
    private val TIER3 = listOf(
        "开战", "停火", "宣战", "空袭", "袭击", "爆炸", "地震", "海啸", "台风",
        "政变", "弹劾", "辞职", "当选", "下台", "坠毁", "遇袭", "核试验", "核泄漏",
        "崩盘", "熔断", "暴跌", "破产", "暴雷", "违约", "退市", "被查", "被捕",
        "降息", "加息", "降准", "利率决议", "制裁", "加征关税", "贸易战", "断供",
        "封杀", "封锁", "紧急状态", "撤离", "停飞", "暂停交易"
    )

    /** 二档：宏观/政策/资本市场大事 */
    private val TIER2 = listOf(
        "美联储", "欧洲央行", "日本央行", "央行", "国务院", "财政部", "证监会",
        "发改委", "统计局", "商务部", "白宫", "欧盟", "联合国", "北约", "国会",
        "通胀", "CPI", "PPI", "PMI", "非农", "GDP", "失业率", "利率", "汇率",
        "法案", "峰会", "协议", "谈判", "选举", "公投", "预算", "债务",
        "IPO", "上市", "并购", "重组", "回购", "财报", "营收", "净利", "市值",
        "历史新高", "历史新低", "大涨", "大跌", "涨停", "跌停", "拉升", "跳水"
    )

    /** 三档：行业/科技/大宗 */
    private val TIER1 = listOf(
        "A股", "港股", "美股", "人民币", "日元", "欧元", "美元指数",
        "芯片", "半导体", "光刻", "算力", "大模型", "人工智能", "机器人",
        "新能源", "光伏", "锂电", "储能", "电动车", "油价", "金价", "铜价",
        "比特币", "以太坊", "关税", "出口管制", "反垄断", "涨价", "降价",
        "发布会", "发射", "临床试验", "获批"
    )

    private const val TIER3_HIT = 34
    private const val TIER2_HIT = 17
    private const val TIER1_HIT = 7

    /** 外网源（英文标题）用词边界匹配，避免 "war" 命中 software/warning */
    private val TIER3_EN = listOf(
        "war", "invasion", "invade", "ceasefire", "airstrike", "air strike", "missile",
        "nuclear", "killed", "dead", "death toll", "explosion", "earthquake", "tsunami",
        "hurricane", "typhoon", "coup", "impeach", "resign", "election", "shot down",
        "attack", "sanction", "tariff", "state of emergency", "evacuat", "collapse",
        "bankrupt", "default", "halt", "downgrade", "rate cut", "rate hike", "layoff",
        "breach", "hack", "outage", "recall", "crash", "explode", "hostage", "strike"
    )

    private val TIER2_EN = listOf(
        "federal reserve", "central bank", "white house", "pentagon", "congress",
        "senate", "supreme court", "united nations", "nato", "inflation", "gdp",
        "unemployment", "summit", "treaty", "budget", "debt", "ipo", "merger",
        "acquisition", "earnings", "revenue", "record high", "record low", "surge",
        "plunge", "rally", "sell-off", "shutdown", "visa", "immigration", "quake"
    )

    private val TIER1_EN = listOf(
        "nvidia", "apple", "google", "microsoft", "meta", "tesla", "openai",
        "chip", "semiconductor", "artificial intelligence", "robot", "oil", "gold",
        "bitcoin", "crypto", "vaccine", "launch", "probe", "lawsuit"
    )

    private const val TIER3_EN_HIT = 30
    private const val TIER2_EN_HIT = 14
    private const val TIER1_EN_HIT = 6

    private fun enRegex(words: List<String>): Regex =
        Regex("\\b(?:" + words.joinToString("|") { Regex.escape(it) } + ")", RegexOption.IGNORE_CASE)

    private val RE3_EN = enRegex(TIER3_EN)
    private val RE2_EN = enRegex(TIER2_EN)
    private val RE1_EN = enRegex(TIER1_EN)

    /**
     * @param junkScore JunkFilter 给出的质量分（0..100）
     * @param sourceCount 同一事件有几个独立来源报道（学 AIHOT 的「参与方」信号）
     * @return 重要度 0..100
     */
    fun score(
        title: String,
        summary: String,
        source: FeedSource,
        junkScore: Int,
        sourceCount: Int = 0
    ): Int {
        val t = title

        // 源信誉打底（最高 33）
        var s = source.trust / 3

        // 关键词加权（最高 55）
        var hit = 0
        for (w in TIER3) if (t.contains(w)) hit += TIER3_HIT
        for (w in TIER2) if (t.contains(w)) hit += TIER2_HIT
        for (w in TIER1) if (t.contains(w)) hit += TIER1_HIT
        // 英文源：头版标题一般止有一个关键词，所以命中即算
        val en = title.lowercase()
        if (RE3_EN.containsMatchIn(en)) hit += TIER3_EN_HIT
        if (RE2_EN.containsMatchIn(en)) hit += TIER2_EN_HIT
        if (RE1_EN.containsMatchIn(en)) hit += TIER1_EN_HIT
        s += minOf(55, hit)

        // 有具体数字更像硬新闻
        if (t.count { it.isDigit() } >= 2) s += 5

        // 质量分高的额外加成，质量分很低的直接压制
        s += (junkScore - 70) / 3

        // 多家独立媒体报道 = 真大事（AIHOT 就是按「多少人在说」排热点的）
        if (sourceCount >= 3) s += 12 else if (sourceCount == 2) s += 6

        // 财经类天然更「值得通知」
        if (source.category == Category.FINANCE) s += 5
        if (source.category == Category.CN || source.category == Category.INTL) s += 2
        if (source.category == Category.MIL) s += 5
        if (source.category == Category.POLITICS) s += 3

        // 摘要里也出现一档关键词（标题外补充信号）
        if (summary.isNotEmpty()) {
            val tail = summary.take(160)
            for (w in TIER3) {
                if (tail.contains(w)) {
                    s += 8
                    break
                }
            }
        }

        return s.coerceIn(0, 100)
    }

    fun isImportant(score: Int, threshold: Int): Boolean = score >= threshold
}
