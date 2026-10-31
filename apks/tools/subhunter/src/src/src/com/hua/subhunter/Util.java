package com.hua.subhunter;

import java.io.ByteArrayOutputStream;
import java.security.MessageDigest;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 纯 Java 小工具：Base64 / URL 解码 / 扁平 JSON / YAML 引号 / 哈希。
 * 刻意不用 android.util.Base64 与 org.json，这样整套解析可以在桌面 JVM 上跑单测。
 */
final class Util {

    private static final char[] B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/".toCharArray();
    private static final int[] B64I = new int[128];

    static {
        for (int i = 0; i < B64I.length; i++) B64I[i] = -1;
        for (int i = 0; i < B64.length; i++) B64I[B64[i]] = i;
        B64I['-'] = 62;
        B64I['_'] = 63;
    }

    private Util() {
    }

    /** 宽松 base64 解码：接受 url-safe、缺 padding、含换行、混入非法字符。 */
    static byte[] b64d(String s) {
        if (s == null) return new byte[0];
        ByteArrayOutputStream out = new ByteArrayOutputStream(s.length());
        int buf = 0, bits = 0;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c < 128 && B64I[c] >= 0) {
                buf = (buf << 6) | B64I[c];
                bits += 6;
                if (bits >= 8) {
                    bits -= 8;
                    out.write((buf >> bits) & 0xFF);
                }
            }
        }
        return out.toByteArray();
    }

    static String b64e(byte[] data) {
        StringBuilder sb = new StringBuilder((data.length + 2) / 3 * 4);
        int i = 0;
        while (i + 2 < data.length) {
            int n = ((data[i] & 0xFF) << 16) | ((data[i + 1] & 0xFF) << 8) | (data[i + 2] & 0xFF);
            sb.append(B64[(n >> 18) & 63]).append(B64[(n >> 12) & 63]).append(B64[(n >> 6) & 63]).append(B64[n & 63]);
            i += 3;
        }
        int rest = data.length - i;
        if (rest == 1) {
            int n = (data[i] & 0xFF) << 16;
            sb.append(B64[(n >> 18) & 63]).append(B64[(n >> 12) & 63]).append("==");
        } else if (rest == 2) {
            int n = ((data[i] & 0xFF) << 16) | ((data[i + 1] & 0xFF) << 8);
            sb.append(B64[(n >> 18) & 63]).append(B64[(n >> 12) & 63]).append(B64[(n >> 6) & 63]).append('=');
        }
        return sb.toString();
    }

    static String b64e(String text) {
        return b64e(utf8(text));
    }

    static byte[] utf8(String s) {
        if (s == null) return new byte[0];
        try {
            return s.getBytes("UTF-8");
        } catch (Throwable t) {
            return s.getBytes();
        }
    }

    static String str(byte[] b) {
        if (b == null) return "";
        try {
            return new String(b, "UTF-8");
        } catch (Throwable t) {
            return new String(b);
        }
    }

    static String urlDecode(String s) {
        if (s == null) return "";
        ByteArrayOutputStream out = new ByteArrayOutputStream(s.length());
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '%' && i + 2 < s.length()) {
                int hi = Character.digit(s.charAt(i + 1), 16);
                int lo = Character.digit(s.charAt(i + 2), 16);
                if (hi >= 0 && lo >= 0) {
                    out.write((hi << 4) + lo);
                    i += 2;
                    continue;
                }
            }
            if (c == '+') {
                out.write(' ');
                continue;
            }
            byte[] b = utf8(String.valueOf(c));
            out.write(b, 0, b.length);
        }
        return str(out.toByteArray());
    }

    /**
     * 极简扁平 JSON 解析：取出顶层 "key": "value" / 数字 / true|false，忽略嵌套结构。
     * vmess:// 的配置就是扁平 JSON，够用。
     */
    static Map<String, String> jsonFlat(String json) {
        LinkedHashMap<String, String> map = new LinkedHashMap<String, String>();
        if (json == null) return map;
        int i = 0, n = json.length();
        while (i < n) {
            int k = json.indexOf('"', i);
            if (k < 0) break;
            int ke = json.indexOf('"', k + 1);
            if (ke < 0) break;
            String key = unescape(json.substring(k + 1, ke));
            int colon = json.indexOf(':', ke + 1);
            if (colon < 0) break;
            int v = colon + 1;
            while (v < n && Character.isWhitespace(json.charAt(v))) v++;
            if (v >= n) break;
            char c = json.charAt(v);
            if (c == '"') {
                int end = v + 1;
                StringBuilder sb = new StringBuilder();
                while (end < n) {
                    char ch = json.charAt(end);
                    if (ch == '\\') {
                        sb.append(ch);
                        if (end + 1 < n) sb.append(json.charAt(end + 1));
                        end += 2;
                        continue;
                    }
                    if (ch == '"') break;
                    sb.append(ch);
                    end++;
                }
                map.put(key, unescape(sb.toString()));
                i = end + 1;
            } else if (c == '{' || c == '[') {
                i = skipValue(json, v);
            } else {
                int end = v;
                while (end < n && json.charAt(end) != ',' && json.charAt(end) != '}') end++;
                String raw = json.substring(v, end).trim();
                if (raw.endsWith(",")) raw = raw.substring(0, raw.length() - 1).trim();
                map.put(key, raw);
                i = end;
            }
        }
        return map;
    }

    private static int skipValue(String s, int start) {
        int depth = 0;
        boolean inStr = false;
        for (int i = start; i < s.length(); i++) {
            char c = s.charAt(i);
            if (inStr) {
                if (c == '\\') i++;
                else if (c == '"') inStr = false;
                continue;
            }
            if (c == '"') inStr = true;
            else if (c == '{' || c == '[') depth++;
            else if (c == '}' || c == ']') {
                depth--;
                if (depth == 0) return i + 1;
            }
        }
        return s.length();
    }

    private static String unescape(String s) {
        if (s == null || s.indexOf('\\') < 0) return s == null ? "" : s;
        StringBuilder sb = new StringBuilder(s.length());
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c != '\\' || i + 1 >= s.length()) {
                sb.append(c);
                continue;
            }
            char n = s.charAt(++i);
            switch (n) {
                case 'n':
                    sb.append('\n');
                    break;
                case 't':
                    sb.append('\t');
                    break;
                case 'r':
                    sb.append('\r');
                    break;
                case 'b':
                    sb.append('\b');
                    break;
                case 'f':
                    sb.append('\f');
                    break;
                case 'u':
                    if (i + 4 < s.length()) {
                        try {
                            sb.append((char) Integer.parseInt(s.substring(i + 1, i + 5), 16));
                            i += 4;
                        } catch (Throwable t) {
                            sb.append("u");
                        }
                    }
                    break;
                default:
                    sb.append(n);
            }
        }
        return sb.toString();
    }

    /** YAML 双引号字符串：转义反斜杠与双引号，去掉控制字符。 */
    static String yq(String v) {
        if (v == null) v = "";
        StringBuilder sb = new StringBuilder(v.length() + 2);
        sb.append('"');
        for (int i = 0; i < v.length(); i++) {
            char c = v.charAt(i);
            if (c == '"' || c == '\\') sb.append('\\').append(c);
            else if (c == '\n') sb.append("\\n");
            else if (c < 0x20) sb.append(' ');
            else sb.append(c);
        }
        sb.append('"');
        return sb.toString();
    }

    static String hex(byte[] b) {
        StringBuilder sb = new StringBuilder(b.length * 2);
        for (byte x : b) {
            sb.append(Character.forDigit((x >> 4) & 15, 16)).append(Character.forDigit(x & 15, 16));
        }
        return sb.toString();
    }

    static String sha1(String s) {
        try {
            return hex(MessageDigest.getInstance("SHA-1").digest(utf8(s)));
        } catch (Throwable t) {
            return Integer.toHexString(s == null ? 0 : s.hashCode());
        }
    }

    static String md5(String s) {
        try {
            return hex(MessageDigest.getInstance("MD5").digest(utf8(s)));
        } catch (Throwable t) {
            return Integer.toHexString(s == null ? 0 : s.hashCode());
        }
    }

    static boolean isBlank(String s) {
        return s == null || s.trim().length() == 0;
    }

    static String nz(String s) {
        return s == null ? "" : s;
    }

    static boolean truthy(String s) {
        if (s == null) return false;
        String v = s.trim().toLowerCase();
        return v.equals("1") || v.equals("true") || v.equals("yes") || v.equals("on") || v.equals("tls") || v.equals("reality");
    }

    static int toInt(String s, int def) {
        try {
            String v = nz(s).trim();
            if (v.length() == 0) return def;
            return Integer.parseInt(v);
        } catch (Throwable t) {
            return def;
        }
    }
}
