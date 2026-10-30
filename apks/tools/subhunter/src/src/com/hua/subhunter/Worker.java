package com.hua.subhunter;

import android.content.Context;
import android.os.PowerManager;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** 后台抓取（JobService / 广播 / 前台服务共用一份逻辑）。 */
final class Worker {

    static final class Outcome {
        Engine.Result result;
        int newCount = 0;
        int prevCount = 0;
        String error = "";
    }

    private Worker() {
    }

    static Engine.Result runNow(Context c, Engine.Sink sink) {
        return run(c, sink).result;
    }

    static Outcome run(Context c, Engine.Sink sink) {
        Outcome out = new Outcome();
        Store st = Store.get(c);
        Hub.fetching = true;

        Set<String> before = new HashSet<String>();
        List<Node> prev = st.nodes();
        for (Node n : prev) before.add(n.scheme + "|" + n.server + "|" + n.port);
        out.prevCount = prev.size();

        PowerManager.WakeLock lock = null;
        try {
            PowerManager pm = (PowerManager) c.getSystemService(Context.POWER_SERVICE);
            if (pm != null) {
                lock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "subhunter:fetch");
                lock.setReferenceCounted(false);
                lock.acquire(6 * 60 * 1000L);
            }
        } catch (Throwable ignore) {
        }

        try {
            Engine.Options o = new Engine.Options();
            o.healthCheck = st.pingOn();
            o.maxNodes = Math.max(20, st.maxNodes());
            o.pingTimeoutMs = Math.max(800, st.pingTimeout());
            List<Source> srcs = st.sources();
            for (Source src : srcs) {
                String via = st.meta("via:" + src.id, "");
                if (!Util.isBlank(via)) o.preferHost.put(src.id, via);
            }
            Engine.Result r = Engine.run(srcs, o, sink);
            for (Engine.SrcStat stat : r.stats) {
                if (stat.ok && !Util.isBlank(stat.via)) st.put("via:" + stat.id, stat.via);
            }
            out.result = r;
            if (!r.nodes.isEmpty()) {
                st.saveResult(r);
                Set<String> after = new HashSet<String>();
                for (Node n : r.nodes) {
                    String k = n.scheme + "|" + n.server + "|" + n.port;
                    if (before.add(k)) out.newCount++;
                    after.add(k);
                }
            } else {
                out.error = "这次没抓到任何节点，沿用上次结果";
            }
        } catch (Throwable t) {
            out.error = t.getClass().getSimpleName() + ": " + t.getMessage();
        } finally {
            Hub.fetching = false;
            if (lock != null) {
                try {
                    if (lock.isHeld()) lock.release();
                } catch (Throwable ignore) {
                }
            }
        }
        return out;
    }
}
