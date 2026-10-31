package com.hua.subhunter;

import java.util.ArrayList;
import java.util.List;

/** 一个订阅源。 */
final class Source {

    String id = "";
    String name = "";
    String url = "";
    String kind = "auto";       // auto / uri / clash
    boolean enabled = true;
    boolean builtin = false;
    String note = "";

    Source() {
    }

    Source(String id, String name, String url, String kind, boolean enabled, String note) {
        this.id = id;
        this.name = name;
        this.url = url;
        this.kind = kind;
        this.enabled = enabled;
        this.builtin = true;
        this.note = note;
    }

    /** 制表符分隔的一行，够用且不用引入 JSON。 */
    String encode() {
        StringBuilder sb = new StringBuilder();
        sb.append(esc(id)).append('\t').append(esc(name)).append('\t').append(esc(kind))
                .append('\t').append(enabled ? "1" : "0").append('\t').append(esc(url))
                .append('\t').append(builtin ? "1" : "0").append('\t').append(esc(note));
        return sb.toString();
    }

    static Source decode(String line) {
        if (Util.isBlank(line)) return null;
        String[] f = line.split("\t", -1);
        if (f.length < 5) return null;
        Source s = new Source();
        s.id = unesc(f[0]);
        s.name = unesc(f[1]);
        s.kind = unesc(f[2]);
        s.enabled = f[3].equals("1");
        s.url = unesc(f[4]);
        s.builtin = f.length > 5 && f[5].equals("1");
        s.note = f.length > 6 ? unesc(f[6]) : "";
        return s;
    }

    private static String esc(String s) {
        return Util.nz(s).replace("\t", " ").replace("\n", " ").replace("\r", " ");
    }

    private static String unesc(String s) {
        return Util.nz(s);
    }

    Source copy() {
        Source s = new Source();
        s.id = id;
        s.name = name;
        s.url = url;
        s.kind = kind;
        s.enabled = enabled;
        s.builtin = builtin;
        s.note = note;
        return s;
    }
}

/** 内置公益节点聚合源。全部是公开仓库的 raw 地址，抓取时自动套 CDN 镜像。 */
final class Sources {

    private Sources() {
    }

    static List<Source> builtin() {
        List<Source> list = new ArrayList<Source>();
        // 实测可用（2026-05 复核），按节点量排序
        add(list, "ermaozi", "ermaozi 每日聚合",
                "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
                "uri", true, "每日更新 · 约 500 条 · v2ray 链接");
        add(list, "v2rayagg", "V2RayAggregator",
                "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/Eternity.txt",
                "uri", true, "海外聚合 · 约 400 条");
        add(list, "nomorewalls", "NoMoreWalls",
                "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.txt",
                "clash", true, "Clash 名单 · 节点量最大 · 需 mihomo");
        add(list, "automerge", "AutoMergePublicNodes",
                "https://raw.githubusercontent.com/chengaopan/AutoMergePublicNodes/master/list.yml",
                "clash", true, "Clash 名单 · 自动合并");
        add(list, "freefq-paw", "Free-servers",
                "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
                "uri", true, "少量精选 · hysteria2 为主");
        add(list, "ripao", "ripaojiedian",
                "https://raw.githubusercontent.com/ripaojiedian/freenode/main/sub",
                "uri", true, "小体积精选源");
        add(list, "ermaozi-clash", "ermaozi Clash 版",
                "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/clash.yml",
                "clash", false, "与 v2ray 版同源，Clash 用户可选");
        add(list, "aiboboxx", "aiboboxx/v2rayfree",
                "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/v2",
                "uri", false, "老牌日更源，时好时坏");
        add(list, "soroush", "Telegram 采集器",
                "https://raw.githubusercontent.com/soroushmirzaei/telegram-configs-collector/main/sub/normal/mix",
                "uri", false, "TG 频道采集，量大但死节点多");
        return list;
    }

    private static void add(List<Source> list, String id, String name, String url, String kind,
                            boolean enabled, String note) {
        list.add(new Source(id, name, url, kind, enabled, note));
    }

    static Source byId(List<Source> all, String id) {
        for (Source s : all) if (s.id != null && s.id.equals(id)) return s;
        return null;
    }
}
