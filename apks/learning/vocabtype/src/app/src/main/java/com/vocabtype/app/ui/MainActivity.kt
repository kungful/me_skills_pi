package com.vocabtype.app.ui

import android.content.Intent
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.Editable
import android.text.TextWatcher
import android.view.KeyEvent
import android.view.ScaleGestureDetector
import android.view.View
import android.view.inputmethod.InputMethodManager
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.vocabtype.app.R
import com.vocabtype.app.core.Ai
import com.vocabtype.app.core.Insets
import com.vocabtype.app.core.Prefs
import com.vocabtype.app.core.Speaker
import com.vocabtype.app.core.SpeakService
import com.vocabtype.app.core.VoiceBox
import com.vocabtype.app.data.DictMeta
import com.vocabtype.app.data.Dicts
import com.vocabtype.app.data.Sent
import com.vocabtype.app.data.W
import com.vocabtype.app.fx.Sfx
import com.vocabtype.app.fx.Vib
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.max

class MainActivity : AppCompatActivity() {

    companion object {
        const val MODE_WORD = 0
        const val MODE_SHORT = 1
        const val MODE_COMPLEX = 2

        const val ORD_SEQ = 0
        const val ORD_RANDOM = 1
        const val ORD_REVIEW = 2
        const val ORD_SMART = 3

        const val RQ_DICT = 1
        const val RQ_SETTINGS = 2
        const val RQ_REVIEW = 3
        const val RQ_DICTATE = 4

        /** 打字区字号上下限（sp），和设置页的 seek 范围保持一致 */
        const val FS_MIN = 22
        const val FS_MAX = 80
        /** 长按 A- / A+ 复位到这个默认字号 */
        const val FS_DEF = 46
    }

    private lateinit var prefs: Prefs
    private lateinit var speaker: Speaker
    private val handler = Handler(Looper.getMainLooper())

    private lateinit var rain: Rain
    private lateinit var typeView: TypeView
    private lateinit var typeBox: FrameLayout
    private lateinit var et: EditText
    private lateinit var tvWpm: TextView
    private lateinit var tvAcc: TextView
    private lateinit var tvStrk: TextView
    private lateinit var tvErr: TextView
    private lateinit var tvProg: TextView
    private lateinit var tvPhone: TextView
    private lateinit var tvTrans: TextView
    private lateinit var tvHint: TextView
    private lateinit var tvFoot: TextView
    private lateinit var tvBrand: TextView
    private lateinit var tvTail: TextView
    private lateinit var btnDict: Button
    private lateinit var tabWord: Button
    private lateinit var tabShort: Button
    private lateinit var tabComplex: Button
    private lateinit var btnLoop: ImageButton
    private lateinit var btnCase: Button
    private lateinit var btnSizeDown: Button
    private lateinit var scale: ScaleGestureDetector
    private lateinit var btnSizeUp: Button
    private lateinit var cardShort: LinearLayout
    private lateinit var cardComplex: LinearLayout
    private lateinit var shortZh: TextView
    private lateinit var tvShortGram: TextView
    private lateinit var complexZh: TextView
    private lateinit var tvComplexGram: TextView
    private lateinit var shortFlow: FlowLayout
    private lateinit var complexFlow: FlowLayout
    private lateinit var statsBar: LinearLayout
    private lateinit var content: LinearLayout
    private lateinit var scroll: ScrollView

    // ---------------- 词库 ----------------
    private var metas: List<DictMeta> = emptyList()
    private var dict: List<W> = emptyList()
    private var order: IntArray = IntArray(0)
    private var pos = 0
    private var customWords: List<W>? = null
    private var mode = MODE_WORD

    // ---------------- 打字 ----------------
    private var targets: List<String> = emptyList()
    private var wi = 0
    private var buf = ""
    private var refWord: W? = null
    private var guard = false
    private var startAt = 0L
    private var idleAt = 0L

    // ---------------- 会话统计 ----------------
    private var sTyped = 0
    private var sCorrect = 0
    private var sMistakes = 0
    private var sStreak = 0
    private var sBest = 0
    private var sWords = 0

    /** 默写模式：只看释义/听音，不看句子 */
    private var blind = false

    // ---------------- 当前例句 ----------------
    private var shortS: Sent.Pair_? = null
    private var complexS: Sent.Pair_? = null
    private var shortGram = ""
    private var complexGram = ""
    private var aiToken = 0

    private var zen = false
    private var pendingFocus = true

    // ================================================================

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        prefs = Prefs(this)
        com.vocabtype.app.core.EdgeDrm.selfTest()
        com.vocabtype.app.core.EdgeTts.selfTestAsync()
        speaker = VoiceBox.get(this, prefs)
        // 申请通知权限（Android 13+），后台朗读的常驻通知要用
        runCatching {
            if (Build.VERSION.SDK_INT >= 33 &&
                checkSelfPermission("android.permission.POST_NOTIFICATIONS") !=
                android.content.pm.PackageManager.PERMISSION_GRANTED
            ) {
                requestPermissions(arrayOf("android.permission.POST_NOTIFICATIONS"), 91)
            }
        }
        // 提前把前台服务挂上，退到后台才不会被掐
        SpeakService.ensure(this)
        Sfx.enabled = prefs.soundOn
        Vib.enabled = prefs.vibrateOn
        Vib.bind(this)

        bind()
        Insets.apply(this, content, ime = true)
        Sent.preload(this)
        Sfx.prepare()

        metas = Dicts.index(this)
        if (metas.isEmpty()) {
            toast("词库数据缺失")
        }

        wire()

        loadDict(prefs.dictId, fresh = true)
        applyLook()
        showCurrent()

        if (prefs.vibrateOn) Vib.bind(this)
    }

    // ----------------------------------------------------------------

    private fun bind() {
        rain = findViewById(R.id.rain)
        typeView = findViewById(R.id.typeView)
        typeBox = findViewById(R.id.typeBox)
        et = findViewById(R.id.etInput)
        tvWpm = findViewById(R.id.tvWpm)
        tvAcc = findViewById(R.id.tvAcc)
        tvStrk = findViewById(R.id.tvStrk)
        tvErr = findViewById(R.id.tvErr)
        tvProg = findViewById(R.id.tvProg)
        tvPhone = findViewById(R.id.tvPhone)
        tvTrans = findViewById(R.id.tvTrans)
        tvHint = findViewById(R.id.tvHint)
        tvFoot = findViewById(R.id.tvFoot)
        tvBrand = findViewById(R.id.tvBrand)
        tvTail = findViewById(R.id.tvTail)
        btnDict = findViewById(R.id.btnDict)
        tabWord = findViewById(R.id.tabWord)
        tabShort = findViewById(R.id.tabShort)
        tabComplex = findViewById(R.id.tabComplex)
        btnLoop = findViewById(R.id.btnLoop)
        btnCase = findViewById(R.id.btnCase)
        btnSizeDown = findViewById(R.id.btnSizeDown)
        btnSizeUp = findViewById(R.id.btnSizeUp)
        cardShort = findViewById(R.id.cardShort)
        cardComplex = findViewById(R.id.cardComplex)
        shortZh = findViewById(R.id.shortZh)
        tvShortGram = findViewById(R.id.shortGram)
        complexZh = findViewById(R.id.complexZh)
        tvComplexGram = findViewById(R.id.complexGram)
        shortFlow = findViewById(R.id.shortFlow)
        complexFlow = findViewById(R.id.complexFlow)
        statsBar = findViewById(R.id.statsBar)
        content = findViewById(R.id.content)
        scroll = findViewById(R.id.scroll)
    }

    private fun wire() {
        btnDict.setOnClickListener { startActivityForResult(Intent(this, DictActivity::class.java), RQ_DICT) }
        findViewById<ImageButton>(R.id.btnSettings).setOnClickListener {
            startActivityForResult(Intent(this, SettingsActivity::class.java), RQ_SETTINGS)
        }
        findViewById<ImageButton>(R.id.btnStats).setOnClickListener { openStats() }
        findViewById<ImageButton>(R.id.btnReview).setOnClickListener { openReview() }

        tabWord.setOnClickListener { setMode(MODE_WORD) }
        tabShort.setOnClickListener { setMode(MODE_SHORT) }
        tabComplex.setOnClickListener { setMode(MODE_COMPLEX) }

        findViewById<ImageButton>(R.id.btnPlay).setOnClickListener { playAll() }
        findViewById<ImageButton>(R.id.btnPlayer).setOnClickListener {
            val i = Intent(this, PlayerActivity::class.java)
            i.putExtra("from", pos)
            i.putExtra("autoplay", false)
            startActivity(i)
        }

        // 打字区显示大写 / 小写一键切（原版默认大写，这里给个开关）
        btnCase.setOnClickListener {
            prefs.upper = !prefs.upper
            if (prefs.vibrateOn) Vib.ok()
            paintCase()
            redraw()
        }
        // 字号加减
        btnSizeDown.setOnClickListener { bumpSize(-3) }
        btnSizeUp.setOnClickListener { bumpSize(3) }
        // 长按 A- / A+ 复位到默认字号
        val reset = android.view.View.OnLongClickListener {
            prefs.fsType = FS_DEF
            if (prefs.vibrateOn) Vib.ok()
            paintCase(); redraw()
            flashFoot("字号已复位到 ${FS_DEF}sp")
            true
        }
        btnSizeDown.setOnLongClickListener(reset)
        btnSizeUp.setOnLongClickListener(reset)
        // 两指捉合直接缩放打字区字号
        scale = ScaleGestureDetector(this, object : ScaleGestureDetector.SimpleOnScaleGestureListener() {
            override fun onScale(d: ScaleGestureDetector): Boolean {
                val nv = (prefs.fsType * d.scaleFactor).toInt().coerceIn(FS_MIN, FS_MAX)
                if (nv != prefs.fsType) {
                    prefs.fsType = nv
                    paintCase()
                    redraw()
                    if (prefs.vibrateOn) Vib.ok()
                }
                return true
            }
        })
        // 双指捉合缩放：始终把事件喂给检测器（它会自己忽略单指），
        // 但只在多指/缩放进行中时消费事件，单指点按仍然走 onClick / onLongClick
        typeBox.setOnTouchListener { _, e ->
            scale.onTouchEvent(e)
            scale.isInProgress || e.pointerCount >= 2
        }
        btnLoop.setOnClickListener {
            prefs.loopAudio = !prefs.loopAudio
            paintLoop()
            if (prefs.loopAudio) startLoop() else speaker.stopLoop()
        }
        findViewById<ImageButton>(R.id.btnZen).setOnClickListener { toggleZen() }

        findViewById<ImageButton>(R.id.shortPlay).setOnClickListener {
            shortS?.let { speaker.saySentence(it.en, it.zh) }
        }
        findViewById<ImageButton>(R.id.complexPlay).setOnClickListener {
            complexS?.let { speaker.saySentence(it.en, it.zh) }
        }
        findViewById<ImageButton>(R.id.shortRegen).setOnClickListener { regen(short = true) }
        findViewById<ImageButton>(R.id.complexRegen).setOnClickListener { regen(short = false) }

        et.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun afterTextChanged(s: Editable?) {
                if (guard) return
                onInput(s?.toString() ?: "")
            }
        })
        et.setOnKeyListener { _, code, e ->
            if (code == KeyEvent.KEYCODE_DEL && e.action == KeyEvent.ACTION_DOWN) {
                // 空输入框时 IME 不产生文本变化，这里兜一层
                if (buf.isNotEmpty()) { back()
                    return@setOnKeyListener true }
            }
            false
        }

        typeBox.setOnClickListener { focusInput() }
        typeBox.setOnLongClickListener { clearAll(); true }
        scroll.setOnClickListener { focusInput() }
        tvHint.setOnClickListener { focusInput() }
    }

    // ---------------------------------------------------------------- 词库

    private fun loadDict(id: Int, fresh: Boolean) {
        if (metas.isEmpty()) return
        val m = metas.firstOrNull { it.id == id } ?: metas[0]
        dict = Dicts.words(this, m)
        prefs.dictId = m.id
        btnDict.text = m.name + "  ·  " + dict.size
        customWords = null
        if (fresh) pos = prefs.dictProgress(m.id).coerceIn(0, max(0, dict.size - 1))
        buildOrder()
    }

    private fun buildOrder() {
        val n = dict.size
        val idx = ArrayList<Int>(n)
        for (i in 0 until n) idx.add(i)
        when (prefs.wordOrder) {
            ORD_RANDOM -> idx.shuffle()
            ORD_REVIEW -> {
                val mis = prefs.mistakes()
                val r = idx.filter { mis.containsKey(dict[it].name.lowercase()) }
                order = if (r.isNotEmpty()) r.toIntArray() else idx.toIntArray()
                return
            }
            ORD_SMART -> {
                val mis = prefs.mistakes()
                val err = idx.filter { mis.containsKey(dict[it].name.lowercase()) }.shuffled()
                val ok = idx.filter { !mis.containsKey(dict[it].name.lowercase()) }.shuffled()
                order = (err + ok).toIntArray()
                return
            }
        }
        order = idx.toIntArray()
    }

    private fun cur(): W? {
        customWords?.let { return it.getOrNull(pos) }
        if (order.isEmpty()) return null
        val oi = order.getOrNull(pos) ?: return null
        return dict.getOrNull(oi)
    }

    // ---------------------------------------------------------------- 目标

    private fun setMode(m: Int) {
        if (mode == m) return
        mode = m
        prefs.mode = m
        paintMode()
        refWord = null
        buf = ""
        showCurrent()
    }

    private fun paintMode() {
        tabWord.isSelected = mode == MODE_WORD
        tabShort.isSelected = mode == MODE_SHORT
        tabComplex.isSelected = mode == MODE_COMPLEX
    }

    private fun paintLoop() {
        btnLoop.isSelected = prefs.loopAudio
    }

    /** 大小写按钮：亮绿 = 大写，灰 = 照原样小写；顺带把当前字号写在 A- / A+ 上 */
    private fun paintCase() {
        btnCase.text = if (prefs.upper) "AA" else "Aa"
        btnCase.contentDescription =
            if (prefs.upper) "大小写切换，当前全大写" else "大小写切换，当前照原样小写"
        btnCase.isSelected = prefs.upper
        btnCase.setTextColor(
            if (prefs.upper) getColor(R.color.green) else getColor(R.color.text_mid)
        )
        val dim = getColor(R.color.text_mid)
        val lit = getColor(R.color.cyan)
        btnSizeDown.setTextColor(if (prefs.fsType > FS_MIN) lit else dim)
        btnSizeUp.setTextColor(if (prefs.fsType < FS_MAX) lit else dim)
    }

    /** 调打字区字号，并在底部提示条上闪一下当前值 */
    private fun bumpSize(d: Int) {
        val nv = (prefs.fsType + d).coerceIn(FS_MIN, FS_MAX)
        if (nv == prefs.fsType) {
            toast(if (d > 0) "已经最大了" else "已经最小了")
            return
        }
        prefs.fsType = nv
        if (prefs.vibrateOn) Vib.ok()
        paintCase()
        redraw()
        flashFoot("打字区字号 ${nv}sp   ·   也可以双指在打字区抚合缩放")
    }

    private var footFlash: Runnable? = null

    /** 播放器式自动连播 */
    private var autoPlaying = false

    private fun flashFoot(msg: String) {
        tvFoot.text = msg
        footFlash?.let { handler.removeCallbacks(it) }
        val r = Runnable { tvFoot.text = getString(R.string.foot_hint) }
        footFlash = r
        handler.postDelayed(r, 2200)
    }

    /** 把当前词的例句（离线 + 可选 AI）准备好 */
    private fun showCurrent(silent: Boolean = false) {
        val w = cur()
        aiToken++
        if (!silent) {
            speaker.stopLoop()
            speaker.stop()
        }
        if (w == null) {
            targets = emptyList()
            buf = ""
            typeView.setContent(emptyList(), "", 0)
            typeView.setEmptyText("[ 词库为空 ]")
            tvPhone.text = ""
            tvTrans.text = ""
            cardShort.visibility = View.GONE
            cardComplex.visibility = View.GONE
            return
        }

        // 离线例句
        shortS = Sent.short(this, w.name)
        complexS = Sent.complex(this, w.name)
        shortGram = ""
        complexGram = ""
        if (blind) { shortS = null; complexS = null }

        // 换词就把发音先下好（有道在线时点播放零等待）
        if (prefs.prefetchVoice) speaker.prefetch(w.name)

        fillTargets(w)
        buf = ""
        wi = 0
        startAt = 0L
        pushInput("")
        redraw()

        tvPhone.text = if (prefs.showPhonetic && !blind && w.phone.isNotBlank()) "/" + w.phone.trim('/') + "/" else ""
        tvPhone.visibility = if (blind) View.GONE else View.VISIBLE
        tvTrans.text = if (prefs.showTranslation || blind) w.trans else ""
        tvTrans.visibility = if ((prefs.showTranslation || blind) && w.trans.isNotBlank()) View.VISIBLE else View.GONE
        tvHint.text = if (blind) "[ 默写 ] 听发音 · 看释义 · 敲出单词" else getString(R.string.hint_idle)

        paintMode()
        paintLoop()
        refreshCards()
        updateStats()
        maybeAi(w)

        if (!silent && !autoPlaying && prefs.autoPlayWord) {
            val say = if (mode == MODE_WORD || targets.size == 1) w.name else w.name
            val sent = if (mode == MODE_WORD) null else curSentenceText()
            if (sent != null && prefs.autoPlaySentence) {
                speaker.saySentence(sent, curSentenceZh())
            } else {
                speaker.sayWord(say, w.trans)
            }
        }
        if (!silent && !autoPlaying && prefs.loopAudio) startLoop()
    }

    private fun fillTargets(w: W) {
        refWord?.let {
            targets = listOf(it.name)
            return
        }
        if (blind) {
            targets = listOf(w.name)
            return
        }
        val sent = when (mode) {
            MODE_SHORT -> shortS?.en
            MODE_COMPLEX -> complexS?.en
            else -> null
        }
        targets = if (sent.isNullOrBlank()) listOf(w.name) else splitTargets(sent)
    }

    /**
     * 句子拆成打字目标。
     * 标点必须剥掉，不然用户在手机上要切到符号键盘才能打句尾的句号；
     * 连字符/斜杠直接当分隔符切开（well-known → well + known）。
     * 撇号保留（don't 在英文键盘上很好打）。
     */
    private fun splitTargets(sentence: String): List<String> {
        val out = ArrayList<String>(16)
        for (raw in Sent.words(sentence)) {
            for (part in raw.split('-', '\u2013', '\u2014', '/', '\\')) {
                val t = part.trim { c -> !c.isLetter() && c != '\'' && c != '\u2019' }
                if (t.isNotEmpty()) out.add(t)
            }
        }
        return out
    }

    private fun curSentenceText(): String? = when (mode) {
        MODE_SHORT -> shortS?.en
        MODE_COMPLEX -> complexS?.en
        else -> null
    }

    private fun curSentenceZh(): String? = when (mode) {
        MODE_SHORT -> shortS?.zh
        MODE_COMPLEX -> complexS?.zh
        else -> null
    }

    private fun currentTarget(): String = targets.getOrNull(wi) ?: ""

    private fun redraw() {
        typeView.setTypeSize(prefs.fsType * resources.displayMetrics.scaledDensity)
        typeView.upper = prefs.upper
        typeView.setContent(targets, buf, wi)
        // 给读屏 / 自动化测试留个抓手
        typeView.contentDescription = "VT|target=${targets.joinToString(" ")}|wi=$wi|buf=$buf"
    }

    // ---------------------------------------------------------------- 输入

    private fun pushInput(s: String) {
        guard = true
        et.setText(s)
        et.setSelection(et.text?.length ?: 0)
        lastInput = s
        guard = false
    }

    private var lastInput = ""

    private fun onInput(raw: String) {
        val target = currentTarget()
        if (target.isEmpty()) { pushInput(""); return }

        // 只留可见 ASCII，扔掉空格/中文/换行
        val t = raw.filter { it.code in 33..126 }
        val clean = if (t.length != raw.length) t else raw

        idleAt = System.currentTimeMillis()
        pauseLoopIfTyping()

        if (clean.isEmpty()) {
            if (buf.isNotEmpty()) back()
            else if (raw.isNotEmpty()) pushInput("")
            return
        }

        // 变短 = 删除
        if (clean.length < lastInput.length) {
            lastInput = clean
            buf = clean
            afterEdit()
            return
        }

        // 变长 = 新增字符，逐个判定
        var accepted = lastInput
        var reject = false
        for (i in lastInput.length until clean.length) {
            val c = clean[i]
            val k = accepted.length
            val expect = if (k < target.length) target[k] else null
            val ok = expect != null && expect.lowercaseChar() == c.lowercaseChar()
            sTyped++
            if (ok) {
                sCorrect++
                accepted += c
            } else {
                registerMistake(expect == null)
                if (prefs.strictTyping) {
                    reject = true
                } else {
                    accepted += c
                }
            }
        }

        lastInput = accepted
        buf = accepted
        if (reject) {
            pushInput(accepted)
            typeView.flashError()
            afterEdit()
            return
        }
        if (accepted != clean) pushInput(accepted)
        afterEdit()
    }

    private fun back() {
        if (buf.isEmpty()) return
        buf = buf.substring(0, buf.length - 1)
        lastInput = buf
        pushInput(buf)
        afterEdit()
    }

    private fun clearAll() {
        buf = ""
        lastInput = ""
        pushInput("")
        afterEdit()
        toast("已清空")
    }

    private fun afterEdit() {
        redraw()
        updateStats()

        val target = currentTarget()
        if (target.isNotEmpty() && buf.equals(target, ignoreCase = true)) {
            completeWord()
        }
    }

    private fun registerMistake(overflow: Boolean) {
        sMistakes++
        sStreak = 0
        Sfx.play(Sfx.ERR)
        if (prefs.vibrateOn) Vib.bad()
        val w = refWord ?: cur()
        val nm = currentTarget().ifBlank { w?.name ?: "" }
        if (!overflow && nm.isNotEmpty()) {
            val key = nm.lowercase().trim { !it.isLetter() && it != '\'' && it != '-' }
            if (key.isNotEmpty()) {
                val m = prefs.mistakes()
                m[key] = (m[key] ?: 0) + 1
                prefs.saveMistakes(m)
                val q = prefs.queue()
                if (!q.contains(key)) { q.add(key); prefs.saveQueue(q) }
            }
        }
    }

    private fun completeWord() {
        sWords++
        sStreak++
        if (sStreak > sBest) sBest = sStreak
        Sfx.play(Sfx.WORD)
        if (prefs.vibrateOn) Vib.ok()
        typeView.flashDone()

        // 记「已练过」
        val nm = currentTarget().lowercase()
        if (nm.isNotEmpty()) {
            val set = prefs.learnedSet()
            if (set.add(nm)) { prefs.saveLearnedSet(set); prefs.learned = set.size }
            // 打对了就从复习队列里挪走
            val q = prefs.queue()
            if (q.remove(nm)) prefs.saveQueue(q)
        }

        if (refWord != null) {
            refWord = null
            buf = ""
            showCurrent()
            return
        }

        if (mode == MODE_WORD || targets.size <= 1) {
            buf = ""
            advance()
            return
        }

        // 句子模式：推进到下一个词
        wi++
        buf = ""
        lastInput = ""
        pushInput("")
        if (wi >= targets.size) {
            completeSentence()
        } else {
            redraw()
            updateStats()
        }
    }

    private fun completeSentence() {
        Sfx.play(Sfx.SENT)
        val words = targets.filter { it.isNotBlank() }
            .map { it.lowercase().trim { c -> !c.isLetter() && c != '\'' && c != '-' } }
            .filter { it.isNotEmpty() }

        if (prefs.dictationReview && !blind && words.size in 2..24) {
            val i = Intent(this, ReviewActivity::class.java)
            i.putExtra(ReviewActivity.EXTRA_WORDS, ArrayList(words))
            i.putExtra(ReviewActivity.EXTRA_SENTENCE, targets.joinToString(" "))
            i.putExtra(ReviewActivity.EXTRA_MODE, 1)
            startActivityForResult(i, RQ_DICTATE)
            reviewOpen = true
        } else {
            advance()
        }
    }

    private var reviewOpen = false

    private fun advance() {
        // 整本打完 → 掌声 + 重来
        if (customWords == null && order.isNotEmpty() && pos >= order.size - 1) {
            finishRound()
            return
        }
        if (customWords != null && pos >= customWords!!.size - 1) {
            customWords = null
            blind = false
            pos = 0
            showCurrent()
            return
        }
        pos++
        if (customWords == null) prefs.setDictProgress(prefs.dictId, pos)
        showCurrent()
    }

    private fun finishRound() {
        Sfx.play(Sfx.DONE)
        saveSession()
        val secs = ((System.currentTimeMillis() - sessStart()) / 1000).coerceAtLeast(1L).toInt()
        AlertDialog.Builder(this)
            .setTitle("[ 词库通关 ]")
            .setMessage(
                "词库：${btnDict.text}\n\n" +
                    "本次打击 ${sWords} 个\n" +
                    "用时 ${fmtTime(secs)}\n" +
                    "平均 WPM ${wpm()}\n" +
                    "准确率 ${acc()}%\n" +
                    "最长连击 ${sBest}"
            )
            .setPositiveButton("再来一遍") { _, _ -> pos = 0; prefs.setDictProgress(prefs.dictId, 0); showCurrent() }
            .setNegativeButton("休息一下") { _, _ -> pos = 0; showCurrent() }
            .setCancelable(false)
            .show()
    }

    private fun sessStart(): Long = if (sessT0 == 0L) System.currentTimeMillis() else sessT0

    private var sessT0 = 0L

    // ---------------------------------------------------------------- 统计

    private fun wpm(): String {
        if (sTyped == 0) return "0.00"
        val secs = ((System.currentTimeMillis() - sessStart()) / 1000.0).coerceAtLeast(1.0)
        val w = sTyped / 5.0
        return String.format(Locale.US, "%.2f", w / (secs / 60.0))
    }

    private fun acc(): String {
        if (sTyped == 0) return "0.00"
        return String.format(Locale.US, "%.2f", sCorrect * 100.0 / sTyped)
    }

    private fun updateStats() {
        if (sessT0 == 0L && sWords == 0 && sTyped == 0) sessT0 = System.currentTimeMillis()
        tvWpm.text = wpm() + " WPM"
        tvAcc.text = acc() + "%"
        tvStrk.text = "STRK $sStreak"
        tvErr.text = "ERR $sMistakes"
        val total = if (customWords != null) customWords!!.size else order.size
        tvProg.text = (pos + 1).coerceAtMost(max(1, total)).toString() + "/" + total
    }

    private fun saveSession() {
        if (sTyped == 0 && sWords == 0) return
        prefs.totalTyped += sTyped
        prefs.totalCorrect += sCorrect
        prefs.totalMistakes += sMistakes
        prefs.totalWords += sWords
        if (sBest > prefs.bestStreak) prefs.bestStreak = sBest
        val secs = ((System.currentTimeMillis() - sessStart()) / 1000).toInt()
        prefs.totalSeconds += secs
        prefs.sessions += 1
        val day = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())
        if (prefs.lastDay != day) {
            prefs.lastDay = day
            prefs.practiceDays += 1
        }
    }

    private fun resetSession() {
        sTyped = 0; sCorrect = 0; sMistakes = 0; sStreak = 0; sBest = 0; sWords = 0
        sessT0 = 0L
    }

    private fun fmtTime(s: Int): String = "%d:%02d".format(s / 60, s % 60)

    // ---------------------------------------------------------------- 例句卡

    private fun refreshCards() {
        val w = cur()
        val showShort = shortS != null && w != null
        val showComplex = complexS != null && w != null
        if (!showShort && !showComplex) {
            cardShort.visibility = View.GONE
            cardComplex.visibility = View.GONE
            tvTail.text = "[ 该词暂无例句 · 点词库换个词，或填 DeepSeek Key 让 AI 造句 ]"
            return
        }
        tvTail.text = "点句子里的任意单词 → 发音 + 释义"

        if (showShort) {
            cardShort.visibility = View.VISIBLE
            shortZh.text = shortS!!.zh.ifBlank { "" }
            shortZh.visibility = if (shortS!!.zh.isBlank()) View.GONE else View.VISIBLE
            tvShortGram.text = shortGram
            tvShortGram.visibility = if (shortGram.isBlank()) View.GONE else View.VISIBLE
            buildChips(shortFlow, shortS!!.en)
        } else cardShort.visibility = View.GONE

        if (showComplex) {
            cardComplex.visibility = View.VISIBLE
            complexZh.text = complexS!!.zh.ifBlank { "" }
            complexZh.visibility = if (complexS!!.zh.isBlank()) View.GONE else View.VISIBLE
            tvComplexGram.text = complexGram
            tvComplexGram.visibility = if (complexGram.isBlank()) View.GONE else View.VISIBLE
            buildChips(complexFlow, complexS!!.en)
        } else cardComplex.visibility = View.GONE
    }

    private fun buildChips(flow: FlowLayout, sentence: String) {
        flow.removeAllViews()
        val hl = cur()?.name?.lowercase() ?: ""
        for (tk in Sent.tokenize(sentence)) {
            val tv = TextView(this)
            tv.typeface = android.graphics.Typeface.MONOSPACE
            tv.textSize = prefs.fsSent.toFloat()
            tv.setPadding(dp(3f), dp(2f), dp(3f), dp(2f))
            tv.text = tk.text
            if (!tk.word) {
                tv.setTextColor(Color.parseColor("#8A9BB2"))
                flow.addWord(tv)
                continue
            }
            val isTarget = tk.clean.lowercase() == hl
            tv.setTextColor(if (isTarget) Color.parseColor("#39FF14") else Color.parseColor("#00F0FF"))
            tv.setBackgroundResource(R.drawable.bg_word_item)
            val word = tk.clean
            tv.setOnClickListener { onChip(word, tv) }
            flow.addWord(tv)
        }
    }

    /** 点句子里的单词：发音 + 查释义 + 把它切成本轮打字目标（原版就是这个行为） */
    private fun onChip(word: String, tv: TextView) {
        tv.isActivated = true
        val w = Dicts.lookupAny(this, word)
        speaker.sayWord(word, w?.trans)
        if (w != null) {
            refWord = w
            if (prefs.prefetchVoice) speaker.prefetch(w.name)
            tvPhone.text = if (prefs.showPhonetic && w.phone.isNotBlank()) "/" + w.phone.trim('/') + "/" else ""
            tvTrans.text = w.trans
            tvTrans.visibility = View.VISIBLE
            fillTargets(w)
            wi = 0
            buf = ""
            lastInput = ""
            pushInput("")
            redraw()
            updateStats()
            tvHint.text = "正在练：「 ${w.name} 」  ·  打完自动回到句子"
            tvTail.text = w.trans.take(60)
        } else {
            tvHint.text = "「$word」不在当前词库里，只发音"
        }
        if (prefs.loopAudio) startLoop()
    }

    // ---------------------------------------------------------------- AI 造句

    private fun maybeAi(w: W) {
        if (!prefs.aiOn || prefs.aiKey.isBlank()) return
        val token = aiToken
        Ai.generate(prefs.aiKey, prefs.aiSystem, prefs.aiTemplate, w.name, w.trans) { r ->
            if (token != aiToken || r == null) return@generate
            if (r.shortEn.isNotBlank()) {
                shortS = Sent.Pair_(r.shortEn, r.shortZh)
                shortGram = r.shortGram
            }
            if (r.complexEn.isNotBlank()) {
                complexS = Sent.Pair_(r.complexEn, r.complexZh)
                complexGram = r.complexGram
            }
            if (mode != MODE_WORD) {
                fillTargets(w)
                if (wi >= targets.size) { wi = 0; buf = ""; lastInput = ""; pushInput(""); redraw() }
            }
            refreshCards()
        }
    }

    private fun regen(short: Boolean) {
        val w = cur() ?: return
        if (prefs.aiKey.isBlank()) {
            // 没配 AI 就把库里的句子再取一次（换一个词继续也不至于卡住）
            toast("没填 DeepSeek API Key，用的是内置句子库")
            return
        }
        val token = ++aiToken
        tvHint.text = "[ AI 造句中… ]"
        Ai.generate(prefs.aiKey, prefs.aiSystem, prefs.aiTemplate, w.name, w.trans) { r ->
            if (token != aiToken) return@generate
            tvHint.text = if (r == null) "AI 请求失败，用内置句子" else "AI 造句完成"
            if (r != null) {
                if (short && r.shortEn.isNotBlank()) { shortS = Sent.Pair_(r.shortEn, r.shortZh); shortGram = r.shortGram }
                if (!short && r.complexEn.isNotBlank()) { complexS = Sent.Pair_(r.complexEn, r.complexZh); complexGram = r.complexGram }
                if (mode != MODE_WORD) {
                    fillTargets(w); wi = 0; buf = ""; lastInput = ""; pushInput(""); redraw()
                }
                refreshCards()
            }
        }
    }

    // ---------------------------------------------------------------- 播放

    /** 把当前词序排成播放列表：每组 = 英文单词 →（中文）→ 句子 */
    private fun buildSeries(): List<List<String>> {
        val out = ArrayList<List<String>>()
        val total = if (customWords != null) customWords!!.size else order.size
        for (i in 0 until total) {
            val w = wordAt(i) ?: continue
            val g = ArrayList<String>(3)
            g.add(w.name)
            if (prefs.readZh) Speaker.zhSpeech(w.trans).takeIf { it.isNotBlank() }?.let { g.add(it) }
            val sent = sentEnAt(i)
            if (!sent.isNullOrBlank()) g.add(sent)
            out.add(g)
        }
        return out
    }

    private fun wordAt(i: Int): W? {
        customWords?.let { return it.getOrNull(i) }
        val oi = order.getOrNull(i) ?: return null
        return dict.getOrNull(oi)
    }

    private fun sentEnAt(i: Int): String? = when (mode) {
        MODE_SHORT -> wordAt(i)?.let { Sent.short(this, it.name)?.en }
        MODE_COMPLEX -> wordAt(i)?.let { Sent.complex(this, it.name)?.en }
        else -> null
    }

    /** 播放器式自动连播：从当前词开始，一个接一个念下去 */
    private fun startAutoPlay(from: Int = pos) {
        val list = buildSeries()
        if (list.isEmpty()) {
            toast("词库是空的")
            return
        }
        autoPlaying = true
        paintPlayState()
        speaker.playSeries(
            list, from,
            onGroup = { idx ->
                // 播放器翻页：界面跟着走（但不打断播放）
                if (idx != pos && idx in 0 until list.size) {
                    pos = idx
                    if (customWords == null) prefs.setDictProgress(prefs.dictId, pos)
                    showCurrent(silent = true)
                }
                paintPlayState()
            },
            onDone = {
                autoPlaying = false
                paintPlayState()
                toast("全部播完")
            }
        )
        SpeakService.ensure(this)
    }

    private fun stopAutoPlay() {
        autoPlaying = false
        speaker.stop()
        paintPlayState()
    }

    private fun paintPlayState() {
        findViewById<ImageButton>(R.id.btnPlay)?.isSelected = autoPlaying
        findViewById<ImageButton>(R.id.btnPlay)?.contentDescription =
            if (autoPlaying) "停止自动连播" else "播放"
    }

    private fun playAll() {
        if (autoPlaying) {
            stopAutoPlay()
            flashFoot("自动连播已停止")
        } else {
            startAutoPlay()
            flashFoot("自动连播开始 · 退到后台/锁屏也会继续")
        }
    }

    private fun startLoop() {
        if (!prefs.loopAudio) return
        val w = cur() ?: return
        // 单词走有道真人音 → （中文模式）释义 → 句子，交替循环
        speaker.loopPair(w.name, curSentenceText(), w.trans)
    }

    private fun pauseLoopIfTyping() {
        if (!prefs.loopAudio || !prefs.pauseLoopWhileTyping) return
        val t = speaker
        t.stopLoop()
        handler.removeCallbacks(loopResume)
        handler.postDelayed(loopResume, 1600L)
    }

    private val loopResume = Runnable {
        if (!isFinishing && prefs.loopAudio && System.currentTimeMillis() - idleAt > 1200) startLoop()
    }

    // ---------------------------------------------------------------- 界面动作

    private fun toggleZen() {
        zen = !zen
        val vis = if (zen) View.GONE else View.VISIBLE
        tvBrand.visibility = vis
        btnDict.visibility = vis
        findViewById<ImageButton>(R.id.btnStats).visibility = vis
        findViewById<ImageButton>(R.id.btnReview).visibility = vis
        findViewById<ImageButton>(R.id.btnSettings).visibility = vis
        statsBar.visibility = vis
        tabWord.visibility = vis
        tabShort.visibility = vis
        tabComplex.visibility = vis
        findViewById<ImageButton>(R.id.btnPlay).visibility = vis
        findViewById<ImageButton>(R.id.btnLoop).visibility = vis
        findViewById<ImageButton>(R.id.btnZen).visibility = if (zen) View.VISIBLE else View.VISIBLE
        tvFoot.visibility = vis
        tvTail.visibility = vis
        cardShort.visibility = if (zen) View.GONE else cardShort.visibility
        cardComplex.visibility = if (zen) View.GONE else cardComplex.visibility
        tvPhone.visibility = if (zen) View.GONE else View.VISIBLE
        rain.visibility = if (zen) View.GONE else View.VISIBLE
        if (!zen) refreshCards()
        toast(if (zen) "禅定模式：只留打字区" else "退出禅定")
    }

    private fun focusInput() {
        et.requestFocus()
        val im = getSystemService(INPUT_METHOD_SERVICE) as? InputMethodManager
        im?.showSoftInput(et, InputMethodManager.SHOW_IMPLICIT)
    }

    private fun openStats() {
        val i = Intent(this, StatsActivity::class.java)
        i.putExtra(StatsActivity.E_SESSION, intArrayOf(sTyped, sCorrect, sMistakes, sWords, sBest))
        i.putExtra(StatsActivity.E_SECONDS, ((System.currentTimeMillis() - sessStart()) / 1000).toInt())
        i.putExtra(StatsActivity.E_EPOCH, sessT0)
        startActivity(i)
    }

    private fun openReview() {
        val q = prefs.queue()
        if (q.isEmpty()) {
            toast("错词本是空的，先错几个词吧")
            return
        }
        val i = Intent(this, ReviewActivity::class.java)
        i.putExtra(ReviewActivity.EXTRA_WORDS, ArrayList(q))
        i.putExtra(ReviewActivity.EXTRA_MODE, 0)
        startActivityForResult(i, RQ_REVIEW)
        reviewOpen = true
    }
    private fun applyLook() {
        rain.visibility = if (prefs.matrix) View.VISIBLE else View.GONE
        if (prefs.matrix) rain.start() else rain.stop()
        Sfx.enabled = prefs.soundOn
        Vib.enabled = prefs.vibrateOn
        speaker.applyPrefs(prefs)
        paintCase()
        paintLoop()
        redraw()
    }

    // ---------------------------------------------------------------- 生命周期

    override fun onResume() {
        super.onResume()
        reviewOpen = false
        val oldId = prefs.dictId
        if (oldId != lastDictId) {
            lastDictId = oldId
            loadDict(oldId, fresh = true)
        }
        applyLook()
        updateStats()
        if (pendingFocus) {
            pendingFocus = false
            handler.postDelayed({ focusInput() }, 260)
        }
    }

    private var lastDictId = -1

    override fun onPause() {
        super.onPause()
        // 后台播放开着就让它继续念；关掉才在这里停
        if (!prefs.backgroundPlay) speaker.stop()
        saveSession()
        resetSession()
    }

    override fun onDestroy() {
        super.onDestroy()
        // 进程内单例还被后台服务用着，这里不能 shutdown，只摘掉回调
        speaker.stop()
        if (!prefs.backgroundPlay) {
            speaker.shutdown()
            SpeakService.stopService(this)
        }
        Sfx.release()
    }

    @Deprecated("")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        when (requestCode) {
            RQ_DICT -> {
                lastDictId = prefs.dictId
                loadDict(prefs.dictId, fresh = true)
                applyLook()
                showCurrent()
            }
            RQ_REVIEW, RQ_DICTATE -> {
                reviewOpen = false
                val words = data?.getStringArrayListExtra(ReviewActivity.RESULT_WORDS)
                if (!words.isNullOrEmpty()) {
                    val list = ArrayList<W>()
                    for (s in words) list.add(Dicts.lookupAny(this, s) ?: W(s, "", ""))
                    customWords = list
                    blind = true
                    pos = 0
                    showCurrent()
                } else {
                    blind = false
                    advance()
                }
            }
            RQ_SETTINGS -> {
                applyLook()
                buildOrder()
                showCurrent()
            }
        }
    }

    // ----------------------------------------------------------------

    private fun dp(v: Float) = (v * resources.displayMetrics.density + 0.5f).toInt()

    private fun toast(s: String) {
        Toast.makeText(this, s, Toast.LENGTH_SHORT).show()
    }
}
