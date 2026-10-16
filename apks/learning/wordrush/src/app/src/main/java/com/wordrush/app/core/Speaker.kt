package com.wordrush.app.core

import android.content.Context
import android.speech.tts.TextToSpeech
import java.util.Locale

/**
 * 系统 TTS 朗读。没装英文语音包也不会崩，只是发音功能自动关掉
 * （听力题届时会退化成普通选择题）。
 */
class Speaker(ctx: Context) {

    private var tts: TextToSpeech? = null
    private var ready = false

    var available = false
        private set

    /** TTS 初始化回调是否已经回来（不管成不成功） */
    var resolved = false
        private set

    var onReady: (() -> Unit)? = null

    init {
        try {
            tts = TextToSpeech(ctx.applicationContext) { status ->
                if (status == TextToSpeech.SUCCESS) {
                    val r = tts?.setLanguage(Locale.US)
                    available = r != TextToSpeech.LANG_MISSING_DATA && r != TextToSpeech.LANG_NOT_SUPPORTED
                    if (available) {
                        tts?.setSpeechRate(0.92f)
                        tts?.setPitch(1.0f)
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

    fun say(text: String) {
        if (!ready) return
        try {
            tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "wr")
        } catch (_: Exception) {
        }
    }

    fun stop() {
        runCatching { tts?.stop() }
    }

    fun shutdown() {
        runCatching { tts?.stop() }
        runCatching { tts?.shutdown() }
        tts = null
        ready = false
    }
}
