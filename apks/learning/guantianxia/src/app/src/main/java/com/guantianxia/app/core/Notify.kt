package com.guantianxia.app.core

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.guantianxia.app.R
import com.guantianxia.app.data.Article
import com.guantianxia.app.ui.ArticleActivity

/**
 * 重大新闻通知。多条合并成一条 InboxStyle，避免刷屏。
 */
object Notify {

    const val CHANNEL_IMPORTANT = "gtx_important"
    private const val ID_IMPORTANT = 1001

    /** 后台常驻通知（前台服务用） */
    const val CHANNEL_BG = "gtx_bg"
    const val ID_BG = 1002

    fun ensureChannels(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = context.getSystemService(NotificationManager::class.java) ?: return

        if (nm.getNotificationChannel(CHANNEL_BG) == null) {
            nm.createNotificationChannel(
                NotificationChannel(
                    CHANNEL_BG,
                    "后台运行",
                    NotificationManager.IMPORTANCE_MIN
                ).apply {
                    description = "常驻通知：显示下次刷新时间，并保持后台抓取能力"
                    setShowBadge(false)
                }
            )
        }

        val channel = NotificationChannel(
            CHANNEL_IMPORTANT,
            "重大新闻",
            NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = "时政、宏观、资本市场的重要事件"
            enableLights(true)
            enableVibration(true)
            setShowBadge(true)
        }
        nm.createNotificationChannel(channel)
    }

    fun canPost(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return true
        return ContextCompat.checkSelfPermission(
            context, Manifest.permission.POST_NOTIFICATIONS
        ) == PackageManager.PERMISSION_GRANTED
    }

    /** @param items 按重要度从高到低 */
    fun important(context: Context, items: List<Article>) {
        if (items.isEmpty() || !canPost(context)) return
        ensureChannels(context)

        val top = items.first()
        val tapIntent = ArticleActivity.intent(context, top.title, top.url).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        }
        val pi = PendingIntent.getActivity(
            context,
            1,
            tapIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val style = NotificationCompat.InboxStyle()
        items.take(5).forEach { style.addLine(clip(it.title, 60)) }
        if (items.size > 5) style.setSummaryText("等 ${items.size} 条")

        val builder = NotificationCompat.Builder(context, CHANNEL_IMPORTANT)
            .setSmallIcon(R.drawable.ic_notify)
            .setContentTitle(if (items.size == 1) "重大新闻" else "重大新闻 · ${items.size} 条")
            .setContentText(clip(top.title, 80))
            .setStyle(style)
            .setAutoCancel(true)
            .setContentIntent(pi)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory("news")
            // 锁屏 / 息屏时也把内容显示出来（否则只会提示「1 条新消息」）
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setShowWhen(true)
            .setWhen(System.currentTimeMillis())
            .setGroup("gtx-important")

        runCatching {
            NotificationManagerCompat.from(context).notify(ID_IMPORTANT, builder.build())
        }
    }

    fun clear(context: Context) {
        runCatching { NotificationManagerCompat.from(context).cancel(ID_IMPORTANT) }
    }

    private fun clip(s: String, n: Int) = if (s.length <= n) s else s.take(n - 1) + "…"
}
