package com.hua.sunnet;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.util.Log;
import android.webkit.JavascriptInterface;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * 前端（assets/app.js）与原生之间的唯一通道。
 *
 * 页面只做一件事：window.SunNet.invoke(reqId, op, argsJson)
 * 原生做完异步活，再 window.__apiResult(reqId, ok, payload) 回吐。
 *   ok = 1 → payload 是接口返回的 JSON 文本
 *   ok = 0 → payload 是错误原因（纯文本）
 *
 * op 一览：
 *   status                 当前连接状态
 *   wifi  {"host":"192.168.4.1"}        切到 WiFi/HTTP 通道
 *   ble.scan {"ms":6000}                扫 BLE，回 [{id,name,rssi,ours}]
 *   ble.connect {"id":"AA:BB:.."}       连 BLE
 *   ble.disconnect                      断 BLE
 *   get  {"path":"/api/state"}          读接口
 *   post {"path":"/api/cmd","body":"{…}"} 发命令
 *   copy {"text":"…"}                   写剪贴板
 *   paste                               读剪贴板 → {ok,text}
 *   pick {"mime":"application/json"}     选文件读文本 → {ok,name,text}
 */
public class Bridge {

    private static final String TAG = "SunNetBridge";

    private final MainActivity act;
    private final BleClient ble;
    private final ExecutorService pool = Executors.newFixedThreadPool(3);

    private String mode = "none";     // none | http | ble
    private String host = "192.168.4.1";
    private int port = 80;

    static final int REQ_PICK = 9002;      // 选文件
    private ResultCb pickCb;

    public Bridge(MainActivity a) {
        this.act = a;
        this.ble = new BleClient(a, new BleClient.Sink() {
            @Override public void onEvent(String json) { act.pushEvent("conn", json); }
            @Override public void onLog(String line) { Log.i(TAG, line); }
        });
    }

    public BleClient ble() { return ble; }

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
        Log.i(TAG, "invoke " + op + " " + argsJson);
        ResultCb cb = new ResultCb(this, reqId);
        try {
            switch (op) {
                case "status": cb.ok(statusJson()); return;
                case "wifi": {
                    JSONObject a = new JSONObject(argsJson == null ? "{}" : argsJson);
                    String h = a.optString("host", "").trim();
                    if (h.isEmpty()) { cb.err("请填 IP 或主机名"); return; }
                    if (h.contains("://")) { cb.err("只填 IP，不要带 http://"); return; }
                    if (h.contains("/")) h = h.substring(0, h.indexOf('/'));
                    if (h.contains(":")) {
                        int i = h.lastIndexOf(':');
                        try { port = Integer.parseInt(h.substring(i + 1)); } catch (Exception ignored) { }
                        h = h.substring(0, i);
                    } else port = 80;
                    host = h;
                    mode = "http";
                    ble.disconnect();
                    act.pushEvent("conn", "{\"state\":\"connected\",\"mode\":\"http\",\"name\":\""
                            + host + ":" + port + "\"}");
                    cb.ok("{\"ok\":true,\"mode\":\"http\",\"host\":\"" + host + "\",\"port\":" + port + "}");
                    return;
                }
                case "ble.scan": {
                    JSONObject a = new JSONObject(argsJson == null ? "{}" : argsJson);
                    final int ms = a.optInt("ms", 6000);
                    mode = "ble";
                    ble.scan(ms, cb);
                    return;
                }
                case "ble.connect": {
                    JSONObject a = new JSONObject(argsJson == null ? "{}" : argsJson);
                    final String id = a.optString("id", "");
                    if (id.isEmpty()) { cb.err("缺设备地址"); return; }
                    mode = "ble";
                    ble.setName(a.optString("name", ""));
                    ble.connect(id, cb);
                    return;
                }
                case "exit": {
                    cb.ok("{\"ok\":true}");
                    act.finish();
                    return;
                }
                case "copy": {
                    final String text = new JSONObject(argsJson == null ? "{}" : argsJson)
                            .optString("text", "");
                    act.runOnUiThread(new Runnable() {
                        public void run() {
                            try {
                                ClipboardManager cm = (ClipboardManager)
                                        act.getSystemService(Context.CLIPBOARD_SERVICE);
                                cm.setPrimaryClip(ClipData.newPlainText("sunnet", text));
                                cb.ok("{\"ok\":true}");
                            } catch (Throwable t) {
                                cb.err("复制失败: " + t.getMessage());
                            }
                        }
                    });
                    return;
                }
                case "open": {
                    JSONObject a = new JSONObject(argsJson == null ? "{}" : argsJson);
                    final ArrayList<String> urls = new ArrayList<>();
                    JSONArray arr = a.optJSONArray("urls");
                    if (arr != null) {
                        for (int i = 0; i < arr.length(); i++) {
                            String s = arr.optString(i, "");
                            if (!s.isEmpty()) urls.add(s);
                        }
                    }
                    String one = a.optString("url", "");
                    if (!one.isEmpty()) urls.add(one);
                    String fb = a.optString("fallback", "");
                    if (!fb.isEmpty()) urls.add(fb);
                    if (urls.isEmpty()) { cb.err("空链接"); return; }
                    act.runOnUiThread(() -> {
                        for (int i = 0; i < urls.size(); i++) {
                            if (openUrl(urls.get(i))) {
                                cb.ok("{\"ok\":true,\"i\":" + i + "}");
                                return;
                            }
                        }
                        cb.err("打不开（对应的 App 和浏览器都没找到）");
                    });
                    return;
                }
                case "paste": {
                    act.runOnUiThread(() -> {
                        try {
                            ClipboardManager cm = (ClipboardManager)
                                    act.getSystemService(Context.CLIPBOARD_SERVICE);
                            if (cm == null || !cm.hasPrimaryClip() || cm.getPrimaryClip().getItemCount() <= 0) {
                                cb.err("剪贴板是空的");
                                return;
                            }
                            CharSequence cs = cm.getPrimaryClip().getItemAt(0).coerceToText(act);
                            String t = cs == null ? "" : cs.toString();
                            if (t.isEmpty()) { cb.err("剪贴板里没有文字"); return; }
                            cb.ok("{\"ok\":true,\"text\":" + JSONObject.quote(t) + "}");
                        } catch (Throwable e) {
                            cb.err("读剪贴板失败: " + e.getMessage());
                        }
                    });
                    return;
                }
                case "pick": {
                    final String mime = new JSONObject(argsJson == null ? "{}" : argsJson)
                            .optString("mime", "*/*");
                    act.runOnUiThread(() -> {
                        if (pickCb != null) { pickCb.err("已经有一个选文件的框开着了"); pickCb = null; }
                        try {
                            Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                            i.addCategory(Intent.CATEGORY_OPENABLE);
                            i.setType(mime.isEmpty() ? "*/*" : mime);
                            i.putExtra(Intent.EXTRA_MIME_TYPES, new String[] {
                                    "application/json", "text/plain", "application/octet-stream", "*/*" });
                            pickCb = cb;
                            act.startActivityForResult(i, REQ_PICK);
                        } catch (Throwable e) {
                            pickCb = null;
                            cb.err("打不开文件选择器: " + e.getMessage());
                        }
                    });
                    return;
                }
                case "ble.perm": {
                    act.requestBlePermissions();
                    cb.ok("{\"ok\":true}");
                    return;
                }
                case "ble.disconnect": {
                    ble.disconnect();
                    mode = "none";
                    act.pushEvent("conn", "{\"state\":\"disconnected\",\"mode\":\"ble\"}");
                    cb.ok("{\"ok\":true}");
                    return;
                }
                case "get": {
                    JSONObject a = new JSONObject(argsJson == null ? "{}" : argsJson);
                    route(a.optString("path", "/api/state"), null, cb);
                    return;
                }
                case "post": {
                    JSONObject a = new JSONObject(argsJson == null ? "{}" : argsJson);
                    route(a.optString("path", "/api/cmd"), a.optString("body", "{}"), cb);
                    return;
                }
                default: cb.err("未知 op: " + op);
            }
        } catch (Exception e) {
            cb.err("调用失败: " + e);
        }
    }

    private void route(final String path, final String body, final ResultCb cb) {
        if ("ble".equals(mode)) { ble.call(path, body, cb); return; }
        if ("http".equals(mode)) {
            pool.execute(() -> {
                try { cb.ok(http(path, body)); } catch (Exception e) { cb.err(e.getMessage()); }
            });
            return;
        }
        cb.err("未连接：先连 WiFi 或 BLE");
    }

    // ------------------------------------------------------------ HTTP
    private String http(String path, String body) throws Exception {
        String url = "http://" + host + (port == 80 ? "" : ":" + port) + path;
        if (!path.startsWith("/")) url = "http://" + host + "/" + path;
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        try {
            c.setConnectTimeout(4000);
            c.setReadTimeout(6000);
            c.setRequestProperty("Accept", "application/json");
            if (body != null) {
                c.setRequestMethod("POST");
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type", "application/json");
                byte[] b = body.getBytes("UTF-8");
                c.setFixedLengthStreamingMode(b.length);
                OutputStream os = c.getOutputStream();
                os.write(b);
                os.flush();
                os.close();
            } else c.setRequestMethod("GET");

            int code = c.getResponseCode();
            InputStream is = (code >= 400) ? c.getErrorStream() : c.getInputStream();
            StringBuilder sb = new StringBuilder();
            if (is != null) {
                BufferedReader r = new BufferedReader(new InputStreamReader(is, "UTF-8"));
                String line;
                while ((line = r.readLine()) != null) sb.append(line).append('\n');
                r.close();
            }
            String text = sb.toString().trim();
            if (text.isEmpty()) throw new Exception("HTTP " + code + " 空响应（设备没起来？）");
            if (code >= 400 && !text.startsWith("{")) throw new Exception("HTTP " + code + ": " + text);
            return text;
        } finally {
            c.disconnect();
        }
    }

    /** 选文件回来后把文本交给 JS（在 MainActivity.onActivityResult 里调）*/
    public void onActivityResult(int req, int res, Intent data) {
        if (req != REQ_PICK || pickCb == null) return;
        final ResultCb cb = pickCb;
        pickCb = null;
        if (res != android.app.Activity.RESULT_OK || data == null || data.getData() == null) {
            cb.err("已取消");
            return;
        }
        final Uri uri = data.getData();
        String name = uri.getLastPathSegment() == null ? "" : uri.getLastPathSegment();
        try {
            String t = readText(uri, 2 * 1024 * 1024);
            cb.ok("{\"ok\":true,\"name\":" + JSONObject.quote(name) +
                    ",\"text\":" + JSONObject.quote(t) + "}");
        } catch (Throwable e) {
            cb.err("读文件失败: " + e.getMessage());
        }
    }

    private String readText(Uri uri, int limit) throws Exception {
        InputStream in = act.getContentResolver().openInputStream(uri);
        if (in == null) throw new Exception("打不开");
        java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int n, total = 0;
        while ((n = in.read(buf)) > 0) {
            total += n;
            if (total > limit) { in.close(); throw new Exception("文件太大（限 2MB）"); }
            bo.write(buf, 0, n);
        }
        in.close();
        return new String(bo.toByteArray(), "UTF-8");
    }

    private boolean openUrl(String url) {
        if (url == null || url.isEmpty()) return false;
        try {
            Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            act.startActivity(i);
            return true;
        } catch (Throwable t) {
            Log.w(TAG, "openUrl " + url + " -> " + t);
            return false;
        }
    }

    // ------------------------------------------------------------ 状态
    public String statusJson() {
        JSONObject o = new JSONObject();
        try {
            o.put("mode", mode);
            o.put("host", host);
            o.put("port", port);
            o.put("bleConnected", ble.isConnected());
            o.put("bleReady", ble.enabled());
            o.put("blePerm", ble.hasPermission());
        } catch (Exception ignored) { }
        return o.toString();
    }

    public void shutdown() { ble.disconnect(); pool.shutdownNow(); }

    public static String version() { return "1.0"; }

    public Context ctx() { return act; }
}
