package com.hua.subhunter;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** 开机 / 升级后把每日定时重新排上（否则重启后闹钟就没了）。 */
public class BootReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(Context context, Intent intent) {
        try {
            Store st = Store.get(context);
            // 恢复清单里不存在的新内置源
            st.sources();
            Sched.reschedule(context);
            if (st.autoOn()) {
                // 开机 2 分钟后再补一次，避免开机瞬间网络还没起来
                Sched.enqueueOnce(context);
            }
        } catch (Throwable ignore) {
        }
    }
}
