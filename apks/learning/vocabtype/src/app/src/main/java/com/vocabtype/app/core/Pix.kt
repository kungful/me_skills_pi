package com.vocabtype.app.core

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.Handler
import android.os.Looper
import android.util.LruCache
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.security.MessageDigest
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors

/**
 * 单词配图：给每个词强行塞一张"尽量接近词义"的图，用视觉绑住记忆。
 *
 * 图源（都不需要 Key，实测可用）：
 *   1. 必应图片 `bing.com/images/async?q=<word>` —— 英文字面最准，抓 murl 原图
 *   2. 百度图片 `image.baidu.com/search/acjson?word=<word>` —— 国内快
 *
 * 策略：
 *   · 先查本地缓存（filesDir/pic/<sha1>.jpg），命中直接给位图；
 *   · 没有就后台下载，先落盘再解码，下次秒开；
 *   · 内存里再压一层 LruCache，滚动列表不卡；
 *   · 全部失败返回 null，界面显示占位符，绝不留白屏。
 *
 * 不把图片打进 APK 的原因：2114 个词 × ~40KB ≈ 80MB，安装包会爆。
 */
class Pix(private val ctx: Context) {

    companion object {
        private const val DIR = "pic"
        private const val CONNECT_MS = 6000
        private const val READ_MS = 12000
        private const val UA =
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        /** 百度图片 json 里的图片地址（raw string，避免转义地狱） */
        private val THUMB_RE = """"(?:thumbURL|middleURL)":"(https?://[^"]+)""""
    }

    private val handler = Handler(Looper.getMainLooper())
    private val dir = File(ctx.filesDir, DIR)
    private val pool = Executors.newFixedThreadPool(3)
    private val inflight = ConcurrentHashMap<String, Boolean>()
    private val dead = ConcurrentHashMap.newKeySet<String>()

    /** 内存缓存，按 1/8 可用内存取上限 */
    private val mem = object : LruCache<String, Bitmap>(
        (Runtime.getRuntime().maxMemory() / 8).toInt().coerceAtLeast(4 * 1024 * 1024)
    ) {
        override fun sizeOf(key: String, value: Bitmap): Int = value.byteCount
    }

    var netOn = true

    // ------------------------------------------------------------ 对外

    /** 同步读缓存（不联网），有就返回 */
    fun cached(word: String): Bitmap? {
        val k = sha1(word.lowercase().trim())
        mem.get(k)?.let { return it }
        val f = File(dir, "$k.jpg")
        if (!f.isFile || f.length() < 1024) return null
        val bmp = runCatching { BitmapFactory.decodeFile(f.absolutePath) }.getOrNull() ?: return null
        mem.put(k, bmp)
        return bmp
    }

    /** 异步取图：命中缓存立刻回调，否则下载后回调（主线程） */
    fun load(word: String, onBitmap: (Bitmap?) -> Unit) {
        if (word.isBlank()) {
            onBitmap(null)
            return
        }
        cached(word)?.let {
            onBitmap(it)
            return
        }
        val k = sha1(word.lowercase().trim())
        if (!netOn || dead.contains(k)) {
            onBitmap(null)
            return
        }
        if (inflight.putIfAbsent(k, true) != null) {
            // 已经在下了，稍后再查缓存
            handler.postDelayed({ load(word, onBitmap) }, 400L)
            return
        }
        pool.execute {
            val f = fetch(word, k)
            handler.post {
                inflight.remove(k)
                if (f == null) {
                    dead.add(k)
                    onBitmap(null)
                } else {
                    val bmp = runCatching { BitmapFactory.decodeFile(f.absolutePath) }.getOrNull()
                    if (bmp != null) mem.put(k, bmp)
                    onBitmap(bmp)
                }
            }
        }
    }

    /**
     * 播放器用：提前把后面几个词的图抓好，切词时几乎零空窗。
     * 单线程顺序抓，避免和正在播的那张抢带宽。
     */
    fun prefetchAhead(words: List<String>, from: Int, ahead: Int = 5) {
        if (!netOn || words.isEmpty()) return
        val todo = ArrayList<String>(ahead)
        var i = from
        var guard = 0
        while (todo.size < ahead && guard < words.size * 2) {
            val w = words[(i % words.size + words.size) % words.size]
            if (w.isNotBlank() && cached(w) == null && !dead.contains(sha1(w.lowercase().trim()))) {
                todo.add(w)
            }
            i++
            guard++
        }
        if (todo.isEmpty()) return
        pool.execute {
            for (w in todo) {
                val k = sha1(w.lowercase().trim())
                if (cached(w) != null || dead.contains(k)) continue
                if (inflight.putIfAbsent(k, true) == null) {
                    fetch(w, k)
                    inflight.remove(k)
                }
            }
        }
    }

    fun prefetch(word: String) {
        if (word.isBlank() || cached(word) != null) return
        val k = sha1(word.lowercase().trim())
        if (!netOn || dead.contains(k)) return
        if (inflight.putIfAbsent(k, true) != null) return
        pool.execute {
            fetch(word, k)
            inflight.remove(k)
        }
    }

    fun cacheCount(): Int = runCatching { dir.listFiles()?.count { it.length() > 1024 } ?: 0 }
        .getOrDefault(0)

    fun sizeBytes(): Long =
        runCatching { dir.listFiles()?.sumOf { it.length() } ?: 0L }.getOrDefault(0L)

    fun clearCache() {
        runCatching { dir.listFiles()?.forEach { it.delete() } }
        mem.evictAll()
        dead.clear()
    }

    fun shutdown() {
        runCatching { pool.shutdownNow() }
        mem.evictAll()
    }

    // ------------------------------------------------------------ 下载

    private fun sha1(s: String): String {
        val d = MessageDigest.getInstance("SHA-1").digest(s.toByteArray(Charsets.UTF_8))
        val sb = StringBuilder()
        for (b in d) sb.append(String.format("%02x", b))
        return sb.toString()
    }

    /**
     * 候选图地址。**百度优先**：国内直连、快；
     * 必应放后面 —— 走 Clash 等代理时常被投到失效节点，光等超时就浪费好几秒。
     */
    private fun candidates(word: String): List<String> {
        val q = URLEncoder.encode(word, "UTF-8")
        val out = ArrayList<String>(8)

        // 1) 百度图片
        runCatching {
            val js = httpText("https://image.baidu.com/search/acjson?tn=resultjson_com&word=$q&pn=0&rn=8")
            val re = Regex(THUMB_RE)
            re.findAll(js).take(6).forEach { m ->
                val u = m.groupValues.drop(1).firstOrNull { it.isNotEmpty() } ?: ""
                if (u.startsWith("http")) out.add(u)
            }
        }

        // 2) 必应图片（百度没结果时再试）
        if (out.isEmpty()) {
            runCatching {
                val html = httpText("https://cn.bing.com/images/async?q=$q&first=0&count=8&mkt=zh-CN", 4000)
                Regex("murl&quot;:&quot;(.*?)&quot;").findAll(html).take(6).forEach { m ->
                    val u = m.groupValues[1]
                    if (u.startsWith("http")) out.add(u)
                }
            }
        }

        // 3) 兜底：随便给张图，总比空白强
        if (out.isEmpty()) out.add("https://picsum.photos/480/360?random=" + q.hashCode())
        return out
    }

    private fun httpText(url: String, readMs: Int = READ_MS): String {
        var conn: HttpURLConnection? = null
        return try {
            conn = (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = 4000
                readTimeout = readMs
                setRequestProperty("User-Agent", UA)
                setRequestProperty("Accept-Language", "en-US,en;q=0.9")
            }
            conn.inputStream.use { it.readBytes().toString(Charsets.UTF_8) }
        } finally {
            runCatching { conn?.disconnect() }
        }
    }

    private fun fetch(word: String, key: String): File? {
        for (u in candidates(word)) {
            val f = download(u, key) ?: continue
            return f
        }
        return null
    }

    private fun download(url: String, key: String): File? {
        var conn: HttpURLConnection? = null
        var tmp: File? = null
        return try {
            conn = (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = CONNECT_MS
                readTimeout = READ_MS
                instanceFollowRedirects = true
                setRequestProperty("User-Agent", UA)
                setRequestProperty("Accept", "image/*,*/*")
            }
            if (conn.responseCode != 200) return null
            val ct = conn.contentType ?: ""
            if (!ct.startsWith("image")) return null
            dir.mkdirs()
            tmp = File(dir, "$key.part")
            conn.inputStream.use { ins ->
                tmp.outputStream().use { out -> ins.copyTo(out, 16 * 1024) }
            }
            if (tmp.length() < 2048) {
                tmp.delete()
                return null
            }
            val out = File(dir, "$key.jpg")
            if (!tmp.renameTo(out)) {
                tmp.copyTo(out, overwrite = true)
                tmp.delete()
            }
            out
        } catch (_: Exception) {
            runCatching { tmp?.delete() }
            null
        } finally {
            runCatching { conn?.disconnect() }
        }
    }
}
