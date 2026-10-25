package com.vocabtype.app.ui

import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.SeekBar
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.vocabtype.app.R
import com.vocabtype.app.core.Insets
import com.vocabtype.app.core.Prefs
import com.vocabtype.app.core.SpeakService
import com.vocabtype.app.core.Speaker
import com.vocabtype.app.core.VoiceBox
import com.vocabtype.app.data.Dicts
import com.vocabtype.app.data.Sent
import com.vocabtype.app.data.W
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 播放器：把词库当歌单听。
 *
 * 参数全部即时生效（改完立刻从当前位置重新念），并且写进 Prefs：
 *   · 顺序 / 随机 / 只练错词
 *   · 读什么：单词、中文释义、例句（任意组合）
 *   · 每个词读几遍、词间隔、语速
 *   · 循环、后台播放
 */
class PlayerActivity : AppCompatActivity() {

    companion object {
        const val ORD_SEQ = 0
        const val ORD_RANDOM = 1
        const val ORD_WRONG = 2
    }

    private lateinit var prefs: Prefs
    private lateinit var speaker: Speaker
    private val handler = Handler(Looper.getMainLooper())

    private lateinit var tvNow: TextView
    private lateinit var tvPhone: TextView
    private lateinit var tvZh: TextView
    private lateinit var tvSent: TextView
    private lateinit var tvClock: TextView
    private lateinit var tvCount: TextView
    private lateinit var sbPos: SeekBar
    private lateinit var btnPlay: ImageButton
    private lateinit var btnOrder: Button
    private lateinit var box: LinearLayout

    private var words: List<W> = emptyList()
    private var warmInfo: TextView? = null
    private var idx = 0
    private var playing = false
    private var startedAt = 0L
    private var dragging = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_player)
        prefs = Prefs(this)
        Insets.apply(this, findViewById(R.id.root))
        speaker = VoiceBox.get(this, prefs)
        SpeakService.ensure(this)

        tvNow = findViewById(R.id.tvNow)
        tvPhone = findViewById(R.id.tvPhone)
        tvZh = findViewById(R.id.tvZh)
        tvSent = findViewById(R.id.tvSent)
        tvClock = findViewById(R.id.tvClock)
        tvCount = findViewById(R.id.tvCount)
        sbPos = findViewById(R.id.sbPos)
        btnPlay = findViewById(R.id.btnPlay)
        btnOrder = findViewById(R.id.btnOrder)
        box = findViewById(R.id.box)

        findViewById<ImageButton>(R.id.btnBack).setOnClickListener { finish() }
        findViewById<ImageButton>(R.id.btnPrev).setOnClickListener { jump(-1) }
        findViewById<ImageButton>(R.id.btnNext).setOnClickListener { jump(1) }
        btnPlay.setOnClickListener { toggle() }
        btnOrder.setOnClickListener { cycleOrder() }

        sbPos.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(s: SeekBar?, p: Int, fromUser: Boolean) {}
            override fun onStartTrackingTouch(s: SeekBar?) {
                dragging = true
            }

            override fun onStopTrackingTouch(s: SeekBar?) {
                dragging = false
                val p = s?.progress ?: return
                val wasPlaying = playing
                idx = p.coerceIn(0, (words.size - 1).coerceAtLeast(0))
                showCurrent(indexOnly = true)
                if (wasPlaying) {
                    start()
                }
            }
        })

        loadWords()
        buildPanels()
        applyParams()
        showCurrent(indexOnly = true)
        paintOrder()

        // 从上一界面带过来的"从第几个开始"
        idx = intent.getIntExtra("from", prefs.dictProgress(prefs.dictId))
            .coerceIn(0, (words.size - 1).coerceAtLeast(0))
        showCurrent(indexOnly = true)

        // 一进来直接开始播
        handler.postDelayed({ if (intent.getBooleanExtra("autoplay", true)) start() }, 380)
    }

    override fun onResume() {
        super.onResume()
        speaker.onState = { onSpeakerState() }
        paintPlay()
    }

    override fun onPause() {
        super.onPause()
        speaker.onState = null
        // 后台播放关掉，就跟着界面一起停
        if (!prefs.backgroundPlay) {
            playing = false
            speaker.stop()
        }
        saveProgress()
    }

    override fun onDestroy() {
        super.onDestroy()
        handler.removeCallbacksAndMessages(null)
        speaker.onState = null
    }

    // ------------------------------------------------------------ 数据

    private fun loadWords() {
        val metas = Dicts.index(this)
        val meta = metas.firstOrNull { it.id == prefs.dictId } ?: metas.firstOrNull() ?: return
        val all = Dicts.words(this, meta)
        words = when (prefs.playOrder) {
            ORD_RANDOM -> all.shuffled()
            ORD_WRONG -> {
                val q = prefs.queue()
                val set = q.map { it.lowercase() }.toHashSet()
                all.filter { it.name.lowercase() in set }.ifEmpty { all }
            }

            else -> all
        }
    }

    private fun reloadOrder() {
        val wasPlaying = playing
        speaker.stop()
        playing = false
        loadWords()
        idx = idx.coerceIn(0, (words.size - 1).coerceAtLeast(0))
        sbPos.max = (words.size - 1).coerceAtLeast(0)
        showCurrent(indexOnly = true)
        paintPlay()
        if (wasPlaying) start()
    }

    private fun saveProgress() {
        if (words.isEmpty()) return
        prefs.setDictProgress(prefs.dictId, idx)
    }

    // ------------------------------------------------------------ 播放

    private fun toggle() {
        if (playing) {
            playing = false
            speaker.pause()
            paintPlay()
        } else {
            start()
        }
    }

    private fun start() {
        val list = buildSeries()
        if (list.isEmpty()) {
            toast("没有可播放的内容：至少勾选「单词」")
            return
        }
        playing = true
        startedAt = System.currentTimeMillis()
        speaker.playSeries(
            list, idx,
            onGroup = { i ->
                idx = i
                showCurrent(indexOnly = true)
            },
            onDone = {
                playing = false
                paintPlay()
                saveProgress()
                toast("播放完毕")
            }
        )
        paintPlay()
    }

    private fun jump(d: Int) {
        if (words.isEmpty()) return
        val was = playing
        idx = (idx + d).coerceIn(0, words.size - 1)
        showCurrent(indexOnly = true)
        if (was) {
            speaker.stop()
            start()
        }
    }

    /** 每组：单词 ×重复次数 → 中文 → 句子 */
    private fun buildSeries(): List<List<String>> {
        val out = ArrayList<List<String>>()
        for (w in words) {
            val g = ArrayList<String>(6)
            if (prefs.playWord) repeat(prefs.playRepeat.coerceIn(1, 4)) { g.add(w.name) }
            if (prefs.playZh) {
                val c = Speaker.zhSpeech(w.trans)
                if (c.isNotBlank()) {
                    repeat(prefs.playRepeat.coerceIn(1, 2)) { g.add(c) }
                }
            }
            if (prefs.playSentence) {
                val s = Sent.short(this, w.name)?.en ?: Sent.complex(this, w.name)?.en
                if (!s.isNullOrBlank()) g.add(s)
            }
            if (g.isEmpty()) continue
            out.add(g)
        }
        return out
    }

    private fun applyParams() {
        speaker.applyPrefs(prefs)
        speaker.gapMs = prefs.playGap.toLong()
        speaker.zhRate = prefs.playZhRate
        speaker.zhOn = prefs.playZh || prefs.readZh
    }

    private fun onSpeakerState() {
        paintPlay()
    }

    private fun paintPlay() {
        val on = playing || speaker.nowPlaying
        btnPlay.setImageResource(if (on) R.drawable.ic_pause_big else R.drawable.ic_play_big)
        btnPlay.contentDescription = if (on) "暂停" else "播放"
    }

    // ------------------------------------------------------------ 界面

    private fun showCurrent(indexOnly: Boolean) {
        val w = words.getOrNull(idx + 0)
        tvCount.text = (idx + 1).coerceAtMost(words.size).toString() + " / " + words.size
        if (!dragging) {
            sbPos.max = (words.size - 1).coerceAtLeast(0)
            sbPos.progress = idx
        }
        if (w == null) {
            tvNow.text = "—"
            tvPhone.text = ""
            tvZh.text = ""
            tvSent.text = ""
            return
        }
        tvNow.text = w.name
        tvPhone.text = if (w.phone.isNotBlank()) "/" + w.phone.trim('/') + "/" else ""
        tvZh.text = w.trans
        val s = Sent.short(this, w.name) ?: Sent.complex(this, w.name)
        tvSent.text = s?.en ?: ""
        tvSent.visibility = if (s == null) View.GONE else View.VISIBLE
        tick()
    }

    private fun tick() {
        val fmt = SimpleDateFormat("mm:ss", Locale.US)
        val now = if (playing) System.currentTimeMillis() else startedAt
        val el = if (startedAt > 0 && now > startedAt) now - startedAt else 0
        val total = (words.size * (prefs.playRepeat * 2 + 3) * 1500L)
        tvClock.text = fmt.format(Date(el)) + " / " + fmt.format(Date(total))
        handler.removeCallbacks(tickR)
        if (playing) handler.postDelayed(tickR, 500)
    }

    private val tickR = Runnable { tick() }

    private fun cycleOrder() {
        prefs.playOrder = when (prefs.playOrder) {
            ORD_SEQ -> ORD_RANDOM
            ORD_RANDOM -> ORD_WRONG
            else -> ORD_SEQ
        }
        paintOrder()
        reloadOrder()
        buildPanels()
    }

    private fun paintOrder() {
        btnOrder.text = when (prefs.playOrder) {
            ORD_RANDOM -> "随机"
            ORD_WRONG -> "只错词"
            else -> "顺序"
        }
    }

    private fun toast(s: String) = Toast.makeText(this, s, Toast.LENGTH_SHORT).show()

    // ------------------------------------------------------------ 参数面板

    private fun buildPanels() {
        box.removeAllViews()

        head("CONTENT // 每轮读什么")
        toggle("读单词", "英文单词本体（有道真人音）", { prefs.playWord }) {
            prefs.playWord = it; applyParams(); afterChange()
        }
        toggle("读中文释义", "用中文念一遍意思（百度 zh）", { prefs.playZh }) {
            prefs.playZh = it; applyParams(); afterChange()
        }
        toggle("读例句", "每个词再读一句例句", { prefs.playSentence }) {
            prefs.playSentence = it; applyParams(); afterChange()
        }
        seg("每个词读几遍", arrayOf("1 遍", "2 遍", "3 遍"), { prefs.playRepeat - 1 }) {
            prefs.playRepeat = it + 1; applyParams(); afterChange()
        }

        head("TEMPO // 节奏")
        seek("语速", 5, 18, { (prefs.ttsRate * 10).toInt() }, {
            prefs.ttsRate = it / 10f; applyParams(); afterChange()
        }) { String.format(Locale.US, "%.1fx", it / 10.0) }
        seek("中文语速", 5, 15, { (prefs.playZhRate * 10).toInt() }, {
            prefs.playZhRate = it / 10f; applyParams()
        }) { String.format(Locale.US, "%.1fx", it / 10.0) }
        seek("词间停顿", 0, 30, { prefs.playGap / 100 }, { prefs.playGap = it * 100; applyParams() }) {
            String.format(Locale.US, "%.1fs", it / 10.0)
        }

        head("VOICE // 音色")
        seg("口音", arrayOf("英音 UK", "美音 US"), { prefs.accent - 1 }) {
            prefs.accent = it + 1; applyParams()
        }
        seg("发音引擎", arrayOf("系统 TTS", "有道在线"), { prefs.voiceEngine }) {
            prefs.voiceEngine = it; applyParams(); afterChange()
        }

        head("SCOPE // 范围")
        seg("顺序", arrayOf("顺序", "随机", "只错词"), { prefs.playOrder }) {
            prefs.playOrder = it
            paintOrder(); reloadOrder(); buildPanels()
        }
        toggle("后台播放", "切出去 / 锁屏也继续（通知栏可控制）", { prefs.backgroundPlay }) {
            prefs.backgroundPlay = it
            if (it) SpeakService.ensure(this) else SpeakService.stopService(this)
        }
        toggle("换词预下载", "提前把音频下好，几乎零等待", { prefs.prefetchVoice }) {
            prefs.prefetchVoice = it
        }
        // 中文预合成：中文引擎单次合成慢，但每句很短，提前批量做完就零等待
        val bar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(0, dp(10), 0, 0)
        }
        val go = Button(this).apply {
            text = "预合成中文"
            textSize = 12f
            typeface = android.graphics.Typeface.MONOSPACE
            setTextColor(Color.parseColor("#FF00F0FF"))
            background = resources.getDrawable(R.drawable.bg_btn, theme)
            minWidth = 0
            minHeight = 0
            setPadding(dp(12), dp(8), dp(12), dp(8))
            stateListAnimator = null
        }
        go.setOnClickListener { warmZh(go) }
        bar.addView(go, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply { rightMargin = dp(8) })
        val info = txt("中文已缓存 0 条", 12f, "#FF8A9BB2")
        warmInfo = info
        bar.addView(info)
        box.addView(bar)

        // 进来就自动在后台把整本中文预热掉（不打扰）
        if (prefs.playZh) handler.postDelayed({ warmZh(null, info) }, 1200)

        val pad = View(this)
        pad.layoutParams = LinearLayout.LayoutParams(1, dp(30))
        box.addView(pad)
    }

    private var warmCancel: Runnable? = null
    private var warming = false

    /** 批量预合成中文释义（第二次进播放器就完全不用等） */
    private fun warmZh(btn: Button?, info: TextView? = null) {
        if (warming) {
            warmCancel?.run()
            warming = false
            btn?.text = "预合成中文"
            return
        }
        val texts = words.mapNotNull {
            val c = Speaker.zhSpeech(it.trans)
            if (c.isNotBlank()) c else null
        }
        if (texts.isEmpty()) {
            toast("没有中文释义可合成")
            return
        }
        warming = true
        btn?.text = "取消"
        warmCancel = speaker.voiceEngine.warmZh(
            texts,
            onProgress = { d, t ->
                runOnUiThread {
                    val msg = "中文 $d / $t"
                    btn?.text = "取消"
                    warmInfo?.text = msg
                }
            },
            onFinish = { ok, fail ->
                runOnUiThread {
                    warming = false
                    btn?.text = "预合成中文"
                    warmInfo?.text = "中文已缓存 $ok 条" + (if (fail > 0) "（$fail 失败）" else "")
                    toast("中文预合成完成：$ok 条")
                }
            }
        )
    }

    /** 参数变了：从当前位置重播，立刻听到效果 */
    private fun afterChange() {
        applyParams()
        if (playing) {
            speaker.stop()
            handler.postDelayed({ start() }, 120)
        }
    }

    private fun head(t: String) {
        val tv = TextView(this)
        tv.text = "── $t ──────────────"
        tv.setTextColor(Color.parseColor("#FF00F0FF"))
        tv.textSize = 11f
        tv.typeface = android.graphics.Typeface.MONOSPACE
        tv.letterSpacing = 0.08f
        tv.setPadding(0, dp(16), 0, dp(6))
        box.addView(tv)
    }

    private fun row(): LinearLayout = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        setPadding(dp(11), dp(9), dp(9), dp(9))
        background = resources.getDrawable(R.drawable.bg_row, theme)
        layoutParams = LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply { topMargin = dp(5) }
    }

    private fun toggle(title: String, sub: String?, get: () -> Boolean, set: (Boolean) -> Unit) {
        val r = row()
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        col.addView(txt(title, 14f, "#FFE0E6ED"))
        if (sub != null) col.addView(txt(sub, 11f, "#FF4A5568").apply {
            setPadding(0, dp(2), 0, 0)
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
        }
        box.addView(r)
    }

    private fun seg(title: String, labels: Array<String>, get: () -> Int, set: (Int) -> Unit) {
        val wrap = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = resources.getDrawable(R.drawable.bg_row, theme)
            setPadding(dp(11), dp(9), dp(11), dp(10))
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply { topMargin = dp(5) }
        }
        wrap.addView(txt(title, 14f, "#FFE0E6ED"))
        val bar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(0, dp(8), 0, 0)
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
        box.addView(wrap)
    }

    private fun seek(
        title: String, min: Int, max: Int,
        get: () -> Int, set: (Int) -> Unit,
        fmt: (Int) -> String = { it.toString() }
    ) {
        val wrap = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = resources.getDrawable(R.drawable.bg_row, theme)
            setPadding(dp(11), dp(9), dp(11), dp(7))
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply { topMargin = dp(5) }
        }
        val top = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        top.addView(
            txt(title, 14f, "#FFE0E6ED"),
            LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
        )
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
            override fun onStopTrackingTouch(s: SeekBar?) {
                if (playing) afterChange()
            }
        })
        wrap.addView(sb)
        box.addView(wrap)
    }

    private fun txt(t: String, size: Float, color: String): TextView {
        val v = TextView(this)
        v.text = t
        v.textSize = size
        v.setTextColor(Color.parseColor(color))
        v.typeface = android.graphics.Typeface.MONOSPACE
        v.includeFontPadding = false
        return v
    }

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()
}
