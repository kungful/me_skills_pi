package io.pilink

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONArray
import org.json.JSONObject

/**
 * 一个「出口地址」：手机能用来连这台电脑的任意一个地址。
 *
 * 异地通知的核心思路：手机手里有一份清单，谁通用谁（详见 EndpointManager.kt）。
 * 清单里的东西有两个来源：
 *   1. /app 页一键配置时随深链一起传进来的（bases 参数）
 *   2. 之后每条推送流的 open 帧、每 10 个心跳、以及每条消息里带回来的 bases
 * 所以公网 IP 变了、隧道换域名了，手机自己就会更新，不需要再配一次。
 */
data class Endpoint(
    val base: String,
    /** lan / tunnel / ipv6 / ipv4 / custom / manual —— 只用于显示与排序 */
    val kind: String = "custom",
    /** 连续失败次数。两次以上就排到最后，降到 0 才回到前面 */
    val fails: Int = 0,
    /** 最后一次连通的时刻（排序时优先） */
    val lastOkAt: Long = 0L,
    val lastTryAt: Long = 0L,
)

/**
 * 全部状态放一个 SharedPreferences 里，故意不引 Room/DataStore：
 * 这一层的数据量（一个游标 id、400 个去重 id、50 条历史）不值得多一个依赖。
 */
class Prefs(context: Context) {

    private val sp: SharedPreferences =
        context.applicationContext.getSharedPreferences("pilink", Context.MODE_PRIVATE)

    /** 派发台地址（例：http://192.168.1.100:8787）—— 消息中转也在它身上 */
    var base: String
        get() = (sp.getString(K_BASE, "http://192.168.1.100:8787") ?: "").trim().trimEnd('/')
        set(v) = sp.edit().putString(K_BASE, v.trim().trimEnd('/')).apply()

    /** 派发台令牌。推送流与轮询都要带它 */
    var token: String
        get() = (sp.getString(K_TOKEN, "") ?: "").trim()
        set(v) = sp.edit().putString(K_TOKEN, v.trim()).apply()

    /** 收条成功后回调的地址（可空） */
    var ackUrl: String
        get() = (sp.getString(K_ACK, "") ?: "").trim()
        set(v) = sp.edit().putString(K_ACK, v.trim()).apply()

    // ── 异地（公网）出口 ─────────────────────────────────────────────────
    /**
     * 异地自动切换。关掉 = 死死用上面那个「派发台地址」，不探测、不换。
     * 开着 = 上面那个作为首选，通了就用；不通就在候选清单里自动换下一个。
     */
    var autoSwitch: Boolean
        get() = sp.getBoolean(K_AUTO_SWITCH, true)
        set(v) = sp.edit().putBoolean(K_AUTO_SWITCH, v).apply()

    /** 当前正在用的出口（空 = 还没选过，用 prefs.base） */
    var activeBase: String
        get() = (sp.getString(K_ACTIVE, "") ?: "").trim()
        set(v) = sp.edit().putString(K_ACTIVE, v.trim().trimEnd('/')).apply()

    /** 已知候选出口（手动配的 base 不在这里，它单独存） */
    fun endpoints(): List<Endpoint> {
        val raw = sp.getString(K_ENDPOINTS, "[]") ?: "[]"
        val out = ArrayList<Endpoint>()
        try {
            val arr = JSONArray(raw)
            for (i in 0 until arr.length()) {
                val o = arr.optJSONObject(i) ?: continue
                val base = o.optString("base", "").trim().trimEnd('/')
                if (base.isEmpty()) continue
                out.add(
                    Endpoint(
                        base = base,
                        kind = o.optString("kind", guessKind(base)),
                        fails = o.optInt("fails", 0),
                        lastOkAt = o.optLong("lastOkAt", 0L),
                        lastTryAt = o.optLong("lastTryAt", 0L),
                    )
                )
            }
        } catch (e: Exception) {
            // 存坏了就当没存过 —— 不能因为一个 JSON 坏掉就让整个 App 起不来
        }
        return out
    }

    fun saveEndpoints(list: List<Endpoint>) {
        val arr = JSONArray()
        list.take(12).forEach { e ->
            arr.put(
                JSONObject().apply {
                    put("base", e.base)
                    put("kind", e.kind)
                    put("fails", e.fails)
                    put("lastOkAt", e.lastOkAt)
                    put("lastTryAt", e.lastTryAt)
                }
            )
        }
        sp.edit().putString(K_ENDPOINTS, arr.toString()).apply()
    }

    /** 忘了某个地址（设置页里手动删） */
    fun forgetEndpoint(base: String) {
        val clean = base.trim().trimEnd('/')
        saveEndpoints(endpoints().filterNot { it.base == clean })
        if (activeBase == clean) activeBase = ""
    }

    /** 从地址形状猜一个类型（只影响界面上的标签，猜错不影响能不能连） */
    fun guessKind(base: String): String = when {
        base.startsWith("https://") -> "tunnel"
        base.contains("[") && base.contains("]") -> "ipv6"
        Regex("^http://(10\\.|192\\.168\\.|172\\.(1[6-9]|2\\d|3[01])\\.|127\\.|localhost)").containsMatchIn(base) -> "lan"
        else -> "ipv4"
    }

    /** 用户是否希望常驻订阅。开机自启只看这个标志。 */
    var enabled: Boolean
        get() = sp.getBoolean(K_ENABLED, false)
        set(v) = sp.edit().putBoolean(K_ENABLED, v).apply()

    /** 是否已经弹过「加电池白名单」的引导（只弹一次，不骚扰） */
    var whitelistAsked: Boolean
        get() = sp.getBoolean(K_WL_ASKED, false)
        set(v) = sp.edit().putBoolean(K_WL_ASKED, v).apply()

    /** 最后一条收到的消息 id。重连时带 since=<它>，把断线期间漏掉的补回来。 */
    var lastId: String
        get() = sp.getString(K_LAST_ID, "") ?: ""
        set(v) = sp.edit().putString(K_LAST_ID, v).apply()

    /** 人类可读的连接状态，界面每秒读一次 */
    var status: String
        get() = sp.getString(K_STATUS, "未启动") ?: "未启动"
        set(v) = sp.edit().putString(K_STATUS, v).apply()

    var lastFrameAt: Long
        get() = sp.getLong(K_LAST_FRAME, 0L)
        set(v) = sp.edit().putLong(K_LAST_FRAME, v).apply()

    var connectCount: Int
        get() = sp.getInt(K_CONNECTS, 0)
        set(v) = sp.edit().putInt(K_CONNECTS, v).apply()

    // ── 心跳与重连节奏（全在客户端，服务端不用管） ──────────────────────────
    // 这几个值的含义：
    //   pingSeconds     多久没收到任何帧就发一个 WebSocket PING；再等同样久没 PONG 就判死
    //   staleSeconds    两条路（WS 帧 + HTTP 轮询）都静默这么久 → 强制重连
    //   pollSeconds     已连接时的轮询兜底间隔（独立的第二条通道，用来补 WS 漏掉的）
    //   idlePollSeconds 未连接时的轮询重试间隔
    // 更短 = 更早发现断线、恢复更快；代价是手机无线电唤醒更频繁、耗电略增。

    var pingSeconds: Int
        get() = sp.getInt(K_PING, D_PING).coerceIn(5, 300)
        set(v) = sp.edit().putInt(K_PING, v).apply()

    var staleSeconds: Int
        get() = sp.getInt(K_STALE, D_STALE).coerceIn(30, 900)
        set(v) = sp.edit().putInt(K_STALE, v).apply()

    var pollSeconds: Int
        get() = sp.getInt(K_POLL, D_POLL).coerceIn(10, 600)
        set(v) = sp.edit().putInt(K_POLL, v).apply()

    var idlePollSeconds: Int
        get() = sp.getInt(K_IDLE_POLL, D_IDLE_POLL).coerceIn(5, 300)
        set(v) = sp.edit().putInt(K_IDLE_POLL, v).apply()

    fun resetTuning() = sp.edit()
        .putInt(K_PING, D_PING)
        .putInt(K_STALE, D_STALE)
        .putInt(K_POLL, D_POLL)
        .putInt(K_IDLE_POLL, D_IDLE_POLL)
        .apply()

    // ── 去重 ───────────────────────────────────────────────────────────────
    // WS 和轮询兜底是两条独立的路，同一条消息可能两边都到，所以必须按 id 去重。
    fun seen(id: String): Boolean = sp.getStringSet(K_SEEN, emptySet())?.contains(id) ?: false

    fun rememberSeen(id: String) {
        val set = (sp.getStringSet(K_SEEN, emptySet()) ?: emptySet()).toMutableSet()
        set.add(id)
        // 只留最近 400 个，免得这个 Set 无限长
        val trimmed = if (set.size > 400) set.toList().takeLast(400).toSet() else set.toSet()
        sp.edit().putStringSet(K_SEEN, trimmed).apply()
    }

    // ── 本地历史（离线可查） ────────────────────────────────────────────────
    fun history(): List<Msg> {
        val raw = sp.getString(K_HISTORY, "[]") ?: "[]"
        return try {
            val arr = JSONArray(raw)
            (0 until arr.length()).mapNotNull { i -> arr.optJSONObject(i)?.let { Msg.fromJson(it) } }
        } catch (e: Exception) {
            emptyList()
        }
    }

    fun addHistory(m: Msg) {
        val list = ArrayList(history())
        list.add(0, m)
        while (list.size > 50) list.removeAt(list.size - 1)
        val arr = JSONArray()
        list.forEach { arr.put(it.toJson()) }
        sp.edit().putString(K_HISTORY, arr.toString()).apply()
    }

    fun clearHistory() = sp.edit().putString(K_HISTORY, "[]").apply()

    private companion object {
        const val K_BASE = "base"
        const val K_TOKEN = "token"
        const val K_ACK = "ackUrl"
        const val K_ENABLED = "enabled"
        const val K_WL_ASKED = "whitelistAsked"
        const val K_LAST_ID = "lastId"
        const val K_STATUS = "status"
        const val K_LAST_FRAME = "lastFrameAt"
        const val K_CONNECTS = "connects"
        const val K_SEEN = "seen"
        const val K_HISTORY = "history"
        const val K_PING = "pingSeconds"
        const val K_STALE = "staleSeconds"
        const val K_POLL = "pollSeconds"
        const val K_IDLE_POLL = "idlePollSeconds"
        const val K_AUTO_SWITCH = "autoSwitch"
        const val K_ACTIVE = "activeBase"
        const val K_ENDPOINTS = "endpoints"

        // 默认值与 Subscriber 里的行为一致：20s 心跳 / 90s 静默判死 / 30s、10s 轮询
        const val D_PING = 20
        const val D_STALE = 90
        const val D_POLL = 30
        const val D_IDLE_POLL = 10
    }
}
