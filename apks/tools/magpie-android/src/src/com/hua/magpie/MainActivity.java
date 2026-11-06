package com.hua.magpie;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.io.ByteArrayOutputStream;
import java.io.FileInputStream;
import java.net.InetSocketAddress;
import java.net.Socket;

public class MainActivity extends Activity {

    /** 固定 key，重启后浏览器/WebView 的 cookie 依然有效（>=16 位，仅 A-Za-z0-9-._~）。 */
    public static final String WEB_KEY = "magpie-phone-gateway-key-0101";
    public static final int PAGE_PORT = 3430;

    static final String LINK = "http://127.0.0.1:" + PAGE_PORT + "/?k=" + WEB_KEY;

    private WebView web;
    private LinearLayout cover;
    private TextView tip;
    private final Handler h = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        FrameLayout root = new FrameLayout(this);

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setLoadWithOverviewMode(false);
        s.setUseWideViewPort(false);
        s.setSupportZoom(false);
        s.setAllowFileAccess(false);
        s.setMediaPlaybackRequiresUserGesture(true);
        web.setWebViewClient(new WebViewClient());
        web.setBackgroundColor(Color.parseColor("#111114"));
        root.addView(web, new FrameLayout.LayoutParams(-1, -1));

        cover = new LinearLayout(this);
        cover.setOrientation(LinearLayout.VERTICAL);
        cover.setGravity(Gravity.CENTER);
        cover.setBackgroundColor(Color.parseColor("#111114"));
        cover.setPadding(48, 48, 48, 48);

        tip = new TextView(this);
        tip.setTextColor(Color.parseColor("#dcdce0"));
        tip.setTextSize(15);
        tip.setGravity(Gravity.CENTER);
        tip.setText("正在启动 magpie…\n首次启动要解出 60MB 运行时，稍等十几秒");
        cover.addView(tip, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER);
        row.setPadding(0, 36, 0, 0);

        Button retry = new Button(this);
        retry.setText("重试");
        retry.setOnClickListener(v -> {
            startGateway();
            waitAndLoad();
        });
        row.addView(retry);

        Button logs = new Button(this);
        logs.setText("日志");
        logs.setOnClickListener(v -> showLog());
        row.addView(logs);

        cover.addView(row, new LinearLayout.LayoutParams(-1, -2));
        root.addView(cover, new FrameLayout.LayoutParams(-1, -1));

        setContentView(root);

        askNotifications();
        askBattery();
        startGateway();
        waitAndLoad();
    }

    /** 一次就好：让系统别把网关当成省电对象。国产 ROM 自己的后台管理还得手动开。 */
    private void askBattery() {
        android.os.PowerManager pm = (android.os.PowerManager) getSystemService(POWER_SERVICE);
        if (pm == null || pm.isIgnoringBatteryOptimizations(getPackageName())) return;
        android.content.SharedPreferences sp = getSharedPreferences("magpie", MODE_PRIVATE);
        if (sp.getBoolean("asked_battery", false)) return;
        sp.edit().putBoolean("asked_battery", true).apply();
        try {
            Intent i = new Intent(android.provider.Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS);
            i.setData(android.net.Uri.parse("package:" + getPackageName()));
            startActivity(i);
        } catch (Exception e) {
            android.util.Log.i("magpie", "电池优化申请打不开: " + e);
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        // 回到前台：顺手确保服务在跑；网关卡死/被杀就自动恢复，不用用户点「重试」
        startGateway();
        new Thread(() -> {
            if (!tryConnect()) h.post(MainActivity.this::waitAndLoad);
        }, "magpie-resume").start();
    }

    private void askNotifications() {
        if (Build.VERSION.SDK_INT >= 33) {
            if (checkSelfPermission("android.permission.POST_NOTIFICATIONS")
                    != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"}, 1);
            }
        }
    }

    private void startGateway() {
        Intent i = new Intent(this, GwService.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(i);
        } else {
            startService(i);
        }
    }

    private boolean tryConnect() {
        try (Socket sock = new Socket()) {
            sock.connect(new InetSocketAddress("127.0.0.1", PAGE_PORT), 1500);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    private volatile boolean polling = false;

    private void waitAndLoad() {
        cover.setVisibility(View.VISIBLE);
        tip.setText("正在启动 magpie…\n首次启动要解出 60MB 运行时，稍等十几秒");
        startPoll();
    }

    /** 探活必须在后台线程：Android 禁止主线程碰 socket（NetworkOnMainThreadException）。 */
    private void startPoll() {
        if (polling) return;
        polling = true;
        new Thread(() -> {
            for (int n = 1; n <= 120 && polling; n++) {
                if (tryConnect()) {
                    polling = false;
                    android.util.Log.i("magpie", "port open after " + n + " tries");
                    h.post(() -> {
                        cover.setVisibility(View.GONE);
                        web.loadUrl(LINK);
                    });
                    return;
                }
                final int k = n;
                h.post(() -> {
                    if (k == 16) {
                        tip.setText("还在启动…（首次初始化配置较慢）");
                    } else if (k > 120) {
                        tip.setText("启动超时。点“日志”看 magpie 的输出去哪了。");
                    }
                });
                try {
                    Thread.sleep(500);
                } catch (InterruptedException e) {
                    return;
                }
            }
            polling = false;
        }, "magpie-poll").start();
    }

    private void showLog() {
        String text = tail(GwService.logFile(this), 12000);
        TextView tv = new TextView(this);
        tv.setText(text.isEmpty() ? "(还没有日志)" : text);
        tv.setTextSize(11);
        tv.setTextIsSelectable(true);
        tv.setPadding(24, 24, 24, 24);
        ScrollView sv = new ScrollView(this);
        sv.addView(tv);
        new AlertDialog.Builder(this)
                .setTitle("magpie 日志")
                .setView(sv)
                .setPositiveButton("关闭", null)
                .setNeutralButton("后台设置", (d, w) -> openAppSettings())
                .setNegativeButton("重启网关", (d, w) -> {
                    startGateway();
                    waitAndLoad();
                })
                .show();
    }

    /** 直接跳到本应用的系统设置页：iQOO/vivo 的「电池 → 后台耗电管理」从这儿往下走。 */
    private void openAppSettings() {
        try {
            Intent i = new Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
            i.setData(android.net.Uri.parse("package:" + getPackageName()));
            startActivity(i);
        } catch (Exception e) {
            android.util.Log.i("magpie", "打开设置失败: " + e);
        }
    }

    private static String tail(java.io.File f, int max) {
        if (f == null || !f.exists()) return "";
        try (FileInputStream in = new FileInputStream(f)) {
            long len = f.length();
            long skip = Math.max(0, len - max);
            in.skip(skip);
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
            return out.toString("UTF-8");
        } catch (Exception e) {
            return "读取日志失败: " + e;
        }
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) {
            web.goBack();
        } else {
            // 网关留在前台服务里继续跑
            moveTaskToBack(true);
        }
    }
}
