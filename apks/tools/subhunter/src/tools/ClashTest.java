package com.hua.subhunter;

import java.io.FileOutputStream;
import java.util.ArrayList;
import java.util.List;

/** 专门验证 Clash 名单（proxies: 段）解析与回灌：抓两个真实名单，生成配置交给 mihomo 校验。 */
public class ClashTest {

    public static void main(String[] args) throws Exception {
        String[] urls = {
                "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.txt",
                "https://raw.githubusercontent.com/chengaopan/AutoMergePublicNodes/master/list.yml",
                "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/clash.yml",
        };
        List<Node> all = new ArrayList<Node>();
        for (String u : urls) {
            String body = null;
            for (String c : Fetcher.candidates(u)) {
                body = Fetcher.get(c, 8000, 20000);
                if (body != null) break;
            }
            if (body == null) {
                System.out.println("抓取失败: " + u);
                continue;
            }
            List<Node> nodes = Parse.body(body);
            int rawYaml = 0;
            for (Node n : nodes) if (n.rawYaml != null) rawYaml++;
            System.out.println(String.format("%-70s 解析 %4d 条（原样 YAML %d）", u.substring(u.lastIndexOf('/') + 1), nodes.size(), rawYaml));
            all.addAll(nodes);
            if (!nodes.isEmpty()) {
                Node n = nodes.get(0);
                System.out.println("  首个节点: " + n.scheme + " " + n.endpoint() + " " + n.name + " → uri=" + n.toUri().substring(0, Math.min(60, n.toUri().length())));
            }
        }
        String yaml = Gen.clash(all, "clash-test");
        FileOutputStream fos = new FileOutputStream("/tmp/out/clash_from_yaml.yaml");
        fos.write(Util.utf8(yaml));
        fos.close();
        System.out.println("合计 " + all.size() + " → clash " + Gen.countClash(all) + " / uri " + Gen.countUri(all));
        System.out.println("写入 /tmp/out/clash_from_yaml.yaml");
    }
}
