package org.opensource.lifealgo.reminder

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import org.opensource.lifealgo.LifeAlgoApp
import java.util.Calendar

/**
 * 每日提醒调度。
 *
 * 说明：中国大陆的 OEM 系统对后台闹钟管得很严，所以这里只做"尽力而为"：
 * 优先用精确闹钟（需要用户在系统设置里允许），拿不到权限就退化成不精确闹钟。
 * 不依赖任何推送服务（FCM 在国内不可用，厂商通道要企业资质），
 * 因此不需要联网、也不需要账号。
 */
object ReminderScheduler {

    private const val REQ = 2001

    fun rescheduleFromSettings(context: Context) {
        val settings = LifeAlgoApp.from(context).settings
        if (settings.reminderEnabled) {
            schedule(context, settings.reminderHour, settings.reminderMinute)
        } else {
            cancel(context)
        }
    }

    fun schedule(context: Context, hour: Int, minute: Int) {
        val am = context.getSystemService(AlarmManager::class.java) ?: return
        val trigger = nextTrigger(hour, minute)
        val pi = pendingIntent(context, PendingIntent.FLAG_UPDATE_CURRENT) ?: return

        val canExact = Build.VERSION.SDK_INT < Build.VERSION_CODES.S || am.canScheduleExactAlarms()
        runCatching {
            if (canExact) {
                am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, trigger, pi)
            } else {
                am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, trigger, pi)
            }
        }.onFailure {
            runCatching { am.set(AlarmManager.RTC_WAKEUP, trigger, pi) }
        }
    }

    fun cancel(context: Context) {
        val am = context.getSystemService(AlarmManager::class.java) ?: return
        am.cancel(pendingIntent(context, PendingIntent.FLAG_NO_CREATE) ?: return)
    }

    fun nextTrigger(hour: Int, minute: Int, from: Long = System.currentTimeMillis()): Long {
        val c = Calendar.getInstance().apply {
            timeInMillis = from
            set(Calendar.HOUR_OF_DAY, hour)
            set(Calendar.MINUTE, minute)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        if (c.timeInMillis <= from) c.add(Calendar.DAY_OF_YEAR, 1)
        return c.timeInMillis
    }

    private fun pendingIntent(context: Context, flags: Int): PendingIntent? {
        val intent = Intent(context, ReminderReceiver::class.java).apply {
            action = ReminderReceiver.ACTION_DAILY
        }
        return PendingIntent.getBroadcast(
            context,
            REQ,
            intent,
            flags or PendingIntent.FLAG_IMMUTABLE,
        )
    }
}
