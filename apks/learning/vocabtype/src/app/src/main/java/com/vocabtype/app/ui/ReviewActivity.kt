package com.vocabtype.app.ui

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.vocabtype.app.R
import com.vocabtype.app.core.Insets
import com.vocabtype.app.core.Prefs
import com.vocabtype.app.core.Speaker
import com.vocabtype.app.core.VoiceBox
import com.vocabtype.app.data.Dicts

/**
 * 两种用法：
 *   MODE_PICK   = 0  错词本选词复习（多选）
 *   MODE_DICTATE= 1  整句听写（打完整句后，把句中的词再默写一遍）
 * 都是选中一批词回传给 MainActivity，然后在「默写」状态下逐个敲。
 */
class ReviewActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_WORDS = "words"
        const val EXTRA_SENTENCE = "sentence"
        const val EXTRA_MODE = "mode"
        const val RESULT_WORDS = "picked"

        const val MODE_PICK = 0
        const val MODE_DICTATE = 1
    }

    private lateinit var prefs: Prefs
    private lateinit var speaker: Speaker
    private val picked = LinkedHashSet<String>()
    private lateinit var flow: FlowLayout
    private lateinit var tvHead: TextView
    private lateinit var tvSub: TextView
    private lateinit var btnGo: TextView
    private var mode = MODE_PICK
    private var words: List<String> = emptyList()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_review)
        prefs = Prefs(this)
        Insets.apply(this, findViewById(R.id.root), top = false)
        speaker = VoiceBox.get(this, prefs)

        mode = intent.getIntExtra(EXTRA_MODE, MODE_PICK)
        words = intent.getStringArrayListExtra(EXTRA_WORDS) ?: ArrayList()
        val sentence = intent.getStringExtra(EXTRA_SENTENCE) ?: ""

        flow = findViewById(R.id.flow)
        tvHead = findViewById(R.id.tvHead)
        tvSub = findViewById(R.id.tvSub)
        btnGo = findViewById(R.id.btnGo)

        findViewById<ImageButton>(R.id.btnClose).setOnClickListener { finish() }
        findViewById<TextView>(R.id.btnCancel).setOnClickListener { finish() }

        if (mode == MODE_DICTATE) {
            setupDictate(sentence)
        } else {
            setupPick()
        }
    }

    // ----------------------------------------------------------------

    private fun setupPick() {
        val queue = prefs.queue()
        val mis = prefs.mistakes()
        tvHead.text = "[ 错词本 · ${queue.size} 个 ]"
        tvSub.text = "点一下选中 / 再点取消 · 长按可听发音 · 不选就直接开始 = 全部"

        val bar = findViewById<LinearLayout>(R.id.bar)
        bar.visibility = android.view.View.VISIBLE
        (bar.getChildAt(0) as TextView).setOnClickListener { pickAll(true) }
        (bar.getChildAt(1) as TextView).setOnClickListener { pickAll(false) }
        (bar.getChildAt(2) as TextView).setOnClickListener {
            AlertDialog.Builder(this)
                .setTitle("[ 清空错词本 ]")
                .setMessage("把错词本和复习队列一次性清空？此操作不可撤销。")
                .setPositiveButton("清空") { _, _ ->
                    prefs.clearMistakes()
                    toast("错词本已清空")
                    finish()
                }
                .setNegativeButton("取消", null).show()
        }

        render(queue)
        btnGo.text = "开始复习"
    }

    private fun setupDictate(sentence: String) {
        tvHead.text = "[ 整句听写 ]"
        tvSub.text = if (sentence.isBlank()) "点词听发音，然后逐个默写"
        else "原句：$sentence"
        flow.visibility = android.view.ViewGroup.VISIBLE
        render(words)
        btnGo.text = "开始默写（${words.size} 词）"
        picked.addAll(words.map { it })
        paintAll()
    }

    private fun pickAll(on: Boolean) {
        picked.clear()
        if (on) picked.addAll(words.map { it.lowercase() })
        paintAll()
    }

    private fun render(list: List<String>) {
        flow.removeAllViews()
        val mis = prefs.mistakes()
        for (raw in list) {
            val key = raw.lowercase()
            val w = Dicts.lookupAny(this, key)
            val chip = TextView(this)
            chip.typeface = Typeface.MONOSPACE
            chip.textSize = prefs.fsSent.toFloat()
            chip.setPadding(dp(8), dp(6), dp(8), dp(6))
            chip.background = resources.getDrawable(R.drawable.bg_chip_on, theme)
            val cnt = mis[key] ?: 0
            chip.text = if (mode == MODE_PICK && cnt > 0) "$raw ×$cnt" else raw
            chip.setTextColor(Color.parseColor("#FFE0E6ED"))
            chip.tag = key
            chip.setOnClickListener {
                if (picked.contains(key)) picked.remove(key) else picked.add(key)
                paintAll()
            }
            chip.setOnLongClickListener {
                speaker.say(key)
                if (w != null) toast("${w.name}  ${w.trans.take(40)}")
                true
            }
            flow.addWord(chip)
        }
        paintAll()
    }

    private fun paintAll() {
        for (i in 0 until flow.childCount) {
            val c = flow.getChildAt(i) as TextView
            val on = picked.contains(c.tag as String)
            c.isSelected = on
            c.setTextColor(Color.parseColor(if (on) "#FF39FF14" else "#FFE0E6ED"))
        }
        btnGo.text = when {
            mode == MODE_DICTATE -> "开始默写（${words.size} 词）"
            picked.isEmpty() -> "全部复习（${words.size} 词）"
            else -> "开始复习（${picked.size} 词）"
        }
        (findViewById<android.widget.TextView>(R.id.tvCount)).text =
            "已选 ${picked.size} / ${words.size}"
    }

    private fun go() {
        val out = ArrayList<String>()
        if (picked.isEmpty()) out.addAll(words) else out.addAll(picked)
        if (out.isEmpty()) {
            toast("没有可复习的词")
            return
        }
        setResult(Activity.RESULT_OK, Intent().putStringArrayListExtra(RESULT_WORDS, out))
        finish()
    }

    override fun onCreateOptionsMenu(menu: android.view.Menu?): Boolean = false

    override fun onResume() {
        super.onResume()
        btnGo.setOnClickListener { go() }
    }

    override fun onPause() {
        super.onPause()
        speaker.stop()
    }

    override fun onDestroy() {
        super.onDestroy()
        // 后台服务还在用同一个播放器，这里只停回声，不 shutdown
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density + 0.5f).toInt()
    private fun toast(s: String) = Toast.makeText(this, s, Toast.LENGTH_SHORT).show()
}
