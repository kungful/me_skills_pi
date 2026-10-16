package com.vocabtype.app.ui

import android.content.Context
import android.util.AttributeSet
import android.view.View
import android.view.ViewGroup

/** 会自动换行的横向排列容器，用来把句子拆成一堆可点的词 */
class FlowLayout @JvmOverloads constructor(
    ctx: Context,
    attrs: AttributeSet? = null
) : ViewGroup(ctx, attrs) {

    var hGap = 0
    var vGap = 0

    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        val w = MeasureSpec.getSize(widthMeasureSpec).coerceAtLeast(1)
        var x = 0
        var y = 0
        var lineH = 0
        for (i in 0 until childCount) {
            val c = getChildAt(i)
            if (c.visibility == GONE) continue
            measureChild(c, MeasureSpec.makeMeasureSpec(w, MeasureSpec.AT_MOST),
                MeasureSpec.makeMeasureSpec(0, MeasureSpec.UNSPECIFIED))
            val cw = c.measuredWidth
            val ch = c.measuredHeight
            if (x > 0 && x + cw > w) {
                x = 0
                y += lineH + vGap
                lineH = 0
            }
            x += cw + hGap
            if (ch > lineH) lineH = ch
        }
        val total = y + lineH + paddingTop + paddingBottom
        setMeasuredDimension(w, total)
    }

    override fun onLayout(changed: Boolean, l: Int, t: Int, r: Int, b: Int) {
        val w = (r - l - paddingLeft - paddingRight).coerceAtLeast(1)
        var x = paddingLeft
        var y = paddingTop
        var lineH = 0
        for (i in 0 until childCount) {
            val c = getChildAt(i)
            if (c.visibility == GONE) continue
            val cw = c.measuredWidth
            val ch = c.measuredHeight
            if (x > paddingLeft && x + cw > paddingLeft + w) {
                x = paddingLeft
                y += lineH + vGap
                lineH = 0
            }
            c.layout(x, y, x + cw, y + ch)
            x += cw + hGap
            if (ch > lineH) lineH = ch
        }
    }

    fun addWord(v: View) {
        if (v.layoutParams == null) {
            v.layoutParams = LayoutParams(LayoutParams.WRAP_CONTENT, LayoutParams.WRAP_CONTENT)
        }
        addView(v)
    }
}
