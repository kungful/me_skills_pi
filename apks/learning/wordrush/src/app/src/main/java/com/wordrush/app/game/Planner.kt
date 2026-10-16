package com.wordrush.app.game

import android.content.Context
import com.wordrush.app.core.Day
import com.wordrush.app.core.Prefs
import com.wordrush.app.data.Bank
import com.wordrush.app.data.ProgressStore
import com.wordrush.app.data.Word

/** 今日挑战的配比：复习为主、每天掺一部分新词 */
class Plan(val review: List<Word>, val fresh: List<Word>) {
    val all: List<Word> get() = review + fresh
    val size get() = review.size + fresh.size
}

object Planner {

    fun today(ctx: Context, prefs: Prefs, store: ProgressStore): Plan {
        val bank = prefs.curBank()
        val today = Day.today()

        // 目标不是硬上限：已经学够就补一点，保证「开始挑战」永远有内容
        val base = prefs.goal.coerceIn(5, 100)
        val done = prefs.todayWords
        val target = if (done >= base) 12 else (base - done).coerceAtLeast(12 - done).coerceAtLeast(6)

        val due = store.dueWords(ctx, bank, today, 400)
        val reviewTake = minOf(due.size, (target * 3) / 4)
        val freshTake = target - reviewTake

        val all = Bank.words(ctx, bank)
        val frontier = store.frontier(ctx, bank)
        val fresh = if (frontier >= all.size) emptyList()
        else all.subList(frontier, minOf(all.size, frontier + freshTake)).toList()

        return Plan(due.take(reviewTake), fresh)
    }

    fun dueCount(ctx: Context, prefs: Prefs, store: ProgressStore): Int =
        store.dueWords(ctx, prefs.curBank(), Day.today(), 9999).size
}
