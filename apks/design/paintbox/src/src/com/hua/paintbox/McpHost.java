package com.hua.paintbox;

import android.content.Context;

import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;

/**
 * MCP 服务的单一实例：设置（开关 / 端口 / 监听范围 / 令牌）存在 SecurePrefs，
 * 服务器本身常驻在这里，界面和前台服务都通过它开关。
 */
public final class McpHost {

    public static final int DEFAULT_PORT = PaintBoxTools.DEFAULT_PORT;
    public static final String BIND_LOOPBACK = "loopback";
    public static final String BIND_LAN = "lan";

    private static McpHost instance;

    public static synchronized McpHost get(Context c) {
        if (instance == null) instance = new McpHost(c.getApplicationContext());
        return instance;
    }

    /** 服务器状态变化时回调（界面刷新用）。 */
    public interface Listener {
        void onMcpChanged();
    }

    private final Context ctx;
    private final SecurePrefs prefs;
    private final List<Listener> listeners = new ArrayList<>();
    private final List<Mcp.LogSink> sinks = new ArrayList<>();
    private Mcp server;

    private McpHost(Context c) {
        this.ctx = c;
        this.prefs = new SecurePrefs(c);
    }

    // ------------------------------------------------------------------ 设置

    public boolean enabled() {
        return prefs.getBool("mcp.enabled", false);
    }

    public void setEnabled(boolean on) {
        prefs.putBool("mcp.enabled", on);
    }

    public int port() {
        try {
            int p = Integer.parseInt(prefs.get("mcp.port", String.valueOf(DEFAULT_PORT)).trim());
            return p >= 1024 && p <= 65535 ? p : DEFAULT_PORT;
        } catch (Throwable t) {
            return DEFAULT_PORT;
        }
    }

    public void setPort(int p) {
        prefs.put("mcp.port", String.valueOf(p));
    }

    public String bindMode() {
        return BIND_LAN.equals(prefs.get("mcp.bind", BIND_LOOPBACK)) ? BIND_LAN : BIND_LOOPBACK;
    }

    public void setBindMode(String mode) {
        prefs.put("mcp.bind", BIND_LAN.equals(mode) ? BIND_LAN : BIND_LOOPBACK);
    }

    public String bindHost() {
        return BIND_LAN.equals(bindMode()) ? "0.0.0.0" : "127.0.0.1";
    }

    public String token() {
        return prefs.get("mcp.token", "");
    }

    public void setToken(String t) {
        prefs.put("mcp.token", t == null ? "" : t.trim());
    }

    public String newToken() {
        byte[] b = new byte[24];
        new SecureRandom().nextBytes(b);
        String t = Base64.getUrlEncoder().withoutPadding().encodeToString(b);
        setToken(t);
        return t;
    }

    /** 界面要复制的那个 URL。监听 0.0.0.0 时用局域网地址，否则 127.0.0.1。 */
    public String url() {
        int p = server != null && server.running() ? server.port() : port();
        if (BIND_LAN.equals(bindMode())) {
            String ip = NetInfo.lanIpv4();
            return "http://" + (ip == null ? "127.0.0.1" : ip) + ":" + p + "/mcp";
        }
        return "http://127.0.0.1:" + p + "/mcp";
    }

    // ------------------------------------------------------------------ 服务

    public synchronized Mcp server() {
        return server;
    }

    public boolean running() {
        Mcp s = server;
        return s != null && s.running();
    }

    /** 启停服务器；返回 null 表示成功，否则是失败原因。 */
    public synchronized String apply() {
        boolean want = enabled();
        if (!want) {
            if (server != null) {
                server.stop();
                server = null;
            }
            notifyChanged();
            return null;
        }
        String token = token();
        if (BIND_LAN.equals(bindMode()) && (token == null || token.isEmpty())) {
            // 开到局域网就把令牌补上，别让同网段的人随便调
            token = newToken();
            log("已自动生成访问令牌（局域网开放需要）");
        }
        try {
            if (server == null) {
                server = new Mcp(new PaintBoxTools(ctx), "paintbox", "跑图助手", "1.0",
                        "跑图助手：用 grsai 接口生成图片。先 list_models 看模型和档位，"
                                + "再用 draw_image 出图（每次扣费），没等完就用 draw_status 取图。"
                                + "图片会存进手机相册 Pictures/跑图助手，同时返回可下载的 URL。",
                        this::log);
            }
            server.start(port(), bindHost(), token);
            log("监听 " + bindHost() + ":" + server.port() + "  工具 " + server.defs().size() + " 个"
                    + (token == null || token.isEmpty() ? "（无令牌）" : "（需 Bearer 令牌）"));
            notifyChanged();
            return null;
        } catch (Throwable t) {
            log("启动失败: " + t);
            server = null;
            notifyChanged();
            return String.valueOf(t.getMessage() == null ? t : t.getMessage());
        }
    }

    public synchronized void restart() {
        if (server != null) {
            server.stop();
            server = null;
        }
        apply();
    }

    // ------------------------------------------------------------------ 日志 / 监听

    public void log(String line) {
        List<Mcp.LogSink> copy;
        synchronized (sinks) {
            copy = new ArrayList<>(sinks);
        }
        for (Mcp.LogSink s : copy) {
            try {
                s.log(line);
            } catch (Throwable ignored) {
            }
        }
    }

    public void addSink(Mcp.LogSink s) {
        synchronized (sinks) {
            sinks.add(s);
        }
    }

    public void removeSink(Mcp.LogSink s) {
        synchronized (sinks) {
            sinks.remove(s);
        }
    }

    public void addListener(Listener l) {
        synchronized (listeners) {
            listeners.add(l);
        }
    }

    public void removeListener(Listener l) {
        synchronized (listeners) {
            listeners.remove(l);
        }
    }

    private void notifyChanged() {
        List<Listener> copy;
        synchronized (listeners) {
            copy = new ArrayList<>(listeners);
        }
        for (Listener l : copy) {
            try {
                l.onMcpChanged();
            } catch (Throwable ignored) {
            }
        }
    }
}
