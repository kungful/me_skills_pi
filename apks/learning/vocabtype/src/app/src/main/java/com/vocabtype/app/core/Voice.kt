package com.vocabtype.app.core

import android.content.Context
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.os.Handler
import android.os.Looper
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.security.MessageDigest
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger

/**
 * 有道词典发音接口 —— 免费、不要 Key、真人音质，英音/美音可选。
 *
 *     https://dict.youdao.com/dictvoice?audio=<文本>&type=1(英) / 2(美)
 *
 * 实测结论（2026-10）：
 *   · 单词、常用短语命中率极高（30/30），返回 mp3（ID3/FFFB）或 wav（RIFF），
 *     MediaPlayer 两种都能直接放；
 *   · 它是**词典语料库**而不是通用 TTS，自造长句一律 500 `returned null audio`，
 *     所以超过 [ONLINE_MAX_WORDS] 个词的文本由调用方交给系统 TTS。
 *
 * 下载一次就落盘（filesDir/voice），之后完全离线也能播；先写 .part 再改名，
 * 保证不会把半截文件当缓存读出来。
 */
class Voice(private val ctx: Context) {

    companion object {
        const val UK = 1
        const val US = 2

        /** 超过这么多"词"就认为不是词典条目，直接走系统 TTS */
        const val ONLINE_MAX_WORDS = 3

        /** 单条文本最长字符数，再长基本不是词典条目 */
        const val ONLINE_MAX_CHARS = 40

        private const val DIR = "voice"
        private const val UA =
            "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Mobile Safari/537.36"
    }

    /** 1 = 英音，2 = 美音 */
    @Volatile
    var accent = US

    /** 播放速度（0.5x ~ 2.0x，用 PlaybackParams 变速，不改变音调太多） */
    @Volatile
    var rate = 1.0f

    private val handler = Handler(Looper.getMainLooper())
    private val dir = File(ctx.filesDir, DIR)
    private val pool = Executors.newFixedThreadPool(3)
    private val sweepPool = Executors.newFixedThreadPool(4)
    private val inflight = ConcurrentHashMap<String, Boolean>()

    /** 接口明确说"没有"的条目（500/404），本次进程内不再重复请求 */
    private val dead = ConcurrentHashMap.newKeySet<String>()

    private var player: MediaPlayer? = null
    private var token = 0

    // ------------------------------------------------------------ 对外

    /** 这段文本适合走在线接口吗（词典条目 vs 长句） */
    fun fits(text: String): Boolean {
        val t = text.trim()
        if (t.isEmpty() || t.length > ONLINE_MAX_CHARS) return false
        val words = t.split(' ', '\t', '\n').filter { it.isNotBlank() }
        return words.size in 1..ONLINE_MAX_WORDS
    }

    /** 已经缓存过的条数 */
    fun cacheCount(): Int = runCatching { dir.listFiles()?.size ?: 0 }.getOrDefault(0)

    /** 缓存占用字节 */
    fun sizeBytes(): Long = runCatching { dir.listFiles()?.sumOf { it.length() } ?: 0L }.getOrDefault(0L)

    fun clearCache() {
        runCatching { dir.listFiles()?.forEach { it.delete() } }
    }

    /** 试听：播一段文本，播完回调 onDone，放不了（下载失败/没网）回调 onFail */
    fun play(text: String, onDone: () -> Unit, onFail: () -> Unit) {
        val t = ++token
        val hit = cached(text, accent)
        if (hit != null) {
            start(hit, onDone, onFail)
            return
        }
        val key = keyOf(text)
        if (dead.contains(key)) {          // 这词语料库里没有，别等了，直接交给系统 TTS
            onFail()
            return
        }
        if (inflight.putIfAbsent(key, true) != null) {
            // 同一条正在下：稍等一下再来看缓存
            handler.postDelayed({ if (t == token) play(text, onDone, onFail) }, 280L)
            return
        }
        pool.execute {
            val f = download(text, accent)
            handler.post {
                inflight.remove(key)
                if (t != token) return@post       // 已经翻页/停了，悄悄丢掉
                if (f != null) start(f, onDone, onFail) else {
                    dead.add(key)
                    onFail()
                }
            }
        }
    }

    /** 只下载不播放（换词时预热，让点播放零等待） */
    fun prefetch(text: String) {
        if (!fits(text)) return
        if (cached(text, accent) != null) return
        val key = keyOf(text)
        if (dead.contains(key)) return
        if (inflight.putIfAbsent(key, true) != null) return
        pool.execute {
            download(text, accent)
            inflight.remove(key)
        }
    }

    fun stop() {
        token++
        stopPlayer()
    }

    /**
     * 批量预下载（词库整本）。返回一个可取消的句柄。
     * onProgress(done, total) / onFinish(ok, fail) 都回到主线程。
     */
    fun sweep(
        words: List<String>,
        onProgress: (Int, Int) -> Unit,
        onFinish: (ok: Int, fail: Int) -> Unit
    ): Runnable {
        val cancel = AtomicBoolean(false)
        val total = words.size
        val idx = AtomicInteger(0)
        val ok = AtomicInteger(0)
        val fail = AtomicInteger(0)
        val left = AtomicInteger(4)
        if (total == 0) {
            handler.post { onFinish(0, 0) }
            return Runnable { }
        }
        repeat(4) {
            sweepPool.execute {
                try {
                    while (!cancel.get()) {
                        val i = idx.getAndIncrement()
                        if (i >= total) break
                        val w = words[i]
                        val f = if (dead.contains(keyOf(w))) null else download(w, accent)
                        if (f != null) ok.incrementAndGet()
                        else {
                            dead.add(keyOf(w))
                            fail.incrementAndGet()
                        }
                        val d = idx.get().coerceAtMost(total)
                        handler.post { onProgress(d, total) }
                    }
                } finally {
                    if (left.decrementAndGet() == 0) {
                        handler.post { onFinish(ok.get(), fail.get()) }
                    }
                }
            }
        }
        return Runnable { cancel.set(true) }
    }

    fun shutdown() {
        token++
        stopPlayer()
        runCatching { pool.shutdownNow() }
        runCatching { sweepPool.shutdownNow() }
    }

    // ------------------------------------------------------------ 内部

    private fun start(f: File, onDone: () -> Unit, onFail: () -> Unit) {
        stopPlayer()
        try {
            val mp = MediaPlayer()
            mp.setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
            mp.setDataSource(f.absolutePath)
            mp.prepare()
            val sp = rate.coerceIn(0.5f, 2.0f)
            if (sp != 1.0f) {
                runCatching { mp.playbackParams = mp.playbackParams.setSpeed(sp) }
            }
            mp.setOnCompletionListener {
                stopPlayer()
                onDone()
            }
            mp.setOnErrorListener { _, _, _ ->
                stopPlayer()
                onFail()
                true
            }
            player = mp
            mp.start()
        } catch (e: Exception) {
            stopPlayer()
            // 文件坏了就当没缓存，下次重新下
            runCatching { f.delete() }
            onFail()
        }
    }

    private fun stopPlayer() {
        val p = player ?: return
        player = null
        runCatching { if (p.isPlaying) p.stop() }
        runCatching { p.reset() }
        runCatching { p.release() }
    }

    private fun keyOf(text: String) = "$accent|${text.lowercase().trim()}"

    private fun sha1(s: String): String {
        val d = MessageDigest.getInstance("SHA-1").digest(s.toByteArray(Charsets.UTF_8))
        val sb = StringBuilder()
        for (b in d) sb.append(String.format("%02x", b))
        return sb.toString()
    }

    private fun base(text: String, type: Int): String =
        "y${type}_" + sha1("$type|${text.lowercase().trim()}")

    /** 找已缓存的文件（后缀按真实格式存，所以挨个试） */
    private fun cached(text: String, type: Int): File? {
        val b = base(text, type)
        for (e in EXT) {
            val f = File(dir, b + e)
            if (f.isFile && f.length() > 512) return f
        }
        return null
    }

    private fun download(text: String, type: Int): File? {
        val hit = cached(text, type)
        if (hit != null) return hit
        val url = "https://dict.youdao.com/dictvoice?audio=" +
                URLEncoder.encode(text.trim(), "UTF-8").replace("+", "%20") + "&type=$type"
        var conn: HttpURLConnection? = null
        var tmp: File? = null
        return try {
            conn = (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = 5000
                readTimeout = 8000
                requestMethod = "GET"
                instanceFollowRedirects = true
                setRequestProperty("User-Agent", UA)
                setRequestProperty("Accept", "audio/*,*/*")
            }
            if (conn.responseCode != 200) return null
            val ct = conn.contentType ?: ""
            if (!ct.startsWith("audio")) return null
            dir.mkdirs()
            tmp = File(dir, base(text, type) + ".part")
            conn.inputStream.use { ins ->
                tmp.outputStream().use { out -> ins.copyTo(out, 16 * 1024) }
            }
            if (tmp.length() < 512) {
                tmp.delete()
                return null
            }
            // 认一下真实格式（接口有时给 mp3 有时给 wav，content-type 不可信）
            val head = ByteArray(4)
            tmp.inputStream().use { it.read(head) }
            val ext = sniff(head)
            val out = File(dir, base(text, type) + ext)
            if (!tmp.renameTo(out)) {
                tmp.copyTo(out, overwrite = true)
                tmp.delete()
            }
            if (out.length() < 512) {
                out.delete()
                null
            } else out
        } catch (e: Exception) {
            runCatching { tmp?.delete() }
            null
        } finally {
            runCatching { conn?.disconnect() }
        }
    }

    private fun sniff(h: ByteArray): String {
        val b0 = h[0].toInt() and 0xFF
        val b1 = h[1].toInt() and 0xFF
        val b2 = h[2].toInt() and 0xFF
        val b3 = h[3].toInt() and 0xFF
        return when {
            // "RIFF" = wav
            b0 == 0x52 && b1 == 0x49 && b2 == 0x46 && b3 == 0x46 -> ".wav"
            // "ID3" = mp3
            b0 == 0x49 && b1 == 0x44 && b2 == 0x33 -> ".mp3"
            // 裸 mp3 帧同步 0xFFEx / 0xFFFx
            b0 == 0xFF && (b1 and 0xE0) == 0xE0 -> ".mp3"
            // "OggS"
            b0 == 0x4F && b1 == 0x67 && b2 == 0x67 && b3 == 0x53 -> ".ogg"
            else -> ".dat"
        }
    }

    private val EXT get() = arrayOf(".mp3", ".wav", ".ogg", ".dat")
}
