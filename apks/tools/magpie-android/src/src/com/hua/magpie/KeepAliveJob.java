package com.hua.magpie;

import android.app.job.JobParameters;
import android.app.job.JobService;
import android.content.Intent;
import android.os.Build;

/**
 * 定时 resurrect：JobScheduler 的周期任务由系统调度，即使进程被杀、闹钟被清，
 * 系统也会按 15 分钟周期把它叫起来一次。醒来只做一件事——网关不在就把它拉起来。
 */
public class KeepAliveJob extends JobService {
    @Override
    public boolean onStartJob(JobParameters params) {
        try {
            if (!GwService.answers("http://127.0.0.1:3425/api/hello", 1200, 3000)) {
                GwService.appendLog(this, "JobScheduler 巡检：网关不在，拉起");
                Intent i = new Intent(this, GwService.class).setAction(GwService.ACTION_ALARM);
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    startForegroundService(i);
                } else {
                    startService(i);
                }
            }
        } catch (Exception ignored) {
        }
        return false;
    }

    @Override
    public boolean onStopJob(JobParameters params) {
        return false;
    }
}
