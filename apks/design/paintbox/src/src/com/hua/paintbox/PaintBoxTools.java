package com.hua.paintbox;

import android.content.Context;
import android.net.Uri;
import android.util.Base64;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/**
 * 跑图助手暴露给 MCP 的工具：出图（grsai gpt-image 家族）、查任务、看模型表。
 * 密钥和线路沿用「设置」页里存的同一份（SecurePrefs），MCP 这边不重复配置。
 */
public class PaintBoxTools implements Mcp.Tools {

    public static final int DEFAULT_PORT = 8766;

    private final Context ctx;
    private final SecurePrefs prefs;

    public PaintBoxTools(Context c) {
        this.ctx = c.getApplicationContext();
        this.prefs = new SecurePrefs(this.ctx);
    }

    // ------------------------------------------------------------------ 定义

    private static final String S_LIST_MODELS = "{"
            + "\"type\":\"object\",\"properties\":{},\"additionalProperties\":false}";

    private static final String S_DRAW = "{"
            + "\"type\":\"object\","
            + "\"properties\":{"
            + "\"prompt\":{\"type\":\"string\",\"description\":\"提示词，描述想要生成的图像内容\"},"
            + "\"model\":{\"type\":\"string\",\"description\":\"默认 gpt-image-2；2.5/2.6 家族见 list_models\"},"
            + "\"quality\":{\"type\":\"string\",\"description\":\"auto/low/medium/high/xhigh/max，按模型支持情况\"},"
            + "\"aspect\":{\"type\":\"string\",\"description\":\"像素值，如 1024x1024、1536x1024、3840x2160\"},"
            + "\"count\":{\"type\":\"integer\",\"minimum\":1,\"maximum\":4,\"description\":\"出几张，默认 1，每张都扣费\"},"
            + "\"background\":{\"type\":\"string\",\"enum\":[\"auto\",\"transparent\"],\"description\":\"transparent 只有 vip/flare/sunburst 支持\"},"
            + "\"ref_urls\":{\"type\":\"array\",\"items\":{\"type\":\"string\"},\"description\":\"参考图 URL（http/https），可多张\"},"
            + "\"ref_paths\":{\"type\":\"array\",\"items\":{\"type\":\"string\"},\"description\":\"本机参考图路径（file:// 或 /sdcard/... 或 content://），会转成 base64 data URI 上传\"},"
            + "\"wait_seconds\":{\"type\":\"integer\",\"minimum\":0,\"maximum\":240,\"description\":\"等出图的最长秒数，默认 120；0 表示只提交、立刻返回 task_id\"},"
            + "\"save_gallery\":{\"type\":\"boolean\",\"description\":\"成功后是否存进相册 Pictures/跑图助手，默认 true\"}"
            + "},"
            + "\"required\":[\"prompt\"]}";

    private static final String S_STATUS = "{"
            + "\"type\":\"object\","
            + "\"properties\":{"
            + "\"task_id\":{\"type\":\"string\",\"description\":\"draw_image 返回的 task_id\"},"
            + "\"wait_seconds\":{\"type\":\"integer\",\"minimum\":0,\"maximum\":240,\"description\":\"继续等多少秒，默认 0\"},"
            + "\"save_gallery\":{\"type\":\"boolean\",\"description\":\"成功后是否存进相册，默认 true\"}"
            + "},"
            + "\"required\":[\"task_id\"]}";

    @Override
    public List<Mcp.Def> defs() {
        List<Mcp.Def> out = new ArrayList<>();
        out.add(new Mcp.Def("list_models", "可用出图模型",
                "列出 grsai 支持的模型、每个模型的 quality 档位、是否支持透明背景，以及当前 App 里配好的线路。",
                S_LIST_MODELS, true, false));
        out.add(new Mcp.Def("draw_image", "生成图片（grsai）",
                "调用 grsai /v1/draw/completions 出图（gpt-image-2 / 2.5 / 2.6 家族），会自动轮询 /v1/draw/result，"
                        + "成功后把图存进手机相册并返回图片 URL。每次调用都会扣费。"
                        + "一次调用最多等 240 秒；如果 wait_seconds 到了还没出图，会返回 status=running 和 task_id，"
                        + "再用 draw_status(task_id) 接着等或取图。",
                S_DRAW, false, false));
        out.add(new Mcp.Def("draw_status", "查 / 取出图任务",
                "查询一个出图任务的进度；成功了会下载图片、存进相册，并返回 URL 与保存位置。",
                S_STATUS, true, false));
        return out;
    }

    // ------------------------------------------------------------------ 调度

    @Override
    public JSONObject call(String name, JSONObject args) throws Exception {
        if ("list_models".equals(name)) return listModels();
        if ("draw_image".equals(name)) return drawImage(args);
        if ("draw_status".equals(name)) return drawStatus(args);
        throw new IllegalArgumentException("unknown tool: " + name);
    }

    // ------------------------------------------------------------------ list_models

    private JSONObject listModels() throws Exception {
        JSONObject out = new JSONObject();
        JSONArray models = new JSONArray();
        for (String m : Grsai.MODELS) {
            JSONObject o = new JSONObject();
            o.put("model", m);
            JSONArray q = new JSONArray();
            for (String s : Grsai.qualitiesFor(m)) q.put(s);
            o.put("quality", q);
            o.put("background_transparent", Grsai.supportsBackground(m));
            models.put(o);
        }
        out.put("models", models);
        JSONArray aspects = new JSONArray();
        for (String a : Grsai.ASPECTS) aspects.put(a);
        out.put("aspects", aspects);
        out.put("host", hostInUse());
        out.put("has_key", new Grsai("", prefs.get("grsai.key", "")).hasKey());
        out.put("defaults", defaults());
        return out;
    }

    private JSONObject defaults() throws Exception {
        JSONObject d = new JSONObject();
        d.put("model", prefs.get("grsai.model", "gpt-image-2"));
        d.put("quality", prefs.get("grsai.quality", "auto"));
        d.put("aspect", prefs.get("grsai.aspect", "1024x1024"));
        return d;
    }

    private String hostInUse() {
        return Grsai.resolveHost(prefs.get("grsai.host", "domestic"), prefs.get("grsai.host.custom", ""));
    }

    private Grsai api() {
        String key = prefs.get("grsai.key", "");
        if (key == null || key.trim().isEmpty()) {
            throw new IllegalStateException("App 里还没填 grsai API Key：打开「跑图助手 → 设置 → grsai 出图密钥」保存后重试");
        }
        return new Grsai(hostInUse(), key);
    }

    // ------------------------------------------------------------------ draw_image

    private JSONObject drawImage(JSONObject a) throws Exception {
        String prompt = a.optString("prompt", "").trim();
        if (prompt.isEmpty()) throw new IllegalArgumentException("prompt 不能为空");
        Grsai api = api();

        JSONObject d = defaults();
        String model = a.optString("model", d.optString("model", "gpt-image-2")).trim();
        boolean known = false;
        for (String m : Grsai.MODELS) if (m.equals(model)) known = true;
        if (!known) throw new IllegalArgumentException("未知模型 " + model + "，可用: " + String.join(", ", Grsai.MODELS));

        String quality = a.optString("quality", "").trim();
        if (quality.isEmpty()) {
            String[] qs = Grsai.qualitiesFor(model);
            quality = qs.length > 0 ? qs[0] : "auto";
        }
        String aspect = a.optString("aspect", d.optString("aspect", "1024x1024")).trim();
        if (!aspect.matches("\\d{2,5}x\\d{2,5}")) {
            throw new IllegalArgumentException("aspect 要写成像素值，如 1024x1024（收到 " + aspect + "）");
        }
        int count = Math.max(1, Math.min(4, a.optInt("count", 1)));
        String background = a.optString("background", "auto").trim();
        if (!background.isEmpty() && !"auto".equals(background) && !"transparent".equals(background)) {
            throw new IllegalArgumentException("background 只能是 auto 或 transparent");
        }
        int wait = Math.max(0, Math.min(240, a.optInt("wait_seconds", 120)));
        boolean save = a.optBoolean("save_gallery", true);

        List<String> refs = new ArrayList<>();
        JSONArray ru = a.optJSONArray("ref_urls");
        if (ru != null) {
            for (int i = 0; i < ru.length(); i++) {
                String u = ru.optString(i, "").trim();
                if (!u.isEmpty()) refs.add(u);
            }
        }
        JSONArray rp = a.optJSONArray("ref_paths");
        if (rp != null) {
            for (int i = 0; i < rp.length(); i++) {
                String p = rp.optString(i, "").trim();
                if (!p.isEmpty()) refs.add(asDataUri(p));
            }
        }

        JSONArray warnings = new JSONArray();
        List<String> qs = java.util.Arrays.asList(Grsai.qualitiesFor(model));
        if (!qs.contains(quality)) warnings.put("模型 " + model + " 文档档位是 " + qs + "，仍按 " + quality + " 提交");
        boolean transparent = "transparent".equals(background);
        if (transparent && !Grsai.supportsBackground(model)) {
            transparent = false;
            warnings.put("模型 " + model + " 不支持透明背景，已忽略 background");
        }

        long t0 = System.currentTimeMillis();
        long deadline = t0 + wait * 1000L;
        List<String> taskIds = new ArrayList<>();
        for (int i = 1; i <= count; i++) {
            JSONObject p = new JSONObject();
            p.put("model", model);
            p.put("prompt", prompt);
            p.put("aspectRatio", aspect);
            p.put("quality", quality);
            if (transparent) p.put("background", "transparent");
            if (!refs.isEmpty()) p.put("urls", Grsai.urlArray(refs));
            taskIds.add(api.submit(p));
        }

        JSONObject out = new JSONObject();
        out.put("host", api.host());
        out.put("model", model);
        out.put("quality", quality);
        out.put("aspect", aspect);
        out.put("task_ids", new JSONArray(taskIds));
        if (warnings.length() > 0) out.put("warnings", warnings);

        JSONArray tasks = new JSONArray();
        JSONArray images = new JSONArray();
        boolean anyRunning = false;
        for (String tid : taskIds) {
            JSONObject one = awaitTask(api, tid, deadline, save);
            tasks.put(one);
            JSONObject img = one.optJSONObject("image");
            if (img != null) images.put(img);
            String st = one.optString("status", "");
            if (!"succeeded".equals(st) && !"failed".equals(st)) anyRunning = true;
        }
        out.put("tasks", tasks);
        out.put("images", images);
        out.put("image_urls", urlsOf(images));
        out.put("status", images.length() == tasks.length() ? "succeeded"
                : anyRunning ? "running" : "failed");
        out.put("elapsed_ms", System.currentTimeMillis() - t0);
        if (anyRunning) {
            out.put("hint", "还在跑：用 draw_status(task_id=…) 继续等或取图；不要重复提交，会重复扣费。");
        }
        return out;
    }

    private JSONObject drawStatus(JSONObject a) throws Exception {
        String tid = a.optString("task_id", "").trim();
        if (tid.isEmpty()) throw new IllegalArgumentException("task_id 不能为空");
        Grsai api = api();
        int wait = Math.max(0, Math.min(240, a.optInt("wait_seconds", 0)));
        boolean save = a.optBoolean("save_gallery", true);
        long deadline = System.currentTimeMillis() + wait * 1000L;
        JSONObject one = awaitTask(api, tid, deadline, save);
        JSONObject out = new JSONObject();
        out.put("task_id", tid);
        out.put("status", one.optString("status", "?"));
        out.put("progress", one.optInt("progress", 0));
        JSONObject img = one.optJSONObject("image");
        if (img != null) {
            JSONArray arr = new JSONArray();
            arr.put(img);
            out.put("images", arr);
            out.put("image_urls", urlsOf(arr));
        } else {
            out.put("images", new JSONArray());
        }
        if (one.has("failure_reason")) out.put("failure_reason", one.optString("failure_reason", ""));
        if (one.has("error")) out.put("error", one.optString("error", ""));
        return out;
    }

    private static JSONArray urlsOf(JSONArray images) {
        JSONArray urls = new JSONArray();
        for (int i = 0; i < images.length(); i++) {
            JSONObject o = images.optJSONObject(i);
            String u = o == null ? "" : o.optString("url", "");
            if (!u.isEmpty()) urls.put(u);
        }
        return urls;
    }

    /** 轮询一个任务直到成功/失败/到点；成功时下载并存相册。 */
    private JSONObject awaitTask(Grsai api, String tid, long deadlineMs, boolean save) throws Exception {
        long t0 = System.currentTimeMillis();
        JSONObject result = new JSONObject();
        result.put("task_id", tid);
        int retries = 0;
        while (true) {
            JSONObject d;
            try {
                d = api.pollOnce(tid);
            } catch (Exception e) {
                // 网络抖动：还有时间就再试，别把整个调用打掉
                if (System.currentTimeMillis() + 5000 > deadlineMs) throw e;
                d = null;
            }
            if (d != null) {
                String st = d.optString("status", "");
                int pr = d.optInt("progress", 0);
                result.put("status", st);
                result.put("progress", pr);
                if ("succeeded".equals(st)) {
                    JSONArray res = d.optJSONArray("results");
                    if (res == null || res.length() == 0) {
                        result.put("status", "failed");
                        result.put("error", "状态成功但没有结果 URL");
                        return result;
                    }
                    JSONArray images = new JSONArray();
                    for (int i = 0; i < res.length(); i++) {
                        String url = res.optJSONObject(i).optString("url", "");
                        if (url.isEmpty()) continue;
                        images.put(fetchResult(api, url, save));
                    }
                    result.put("images", images);
                    JSONObject first = images.optJSONObject(0);
                    if (first != null) result.put("image", first);
                    return result;
                }
                if ("failed".equals(st)) {
                    String reason = d.optString("failure_reason", "");
                    String err = d.optString("error", "");
                    result.put("failure_reason", reason);
                    result.put("error", err.isEmpty() ? reason : err);
                    if ("error".equals(reason) && retries < 2 && System.currentTimeMillis() + 6000 < deadlineMs) {
                        retries++;
                        sleep(3000);
                        continue;
                    }
                    return result;
                }
            }
            if (System.currentTimeMillis() + 5500 > deadlineMs) {
                if (!result.has("status")) result.put("status", "running");
                result.put("progress", result.optInt("progress", 0));
                result.put("waited_ms", System.currentTimeMillis() - t0);
                return result;
            }
            sleep(5000);
        }
    }

    /** 下载结果图，可选存相册，返回 {url, pixels, kb, path}。 */
    private JSONObject fetchResult(Grsai api, String url, boolean save) throws Exception {
        JSONObject o = new JSONObject();
        o.put("url", url);
        byte[] png = api.download(url);
        o.put("pixels", Grsai.pixelSize(png));
        o.put("kb", png.length / 1024);
        if (save) {
            SimpleDateFormat f = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US);
            String name = "grsai_" + f.format(new Date()) + ".png";
            try {
                o.put("path", Gallery.save(ctx, name, png, "image/png"));
            } catch (Throwable t) {
                o.put("save_error", String.valueOf(t.getMessage() == null ? t : t.getMessage()));
            }
        }
        return o;
    }

    /** 本机图片路径 / content URI → data URI；已经是 http(s) 就原样返回。 */
    private String asDataUri(String p) throws Exception {
        if (p.startsWith("http://") || p.startsWith("https://") || p.startsWith("data:")) return p;
        byte[] bytes;
        if (p.startsWith("content://")) {
            try (InputStream in = ctx.getContentResolver().openInputStream(Uri.parse(p))) {
                if (in == null) throw new IllegalArgumentException("打不开 content URI: " + p);
                bytes = readAll(in);
            }
        } else {
            String path = p.startsWith("file://") ? p.substring("file://".length()) : p;
            File f = new File(path);
            if (!f.isFile()) throw new IllegalArgumentException("找不到参考图: " + path);
            if (f.length() > 24L * 1024 * 1024) throw new IllegalArgumentException("参考图太大(>24MB): " + path);
            try (InputStream in = new FileInputStream(f)) {
                bytes = readAll(in);
            }
        }
        String lower = p.toLowerCase(Locale.US);
        String mime = lower.endsWith(".jpg") || lower.endsWith(".jpeg") ? "image/jpeg"
                : lower.endsWith(".webp") ? "image/webp" : "image/png";
        return "data:" + mime + ";base64," + Base64.encodeToString(bytes, Base64.NO_WRAP);
    }

    private static byte[] readAll(InputStream in) throws Exception {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int n;
        while ((n = in.read(buf)) > 0) bos.write(buf, 0, n);
        return bos.toByteArray();
    }

    private static void sleep(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
