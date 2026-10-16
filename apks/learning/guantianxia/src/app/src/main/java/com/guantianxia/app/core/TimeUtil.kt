package com.guantianxia.app.core

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

object TimeUtil {

    private val RFC822 = listOf(
        "EEE, dd MMM yyyy HH:mm:ss Z",
        "EEE, dd MMM yyyy HH:mm:ss zzz",
        "EEE, dd MMM yyyy HH:mm Z",
        "EEE, dd MMM yyyy HH:mm:ss",
        "EEE MMM dd HH:mm:ss Z yyyy"
    )

    private val ISO = listOf(
        "yyyy-MM-dd'T'HH:mm:ssXXX",
        "yyyy-MM-dd'T'HH:mm:ss.SSSXXX",
        "yyyy-MM-dd'T'HH:mm:ss'Z'",
        "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'",
        "yyyy-MM-dd'T'HH:mm:ss",
        "yyyy-MM-dd HH:mm:ss",
        "yyyy/MM/dd HH:mm:ss",
        "yyyy/MM/dd HH:mm",
        "yyyy-MM-dd HH:mm",
        "yyyy-MM-dd"
    )

    /** 解析各种乱七八糟的时间格式，失败返回 0 */
    fun parse(raw: String?): Long {
        val s = raw?.trim().orEmpty()
        if (s.isEmpty()) return 0L
        for (p in RFC822) {
            parseWith(s, p, Locale.US)?.let { return it }
            parseWith(s, p, Locale.ENGLISH)?.let { return it }
        }
        val fixed = s.replace("Z", "+00:00").let {
            // "2026-10-02T12:00:00+00:00" -> SimpleDateFormat 支持 XXX，去掉末尾 : 的写法也支持
            it
        }
        for (p in ISO) {
            parseWith(s, p, Locale.US)?.let { return it }
            parseWith(fixed, p, Locale.US)?.let { return it }
        }
        // 只有日期+时间的纯数字
        s.toLongOrNull()?.let { v ->
            // 秒级时间戳
            if (v in 1_000_000_000L..4_000_000_000L) return v * 1000
            if (v > 1_000_000_000_000L) return v
        }
        return 0L
    }

    private fun parseWith(s: String, pattern: String, locale: Locale): Long? {
        return try {
            val f = SimpleDateFormat(pattern, locale)
            f.timeZone = TimeZone.getTimeZone("GMT")
            f.isLenient = true
            val d: Date = f.parse(s) ?: return null
            d.time
        } catch (t: Throwable) {
            null
        }
    }

    /** 相对时间：3分钟前 / 2小时前 / 昨天 / 09-28 */
    fun ago(ts: Long): String {
        if (ts <= 0L) return ""
        val diff = System.currentTimeMillis() - ts
        if (diff < 0) return "刚刚"
        val min = diff / 60_000
        if (min < 1) return "刚刚"
        if (min < 60) return "${min}分钟前"
        val hour = min / 60
        if (hour < 24) return "${hour}小时前"
        val day = hour / 24
        if (day == 1L) return "昨天"
        if (day < 7) return "${day}天前"
        return SimpleDateFormat("MM-dd", Locale.getDefault()).format(Date(ts))
    }

    fun nowText(): String =
        SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()).format(Date(System.currentTimeMillis()))
}
