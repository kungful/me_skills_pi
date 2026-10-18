package com.hua.teastrategist;

import android.Manifest;
import android.app.Activity;
import android.app.AlarmManager;
import android.app.NotificationManager;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.webkit.ConsoleMessage;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.widget.FrameLayout;

/**
 * 茶叶军师 —— WebView 壳子 + 原生网络桥。
 *
 * 页面（assets/）只负责画界面；所有联网（行情/快讯/热搜/汇率/大模型）、
 * 本地存储、导出分享都走 Bridge.invoke()。这样没有跨域限制，
 * 也不需要 WebView 自己去连各种财经接口。
 */
public class MainActivity extends Activity {

    private static final String HOME = "file:///android_asset/index.html";
    private static final int REQ_NOTIFY = 2001;

    private WebView web;
    private Bridge bridge;
    private boolean pageReady = false;
    private boolean wantBriefing = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestWindowFeature(Window.FEATURE_NO_TITLE);

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(0xFF0D1210);

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setLoadWithOverviewMode(false);
        s.setUseWideViewPort(true);
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        if (Build.VERSION.SDK_INT >= 26) s.setSafeBrowsingEnabled(false);
        web.setBackgroundColor(0xFF0D1210);
        web.setVerticalScrollBarEnabled(true);
        web.setOverScrollMode(View.OVER_SCROLL_IF_CONTENT_SCROLLS);

        bridge = new Bridge(this);
        web.addJavascriptInterface(bridge, "Tea");

        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onConsoleMessage(ConsoleMessage m) {
                android.util.Log.i("TeaStrategistWeb", m.message() + " @" + m.lineNumber());
                return true;
            }
        });
        web.setWebViewClient(new android.webkit.WebViewClient() {
            @Override public void onPageFinished(WebView v, String url) {
                pageReady = true;
                if (wantBriefing) { wantBriefing = false; showBriefing(); }
            }
        });

        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT);
        root.addView(web, lp);
        setContentView(root);

        web.loadUrl(HOME);

        Briefing.ensureChannel(this);
        Briefing.schedule(this);
        if (getIntent() != null && getIntent().getBooleanExtra("showBriefing", false)) wantBriefing = true;
    }

    // ------------------------------------------------------------ 通知点进来
    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        if (intent != null && intent.getBooleanExtra("showBriefing", false)) {
            if (pageReady) showBriefing(); else wantBriefing = true;
        }
    }

    private void showBriefing() {
        postJs("window.__showBriefing && window.__showBriefing()");
    }

    // ------------------------------------------------------------ 通知权限
    public boolean hasNotifyPermission() {
        if (Build.VERSION.SDK_INT < 33) return true;
        return checkSelfPermission("android.permission.POST_NOTIFICATIONS") == PackageManager.PERMISSION_GRANTED;
    }

    public void requestNotifyPermission() {
        if (Build.VERSION.SDK_INT < 33) return;
        if (hasNotifyPermission()) return;
        requestPermissions(new String[] { "android.permission.POST_NOTIFICATIONS" }, REQ_NOTIFY);
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] perms, int[] res) {
        super.onRequestPermissionsResult(code, perms, res);
        if (code != REQ_NOTIFY) return;
        boolean ok = res.length > 0 && res[0] == PackageManager.PERMISSION_GRANTED;
        postJs("window.__event && window.__event('notifyPerm','" + (ok ? "granted" : "denied") + "')");
    }

    /** 下一个晨报闹钟大概什么时候（只看设置，给界面显示用） */
    public String nextAlarmText() {
        try {
            boolean on = getSharedPreferences("teastrategist", MODE_PRIVATE)
                    .getBoolean("briefing.on", false);
            if (!on) return "";
            String hhmm = getSharedPreferences("teastrategist", MODE_PRIVATE)
                    .getString("briefing.time", "07:30");
            AlarmManager am = (AlarmManager) getSystemService(ALARM_SERVICE);
            if (am == null) return hhmm;
            return hhmm + "（每天）";
        } catch (Throwable t) { return ""; }
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        try { if (bridge != null) bridge.onActivityResult(req, res, data); } catch (Throwable ignored) { }
    }

    // ------------------------------------------------------------ 给 Bridge 用
    public void postJs(final String js) {
        runOnUiThread(() -> {
            try { web.evaluateJavascript(js, null); }
            catch (Exception e) { android.util.Log.w("TeaStrategistWeb", "postJs " + e); }
        });
    }

    public void pushEvent(String name, String json) {
        postJs("window.__event(" + q(name) + "," + q(json) + ")");
    }

    private static String q(String s) {
        if (s == null) return "''";
        StringBuilder sb = new StringBuilder("'");
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '\\' || c == '\'') sb.append('\\').append(c);
            else if (c == '\n') sb.append("\\n");
            else if (c == '\r') sb.append("\\r");
            else sb.append(c);
        }
        return sb.append('\'').toString();
    }

    @Override
    public boolean onKeyDown(int code, KeyEvent ev) {
        if (code == KeyEvent.KEYCODE_BACK) {
            postJs("window.__back && window.__back()");
            return true;
        }
        return super.onKeyDown(code, ev);
    }

    @Override
    protected void onDestroy() {
        try { if (bridge != null) bridge.shutdown(); } catch (Exception ignored) { }
        super.onDestroy();
    }
}
