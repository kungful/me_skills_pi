package com.guantianxia.app.ui.news

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.view.View
import android.widget.ImageButton
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import com.google.android.material.chip.Chip
import com.google.android.material.chip.ChipGroup
import com.guantianxia.app.App
import com.guantianxia.app.R
import com.guantianxia.app.core.Notify
import com.guantianxia.app.core.Prefs
import com.guantianxia.app.core.TimeUtil
import com.guantianxia.app.data.Category
import com.guantianxia.app.data.Db
import com.guantianxia.app.repo.FeedRepo
import com.guantianxia.app.ui.ArticleActions
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class NewsFragment : Fragment(R.layout.fragment_news) {

    private val repo by lazy { FeedRepo(requireContext().applicationContext) }
    private val db by lazy { Db(requireContext().applicationContext) }
    private val prefs by lazy { Prefs(requireContext().applicationContext) }

    private lateinit var adapter: NewsAdapter
    private lateinit var bell: ImageButton
    private var filter: String = Category.ALL

    /** 首帧布局完成、默认 chip 定住之前，忽略 ChipGroup 自己产生的勾选变化 */
    private var chipsReady = false

    /** 上次加载用的频道：只有换频道才把列表拉回第一条，同频道刷新保留阅读位置 */
    private var lastFilter: String? = null

    /** 请求通知权限（Android 13+ 才需要） */
    private val askNotifyPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            prefs.notifyEnabled = granted
            prefs.askedNotify = true
            renderBell()
            toast(if (granted) R.string.notify_on else R.string.notify_need_permission)
        }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        val chips = view.findViewById<ChipGroup>(R.id.chips)
        val swipe = view.findViewById<SwipeRefreshLayout>(R.id.swipe)
        val status = view.findViewById<TextView>(R.id.tv_status)
        val rv = view.findViewById<RecyclerView>(R.id.rv)
        bell = view.findViewById(R.id.btn_bell)
        bell.setOnClickListener { toggleNotify() }
        bell.setOnLongClickListener {
            showNotifyMenu()
            true
        }
        renderBell()

        adapter = NewsAdapter(
            onOpen = { a -> ArticleActions.open(requireContext(), a) },
            onShare = { a -> ArticleActions.shareDialog(requireActivity(), a) },
            onMore = { a ->
                ArticleActions.showMenu(requireActivity(), a, db) { load() }
            }
        )
        rv.layoutManager = LinearLayoutManager(requireContext())
        rv.adapter = adapter

        buildChips(chips)
        swipe.setOnRefreshListener { doRefresh(swipe, status) }

        load()
        if (prefs.lastRefresh == 0L) {
            swipe.isRefreshing = true
            doRefresh(swipe, status)
        }
    }

    private fun buildChips(group: ChipGroup) {
        var firstId = View.NO_ID
        for (key in Category.TABS) {
            val chip = Chip(requireContext())
            chip.id = View.generateViewId()
            chip.text = getString(Category.labelRes(key))
            chip.isCheckable = true
            chip.tag = key
            group.addView(chip)
            if (firstId == View.NO_ID) firstId = chip.id
        }
        // 先只接管回调：首帧布局前 ChipGroup 内部还可能自己挑一个 chip 勾上，
        // 所以用 chipsReady 把这类「非用户」变更全过滤掉，等布局完再定住默认项。
        group.setOnCheckedChangeListener { g, id ->
            if (!chipsReady) return@setOnCheckedChangeListener
            val c = g.findViewById<Chip>(id)
            filter = (c?.tag as? String) ?: Category.ALL
            load()
        }
        group.post {
            if (firstId != View.NO_ID) group.check(firstId)
            filter = Category.ALL
            chipsReady = true
        }
    }

    /** 状态栏里显示外网源的真实抓取成绩，而不是一个容易误报的「已连/未连」 */
    private fun intlText(): String {
        val ok = prefs.intlOkCount
        return when {
            ok < 0 -> ""
            prefs.intlEnabled -> " · 外网 $ok 源"
            else -> " · 外网已关"
        }
    }

    private fun doRefresh(swipe: SwipeRefreshLayout, status: TextView) {
        viewLifecycleOwner.lifecycleScope.launch {
            val stats = repo.refresh { msg ->
                activity?.runOnUiThread { if (isAdded) status.text = msg }
            }
            swipe.isRefreshing = false
            if (!isAdded) return@launch
            val extra = if (stats.notified > 0) " · 通知 ${stats.notified}" else ""
            status.text = "源 ${stats.ok}/${stats.sources} 成功 · 抓回 ${stats.fetched} · " +
                "入库 ${stats.kept} · 去重 ${stats.dup} · 过滤 ${stats.junk} · 失败 ${stats.failed}$extra"
            load()
        }
    }

    private fun load() {
        if (!isAdded) return
        viewLifecycleOwner.lifecycleScope.launch {
            // 「热门」不是真实分类，而是按事件热度排的榜单（学 AIHOT 的 hot 榜）
            val hot = filter == Category.HOT
            val category = if (filter == Category.ALL || filter == Category.SAVED || hot) null else filter
            val savedOnly = filter == Category.SAVED
            val result = withContext(Dispatchers.IO) {
                val list = if (hot) db.hotArticles(300) else db.query(category, savedOnly, 300)
                list to db.articleCount()
            }
            if (!isAdded) return@launch
            val list = result.first
            adapter.submit(list)
            // 切频道要直接看到第一条，而不是停在上一个频道滚动到的位置
            if (lastFilter != filter) {
                lastFilter = filter
                view?.findViewById<RecyclerView>(R.id.rv)?.scrollToPosition(0)
            }
            val tv = view?.findViewById<TextView>(R.id.tv_status) ?: return@launch
            tv.text = if (list.isEmpty()) {
                if (hot) "暂时没有热点（同一件事有 2 家以上媒体报道才会进榜）"
                else getString(R.string.empty_hint)
            } else {
                (if (hot) "热点 ${list.size} 件事" else "当前 ${list.size} 条") +
                    " · 库内 ${result.second} 条 · 更新于 ${TimeUtil.ago(prefs.lastRefresh)}" +
                    intlText()
            }
        }
    }

    override fun onResume() {
        super.onResume()
        // 用户可能去系统设置里改过通知权限
        if (::bell.isInitialized) renderBell()
    }

    /** 铃铛状态 = 开关打开 且 系统权限已给 */
    private fun notifyActive(): Boolean {
        if (!prefs.notifyEnabled) return false
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return true
        return ContextCompat.checkSelfPermission(
            requireContext(), Manifest.permission.POST_NOTIFICATIONS
        ) == PackageManager.PERMISSION_GRANTED
    }

    private fun renderBell() {
        val on = notifyActive()
        bell.setImageResource(if (on) R.drawable.ic_bell else R.drawable.ic_bell_off)
        val color = ContextCompat.getColor(
            requireContext(),
            if (on) R.color.brand else android.R.color.darker_gray
        )
        bell.imageTintList = android.content.res.ColorStateList.valueOf(color)
    }

    private fun toggleNotify() {
        val wantOn = !notifyActive()
        if (wantOn && Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(
                requireContext(), Manifest.permission.POST_NOTIFICATIONS
            ) != PackageManager.PERMISSION_GRANTED
        ) {
            if (prefs.askedNotify && !shouldShowRequestPermissionRationale(
                    Manifest.permission.POST_NOTIFICATIONS
                )
            ) {
                // 用户之前拒绝过且不再弹窗，只能引导去设置
                toast(R.string.notify_need_permission)
                return
            }
            askNotifyPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
            return
        }
        prefs.notifyEnabled = wantOn
        renderBell()
        toast(if (wantOn) R.string.notify_on else R.string.notify_off)
    }

    /** 长按铃铛：拿库内最新的几条立刻推一次，验证通知能不能弹出来 */
    private fun testNotify() {
        viewLifecycleOwner.lifecycleScope.launch {
            val top = withContext(Dispatchers.IO) { db.query(null, false, 3) }
            if (top.isEmpty()) {
                toast(R.string.empty_hint)
            } else {
                Notify.important(requireContext(), top.take(2))
                toast(R.string.notify_test_sent)
            }
        }
    }

    /**
     * 长按铃铛：测试通知 / 后台运行（关屏保推送）/ 系统通知设置。
     */
    private fun showNotifyMenu() {
        val bgOn = prefs.bgEnabled
        val items = arrayOf(
            getString(R.string.notify_test),
            getString(if (bgOn) R.string.bg_menu_off else R.string.bg_menu_on),
            getString(R.string.notify_battery),
            getString(R.string.notify_system)
        )
        AlertDialog.Builder(requireActivity())
            .setTitle(R.string.action_notify)
            .setItems(items) { _, i ->
                when (i) {
                    0 -> if (notifyActive()) testNotify() else toast(R.string.notify_off)
                    1 -> toggleBg()
                    2 -> openBatterySettings()
                    else -> openNotificationSettings()
                }
            }
            .show()
    }

    /** 切换后台常驻；开启后引导去电池白名单，否则系统还是会杀 */
    private fun toggleBg() {
        val on = !prefs.bgEnabled
        prefs.bgEnabled = on
        App.applyRefreshPolicy(requireContext())
        if (on) {
            // 后台抓取需要通知权限，否则前台服务拿不到常驻通知
            if (!notifyActive()) {
                toast(R.string.bg_need_permission)
            }
            toast(R.string.bg_on_hint)
            // 顺手把系统电池白名单也打开（国产 ROM 的自启动页）
            openBatterySettings()
        } else {
            toast(R.string.bg_off)
        }
    }

    /**
     * 关屏能不能收到推送，取决于系统肯不肯让 App 在后台跑：
     * 1) Android 自带的 Doze（深度休眠）—— 申请「忽略电池优化」；
     * 2) 国产 ROM 的「自启动 / 后台高耗电」白名单 —— 跳系统设置手动开。
     */
    private fun openBatterySettings() {
        val ctx = requireContext()
        val pkg = ctx.packageName

        // 1) 先申请忽略电池优化（系统自带弹窗）
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val pm = ctx.getSystemService(Context.POWER_SERVICE) as? PowerManager
            if (pm != null && !pm.isIgnoringBatteryOptimizations(pkg)) {
                val ok = runCatching {
                    startActivity(
                        Intent(
                            Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                            Uri.parse("package:$pkg")
                        )
                    )
                }.isSuccess
                if (ok) return
            }
        }

        // 2) 没有弹窗就跳国产 ROM 的自启动/后台管理页，不行再退到应用详情
        val romPages = listOf(
            // vivo / iQOO
            "com.vivo.permissionmanager" to
                "com.vivo.permissionmanager.activity.BgStartUpManagerActivity",
            // 小米
            "com.miui.securitycenter" to
                "com.miui.permcenter.autostart.AutoStartManagementActivity",
            // OPPO / 一加
            "com.coloros.safecenter" to
                "com.coloros.safecenter.permission.startup.StartupAppListActivity",
            "com.oplus.battery" to "com.oplus.powermanager.fuelgaue.PowerUsageModelActivity",
            // 华为
            "com.huawei.systemmanager" to
                "com.huawei.systemmanager.startupmgr.ui.StartupNormalAppListActivity",
            // 三星
            "com.samsung.android.lool" to
                "com.samsung.android.sm.ui.battery.BatteryActivity"
        )
        for ((p, cls) in romPages) {
            val jumped = runCatching {
                startActivity(Intent().setClassName(p, cls).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            }.isSuccess
            if (jumped) return
        }

        runCatching {
            startActivity(
                Intent(
                    Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                    Uri.parse("package:$pkg")
                )
            )
        }
        toast(R.string.notify_manual_hint)
    }

    private fun openNotificationSettings() {
        val ctx = requireContext()
        val ok = runCatching {
            startActivity(
                Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                    .putExtra(Settings.EXTRA_APP_PACKAGE, ctx.packageName)
            )
        }.isSuccess
        if (!ok) {
            runCatching {
                startActivity(
                    Intent(
                        Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                        Uri.parse("package:${ctx.packageName}")
                    )
                )
            }
        }
    }

    private fun toast(res: Int) {
        if (isAdded) Toast.makeText(requireContext(), res, Toast.LENGTH_SHORT).show()
    }

    private fun openUrl(url: String) {
        ArticleActions.openInBrowser(requireContext(), url)
    }
}
