package com.hua.subhunter;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** 每日闹钟 / JobScheduler 的触发入口。 */
public class AutoReceiver extends BroadcastReceiver {

    static final String ACTION_TICK = "com.hua.subhunter.TICK";

    @Override
    public void onReceive(Context context, Intent intent) {
        try {
            Store st = Store.get(context);
            if (!st.autoOn()) {
                Sched.reschedule(context);
                return;
            }
            // 交给 JobScheduler：Android 12+ 从后台直接起前台服务会被拦，Job 更稳
            Sched.enqueueOnce(context);
        } catch (Throwable t) {
            runInline(context);
        }
    }

    /** 兜底：没有 JobScheduler 时直接在这里同步跑。 */
    static void runInline(final Context context) {
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    Worker.Outcome o = Worker.run(context, null);
                    if (o.result != null && !o.result.nodes.isEmpty() && Store.get(context).notifOn()) {
                        Sched.notify(context, Sched.N_RESULT, "订阅猎手 · 已自动同步",
                                SubService.summary(o));
                    }
                } catch (Throwable ignore) {
                }
            }
        }, "subhunter-inline").start();
    }
}
