package com.hua.canopystruct;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.ActivityInfo;
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
 * 棚架受力分析 —— 占位说明见 assets/index.html。
 *
 * 页面上是纯 JS 的力学求解器（平面桁架/刚架矩阵位移法 + 风荷载规范计算），
 * 三维视图用本地 three.js（WebGL）。原生层只做 WebView 壳子和一个
 * 很小的桥：存参数、导出报告、分享、剪贴板。
 */
public class MainActivity extends Activity {

    private static final String HOME = "file:///android_asset/index.html";

    private WebView web;
    private Bridge bridge;
    private boolean pageReady = false;
    private String pendingJs = null;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        // 三维是横屏好看，但手机在看参数表时竖屏舒服 —— 允许自由旋转
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_FULL_SENSOR);

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(0xFF0B1014);

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
        s.setJavaScriptCanOpenWindowsAutomatically(false);
        if (Build.VERSION.SDK_INT >= 21) s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        if (Build.VERSION.SDK_INT >= 26) s.setSafeBrowsingEnabled(false);
        web.setBackgroundColor(0xFF0B1014);
        web.setVerticalScrollBarEnabled(false);
        web.setHorizontalScrollBarEnabled(false);
        web.setOverScrollMode(View.OVER_SCROLL_NEVER);
        // 注意：不要给 WebView 设 LAYER_TYPE_HARDWARE —— 会让 WebGL(three.js) 白屏

        bridge = new Bridge(this);
        web.addJavascriptInterface(bridge, "Hua");

        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onConsoleMessage(ConsoleMessage m) {
                android.util.Log.i("CanopyStructWeb", m.message() + " @" + m.lineNumber());
                return true;
            }
        });
        web.setWebViewClient(new android.webkit.WebViewClient() {
            @Override public void onPageFinished(WebView v, String url) {
                pageReady = true;
                if (pendingJs != null) { String j = pendingJs; pendingJs = null; web.evaluateJavascript(j, null); }
            }
        });

        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT);
        root.addView(web, lp);
        setContentView(root);
        web.loadUrl(HOME);
    }

    public void postJs(final String js) {
        runOnUiThread(() -> {
            try {
                if (!pageReady) { pendingJs = js; return; }
                web.evaluateJavascript(js, null);
            } catch (Exception e) { android.util.Log.w("CanopyStructWeb", "postJs " + e); }
        });
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
