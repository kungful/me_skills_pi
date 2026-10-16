package com.guantianxia.app.filter

import com.guantianxia.app.data.FeedSource

/**
 * 垃圾新闻过滤：规则打分，0 分最垃圾，100 分最干净。
 * 分数低于阈值直接不入库。
 *
 * 打分维度：
 *   1. 源信誉（基础分）
 *   2. 标题党特征扣分
 *   3. 广告/导流扣分
 *   4. 违法/博彩/荐股等硬垃圾直接 0 分
 *   5. 有具体数字、机构名、财经术语加分（说明是真新闻）
 */
object JunkFilter {

    private val CLICKBAIT = listOf(
        "震惊", "惊呆", "万万没想到", "不看后悔", "速看", "太可怕", "吓人",
        "揭秘", "内幕", "刚刚", "突发", "炸了", "疯传", "删前", "真相是",
        "厉害了", "笑死", "必看", "慎入", "全网都在", "刷屏", "曝光"
    )

    private val SPAM = listOf(
        "优惠券", "点击领取", "限时秒杀", "加微信", "代购", "兼职", "日赚",
        "返利", "免费领取", "扫码", "私聊", "推广", "广告", "福利群",
        "关注公众号", "点击购买", "折扣", "拼单", "砍价"
    )

    /** 命中即判定为垃圾（垃圾信息/违法违规） */
    private val HARD_BLOCK = listOf(
        "博彩", "赌场", "彩票代", "配资", "稳赚不赔", "加群领", "荐股群",
        "内幕消息股", "裸聊", "成人", "壮阳", "办证"
    )

    /** 真实新闻的强特征 */
    private val REAL_HINT = listOf(
        "央行", "证监会", "财政部", "发改委", "统计局", "商务部", "工信部",
        "美联储", "欧洲央行", "日本央行", "国务院", "白宫", "欧盟",
        "GDP", "CPI", "PPI", "PMI", "降息", "加息", "降准", "汇率", "关税",
        "A股", "港股", "美股", "债市", "基金", "IPO", "财报", "营收", "净利",
        "市值", "通胀", "失业率", "出口", "进口", "并购", "融资",
        "人工智能", "半导体", "芯片", "新能源", "算力", "大模型", "开源",
        "法案", "选举", "峰会", "协议", "制裁", "停火", "发射"
    )

    /**
     * @return 0..100，越高越正常
     */
    fun score(title: String, summary: String, source: FeedSource): Int {
        val t = title.trim()
        val s = summary.trim()
        for (k in HARD_BLOCK) {
            if (t.contains(k) || s.contains(k)) return 0
        }

        var score = source.trust

        // 标题长度
        if (t.length < 8) score -= 45
        else if (t.length in 12..64) score += 4
        else if (t.length > 110) score -= 14

        // 标题党
        var cb = 0
        for (k in CLICKBAIT) if (t.contains(k)) cb++
        score -= cb * 18

        // 广告导流
        var sp = 0
        for (k in SPAM) if (t.contains(k) || s.contains(k)) sp++
        score -= sp * 30

        // 感叹号/问号堆叠
        val punct = t.count { it == '！' || it == '？' || it == '!' || it == '?' }
        if (punct >= 2) score -= 15

        // 有具体数字 = 更像真新闻
        if (t.count { it.isDigit() } >= 2) score += 6

        // 财经/时政术语
        var hint = 0
        for (k in REAL_HINT) if (t.contains(k)) hint++
        if (hint > 0) score += minOf(10, hint * 5)

        // 没有摘要说明源里信息量低
        if (s.isEmpty()) score -= 8

        // 全大写英文（英文源标题党常见特征）
        val letters = t.count { it.isLetter() }
        if (letters > 12) {
            val upper = t.count { it.isUpperCase() }
            if (upper.toDouble() / letters > 0.7) score -= 12
        }

        return score.coerceIn(0, 100)
    }

    fun isJunk(score: Int, threshold: Int): Boolean = score < threshold

    /** 给界面用的可读标签 */
    fun label(score: Int): String = when {
        score >= 85 -> "优质"
        score >= 70 -> "正常"
        score >= 55 -> "一般"
        else -> "存疑"
    }
}
