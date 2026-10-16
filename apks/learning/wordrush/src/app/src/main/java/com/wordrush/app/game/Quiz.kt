package com.wordrush.app.game

import com.wordrush.app.data.Word
import kotlin.math.abs
import kotlin.random.Random

const val M_EN2ZH = 0
const val M_ZH2EN = 1
const val M_LISTEN = 2
const val M_SPELL = 3
const val M_MATCH = 4

val SPELLABLE = Regex("^[A-Za-z]{2,}$")

sealed class Q {
    abstract val words: List<Word>
    val primary: Word get() = words[0]
}

/** 选择题：mode 决定题面与选项语言 */
class ChoiceQ(
    override val words: List<Word>,
    val mode: Int,
    val opts: List<String>,
    val ans: Int
) : Q()

/** 拼写题 */
class SpellQ(override val words: List<Word>) : Q() {
    val word: Word get() = words[0]
}

/** 连连看：4 组英中配对 */
class MatchQ(override val words: List<Word>) : Q()

object QuizMaker {

    fun build(seed: List<Word>, pool: List<Word>, listenOk: Boolean, rnd: Random): List<Q> {
        val qs = ArrayList<Q>(seed.size + 8)
        var i = 0
        var n = 0
        while (i < seed.size) {
            val remain = seed.size - i
            // 每 7 题左右插一轮配对，节奏上有变化
            if (n > 0 && n % 7 == 0 && remain >= 4 && rnd.nextFloat() < 0.8f) {
                val group = seed.subList(i, i + 4).toMutableList()
                group.shuffle(rnd)
                qs.add(MatchQ(group))
                i += 4
            } else {
                qs.add(one(seed[i], pool, listenOk, n, rnd))
                i += 1
            }
            n++
        }
        return qs
    }

    private fun one(w: Word, pool: List<Word>, listenOk: Boolean, n: Int, rnd: Random): Q {
        var mode = when ((n + rnd.nextInt(3)) % 5) {
            0 -> M_EN2ZH
            1 -> if (listenOk) M_LISTEN else M_EN2ZH
            2 -> M_ZH2EN
            3 -> M_SPELL
            else -> M_EN2ZH
        }
        if (mode == M_SPELL && !SPELLABLE.matches(w.en)) mode = M_EN2ZH

        if (mode == M_SPELL) return SpellQ(listOf(w))

        val distract = distractors(w, pool, rnd, 3)
        if (distract.size < 3) {
            return if (SPELLABLE.matches(w.en)) SpellQ(listOf(w))
            else ChoiceQ(listOf(w), M_EN2ZH, listOf(w.zh), 0)
        }

        val answerText = if (mode == M_EN2ZH) w.zh else w.en
        val texts = ArrayList<String>(4)
        texts.add(answerText)
        for (d in distract) texts.add(if (mode == M_EN2ZH) d.zh else d.en)
        shuffleKeepingAnswer(texts, answerText, rnd)
        return ChoiceQ(listOf(w), mode, texts, texts.indexOf(answerText))
    }

    /** 洗牌并保证答案不在第一项（否则位置会形成规律） */
    private fun shuffleKeepingAnswer(list: MutableList<String>, answer: String, rnd: Random) {
        for (i in list.size - 1 downTo 1) {
            val j = rnd.nextInt(i + 1)
            val t = list[i]; list[i] = list[j]; list[j] = t
        }
        // 保证答案不在第一个（不然太容易形成规律）
        if (list[0] == answer && list.size > 1) {
            val t = list[0]; list[0] = list[1]; list[1] = t
        }
    }

    /**
     * 干扰项：优先挑长度接近的，读起来更难区分。
     * 只随机采样一部分词，2843 个词也不会每题全扫。
     */
    private fun distractors(w: Word, pool: List<Word>, rnd: Random, count: Int): List<Word> {
        val near = ArrayList<Word>()
        val far = ArrayList<Word>()
        repeat(240) {
            val c = pool[rnd.nextInt(pool.size)]
            if (c.id == w.id) return@repeat
            if (c.zh == w.zh || c.en.equals(w.en, true)) return@repeat
            if (abs(c.en.length - w.en.length) <= 3) near.add(c) else far.add(c)
        }
        val out = ArrayList<Word>(count)
        val used = HashSet<String>()
        used.add(w.zh)
        used.add(w.en)
        fun take(c: Word): Boolean {
            if (c.id == w.id) return false
            if (used.contains(c.zh) || used.contains(c.en)) return false
            used.add(c.zh)
            used.add(c.en)
            out.add(c)
            return true
        }
        for (list in listOf(near, far)) {
            for (c in list) {
                if (out.size >= count) break
                take(c)
            }
            if (out.size >= count) break
        }
        // 兜底：采样不够就从词表顺序补
        if (out.size < count) {
            for (c in pool) {
                if (out.size >= count) break
                take(c)
            }
        }
        return out
    }
}
