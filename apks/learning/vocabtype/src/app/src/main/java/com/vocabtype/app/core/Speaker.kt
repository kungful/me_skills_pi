package com.vocabtype.app.core

import android.content.Context
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import java.util.Locale

/**
 * 发音器。一个统一出口，内部三条路：
 *
 *   · 在线免费发音（[Voice]）：有道（单词真人音）+ 百度（长句 / 中文）
 *   · 系统 TTS：兜底，任何一条在线路失败都会自动退到它
 *   · 中文释义朗读：复用同一条链（百度 zh 明显好于手机自带中文包）
 *
 * 播放调度是「串行队列 + 代号(gen)」：换词 / 停止 / 暂停都会让旧回调作废，
 * 循环朗读用「上一段播完再排下一段」实现，不会自己叠在一起。
 *
 * 全局只有一个实例（[VoiceBox]），[SpeakService] 和界面共用它，
 * 所以退到后台、锁屏都不会被掐断。
 */
class Speaker(ctx: Context) {

    /** 0 = 只用系统 TTS；1 = 在线真人音优先（默认） */
    var engine = 1
        set(v) {
            field = if (v == 1) 1 else 0
            voice.netOn = field == 1
        }

    private val voice = Voice(ctx.applicationContext)

    /** 1 = 英音，2 = 美音 */
    var accent = Voice.US
        set(v) {
            field = if (v == Voice.UK) Voice.UK else Voice.US
            voice.accent = field
            runCatching {
                if (ready) tts?.setLanguage(if (field == Voice.UK) Locale.UK else Locale.US)
            }
        }

    /** 语速 0.4x ~ 2.0x：同时喂给 MediaPlayer 和系统 TTS */
    var rate: Float = 1.0f
        set(v) {
            field = v.coerceIn(0.4f, 2.0f)
            voice.rate = field
            voice.spd = (3 * field).toInt().coerceIn(1, 7)
            runCatching { if (ready) tts?.setSpeechRate(field) }
        }

    /** 中文释义朗读 */
    var zhOn = false
        set(v) {
            field = v
            voice.zhOn = v
        }

    var available = false
        private set

    var resolved = false
        private set

    var onReady: (() -> Unit)? = null

    val canSpeak: Boolean get() = engine == 1 || available

    // —— 给后台通知用的状态 ——
    @Volatile
    var nowLabel: String = ""
        private set
    @Volatile
    var nowPlaying: Boolean = false
        private set
    @Volatile
    var nowLoop: Boolean = false
        private set

    /** 播放状态变化（服务用它刷通知） */
    var onState: (() -> Unit)? = null

    private val handler = Handler(Looper.getMainLooper())
    private var tts: TextToSpeech? = null
    private var ready = false

    /** 当前这一轮播放的代号：只有公开入口和 stop/pause 才会动它 */
    private var gen = 0
    private var ttsDone: (() -> Unit)? = null
    private var uttId = 0
    private var lastSpokeAt = 0L

    private var loopWord: String? = null
    private var loopSent: String? = null
    private var series: List<List<String>>? = null
    private var seriesAt = 0
    private var seriesOnGroup: ((Int) -> Unit)? = null
    private var seriesOnDone: (() -> Unit)? = null

    private var queue: List<String> = emptyList()
    private var qi = 0
    private var loop = false
    private var onLast: (() -> Unit)? = null

    init {
        try {
            tts = TextToSpeech(ctx.applicationContext) { status ->
                if (status == TextToSpeech.SUCCESS) {
                    val r = tts?.setLanguage(if (accent == Voice.UK) Locale.UK else Locale.US)
                    available =
                        r != TextToSpeech.LANG_MISSING_DATA && r != TextToSpeech.LANG_NOT_SUPPORTED
                    if (available) {
                        runCatching {
                            tts?.setSpeechRate(rate)
                            tts?.setPitch(1.0f)
                        }
                        tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                            override fun onStart(id: String?) {}

                            @Deprecated("")
                            override fun onError(id: String?, code: Int) {}

                            override fun onError(id: String?) {
                                val cb = ttsDone
                                ttsDone = null
                                handler.post { cb?.invoke() }
                            }

                            override fun onDone(id: String?) {
                                val cb = ttsDone
                                ttsDone = null
                                handler.post { cb?.invoke() }
                            }
                        })
                    }
                }
                ready = available
                resolved = true
                onReady?.invoke()
            }
        } catch (_: Exception) {
            available = false
            resolved = true
        }
    }

    /** 按设置项配好引擎 / 口音 / 语速 / 中文 */
    fun applyPrefs(p: Prefs): Speaker {
        voice.netOn = p.voiceEngine == 1
        engine = p.voiceEngine
        accent = p.accent
        rate = p.ttsRate
        zhOn = p.readZh
        return this
    }

    /** 设置页预下载共用同一个缓存目录 */
    val voiceEngine: Voice get() = voice

    // ---------------------------------------------------------------- 对外

    /** 读一段纯文本（句中单词、复习页的词、随机句子） */
    fun say(text: String) {
        if (text.isBlank()) return
        loopWord = null
        loopSent = null
        start(listOf(text), loop = false, onLast = null)
    }

    /** 单词：英文 →（中文模式下）释义 */
    fun sayWord(en: String, zh: String?) {
        if (en.isBlank() && zh.isNullOrBlank()) return
        val items = ArrayList<String>(2)
        if (en.isNotBlank()) items.add(en)
        if (zhOn && !zh.isNullOrBlank()) {
            val c = zhSpeech(zh)
            if (c.isNotBlank()) items.add(c)
        }
        loopWord = null
        loopSent = null
        start(items, loop = false, onLast = null)
    }

    /** 整句：英文 →（中文模式下）中文 */
    fun saySentence(en: String, zh: String?) {
        if (en.isBlank()) return
        val items = ArrayList<String>(2)
        items.add(en)
        if (zhOn && !zh.isNullOrBlank()) {
            val c = zhSpeech(zh)
            if (c.isNotBlank()) items.add(c)
        }
        loopWord = null
        loopSent = null
        start(items, loop = false, onLast = null)
    }

    /** 循环朗读某段文字 */
    fun loopSay(text: String) {
        if (text.isBlank()) return
        if (loopWord == text && loopSent == null) return
        stop()
        loopWord = text
        loopSent = null
        start(listOf(text), loop = true, onLast = null)
    }

    /** 单词 →（中文释义）→ 句子，交替循环 */
    fun loopPair(word: String, sent: String?, zh: String? = null) {
        if (word.isBlank()) return
        if (loopWord == word && loopSent == sent) return
        stop()
        loopWord = word
        loopSent = sent
        val items = ArrayList<String>(3)
        items.add(word)
        if (zhOn && !zh.isNullOrBlank()) {
            val c = zhSpeech(zh)
            if (c.isNotBlank()) items.add(c)
        }
        if (!sent.isNullOrBlank()) items.add(sent)
        start(items, loop = true, onLast = null)
    }

    /** 单词 →→ 句子（按顺序播一遍） */
    fun sayThen(first: String, second: String, onSecond: (() -> Unit)? = null) {
        val items = ArrayList<String>(2)
        if (first.isNotBlank()) items.add(first)
        if (second.isNotBlank()) items.add(second)
        if (items.isEmpty()) return
        loopWord = null
        loopSent = null
        start(items, loop = false, onLast = onSecond)
    }

    /**
     * 播放器式连播：把 [groups] 一组一组播下去，
     * 每组内部按顺序念（单词 → 中文 → 句子），组与组之间自动衔接。
     * [onGroup] 每组开始前回调（界面靠它翻页），[onDone] 整批播完回调。
     */
    fun playSeries(
        groups: List<List<String>>,
        from: Int,
        onGroup: (Int) -> Unit,
        onDone: () -> Unit
    ) {
        if (groups.isEmpty()) return
        series = groups
        seriesAt = from.coerceIn(0, groups.size - 1)
        seriesOnGroup = onGroup
        seriesOnDone = onDone
        loopWord = null
        loopSent = null
        nowLoop = false
        val t = ++gen
        stepSeries(t)
    }

    /** 当前是不是在连播 */
    val inSeries: Boolean get() = series != null

    /** 停掉循环（同时也停掉正在播的） */
    fun stopLoop() = stop()

    fun stop() {
        series = null
        loopWord = null
        loopSent = null
        gen++
        ttsDone = null
        runCatching { tts?.stop() }
        voice.stop()
        nowPlaying = false
        nowLoop = false
        fire()
    }

    /** 暂停：记住当前这一句，[resume] 从它继续 */
    fun pause() {
        gen++
        ttsDone = null
        runCatching { tts?.stop() }
        voice.stop()
        nowPlaying = false
        fire()
    }

    fun resume() {
        if (series != null) {
            val t = ++gen
            nowPlaying = true
            fire()
            stepSeries(t)
            return
        }
        if (queue.isEmpty()) return
        val t = ++gen
        nowPlaying = true
        fire()
        step(queue, qi.coerceIn(0, queue.size - 1), t, loop, onLast)
    }

    val canResume: Boolean get() = series != null || queue.isNotEmpty()

    fun shutdown() {
        gen++
        ttsDone = null
        runCatching { tts?.stop() }
        runCatching { tts?.shutdown() }
        tts = null
        ready = false
        voice.shutdown()
        nowPlaying = false
        nowLoop = false
        fire()
    }

    /** 换词时预热发音 */
    fun prefetch(text: String) {
        if (engine == 1) voice.prefetch(text)
    }

    // ---------------------------------------------------------------- 调度

    private fun start(items: List<String>, loop: Boolean, onLast: (() -> Unit)?) {
        if (items.isEmpty()) return
        queue = items
        qi = 0
        this.loop = loop
        this.onLast = onLast
        nowLoop = loop
        nowLabel = items.firstOrNull().orEmpty()
        nowPlaying = true
        fire()
        val t = ++gen
        step(items, 0, t, loop, onLast)
    }

    private fun stepSeries(t: Int) {
        if (t != gen) return
        val g = series
        if (g == null || seriesAt !in g.indices) {
            series = null
            nowPlaying = false
            fire()
            seriesOnDone?.invoke()
            return
        }
        seriesOnGroup?.invoke(seriesAt)
        val items = g[seriesAt].filter { it.isNotBlank() }
        if (items.isEmpty()) {
            seriesAt++
            stepSeries(t)
            return
        }
        queue = items
        qi = 0
        nowLabel = items.first()
        nowPlaying = true
        fire()
        step(items, 0, t, false) {
            if (t == gen) {
                seriesAt++
                stepSeries(t)
            }
        }
    }

    private fun step(items: List<String>, i: Int, t: Int, loop: Boolean, onLast: (() -> Unit)?) {
        if (t != gen) return
        if (i >= items.size) {
            qi = 0
            onLast?.invoke()
            if (!loop) {
                nowPlaying = false
                fire()
                return
            }
            val gap = if (System.currentTimeMillis() - lastSpokeAt < 200) 600L else 500L
            handler.postDelayed({
                if (t == gen) step(items, 0, t, loop, onLast)
            }, gap)
            return
        }
        qi = i
        nowLabel = items[i]
        fire()
        utter(items[i], t) { step(items, i + 1, t, loop, onLast) }
    }

    private fun utter(text: String, t: Int, onEnd: () -> Unit) {
        if (t != gen) return
        if (text.isBlank()) {
            handler.postDelayed({ onEnd() }, 60L)
            return
        }
        lastSpokeAt = System.currentTimeMillis()
        val tryNet = engine == 1 && voice.canSay(text)
        android.util.Log.i("VT", "utter t=$t tryNet=$tryNet engine=$engine canSay=${voice.canSay(text)} text=${text.take(30)}")
        if (tryNet) {
            voice.play(text, { if (t == gen) onEnd() }, {
                android.util.Log.w("VT", "net FAIL -> tts: ${text.take(30)}")
                if (t == gen) utterTts(text, t, onEnd)
            })
        } else {
            utterTts(text, t, onEnd)
        }
    }

    private fun utterTts(text: String, t: Int, onEnd: () -> Unit) {
        if (t != gen) return
        if (!ready) {
            handler.postDelayed({ if (t == gen) onEnd() }, 600L)
            return
        }
        ttsDone = onEnd
        lastSpokeAt = System.currentTimeMillis()
        android.util.Log.i("VT", "tts speak ready=$ready: ${text.take(30)}")
        val chinese = voice.isChinese(text)
        runCatching {
            tts?.setLanguage(
                if (chinese) Locale.CHINA
                else if (accent == Voice.UK) Locale.UK else Locale.US
            )
        }
        val id = "vt-" + (++uttId)
        val r = try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, id)
            } else {
                @Suppress("DEPRECATION")
                tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null)
            }
        } catch (_: Exception) {
            TextToSpeech.ERROR
        }
        if (r == TextToSpeech.ERROR) {
            ttsDone = null
            handler.postDelayed({ if (t == gen) onEnd() }, 600L)
        }
    }

    private fun fire() {
        onState?.invoke()
    }

    companion object {
        /** 把释义洗成能朗读的中文：去掉词性、括号、分隔符 */
        fun zhSpeech(s: String): String {
            var t = s
            t = t.replace(Regex("[a-zA-Z]{1,6}\\.\\s*"), " ")
            t = t.replace(Regex("[（(\\[【].{0,20}?[)）\\]】]"), " ")
            t = t.replace(Regex("[；;·•/\\\\|｜、]+"), "，")
            t = t.replace(Regex("[：:]+"), " ")
            t = t.replace(Regex("\\s+"), " ")
            t = t.replace(Regex("^[，。、\\s]+"), "")
            t = t.replace(Regex("[，。、\\s]+$"), "")
            return t.trim().take(180)
        }
    }
}

/**
 * 进程内唯一的 [Speaker]。界面和 [SpeakService] 取到的是同一个实例，
 * 所以切后台、锁屏都不会断音。
 */
object VoiceBox {

    @Volatile
    private var inst: Speaker? = null

    fun get(ctx: Context, p: Prefs? = null): Speaker {
        var s = inst
        if (s == null) {
            synchronized(this) {
                s = inst ?: Speaker(ctx.applicationContext).also { inst = it }
            }
        }
        if (p != null) s?.applyPrefs(p)
        return s!!
    }

    fun peek(): Speaker? = inst
}
