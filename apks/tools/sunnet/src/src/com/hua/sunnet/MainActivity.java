package com.hua.sunnet;

import android.Manifest;
import android.app.Activity;
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
import android.widget.Toast;

import java.util.ArrayList;
import java.util.List;

/**
 * 太阳网控制器 —— WebView 壳子 + 原生网络桥。
 *
 * 页面（assets/）只负责画界面，一切网络访问（WiFi/HTTP 与 BLE）都走
 * Bridge.invoke()，所以没有跨域问题，也不需要 WebView 直连设备。
 */
public class MainActivity extends Activity {

    private static final String HOME = "file:///android_asset/index.html";
    private static final int REQ_PERM = 1001;

    private WebView web;
    private Bridge bridge;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestWindowFeature(Window.FEATURE_NO_TITLE);

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(0xFF0D1117);

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
        web.setBackgroundColor(0xFF0D1117);
        web.setVerticalScrollBarEnabled(true);
        web.setOverScrollMode(View.OVER_SCROLL_IF_CONTENT_SCROLLS);

        bridge = new Bridge(this);
        web.addJavascriptInterface(bridge, "SunNet");

        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onConsoleMessage(ConsoleMessage m) {
                android.util.Log.i("SunNetWeb", m.message() + " @" + m.lineNumber());
                return true;
            }
        });

        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT);
        root.addView(web, lp);
        setContentView(root);

        web.loadUrl(HOME);

        // 蓝牙权限：进来自动问一次（可在设置里拒绝，页面上有按钮重新问）
        requestBlePermissions(false);
    }

    // ------------------------------------------------------------ 权限
    public void requestBlePermissions() { requestBlePermissions(true); }

    private void requestBlePermissions(boolean toast) {
        List<String> need = new ArrayList<>();
        if (Build.VERSION.SDK_INT >= 31) {
            if (checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN) != PackageManager.PERMISSION_GRANTED)
                need.add(Manifest.permission.BLUETOOTH_SCAN);
            if (checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED)
                need.add(Manifest.permission.BLUETOOTH_CONNECT);
        } else {
            if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED)
                need.add(Manifest.permission.ACCESS_FINE_LOCATION);
        }
        if (need.isEmpty()) {
            if (toast) runOnUiThread(() -> Toast.makeText(this, "蓝牙权限已就绪", Toast.LENGTH_SHORT).show());
            return;
        }
        requestPermissions(need.toArray(new String[0]), REQ_PERM);
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] perms, int[] res) {
        super.onRequestPermissionsResult(code, perms, res);
        if (code != REQ_PERM) return;
        int ok = 0;
        for (int r : res) if (r == PackageManager.PERMISSION_GRANTED) ok++;
        Toast.makeText(this, ok == res.length ? "蓝牙权限已授予，可以扫设备了"
                : "权限被拒；只能用 WiFi 通道（要连设备热点）", Toast.LENGTH_LONG).show();
        pushEvent("conn", "{\"state\":\"perm\"}");
    }

    // ------------------------------------------------------------ 给 Bridge 用
    public void postJs(final String js) {
        runOnUiThread(() -> {
            try { web.evaluateJavascript(js, null); }
            catch (Exception e) { android.util.Log.w("SunNetWeb", "postJs " + e); }
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
