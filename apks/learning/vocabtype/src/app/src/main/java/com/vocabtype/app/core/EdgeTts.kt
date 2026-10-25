package com.vocabtype.app.core

import android.util.Log
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import okio.ByteString.Companion.toByteString
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * 微软 Edge「大声朗读」神经语音合成。
 *
 * 这是目前免费方案里中文/英文音质最好的（晓晓、云希、Aria…），
 * 走 WebSocket 流式，实测首包 0.2~0.5 秒，够实时用。
 *
 * 协议：连上后先发 speech.config（指定 mp3/24kHz/48kbps），
 * 再发 ssml，服务端回若干二进制帧（每帧前 2 字节是大端头长度），
 * 直到收到文本帧 "Path:turn.end"。
 *
 * 签名见 [EdgeDrm]。
 */
object EdgeTts {

    private const val TAG = "VTEDGE"

    const val VOICE_XIAOXIAO = "zh-CN-XiaoxiaoNeural"
    const val VOICE_XIAOYI = "zh-CN-XiaoyiNeural"
    const val VOICE_YUNXI = "zh-CN-YunxiNeural"
    const val VOICE_YUNYANG = "zh-CN-YunyangNeural"
    const val VOICE_ARIA = "en-US-AriaNeural"
    const val VOICE_AVA = "en-US-AvaNeural"
    const val VOICE_EMMA = "en-US-EmmaNeural"

    private val client: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(8, TimeUnit.SECONDS)
            .readTimeout(20, TimeUnit.SECONDS)
            .writeTimeout(10, TimeUnit.SECONDS)
            .build()
    }

    /** 中文音色表（界面用） */
    val ZH_VOICES = listOf(
        Voice(VOICE_XIAOXIAO, "晓晓（女·自然）"),
        Voice(VOICE_XIAOYI, "晓伊（女·活泼）"),
        Voice(VOICE_YUNXI, "云希（男·年轻）"),
        Voice(VOICE_YUNYANG, "云扬（男·播音）")
    )

    class Voice(val id: String, val label: String)

    /**
     * 合成一段文本，返回 mp3 字节；失败返回 null。
     * 这个是阻塞调用，必须在后台线程用。
     */
    fun synth(text: String, voice: String, ratePercent: Int = 0): ByteArray? {
        if (text.isBlank()) return null
        val connId = java.util.UUID.randomUUID().toString().replace("-", "")
        val gec = EdgeDrm.generateSecMsGec()
        val url = "${EdgeDrm.WSS_URL}&ConnectionId=$connId" +
                "&Sec-MS-GEC=$gec&Sec-MS-GEC-Version=${EdgeDrm.SEC_MS_GEC_VERSION}"

        val req = Request.Builder()
            .url(url)
            .header("Origin", "chrome-extension://jdiccldimpdaibmpdkjnbmckianbfold")
            .header("Pragma", "no-cache")
            .header("Cache-Control", "no-cache")
            .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " +
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0")
            .header("Accept-Language", "en-US,en;q=0.9")
            .build()

        val out = java.io.ByteArrayOutputStream(32 * 1024)
        val done = CountDownLatch(1)
        val failedFlag = java.util.concurrent.atomic.AtomicBoolean(false)

        val lsn = object : WebSocketListener() {
            override fun onOpen(ws: WebSocket, response: Response) {
                try {
                    ws.send(configMsg())
                    ws.send(ssmlMsg(text, voice, ratePercent))
                } catch (e: Exception) {
                    failedFlag.set(true)
                    done.countDown()
                }
            }

            override fun onMessage(ws: WebSocket, bytes: ByteString) {
                try {
                    val b = bytes.toByteArray()
                    if (b.size < 2) return
                    // 头长度是大端 uint16
                    val hdr = ((b[0].toInt() and 0xFF) shl 8) or (b[1].toInt() and 0xFF)
                    val start = 2 + hdr
                    if (b.size > start) out.write(b, start, b.size - start)
                } catch (_: Exception) {
                }
            }

            override fun onMessage(ws: WebSocket, text: String) {
                if (text.contains("Path:turn.end")) {
                    runCatching { ws.close(1000, null) }
                    done.countDown()
                } else if (text.contains("Path:error")) {
                    Log.w(TAG, "server error: ${text.take(200)}")
                    failedFlag.set(true)
                    done.countDown()
                }
            }

            override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                Log.w(TAG, "ws fail: ${t.message} http=${response?.code}")
                failedFlag.set(true)
                done.countDown()
            }

            override fun onClosed(ws: WebSocket, code: Int, reason: String) {
                done.countDown()
            }
        }

        return try {
            val ws = client.newWebSocket(req, lsn)
            if (!done.await(25, TimeUnit.SECONDS)) {
                runCatching { ws.cancel() }
                Log.w(TAG, "synth timeout")
                return null
            }
            val data = out.toByteArray()
            if (failedFlag.get() || data.size < 1024) null else data
        } catch (e: Exception) {
            Log.w(TAG, "synth ex: ${e.message}")
            null
        }
    }

    private fun dateString(): String {
        val f = SimpleDateFormat("EEE MMM dd yyyy HH:mm:ss 'GMT+0000 (Coordinated Universal Time)'", Locale.US)
        f.timeZone = TimeZone.getTimeZone("UTC")
        return f.format(Date())
    }

    private fun configMsg(): String =
        "X-Timestamp:${dateString()}\r\n" +
                "Content-Type:application/json; charset=utf-8\r\n" +
                "Path:speech.config\r\n\r\n" +
                "{\"context\":{\"synthesis\":{\"audio\":{\"metadataoptions\":{" +
                "\"sentenceBoundaryEnabled\":\"false\",\"wordBoundaryEnabled\":\"false\"}," +
                "\"outputFormat\":\"audio-24khz-48kbitrate-mono-mp3\"}}}}\r\n"

    private fun esc(s: String): String =
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    private fun ssmlMsg(text: String, voice: String, ratePercent: Int): String {
        val lang = voice.substringBefore('-')
        val name = voice.substringAfter('-')
        val rate = if (ratePercent >= 0) "+${ratePercent}%" else "${ratePercent}%"
        val ssml = "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='$lang'>" +
                "<voice name='Microsoft Server Speech Text to Speech Voice ($lang, $name)'>" +
                "<prosody rate='$rate' volume='+0%' pitch='+0Hz'>${esc(text)}</prosody>" +
                "</voice></speak>"
        return "X-RequestId:${java.util.UUID.randomUUID().toString().replace("-", "").uppercase()}\r\n" +
                "Content-Type:application/ssml+xml\r\n" +
                "X-Timestamp:${dateString()}\r\n" +
                "Path:ssml\r\n\r\n" + ssml
    }
}
