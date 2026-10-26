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
 * 免费在线发音（全部实测过，不需要任何 Key）：
 *
 *   · 有道词典发音  https://dict.youdao.com/dictvoice?audio=..&type=1|2
 *       英音/美音真人音，单词和常用短语最准最快（~0.1s）。
 *       但它是**词典语料库不是通用 TTS**：自造长句一律 500 `returned null audio`，
 *       也读不了中文。所以只用来读单词。
 *
 *   · 百度翻译发音  https://fanyi.baidu.com/gettts?lan=..&text=..&spd=3&source=web
 *       通用 TTS：英文长句、中文整句都能读，lan=en 美音 / uk 英音 / zh+v=中文。
 *       冷启动 0.8~1.2s（偶发十几秒，所以做了超时 + 回退）。
 *
 *   · Google 翻译发音  https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl=..
 *       音质最好，但国内直连不通，只在能连上时用；可作为前两个都失败后的兜底。
 *
 * 策略：语言+长度决定用哪家，按优先级挨个试，全失败再交给系统 TTS。
 * 下载一次就落盘（filesDir/voice），之后完全离线也能播；先写 .part 再改名。
 */
class Voice(private val ctx: Context) {

    companion object {
        const val UK = 1
        const val US = 2

        /** 有道只吃"词典条目"：这么多个词以内才尝试 */
        const val ENTRY_MAX_WORDS = 3
        const val ENTRY_MAX_CHARS = 40

        /** 单次请求的超时（百度冷启动偶尔十几秒，超过就换源） */
        private const val CONNECT_MS = 5000
        private const val READ_MS = 12000

        private const val DIR = "voice"
        private const val UA =
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    }

    /** 1 = 英音，2 = 美音 */
    @Volatile
    var accent = US

    /** 播放速度（0.5x ~ 2.0x） */
    @Volatile
    var rate = 1.0f

    /** 百度语速档位 1..7（3 = 正常） */
    @Volatile
    var spd = 3

    /** 中文朗读用（百度 zh）；false = 不读中文 */
    @Volatile
    var zhOn = false

    /** 关掉：只用系统 TTS（用户不想联网时） */
    @Volatile
    var netOn = true

    /** 0 = 有道/百度（快）; 1 = 微软神经语音（音质最好，稍慢） */
    @Volatile
    var edgeOn = false
        set(v) {
            val old = srcTag()
            field = v
            val now = srcTag()
            if (old != now) dropCacheFor(now)
        }

    private fun srcTag(): String = if (edgeOn) "e:$edgeVoice" else "n"

    /** 微软音色 id */
    @Volatile
    var edgeVoice: String = EdgeTts.VOICE_XIAOXIAO
        set(v) {
            val old = srcTag()
            field = v
            if (old != srcTag()) dropCacheFor(srcTag())
        }

    private val handler = Handler(Looper.getMainLooper())
    private val dir = File(ctx.filesDir, DIR)
    private val pool = Executors.newFixedThreadPool(3)
    private val sweepPool = Executors.newFixedThreadPool(4)
    private val inflight = ConcurrentHashMap<String, Boolean>()

    /** 这些 (源,文本) 已经确认拿不到，本进程内不再重复请求 */
    private val dead = ConcurrentHashMap.newKeySet<String>()

    private var player: MediaPlayer? = null
    private var token = 0

    // ------------------------------------------------------------ 能力判断

    /** 是"词典条目"吗（单词 / 两三个词的短语） */
    fun isEntry(text: String): Boolean {
        val t = text.trim()
        if (t.isEmpty()) return false
        if (isChinese(t)) return t.length <= 20        // 中文释义都是短词，<=20 字算词条
        if (t.length > ENTRY_MAX_CHARS) return false
        val words = t.split(' ', '\t', '\n').filter { it.isNotBlank() }
        return words.size in 1..ENTRY_MAX_WORDS
    }

    /** 含中文 */
    fun isChinese(text: String): Boolean {
        for (c in text) if (c.code in 0x4E00..0x9FFF || c.code in 0x3400..0x4DBF) return true
        return false
    }

    /** 这个文本走在线发音有意义吗 */
    fun canSay(text: String): Boolean {
        if (!netOn) return false
        val t = text.trim()
        if (t.isEmpty()) return false
        return if (isChinese(t)) zhOn else true
    }

    // ------------------------------------------------------------ 缓存信息

    fun cacheCount(): Int = runCatching { dir.listFiles()?.size ?: 0 }.getOrDefault(0)

    fun sizeBytes(): Long =
        runCatching { dir.listFiles()?.sumOf { it.length() } ?: 0L }.getOrDefault(0L)

    /**
     * 换音色/切换音源后清掉旧缓存。
     * 缓存文件名是内容哈希，无法反查属于哪个音色，所以只能全清
     * —— 但这是对的：换了声音就该重新合成，否则会一直听到老声音。
     */
    fun dropCacheFor(srcTag: String) {
        runCatching { dir.listFiles()?.forEach { it.delete() } }
        dead.clear()
    }

    fun clearCache() {
        runCatching { dir.listFiles()?.forEach { it.delete() } }
        dead.clear()
    }

    // ------------------------------------------------------------ 播放

    /** 播一段文本；成功播完 onDone，放不了 onFail（调用方随后回退系统 TTS） */
    fun play(text: String, onDone: () -> Unit, onFail: () -> Unit) {
        val t = ++token
        if (!canSay(text)) {
            onFail()
            return
        }
        val key = keyOf(text)
        val hit = cached(key)
        if (hit != null) {
            start(hit, onDone, onFail)
            return
        }
        if (dead.contains(key)) {
            onFail()
            return
        }
        if (inflight.putIfAbsent(key, true) != null) {
            // 同一条正在下：稍等再来看缓存
            handler.postDelayed({ if (t == token) play(text, onDone, onFail) }, 300L)
            return
        }
        pool.execute {
            val f = download(text, key)
            handler.post {
                inflight.remove(key)
                if (t != token) return@post        // 已经翻页/停了，悄悄丢掉
                if (f != null) {
                    start(f, onDone, onFail)
                } else {
                    dead.add(key)
                    onFail()
                }
            }
        }
    }

    /** 只下载不播放（换词预热） */
    fun prefetch(text: String) {
        if (!canSay(text)) return
        val key = keyOf(text)
        if (cached(key) != null || dead.contains(key)) return
        if (inflight.putIfAbsent(key, true) != null) return
        pool.execute {
            download(text, key)
            inflight.remove(key)
        }
    }

    fun stop() {
        token++
        stopPlayer()
    }

    fun shutdown() {
        token++
        stopPlayer()
        runCatching { pool.shutdownNow() }
        runCatching { sweepPool.shutdownNow() }
    }

    // ------------------------------------------------------------ 批量预下载

    /**
     * 中文释义批量预合成。中文释义都是 2~8 字的短词，下载一次就永久缓存，
     * 之后播放零等待 —— 这样即使引擎单次要 4~5 秒也不影响体验。
     */
    fun warmZh(texts: List<String>, onProgress: (Int, Int) -> Unit, onFinish: (Int, Int) -> Unit): Runnable {
        val cancel = AtomicBoolean(false)
        val uniq = texts.map { it.trim() }.filter { it.isNotEmpty() }.distinct()
        val total = uniq.size
        if (total == 0) {
            handler.post { onFinish(0, 0) }
            return Runnable { }
        }
        val idx = AtomicInteger(0)
        val ok = AtomicInteger(0)
        val fail = AtomicInteger(0)
        val left = AtomicInteger(4)
        repeat(4) {
            sweepPool.execute {
                try {
                    while (!cancel.get()) {
                        val i = idx.getAndIncrement()
                        if (i >= total) break
                        val t = uniq[i]
                        val key = keyOf(t)
                        val f = if (dead.contains(key)) null else download(t, key)
                        if (f != null) ok.incrementAndGet() else fail.incrementAndGet()
                        val d = idx.get().coerceAtMost(total)
                        handler.post { onProgress(d, total) }
                    }
                } finally {
                    if (left.decrementAndGet() == 0) handler.post { onFinish(ok.get(), fail.get()) }
                }
            }
        }
        return Runnable { cancel.set(true) }
    }

    fun sweep(
        words: List<String>,
        onProgress: (Int, Int) -> Unit,
        onFinish: (ok: Int, fail: Int) -> Unit
    ): Runnable {
        val cancel = AtomicBoolean(false)
        val total = words.size
        if (total == 0) {
            handler.post { onFinish(0, 0) }
            return Runnable { }
        }
        val idx = AtomicInteger(0)
        val ok = AtomicInteger(0)
        val fail = AtomicInteger(0)
        val left = AtomicInteger(4)
        repeat(4) {
            sweepPool.execute {
                try {
                    while (!cancel.get()) {
                        val i = idx.getAndIncrement()
                        if (i >= total) break
                        val w = words[i]
                        val key = keyOf(w)
                        val f = if (dead.contains(key)) null else download(w, key)
                        if (f != null) ok.incrementAndGet()
                        else {
                            dead.add(key)
                            fail.incrementAndGet()
                        }
                        val d = idx.get().coerceAtMost(total)
                        handler.post { onProgress(d, total) }
                    }
                } finally {
                    if (left.decrementAndGet() == 0) handler.post { onFinish(ok.get(), fail.get()) }
                }
            }
        }
        return Runnable { cancel.set(true) }
    }

    // ------------------------------------------------------------ 音源

    private class Src(val tag: String, val url: String)

    /**
     * 按「语言 + 是不是词典条目」排优先级：
     *   英文词条 → 有道(英/美) → 百度 → Google
     *   英文句子 → 百度 → Google
     *   中文     → 百度(zh) → Google(zh-CN)
     */
    private fun sources(text: String): List<Src> {
        val t = text.trim()
        val q = URLEncoder.encode(t, "UTF-8").replace("+", "%20")
        val out = ArrayList<Src>(3)
        if (isChinese(t)) {
            if (edgeOn) out.add(Src("edge", "EDGE"))
            if (isEntry(t)) {
                out.add(Src("youdao-zh", "https://dict.youdao.com/dictvoice?le=zh&audio=$q"))
            }
            out.add(Src("baidu-z", "https://fanyi.baidu.com/gettts?lan=zh&text=$q&spd=$spd&source=web"))
            out.add(Src("google-z", "https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl=zh-CN&q=$q"))
        } else {
            if (edgeOn) out.add(Src("edge", "EDGE"))
            if (isEntry(t)) {
                out.add(Src("youdao-$accent", "https://dict.youdao.com/dictvoice?audio=$q&type=$accent"))
            }
            val lan = if (accent == UK) "uk" else "en"
            out.add(Src("baidu-$lan", "https://fanyi.baidu.com/gettts?lan=$lan&text=$q&spd=$spd&source=web"))
            val tl = if (accent == UK) "en-GB" else "en"
            out.add(Src("google-$tl", "https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl=$tl&q=$q"))
        }
        return out
    }

    // ------------------------------------------------------------ 下载

    /**
     * 缓存键必须带"用哪家音源合成的"指纹，否则：
     *   先用百度合成中文 -> 缓存命中 -> 之后开微软也永远读不到新音质。
     */
    private fun keyOf(text: String): String {
        val src = if (edgeOn) "e:$edgeVoice" else "n"
        val kind = when {
            isChinese(text) -> "z"
            isEntry(text) -> "w$accent"
            else -> "s$accent"
        }
        return "$kind|$src|${text.trim().lowercase()}"
    }

    private fun sha1(s: String): String {
        val d = MessageDigest.getInstance("SHA-1").digest(s.toByteArray(Charsets.UTF_8))
        val sb = StringBuilder()
        for (b in d) sb.append(String.format("%02x", b))
        return sb.toString()
    }

    private fun cached(key: String): File? {
        val b = sha1("C|" + key)
        for (e in EXT) {
            val f = File(dir, b + e)
            if (f.isFile && f.length() > 512) return f
        }
        return null
    }

    /** 按优先级挨个音源试，拿到就落盘（文件名只跟 key 有关，换音源也认） */
    private fun download(text: String, key: String): File? {
        val hit = cached(key)
        if (hit != null) return hit
        for (s in sources(text)) {
            val dk = "${s.tag}|$key"
            if (dead.contains(dk)) continue
            val f = fetch(s, text, dk, key)
            if (f != null) return f
        }
        return null
    }

    private fun fetch(s: Src, text: String, deadKey: String, cacheKey: String): File? {
        if (!netOn) return null
        if (s.url == "EDGE") return fetchEdge(text, deadKey, cacheKey)
        var conn: HttpURLConnection? = null
        var tmp: File? = null
        return try {
            conn = (URL(s.url).openConnection() as HttpURLConnection).apply {
                connectTimeout = CONNECT_MS
                readTimeout = READ_MS
                requestMethod = "GET"
                instanceFollowRedirects = true
                setRequestProperty("User-Agent", UA)
                setRequestProperty("Accept", "audio/*,*/*")
                setRequestProperty("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8")
                if (s.tag.startsWith("baidu")) setRequestProperty("Referer", "https://fanyi.baidu.com/")
            }
            if (conn.responseCode != 200) {
                dead.add(deadKey)
                return null
            }
            val ct = conn.contentType ?: ""
            if (ct.startsWith("text/") || ct.contains("json")) {
                dead.add(deadKey)
                return null
            }
            dir.mkdirs()
            tmp = File(dir, sha1("C|" + cacheKey) + ".part")
            conn.inputStream.use { ins ->
                tmp.outputStream().use { out -> ins.copyTo(out, 16 * 1024) }
            }
            if (tmp.length() < 512) {
                tmp.delete()
                dead.add(deadKey)
                return null
            }
            // 嗅探真实格式：各家返回 mp3 / wav / ogg 不等，Content-Type 不可信
            val head = ByteArray(4)
            tmp.inputStream().use { it.read(head) }
            val out = File(dir, sha1("C|" + cacheKey) + sniff(head))
            if (!tmp.renameTo(out)) {
                tmp.copyTo(out, overwrite = true)
                tmp.delete()
            }
            if (out.length() < 512) {
                out.delete()
                dead.add(deadKey)
                null
            } else out
        } catch (e: Exception) {
            runCatching { tmp?.delete() }
            dead.add(deadKey)
            null
        } finally {
            runCatching { conn?.disconnect() }
        }
    }

    /** 微软神经语音：WebSocket 合成后落盘 */
    private fun fetchEdge(text: String, deadKey: String, cacheKey: String): File? {
        return try {
            val body = EdgeTts.synth(text, edgeVoice, ((rate - 1f) * 100).toInt())
            android.util.Log.i("VTEDGE", "synth '$text' voice=$edgeVoice -> ${body?.size ?: -1}B")
            if (body == null || body.size < 1024) {
                dead.add(deadKey)
                return null
            }
            dir.mkdirs()
            val out = File(dir, sha1("C|" + cacheKey) + ".mp3")
            out.writeBytes(body)
            out
        } catch (e: Exception) {
            dead.add(deadKey)
            null
        }
    }

    private fun sniff(h: ByteArray): String {
        val b0 = h[0].toInt() and 0xFF
        val b1 = h[1].toInt() and 0xFF
        val b2 = h[2].toInt() and 0xFF
        val b3 = h[3].toInt() and 0xFF
        return when {
            b0 == 0x52 && b1 == 0x49 && b2 == 0x46 && b3 == 0x46 -> ".wav"   // RIFF
            b0 == 0x49 && b1 == 0x44 && b2 == 0x33 -> ".mp3"                 // ID3
            b0 == 0xFF && (b1 and 0xE0) == 0xE0 -> ".mp3"                    // 裸 mp3 帧
            b0 == 0x4F && b1 == 0x67 && b2 == 0x67 && b3 == 0x53 -> ".ogg"   // OggS
            else -> ".dat"
        }
    }

    private val EXT get() = arrayOf(".mp3", ".wav", ".ogg", ".dat")

    // ------------------------------------------------------------ 播放器

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
            if (sp != 1.0f) runCatching { mp.playbackParams = mp.playbackParams.setSpeed(sp) }
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
            runCatching { f.delete() }        // 文件坏了，下次重下
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
}
