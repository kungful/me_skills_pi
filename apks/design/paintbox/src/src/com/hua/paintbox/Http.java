package com.hua.paintbox;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

public class Http {

    public static class R {
        public int code;
        public String body = "";
        @Override public String toString() { return "HTTP " + code + " " + body; }
    }

    public static R req(String method, String url, String body, String bearer, int readTimeoutMs)
            throws IOException {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        try {
            c.setRequestMethod(method);
            c.setConnectTimeout(20000);
            c.setReadTimeout(readTimeoutMs);
            c.setRequestProperty("Accept", "application/json");
            c.setRequestProperty("User-Agent", "PaintBox-Android/1.0");
            if (bearer != null && bearer.length() > 0) {
                c.setRequestProperty("Authorization", "Bearer " + bearer);
            }
            if (body != null) {
                byte[] b = body.getBytes("UTF-8");
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                c.setFixedLengthStreamingMode(b.length);
                OutputStream os = c.getOutputStream();
                os.write(b);
                os.flush();
                os.close();
            }
            R r = new R();
            r.code = c.getResponseCode();
            InputStream is = r.code >= 400 ? c.getErrorStream() : c.getInputStream();
            r.body = is == null ? "" : read(is);
            return r;
        } finally {
            c.disconnect();
        }
    }

    public static String get(String url, String bearer, int readTimeoutMs) throws IOException {
        return req("GET", url, null, bearer, readTimeoutMs).body;
    }

    public static byte[] bytes(String url, String bearer, int readTimeoutMs) throws IOException {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        try {
            c.setConnectTimeout(20000);
            c.setReadTimeout(readTimeoutMs);
            c.setRequestProperty("User-Agent", "PaintBox-Android/1.0");
            if (bearer != null && bearer.length() > 0) {
                c.setRequestProperty("Authorization", "Bearer " + bearer);
            }
            int code = c.getResponseCode();
            InputStream is = code >= 400 ? c.getErrorStream() : c.getInputStream();
            if (code >= 400) throw new IOException("HTTP " + code + " " + (is == null ? "" : abbr(read(is), 300)));
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            byte[] buf = new byte[16384];
            int n;
            while ((n = is.read(buf)) > 0) bo.write(buf, 0, n);
            return bo.toByteArray();
        } finally {
            c.disconnect();
        }
    }

    private static String read(InputStream is) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(is, "UTF-8"));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = br.readLine()) != null) sb.append(line).append('\n');
        br.close();
        return sb.toString();
    }

    public static String abbr(String s, int max) {
        if (s == null) return "";
        s = s.trim();
        return s.length() <= max ? s : s.substring(0, max) + "…";
    }

    public static String pretty(String raw) {
        try {
            Object o = new org.json.JSONTokener(raw).nextValue();
            return o instanceof org.json.JSONObject
                    ? ((org.json.JSONObject) o).toString(2)
                    : ((org.json.JSONArray) o).toString(2);
        } catch (Throwable t) {
            return raw;
        }
    }
}
