package com.vocabtype.app.ui

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.util.AttributeSet
import android.view.View
import kotlin.random.Random

/**
 * 背景代码雨。用「头 + 拖尾」直接画，比黑幕叠加省一层 Bitmap，
 * 在中端机上也能跑满帧。
 */
class Rain @JvmOverloads constructor(
    ctx: Context,
    attrs: AttributeSet? = null
) : View(ctx, attrs) {

    private val glyphs = "0123456789ABCDEF<>{}[]/\\|=+*#$%&@ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾅﾆﾇﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾜ".toCharArray()

    private val p = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        typeface = Typeface.MONOSPACE
        textSize = 15f
        textAlign = Paint.Align.LEFT
    }

    private val head = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        typeface = Typeface.MONOSPACE
        textSize = 15f
        color = Color.parseColor("#CCE8FFFC")
    }

    private var cols = 0
    private var colW = 0f
    private var dropY = FloatArray(0)
    private var spd = FloatArray(0)
    private var last = 0L
    private val rnd = Random(20241004)

    private var running = false

    private val tick = object : Runnable {
        override fun run() {
            if (!running) return
            step()
            invalidate()
            postDelayed(this, 46L)
        }
    }

    fun start() {
        if (running) return
        running = true
        postDelayed(tick, 46L)
    }

    fun stop() {
        running = false
        removeCallbacks(tick)
    }

    override fun onSizeChanged(w: Int, h: Int, ow: Int, oh: Int) {
        super.onSizeChanged(w, h, ow, oh)
        cols = (w / (p.textSize * 1.05f)).toInt().coerceAtLeast(1)
        colW = w.toFloat() / cols
        dropY = FloatArray(cols) { rnd.nextFloat() * h * 1.6f - h * 0.6f }
        spd = FloatArray(cols) { 26f + rnd.nextFloat() * 74f }
        last = System.nanoTime()
        invalidate()
    }

    private fun step() {
        val now = System.nanoTime()
        val dt = ((now - last) / 1_000_000_000f).coerceIn(0f, 0.12f)
        last = now
        val h = height.toFloat()
        for (i in 0 until cols) {
            dropY[i] += spd[i] * dt
            if (dropY[i] - 16 * p.textSize > h) {
                dropY[i] = -rnd.nextFloat() * h * 0.5f
                spd[i] = 26f + rnd.nextFloat() * 74f
            }
        }
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (cols == 0) return
        val lh = p.textSize * 1.06f
        for (i in 0 until cols) {
            val x = i * colW + colW * 0.12f
            var y = dropY[i]
            var k = 0
            while (k < 16 && y > -lh) {
                val yy = y - k * lh
                if (yy < height + lh) {
                    val ch = glyphs[((i * 31 + k * 17 + ((yy / lh).toInt())) and 0x7fffffff) % glyphs.size]
                    if (k == 0) {
                        canvas.drawText(ch.toString(), x, yy, head)
                    } else {
                        val a = (170 - k * 10).coerceAtLeast(12)
                        p.color = Color.argb(a, 0, 190, 210)
                        canvas.drawText(ch.toString(), x, yy, p)
                    }
                }
                y -= lh
                k++
            }
        }
    }
}
