package com.hua.subhunter;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.provider.MediaStore;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.util.List;

/** JS ⇄ 原生桥。所有方法都在 WebView 的 JS 线程被调用，回页面一律 handler.post。 */
public class Bridge {

    private final Activity act;
    private final WebView web;
    private final Handler main = new Handler(Looper.getMainLooper());
    private volatile boolean cancelFlag = false;
    private volatile boolean running = false;
    private long lastProgressAt = 0;

    Bridge(Activity act, WebView web) {
        this.act = act;
        this.web = web;
    }

    // ------------------------------------------------------------------ 状态

    @JavascriptInterface
    public String state() {
        Store st = Store.get(act);
        try {
            JSONObject o = new JSONObject();
            o.put("ver", "1.0.3");
            o.put("sdk", Build.VERSION.SDK_INT);
            o.put("lastTime", st.lastTime());
            o.put("nodeCount", Util.toInt(st.meta("nodeCount", "0"), 0));
            o.put("clashCount", Util.toInt(st.meta("clashCount", "0"), 0));
            o.put("uriCount", Util.toInt(st.meta("uriCount", "0"), 0));
            o.put("rawTotal", Util.toInt(st.meta("rawTotal", "0"), 0));
            o.put("aliveTotal", Util.toInt(st.meta("aliveTotal", "-1"), -1));
            o.put("costMs", Util.toInt(st.meta("costMs", "0"), 0));
            o.put("prevCount", Util.toInt(st.meta("prevCount", "0"), 0));
            o.put("hasData", !Util.isBlank(st.clashYaml()));

            o.put("pingOn", st.pingOn());
            o.put("maxNodes", st.maxNodes());
            o.put("pingMs", st.pingTimeout());
            o.put("autoOn", st.autoOn());
            o.put("hour", st.autoHour());
            o.put("minute", st.autoMinute());
            o.put("port", Hub.serverPort(st.port()));
            o.put("notifOn", st.notifOn());
            o.put("fetching", running || Hub.fetching);
            o.put("log", Hub.lastLog);

            boolean on = Hub.serverRunning();
            o.put("serverOn", on);
            String base = "http://127.0.0.1:" + Hub.serverPort(st.port());
            o.put("urlClash", base + "/clash");
            o.put("urlV2ray", base + "/v2ray");

            JSONArray arr = new JSONArray();
            List<Source> list = st.sources();
            List<String[]> stats = st.stats();
            for (Source s : list) {
                JSONObject j = new JSONObject();
                j.put("id", s.id);
                j.put("name", s.name);
                j.put("url", s.url);
                j.put("kind", s.kind);
                j.put("on", s.enabled);
                j.put("builtin", s.builtin);
                j.put("note", s.note);
                j.put("count", 0);
                j.put("ok", true);
                j.put("ms", 0);
                j.put("info", "");
                for (String[] f : stats) {
                    if (f[0].equals(s.id)) {
                        j.put("ok", f[2].equals("1"));
                        j.put("count", Util.toInt(f[3], 0));
                        j.put("ms", Util.toInt(f[4], 0));
                        j.put("info", f[5]);
                        break;
                    }
                }
                arr.put(j);
            }
            o.put("sources", arr);
            return o.toString();
        } catch (Throwable t) {
            return "{\"error\":\"" + t.getClass().getSimpleName() + "\"}";
        }
    }

    @JavascriptInterface
    public String nodes(int page) {
        Store st = Store.get(act);
        List<Node> all = st.nodes();
        JSONArray arr = new JSONArray();
        int per = 120;
        int from = Math.max(0, page) * per;
        int to = Math.min(all.size(), from + per);
        try {
            for (int i = from; i < to; i++) {
                Node n = all.get(i);
                JSONObject j = new JSONObject();
                j.put("s", n.scheme);
                j.put("n", n.name);
                j.put("e", n.endpoint());
                j.put("l", n.latency);
                j.put("r", n.region());
                j.put("u", n.toUri());
                arr.put(j);
            }
            JSONObject o = new JSONObject();
            o.put("total", all.size());
            o.put("page", page);
            o.put("per", per);
            o.put("list", arr);
            return o.toString();
        } catch (Throwable t) {
            return "{\"total\":0,\"page\":0,\"list\":[]}";
        }
    }

    // ------------------------------------------------------------------ 抓取

    /**
     * 开始抓取。返回 false 表示这次没启动（已经在抓），页面据此恢复按钮，
     * 避免「点了没反应、按钮永远停在⏳」。
     */
    @JavascriptInterface
    public boolean runFetch() {
        if (running || Hub.fetching) {
            toast("正在抓取中，稍等…");
            return false;
        }
        running = true;
        cancelFlag = false;
        Log.i("SubHunter", "runFetch: start");
        new Thread(new Runnable() {
            @Override
            public void run() {
                Engine.Sink sink = new Engine.Sink() {
                    @Override
                    public void progress(int pct, String stage, String msg) {
                        long now = System.currentTimeMillis();
                        boolean important = "done".equals(stage) || pct >= 99 || pct <= 2;
                        if (!important && now - lastProgressAt < 220) return;
                        lastProgressAt = now;
                        try {
                            JSONObject j = new JSONObject();
                            j.put("pct", pct);
                            j.put("stage", stage);
                            j.put("msg", msg);
                            call("__progress", j.toString());
                        } catch (Throwable ignore) {
                        }
                    }

                    @Override
                    public boolean cancelled() {
                        return cancelFlag;
                    }
                };
                Worker.Outcome out = null;
                String crash = "";
                try {
                    out = Worker.run(act, sink);
                } catch (Throwable t) {
                    crash = t.getClass().getSimpleName() + ": " + t.getMessage();
                    Log.w("SubHunter", "runFetch: " + crash, t);
                }
                running = false;
                Log.i("SubHunter", "runFetch: done ok=" + (out != null && out.result != null));
                // 这一条必须发出去：state() 取失败也不能把页面卡在⏳
                JSONObject j = new JSONObject();
                try {
                    boolean ok = out != null && out.result != null && out.result.nodes.size() > 0;
                    j.put("ok", ok);
                    j.put("newCount", out == null ? 0 : out.newCount);
                    j.put("prevCount", out == null ? 0 : out.prevCount);
                    j.put("msg", ok ? SubService.summary(out)
                            : (Util.isBlank(crash) ? (out == null || Util.isBlank(out.error) ? "抓取失败" : out.error) : crash));
                } catch (Throwable ignore) {
                }
                try {
                    j.put("state", new JSONObject(state()));
                } catch (Throwable ignore) {
                }
                call("__fetchDone", j.toString());
            }
        }, "subhunter-fetch").start();
        return true;
    }

    @JavascriptInterface
    public void cancelFetch() {
        cancelFlag = true;
    }

    // ------------------------------------------------------------------ 复制 / 分享 / 导出

    @JavascriptInterface
    public boolean copy(String text) {
        if (text == null) return false;
        try {
            ClipboardManager cm = (ClipboardManager) act.getSystemService(Context.CLIPBOARD_SERVICE);
            if (cm == null) return false;
            cm.setPrimaryClip(ClipData.newPlainText("订阅猎手", text));
            toast("已复制 " + text.length() + " 字符");
            return true;
        } catch (Throwable t) {
            return false;
        }
    }

    @JavascriptInterface
    public String payload(String kind) {
        Store st = Store.get(act);
        if ("v2ray".equals(kind)) return st.v2rayB64();
        if ("clash".equals(kind)) return st.clashYaml();
        if ("uris".equals(kind)) return Util.str(Util.b64d(st.v2rayB64()));
        if ("urlClash".equals(kind)) return "http://127.0.0.1:" + Hub.serverPort(st.port()) + "/clash";
        if ("urlV2ray".equals(kind)) return "http://127.0.0.1:" + Hub.serverPort(st.port()) + "/v2ray";
        return "";
    }

    @JavascriptInterface
    public boolean copyKind(String kind) {
        String s = payload(kind);
        if (Util.isBlank(s)) {
            toast("还没有数据，先点「抓取」");
            return false;
        }
        return copy(s);
    }

    @JavascriptInterface
    public String shareKind(String kind) {
        try {
            String s = payload(kind);
            if (Util.isBlank(s)) return "没有数据";
            Intent i = new Intent(Intent.ACTION_SEND);
            i.setType("text/plain");
            i.putExtra(Intent.EXTRA_SUBJECT, "订阅猎手 · " + kind);
            i.putExtra(Intent.EXTRA_TEXT, s);
            act.startActivity(Intent.createChooser(i, "分享订阅"));
            return "ok";
        } catch (Throwable t) {
            return t.getClass().getSimpleName();
        }
    }

    /** 导出到「下载/订阅猎手/」，Clash Meta / v2rayNG 都能从文件导入。 */
    @JavascriptInterface
    public String exportFiles() {
        Store st = Store.get(act);
        String clash = st.clashYaml();
        String v2 = st.v2rayB64();
        if (Util.isBlank(clash) || Util.isBlank(v2)) return "还没有数据";
        String where = "";
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                where = saveMedia("clash.yaml", clash);
                saveMedia("v2ray.txt", v2);
                where = "下载/SubHunter/";
            } else {
                File dir = new File(act.getExternalFilesDir(null), "export");
                if (!dir.exists()) dir.mkdirs();
                writeFile(new File(dir, "clash.yaml"), clash);
                writeFile(new File(dir, "v2ray.txt"), v2);
                where = dir.getAbsolutePath();
            }
            return "已导出到 " + where;
        } catch (Throwable t) {
            return "导出失败：" + t.getClass().getSimpleName();
        }
    }

    @SuppressWarnings("deprecation")
    private String saveMedia(String name, String body) throws Exception {
        ContentValues cv = new ContentValues();
        cv.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
        cv.put(MediaStore.MediaColumns.MIME_TYPE, name.endsWith(".yaml") ? "text/yaml" : "text/plain");
        cv.put(MediaStore.MediaColumns.RELATIVE_PATH, "Download/SubHunter");
        Uri uri = act.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, cv);
        if (uri == null) throw new IllegalStateException("insert failed");
        OutputStream os = act.getContentResolver().openOutputStream(uri);
        if (os == null) throw new IllegalStateException("open failed");
        os.write(Util.utf8(body));
        os.flush();
        os.close();
        return uri.toString();
    }

    private static void writeFile(File f, String body) throws Exception {
        FileOutputStream fos = new FileOutputStream(f);
        fos.write(Util.utf8(body));
        fos.close();
    }

    // ------------------------------------------------------------------ 设置 / 源管理

    @JavascriptInterface
    public String setSetting(String key, String value) {
        Store st = Store.get(act);
        st.put(key, value);
        if ("auto".equals(key) || "hour".equals(key) || "minute".equals(key)) {
            Sched.reschedule(act);
            if (value.equals("1") || value.equals("true")) Sched.enqueueOnce(act);
        }
        if ("port".equals(key)) {
            boolean was = Hub.serverRunning();
            if (was) {
                SubService.stopServer(act);
                try {
                    Thread.sleep(260);
                } catch (InterruptedException ignore) {
                }
                SubService.startServer(act);
            }
        }
        return state();
    }

    @JavascriptInterface
    public String toggleSource(String id, boolean on) {
        Store.get(act).setSourceEnabled(id, on);
        return state();
    }

    @JavascriptInterface
    public String addSource(String name, String url) {
        if (Util.isBlank(url) || !(url.startsWith("http://") || url.startsWith("https://"))) {
            return "{\"ok\":false,\"msg\":\"地址要以 http(s):// 开头\"}";
        }
        Store.get(act).addSource(name, url);
        return "{\"ok\":true,\"state\":" + state() + "}";
    }

    @JavascriptInterface
    public String removeSource(String id) {
        Store.get(act).removeSource(id);
        return state();
    }

    // ------------------------------------------------------------------ 本机订阅服务

    @JavascriptInterface
    public String serverToggle(boolean on) {
        if (on) SubService.startServer(act);
        else SubService.stopServer(act);
        final int[] waited = {0};
        while (waited[0] < 30 && Hub.serverRunning() != on) {
            try {
                Thread.sleep(100);
            } catch (InterruptedException ignore) {
            }
            waited[0]++;
        }
        Store.get(act).put("serverWanted", on ? "1" : "0");
        return state();
    }

    // ------------------------------------------------------------------ 杂项

    @JavascriptInterface
    public void toast(String msg) {
        final String m = msg;
        main.post(new Runnable() {
            @Override
            public void run() {
                try {
                    Toast.makeText(act, m, Toast.LENGTH_SHORT).show();
                } catch (Throwable ignore) {
                }
            }
        });
    }

    @JavascriptInterface
    public boolean openApp(String pkg) {
        try {
            Intent i = act.getPackageManager().getLaunchIntentForPackage(pkg);
            if (i == null) return false;
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            act.startActivity(i);
            return true;
        } catch (Throwable t) {
            return false;
        }
    }

    @JavascriptInterface
    public void openUrl(String url) {
        try {
            Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            act.startActivity(i);
        } catch (Throwable t) {
            toast("没有可打开该链接的应用");
        }
    }

    @JavascriptInterface
    public void requestNotif() {
        main.post(new Runnable() {
            @Override
            public void run() {
                if (act instanceof MainActivity) ((MainActivity) act).requestNotifPermission();
            }
        });
    }

    @JavascriptInterface
    public String clearCache() {
        Store st = Store.get(act);
        st.saveResult(new Engine.Result());
        st.put("nodeCount", "0");
        st.put("clashCount", "0");
        st.put("uriCount", "0");
        st.put("lastTime", "");
        return state();
    }

    private void call(final String fn, final String json) {
        main.post(new Runnable() {
            @Override
            public void run() {
                try {
                    String js = "window." + fn + " && window." + fn + "(" + json + ")";
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) web.evaluateJavascript(js, null);
                    else web.loadUrl("javascript:" + js);
                } catch (Throwable ignore) {
                }
            }
        });
    }
}
