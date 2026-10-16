package com.guantianxia.app.net

import com.guantianxia.app.data.Category
import java.util.Calendar

/**
 * 网页列表抓取（RSS 停更的站点靠这个兜底）。
 *
 * 目前只有一个站点：观察者网。它的 RSS 只吐首页 HTML，
 * 但频道页结构很规整，链接自带栏目和日期：
 *   /JunShi/2026_10_02_903033.shtml
 */
object HtmlList {

    /** 链接形如 /ZhengZhi/2026_10_02_903033.shtml，正则可直接切出栏目和日期 */
    private val GC_LINK = Regex(
        "<a[^>]+href=\"/([A-Za-z·]{2,20})/(\\d{4})_(\\d{2})_(\\d{2})_(\\d{2,9})\\.shtml\"[^>]*>(.*?)</a>",
        RegexOption.DOT_MATCHES_ALL
    )

    /** 栏目 → App 频道 */
    val COLUMN_CATEGORY = mapOf(
        "JunShi" to Category.MIL,
        // 「国际战略」其实是地缘政治评论，归国际；
        // 里面真正讲武器的那些查询时会被军事频道的关键词条件一并捞出来
        "GuoJi·ZhanLue" to Category.INTL,
        "ZhengZhi" to Category.POLITICS,
        "CaiJing" to Category.FINANCE,
        "TiYu" to Category.SPORTS
    )

    private val GC_URL = Regex("/([A-Za-z·]{2,20})/\\d{4}_\\d{2}_\\d{2}_\\d{2,9}\\.shtml")

    /** 从观察者网的详情页地址反推它属于哪个频道（老的库数据重算时用） */
    fun categoryOf(url: String): String? =
        GC_URL.find(url)?.let { COLUMN_CATEGORY[it.groupValues[1]] }

    fun guancha(html: String, limit: Int = 120): List<FeedParser.Raw> {
        val out = ArrayList<FeedParser.Raw>()
        val seen = HashSet<String>()
        val cal = Calendar.getInstance()
        var order = 0

        for (m in GC_LINK.findAll(html)) {
            val column = m.groupValues[1]
            val category = COLUMN_CATEGORY[column] ?: continue
            val year = m.groupValues[2].toIntOrNull() ?: continue
            val month = m.groupValues[3].toIntOrNull() ?: continue
            val day = m.groupValues[4].toIntOrNull() ?: continue

            val url = "https://www.guancha.cn/$column/" +
                "${m.groupValues[2]}_${m.groupValues[3]}_${m.groupValues[4]}_${m.groupValues[5]}.shtml"
            if (!seen.add(url)) continue

            val title = FeedParser.stripTags(m.groupValues[6])
            if (title.length < 6) continue

            // 链接里只有日期没有时刻，取当天中午；同一页按出现顺序（新→旧）
            // 逐条减一分钟，保证「最新在上」的顺序不被打乱
            cal.clear()
            cal.set(year, month - 1, day, 12, 0, 0)
            var ts = cal.timeInMillis - order * 60_000L
            order++
            if (ts <= 0L) ts = System.currentTimeMillis()

            out.add(FeedParser.Raw(title = title, link = url, desc = "", date = "", category = category, ts = ts))
            if (out.size >= limit) break
        }
        return out
    }
}
