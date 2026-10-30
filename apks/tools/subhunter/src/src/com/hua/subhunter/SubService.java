package com.hua.subhunter;

import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;

/** 本机订阅服务宿主：把 LocalServer 放进前台服务里，App 退到后台也不断。 */
public class SubService extends Service {

    static final String ACTION_SERVER_ON = "com.hua.subhunter.SERVER_ON";
    static final String ACTION_SERVER_OFF = "com.hua.subhunter.SERVER_OFF";
    static final String ACTION_AUTO_FETCH = "com.hua.subhunter.AUTO_FETCH";

    private LocalServer server;

    static void startServer(Context c) {
        Intent i = new Intent(c, SubService.class).setAction(ACTION_SERVER_ON);
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) c.startForegroundService(i);
            else c.startService(i);
        } catch (Throwable t) {
            try {
                c.startService(i);
            } catch (Throwable ignore) {
            }
        }
    }

    static void stopServer(Context c) {
        Intent i = new Intent(c, SubService.class).setAction(ACTION_SERVER_OFF);
        try {
            c.startService(i);
        } catch (Throwable ignore) {
        }
    }

    static void autoFetch(Context c) {
        Intent i = new Intent(c, SubService.class).setAction(ACTION_AUTO_FETCH);
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) c.startForegroundService(i);
            else c.startService(i);
        } catch (Throwable ignore) {
        }
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent == null || intent.getAction() == null ? ACTION_SERVER_ON : intent.getAction();
        Store st = Store.get(this);

        if (ACTION_SERVER_OFF.equals(action)) {
            stopServerInternal();
            stopSelf();
            return START_NOT_STICKY;
        }

        goForeground(ACTION_AUTO_FETCH.equals(action));
        if (ACTION_SERVER_ON.equals(action)) startServerInternal(st.port());
        if (ACTION_AUTO_FETCH.equals(action)) {
            final Context ctx = this;
            new Thread(new Runnable() {
                @Override
                public void run() {
                    Worker.Outcome o = Worker.run(ctx, null);
                    if (o.result != null && o.result.nodes.size() > 0 && Store.get(ctx).notifOn()) {
                        Sched.notify(ctx, Sched.N_RESULT, "订阅猎手 · 已自动同步",
                                summary(o));
                    }
                    goForeground(false);
                    // 只为了抓这一下，服务不必常住（本机订阅服务没开就退下）
                    if (server == null || !server.isRunning()) {
                        stopForeground(true);
                        stopSelf();
                    }
                }
            }, "subhunter-auto").start();
        }
        return START_STICKY;
    }

    static String summary(Worker.Outcome o) {
        if (o.result == null) return Util.isBlank(o.error) ? "抓取失败" : o.error;
        int n = o.result.nodes.size();
        String extra = o.newCount > 0 ? ("新增 " + o.newCount + " 个") : "与上次一致";
        return n + " 个可用节点 · " + extra + " · 可用 " + Math.max(0, o.result.aliveTotal);
    }

    private void goForeground(boolean busy) {
        try {
            Sched.ensureChannel(this);
            boolean srv = server != null && server.isRunning();
            String title;
            String text;
            if (busy) {
                title = "正在同步公益节点…";
                text = "抓取 + 测活，大约 1 分钟";
            } else if (srv) {
                title = "订阅猎手 · 本机订阅服务";
                text = "127.0.0.1:" + server.port() + "/clash · 每天自动更新";
            } else {
                title = "订阅猎手 · 已完成";
                text = Sched.cachedSummary(this);
            }
            startForeground(Sched.N_SERVER, Sched.notification(this, title, text, srv || busy));
        } catch (Throwable ignore) {
        }
    }

    private void startServerInternal(int port) {
        if (server != null && server.isRunning()) {
            goForeground(false);
            return;
        }
        final Store st = Store.get(this);
        server = new LocalServer(port, new LocalServer.Provider() {
            @Override
            public String clashYaml() {
                String y = st.clashYaml();
                return Util.isBlank(y) ? "# 订阅猎手：还没有数据，先回 App 抓一次\n" : y;
            }

            @Override
            public String v2rayB64() {
                return st.v2rayB64();
            }

            @Override
            public String info() {
                return "{\"time\":" + q(st.lastTime()) + ",\"nodes\":" + q(st.meta("nodeCount", "0"))
                        + ",\"clash\":" + q(st.meta("clashCount", "0")) + "}";
            }
        });
        boolean ok = server.start();
        Hub.SERVER = server;
        Hub.log(ok ? "本机订阅服务已启动 :" + port : "启动失败：" + server.lastError());
        if (!ok) {
            // 端口被占用时换一个
            LocalServer alt = new LocalServer(port + 1, server.provider());
            if (alt.start()) {
                server = alt;
                Hub.SERVER = alt;
                Hub.log("端口 " + port + " 被占用，改用 " + (port + 1));
            }
        }
        goForeground(false);
    }

    private static String q(String s) {
        return Util.yq(Util.nz(s));
    }

    private void stopServerInternal() {
        if (server != null) {
            server.stop();
            Hub.SERVER = null;
            server = null;
        }
        Hub.log("本机订阅服务已停止");
        try {
            stopForeground(true);
        } catch (Throwable ignore) {
        }
        Sched.cancelNotification(this, Sched.N_SERVER);
    }

    @Override
    public void onDestroy() {
        stopServerInternal();
        super.onDestroy();
    }

    /**
     * Android 15（API 35）起，dataSync 类型的前台服务在后台累计只能跑 6 小时，
     * 到点系统回调这里；不处理就会 RemoteServiceException 崩掉。
     * 这里主动收工：数据已经在本地落盘，用户下次打开 App 会自动续上。
     * compileSdk 34 下没有这个方法，所以不加 @Override，靠签名分派即可。
     */
    public void onTimeout(int startId, int fgsType) {
        Hub.log("后台服务到时长上限，已主动收工（数据已保存）");
        try {
            Store.get(this).put("serverWanted", "1");
        } catch (Throwable ignore) {
        }
        stopServerInternal();
        stopSelf();
    }

    /** Android 14 的短时前台服务超时回调。 */
    public void onTimeout(int startId) {
        onTimeout(startId, 0);
    }
}
