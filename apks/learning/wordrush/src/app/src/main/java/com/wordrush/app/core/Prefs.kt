package com.wordrush.app.core

import android.content.Context
import java.util.Calendar

/**
 * 全部本地存储，不联网、不要账号。
 * 「天数」用 yyyyDDD 这种自增整数表示，跨年也能正确比较。
 */
class Prefs(ctx: Context) {

    private val sp = ctx.applicationContext.getSharedPreferences("wordrush", Context.MODE_PRIVATE)

    // ---------- 设置 ----------
    var soundOn: Boolean
        get() = sp.getBoolean("sound", true)
        set(v) = sp.edit().putBoolean("sound", v).apply()

    var vibrateOn: Boolean
        get() = sp.getBoolean("vibrate", true)
        set(v) = sp.edit().putBoolean("vibrate", v).apply()

    /** 每日目标词数 */
    var goal: Int
        get() = sp.getInt("goal", 20)
        set(v) = sp.edit().putInt("goal", v.coerceIn(5, 100)).apply()

    // ---------- 成长 ----------
    var xp: Int
        get() = sp.getInt("xp", 0)
        set(v) = sp.edit().putInt("xp", v.coerceAtLeast(0)).apply()

    var coins: Int
        get() = sp.getInt("coins", 0)
        set(v) = sp.edit().putInt("coins", v.coerceAtLeast(0)).apply()

    var streak: Int
        get() = sp.getInt("streak", 0)
        set(v) = sp.edit().putInt("streak", v).apply()

    var bestStreak: Int
        get() = sp.getInt("best_streak", 0)
        set(v) = sp.edit().putInt("best_streak", v).apply()

    var lastPlayDay: Long
        get() = sp.getLong("last_day", 0L)
        set(v) = sp.edit().putLong("last_day", v).apply()

    // ---------- 今日 ----------
    var todayDay: Long
        get() = sp.getLong("today_day", 0L)
        set(v) = sp.edit().putLong("today_day", v).apply()

    var todayWords: Int
        get() = sp.getInt("today_words", 0)
        set(v) = sp.edit().putInt("today_words", v).apply()

    var todayXp: Int
        get() = sp.getInt("today_xp", 0)
        set(v) = sp.edit().putInt("today_xp", v).apply()

    var todayCorrect: Int
        get() = sp.getInt("today_ok", 0)
        set(v) = sp.edit().putInt("today_ok", v).apply()

    var todayTotal: Int
        get() = sp.getInt("today_all", 0)
        set(v) = sp.edit().putInt("today_all", v).apply()

    // ---------- 累计 ----------
    var lifeCorrect: Int
        get() = sp.getInt("life_ok", 0)
        set(v) = sp.edit().putInt("life_ok", v).apply()

    var lifeTotal: Int
        get() = sp.getInt("life_all", 0)
        set(v) = sp.edit().putInt("life_all", v).apply()

    var lifeXp: Int
        get() = sp.getInt("life_xp", 0)
        set(v) = sp.edit().putInt("life_xp", v).apply()

    var playDays: Int
        get() = sp.getInt("play_days", 0)
        set(v) = sp.edit().putInt("play_days", v).apply()

    // ---------- 词库进度 ----------
    fun curBank(): Int = sp.getInt("bank", 0)

    fun setBank(b: Int) = sp.edit().putInt("bank", b).apply()

    /** 已通关的关卡数（关卡按顺序解锁） */
    fun done(bank: Int): Int = sp.getInt("done_$bank", 0)

    fun setDone(bank: Int, n: Int) = sp.edit().putInt("done_$bank", n).apply()

    /** 每关星数，逗号分隔，index = 关卡序号 */
    fun stars(bank: Int): IntArray {
        val s = sp.getString("stars_$bank", "") ?: ""
        if (s.isEmpty()) return IntArray(0)
        return s.split(',').map { it.toIntOrNull() ?: 0 }.toIntArray()
    }

    fun setStar(bank: Int, level: Int, star: Int) {
        val cur = stars(bank).toMutableList()
        while (cur.size <= level) cur.add(0)
        if (star > cur[level]) cur[level] = star
        sp.edit().putString("stars_$bank", cur.joinToString(",")).apply()
    }

    fun starSum(bank: Int): Int = stars(bank).sum()

    /** 今日挑战是否已经开始（用于防止刷「今日」） */
    fun rolloverIfNeeded() {
        val t = Day.today()
        if (todayDay != t) {
            todayDay = t
            todayWords = 0
            todayXp = 0
            todayCorrect = 0
            todayTotal = 0
            // 连续天数：昨天玩过就 +1，否则重置
            if (lastPlayDay != t) {
                if (lastPlayDay == Day.yesterday()) {
                    streak += 1
                } else if (lastPlayDay != 0L) {
                    streak = 1
                } else {
                    streak = 1
                }
            }
            lastPlayDay = t
            playDays += 1
            bestStreak = maxOf(bestStreak, streak)
        }
    }

    /** 今日答过一题 */
    fun addAnswer(correct: Boolean, xpGain: Int) {
        todayTotal += 1
        lifeTotal += 1
        if (correct) {
            todayCorrect += 1
            lifeCorrect += 1
        }
        todayXp += xpGain
        lifeXp += xpGain
    }

    fun wipeAll() = sp.edit().clear().apply()

    companion object {
        const val BANK_L1 = 0
        const val BANK_L2 = 1
    }
}

/** 日期与等级曲线 */
object Day {
    fun num(c: Calendar): Long = c.get(Calendar.YEAR) * 1000L + c.get(Calendar.DAY_OF_YEAR)

    fun today(): Long = num(Calendar.getInstance())

    fun yesterday(): Long {
        val c = Calendar.getInstance()
        c.add(Calendar.DAY_OF_YEAR, -1)
        return num(c)
    }
}

object Level {
    /** 达到 lv 级所需的累计经验 */
    fun xpFor(lv: Int): Int = 200 * (lv - 1) * (lv - 1)

    fun of(xp: Int): Int {
        var lv = 1
        while (lv < 200 && xp >= xpFor(lv + 1)) lv++
        return lv
    }

    /** 当前等级内的进度 0..1 */
    fun progress(xp: Int): Float {
        val lv = of(xp)
        val a = xpFor(lv)
        val b = xpFor(lv + 1)
        if (b <= a) return 1f
        return ((xp - a).toFloat() / (b - a)).coerceIn(0f, 1f)
    }

    fun xpToNext(xp: Int): Int = maxOf(0, xpFor(of(xp) + 1) - xp)
}
