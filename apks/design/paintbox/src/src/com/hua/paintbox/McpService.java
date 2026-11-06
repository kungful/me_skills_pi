package com.hua.paintbox;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;

/**
 * MCP 打开期间的前台服务：只为让进程在后台活着、端口一直开着。
 * 被系统回收后会重建（START_STICKY）；开关关掉就当场退出。
 */
public class McpService extends Service {

    public static final String ACTION_START = "com.hua.paintbox.MCP_START";
    public static final String ACTION_STOP = "com.hua.paintbox.MCP_STOP";
    private static final String CHANNEL = "mcp";
    private static final int NOTIFICATION_ID = 43;

    private McpHost host() {
        return McpHost.get(this);
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent == null ? null : intent.getAction();
        McpHost h = host();
        if (ACTION_STOP.equals(action)) {
            h.setEnabled(false);
            h.apply();
            stopSelf();
            return START_NOT_STICKY;
        }
        if (ACTION_START.equals(action)) {
            h.setEnabled(true);
        }
        if (!h.enabled()) {
            h.apply();
            stopSelf();
            return START_NOT_STICKY;
        }
        ensureChannel();
        try {
            Notification n = buildNotification();
            if (Build.VERSION.SDK_INT >= 34) {
                startForeground(NOTIFICATION_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
            } else {
                startForeground(NOTIFICATION_ID, n);
            }
        } catch (Throwable t) {
            h.log("进前台失败: " + t);
        }
        String err = h.apply();
        if (err != null) {
            android.widget.Toast.makeText(this, "MCP 启动失败：" + err, android.widget.Toast.LENGTH_LONG).show();
        }
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        McpHost h = host();
        Mcp server = h.server();
        if (server != null) {
            server.stop();
            h.log("MCP 已停止（服务结束）");
        }
        super.onDestroy();
    }

    private void ensureChannel() {
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (nm == null) return;
        if (nm.getNotificationChannel(CHANNEL) != null) return;
        NotificationChannel ch = new NotificationChannel(CHANNEL, "MCP 服务", NotificationManager.IMPORTANCE_LOW);
        ch.setDescription("跑图助手的 MCP 端口开着的时候显示");
        ch.setShowBadge(false);
        nm.createNotificationChannel(ch);
    }

    private Notification buildNotification() {
        McpHost h = host();
        Intent open = new Intent(this, MainActivity.class);
        PendingIntent pi = PendingIntent.getActivity(this, 0, open,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Intent off = new Intent(this, McpService.class).setAction(ACTION_STOP);
        PendingIntent offPi = PendingIntent.getService(this, 1, off,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, CHANNEL)
                : new Notification.Builder(this);
        return b.setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
                .setContentTitle("跑图助手 MCP")
                .setContentText(h.url() + " · " + (h.token().isEmpty() ? "无令牌" : "需令牌"))
                .setContentIntent(pi)
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .addAction(new Notification.Action.Builder(null, "关掉", offPi).build())
                .build();
    }
}
