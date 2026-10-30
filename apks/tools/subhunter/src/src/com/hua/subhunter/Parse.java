package com.hua.subhunter;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 订阅正文解析：v2ray 分享链接列表 / base64 列表 / Clash proxies 列表。 */
final class Parse {

    private Parse() {
    }

    /** 自动判别正文格式（明文链接、base64 链接、Clash YAML）。 */
    static List<Node> body(String body) {
        List<Node> out = new ArrayList<Node>();
        if (Util.isBlank(body)) return out;
        String text = body.trim();

        if (looksClash(text)) {
            out.addAll(clash(text));
            if (!out.isEmpty()) return out;
        }

        List<Node> direct = text(text);
        if (!direct.isEmpty()) return direct;

        // 整体 base64
        String decoded = Util.str(Util.b64d(text.replaceAll("\\s+", "")));
        if (decoded.contains("://")) {
            if (looksClash(decoded)) out.addAll(clash(decoded));
            if (out.isEmpty()) out.addAll(text(decoded));
        }
        return out;
    }

    private static boolean looksClash(String text) {
        if (text.indexOf("proxies:") < 0) return false;
        return text.indexOf("- name:") >= 0 || text.indexOf("- {") >= 0 || text.indexOf("- {\"") >= 0;
    }

    /** 逐行解析分享链接。 */
    static List<Node> text(String text) {
        List<Node> out = new ArrayList<Node>();
        if (text == null) return out;
        String[] lines = text.split("\r?\n");
        for (String line : lines) {
            if (line == null) continue;
            String s = line.trim();
            if (s.length() < 8) continue;
            if (s.startsWith("#") || s.startsWith("//")) continue;
            int sp = s.indexOf("://");
            if (sp <= 0 || sp > 12) continue;
            String scheme = s.substring(0, sp).toLowerCase();
            if (!known(scheme)) continue;
            Node n = uri(s);
            if (n != null && !badEndpoint(n.server, n.port)) out.add(n);
        }
        return out;
    }

    private static boolean known(String scheme) {
        for (String s : Node.SCHEMES) if (s.equals(scheme)) return true;
        return false;
    }

    // ------------------------------------------------------------------ 单条分享链接

    static Node uri(String rawUri) {
        try {
            String u = rawUri.trim();
            int sp = u.indexOf("://");
            if (sp <= 0) return null;
            String scheme = u.substring(0, sp).toLowerCase();
            if (scheme.equals("hy2")) scheme = "hysteria2";
            String body = u.substring(sp + 3);
            String frag = "";
            int h = body.indexOf('#');
            if (h >= 0) {
                frag = Util.urlDecode(body.substring(h + 1));
                body = body.substring(0, h);
            }
            if (scheme.equals("vmess")) return vmess(rawUri, body, frag);

            String query = "";
            int q = body.indexOf('?');
            if (q >= 0) {
                query = body.substring(q + 1);
                body = body.substring(0, q);
            }
            Map<String, String> p = params(query);

            if (scheme.equals("ss")) return ss(rawUri, body, p, frag);
            if (scheme.equals("ssr")) {
                Node n = new Node();
                n.scheme = "ssr";
                n.raw = rawUri;
                n.name = Util.isBlank(frag) ? "ssr" : frag;
                return n;
            }
            int at = body.lastIndexOf('@');
            if (at <= 0) return null;
            String userinfo = body.substring(0, at);
            String hostport = body.substring(at + 1);
            String[] hp = hostPort(hostport);
            if (hp == null) return null;

            Node n = new Node();
            n.scheme = scheme;
            n.raw = rawUri;
            n.server = hp[0];
            n.port = Util.toInt(hp[1], 443);
            n.name = Util.isBlank(frag) ? n.endpoint() : frag;

            if (scheme.equals("vless")) {
                n.uuid = Util.urlDecode(userinfo);
                String sec = low(first(p, "security", ""));
                n.reality = sec.equals("reality");
                n.tls = sec.equals("tls") || sec.equals("reality") || sec.equals("xtls");
                n.sni = first(p, "sni", first(p, "peer", ""));
                n.flow = first(p, "flow", "");
                n.net = normNet(first(p, "type", "tcp"));
                n.path = Util.urlDecode(first(p, "path", ""));
                n.wsHost = first(p, "host", "");
                n.serviceName = first(p, "serviceName", "");
                n.alpn = first(p, "alpn", "");
                n.fingerprint = first(p, "fp", "");
                n.pbk = first(p, "pbk", "");
                n.sid = first(p, "sid", "");
                n.skipCertVerify = Util.truthy(first(p, "allowInsecure", ""));
            } else if (scheme.equals("trojan")) {
                n.password = Util.urlDecode(userinfo);
                n.tls = true;
                n.sni = first(p, "sni", first(p, "peer", ""));
                if (Util.isBlank(n.sni)) n.sni = first(p, "host", "");
                n.net = normNet(first(p, "type", "tcp"));
                n.path = Util.urlDecode(first(p, "path", ""));
                n.wsHost = first(p, "host", "");
                n.serviceName = first(p, "serviceName", "");
                n.alpn = first(p, "alpn", "");
                n.fingerprint = first(p, "fp", "");
                n.skipCertVerify = Util.truthy(first(p, "allowInsecure", ""));
            } else if (scheme.equals("hysteria2")) {
                n.password = Util.urlDecode(userinfo);
                n.tls = true;
                n.sni = first(p, "sni", first(p, "peer", ""));
                n.skipCertVerify = Util.truthy(first(p, "insecure", "")) || Util.truthy(first(p, "allowInsecure", ""));
                n.alpn = first(p, "alpn", "");
            } else if (scheme.equals("tuic")) {
                String ui = Util.urlDecode(userinfo);
                int colon = ui.indexOf(':');
                if (colon > 0) {
                    n.uuid = ui.substring(0, colon);
                    n.password = ui.substring(colon + 1);
                } else {
                    n.uuid = ui;
                }
                n.tls = true;
                n.sni = first(p, "sni", "");
                n.alpn = first(p, "alpn", "");
                n.skipCertVerify = Util.truthy(first(p, "allow_insecure", first(p, "insecure", "")));
            } else if (scheme.equals("hysteria") || scheme.equals("juicity") || scheme.equals("socks") || scheme.equals("http")) {
                n.password = Util.urlDecode(userinfo);
                n.tls = scheme.equals("hysteria") || scheme.equals("juicity");
                n.sni = first(p, "peer", first(p, "sni", ""));
                n.skipCertVerify = Util.truthy(first(p, "insecure", ""));
            } else {
                return null;
            }
            return n;
        } catch (Throwable t) {
            return null;
        }
    }

    private static Node vmess(String rawUri, String body, String frag) {
        String json = Util.str(Util.b64d(body));
        if (json.indexOf('{') < 0) json = Util.str(Util.b64d(Util.urlDecode(body)));
        if (json.indexOf('{') < 0) {
            // 少数源直接把 JSON 明文塞在 vmess:// 后面
            json = Util.urlDecode(body);
        }
        if (json.indexOf('{') < 0) return null;
        Map<String, String> m = Util.jsonFlat(json);
        Node n = new Node();
        n.scheme = "vmess";
        n.raw = rawUri;
        n.server = Util.nz(m.get("add")).trim();
        n.port = Util.toInt(m.get("port"), 443);
        n.uuid = Util.nz(m.get("id")).trim();
        n.alterId = Util.toInt(m.get("aid"), 0);
        String scy = Util.nz(m.get("scy")).trim();
        n.cipher = Util.isBlank(scy) ? "auto" : scy;
        String tls = low(Util.nz(m.get("tls")));
        n.reality = tls.equals("reality");
        n.tls = tls.equals("tls") || tls.equals("reality") || tls.equals("true") || tls.equals("1");
        n.net = normNet(Util.nz(m.get("net")));
        n.headerType = Util.nz(m.get("type"));
        n.wsHost = Util.nz(m.get("host"));
        n.path = Util.nz(m.get("path"));
        n.sni = Util.nz(m.get("sni"));
        if (Util.isBlank(n.sni) && n.tls && !Util.isBlank(n.wsHost) && !n.wsHost.contains(":")) n.sni = n.wsHost;
        n.fingerprint = Util.nz(m.get("fp"));
        n.alpn = Util.nz(m.get("alpn"));
        String ps = Util.nz(m.get("ps"));
        n.name = !Util.isBlank(ps) ? ps : (!Util.isBlank(frag) ? frag : n.endpoint());
        if (Util.isBlank(n.server) || Util.isBlank(n.uuid)) return null;
        return n;
    }

    private static Node ss(String rawUri, String body, Map<String, String> p, String frag) {
        String method = "";
        String pass = "";
        String hostport = "";
        int at = body.lastIndexOf('@');
        if (at > 0) {
            String userinfo = body.substring(0, at);
            hostport = body.substring(at + 1);
            String plain = Util.str(Util.b64d(userinfo));
            if (plain.indexOf(':') > 0) {
                method = plain.substring(0, plain.indexOf(':'));
                pass = plain.substring(plain.indexOf(':') + 1);
            } else {
                String ui = Util.urlDecode(userinfo);
                if (ui.indexOf(':') > 0) {
                    method = ui.substring(0, ui.indexOf(':'));
                    pass = ui.substring(ui.indexOf(':') + 1);
                }
            }
        } else {
            String plain = Util.str(Util.b64d(body));
            int at2 = plain.lastIndexOf('@');
            if (at2 <= 0) return null;
            hostport = plain.substring(at2 + 1);
            String userinfo = plain.substring(0, at2);
            if (userinfo.indexOf(':') <= 0) return null;
            method = userinfo.substring(0, userinfo.indexOf(':'));
            pass = userinfo.substring(userinfo.indexOf(':') + 1);
        }
        String[] hp = hostPort(hostport);
        if (hp == null) return null;
        Node n = new Node();
        n.scheme = "ss";
        n.raw = rawUri;
        n.server = hp[0];
        n.port = Util.toInt(hp[1], 8388);
        n.cipher = method.trim();
        n.password = pass;
        n.name = Util.isBlank(frag) ? n.endpoint() : frag;
        String plugin = first(p, "plugin", "");
        if (!Util.isBlank(plugin)) {
            String pl = Util.urlDecode(plugin);
            int semi = pl.indexOf(';');
            if (semi > 0) {
                n.plugin = pl.substring(0, semi);
                n.pluginOpts = pl.substring(semi + 1);
            } else {
                n.plugin = pl;
            }
            String lo = pl.toLowerCase();
            n.tls = lo.contains("tls");
            if (lo.contains("obfs")) n.net = "tcp";
        }
        if (Util.isBlank(n.cipher) || Util.isBlank(n.password)) return null;
        return n;
    }

    // ------------------------------------------------------------------ Clash YAML

    /** 解析 Clash 配置里的 proxies 列表（块式 + 流式都吃）。 */
    static List<Node> clash(String yaml) {
        List<Node> out = new ArrayList<Node>();
        if (yaml == null) return out;
        String[] lines = yaml.split("\r?\n");

        int start = -1;
        int baseIndent = 0;
        for (int i = 0; i < lines.length; i++) {
            String t = lines[i].trim();
            if (t.startsWith("proxies:")) {
                start = i;
                baseIndent = indentOf(lines[i]);
                break;
            }
        }
        if (start < 0) return out;

        List<List<String>> blocks = new ArrayList<List<String>>();
        List<String> cur = null;
        int dashIndent = -1;
        for (int i = start + 1; i < lines.length; i++) {
            String line = lines[i];
            String t = line.trim();
            int ind = indentOf(line);
            if (t.length() == 0) continue;
            if (ind <= baseIndent && !t.startsWith("-")) break;
            if (t.startsWith("-") && (dashIndent < 0 || ind <= dashIndent)) {
                dashIndent = ind;
                cur = new ArrayList<String>();
                blocks.add(cur);
            }
            if (cur == null) continue;
            if (ind < dashIndent) break;
            cur.add(line);
        }

        for (List<String> block : blocks) {
            Node n = fromBlock(block, dashIndent);
            if (n != null) out.add(n);
        }
        return out;
    }

    private static Node fromBlock(List<String> block, int dashIndent) {
        if (block.isEmpty()) return null;
        String first = block.get(0).trim();
        Map<String, String> m = new LinkedHashMap<String, String>();

        if (first.startsWith("- {") || first.startsWith("- {")) {
            String flow = first.substring(first.indexOf('{'));
            // 掐掉行尾注释
            int hash = flow.indexOf(" #");
            if (hash > 0) flow = flow.substring(0, hash);
            Map<String, String> fm = flowMap(flow);
            m.putAll(fm);
        } else {
            m.putAll(blockMap(block, dashIndent));
        }

        String type = low(m.get("type"));
        if (Util.isBlank(type)) return null;
        if (!clashTypeOk(type)) return null;
        String server = strip(m.get("server"));
        int port = Util.toInt(strip(m.get("port")), 0);
        if (badEndpoint(server, port)) return null;

        Node n = new Node();
        n.scheme = type.equals("hysteria2") ? "hysteria2" : type;
        n.server = server;
        n.port = port;
        String nm = strip(m.get("name"));
        if (Util.isBlank(nm)) nm = server + ":" + port;
        n.name = nm;

        n.uuid = strip(m.get("uuid"));
        n.password = strip(firstNonBlank(m.get("password"), m.get("auth"), m.get("auth-str")));
        n.cipher = strip(firstNonBlank(m.get("cipher"), m.get("method")));
        n.alterId = Util.toInt(strip(m.get("alterId")), 0);
        n.flow = strip(m.get("flow"));
        n.tls = Util.truthy(strip(m.get("tls")));
        n.reality = !Util.isBlank(m.get("reality-opts.public-key"));
        if (n.reality) n.tls = true;
        n.sni = strip(firstNonBlank(m.get("servername"), m.get("sni"), m.get("peer")));
        n.net = normNet(strip(m.get("network")));
        n.path = strip(firstNonBlank(firstNonBlank(m.get("ws-opts.path"), m.get("h2-opts.path"), m.get("http-upgrade-opts.path")), m.get("grpc-opts.grpc-service-name"), m.get("path")));
        n.serviceName = strip(m.get("grpc-opts.grpc-service-name"));
        n.wsHost = strip(firstNonBlank(m.get("ws-opts.headers.Host"), m.get("ws-opts.headers.host"), m.get("h2-opts.host")));
        n.skipCertVerify = Util.truthy(strip(m.get("skip-cert-verify")));
        n.fingerprint = strip(firstNonBlank(m.get("client-fingerprint"), m.get("fingerprint")));
        n.alpn = strip(m.get("alpn"));
        n.pbk = strip(m.get("reality-opts.public-key"));
        n.sid = strip(m.get("reality-opts.short-id"));

        String plugin = strip(m.get("plugin"));
        if (!Util.isBlank(plugin)) {
            n.plugin = plugin;
            String mode = strip(m.get("plugin-opts.mode"));
            String host = strip(firstNonBlank(m.get("plugin-opts.host"), m.get("plugin-opts.host")));
            if (!Util.isBlank(mode)) n.pluginOpts = "obfs=" + mode + (Util.isBlank(host) ? "" : ";obfs-host=" + host);
            if (!Util.isBlank(strip(m.get("plugin-opts.path")))) n.path = strip(m.get("plugin-opts.path"));
        }
        if (Util.isBlank(n.net) && !Util.isBlank(strip(m.get("plugin-opts.mode")))) n.net = "tcp";

        // 归一化缩进：proxies 列表项统一顶格，否则会和其他生成的条目错位导致 YAML 解析失败
        int shift = -dashIndent;
        List<String> raw = new ArrayList<String>(block.size());
        for (String line : block) {
            String l = line;
            if (shift > 0) {
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < shift; i++) sb.append(' ');
                l = sb.append(l).toString();
            } else if (shift < 0) {
                int cut = Math.min(-shift, indentOf(l));
                l = l.substring(cut);
            }
            raw.add(l);
        }
        n.rawYaml = raw;

        if (!n.clashReady()) return null;
        return n;
    }

    /** 块式：`key: value` + 嵌套 `sub: value`，键拼成 parent.sub。 */
    private static Map<String, String> blockMap(List<String> block, int dashIndent) {
        Map<String, String> m = new LinkedHashMap<String, String>();
        List<String> path = new ArrayList<String>();
        List<Integer> depths = new ArrayList<Integer>();

        String first = block.get(0).trim();
        if (first.startsWith("-")) first = first.substring(1).trim();
        parseKV(first, 1, path, depths, m);

        for (int i = 1; i < block.size(); i++) {
            String raw = block.get(i);
            String t = raw.trim();
            if (t.startsWith("#")) continue;
            int ind = indentOf(raw);
            int depth = Math.max(1, (ind - dashIndent) / 2);
            parseKV(t, depth, path, depths, m);
        }
        return m;
    }

    private static void parseKV(String t, int depth, List<String> path, List<Integer> depths, Map<String, String> m) {
        if (t.length() == 0) return;
        if (t.startsWith("- ")) {
            // 父键的列表项：alpn: 下面的 - h2
            if (!path.isEmpty()) {
                String parent = join(path);
                String v = yamlScalar(t.substring(2).trim());
                String old = m.get(parent);
                m.put(parent, Util.isBlank(old) ? v : old + "," + v);
            }
            return;
        }
        int colon = t.indexOf(':');
        if (colon <= 0) return;
        String key = t.substring(0, colon).trim();
        String val = t.substring(colon + 1).trim();

        while (!depths.isEmpty() && depths.get(depths.size() - 1) >= depth) {
            depths.remove(depths.size() - 1);
            path.remove(path.size() - 1);
        }
        if (Util.isBlank(val)) {
            depths.add(depth);
            path.add(key);
            return;
        }
        List<String> full = new ArrayList<String>(path);
        full.add(key);
        m.put(join(full), yamlScalar(val));
    }

    private static String join(List<String> parts) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < parts.size(); i++) {
            if (i > 0) sb.append('.');
            sb.append(parts.get(i));
        }
        return sb.toString();
    }

    /** 流式 map：{name: "x", port: 443, ws-opts: {path: /}} */
    private static Map<String, String> flowMap(String flow) {
        Map<String, String> m = new LinkedHashMap<String, String>();
        String inner = flow.trim();
        if (inner.startsWith("{")) inner = inner.substring(1);
        if (inner.endsWith("}")) inner = inner.substring(0, inner.length() - 1);
        List<String> parts = splitFlow(inner);
        for (String part : parts) {
            int colon = topColon(part);
            if (colon <= 0) continue;
            String k = part.substring(0, colon).trim();
            String v = part.substring(colon + 1).trim();
            if (v.startsWith("{")) {
                Map<String, String> sub = flowMap(v);
                for (Map.Entry<String, String> e : sub.entrySet()) m.put(k + "." + e.getKey(), e.getValue());
            } else {
                m.put(k, yamlScalar(v));
            }
        }
        return m;
    }

    private static List<String> splitFlow(String s) {
        List<String> out = new ArrayList<String>();
        StringBuilder cur = new StringBuilder();
        int depth = 0;
        boolean inStr = false;
        char quote = 0;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (inStr) {
                cur.append(c);
                if (c == quote) inStr = false;
                continue;
            }
            if (c == '"' || c == '\'') {
                inStr = true;
                quote = c;
                cur.append(c);
                continue;
            }
            if (c == '{' || c == '[') depth++;
            else if (c == '}' || c == ']') depth--;
            if (c == ',' && depth == 0) {
                out.add(cur.toString());
                cur.setLength(0);
                continue;
            }
            cur.append(c);
        }
        if (cur.length() > 0) out.add(cur.toString());
        return out;
    }

    private static int topColon(String s) {
        int depth = 0;
        boolean inStr = false;
        char quote = 0;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (inStr) {
                if (c == quote) inStr = false;
                continue;
            }
            if (c == '"' || c == '\'') {
                inStr = true;
                quote = c;
                continue;
            }
            if (c == '{' || c == '[') depth++;
            else if (c == '}' || c == ']') depth--;
            else if (c == ':' && depth == 0) {
                if (i + 1 < s.length() && s.charAt(i + 1) == ' ') return i;
                if (i + 1 == s.length()) return i;
            }
        }
        return -1;
    }

    private static String yamlScalar(String v) {
        String s = v.trim();
        if (s.length() >= 2) {
            char a = s.charAt(0), b = s.charAt(s.length() - 1);
            if ((a == '"' && b == '"') || (a == '\'' && b == '\'')) {
                String inner = s.substring(1, s.length() - 1);
                if (a == '"') inner = inner.replace("\\\"", "\"").replace("\\\\", "\\");
                return inner.trim();
            }
        }
        int hash = s.indexOf(" #");
        if (hash > 0) s = s.substring(0, hash).trim();
        return s;
    }

    private static String strip(String s) {
        return s == null ? "" : s.trim();
    }

    /** Clash 名单里只收真正能当节点用的类型（http/socks 之类多是钓鱼占位条目）。 */
    static boolean clashTypeOk(String type) {
        return type.equals("vmess") || type.equals("vless") || type.equals("trojan")
                || type.equals("ss") || type.equals("ssr") || type.equals("hysteria")
                || type.equals("hysteria2") || type.equals("tuic");
    }

    /**
     * 过滤钓鱼 / 占位条目：NoMoreWalls 之类会在名单里塞 127.0.0.53、10.x、0.0.0.0
     * 这种假节点，名字写着「防范境外势力渗透」，专抓爬虫。内网地址对我们也没意义。
     */
    static boolean badEndpoint(String host, int port) {
        if (host == null) return true;
        String h = host.trim().toLowerCase();
        if (h.length() == 0 || port <= 0 || port > 65535) return true;
        if (h.equals("localhost") || h.equals("::1") || h.equals("0.0.0.0")
                || h.equals("[::]") || h.equals("[::1]") || h.equals("none") || h.equals("null")) return true;
        if (h.startsWith("127.") || h.startsWith("10.") || h.startsWith("192.168.")
                || h.startsWith("169.254.") || h.startsWith("198.18.") || h.startsWith("198.19.")
                || h.startsWith("255.255.255.255")) return true;
        if (h.startsWith("172.")) {
            int dot = h.indexOf('.', 4);
            if (dot > 4) {
                int second = Util.toInt(h.substring(4, dot), -1);
                if (second >= 16 && second <= 31) return true;
            }
        }
        return false;
    }

    // ------------------------------------------------------------------ 小工具

    static int indentOf(String line) {
        int i = 0;
        while (i < line.length() && (line.charAt(i) == ' ' || line.charAt(i) == '\t')) i++;
        return i;
    }

    static String[] hostPort(String s) {
        String v = s.trim();
        if (v.length() == 0) return null;
        String host;
        String portPart;
        if (v.startsWith("[")) {
            int close = v.indexOf(']');
            if (close < 0) return null;
            host = v.substring(1, close);
            int colon = v.indexOf(':', close);
            portPart = colon > 0 ? v.substring(colon + 1) : "443";
        } else {
            int colon = v.lastIndexOf(':');
            if (colon <= 0) {
                host = v;
                portPart = "443";
            } else {
                host = v.substring(0, colon);
                portPart = v.substring(colon + 1);
            }
        }
        host = host.trim();
        int slash = host.indexOf('/');
        if (slash > 0) host = host.substring(0, slash);
        int port = Util.toInt(portPart.replaceAll("[^0-9].*$", ""), 443);
        if (host.length() == 0) return null;
        return new String[]{host, String.valueOf(port)};
    }

    private static Map<String, String> params(String query) {
        Map<String, String> m = new LinkedHashMap<String, String>();
        if (Util.isBlank(query)) return m;
        for (String kv : query.split("&")) {
            if (kv.length() == 0) continue;
            int eq = kv.indexOf('=');
            if (eq < 0) {
                m.put(low(kv), "");
            } else {
                m.put(low(kv.substring(0, eq)), kv.substring(eq + 1));
            }
        }
        return m;
    }

    private static String first(Map<String, String> m, String key, String def) {
        String v = m.get(low(key));
        if (Util.isBlank(v)) return def;
        return Util.urlDecode(v);
    }

    private static String firstNonBlank(String a, String b) {
        return Util.isBlank(a) ? b : a;
    }

    private static String firstNonBlank(String a, String b, String c) {
        if (!Util.isBlank(a)) return a;
        if (!Util.isBlank(b)) return b;
        return c;
    }

    private static String low(String s) {
        return s == null ? "" : s.trim().toLowerCase();
    }

    static String normNet(String s) {
        String v = low(s);
        if (v.equals("") || v.equals("none") || v.equals("tcp") || v.equals("raw")) return "tcp";
        if (v.startsWith("ws")) return "ws";
        if (v.startsWith("grpc")) return "grpc";
        if (v.equals("h2") || v.equals("http") || v.equals("h2c")) return "h2";
        if (v.startsWith("httpupgrade")) return "httpupgrade";
        if (v.equals("quic")) return "quic";
        return v;
    }
}
