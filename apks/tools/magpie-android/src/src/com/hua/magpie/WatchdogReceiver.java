package com.hua.magpie;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

/**
 * 闹钟唤回：服务进程被系统冻住/回收之后，AlarmManager 的闹钟是唯一还能把它叫醒的东西
 * （投递闹钟时系统会临时解冻目标应用）。醒来后交给服务做一次健康检查并重新排下一次闹钟。
 */
public class WatchdogReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        GwService.appendLog(context, "闹钟唤醒：检查网关");
        Intent i = new Intent(context, GwService.class).setAction(GwService.ACTION_ALARM);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(i);
        } else {
            context.startService(i);
        }
    }
}
