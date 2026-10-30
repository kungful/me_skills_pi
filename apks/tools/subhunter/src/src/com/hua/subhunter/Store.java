package com.hua.subhunter;

import android.content.Context;
import android.content.SharedPreferences;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.util.ArrayList;
import java.util.List;

/** 本地持久化：源列表 / 设置 / 上次产物（断网时直接拿这里的东西去复制）。 */
final class Store {

    private static final String PREF = "subhunter";
    private static Store inst;

    private final Context ctx;
    private final SharedPreferences sp;

    // 文件内容缓存：state() 每几秒被 JS 拉一次，没必要反复读几十 KB
    private String cClash, cV2ray, cNodes;

    private Store(Context c) {
        ctx = c.getApplicationContext();
        sp = ctx.getSharedPreferences(PREF, Context.MODE_PRIVATE);
    }

    static synchronized Store get(Context c) {
        if (inst == null) inst = new Store(c);
        return inst;
    }

    // ---------------------------------------------------------------- 源

    List<Source> sources() {
        List<Source> out = new ArrayList<Source>();
        String raw = sp.getString("sources", "");
        if (Util.isBlank(raw)) {
            out.addAll(Sources.builtin());
            saveSources(out);
            return out;
        }
        for (String line : raw.split("\n")) {
            Source s = Source.decode(line);
            if (s != null && !Util.isBlank(s.url)) out.add(s);
        }
        // 版本升级后补上新增的内置源
        List<Source> builtin = Sources.builtin();
        for (Source b : builtin) {
            if (Sources.byId(out, b.id) == null) out.add(b);
        }
        return out;
    }

    void saveSources(List<Source> list) {
        StringBuilder sb = new StringBuilder();
        for (Source s : list) {
            if (sb.length() > 0) sb.append('\n');
            sb.append(s.encode());
        }
        sp.edit().putString("sources", sb.toString()).commit();
    }

    Source source(String id) {
        return Sources.byId(sources(), id);
    }

    void setSourceEnabled(String id, boolean on) {
        List<Source> list = sources();
        Source s = Sources.byId(list, id);
        if (s != null) {
            s.enabled = on;
            saveSources(list);
        }
    }

    void addSource(String name, String url) {
        List<Source> list = sources();
        Source s = new Source();
        s.id = "u" + System.currentTimeMillis();
        s.name = Util.isBlank(name) ? "自定义源" : name.trim();
        s.url = url.trim();
        s.kind = "auto";
        s.enabled = true;
        s.builtin = false;
        s.note = "手动添加";
        list.add(s);
        saveSources(list);
    }

    void removeSource(String id) {
        List<Source> list = sources();
        List<Source> keep = new ArrayList<Source>();
        for (Source s : list) if (!s.id.equals(id)) keep.add(s);
        saveSources(keep);
    }

    // ---------------------------------------------------------------- 设置

    int maxNodes() {
        return intOf("maxNodes", 200);
    }

    boolean pingOn() {
        return boolOf("ping", true);
    }

    int pingTimeout() {
        return intOf("pingMs", 2500);
    }

    boolean autoOn() {
        return boolOf("auto", true);
    }

    int autoHour() {
        return intOf("hour", 4);
    }

    int autoMinute() {
        return intOf("minute", 30);
    }

    int port() {
        return intOf("port", 8791);
    }

    boolean notifOn() {
        return boolOf("notif", true);
    }

    void put(String k, String v) {
        sp.edit().putString(k, v).commit();
    }

    int intOf(String k, int def) {
        return Util.toInt(sp.getString(k, String.valueOf(def)), def);
    }

    boolean boolOf(String k, boolean def) {
        String v = sp.getString(k, def ? "1" : "0");
        return Util.truthy(v) || "1".equals(v);
    }

    // ---------------------------------------------------------------- 结果

    void saveResult(Engine.Result r) {
        write(new File(ctx.getFilesDir(), "clash.yaml"), r.clashYaml);
        write(new File(ctx.getFilesDir(), "v2ray.txt"), r.v2rayB64);
        cClash = r.clashYaml;
        cV2ray = r.v2rayB64;
        cNodes = null;
        StringBuilder sb = new StringBuilder();
        for (Node n : r.nodes) {
            sb.append(esc(n.scheme)).append('\t')
                    .append(esc(n.name)).append('\t')
                    .append(esc(n.server)).append('\t')
                    .append(n.port).append('\t')
                    .append(n.latency).append('\t')
                    .append(esc(n.region())).append('\t')
                    .append(esc(n.toUri())).append('\n');
        }
        write(new File(ctx.getFilesDir(), "nodes.lst"), sb.toString());

        StringBuilder st = new StringBuilder();
        for (Engine.SrcStat s : r.stats) {
            if (st.length() > 0) st.append('\n');
            st.append(esc(s.id)).append('\t').append(esc(s.name)).append('\t')
                    .append(s.ok ? "1" : "0").append('\t').append(s.count).append('\t')
                    .append(s.ms).append('\t').append(esc(s.ok ? s.via : s.err));
        }
        sp.edit()
                .putString("lastTime", r.timeLabel)
                .putString("lastTs", String.valueOf(r.timestamp))
                .putString("rawTotal", String.valueOf(r.rawTotal))
                .putString("aliveTotal", String.valueOf(r.aliveTotal))
                .putString("clashCount", String.valueOf(r.clashCount))
                .putString("uriCount", String.valueOf(r.uriCount))
                .putString("costMs", String.valueOf(r.costMs))
                .putString("stats", st.toString())
                .putString("prevCount", sp.getString("nodeCount", "0"))
                .putString("nodeCount", String.valueOf(r.nodes.size()))
                .commit();
    }

    String clashYaml() {
        if (cClash == null) cClash = read(new File(ctx.getFilesDir(), "clash.yaml"));
        return cClash;
    }

    String v2rayB64() {
        if (cV2ray == null) cV2ray = read(new File(ctx.getFilesDir(), "v2ray.txt"));
        return cV2ray;
    }

    String lastTime() {
        return sp.getString("lastTime", "");
    }

    String meta(String key, String def) {
        return sp.getString(key, def);
    }

    List<Node> nodes() {
        List<Node> out = new ArrayList<Node>();
        String raw = cNodes;
        if (raw == null) {
            raw = read(new File(ctx.getFilesDir(), "nodes.lst"));
            cNodes = raw;
        }
        if (Util.isBlank(raw)) return out;
        for (String line : raw.split("\n")) {
            if (Util.isBlank(line)) continue;
            String[] f = line.split("\t", -1);
            if (f.length < 6) continue;
            Node n = new Node();
            n.scheme = f[0];
            n.name = f[1];
            n.server = f[2];
            n.port = Util.toInt(f[3], 0);
            n.latency = Util.toInt(f[4], -1);
            n.raw = f.length > 6 ? f[6] : "";
            out.add(n);
        }
        return out;
    }

    List<String[]> stats() {
        List<String[]> out = new ArrayList<String[]>();
        String raw = sp.getString("stats", "");
        if (Util.isBlank(raw)) return out;
        for (String line : raw.split("\n")) {
            String[] f = line.split("\t", -1);
            if (f.length >= 6) out.add(f);
        }
        return out;
    }

    // ---------------------------------------------------------------- 文件

    private static void write(File f, String s) {
        if (s == null) s = "";
        try {
            FileOutputStream fos = new FileOutputStream(f);
            fos.write(Util.utf8(s));
            fos.close();
        } catch (Throwable ignore) {
        }
    }

    private static String read(File f) {
        if (!f.exists()) return "";
        try {
            FileInputStream fis = new FileInputStream(f);
            ByteArrayOutputStream bos = new ByteArrayOutputStream((int) Math.max(64, f.length()));
            byte[] buf = new byte[8192];
            int n;
            while ((n = fis.read(buf)) > 0) bos.write(buf, 0, n);
            fis.close();
            return Util.str(bos.toByteArray());
        } catch (Throwable t) {
            return "";
        }
    }

    private static String esc(String s) {
        return Util.nz(s).replace("\t", " ").replace("\n", " ").replace("\r", " ");
    }
}
