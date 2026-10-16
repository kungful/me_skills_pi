package com.demandradar

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.os.Environment
import android.provider.Settings
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.CheckBox
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : Activity() {

    private lateinit var tvStatus: TextView
    private lateinit var tvStats: TextView
    private lateinit var tvLog: TextView
    private lateinit var llTopics: LinearLayout
    private lateinit var llRecent: LinearLayout
    private lateinit var cbCollect: CheckBox
    private lateinit var cbAllowAll: CheckBox

    /** 同步开关状态时置 true，避免初始化反过来把存的值改掉 */
    private var loading = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        Prefs.migrate(this)

        tvStatus = findViewById(R.id.tvStatus)
        tvStats = findViewById(R.id.tvStats)
        tvLog = findViewById(R.id.tvLog)
        llTopics = findViewById(R.id.llTopics)
        llRecent = findViewById(R.id.llRecent)
        cbCollect = findViewById(R.id.cbCollect)
        cbAllowAll = findViewById(R.id.cbAllowAll)

        findViewById<Button>(R.id.btnAcc).setOnClickListener {
            runCatching { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
                .onFailure { Toast.makeText(this, "打开不了设置，请手动到 设置→无障碍", Toast.LENGTH_LONG).show() }
        }
        findViewById<Button>(R.id.btnAnalyze).setOnClickListener {
            Toast.makeText(this, "分析中…", Toast.LENGTH_SHORT).show()
            Thread {
                Hub.analyze(this)
                runOnUiThread { refresh() }
            }.start()
        }
        findViewById<Button>(R.id.btnExport).setOnClickListener { export() }

        cbCollect.setOnCheckedChangeListener { _, v -> if (!loading) Prefs.setCollecting(this, v) }
        cbAllowAll.setOnCheckedChangeListener { _, v -> if (!loading) Prefs.setAllowAll(this, v) }
    }

    override fun onResume() {
        super.onResume()
        // 先把开关状态同步成存的值再开监听，否则初始化时会反过来把存的值改掉
        loading = true
        cbCollect.isChecked = Prefs.collecting(this)
        cbAllowAll.isChecked = Prefs.allowAll(this)
        loading = false
        refresh()
    }

    // ------------------------------------------------------------ 界面刷新

    private fun refresh() {
        val on = Prefs.enabled(this)
        tvStatus.text = if (on) "✅ 读屏已开启，正常刷小红书/闲鱼/抖音就会自动记录"
        else "⚠️ 读屏未开启：点下面的按钮，在「已下载的服务」里找到『需求雷达』并打开"
        tvStatus.setBackgroundColor(if (on) 0xFFE8F5E9.toInt() else 0xFFFFF3E0.toInt())

        val s = Store.get(this).stats()
        tvStats.text = "采集 ${s.screens} 屏（今日 ${s.todayScreens}） ｜ " +
            "高价值线索 ${s.highValue} 条 ｜ 机会主题 ${s.topics} 个"

        llTopics.removeAllViews()
        val topics = Store.get(this).loadTopics()
        if (topics.isEmpty()) {
            llTopics.addView(hint("还没有数据。开启读屏后去刷几分钟小红书，再点「重新分析」。"))
        } else {
            topics.take(15).forEach { llTopics.addView(topicCard(it)) }
        }

        llRecent.removeAllViews()
        val recent = Store.get(this).recentScreens(8)
        if (recent.isEmpty()) {
            llRecent.addView(hint("暂无"))
        } else {
            recent.forEach { (app, body) ->
                llRecent.addView(hint("【$app】" + Scorer.snippet(body, "", 90)))
            }
        }

        val logs = ScreenReaderService.recentLogs
        tvLog.text = if (logs.isEmpty()) "（刚启动，还没有日志）"
        else logs.toList().asReversed().take(12).joinToString("\n")
    }

    private fun topicCard(t: Topic): View {
        val v = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 20, 24, 20)
            setBackgroundColor(0xFFF7F7F7.toInt())
        }
        val head = TextView(this).apply {
            text = "#${t.rank}  ${t.label}   ${t.score.toInt()}分"
            textSize = 16f
            setTypeface(typeface, Typeface.BOLD)
        }
        val l2 = TextView(this).apply {
            text = "证据 ${t.evidence} 条 / 来源 ${t.sources.size} 个 ｜ 痛感 ${t.pain.toInt()} ｜ " +
                "付费 ${t.pay.toInt()} ｜ 最新 ${Hub.stamp(t.lastSeen)}"
            textSize = 12.5f
            setTextColor(Color.DKGRAY)
        }
        val l3 = TextView(this).apply { text = t.money; textSize = 13f; setTextColor(0xFF00695C.toInt()) }
        v.addView(head)
        v.addView(l2)
        v.addView(l3)
        t.samples.take(2).forEach { s ->
            v.addView(
                TextView(this).apply {
                    text = "· " + s.text
                    textSize = 12.5f
                    setTextColor(0xFF424242.toInt())
                    setPadding(0, 8, 0, 0)
                },
            )
        }
        val lp = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT,
        )
        lp.bottomMargin = 14
        v.layoutParams = lp
        return v
    }

    private fun hint(s: String) = TextView(this).apply {
        text = s
        textSize = 13f
        setTextColor(0xFF757575.toInt())
        gravity = Gravity.START
        setPadding(0, 6, 0, 6)
    }

    // ------------------------------------------------------------ 导出

    private fun export() {
        Thread {
            val msg = runCatching {
                val dir = File(
                    Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS),
                    "demand-radar",
                )
                dir.mkdirs()
                val stamp = SimpleDateFormat("yyyyMMdd-HHmm", Locale.US).format(Date())
                val f = File(dir, "screen-items-$stamp.json")
                f.writeText(Store.get(this).exportJson())
                "已导出到 下载/demand-radar/${f.name}（可拷回电脑做深度分析）"
            }.getOrElse { "导出失败：${it.message}" }
            runOnUiThread { Toast.makeText(this, msg, Toast.LENGTH_LONG).show() }
        }.start()
    }
}
