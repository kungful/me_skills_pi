package com.wordrush.app.ui

import android.animation.ObjectAnimator
import android.annotation.SuppressLint
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.wordrush.app.R
import com.wordrush.app.core.Day
import com.wordrush.app.core.Edge
import com.wordrush.app.core.Level
import com.wordrush.app.core.Prefs
import com.wordrush.app.core.Speaker
import com.wordrush.app.data.Bank
import com.wordrush.app.data.ProgressStore
import com.wordrush.app.data.Srs
import com.wordrush.app.data.Word
import com.wordrush.app.fx.Sfx
import com.wordrush.app.fx.Vib
import com.wordrush.app.game.ChoiceQ
import com.wordrush.app.game.M_EN2ZH
import com.wordrush.app.game.M_LISTEN
import com.wordrush.app.game.M_MATCH
import com.wordrush.app.game.M_SPELL
import com.wordrush.app.game.M_ZH2EN
import com.wordrush.app.game.MatchQ
import com.wordrush.app.game.Planner
import com.wordrush.app.game.Q
import com.wordrush.app.game.QuizMaker
import com.wordrush.app.game.SpellQ
import kotlin.math.abs
import kotlin.random.Random

class PlayActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_MODE = "mode"
        const val EXTRA_BANK = "bank"
        const val EXTRA_LEVEL = "level"

        const val MODE_DAILY = 0
        const val MODE_LEVEL = 1
        const val MODE_WRONG = 2
        const val MODE_CUSTOM = 3

        const val EXTRA_IDS = "ids"
    }

    private lateinit var prefs: Prefs
    private lateinit var store: ProgressStore
    private lateinit var speaker: Speaker

    private var mode = MODE_DAILY
    private var bank = 0
    private var level = 0

    private var qs: List<Q> = emptyList()
    private var idx = 0
    private val maxHearts = 3
    private var hearts = maxHearts
    private var combo = 0
    private var maxCombo = 0
    private var score = 0
    private var correct = 0
    private var answered = 0
    private var xpGain = 0
    private var coinGain = 0
    private val freshIds = HashSet<Int>()
    private var startAt = 0L
    private var busy = false
    private var finished = false
    private var waitingTts = false

    private val handler = Handler(Looper.getMainLooper())
    private val rnd = Random(System.currentTimeMillis())

    private lateinit var vMeterQ: MeterView
    private lateinit var vPos: TextView
    private lateinit var vHearts: LinearLayout
    private lateinit var vCombo: TextView
    private lateinit var vScore: TextView
    private lateinit var vKind: TextView
    private lateinit var vAudio: ImageView
    private lateinit var vQ: TextView
    private lateinit var vIpa: TextView
    private lateinit var vTip: TextView
    private lateinit var vOptions: LinearLayout
    private lateinit var vSpellArea: LinearLayout
    private lateinit var vSlots: LinearLayout
    private lateinit var vKeypad: LinearLayout
    private lateinit var vBtnHint: TextView
    private lateinit var vMatchArea: LinearLayout
    private lateinit var vColLeft: LinearLayout
    private lateinit var vColRight: LinearLayout
    private lateinit var vFooter: TextView
    private lateinit var vCorrectCard: LinearLayout
    private lateinit var vCcWord: TextView
    private lateinit var vCcMean: TextView
    private lateinit var vResult: View
    private lateinit var vRoot: View

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_play)
        vRoot = findViewById(R.id.root)
        Edge.install(this, vRoot)

        prefs = Prefs(this)
        store = ProgressStore(this)
        speaker = Speaker(this)
        Sfx.enabled = prefs.soundOn
        Vib.enabled = prefs.vibrateOn

        mode = intent.getIntExtra(EXTRA_MODE, MODE_DAILY)
        bank = intent.getIntExtra(EXTRA_BANK, prefs.curBank())
        level = intent.getIntExtra(EXTRA_LEVEL, 0)

        bindViews()
        prefs.rolloverIfNeeded()

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (finished) {
                    finish()
                    return
                }
                AlertDialog.Builder(this@PlayActivity)
                    .setTitle("要放弃这一轮吗？")
                    .setMessage("本轮的答题记录不会保存")
                    .setPositiveButton("放弃") { _, _ -> finish() }
                    .setNegativeButton("继续答题", null)
                    .show()
            }
        })

        startRound()
    }

    private fun bindViews() {
        vMeterQ = findViewById(R.id.meterQ)
        vPos = findViewById(R.id.tvPos)
        vHearts = findViewById(R.id.hearts)
        vCombo = findViewById(R.id.tvCombo)
        vScore = findViewById(R.id.tvScore)
        vKind = findViewById(R.id.tvKind)
        vAudio = findViewById(R.id.btnAudio)
        vQ = findViewById(R.id.tvQ)
        vIpa = findViewById(R.id.tvIpa)
        vTip = findViewById(R.id.tvTip)
        vOptions = findViewById(R.id.options)
        vSpellArea = findViewById(R.id.spellArea)
        vSlots = findViewById(R.id.slots)
        vKeypad = findViewById(R.id.keypad)
        vBtnHint = findViewById(R.id.btnHint)
        vMatchArea = findViewById(R.id.matchArea)
        vColLeft = findViewById(R.id.colLeft)
        vColRight = findViewById(R.id.colRight)
        vFooter = findViewById(R.id.tvFooter)
        vCorrectCard = findViewById(R.id.correctCard)
        vCcWord = findViewById(R.id.ccWord)
        vCcMean = findViewById(R.id.ccMean)
        vResult = findViewById(R.id.resultLayer)

        findViewById<View>(R.id.btnClose).setOnClickListener { onBackPressedDispatcher.onBackPressed() }
        findViewById<View>(R.id.ccAudio).setOnClickListener { say(vCcWord.tag as? String ?: "") }
        vAudio.setOnClickListener { if (vQ.tag is String) say(vQ.tag as String) }
        vBtnHint.setOnClickListener { useHint() }
        findViewById<View>(R.id.btnAgain).setOnClickListener { startRound() }
        findViewById<View>(R.id.btnBack).setOnClickListener { finish() }

        buildHearts()
        buildKeypad()
    }

    // =========================== 回合 ===========================

    private fun startRound() {
        handler.removeCallbacksAndMessages(null)
        vResult.visibility = View.GONE
        vCorrectCard.visibility = View.GONE
        idx = 0
        hearts = maxHearts
        combo = 0
        maxCombo = 0
        score = 0
        correct = 0
        answered = 0
        xpGain = 0
        coinGain = 0
        busy = false
        finished = false
        freshIds.clear()
        startAt = System.currentTimeMillis()

        // TTS 是异步初始化的：还没问出结果就先等它一下，
        // 否则第一轮永远不会出听力题。
        if (!speaker.resolved && !waitingTts) {
            waitingTts = true
            speaker.onReady = { handler.post { if (waitingTts) { waitingTts = false; begin() } } }
            handler.postDelayed({ if (waitingTts) { waitingTts = false; begin() } }, 700)
            return
        }
        waitingTts = false
        begin()
    }

    private fun begin() {
        val all = Bank.words(this, bank)
        val seed: List<Word> = when (mode) {
            MODE_LEVEL -> Bank.levelWords(this, bank, level)
            MODE_WRONG -> store.wrongWords(this).take(20)
            MODE_CUSTOM -> {
                val ids = intent.getIntArrayExtra(EXTRA_IDS)
                if (ids != null && ids.isNotEmpty()) {
                    val out = ArrayList<Word>(ids.size)
                    for (id in ids) {
                        val i = id - bank * 100000
                        if (i in all.indices) out.add(all[i])
                    }
                    out
                } else {
                    all.filter { store.rec(it.id)?.mastered != true }.take(20)
                }
            }
            else -> Planner.today(this, prefs, store).all
        }

        if (seed.isEmpty()) {
            AlertDialog.Builder(this)
                .setMessage("这个词库暂时没有可练的单词，去关卡地图看看吧。")
                .setPositiveButton("知道了") { _, _ -> finish() }
                .setCancelable(false)
                .show()
            return
        }

        // 记下哪些是首次出现的新词
        for (w in seed) if (!store.has(w.id)) freshIds.add(w.id)

        qs = QuizMaker.build(seed, all, speaker.available, rnd)
        updateHearts()
        draw()
    }

    private fun draw() {
        if (idx >= qs.size) {
            endRound()
            return
        }
        val q = qs[idx]
        busy = false
        hideCorrection()
        vMeterQ.setProgress(idx.toFloat() / qs.size, true)
        vPos.text = "${idx + 1}/${qs.size}"
        vScore.text = score.toString()
        vCombo.visibility = if (combo >= 2) View.VISIBLE else View.GONE
        vCombo.text = "连击 x$combo"

        vOptions.removeAllViews()
        vSpellArea.visibility = View.GONE
        vMatchArea.visibility = View.GONE
        vOptions.visibility = View.VISIBLE
        vFooter.visibility = View.GONE
        vQ.textSize = 34f
        vIpa.visibility = View.VISIBLE
        vAudio.visibility = View.GONE
        vQ.tag = null

        when (q) {
            is ChoiceQ -> drawChoice(q)
            is SpellQ -> drawSpell(q)
            is MatchQ -> drawMatch(q)
        }
    }

    // =========================== 选择题 ===========================

    @SuppressLint("SetTextI18n")
    private fun drawChoice(q: ChoiceQ) {
        val w = q.primary
        vQ.tag = w.en
        when (q.mode) {
            M_EN2ZH -> {
                vKind.text = "选择正确的中文释义"
                vQ.text = w.en
                vQ.textSize = 34f
                vIpa.text = w.ipa
                vTip.text = if (w.ipa.isEmpty()) "" else "点单词可听发音"
            }
            M_ZH2EN -> {
                vKind.text = "选出对应的英文单词"
                vQ.text = w.mean
                vQ.textSize = if (w.mean.length > 14) 24f else 30f
                vIpa.text = ""
                vIpa.visibility = View.GONE
                vTip.text = ""
            }
            M_LISTEN -> {
                vKind.text = "听发音，选出你听到的单词"
                vQ.text = "？"
                vQ.textSize = 34f
                vIpa.text = ""
                vIpa.visibility = View.GONE
                vAudio.visibility = View.VISIBLE
                vTip.text = "没听清可以再点一次"
                handler.postDelayed({ say(w.en) }, 320)
            }
        }
        vTip.visibility = if (vTip.text.isNullOrEmpty()) View.GONE else View.VISIBLE

        val inflater = LayoutInflater.from(this)
        val keys = listOf("A", "B", "C", "D")
        for (i in q.opts.indices) {
            val row = inflater.inflate(R.layout.view_option, vOptions, false)
            row.findViewById<TextView>(R.id.tvKey).text = keys.getOrElse(i) { "?" }
            row.findViewById<TextView>(R.id.tvOpt).text = q.opts[i]
            row.setOnClickListener { onChoice(row, q, i) }
            vOptions.addView(row)
        }
    }

    private fun onChoice(row: View, q: ChoiceQ, picked: Int) {
        if (busy || finished) return
        busy = true
        val ok = picked == q.ans
        val mark = row.findViewById<ImageView>(R.id.ivMark)
        val rows = (0 until vOptions.childCount).map { vOptions.getChildAt(it) }

        for (i in rows.indices) {
            rows[i].isClickable = false
            if (i == q.ans) {
                rows[i].setBackgroundResource(R.drawable.opt_right)
                if (i != picked) {
                    val m = rows[i].findViewById<ImageView>(R.id.ivMark)
                    m.setImageResource(R.drawable.ic_check)
                    m.visibility = View.VISIBLE
                }
            } else if (i == picked) {
                rows[i].setBackgroundResource(R.drawable.opt_wrong)
            } else {
                rows[i].setBackgroundResource(R.drawable.opt_dim)
            }
        }
        if (ok) {
            mark.setImageResource(R.drawable.ic_check)
            mark.visibility = View.VISIBLE
        }

        resolve(ok, q.primary)
        val delay = if (ok) 620L else 1500L
        handler.postDelayed({
            if (ok) advance() else loseAndContinue()
        }, delay)
    }

    // =========================== 拼写题 ===========================

    private var spellTarget = ""
    private var spellTyped = ""

    @SuppressLint("SetTextI18n")
    private fun drawSpell(q: SpellQ) {
        val w = q.word
        vKind.text = "根据释义拼出这个单词"
        vQ.text = w.mean
        vQ.textSize = if (w.mean.length > 14) 24f else 30f
        vQ.tag = w.en
        vIpa.text = w.ipa
        vIpa.visibility = if (w.ipa.isEmpty()) View.GONE else View.VISIBLE
        vTip.text = "${w.en.length} 个字母"
        vTip.visibility = View.VISIBLE

        vOptions.removeAllViews()
        vOptions.visibility = View.GONE
        vSpellArea.visibility = View.VISIBLE
        vBtnHint.visibility = View.VISIBLE
        vBtnHint.text = "提示首个字母 (-5 分)"

        spellTarget = w.en
        spellTyped = ""
        renderSlots()
    }

    private fun renderSlots(state: Int = 0) {
        vSlots.removeAllViews()
        val size = if (spellTarget.length > 12) 36 else 42
        for (i in spellTarget.indices) {
            val tv = TextView(this)
            tv.text = if (i < spellTyped.length) spellTyped[i].uppercase() else ""
            tv.gravity = Gravity.CENTER
            tv.textSize = 19f
            tv.setTextColor(
                when (state) {
                    1 -> 0xFF34D399.toInt()
                    2 -> 0xFFFB5B5B.toInt()
                    else -> 0xFFEAF0FF.toInt()
                }
            )
            tv.setBackgroundResource(R.drawable.slot)
            val lp = LinearLayout.LayoutParams(dp(size), dp(size + 4))
            lp.marginStart = dp(2)
            lp.marginEnd = dp(2)
            vSlots.addView(tv, lp)
        }
    }

    private fun buildKeypad() {
        val rows = listOf("ABCDEFG", "HIJKLMN", "OPQRSTU", "VWXYZ")
        for ((ri, row) in rows.withIndex()) {
            val rl = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
            for (ch in row) {
                rl.addView(makeKey(ch.toString()) { typeChar(ch) })
            }
            if (ri == rows.lastIndex) {
                rl.addView(makeKey("\u232B") { backspace() })
                rl.addView(makeKey("\u2713") { checkSpell(true) })
            }
            val lp = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
            lp.topMargin = dp(6)
            vKeypad.addView(rl, lp)
        }
    }

    private fun makeKey(label: String, action: () -> Unit): TextView {
        val tv = TextView(this)
        tv.text = label
        tv.gravity = Gravity.CENTER
        tv.textSize = 16f
        tv.setTextColor(0xFFEAF0FF.toInt())
        tv.setBackgroundResource(R.drawable.key)
        tv.isClickable = true
        tv.isFocusable = true
        tv.setOnClickListener {
            Sfx.play(Sfx.TAP)
            Vib.tap(this)
            action()
        }
        val lp = LinearLayout.LayoutParams(0, dp(46), 1f)
        lp.marginStart = dp(3)
        lp.marginEnd = dp(3)
        tv.layoutParams = lp
        return tv
    }

    private fun typeChar(ch: Char) {
        if (busy || finished) return
        if (spellTyped.length >= spellTarget.length) return
        spellTyped += ch.lowercaseChar()
        renderSlots()
        if (spellTyped.length == spellTarget.length) checkSpell(false)
    }

    private fun backspace() {
        if (busy || finished) return
        if (spellTyped.isNotEmpty()) {
            spellTyped = spellTyped.substring(0, spellTyped.length - 1)
            renderSlots()
        }
    }

    private fun useHint() {
        if (busy || finished) return
        if (spellTyped.isEmpty()) {
            spellTarget.firstOrNull()?.let {
                spellTyped += it
                score = maxOf(0, score - 5)
                vScore.text = score.toString()
                renderSlots()
                if (spellTyped.length == spellTarget.length) checkSpell(false)
            }
        } else {
            vBtnHint.text = "提示已用"
        }
    }

    private fun checkSpell(manual: Boolean) {
        if (busy || finished) return
        if (spellTyped.isEmpty()) return
        busy = true
        val w = qs[idx].primary
        val ok = spellTyped.equals(spellTarget, ignoreCase = true)
        renderSlots(if (ok) 1 else 2)
        if (!ok) {
            ObjectAnimator.ofFloat(vSlots, "translationX", 0f, -14f, 14f, -9f, 9f, 0f)
                .apply { duration = 380 }
                .start()
        }
        vBtnHint.visibility = View.GONE
        resolve(ok, w)
        handler.postDelayed({
            if (ok) advance() else loseAndContinue()
        }, if (ok) 620L else 1600L)
    }

    // =========================== 配对题 ===========================

    private var matchErrors = HashMap<Int, Int>()
    private var selEnWord: Word? = null
    private var selEnView: View? = null
    private var matchDone = 0

    @SuppressLint("SetTextI18n")
    private fun drawMatch(q: MatchQ) {
        vKind.text = "把英文和中文配对"
        vQ.text = "\uD83D\uDD17"
        vQ.textSize = 34f
        vIpa.visibility = View.GONE
        vTip.text = "先点英文，再点中文（点错不扣命，但连击会断）"
        vTip.visibility = View.VISIBLE

        vOptions.removeAllViews()
        vOptions.visibility = View.GONE
        vSpellArea.visibility = View.GONE
        vMatchArea.visibility = View.VISIBLE
        vColLeft.removeAllViews()
        vColRight.removeAllViews()

        matchErrors.clear()
        selEnWord = null
        selEnView = null
        matchDone = 0

        val inflater = LayoutInflater.from(this)
        val ens = q.words.shuffled(rnd)
        val zhs = q.words.shuffled(rnd)

        for (w in ens) {
            val chip = inflater.inflate(R.layout.view_chip, vColLeft, false)
            chip.findViewById<TextView>(R.id.tvChip).text = w.en
            chip.findViewById<TextView>(R.id.tvChip).textSize = 17f
            chip.setOnClickListener { pickEn(chip, w) }
            chip.tag = w
            vColLeft.addView(chip)
        }
        for (w in zhs) {
            val chip = inflater.inflate(R.layout.view_chip, vColRight, false)
            chip.findViewById<TextView>(R.id.tvChip).text = w.shortMean
            chip.findViewById<TextView>(R.id.tvChip).textSize = 14f
            chip.setOnClickListener { pickZh(chip, w) }
            chip.tag = w
            vColRight.addView(chip)
        }
    }

    private fun pickEn(chip: View, w: Word) {
        if (busy || finished || chip.alpha < 1f) return
        selEnView?.setBackgroundResource(R.drawable.opt_normal)
        selEnWord = w
        selEnView = chip
        chip.setBackgroundResource(R.drawable.opt_sel)
        Sfx.play(Sfx.TAP)
        Vib.tap(this)
    }

    private fun pickZh(chip: View, w: Word) {
        if (busy || finished || chip.alpha < 1f) return
        val enW = selEnWord ?: run {
            Sfx.play(Sfx.TAP)
            return
        }
        val enView = selEnView
        selEnWord = null
        selEnView = null
        enView?.setBackgroundResource(R.drawable.opt_normal)

        if (enW.id == w.id) {
            Sfx.play(Sfx.RIGHT)
            Vib.tap(this)
            enView?.setBackgroundResource(R.drawable.opt_right)
            chip.setBackgroundResource(R.drawable.opt_right)
            fadeOut(enView)
            fadeOut(chip)
            combo++
            maxCombo = maxOf(maxCombo, combo)
            correct++
            answered++
            score += 10
            awardXp(4)
            vScore.text = score.toString()
            matchDone++
            store.recOrNew(w.id)
            Srs.grade(store.recOrNew(w.id), true, Day.today())
            store.markDirty()
            prefs.addAnswer(true, 4)
            handler.postDelayed({
                if (matchDone >= 4) {
                    val anyErr = matchErrors.values.any { it > 0 }
                    if (!anyErr) {
                        vCombo.visibility = View.VISIBLE
                        vCombo.text = "完美配对"
                        Sfx.playCombo(6)
                        score += 20
                        vScore.text = score.toString()
                        awardXp(10)
                    }
                    handler.postDelayed({ advance() }, 520)
                }
            }, 260)
        } else {
            matchErrors[enW.id] = (matchErrors[enW.id] ?: 0) + 1
            matchErrors[w.id] = (matchErrors[w.id] ?: 0) + 1
            combo = 0
            vCombo.visibility = View.GONE
            Sfx.play(Sfx.WRONG)
            Vib.wrong(this)
            enView?.setBackgroundResource(R.drawable.opt_wrong)
            chip.setBackgroundResource(R.drawable.opt_wrong)
            handler.postDelayed({
                enView?.setBackgroundResource(R.drawable.opt_normal)
                chip.setBackgroundResource(R.drawable.opt_normal)
            }, 460)
        }
        if (combo >= 2) {
            vCombo.visibility = View.VISIBLE
            vCombo.text = "连击 x$combo"
        }
    }

    private fun fadeOut(v: View?) {
        v ?: return
        v.animate().alpha(0.32f).setDuration(240).start()
        v.isClickable = false
    }

    // =========================== 判分 ===========================

    private fun awardXp(n: Int) {
        xpGain += n
        coinGain += 1
    }

    private fun resolve(ok: Boolean, w: Word) {
        answered++
        if (ok) {
            correct++
            combo++
            maxCombo = maxOf(maxCombo, combo)
            val bonus = minOf(combo, 10) * 2
            val base = if (qs[idx] is SpellQ) 16 else 10
            score += base + bonus
            vScore.text = score.toString()
            if (combo >= 2) {
                vCombo.visibility = View.VISIBLE
                vCombo.text = "连击 x$combo"
            }
            Sfx.playCombo(combo)
            Vib.right(this)
            floatText("+${base + bonus}", 0xFF35E0FF.toInt())
            if (combo == 5 || combo == 10 || combo == 15) floatText("连击 x$combo!", 0xFFFFC93C.toInt())
            awardXp(5 + minOf(combo, 5))
        } else {
            combo = 0
            vCombo.visibility = View.GONE
            Sfx.play(Sfx.WRONG)
            Vib.wrong(this)
            floatText("MISS", 0xFFFB5B5B.toInt())
            showCorrection(w)
        }
        val r = store.recOrNew(w.id)
        Srs.grade(r, ok, Day.today())
        store.markDirty()
        prefs.addAnswer(ok, if (ok) 5 + minOf(combo, 5) else 0)
    }

    /** 答错：掉一颗心，浮出纠错卡 */
    private fun loseAndContinue() {
        hearts--
        updateHearts()
        if (hearts <= 0) {
            endRound()
        } else {
            hideCorrection()
            advance()
        }
    }

    private fun showCorrection(w: Word) {
        vCcWord.text = w.en
        vCcWord.tag = w.en
        vCcMean.text = (if (w.ipa.isEmpty()) "" else "/${w.ipa}/  ") + w.zh
        vCorrectCard.visibility = View.VISIBLE
        vCorrectCard.alpha = 0f
        vCorrectCard.translationY = dp(40).toFloat()
        vCorrectCard.animate().alpha(1f).translationY(0f).setDuration(220).start()
        say(w.en)
    }

    private fun hideCorrection() {
        vCorrectCard.visibility = View.GONE
    }

    private fun advance() {
        idx++
        if (idx >= qs.size) endRound() else draw()
    }

    private fun updateHearts() {
        for (i in 0 until vHearts.childCount) {
            val iv = vHearts.getChildAt(i) as ImageView
            iv.setImageResource(if (i < hearts) R.drawable.ic_heart else R.drawable.ic_heart_empty)
            iv.alpha = if (i < hearts) 1f else 0.55f
        }
    }

    private fun buildHearts() {
        vHearts.removeAllViews()
        for (i in 0 until maxHearts) {
            val iv = ImageView(this)
            iv.setImageResource(R.drawable.ic_heart)
            val lp = LinearLayout.LayoutParams(dp(22), dp(22))
            lp.marginEnd = dp(5)
            vHearts.addView(iv, lp)
        }
        updateHearts()
    }

    private fun floatText(text: String, color: Int) {
        val tv = TextView(this)
        tv.text = text
        tv.textSize = 20f
        tv.setTypeface(tv.typeface, android.graphics.Typeface.BOLD)
        tv.setTextColor(color)
        val lp = android.widget.FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT
        )
        lp.gravity = Gravity.CENTER_HORIZONTAL or Gravity.CENTER_VERTICAL
        lp.topMargin = dp(40)
        (vRoot as ViewGroup).addView(tv, lp)
        tv.animate()
            .translationY(-dp(110).toFloat())
            .alpha(0f)
            .setDuration(760)
            .withEndAction { (vRoot as ViewGroup).removeView(tv) }
            .start()
    }

    private fun say(text: String) {
        if (text.isNotEmpty()) speaker.say(text)
    }

    // =========================== 结算 ===========================

    @SuppressLint("SetTextI18n")
    private fun endRound() {
        if (finished) return
        finished = true
        handler.removeCallbacksAndMessages(null)
        hideCorrection()

        val win = hearts > 0
        val acc = if (answered == 0) 0f else correct.toFloat() / answered
        val secs = ((System.currentTimeMillis() - startAt) / 1000L).coerceAtLeast(1L)

        val stars = when {
            !win -> 0
            acc >= 0.99f -> 3
            acc >= 0.85f -> 2
            acc >= 0.6f -> 1
            else -> 1
        }

        if (win) {
            xpGain += 25
            coinGain += 10
        } else {
            coinGain += correct / 3
        }

        // 今日任务计数：新词按首次学习算
        var newWords = 0
        for (id in freshIds) {
            val r = store.rec(id)
            if (r != null && r.correct > 0) newWords++
        }
        prefs.todayWords += newWords
        if (prefs.todayWords > 0) prefs.lastPlayDay = Day.today()

        prefs.xp += xpGain
        prefs.coins += coinGain
        if (mode == MODE_LEVEL && win) {
            prefs.setStar(bank, level, stars)
            if (level + 1 > prefs.done(bank)) prefs.setDone(bank, level + 1)
        }
        store.save()

        vMeterQ.setProgress(1f, true)
        vResult.visibility = View.VISIBLE

        findViewById<TextView>(R.id.resTitle).text = when {
            !win -> "挑战失败"
            stars == 3 -> "完美通关！"
            else -> "通关！"
        }
        findViewById<TextView>(R.id.resSub).text = when {
            !win -> "生命值用完了，再来一次吧"
            mode == MODE_LEVEL -> "第 ${level + 1} 关已完成"
            else -> "今天又前进了一步"
        }
        findViewById<TextView>(R.id.resAcc).text = "${(acc * 100).toInt()}%  ($correct/$answered)"
        findViewById<TextView>(R.id.resCombo).text = "x$maxCombo"
        findViewById<TextView>(R.id.resTime).text = fmtTime(secs)
        findViewById<TextView>(R.id.resXp).text = "+$xpGain"
        findViewById<TextView>(R.id.resCoin).text = "+$coinGain"
        val lvNow = Level.of(prefs.xp)
        findViewById<TextView>(R.id.resNew).text =
            "新学 $newWords 词 · 等级 Lv.$lvNow · 距下一级还需 ${Level.xpToNext(prefs.xp)} XP"

        buildStars(stars)
        if (win) {
            Sfx.play(Sfx.WIN)
            Vib.pattern(this, longArrayOf(0, 30, 60, 30, 60, 90))
        } else {
            Sfx.play(Sfx.FAIL)
        }
    }

    private fun fmtTime(sec: Long): String =
        if (sec < 60) "${sec} 秒" else "${sec / 60} 分 ${sec % 60} 秒"

    private fun buildStars(n: Int) {
        val row = findViewById<LinearLayout>(R.id.starRow)
        row.removeAllViews()
        for (i in 0 until 3) {
            val iv = ImageView(this)
            iv.setImageResource(if (i < n) R.drawable.ic_star else R.drawable.ic_star_empty)
            val lp = LinearLayout.LayoutParams(dp(52), dp(52))
            lp.marginStart = dp(6)
            lp.marginEnd = dp(6)
            row.addView(iv, lp)
            iv.scaleX = 0f
            iv.scaleY = 0f
            iv.animate().scaleX(1f).scaleY(1f)
                .setStartDelay(160L + i * 190L)
                .setDuration(320)
                .start()
            if (i < n) {
                handler.postDelayed({ Sfx.play(Sfx.COMBO) }, 160L + i * 190L)
            }
        }
    }

    override fun onPause() {
        super.onPause()
        speaker.stop()
        store.saveIfDirty()
    }

    override fun onDestroy() {
        super.onDestroy()
        handler.removeCallbacksAndMessages(null)
        speaker.shutdown()
        store.saveIfDirty()
    }

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density + 0.5f).toInt()
}
