package com.demandradar

import android.accessibilityservice.AccessibilityService
import android.content.Context
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

/**
 * 读屏服务：你正常刷手机，它把屏幕上的文字记下来当需求素材。
 *
 * 设计上刻意保持「人机协作」：
 *   - 只读，从不自动点击/滑动/翻页
 *   - 默认只采白名单 App，避免把系统界面和私密内容一起收进来
 *   - 同一屏内容只记一次，重复刷不会重复计数
 */
class ScreenReaderService : AccessibilityService() {

    private var lastPkg = ""
    private var lastAt = 0L
    private var lastHash = ""

    override fun onServiceConnected() {
        super.onServiceConnected()
        Prefs.migrate(this)
        Prefs.setEnabled(this, true)
        instance = this
    }

    override fun onUnbind(intent: android.content.Intent?): Boolean {
        Prefs.setEnabled(this, false)
        instance = null
        return super.onUnbind(intent)
    }

    override fun onDestroy() {
        Prefs.setEnabled(this, false)
        instance = null
        super.onDestroy()
    }

    override fun onInterrupt() = Unit

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        val e = event ?: return
        when (e.eventType) {
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED,
            AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED,
            AccessibilityEvent.TYPE_VIEW_SCROLLED,
            -> Unit
            else -> return
        }

        val pkg = e.packageName?.toString() ?: return
        if (pkg == packageName) return
        if (!Prefs.collecting(this)) return
        if (Skip.isSystem(pkg)) {
            log("跳过 $pkg（桌面/系统界面）")
            return
        }

        val lex = Lexicon.get(this)
        val named = lex.apps[pkg]
        if (named == null && !Prefs.allowAll(this)) {
            log("跳过 $pkg（不在名单内）")
            return
        }

        // 同一个包最快 1.5 秒一次，避免刷屏时把 CPU 和库塞爆
        val now = System.currentTimeMillis()
        if (pkg == lastPkg && now - lastAt < 1500) return
        lastAt = now
        lastPkg = pkg

        val root = rootInActiveWindow ?: return
        // 关键：必须确认当前活动窗口就是这个 App。
        // 否则切 App 的一瞬间会把上一个 App 的界面内容记到新 App 头上。
        val rootPkg = root.packageName?.toString()
        if (rootPkg != null && rootPkg != pkg) {
            log("跳过 $pkg（活动窗口其实是 $rootPkg，正在切换）")
            return
        }

        val texts = ArrayList<String>(64)
        collect(root, texts, 0)
        if (texts.isEmpty()) return

        // 内容一模一样就不重复入库
        val h = Store.sha1(texts.joinToString("\u0001"))
        if (h == lastHash) return
        lastHash = h

        val it = Hub.ingest(this, pkg, named ?: pkg, texts)
        if (it == null) {
            log("记下但无价值 $pkg（正文太短/与上一屏重复/无信号）")
            return
        }
        log("入库 ${named ?: pkg} ${String.format("%.1f", it.demand)}分 ${Scorer.snippet(it.text, "", 40)}")
        Stats.bump(this, it)
    }

    private fun log(msg: String) {
        Log.i(TAG, msg)
        val ring = recentLogs
        ring.addLast(msg)
        while (ring.size > 40) ring.removeFirst()
    }

    private fun collect(node: AccessibilityNodeInfo?, out: MutableList<String>, depth: Int) {
        if (node == null || depth > 40 || out.size > 400) return
        if (!node.isVisibleToUser) return
        node.text?.toString()?.trim()?.takeIf { it.isNotEmpty() }?.let { out.add(it) }
        node.contentDescription?.toString()?.trim()?.takeIf { it.isNotEmpty() }?.let { out.add(it) }
        for (i in 0 until node.childCount) collect(node.getChild(i), out, depth + 1)
    }

    companion object {
        const val TAG = "DemandRadar"
        val recentLogs = ArrayDeque<String>()

        @Volatile var instance: ScreenReaderService? = null
    }
}

/** 要跳过的包：桌面、系统 UI、输入法、系统设置…全是噪音 */
object Skip {
    private val DENY = Regex(
        "(launcher|systemui|com\\.android\\.|com\\.vivo\\.|com\\.bbk\\.|com\\.iQOO\\.|" +
            "inputmethod|com\\.sohu\\.inputmethod|\\.settings$|com\\.google\\.android\\.|" +
            "com\\.qualcomm\\.|touchpanel|com\\.android\\.systemui|com\\.demandradar)",
        RegexOption.IGNORE_CASE,
    )

    fun isSystem(pkg: String): Boolean = DENY.containsMatchIn(pkg)
}

/** 轻量偏好存储 */
object Prefs {
    private const val NAME = "demand_radar"
    private const val K_ALLOW_ALL = "allow_all"
    private const val K_VER = "prefs_ver"
    private const val VER = 2

    fun allowAll(ctx: Context): Boolean =
        ctx.getSharedPreferences(NAME, Context.MODE_PRIVATE).getBoolean(K_ALLOW_ALL, false)

    fun setAllowAll(ctx: Context, v: Boolean) =
        ctx.getSharedPreferences(NAME, Context.MODE_PRIVATE).edit().putBoolean(K_ALLOW_ALL, v).apply()

    /** 服务是否真的被系统连上了（用它判断无障碍有没有开） */
    fun setEnabled(ctx: Context, v: Boolean) =
        ctx.getSharedPreferences(NAME, Context.MODE_PRIVATE).edit().putBoolean("service_on", v).apply()

    fun enabled(ctx: Context): Boolean =
        ScreenReaderService.instance != null ||
            ctx.getSharedPreferences(NAME, Context.MODE_PRIVATE).getBoolean("service_on", false)

    fun collecting(ctx: Context): Boolean =
        ctx.getSharedPreferences(NAME, Context.MODE_PRIVATE).getBoolean("collecting", true)

    fun setCollecting(ctx: Context, v: Boolean) =
        ctx.getSharedPreferences(NAME, Context.MODE_PRIVATE).edit().putBoolean("collecting", v).apply()

    /**
     * 一次性修正：旧版本可能因为界面开关初始化时序，把「采集所有 App」意外存成了 true。
     * 这里强制改回默认值，只做一次。
     */
    fun migrate(ctx: Context) {
        val sp = ctx.getSharedPreferences(NAME, Context.MODE_PRIVATE)
        if (sp.getInt(K_VER, 0) >= VER) return
        sp.edit().putBoolean(K_ALLOW_ALL, false).putInt(K_VER, VER).apply()
    }
}

/** 简单的运行计数，给通知/界面用 */
object Stats {
    @Volatile var lastDemand: Double = 0.0
    @Volatile var lastText: String = ""
    @Volatile var lastApp: String = ""

    fun bump(ctx: Context, it: Item) {
        lastDemand = it.demand
        lastText = Scorer.snippet(it.text, "", 80)
        lastApp = it.title
    }
}
