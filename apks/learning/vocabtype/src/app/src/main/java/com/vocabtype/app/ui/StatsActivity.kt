package com.vocabtype.app.ui

import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.vocabtype.app.R
import com.vocabtype.app.core.Insets
import com.vocabtype.app.core.Prefs
import com.vocabtype.app.data.Dicts
import java.util.Locale

class StatsActivity : AppCompatActivity() {

    companion object {
        const val E_SESSION = "sess"
        const val E_SECONDS = "secs"
        const val E_EPOCH = "epoch"
    }

    private lateinit var prefs: Prefs
    private lateinit var box: LinearLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_stats)
        prefs = Prefs(this)
        Insets.apply(this, findViewById(R.id.root), top = false)
        box = findViewById(R.id.box)
        findViewById<ImageButton>(R.id.btnClose).setOnClickListener { finish() }
        build()
    }

    private fun build() {
        box.removeAllViews()

        val sess = intent.getIntArrayExtra(E_SESSION) ?: intArrayOf(0, 0, 0, 0, 0)
        val secs = intent.getIntExtra(E_SECONDS, 0)
        head("SESSION // 本节")
        kv(
            "敲击字符" to "${sess[0]}",
            "正确字符" to "${sess[1]}",
            "错误" to "${sess[2]}",
            "本节正确率" to pct(sess[1], sess[0]),
            "本节速度" to wpm(sess[0], secs),
            "打完单词" to "${sess[3]}",
            "最长连击" to "${sess[4]}",
            "用时" to "%d:%02d".format(secs / 60, secs % 60)
        )

        head("ALL TIME // 累计")
        kv(
            "累计敲击" to "${prefs.totalTyped}",
            "累计正确率" to pct(prefs.totalCorrect, prefs.totalTyped),
            "累计单词" to "${prefs.totalWords}",
            "历史最长连击" to "${prefs.bestStreak}",
            "累计错误" to "${prefs.totalMistakes}",
            "练过的不同单词" to "${prefs.learned}",
            "练习天数" to "${prefs.practiceDays}",
            "会话次数" to "${prefs.sessions}",
            "累计时长" to "%d 时 %d 分".format(prefs.totalSeconds / 3600, (prefs.totalSeconds % 3600) / 60)
        )

        val mis = prefs.mistakes()
        val q = prefs.queue()
        head("MISTAKES // 错词本")
        if (mis.isEmpty()) {
            note("错词本是空的。")
        } else {
            val top = mis.entries.sortedByDescending { it.value }.take(12)
            val sb = StringBuilder()
            for ((k, v) in top) sb.append(k).append(" ×").append(v).append("   ")
            note("共 ${mis.size} 个错词 · 复习队列 ${q.size} 个\n\nTOP: " + sb.toString().trim())
        }

        head("PROGRESS // 词库进度")
        for (m in Dicts.index(this)) {
            val done = prefs.dictProgress(m.id).coerceIn(0, m.count.coerceAtLeast(1))
            val p = if (m.count > 0) done * 100.0 / m.count else 0.0
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(0, dp(7), 0, dp(7))
            }
            val t = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
            t.addView(txt(m.name + if (m.id == prefs.dictId) "  ◀当前" else "", 13f, "#FFE0E6ED"),
                LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            t.addView(txt(String.format(Locale.US, "%.1f%%", p), 12f, "#FF39FF14"))
            row.addView(t)
            row.addView(txt(bar(p), 10f, "#FF00F0FF").apply { setPadding(0, dp(3), 0, 0) })
            row.addView(txt("$done / ${m.count}", 10f, "#FF4A5568").apply { setPadding(0, dp(2), 0, 0) })
            box.addView(row)
        }

        head("DANGER // 危险操作")
        val b1 = btn("清空错词本") {
            AlertDialog.Builder(this).setTitle("[ 清空错词本 ]")
                .setMessage("错词和复习队列都会被清掉。")
                .setPositiveButton("清空") { _, _ -> prefs.clearMistakes(); build(); toast("已清空") }
                .setNegativeButton("取消", null).show()
        }
        val b2 = btn("清空全部数据") {
            AlertDialog.Builder(this).setTitle("[ 清空全部数据 ]")
                .setMessage("所有设置、统计、错词本、打字进度全部归零，且不可恢复。\n确定？")
                .setPositiveButton("全部清空") { _, _ -> prefs.wipeAll(); build(); toast("已全部清空") }
                .setNegativeButton("取消", null).show()
        }
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        row.addView(b1)
        (b2.layoutParams as? LinearLayout.LayoutParams)?.leftMargin = dp(8)
        row.addView(b2, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply { leftMargin = dp(8) })
        box.addView(row)
    }

    // ----------------------------------------------------------------

    private fun head(t: String) {
        val tv = txt("── $t ──────────────", 12f, "#FF00F0FF")
        tv.letterSpacing = 0.08f
        tv.setPadding(0, dp(18), 0, dp(8))
        box.addView(tv)
    }

    private fun note(t: String) {
        val tv = txt(t, 11.5f, "#FF8A9BB2")
        tv.setLineSpacing(0f, 1.35f)
        box.addView(tv)
    }

    private fun kv(vararg pairs: Pair<String, String>) {
        for ((k, v) in pairs) {
            val r = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                setPadding(0, dp(5), 0, dp(5))
            }
            r.addView(txt(k, 12.5f, "#FF8A9BB2"),
                LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            r.addView(txt(v, 13f, "#FF39FF14"))
            box.addView(r)
        }
    }

    private fun btn(t: String, on: () -> Unit): TextView {
        val b = txt(t, 12f, "#FF00F0FF")
        b.background = resources.getDrawable(R.drawable.bg_btn, theme)
        b.setPadding(dp(14), dp(9), dp(14), dp(9))
        b.setOnClickListener { on() }
        return b
    }

    private fun txt(t: String, size: Float, color: String): TextView {
        val v = TextView(this)
        v.text = t
        v.textSize = size
        v.setTextColor(Color.parseColor(color))
        v.typeface = Typeface.MONOSPACE
        v.gravity = Gravity.START
        return v
    }

    private fun bar(pct: Double): String {
        val n = 26
        val on = ((pct / 100.0) * n).toInt().coerceIn(0, n)
        val sb = StringBuilder()
        for (i in 0 until n) sb.append(if (i < on) '█' else '░')
        return sb.toString()
    }

    private fun pct(a: Int, b: Int): String =
        if (b <= 0) "0.00%" else String.format(Locale.US, "%.2f%%", a * 100.0 / b)

    private fun wpm(chars: Int, secs: Int): String {
        if (chars <= 0 || secs <= 0) return "0.00 WPM"
        return String.format(Locale.US, "%.2f WPM", (chars / 5.0) / (secs / 60.0))
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density + 0.5f).toInt()
    private fun toast(s: String) = Toast.makeText(this, s, Toast.LENGTH_SHORT).show()
}
