package com.hua.canopystruct;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.webkit.JavascriptInterface;

import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.util.Iterator;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * JS ↔ 原生 的小桥。
 *
 * 页面调：Hua.invoke(reqId, op, jsonArgs)
 * 原生回：window.__apiResult(reqId, ok(1/0), payload)
 *
 * op：
 *   status                          设备信息
 *   store.set {key,value}           存参数
 *   store.get {key,default}         → {ok,value}
 *   store.all                       → {ok, k:v…}
 *   store.del {key}
 *   copy {text}                     写剪贴板
 *   save  {name,text}               导出到 外部私有目录/导出 → {ok,path,bytes}
 *   share {title,text}              系统分享
 *   open  {url}                     浏览器打开
 *   exit                            退出
 */
public class Bridge {

    private static final String SP = "canopystruct";

    private final MainActivity act;
    private final SharedPreferences sp;
    private final ExecutorService pool = Executors.newFixedThreadPool(2);
    private final Handler ui = new Handler(Looper.getMainLooper());

    public Bridge(MainActivity a) {
        this.act = a;
        this.sp = a.getSharedPreferences(SP, Context.MODE_PRIVATE);
    }

    // ---------------------------------------------------------------- 回调
    private void deliver(String reqId, boolean ok, String payload) {
        String js = "window.__apiResult(" + q(reqId) + "," + (ok ? "1" : "0") + "," + q(payload == null ? "" : payload) + ")";
        act.postJs(js);
    }

    private static String q(String s) {
        StringBuilder sb = new StringBuilder("'");
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '\\': sb.append("\\\\"); break;
                case '\'': sb.append("\\'"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\u2028': sb.append("\\u2028"); break;
                case '\u2029': sb.append("\\u2029"); break;
                default: sb.append(c);
            }
        }
        return sb.append('\'').toString();
    }

    // ---------------------------------------------------------------- 入口
    @JavascriptInterface
    public void invoke(String reqId, String op, String argsJson) {
        try {
            JSONObject a = new JSONObject(argsJson == null || argsJson.isEmpty() ? "{}" : argsJson);
            switch (op == null ? "" : op) {
                case "status": {
                    JSONObject o = new JSONObject();
                    o.put("ok", true);
                    o.put("app", "棚架受力分析");
                    o.put("version", "1.0");
                    o.put("sdk", Build.VERSION.SDK_INT);
                    o.put("model", Build.MANUFACTURER + " " + Build.MODEL);
                    o.put("android", Build.VERSION.RELEASE);
                    deliver(reqId, true, o.toString());
                    return;
                }
                case "store.set": {
                    sp.edit().putString(a.optString("key", "k"), a.optString("value", "")).apply();
                    deliver(reqId, true, "{\"ok\":true}");
                    return;
                }
                case "store.get": {
                    JSONObject o = new JSONObject();
                    o.put("ok", true);
                    o.put("value", sp.getString(a.optString("key", ""), a.optString("default", "")));
                    deliver(reqId, true, o.toString());
                    return;
                }
                case "store.all": {
                    JSONObject o = new JSONObject();
                    o.put("ok", true);
                    for (Map.Entry<String, ?> e : sp.getAll().entrySet())
                        o.put(e.getKey(), e.getValue() == null ? "" : String.valueOf(e.getValue()));
                    deliver(reqId, true, o.toString());
                    return;
                }
                case "store.del": {
                    sp.edit().remove(a.optString("key", "")).apply();
                    deliver(reqId, true, "{\"ok\":true}");
                    return;
                }
                case "copy": {
                    final String text = a.optString("text", "");
                    ui.post(() -> {
                        try {
                            ClipboardManager cm = (ClipboardManager) act.getSystemService(Context.CLIPBOARD_SERVICE);
                            cm.setPrimaryClip(ClipData.newPlainText("棚架受力分析", text));
                            deliver(reqId, true, "{\"ok\":true}");
                        } catch (Throwable t) { deliver(reqId, false, "复制失败: " + t.getMessage()); }
                    });
                    return;
                }
                case "save": {
                    final String name = a.optString("name", "棚架受力报告.md");
                    final String text = a.optString("text", "");
                    pool.execute(() -> {
                        try {
                            File dir = act.getExternalFilesDir(null);
                            if (dir == null) dir = act.getFilesDir();
                            File out = new File(dir, "导出");
                            if (!out.exists()) out.mkdirs();
                            File f = new File(out, safe(name));
                            FileOutputStream fo = new FileOutputStream(f);
                            fo.write(text.getBytes("UTF-8"));
                            fo.flush(); fo.close();
                            JSONObject o = new JSONObject();
                            o.put("ok", true); o.put("path", f.getAbsolutePath()); o.put("bytes", f.length());
                            deliver(reqId, true, o.toString());
                        } catch (Exception e) { deliver(reqId, false, "保存失败: " + e.getMessage()); }
                    });
                    return;
                }
                case "share": {
                    final String title = a.optString("title", "棚架受力分析");
                    final String text = a.optString("text", "");
                    ui.post(() -> {
                        try {
                            Intent i = new Intent(Intent.ACTION_SEND);
                            i.setType("text/plain");
                            i.putExtra(Intent.EXTRA_SUBJECT, title);
                            i.putExtra(Intent.EXTRA_TEXT, text);
                            Intent c = Intent.createChooser(i, "分享到");
                            c.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                            act.startActivity(c);
                            deliver(reqId, true, "{\"ok\":true}");
                        } catch (Throwable t) { deliver(reqId, false, "分享失败: " + t.getMessage()); }
                    });
                    return;
                }
                case "open": {
                    final String url = a.optString("url", "");
                    ui.post(() -> {
                        try {
                            Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                            act.startActivity(i);
                            deliver(reqId, true, "{\"ok\":true}");
                        } catch (Throwable t) { deliver(reqId, false, "打不开"); }
                    });
                    return;
                }
                case "exit": {
                    deliver(reqId, true, "{\"ok\":true}");
                    ui.post(() -> act.finish());
                    return;
                }
                default:
                    deliver(reqId, false, "未知 op: " + op);
            }
        } catch (Exception e) {
            deliver(reqId, false, "调用失败: " + e);
        }
    }

    private static String safe(String n) {
        String s = n.replaceAll("[\\\\/:*?\"<>|]", "_");
        if (s.length() > 80) s = s.substring(0, 80);
        return s.isEmpty() ? "report.md" : s;
    }

    public void shutdown() { pool.shutdownNow(); }
}
