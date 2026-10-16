package io.pilink

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * 设置页。所有可编辑的东西都在这里 —— 主界面不放输入框，避免误触改配置
 * （配置错了的表现是"看着已连接、其实收不到"，很难自查）。
 *
 * 心跳与重连节奏全部是客户端参数，改完走 PiLinkService.reload() 立刻生效，
 * keepalive 由 App 把「心跳间隔」当 ka 传给服务端，PC 侧没有任何要调的东西。
 */
class SettingsActivity : Activity() {

    private lateinit var prefs: Prefs
    private lateinit var baseIn: EditText
    private lateinit var tokenIn: EditText
    private lateinit var ackIn: EditText
    private lateinit var pingIn: EditText
    private lateinit var staleIn: EditText
    private lateinit var pollIn: EditText
    private lateinit var idlePollIn: EditText
    private lateinit var statusOut: TextView
    private lateinit var remoteOut: TextView
    private lateinit var autoSwitchBox: TextView
    private lateinit var manualAdd: EditText
    private val scope = CoroutineScope(Dispatchers.IO)
    private lateinit var manager: EndpointManager

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = Prefs(this)
        manager = EndpointManager(this, prefs)
        setContentView(buildUi())
    }

    private fun buildUi(): View {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(MainActivity.C.BG)
            setPadding(dp(18), dp(14), dp(18), dp(28))
        }

        val bar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        bar.addView(TextView(this).apply {
            text = "设置"
            textSize = 20f
            setTypeface(typeface, Typeface.BOLD)
            setTextColor(MainActivity.C.TEXT)
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        bar.addView(TextView(this).apply {
            text = "返回"
            textSize = 13.5f
            setTextColor(MainActivity.C.ACCENT)
            setPadding(dp(14), dp(8), 0, dp(8))
            isClickable = true
            setOnClickListener { finish() }
        })
        root.addView(bar)

        // ── 服务器 ────────────────────────────────────────────────────────
        root.addView(section("派发台"))
        root.addView(note(
            "最省事的做法：手机浏览器打开 派发台地址 /app，点「一键配置」，下面三栏会自己填好 —— 不用手打。\n" +
                "消息中转就在派发台里，不需要任何第三方推送服务，也没有主题（topic）这个概念。"
        ))
        baseIn = field("派发台地址", "http://192.168.1.100:8787", prefs.base, InputType.TYPE_TEXT_VARIATION_URI)
        tokenIn = field("派发台令牌", "在 ~/.pi/android-link/local.json 的 lan.consoleToken", prefs.token, InputType.TYPE_CLASS_TEXT)
        ackIn = field("送达回执地址（可空）", "http://192.168.1.100:8787/api/ack", prefs.ackUrl, InputType.TYPE_TEXT_VARIATION_URI)
        listOf(baseIn, tokenIn, ackIn).forEach { root.addView(it.parent as View) }

        // ── 异地（出门在外也能收） ───────────────────────────────────────
        root.addView(section("异地通知（不用服务器、不用账号）"))
        root.addView(note(
            "手机手里有一份「能连上这台电脑的地址」清单：局域网、免账号隧道（cloudflared 之类）、" +
                "公网 IPv6、公网 IPv4（需路由器端口映射）。谁通用谁；地址变了（换公网 IP、隧道换域名）" +
                "下一条通知会自己把新地址带过来，不需要重新配置。\n" +
                "下面的清单由服务端下发，点「挨个探测」可以当场看到哪些地址此刻能连。"
        ))
        autoSwitchBox = TextView(this).apply {
            textSize = 13.5f
            setTextColor(MainActivity.C.TEXT)
            setPadding(0, dp(8), 0, dp(2))
            isClickable = true
            setOnClickListener {
                prefs.autoSwitch = !prefs.autoSwitch
                renderRemote()
                PiLinkService.kick(this@SettingsActivity)
            }
        }
        root.addView(autoSwitchBox)
        remoteOut = TextView(this).apply {
            textSize = 12f
            typeface = Typeface.MONOSPACE
            setTextColor(MainActivity.C.TEXT)
            setLineSpacing(dp(2).toFloat(), 1f)
            setPadding(dp(12), dp(12), dp(12), dp(12))
            background = rounded(MainActivity.C.CARD, dp(10).toFloat())
        }
        root.addView(remoteOut)
        val addBox = field("手动加一个出口地址（可空）", "https://xxx.trycloudflare.com", "", InputType.TYPE_TEXT_VARIATION_URI)
        manualAdd = addBox
        root.addView(addBox.parent as View)
        root.addView(pair(
            button("挨个探测", false) { probeAll() },
            button("添加并启用", false) { addManual() },
        ))
        renderRemote()

        // ── 心跳与重连 ────────────────────────────────────────────────────
        root.addView(section("心跳与重连（都是客户端参数，服务端不用动）"))
        root.addView(note(
            "更短 = 更早发现断线、恢复更快；代价是手机无线电唤醒更频繁、耗电略增。\n" +
                "“静默判死”会自动保持 ≥ 心跳×2（否则看门狗会和心跳互相打架）。"
        ))
        pingIn = field("心跳间隔（秒）", "5–300，推荐 20", prefs.pingSeconds.toString(), InputType.TYPE_CLASS_NUMBER)
        staleIn = field("静默判死（秒）", "30–900，推荐 90", prefs.staleSeconds.toString(), InputType.TYPE_CLASS_NUMBER)
        pollIn = field("轮询兜底·已连接（秒）", "10–600，推荐 30", prefs.pollSeconds.toString(), InputType.TYPE_CLASS_NUMBER)
        idlePollIn = field("轮询兜底·未连接（秒）", "5–300，推荐 10", prefs.idlePollSeconds.toString(), InputType.TYPE_CLASS_NUMBER)
        listOf(pingIn, staleIn, pollIn, idlePollIn).forEach { root.addView(it.parent as View) }
        root.addView(pair(
            button("保存并生效", true) { save() },
            button("恢复默认节奏", false) {
                prefs.resetTuning()
                fillTuningFields()
                toast("已恢复默认（记得再点保存并生效）")
            },
        ))

        // ── 动作 ──────────────────────────────────────────────────────────
        root.addView(section("操作"))
        root.addView(pair(
            button("强制重连", false) { PiLinkService.kick(this); toast("已要求重连") },
            button("停止订阅", false) { confirmStop() },
        ))
        // 这一条是隔离实验：本地造一条带 3 个动作的通知，完全不经过服务端。
        // 关心的是「系统渲染不动」还是「我们的消息解析出问题」—— 这一条一点就能分开。
        root.addView(pair(
            button("动作按钮自检", false) { selfTest() },
            button("响铃自检", false) { ringTest() },
        ))
        root.addView(pair(
            button("电池白名单", false) { askBattery() },
            button("通知权限", false) { askNotifications() },
        ))
        root.addView(pair(
            button("清空历史", false) { prefs.clearHistory(); toast("历史已清空") },
            button("刷新状态", false) { refresh() },
        ))

        // ── 状态 ──────────────────────────────────────────────────────────
        root.addView(section("当前状态"))
        statusOut = TextView(this).apply {
            textSize = 12.5f
            typeface = Typeface.MONOSPACE
            setTextColor(MainActivity.C.TEXT)
            setPadding(dp(12), dp(12), dp(12), dp(12))
            background = rounded(MainActivity.C.CARD, dp(10).toFloat())
        }
        root.addView(statusOut)

        // ── 说明 ──────────────────────────────────────────────────────────
        root.addView(section("ColorOS（OPPO）必须放行三件事"))
        root.addView(note(
            "1. 设置 → 应用管理 → Pi 通知 → 耗电管理 → 允许「允许后台活动 / 允许后台运行」\n" +
                "2. 同页 → 自启动 → 允许\n" +
                "3. 最近任务里把这个卡片下拉加锁（防手滑清理）\n\n" +
                "电池白名单尤其关键：Android 息屏闲置后进 Doze 会**给所有应用断网**，" +
                "只有白名单里的被豁免。不在白名单里，任何长连接客户端（本应用也一样）手机放兜里时都收不到。\n" +
                "不需要「闹钟和提醒」权限 —— 重连是常驻协程 + 非精确闹钟自愈。"
        ))

        root.addView(section("它是怎么活的"))
        root.addView(note(
            "· 主通道：一条 NDJSON 长连接（/pi/stream），服务端每条 keepalive 都刷新读截止\n" +
                "· 兜底：HTTP 轮询（/pi/messages?since=），两条路按消息 id 去重\n" +
                "· 重连是常驻协程里的循环，不依赖任何特殊权限\n" +
                "· 断线补收靠游标 since=<最后一条 id>，所以断多久都不会丢、只会迟到\n" +
                "· 收到即回执（acks.jsonl），服务端能看到「送达 / 未送达」"
        ))

        return ScrollView(this).apply { addView(root) }
    }

    override fun onResume() {
        super.onResume()
        refresh()
    }

    private fun refresh() {
        val silent = if (prefs.lastFrameAt > 0) (System.currentTimeMillis() - prefs.lastFrameAt) / 1000 else -1
        statusOut.text = buildString {
            append("版本：").append(versionLabel()).append('\n')
            append("状态：").append(prefs.status).append('\n')
            append("当前出口：").append(prefs.activeBase.ifEmpty { prefs.base }).append('\n')
            append("已连接次数：").append(prefs.connectCount).append('\n')
            append("最近一帧：").append(if (silent < 0) "（还没有）" else "${silent}s 前").append('\n')
            append("游标 lastId：").append(prefs.lastId.ifEmpty { "（还没收到过）" }).append('\n')
            append("生效节奏：心跳 ").append(prefs.pingSeconds).append("s")
            append(" / 静默 ").append(prefs.staleSeconds).append("s")
            append(" / 轮询 ").append(prefs.pollSeconds).append("s·")
            append(prefs.idlePollSeconds).append("s")
        }
        renderRemote()
    }

    /** 异地出口清单：一眼看清「现在在用哪个、还有哪些备用、能不能连」 */
    private fun renderRemote() {
        autoSwitchBox.text = (if (prefs.autoSwitch) "☑" else "☐") +
            " 异地自动切换（点一下开关）" + if (prefs.autoSwitch) "" else " —— 关了就死用上面那个地址"
        val rows = StringBuilder()
        val active = prefs.activeBase.ifEmpty { prefs.base }
        for (e in manager.candidates()) {
            val mark = if (e.base == active) "▶ " else "  "
            val state = when {
                e.base == prefs.base -> "手动配置的地址"
                e.fails == 0 -> "可用"
                else -> "连不上×${e.fails}"
            }
            rows.append(mark).append(manager.labelOf(e.base)).append('\n')
                .append("    ").append(state).append('\n')
        }
        if (rows.isEmpty()) rows.append("（还没有候选地址 —— 启动一次派发台就会下发）")
        rows.append('\n').append("手动地址永远排第一；连不上会自动换下一个，连通后自动回到前面。")
        remoteOut.text = rows.toString()
    }

    /** 挨个探一遍：当场看到哪个出口此刻真的能连（每个最多 2.5s 超时） */
    private fun probeAll() {
        toast("探测中…")
        scope.launch {
            val results = manager.probeAll()
            runOnUiThread {
                renderRemote()
                val okList = results.filter { it.second }.map { it.first.base }
                toast(if (okList.isEmpty()) "一个都连不上" else "能连 ${'$'}{okList.size} 个，已选中最新的")
                PiLinkService.kick(this@SettingsActivity)
            }
        }
    }

    /** 手动加一个出口（已经有自己的反向代理/穿透时用），并立即启用它 */
    private fun addManual() {
        val value = manualAdd.text.toString().trim().trimEnd('/')
        if (value.isEmpty()) {
            toast("先填一个地址")
            return
        }
        if (!value.startsWith("http://") && !value.startsWith("https://")) {
            toast("地址要以 http:// 或 https:// 开头")
            return
        }
        if (value == prefs.base) {
            toast("这个就是上面那个派发台地址")
            return
        }
        manager.forceBase(value)
        prefs.saveEndpoints(
            (prefs.endpoints().filterNot { it.base == value } + Endpoint(value, prefs.guessKind(value))).take(12)
        )
        manualAdd.setText("")
        prefs.autoSwitch = true
        renderRemote()
        PiLinkService.kick(this)
        toast("已添加并启用：${'$'}value")
    }

    @Suppress("DEPRECATION")
    private fun versionLabel(): String = try {
        val info = packageManager.getPackageInfo(packageName, 0)
        "${info.versionName} (${info.versionCode})"
    } catch (e: Exception) {
        "?"
    }

    /**
     * 响铃自检：两条通知分别走「报错/中断」（高重要性，响铃+震动）和
     * 「任务完成」（普通）两个渠道。用来当场验证“声音/震动/锁屏显示”这一层，
     * 不用等真实推送。
     */
    private fun ringTest() {
        val now = System.currentTimeMillis()
        Notifier.post(
            this,
            Msg(
                id = "ringtest-alert-$now",
                time = now,
                title = "【响铃自检·报错渠道】应当响铃 + 震动",
                body = "这条走 IMPORTANCE_HIGH 渠道。锁屏上应该直接看到这段字（不是“内容已隐藏”）。",
                priority = 4,
                click = null,
                actions = emptyList(),
                group = null,
            ),
        )
        Notifier.post(
            this,
            Msg(
                id = "ringtest-done-$now",
                time = now + 1,
                title = "【响铃自检·完成渠道】只有提示音",
                body = "这条走 IMPORTANCE_DEFAULT 渠道，不震动。两条一起发，方便对比。",
                priority = 3,
                click = null,
                actions = emptyList(),
                group = null,
            ),
        )
        toast("已发两条，锁屏看一下响不响、显不显示内容")
    }

    /**
     * 本地自检：不经过服务端、不经过解析，直接造一条带 3 个动作的通知。
     * 用它把两类问题分开：
     *   · 自检通知也没按钮 → 是系统/通知样式不渲染动作（跟我们的消息处理无关）
     *   · 自检通知有 3 个按钮、真实推送没有 → 才是我们解析或构造的问题
     */
    private fun selfTest() {
        val now = System.currentTimeMillis()
        Notifier.post(
            this,
            Msg(
                id = "selftest-$now",
                time = now,
                title = "【动作按钮自检】本地生成，不过服务端",
                body = "这条里有三个动作按钮。若这里看不到按钮，就是系统/通知样式不渲染动作，与消息解析无关。",
                priority = 4,
                click = "http://192.168.1.100:30141/",
                actions = listOf(
                    MsgAction("打开会话", "http://192.168.1.100:30141/"),
                    MsgAction("派发台", "http://192.168.1.100:8787/"),
                    MsgAction("让它继续跑", "http://192.168.1.100:8787/"),
                ),
                group = null,
            ),
        )
        toast("已发一条本地自检通知")
    }

    // ── 保存 ───────────────────────────────────────────────────────────────

    private fun save() {
        prefs.base = baseIn.text.toString()
        prefs.token = tokenIn.text.toString()
        prefs.ackUrl = ackIn.text.toString()
        if (prefs.base.isEmpty() || prefs.token.isEmpty()) {
            toast("派发台地址和令牌都必须填")
            return
        }

        // 夹取到安全区间，并把夹取后的真实值回填，免得你以为改成了其实没生效
        val ping = clamp(pingIn, prefs.pingSeconds, 5, 300)
        var stale = clamp(staleIn, prefs.staleSeconds, 30, 900)
        if (stale < ping * 2) stale = minOf(ping * 2, 900)
        val poll = clamp(pollIn, prefs.pollSeconds, 10, 600)
        val idle = clamp(idlePollIn, prefs.idlePollSeconds, 5, 300)

        prefs.pingSeconds = ping
        prefs.staleSeconds = stale
        prefs.pollSeconds = poll
        prefs.idlePollSeconds = idle
        fillTuningFields()

        PiLinkService.reload(this)
        toast("已保存，新节奏立刻生效")
        refresh()
    }

    private fun clamp(field: EditText, fallback: Int, min: Int, max: Int): Int {
        val raw = field.text.toString().trim().toIntOrNull()
        if (raw == null) return fallback
        return raw.coerceIn(min, max)
    }

    private fun fillTuningFields() {
        pingIn.setText(prefs.pingSeconds.toString())
        staleIn.setText(prefs.staleSeconds.toString())
        pollIn.setText(prefs.pollSeconds.toString())
        idlePollIn.setText(prefs.idlePollSeconds.toString())
    }

    // ── 动作 ───────────────────────────────────────────────────────────────

    /** 「停止订阅」加一道确认：误点一下就会静默停止（而首屏还会显示已连接，很难自查） */
    private fun confirmStop() {
        AlertDialog.Builder(this)
            .setTitle("停止订阅？")
            .setMessage("停止后不再接收任何通知，开机自启也会关掉。重新开启：点「保存并生效」。")
            .setPositiveButton("停止") { _, _ ->
                PiLinkService.stop(this)
                toast("已停止订阅")
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun askNotifications() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        if (checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED) {
            toast("通知权限已授予")
            return
        }
        requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 1)
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

    // ── 小工具 ─────────────────────────────────────────────────────────────

    private fun section(text: String) = TextView(this).apply {
        this.text = text
        textSize = 14f
        setTypeface(typeface, Typeface.BOLD)
        setTextColor(MainActivity.C.TEXT)
        setPadding(0, dp(20), 0, dp(7))
    }

    private fun note(text: String) = TextView(this).apply {
        this.text = text
        textSize = 12.5f
        setTextColor(MainActivity.C.MUTED)
        setLineSpacing(dp(2).toFloat(), 1f)
        setPadding(0, dp(6), 0, dp(2))
    }

    private fun field(label: String, hintText: String, value: String, type: Int): EditText {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, dp(9), 0, dp(9))
        }
        box.addView(TextView(this).apply {
            text = label
            textSize = 12f
            setTextColor(MainActivity.C.MUTED)
        })
        val edit = EditText(this).apply {
            hint = hintText
            setText(value)
            inputType = type
            textSize = 14f
            setSingleLine(true)
            setSelectAllOnFocus(value.isNotEmpty())
            setPadding(0, dp(6), 0, dp(6))
        }
        box.addView(edit)
        return edit
    }

    private fun pair(a: View, b: View) = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL
        setPadding(0, dp(5), 0, 0)
        addView(a, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        addView(b, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
    }

    private fun button(label: String, primary: Boolean, onClick: () -> Unit) = Button(this).apply {
        text = label
        textSize = 13f
        setOnClickListener { onClick() }
    }

    private fun rounded(color: Int, radius: Float) = GradientDrawable().apply {
        setColor(color)
        cornerRadius = radius
    }

    private fun dp(v: Int): Int = TypedValue.applyDimension(
        TypedValue.COMPLEX_UNIT_DIP, v.toFloat(), resources.displayMetrics
    ).toInt()

    private fun toast(text: String) = Toast.makeText(this, text, Toast.LENGTH_SHORT).show()
}
