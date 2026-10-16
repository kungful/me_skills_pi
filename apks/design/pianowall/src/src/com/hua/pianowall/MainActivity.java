package com.hua.pianowall;

import android.app.Activity;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.MediaStore;
import android.util.Base64;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.widget.FrameLayout;
import android.widget.Toast;

import java.io.OutputStream;

/**
 * 钢琴墙 3D 演示 —— 一个 WebView 壳子。
 * 页面（assets/index.html）是全部逻辑：Three.js 三维演示 + Canvas 图纸。
 * 原生这边只做两件事：全屏承载 WebView、把页面导出的 PNG 存进系统相册。
 */
public class MainActivity extends Activity {

    private WebView web;
    private static final String HOME = "file:///android_asset/index.html";

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
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(false);
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        web.setBackgroundColor(0xFF0D1117);
        web.setHorizontalScrollBarEnabled(false);
        web.setVerticalScrollBarEnabled(false);
        web.setOverScrollMode(View.OVER_SCROLL_NEVER);
        web.setWebChromeClient(new WebChromeClient());
        web.addJavascriptInterface(new Bridge(), "AndroidSAVE");
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
            WebView.setWebContentsDebuggingEnabled(true);
        }
        root.addView(web, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(root);

        if (savedInstanceState != null) {
            web.restoreState(savedInstanceState);
        } else {
            web.loadUrl(HOME);
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        if (web != null) web.saveState(out);
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }

    /* ---------------- 页面 → 原生 ---------------- */
    public class Bridge {

        /** 把 data:image/png;base64,... 存到相册 Pictures/PianoWall */
        @JavascriptInterface
        public void savePng(String name, String dataUrl) {
            String path = null;
            try {
                int comma = dataUrl.indexOf(',');
                String b64 = comma >= 0 ? dataUrl.substring(comma + 1) : dataUrl;
                byte[] bytes = Base64.decode(b64, Base64.DEFAULT);
                path = save(bytes, name);
            } catch (Throwable t) {
                path = null;
            }
            final String msg = path != null
                    ? "已保存到相册 Pictures/PianoWall\n" + path
                    : "保存失败";
            runOnUiThread(new Runnable() {
                public void run() { Toast.makeText(MainActivity.this, msg, Toast.LENGTH_LONG).show(); }
            });
        }

        @JavascriptInterface
        public void toast(final String text) {
            runOnUiThread(new Runnable() {
                public void run() { Toast.makeText(MainActivity.this, text, Toast.LENGTH_SHORT).show(); }
            });
        }
    }

    private String save(byte[] bytes, String name) throws Exception {
        String file = (name == null || name.trim().isEmpty() ? "PianoWall" : name.trim());
        if (!file.toLowerCase().endsWith(".png")) file = file + ".png";
        // 校验能解码，避免存进坏图
        Bitmap bm = BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
        if (bm == null) throw new Exception("bad png");

        ContentResolver cr = getContentResolver();
        ContentValues v = new ContentValues();
        v.put(MediaStore.Images.Media.DISPLAY_NAME, file);
        v.put(MediaStore.Images.Media.MIME_TYPE, "image/png");
        v.put(MediaStore.Images.Media.WIDTH, bm.getWidth());
        v.put(MediaStore.Images.Media.HEIGHT, bm.getHeight());
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            v.put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/PianoWall");
            v.put(MediaStore.Images.Media.IS_PENDING, 1);
        }
        Uri uri = cr.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, v);
        if (uri == null) throw new Exception("insert failed");
        OutputStream os = cr.openOutputStream(uri);
        os.write(bytes);
        os.flush();
        os.close();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ContentValues done = new ContentValues();
            done.put(MediaStore.Images.Media.IS_PENDING, 0);
            cr.update(uri, done, null, null);
        }
        return uri.toString();
    }
}
