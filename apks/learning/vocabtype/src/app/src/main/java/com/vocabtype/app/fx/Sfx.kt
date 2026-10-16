package com.vocabtype.app.fx

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import kotlin.math.PI
import kotlin.math.exp
import kotlin.math.sin

/**
 * 音效全部是实时合成的 PCM，APK 里一个音频文件都不带。
 *
 * 关键点：每类音效只建一条 MODE_STATIC 的 AudioTrack，重复播放时
 * reloadStaticData() 就能立刻重放 —— 打字是每秒好几个音，不能每个音
 * 都 new 一条 AudioTrack，那样会卡。
 */
object Sfx {

    const val KEY = 0
    const val WORD = 1
    const val ERR = 2
    const val SENT = 3
    const val DONE = 4

    private const val SR = 22050
    private const val N = 5

    var enabled = true

    private val data = arrayOfNulls<ShortArray>(N)
    private val tracks = arrayOfNulls<AudioTrack>(N)
    private var built = false

    private fun ensure(kind: Int) {
        if (tracks[kind] != null) return
        val d = data[kind] ?: build(kind).also { data[kind] = it }
        if (d.isEmpty()) return
        try {
            val t = AudioTrack.Builder()
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_ASSISTANCE_SONIFICATION)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                        .build()
                )
                .setAudioFormat(
                    AudioFormat.Builder()
                        .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                        .setSampleRate(SR)
                        .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                        .build()
                )
                .setBufferSizeInBytes(d.size * 2)
                .setTransferMode(AudioTrack.MODE_STATIC)
                .setSessionId(AudioManager.AUDIO_SESSION_ID_GENERATE)
                .build()
            t.write(d, 0, d.size)
            tracks[kind] = t
        } catch (_: Exception) {
        }
    }

    fun prepare() {
        if (built) return
        built = true
        for (k in 0 until N) ensure(k)
    }

    fun play(kind: Int) {
        if (!enabled) return
        ensure(kind)
        val t = tracks[kind] ?: return
        try {
            if (t.playState == AudioTrack.PLAYSTATE_PLAYING) t.stop()
            t.reloadStaticData()
            t.play()
        } catch (_: Exception) {
        }
    }

    fun release() {
        for (i in 0 until N) {
            runCatching { tracks[i]?.pause(); tracks[i]?.flush(); tracks[i]?.release() }
            tracks[i] = null
        }
    }

    private fun build(kind: Int): ShortArray = when (kind) {
        KEY -> click()
        WORD -> notes(0.30, 0.045 to 784.0, 0.105 to 1175.0)
        ERR -> notes(0.32, 0.080 to 233.0, 0.120 to 165.0)
        SENT -> notes(0.42, 0.070 to 659.0, 0.070 to 880.0, 0.140 to 1319.0)
        DONE -> notes(0.55, 0.085 to 523.0, 0.085 to 659.0, 0.085 to 784.0, 0.200 to 1047.0)
        else -> ShortArray(0)
    }

    /** 机械键盘「嗒」：极短噪声 + 一点金属味 */
    private fun click(): ShortArray {
        val n = (SR * 0.024).toInt()
        val out = ShortArray(n)
        var seed = 12345
        for (i in 0 until n) {
            seed = seed * 1103515245 + 12345
            val noise = ((seed shr 16) and 0x7FFF) / 32768.0 - 1.0
            val t = i.toDouble() / SR
            val env = exp(-t * 165.0)
            val tone = sin(2 * PI * 1850.0 * t) * 0.30
            val v = (noise * 0.52 + tone) * env * 0.34
            out[i] = (v * Short.MAX_VALUE).toInt().coerceIn(-32768, 32767).toShort()
        }
        return out
    }

    private fun notes(volume: Double, vararg seq: Pair<Double, Double>): ShortArray {
        val total = seq.sumOf { (SR * it.first).toInt() }
        val out = ShortArray(total)
        var p = 0
        for ((dur, freq) in seq) {
            val n = (SR * dur).toInt()
            for (i in 0 until n) {
                val t = i.toDouble() / SR
                val atk = (i / (SR * 0.004)).coerceAtMost(1.0)
                val rel = ((n - i) / (SR * 0.030)).coerceAtMost(1.0)
                val s = sin(2 * PI * freq * t) * 0.72 + sin(4 * PI * freq * t) * 0.28
                val v = s * atk * rel * volume * exp(-t * 2.2)
                out[p + i] = (v * Short.MAX_VALUE * 0.85).toInt().coerceIn(-32768, 32767).toShort()
            }
            p += n
        }
        return out
    }
}
