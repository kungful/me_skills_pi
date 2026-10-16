package org.opensource.lifealgo.reminder

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** 重启 / 覆盖安装后系统会清掉闹钟，这里补回来。 */
class BootReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        when (intent.action) {
            Intent.ACTION_BOOT_COMPLETED,
            Intent.ACTION_MY_PACKAGE_REPLACED,
            -> runCatching { ReminderScheduler.rescheduleFromSettings(context) }
        }
    }
}
