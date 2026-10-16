package com.hua.paintbox;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Thin client for the 仙宫云 / XGC Open API.
 * Base https://api.xiangongyun.com, auth: Authorization: Bearer &lt;访问令牌&gt;.
 *
 * Standing rule (copied from the xgc-api skill): this client must NEVER delete an image.
 * Images cost nothing to keep; the user deletes them by hand in the console.
 */
public class Xgc {

    public static final String BASE = "https://api.xiangongyun.com";

    /** Hard-blocked endpoints - image deletion is forbidden for this client, always. */
    private static final String[] IMAGE_DENYLIST = {
            "/open/image/destroy", "/open/image/delete", "/open/image/remove", "/open/images/destroy"
    };

    private final String token;

    public Xgc(String token) {
        this.token = token == null ? "" : token.trim();
    }

    public boolean hasToken() {
        return token.length() > 0;
    }

    public JSONObject call(String method, String path, JSONObject body) throws Exception {
        for (String bad : IMAGE_DENYLIST) {
            if (path.contains(bad)) {
                throw new IllegalStateException("拒绝执行：本 App 永不删除镜像（请到仙宫云控制台手动删除）");
            }
        }
        Http.R r = Http.req(method, BASE + path, body == null ? null : body.toString(), token, 60000);
        if (r.body == null || r.body.trim().isEmpty()) {
            throw new RuntimeException("HTTP " + r.code + " 空响应");
        }
        JSONObject j;
        try {
            j = new JSONObject(r.body);
        } catch (Throwable t) {
            throw new RuntimeException("HTTP " + r.code + " 非 JSON 响应: " + Http.abbr(r.body, 300));
        }
        if (!ok(j)) {
            throw new RuntimeException("API 报错 code=" + j.opt("code") + " msg=" + j.optString("msg")
                    + " " + Http.abbr(r.body, 200));
        }
        return j;
    }

    public static boolean ok(JSONObject r) {
        if (r == null) return false;
        if (r.has("success")) return r.optBoolean("success", false);
        Object c = r.opt("code");
        if (c == null) return true;
        String s = String.valueOf(c);
        return "0".equals(s) || "200".equals(s);
    }

    /** Unwraps the useful payload (data / result / list) or returns the envelope itself. */
    public static JSONObject payload(JSONObject r) {
        for (String k : new String[]{"data", "result"}) {
            JSONObject o = r.optJSONObject(k);
            if (o != null) return o;
        }
        return r;
    }

    public static JSONArray payloadList(JSONObject r) {
        for (String k : new String[]{"data", "result", "list", "results"}) {
            JSONArray a = r.optJSONArray(k);
            if (a != null) return a;
        }
        return new JSONArray();
    }

    public JSONObject whoami() throws Exception { return call("GET", "/open/whoami", null); }

    public JSONObject balanceRaw() throws Exception { return call("GET", "/open/balance", null); }

    public double balance() throws Exception {
        JSONObject d = payload(balanceRaw());
        if (d.has("balance")) return d.optDouble("balance", 0);
        return d.optDouble("amount", 0);
    }

    public JSONArray instances() throws Exception { return payloadList(call("GET", "/open/instances", null)); }

    public JSONArray images() throws Exception { return payloadList(call("GET", "/open/images", null)); }

    public JSONObject deploy(JSONObject body) throws Exception {
        return call("POST", "/open/instance/deploy", body);
    }

    public JSONObject boot(String id) throws Exception { return life("/open/instance/boot", id); }

    public JSONObject shutdown(String id) throws Exception { return life("/open/instance/shutdown", id); }

    public JSONObject shutdownReleaseGpu(String id) throws Exception {
        return life("/open/instance/shutdown_release_gpu", id);
    }

    public JSONObject shutdownDestroy(String id) throws Exception {
        return life("/open/instance/shutdown_destroy", id);
    }

    public JSONObject destroy(String id) throws Exception { return life("/open/instance/destroy", id); }

    private JSONObject life(String path, String id) throws Exception {
        JSONObject b = new JSONObject();
        b.put("id", id);
        return call("POST", path, b);
    }

    public String publicUrl(String instanceId, int port) {
        return "https://" + instanceId + "-" + port + ".container.x-gpu.com";
    }

    public static boolean isRunning(JSONObject inst) {
        String s = inst.optString("status", "").toLowerCase();
        return s.equals("running") || s.equals("运行中") || s.equals("starting")
                || s.equals("runninging") || s.equals("1") || s.equals("true");
    }

    public static String statusText(JSONObject inst) {
        String s = inst.optString("status", "?");
        String low = s.toLowerCase();
        if (low.equals("running") || s.equals("运行中")) return "运行中（计费中）";
        if (low.equals("shutdown") || low.equals("stopped") || s.equals("已关机")) return "已关机";
        if (low.equals("creating") || low.equals("provisioning") || low.equals("starting")) return "开机中（不计费）";
        return s;
    }

    /** Masked fingerprint of the token; the token itself is never shown or logged. */
    public static String fingerprint(String t) {
        if (t == null || t.isEmpty()) return "(未设置)";
        if (t.length() <= 8) return t.charAt(0) + "***" + t.charAt(t.length() - 1)
                + " len=" + t.length();
        return t.substring(0, 4) + "…" + t.substring(t.length() - 4) + " len=" + t.length();
    }

    public static void copy(android.content.Context c, String label, String text) {
        try {
            android.content.ClipboardManager cm = (android.content.ClipboardManager)
                    c.getSystemService(android.content.Context.CLIPBOARD_SERVICE);
            cm.setPrimaryClip(android.content.ClipData.newPlainText(label, text));
            android.widget.Toast.makeText(c, "已复制: " + Http.abbr(text, 40),
                    android.widget.Toast.LENGTH_SHORT).show();
        } catch (Throwable t) {
            android.widget.Toast.makeText(c, "复制失败", android.widget.Toast.LENGTH_SHORT).show();
        }
    }
}
