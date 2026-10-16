package com.hua.paintbox;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * In-app ComfyUI console: the 仙宫云 container exposes 8188 publicly as
 * https://<instance-id>-8188.container.x-gpu.com, so the phone drives it directly - no PC needed.
 */
public class ComfyView extends LinearLayout {

    private final SecurePrefs prefs;
    private final ExecutorService ex = Executors.newSingleThreadExecutor();
    private final Handler ui = new Handler(Looper.getMainLooper());

    private EditText idEd;
    private Theme.Chips portChips;
    private WebView web;
    private TextView statusTv;
    private ProgressBar prog;

    public ComfyView(Activity c) {
        super(c);
        prefs = new SecurePrefs(c);
        setOrientation(VERTICAL);
        setBackgroundColor(0x00000000);
        build(c);
    }

    private void build(Activity c) {
        LinearLayout head = Ui.col(c);
        head.setPadding(Ui.dp(c, 16), Ui.dp(c, 12), Ui.dp(c, 16), Ui.dp(c, 8));

        LinearLayout bar = Theme.card(c);
        LinearLayout t = Ui.row(c);
        t.addView(Theme.section(c, "ComfyUI 控制台"), Ui.weight(1f));
        statusTv = Theme.pill(c, "未连接", Theme.MUTED);
        t.addView(statusTv);
        bar.addView(t);
        bar.addView(Theme.note(c, "先在「仙宫云」部署 / 启动实例，等它变成「运行中」，再来这里打开。"
                + "手机浏览器直连实例的 8188 公网端口，全程不经过电脑。"));

        bar.addView(Theme.label(c, "实例 ID"));
        idEd = Theme.input(c, "在「仙宫云」标签页复制实例 ID", false, 1);
        idEd.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, 13);
        bar.addView(idEd);

        bar.addView(Theme.label(c, "端口"));
        portChips = new Theme.Chips(c, new String[]{"8188 ComfyUI", "7860 SD WebUI",
                "8888 Jupyter", "22 SSH"}, "8188 ComfyUI", null);
        bar.addView(portChips, Ui.matchWrap());

        LinearLayout r2 = Ui.row(c);
        r2.setPadding(0, Ui.dp(c, 12), 0, 0);
        Button open = Theme.primary(c, "打开");
        Button pick = Theme.ghost(c, "选实例");
        Button probe = Theme.ghost(c, "探测");
        Button ext = Theme.ghost(c, "外部浏览器");
        r2.addView(open, Ui.weight(1f));
        r2.addView(margin(pick, 8));
        bar.addView(r2);
        LinearLayout r3 = Ui.row(c);
        r3.setPadding(0, Ui.dp(c, 8), 0, 0);
        r3.addView(probe);
        r3.addView(margin(ext, 8));
        bar.addView(r3);

        prog = Theme.progress(c);
        LinearLayout.LayoutParams plp = Ui.matchWrap();
        plp.setMargins(0, Ui.dp(c, 12), 0, 0);
        prog.setLayoutParams(plp);
        bar.addView(prog);
        head.addView(bar);
        addView(head, Ui.matchWrap());

        web = new WebView(c);
        web.setBackgroundColor(0xFF0E131C);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);
        s.setBuiltInZoomControls(true);
        s.setDisplayZoomControls(false);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        s.setUserAgentString(s.getUserAgentString() + " PaintBox/1.0");
        web.setWebViewClient(new WebViewClient() {
            @Override public void onPageStarted(WebView v, String url, Bitmap f) {
                prog.setProgress(5);
                setStatus("加载中…", Theme.ACCENT);
            }
            @Override public void onPageFinished(WebView v, String url) {
                prog.setProgress(100);
                setStatus("已加载", Theme.OK);
            }
            @Override public boolean shouldOverrideUrlLoading(WebView v, String url) {
                return false;
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public void onProgressChanged(WebView v, int np) {
                prog.setProgress(np);
            }
        });
        LinearLayout webWrap = Ui.col(c);
        webWrap.setPadding(Ui.dp(c, 10), 0, Ui.dp(c, 10), Ui.dp(c, 10));
        webWrap.addView(web, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        addView(webWrap, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        open.setOnClickListener(v -> load());
        probe.setOnClickListener(v -> probe());
        pick.setOnClickListener(v -> pickInstance());
        ext.setOnClickListener(v -> {
            String u = url();
            if (u == null) return;
            try {
                getContext().startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(u)));
            } catch (Throwable t2) {
                toast("打不开浏览器: " + t2);
            }
        });

        idEd.setText(prefs.get("comfy.lastId", ""));
    }

    private View margin(View v, int dp) {
        LinearLayout.LayoutParams lp = Ui.wrap();
        lp.setMargins(Ui.dp(getContext(), dp), 0, 0, 0);
        v.setLayoutParams(lp);
        return v;
    }

    private void setStatus(String s, int color) {
        statusTv.setText(s);
        statusTv.setTextColor(color);
        statusTv.setBackground(Theme.round(getContext(),
                Theme.blend(Theme.BG, color, 0.18f), Theme.blend(Theme.BG, color, 0.5f), 999, 1));
    }

    public void setInstanceId(String id) {
        idEd.setText(id);
        if (id != null && !id.isEmpty()) load();
    }

    private int port() {
        String v = portChips.value();
        try {
            return Integer.parseInt(v.split(" ")[0]);
        } catch (Throwable t) {
            return 8188;
        }
    }

    private String url() {
        String id = idEd.getText().toString().trim();
        if (id.isEmpty()) {
            toast("先填实例 ID（在「仙宫云」标签页里复制）");
            return null;
        }
        return "https://" + id + "-" + port() + ".container.x-gpu.com";
    }

    private void load() {
        String u = url();
        if (u == null) return;
        prefs.put("comfy.lastId", idEd.getText().toString().trim());
        prog.setProgress(0);
        setStatus("连接中…", Theme.WARN);
        web.loadUrl(u);
    }

    /** Cheap readiness check that needs no SSH: ComfyUI answers /system_stats with 200. */
    private void probe() {
        final String u = url();
        if (u == null) return;
        final String body = u + (port() == 8188 ? "/system_stats" : "/");
        ex.execute(() -> {
            try {
                String res = Http.get(body, null, 15000);
                ui.post(() -> {
                    setStatus("已就绪", Theme.OK);
                    statusLine("✓ " + Http.abbr(res.replaceAll("\\s+", " "), 200));
                    toast("服务活着，可以出图了");
                });
            } catch (Throwable t) {
                ui.post(() -> {
                    setStatus("探测失败", Theme.DANGER);
                    toast("连不上: " + t);
                });
            }
        });
    }

    private void statusLine(final String s) {
        new AlertDialog.Builder(getContext()).setTitle("探测结果").setMessage(s)
                .setPositiveButton("好", null).show();
    }

    private void pickInstance() {
        ex.execute(() -> {
            try {
                final JSONArray arr = new Xgc(prefs.get("xgc.token", "")).instances();
                ui.post(() -> {
                    final java.util.List<String> ids = new java.util.ArrayList<>();
                    final java.util.List<String> labels = new java.util.ArrayList<>();
                    for (int i = 0; i < arr.length(); i++) {
                        JSONObject o = arr.optJSONObject(i);
                        if (o == null) continue;
                        ids.add(o.optString("id"));
                        labels.add(Xgc.statusText(o) + " · " + o.optString("name", "") + "\n"
                                + o.optString("id"));
                    }
                    if (ids.isEmpty()) {
                        toast("没有实例，先去「仙宫云」部署一台");
                        return;
                    }
                    new AlertDialog.Builder(getContext())
                            .setTitle("选一台实例")
                            .setItems(labels.toArray(new String[0]), (d, w) -> setInstanceId(ids.get(w)))
                            .show();
                });
            } catch (Throwable t) {
                ui.post(() -> toast("读取实例失败: " + t));
            }
        });
    }

    private void toast(final String s) {
        ui.post(() -> Toast.makeText(getContext(), s, Toast.LENGTH_LONG).show());
    }
}
