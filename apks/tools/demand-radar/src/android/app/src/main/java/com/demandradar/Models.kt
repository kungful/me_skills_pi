package com.demandradar

import java.util.UUID

/** 一条需求素材（一屏文字 / 一条评论 / 一个 issue …） */
class Item(
    var source: String,
    var extId: String = "",
    var title: String = "",
    var body: String = "",
    var url: String = "",
    var author: String = "",
    var lang: String = "zh",
    var ts: Long = System.currentTimeMillis(),
    var weight: Double = 1.0,
    var heat: Double = 0.0,
    var prior: Double = 0.45,
) {
    var id: Long = 0
    val keyId: String = extId.ifEmpty { UUID.randomUUID().toString() }

    var demand: Double = 0.0
    var pain: Double = 0.0
    var pay: Double = 0.0
    var urgency: Double = 0.0
    var signals: List<String> = emptyList()
    var keywords: List<String> = emptyList()
    var categories: List<String> = emptyList()

    val text: String get() = listOf(title, body).filter { it.isNotBlank() }.joinToString("\n")
}

/** 一条证据样例 */
class Sample(
    val source: String,
    val author: String,
    val url: String,
    val ts: Long,
    val text: String,
    val score: Double,
)

/** 一个需求主题（机会） */
class Topic(
    val slug: String,
    val label: String,
    val keywords: List<String>,
    val categories: List<String>,
    val itemIds: List<String>,
    val sources: Map<String, Int>,
    val authors: Int,
    val score: Double,
    val pain: Double,
    val pay: Double,
    val urgency: Double,
    val diversity: Double,
    val heat: Double,
    val firstSeen: Long,
    val lastSeen: Long,
    val money: String,
    val validation: List<String>,
    val samples: List<Sample>,
) {
    var rank: Int = 0

    val evidence: Int get() = itemIds.size

    /** 一句话可执行结论 */
    fun brief(): String {
        val tone = if (score >= 55) "强" else if (score >= 35) "中" else "弱"
        val payTone = if (pay >= 25) "有付费信号" else if (pay >= 10) "偶有付费信号" else "暂未见付费信号"
        return "[$tone] $label ｜ 证据 ${itemIds.size} 条 / 来源 ${sources.size} 个 ｜ " +
            "痛感 ${pain.toInt()}·$payTone·多样性 ${diversity.toInt()} ｜ $money"
    }
}

val MAT_LABEL = mapOf(0 to "蓝海机会", 1 to "有竞争", 2 to "红海赛道")
