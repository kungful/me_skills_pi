package com.wordrush.app.fx

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import android.os.Handler
import android.os.Looper
import kotlin.math.PI
import kotlin.math.exp
import kotlin.math.sin

/**
 * 音效不用音频文件，直接合成 PCM。
 * 好处：APK 里一个音频资源都不用带，音高/音量还能随手改。
 */
object Sfx {

    const val TAP = 0
    const val RIGHT = 1
    const val WRONG = 2
    const val COMBO = 3
    const val WIN = 4
    const val FAIL = 5

    private const val SR = 22050

    var enabled = true

    private val handler = Handler(Looper.getMainLooper())
    private val cache = HashMap<Int, ShortArray>()

    fun play(kind: Int) = emit(kind, 1.0)

    /** 连击越高音越高，形成正反馈 */
    fun playCombo(combo: Int) {
        val shift = when {
            combo >= 15 -> 1.8
            combo >= 10 -> 1.5
            combo >= 6 -> 1.25
            combo >= 3 -> 1.1
            else -> 1.0
        }
        emit(COMBO, shift)
    }

    private fun emit(kind: Int, shift: Double) {
        if (!enabled) return
        val key = kind * 1000 + (shift * 100).toInt()
        val data = cache.getOrPut(key) { build(kind, shift) }
        if (data.isEmpty()) return
        try {
            val track = AudioTrack.Builder()
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_GAME)
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
                .setBufferSizeInBytes(data.size * 2)
                .setTransferMode(AudioTrack.MODE_STATIC)
                .setSessionId(AudioManager.AUDIO_SESSION_ID_GENERATE)
                .build()
            track.write(data, 0, data.size)
            track.play()
            handler.postDelayed({ runCatching { track.release() } }, data.size * 1000L / SR + 300L)
        } catch (_: Exception) {
            // 没声音也不该影响游戏
        }
    }

    private fun build(kind: Int, shift: Double): ShortArray = when (kind) {
        TAP -> notes(0.10, 0.030 to 1200.0 * shift)
        RIGHT -> notes(0.30, 0.055 to 784.0 * shift, 0.130 to 1175.0 * shift)
        WRONG -> notes(0.34, 0.110 to 233.0 * shift, 0.180 to 165.0 * shift)
        COMBO -> notes(0.34, 0.045 to 659.0 * shift, 0.045 to 880.0 * shift, 0.075 to 1319.0 * shift)
        WIN -> notes(0.55, 0.090 to 523.0, 0.090 to 659.0, 0.090 to 784.0, 0.190 to 1047.0)
        FAIL -> notes(0.50, 0.100 to 392.0, 0.100 to 330.0, 0.100 to 262.0, 0.170 to 196.0)
        else -> ShortArray(0)
    }

    /** seq: 依次拼接的 (时长秒, 频率) */
    private fun notes(volume: Double, vararg seq: Pair<Double, Double>): ShortArray {
        val total = seq.sumOf { (SR * it.first).toInt() }
        val out = ShortArray(total)
        var p = 0
        for ((dur, freq) in seq) {
            val n = (SR * dur).toInt()
            for (i in 0 until n) {
                val t = i.toDouble() / SR
                // 5ms 淡入 / 25ms 淡出，避免爆音
                val atk = (i / (SR * 0.005)).coerceAtMost(1.0)
                val rel = ((n - i) / (SR * 0.025)).coerceAtMost(1.0)
                // 叠一点二次谐波，声音更「电子」
                val s = sin(2 * PI * freq * t) * 0.75 + sin(4 * PI * freq * t) * 0.25
                val v = s * atk * rel * volume * exp(-t * 2.0)
                out[p + i] = (v * Short.MAX_VALUE * 0.9).toInt().coerceIn(-32768, 32767).toShort()
            }
            p += n
        }
        return out
    }
}
