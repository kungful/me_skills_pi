package com.guantianxia.app.core

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import android.text.TextUtils
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 生成朋友圈分享卡片（1080×1350，4:5，朋友圈最合适的比例）。
 *
 * 为什么需要它：微信朋友圈不接受第三方预填文字，
 * 直接分享链接只会得到一条光秃秃的网址，所以把标题画进图片里。
 */
object ShareCard {

    private const val W = 1080
    private const val H = 1350

    private const val BRAND = "#1F6FEB"
    private const val INK = "#111111"
    private const val GRAY = "#6B7280"
    private const val LINE = "#E9EDF2"

    fun render(title: String, summary: String, source: String, url: String): Bitmap {
        val bmp = Bitmap.createBitmap(W, H, Bitmap.Config.ARGB_8888)
        val c = Canvas(bmp)
        c.drawColor(Color.WHITE)

        val brand = Color.parseColor(BRAND)
        val pad = 76f

        // 顶部品牌条
        c.drawRect(0f, 0f, W.toFloat(), 16f, Paint().apply { color = brand })

        var y = 168f

        // 来源标签
        if (source.isNotBlank()) {
            c.drawText(
                source,
                pad,
                y,
                Paint(Paint.ANTI_ALIAS_FLAG).apply {
                    color = brand
                    textSize = 36f
                    isFakeBoldText = true
                }
            )
        }
        y += 62f

        // 标题
        val titlePaint = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.parseColor(INK)
            textSize = 66f
            isFakeBoldText = true
        }
        y = block(c, title, titlePaint, pad, y, W - pad * 2, 8, 16f)

        // 摘要
        if (summary.isNotBlank()) {
            y += 46f
            val sumPaint = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
                color = Color.parseColor(GRAY)
                textSize = 40f
            }
            y = block(c, summary, sumPaint, pad, y, W - pad * 2, 5, 14f)
        }

        // 分隔线
        val lineY = H - 208f
        c.drawRect(pad, lineY, W - pad, lineY + 2f, Paint().apply { color = Color.parseColor(LINE) })

        // 底部：品牌 + 日期
        c.drawText(
            "观天下",
            pad,
            H - 118f,
            Paint(Paint.ANTI_ALIAS_FLAG).apply {
                color = brand
                textSize = 44f
                isFakeBoldText = true
            }
        )
        val date = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.CHINA).format(Date())
        val datePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.parseColor(GRAY)
            textSize = 34f
            textAlign = Paint.Align.RIGHT
        }
        c.drawText(date, W - pad, H - 118f, datePaint)

        // 网址（长文被转发后还能找到原文）
        if (url.isNotBlank()) {
            val urlPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                color = Color.parseColor("#9AA4B2")
                textSize = 30f
            }
            c.drawText(TextUtils.ellipsize(url, TextPaint(urlPaint), W - pad * 2, TextUtils.TruncateAt.MIDDLE).toString(), pad, H - 62f, urlPaint)
        }

        return bmp
    }

    /** 画一段自动换行的文字，返回结束时的 y 坐标 */
    private fun block(
        c: Canvas,
        text: String,
        paint: TextPaint,
        x: Float,
        y: Float,
        width: Float,
        maxLines: Int,
        extra: Float
    ): Float {
        val layout = StaticLayout.Builder
            .obtain(text, 0, text.length, paint, width.toInt())
            .setAlignment(Layout.Alignment.ALIGN_NORMAL)
            .setLineSpacing(extra, 1f)
            .setMaxLines(maxLines)
            .setEllipsize(TextUtils.TruncateAt.END)
            .setIncludePad(false)
            .build()
        c.save()
        c.translate(x, y)
        layout.draw(c)
        c.restore()
        return y + layout.height
    }
}
