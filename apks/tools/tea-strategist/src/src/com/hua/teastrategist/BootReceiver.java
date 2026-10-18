package com.hua.teastrategist;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** 开机后重新排上晨报闹钟（AlarmManager 的重复闹钟重启会丢）。 */
public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        try { Briefing.schedule(context.getApplicationContext()); } catch (Throwable ignored) { }
    }
}
