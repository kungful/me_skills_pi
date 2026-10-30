package com.hua.subhunter;

import java.io.BufferedInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;

/** 抓取：直连 + 自动套 GitHub 镜像（国内直连 raw.githubusercontent 基本不通）。 */
final class Fetcher {

    static final String UA = "clash-verge/v2.1.4";

    private Fetcher() {
    }

    /** 同一份文件的全部候选地址，按「直连 → CDN → 代理」排序。 */
    static List<String> candidates(String url) {
        List<String> out = new ArrayList<String>();
        String u = Util.nz(url).trim();
        if (u.length() == 0) return out;
        out.add(u);

        String prefix = "https://raw.githubusercontent.com/";
        if (u.startsWith(prefix)) {
            String rest = u.substring(prefix.length());   // user/repo/branch/path...
            String[] seg = rest.split("/", 4);
            if (seg.length == 4) {
                String user = seg[0], repo = seg[1], branch = seg[2], path = seg[3];
                String gh = user + "/" + repo + "@" + branch + "/" + path;
                out.add("https://cdn.jsdelivr.net/gh/" + gh);
                out.add("https://fastly.jsdelivr.net/gh/" + gh);
                out.add("https://gcore.jsdelivr.net/gh/" + gh);
                out.add("https://ghproxy.net/" + u);
                out.add("https://ghfast.top/" + u);
                out.add("https://gh-proxy.com/" + u);
                out.add("https://raw.gitmirror.com/" + rest);
                out.add("https://github.moeyy.xyz/" + u);
                out.add("https://ghproxy.cc/" + u);
            }
        }
        return out;
    }

    /** GET 文本。不抛异常，失败返回 null（由调用方统计）。 */
    static String get(String url, int connectMs, int readMs) {
        HttpURLConnection conn = null;
        try {
            URL u = new URL(url);
            conn = (HttpURLConnection) u.openConnection();
            conn.setConnectTimeout(connectMs);
            conn.setReadTimeout(readMs);
            conn.setInstanceFollowRedirects(true);
            conn.setRequestMethod("GET");
            conn.setRequestProperty("User-Agent", UA);
            conn.setRequestProperty("Accept", "*/*");
            conn.setRequestProperty("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8");
            conn.setRequestProperty("Accept-Encoding", "identity");
            conn.setRequestProperty("Cache-Control", "no-cache");
            int code = conn.getResponseCode();
            if (code < 200 || code >= 300) {
                drain(conn.getErrorStream());
                return null;
            }
            InputStream is = conn.getInputStream();
            if (is == null) return null;
            BufferedInputStream bis = new BufferedInputStream(is, 16384);
            ByteArrayOutputStream bos = new ByteArrayOutputStream(65536);
            byte[] buf = new byte[16384];
            int n;
            int guard = 0;
            while ((n = bis.read(buf)) > 0) {
                bos.write(buf, 0, n);
                if (bos.size() > 8 * 1024 * 1024) break;      // 8MB 保护
                if ((++guard & 63) == 0) Thread.sleep(0);      // 让出调度
            }
            bis.close();
            String body = Util.str(bos.toByteArray());
            return body.trim().length() == 0 ? null : body;
        } catch (Throwable t) {
            return null;
        } finally {
            if (conn != null) {
                try {
                    conn.disconnect();
                } catch (Throwable ignore) {
                }
            }
        }
    }

    private static void drain(InputStream is) {
        try {
            if (is != null) {
                byte[] b = new byte[4096];
                while (is.read(b) > 0) ;
                is.close();
            }
        } catch (Throwable ignore) {
        }
    }
}
