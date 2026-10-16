package com.vocabtype.app.ui

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.util.AttributeSet
import android.view.View
import android.view.animation.AnimationUtils
import android.view.animation.TranslateAnimation
import kotlin.math.max

/**
 * 打字主显示区。
 *
 * 逐字符上色，就是原版 HTML span 那套逻辑搬到 Canvas 上：
 *   未输入 = 灰  输入正确 = 绿  输入错误 = 红  已打完的词 = 暗绿  多打的字符 = 紫
 */
class TypeView @JvmOverloads constructor(
    ctx: Context,
    attrs: AttributeSet? = null
) : View(ctx, attrs) {

    companion object {
        const val ST_UN = 0
        const val ST_OK = 1
        const val ST_BAD = 2
        const val ST_DONE = 3
        const val ST_EXTRA = 4

        private const val C_OK = "#39FF14"
        private const val C_BAD = "#FF003C"
        private const val C_UN = "#3E4C5E"
        private const val C_DONE = "#2A6E4A"
        private const val C_EX = "#B388FF"
    }

    private class Cell(val ch: Char, val st: Int)

    private val p = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        typeface = Typeface.MONOSPACE
        textAlign = Paint.Align.LEFT
        isSubpixelText = true
        textSize = 46f * resources.displayMetrics.scaledDensity
        shadowColorVal = Color.parseColor("#FF39FF14")
        setShadowLayer(9f * resources.displayMetrics.scaledDensity, 0f, 0f, shadowColorVal)
    }

    /** Paint 只有 setShadowLayer，没有 setShadowRadius，所以自己存一份颜色 */
    private var shadowColorVal = Color.BLACK

    var upper = true
        set(v) { field = v; relayout() }

    private var words: List<String> = emptyList()
    private var buf = ""
    private var active = 0

    private var lines: List<List<Cell>> = emptyList()
    private var caretLine = -1
    private var caretCell = -1
    private var lineH = 0f
    private var charW = 0f

    private var caretOn = true

    private val blinker = object : Runnable {
        override fun run() {
            caretOn = !caretOn
            invalidate()
            postDelayed(this, 520L)
        }
    }

    private var popAt = 0L

    init {
        postDelayed(blinker, 520L)
    }

    private fun dp(v: Float) = v * resources.displayMetrics.density

    fun setTypeSize(px: Float) {
        p.textSize = px
        p.setShadowLayer(dp(9f), 0f, 0f, shadowColorVal)
        relayout()
    }

    fun typeSize(): Float = p.textSize

    fun setContent(wordList: List<String>, buffer: String, activeIdx: Int) {
        words = wordList
        buf = buffer
        active = activeIdx
        relayout()
    }

    fun flashError() {
        val a = TranslateAnimation(-dp(7f), dp(7f), 0f, 0f)
        a.duration = 95
        startAnimation(a)
    }

    fun flashDone() {
        popAt = AnimationUtils.currentAnimationTimeMillis()
        invalidate()
    }

    private fun relayout() {
        charW = p.measureText("M")
        lineH = p.textSize * 1.40f
        rebuild()
        requestLayout()
        invalidate()
    }

    // ------------------------------------------------------------------

    private fun rebuild() {
        val out = ArrayList<List<Cell>>()
        caretLine = -1
        caretCell = -1
        if (words.isEmpty() || width <= 0) {
            lines = out
            return
        }
        val avail = (width - paddingLeft - paddingRight).toFloat()
        var line = ArrayList<Cell>()
        var w = 0f

        for (i in words.indices) {
            val raw = words[i]
            val cells = ArrayList<Cell>(raw.length + 8)
            var caretInThisWord = -1
            when {
                i < active -> for (c in raw) cells.add(Cell(c, ST_DONE))
                i > active -> for (c in raw) cells.add(Cell(c, ST_UN))
                else -> {
                    for (ci in raw.indices) {
                        val st = when {
                            ci >= buf.length -> ST_UN
                            buf[ci].lowercaseChar() == raw[ci].lowercaseChar() -> ST_OK
                            else -> ST_BAD
                        }
                        cells.add(Cell(raw[ci], st))
                    }
                    for (ci in raw.length until buf.length) cells.add(Cell(buf[ci], ST_EXTRA))
                    caretInThisWord = buf.length.coerceAtMost(cells.size)
                }
            }

            val wWidth = cells.size * charW
            if (line.isNotEmpty() && w + charW + wWidth > avail) {
                out.add(line)
                line = ArrayList()
                w = 0f
            }
            if (line.isNotEmpty()) {
                line.add(Cell(' ', ST_UN))
                w += charW
            }
            if (caretInThisWord >= 0) {
                caretLine = out.size
                caretCell = line.size + caretInThisWord
            }
            line.addAll(cells)
            w += wWidth
        }
        if (line.isNotEmpty()) out.add(line)
        if (caretLine > out.size - 1) caretLine = out.size - 1
        lines = out
    }

    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        val w = MeasureSpec.getSize(widthMeasureSpec)
        super.onMeasure(widthMeasureSpec, heightMeasureSpec)
        if (w != width) {
            charW = p.measureText("M")
            lineH = p.textSize * 1.40f
        }
        if (lines.isEmpty() && words.isNotEmpty()) rebuild()
        val h = max((lineH * lines.size.coerceAtLeast(1)).toInt() + paddingTop + paddingBottom,
            (lineH * 1.6f).toInt())
        setMeasuredDimension(w, h)
    }

    override fun onSizeChanged(w: Int, h: Int, ow: Int, oh: Int) {
        super.onSizeChanged(w, h, ow, oh)
        charW = p.measureText("M")
        lineH = p.textSize * 1.40f
        rebuild()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (lines.isEmpty()) {
            p.shadowLayer(0f)
            p.color = Color.parseColor(C_UN)
            p.textAlign = Paint.Align.CENTER
            canvas.drawText(_empty, width / 2f, height / 2f + p.textSize / 3f, p)
            p.textAlign = Paint.Align.LEFT
            p.shadowLayer(dp(9f))
            return
        }

        val now = AnimationUtils.currentAnimationTimeMillis()
        val pop = if (popAt > 0) ((now - popAt) / 260f).coerceIn(0f, 1f) else 1f
        val scale = if (pop < 1f) 1f + (1f - pop) * 0.06f else 1f
        val avail = (width - paddingLeft - paddingRight).toFloat()
        val base0 = paddingTop + p.textSize * 1.06f

        for (li in lines.indices) {
            val line = lines[li]
            var x = paddingLeft + (avail - line.size * charW) / 2f
            val base = base0 + li * lineH
            for (c in line) {
                when (c.st) {
                    ST_OK -> { p.color = Color.parseColor(C_OK); p.shadowLayer(dp(10f), "#8039FF14") }
                    ST_BAD -> { p.color = Color.parseColor(C_BAD); p.shadowLayer(dp(10f), "#80FF003C") }
                    ST_DONE -> { p.color = Color.parseColor(C_DONE); p.shadowLayer(0f) }
                    ST_EXTRA -> { p.color = Color.parseColor(C_EX); p.shadowLayer(dp(6f), "#40B388FF") }
                    else -> { p.color = Color.parseColor(C_UN); p.shadowLayer(0f) }
                }
                val ch = if (upper) c.ch.uppercaseChar() else c.ch
                if (scale != 1f) {
                    canvas.save()
                    canvas.scale(scale, scale, x + charW / 2f, base)
                    canvas.drawText(ch.toString(), x, base, p)
                    canvas.restore()
                } else {
                    canvas.drawText(ch.toString(), x, base, p)
                }
                x += charW
            }

            if (li == caretLine && caretOn) {
                val cx = paddingLeft + (avail - line.size * charW) / 2f + caretCell * charW
                p.color = Color.parseColor(C_OK)
                p.shadowLayer(dp(10f), "#8039FF14")
                canvas.drawRect(
                    cx, base - p.textSize * 0.94f,
                    cx + charW * 0.88f, base + p.textSize * 0.10f, p
                )
            }
        }
    }

    private fun Paint.shadowLayer(r: Float, color: String? = null) {
        val c = if (color != null) Color.parseColor(color) else shadowColorVal
        setShadowLayer(r, 0f, 0f, c)
    }

    private var _empty = "[ 请选择词库 ]"

    fun setEmptyText(s: String) {
        _empty = s
        invalidate()
    }
}
