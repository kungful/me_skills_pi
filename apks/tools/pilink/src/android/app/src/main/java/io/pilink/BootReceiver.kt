package io.pilink

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

/** 开机 / 应用更新后把订阅拉起来（清单里声明了 RECEIVE_BOOT_COMPLETED） */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action ?: return
        Log.i("PiLink", "BootReceiver: $action")
        val prefs = Prefs(context)
        if (!prefs.enabled) {
            Log.i("PiLink", "用户没开启订阅，跳过开机自启")
            return
        }
        PiLinkService.start(context)
    }
}
