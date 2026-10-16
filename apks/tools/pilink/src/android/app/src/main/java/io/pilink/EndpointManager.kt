package io.pilink

import android.content.Context
import android.util.Log
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

/**
 * 异地出口的挑选与轮换 —— 「不用服务器也能在外面收到通知」的全部手机端逻辑。
 *
 * ── 为什么手机手里要有一份清单 ─────────────────────────────────────────
 * 服务端没法主动联系一部在外面的手机（那就变成要账号的推送服务了）。所以反过来做：
 * 电脑把「所有能连到它的地址」都告诉手机（局域网 / 免账号隧道 / 公网 IPv6 /
 * 公网 IPv4），手机自己挨个试，谁通用谁。
 *
 * 清单会自己更新，不需要用户再配一次：
 *   · 每次推送流建立（event=open）→ 服务端把当下全部候选地址发过来
 *   · 每 10 个心跳 → 再发一次（所以「隧道重启换了域名」也能学到）
 *   · 每条消息里也带一份（轮询兵底通道拿到的消息同样能学到）
 *   · /app 页的「一键配置」深链里也带一份（出门前在家里点一下就行）
 *
 * ── 切换策略 ───────────────────────────────────────────────────────────
 *   · 手动配的那个地址永远排第一（它是你确认过的）
 *   · 已经在用的地址先试；连不上就换下一个（重连循环本身就是探测）
 *   · 某个地址连续失败 2 次就排到最后，连通一次就清零
 *   · 令牌错（HTTP 401）时**不**换地址 —— 换也没用，令牌是同一个
 */
class EndpointManager(private val ctx: Context, private val prefs: Prefs) {

    /** 探测用的客户端：必须很短，否则换一个地址要等十几秒。宁可直接试错。 */
    private val prober = OkHttpClient.Builder()
        .connectTimeout(2_500, TimeUnit.MILLISECONDS)
        .readTimeout(2_500, TimeUnit.MILLISECONDS)
        .callTimeout(3_500, TimeUnit.MILLISECONDS)
        .retryOnConnectionFailure(false)
        .build()

    /** 同一个地址刚失败过就不马上重试（避免死磕一个已经没用的地址） */
    private val cooldownMs = 20_000L

    private fun manual(): String = prefs.base.trimEnd('/')

    /** 候选清单：手动地址第一，其余按「最后连通时间 → 失败次数」排 */
    fun candidates(): List<Endpoint> {
        val learned = prefs.endpoints()
            .filter { it.base != manual() }
            .sortedWith(
                compareByDescending<Endpoint> { it.fails == 0 }
                    .thenByDescending { it.lastOkAt }
                    .thenBy { it.fails },
            )
        val out = ArrayList<Endpoint>()
        if (manual().isNotEmpty()) {
            out.add(Endpoint(manual(), "manual", 0, prefs.lastFrameAt, 0L))
        }
        out.addAll(learned)
        return out
    }

    /** 下一轮该试哪个（关掉自动切换时永远是手动地址） */
    fun peek(): String {
        if (!prefs.autoSwitch) return manual()
        val active = prefs.activeBase
        val all = candidates()
        if (active.isNotEmpty() && all.any { it.base == active }) {
            val entry = all.first { it.base == active }
            if (entry.fails == 0 || System.currentTimeMillis() - entry.lastTryAt > cooldownMs) return active
        }
        return all.firstOrNull()?.base ?: manual()
    }

    /**
     * 上一个地址试过了都不行 → 换一个。exclude 是刚失败的那个。
     * 返回 null 表示「候选都轮完了」，调用方应该回到退避等待、下轮从头再来
     * （下一轮可能已经有新地址学进来了）。
     */
    fun next(exclude: String?): String? {
        if (!prefs.autoSwitch) return null
        val all = candidates().map { it.base }
        if (all.size <= 1) return null
        val now = System.currentTimeMillis()
        return all.firstOrNull { it != exclude && it != manual() && !isCooling(it, now) }
            ?: all.firstOrNull { it != exclude }
    }

    private fun isCooling(base: String, now: Long): Boolean {
        val entry = prefs.endpoints().firstOrNull { it.base == base } ?: return false
        return entry.fails > 0 && now - entry.lastTryAt < cooldownMs
    }

    fun noteSuccess(base: String) {
        val now = System.currentTimeMillis()
        update(base) { it.copy(fails = 0, lastOkAt = now, lastTryAt = now) }
        if (prefs.activeBase != base) {
            prefs.activeBase = base
            Log.i(TAG, "出口切到 $base（${labelOf(base)}）")
        }
    }

    fun noteFailure(base: String) {
        val now = System.currentTimeMillis()
        update(base) { it.copy(fails = it.fails + 1, lastTryAt = now) }
    }

    /**
     * 从服务端下发的帧里学地址。
     * 只在「确实有变化」时才写盘（心跳每 ka 秒一帧，不这么做会把 SharedPreferences 写爆）。
     */
    fun learn(bases: List<String>, preferred: String?) {
        val clean = bases.map { it.trim().trimEnd('/') }
            .filter { it.startsWith("http://") || it.startsWith("https://") }
            .distinct()
        if (clean.isEmpty()) return
        val now = System.currentTimeMillis()
        val old = prefs.endpoints()
        val merged = ArrayList<Endpoint>()
        for (base in clean) {
            val prev = old.firstOrNull { it.base == base }
            // 服务端排在越前面越优先（局域网 → 隧道 → IPv6 → IPv4），
            // 排序上体现为：旧清单里没有的插到前面（它们通常刚被加进来）
            merged.add(
                prev?.copy(kind = prefs.guessKind(base), lastTryAt = if (prev.lastOkAt > 0) prev.lastTryAt else now)
                    ?: Endpoint(base, prefs.guessKind(base), 0, 0L, now)
            )
        }
        // 已经被替换掉的老地址（比如隧道换了域名）保留最后一条痕迹，但排到末尾
        for (e in old) if (merged.none { it.base == e.base }) merged.add(e.copy(fails = e.fails + 1))
        if (preferred != null) {
            val i = merged.indexOfFirst { it.base == preferred.trimEnd('/') }
            if (i > 0) merged.add(0, merged.removeAt(i))
        }
        val trimmed = merged.sortedByDescending { it.base in clean.take(3) }.take(12)
        if (trimmed.map { it.base to it.fails } != old.map { it.base to it.fails }) {
            prefs.saveEndpoints(trimmed)
            Log.i(TAG, "学到 ${clean.size} 个候选出口：${clean.joinToString(" , ")}")
        }
    }

    /** 设置页的「挨个探一遍」。返回 base → 通不通 */
    suspend fun probeAll(): List<Pair<Endpoint, Boolean>> {
        val out = ArrayList<Pair<Endpoint, Boolean>>()
        for (e in candidates()) {
            out.add(e to probe(e.base))
        }
        return out
    }

    /** 便宜地探一个地址：打 /pi/ping（顺带把候选清单也拿回来） */
    fun probe(base: String): Boolean {
        val token = prefs.token
        val url = "$base/pi/ping" + if (token.isEmpty()) "" else "?t=$token"
        return try {
            val request = Request.Builder().url(url).build()
            prober.newCall(request).execute().use { response ->
                val ok = response.isSuccessful
                if (ok) noteSuccess(base) else noteFailure(base)
                ok
            }
        } catch (e: Exception) {
            noteFailure(base)
            false
        }
    }

    fun forceBase(base: String) {
        prefs.activeBase = base
        update(base) { it.copy(fails = 0) }
    }

    /** 界面上显示的标签：只影响可读性 */
    fun labelOf(base: String): String {
        val kind = if (base == manual()) "manual" else (prefs.endpoints().firstOrNull { it.base == base }?.kind ?: prefs.guessKind(base))
        val host = base.removePrefix("https://").removePrefix("http://").trimEnd('/')
        val name = when (kind) {
            "manual" -> "手动配置"
            "lan" -> "局域网"
            "tunnel" -> "免账号隧道"
            "ipv6" -> "公网 IPv6"
            "ipv4" -> "公网 IPv4"
            else -> "其他"
        }
        return "$name · $host"
    }

    private fun update(base: String, block: (Endpoint) -> Endpoint) {
        if (base.isEmpty()) return
        val list = prefs.endpoints().toMutableList()
        val i = list.indexOfFirst { it.base == base }
        if (i < 0) {
            if (list.size >= 12) return
            list.add(block(Endpoint(base, prefs.guessKind(base))))
        } else {
            list[i] = block(list[i])
        }
        prefs.saveEndpoints(list)
    }

    private companion object {
        const val TAG = "PiLink"
    }
}
