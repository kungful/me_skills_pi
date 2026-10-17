package com.picpe.cpe140;

import androidx.appcompat.app.AppCompatActivity;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;

import java.io.OutputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 原生抓包页 —— 全按钮操作，不需要打命令。
 *
 * 设备端能力来自 /www/cgi-bin/tools（root 执行的 CGI），本页只负责：
 *   选接口 / 填过滤 / 设时长 -> 开始 / 停止 -> 列表 -> 导出到手机或删除。
 * 导出的 pcap 用系统文件选择器落盘，电脑上可直接用 Wireshark 打开。
 */
public class CaptureActivity extends AppCompatActivity {

    private static final int BG = Color.parseColor("#0f1115");
    private static final int CARD = Color.parseColor("#181b22");
    private static final int LINE = Color.parseColor("#272b35");
    private static final int FG = Color.parseColor("#e6e8ee");
    private static final int DIM = Color.parseColor("#8b93a7");
    private static final int ACC = Color.parseColor("#4c8dff");
    private static final int BAD = Color.parseColor("#ff5a5a");

    private final ExecutorService ex = Executors.newSingleThreadExecutor();
    private final Handler ui = new Handler(Looper.getMainLooper());

    private Cpe cpe;
    private String host;

    private Spinner spIf;
    private EditText etFilter, etSecs;
    private Button bStart, bStop, bRefresh, bScan;
    private TextView tvState;
    private LinearLayout listBox;

    private ActivityResultLauncher<String> saveDoc;
    private String pendingFile;
    private byte[] pendingBytes;

    /** 设备列表里的一行。 */
    private static class Item {
        String name;
        long size;

        Item(String n, long s) {
            name = n;
            size = s;
        }
    }

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        host = getIntent().getStringExtra("host");
        if (host == null || host.isEmpty()) host = "192.168.188.254";
        cpe = new Cpe(host);

        saveDoc = registerForActivityResult(new ActivityResultContracts.CreateDocument("application/vnd.tcpdump.pcap"), uri -> {
            if (uri == null) {
                toast("已取消导出");
                return;
            }
            final Uri u = uri;
            final byte[] d = pendingBytes;
            if (d == null || d.length == 0) {
                toast("没有数据可保存");
                return;
            }
            try {
                OutputStream o = getContentResolver().openOutputStream(u);
                if (o == null) throw new Exception("无法写入");
                o.write(d);
                o.close();
                toast("已导出 " + pendingFile + "（" + sz(d.length) + "）");
            } catch (Exception e) {
                toast("导出失败: " + e.getMessage());
            }
            pendingBytes = null;
        });

        setContentView(build());
        refresh();
    }

    // ------------------------------------------------------------------ UI

    private View build() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BG);

        // 顶栏
        LinearLayout top = new LinearLayout(this);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);
        top.setPadding(dp(12), dp(10), dp(12), dp(6));
        Button back = mkBtn("‹ 返回", CARD, FG);
        back.setOnClickListener(v -> finish());
        top.addView(back, new LinearLayout.LayoutParams(dp(84), dp(40)));
        TextView t = new TextView(this);
        t.setText("  抓包  ·  " + host);
        t.setTextColor(FG);
        t.setTextSize(16f);
        top.addView(t, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        root.addView(top);

        ScrollView sc = new ScrollView(this);
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setPadding(dp(12), 0, dp(12), dp(24));
        sc.addView(col);
        root.addView(sc, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        // ---- 控制卡 ----
        LinearLayout c1 = card();
        c1.addView(sect("选择接口与过滤"));

        spIf = new Spinner(this);
        String[] ifs = {"br-lan（内网全部流量）", "apcli0（上行 STA）", "wlan0（本机 AP）", "eth1（网口）"};
        ArrayAdapter<String> ad = new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, ifs);
        spIf.setAdapter(ad);
        c1.addView(spIf, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(48)));

        etFilter = mkInput("可留空 = 全抓。例：port 80 / host 192.168.188.174", false);
        c1.addView(label("过滤表达式（BPF）"));
        c1.addView(etFilter);

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        etSecs = mkInput("30", true);
        etSecs.setText("30");
        row.addView(etSecs, new LinearLayout.LayoutParams(0, dp(46), 1f));
        TextView sec = new TextView(this);
        sec.setText("  秒后自动停");
        sec.setTextColor(DIM);
        sec.setTextSize(13f);
        row.addView(sec);
        c1.addView(label("抓多久"));
        c1.addView(row);

        LinearLayout row2 = new LinearLayout(this);
        row2.setOrientation(LinearLayout.HORIZONTAL);
        row2.setPadding(0, dp(10), 0, 0);
        bStart = mkBtn("● 开始抓包", ACC, Color.WHITE);
        bStart.setOnClickListener(v -> start());
        bStop = mkBtn("■ 停止", Color.parseColor("#3a1e22"), BAD);
        bStop.setOnClickListener(v -> stop());
        row2.addView(bStart, new LinearLayout.LayoutParams(0, dp(46), 1f));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, dp(46), 1f);
        lp.leftMargin = dp(8);
        row2.addView(bStop, lp);
        c1.addView(row2);

        bScan = mkBtn("扫描附近的 WiFi（选一个做过滤）", CARD, FG);
        bScan.setOnClickListener(v -> scan());
        LinearLayout.LayoutParams lp3 = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(44));
        lp3.topMargin = dp(10);
        c1.addView(bScan, lp3);
        col.addView(c1);

        // ---- 文件列表 ----
        LinearLayout c2 = card();
        c2.addView(sect("抓包文件（点「导出」存到手机）"));
        tvState = new TextView(this);
        tvState.setTextColor(DIM);
        tvState.setTextSize(12f);
        tvState.setText("状态：读取中…");
        c2.addView(tvState);

        listBox = new LinearLayout(this);
        listBox.setOrientation(LinearLayout.VERTICAL);
        listBox.setPadding(0, dp(8), 0, 0);
        c2.addView(listBox);

        bRefresh = mkBtn("刷新列表", CARD, FG);
        bRefresh.setOnClickListener(v -> refresh());
        LinearLayout.LayoutParams lp2 = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(44));
        lp2.topMargin = dp(10);
        c2.addView(bRefresh, lp2);
        col.addView(c2);

        TextView note = new TextView(this);
        note.setText("说明：文件存在设备的 /tmp/cap（内存盘，重启即清空）。导出后是标准 pcap，"
                + "电脑上用 Wireshark 打开即可。抓包在设备端以 root 运行。");
        note.setTextColor(DIM);
        note.setTextSize(11.5f);
        note.setPadding(dp(4), dp(10), dp(4), 0);
        col.addView(note);

        return root;
    }

    private LinearLayout card() {
        LinearLayout l = new LinearLayout(this);
        l.setOrientation(LinearLayout.VERTICAL);
        l.setBackgroundColor(CARD);
        l.setPadding(dp(14), dp(12), dp(14), dp(12));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(10);
        l.setLayoutParams(lp);
        return l;
    }

    private TextView sect(String s) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextColor(DIM);
        t.setTextSize(12f);
        t.setPadding(0, 0, 0, dp(8));
        return t;
    }

    private TextView label(String s) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextColor(DIM);
        t.setTextSize(12f);
        t.setPadding(0, dp(10), 0, dp(4));
        return t;
    }

    private EditText mkInput(String hint, boolean num) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setTextSize(14f);
        e.setTextColor(FG);
        e.setHintTextColor(DIM);
        e.setBackgroundColor(Color.parseColor("#0d0f14"));
        e.setPadding(dp(10), 0, dp(10), 0);
        e.setSingleLine(true);
        if (num) e.setInputType(InputType.TYPE_CLASS_NUMBER);
        return e;
    }

    private Button mkBtn(String text, int bg, int fg) {
        Button b = new Button(this);
        b.setText(text);
        b.setTextSize(13.5f);
        b.setTextColor(fg);
        b.setAllCaps(false);
        b.setBackgroundColor(bg);
        return b;
    }

    private int dp(int v) {
        return (int) (v * getResources().getDisplayMetrics().density + 0.5f);
    }

    private void toast(String s) {
        Toast.makeText(this, s, Toast.LENGTH_SHORT).show();
    }

    private static String sz(long n) {
        if (n < 1024) return n + " B";
        if (n < 1048576) return String.format(java.util.Locale.US, "%.1f KB", n / 1024.0);
        return String.format(java.util.Locale.US, "%.2f MB", n / 1048576.0);
    }

    // ------------------------------------------------------------- 动作

    private void start() {
        final String ifn = new String[]{"br-lan", "apcli0", "wlan0", "eth1"}[spIf.getSelectedItemPosition()];
        final String filt = etFilter.getText().toString().trim();
        String s = etSecs.getText().toString().trim();
        final String secs = s.isEmpty() ? "30" : s;
        bStart.setEnabled(false);
        tvState.setText("状态：正在启动…");
        ex.execute(() -> {
            try {
                String r = cpe.tools("cap_start", "if", ifn, "filt", filt, "secs", secs);
                final String msg = line(r, "file");
                ui.post(() -> {
                    toast(msg == null ? "已开始抓包" : "已开始：" + msg);
                    refresh();
                });
            } catch (Exception e) {
                ui.post(() -> {
                    tvState.setText("状态：启动失败 - " + e.getMessage());
                    toast("启动失败: " + e.getMessage());
                });
            } finally {
                ui.post(() -> bStart.setEnabled(true));
            }
        });
    }

    private void stop() {
        bStop.setEnabled(false);
        ex.execute(() -> {
            try {
                cpe.tools("cap_stop");
                ui.post(() -> {
                    toast("已停止");
                    refresh();
                });
            } catch (Exception e) {
                ui.post(() -> toast("停止失败: " + e.getMessage()));
            } finally {
                ui.post(() -> bStop.setEnabled(true));
            }
        });
    }

    private void refresh() {
        bRefresh.setEnabled(false);
        ex.execute(() -> {
            List<Item> items = new ArrayList<>();
            String state = "?";
            String err = null;
            try {
                String r = cpe.tools("cap_list");
                for (String ln : r.split("\n")) {
                    if (ln.startsWith("state=")) {
                        state = ln.substring(6).trim();
                    } else if (ln.startsWith("file=")) {
                        String v = ln.substring(5).trim();
                        int sp = v.lastIndexOf(' ');
                        if (sp > 0) {
                            String nm = v.substring(0, sp);
                            String szs = v.substring(sp + 1).replace("B", "").trim();
                            long n = 0;
                            try {
                                n = Long.parseLong(szs);
                            } catch (Exception ignore) {
                            }
                            items.add(new Item(nm, n));
                        }
                    } else if (ln.startsWith("err=")) {
                        err = ln.substring(4);
                    }
                }
            } catch (Exception e) {
                err = e.getMessage();
            }
            final List<Item> fi = items;
            final String fs = state;
            final String fe = err;
            ui.post(() -> renderList(fi, fs, fe));
        });
    }

    private void renderList(List<Item> items, String state, String err) {
        bRefresh.setEnabled(true);
        if (err != null) {
            tvState.setText("状态：出错 - " + err);
        } else {
            boolean running = state != null && state.startsWith("running");
            tvState.setText("状态：" + (running ? "● 正在抓包（" + state + "）" : "空闲")
                    + "   共 " + items.size() + " 个文件");
            tvState.setTextColor(running ? Color.parseColor("#ff5a5a") : DIM);
        }
        listBox.removeAllViews();
        if (items.isEmpty()) {
            TextView e = new TextView(this);
            e.setText("（还没有抓包文件）");
            e.setTextColor(DIM);
            e.setTextSize(13f);
            listBox.addView(e);
            return;
        }
        for (Item it : items) {
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setPadding(0, dp(6), 0, dp(6));

            TextView nm = new TextView(this);
            nm.setText(it.name + "\n" + sz(it.size));
            nm.setTextColor(FG);
            nm.setTextSize(12.5f);
            row.addView(nm, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

            Button exp = mkBtn("导出", ACC, Color.WHITE);
            exp.setTextSize(12.5f);
            exp.setOnClickListener(v -> export(it));
            row.addView(exp, new LinearLayout.LayoutParams(dp(64), dp(38)));

            Button del = mkBtn("删除", CARD, BAD);
            del.setTextSize(12.5f);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(64), dp(38));
            lp.leftMargin = dp(6);
            del.setOnClickListener(v -> remove(it));
            row.addView(del, lp);

            listBox.addView(row);

            View line = new View(this);
            line.setBackgroundColor(LINE);
            listBox.addView(line, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, 1));
        }
    }

    private void export(Item it) {
        pendingFile = it.name;
        pendingBytes = null;
        toast("正在读取 " + it.name + " …");
        ex.execute(() -> {
            try {
                byte[] d = cpe.toolsBytes("op=cap_get&f=" + Cpe.toolsEnc(it.name));
                pendingBytes = d;
                pendingFile = it.name;
                ui.post(() -> saveDoc.launch(it.name));
            } catch (Exception e) {
                ui.post(() -> toast("读取失败: " + e.getMessage()));
            }
        });
    }

    private void remove(Item it) {
        ex.execute(() -> {
            try {
                cpe.tools("cap_del", "f", it.name);
                ui.post(() -> {
                    toast("已删除 " + it.name);
                    refresh();
                });
            } catch (Exception e) {
                ui.post(() -> toast("删除失败: " + e.getMessage()));
            }
        });
    }

    // ------------------------------------------------------- 扫描附近 WiFi

    private void scan() {
        bScan.setEnabled(false);
        tvState.setTextColor(DIM);
        tvState.setText("状态：正在扫描附近 WiFi…（单射频，本机 AP 会短暂中断）");
        ex.execute(() -> {
            final List<String[]> found = new ArrayList<>();
            String err = null;
            try {
                String r = cpe.tools("scan");
                for (String ln : r.split("\n")) {
                    if (!ln.startsWith("wifi=")) continue;
                    String[] p = ln.substring(5).split("\\|");
                    if (p.length >= 4) {
                        found.add(new String[]{unesc(p[0]), p[1], p[2], p[3]});
                    }
                }
            } catch (Exception e) {
                err = e.getMessage();
            }
            final String fe = err;
            ui.post(() -> {
                bScan.setEnabled(true);
                tvState.setTextColor(DIM);
                tvState.setText("状态：空闲（扫描到 " + found.size() + " 个 AP）");
                showScan(found, fe);
            });
        });
    }

    private void showScan(List<String[]> found, String err) {
        if (err != null) { toast("扫描失败: " + err); return; }
        if (found.isEmpty()) { toast("没有扫到 AP"); return; }
        final String[] items = new String[found.size()];
        for (int i = 0; i < found.size(); i++) {
            String[] f = found.get(i);
            items[i] = f[0] + "   " + chOf(f[2]) + "    " + f[3] + " dBm\n" + f[1];
        }
        new android.app.AlertDialog.Builder(this)
                .setTitle("附近的 WiFi（点一个 -> 用它做抓包过滤）")
                .setItems(items, (d, w) -> {
                    String bssid = found.get(w)[1];
                    etFilter.setText("ether host " + bssid);
                    toast("过滤已设为 ether host " + bssid + "（只能看到它在本信道上的帧）");
                })
                .setNegativeButton("取消", null)
                .show();
    }

    /** 频率 -> 信道号 */
    private static String chOf(String mhz) {
        try {
            int f = (int) Double.parseDouble(mhz);
            if (f >= 2407 && f <= 2484) return "ch" + ((f - 2407) / 5);
            if (f >= 5000) return "ch" + ((f - 5000) / 5);
            return mhz + "MHz";
        } catch (Exception e) {
            return "?";
        }
    }

    /** iw 把非 ASCII 的 SSID 输出成 \xNN，还原成 UTF-8。 */
    private static String unesc(String s) {
        if (s == null) return "";
        if (s.indexOf("\\x") < 0) return s;
        java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '\\' && i + 3 < s.length() && s.charAt(i + 1) == 'x') {
                try {
                    bo.write(Integer.parseInt(s.substring(i + 2, i + 4), 16));
                    i += 3;
                    continue;
                } catch (Exception ignore) {
                }
            }
            try {
                bo.write(String.valueOf(c).getBytes("UTF-8"));
            } catch (Exception ignore) {
            }
        }
        try {
            return new String(bo.toByteArray(), "UTF-8");
        } catch (Exception e) {
            return s;
        }
    }

    /** 从 "key=value" 多行里取某个 key。 */
    private static String line(String text, String key) {
        for (String ln : text.split("\n")) {
            if (ln.startsWith(key + "=")) return ln.substring(key.length() + 1).trim();
        }
        return null;
    }

    @Override
    protected void onDestroy() {
        ex.shutdownNow();
        super.onDestroy();
    }
}
