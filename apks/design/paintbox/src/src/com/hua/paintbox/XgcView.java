package com.hua.paintbox;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
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
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class XgcView extends android.widget.ScrollView {

    private static final String DEFAULT_IMAGE = "f0cbf8c7-96c7-4010-a645-1898927c33ea";
    private static final String[] GPUS = {
            "NVIDIA GeForce RTX 4090 D",
            "NVIDIA GeForce RTX 4090",
            "NVIDIA GeForce RTX 4090 D 48G",
    };

    private final SecurePrefs prefs;
    private final ExecutorService ex = Executors.newSingleThreadExecutor();
    private final Handler ui = new Handler(Looper.getMainLooper());

    private TextView balanceTv, bannerTv, tokenTv, heroBadge;
    private LinearLayout instBox, deployBody;
    private TextView deployChev;
    private LogPane log;
    private Theme.Chips gpuChips, countChips, typeChips;
    private EditText imageEd, nameEd;
    private CheckBox ackCk;
    private CheckBox autoCk;
    private boolean autoRunning = false;

    public XgcView(Activity c) {
        super(c);
        prefs = new SecurePrefs(c);
        setFillViewport(true);
        setBackgroundColor(0x00000000);
        build(c);
        refreshAll();
    }

    private Xgc api() {
        return new Xgc(prefs.get("xgc.token", ""));
    }

    private void build(Activity c) {
        LinearLayout root = Theme.screen(c);

        LinearLayout hero = Theme.hero(c, "仙宫云 GPU", "按秒计费，只有「运行中」在烧钱 · 跑完立刻销毁", "XGC");
        heroBadge = (TextView) ((LinearLayout) hero.getChildAt(0)).getChildAt(1);
        root.addView(hero);

        // ---- status
        LinearLayout st = Theme.card(c);
        LinearLayout stRow = Ui.row(c);
        LinearLayout stCol = Ui.col(c);
        stCol.addView(Theme.label(c, "账户余额"));
        balanceTv = Ui.text(c, "¥ —", 27, true);
        balanceTv.setTextColor(Theme.TEXT);
        stCol.addView(balanceTv);
        stRow.addView(stCol, Ui.weight(1f));
        bannerTv = Ui.text(c, "检查中…", 11.5f, true);
        bannerTv.setGravity(Gravity.CENTER);
        bannerTv.setPadding(Ui.dp(c, 12), Ui.dp(c, 8), Ui.dp(c, 12), Ui.dp(c, 8));
        stRow.addView(bannerTv);
        st.addView(stRow);
        tokenTv = Theme.note(c, "令牌: —");
        tokenTv.setPadding(0, Ui.dp(c, 8), 0, 0);
        st.addView(tokenTv);

        LinearLayout bRow = Ui.row(c);
        bRow.setPadding(0, Ui.dp(c, 12), 0, 0);
        Button rf = Theme.ghost(c, "刷新");
        Button ck = Theme.ghost(c, "校验令牌");
        Button im = Theme.ghost(c, "我的镜像");
        bRow.addView(rf);
        bRow.addView(gapBtn(c, ck));
        bRow.addView(gapBtn(c, im));
        st.addView(bRow);

        autoCk = Theme.check(c, "自动刷新（15 秒，盯着计费状态）");
        autoCk.setPadding(0, Ui.dp(c, 10), 0, 0);
        st.addView(autoCk);
        root.addView(st);

        // ---- instances
        LinearLayout instCard = Theme.card(c);
        LinearLayout ih = Ui.row(c);
        ih.addView(Theme.section(c, "实例"), Ui.weight(1f));
        TextView hint = Theme.note(c, "点「ComfyUI 出图」直接跳去出图");
        ih.addView(hint);
        instCard.addView(ih);
        instBox = Ui.col(c);
        instBox.setPadding(0, Ui.dp(c, 6), 0, 0);
        instCard.addView(instBox);
        root.addView(instCard);

        // ---- deploy (collapsible)
        LinearLayout dep = Theme.card(c);
        LinearLayout dh = Ui.row(c);
        dh.setClickable(true);
        dh.addView(Theme.section(c, "新建实例"), Ui.weight(1f));
        deployChev = Ui.text(c, "▾", 15, true);
        deployChev.setTextColor(Theme.MUTED);
        dh.addView(deployChev);
        dep.addView(dh);
        dep.addView(Theme.note(c, "部署到「运行中」之前不计费；一旦运行中就开始按秒扣钱。"));

        deployBody = Ui.col(c);
        deployBody.setVisibility(View.GONE);
        deployBody.addView(Theme.label(c, "GPU 型号"));
        gpuChips = new Theme.Chips(c, GPUS, prefs.get("xgc.gpu", GPUS[0]), null);
        deployBody.addView(gpuChips, Ui.matchWrap());
        deployBody.addView(Theme.label(c, "数量"));
        countChips = new Theme.Chips(c, new String[]{"1", "2"}, "1", null);
        deployBody.addView(countChips, Ui.matchWrap());
        deployBody.addView(Theme.label(c, "镜像类型"));
        typeChips = new Theme.Chips(c, new String[]{"public", "community", "private"}, "public", null);
        deployBody.addView(typeChips, Ui.matchWrap());
        deployBody.addView(Theme.label(c, "镜像 ID"));
        imageEd = Theme.input(c, "镜像 id", false, 1);
        imageEd.setText(prefs.get("xgc.image", DEFAULT_IMAGE));
        imageEd.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12.5f);
        deployBody.addView(imageEd);
        deployBody.addView(Theme.note(c, "默认跑图镜像 f0cbf8c7…（「agent调用此镜像跑图」，用户手工维护，内容会变）"));
        deployBody.addView(Theme.label(c, "实例名（可选）"));
        nameEd = Theme.input(c, "例如 xgc-runpic", false, 1);
        deployBody.addView(nameEd);
        ackCk = Theme.check(c, "我确认这是扣费操作，且用完会销毁");
        ackCk.setPadding(0, Ui.dp(c, 12), 0, Ui.dp(c, 4));
        deployBody.addView(ackCk);
        Button depBtn = Theme.primary(c, "部署 · 开始计费");
        deployBody.addView(depBtn);
        dep.addView(deployBody);
        dh.setOnClickListener(v -> {
            boolean open = deployBody.getVisibility() != VISIBLE;
            deployBody.setVisibility(open ? VISIBLE : GONE);
            deployChev.animate().rotation(open ? 180 : 0).setDuration(140).start();
        });
        root.addView(dep);

        log = new LogPane(c);
        root.addView(log);
        addView(root);

        rf.setOnClickListener(v -> refreshAll());
        ck.setOnClickListener(v -> bg(() -> {
            String t = prefs.get("xgc.token", "");
            log.log("令牌指纹: " + Xgc.fingerprint(t));
            api().balance();
            log.log("鉴权 OK，令牌可用");
        }));
        im.setOnClickListener(v -> bg(() -> {
            JSONArray arr = api().images();
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < arr.length(); i++) {
                JSONObject o = arr.optJSONObject(i);
                if (o == null) continue;
                sb.append("· ").append(o.optString("name", "?")).append('\n')
                        .append("   ").append(o.optString("id", "?")).append("\n\n");
            }
            if (sb.length() == 0) sb.append("（没有私有镜像）");
            final String s = sb.toString();
            ui(() -> showText("我的镜像 · 只读（本 App 永不删镜像）", s));
            log.log("镜像列表: " + arr.length() + " 个");
        }));
        depBtn.setOnClickListener(v -> doDeploy());
        autoCk.setOnCheckedChangeListener((v, checked) -> {
            autoRunning = checked;
            if (checked) autoLoop();
        });
    }

    private View gapBtn(Activity c, View v) {
        LinearLayout.LayoutParams lp = Ui.wrap();
        lp.setMargins(Ui.dp(c, 8), 0, 0, 0);
        v.setLayoutParams(lp);
        return v;
    }

    // ------------------------------------------------------------------ deploy

    private void doDeploy() {
        if (!ackCk.isChecked()) {
            toast("先勾选确认（这是扣费操作）");
            return;
        }
        if (prefs.get("xgc.token", "").isEmpty()) {
            toast("先去「设置」填仙宫云访问令牌");
            return;
        }
        final JSONObject body = new JSONObject();
        try {
            body.put("gpu_model", gpuChips.value());
            body.put("gpu_count", Integer.parseInt(countChips.value()));
            body.put("data_center_id", 1);
            body.put("image", imageEd.getText().toString().trim());
            body.put("image_type", typeChips.value());
            String nm = nameEd.getText().toString().trim();
            if (!nm.isEmpty()) body.put("name", nm);
        } catch (Throwable t) {
            toast("参数有误: " + t);
            return;
        }
        String msg = "将要发送：\n\n" + Http.pretty(body.toString()) + "\n\n"
                + "参考价：RTX 4090 D = ¥1.59/小时 = ¥0.000442/秒。\n"
                + "开机等待免费，但进入「运行中」就开始扣钱，直到销毁。\n\n确认部署？";
        new AlertDialog.Builder(getContext())
                .setTitle("确认部署 · 扣费")
                .setMessage(msg)
                .setPositiveButton("确认部署", (d, w) -> {
                    prefs.put("xgc.image", imageEd.getText().toString().trim());
                    prefs.put("xgc.gpu", gpuChips.value());
                    ackCk.setChecked(false);
                    bg(() -> {
                        log.log("[部署] " + body);
                        JSONObject r = api().deploy(body);
                        log.log("[部署返回] " + Http.abbr(r.toString(), 600));
                        ui(() -> toast("已提交：开机中不计费，等它变「运行中」"));
                        sleep(4000);
                        refreshAllBlocking();
                    });
                })
                .setNegativeButton("取消", null)
                .show();
    }

    // ------------------------------------------------------------------ refresh

    public void refreshAll() {
        bg(this::refreshAllBlocking);
    }

    private void refreshAllBlocking() {
        try {
            Xgc x = api();
            final String tokenLine = "令牌: " + Xgc.fingerprint(prefs.get("xgc.token", ""))
                    + (prefs.encrypted() ? " · Keystore 加密" : " · 明文存储");
            ui(() -> tokenTv.setText(tokenLine));
            if (!x.hasToken()) {
                ui(() -> {
                    balanceTv.setText("¥ —");
                    setBanner("未设置令牌", Theme.WARN);
                    instBox.removeAllViews();
                    instBox.addView(Theme.note(getContext(), "去「设置」粘贴仙宫云访问令牌"));
                });
                return;
            }
            double bal = x.balance();
            final JSONArray arr = x.instances();
            final List<JSONObject> list = new ArrayList<>();
            int running = 0;
            for (int i = 0; i < arr.length(); i++) {
                JSONObject o = arr.optJSONObject(i);
                if (o == null) continue;
                list.add(o);
                if (Xgc.isRunning(o)) running++;
            }
            final int run = running;
            final StringBuilder logMsg = new StringBuilder();
            for (JSONObject o : list) {
                logMsg.append(Xgc.statusText(o)).append("  ").append(o.optString("name", ""))
                        .append("  ").append(o.optString("id", "")).append('\n');
            }
            final double balF = bal;
            ui(() -> {
                balanceTv.setText(String.format("¥ %.2f", balF));
                balanceTv.setTextColor(balF <= 0 ? Theme.DANGER : Theme.TEXT);
                setBanner(run > 0 ? run + " 台计费中" : "没有计费中的实例",
                        run > 0 ? Theme.DANGER : Theme.OK);
                heroBadge.setText(run > 0 ? "计费中 " + run : "空闲");
                renderInstances(list);
            });
            log.log("已刷新：" + list.size() + " 台实例，运行中 " + run + " 台；余额 ¥"
                    + String.format("%.2f", balF));
            if (run > 0) log.log("计费中：\n" + logMsg.toString().trim());
        } catch (Throwable t) {
            log.log("✗ " + t);
        }
    }

    private void setBanner(String text, int color) {
        bannerTv.setText(text);
        bannerTv.setTextColor(color);
        bannerTv.setBackground(Theme.round(getContext(), Theme.blend(Theme.BG, color, 0.18f),
                Theme.blend(Theme.BG, color, 0.5f), 999, 1));
    }

    private void renderInstances(List<JSONObject> list) {
        instBox.removeAllViews();
        if (list.isEmpty()) {
            LinearLayout empty = Ui.col(getContext());
            empty.setPadding(0, Ui.dp(getContext(), 10), 0, Ui.dp(getContext(), 6));
            TextView t = Ui.text(getContext(), "什么都没在跑 · 安全", 13.5f, true);
            t.setTextColor(Theme.OK);
            empty.addView(t);
            empty.addView(Theme.note(getContext(), "要出图就展开下面的「新建实例」部署一台。"));
            instBox.addView(empty);
            return;
        }
        for (JSONObject o : list) instBox.addView(card(o));
    }

    private View card(JSONObject inst) {
        Activity c = (Activity) getContext();
        LinearLayout card = Ui.col(c);
        card.setBackground(Theme.round(c, Theme.SURFACE2, Theme.STROKE, 16, 1));
        card.setPadding(Ui.dp(c, 14), Ui.dp(c, 12), Ui.dp(c, 14), Ui.dp(c, 14));
        LinearLayout.LayoutParams clp = Ui.matchWrap();
        clp.setMargins(0, Ui.dp(c, 8), 0, 0);
        card.setLayoutParams(clp);

        final String id = inst.optString("id", "?");
        boolean running = Xgc.isRunning(inst);
        String status = Xgc.statusText(inst);

        LinearLayout head = Ui.row(c);
        TextView name = Ui.text(c, inst.optString("name", "(未命名)"), 15.5f, true);
        name.setTextColor(Theme.TEXT);
        head.addView(name, Ui.weight(1f));
        head.addView(Theme.pill(c, status, Theme.colorFor(status)));
        card.addView(head);

        TextView idTv = Ui.text(c, id, 11.5f, false);
        idTv.setTextColor(Theme.MUTED);
        idTv.setPadding(0, Ui.dp(c, 6), 0, Ui.dp(c, 8));
        card.addView(idTv);

        LinearLayout meta = Ui.row(c);
        meta.addView(metaCol(c, "GPU", inst.optString("gpu_model", "?")
                + " × " + inst.optString("gpu_used", "?")), Ui.weight(1f));
        meta.addView(metaCol(c, "单价", "¥" + inst.optString("price_per_hour", "?") + " / 小时"), Ui.weight(1f));
        card.addView(meta);
        TextView created = Theme.note(c, "创建于 " + inst.optString("create_timestamp", "?"));
        created.setPadding(0, Ui.dp(c, 8), 0, 0);
        card.addView(created);

        LinearLayout r1 = Ui.row(c);
        r1.setPadding(0, Ui.dp(c, 12), 0, 0);
        Button comfy = Theme.primary(c, "ComfyUI 出图");
        comfy.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
        comfy.setMinHeight(Ui.dp(c, 40));
        Button copyId = Theme.small(c, "复制 ID");
        r1.addView(comfy, Ui.weight(1f));
        r1.addView(gapBtn(c, copyId));
        card.addView(r1);

        LinearLayout r2 = Ui.row(c);
        r2.setPadding(0, Ui.dp(c, 8), 0, 0);
        Button url = Theme.small(c, "URL");
        Button cred = Theme.small(c, "连接信息");
        Button boot = Theme.small(c, "启动");
        Button rel = Theme.small(c, "关机·释放GPU");
        r2.addView(url);
        r2.addView(gapBtn(c, cred));
        r2.addView(gapBtn(c, boot));
        r2.addView(gapBtn(c, rel));
        card.addView(r2);

        LinearLayout r3 = Ui.row(c);
        r3.setPadding(0, Ui.dp(c, 8), 0, 0);
        Button keep = Theme.small(c, "关机·留GPU（仍计费）");
        Button kill = Theme.danger(c, "销毁实例");
        kill.setTextSize(TypedValue.COMPLEX_UNIT_SP, 11.5f);
        kill.setMinHeight(Ui.dp(c, 30));
        kill.setPadding(Ui.dp(c, 10), Ui.dp(c, 4), Ui.dp(c, 10), Ui.dp(c, 4));
        r3.addView(keep);
        r3.addView(gapBtn(c, kill));
        card.addView(r3);

        comfy.setOnClickListener(v -> ((MainActivity) getContext()).showComfy(id));
        copyId.setOnClickListener(v -> Xgc.copy(getContext(), "xgc-id", id));
        url.setOnClickListener(v -> {
            String u = api().publicUrl(id, 8188);
            new AlertDialog.Builder(getContext())
                    .setTitle("公网地址")
                    .setMessage(u + "\n\nComfyUI 8188 · SD WebUI 7860 · Jupyter 8888 · SSH 22")
                    .setPositiveButton("复制", (d, w) -> Xgc.copy(getContext(), "url", u))
                    .setNeutralButton("浏览器打开", (d, w) -> {
                        try {
                            getContext().startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(u)));
                        } catch (Throwable t) {
                            toast("打不开浏览器: " + t);
                        }
                    })
                    .setNegativeButton("关闭", null)
                    .show();
        });
        cred.setOnClickListener(v -> {
            StringBuilder sb = new StringBuilder();
            sb.append("ssh   ").append(inst.optString("ssh_user", "root")).append('@')
                    .append(inst.optString("ssh_domain", id + "-22.container.x-gpu.com"))
                    .append(" -p ").append(inst.optString("ssh_port", "?")).append('\n');
            sb.append("密码  ").append(inst.optString("password", "(无)")).append('\n');
            sb.append("jupyter  ").append(inst.optString("jupyter_url", "-")).append('\n');
            sb.append("token    ").append(inst.optString("jupyter_token", "-")).append("\n\n");
            sb.append("你自己的账号凭据，别截图外发。");
            showText("连接信息 · " + Http.abbr(id, 12), sb.toString());
        });
        boot.setOnClickListener(v -> guard("启动实例 " + id + "\n（会重新开始按秒计费）",
                () -> lifeOp(id, "boot", x -> x.boot(id))));
        rel.setOnClickListener(v -> guard("关机并释放 GPU " + id
                        + "\n\nGPU 停止计费，系统盘 ¥0.00003/GB/小时 继续。",
                () -> lifeOp(id, "shutdown_release_gpu", x -> x.shutdownReleaseGpu(id))));
        keep.setOnClickListener(v -> guard("关机但保留 GPU " + id
                        + "\n\n⚠️ 仍然按小时计费，别这么干。",
                () -> lifeOp(id, "shutdown", x -> x.shutdown(id))));
        kill.setOnClickListener(v -> guard("销毁实例 " + id
                        + "\n\n数据全丢，计费立即停止。这是正确的收尾方式。",
                () -> lifeOp(id, "destroy", x -> x.destroy(id))));
        return card;
    }

    private View metaCol(Activity c, String label, String value) {
        LinearLayout l = Ui.col(c);
        TextView a = Theme.label(c, label);
        a.setPadding(0, 0, 0, Ui.dp(c, 2));
        l.addView(a);
        TextView b = Ui.text(c, value, 12.5f, false);
        b.setTextColor(Theme.TEXT);
        l.addView(b);
        return l;
    }

    private interface Op {
        JSONObject run(Xgc x) throws Exception;
    }

    private void lifeOp(String id, final String what, final Op op) {
        bg(() -> {
            try {
                JSONObject r = op.run(api());
                log.log("[已发送 " + what + " " + id + "] " + Http.abbr(r.toString(), 300));
                sleep(3000);
                refreshAllBlocking();
            } catch (Throwable t) {
                log.log("✗ " + what + " 失败: " + t);
            }
        });
    }

    private void guard(String what, final Runnable ok) {
        new AlertDialog.Builder(getContext())
                .setTitle("确认操作 · 改动账号状态")
                .setMessage(what + "\n\n确认执行？")
                .setPositiveButton("确认", (d, w) -> ok.run())
                .setNegativeButton("取消", null)
                .show();
    }

    private void showText(String title, String body) {
        TextView tv = Ui.text(getContext(), body, 12.5f, false);
        tv.setTextColor(Theme.TEXT);
        tv.setTextIsSelectable(true);
        tv.setLineSpacing(Ui.dp(getContext(), 3), 1f);
        int p = Ui.dp(getContext(), 18);
        tv.setPadding(p, Ui.dp(getContext(), 6), p, p);
        android.widget.ScrollView sv = new android.widget.ScrollView(getContext());
        sv.addView(tv);
        new AlertDialog.Builder(getContext()).setTitle(title).setView(sv)
                .setPositiveButton("关闭", null).show();
    }

    private void autoLoop() {
        ui.postDelayed(new Runnable() {
            @Override public void run() {
                if (!autoRunning) return;
                bg(XgcView.this::refreshAllBlocking);
                ui.postDelayed(this, 15000);
            }
        }, 15000);
    }

    private interface Task {
        void run() throws Exception;
    }

    private void bg(final Task r) {
        ex.execute(() -> {
            try {
                r.run();
            } catch (Throwable t) {
                log.log("✗ " + t);
            }
        });
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
}
