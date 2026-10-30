package com.hua.subhunter;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {

    private WebView web;
    private Bridge bridge;

    @SuppressWarnings("deprecation")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            Window w = getWindow();
            w.clearFlags(WindowManager.LayoutParams.FLAG_TRANSLUCENT_STATUS);
            w.setStatusBarColor(Color.parseColor("#0B1017"));
            w.setNavigationBarColor(Color.parseColor("#0B1017"));
        }

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);
        s.setUseWideViewPort(false);
        s.setLoadWithOverviewMode(false);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setTextZoom(100);
        try {
            s.setAllowFileAccessFromFileURLs(true);
            s.setAllowUniversalAccessFromFileURLs(true);
        } catch (Throwable ignore) {
        }

        web.setBackgroundColor(Color.parseColor("#0B1017"));
        web.setOverScrollMode(View.OVER_SCROLL_NEVER);
        web.setVerticalScrollBarEnabled(false);
        web.setHorizontalScrollBarEnabled(false);
        web.setWebViewClient(new WebViewClient());
        web.setWebChromeClient(new WebChromeClient());
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
            WebView.setWebContentsDebuggingEnabled(false);
        }

        setContentView(web);
        bridge = new Bridge(this, web);
        web.addJavascriptInterface(bridge, "Native");
        web.loadUrl("file:///android_asset/index.html");

        Sched.ensureChannel(this);
        Store st = Store.get(this);
        // 上次开着本机订阅服务就自动拉起来，保证订阅地址长期可用
        if (st.boolOf("serverWanted", false) || Hub.serverRunning()) {
            SubService.startServer(this);
        }
        Sched.reschedule(this);
        requestNotifPermissionQuiet();
    }

    @Override
    protected void onResume() {
        super.onResume();
        // 抓取期间切到别的 App，WebView 的 JS 回调会被丢掉；回来时强制对齐一次状态
        if (web != null) {
            try {
                web.evaluateJavascript("window.__onResume&&window.__onResume()", null);
            } catch (Throwable ignore) {
            }
        }
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            if (web != null && web.canGoBack()) {
                web.goBack();
                return true;
            }
        }
        return super.onKeyDown(keyCode, event);
    }

    void requestNotifPermission() {
        if (Build.VERSION.SDK_INT >= 33) {
            try {
                requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 2001);
            } catch (Throwable ignore) {
            }
        }
    }

    private void requestNotifPermissionQuiet() {
        if (Build.VERSION.SDK_INT >= 33) {
            try {
                if (checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                    requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 2001);
                }
            } catch (Throwable ignore) {
            }
        }
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            try {
                web.removeJavascriptInterface("Native");
            } catch (Throwable ignore) {
            }
        }
        super.onDestroy();
    }
}
