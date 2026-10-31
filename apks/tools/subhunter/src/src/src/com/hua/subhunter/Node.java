package com.hua.subhunter;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 一个节点：既能转成 Clash 的 proxies 条目，也能转回 v2ray 的分享链接。 */
final class Node {

    static final String[] SCHEMES = {
            "vmess", "vless", "trojan", "ss", "ssr", "hysteria2", "hy2", "hysteria", "tuic"
    };

    String scheme = "";
    String name = "";
    String server = "";
    int port = 443;

    /** 原始分享链接（来自 uri 源时保留，输出 v2ray 订阅时优先用它）。 */
    String raw = "";

    /** 从 Clash 列表解析出来的原始 proxies 片段（逐行，已含缩进），用于无损回灌 Clash。 */
    List<String> rawYaml = null;

    // --- 认证 / 协议参数 ---
    String uuid = "";
    String password = "";
    String cipher = "";        // ss 加密方式 / vmess scy
    int alterId = 0;
    String flow = "";
    String plugin = "";        // ss plugin（obfs / v2ray-plugin）
    String pluginOpts = "";

    boolean tls = false;
    boolean reality = false;
    boolean skipCertVerify = false;
    String sni = "";
    String net = "";           // tcp / ws / grpc / h2 / http
    String path = "";
    String wsHost = "";
    String serviceName = "";
    String headerType = "";
    String alpn = "";
    String fingerprint = "";
    String pbk = "";
    String sid = "";

    // --- 运行时信息（不持久化的活数据也在里面，简单起见一起存）---
    int latency = -1;
    String sourceId = "";
    String sourceName = "";

    // ------------------------------------------------------------------ 标识

    /** 去重键：同协议 + 同服务器端口 + 同凭据 视为同一节点（名字不同不算区别）。 */
    String key() {
        String cred = !uuid.isEmpty() ? uuid : (!password.isEmpty() ? password : cipher);
        return scheme + "|" + server + "|" + port + "|" + cred;
    }

    String endpoint() {
        return server + ":" + port;
    }

    boolean pingable() {
        return !server.isEmpty() && port > 0 && port < 65536;
    }

    // ------------------------------------------------------------------ 地区

    static final String[][] REGIONS = {
            {"🇭🇰", "香港"}, {"Hong Kong", "香港"}, {"HongKong", "香港"}, {"HK", "香港"}, {"港", "香港"},
            {"🇹🇼", "台湾"}, {"Taiwan", "台湾"}, {"TW", "台湾"}, {"台", "台湾"},
            {"🇯🇵", "日本"}, {"Japan", "日本"}, {"JP", "日本"}, {"东京", "日本"}, {"大阪", "日本"}, {"日", "日本"},
            {"🇸🇬", "新加坡"}, {"Singapore", "新加坡"}, {"SG", "新加坡"}, {"狮城", "新加坡"}, {"新加坡", "新加坡"},
            {"🇺🇸", "美国"}, {"United States", "美国"}, {"US", "美国"}, {"洛杉矶", "美国"}, {"圣何塞", "美国"}, {"美", "美国"},
            {"🇰🇷", "韩国"}, {"Korea", "韩国"}, {"KR", "韩国"}, {"首尔", "韩国"}, {"韩", "韩国"},
            {"🇩🇪", "德国"}, {"Germany", "德国"}, {"DE", "德国"}, {"德", "德国"},
            {"🇬🇧", "英国"}, {"United Kingdom", "英国"}, {"GB", "英国"}, {"UK", "英国"}, {"伦敦", "英国"}, {"英", "英国"},
            {"🇳🇱", "荷兰"}, {"Netherlands", "荷兰"}, {"NL", "荷兰"},
            {"🇫🇷", "法国"}, {"France", "法国"}, {"FR", "法国"},
            {"🇷🇺", "俄罗斯"}, {"Russia", "俄罗斯"}, {"RU", "俄罗斯"},
            {"🇨🇦", "加拿大"}, {"Canada", "加拿大"}, {"CA", "加拿大"},
            {"🇦🇺", "澳大利亚"}, {"Australia", "澳大利亚"}, {"AU", "澳大利亚"},
            {"🇮🇳", "印度"}, {"India", "印度"}, {"IN", "印度"},
            {"🇹🇷", "土耳其"}, {"Turkey", "土耳其"}, {"TR", "土耳其"},
            {"🇧🇷", "巴西"}, {"Brazil", "巴西"}, {"BR", "巴西"},
            {"🇦🇷", "阿根廷"}, {"Argentina", "阿根廷"},
            {"🇻🇳", "越南"}, {"Vietnam", "越南"}, {"VN", "越南"},
            {"🇹🇭", "泰国"}, {"Thailand", "泰国"}, {"TH", "泰国"},
            {"🇲🇾", "马来西亚"}, {"Malaysia", "马来西亚"}, {"MY", "马来西亚"},
            {"🇮🇩", "印尼"}, {"Indonesia", "印尼"}, {"ID", "印尼"},
            {"🇵🇭", "菲律宾"}, {"Philippines", "菲律宾"},
            {"🇮🇹", "意大利"}, {"Italy", "意大利"}, {"IT", "意大利"},
            {"🇪🇸", "西班牙"}, {"Spain", "西班牙"}, {"ES", "西班牙"},
            {"🇵🇱", "波兰"}, {"Poland", "波兰"},
            {"🇨🇭", "瑞士"}, {"Switzerland", "瑞士"},
            {"🇸🇪", "瑞典"}, {"Sweden", "瑞典"},
            {"🇫🇮", "芬兰"}, {"Finland", "芬兰"},
            {"🇳🇴", "挪威"}, {"Norway", "挪威"},
            {"🇩🇰", "丹麦"}, {"Denmark", "丹麦"},
            {"🇦🇪", "阿联酋"}, {"Emirates", "阿联酋"}, {"Dubai", "阿联酋"},
            {"🇮🇱", "以色列"}, {"Israel", "以色列"},
            {"🇿🇦", "南非"}, {"South Africa", "南非"},
            {"🇲🇽", "墨西哥"}, {"Mexico", "墨西哥"},
            {"🇨🇱", "智利"}, {"Chile", "智利"},
            {"🇺🇦", "乌克兰"}, {"Ukraine", "乌克兰"},
            {"🇨🇳", "中国"}, {"China", "中国"}, {"CN", "中国"},
    };

    String region() {
        String n = Util.nz(name);
        String up = n.toUpperCase();
        for (String[] r : REGIONS) {
            if (r[0].length() > 1 && n.contains(r[0])) return r[1];
        }
        for (String[] r : REGIONS) {
            if (r[0].length() <= 2) continue;
            if (n.contains(r[0])) return r[1];
        }
        // 两字母国家码只在名字边界上匹配，避免 "US" 命中 "RUSSIA"
        for (String[] r : REGIONS) {
            if (r[0].length() != 2) continue;
            String code = r[0];
            int idx = up.indexOf(code);
            while (idx >= 0) {
                char before = idx > 0 ? up.charAt(idx - 1) : ' ';
                char after = idx + 2 < up.length() ? up.charAt(idx + 2) : ' ';
                boolean okBefore = !Character.isLetterOrDigit(before);
                boolean okAfter = !Character.isLetterOrDigit(after);
                if (okBefore && okAfter) return r[1];
                idx = up.indexOf(code, idx + 1);
            }
        }
        return "其它";
    }

    // ------------------------------------------------------------------ Clash

    boolean clashReady() {
        if (rawYaml != null && !rawYaml.isEmpty()) return true;
        if (server.isEmpty() || port <= 0) return false;
        if (scheme.equals("vmess") || scheme.equals("vless")) return !uuid.isEmpty();
        if (scheme.equals("trojan")) return !password.isEmpty();
        if (scheme.equals("ss")) return !cipher.isEmpty() && !password.isEmpty();
        if (scheme.equals("hysteria2") || scheme.equals("hy2")) return !password.isEmpty();
        if (scheme.equals("tuic")) return !uuid.isEmpty() || !password.isEmpty();
        return false;
    }

    /** 生成 Clash(mihomo) proxies 列表里的一条（含前导 "- "，后续行 2 空格缩进）。 */
    String toClash(String outName) {
        if (rawYaml != null && !rawYaml.isEmpty()) {
            List<String> lines = new ArrayList<String>(rawYaml);
            String quoted = java.util.regex.Matcher.quoteReplacement(Util.yq(outName));
            int nameAt = -1;
            for (int i = 0; i < lines.size(); i++) {
                String t = lines.get(i).trim();
                if (t.startsWith("name:") || t.startsWith("- name:") || t.contains("{name:") || t.contains(", name:")) {
                    nameAt = i;
                    break;
                }
            }
            if (nameAt >= 0) {
                String l = lines.get(nameAt);
                if (l.indexOf('{') >= 0) {
                    l = l.replaceFirst("(name\\s*:\\s*)(\"[^\"]*\"|'[^']*'|[^,}]+)", "$1" + quoted);
                } else {
                    l = l.replaceFirst("^(\\s*(?:-\\s*)?name\\s*:\\s*)(\"[^\"]*\"|'[^']*'|.*)$", "$1" + quoted);
                }
                lines.set(nameAt, l);
            } else {
                // 块里没写 name（少见）：插在首行后面
                String first = lines.get(0);
                String indent = first.startsWith("- ") ? "  " : "  ";
                lines.add(1, indent + "name: " + Util.yq(outName));
            }
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < lines.size(); i++) {
                if (i > 0) sb.append('\n');
                sb.append(lines.get(i));
            }
            return sb.toString();
        }
        StringBuilder s = new StringBuilder(320);
        s.append("- name: ").append(Util.yq(outName)).append('\n');
        String type = scheme.equals("hy2") ? "hysteria2" : scheme;
        s.append("  type: ").append(type).append('\n');
        s.append("  server: ").append(Util.yq(server)).append('\n');
        s.append("  port: ").append(port).append('\n');

        if (scheme.equals("vmess")) {
            s.append("  uuid: ").append(Util.yq(uuid)).append('\n');
            s.append("  alterId: ").append(Math.max(0, alterId)).append('\n');
            s.append("  cipher: ").append(Util.yq(Util.isBlank(cipher) ? "auto" : cipher)).append('\n');
            s.append("  udp: true\n");
        } else if (scheme.equals("vless")) {
            s.append("  uuid: ").append(Util.yq(uuid)).append('\n');
            s.append("  udp: true\n");
            if (!Util.isBlank(flow)) s.append("  flow: ").append(Util.yq(flow)).append('\n');
        } else if (scheme.equals("trojan")) {
            s.append("  password: ").append(Util.yq(password)).append('\n');
            s.append("  udp: true\n");
        } else if (scheme.equals("ss")) {
            s.append("  cipher: ").append(Util.yq(cipher)).append('\n');
            s.append("  password: ").append(Util.yq(password)).append('\n');
            s.append("  udp: true\n");
            if (!Util.isBlank(plugin)) {
                String p = plugin.toLowerCase();
                if (p.contains("obfs")) {
                    s.append("  plugin: obfs\n");
                    s.append("  plugin-opts:\n");
                    s.append("    mode: ").append(Util.yq(obfsMode() )).append('\n');
                    String h = obfsHost();
                    if (!Util.isBlank(h)) s.append("    host: ").append(Util.yq(h)).append('\n');
                } else if (p.contains("v2ray")) {
                    s.append("  plugin: v2ray-plugin\n");
                    s.append("  plugin-opts:\n");
                    s.append("    mode: websocket\n");
                    String h = obfsHost();
                    if (!Util.isBlank(h)) s.append("    host: ").append(Util.yq(h)).append('\n');
                    s.append("    tls: ").append(tls).append('\n');
                    if (!Util.isBlank(path)) s.append("    path: ").append(Util.yq(path)).append('\n');
                }
            }
        } else if (scheme.equals("hysteria2") || scheme.equals("hy2")) {
            s.append("  password: ").append(Util.yq(password)).append('\n');
            s.append("  up: \"60 Mbps\"\n  down: \"200 Mbps\"\n");
        } else if (scheme.equals("tuic")) {
            if (!Util.isBlank(uuid)) s.append("  uuid: ").append(Util.yq(uuid)).append('\n');
            if (!Util.isBlank(password)) s.append("  password: ").append(Util.yq(password)).append('\n');
            s.append("  udp-relay-mode: native\n");
            s.append("  congestion-controller: bbr\n");
            s.append("  reduce-rtt: true\n");
        } else {
            return null;
        }

        boolean needTlsField = !(scheme.equals("hysteria2") || scheme.equals("hy2") || scheme.equals("tuic") || scheme.equals("ss"));
        if (needTlsField && tls && !reality) s.append("  tls: true\n");
        if (reality) {
            s.append("  tls: true\n");
            s.append("  reality-opts:\n");
            if (!Util.isBlank(pbk)) s.append("    public-key: ").append(Util.yq(pbk)).append('\n');
            if (!Util.isBlank(sid)) s.append("    short-id: ").append(Util.yq(sid)).append('\n');
        }
        if (!Util.isBlank(sni)) {
            if (scheme.equals("trojan") || scheme.equals("ss")) s.append("  sni: ").append(Util.yq(sni)).append('\n');
            else s.append("  servername: ").append(Util.yq(sni)).append('\n');
        }
        if (skipCertVerify) s.append("  skip-cert-verify: true\n");
        if (!Util.isBlank(fingerprint)) s.append("  client-fingerprint: ").append(Util.yq(fingerprint)).append('\n');
        if (!Util.isBlank(alpn)) {
            s.append("  alpn:\n");
            for (String a : alpn.split(",")) {
                if (!Util.isBlank(a)) s.append("    - ").append(Util.yq(a.trim())).append('\n');
            }
        }

        String network = Util.isBlank(net) ? "tcp" : net.toLowerCase();
        if (!scheme.equals("ss") && !scheme.equals("hysteria2") && !scheme.equals("hy2") && !scheme.equals("tuic")) {
            if (!network.equals("tcp")) s.append("  network: ").append(Util.yq(network)).append('\n');
            if (network.equals("ws")) {
                s.append("  ws-opts:\n");
                s.append("    path: ").append(Util.yq(Util.isBlank(path) ? "/" : path)).append('\n');
                if (!Util.isBlank(wsHost)) {
                    s.append("    headers:\n");
                    s.append("      Host: ").append(Util.yq(wsHost)).append('\n');
                }
            } else if (network.equals("grpc")) {
                s.append("  grpc-opts:\n");
                s.append("    grpc-service-name: ").append(Util.yq(Util.isBlank(serviceName) ? "" : serviceName)).append('\n');
            } else if (network.equals("h2") || network.equals("http")) {
                s.append("  h2-opts:\n");
                s.append("    path: ").append(Util.yq(Util.isBlank(path) ? "/" : path)).append('\n');
                if (!Util.isBlank(wsHost)) {
                    s.append("    host:\n");
                    s.append("      - ").append(Util.yq(wsHost)).append('\n');
                }
            } else if (network.equals("httpupgrade")) {
                s.append("  http-upgrade-opts:\n");
                s.append("    path: ").append(Util.yq(Util.isBlank(path) ? "/" : path)).append('\n');
            }
        }
        return s.toString();
    }

    private String obfsMode() {
        String p = Util.nz(pluginOpts);
        int i = p.indexOf("obfs=");
        if (i >= 0) {
            String v = p.substring(i + 5);
            int amp = v.indexOf(';');
            if (amp >= 0) v = v.substring(0, amp);
            if (!Util.isBlank(v)) return v.trim();
        }
        return "http";
    }

    private String obfsHost() {
        String p = Util.nz(pluginOpts);
        int i = p.indexOf("obfs-host=");
        if (i >= 0) {
            String v = p.substring(i + 10);
            int amp = v.indexOf(';');
            if (amp >= 0) v = v.substring(0, amp);
            return v.trim();
        }
        int j = p.indexOf("host=");
        if (j >= 0) {
            String v = p.substring(j + 5);
            int amp = v.indexOf(';');
            if (amp >= 0) v = v.substring(0, amp);
            return v.trim();
        }
        return "";
    }

    // ------------------------------------------------------------------ v2ray

    /** 输出 v2ray/v2rayNG 能吃的分享链接。 */
    String toUri() {
        if (!Util.isBlank(raw)) return raw;
        if (scheme.equals("vmess")) {
            Map<String, String> m = new LinkedHashMap<String, String>();
            m.put("v", "2");
            m.put("ps", name);
            m.put("add", server);
            m.put("port", String.valueOf(port));
            m.put("id", uuid);
            m.put("aid", String.valueOf(Math.max(0, alterId)));
            m.put("scy", Util.isBlank(cipher) ? "auto" : cipher);
            m.put("net", Util.isBlank(net) ? "tcp" : net);
            m.put("type", Util.isBlank(headerType) ? "none" : headerType);
            m.put("host", Util.isBlank(wsHost) ? "" : wsHost);
            m.put("path", Util.isBlank(path) ? "" : path);
            m.put("tls", tls ? "tls" : "");
            m.put("sni", sni);
            m.put("fp", fingerprint);
            m.put("alpn", alpn);
            return "vmess://" + Util.b64e(json(m));
        }
        if (scheme.equals("vless")) {
            StringBuilder q = new StringBuilder();
            q.append("encryption=none");
            if (reality) q.append("&security=reality");
            else if (tls) q.append("&security=tls");
            if (!Util.isBlank(sni)) q.append("&sni=").append(enc(sni));
            if (!Util.isBlank(flow)) q.append("&flow=").append(enc(flow));
            if (!Util.isBlank(net)) q.append("&type=").append(enc(net));
            if (!Util.isBlank(path)) q.append("&path=").append(enc(path));
            if (!Util.isBlank(wsHost)) q.append("&host=").append(enc(wsHost));
            if (!Util.isBlank(serviceName)) q.append("&serviceName=").append(enc(serviceName));
            if (!Util.isBlank(pbk)) q.append("&pbk=").append(enc(pbk));
            if (!Util.isBlank(sid)) q.append("&sid=").append(enc(sid));
            if (!Util.isBlank(fingerprint)) q.append("&fp=").append(enc(fingerprint));
            if (!Util.isBlank(alpn)) q.append("&alpn=").append(enc(alpn));
            if (skipCertVerify) q.append("&allowInsecure=1");
            return "vless://" + enc(uuid) + "@" + server + ":" + port + "?" + q + frag();
        }
        if (scheme.equals("trojan")) {
            StringBuilder q = new StringBuilder();
            if (!Util.isBlank(sni)) q.append("sni=").append(enc(sni));
            if (!Util.isBlank(net)) q.append("&type=").append(enc(net));
            if (!Util.isBlank(path)) q.append("&path=").append(enc(path));
            if (!Util.isBlank(wsHost)) q.append("&host=").append(enc(wsHost));
            if (skipCertVerify) q.append("&allowInsecure=1");
            String qs = q.length() > 0 ? (q.charAt(0) == '&' ? "?" + q.substring(1) : "?" + q) : "";
            return "trojan://" + enc(password) + "@" + server + ":" + port + qs + frag();
        }
        if (scheme.equals("ss")) {
            String userinfo = Util.b64e(Util.utf8(cipher + ":" + password));
            StringBuilder q = new StringBuilder();
            if (!Util.isBlank(plugin)) {
                q.append("?plugin=").append(enc(plugin + (Util.isBlank(pluginOpts) ? "" : ";" + pluginOpts)));
            }
            return "ss://" + userinfo + "@" + server + ":" + port + q + frag();
        }
        if (scheme.equals("hysteria2") || scheme.equals("hy2")) {
            StringBuilder q = new StringBuilder();
            if (!Util.isBlank(sni)) q.append("sni=").append(enc(sni));
            if (skipCertVerify) q.append(q.length() > 0 ? "&insecure=1" : "insecure=1");
            String qs = q.length() > 0 ? "?" + q : "";
            return "hysteria2://" + enc(password) + "@" + server + ":" + port + qs + frag();
        }
        if (scheme.equals("tuic")) {
            StringBuilder q = new StringBuilder();
            if (!Util.isBlank(sni)) q.append("sni=").append(enc(sni));
            if (skipCertVerify) q.append(q.length() > 0 ? "&allow_insecure=1" : "allow_insecure=1");
            if (!Util.isBlank(alpn)) q.append(q.length() > 0 ? "&alpn=" + enc(alpn) : "alpn=" + enc(alpn));
            String qs = q.length() > 0 ? "?" + q : "";
            String cred = Util.isBlank(password) ? enc(uuid) : enc(uuid) + ":" + enc(password);
            return "tuic://" + cred + "@" + server + ":" + port + qs + frag();
        }
        return raw;
    }

    private String frag() {
        String n = Util.isBlank(name) ? endpoint() : name;
        return "#" + enc(n);
    }

    static String enc(String s) {
        if (s == null) return "";
        StringBuilder sb = new StringBuilder(s.length());
        byte[] b = Util.utf8(s);
        for (byte x : b) {
            int c = x & 0xFF;
            if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9')
                    || c == '-' || c == '_' || c == '.' || c == '~' || c == ':' || c == '@' || c == '=') {
                sb.append((char) c);
            } else {
                sb.append('%').append(Character.toUpperCase(Character.forDigit((c >> 4) & 15, 16)))
                        .append(Character.toUpperCase(Character.forDigit(c & 15, 16)));
            }
        }
        return sb.toString();
    }

    private static String json(Map<String, String> m) {
        StringBuilder sb = new StringBuilder(256);
        sb.append('{');
        boolean first = true;
        for (Map.Entry<String, String> e : m.entrySet()) {
            if (!first) sb.append(',');
            first = false;
            sb.append('"').append(e.getKey()).append("\":\"").append(esc(e.getValue())).append('"');
        }
        sb.append('}');
        return sb.toString();
    }

    private static String esc(String s) {
        if (s == null) return "";
        StringBuilder sb = new StringBuilder(s.length() + 8);
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '"' || c == '\\') sb.append('\\').append(c);
            else if (c == '\n') sb.append("\\n");
            else if (c < 0x20) sb.append(' ');
            else sb.append(c);
        }
        return sb.toString();
    }
}
