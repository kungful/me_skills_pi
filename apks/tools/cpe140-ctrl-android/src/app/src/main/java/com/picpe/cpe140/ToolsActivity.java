package com.picpe.cpe140;

import android.app.Activity;
import android.app.DownloadManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

/**
 * 网页工具箱 —— 直接加载设备端的 /tools.html。
 *
 * 为什么不把这套功能用 Java 重写一遍：
 *   设备端（/www/cgi-bin/tools）本身就以 root 执行，抓包/WoL/自愈/加固/命令台
 *   全在那边；App 里再实现一份只会双份维护、还容易跟固件版本对不上。
 *   这里只做"容器"，并把 pcap 下载接到系统下载管理器。
 */
public class ToolsActivity extends Activity {

    private WebView wv;
    private TextView bar;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        String host = getIntent().getStringExtra("host");
        if (host == null || host.isEmpty()) host = "192.168.188.254";
        final String url = "http://" + host + "/tools.html";

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.parseColor("#0f1115"));

        bar = new TextView(this);
        bar.setText("  " + url);
        bar.setTextColor(Color.parseColor("#8b93a7"));
        bar.setTextSize(11f);
        bar.setPadding(10, 10, 10, 10);
        bar.setOnClickListener(v -> wv.reload());
        root.addView(bar, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        wv = new WebView(this);
        WebSettings s = wv.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);
        s.setCacheMode(WebSettings.LOAD_NO_CACHE);
        wv.setBackgroundColor(Color.parseColor("#0f1115"));
        wv.setWebViewClient(new WebViewClient());
        wv.setWebChromeClient(new WebChromeClient());
        CookieManager.getInstance().setAcceptCookie(true);
        wv.setDownloadListener(new DownloadListener() {
            @Override
            public void onDownloadStart(String u, String ua, String cd, String mime, long len) {
                try {
                    DownloadManager.Request r = new DownloadManager.Request(Uri.parse(u));
                    String name = "cpe140.pcap";
                    if (cd != null && cd.contains("filename=")) {
                        name = cd.substring(cd.indexOf("filename=") + 9).trim().replace("\"", "");
                    }
                    r.setTitle(name);
                    r.setMimeType(mime == null ? "application/octet-stream" : mime);
                    r.setNotificationVisibility(
                            DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                    ((DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE)).enqueue(r);
                    Toast.makeText(ToolsActivity.this, "开始下载 " + name, Toast.LENGTH_SHORT).show();
                } catch (Exception e) {
                    try {
                        startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(u)));
                    } catch (Exception e2) {
                        Toast.makeText(ToolsActivity.this, "下载失败: " + e.getMessage(),
                                Toast.LENGTH_LONG).show();
                    }
                }
            }
        });
        root.addView(wv, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        setContentView(root);
        wv.loadUrl(url);
    }

    @Override
    public void onBackPressed() {
        if (wv != null && wv.canGoBack()) wv.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        if (wv != null) {
            wv.loadUrl("about:blank");
            wv.destroy();
            wv = null;
        }
        super.onDestroy();
    }
}
