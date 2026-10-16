package com.hua.cosmos;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.os.Vibrator;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.ConsoleMessage;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.Toast;

public class MainActivity extends Activity {

    private WebView web;
    private boolean canGoBackInApp = false;
    private long lastBackPress = 0L;

    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        Window w = getWindow();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            w.addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);
            w.setStatusBarColor(Color.parseColor("#0B0F16"));
            w.setNavigationBarColor(Color.parseColor("#0B0F16"));
        }

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.parseColor("#0B0F16"));
        root.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        web = new WebView(this);
        web.setBackgroundColor(Color.parseColor("#0B0F16"));
        web.setLayoutParams(new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        root.addView(web);
        setContentView(root);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setLoadsImagesAutomatically(true);
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(false);
        s.setTextZoom(100);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setMediaPlaybackRequiresUserGesture(false);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.JELLY_BEAN) {
            s.setAllowFileAccessFromFileURLs(true);
            s.setAllowUniversalAccessFromFileURLs(true);
        }

        web.setWebViewClient(new WebViewClient());
        // 把网页里的 console 输出转到 logcat（tag: CosmosJS），排查问题时非常有用
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onConsoleMessage(ConsoleMessage m) {
                android.util.Log.i("CosmosJS", m.message()
                        + " @" + m.sourceId() + ":" + m.lineNumber());
                return true;
            }
        });
        // 允许用 Chrome 的 chrome://inspect / adb 连进来调试（仅本地 adb 可达）
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
            WebView.setWebContentsDebuggingEnabled(true);
        }
        web.addJavascriptInterface(new Bridge(), "Native");
        web.loadUrl("file:///android_asset/www/index.html");
    }

    @Override
    public void onBackPressed() {
        if (canGoBackInApp) {
            web.evaluateJavascript("window.__cosmosBack && window.__cosmosBack();", null);
            return;
        }
        long now = System.currentTimeMillis();
        if (now - lastBackPress < 2000L) {
            super.onBackPressed();
        } else {
            lastBackPress = now;
            toast("再按一次退出");
        }
    }

    private void toast(String msg) {
        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show();
    }

    public class Bridge {

        @JavascriptInterface
        public void setCanBack(boolean can) {
            canGoBackInApp = can;
        }

        @JavascriptInterface
        public void save(String json) {
            SharedPreferences sp = getSharedPreferences("cosmos", Context.MODE_PRIVATE);
            sp.edit().putString("progress", json).apply();
        }

        @JavascriptInterface
        public String load() {
            SharedPreferences sp = getSharedPreferences("cosmos", Context.MODE_PRIVATE);
            return sp.getString("progress", "");
        }

        @JavascriptInterface
        public void clear() {
            SharedPreferences sp = getSharedPreferences("cosmos", Context.MODE_PRIVATE);
            sp.edit().remove("progress").apply();
        }

        @JavascriptInterface
        public void toast(String msg) {
            runOnUiThread(new Runnable() {
                public void run() {
                    MainActivity.this.toast(msg);
                }
            });
        }

        @JavascriptInterface
        public void buzz(int ms) {
            try {
                Vibrator v = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
                if (v != null && v.hasVibrator()) v.vibrate(ms);
            } catch (Throwable ignored) {
            }
        }

        @JavascriptInterface
        public void exitApp() {
            runOnUiThread(new Runnable() {
                public void run() {
                    finish();
                }
            });
        }

        @JavascriptInterface
        public String info() {
            return Build.MANUFACTURER + " " + Build.MODEL + " / API " + Build.VERSION.SDK_INT;
        }
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.destroy();
            web = null;
        }
        super.onDestroy();
    }
}
