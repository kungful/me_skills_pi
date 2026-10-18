package com.hua.teastrategist;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** 定时闹钟到点后跑晨报。goAsync 让进程在后台多活一会儿。 */
public class BriefingReceiver extends BroadcastReceiver {

    private static final ExecutorService POOL = Executors.newSingleThreadExecutor();

    @Override
    public void onReceive(final Context context, Intent intent) {
        final PendingResult pr = goAsync();
        final Context c = context.getApplicationContext();
        POOL.execute(new Runnable() {
            public void run() {
                try { Briefing.run(c); }
                catch (Throwable ignored) { }
                finally { try { pr.finish(); } catch (Throwable ignored) { } }
            }
        });
    }
}
