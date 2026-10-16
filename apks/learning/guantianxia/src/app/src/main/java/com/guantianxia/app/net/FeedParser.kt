package com.guantianxia.app.net

import android.util.Xml
import org.xmlpull.v1.XmlPullParser
import java.io.StringReader

/**
 * RSS 2.0 / Atom 通用解析（不依赖任何三方库）。
 */
object FeedParser {

    data class Raw(
        val title: String,
        val link: String,
        val desc: String,
        val date: String,
        /** 按条目覆盖频道（网页抓取用），空则用源自身的 */
        val category: String = "",
        /** 已经算好的时间戳（毫秒），>0 时直接用，不再解析 [date] */
        val ts: Long = 0L
    )

    fun parse(xml: String, limit: Int = 80): List<Raw> {
        val out = ArrayList<Raw>()
        val parser = Xml.newPullParser()
        try {
            parser.setFeature(XmlPullParser.FEATURE_PROCESS_NAMESPACES, false)
            parser.setInput(StringReader(xml))
        } catch (t: Throwable) {
            return out
        }

        var title = ""
        var link = ""
        var desc = ""
        var date = ""
        var inItem = false
        var tag: String? = null
        val sb = StringBuilder()

        try {
            var ev = parser.eventType
            while (ev != XmlPullParser.END_DOCUMENT) {
                when (ev) {
                    XmlPullParser.START_TAG -> {
                        val n = parser.name?.lowercase() ?: ""
                        if (n == "item" || n == "entry") {
                            inItem = true
                            title = ""; link = ""; desc = ""; date = ""
                        }
                        tag = if (inItem) n else null
                        sb.setLength(0)
                        if (inItem && n == "link" && link.isEmpty()) {
                            val href = parser.getAttributeValue(null, "href")
                            if (!href.isNullOrBlank()) link = href.trim()
                        }
                    }

                    XmlPullParser.TEXT, XmlPullParser.CDSECT -> {
                        if (inItem && tag != null) sb.append(parser.text ?: "")
                    }

                    XmlPullParser.END_TAG -> {
                        val n = parser.name?.lowercase() ?: ""
                        if (inItem) {
                            val text = sb.toString()
                            when (n) {
                                "title" -> if (title.isEmpty()) title = text.trim()
                                "link" -> if (link.isEmpty()) link = text.trim()
                                "description", "summary", "content", "encoded" ->
                                    if (desc.isEmpty()) desc = text
                                "pubdate", "published", "updated", "date", "issued" ->
                                    if (date.isEmpty()) date = text.trim()
                            }
                            if (n == "item" || n == "entry") {
                                inItem = false
                                if (title.isNotEmpty() && link.isNotEmpty() && isHttp(link)) {
                                    out.add(
                                        Raw(
                                            title = stripTags(title),
                                            link = link,
                                            desc = stripTags(desc),
                                            date = date
                                        )
                                    )
                                }
                            }
                        }
                        tag = null
                    }
                }
                if (out.size >= limit) break
                ev = parser.next()
            }
        } catch (t: Throwable) {
            // XML 截断是常态，能解析多少算多少
        }
        return out
    }

    private fun isHttp(u: String): Boolean =
        u.startsWith("http://") || u.startsWith("https://")

    /** 去 HTML 标签 + 解码常用实体 + 压空白 */
    fun stripTags(s: String): String {
        if (s.isEmpty()) return ""
        var t = s
        if (t.contains('<')) t = t.replace(Regex("<[^>]{0,400}>"), " ")
        t = t.replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&quot;", "\"")
            .replace("&#39;", "'")
            .replace("&apos;", "'")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&hellip;", "…")
            .replace("&mdash;", "—")
            .replace("&ldquo;", "“")
            .replace("&rdquo;", "”")
        t = t.replace(Regex("&#(\\d{2,5});")) { m ->
            val code = m.groupValues[1].toIntOrNull() ?: 0
            if (code > 0) String(Character.toChars(code)) else ""
        }
        t = t.replace(Regex("\\s+"), " ").trim()
        return t
    }
}
