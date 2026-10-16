package org.opensource.lifealgo.reminder

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import org.opensource.lifealgo.LifeAlgoApp
import org.opensource.lifealgo.MainActivity
import org.opensource.lifealgo.R
import org.opensource.lifealgo.data.DailyEngine

object Notifications {

    const val CHANNEL_DAILY = "daily_brief"
    const val ID_DAILY = 1001

    fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val mgr = context.getSystemService(NotificationManager::class.java) ?: return
        if (mgr.getNotificationChannel(CHANNEL_DAILY) != null) return
        val channel = NotificationChannel(
            CHANNEL_DAILY,
            "每日指南",
            NotificationManager.IMPORTANCE_DEFAULT,
        ).apply {
            description = "每天一条穿搭 + 营养 + 睡眠 + 训练，点开看原理"
            enableVibration(true)
        }
        mgr.createNotificationChannel(channel)
    }

    /** 用当日推送内容发一条通知。接收器在后台调用，所以自己算一遍内容。 */
    fun postDaily(context: Context) {
        val app = LifeAlgoApp.from(context)
        val settings = app.settings
        val enabled = settings.reminderCategories
            .split(',')
            .map { it.trim() }
            .filter { it.isNotEmpty() }
            .toSet()

        val plan = DailyEngine.plan(
            now = System.currentTimeMillis(),
            categories = app.content.categories,
            articles = app.content.articles,
            enabledCategoryIds = enabled,
        )
        val (title, body) = DailyEngine.notificationText(plan)

        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val flags = PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        val pi = PendingIntent.getActivity(context, 0, intent, flags)

        val builder = NotificationCompat.Builder(context, CHANNEL_DAILY)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setAutoCancel(true)
            .setContentIntent(pi)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)

        if (plan.picks.size > 1) {
            val more = plan.picks.drop(1).joinToString(" · ") { "${it.category.name}｜${it.article.title}" }
            builder.setSubText(more.take(100))
        }

        runCatching {
            NotificationManagerCompat.from(context).notify(ID_DAILY, builder.build())
        }
    }
}
