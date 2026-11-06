package com.hua.magpie;

import android.app.AlarmManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkRequest;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * 把 magpie-cli-android-arm64（打包成 jniLibs/lib/arm64-v8a/libmagpie.so）
 * 当子进程跑起来：`magpie serve --web=127.0.0.1:3430`
 * —— 一个进程同时提供网关（3425）和手机版网页（3430），插件跑在它拉起的 Bun 里。
 *
 * 稳定性加固（Android 的后台很凶，尤其是国产 ROM）：
 *   1. 本服务跑在独立进程 :gw，UI 进程被杀/被冻与它无关；
 *   2. 20 秒看门狗：/api/hello 连续两次不应答 → 杀掉整棵子进程树重启；
 *      每 3 轮再做一次"深探"（页面端口的 API），防网关活着但插件宿主卡死；
 *   3. AlarmManager 每 10 分钟一次的一次性闹钟：被系统冻住时闹钟会把它解冻并唤回，
 *      顺便做一次健康检查；
 *   4. 网络切换（Wi-Fi ↔ 5G）回调里立刻探一次，断了就重启；
 *   5. PARTIAL_WAKE_LOCK + 前台通知（带「重启」「停止」）。
 */
public class GwService extends Service {

    static final String CHANNEL = "magpie";
    static final int NOTIF_ID = 0x9527;
    static final String ACTION_STOP = "com.hua.magpie.action.STOP";
    static final String ACTION_RESTART = "com.hua.magpie.action.RESTART";
    static final String ACTION_ALARM = "com.hua.magpie.action.ALARM";

    static final long WATCH_MS = 20000L;
    static final long ALARM_MS = 2 * 60 * 1000L;   // 被 idle 时系统会自己降到 ~9 分钟

    private Process proc;
    private PowerManager.WakeLock lock;
    private volatile boolean wantRun = false;
    private volatile boolean explicitStop = false;
    private int restarts = 0;
    private int watchFails = 0;
    private Thread watchdog;
    private ConnectivityManager.NetworkCallback netCb;

    static File logFile(Context c) {
        return new File(c.getFilesDir(), "magpie.log");
    }

    static synchronized void appendLog(Context c, String line) {
        try {
            File f = logFile(c);
            if (f.length() > 2 * 1024 * 1024) {
                File old = new File(c.getFilesDir(), "magpie.log.1");
                if (old.exists()) old.delete();
                f.renameTo(old);
            }
            String t = new SimpleDateFormat("MM-dd HH:mm:ss", Locale.US).format(new Date());
            try (OutputStream os = new FileOutputStream(f, true)) {
                os.write((t + "  " + line + "\n").getBytes("UTF-8"));
            }
        } catch (Exception ignored) {
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        createChannel();
        PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
        if (pm != null) {
            lock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "magpie:gateway");
            lock.setReferenceCounted(false);
        }
        watchNetwork();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent == null ? null : intent.getAction();
        if (ACTION_STOP.equals(action)) {
            wantRun = false;
            explicitStop = true;
            stopAll();
            stopSelf();
            return START_NOT_STICKY;
        }
        wantRun = true;
        explicitStop = false;
        startForeground(NOTIF_ID, buildNotification());
        if (lock != null && !lock.isHeld()) {
            lock.acquire();
        }
        if (ACTION_RESTART.equals(action)) {
            appendLog(this, "手动重启网关");
            hardReset();
        }
        ensureRunning();
        startWatchdog();
        scheduleAlarm();
        scheduleJob();
        return START_STICKY;
    }

    // ---- 健康检查 ---------------------------------------------------------

    /** 任何 HTTP 应答（200/401/404 都算）说明网关活着；超时或连不上才算死。 */
    static boolean answers(String url, int connectTimeout, int readTimeout) {
        Socket s = new Socket();
        try {
            java.net.URL u = new java.net.URL(url);
            s.connect(new InetSocketAddress("127.0.0.1", u.getPort()), connectTimeout);
            s.setSoTimeout(readTimeout);
            String req = "GET " + u.getPath() + (u.getQuery() == null ? "" : "?" + u.getQuery())
                    + " HTTP/1.0\r\nHost: 127.0.0.1\r\nAccept: */*\r\n\r\n";
            s.getOutputStream().write(req.getBytes("UTF-8"));
            s.getOutputStream().flush();
            return s.getInputStream().read() >= 0;
        } catch (Exception e) {
            return false;
        } finally {
            try {
                s.close();
            } catch (Exception ignored) {
            }
        }
    }

    private static boolean gatewayAlive() {
        return answers("http://127.0.0.1:3425/api/hello", 1200, 3000);
    }

    /** 深探：页面端口的 API，能应答说明 magpie 的主循环（含插件宿主）没卡死。 */
    private static boolean deepAlive() {
        return answers("http://127.0.0.1:3430/api/plugins/market?k=" + MainActivity.WEB_KEY, 1500, 12000);
    }

    // ---- 子进程 -----------------------------------------------------------

    /**
     * 保证只有一个、而且是我们自己看得见的那个网关进程。
     * 加锁：onStartCommand / 看门狗 / 网络回调 / 崩后重启四条线都会调它，
     * 不加锁会并发起两个子进程，后一个 bind 失败退出，然后进入重启死循环
     * （page 那边就会报 "another magpie serves the gateway here"）。
     */
    private synchronized void ensureRunning() {
        if (proc != null && proc.isAlive()) return;
        if (gatewayAlive()) {
            // 端口被一个不归本服务管的残留进程占着（上个版本、上次安装的孤儿子进程）：
            // 它我们杀不掉也重启不了，直接清掉换自己的，才能“重启网关”按得动。
            appendLog(this, "端口已被别的 magpie 占着，清理后接管");
            killStaleProcesses();
            waitPortFree(4000);
        }
        File bin = new File(getApplicationInfo().nativeLibraryDir, "libmagpie.so");
        if (!bin.canExecute()) {
            appendLog(this, "二进制不可执行: " + bin.getAbsolutePath());
            updateNotification("启动失败：二进制不可执行");
            wantRun = false;
            return;
        }
        File home = getFilesDir();
        ProcessBuilder pb = new ProcessBuilder(
                bin.getAbsolutePath(),
                "serve",
                "--web=127.0.0.1:" + MainActivity.PAGE_PORT);
        pb.redirectErrorStream(true);
        pb.directory(home);
        pb.environment().put("HOME", home.getAbsolutePath());
        pb.environment().put("XDG_CONFIG_HOME", home.getAbsolutePath());
        pb.environment().put("TMPDIR", getCacheDir().getAbsolutePath());
        pb.environment().put("MAGPIE_WEB_KEY", MainActivity.WEB_KEY);
        pb.environment().put("TZ", "Asia/Shanghai");
        pb.environment().put("PATH", "/system/bin:/system/xbin:/vendor/bin");
        appendLog(this, "启动 " + bin.getAbsolutePath() + " serve --web=127.0.0.1:" + MainActivity.PAGE_PORT);
        try {
            proc = pb.start();
        } catch (Exception e) {
            appendLog(this, "exec 失败: " + e);
            updateNotification("启动失败：" + e.getMessage());
            return;
        }
        pumpOutput(proc);
        updateNotification(null);
    }

    private void pumpOutput(final Process p) {
        Thread t = new Thread(() -> {
            byte[] buf = new byte[8192];
            StringBuilder line = new StringBuilder();
            try (InputStream in = p.getInputStream()) {
                int n;
                while ((n = in.read(buf)) > 0) {
                    for (int i = 0; i < n; i++) {
                        char ch = (char) (buf[i] & 0xff);
                        if (ch == '\n') {
                            appendLog(GwService.this, line.toString());
                            line.setLength(0);
                        } else if (line.length() < 2000) {
                            line.append(ch);
                        }
                    }
                }
            } catch (Exception ignored) {
            }
            int code = -1;
            try {
                code = p.waitFor();
            } catch (InterruptedException ignored) {
            }
            appendLog(GwService.this, "magpie 退出，code=" + code);
            if (!wantRun) return;
            if (restarts < 5) {
                restarts++;
                long wait = Math.min(2000L * restarts, 15000L);
                appendLog(GwService.this, wait / 1000 + " 秒后重启（第 " + restarts + " 次）");
                new Thread(() -> {
                    try {
                        Thread.sleep(wait);
                    } catch (InterruptedException ignored) {
                    }
                    if (wantRun) ensureRunning();
                }).start();
            } else {
                updateNotification("magpie 反复退出，点通知看日志");
            }
        }, "magpie-pump");
        t.setDaemon(true);
        t.start();
    }

    /** 硬重启：杀子进程 + 清掉同 uid 的残留 magpie/bun 进程 + 等端口释放。 */
    private synchronized void hardReset() {
        killChild();
        killStaleProcesses();
        waitPortFree(4000);
        restarts = 0;
        watchFails = 0;
    }

    /** 扫 /proc，把本应用 uid 下还活着的 libmagpie.so / magpie-bun 全部 SIGKILL。 */
    private void killStaleProcesses() {
        File[] files = new File("/proc").listFiles();
        if (files == null) return;
        int self = android.os.Process.myPid();
        for (File f : files) {
            String name = f.getName();
            if (name.isEmpty() || !Character.isDigit(name.charAt(0))) continue;
            int pid;
            try {
                pid = Integer.parseInt(name);
            } catch (NumberFormatException e) {
                continue;
            }
            if (pid == self) continue;
            try {
                byte[] b = java.nio.file.Files.readAllBytes(new File(f, "cmdline").toPath());
                String cmd = new String(b, "UTF-8").replace('\0', ' ').trim();
                if (cmd.contains("libmagpie.so") || cmd.contains("magpie-bun")) {
                    appendLog(this, "清理残留进程 " + pid + "  " + cmd);
                    Runtime.getRuntime().exec(new String[]{"sh", "-c", "kill -9 " + pid}).waitFor();
                }
            } catch (Exception ignored) {
                // 别的应用的 /proc/<pid> 读不到，跳过
            }
        }
    }

    private void waitPortFree(long maxMs) {
        long until = System.currentTimeMillis() + maxMs;
        while (System.currentTimeMillis() < until) {
            if (!portOpen(3425) && !portOpen(MainActivity.PAGE_PORT)) return;
            try {
                Thread.sleep(200);
            } catch (InterruptedException e) {
                return;
            }
        }
    }

    private static boolean portOpen(int port) {
        try (Socket s = new Socket()) {
            s.connect(new InetSocketAddress("127.0.0.1", port), 400);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    private void killChild() {
        try {
            if (proc != null) {
                // 连带 Bun 插件宿主一起杀掉，restart 才是干净的
                int pid = pidOf(proc);
                proc.destroy();
                proc = null;
                if (pid > 0) killTree(pid);
            }
        } catch (Exception ignored) {
        }
    }

    /** Android 上拿不到 Process.pid()（API 26 有但被隐藏），用反射兜底。 */
    private static int pidOf(Process p) {
        try {
            java.lang.reflect.Method m = p.getClass().getMethod("pid");
            Object v = m.invoke(p);
            return v instanceof Integer ? (Integer) v : (int) (long) (Long) v;
        } catch (Exception e) {
            return -1;
        }
    }

    private static void killTree(int pid) {
        try {
            // 子进程的 bun：先 SIGTERM 再 SIGKILL，避免留下孤儿占端口
            Runtime.getRuntime().exec(new String[]{"sh", "-c", "kill " + pid + " 2>/dev/null; sleep 0.3; kill -9 " + pid + " 2>/dev/null"});
        } catch (Exception ignored) {
        }
    }

    // ---- 看门狗 -----------------------------------------------------------

    private void startWatchdog() {
        if (watchdog != null && watchdog.isAlive()) return;
        watchdog = new Thread(() -> {
            int round = 0;
            while (wantRun) {
                try {
                    Thread.sleep(WATCH_MS);
                } catch (InterruptedException e) {
                    return;
                }
                if (!wantRun) return;
                round++;
                boolean ok = gatewayAlive();
                if (ok && round % 3 == 0) {
                    // 深探：网关活着但插件宿主卡死时也能发现
                    ok = deepAlive();
                }
                if (ok) {
                    if (watchFails > 0) appendLog(this, "看门狗：网关恢复");
                    watchFails = 0;
                    restarts = 0;   // 活得好就把崩溃计数清零，不然几次抖动后就再也不重启了
                    continue;
                }
                watchFails++;
                appendLog(this, "看门狗：网关没应答（第 " + watchFails + " 次，round=" + round + "）");
                if (watchFails >= 2) {
                    appendLog(this, "看门狗：重启整棵网关进程");
                    hardReset();
                    ensureRunning();
                }
            }
        }, "magpie-watchdog");
        watchdog.setDaemon(true);
        watchdog.start();
    }

    // ---- 闹钟：被系统冻住时的救命索 ---------------------------------------

    private PendingIntent alarmIntent() {
        Intent i = new Intent(this, WatchdogReceiver.class).setAction(ACTION_ALARM);
        int f = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) f |= PendingIntent.FLAG_IMMUTABLE;
        return PendingIntent.getBroadcast(this, 71, i, f);
    }

    /** 第二条复活线：系统级周期任务（15 分钟），进程被杀、闹钟被清也还会被叫醒。 */
    private void scheduleJob() {
        try {
            android.app.job.JobScheduler js =
                    (android.app.job.JobScheduler) getSystemService(JOB_SCHEDULER_SERVICE);
            if (js == null) return;
            android.content.ComponentName cn = new android.content.ComponentName(this, KeepAliveJob.class);
            if (js.getPendingJob(4242) != null) return;
            android.app.job.JobInfo job = new android.app.job.JobInfo.Builder(4242, cn)
                    .setPeriodic(15 * 60 * 1000L)
                    .setPersisted(true)
                    .build();
            js.schedule(job);
        } catch (Exception e) {
            appendLog(this, "JobScheduler 安排失败: " + e);
        }
    }

    @Override
    public void onTaskRemoved(Intent rootIntent) {
        // 划掉最近任务：服务还在就留着，顺便把闹钟往前挪一点
        if (wantRun) {
            appendLog(this, "任务被划掉，安排唤回");
            scheduleAlarm();
            scheduleJob();
        }
        super.onTaskRemoved(rootIntent);
    }

    private void scheduleAlarm() {
        try {
            AlarmManager am = (AlarmManager) getSystemService(ALARM_SERVICE);
            if (am == null) return;
            am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,
                    System.currentTimeMillis() + ALARM_MS, alarmIntent());
        } catch (Exception e) {
            appendLog(this, "闹钟安排失败: " + e);
        }
    }

    // ---- 网络变化 ---------------------------------------------------------

    private void watchNetwork() {
        try {
            ConnectivityManager cm = (ConnectivityManager) getSystemService(CONNECTIVITY_SERVICE);
            if (cm == null) return;
            netCb = new ConnectivityManager.NetworkCallback() {
                @Override
                public void onAvailable(Network network) {
                    if (!wantRun) return;
                    // 刚切网络时旧连接会硬断，网关自己也会重连；等一会儿再判，
                    // 否则会把还在重启中的网关反复杀掉（之前的误重启就是这么来的）
                    new Thread(() -> {
                        try {
                            Thread.sleep(6000);
                        } catch (InterruptedException e) {
                            return;
                        }
                        if (!wantRun) return;
                        if (gatewayAlive()) {
                            appendLog(GwService.this, "网络变化，网关正常");
                            restarts = 0;
                            return;
                        }
                        try {
                            Thread.sleep(6000);
                        } catch (InterruptedException e) {
                            return;
                        }
                        if (!wantRun || gatewayAlive()) return;
                        appendLog(GwService.this, "网络变化后 12 秒仍无应答，重启网关");
                        synchronized (GwService.this) {
                            hardReset();
                            ensureRunning();
                        }
                    }, "magpie-net").start();
                }
            };
            cm.registerNetworkCallback(new NetworkRequest.Builder().build(), netCb);
        } catch (Exception e) {
            appendLog(this, "注册网络回调失败: " + e);
        }
    }

    // ---- 生命周期 ---------------------------------------------------------

    @Override
    public void onDestroy() {
        wantRun = false;
        // 不是用户点「停止」的话（系统回收 / 划掉任务），不杀子进程：
        // 它自己还能继续服务，下次进来直接沿用。
        if (explicitStop || proc == null) {
            stopAll();
        } else {
            if (lock != null && lock.isHeld()) lock.release();
            try {
                stopForeground(true);
            } catch (Exception ignored) {
            }
            // 服务被杀也要给自己留个闹钟，10 分钟后唤回来
            scheduleAlarm();
        }
        super.onDestroy();
    }

    private void stopAll() {
        killChild();
        if (lock != null && lock.isHeld()) lock.release();
        try {
            AlarmManager am = (AlarmManager) getSystemService(ALARM_SERVICE);
            if (am != null) am.cancel(alarmIntent());
        } catch (Exception ignored) {
        }
        try {
            if (netCb != null) {
                ConnectivityManager cm = (ConnectivityManager) getSystemService(CONNECTIVITY_SERVICE);
                if (cm != null) cm.unregisterNetworkCallback(netCb);
            }
        } catch (Exception ignored) {
        }
        try {
            stopForeground(true);
        } catch (Exception ignored) {
        }
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    // ---- 通知 -------------------------------------------------------------

    private void createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) return;
        NotificationChannel ch = new NotificationChannel(
                CHANNEL, "magpie 网关", NotificationManager.IMPORTANCE_LOW);
        ch.setShowBadge(false);
        nm.createNotificationChannel(ch);
    }

    private PendingIntent openIntent() {
        Intent i = new Intent(this, MainActivity.class);
        i.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        int f = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) f |= PendingIntent.FLAG_IMMUTABLE;
        return PendingIntent.getActivity(this, 0, i, f);
    }

    private PendingIntent actionIntent(String action, int code) {
        Intent i = new Intent(this, GwService.class).setAction(action);
        int f = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) f |= PendingIntent.FLAG_IMMUTABLE;
        return PendingIntent.getService(this, code, i, f);
    }

    private Notification.Builder builder(String text) {
        Notification.Builder b = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL)
                : new Notification.Builder(this);
        b.setSmallIcon(android.R.drawable.stat_notify_sync)
                .setContentTitle("magpie 网关运行中")
                .setContentText(text == null ? "127.0.0.1:3425 · 点开控制台" : text)
                .setOngoing(true)
                .setContentIntent(openIntent())
                .addAction(new Notification.Action.Builder(null, "重启", actionIntent(ACTION_RESTART, 2)).build())
                .addAction(new Notification.Action.Builder(null, "停止", actionIntent(ACTION_STOP, 1)).build());
        return b;
    }

    private Notification buildNotification() {
        return builder(null).build();
    }

    private void updateNotification(String text) {
        try {
            NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm != null) nm.notify(NOTIF_ID, builder(text).build());
        } catch (Exception ignored) {
        }
    }
}
