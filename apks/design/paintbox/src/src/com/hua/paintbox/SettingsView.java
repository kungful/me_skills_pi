package com.hua.paintbox;

import android.app.Activity;
import android.app.AlertDialog;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class SettingsView extends android.widget.ScrollView {

    private final SecurePrefs prefs;
    private final ExecutorService ex = Executors.newSingleThreadExecutor();
    private final Handler ui = new Handler(Looper.getMainLooper());

    private EditText grsaiKeyEd, xgcTokenEd, hostCustomEd;
    private Theme.Chips hostChips;
    private TextView grsaiState, xgcState, storeState;
    private LogPane log;

    public SettingsView(Activity c) {
        super(c);
        prefs = new SecurePrefs(c);
        setFillViewport(true);
        setBackgroundColor(0x00000000);
        build(c);
    }

    private void build(Activity c) {
        LinearLayout root = Theme.screen(c);
        root.addView(Theme.hero(c, "设置", "密钥只存在这台手机里（Android Keystore AES-GCM）；请求由手机直接打到官方接口，中间没有任何服务器。",
                "LOCAL ONLY"));

        // ---------------- storage
        LinearLayout s = Theme.card(c);
        LinearLayout sRow = Ui.row(c);
        sRow.addView(Theme.section(c, "本地存储"), Ui.weight(1f));
        storeState = Theme.pill(c, prefs.encrypted() ? "已加密" : "明文",
                prefs.encrypted() ? Theme.OK : Theme.WARN);
        sRow.addView(storeState);
        s.addView(sRow);
        s.addView(Theme.note(c, prefs.encrypted()
                ? "Android Keystore 里的主密钥加密后写入应用私有目录。换机 / 卸载后无法解密，需要重新填。"
                : "⚠️ Keystore 不可用，密钥以明文存在应用私有目录（仅本机可读）。"));
        root.addView(s);

        // ---------------- grsai
        LinearLayout g = Theme.card(c);
        LinearLayout gh = Ui.row(c);
        gh.addView(Theme.section(c, "grsai 出图密钥"), Ui.weight(1f));
        grsaiState = Theme.pill(c, "—", Theme.MUTED);
        gh.addView(grsaiState);
        g.addView(gh);
        g.addView(Theme.note(c, "grsai 控制台里的 API Key，请求时放进 Authorization 头。"));
        g.addView(Theme.label(c, "api key"));
        grsaiKeyEd = Theme.secret(c, "sk-…");
        grsaiKeyEd.setText(prefs.get("grsai.key", ""));
        g.addView(grsaiKeyEd);

        g.addView(Theme.label(c, "接口线路"));
        hostChips = new Theme.Chips(c, new String[]{"国内 dakka", "海外 grsaiapi", "自定义"},
                hostName(prefs.get("grsai.host", "domestic")), null);
        g.addView(hostChips, Ui.matchWrap());

        g.addView(Theme.label(c, "自定义地址（可选）"));
        hostCustomEd = Theme.input(c, "https://… 留空则用所选线路", false, 1);
        hostCustomEd.setText(prefs.get("grsai.host.custom", ""));
        g.addView(hostCustomEd);

        LinearLayout gb = Ui.row(c);
        gb.setPadding(0, Ui.dp(c, 12), 0, 0);
        Button saveG = Theme.primary(c, "保存");
        Button testG = Theme.ghost(c, "测一下");
        gb.addView(saveG, Ui.weight(1f));
        LinearLayout.LayoutParams glp = Ui.wrap();
        glp.setMargins(Ui.dp(c, 8), 0, 0, 0);
        testG.setLayoutParams(glp);
        gb.addView(testG);
        g.addView(gb);
        g.addView(Theme.note(c, "「测一下」会真实提交一个最小任务来验证 Key（几分钱）。会先弹确认。"));
        root.addView(g);

        // ---------------- xgc
        LinearLayout x = Theme.card(c);
        LinearLayout xh = Ui.row(c);
        xh.addView(Theme.section(c, "仙宫云 访问令牌"), Ui.weight(1f));
        xgcState = Theme.pill(c, "—", Theme.MUTED);
        xh.addView(xgcState);
        x.addView(xh);
        x.addView(Theme.note(c, "控制台 → 访问令牌。令牌等于账号完全控制权，别外发、别截图。"));
        x.addView(Theme.label(c, "access token"));
        xgcTokenEd = Theme.secret(c, "访问令牌");
        xgcTokenEd.setText(prefs.get("xgc.token", ""));
        x.addView(xgcTokenEd);
        LinearLayout xb = Ui.row(c);
        xb.setPadding(0, Ui.dp(c, 12), 0, 0);
        Button saveX = Theme.primary(c, "保存");
        Button checkX = Theme.ghost(c, "校验令牌");
        Button clearX = Theme.ghost(c, "清空");
        xb.addView(saveX, Ui.weight(1f));
        xb.addView(gap(c, 8, checkX));
        xb.addView(gap(c, 8, clearX));
        x.addView(xb);
        x.addView(Theme.note(c, "本 App 硬性禁止删除镜像（技能 Hard Rule 0）：镜像列表只读，要删请去控制台。"));
        root.addView(x);

        // ---------------- about
        LinearLayout a = Theme.card(c);
        a.addView(Theme.section(c, "默认值与成本"));
        a.addView(Theme.divider(c));
        a.addView(kv(c, "跑图镜像", "f0cbf8c7-96c7-4010-a645-1898927c33ea"));
        a.addView(kv(c, "默认 GPU", "RTX 4090 D · ¥1.59 / 小时"));
        a.addView(kv(c, "计费规则", "只有「运行中」计费，开机/铺镜像是免费的"));
        a.addView(kv(c, "单张成本", "约 ¥0.025；一次开机跑 8 张约 ¥0.011 / 张"));
        a.addView(kv(c, "安全铁律", "永不删镜像；部署/启动/销毁都二次确认"));
        a.addView(Theme.divider(c));
        a.addView(Theme.note(c, "com.hua.paintbox · 纯 SDK 手搓，无 AndroidX、无中间服务器、无统计上报"));
        root.addView(a);

        log = new LogPane(c);
        root.addView(log);
        addView(root);

        refreshBadges();

        saveG.setOnClickListener(v -> {
            save();
            refreshBadges();
            log.log("已保存 grsai 配置（Key " + fp(prefs.get("grsai.key", "")) + "，线路 "
                    + prefs.get("grsai.host", "domestic") + "）");
            toast("已保存");
        });
        testG.setOnClickListener(v -> {
            save();
            refreshBadges();
            final String host = Grsai.resolveHost(prefs.get("grsai.host", "domestic"),
                    prefs.get("grsai.host.custom", ""));
            if (prefs.get("grsai.key", "").isEmpty()) {
                toast("先把 Key 填上");
                return;
            }
            new AlertDialog.Builder(getContext())
                    .setTitle("真的要提交吗？· 扣费")
                    .setMessage("会真实提交一个最小任务来验证 Key（通常几分钱）。\n\n"
                            + "线路  " + host + "\n模型  gpt-image-2 / 1024x1024\n\n继续？")
                    .setPositiveButton("提交测试", (d, w) -> ex.execute(() -> {
                        try {
                            final Grsai api = new Grsai(host, prefs.get("grsai.key", ""));
                            org.json.JSONObject p = new org.json.JSONObject();
                            p.put("model", "gpt-image-2");
                            p.put("prompt", "ping");
                            p.put("aspectRatio", "1024x1024");
                            p.put("webHook", "-1");
                            String id = api.submit(p);
                            ui.post(() -> {
                                log.log("✓ Key 可用，测试任务 id=" + id + "（去「AI 出图」用任务 ID 续查）");
                                toast("Key 可用");
                            });
                        } catch (Throwable t) {
                            ui.post(() -> log.log("✗ " + t));
                        }
                    }))
                    .setNegativeButton("算了", null)
                    .show();
        });

        saveX.setOnClickListener(v -> {
            save();
            refreshBadges();
            log.log("已保存仙宫云令牌 " + Xgc.fingerprint(prefs.get("xgc.token", "")));
            toast("已保存");
        });
        checkX.setOnClickListener(v -> {
            save();
            refreshBadges();
            ex.execute(() -> {
                try {
                    double bal = new Xgc(prefs.get("xgc.token", "")).balance();
                    final String line = "✓ 令牌可用 " + Xgc.fingerprint(prefs.get("xgc.token", ""))
                            + "  余额 ¥" + String.format("%.2f", bal);
                    ui.post(() -> {
                        log.log(line);
                        toast("令牌可用");
                    });
                } catch (Throwable t) {
                    ui.post(() -> log.log("✗ " + t));
                }
            });
        });
        clearX.setOnClickListener(v -> new AlertDialog.Builder(getContext())
                .setTitle("清空令牌？")
                .setMessage("会从本机删除保存的仙宫云访问令牌。云端实例不受影响。")
                .setPositiveButton("清空", (d, w) -> {
                    prefs.put("xgc.token", "");
                    xgcTokenEd.setText("");
                    refreshBadges();
                    toast("已清空");
                })
                .setNegativeButton("取消", null).show());
    }

    private View gap(Activity c, int dp, View v) {
        LinearLayout.LayoutParams lp = Ui.wrap();
        lp.setMargins(Ui.dp(c, dp), 0, 0, 0);
        v.setLayoutParams(lp);
        return v;
    }

    private View kv(Activity c, String k, String v) {
        LinearLayout l = Ui.row(c);
        l.setPadding(0, Ui.dp(c, 5), 0, Ui.dp(c, 5));
        LinearLayout left = Ui.col(c);
        TextView a = Ui.text(c, k, 12.5f, false);
        a.setTextColor(Theme.MUTED);
        left.addView(a);
        l.addView(left, Ui.lp(Ui.dp(c, 84), ViewGroup.LayoutParams.WRAP_CONTENT));
        TextView b = Ui.text(c, v, 12.5f, false);
        b.setTextColor(Theme.TEXT);
        l.addView(b, Ui.weight(1f));
        return l;
    }

    private void refreshBadges() {
        String gk = grsaiKeyEd.getText().toString().trim();
        grsaiState.setText(gk.isEmpty() ? "未设置" : fp(gk));
        grsaiState.setTextColor(gk.isEmpty() ? Theme.WARN : Theme.OK);
        grsaiState.setBackground(Theme.round(getContext(),
                Theme.blend(Theme.BG, gk.isEmpty() ? Theme.WARN : Theme.OK, 0.18f),
                Theme.blend(Theme.BG, gk.isEmpty() ? Theme.WARN : Theme.OK, 0.5f), 999, 1));
        String xk = xgcTokenEd.getText().toString().trim();
        xgcState.setText(xk.isEmpty() ? "未设置" : Xgc.fingerprint(xk));
        xgcState.setTextColor(xk.isEmpty() ? Theme.WARN : Theme.OK);
        xgcState.setBackground(Theme.round(getContext(),
                Theme.blend(Theme.BG, xk.isEmpty() ? Theme.WARN : Theme.OK, 0.18f),
                Theme.blend(Theme.BG, xk.isEmpty() ? Theme.WARN : Theme.OK, 0.5f), 999, 1));
    }

    private static String fp(String k) {
        if (k == null || k.isEmpty()) return "未设置";
        if (k.length() <= 8) return "已设置 " + k.length() + " 位";
        return k.substring(0, 4) + "…" + k.substring(k.length() - 4);
    }

    private static String hostName(String h) {
        if ("overseas".equals(h)) return "海外 grsaiapi";
        if ("custom".equals(h)) return "自定义";
        return "国内 dakka";
    }

    private static String hostPref(String label) {
        if (label.startsWith("海外")) return "overseas";
        if (label.startsWith("自定义")) return "custom";
        return "domestic";
    }

    private void save() {
        prefs.put("grsai.key", grsaiKeyEd.getText().toString().trim());
        prefs.put("xgc.token", xgcTokenEd.getText().toString().trim());
        prefs.put("grsai.host.custom", hostCustomEd.getText().toString().trim());
        prefs.put("grsai.host", hostPref(hostChips.value()));
    }

    private void toast(final String s) {
        Toast.makeText(getContext(), s, Toast.LENGTH_SHORT).show();
    }
}
