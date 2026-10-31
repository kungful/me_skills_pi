package com.hua.subhunter;

import android.app.job.JobParameters;
import android.app.job.JobService;
import android.content.Context;

/** JobScheduler 执行体：每日自动抓取（Doze 下比 Alarm 可靠）。 */
public class AutoJobService extends JobService {

    private volatile Thread worker;

    @Override
    public boolean onStartJob(final JobParameters params) {
        final Context ctx = getApplicationContext();
        worker = new Thread(new Runnable() {
            @Override
            public void run() {
                boolean ok = true;
                try {
                    Store st = Store.get(ctx);
                    if (params.getJobId() == Sched.JOB_DAILY && !st.autoOn()) {
                        jobFinished(params, false);
                        return;
                    }
                    Worker.Outcome o = Worker.run(ctx, null);
                    if (o.result != null && !o.result.nodes.isEmpty() && st.notifOn()) {
                        Sched.notify(ctx, Sched.N_RESULT, "订阅猎手 · 已自动同步",
                                SubService.summary(o));
                    } else if (o.newCount == 0 && o.result != null && st.notifOn() && params.getJobId() == Sched.JOB_DAILY) {
                        Sched.notify(ctx, Sched.N_RESULT, "订阅猎手 · 同步完成",
                                "节点与上次一致（" + o.result.nodes.size() + " 个）");
                    }
                } catch (Throwable t) {
                    ok = false;
                }
                jobFinished(params, !ok);
            }
        }, "subhunter-job");
        worker.start();
        return true;
    }

    @Override
    public boolean onStopJob(JobParameters params) {
        if (worker != null) worker.interrupt();
        return true;
    }
}
