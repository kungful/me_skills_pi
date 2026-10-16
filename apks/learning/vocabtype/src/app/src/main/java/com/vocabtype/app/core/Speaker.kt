package com.vocabtype.app.core

import android.content.Context
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import java.util.Locale

/**
 * 发音器。两套引擎，一个统一出口：
 *
 *   · [engine] = 0 —— 系统 TTS（离线，长句也能读，音色看手机装了什么包）
 *   · [engine] = 1 —— 有道在线真人发音（[Voice]，音质好、英音/美音可选）
 *
 * 在线引擎只吃得下**词典条目**（单词/常用短语），所以：
 *   · 单词、短语 → 走有道，播不了（没网/语料里没有）自动退回系统 TTS；
 *   · 长句 → 直接走系统 TTS。
 *
 * 播放调度是「串行队列 + 代号(gen)」：换词、停止都会让旧回调作废，
 * 循环朗读用「上一段播完再排下一段」实现，所以不会自己叠在一起。
 */
class Speaker(ctx: Context) {

    /** 0 = 系统 TTS；1 = 有道在线真人发音 */
    var engine = 0
        set(v) {
            field = if (v == 1) 1 else 0
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

    var rate: Float = 1.0f
        set(v) {
            field = v.coerceIn(0.4f, 2.0f)
            voice.rate = field
            runCatching { if (ready) tts?.setSpeechRate(field) }
        }

    var available = false
        private set

    var resolved = false
        private set

    var onReady: (() -> Unit)? = null

    /** 能出声吗（在线引擎不依赖语音包） */
    val canSpeak: Boolean get() = engine == 1 || available

    private val handler = Handler(Looper.getMainLooper())
    private var tts: TextToSpeech? = null
    private var ready = false

    /** 当前这一轮播放的代号：只有公开入口和 stop 才会动它 */
    private var gen = 0

    /** 系统 TTS 这一句播完后要叫谁 */
    private var ttsDone: (() -> Unit)? = null
    private var uttId = 0
    private var lastSpokeAt = 0L

    private var loopWord: String? = null
    private var loopSent: String? = null

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

    /** 按设置项配好引擎 / 口音 / 语速 */
    fun applyPrefs(p: Prefs): Speaker {
        engine = p.voiceEngine
        accent = p.accent
        rate = p.ttsRate
        return this
    }

    val voiceEngine: Voice get() = voice

    // ---------------------------------------------------------------- 对外

    fun say(text: String) {
        if (text.isBlank()) return
        dropLoop()
        play(listOf(text), loop = false, onLast = null)
    }

    /** 循环朗读某段文字（比如整句） */
    fun loopSay(text: String) {
        if (text.isBlank()) return
        if (loopWord == text && loopSent == null) return
        stop()
        loopWord = text
        loopSent = null
        play(listOf(text), loop = true, onLast = null)
    }

    /** 单词 → 句子 交替循环（单词能吃到真人音，句子交给系统 TTS） */
    fun loopPair(word: String, sent: String?) {
        if (word.isBlank()) return
        if (loopWord == word && loopSent == sent) return
        stop()
        loopWord = word
        loopSent = sent
        val items = if (sent.isNullOrBlank()) listOf(word) else listOf(word, sent)
        play(items, loop = true, onLast = null)
    }

    /** 单词 → 停顿 → 句子 */
    fun sayThen(first: String, second: String, onSecond: (() -> Unit)? = null) {
        dropLoop()
        play(listOf(first, second), loop = false, onLast = onSecond)
    }

    fun stopLoop() {
        dropLoop()
        gen++
    }

    fun stop() {
        dropLoop()
        gen++
        ttsDone = null
        runCatching { tts?.stop() }
        voice.stop()
    }

    fun shutdown() {
        dropLoop()
        gen++
        ttsDone = null
        runCatching { tts?.stop() }
        runCatching { tts?.shutdown() }
        tts = null
        ready = false
        voice.shutdown()
    }

    /** 换词时预热发音，让点播放零等待 */
    fun prefetch(text: String) {
        if (engine == 1) voice.prefetch(text)
    }

    // ---------------------------------------------------------------- 调度

    private fun dropLoop() {
        loopWord = null
        loopSent = null
    }

    private fun play(items: List<String>, loop: Boolean, onLast: (() -> Unit)?) {
        gen++
        step(items, 0, gen, loop, onLast)
    }

    private fun step(items: List<String>, i: Int, t: Int, loop: Boolean, onLast: (() -> Unit)?) {
        if (t != gen) return
        if (i >= items.size) {
            onLast?.invoke()
            if (!loop) return
            // 上一段刚播完就接着播，中间留一点气口，但别叠得太密
            val gap = if (System.currentTimeMillis() - lastSpokeAt < 200) 500L else 420L
            handler.postDelayed({ if (t == gen) step(items, 0, t, loop, onLast) }, gap)
            return
        }
        utter(items[i], t) { step(items, i + 1, t, loop, onLast) }
    }

    private fun utter(text: String, t: Int, onEnd: () -> Unit) {
        if (t != gen) return
        lastSpokeAt = System.currentTimeMillis()
        if (engine == 1 && voice.fits(text)) {
            voice.play(
                text,
                onDone = { if (t == gen) onEnd() },
                onFail = { if (t == gen) utterTts(text, t, onEnd) }
            )
        } else {
            utterTts(text, t, onEnd)
        }
    }

    private fun utterTts(text: String, t: Int, onEnd: () -> Unit) {
        if (t != gen) return
        if (!ready) {
            // 没装英文语音包：给个节流，别把循环变成空转
            handler.postDelayed({ if (t == gen) onEnd() }, if (engine == 1) 900L else 600L)
            return
        }
        ttsDone = onEnd
        lastSpokeAt = System.currentTimeMillis()
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
}
