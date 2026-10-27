package com.vocabtype.app.core

import android.util.Log
import okhttp3.Dns
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import java.io.ByteArrayOutputStream
import java.net.InetAddress
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.UUID
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/**
 * 微软 Edge「大声朗读」神经语音合成（免费，无需 Key）。
 *
 * 中文音质是目前免费方案里最好的（晓晓/云希…），走 WebSocket 流式，
 * 实测首包 0.2~0.5 秒。协议要点：
 *   · 先发 speech.config（mp3 / 24kHz / 48kbps），再发 ssml；
 *   · 二进制帧**前 2 字节是大端头长度**，跳过后才是音频；
 *   · 文本帧出现 `Path:turn.end` 表示结束。签名见 [EdgeDrm]。
 *
 * ⚠ 手机上常有 Clash / v2ray 之类把 speech.platform.bing.com 解析成
 * 198.18.x.x（fake-ip），但代理没放行这条长连接，于是 TLS 直接被断
 * （SSLHandshakeException: connection closed）。所以这里自带 [Dns]：
 * 一旦发现解析结果落在 fake-ip 段，就换成内置的真实 IP 直连，
 * Host/SNI 仍是原域名。
 */
object EdgeTts {

    private const val TAG = "VTEDGE"
    private const val HOST = "speech.platform.bing.com"

    /** 微软该域名的真实 Anycast 地址（fake-ip 劫持时用它兜底） */
    private val REAL_IPS = arrayOf(
        "150.171.28.10",
        "150.171.27.10",
        "13.107.246.10",
        "13.107.252.10"
    )

    const val VOICE_XIAOXIAO = "zh-CN-XiaoxiaoNeural"
    const val VOICE_XIAOYI = "zh-CN-XiaoyiNeural"
    const val VOICE_YUNXI = "zh-CN-YunxiNeural"
    const val VOICE_YUNYANG = "zh-CN-YunyangNeural"
    const val VOICE_ARIA = "en-US-AriaNeural"
    const val VOICE_AVA = "en-US-AvaNeural"
    const val VOICE_EMMA = "en-US-EmmaNeural"

    class Voice(val id: String, val label: String)

    val ZH_VOICES = listOf(
        Voice(VOICE_XIAOXIAO, "晓晓"),
        Voice(VOICE_XIAOYI, "晓伊"),
        Voice(VOICE_YUNXI, "云希"),
        Voice(VOICE_YUNYANG, "云扬")
    )

    val EN_VOICES = listOf(
        Voice(VOICE_ARIA, "Aria"),
        Voice(VOICE_AVA, "Ava"),
        Voice(VOICE_EMMA, "Emma")
    )

    /** 伪造/代理地址段：198.18.0.0/15（Clash fake-ip 默认）、127.x、0.0.0.0 */
    private fun isFake(ip: String): Boolean =
        ip.startsWith("198.18.") || ip.startsWith("198.19.") ||
                ip.startsWith("127.") || ip == "0.0.0.0"

    /** 自定义 DNS：被劫持时返回真实 IP */
    private val safeDns = object : Dns {
        override fun lookup(hostname: String): List<InetAddress> {
            val raw = runCatching { Dns.SYSTEM.lookup(hostname) }.getOrDefault(emptyList())
            val ips = raw.map { it.hostAddress ?: "" }
            val good = raw.filterNot { isFake(it.hostAddress ?: "") }
            if (good.isNotEmpty() && good.size == raw.size) return raw
            if (hostname == HOST) {
                Log.i(TAG, "DNS 被劫持(" + ips.joinToString(",") + ")，改连真实 IP")
                val out = ArrayList<InetAddress>()
                for (s in REAL_IPS) {
                    runCatching { out.add(InetAddress.getByName(s)) }
                }
                if (out.isNotEmpty()) return out
            }
            return raw
        }
    }

    private val client: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .dns(safeDns)
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(15, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .build()
    }

    /** 阻塞合成，返回 mp3 字节；失败返回 null（后台线程调用） */
    fun synth(text: String, voice: String, ratePercent: Int = 0): ByteArray? {
        if (text.isBlank()) return null
        // 失败重试一次（fake-ip 切换后第一次可能仍失败）
        val first = tryOnce(text, voice, ratePercent)
        if (first != null) return first
        Log.i(TAG, "第一次失败，重试")
        return tryOnce(text, voice, ratePercent)
    }

    private fun tryOnce(text: String, voice: String, ratePercent: Int): ByteArray? {
        val connId = UUID.randomUUID().toString().replace("-", "")
        val gec = EdgeDrm.generateSecMsGec()
        val url = EdgeDrm.WSS_URL +
                "&ConnectionId=" + connId +
                "&Sec-MS-GEC=" + gec +
                "&Sec-MS-GEC-Version=" + EdgeDrm.SEC_MS_GEC_VERSION

        val req = Request.Builder()
            .url(url)
            .header("Origin", "chrome-extension://jdiccldimpdaibmpdkjnbmckianbfold")
            .header("Pragma", "no-cache")
            .header("Cache-Control", "no-cache")
            .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " +
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0")
            .header("Accept-Language", "en-US,en;q=0.9")
            .build()

        val out = ByteArrayOutputStream(48 * 1024)
        val done = CountDownLatch(1)
        val failed = AtomicBoolean(false)
        val frames = intArrayOf(0)

        val lsn = object : WebSocketListener() {
            override fun onOpen(ws: WebSocket, response: Response) {
                try {
                    ws.send(configMsg())
                    ws.send(ssmlMsg(text, voice, ratePercent))
                } catch (e: Exception) {
                    Log.w(TAG, "send fail: " + e.message)
                    failed.set(true)
                    done.countDown()
                }
            }

            override fun onMessage(ws: WebSocket, bytes: ByteString) {
                try {
                    val b = bytes.toByteArray()
                    if (b.size < 2) return
                    val hdr = ((b[0].toInt() and 0xFF) shl 8) or (b[1].toInt() and 0xFF)
                    val startPos = 2 + hdr
                    if (b.size > startPos) {
                        out.write(b, startPos, b.size - startPos)
                        frames[0]++
                    }
                } catch (_: Exception) {
                }
            }

            override fun onMessage(ws: WebSocket, text: String) {
                if (text.contains("Path:turn.end")) {
                    runCatching { ws.close(1000, null) }
                    done.countDown()
                } else if (text.contains("Path:error")) {
                    Log.w(TAG, "server error: " + text.take(200))
                    failed.set(true)
                    done.countDown()
                }
            }

            override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                Log.w(TAG, "ws FAIL " + t.javaClass.simpleName + ": " + t.message +
                        " http=" + (response?.code ?: 0))
                failed.set(true)
                done.countDown()
            }

            override fun onClosed(ws: WebSocket, code: Int, reason: String) {
                done.countDown()
            }
        }

        return try {
            val ws = client.newWebSocket(req, lsn)
            val ok = done.await(30, TimeUnit.SECONDS)
            if (!ok) {
                runCatching { ws.cancel() }
                Log.w(TAG, "timeout frames=" + frames[0] + " bytes=" + out.size())
                null
            } else {
                val data = out.toByteArray()
                Log.i(TAG, "synth frames=" + frames[0] + " bytes=" + data.size +
                        " failed=" + failed.get())
                if (failed.get() || data.size < 1024) null else data
            }
        } catch (e: Exception) {
            Log.w(TAG, "synth ex: " + e.message)
            null
        }
    }

    /** 自检：后台合成一句中文，日志可见成败与耗时 */
    fun selfTestAsync() {
        Thread {
            val t0 = System.currentTimeMillis()
            val r = synth("文明，文化", VOICE_XIAOXIAO, 0)
            Log.i(
                TAG,
                "selfTest zh -> " + (r?.size ?: -1) + "B in " +
                        (System.currentTimeMillis() - t0) + "ms"
            )
        }.start()
    }

    private fun dateString(): String {
        val f = SimpleDateFormat(
            "EEE MMM dd yyyy HH:mm:ss 'GMT+0000 (Coordinated Universal Time)'", Locale.US
        )
        f.timeZone = TimeZone.getTimeZone("UTC")
        return f.format(Date())
    }

    private fun configMsg(): String =
        "X-Timestamp:" + dateString() + "\r\n" +
                "Content-Type:application/json; charset=utf-8\r\n" +
                "Path:speech.config\r\n\r\n" +
                "{\"context\":{\"synthesis\":{\"audio\":{\"metadataoptions\":{" +
                "\"sentenceBoundaryEnabled\":\"false\",\"wordBoundaryEnabled\":\"false\"}," +
                "\"outputFormat\":\"audio-24khz-48kbitrate-mono-mp3\"}}}}\r\n"

    private fun esc(s: String): String = s
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")

    private fun ssmlMsg(text: String, voice: String, ratePercent: Int): String {
        val lang = voice.substringBefore('-')
        val name = voice.substringAfter('-')
        val rate = if (ratePercent >= 0) "+" + ratePercent + "%" else ratePercent.toString() + "%"
        val ssml = "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='" + lang + "'>" +
                "<voice name='Microsoft Server Speech Text to Speech Voice (" + lang + ", " + name + ")'>" +
                "<prosody rate='" + rate + "' volume='+0%' pitch='+0Hz'>" + esc(text) + "</prosody>" +
                "</voice></speak>"
        return "X-RequestId:" + UUID.randomUUID().toString().replace("-", "").uppercase() + "\r\n" +
                "Content-Type:application/ssml+xml\r\n" +
                "X-Timestamp:" + dateString() + "\r\n" +
                "Path:ssml\r\n\r\n" + ssml
    }
}
