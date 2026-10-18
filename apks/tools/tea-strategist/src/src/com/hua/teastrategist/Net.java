package com.hua.teastrategist;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;
import java.util.zip.GZIPInputStream;

/**
 * 原生 HTTP 客户端。
 *
 * 为什么要放在原生：WebView 里的 fetch/XHR 受同源策略限制，抓不了
 * 腾讯行情、东方财富、新浪这类接口。放在 Java 层就完全没有跨域问题。
 *
 * 另外这里处理了一个老问题：腾讯行情返回的是 GBK，不处理就是乱码。
 */
final class Net {

    static final class Res {
        int status;
        String body;
        String charset;
        Map<String, String> headers = new HashMap<>();
    }

    static Res fetch(String url, String method, Map<String, String> headers,
                     String body, String encoding, int timeoutSec) throws Exception {

        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        try {
            c.setInstanceFollowRedirects(true);
            c.setConnectTimeout(Math.max(3000, timeoutSec * 1000 / 2));
            c.setReadTimeout(Math.max(5000, timeoutSec * 1000));
            c.setRequestProperty("User-Agent",
                    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Mobile Safari/537.36");
            c.setRequestProperty("Accept", "*/*");
            c.setRequestProperty("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8");
            if (headers != null) {
                for (Map.Entry<String, String> e : headers.entrySet()) {
                    if (e.getKey() == null) continue;
                    c.setRequestProperty(e.getKey(), e.getValue() == null ? "" : e.getValue());
                }
            }

            boolean hasBody = body != null && !body.isEmpty();
            if (hasBody && "GET".equalsIgnoreCase(method)) method = "POST";
            c.setRequestMethod(method == null || method.isEmpty() ? (hasBody ? "POST" : "GET") : method.toUpperCase());

            if (hasBody) {
                c.setDoOutput(true);
                if (c.getRequestProperty("Content-Type") == null)
                    c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                byte[] b = body.getBytes("UTF-8");
                c.setFixedLengthStreamingMode(b.length);
                OutputStream os = c.getOutputStream();
                os.write(b);
                os.flush();
                os.close();
            }

            Res r = new Res();
            r.status = c.getResponseCode();
            for (Map.Entry<String, java.util.List<String>> e : c.getHeaderFields().entrySet()) {
                if (e.getKey() != null && e.getValue() != null && !e.getValue().isEmpty())
                    r.headers.put(e.getKey().toLowerCase(), e.getValue().get(0));
            }

            byte[] raw;
            InputStream is = (r.status >= 400) ? c.getErrorStream() : c.getInputStream();
            if (is == null) { r.body = ""; return r; }

            String ce = c.getContentEncoding();
            if (ce != null && ce.toLowerCase().contains("gzip")) is = new GZIPInputStream(is);

            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = is.read(buf)) > 0) bo.write(buf, 0, n);
            is.close();
            raw = bo.toByteArray();

            String enc = pickEncoding(encoding, r.headers.get("content-type"));
            r.charset = enc;
            r.body = decode(raw, enc);
            // 客户端没声明编码、又解出乱码 → 退回复试 GBK
            if (r.body.indexOf('\uFFFD') >= 0 && !"gbk".equals(enc)) {
                String alt = decode(raw, "GBK");
                if (alt.indexOf('\uFFFD') < r.body.indexOf('\uFFFD')) {
                    r.body = alt;
                    r.charset = "gbk";
                }
            }
            return r;
        } finally {
            try { c.disconnect(); } catch (Exception ignored) { }
        }
    }

    private static String pickEncoding(String explicit, String contentType) {
        if (explicit != null && !explicit.isEmpty()) return explicit.toLowerCase();
        if (contentType != null) {
            int i = contentType.toLowerCase().indexOf("charset=");
            if (i >= 0) {
                String s = contentType.substring(i + 8).trim();
                int j = s.indexOf(';');
                if (j > 0) s = s.substring(0, j);
                s = s.replace("\"", "").trim().toLowerCase();
                if (s.startsWith("gb") || s.contains("gb2312")) return "GBK";
                if (s.contains("utf")) return "UTF-8";
                return s;
            }
        }
        return "UTF-8";
    }

    private static String decode(byte[] raw, String enc) {
        try { return new String(raw, enc); }
        catch (Exception e) {
            try { return new String(raw, "UTF-8"); } catch (Exception e2) { return ""; }
        }
    }

    static String toQuery(Map<String, String> m) {
        if (m == null || m.isEmpty()) return "";
        StringBuilder sb = new StringBuilder();
        for (Iterator<Map.Entry<String, String>> it = m.entrySet().iterator(); it.hasNext(); ) {
            Map.Entry<String, String> e = it.next();
            sb.append(e.getKey()).append('=').append(e.getValue() == null ? "" : e.getValue());
            if (it.hasNext()) sb.append('&');
        }
        return sb.toString();
    }

    static String readAll(InputStream in) throws Exception {
        BufferedReader r = new BufferedReader(new InputStreamReader(in, "UTF-8"));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = r.readLine()) != null) sb.append(line).append('\n');
        r.close();
        return sb.toString();
    }
}
