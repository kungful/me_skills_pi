package com.hua.subhunter;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/** 订阅产物生成：Clash(mihomo) YAML 与 v2ray(base64) 两种。 */
final class Gen {

    static final String GROUP_SELECT = "🚀 节点选择";
    static final String GROUP_AUTO = "♻️ 自动选择";
    static final String GROUP_FALLBACK = "🔯 故障转移";

    private Gen() {
    }

    /** 生成 Clash / mihomo 订阅。timeLabel 只用于注释头部。 */
    static String clash(List<Node> nodes, String timeLabel) {
        List<Node> ok = new ArrayList<Node>();
        for (Node n : nodes) if (n.clashReady()) ok.add(n);

        if (ok.isEmpty()) {
            return "# 订阅猎手：这一轮没有能转成 Clash 的节点\n"
                    + "mixed-port: 7890\nmode: direct\nlog-level: warning\n"
                    + "proxies: []\nproxy-groups: []\nrules:\n  - MATCH,DIRECT\n";
        }

        List<String> names = uniqueNames(ok);
        StringBuilder y = new StringBuilder(4096);
        y.append("# 订阅猎手 SubHunter").append(timeLabel == null ? "" : " · " + timeLabel).append('\n');
        y.append("# 节点数: ").append(ok.size()).append("（mihomo / Clash Meta 及以上）\n");
        y.append("# 说明: 仅用于自建/公开节点聚合备份，请遵守当地法律法规。\n\n");

        y.append("mixed-port: 7890\n");
        y.append("allow-lan: false\n");
        y.append("bind-address: '*'\n");
        y.append("mode: rule\n");
        y.append("log-level: warning\n");
        y.append("ipv6: false\n");
        y.append("unified-delay: true\n");
        y.append("tcp-concurrent: true\n\n");

        y.append("profile:\n");
        y.append("  store-selected: true\n");
        y.append("  store-fake-ip: true\n\n");

        y.append("sniffer:\n");
        y.append("  enable: true\n");
        y.append("  sniff:\n");
        y.append("    TLS:\n");
        y.append("      ports: [443, 8443]\n");
        y.append("    HTTP:\n");
        y.append("      ports: [80, 8080-8880]\n\n");

        // 刻意不写 fallback / fallback-filter：只要写了 fallback，mihomo 就会去下载 geoip 数据库，
        // 手机第一次导入时可能直接因为下载超时而判定「配置加载失败」。
        y.append("dns:\n");
        y.append("  enable: true\n");
        y.append("  ipv6: false\n");
        y.append("  enhanced-mode: fake-ip\n");
        y.append("  fake-ip-range: 198.18.0.1/16\n");
        y.append("  default-nameserver:\n");
        y.append("    - 223.5.5.5\n");
        y.append("    - 119.29.29.29\n");
        y.append("  nameserver:\n");
        y.append("    - 223.5.5.5\n");
        y.append("    - 119.29.29.29\n\n");

        y.append("proxies:\n");
        for (int i = 0; i < ok.size(); i++) {
            String block = ok.get(i).toClash(names.get(i));
            if (block == null) continue;
            y.append(block).append('\n');
        }

        y.append("\nproxy-groups:\n");
        y.append("- name: ").append(Util.yq(GROUP_SELECT)).append('\n');
        y.append("  type: select\n");
        y.append("  proxies:\n");
        y.append("    - ").append(Util.yq(GROUP_AUTO)).append('\n');
        y.append("    - ").append(Util.yq(GROUP_FALLBACK)).append('\n');
        y.append("    - DIRECT\n");
        for (String n : names) y.append("    - ").append(Util.yq(n)).append('\n');

        y.append("- name: ").append(Util.yq(GROUP_AUTO)).append('\n');
        y.append("  type: url-test\n");
        y.append("  url: \"http://cp.cloudflare.com/generate_204\"\n");
        y.append("  interval: 600\n");
        y.append("  tolerance: 80\n");
        y.append("  proxies:\n");
        for (String n : names) y.append("    - ").append(Util.yq(n)).append('\n');

        y.append("- name: ").append(Util.yq(GROUP_FALLBACK)).append('\n');
        y.append("  type: fallback\n");
        y.append("  url: \"http://cp.cloudflare.com/generate_204\"\n");
        y.append("  interval: 600\n");
        y.append("  proxies:\n");
        for (String n : names) y.append("    - ").append(Util.yq(n)).append('\n');

        y.append("\nrules:\n");
        // 刻意不用 GEOIP/GEOSITE：客户端没下 geodata 时那两个规则会让整份配置加载失败
        y.append("  - IP-CIDR,127.0.0.0/8,DIRECT,no-resolve\n");
        y.append("  - IP-CIDR,10.0.0.0/8,DIRECT,no-resolve\n");
        y.append("  - IP-CIDR,172.16.0.0/12,DIRECT,no-resolve\n");
        y.append("  - IP-CIDR,192.168.0.0/16,DIRECT,no-resolve\n");
        y.append("  - IP-CIDR,100.64.0.0/10,DIRECT,no-resolve\n");
        y.append("  - DOMAIN-SUFFIX,cn,DIRECT\n");
        y.append("  - DOMAIN-SUFFIX,qq.com,DIRECT\n");
        y.append("  - DOMAIN-SUFFIX,taobao.com,DIRECT\n");
        y.append("  - DOMAIN-SUFFIX,aliyun.com,DIRECT\n");
        y.append("  - DOMAIN-SUFFIX,bilibili.com,DIRECT\n");
        y.append("  - MATCH,").append(GROUP_SELECT).append('\n');
        return y.toString();
    }

    /** 生成 v2ray / v2rayNG / NekoBox 通用的 base64 订阅。 */
    static String v2ray(List<Node> nodes, String timeLabel) {
        Set<String> seen = new LinkedHashSet<String>();
        StringBuilder sb = new StringBuilder(8192);
        int count = 0;
        for (Node n : nodes) {
            String u = n.toUri();
            if (Util.isBlank(u)) continue;
            if (!seen.add(u)) continue;
            sb.append(u).append('\n');
            count++;
        }
        String payload = sb.toString();
        if (timeLabel != null) {
            // base64 里不能放注释，把批次信息留在外面由调用方展示
        }
        return Util.b64e(Util.utf8(payload));
    }

    static int countUri(List<Node> nodes) {
        Set<String> seen = new HashSet<String>();
        int c = 0;
        for (Node n : nodes) {
            String u = n.toUri();
            if (Util.isBlank(u)) continue;
            if (seen.add(u)) c++;
        }
        return c;
    }

    static int countClash(List<Node> nodes) {
        int c = 0;
        for (Node n : nodes) if (n.clashReady()) c++;
        return c;
    }

    /** Clash 要求 proxies 名字唯一，重名的追加序号。 */
    private static List<String> uniqueNames(List<Node> nodes) {
        List<String> out = new ArrayList<String>(nodes.size());
        Set<String> used = new HashSet<String>();
        for (Node n : nodes) {
            String base = Util.isBlank(n.name) ? n.endpoint() : n.name.trim();
            if (base.equalsIgnoreCase("DIRECT") || base.equalsIgnoreCase("REJECT")) base = "节点 " + base;
            String name = base;
            int i = 2;
            while (used.contains(name)) {
                name = base + " " + i;
                i++;
            }
            used.add(name);
            out.add(name.length() > 48 ? name.substring(0, 48) + "…" : name);
        }
        // 截断后可能又重名，再走一遍
        Set<String> used2 = new HashSet<String>();
        for (int i = 0; i < out.size(); i++) {
            String name = out.get(i);
            if (used2.contains(name)) {
                String base = name;
                int k = 2;
                while (used2.contains(base + " " + k)) k++;
                name = base + " " + k;
            }
            used2.add(name);
            out.set(i, name);
        }
        return out;
    }
}
