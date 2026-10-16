package io.pilink

import android.content.Context
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import okhttp3.Call
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.max

/**
 * 订阅端。协议是自家的（派发台 /pi/stream），不经过任何第三方推送服务。
 *
 * 相比上一版（WebSocket + 第三方中转）：
 *   · 只发一次普通 GET，然后一行一行读 NDJSON —— 没有升级握手，路由器/代理更不容易掐
 *   · 服务端每 `ka` 秒写一条 keepalive，所以 **OkHttp 的 readTimeout 就是硬读截止**：
 *     死链路最多 2×ka+5 秒暴露（默认 20s → 45s），不需要自己攒心跳
 *   · 重连依旧是常驻协程里的循环，不依赖任何特殊权限
 *   · 另有一条 HTTP 轮询兜底（/pi/messages?since=），和主流按消息 id 去重
 */
class Subscriber(
    private val ctx: Context,
    private val prefs: Prefs,
    private val onMessage: (Msg) -> Unit,
    private val onStatus: (String) -> Unit,
) {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val running = AtomicBoolean(false)

    /**
     * 异地出口管理器。地址不再是单一的 prefs.base，而是一份「谁通用谁」的清单
     * （局域网 / 免账号隧道 / 公网 IPv6 / 公网 IPv4），详见 EndpointManager.kt。
     */
    val endpoints = EndpointManager(ctx, prefs)

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        // 【关键】故意不设读超时（readTimeout(0)）。
        // 之前那套 WebSocket 版本就是这么跑的，而且能稳定活很久；
        // 我重写成 HTTP 流式时把它设成了 45s，结果只要有一个 keepalive 迟到
        // （网络抖一下、PC 忙一下）整条流就被自己杀死 —— 这就是日志里
        // “活 112s/289s/115s 后 timeout”的来源。
        // 现在改回：不设读超时，判死全交给下面那个 90 秒静默看门狗。
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .retryOnConnectionFailure(true)
        .build()

    @Volatile private var call: Call? = null
    @Volatile private var connected = false
    @Volatile private var connectedAt = 0L

    /**
     * 进程内去重。主通道（推送流）和轮询兜底可能在同一毫秒拿到同一条消息，
     * 而“检查 seen → 写入 seen”不是原子的：两条协程都可能先看到“没见过”，
     * 于是同一条通知弹两次、回执也回两次（实测过，相差几十毫秒）。
     * 抢锁后再查再写，就不会并发穿过。
     */
    private val seenLock = Any()
    private val seenInMemory = LinkedHashSet<String>()

    private fun claim(id: String): Boolean = synchronized(seenLock) {
        if (seenInMemory.contains(id) || prefs.seen(id)) return@synchronized false
        seenInMemory.add(id)
        while (seenInMemory.size > 400) seenInMemory.remove(seenInMemory.first())
        prefs.rememberSeen(id)
        true
    }

    /**
     * 判活时间戳 = 「最近一次证明这条链路还活着」的时刻。
     * 被两条路刷新：① 推送流上的任何一行（含 keepalive）② 轮询成功。
     * 只认 ① 的话，轮询恰好正常而流失灵时会被误判成死。
     */
    @Volatile private var lastAlive = 0L
    private var attempt = 0

    fun start() {
        if (!running.compareAndSet(false, true)) return
        lastAlive = System.currentTimeMillis()
        Log.i(
            TAG,
            "参数：keepalive ${prefs.pingSeconds}s / 静默判死 ${prefs.staleSeconds}s（读截止 ${readTimeoutSeconds()}s） / " +
                "轮询 ${prefs.pollSeconds}s(已连)·${prefs.idlePollSeconds}s(断开) → ${endpoints.peek()} · " +
                "候选 ${endpoints.candidates().size} 个 · 自动切换 ${if (prefs.autoSwitch) "开" else "关"}",
        )
        scope.launch {
            primeCursorIfNeeded()
            streamLoop()
        }
        scope.launch { watchdogLoop() }
        scope.launch { pollLoop() }
        // 注：曾经还有一个每 30 秒一条的 alive 心跳（用来画“进程活没活”的时间线）。
        // 它只在排查断连期间有用，稳定后就是柱刷屏的噪声，已移除。
        // 现在只在“有事件发生”时上报：断开原因、通知是否被系统收下、服务创建/销毁等。
    }

    /**
     * 首次运行时把游标定到「当前最新那条」的 id（不补发历史）。
     *
     * 为什么必须有这一步：lastId 为空时每一条连接都带 since=none，意思就是
     * 「我什么都不要」。于是就算手机每 2 秒重连一次，断的那几秒里发布的消息
     * **永远不会被补回来** —— 重连再勤也没用。这就是「服务已连接但一条通知都收不到」
     * 的真因（日志里一路都是“补发 0 条”）。定住游标之后，每次重连都会带
     * since=<id> 去补收。
     */
    private fun primeCursorIfNeeded() {
        if (prefs.lastId.isNotEmpty()) return
        try {
            val request = Request.Builder().url(url(endpoints.peek(), "/pi/messages", "since=all")).build()
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return
                val body = response.body?.string() ?: return
                val last = body.lineSequence().filter { it.isNotBlank() }.lastOrNull() ?: return
                val id = JSONObject(last).optString("id", "")
                if (id.isNotEmpty()) {
                    prefs.lastId = id
                    Log.i(TAG, "首发游标已定到 $id（不补发历史，但之后每一条都不会丢）")
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "定游标失败（下次重连会重试）：${e.message}")
        }
    }

    fun stop() {
        running.set(false)
        call?.cancel()
        call = null
        connected = false
    }

    /** 立刻强制重连（界面上的"强制重连"按钮走这里） */
    fun kick() {
        call?.cancel()
    }

    /**
     * 自愈闹钟走这里：只在该动的时候才动。
     *
     * 以前自愈闹钟无条件调 kick()，每 5 分钟把一条健康的流主动掉
     * （日志里那条活 289 秒后断开的，就是它干的）—— 自愈变成了自伤。
     * 现在改成：链路正常就不动它。
     */
    fun healthCheck() {
        val silent = System.currentTimeMillis() - lastAlive
        val staleMs = prefs.staleSeconds * 1000L
        if (connected && silent <= staleMs) return
        call?.cancel()
    }

    // ── 主循环：开流 → 一行行读 → 断了就退避重连。不需要任何权限。 ────────
    private suspend fun streamLoop() {
        while (running.get()) {
            // 游标还空着（首次运行）就先定住它，否则这条流等于白连
            if (prefs.lastId.isEmpty()) primeCursorIfNeeded()
            val base = endpoints.peek()
            val url = streamUrl(base)
            Log.i(TAG, "打开推送流 $url")
            onStatus(
                if (attempt == 0) "连接中…"
                else "重连中（第 $attempt 次）… ${endpoints.labelOf(base)}"
            )
            var reason = "未知"
            /** 401/403 = 令牌或权限不对，换地址也没用，所以不触发轮换 */
            var authRejected = false

            try {
                val request = Request.Builder().url(url).build()
                val current = client.newCall(request)
                call = current
                current.execute().use { response ->
                    if (!response.isSuccessful) {
                        reason = "HTTP ${response.code}"
                        authRejected = response.code == 401 || response.code == 403
                        Log.w(TAG, "推送流被拒绝：$reason${if (authRejected) "（令牌/权限问题，换地址也没用）" else ""}")
                    } else {
                        connected = true
                        connectedAt = System.currentTimeMillis()
                        markAlive()
                        prefs.connectCount = prefs.connectCount + 1
                        attempt = 0
                        endpoints.noteSuccess(base)
                        Log.i(TAG, "推送流已建立（${endpoints.labelOf(base)}）")
                        onStatus("已连接 · ${endpoints.labelOf(base)}")

                        val source = response.body?.source()
                        if (source == null) {
                            reason = "响应没有 body"
                        } else {
                            while (running.get()) {
                                val line = source.readUtf8Line() ?: break // null = 服务端关了
                                if (line.isBlank()) continue
                                markAlive()
                                handleLine(line)
                            }
                            reason = "服务端关闭"
                        }
                    }
                }
            } catch (e: Exception) {
                reason = "${e.javaClass.simpleName}: ${e.message ?: ""}"
                Log.w(TAG, "推送流断开：$reason")
            }

            call = null
            connected = false
            // 连不上就记一笔，并考虑换一个出口接着试。
            // 关键点：重连循环本身就是探测，所以不需要额外的探测请求（不耗电、不被打断）。
            endpoints.noteFailure(base)
            val alternative = if (authRejected) null else endpoints.next(base)
            if (alternative != null && alternative != base) {
                Log.i(TAG, "换一个出口重试：${endpoints.labelOf(alternative)}")
                onStatus("断开（$reason），换地址重连…")
                delay(1_000)
                continue
            }
            // 流一断就立刻补一次：把「断的那几秒里发布的消息」当场捞回来，
            // 不必等下一个轮询周期（默认 30s）。
            if (prefs.lastId.isNotEmpty()) {
                try {
                    pollOnce()
                } catch (e: Exception) {
                    Log.w(TAG, "断线即时补收失败：${e.message}")
                }
            }
            if (!running.get()) break

            val wait = RETRY_MS[minOf(attempt, RETRY_MS.size - 1)]
            attempt++
            onStatus("断开（$reason），${wait / 1000}s 后重连")
            delay(wait)
        }
    }

    // ── 静默看门狗 ────────────────────────────────────────────────────────
    // 只在「自以为连着」+「两条路 90s 都没有活着的证据」时才动。
    private suspend fun watchdogLoop() {
        while (running.get()) {
            delay(10_000)
            if (!running.get()) break
            val silent = System.currentTimeMillis() - lastAlive
            val staleMs = prefs.staleSeconds * 1000L
            if (connected && silent > staleMs) {
                Log.w(TAG, "推送流与轮询双双静默 ${silent / 1000}s（阈值 ${staleMs / 1000}s），强制重连")
                onStatus("链路静默 ${silent / 1000}s，重连中…")
                call?.cancel()
            }
        }
    }

    // ── 轮询兜底：流挂了也不怕 ─────────────────────────────────────────────
    private suspend fun pollLoop() {
        while (running.get()) {
            delay(if (connected) prefs.pollSeconds * 1000L else prefs.idlePollSeconds * 1000L)
            if (!running.get()) break
            try {
                pollOnce()
            } catch (e: Exception) {
                Log.w(TAG, "轮询失败：${e.message}")
            }
        }
    }

    private fun pollOnce() {
        val base = endpoints.peek()
        val request = Request.Builder().url(url(base, "/pi/messages", "since=${sinceParam()}")).build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                Log.w(TAG, "轮询 HTTP ${response.code}")
                return
            }
            // 轮询成功 = 这条路径确实通，是除推送流之外的第二个判活证据
            markAlive()
            endpoints.noteSuccess(base)
            val body = response.body?.string() ?: return
            body.lineSequence().filter { it.isNotBlank() }.forEach { line ->
                try {
                    handleObject(JSONObject(line))
                } catch (e: Exception) {
                    Log.w(TAG, "轮询返回了非 JSON 行：${line.take(80)}")
                }
            }
        }
    }

    // ── 收行 ───────────────────────────────────────────────────────────────
    private fun handleLine(line: String) {
        val obj = try {
            JSONObject(line)
        } catch (e: Exception) {
            return
        }
        handleObject(obj)
    }

    private fun handleObject(obj: JSONObject) {
        // 每一帧都带着候选地址清单（open 帧、每 10 个心跳、每条消息里都有）。
        // 这是手机知道「隧道换了域名」「公网 IP 变了」的唯一途径 —— 必须在
        // event 过滤之前处理，否则 keepalive 帧里带的地址就丢了。
        learnBases(obj)

        // open / keepalive 只算"活着"（上游已刷新 lastAlive），不产生通知
        if (obj.optString("event", "message") != "message") return

        val id = obj.optString("id", "")
        if (id.isEmpty()) return
        // 原子去重（见 claim 的注释）
        if (!claim(id)) return

        prefs.lastId = id

        val msg = Msg.fromJson(obj) ?: return
        onMessage(msg)
        ack(msg)
    }

    /** 收到即回执。有了它，"到底送到没有"是确定的。 */
    private fun ack(msg: Msg) {
        val url = prefs.ackUrl
        if (url.isEmpty()) return
        scope.launch {
            try {
                val payload = JSONObject().apply {
                    put("id", msg.id)
                    put("time", msg.time / 1000L)
                    put("ts", System.currentTimeMillis())
                }.toString()
                val request = Request.Builder()
                    .url(url)
                    .post(payload.toByteArray().toRequestBody(JSON_MEDIA_TYPE))
                    .build()
                client.newCall(request).execute().use { response ->
                    if (response.isSuccessful) {
                        Log.i(TAG, "回执已送达 ${msg.id}")
                    } else {
                        Log.w(TAG, "回执被拒：HTTP ${response.code}（回执地址要带 ?t=<派发台令牌>，或让它免令牌）")
                    }
                }
            } catch (e: Exception) {
                Log.w(TAG, "回执失败：${e.message}")
            }
        }
    }

    /** 从任意一帧里把候选地址清单学下来（去重与排序在 EndpointManager 里做） */
    private fun learnBases(obj: JSONObject) {
        val arr = obj.optJSONArray("bases") ?: return
        if (arr.length() == 0) return
        val list = ArrayList<String>(arr.length())
        for (i in 0 until arr.length()) {
            arr.optString(i, "").takeIf { it.isNotBlank() }?.let { list.add(it) }
        }
        endpoints.learn(list, obj.optString("preferred", "").ifEmpty { null })
    }

    // ── URL ───────────────────────────────────────────────────────────────

    /** 首次安装用 since=none，避免一口气把缓存里的历史消息全弹出来 */
    private fun sinceParam(): String = prefs.lastId.ifEmpty { "none" }

    private fun streamUrl(base: String): String =
        url(base, "/pi/stream", "since=${sinceParam()}&ka=${prefs.pingSeconds}")

    /** @param base 用哪个出口拼 URL —— 异地切换的关键就在这个参数 */
    private fun url(base: String, path: String, params: String): String {
        val token = prefs.token
        return "${base.trimEnd('/')}$path?$params" + if (token.isEmpty()) "" else "&t=$token"
    }

    private fun markAlive() {
        val now = System.currentTimeMillis()
        lastAlive = now
        prefs.lastFrameAt = now
    }

    private fun readTimeoutSeconds(): Long = max(prefs.pingSeconds * 2 + 5, 15).toLong()
    private companion object {
        const val TAG = "PiLink"
        val JSON_MEDIA_TYPE = "application/json".toMediaType()

        /** 退避阶梯：前几档很密，封顶 30s */
        val RETRY_MS = longArrayOf(1_000, 2_000, 3_000, 5_000, 8_000, 13_000, 21_000, 30_000)
    }
}
