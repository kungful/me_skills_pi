package com.picpe.cpe140;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
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
 *
 * 全部功能走两条未认证通道：
 *   1) Web API（/cgi-bin/*）读/写配置、重启、改口令；
 *   2) /cgi-bin/timectrl 的 root 命令注入 —— 等价于设备的 root shell。
 *
 * UI：纯自绘深色风格（自写 drawable + 自写底部导航），不依赖 Material 主题。
 */
public class MainActivity extends AppCompatActivity {

    private static final String DEF_HOST = "192.168.188.254";

    private final ExecutorService ex = Executors.newSingleThreadExecutor();
    private final Handler ui = new Handler(Looper.getMainLooper());

    private Cpe cpe;
    private TextView status, pill, guardState, fixState;
    private TextView[] out = new TextView[6];
    private ScrollView[] panels = new ScrollView[6];
    private LinearLayout[] navs = new LinearLayout[6];
    private ImageView[] navIcons = new ImageView[6];
    private TextView[] navLabels = new TextView[6];
    private EditText hostBox, cmdBox, kKey, kVal, schW, schH, schM, guardMin;
    private Switch schEn;
    private int tab = 1;

    private final List<String> hist = new ArrayList<>();
    private int histPos = -1;

    private String pendingTask, pendingArg;
    private ActivityResultLauncher<String> createDoc;
    private ActivityResultLauncher<String[]> openDoc;

    // ============================================================ 生命周期

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        setContentView(R.layout.activity_main);

        // targetSdk 35+ 强制边到边：自己把系统栏/刘海的内边距补上
        View root = findViewById(R.id.root);
        ViewCompat.setOnApplyWindowInsetsListener(root, (v, ins) -> {
            androidx.core.graphics.Insets bars = ins.getInsets(
                    WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout());
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return ins;
        });

        pill = findViewById(R.id.pill_state);
        status = findViewById(R.id.status);
        hostBox = findViewById(R.id.host);
        cmdBox = findViewById(R.id.cmd);
        kKey = findViewById(R.id.k_key);
        kVal = findViewById(R.id.k_val);
        schEn = findViewById(R.id.sch_en);
        schW = findViewById(R.id.sch_w);
        schH = findViewById(R.id.sch_h);
        schM = findViewById(R.id.sch_m);
        guardMin = findViewById(R.id.guardMin);
        guardState = findViewById(R.id.guardState);
        fixState = findViewById(R.id.fixState);

        out[1] = findViewById(R.id.out1);
        out[2] = findViewById(R.id.out2);
        out[3] = findViewById(R.id.out3);
        out[4] = findViewById(R.id.out4);
        out[5] = findViewById(R.id.out5);

        int[] navIds = {0, R.id.nav1, R.id.nav2, R.id.nav3, R.id.nav4, R.id.nav5};
        int[] iconIds = {0, R.id.navi1, R.id.navi2, R.id.navi3, R.id.navi4, R.id.navi5};
        int[] labelIds = {0, R.id.navt1, R.id.navt2, R.id.navt3, R.id.navt4, R.id.navt5};
        int[] panelIds = {0, R.id.panel1, R.id.panel2, R.id.panel3, R.id.panel4, R.id.panel5};
        for (int i = 1; i <= 5; i++) {
            navs[i] = findViewById(navIds[i]);
            navIcons[i] = findViewById(iconIds[i]);
            navLabels[i] = findViewById(labelIds[i]);
            panels[i] = findViewById(panelIds[i]);
            final int n = i;
            navs[i].setOnClickListener(v -> selectTab(n));
        }

        createDoc = registerForActivityResult(
                new ActivityResultContracts.CreateDocument("application/octet-stream"), uri -> {
                    if (uri == null) {
                        say(out[tab], "已取消。");
                        return;
                    }
                    final Uri u = uri;
                    if ("dumpflash".equals(pendingTask)) {
                        bg(out[5], "正在读取 /dev/mtd9（8MB，约 10 秒）…", () -> {
                            byte[] d = cpe.dumpFlash(9);
                            writeUri(u, d);
                            return "已备份 " + sz(d.length) + " → " + u.getLastPathSegment()
                                    + "\n（md5 可在电脑上用 cpe140.py 复核）";
                        });
                    } else if ("pull".equals(pendingTask)) {
                        final String remote = pendingArg;
                        bg(out[5], "正在下载 " + remote + " …", () -> {
                            byte[] d = cpe.readBytes(remote, 300000);
                            writeUri(u, d);
                            return "已下载 " + sz(d.length) + " → " + u.getLastPathSegment();
                        });
                    } else if ("cfgsave".equals(pendingTask)) {
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

        findViewById(R.id.b_connect).setOnClickListener(v -> {
            hideKeyboard();
            connect();
        });

        // ---------------------------------------------------------- 1 概览
        on(R.id.b_info, 1, "设备信息", () -> Cpe.pretty(cpe.sysinfo()));
        on(R.id.b_link, 1, "链路状态（上游接入）", () -> Cpe.pretty(cpe.wirelessStatus()));
        on(R.id.b_wan, 1, "WAN", () -> Cpe.pretty(cpe.wan()));
        on(R.id.b_lan, 1, "LAN", () -> Cpe.pretty(cpe.lan()));
        on(R.id.b_wifi, 1, "无线配置", () -> Cpe.pretty(cpe.wifiConfig()));
        on(R.id.b_doctor, 1, "系统自检", () -> cpe.doctor());

        // -------------------------------------------------------- 2 客户端
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

        // ---------------------------------------------------------- 3 配置
        on(R.id.b_cfgall, 3, "全量配置", () -> cpe.cfgAll().toString(2));
        findViewById(R.id.b_cfgsave).setOnClickListener(v -> {
            if (!ready(3)) return;
            pendingTask = "cfgsave";
            createDoc.launch("cpe140_config.json");
        });
        findViewById(R.id.b_cfgset).setOnClickListener(v -> {
            if (!ready(3)) return;
            hideKeyboard();
            final String k = kKey.getText().toString().trim();
            final String val = kVal.getText().toString();
            if (k.isEmpty()) {
                say(out[3], "先填 KEY，例如 SysDevName。");
                return;
            }
            if (Cpe.DANGEROUS.contains(k.toUpperCase())) {
                confirm("危险键写入", k + " 属于可能中断连接 / 牵连无线的键，"
                                + "写错会掉线甚至失联。\n确认要写吗？",
                        () -> bg(out[3], "写入 " + k + " …", () -> {
                            cpe.cfgSet(true, k, val);
                            return "已写 " + k + " = " + val + "\n（改无线类字段会让 wifi 短暂重启）";
                        }));
            } else {
                bg(out[3], "写入 " + k + " …", () -> {
                    cpe.cfgSet(true, k, val);
                    return "已写 " + k + " = " + val;
                });
            }
        });

        // ---------------------------------------------------------- 4 终端
        findViewById(R.id.b_help).setOnClickListener(v ->
                Help.show(this, s -> cmdBox.setText(s)));
        findViewById(R.id.b_hist).setOnClickListener(v -> {
            if (hist.isEmpty()) {
                toast("还没有历史命令");
                return;
            }
            histPos = histPos <= 0 ? hist.size() - 1 : histPos - 1;
            cmdBox.setText(hist.get(histPos));
            cmdBox.setSelection(cmdBox.getText().length());
        });
        findViewById(R.id.b_clear).setOnClickListener(v -> say(out[4], "$ 界面已清空，历史还在「↑ 上一条」里。"));
        findViewById(R.id.b_run).setOnClickListener(v -> {
            hideKeyboard();
            runCmd(cmdBox.getText().toString());
        });
        cmdBox.setOnEditorActionListener((v, actionId, ev) -> {
            hideKeyboard();
            runCmd(cmdBox.getText().toString());
            return true;
        });
        quick(R.id.q1, "id; uname -a", "我是谁");
        quick(R.id.q2, "ps w", "进程");
        quick(R.id.q3, "df -h", "磁盘");
        quick(R.id.q4, "ip a", "网卡与地址");
        quick(R.id.q5, "cat /proc/net/arp", "在线设备");
        quick(R.id.q6, "logread | tail -40", "系统日志");
        quick(R.id.q7, "ls -la /www; ls -la /etc/config", "网站目录");

        // ---------------------------------------------------------- 5 维护
        findViewById(R.id.b_dump).setOnClickListener(v -> {
            if (!ready(5)) return;
            pendingTask = "dumpflash";
            createDoc.launch("cpe140_fullflash.bin");
        });
        findViewById(R.id.b_pull).setOnClickListener(v -> {
            if (!ready(5)) return;
            input("下载设备文件", "设备上的路径", "/etc/config/administrator", s -> {
                pendingTask = "pull";
                pendingArg = s;
                String name = s.substring(s.lastIndexOf('/') + 1);
                if (name.isEmpty()) name = "cpe140_file.bin";
                createDoc.launch(name);
            });
        });
        findViewById(R.id.b_push).setOnClickListener(v -> {
            if (!ready(5)) return;
            input("上传文件", "目标路径", "/tmp/u.bin", s -> {
                pendingTask = "push";
                pendingArg = s;
                openDoc.launch(new String[]{"*/*"});
            });
        });
        findViewById(R.id.b_clean).setOnClickListener(v -> {
            if (!ready(5)) return;
            bg(out[5], "清理 /tmp/.cpeout /tmp/.cpesh /tmp/upload.img /www/.cpeout …", () -> {
                cpe.clean();
                return "已清理设备上的临时文件。";
            });
        });
        findViewById(R.id.b_relink).setOnClickListener(v -> {
            if (!ready(5)) return;
            bg(out[5], "重铺 /www/.cpeout -> /tmp/.cpeout …", () ->
                    "回显通道已重铺：\n" + cpe.repairChannel());
        });
        findViewById(R.id.b_log).setOnClickListener(v -> {
            if (!ready(5)) return;
            String s = cpe.logTail();
            out[5].setText(s.isEmpty() ? "还没有发出任何请求。" : "最近的 HTTP 请求（最后一条最新）：" + s);
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
                        JSONObject r = cpe.setPassword(u.getText().toString(),
                                o.getText().toString(), n.getText().toString());
                        return "返回 " + r + "\n（未认证也能改 —— 这正是该修的洞）";
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
            confirm("恢复出厂设置", "会清空全部配置（含无线名 / 口令）并重启！\n"
                            + "除非你手里有配置备份和网线兜底，否则别点。确认？",
                    () -> bg(out[5], "下发恢复出厂…", () -> {
                        cpe.factoryReset();
                        return "已下发恢复出厂。设备将重启并回到出厂配置。";
                    }));
        });

        // -------- 断网诊断 / 分级软修复 --------
        findViewById(R.id.b_diag).setOnClickListener(v -> {
            if (!ready(5)) return;
            bg(fixState, "一键诊断（只读，不改设备）…\n（约 15~30 秒）", () -> cpe.diagnose());
        });
        findViewById(R.id.b_fix).setOnClickListener(v -> {
            if (!ready(5)) return;
            confirm("立即救网（分级软修复）",
                    "从最轻的动作开始逐级试，网络一通就立刻停：\n\n"
                            + "1) 强制固件重新检测上网（零影响，专治门户劫持误判）\n"
                            + "2) 放开被固件自己禁用的上行\n"
                            + "3) 重新申请上行 DHCP（不动无线）\n"
                            + "4) 让上行重新握手（断 1~3 秒）\n"
                            + "5) 重起上行接口 wan\n"
                            + "6) wifi reload（整无线栈重启，本机 AP 闪一下）\n\n"
                            + "全程最多约 1 分半。修不好也不折腾，交给看门狗。确认？",
                    () -> bg(fixState(), "救网中（最多约 100 秒，别离开）…", () -> cpe.netfixRun(false, 100)));
        });
        findViewById(R.id.b_fix_dry).setOnClickListener(v -> {
            if (!ready(5)) return;
            bg(fixState(), "干跑（只算，不动设备）…", () -> cpe.netfixRun(true, 60)
                    + "\n\n说明：干跑只打印「真跑的话会做什么」，绝不执行任何一步。");
        });
        findViewById(R.id.b_fix_status).setOnClickListener(v -> {
            if (!ready(5)) return;
            bg(fixState(), "读分级软修状态…", () -> cpe.netfixStatus());
        });
        findViewById(R.id.b_fix_log).setOnClickListener(v -> {
            if (!ready(5)) return;
            bg(fixState(), "读分级软修日志…", () -> cpe.netfixLog());
        });
        findViewById(R.id.b_fix_install).setOnClickListener(v -> {
            if (!ready(5)) return;
            bg(fixState(), "装/更新分级软修脚本…",
                    () -> cpe.netfixInstall(asset("netfix.sh"), Cpe.WAN_TARGETS));
        });

        // -------- 看门狗 --------
        findViewById(R.id.b_g5).setOnClickListener(v -> guardMin.setText("5"));
        findViewById(R.id.b_g10).setOnClickListener(v -> guardMin.setText("10"));
        findViewById(R.id.b_g20).setOnClickListener(v -> guardMin.setText("20"));
        findViewById(R.id.b_guard_on).setOnClickListener(v -> {
            if (!ready(5)) return;
            final int m = Math.max(2, num(guardMin.getText().toString(), 10));
            confirm("开启断网看门狗",
                    "从现在起：设备每 2 分钟探测一次外网，连续 " + m + " 分钟不通就自动重启它自己。\n\n"
                            + "重启之前会先跑一遍「分级软修复」（轻动作先试，救得回来就不重启）。\n\n"
                            + "制动规则：两次重启至少隔 30 分钟；单次断网最多重启 3 次，"
                            + "之后改为每 6 小时才试一次（不会无限重启）。\n"
                            + "网络一恢复就重新计。\n\n"
                            + "它和「定时重启」互不干扰；想停就点「停用」。确认开启？",
                    () -> bg(guardState(), "安装并开启看门狗（阈值 " + m + " 分钟）…", () ->
                            cpe.guardInstallSoft(asset("netguard.sh"), asset("netfix.sh"),
                                    m, "reboot", true)));
        });
        findViewById(R.id.b_guard_off).setOnClickListener(v -> {
            if (!ready(5)) return;
            bg(guardState(), "停用看门狗…", () -> {
                cpe.guardOff();
                return "已停用（脚本还留着，随时能再开）。\n\n" + cpe.guardStatus();
            });
        });
        findViewById(R.id.b_guard_status).setOnClickListener(v -> {
            if (!ready(5)) return;
            bg(guardState(), "读看门狗状态…", () -> cpe.guardStatus());
        });
        findViewById(R.id.b_guard_log).setOnClickListener(v -> {
            if (!ready(5)) return;
            bg(guardState(), "读看门狗日志…", () -> cpe.guardLog());
        });
        findViewById(R.id.b_guard_test).setOnClickListener(v -> {
            if (!ready(5)) return;
            bg(guardState(), "干跑（只算，不重启）…", () -> cpe.guardTest()
                    + "\n\n说明：这一步不会重启设备，只是把「现在断网的话它会怎么判」算给你看。");
        });
        findViewById(R.id.b_guard_uninstall).setOnClickListener(v -> {
            if (!ready(5)) return;
            confirm("卸载看门狗", "删除设备上的 /etc/netguard.sh 和参数文件，并摘掉定时任务。\n"
                    + "设备回到没装过的状态。确认？", () -> bg(guardState(), "卸载…",
                    () -> cpe.guardUninstall() + "\n" + cpe.guardStatus()));
        });

        // -------- 定时重启 --------
        findViewById(R.id.b_read_sch).setOnClickListener(v -> bg(out[5], "读定时重启…", () -> {
            JSONObject s = cpe.sched();
            final String t = "启用=" + s.optString("AUTO_REBOOT_ENABLED")
                    + "  周=" + s.optString("AUTO_REBOOT_WEEK")
                    + "（0=每天）  时=" + s.optString("AUTO_REBOOT_HOUR")
                    + "  分=" + s.optString("AUTO_REBOOT_MIN");
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
            hideKeyboard();
            final int w = num(schW.getText().toString(), 0);
            final int h = num(schH.getText().toString(), 4);
            final int m = num(schM.getText().toString(), 0);
            bg(out[5], "写定时重启…", () -> {
                cpe.setSchedule(schEn.isChecked(), w, h, m);
                return "已设置：启用=" + schEn.isChecked() + " 周=" + w + " 时=" + h + " 分=" + m
                        + "\n（每周 " + w + " 的 " + h + ":" + m + " 重启；0 表示每天）";
            });
        });

        selectTab(1);
        ui.postDelayed(this::connect, 300);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        ex.execute(() -> {
            if (cpe != null) {
                cpe.clean();
            }
        });
        ex.shutdown();
    }

    // ============================================================== 小工具

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

    private TextView guardState() {
        return guardState;
    }

    private TextView fixState() {
        return fixState;
    }

    private void toast(String s) {
        Toast.makeText(this, s, Toast.LENGTH_SHORT).show();
    }

    private void hideKeyboard() {
        View v = getCurrentFocus();
        if (v == null) {
            return;
        }
        InputMethodManager im = (InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE);
        if (im != null) {
            im.hideSoftInputFromWindow(v.getWindowToken(), 0);
        }
        v.clearFocus();
    }

    private void selectTab(int n) {
        tab = n;
        for (int i = 1; i <= 5; i++) {
            boolean on = i == n;
            panels[i].setVisibility(on ? View.VISIBLE : View.GONE);
            navs[i].setBackgroundResource(on ? R.drawable.bg_nav_on : R.drawable.bg_nav);
            navIcons[i].setColorFilter(ContextCompat.getColor(this, on ? R.color.cyan : R.color.tab_text));
            navLabels[i].setTextColor(ContextCompat.getColor(this, on ? R.color.cyan : R.color.tab_text));
        }
    }

    /** 快捷命令 chip：点 = 填入并执行；长按 = 只填入。 */
    private void quick(int id, String cmd, String label) {
        Button b = findViewById(id);
        b.setText(label);
        b.setOnClickListener(v -> {
            hideKeyboard();
            cmdBox.setText(cmd);
            if (ready(4)) runCmd(cmd);
        });
        b.setOnLongClickListener(v -> {
            cmdBox.setText(cmd);
            cmdBox.setSelection(cmd.length());
            toast("已填入，可改完再点「运行」");
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
            toast("先点顶部「连接」");
            selectTab(1);
            return false;
        }
        return true;
    }

    private void runCmd(String cmd) {
        final String c = cmd == null ? "" : cmd.trim();
        if (c.isEmpty()) {
            return;
        }
        hist.add(c);
        histPos = -1;
        bg(out[4], "$ " + c, () -> {
            String r = cpe.run(c);
            return r == null || r.trim().isEmpty() ? "（这条命令没有输出）" : r;
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

    // ================================================================ 连接

    private void connect() {
        final String h = hostBox.getText().toString().trim();
        if (h.isEmpty()) {
            toast("填设备地址");
            return;
        }
        cpe = new Cpe(h);
        pill.setText("● 连接中");
        pill.setTextColor(ContextCompat.getColor(this, R.color.amber));
        status.setTextColor(ContextCompat.getColor(this, R.color.amber));
        status.setText("正在连 " + h + " …");
        ex.execute(() -> {
            try {
                JSONObject si = cpe.sysinfo();
                JSONObject cfg = cpe.cfgAll();
                JSONObject wl = cpe.wirelessStatus();
                final String dev = si.optString("PRODUCTNAME", "?");
                final String fw = si.optString("FIRMVERSION", "?");
                final String link = wl.optString("ssid", "?") + "  ch" + wl.optString("channel")
                        + "  " + wl.optString("rssi") + "dBm";
                final String ap = cpe.cfgGet("WLAN0_VAP0_SSID");
                final int n = cfg.length();
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
                String gs;
                try {
                    gs = cpe.guardStatus();
                } catch (Throwable t) {
                    gs = "（读看门狗状态失败：" + t.getMessage() + "）";
                }
                final String guard = gs;
                ui.post(() -> {
                    pill.setText("● 已连接");
                    pill.setTextColor(ContextCompat.getColor(this, R.color.green));
                    status.setTextColor(ContextCompat.getColor(this, R.color.dim));
                    status.setText("root 通道就绪（未认证可读 " + n + " 项配置）\n"
                            + "上行 " + link);
                    ((TextView) findViewById(R.id.k_dev)).setText(dev);
                    ((TextView) findViewById(R.id.k_fw)).setText(fw);
                    ((TextView) findViewById(R.id.k_link)).setText(link);
                    ((TextView) findViewById(R.id.k_ap)).setText(ap == null ? "—" : ap);
                    guardState.setText(guard);
                    out[1].setText("设备可达。点上面按钮看数据，或去「终端」以 root 跑命令。");
                });
            } catch (Throwable e) {
                ui.post(() -> {
                    pill.setText("● 未连接");
                    pill.setTextColor(ContextCompat.getColor(this, R.color.red));
                    status.setTextColor(ContextCompat.getColor(this, R.color.red));
                    status.setText("连接失败：" + e.getMessage()
                            + "\n（手机要连到中继器自己的 WiFi，或它后级的网络）");
                });
            }
        });
    }

    // =============================================================== 资源

    private byte[] asset(String name) throws Exception {
        InputStream in = getAssets().open(name);
        ByteArrayOutputStream bo = new ByteArrayOutputStream();
        byte[] buf = new byte[1 << 13];
        int n;
        while ((n = in.read(buf)) > 0) {
            bo.write(buf, 0, n);
        }
        in.close();
        return bo.toByteArray();
    }

    // ============================================================= SAF IO

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
