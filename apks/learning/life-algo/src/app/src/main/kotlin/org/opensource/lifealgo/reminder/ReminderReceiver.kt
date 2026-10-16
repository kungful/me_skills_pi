package org.opensource.lifealgo.reminder

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** 到点发通知，并把下一次闹钟排上（一次性闹钟需要自己续期）。 */
class ReminderReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != ACTION_DAILY) return
        runCatching { Notifications.postDaily(context) }
        // 续期明天的
        runCatching { ReminderScheduler.rescheduleFromSettings(context) }
    }

    companion object {
        const val ACTION_DAILY = "org.opensource.lifealgo.DAILY_REMINDER"
    }
}
