package com.hua.subhunter;

import android.app.AlarmManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.job.JobInfo;
import android.app.job.JobScheduler;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

import java.util.Calendar;

/** 每日定时（Alarm 主调度 + JobScheduler 兜底）与通知。 */
final class Sched {

    static final String CH = "subhunter";
    static final int JOB_DAILY = 8801;
    static final int JOB_ONCE = 8802;
    static final int N_SERVER = 1;
    static final int N_RESULT = 2;
    static final int N_FETCH = 3;

    private Sched() {
    }

    // ------------------------------------------------------------------ 通知

    static void ensureChannel(Context c) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        try {
            NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm == null) return;
            NotificationChannel ch = new NotificationChannel(CH, "订阅同步", NotificationManager.IMPORTANCE_LOW);
            ch.setDescription("每日节点抓取与本机订阅服务状态");
            ch.setShowBadge(false);
            nm.createNotificationChannel(ch);
        } catch (Throwable ignore) {
        }
    }

    static Notification notification(Context c, String title, String text, boolean ongoing) {
        ensureChannel(c);
        Notification.Builder b;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            b = new Notification.Builder(c, CH);
        } else {
            b = new Notification.Builder(c);
        }
        b.setContentTitle(title)
                .setContentText(text)
                .setSmallIcon(android.R.drawable.stat_notify_sync)
                .setOngoing(ongoing)
                .setOnlyAlertOnce(true);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            b.setVisibility(Notification.VISIBILITY_SECRET);
        }
        Intent i = new Intent(c, MainActivity.class);
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) flags |= PendingIntent.FLAG_IMMUTABLE;
        b.setContentIntent(PendingIntent.getActivity(c, 0, i, flags));
        return b.build();
    }

    static void notify(Context c, int id, String title, String text) {
        try {
            NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm == null) return;
            Notification.Builder b;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                ensureChannel(c);
                b = new Notification.Builder(c, CH);
            } else {
                b = new Notification.Builder(c);
            }
            b.setContentTitle(title).setContentText(text)
                    .setSmallIcon(android.R.drawable.stat_notify_sync)
                    .setAutoCancel(true);
            Intent i = new Intent(c, MainActivity.class);
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
            int flags = PendingIntent.FLAG_UPDATE_CURRENT;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) flags |= PendingIntent.FLAG_IMMUTABLE;
            b.setContentIntent(PendingIntent.getActivity(c, 0, i, flags));
            nm.notify(id, b.build());
        } catch (Throwable ignore) {
        }
    }

    static void cancelNotification(Context c, int id) {
        try {
            NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm != null) nm.cancel(id);
        } catch (Throwable ignore) {
        }
    }

    // ------------------------------------------------------------------ 定时

    static long nextTrigger(int hour, int minute) {
        Calendar cal = Calendar.getInstance();
        cal.set(Calendar.HOUR_OF_DAY, Math.max(0, Math.min(23, hour)));
        cal.set(Calendar.MINUTE, Math.max(0, Math.min(59, minute)));
        cal.set(Calendar.SECOND, 0);
        cal.set(Calendar.MILLISECOND, 0);
        if (cal.getTimeInMillis() <= System.currentTimeMillis() + 60_000L) {
            cal.add(Calendar.DAY_OF_YEAR, 1);
        }
        return cal.getTimeInMillis();
    }

    /** 依据设置重新排程；关掉自动抓取时清掉所有定时。 */
    static void reschedule(Context c) {
        Store st = Store.get(c);
        AlarmManager am = (AlarmManager) c.getSystemService(Context.ALARM_SERVICE);
        Intent i = new Intent(c, AutoReceiver.class).setAction(AutoReceiver.ACTION_TICK);
        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) flags |= PendingIntent.FLAG_IMMUTABLE;
        PendingIntent pi = PendingIntent.getBroadcast(c, 100, i, flags);

        if (am != null) {
            try {
                am.cancel(pi);
            } catch (Throwable ignore) {
            }
        }
        JobScheduler js = (JobScheduler) c.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if (js != null) {
            try {
                js.cancel(JOB_DAILY);
            } catch (Throwable ignore) {
            }
        }

        if (!st.autoOn()) return;

        long at = nextTrigger(st.autoHour(), st.autoMinute());
        if (am != null) {
            try {
                am.setInexactRepeating(AlarmManager.RTC_WAKEUP, at, AlarmManager.INTERVAL_DAY, pi);
            } catch (Throwable t) {
                try {
                    am.set(AlarmManager.RTC_WAKEUP, at, pi);
                } catch (Throwable ignore) {
                }
            }
        }
        if (js != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            try {
                JobInfo job = new JobInfo.Builder(JOB_DAILY, new ComponentName(c, AutoJobService.class))
                        .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                        .setPeriodic(24 * 60 * 60 * 1000L)
                        .setPersisted(true)
                        .build();
                js.schedule(job);
            } catch (Throwable ignore) {
            }
        }
    }

    /** 立刻提交一个一次性后台任务（开机/闹钟触发时用，绕开 FGS 后台限制）。 */
    static void enqueueOnce(Context c) {
        JobScheduler js = (JobScheduler) c.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if (js == null) {
            AutoReceiver.runInline(c);
            return;
        }
        try {
            JobInfo job = new JobInfo.Builder(JOB_ONCE, new ComponentName(c, AutoJobService.class))
                    .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                    .setOverrideDeadline(10 * 60 * 1000L)
                    .build();
            js.schedule(job);
        } catch (Throwable t) {
            AutoReceiver.runInline(c);
        }
    }

    static String cachedSummary(Context c) {
        Store st = Store.get(c);
        String t = st.lastTime();
        int n = Util.toInt(st.meta("nodeCount", "0"), 0);
        if (Util.isBlank(t)) return "尚未抓取过";
        return t + " · " + n + " 个节点";
    }
}
