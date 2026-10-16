package com.wordrush.app.ui

import android.annotation.SuppressLint
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.wordrush.app.R
import com.wordrush.app.core.Day
import com.wordrush.app.core.Edge
import com.wordrush.app.core.Level
import com.wordrush.app.core.Prefs
import com.wordrush.app.data.Bank
import com.wordrush.app.data.ProgressStore
import com.wordrush.app.data.Srs

class StatsActivity : AppCompatActivity() {

    private lateinit var prefs: Prefs
    private lateinit var store: ProgressStore

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_stats)
        Edge.install(this, findViewById(R.id.root))
        prefs = Prefs(this)
        store = ProgressStore(this)

        findViewById<View>(R.id.btnBack).setOnClickListener { finish() }
        findViewById<View>(R.id.btnReset).setOnClickListener { confirmReset() }
        fill()
    }

    override fun onPause() {
        super.onPause()
        store.saveIfDirty()
    }

    private fun confirmReset() {
        AlertDialog.Builder(this)
            .setTitle("清空全部学习数据？")
            .setMessage("等级、金币、打卡、单词记忆进度都会删除，且无法恢复。")
            .setPositiveButton("确定清空") { _, _ ->
                store.map.clear()
                store.save()
                prefs.wipeAll()
                fill()
            }
            .setNegativeButton("取消", null)
            .show()
    }

    @SuppressLint("SetTextI18n")
    private fun fill() {
        prefs.rolloverIfNeeded()
        val bank = prefs.curBank()
        val c = store.counts()

        findViewById<TextView>(R.id.tvLvLine).text = "等级 Lv.${Level.of(prefs.xp)}"
        findViewById<MeterView>(R.id.meterXp).setProgress(Level.progress(prefs.xp), true)
        findViewById<TextView>(R.id.tvXpLine).text =
            "${prefs.xp} XP · 距 Lv.${Level.of(prefs.xp) + 1} 还需 ${Level.xpToNext(prefs.xp)} XP"

        val grid = findViewById<LinearLayout>(R.id.grid)
        grid.removeAllViews()

        val totalWords = Bank.words(this, 0).size + Bank.words(this, 1).size
        val learned = store.map.size
        val acc = if (prefs.lifeTotal == 0) 0 else prefs.lifeCorrect * 100 / prefs.lifeTotal

        addRow(grid, listOf(
            "已掌握" to "${c[1]}",
            "学习中" to "${c[0]}"
        ))
        addRow(grid, listOf(
            "累计答题" to "${prefs.lifeTotal}",
            "正确率" to "$acc%"
        ))
        addRow(grid, listOf(
            "已接触单词" to "$learned",
            "总词库" to "$totalWords"
        ))
        addRow(grid, listOf(
            "连续打卡" to "${prefs.streak} 天",
            "最长记录" to "${prefs.bestStreak} 天"
        ))
        addRow(grid, listOf(
            "学习天数" to "${prefs.playDays} 天",
            "金币" to "${prefs.coins}"
        ))

        val box = findViewById<LinearLayout>(R.id.bankBox)
        box.removeAllViews()
        for (info in Bank.INFO) {
            val total = Bank.levelCount(this, info.id)
            val done = prefs.done(info.id)
            val stars = prefs.starSum(info.id)
            val words = Bank.words(this, info.id).size
            var mastered = 0
            var learning = 0
            for (w in Bank.words(this, info.id)) {
                val r = store.map[w.id] ?: continue
                if (r.mastered) mastered++ else if (r.correct + r.wrong > 0) learning++
            }
            val card = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setBackgroundResource(R.drawable.card)
                setPadding(dp(16), dp(14), dp(16), dp(14))
            }
            card.addView(text("${info.name} · ${info.sub}", 15f, 0xFFEAF0FF.toInt(), true))
            card.addView(text("单词 $words · 关卡 $done/$total · 星星 $stars/${total * 3}", 12f, 0xFF8494BD.toInt(), false))
            card.addView(text("已掌握 $mastered · 学习中 $learning", 13f, 0xFFB6C2E0.toInt(), false))
            val lp = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
            )
            lp.bottomMargin = dp(10)
            box.addView(card, lp)
        }

        val due = store.dueWords(this, bank, Day.today(), 9999).size
        box.addView(text("今天有 $due 个单词到期需要复习", 12f, 0xFF8494BD.toInt(), false))
    }

    private fun addRow(parent: LinearLayout, cells: List<Pair<String, String>>) {
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        for ((label, value) in cells) {
            val cell = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                gravity = Gravity.CENTER
                setBackgroundResource(R.drawable.card_soft)
                setPadding(dp(10), dp(14), dp(10), dp(14))
            }
            val v = text(value, 20f, 0xFFEAF0FF.toInt(), true)
            val l = text(label, 11f, 0xFF8494BD.toInt(), false)
            cell.addView(v)
            cell.addView(l)
            val lp = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
            lp.marginStart = dp(4)
            lp.marginEnd = dp(4)
            row.addView(cell, lp)
        }
        val rlp = LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
        )
        rlp.topMargin = dp(8)
        parent.addView(row, rlp)
    }

    private fun text(s: String, size: Float, color: Int, bold: Boolean): TextView {
        val tv = TextView(this)
        tv.text = s
        tv.textSize = size
        tv.setTextColor(color)
        if (bold) {
            tv.setTypeface(tv.typeface, android.graphics.Typeface.BOLD)
        }
        val lp = LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT
        )
        lp.topMargin = dp(3)
        tv.layoutParams = lp
        return tv
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density + 0.5f).toInt()
}
