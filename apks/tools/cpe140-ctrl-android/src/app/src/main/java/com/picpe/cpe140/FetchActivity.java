package com.picpe.cpe140;

import android.app.Activity;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URL;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 「抓取另一台中继器的 WebUI 页面」 —— 给手机自己用的。
 *
 * 为什么要有这个页面：
 *   老家中继器（同款易阔）电脑端 WebUI 页面齐全，我们这台的固件被厂商裁掉了 30 个页面。
 *   想把那批页面搬过来补全，就得从它的后台把 .html 抓下来。
 *   但它做 NAT、WAN 侧全封（实测 80/8080/22/23 全关），只有连上它的 WiFi
 *   （SSID 00001111）才能进去 —— 而手机一旦连上它，就断了原来这边的网，
 *   所以在手机上跑最合适：连上 → 抓 → 存到本机 → 回头用数据线取走。
 *
 * 它做两件事：
 *   ① 扫网段：并发 TCP 连 80 端口，把活着的主机找出来（我们之前连上后
 *      .1/.254 都不通、ARP 全空，所以后台地址不一定是常见的那个）。
 *   ② 抓页面：对找到的主机，先取 child_menu.html 解析出所有页面，
 *      再连同"已知缺失的那 30 个"一起逐个下载，存到
 *      /sdcard/Android/data/com.picpe.cpe140/files/other_pages/
 *
 * 存下来的 .bin 就是原始 HTML（没做任何加工），回头 adb pull 出来就行。
 */
public class FetchActivity extends Activity {

    private final ExecutorService pool = Executors.newFixedThreadPool(32);
    private final Handler ui = new Handler(Looper.getMainLooper());

    private EditText netBox;
    private TextView log;
    private Button bScan, bFetch;
    private ScrollView sc;

    /** 我们这台的子菜单里有、但页面上不存在的那些（重点关照） */
    private static final String[] WANT = {
            "dev_manage", "dev_manage_log", "dev_manage_reboot", "dev_manage_pwd",
            "dev_manage_time", "dev_manage_qos", "dev_manage_ipgroup", "dev_manage_timegroup",
            "dev_manage_ddns", "dev_manage_usb",
            "net_lan", "net_lan_staticdhcp", "net_vlan", "net_wan", "net_wan_adv",
            "net_clound", "net_wifidog",
            "net_firewall_dmz", "net_firewall_ip", "net_firewall_mac", "net_firewall_portfw",
            "net_firewall_url", "net_firewall_urlmap",
            "dev_wifi_acl", "dev_wifi_adv", "dev_wifi_timed", "dev_wifi_set", "dev_wifi_wds",
            "user_manager", "visitor_manager"
    };

    private static final String[] SEEDS = {
            "/child_menu.html", "/menu.html", "/index.html", "/main_status.html",
            "/js/config.js", "/login.html"
    };

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(0xFF0E1014);
        int p = dp(14);
        root.setPadding(p, p, p, p);

        TextView t = new TextView(this);
        t.setText("抓取另一台中继器的后台页面");
        t.setTextColor(0xFFE7EAF0);
        t.setTextSize(18);
        t.setPadding(0, 0, 0, dp(6));
        root.addView(t);

        TextView tip = new TextView(this);
        tip.setText("用法：先把手机 WiFi 连到老家中继器的热点（00001111），"
                + "再回来点「扫描 + 抓取」。\n"
                + "扫描会用 32 个并发去试 254 个地址的 80 端口，几秒就出结果。\n"
                + "抓到的页面存在 App 专属目录，回头用数据线 adb pull 取走即可。");
        tip.setTextColor(0xFF8B93A7);
        tip.setTextSize(12);
        tip.setPadding(0, 0, 0, dp(10));
        root.addView(tip);

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        netBox = new EditText(this);
        netBox.setText("192.168.253");
        netBox.setHint("网段前缀");
        netBox.setTextColor(0xFFE7EAF0);
        netBox.setTextSize(14);
        netBox.setBackgroundColor(0xFF12151B);
        netBox.setPadding(dp(10), dp(8), dp(10), dp(8));
        LinearLayout.LayoutParams lp0 = new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        row.addView(netBox, lp0);
        bScan = new Button(this);
        bScan.setText("只扫描");
        row.addView(bScan);
        bFetch = new Button(this);
        bFetch.setText("扫描 + 抓取");
        row.addView(bFetch);
        root.addView(row);

        sc = new ScrollView(this);
        log = new TextView(this);
        log.setTextColor(0xFFC8CDD8);
        log.setTextSize(11);
        log.setTypeface(android.graphics.Typeface.MONOSPACE);
        log.setPadding(0, dp(10), 0, 0);
        sc.addView(log);
        LinearLayout.LayoutParams lp1 = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f);
        root.addView(sc, lp1);

        setContentView(root);

        say("网段默认 192.168.253 —— 就是你给老家中继器改的那个。\n"
                + "如果你改成别的，改上面的前缀再点。\n");

        bScan.setOnClickListener(v -> start(false));
        bFetch.setOnClickListener(v -> start(true));
    }

    private int dp(int v) {
        return (int) (v * getResources().getDisplayMetrics().density + .5f);
    }

    private void say(String s) {
        ui.post(() -> {
            log.append(s + "\n");
            sc.post(() -> sc.fullScroll(View.FOCUS_DOWN));
        });
    }

    private void toast(String s) {
        ui.post(() -> Toast.makeText(this, s, Toast.LENGTH_LONG).show());
    }

    // ================= 主流程 =================

    private void start(boolean doFetch) {
        String net = netBox.getText().toString().trim();
        if (!net.matches("\\d+\\.\\d+\\.\\d+")) {
            toast("网段格式像这样：192.168.253");
            return;
        }
        bScan.setEnabled(false);
        bFetch.setEnabled(false);
        log.setText("");
        new Thread(() -> {
            say("=== 开始（网段 " + net + ".0/24）===");
            List<String> alive = scan(net);
            if (alive.isEmpty()) {
                say("!! 没扫到任何开 80 端口的主机。");
                say("   检查：手机 WiFi 是不是真的连上了 00001111？"
                        + "（设置里能看到信号、能上网不一定代表连上了它）");
                ui.post(() -> { bScan.setEnabled(true); bFetch.setEnabled(true); });
                return;
            }
            say("活着的主机：" + alive);
            if (!doFetch) {
                ui.post(() -> { bScan.setEnabled(true); bFetch.setEnabled(true); });
                return;
            }
            // 挑一个像厂商后台的
            String host = null;
            for (String h : alive) {
                String probe = http(h, "/");
                if (probe != null && (probe.contains("islanguage") || probe.contains("Butterlate")
                        || probe.contains("menu") || probe.contains("易阔") || probe.contains("cms"))) {
                    host = h;
                    say(">>> 这个像后台：" + h + "  首字节 " + probe.length());
                    break;
                }
            }
            if (host == null) {
                host = alive.get(0);
                say(">>> 没认出特征，就拿第一个试：" + host);
            }
            fetchAll(host);
            ui.post(() -> { bScan.setEnabled(true); bFetch.setEnabled(true); });
        }).start();
    }

    /** 并发 TCP 连 80 端口，返回活着的主机 */
    private List<String> scan(String net) {
        List<String> alive = new ArrayList<>();
        AtomicInteger done = new AtomicInteger();
        List<java.util.concurrent.Future<?>> fs = new ArrayList<>();
        for (int i = 1; i <= 254; i++) {
            final String h = net + "." + i;
            fs.add(pool.submit(() -> {
                try (Socket s = new Socket()) {
                    s.connect(new InetSocketAddress(h, 80), 350);
                    synchronized (alive) { alive.add(h); }
                } catch (Exception ignored) {
                } finally {
                    if (done.incrementAndGet() % 64 == 0) {
                        say("  扫描进度 " + done.get() + "/254");
                    }
                }
            }));
        }
        for (java.util.concurrent.Future<?> f : fs) {
            try { f.get(); } catch (Exception ignored) { }
        }
        return alive;
    }

    /** 抓页面 */
    private void fetchAll(String host) {
        File dir = new File(getExternalFilesDir(null), "other_pages");
        if (!dir.exists() && !dir.mkdirs()) {
            say("!! 建目录失败 " + dir);
            return;
        }
        Map<String, String> got = new LinkedHashMap<>();

        say("=== 取目录性文件 ===");
        for (String s : SEEDS) {
            String body = http(host, s);
            if (body == null) { say("   --  " + s); continue; }
            save(dir, s, body);
            got.put(s, body);
            say("   OK  " + s + "  (" + body.length() + " 字节)");
        }

        // 从 child_menu.html / menu.html / config.js 里解析出所有页面
        Set<String> pages = new LinkedHashSet<>();
        for (String n : WANT) pages.add("/" + n + ".html");
        for (String body : got.values()) {
            java.util.regex.Matcher m = java.util.regex.Pattern
                    .compile("([A-Za-z_0-9][A-Za-z_0-9\\-/]*\\.html)")
                    .matcher(body);
            while (m.find()) {
                String s = m.group(1);
                if (s.startsWith("/")) pages.add(s);
                else pages.add("/" + s);
            }
        }
        // 去掉手机版（我们只要 PC 那套）
        List<String> todo = new ArrayList<>();
        for (String s : pages) if (!s.contains("Mobile_")) todo.add(s);
        say("=== 有 " + todo.size() + " 个页面要抓 ===");

        int ok = 0, no = 0;
        for (String s : todo) {
            String body = http(host, s);
            if (body == null || body.length() < 50) {
                no++;
                say("   --  " + s);
                continue;
            }
            save(dir, s, body);
            ok++;
            say("   OK  " + s + "  (" + body.length() + ")");
        }

        say("");
        say("=== 完成：成功 " + ok + " 个，取不到 " + no + " 个 ===");
        say("保存目录（App 专属，卸载才会清）：");
        say("  " + dir.getAbsolutePath());
        say("取走：数据线插上后在我这边执行");
        say("  adb pull " + dir.getAbsolutePath() + " ./other_pages");
        toast("抓完：成功 " + ok + " 个");
    }

    private void save(File dir, String path, String body) {
        try {
            String n = path.replaceFirst("^/", "").replace('/', '_');
            File f = new File(dir, n);
            try (FileOutputStream o = new FileOutputStream(f)) {
                o.write(body.getBytes("UTF-8"));
            }
        } catch (Exception e) {
            say("   写文件失败 " + path + ": " + e);
        }
    }

    /** 取一个路径，返回正文（去掉响应头；非 200 返回 null） */
    private String http(String host, String path) {
        HttpURLConnection c = null;
        try {
            URL u = new URL("http://" + host + path);
            c = (HttpURLConnection) u.openConnection();
            c.setConnectTimeout(4000);
            c.setReadTimeout(8000);
            c.setInstanceFollowRedirects(true);
            c.setRequestProperty("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)");
            c.setRequestProperty("Accept", "*/*");
            c.connect();
            int code = c.getResponseCode();
            InputStream in = (code >= 200 && code < 400) ? c.getInputStream() : c.getErrorStream();
            if (in == null) return null;
            java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
            in.close();
            String s = new String(bo.toByteArray(), "UTF-8");
            // 有些固件会把 HTML 塞在 <!--…--> 或直接返回；这里原样保留
            return s;
        } catch (Exception e) {
            return null;
        } finally {
            if (c != null) c.disconnect();
        }
    }
}
