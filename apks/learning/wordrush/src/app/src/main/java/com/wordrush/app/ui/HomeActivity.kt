package com.wordrush.app.ui

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.wordrush.app.R
import com.wordrush.app.core.Edge
import com.wordrush.app.core.Level
import com.wordrush.app.core.Prefs
import com.wordrush.app.data.Achievements
import com.wordrush.app.data.Bank
import com.wordrush.app.data.Ctx
import com.wordrush.app.data.ProgressStore
import com.wordrush.app.fx.Sfx
import com.wordrush.app.fx.Vib
import com.wordrush.app.game.Planner

class HomeActivity : AppCompatActivity() {

    private lateinit var prefs: Prefs
    private lateinit var store: ProgressStore

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_home)
        Edge.install(this, findViewById(R.id.root))

        prefs = Prefs(this)
        store = ProgressStore(this)
        Sfx.enabled = prefs.soundOn
        Vib.enabled = prefs.vibrateOn

        findViewById<View>(R.id.btnStart).setOnClickListener {
            tap()
            startActivity(
                Intent(this, PlayActivity::class.java)
                    .putExtra(PlayActivity.EXTRA_MODE, PlayActivity.MODE_DAILY)
            )
        }
        findViewById<View>(R.id.cardMap).setOnClickListener {
            tap(); startActivity(Intent(this, MapActivity::class.java))
        }
        findViewById<View>(R.id.cardBank).setOnClickListener {
            tap(); startActivity(Intent(this, BankActivity::class.java))
        }
        findViewById<View>(R.id.cardWrong).setOnClickListener {
            tap(); startActivity(Intent(this, WrongActivity::class.java))
        }
        findViewById<View>(R.id.cardAchieve).setOnClickListener {
            tap(); startActivity(Intent(this, AchieveActivity::class.java))
        }
        findViewById<View>(R.id.cardStats).setOnClickListener {
            tap(); startActivity(Intent(this, StatsActivity::class.java))
        }

        findViewById<View>(R.id.btnSound).setOnClickListener {
            prefs.soundOn = !prefs.soundOn
            Sfx.enabled = prefs.soundOn
            if (prefs.soundOn) Sfx.play(Sfx.TAP)
            refresh()
        }
        findViewById<View>(R.id.btnVib).setOnClickListener {
            prefs.vibrateOn = !prefs.vibrateOn
            Vib.enabled = prefs.vibrateOn
            if (prefs.vibrateOn) Vib.tap(this)
            refresh()
        }
        findViewById<View>(R.id.btnGoal).setOnClickListener { pickGoal() }
    }

    override fun onResume() {
        super.onResume()
        prefs.rolloverIfNeeded()
        Sfx.enabled = prefs.soundOn
        Vib.enabled = prefs.vibrateOn
        refresh()
    }

    override fun onPause() {
        super.onPause()
        store.saveIfDirty()
    }

    override fun onDestroy() {
        super.onDestroy()
        if (isFinishing) store.saveIfDirty()
    }

    private fun tap() {
        Sfx.play(Sfx.TAP)
        Vib.tap(this)
    }

    private fun pickGoal() {
        val opts = intArrayOf(10, 20, 30, 50)
        val labels = opts.map { "$it 词 / 天" }.toTypedArray()
        val cur = opts.indexOf(prefs.goal).coerceAtLeast(0)
        AlertDialog.Builder(this)
            .setTitle("每日目标")
            .setSingleChoiceItems(labels, cur) { d, which ->
                prefs.goal = opts[which]
                d.dismiss()
                refresh()
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun refresh() {
        val bank = prefs.curBank()
        val p = Planner.today(this, prefs, store)

        findViewById<TextView>(R.id.tvLv).text = Level.of(prefs.xp).toString()
        findViewById<com.wordrush.app.ui.MeterView>(R.id.meterXp)
            .setProgress(Level.progress(prefs.xp), false)
        findViewById<TextView>(R.id.tvXpLeft).text = "${prefs.xp} XP"
        findViewById<TextView>(R.id.tvXpRight).text = "还需 ${Level.xpToNext(prefs.xp)}"
        findViewById<TextView>(R.id.tvCoins).text = prefs.coins.toString()

        findViewById<TextView>(R.id.tvStreak).text = "${prefs.streak} 天"
        val goal = prefs.goal
        findViewById<TextView>(R.id.tvTodayCount).text = "${prefs.todayWords} / $goal"

        findViewById<com.wordrush.app.ui.MeterView>(R.id.meterToday).setColors(
            0xFF06121F.toInt(), 0xFF3B5A78.toInt()
        )
        findViewById<com.wordrush.app.ui.MeterView>(R.id.meterToday)
            .setProgress(prefs.todayWords.toFloat() / goal, true)

        val finished = prefs.todayWords >= goal
        findViewById<TextView>(R.id.tvTodaySub).text =
            if (p.size == 0) "这个词库已经学完啦，去练错题本吧"
            else "复习 ${p.review.size} 词 · 新词 ${p.fresh.size} 词" + if (finished) "（今日目标已达成，继续加分）" else ""
        findViewById<TextView>(R.id.tvStartLabel).text = if (finished) "继续加练" else "开始挑战"

        val levels = Bank.levelCount(this, bank)
        findViewById<TextView>(R.id.tvMapSub).text = "$levels 关 · ${prefs.done(bank)} 关已通"
        findViewById<TextView>(R.id.tvBankSub).text = Bank.info(bank).name
        findViewById<TextView>(R.id.tvWrongSub).text = "${store.wrongWords(this).size} 个待攻克"
        findViewById<TextView>(R.id.tvAchieveSub).text =
            "${Achievements.unlockedCount(Ctx(prefs, store, this))} / ${Achievements.ALL.size}"

        val c = store.counts()
        findViewById<TextView>(R.id.tvMastered).text = c[1].toString()
        findViewById<TextView>(R.id.tvLearning).text = c[0].toString()
        findViewById<TextView>(R.id.tvAccuracy).text =
            if (prefs.lifeTotal == 0) "--"
            else "${prefs.lifeCorrect * 100 / prefs.lifeTotal}%"

        findViewById<TextView>(R.id.btnSound).text = if (prefs.soundOn) "音效 开" else "音效 关"
        findViewById<TextView>(R.id.btnVib).text = if (prefs.vibrateOn) "震动 开" else "震动 关"
        findViewById<TextView>(R.id.btnGoal).text = "目标 ${prefs.goal}"
    }
}
