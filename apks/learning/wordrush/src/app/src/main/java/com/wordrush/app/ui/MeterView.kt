package com.wordrush.app.ui

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Shader
import android.util.AttributeSet
import android.view.View
import android.view.animation.DecelerateInterpolator

/** 圆角渐变进度条，带补间动画 */
class MeterView @JvmOverloads constructor(
    ctx: Context,
    attrs: AttributeSet? = null
) : View(ctx, attrs) {

    private val trackPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xFF1B2545.toInt() }
    private val fillPaint = Paint(Paint.ANTI_ALIAS_FLAG)

    private val rect = RectF()
    private var shader: LinearGradient? = null
    private var shown = 0f
    private var animator: ValueAnimator? = null

    var colorA = 0xFF35E0FF.toInt()
    var colorB = 0xFFA855F7.toInt()

    /** 0..1，animate=false 时立刻生效 */
    fun setProgress(p: Float, animate: Boolean = true) {
        val v = p.coerceIn(0f, 1f)
        animator?.cancel()
        if (!animate) {
            shown = v
            invalidate()
            return
        }
        animator = ValueAnimator.ofFloat(shown, v).apply {
            duration = 420
            interpolator = DecelerateInterpolator()
            addUpdateListener {
                shown = it.animatedValue as Float
                invalidate()
            }
            start()
        }
    }

    fun setColors(a: Int, b: Int) {
        colorA = a
        colorB = b
        shader = null
        invalidate()
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        shader = null
        rect.set(0f, 0f, w.toFloat(), h.toFloat())
    }

    override fun onDraw(canvas: Canvas) {
        val w = width.toFloat()
        val h = height.toFloat()
        if (w <= 0f || h <= 0f) return
        val r = h / 2f
        canvas.drawRoundRect(RectF(0f, 0f, w, h), r, r, trackPaint)
        if (shown <= 0.001f) return
        val fw = (w * shown).coerceAtLeast(h)
        var sh = shader
        if (sh == null) {
            sh = LinearGradient(0f, 0f, w, 0f, colorA, colorB, Shader.TileMode.CLAMP)
            shader = sh
        }
        fillPaint.shader = sh
        canvas.drawRoundRect(RectF(0f, 0f, fw, h), r, r, fillPaint)
    }
}
