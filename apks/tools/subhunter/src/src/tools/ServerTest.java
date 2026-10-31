package com.hua.subhunter;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/** 本机订阅服务的 HTTP 冒烟测试（纯 Java，桌面可跑）。 */
public class ServerTest {

    public static void main(String[] args) throws Exception {
        final String clash = read("/tmp/out/clash.yaml");
        final String v2 = read("/tmp/out/v2ray.txt");
        if (clash.length() == 0 || v2.length() == 0) {
            System.out.println("先跑 CoreTest 生成 /tmp/out");
            return;
        }
        LocalServer s = new LocalServer(18791, new LocalServer.Provider() {
            public String clashYaml() {
                return clash;
            }

            public String v2rayB64() {
                return v2;
            }

            public String info() {
                return "{\"nodes\":200}";
            }
        });
        System.out.println("start: " + s.start() + " err=" + s.lastError());
        Thread.sleep(200);

        String[] paths = {"/clash", "/v2ray", "/info", "/health", "/", "/nope"};
        for (String p : paths) {
            String[] r = get("http://127.0.0.1:18791" + p, p.equals("/clash") || p.equals("/v2ray"));
            System.out.println(String.format("%-8s -> %s  %d bytes  head=%s",
                    p, r[0], r[1].length(), r[1].length() > 0 ? r[1].substring(0, Math.min(42, r[1].length())).replace('\n', ' ') : ""));
        }
        System.out.println("hits=" + s.hits());
        s.stop();
        System.out.println("stopped, running=" + s.isRunning());
    }

    private static String[] get(String url, boolean keepBody) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(3000);
        c.setReadTimeout(5000);
        c.setRequestProperty("User-Agent", "clash-verge/v2.1.4");
        int code = c.getResponseCode();
        InputStream is = code >= 400 ? c.getErrorStream() : c.getInputStream();
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        if (is != null) {
            byte[] b = new byte[8192];
            int n;
            while ((n = is.read(b)) > 0) bos.write(b, 0, n);
            is.close();
        }
        String body = new String(bos.toByteArray(), "UTF-8");
        return new String[]{String.valueOf(code), keepBody ? body : body.substring(0, Math.min(64, body.length()))};
    }

    private static String read(String path) throws Exception {
        java.io.File f = new java.io.File(path);
        if (!f.exists()) return "";
        java.io.FileInputStream in = new java.io.FileInputStream(f);
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        byte[] b = new byte[8192];
        int n;
        while ((n = in.read(b)) > 0) bos.write(b, 0, n);
        in.close();
        return new String(bos.toByteArray(), "UTF-8");
    }
}
