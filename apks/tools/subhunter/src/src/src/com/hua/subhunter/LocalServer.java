package com.hua.subhunter;

import java.io.BufferedInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * 本机订阅服务：Clash / v2rayNG 直接填 http://127.0.0.1:PORT/clash 就能订阅，
 * 每天自动抓取后客户端「更新订阅」即拿到最新节点。只监听 127.0.0.1，不对外暴露。
 */
final class LocalServer {

    interface Provider {
        String clashYaml();

        String v2rayB64();

        String info();
    }

    private final int port;
    private final Provider provider;
    private volatile ServerSocket server;
    private volatile boolean running = false;
    private Thread worker;
    private String lastError = "";
    private int hits = 0;

    LocalServer(int port, Provider provider) {
        this.port = port;
        this.provider = provider;
    }

    boolean isRunning() {
        return running;
    }

    Provider provider() {
        return provider;
    }

    int port() {
        return port;
    }

    String lastError() {
        return lastError;
    }

    int hits() {
        return hits;
    }

    synchronized boolean start() {
        if (running) return true;
        try {
            ServerSocket ss = new ServerSocket(port, 16, InetAddress.getByName("127.0.0.1"));
            ss.setReuseAddress(true);
            server = ss;
            running = true;
            lastError = "";
            worker = new Thread(new Runnable() {
                @Override
                public void run() {
                    acceptLoop();
                }
            }, "subhunter-http");
            worker.setDaemon(true);
            worker.start();
            return true;
        } catch (Throwable t) {
            lastError = t.getClass().getSimpleName() + (t.getMessage() == null ? "" : (": " + t.getMessage()));
            running = false;
            return false;
        }
    }

    synchronized void stop() {
        running = false;
        try {
            if (server != null) server.close();
        } catch (Throwable ignore) {
        }
        server = null;
        if (worker != null) {
            try {
                worker.join(600);
            } catch (Throwable ignore) {
            }
            worker = null;
        }
    }

    private void acceptLoop() {
        while (running) {
            Socket s = null;
            try {
                s = server.accept();
                handle(s);
            } catch (Throwable t) {
                if (running) {
                    lastError = String.valueOf(t.getMessage());
                    try {
                        Thread.sleep(120);
                    } catch (InterruptedException ignore) {
                    }
                }
            } finally {
                try {
                    if (s != null) s.close();
                } catch (Throwable ignore) {
                }
            }
        }
    }

    private void handle(Socket s) {
        try {
            s.setSoTimeout(6000);
            InputStream in = new BufferedInputStream(s.getInputStream());
            String first = readLine(in);
            if (first == null) return;
            String path = "/";
            String[] parts = first.split(" ");
            if (parts.length >= 2) path = parts[1];
            String line;
            int guard = 0;
            while ((line = readLine(in)) != null && line.length() > 0 && guard++ < 80) {
                // 丢掉请求头
            }

            String query = "";
            int q = path.indexOf('?');
            if (q >= 0) {
                query = path.substring(q + 1);
                path = path.substring(0, q);
            }
            String p = path.toLowerCase(Locale.ROOT);
            hits++;

            String body;
            String type;
            if (p.equals("/clash") || p.equals("/clash.yaml") || p.equals("/clash.yml") || p.equals("/mihomo")) {
                body = provider.clashYaml();
                type = "text/yaml; charset=utf-8";
            } else if (p.equals("/v2ray") || p.equals("/sub") || p.equals("/v2") || p.equals("/base64")) {
                body = provider.v2rayB64();
                type = "text/plain; charset=utf-8";
            } else if (p.equals("/info")) {
                body = provider.info();
                type = "application/json; charset=utf-8";
            } else if (p.equals("/health")) {
                body = "ok " + now();
                type = "text/plain; charset=utf-8";
            } else if (p.equals("/") || p.equals("/index.html")) {
                body = page(query);
                type = "text/html; charset=utf-8";
            } else {
                respond(s, 404, "text/plain; charset=utf-8", "404 not found");
                return;
            }
            if (body == null || body.length() == 0) body = "";
            respond(s, 200, type, body);
        } catch (Throwable ignore) {
        }
    }

    private void respond(Socket s, int code, String type, String body) throws IOException {
        byte[] data = Util.utf8(body);
        OutputStream os = s.getOutputStream();
        StringBuilder h = new StringBuilder();
        h.append("HTTP/1.1 ").append(code).append(code == 200 ? " OK" : " Not Found").append("\r\n");
        h.append("Content-Type: ").append(type).append("\r\n");
        h.append("Content-Length: ").append(data.length).append("\r\n");
        h.append("Cache-Control: no-store, no-cache, must-revalidate\r\n");
        h.append("Subscription-Userinfo: upload=0; download=0; total=0; expire=0\r\n");
        h.append("Profile-Update-Interval: 24\r\n");
        h.append("Connection: close\r\n\r\n");
        os.write(Util.utf8(h.toString()));
        os.write(data);
        os.flush();
    }

    private static String readLine(InputStream in) throws IOException {
        ByteArrayOutputStream bos = new ByteArrayOutputStream(128);
        int c = in.read();
        if (c < 0) return null;
        while (c >= 0 && c != '\n') {
            if (c != '\r') bos.write(c);
            c = in.read();
            if (bos.size() > 8192) break;
        }
        return Util.str(bos.toByteArray());
    }

    private String page(String query) {
        StringBuilder sb = new StringBuilder(2048);
        sb.append("<!doctype html><meta charset=\"utf-8\"><title>订阅猎手 · 本机订阅服务</title>");
        sb.append("<style>body{background:#0b1017;color:#e8f4f0;font:15px/1.7 -apple-system,'PingFang SC',sans-serif;margin:0;padding:28px}");
        sb.append("code{background:#141c26;padding:2px 7px;border-radius:6px;color:#3ddc97;word-break:break-all}");
        sb.append("a{color:#5ac8fa}h1{font-size:19px;margin:0 0 14px}p{margin:8px 0;color:#9fb3ad}</style>");
        sb.append("<h1>🎯 订阅猎手 · 本机订阅服务</h1>");
        sb.append("<p>服务时间：").append(now()).append("</p>");
        sb.append("<p>Clash / mihomo 订阅地址：<br><code>http://127.0.0.1:").append(port).append("/clash</code></p>");
        sb.append("<p>v2rayNG / NekoBox 订阅地址：<br><code>http://127.0.0.1:").append(port).append("/v2ray</code></p>");
        sb.append("<p>被请求 ").append(hits).append(" 次。App 进程被系统回收后服务会停，重新打开 App 或点「自启」即可。</p>");
        sb.append("</body>");
        return sb.toString();
    }

    private static String now() {
        return new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.CHINA).format(new Date());
    }
}
