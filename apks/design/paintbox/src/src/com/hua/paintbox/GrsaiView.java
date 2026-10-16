package com.hua.paintbox;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class GrsaiView extends android.widget.ScrollView {

    private final SecurePrefs prefs;
    private final ExecutorService ex = Executors.newSingleThreadExecutor();
    private final Handler ui = new Handler(Looper.getMainLooper());

    private EditText promptEd, refUrlEd, taskIdEd;
    private Theme.Chips modelChips, qualityChips, aspectChips, countChips;
    private CheckBox bgCk;
    private LinearLayout refBox;
    private TextView statusTv, costTv, resultMeta;
    private ProgressBar prog;
    private ImageView preview;
    private Button genBtn, stopBtn;
    private LogPane log;

    private final List<String> refUris = new ArrayList<>();
    private final List<String> refNames = new ArrayList<>();
    private volatile boolean cancel = false;
    private volatile boolean busy = false;

    public GrsaiView(Activity c) {
        super(c);
        prefs = new SecurePrefs(c);
        setFillViewport(true);
        setBackgroundColor(0x00000000);
        build(c);
    }

    // ------------------------------------------------------------------ UI

    private void build(Activity c) {
        LinearLayout root = Theme.screen(c);
        root.addView(Theme.hero(c, "AI 出图", "grsai gpt-image 系列 · 文生图 / 图生图，出完自动存进手机图库",
                "GRSAI"));

        // ---- prompt
        LinearLayout pCard = Theme.card(c);
        pCard.addView(Theme.section(c, "提示词"));
        pCard.addView(Theme.label(c, "prompt"));
        promptEd = Theme.input(c, "一只红色的陶瓷茶壶放在白底，柔和影棚光，产品摄影，高清细节", true, 4);
        pCard.addView(promptEd);
        root.addView(pCard);

        // ---- params
        LinearLayout sCard = Theme.card(c);
        sCard.addView(Theme.section(c, "出图参数"));

        sCard.addView(Theme.label(c, "模型"));
        modelChips = new Theme.Chips(c, Grsai.MODELS, prefs.get("grsai.model", "gpt-image-2.5"),
                (v, i) -> {
                    String[] q = Grsai.qualitiesFor(v);
                    String keep = qualityChips.value();
                    qualityChips.setItems(q, keep);
                    boolean canBg = Grsai.supportsBackground(v);
                    bgCk.setEnabled(canBg);
                    bgCk.setText(canBg ? "透明背景 transparent" : "透明背景（该模型未记载支持）");
                    updateCost();
                });
        sCard.addView(modelChips, Ui.matchWrap());

        sCard.addView(Theme.label(c, "质量"));
        qualityChips = new Theme.Chips(c, Grsai.qualitiesFor(modelChips.value()),
                prefs.get("grsai.quality", "auto"), (v, i) -> updateCost());
        sCard.addView(qualityChips, Ui.matchWrap());

        sCard.addView(Theme.label(c, "比例 / 像素"));
        aspectChips = new Theme.Chips(c, Grsai.ASPECTS, prefs.get("grsai.aspect", "1024x1024"),
                (v, i) -> updateCost());
        sCard.addView(aspectChips, Ui.matchWrap());

        sCard.addView(Theme.label(c, "张数"));
        countChips = new Theme.Chips(c, new String[]{"1 张", "2 张", "4 张"}, "1 张", (v, i) -> updateCost());
        sCard.addView(countChips, Ui.matchWrap());

        bgCk = Theme.check(c, "透明背景 transparent");
        bgCk.setPadding(0, Ui.dp(c, 12), 0, 0);
        sCard.addView(bgCk);
        boolean canBg = Grsai.supportsBackground(modelChips.value());
        bgCk.setEnabled(canBg);
        if (!canBg) bgCk.setText("透明背景（该模型未记载支持）");
        root.addView(sCard);

        // ---- references
        LinearLayout rCard = Theme.card(c);
        rCard.addView(Theme.section(c, "参考图"));
        rCard.addView(Theme.note(c, "留空 = 纯文生图。加图 = 图生图 / 换风格（结构锁定的模板见 skill 里的 prompt playbook）。"));
        rCard.addView(Theme.label(c, "图片 URL"));
        refUrlEd = Theme.input(c, "https://…/ref.png", false, 1);
        refUrlEd.setInputType(android.text.InputType.TYPE_TEXT_VARIATION_URI);
        rCard.addView(refUrlEd);
        LinearLayout rRow = Ui.row(c);
        rRow.setPadding(0, Ui.dp(c, 10), 0, 0);
        Button pick = Theme.ghost(c, "＋ 选手机图片");
        Button addUrl = Theme.ghost(c, "＋ 加这个 URL");
        rRow.addView(pick);
        rRow.addView(Theme.spacer(c, 0));
        LinearLayout.LayoutParams slp = Ui.wrap();
        slp.setMargins(Ui.dp(c, 8), 0, 0, 0);
        addUrl.setLayoutParams(slp);
        rRow.addView(addUrl);
        rCard.addView(rRow);
        refBox = Ui.col(c);
        rCard.addView(refBox);
        refreshRefs();
        root.addView(rCard);

        // ---- action
        LinearLayout aCard = Theme.card(c);
        genBtn = Theme.primary(c, "开始出图");
        aCard.addView(genBtn);
        costTv = Theme.note(c, "");
        costTv.setPadding(0, Ui.dp(c, 8), 0, 0);
        aCard.addView(costTv);

        LinearLayout prow = Ui.row(c);
        prow.setPadding(0, Ui.dp(c, 12), 0, 0);
        prog = Theme.progress(c);
        prow.addView(prog, Ui.lp(0, Ui.dp(c, 8), 1f));
        aCard.addView(prow);

        statusTv = Ui.text(c, "空闲", 13, true);
        statusTv.setTextColor(Theme.MUTED);
        statusTv.setPadding(0, Ui.dp(c, 10), 0, 0);
        aCard.addView(statusTv);

        LinearLayout tRow = Ui.row(c);
        tRow.setPadding(0, Ui.dp(c, 10), 0, 0);
        taskIdEd = Theme.input(c, "任务 ID（可粘贴续查）", false, 1);
        taskIdEd.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12.5f);
        tRow.addView(taskIdEd, Ui.lp(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        Button rePoll = Theme.ghost(c, "续查");
        stopBtn = Theme.ghost(c, "停止");
        LinearLayout.LayoutParams mlp = Ui.wrap();
        mlp.setMargins(Ui.dp(c, 8), 0, 0, 0);
        rePoll.setLayoutParams(mlp);
        LinearLayout.LayoutParams mlp2 = Ui.wrap();
        mlp2.setMargins(Ui.dp(c, 8), 0, 0, 0);
        stopBtn.setLayoutParams(mlp2);
        tRow.addView(rePoll);
        tRow.addView(stopBtn);
        aCard.addView(tRow);
        root.addView(aCard);

        // ---- result
        LinearLayout resCard = Theme.card(c);
        resCard.addView(Theme.section(c, "结果"));
        preview = new ImageView(c);
        preview.setAdjustViewBounds(true);
        preview.setScaleType(ImageView.ScaleType.FIT_CENTER);
        preview.setBackground(Theme.round(c, 0xFF0E131C, Theme.STROKE, 14, 1));
        LinearLayout.LayoutParams plp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(c, 260));
        plp.setMargins(0, Ui.dp(c, 10), 0, Ui.dp(c, 6));
        resCard.addView(preview, plp);
        resultMeta = Theme.note(c, "还没有图。点「开始出图」，结果会自动存进 图库/Pictures/" + Gallery.ALBUM);
        resCard.addView(resultMeta);
        root.addView(resCard);

        preview.setOnClickListener(v -> {
            if (ImageViewActivity.LAST != null) {
                getContext().startActivity(new Intent(getContext(), ImageViewActivity.class));
            }
        });
        pick.setOnClickListener(v -> ((MainActivity) getContext()).pickImages());
        addUrl.setOnClickListener(v -> {
            String u = refUrlEd.getText().toString().trim();
            if (!u.startsWith("http")) {
                toast("请输入以 http/https 开头的图片 URL");
                return;
            }
            refUris.add(u);
            refNames.add("URL · " + Http.abbr(u, 34));
            refUrlEd.setText("");
            refreshRefs();
        });
        genBtn.setOnClickListener(v -> confirmAndStart());
        stopBtn.setOnClickListener(v -> {
            cancel = true;
            log.log("已请求停止轮询（已提交的任务还在服务端跑，不会退款）");
        });
        rePoll.setOnClickListener(v -> {
            String id = taskIdEd.getText().toString().trim();
            if (id.isEmpty()) {
                toast("先填任务 ID");
                return;
            }
            startPollOnly(id);
        });

        log = new LogPane(c);
        root.addView(log);
        addView(root);

        updateCost();
        setRunning(false);
    }

    private void updateCost() {
        int n = countChips == null ? 1 : countChips.index() + 1;
        String q = qualityChips == null ? "auto" : qualityChips.value();
        String a = aspectChips == null ? "1024x1024" : aspectChips.value();
        String m = modelChips == null ? "" : modelChips.value();
        costTv.setText("将提交 " + n + " 张 · " + m + " / " + q + " / " + a
                + " · 提交前还会再确认一次（每次提交都消耗额度）");
    }

    // ------------------------------------------------------------------ refs

    public void onPickedImages(Intent data) {
        if (data == null) return;
        try {
            List<Uri> uris = new ArrayList<>();
            if (data.getClipData() != null) {
                for (int i = 0; i < data.getClipData().getItemCount(); i++) {
                    uris.add(data.getClipData().getItemAt(i).getUri());
                }
            } else if (data.getData() != null) {
                uris.add(data.getData());
            }
            for (Uri u : uris) addRefFromUri(u);
        } catch (Throwable t) {
            log.log("✗ 读取参考图失败: " + t);
        }
        refreshRefs();
    }

    private void addRefFromUri(Uri u) throws Exception {
        android.content.ContentResolver cr = getContext().getContentResolver();
        String mime = cr.getType(u);
        if (mime == null || !mime.startsWith("image/")) mime = "image/png";
        InputStream is = cr.openInputStream(u);
        if (is == null) throw new Exception("无法打开 " + u);
        byte[] b = readAll(is);
        if (b.length > 4 * 1024 * 1024) {
            toast("参考图过大（>4MB），已跳过");
            return;
        }
        refUris.add(Grsai.dataUri(mime, b));
        refNames.add("本地图 · " + (b.length / 1024) + " KB");
    }

    private void refreshRefs() {
        refBox.removeAllViews();
        if (refNames.isEmpty()) {
            refBox.addView(Theme.note(getContext(), "（当前没有参考图）"));
            return;
        }
        for (int i = 0; i < refNames.size(); i++) {
            final int idx = i;
            LinearLayout row = Ui.row(getContext());
            row.setPadding(0, Ui.dp(getContext(), 10), 0, 0);
            TextView t = Ui.text(getContext(), (i + 1) + "  " + refNames.get(i), 12.5f, false);
            t.setTextColor(Theme.TEXT);
            row.addView(t, Ui.weight(1f));
            Button x = Theme.small(getContext(), "移除");
            row.addView(x);
            x.setOnClickListener(v -> {
                refUris.remove(idx);
                refNames.remove(idx);
                refreshRefs();
            });
            refBox.addView(row);
        }
    }

    // ------------------------------------------------------------------ run

    private void confirmAndStart() {
        if (busy) {
            toast("还在跑，先等它结束或按「停止」");
            return;
        }
        String prompt = promptEd.getText().toString().trim();
        if (prompt.isEmpty()) {
            toast("请输入提示词");
            return;
        }
        if (prefs.get("grsai.key", "").isEmpty()) {
            toast("先去「设置」填 grsai API Key");
            return;
        }
        final String model = modelChips.value();
        final String quality = qualityChips.value();
        final String aspect = aspectChips.value();
        final int count = countChips.index() + 1;
        final boolean bg = bgCk.isChecked() && bgCk.isEnabled();

        StringBuilder msg = new StringBuilder();
        msg.append("模型  ").append(model).append('\n');
        msg.append("质量  ").append(quality).append('\n');
        msg.append("比例  ").append(aspect).append("（实际像素以返回文件为准）\n");
        msg.append("张数  ").append(count).append('\n');
        msg.append("参考图 ").append(refUris.size()).append(" 张\n");
        msg.append("透明  ").append(bg ? "是" : "否").append("\n\n");
        msg.append("提示词\n").append(Http.abbr(prompt, 140)).append("\n\n");
        msg.append("确认提交？（每次都消耗额度）");

        AlertDialog d = new AlertDialog.Builder(getContext())
                .setTitle("确认出图 · 扣费操作")
                .setMessage(msg.toString())
                .setPositiveButton("提交", (x, w) -> start(prompt, model, quality, aspect, count, bg))
                .setNegativeButton("取消", null)
                .create();
        d.show();
    }

    private void start(final String prompt, final String model, final String quality,
                       final String aspect, final int count, final boolean bg) {
        prefs.put("grsai.model", model);
        prefs.put("grsai.quality", quality);
        prefs.put("grsai.aspect", aspect);
        final String host = Grsai.resolveHost(prefs.get("grsai.host", "domestic"),
                prefs.get("grsai.host.custom", ""));
        final String key = prefs.get("grsai.key", "");
        cancel = false;
        busy = true;
        setRunning(true);
        ex.execute(() -> {
            final Grsai api = new Grsai(host, key);
            try {
                for (int i = 1; i <= count && !cancel; i++) {
                    final int idx = i;
                    ui(() -> statusTv.setText("提交中 " + idx + "/" + count + " …"));
                    log.log("[提交] " + idx + "/" + count + " " + model + " quality=" + quality
                            + " aspect=" + aspect + " refs=" + refUris.size() + " host=" + host);
                    JSONObject p = new JSONObject();
                    p.put("model", model);
                    p.put("prompt", prompt);
                    p.put("aspectRatio", aspect);
                    p.put("quality", quality);
                    if (bg) p.put("background", "transparent");
                    if (!refUris.isEmpty()) p.put("urls", Grsai.urlArray(refUris));
                    String tid = api.submit(p);
                    ui(() -> taskIdEd.setText(tid));
                    log.log("[任务] " + tid);
                    runOneTask(api, tid, idx, count);
                }
            } catch (Throwable t) {
                log.log("✗ " + t);
                ui(() -> statusTv.setText("出错"));
            } finally {
                busy = false;
                ui(() -> setRunning(false));
            }
        });
    }

    private void startPollOnly(final String tid) {
        if (busy) {
            toast("有任务在跑");
            return;
        }
        final String host = Grsai.resolveHost(prefs.get("grsai.host", "domestic"),
                prefs.get("grsai.host.custom", ""));
        final Grsai api = new Grsai(host, prefs.get("grsai.key", ""));
        cancel = false;
        busy = true;
        setRunning(true);
        log.log("[续查] " + tid);
        ex.execute(() -> {
            try {
                runOneTask(api, tid, 1, 1);
            } catch (Throwable t) {
                log.log("✗ " + t);
            } finally {
                busy = false;
                ui(() -> setRunning(false));
            }
        });
    }

    private void runOneTask(Grsai api, String tid, int idx, int count) throws Exception {
        int retries = 0;
        long t0 = System.currentTimeMillis();
        while (true) {
            sleep(5000);
            if (cancel) {
                log.log("已停止轮询（任务 " + tid + " 仍在服务端）");
                return;
            }
            if (System.currentTimeMillis() - t0 > 25 * 60 * 1000L) {
                log.log("等待超时（25 分钟），任务 " + tid + " 还在跑；可用「续查」继续。");
                return;
            }
            JSONObject d = api.pollOnce(tid);
            String st = d.optString("status", "?");
            int pr = d.optInt("progress", 0);
            final long secs = (System.currentTimeMillis() - t0) / 1000;
            ui(() -> {
                prog.setProgress(pr);
                statusTv.setText(idx + "/" + count + "   " + st + "   " + pr + "%   " + secs + "s");
                statusTv.setTextColor("succeeded".equals(st) ? Theme.OK
                        : "failed".equals(st) ? Theme.DANGER : Theme.ACCENT);
            });
            if ("succeeded".equals(st)) {
                JSONArray res = d.optJSONArray("results");
                if (res == null || res.length() == 0) {
                    log.log("✗ 状态成功但没有结果 URL");
                    return;
                }
                String url = res.optJSONObject(0).optString("url", "");
                log.log("[结果] " + url);
                byte[] png = api.download(url);
                String size = Grsai.pixelSize(png);
                SimpleDateFormat f = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US);
                String name = "grsai_" + f.format(new Date()) + ".png";
                String where;
                try {
                    where = Gallery.save(getContext(), name, png, "image/png");
                } catch (Throwable t) {
                    where = "保存失败(" + t.getMessage() + ")";
                }
                log.log("[已保存] " + where + "  实际像素=" + size + "  " + (png.length / 1024) + "KB");
                final byte[] img = png;
                final String s2 = size;
                final String w2 = where;
                ui(() -> {
                    Bitmap bm = BitmapFactory.decodeByteArray(img, 0, img.length);
                    preview.setImageBitmap(bm);
                    ImageViewActivity.LAST = img;
                    statusTv.setText("完成 " + s2);
                    statusTv.setTextColor(Theme.OK);
                    resultMeta.setText("实际像素 " + s2 + " · " + (img.length / 1024) + " KB · " + w2
                            + "（点图可全屏）");
                    prog.setProgress(100);
                });
                return;
            }
            if ("failed".equals(st)) {
                String reason = d.optString("failure_reason", "");
                String err = d.optString("error", "");
                log.log("✗ 失败 reason=" + reason + " error=" + Http.abbr(err, 300) + " (task " + tid + ")");
                if ("error".equals(reason) && retries < 2) {
                    retries++;
                    log.log("[重试] 第 " + retries + " 次（error 类失败会退款）");
                    sleep(3000);
                    continue;
                }
                if ("input_moderation".equals(reason) || "output_moderation".equals(reason)) {
                    log.log("内容审核拦截：按硬规则不改写提示词硬闯，请换正常题材。");
                }
                return;
            }
        }
    }

    // ------------------------------------------------------------------ misc

    private void setRunning(boolean running) {
        genBtn.setEnabled(!running);
        genBtn.setText(running ? "正在出图…" : "开始出图");
        genBtn.setAlpha(running ? 0.55f : 1f);
        stopBtn.setEnabled(running);
        stopBtn.setAlpha(running ? 1f : 0.5f);
        if (!running && prog.getProgress() < 100) prog.setProgress(0);
    }

    private void ui(Runnable r) {
        ui.post(r);
    }

    private void toast(final String s) {
        ui.post(() -> Toast.makeText(getContext(), s, Toast.LENGTH_LONG).show());
    }

    private static void sleep(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException ignored) {
        }
    }

    private static byte[] readAll(InputStream is) throws Exception {
        ByteArrayOutputStream bo = new ByteArrayOutputStream();
        byte[] buf = new byte[16384];
        int n;
        while ((n = is.read(buf)) > 0) bo.write(buf, 0, n);
        is.close();
        return bo.toByteArray();
    }
}
