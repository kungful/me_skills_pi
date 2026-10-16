package com.picpe.cpe140;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.res.ColorStateList;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 易阔 CPE140 中继器控制台（Android）。
 * 全部功能走两条未认证通道：Web API + timectrl 的 root 命令注入。
 */
public class MainActivity extends AppCompatActivity {

    private static final String DEF_HOST = "192.168.188.254";

    private final ExecutorService ex = Executors.newSingleThreadExecutor();
    private final Handler ui = new Handler(Looper.getMainLooper());

    private Cpe cpe;
    private TextView status;
    private TextView[] out = new TextView[6];
    private Button[] tabs = new Button[6];
    private ScrollView[] panels = new ScrollView[6];
    private EditText hostBox, cmdBox, kKey, kVal, schW, schH, schM;
    private Switch schEn;
    private int tab = 1;

    private String pendingTask, pendingArg;
    private ActivityResultLauncher<String> createDoc;
    private ActivityResultLauncher<String[]> openDoc;

    // ------------------------------------------------------------ 生命周期

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        setContentView(R.layout.activity_main);

        // targetSdk 35+ 强制边到边：自己把系统栏/刘海的内边距补上，别让顶栏压状态栏
        View root = findViewById(R.id.root);
        ViewCompat.setOnApplyWindowInsetsListener(root, (v, ins) -> {
            androidx.core.graphics.Insets bars = ins.getInsets(
                    WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout());
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return ins;
        });

        status = findViewById(R.id.status);
        hostBox = findViewById(R.id.host);
        cmdBox = findViewById(R.id.cmd);
        kKey = findViewById(R.id.k_key);
        kVal = findViewById(R.id.k_val);
        schEn = findViewById(R.id.sch_en);
        schW = findViewById(R.id.sch_w);
        schH = findViewById(R.id.sch_h);
        schM = findViewById(R.id.sch_m);

        out[1] = findViewById(R.id.out1);
        out[2] = findViewById(R.id.out2);
        out[3] = findViewById(R.id.out3);
        out[4] = findViewById(R.id.out4);
        out[5] = findViewById(R.id.out5);

        int[] tabIds = {0, R.id.tab1, R.id.tab2, R.id.tab3, R.id.tab4, R.id.tab5};
        int[] panelIds = {0, R.id.panel1, R.id.panel2, R.id.panel3, R.id.panel4, R.id.panel5};
        for (int i = 1; i <= 5; i++) {
            tabs[i] = findViewById(tabIds[i]);
            panels[i] = findViewById(panelIds[i]);
            final int n = i;
            tabs[i].setOnClickListener(v -> selectTab(n));
        }

        createDoc = registerForActivityResult(new ActivityResultContracts.CreateDocument("application/octet-stream"),
                uri -> {
                    if (uri == null) {
                        say(out[tab], "已取消。");
                        return;
                    }
                    if ("dumpflash".equals(pendingTask)) {
                        final Uri u = uri;
                        bg(out[5], "正在经注入通道读取 /dev/mtd9（8MB，约 10 秒）…", () -> {
                            byte[] d = cpe.dumpFlash(9);
                            writeUri(u, d);
                            return "已备份 " + sz(d.length) + " → " + u.getLastPathSegment()
                                    + "\n（md5 请在本机用工具核对）";
                        });
                    } else if ("pull".equals(pendingTask)) {
                        final Uri u = uri;
                        final String remote = pendingArg;
                        bg(out[5], "正在下载 " + remote + " …", () -> {
                            byte[] d = cpe.readBytes(remote, 300000);
                            writeUri(u, d);
                            return "已下载 " + sz(d.length) + " → " + u.getLastPathSegment();
                        });
                    } else if ("cfgsave".equals(pendingTask)) {
                        final Uri u = uri;
                        bg(out[3], "正在导出全量配置…", () -> {
                            String j = cpe.cfgAll().toString(2);
                            writeUri(u, j.getBytes("UTF-8"));
                            return "配置已备份（" + sz(j.getBytes("UTF-8").length) + "）";
                        });
                    }
                });

        openDoc = registerForActivityResult(new ActivityResultContracts.OpenDocument(), uri -> {
            if (uri == null) {
                say(out[tab], "已取消。");
                return;
            }
            final Uri u = uri;
            final String remote = pendingArg;
            bg(out[5], "正在上传到 " + remote + " …", () -> {
                byte[] d = readUri(u);
                cpe.push(d, remote);
                return "已上传 " + sz(d.length) + " → " + remote + "\n（已在设备端 wc -c 校验）";
            });
        });

        findViewById(R.id.b_connect).setOnClickListener(v -> connect());

        // 1 概览
        on(R.id.b_info, 1, "设备信息", () -> Cpe.pretty(cpe.sysinfo()));
        on(R.id.b_link, 1, "链路状态（上游接入）", () -> Cpe.pretty(cpe.wirelessStatus()));
        on(R.id.b_wan, 1, "WAN", () -> Cpe.pretty(cpe.wan()));
        on(R.id.b_lan, 1, "LAN", () -> Cpe.pretty(cpe.lan()));
        on(R.id.b_wifi, 1, "无线配置", () -> Cpe.pretty(cpe.wifiConfig()));
        on(R.id.b_doctor, 1, "系统自检", () -> cpe.doctor());

        // 2 客户端
        on(R.id.b_clients, 2, "DHCP 客户端", () -> Cpe.pretty(cpe.clients()));
        on(R.id.b_arp, 2, "ARP 表", () -> {
            StringBuilder sb = new StringBuilder("IP 地址 / MAC / 接口\n");
            for (String[] r : cpe.arp()) {
                sb.append("  ").append(r[0]).append("  ").append(r[1]).append("  ").append(r[2]).append('\n');
            }
            return sb.toString();
        });
        on(R.id.b_scan, 2, "扫描周边 WiFi", () -> Cpe.pretty(cpe.scan()));
        on(R.id.b_chan, 2, "可用信道", () -> Cpe.pretty(cpe.channels()));

        // 3 配置
        on(R.id.b_cfgall, 3, "全量配置", () -> cpe.cfgAll().toString(2));
        findViewById(R.id.b_cfgsave).setOnClickListener(v -> {
            if (!ready(3)) return;
            pendingTask = "cfgsave";
            createDoc.launch("cpe140_config.json");
        });
        findViewById(R.id.b_cfgset).setOnClickListener(v -> {
            if (!ready(3)) return;
            String k = kKey.getText().toString().trim();
            String val = kVal.getText().toString();
            if (k.isEmpty()) {
                say(out[3], "先填 KEY。");
                return;
            }
            boolean danger = Cpe.DANGEROUS.contains(k.toUpperCase());
            if (danger) {
                confirm("危险键写入", k + " 属于可能中断连接/牵连无线的键，"
                                + "写错会掉线甚至失联（需拿网线+串口救）。\n确认要写吗？",
                        () -> bg(out[3], "写入 " + k + " …", () -> {
                            cpe.cfgSet(true, k, val);
                            return "写入 " + k + " = " + val + "\n返回 OK；改无线类字段会让 wifi 短暂重启。";
                        }));
            } else {
                bg(out[3], "写入 " + k + " …", () -> {
                    cpe.cfgSet(true, k, val);
                    return "写入 " + k + " = " + val;
                });
            }
        });

        // 4 终端
        findViewById(R.id.b_run).setOnClickListener(v -> {
            if (!ready(4)) return;
            runCmd(cmdBox.getText().toString());
        });
        quick(R.id.q1, "id");
        quick(R.id.q2, "ps w");
        quick(R.id.q3, "df -h");
        quick(R.id.q4, "ip a");
        quick(R.id.q5, "cat /proc/net/arp");
        quick(R.id.q6, "logread | tail -40");
        quick(R.id.q7, "ls -la /www");

        // 5 维护
        findViewById(R.id.b_dump).setOnClickListener(v -> {
            if (!ready(5)) return;
            pendingTask = "dumpflash";
            createDoc.launch("cpe140_fullflash.bin");
        });
        findViewById(R.id.b_pull).setOnClickListener(v -> {
            if (!ready(5)) return;
            input("下载设备文件", "设备上的路径（如 /etc/config/administrator）", "/etc/config/administrator", s -> {
                pendingTask = "pull";
                pendingArg = s;
                String name = s.substring(s.lastIndexOf('/') + 1);
                if (name.isEmpty()) name = "cpe140_file.bin";
                createDoc.launch(name);
            });
        });
        findViewById(R.id.b_push).setOnClickListener(v -> {
            if (!ready(5)) return;
            input("上传文件", "目标路径（如 /tmp/u.bin）", "/tmp/u.bin", s -> {
                pendingTask = "push";
                pendingArg = s;
                openDoc.launch(new String[]{"*/*"});
            });
        });
        findViewById(R.id.b_clean).setOnClickListener(v -> {
            if (!ready(5)) return;
            bg(out[5], "清理 /tmp/.cpeout /tmp/.cpesh /tmp/upload.img /www/.cpeout …", () -> {
                cpe.clean();
                return "已清理临时文件。";
            });
        });
        findViewById(R.id.b_pw).setOnClickListener(v -> {
            if (!ready(5)) return;
            LinearLayout l = new LinearLayout(this);
            l.setOrientation(LinearLayout.VERTICAL);
            l.setPadding(dp(16), dp(8), dp(16), dp(0));
            EditText u = et("admin", "用户名");
            EditText o = et("", "旧口令");
            EditText n = et("", "新口令");
            l.addView(u);
            l.addView(o);
            l.addView(n);
            new AlertDialog.Builder(this).setTitle("改 Web 管理员口令").setView(l)
                    .setPositiveButton("改", (d, w) -> bg(out[5], "改口令…", () -> {
                        JSONObject r = cpe.setPassword(u.getText().toString(), o.getText().toString(), n.getText().toString());
                        return "返回 " + r + "\n（未认证也能改，这正是要修的洞）";
                    }))
                    .setNegativeButton("取消", null).show();
        });
        findViewById(R.id.b_reboot).setOnClickListener(v -> {
            if (!ready(5)) return;
            confirm("重启设备", "重启期间中继器会断网约 40 秒，确认？",
                    () -> bg(out[5], "下发重启…", () -> {
                        cpe.reboot();
                        return "已下发重启。约 40 秒后重新连接。";
                    }));
        });
        findViewById(R.id.b_factory).setOnClickListener(v -> {
            if (!ready(5)) return;
            confirm("恢复出厂设置", "会清空全部配置（含无线名/口令）并重启！\n"
                            + "除非你有 easyconfig 备份和网线兜底，否则别点。确认？",
                    () -> bg(out[5], "下发恢复出厂…", () -> {
                        cpe.factoryReset();
                        return "已下发恢复出厂。设备将重启并回到出厂配置。";
                    }));
        });
        findViewById(R.id.b_read_sch).setOnClickListener(v -> bg(out[5], "读定时重启…", () -> {
            JSONObject s = cpe.sched();
            String t = "启用=" + s.optString("AUTO_REBOOT_ENABLED")
                    + " 周=" + s.optString("AUTO_REBOOT_WEEK")
                    + " 时=" + s.optString("AUTO_REBOOT_HOUR")
                    + " 分=" + s.optString("AUTO_REBOOT_MIN");
            ui.post(() -> {
                schEn.setChecked("1".equals(s.optString("AUTO_REBOOT_ENABLED")));
                schW.setText(s.optString("AUTO_REBOOT_WEEK"));
                schH.setText(s.optString("AUTO_REBOOT_HOUR"));
                schM.setText(s.optString("AUTO_REBOOT_MIN"));
            });
            return t;
        }));
        findViewById(R.id.b_sched).setOnClickListener(v -> {
            if (!ready(5)) return;
            int w = num(schW.getText().toString(), 0), h = num(schH.getText().toString(), 4), m = num(schM.getText().toString(), 0);
            bg(out[5], "写定时重启…", () -> {
                cpe.setSchedule(schEn.isChecked(), w, h, m);
                return "已设置：启用=" + schEn.isChecked() + " 周=" + w + " 时=" + h + " 分=" + m;
            });
        });

        selectTab(1);
        ui.postDelayed(this::connect, 300);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        ex.execute(() -> {
            if (cpe != null) cpe.clean();
        });
        ex.shutdown();
    }

    // -------------------------------------------------------------- 小工具

    private static int num(String s, int def) {
        try {
            return Integer.parseInt(s.trim());
        } catch (Exception e) {
            return def;
        }
    }

    private int dp(int v) {
        return Math.round(getResources().getDisplayMetrics().density * v);
    }

    private static String sz(long n) {
        if (n < 1024) return n + " B";
        if (n < 1024 * 1024) return String.format(Locale.US, "%.1f KB", n / 1024.0);
        return String.format(Locale.US, "%.2f MB", n / 1048576.0);
    }

    private EditText et(String val, String hint) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setText(val);
        e.setSingleLine(true);
        e.setTextColor(ContextCompat.getColor(this, R.color.text));
        e.setHintTextColor(ContextCompat.getColor(this, R.color.dim));
        return e;
    }

    private void selectTab(int n) {
        tab = n;
        for (int i = 1; i <= 5; i++) {
            panels[i].setVisibility(i == n ? View.VISIBLE : View.GONE);
            tabs[i].setBackgroundResource(i == n ? R.drawable.bg_tab_on : R.drawable.bg_tab);
            tabs[i].setTextColor(ContextCompat.getColor(this, i == n ? R.color.cyan : R.color.tab_text));
        }
    }

    private void quick(int id, String cmd) {
        Button b = findViewById(id);
        b.setOnClickListener(v -> {
            cmdBox.setText(cmd);
            if (ready(4)) runCmd(cmd);
        });
        b.setOnLongClickListener(v -> {
            cmdBox.setText(cmd);
            return true;
        });
    }

    private void on(int id, int panel, String label, Task t) {
        findViewById(id).setOnClickListener(v -> {
            if (ready(panel)) bg(out[panel], label + " …", t);
        });
    }

    private boolean ready(int panel) {
        if (cpe == null) {
            Toast.makeText(this, "先点「连接」", Toast.LENGTH_SHORT).show();
            selectTab(1);
            return false;
        }
        return true;
    }

    private void runCmd(String cmd) {
        String c = cmd.trim();
        if (c.isEmpty()) return;
        bg(out[4], "$ " + c, () -> {
            String r = cpe.run(c);
            return r == null || r.trim().isEmpty() ? "（无输出）" : r;
        });
    }

    private interface Task {
        String run() throws Exception;
    }

    private void bg(TextView target, String label, Task t) {
        target.setText(label);
        ex.execute(() -> {
            String s;
            try {
                s = t.run();
            } catch (Throwable e) {
                s = "✗ " + e.getClass().getSimpleName() + ": " + e.getMessage()
                        + "\n（设备离线 / IP 变了 / 中继掉了？）";
            }
            final String r = s;
            ui.post(() -> target.setText(label + (label.endsWith("…") ? "\n" : "\n\n") + r));
        });
    }

    private void say(TextView target, String s) {
        target.setText(s);
    }

    private void confirm(String title, String msg, Runnable ok) {
        new AlertDialog.Builder(this).setTitle(title).setMessage(msg)
                .setPositiveButton("确认", (d, w) -> ok.run())
                .setNegativeButton("取消", null).show();
    }

    private void input(String title, String hint, String def, java.util.function.Consumer<String> ok) {
        EditText e = et(def, hint);
        new AlertDialog.Builder(this).setTitle(title).setView(e)
                .setPositiveButton("确定", (d, w) -> ok.accept(e.getText().toString().trim()))
                .setNegativeButton("取消", null).show();
    }

    // ------------------------------------------------------------- 连接

    private void connect() {
        final String h = hostBox.getText().toString().trim();
        if (h.isEmpty()) {
            Toast.makeText(this, "填设备地址", Toast.LENGTH_SHORT).show();
            return;
        }
        cpe = new Cpe(h);
        status.setTextColor(ContextCompat.getColor(this, R.color.amber));
        status.setText("连接 " + h + " …");
        ex.execute(() -> {
            try {
                JSONObject si = cpe.sysinfo();
                JSONObject cfg = cpe.cfgAll();
                final String msg = si.optString("PRODUCTNAME", "?") + " · " + si.optString("FIRMVERSION", "?")
                        + " · 未认证可读 " + cfg.length() + " 项配置";
                JSONObject wl = cpe.wirelessStatus();
                final String link = "上游 " + wl.optString("ssid") + " ch" + wl.optString("channel")
                        + " rssi " + wl.optString("rssi") + "dBm";
                try {
                    JSONObject s = cpe.sched();
                    ui.post(() -> {
                        schEn.setChecked("1".equals(s.optString("AUTO_REBOOT_ENABLED")));
                        schW.setText(s.optString("AUTO_REBOOT_WEEK"));
                        schH.setText(s.optString("AUTO_REBOOT_HOUR"));
                        schM.setText(s.optString("AUTO_REBOOT_MIN"));
                    });
                } catch (Exception ignored) {
                }
                ui.post(() -> {
                    status.setTextColor(ContextCompat.getColor(this, R.color.cyan));
                    status.setText("已连接 " + msg + "\n" + link);
                    out[1].setText("设备可达。点上面按钮看数据，或去「终端」以 root 跑命令。");
                });
            } catch (Throwable e) {
                ui.post(() -> {
                    status.setTextColor(ContextCompat.getColor(this, R.color.red));
                    status.setText("连接失败：" + e.getMessage() + "\n（手机要连到中继器自己的 WiFi 或其后级网络）");
                });
            }
        });
    }

    // ------------------------------------------------------------- SAF IO

    private void writeUri(Uri u, byte[] d) throws Exception {
        OutputStream o = getContentResolver().openOutputStream(u);
        if (o == null) throw new Exception("无法写入目标");
        o.write(d);
        o.close();
    }

    private byte[] readUri(Uri u) throws Exception {
        InputStream in = getContentResolver().openInputStream(u);
        if (in == null) throw new Exception("无法读取所选文件");
        ByteArrayOutputStream bo = new ByteArrayOutputStream();
        byte[] buf = new byte[1 << 16];
        int n;
        while ((n = in.read(buf)) > 0) {
            bo.write(buf, 0, n);
        }
        in.close();
        return bo.toByteArray();
    }
}
