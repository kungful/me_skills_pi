package com.hua.subhunter;

import java.io.File;
import java.io.FileOutputStream;
import java.util.List;

/** 桌面 JVM 冒烟测试：抓真源 → 解析 → 去重 → 生成，检查产物是否合法。 */
public class CoreTest {

    public static void main(String[] args) throws Exception {
        boolean ping = args.length > 0 && args[0].equals("--ping");
        int maxNodes = args.length > 1 ? Integer.parseInt(args[1]) : 200;
        List<Source> sources = Sources.builtin();
        for (Source s : sources) {
            if (s.id.equals("soroush")) s.enabled = false;
        }

        Engine.Options o = new Engine.Options();
        o.healthCheck = ping;
        o.maxNodes = maxNodes;
        o.timeoutMs = 12000;

        Engine.Result r = Engine.run(sources, o, new Engine.Sink() {
            public void progress(int pct, String stage, String msg) {
                System.out.println("[" + pct + "%] " + stage + " · " + msg);
            }

            public boolean cancelled() {
                return false;
            }
        });

        System.out.println("\n== 源统计 ==");
        for (Engine.SrcStat st : r.stats) {
            System.out.println(String.format("%-22s %-6s %4d 个  %5dms  %s",
                    st.name, st.ok ? "OK" : "FAIL", st.count, st.ms, st.ok ? st.via : st.err));
        }
        System.out.println("\n原始 " + r.rawTotal + " → 去重 " + r.nodes.size()
                + " · clash " + r.clashCount + " · uri " + r.uriCount
                + " · 耗时 " + r.costMs + "ms");

        File dir = new File("/tmp/out");
        dir.mkdirs();
        write(new File(dir, "clash.yaml"), r.clashYaml);
        write(new File(dir, "v2ray.txt"), r.v2rayB64);
        System.out.println("clash.yaml " + r.clashYaml.length() + " 字节, v2ray.txt " + r.v2rayB64.length() + " 字节");

        // 抽样打印前几个节点
        int shown = 0;
        for (Node n : r.nodes) {
            System.out.println("  " + n.scheme + " " + n.endpoint() + "  " + n.name
                    + "  lat=" + n.latency + "  原始yaml=" + (n.rawYaml != null));
            if (++shown >= 6) break;
        }
    }

    private static void write(File f, String s) throws Exception {
        FileOutputStream fos = new FileOutputStream(f);
        fos.write(s.getBytes("UTF-8"));
        fos.close();
    }
}
