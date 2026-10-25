package com.vocabtype.app.ui

import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.SeekBar
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.vocabtype.app.R
import com.vocabtype.app.core.Insets
import com.vocabtype.app.core.Prefs
import com.vocabtype.app.core.EdgeTts
import com.vocabtype.app.core.Voice
import com.vocabtype.app.data.Dicts
import java.util.Locale

class SettingsActivity : AppCompatActivity() {

    private lateinit var prefs: Prefs
    private lateinit var box: LinearLayout

    /** 设置页自己一个在线发音实例，专门用来预下载 / 看缓存 */
    private val voice by lazy { Voice(applicationContext) }
    private var sweepCancel: Runnable? = null
    private var sweepBusy = false
    private var cacheInfoView: TextView? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)
        prefs = Prefs(this)
        Insets.apply(this, findViewById(R.id.root), bottom = false)
        box = findViewById(R.id.box)
        findViewById<ImageButton>(R.id.btnBack).setOnClickListener { finish() }
        findViewById<ImageButton>(R.id.btnClose).setOnClickListener { finish() }
        build()
    }

    override fun onDestroy() {
        sweepCancel?.run()
        runCatching { voice.shutdown() }
        super.onDestroy()
    }

    private fun build() {
        box.removeAllViews()

        head("TRAINING // 训练")
        toggle(
            "严格模式", "打错的键不进入输入框，逼你打准（关了会把错字打进缓冲）",
            { prefs.strictTyping }, { prefs.strictTyping = it }
        )
        toggle(
            "整句听写复习", "句子打完后弹出听写面板，把刚打的词再默写一遍",
            { prefs.dictationReview }, { prefs.dictationReview = it }
        )
        seg(
            "词序", arrayOf("顺序", "随机", "只练错词", "智能错词优先"),
            { prefs.wordOrder }, { prefs.wordOrder = it }
        )
        toggle(
            "自动朗读单词", "每换一个词自动发音",
            { prefs.autoPlayWord }, { prefs.autoPlayWord = it }
        )
        toggle(
            "自动朗读句子", "切词后紧接着朗读当前句子",
            { prefs.autoPlaySentence }, { prefs.autoPlaySentence = it }
        )
        toggle(
            "循环朗读", "反复播放当前单词/句子（点顶栏 LOOP 也能开）",
            { prefs.loopAudio }, { prefs.loopAudio = it }
        )
        toggle(
            "打字时暂停循环", "一敲键盘就停，停手一会儿自动继续",
            { prefs.pauseLoopWhileTyping }, { prefs.pauseLoopWhileTyping = it }
        )

        head("DISPLAY // 显示")
        toggle("显示音标", null, { prefs.showPhonetic }, { prefs.showPhonetic = it })
        toggle("显示中文释义", null, { prefs.showTranslation }, { prefs.showTranslation = it })
        toggle("全部大写", "打字区用大写字母显示（原版默认）", { prefs.upper }, { prefs.upper = it })
        toggle("代码雨背景", "关掉省电，老机器更顺", { prefs.matrix }, { prefs.matrix = it })
        seek("打字区字号", 22, 80, { prefs.fsType }, { prefs.fsType = it })
        seek("例句字号", 12, 34, { prefs.fsSent }, { prefs.fsSent = it })

        head("AUDIO // 语音与反馈")
        seek("TTS 语速 ×10", 5, 18, { (prefs.ttsRate * 10).toInt() }, { prefs.ttsRate = it / 10f }, {
            String.format(java.util.Locale.US, "%.1fx", it / 10.0)
        })
        toggle("按键音效", "纯合成音，不带音频文件", { prefs.soundOn }, { prefs.soundOn = it })
        toggle("震动反馈", null, { prefs.vibrateOn }, { prefs.vibrateOn = it })

        head("VOICE // 发音 · 有道在线真人音")
        note("单词/短语走有道词典的免费发音接口（不用 Key，英音美音可选，下过一次就缓存到本地，之后离线也能播）。它是词典语料库、不是通用 TTS，长句读不了，会自动交回系统 TTS。")
        seg("发音引擎", arrayOf("系统 TTS", "有道在线"), { prefs.voiceEngine }, {
            prefs.voiceEngine = it
            toast(if (it == 1) "已切到有道在线真人发音" else "已切回系统 TTS")
        })
        seg("口音", arrayOf("英音 UK", "美音 US"), { prefs.accent - 1 }, { prefs.accent = it + 1 })
        toggle(
            "微软神经语音", "音质最好（晓晓/云希），需要联网；第一次合成稍慢，之后走缓存",
            { prefs.edgeVoiceOn }, { prefs.edgeVoiceOn = it }
        )
        seg(
            "微软中文音色",
            arrayOf("晓晓", "晓伊", "云希", "云扬"),
            { edgeIdx() },
            { prefs.edgeZhVoice = EdgeTts.ZH_VOICES[it].id }
        )
        toggle(
            "中文释义朗读", "英文读完后接着用中文念一遍释义；句子里连中文翻译一起读",
            { prefs.readZh }, { prefs.readZh = it }
        )
        toggle(
            "后台播放", "切出 App / 锁屏也继续朗读（通知栏有暂停、停止按钮）",
            { prefs.backgroundPlay }, { prefs.backgroundPlay = it }
        )
        note("长句和中文走百度翻译的免费发音接口（lan=en/uk/zh），单词走有道词典真人音；两边都失败才退回手机自带 TTS。")
        toggle(
            "换词预下载", "换词时后台先把单词发音下好，点播放零等待",
            { prefs.prefetchVoice }, { prefs.prefetchVoice = it }
        )
        voiceCache()

        head("AI // DeepSeek 造句（可选）")
        note("不填也能用：App 内置 3.4MB 离线句库（Tatoeba + 4000 Essential），6839 个词有例句。填了 Key 就用 AI 现造 + 给语法解析。")
        toggle("启用 AI 造句", null, { prefs.aiOn }, { prefs.aiOn = it })
        text("DeepSeek API Key", prefs.aiKey, multiline = false) { prefs.aiKey = it }
        text("System Prompt", prefs.aiSystem, multiline = true) { prefs.aiSystem = it }
        text("User 模板（{word} / {trans}）", prefs.aiTemplate, multiline = true) { prefs.aiTemplate = it }

        val bar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(0, dp(14), 0, dp(4))
        }
        bar.addView(btn("恢复默认 Prompt") {
            prefs.aiSystem = Prefs.DEFAULT_AI_SYSTEM
            prefs.aiTemplate = Prefs.DEFAULT_AI_TEMPLATE
            build()
            toast("已恢复默认 Prompt")
        }, lp())
        bar.addView(btn("恢复默认设置") {
            AlertDialog.Builder(this).setTitle("[ 恢复默认 ]")
                .setMessage("所有开关恢复默认值。\n累计统计、错词本、打卡进度都会保留。")
                .setPositiveButton("恢复") { _, _ ->
                    prefs.strictTyping = true
                    prefs.dictationReview = true
                    prefs.wordOrder = 0
                    prefs.autoPlayWord = true
                    prefs.autoPlaySentence = true
                    prefs.loopAudio = false
                    prefs.pauseLoopWhileTyping = true
                    prefs.showPhonetic = true
                    prefs.showTranslation = true
                    prefs.upper = true
                    prefs.matrix = true
                    prefs.fsType = 46
                    prefs.fsSent = 21
                    prefs.ttsRate = 1.0f
                    prefs.soundOn = true
                    prefs.vibrateOn = true
                    build()
                    toast("已恢复默认")
                }
                .setNegativeButton("取消", null).show()
        }, lp())
        box.addView(bar)

        val pad = View(this)
        pad.layoutParams = LinearLayout.LayoutParams(1, dp(40))
        box.addView(pad)
    }

    // ------------------------------------------------------------ 行构造器

    private fun head(t: String) {
        val tv = TextView(this)
        tv.text = "── " + t + " ──────────────"
        tv.setTextColor(Color.parseColor("#FF00F0FF"))
        tv.textSize = 12f
        tv.typeface = android.graphics.Typeface.MONOSPACE
        tv.letterSpacing = 0.08f
        tv.setPadding(0, dp(20), 0, dp(8))
        box.addView(tv)
    }

    private fun note(t: String) {
        val tv = TextView(this)
        tv.text = t
        tv.setTextColor(Color.parseColor("#FF4A5568"))
        tv.textSize = 11f
        tv.typeface = android.graphics.Typeface.MONOSPACE
        tv.setLineSpacing(0f, 1.25f)
        tv.setPadding(0, 0, 0, dp(10))
        box.addView(tv)
    }

    private fun row(): LinearLayout = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        setPadding(dp(11), dp(10), dp(9), dp(10))
        background = resources.getDrawable(R.drawable.bg_row, theme)
        layoutParams = LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply { topMargin = dp(6) }
    }

    private fun toggle(
        title: String, sub: String?,
        get: () -> Boolean, set: (Boolean) -> Unit
    ) {
        val r = row()
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        col.addView(txt(title, 14f, "#FFE0E6ED"))
        if (sub != null) col.addView(txt(sub, 11f, "#FF4A5568").apply {
            setPadding(0, dp(3), 0, 0)
            setLineSpacing(0f, 1.2f)
        })
        r.addView(col, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))

        val state = TextView(this)
        state.typeface = android.graphics.Typeface.MONOSPACE
        state.textSize = 13f
        state.setPadding(dp(12), dp(6), dp(12), dp(6))
        fun paint() {
            val on = get()
            state.text = if (on) "[ ON  ]" else "[ OFF ]"
            state.setTextColor(Color.parseColor(if (on) "#FF39FF14" else "#FF4A5568"))
            state.background = resources.getDrawable(R.drawable.bg_chip_on, theme)
            state.isSelected = on
        }
        paint()
        r.addView(state)
        r.setOnClickListener {
            set(!get())
            paint()
            Toast.makeText(this, "$title → ${if (get()) "开" else "关"}", Toast.LENGTH_SHORT).show()
        }
        box.addView(r)
    }

    private fun seg(title: String, labels: Array<String>, get: () -> Int, set: (Int) -> Unit) {
        val wrap = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = resources.getDrawable(R.drawable.bg_row, theme)
            setPadding(dp(11), dp(10), dp(11), dp(11))
        }
        wrap.addView(txt(title, 14f, "#FFE0E6ED"))
        val bar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(0, dp(9), 0, 0)
        }
        val views = ArrayList<TextView>()
        fun paint() {
            for (i in views.indices) views[i].isSelected = i == get()
        }
        for (i in labels.indices) {
            val b = TextView(this)
            b.text = labels[i]
            b.typeface = android.graphics.Typeface.MONOSPACE
            b.textSize = 12f
            b.setPadding(dp(11), dp(7), dp(11), dp(7))
            b.setTextColor(Color.parseColor("#FF8A9BB2"))
            b.background = resources.getDrawable(R.drawable.bg_chip_on, theme)
            b.setOnClickListener {
                set(i)
                paint()
            }
            views.add(b)
            bar.addView(b, LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply { rightMargin = dp(6) })
        }
        paint()
        wrap.addView(bar)
        box.addView(wrap, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply { topMargin = dp(6) })
    }

    private fun seek(
        title: String, min: Int, max: Int,
        get: () -> Int, set: (Int) -> Unit,
        fmt: (Int) -> String = { it.toString() }
    ) {
        val wrap = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = resources.getDrawable(R.drawable.bg_row, theme)
            setPadding(dp(11), dp(10), dp(11), dp(8))
        }
        val top = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        top.addView(txt(title, 14f, "#FFE0E6ED"), LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        val valv = txt(fmt(get()), 13f, "#FF39FF14")
        top.addView(valv)
        wrap.addView(top)

        val sb = SeekBar(this)
        sb.max = (max - min).coerceAtLeast(1)
        sb.progress = (get() - min).coerceIn(0, sb.max)
        sb.progressTintList = android.content.res.ColorStateList.valueOf(Color.parseColor("#FF00F0FF"))
        sb.thumbTintList = android.content.res.ColorStateList.valueOf(Color.parseColor("#FF39FF14"))
        sb.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(s: SeekBar?, p: Int, fromUser: Boolean) {
                val v = min + p
                valv.text = fmt(v)
                set(v)
            }
            override fun onStartTrackingTouch(s: SeekBar?) {}
            override fun onStopTrackingTouch(s: SeekBar?) {}
        })
        wrap.addView(sb)
        box.addView(wrap, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply { topMargin = dp(6) })
    }

    private fun text(title: String, cur: String, multiline: Boolean, set: (String) -> Unit) {
        val wrap = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = resources.getDrawable(R.drawable.bg_row, theme)
            setPadding(dp(11), dp(10), dp(11), dp(11))
        }
        wrap.addView(txt(title, 14f, "#FFE0E6ED"))
        val e = EditText(this)
        e.typeface = android.graphics.Typeface.MONOSPACE
        e.textSize = 12f
        e.setTextColor(Color.parseColor("#FFE0E6ED"))
        e.setHintTextColor(Color.parseColor("#FF4A5568"))
        e.background = resources.getDrawable(R.drawable.bg_input, theme)
        e.setPadding(dp(9), dp(8), dp(9), dp(8))
        e.setText(cur)
        if (multiline) {
            e.inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE
            e.maxLines = 8
            e.gravity = Gravity.TOP
        } else {
            e.inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD
            e.maxLines = 1
            e.imeOptions = android.view.inputmethod.EditorInfo.IME_ACTION_DONE
        }
        e.addTextChangedListener(object : android.text.TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun afterTextChanged(s: android.text.Editable?) { set(s?.toString() ?: "") }
        })
        wrap.addView(e, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply { topMargin = dp(7) })
        box.addView(wrap, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply { topMargin = dp(6) })
    }

    // ------------------------------------------------------------ 发音缓存

    private fun edgeIdx(): Int {
        val id = prefs.edgeZhVoice
        val i = EdgeTts.ZH_VOICES.indexOfFirst { it.id == id }
        return if (i < 0) 0 else i
    }

    private fun cacheInfo(): String =
        "${voice.cacheCount()} 条 / " + String.format(Locale.US, "%.1f MB", voice.sizeBytes() / 1048576.0)

    private fun refreshCacheInfo() {
        cacheInfoView?.text = cacheInfo()
    }

    private fun status(t: String) {
        cacheInfoView?.text = t
    }

    private fun voiceCache() {
        val wrap = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = resources.getDrawable(R.drawable.bg_row, theme)
            setPadding(dp(11), dp(10), dp(11), dp(10))
        }
        val top = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        top.addView(
            txt("发音缓存", 14f, "#FFE0E6ED"),
            LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
        )
        val info = txt(cacheInfo(), 12f, "#FF39FF14")
        cacheInfoView = info
        top.addView(info)
        wrap.addView(top)

        val sub = txt("可以把当前词库整本的发音一次下完，之后完全离线、音质不变", 11f, "#FF4A5568")
        sub.setPadding(0, dp(4), 0, 0)
        sub.setLineSpacing(0f, 1.2f)
        wrap.addView(sub)

        val bar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(0, dp(9), 0, 0)
        }
        val go = btn("预下载当前词库") { }
        go.setOnClickListener { sweep(go) }
        bar.addView(go, lp())
        bar.addView(btn("清空缓存") {
            voice.clearCache()
            refreshCacheInfo()
            toast("发音缓存已清空")
        }, lp())
        wrap.addView(bar)
        box.addView(wrap, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply { topMargin = dp(6) })
    }

    private fun sweep(go: Button) {
        if (sweepBusy) {                       // 再点一下 = 取消
            sweepCancel?.run()
            sweepBusy = false
            go.text = "预下载当前词库"
            refreshCacheInfo()
            return
        }
        val metas = Dicts.index(this)
        val meta = metas.firstOrNull { it.id == prefs.dictId } ?: metas.firstOrNull() ?: return
        sweepBusy = true
        go.text = "取消下载"
        status("读取词库中…")
        Thread {
            val words = runCatching { Dicts.words(this, meta).map { it.name } }.getOrDefault(emptyList())
            runOnUiThread {
                if (words.isEmpty()) {
                    sweepBusy = false
                    go.text = "预下载当前词库"
                    refreshCacheInfo()
                    toast("没读到词库")
                    return@runOnUiThread
                }
                val cancel = voice.sweep(
                    words,
                    onProgress = { d, t -> if (sweepBusy) status("下载中 $d / $t") },
                    onFinish = { ok, fail ->
                        sweepBusy = false
                        go.text = "预下载当前词库"
                        refreshCacheInfo()
                        toast("发音预下载完成：成功 $ok / 失败 $fail")
                    }
                )
                sweepCancel = cancel
            }
        }.start()
    }

    private fun btn(t: String, on: () -> Unit): Button {
        val b = Button(this)
        b.text = t
        b.textSize = 12f
        b.typeface = android.graphics.Typeface.MONOSPACE
        b.setTextColor(Color.parseColor("#FF00F0FF"))
        b.background = resources.getDrawable(R.drawable.bg_btn, theme)
        b.minWidth = 0
        b.minHeight = 0
        b.setPadding(dp(12), dp(8), dp(12), dp(8))
        b.stateListAnimator = null
        b.setOnClickListener { on() }
        return b
    }

    private fun lp(): LinearLayout.LayoutParams =
        LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply { rightMargin = dp(8) }

    private fun txt(t: String, size: Float, color: String): TextView {
        val v = TextView(this)
        v.text = t
        v.textSize = size
        v.setTextColor(Color.parseColor(color))
        v.typeface = android.graphics.Typeface.MONOSPACE
        return v
    }

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density + 0.5f).toInt()

    private fun toast(s: String) = Toast.makeText(this, s, Toast.LENGTH_SHORT).show()
}
