package com.hua.paintbox;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;

import org.json.JSONObject;

/** MCP 面板：开关、端口、监听范围、令牌、URL、工具清单、给 Mika 的配置。 */
public class McpView extends android.widget.ScrollView implements McpHost.Listener, Mcp.LogSink {

    private final Activity act;
    private final McpHost host;
    private final Handler ui = new Handler(Looper.getMainLooper());

    private Switch enableSw;
    private EditText portEd;
    private Theme.Chips bindChips;
    private TextView statePill, urlTv, tokenTv, toolsTv, configTv;
    private LogPane log;

    public McpView(Activity c) {
        super(c);
        act = c;
        host = McpHost.get(c);
        setFillViewport(true);
        setBackgroundColor(0x00000000);
        build();
        host.addListener(this);
        host.addSink(this);
    }

    @Override
    protected void onDetachedFromWindow() {
        host.removeListener(this);
        host.removeSink(this);
        super.onDetachedFromWindow();
    }

    @Override
    public void onMcpChanged() {
        ui.post(this::refresh);
    }

    @Override
    public void log(String line) {
        if (log != null) log.log(line);
    }

    // ------------------------------------------------------------------ build

    private void build() {
        LinearLayout root = Theme.screen(act);
        root.addView(Theme.hero(act, "MCP 控制",
                "把这个 App 变成一个 MCP 服务器：Mika（或别家 agent）连上 http://127.0.0.1:8766/mcp "
                        + "就能自己出图、取图。出图仍然用「设置」里那份 grsai Key，每次出图都扣费。",
                "STREAMABLE HTTP"));

        // ---- 开关
        LinearLayout on = Theme.card(act);
        LinearLayout onRow = Ui.row(act);
        onRow.addView(Theme.section(act, "服务开关"), Ui.weight(1f));
        statePill = Theme.pill(act, "—", Theme.MUTED);
        onRow.addView(statePill);
        on.addView(onRow);
        LinearLayout swRow = Ui.row(act);
        TextView swLabel = Ui.text(act, "开着（前台常驻，通知栏里有开关）", 13, false);
        swLabel.setTextColor(Theme.TEXT);
        swRow.addView(swLabel, Ui.weight(1f));
        enableSw = new Switch(act);
        enableSw.setChecked(host.enabled());
        enableSw.setOnCheckedChangeListener((v, checked) -> toggle(checked));
        swRow.addView(enableSw);
        on.addView(swRow);

        on.addView(Theme.label(act, "端口"));
        portEd = Theme.input(act, "8766", false, 1);
        portEd.setText(String.valueOf(host.port()));
        on.addView(portEd);

        on.addView(Theme.label(act, "监听范围"));
        bindChips = new Theme.Chips(act, new String[]{"只本机 127.0.0.1", "局域网 0.0.0.0"},
                McpHost.BIND_LAN.equals(host.bindMode()) ? "局域网 0.0.0.0" : "只本机 127.0.0.1", null);
        on.addView(bindChips, Ui.matchWrap());
        on.addView(Theme.note(act, "Mika 装在同一台手机上 → 选「只本机」最安全。"
                + "选局域网时会自动生成访问令牌，别在公共 WiFi 下开着。"));

        LinearLayout btnRow = Ui.row(act);
        btnRow.setPadding(0, Ui.dp(act, 12), 0, 0);
        Button save = Theme.primary(act, "保存并重启");
        save.setOnClickListener(v -> saveAndRestart());
        btnRow.addView(save, Ui.weight(1f));
        Button copyCfg = Theme.ghost(act, "复制给 Mika");
        LinearLayout.LayoutParams lp = Ui.wrap();
        lp.setMargins(Ui.dp(act, 8), 0, 0, 0);
        copyCfg.setLayoutParams(lp);
        copyCfg.setOnClickListener(v -> Ui.copy(act, "Mika MCP 配置", configJson()));
        btnRow.addView(copyCfg);
        on.addView(btnRow);
        root.addView(on);

        // ---- 连接信息
        LinearLayout info = Theme.card(act);
        info.addView(Theme.section(act, "连接信息"));
        urlTv = Theme.body(act, "");
        urlTv.setTextIsSelectable(true);
        info.addView(urlTv);
        info.addView(Theme.label(act, "访问令牌（可留空：只听本机时不需要）"));
        LinearLayout tokRow = Ui.row(act);
        tokenTv = Ui.text(act, "", 12.5f, false);
        tokenTv.setTextColor(Theme.TEXT);
        tokenTv.setTextIsSelectable(true);
        tokRow.addView(tokenTv, Ui.weight(1f));
        tokRow.addView(tokBtn("复制", () -> Ui.copy(act, "token", host.token())));
        tokRow.addView(tokBtn("换新", () -> {
            host.newToken();
            host.restart();
            refresh();
        }));
        tokRow.addView(tokBtn("清空", () -> {
            host.setToken("");
            host.restart();
            refresh();
        }));
        info.addView(tokRow);
        info.addView(Theme.note(act, "填了令牌，客户端必须在请求里带 Authorization: Bearer <令牌>。"
                + "也可以用 ?token=… 追加在 URL 后面（Mika 用「访问令牌」那一栏就行）。"));
        root.addView(info);

        // ---- 工具
        LinearLayout tl = Theme.card(act);
        tl.addView(Theme.section(act, "暴露的工具"));
        toolsTv = Theme.body(act, "");
        tl.addView(toolsTv);
        root.addView(tl);

        // ---- 配置
        LinearLayout cfg = Theme.card(act);
        LinearLayout ch = Ui.row(act);
        ch.addView(Theme.section(act, "Mika 里怎么加"), Ui.weight(1f));
        ch.addView(tokBtn("复制 JSON", () -> Ui.copy(act, "Mika MCP 配置", configJson())));
        cfg.addView(ch);
        configTv = Theme.body(act, "");
        configTv.setTextSize(11);
        configTv.setTypeface(android.graphics.Typeface.MONOSPACE);
        configTv.setTextIsSelectable(true);
        cfg.addView(configTv);
        cfg.addView(Theme.note(act, "Mika → 设置 → 电脑连接 / MCP → 外部 MCP 服务器 → 添加："
                + "传输 streamable-http、URL 上面那条、打开「允许本地 http」。"
                + "工具调用默认 60 秒超时，出图慢的话把这一条的超时调到 240 秒。"));
        root.addView(cfg);

        log = new LogPane(act, true);
        root.addView(log, Ui.matchWrap());

        addView(root);
        refresh();
    }

    private TextView tokBtn(String label, Runnable r) {
        TextView t = Ui.text(act, label, 12, false);
        t.setTextColor(Theme.ACCENT);
        t.setPadding(Ui.dp(act, 10), Ui.dp(act, 6), Ui.dp(act, 4), Ui.dp(act, 6));
        t.setOnClickListener(v -> r.run());
        return t;
    }

    // ------------------------------------------------------------------ actions

    private void toggle(boolean on) {
        host.setEnabled(on);
        Intent i = new Intent(act, McpService.class);
        i.setAction(on ? McpService.ACTION_START : McpService.ACTION_STOP);
        if (on) {
            if (Build.VERSION.SDK_INT >= 26) act.startForegroundService(i);
            else act.startService(i);
        } else {
            act.startService(i);
        }
        refresh();
    }

    private void saveAndRestart() {
        int p;
        try {
            p = Integer.parseInt(portEd.getText().toString().trim());
        } catch (Throwable t) {
            toast("端口要是数字");
            return;
        }
        if (p < 1024 || p > 65535) {
            toast("端口取 1024–65535");
            return;
        }
        host.setPort(p);
        host.setBindMode(bindChips.index() == 1 ? McpHost.BIND_LAN : McpHost.BIND_LOOPBACK);
        if (host.enabled()) {
            Intent i = new Intent(act, McpService.class).setAction(McpService.ACTION_START);
            if (Build.VERSION.SDK_INT >= 26) act.startForegroundService(i);
            else act.startService(i);
        } else {
            new AlertDialog.Builder(act).setTitle("服务是关着的")
                    .setMessage("设置已保存。把上面的开关打开，Mika 才能连。")
                    .setPositiveButton("好", null).show();
        }
        ui.postDelayed(this::refresh, 350);
    }

    private void toast(String s) {
        android.widget.Toast.makeText(act, s, android.widget.Toast.LENGTH_SHORT).show();
    }

    // ------------------------------------------------------------------ refresh

    private void refresh() {
        boolean on = host.enabled();
        boolean running = host.running();
        enableSw.setChecked(on);
        statePill.setText(running ? "监听中" : on ? "启动中/失败" : "已关闭");
        statePill.setTextColor(running ? Theme.OK : on ? Theme.WARN : Theme.MUTED);
        urlTv.setText(host.url()
                + (host.token().isEmpty() ? "" : "\n需要 Bearer 令牌"));
        tokenTv.setText(host.token().isEmpty() ? "（未设置）" : host.token());
        StringBuilder sb = new StringBuilder();
        Mcp server = host.server();
        if (server == null) {
            sb.append("服务没起来，工具清单在启动后加载。");
        } else {
            for (Mcp.Def d : server.defs()) {
                sb.append("· ").append(d.name).append("\n  ").append(d.description).append("\n");
            }
        }
        toolsTv.setText(sb.toString());
        configTv.setText(configJson());
        if (!portEd.hasFocus()) portEd.setText(String.valueOf(host.port()));
        bindChips.select(McpHost.BIND_LAN.equals(host.bindMode()) ? "局域网 0.0.0.0" : "只本机 127.0.0.1");
    }

    private String configJson() {
        try {
            JSONObject o = new JSONObject();
            o.put("name", "跑图助手");
            o.put("url", host.url());
            o.put("transport", "streamable-http");
            o.put("allowLocalHttp", true);
            o.put("auth", "token");
            o.put("token", host.token());
            o.put("timeoutSec", 240);
            return o.toString(2);
        } catch (Throwable t) {
            return "{}";
        }
    }
}
