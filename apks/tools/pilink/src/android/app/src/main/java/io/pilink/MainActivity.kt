package io.pilink

import android.app.Activity
import android.app.AlertDialog
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.provider.Settings
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 主界面 = 只读的消息流。刻意【没有】任何输入框：
 * 编辑型控件要是常驻在首屏，误触就改了配置，而配置错了的表现是"看着已连接、其实收不到"。
 * 所有编辑动作都收进 SettingsActivity（右上角"设置"按钮进入）。
 */
class MainActivity : Activity() {

    private lateinit var prefs: Prefs
    private lateinit var dot: TextView
    private lateinit var statusText: TextView
    private lateinit var target: TextView
    private lateinit var listBox: LinearLayout
    private lateinit var emptyHint: TextView
    private lateinit var warnBox: TextView
    private var listSignature = ""

    private val handler = Handler(Looper.getMainLooper())
    private val ticker = object : Runnable {
        override fun run() {
            refresh()
            handler.postDelayed(this, 1_000)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = Prefs(this)
        setContentView(buildUi())
        applyDeepLink(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        applyDeepLink(intent)
    }

    override fun onResume() {
        super.onResume()
        // 从设置页回来时配置可能变了
        target.text = targetLabel()
        listSignature = ""
        handler.post(ticker)
        maybeAskWhitelist()
    }

    /**
     * 一次性提示加电池白名单。
     *
     * 为什么这件事必须做：Android 在息屏闲置后进 Doze，会**给所有 App 断网**；
     * 只有「电池优化白名单」里的应用被豁免。实测证据（当年服务端统计，手机放下 1 分钟内两个客户端一起掉）：
     *   10:04:13 subscribers=1   ← 你在用手机
     *   10:05:13 subscribers=0   ← 手机刚放下，两个客户端一起掉
     * 也就是说：不白名单，任何长连接客户端（包括本 App）手机放兜里时都收不到。
     */
    private fun maybeAskWhitelist() {
        try {
            val pm = getSystemService(PowerManager::class.java)
            if (pm.isIgnoringBatteryOptimizations(packageName)) return
            if (prefs.whitelistAsked) return
            prefs.whitelistAsked = true
            AlertDialog.Builder(this)
                .setTitle("还差一步：电池白名单")
                .setMessage(
                    "Android 息屏闲置后会进 Doze，并给所有应用断网 —— 只有电池优化白名单里的应用被豁免。\n\n" +
                        "不进白名单的话，手机放兜里时本应用也收不到通知。"
                )
                .setPositiveButton("去设置") { _, _ -> askBattery() }
                .setNegativeButton("稍后", null)
                .show()
        } catch (e: Exception) {
            // 拿不到就算了，不打扰
        }
    }

    private fun askBattery() {
        try {
            startActivity(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:$packageName")))
        } catch (e: Exception) {
            try {
                startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
            } catch (e2: Exception) {
                toast("请手动到 设置 → 电池 里给本应用开白名单")
            }
        }
    }

    override fun onPause() {
        super.onPause()
        handler.removeCallbacks(ticker)
    }

    // ── 界面骨架 ───────────────────────────────────────────────────────────

    private fun buildUi(): View {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(C.BG)
        }

        // 顶栏：标题 + 状态 + 设置按钮
        val bar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(18), dp(14), dp(12), dp(10))
        }
        bar.addView(TextView(this).apply {
            text = getString(R.string.app_name)
            textSize = 20f
            setTypeface(typeface, Typeface.BOLD)
            setTextColor(C.TEXT)
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        bar.addView(button("设置", false) {
            startActivity(Intent(this, SettingsActivity::class.java))
        })
        root.addView(bar)

        // 状态行：一个色点 + 一句话 + 目标地址
        val statusRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(18), 0, dp(18), dp(4))
        }
        dot = TextView(this).apply {
            text = "●"
            textSize = 13f
            setPadding(0, 0, dp(7), 0)
        }
        statusText = TextView(this).apply {
            textSize = 13.5f
            setTextColor(C.TEXT)
        }
        statusRow.addView(dot)
        statusRow.addView(statusText, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        root.addView(statusRow)

        target = TextView(this).apply {
            textSize = 11.5f
            setTextColor(C.MUTED)
            setPadding(dp(18), 0, dp(18), dp(10))
        }
        root.addView(target)

        // 通知被系统关掉时必须显眼地说出来 —— 否则就是“消息到了 App、但一条弹窗都没有”，
        // 你只能在两个界面之间来回猜。点它就跳去系统通知设置。
        warnBox = TextView(this).apply {
            textSize = 13f
            setTextColor(Color.parseColor("#8A2B00"))
            setPadding(dp(14), dp(10), dp(14), dp(10))
            background = rounded(Color.parseColor("#FFE8D6"), dp(10).toFloat())
            visibility = View.GONE
            isClickable = true
            setOnClickListener { openNotificationSettings() }
        }
        root.addView(
            warnBox,
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT,
            ).apply { leftMargin = dp(14); rightMargin = dp(14); bottomMargin = dp(8) },
        )

        root.addView(divider())

        // 消息流
        listBox = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        emptyHint = TextView(this).apply {
            text = "还没有收到通知。\n\n会话跑完或异常中断时，这里会自己冒出来。"
            textSize = 13.5f
            setTextColor(C.MUTED)
            setPadding(dp(18), dp(30), dp(18), dp(30))
            gravity = Gravity.CENTER
        }
        val scrollContent = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(12), dp(10), dp(12), dp(24))
            addView(emptyHint)
            addView(listBox)
        }
        root.addView(ScrollView(this).apply { addView(scrollContent) })
        return root
    }

    // ── 刷新 ───────────────────────────────────────────────────────────────

    private fun refresh() {
        val status = prefs.status
        val silent = if (prefs.lastFrameAt > 0) (System.currentTimeMillis() - prefs.lastFrameAt) / 1000 else -1L
        val healthy = status.contains("已连接") && silent in 0..120
        val connecting = status.contains("重连") || status.contains("连接中")
        dot.setTextColor(when {
            healthy -> C.GREEN
            connecting -> C.AMBER
            else -> C.MUTED
        })
        // 关键：不能只信 prefs.status —— 服务被停掉/被杀之后它不会自己改，
        // 于是主界面会一直显示“已连接”（假象）。用“最近一帧”的新鲜度兜底。
        statusText.text = when {
            prefs.token.isEmpty() -> "还没配好 · 点右上角设置"
            legacyConfig() -> "⚠ 还在用旧配置（:8080 是已停用的旧中转）"
            silent > 120 -> "已断开（${silent}s 没有数据）—— 进设置点「保存并生效」重启"
            // 在异地地址上连着 = 出门在外也能收，这是这套东西最想要的状态
            else -> status + if (prefs.autoSwitch && prefs.activeBase.isNotEmpty() && prefs.activeBase != prefs.base) "（异地）" else ""
        }

        val list = prefs.history()
        // 系统会不会把通知静默丢掉？（消息在列表里看得到、却不弹窗，就是这一条）
        val blocked = Notifier.blockedReason(this)
        if (blocked == null) {
            warnBox.visibility = View.GONE
        } else {
            warnBox.visibility = View.VISIBLE
            warnBox.text = "⚠ $blocked\n系统会静默丢弃所有通知 —— 消息在下面看得到，但不会弹出来。点这里去开启。"
        }
        val signature = "${list.size}:${list.firstOrNull()?.id ?: ""}"
        if (signature != listSignature) {
            listSignature = signature
            listBox.removeAllViews()
            emptyHint.visibility = if (list.isEmpty()) View.VISIBLE else View.GONE
            list.forEach { listBox.addView(messageCard(it)) }
        }
    }

    private fun targetLabel(): String = when {
        prefs.token.isEmpty() -> "⚠ 还没配好（缺派发台令牌）—— 用派发台 /app 页一键配置"
        legacyConfig() -> "⚠ 配置还指向 :8080（旧中转已停用）—— 用 /app 页一键配置改成 :8787"
        else -> {
            val active = prefs.activeBase.ifEmpty { prefs.base }
            val remote = prefs.endpoints().count { it.kind == "tunnel" || it.kind == "ipv6" || it.kind == "ipv4" }
            val where = if (active == prefs.base) "局域网" else "异地"
            "$where · $active" + if (remote > 0) " · 另有 $remote 个备用出口" else ""
        }
    }

    /** 旧配置（还指向 :8080 —— 那是已停用的旧中转端口）：现在必须是派发台的 8787 */
    private fun legacyConfig(): Boolean = prefs.base.contains(":8080")

    private fun messageCard(m: Msg): View {
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = rounded(C.CARD, dp(12).toFloat())
            val lp = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
            )
            lp.bottomMargin = dp(9)
            layoutParams = lp
        }

        val head = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(13), dp(11), dp(13), 0)
        }
        head.addView(TextView(this).apply {
            text = "●"
            textSize = 11f
            setTextColor(if (m.priority >= 4) C.RED else C.DONE_DOT)
            setPadding(0, 0, dp(7), 0)
        })
        head.addView(TextView(this).apply {
            text = m.title
            textSize = 14.5f
            setTypeface(typeface, Typeface.BOLD)
            setTextColor(if (m.priority >= 4) C.RED else C.TEXT)
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        head.addView(TextView(this).apply {
            text = timeLabel(m)
            textSize = 11f
            setTextColor(C.MUTED)
        })
        card.addView(head)

        card.addView(TextView(this).apply {
            text = m.body
            textSize = 13.5f
            setTextColor(C.BODY)
            setPadding(dp(21), dp(4), dp(13), dp(12))
            setLineSpacing(dp(3).toFloat(), 1f)
        })

        // 消息自带动作按钮（看门狗每次会发三个：打开会话 / 派发台 / 让它继续跑）。
        // 通知里能点，App 里也应该能点 —— 否则同一件事在两个地方长得不一样。
        val clickable = m.actions.filter { it.url.isNotEmpty() }.take(3)
        if (clickable.isNotEmpty()) {
            val actionsRow = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                setPadding(dp(15), 0, dp(13), dp(11))
            }
            clickable.forEach { a ->
                actionsRow.addView(TextView(this).apply {
                    text = a.label
                    textSize = 12.5f
                    setTextColor(C.ACCENT)
                    setPadding(dp(10), dp(6), dp(10), dp(6))
                    background = rounded(Color.parseColor("#EAF3F2"), dp(8).toFloat())
                    isClickable = true
                    setOnClickListener { openUrl(a.url) }
                }, LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT
                ).apply { rightMargin = dp(7) })
            }
            card.addView(actionsRow)
        }

        // 点卡片主体 = 打开主链接（会话深链 / 派发台）；长按 = 复制全文
        val url = m.click ?: m.actions.firstOrNull()?.url
        if (url != null) {
            card.isClickable = true
            card.setOnClickListener { openUrl(url) }
        }
        card.setOnLongClickListener {
            copyToClipboard("${m.title}\n${m.body}")
            true
        }
        return card
    }

    // ── 深链：pilink://setup?base=...&token=...&ack=... ─────────────────────
    // 派发台 /app 页点一下就配好，不经过任何输入框。
    private fun applyDeepLink(intent: Intent?) {
        val data = intent?.data ?: return
        if (data.scheme != "pilink") return
        val base = data.getQueryParameter("base")
        val token = data.getQueryParameter("token")
        val ack = data.getQueryParameter("ack")
        if (base.isNullOrEmpty() || token.isNullOrEmpty()) return
        prefs.base = base
        prefs.token = token
        if (!ack.isNullOrEmpty()) prefs.ackUrl = ack
        // 顺带把服务端当下的异地地址一并存下（逗号分隔的 URL 列表）。
        // 不存也能用（下一帧通知就会补上），存了就等于出门前已经预先知道备选出口。
        val bases = data.getQueryParameter("bases")
        if (!bases.isNullOrEmpty()) {
            val list = bases.split(",").map { it.trim() }.filter { it.isNotEmpty() }
            if (list.isNotEmpty()) {
                val mgr = EndpointManager(this, prefs)
                mgr.learn(list, list.firstOrNull { it != base })
            }
        }
        PiLinkService.start(this)
        target.text = targetLabel()
        listSignature = ""
        toast("已按派发台的配置启动")
    }

    // ── 小工具 ─────────────────────────────────────────────────────────────

    /** 跳到本应用的系统通知设置页 */
    private fun openNotificationSettings() {
        try {
            startActivity(
                Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                    .putExtra(Settings.EXTRA_APP_PACKAGE, packageName),
            )
        } catch (e: Exception) {
            toast("请手动到 设置 → 应用 → Pi 通知 → 通知 里开启")
        }
    }

    private fun timeLabel(m: Msg): String {
        val ms = if (m.time > 0) m.time else 0L
        if (ms == 0L) return ""
        val sameDay = SimpleDateFormat("yyyyMMdd", Locale.CHINA).format(Date(ms)) ==
            SimpleDateFormat("yyyyMMdd", Locale.CHINA).format(Date())
        return SimpleDateFormat(if (sameDay) "HH:mm" else "MM-dd HH:mm", Locale.CHINA).format(Date(ms))
    }

    private fun openUrl(url: String) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        } catch (e: Exception) {
            toast("打不开这个链接：${e.message}")
        }
    }

    private fun copyToClipboard(text: String) {
        try {
            val cm = getSystemService(ClipboardManager::class.java)
            cm.setPrimaryClip(ClipData.newPlainText("pilink", text))
            toast("已复制")
        } catch (e: Exception) {
            // 忽略
        }
    }

    private fun button(label: String, primary: Boolean, onClick: () -> Unit) = TextView(this).apply {
        text = label
        textSize = 13.5f
        setTextColor(if (primary) Color.WHITE else C.ACCENT)
        setPadding(dp(15), dp(8), dp(15), dp(8))
        background = rounded(if (primary) C.ACCENT else C.CARD, dp(9).toFloat())
        isClickable = true
        setOnClickListener { onClick() }
    }

    private fun divider() = View(this).apply {
        setBackgroundColor(C.LINE)
        layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(1))
    }

    private fun rounded(color: Int, radius: Float) = GradientDrawable().apply {
        setColor(color)
        cornerRadius = radius
    }

    private fun dp(v: Int): Int = TypedValue.applyDimension(
        TypedValue.COMPLEX_UNIT_DIP, v.toFloat(), resources.displayMetrics
    ).toInt()

    internal fun toast(text: String) = Toast.makeText(this, text, Toast.LENGTH_SHORT).show()

    /** 配色集中在这里，两个页面共用 */
    object C {
        val BG = Color.parseColor("#F4F5F7")
        val CARD = Color.WHITE
        val TEXT = Color.parseColor("#1B1D21")
        val BODY = Color.parseColor("#4A5058")
        val MUTED = Color.parseColor("#8A9099")
        val LINE = Color.parseColor("#E3E5E9")
        val ACCENT = Color.parseColor("#0F766E")
        val GREEN = Color.parseColor("#16A34A")
        val AMBER = Color.parseColor("#D97706")
        val RED = Color.parseColor("#DC2626")
        val DONE_DOT = Color.parseColor("#94A3B8")
    }
}
