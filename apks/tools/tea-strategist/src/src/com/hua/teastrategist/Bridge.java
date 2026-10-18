package com.hua.teastrategist;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.util.Log;
import android.webkit.JavascriptInterface;

import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.util.Iterator;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * 页面（assets/app.js）与原生之间的唯一通道。
 *
 * 页面只做一件事：window.Tea.invoke(reqId, op, argsJson)
 * 原生做完异步活，再 window.__apiResult(reqId, ok, payload) 回吐。
 *   ok = 1 → payload 是接口返回的 JSON 文本
 *   ok = 0 → payload 是错误原因（纯文本）
 *
 * op 一览：
 *   status                              设备/版本信息
 *   http   {"url":"…","method":"GET","headers":{…},"body":"…",
 *           "encoding":"gbk","timeout":15}
 *                                       → {"status":200,"charset":"…","body":"…","headers":{…}}
 *   store.set {"key":"k","value":"v"}    写本地设置
 *   store.get {"key":"k"}                读（缺省返回 ""）
 *   store.all                            全量读出 → {k:v,…}
 *   store.del {"key":"k"}
 *   copy {"text":"…"}                    写剪贴板
 *   paste                                读剪贴板 → {ok,text}
 *   open {"url":"…"}                     用浏览器打开
 *   save {"name":"a.md","text":"…"}      存到 App 导出目录 → {ok,path}
 *   share {"title":"…","text":"…"}       系统分享（微信等）
 *   io.read  {"name":"ledger.json"}       读 App 私有文档
 *   io.write {"name":"ledger.json","text":"…"}
 *   briefing.get                         → {ok,text,time}
 *   briefing.run {"ai":true}             立刻生成一份 → {ok,text,time}
 *   briefing.set {"on":true,"time":"07:30","ai":true,"notify":true}
 *   briefing.state                       → {ok,on,time,ai,notify,perm}
 *   notify.perm                          申请通知权限
 *   notify.test                          发一条测试通知
 *   exit                                 退出
 */
public class Bridge {

    private static final String TAG = "TeaStrategistBridge";
    private static final String SP = "teastrategist";

    private final MainActivity act;
    private final ExecutorService pool = Executors.newFixedThreadPool(4);
    private final SharedPreferences sp;

    public Bridge(MainActivity a) {
        this.act = a;
        this.sp = a.getSharedPreferences(SP, Context.MODE_PRIVATE);
    }

    // ------------------------------------------------------------ 结果回调
    public static class ResultCb {
        private final AtomicBoolean fired = new AtomicBoolean(false);
        private final Bridge b;
        private final String reqId;
        ResultCb(Bridge b, String reqId) { this.b = b; this.reqId = reqId; }

        public void done(boolean ok, String payload) {
            if (!fired.compareAndSet(false, true)) return;
            b.deliver(reqId, ok, payload);
        }
        public void ok(String json) { done(true, json); }
        public void err(String msg) { done(false, msg); }
    }

    private void deliver(String reqId, boolean ok, String payload) {
        String js = "window.__apiResult(" + jsStr(reqId) + "," + (ok ? "1" : "0") + ","
                + jsStr(payload == null ? "" : payload) + ")";
        act.postJs(js);
    }

    private static String jsStr(String s) {
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

    // ------------------------------------------------------------ 入口
    @JavascriptInterface
    public void invoke(String reqId, String op, String argsJson) {
        ResultCb cb = new ResultCb(this, reqId);
        JSONObject a;
        try { a = new JSONObject(argsJson == null || argsJson.isEmpty() ? "{}" : argsJson); }
        catch (Exception e) { cb.err("参数不是 JSON"); return; }

        try {
            switch (op) {
                case "status": cb.ok(statusJson()); return;

                case "http": {
                    final String url = a.optString("url", "").trim();
                    if (url.isEmpty()) { cb.err("缺少 url"); return; }
                    if (!url.startsWith("http://") && !url.startsWith("https://")) {
                        cb.err("只支持 http/https"); return;
                    }
                    final String method = a.optString("method", "GET");
                    final String body = a.optString("body", "");
                    final String enc = a.optString("encoding", "");
                    final int timeout = a.optInt("timeout", 15);
                    final java.util.HashMap<String, String> hdrs = new java.util.HashMap<>();
                    JSONObject h = a.optJSONObject("headers");
                    if (h != null) {
                        for (Iterator<String> it = h.keys(); it.hasNext(); ) {
                            String k = it.next();
                            hdrs.put(k, h.optString(k, ""));
                        }
                    }
                    pool.execute(() -> {
                        try {
                            Net.Res r = Net.fetch(url, method, hdrs, body.isEmpty() ? null : body, enc, timeout);
                            JSONObject o = new JSONObject();
                            o.put("status", r.status);
                            o.put("charset", r.charset == null ? "" : r.charset);
                            o.put("body", r.body == null ? "" : r.body);
                            JSONObject ho = new JSONObject();
                            for (Map.Entry<String, String> e : r.headers.entrySet()) ho.put(e.getKey(), e.getValue());
                            o.put("headers", ho);
                            cb.ok(o.toString());
                        } catch (Exception e) {
                            cb.err("请求失败: " + e.getClass().getSimpleName()
                                    + (e.getMessage() == null ? "" : (" " + e.getMessage())));
                        }
                    });
                    return;
                }

                case "store.set": {
                    String k = a.optString("key", "");
                    if (k.isEmpty()) { cb.err("缺 key"); return; }
                    sp.edit().putString(k, a.optString("value", "")).apply();
                    cb.ok("{\"ok\":true}");
                    return;
                }
                case "store.get": {
                    String k = a.optString("key", "");
                    String v = sp.getString(k, a.optString("default", ""));
                    JSONObject o = new JSONObject();
                    o.put("ok", true);
                    o.put("value", v == null ? "" : v);
                    cb.ok(o.toString());
                    return;
                }
                case "store.all": {
                    JSONObject o = new JSONObject();
                    o.put("ok", true);
                    for (Map.Entry<String, ?> e : sp.getAll().entrySet()) {
                        o.put(e.getKey(), e.getValue() == null ? "" : String.valueOf(e.getValue()));
                    }
                    cb.ok(o.toString());
                    return;
                }
                case "store.del": {
                    sp.edit().remove(a.optString("key", "")).apply();
                    cb.ok("{\"ok\":true}");
                    return;
                }

                case "copy": {
                    final String text = a.optString("text", "");
                    act.runOnUiThread(() -> {
                        try {
                            ClipboardManager cm = (ClipboardManager) act.getSystemService(Context.CLIPBOARD_SERVICE);
                            cm.setPrimaryClip(ClipData.newPlainText("茶叶军师", text));
                            cb.ok("{\"ok\":true}");
                        } catch (Throwable t) { cb.err("复制失败: " + t.getMessage()); }
                    });
                    return;
                }
                case "paste": {
                    act.runOnUiThread(() -> {
                        try {
                            ClipboardManager cm = (ClipboardManager) act.getSystemService(Context.CLIPBOARD_SERVICE);
                            if (cm == null || !cm.hasPrimaryClip() || cm.getPrimaryClip().getItemCount() <= 0) {
                                cb.err("剪贴板是空的"); return;
                            }
                            CharSequence cs = cm.getPrimaryClip().getItemAt(0).coerceToText(act);
                            String t = cs == null ? "" : cs.toString();
                            if (t.isEmpty()) { cb.err("剪贴板里没有文字"); return; }
                            cb.ok("{\"ok\":true,\"text\":" + JSONObject.quote(t) + "}");
                        } catch (Throwable e) { cb.err("读剪贴板失败: " + e.getMessage()); }
                    });
                    return;
                }

                case "open": {
                    final String url = a.optString("url", "");
                    if (url.isEmpty()) { cb.err("空链接"); return; }
                    act.runOnUiThread(() -> {
                        try {
                            Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                            act.startActivity(i);
                            cb.ok("{\"ok\":true}");
                        } catch (Throwable t) { cb.err("打不开（没有可用的浏览器）"); }
                    });
                    return;
                }

                case "save": {
                    final String name = a.optString("name", "茶叶军师报告.md");
                    final String text = a.optString("text", "");
                    pool.execute(() -> {
                        try {
                            File dir = act.getExternalFilesDir(null);
                            if (dir == null) dir = act.getFilesDir();
                            File out = new File(dir, "导出");
                            if (!out.exists()) out.mkdirs();
                            File f = new File(out, safeName(name));
                            FileOutputStream fo = new FileOutputStream(f);
                            fo.write(text.getBytes("UTF-8"));
                            fo.flush();
                            fo.close();
                            JSONObject o = new JSONObject();
                            o.put("ok", true);
                            o.put("path", f.getAbsolutePath());
                            o.put("bytes", f.length());
                            cb.ok(o.toString());
                        } catch (Exception e) { cb.err("保存失败: " + e.getMessage()); }
                    });
                    return;
                }

                case "share": {
                    final String title = a.optString("title", "茶叶军师");
                    final String text = a.optString("text", "");
                    act.runOnUiThread(() -> {
                        try {
                            Intent i = new Intent(Intent.ACTION_SEND);
                            i.setType("text/plain");
                            i.putExtra(Intent.EXTRA_SUBJECT, title);
                            i.putExtra(Intent.EXTRA_TEXT, text);
                            Intent c = Intent.createChooser(i, "分享到");
                            c.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                            act.startActivity(c);
                            cb.ok("{\"ok\":true}");
                        } catch (Throwable t) { cb.err("分享失败: " + t.getMessage()); }
                    });
                    return;
                }

                case "io.read": {
                    final String name = a.optString("name", "");
                    if (name.isEmpty()) { cb.err("缺 name"); return; }
                    pool.execute(() -> {
                        try {
                            JSONObject o = new JSONObject();
                            o.put("ok", true);
                            o.put("text", Io.read(act, name));
                            cb.ok(o.toString());
                        } catch (Exception e) { cb.err("读失败: " + e.getMessage()); }
                    });
                    return;
                }
                case "io.write": {
                    final String name = a.optString("name", "");
                    final String text = a.optString("text", "");
                    if (name.isEmpty()) { cb.err("缺 name"); return; }
                    pool.execute(() -> {
                        try {
                            long n = Io.write(act, name, text);
                            JSONObject o = new JSONObject();
                            o.put("ok", true);
                            o.put("bytes", n);
                            cb.ok(o.toString());
                        } catch (Exception e) { cb.err("写失败: " + e.getMessage()); }
                    });
                    return;
                }

                case "briefing.get": {
                    JSONObject o = new JSONObject();
                    o.put("ok", true);
                    o.put("text", sp.getString(Briefing.KEY_LATEST, ""));
                    o.put("time", sp.getString(Briefing.KEY_TIME, ""));
                    cb.ok(o.toString());
                    return;
                }
                case "briefing.run": {
                    final boolean ai = a.optBoolean("ai", true);
                    pool.execute(() -> {
                        try {
                            String text = Briefing.build(act, ai && !sp.getString("mKey", "").isEmpty());
                            String tm = new java.text.SimpleDateFormat("yyyy-MM-dd HH:mm")
                                    .format(new java.util.Date());
                            sp.edit().putString(Briefing.KEY_LATEST, text)
                                     .putString(Briefing.KEY_TIME, tm).apply();
                            JSONObject o = new JSONObject();
                            o.put("ok", true);
                            o.put("text", text);
                            o.put("time", tm);
                            cb.ok(o.toString());
                        } catch (Exception e) { cb.err("生成失败: " + e.getMessage()); }
                    });
                    return;
                }
                case "briefing.set": {
                    sp.edit()
                      .putBoolean("briefing.on", a.optBoolean("on", false))
                      .putString("briefing.time", a.optString("time", "07:30"))
                      .putBoolean("briefing.ai", a.optBoolean("ai", true))
                      .putBoolean("briefing.notify", a.optBoolean("notify", true))
                      .apply();
                    Briefing.schedule(act);
                    cb.ok(briefingState());
                    return;
                }
                case "briefing.state": cb.ok(briefingState()); return;

                case "notify.perm": {
                    act.requestNotifyPermission();
                    cb.ok("{\"ok\":true}");
                    return;
                }
                case "notify.test": {
                    Briefing.notify(act, "茶叶军师", "通知能正常工作。晨报到点会像这样推给你。");
                    cb.ok("{\"ok\":true}");
                    return;
                }

                case "exit": {
                    cb.ok("{\"ok\":true}");
                    act.finish();
                    return;
                }

                default: cb.err("未知 op: " + op);
            }
        } catch (Exception e) {
            cb.err("调用失败: " + e);
        }
    }

    private String briefingState() {
        JSONObject o = new JSONObject();
        try {
            o.put("ok", true);
            o.put("on", sp.getBoolean("briefing.on", false));
            o.put("time", sp.getString("briefing.time", "07:30"));
            o.put("ai", sp.getBoolean("briefing.ai", true));
            o.put("notify", sp.getBoolean("briefing.notify", true));
            o.put("perm", act.hasNotifyPermission());
            o.put("next", act.nextAlarmText());
        } catch (Exception ignored) { }
        return o.toString();
    }

    private static String safeName(String n) {
        String s = n.replaceAll("[\\\\/:*?\"<>|]", "_");
        if (s.length() > 80) s = s.substring(0, 80);
        return s.isEmpty() ? "report.md" : s;
    }

    public void onActivityResult(int req, int res, Intent data) { /* 目前无文件选择需求 */ }

    // ------------------------------------------------------------ 状态
    public String statusJson() {
        JSONObject o = new JSONObject();
        try {
            o.put("ok", true);
            o.put("app", "茶叶军师");
            o.put("version", "1.0");
            o.put("sdk", Build.VERSION.SDK_INT);
            o.put("model", Build.MANUFACTURER + " " + Build.MODEL);
            o.put("android", Build.VERSION.RELEASE);
        } catch (Exception ignored) { }
        return o.toString();
    }

    public void shutdown() { pool.shutdownNow(); }

    public Context ctx() { return act; }
}
