package com.hua.paintbox;

import android.graphics.BitmapFactory;
import android.util.Base64;

import org.json.JSONArray;
import org.json.JSONObject;

/** grsai image generation client (gpt-image-2 / 2.5 family), API facts taken from the skill. */
public class Grsai {

    public static final String HOST_DOMESTIC = "https://grsai.dakka.com.cn";
    public static final String HOST_OVERSEAS = "https://grsaiapi.com";

    public static final String[] MODELS = {
            "gpt-image-2",
            "gpt-image-2-vip",
            "gpt-image-2.5",
            "gpt-image-2.5-flare",
            "gpt-image-2.5-sunburst",
    };

    public static final String[] ASPECTS = {
            "1024x1024", "1536x1024", "1024x1536", "2048x1152", "3840x2160",
    };

    public static final String[] HOSTS = {"domestic", "overseas", "custom"};

    public static String[] qualitiesFor(String model) {
        if ("gpt-image-2".equals(model)) return new String[]{"auto"};
        if ("gpt-image-2-vip".equals(model)) return new String[]{"medium"};
        if ("gpt-image-2.5-flare".equals(model)) return new String[]{"low", "medium", "high"};
        if ("gpt-image-2.5-sunburst".equals(model)) {
            return new String[]{"low", "medium", "high", "xhigh", "max"};
        }
        return new String[]{"auto", "low", "medium", "high"};
    }

    public static boolean supportsBackground(String model) {
        return model != null && (model.contains("vip") || model.contains("flare")
                || model.contains("sunburst"));
    }

    public static String resolveHost(String hostPref, String custom) {
        if ("overseas".equals(hostPref)) return HOST_OVERSEAS;
        if ("custom".equals(hostPref)) {
            String h = custom == null ? "" : custom.trim();
            if (h.isEmpty()) return HOST_DOMESTIC;
            return h;
        }
        return HOST_DOMESTIC;
    }

    private final String host;
    private final String key;

    public Grsai(String host, String key) {
        this.host = host == null ? HOST_DOMESTIC : host.replaceAll("/+$", "");
        this.key = key == null ? "" : key.trim();
    }

    public boolean hasKey() {
        return key.length() > 0;
    }

    public String host() {
        return host;
    }

    /** POST /v1/draw/completions -> task id. webHook=-1 makes it return immediately. */
    public String submit(JSONObject payload) throws Exception {
        payload.put("webHook", "-1");
        Http.R r = Http.req("POST", host + "/v1/draw/completions", payload.toString(), key, 180000);
        JSONObject j = parse(r);
        if (j.optInt("code", -1) != 0) {
            throw new RuntimeException("提交失败: " + Http.abbr(r.body, 400));
        }
        JSONObject d = j.optJSONObject("data");
        if (d == null || d.optString("id", "").isEmpty()) {
            throw new RuntimeException("提交返回里没有任务 id: " + Http.abbr(r.body, 300));
        }
        return d.getString("id");
    }

    /** POST /v1/draw/result -> {status, progress, results[], failure_reason} */
    public JSONObject pollOnce(String taskId) throws Exception {
        JSONObject body = new JSONObject();
        body.put("id", taskId);
        Http.R r = Http.req("POST", host + "/v1/draw/result", body.toString(), key, 60000);
        JSONObject j = parse(r);
        JSONObject d = j.optJSONObject("data");
        if (d == null) throw new RuntimeException("轮询响应异常: " + Http.abbr(r.body, 300));
        return d;
    }

    public byte[] download(String url) throws Exception {
        return Http.bytes(url, null, 180000);
    }

    private JSONObject parse(Http.R r) throws Exception {
        if (r.body == null || r.body.trim().isEmpty()) throw new RuntimeException("HTTP " + r.code + " 空响应");
        try {
            return new JSONObject(r.body);
        } catch (Throwable t) {
            throw new RuntimeException("HTTP " + r.code + " 非 JSON: " + Http.abbr(r.body, 300));
        }
    }

    public static String dataUri(String mime, byte[] bytes) {
        return "data:" + (mime == null ? "image/png" : mime) + ";base64,"
                + Base64.encodeToString(bytes, Base64.NO_WRAP);
    }

    /** Actual pixel size of the returned file (the API does not always honour aspectRatio). */
    public static String pixelSize(byte[] png) {
        try {
            BitmapFactory.Options o = new BitmapFactory.Options();
            o.inJustDecodeBounds = true;
            BitmapFactory.decodeByteArray(png, 0, png.length, o);
            if (o.outWidth > 0 && o.outHeight > 0) return o.outWidth + "x" + o.outHeight;
        } catch (Throwable ignored) {
        }
        return "未知";
    }

    public static JSONArray urlArray(java.util.List<String> urls) {
        JSONArray a = new JSONArray();
        for (String u : urls) a.put(u);
        return a;
    }
}
