package com.hua.subhunter;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicInteger;

/** 抓取 → 解析 → 去重 → 测活 → 生成订阅 的主流水线（纯 Java，可桌面跑）。 */
final class Engine {

    static final class Options {
        int timeoutMs = 12000;
        boolean healthCheck = true;
        int pingTimeoutMs = 2500;
        int maxNodes = 300;
        int fetchThreads = 4;
        int pingThreads = 28;
        /** 每个源上次走通的主机，下次优先用它（避免每次先在墙掉的 raw 上白等）。 */
        java.util.Map<String, String> preferHost = new java.util.HashMap<String, String>();

        Options copy() {
            Options o = new Options();
            o.timeoutMs = timeoutMs;
            o.healthCheck = healthCheck;
            o.pingTimeoutMs = pingTimeoutMs;
            o.maxNodes = maxNodes;
            o.fetchThreads = fetchThreads;
            o.pingThreads = pingThreads;
            o.preferHost.putAll(preferHost);
            return o;
        }
    }

    static final class SrcStat {
        String id = "";
        String name = "";
        String url = "";
        boolean ok = false;
        int count = 0;
        int ms = 0;
        String err = "";
        String via = "";
    }

    static final class Result {
        List<Node> nodes = new ArrayList<Node>();
        String clashYaml = "";
        String v2rayB64 = "";
        List<SrcStat> stats = new ArrayList<SrcStat>();
        int rawTotal = 0;
        int aliveTotal = 0;
        int clashCount = 0;
        int uriCount = 0;
        long costMs = 0;
        String timeLabel = "";
        long timestamp = 0;
    }

    interface Sink {
        void progress(int percent, String stage, String msg);

        boolean cancelled();
    }

    private Engine() {
    }

    static Result run(List<Source> allSources, final Options o, final Sink sink) {
        long t0 = System.currentTimeMillis();
        Result r = new Result();
        r.timestamp = t0;
        r.timeLabel = new SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.CHINA).format(new Date(t0));

        List<Source> on = new ArrayList<Source>();
        for (Source s : allSources) {
            if (s.enabled && !Util.isBlank(s.url)) on.add(s);
        }
        if (on.isEmpty()) {
            if (sink != null) sink.progress(100, "done", "没有启用的订阅源");
            r.costMs = System.currentTimeMillis() - t0;
            return r;
        }

        // ---------------- 1. 并发抓取 ----------------
        if (sink != null) sink.progress(2, "fetch", "开始抓取 " + on.size() + " 个源");
        int threads = Math.max(1, Math.min(o.fetchThreads, on.size()));
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        List<Future<SrcStat>> futures = new ArrayList<Future<SrcStat>>();
        final Map<String, List<Node>> harvested = Collections.synchronizedMap(new LinkedHashMap<String, List<Node>>());

        for (final Source s : on) {
            futures.add(pool.submit(new Callable<SrcStat>() {
                @Override
                public SrcStat call() {
                    return fetchOne(s, o, harvested);
                }
            }));
        }

        final AtomicInteger done = new AtomicInteger();
        for (int i = 0; i < futures.size(); i++) {
            if (cancelled(sink)) break;
            SrcStat st;
            try {
                st = futures.get(i).get();
            } catch (Throwable t) {
                continue;
            }
            r.stats.add(st);
            int d = done.incrementAndGet();
            if (sink != null) {
                int pct = 5 + (int) (d * 40.0 / on.size());
                sink.progress(pct, "fetch", st.name + " → " + (st.ok ? ("+" + st.count + " 节点") : ("失败 " + st.err)));
            }
        }
        pool.shutdownNow();

        // ---------------- 2. 合并去重 ----------------
        LinkedHashMap<String, Node> merged = new LinkedHashMap<String, Node>();
        int rawTotal = 0;
        for (Source s : on) {
            List<Node> list = harvested.get(s.id);
            if (list == null) continue;
            for (Node n : list) {
                rawTotal++;
                n.sourceId = s.id;
                n.sourceName = s.name;
                String k = n.key();
                Node old = merged.get(k);
                if (old == null) {
                    merged.put(k, n);
                } else {
                    // 有原始分享链接的优先（保证 v2ray 订阅可用）
                    if (Util.isBlank(old.raw) && !Util.isBlank(n.raw)) merged.put(k, n);
                }
            }
        }
        List<Node> nodes = new ArrayList<Node>(merged.values());
        r.rawTotal = rawTotal;
        if (sink != null) sink.progress(50, "merge", "去重后 " + nodes.size() + " 个节点（原始 " + rawTotal + "）");

        // ---------------- 3. 测活 ----------------
        if (o.healthCheck && !nodes.isEmpty() && !cancelled(sink)) {
            pingAll(nodes, o, sink);
            int alive = 0;
            for (Node n : nodes) if (n.latency > 0) alive++;
            r.aliveTotal = alive;
            if (sink != null) sink.progress(88, "ping", "测活完成：可用 " + alive + " / " + nodes.size());
        } else {
            r.aliveTotal = -1;
        }

        // ---------------- 4. 排序 + 截断 ----------------
        List<Node> alive = new ArrayList<Node>();
        List<Node> untested = new ArrayList<Node>();
        for (Node n : nodes) {
            if (n.latency > 0) alive.add(n);
            else if (n.latency == -1 && o.healthCheck) untested.add(n);
            else if (!o.healthCheck) alive.add(n);
        }
        Collections.sort(alive, new Comparator<Node>() {
            @Override
            public int compare(Node a, Node b) {
                return a.latency - b.latency;
            }
        });
        List<Node> finalList = new ArrayList<Node>();
        int cap = Math.max(10, o.maxNodes);
        for (Node n : alive) {
            if (finalList.size() >= cap) break;
            finalList.add(n);
        }
        // 可用节点太少时（比如运营商封了杂端口），把没测通的也补上做紧急备用
        int target = alive.size() >= 20 ? Math.min(cap, alive.size()) : cap;
        for (Node n : untested) {
            if (finalList.size() >= target) break;
            finalList.add(n);
        }
        r.nodes = finalList;

        // ---------------- 5. 生成 ----------------
        if (sink != null) sink.progress(94, "gen", "生成 Clash / v2ray 订阅");
        r.clashCount = Gen.countClash(finalList);
        r.uriCount = Gen.countUri(finalList);
        r.clashYaml = Gen.clash(finalList, r.timeLabel);
        r.v2rayB64 = Gen.v2ray(finalList, r.timeLabel);
        r.costMs = System.currentTimeMillis() - t0;
        if (sink != null) sink.progress(100, "done", "完成：Clash " + r.clashCount + " 条 / v2ray " + r.uriCount + " 条");
        return r;
    }

    // ------------------------------------------------------------------

    private static SrcStat fetchOne(Source s, Options o, Map<String, List<Node>> out) {
        SrcStat st = new SrcStat();
        st.id = s.id;
        st.name = s.name;
        st.url = s.url;
        long t0 = System.currentTimeMillis();
        List<String> cands = Fetcher.candidates(s.url);
        String prefer = o.preferHost == null ? null : o.preferHost.get(s.id);
        if (!Util.isBlank(prefer) && cands.size() > 1) {
            List<String> sorted = new ArrayList<String>();
            for (String c : cands) if (hostOf(c).equals(prefer)) sorted.add(c);
            for (String c : cands) if (!hostOf(c).equals(prefer)) sorted.add(c);
            cands = sorted;
        }
        int tries = Math.min(cands.size(), 6);
        for (int i = 0; i < tries; i++) {
            long spent = System.currentTimeMillis() - t0;
            if (spent > 45000L) break;              // 单个源最多耗 45s，不拖垮整轮
            String url = cands.get(i);
            int conn = i == 0 ? Math.min(6000, o.timeoutMs) : 5000;
            int read = i == 0 ? Math.min(15000, o.timeoutMs) : 12000;
            String body = Fetcher.get(url, conn, read);
            if (body == null) continue;
            List<Node> nodes = Parse.body(body);
            if (nodes.isEmpty()) continue;
            for (Node n : nodes) {
                if (n.name == null || n.name.length() == 0) n.name = n.endpoint();
            }
            out.put(s.id, nodes);
            st.ok = true;
            st.count = nodes.size();
            st.ms = (int) (System.currentTimeMillis() - t0);
            st.via = hostOf(url);
            return st;
        }
        st.ok = false;
        st.err = "全部地址都不通";
        st.ms = (int) (System.currentTimeMillis() - t0);
        return st;
    }

    private static String hostOf(String url) {
        try {
            return new java.net.URL(url).getHost();
        } catch (Throwable t) {
            return "";
        }
    }

    /** 分批测活：够用了就停，避免几千个节点的等待。 */
    private static void pingAll(final List<Node> nodes, final Options o, final Sink sink) {
        final int batch = Math.max(24, o.pingThreads * 2);
        List<Node> pending = new ArrayList<Node>();
        for (Node n : nodes) if (n.pingable()) pending.add(n);

        for (int from = 0; from < pending.size(); from += batch) {
            if (cancelled(sink)) return;
            int to = Math.min(pending.size(), from + batch);
            final List<Node> slice = pending.subList(from, to);
            ExecutorService pool = Executors.newFixedThreadPool(Math.min(o.pingThreads, slice.size()));
            List<Future<?>> fs = new ArrayList<Future<?>>();
            for (final Node n : slice) {
                fs.add(pool.submit(new Runnable() {
                    @Override
                    public void run() {
                        n.latency = Health.ping(n.server, n.port, o.pingTimeoutMs);
                    }
                }));
            }
            for (Future<?> f : fs) {
                try {
                    f.get();
                } catch (Throwable ignore) {
                }
            }
            pool.shutdownNow();

            int alive = 0;
            for (Node n : nodes) if (n.latency > 0) alive++;
            if (sink != null) {
                int pct = Math.min(86, 50 + (int) (to * 36.0 / Math.max(1, pending.size())));
                sink.progress(pct, "ping", "已测 " + to + "/" + pending.size() + " · 可用 " + alive);
            }
            if (alive >= Math.max(o.maxNodes, 40)) return;
        }
    }

    private static boolean cancelled(Sink sink) {
        return sink != null && sink.cancelled();
    }
}
