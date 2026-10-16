package com.guantianxia.app.filter

/**
 * 64 位 SimHash：把标题压成一个指纹，汉明距离 <= 3 视为同一条新闻。
 * 用来干掉「同一件事被 8 家媒体转发」的刷屏。
 */
object SimHash {

    private const val FNV_OFFSET = -3750763034362895579L // 0xcbf29ce484222325
    private const val FNV_PRIME = 1099511628211L

    fun of(text: String): Long {
        val t = normalize(text)
        if (t.length < 2) return 0L
        val weights = IntArray(64)
        var i = 0
        while (i < t.length - 1) {
            val gram = t.substring(i, i + 2)
            val h = hash64(gram)
            var b = 0
            while (b < 64) {
                if ((h ushr b) and 1L == 1L) weights[b]++ else weights[b]--
                b++
            }
            i++
        }
        var out = 0L
        for (b in 0 until 64) {
            if (weights[b] > 0) out = out or (1L shl b)
        }
        return out
    }

    fun distance(a: Long, b: Long): Int = java.lang.Long.bitCount(a xor b)

    fun isDup(a: Long, b: Long, threshold: Int = 3): Boolean {
        if (a == 0L || b == 0L) return false
        return distance(a, b) <= threshold
    }

    /** 只保留字母、数字、汉字 */
    fun normalize(text: String): String {
        val sb = StringBuilder(text.length)
        for (ch in text) {
            when {
                ch.isLetterOrDigit() -> sb.append(ch.lowercaseChar())
                else -> Unit
            }
        }
        return sb.toString()
    }

    private fun hash64(s: String): Long {
        var h = FNV_OFFSET
        for (ch in s) {
            h = h xor ch.code.toLong()
            h *= FNV_PRIME
        }
        return h
    }
}
