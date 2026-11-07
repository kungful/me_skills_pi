package com.hua.paintbox;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Semaphore;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 极简 MCP server（Streamable HTTP 传输，只回单个 JSON，不开 SSE 流）。
 *
 * 原理照 Mika 的 McpRpc/MiniHttpServer：一个端口、每个连接一个线程、连接数有上限、
 * 请求头和正文都有大小上限、不做 TLS（只在 127.0.0.1 或局域网里用）。
 * 老协议先 initialize 握手（回 2025-03-26，Mika 客户端要的就是它），新协议（带 _meta 版本号）
 * 也认，只是不做严格的头校验——两边都只是「拿目录 + 调工具」。
 *
 * 服务端不发请求、不发通知、不发会话编号，所以完全无状态：客户端重连不需要带任何东西。
 */
public final class Mcp {

    // ---------------------------------------------------------------- 工具定义

    /** 一条工具：名字、给模型看的说明、inputSchema（JSON 文本，原样回给客户端）。 */
    public static final class Def {
        final String name, title, description, schema;
        final boolean readOnly, destructive;

        public Def(String name, String title, String description, String schema,
                   boolean readOnly, boolean destructive) {
            this.name = name;
            this.title = title;
            this.description = description;
            this.schema = schema;
            this.readOnly = readOnly;
            this.destructive = destructive;
        }

        JSONObject toJson() throws Exception {
            JSONObject o = new JSONObject();
            o.put("name", name);
            o.put("title", title == null ? name : title);
            o.put("description", description == null ? "" : description);
            o.put("inputSchema", new JSONObject(schema));
            JSONObject ann = new JSONObject();
            ann.put("readOnlyHint", readOnly);
            ann.put("destructiveHint", destructive);
            ann.put("openWorldHint", !readOnly);
            o.put("annotations", ann);
            return o;
        }
    }

    /** 工具实现：拿到参数对象，返回结构化结果；抛异常就是 isError 的工具错误。 */
    public interface Tools {
        List<Def> defs();

        /** 执行工具。返回的 JSONObject 既是 structuredContent，也会被序列化成文本给模型看。 */
        JSONObject call(String name, JSONObject args) throws Exception;
    }

    // ---------------------------------------------------------------- 状态

    private static final String LEGACY_VERSION = "2025-03-26";
    private static final Set<String> LEGACY_VERSIONS = new java.util.HashSet<>(java.util.Arrays.asList(
            "2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"));
    private static final Set<String> MODERN_VERSIONS = new java.util.HashSet<>(Collections.singletonList("2026-07-28"));

    private static final int MAX_HEADER_BYTES = 16 * 1024;
    private static final int MAX_BODY_BYTES = 8 * 1024 * 1024;

    private final Tools tools;
    private final String serverName;
    private final String serverTitle;
    private final String version;
    private final String instructions;
    private final LogSink log;
    private final AtomicLong ids = new AtomicLong(0);

    private ServerSocket server;
    private Thread acceptThread;
    private volatile boolean running;
    private final Semaphore slots = new Semaphore(8);
    private final Set<Socket> open = ConcurrentHashMap.newKeySet();
    private final ExecutorService pool = Executors.newCachedThreadPool(r -> {
        Thread t = new Thread(r, "mcp-call");
        t.setDaemon(true);
        return t;
    });
    private volatile String token = "";
    private volatile String bindHost = "127.0.0.1";

    /** 日志出口：App 里接到界面的 LogPane，没有就是空实现。 */
    public interface LogSink {
        void log(String line);
    }

    public Mcp(Tools tools, String serverName, String serverTitle, String version,
               String instructions, LogSink log) {
        this.tools = tools;
        this.serverName = serverName;
        this.serverTitle = serverTitle;
        this.version = version;
        this.instructions = instructions;
        this.log = log == null ? s -> {
        } : log;
    }

    public List<Def> defs() {
        return tools.defs();
    }

    // ---------------------------------------------------------------- 生命周期

    /** 绑定端口并开始收连接；返回实际端口。bindHost 用 "127.0.0.1" 或 "0.0.0.0"。 */
    public synchronized int start(int port, String bindHost, String token) throws IOException {
        stop();
        this.token = token == null ? "" : token.trim();
        this.bindHost = bindHost == null || bindHost.isEmpty() ? "127.0.0.1" : bindHost;
        ServerSocket s = null;
        IOException last = null;
        // 端口偶尔还在 TIME_WAIT / 上一个 socket 刚关：重试三次再认失败
        for (int attempt = 0; attempt < 3; attempt++) {
            ServerSocket cand = new ServerSocket();
            cand.setReuseAddress(true);
            try {
                cand.bind(new InetSocketAddress(InetAddress.getByName(this.bindHost), port), 16);
                s = cand;
                break;
            } catch (IOException e) {
                last = e;
                try {
                    cand.close();
                } catch (IOException ignored) {
                }
                try {
                    Thread.sleep(250);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }
        if (s == null) throw last == null ? new IOException("bind failed") : last;
        server = s;
        running = true;
        final ServerSocket listen = s;
        acceptThread = new Thread(() -> {
            try {
                acceptLoop(listen);
            } catch (Throwable t) {
                android.util.Log.e("McpWatch", "accept loop died", t);
                throw t;
            }
        }, "mcp-accept");
        acceptThread.setDaemon(true);
        acceptThread.start();
        log.log("MCP 已监听 " + this.bindHost + ":" + s.getLocalPort() + "/mcp");
        return s.getLocalPort();
    }

    public synchronized void stop() {
        running = false;
        if (server != null) {
            try {
                server.close();
            } catch (IOException ignored) {
            }
        }
        server = null;
        for (Socket s : new ArrayList<>(open)) {
            try {
                s.close();
            } catch (IOException ignored) {
            }
        }
        open.clear();
    }

    public boolean running() {
        return running;
    }

    /** 线程还活着、端口也还开着才算真的在服务（看门狗用）。 */
    public boolean alive() {
        Thread t = acceptThread;
        return running && server != null && (t == null || t.isAlive());
    }

    public int port() {
        ServerSocket s = server;
        return s == null ? -1 : s.getLocalPort();
    }

    public String bindHost() {
        return bindHost;
    }

    public static String version() {
        return LEGACY_VERSION;
    }

    // ---------------------------------------------------------------- 连接

    private void acceptLoop(ServerSocket s) {
        while (running) {
            Socket socket;
            try {
                socket = s.accept();
            } catch (IOException e) {
                if (!running) break;
                // 单次 accept 出错（连接被重置、fd 暂时不够）不该把整个监听线程带走
                log.log("accept 出错（继续监听）: " + e);
                try {
                    Thread.sleep(120);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    break;
                }
                continue;
            }
            if (!slots.tryAcquire()) {
                closeQuietly(socket);
                continue;
            }
            open.add(socket);
            Thread t = new Thread(() -> {
                try {
                    serve(socket);
                } finally {
                    open.remove(socket);
                    closeQuietly(socket);
                    slots.release();
                }
            }, "mcp-conn");
            t.setDaemon(true);
            t.start();
        }
        log.log("MCP 监听已停止");
    }

    private void serve(Socket socket) {
        android.util.Log.d("McpWatch", "serve " + socket.getRemoteSocketAddress());
        try {
            socket.setSoTimeout(30_000);
            socket.setTcpNoDelay(true);
            InputStream in = new BufferedInputStream(socket.getInputStream());
            OutputStream out = socket.getOutputStream();
            Req req = readRequest(in);
            if (req == null) return;
            Res res = route(req);
            write(out, res);
        } catch (IOException e) {
            // 客户端断开是常态，不刷日志
        } catch (Throwable t) {
            log.log("处理请求出错: " + t);
        }
    }

    private static void closeQuietly(Socket s) {
        try {
            s.close();
        } catch (IOException ignored) {
        }
    }

    // ---------------------------------------------------------------- HTTP

    private static final class Req {
        String method = "";
        String path = "/";
        String query = "";
        final Map<String, String> headers = new LinkedHashMap<>();
        byte[] body = new byte[0];
        String remote = "";

        String header(String name) {
            return headers.get(name.toLowerCase(Locale.US));
        }
    }

    private static final class Res {
        int status = 200;
        String contentType = "application/json";
        byte[] body = new byte[0];
        final Map<String, String> headers = new LinkedHashMap<>();

        static Res json(int status, String text) {
            Res r = new Res();
            r.status = status;
            r.body = text.getBytes(java.nio.charset.StandardCharsets.UTF_8);
            return r;
        }

        static Res empty(int status) {
            Res r = new Res();
            r.status = status;
            r.body = new byte[0];
            return r;
        }

        Res h(String k, String v) {
            headers.put(k, v);
            return this;
        }
    }

    private Req readRequest(InputStream in) throws IOException {
        String line = readLine(in, MAX_HEADER_BYTES);
        if (line == null || line.isEmpty()) return null;
        String[] parts = line.split(" ");
        if (parts.length < 2) throw new IOException("bad request line");
        Req r = new Req();
        r.method = parts[0].toUpperCase(Locale.US);
        String target = parts[1];
        int q = target.indexOf('?');
        if (q >= 0) {
            r.path = target.substring(0, q);
            r.query = target.substring(q + 1);
        } else {
            r.path = target;
        }
        int headerBytes = 0;
        while (true) {
            String h = readLine(in, MAX_HEADER_BYTES);
            if (h == null || h.isEmpty()) break;
            headerBytes += h.length();
            if (headerBytes > MAX_HEADER_BYTES) throw new IOException("headers too large");
            int c = h.indexOf(':');
            if (c > 0) r.headers.put(h.substring(0, c).trim().toLowerCase(Locale.US), h.substring(c + 1).trim());
        }
        String te = r.header("transfer-encoding");
        if (te != null && te.toLowerCase(Locale.US).contains("chunked")) {
            r.body = readChunked(in);
        } else {
            long len = 0;
            String cl = r.header("content-length");
            if (cl != null) {
                try {
                    len = Long.parseLong(cl.trim());
                } catch (NumberFormatException e) {
                    throw new IOException("bad content-length");
                }
            }
            if (len > MAX_BODY_BYTES) throw new IOException("body too large");
            r.body = readFully(in, (int) len);
        }
        return r;
    }

    private static String readLine(InputStream in, int max) throws IOException {
        ByteArrayOutputStream buf = new ByteArrayOutputStream();
        while (true) {
            int b = in.read();
            if (b == -1) return buf.size() == 0 ? null : buf.toString("UTF-8");
            if (buf.size() > max) throw new IOException("line too long");
            if (b == '\n') {
                String s = buf.toString("UTF-8");
                return s.endsWith("\r") ? s.substring(0, s.length() - 1) : s;
            }
            buf.write(b);
        }
    }

    private static byte[] readFully(InputStream in, int len) throws IOException {
        byte[] out = new byte[len];
        int off = 0;
        while (off < len) {
            int n = in.read(out, off, len - off);
            if (n < 0) throw new IOException("unexpected end of body");
            off += n;
        }
        return out;
    }

    private static byte[] readChunked(InputStream in) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        while (true) {
            String sizeLine = readLine(in, 1024);
            if (sizeLine == null) break;
            int semi = sizeLine.indexOf(';');
            String hex = (semi >= 0 ? sizeLine.substring(0, semi) : sizeLine).trim();
            if (hex.isEmpty()) continue;
            int size = Integer.parseInt(hex, 16);
            if (size == 0) {
                // 吃掉 trailer
                while (true) {
                    String t = readLine(in, MAX_HEADER_BYTES);
                    if (t == null || t.isEmpty()) break;
                }
                break;
            }
            if (out.size() + size > MAX_BODY_BYTES) throw new IOException("body too large");
            out.write(readFully(in, size));
            readLine(in, 8);
        }
        return out.toByteArray();
    }

    private void write(OutputStream out, Res res) throws IOException {
        StringBuilder head = new StringBuilder();
        head.append("HTTP/1.1 ").append(res.status).append(' ').append(reason(res.status)).append("\r\n");
        head.append("Content-Type: ").append(res.contentType).append("\r\n");
        head.append("Content-Length: ").append(res.body.length).append("\r\n");
        head.append("Cache-Control: no-store\r\n");
        head.append("Connection: close\r\n");
        for (Map.Entry<String, String> e : res.headers.entrySet()) {
            head.append(e.getKey()).append(": ").append(e.getValue()).append("\r\n");
        }
        head.append("\r\n");
        out.write(head.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
        if (res.body.length > 0) out.write(res.body);
        out.flush();
    }

    private static String reason(int status) {
        switch (status) {
            case 200:
                return "OK";
            case 202:
                return "Accepted";
            case 204:
                return "No Content";
            case 400:
                return "Bad Request";
            case 401:
                return "Unauthorized";
            case 404:
                return "Not Found";
            case 405:
                return "Method Not Allowed";
            case 406:
                return "Not Acceptable";
            case 415:
                return "Unsupported Media Type";
            case 500:
                return "Internal Server Error";
            case 503:
                return "Service Unavailable";
            default:
                return "OK";
        }
    }

    // ---------------------------------------------------------------- 路由

    private Res route(Req req) {
        String path = req.path == null ? "/" : req.path;
        boolean api = path.equals("/mcp") || path.equals("/mcp/") || path.equals("/") || path.isEmpty();

        if (!api && path.equals("/health")) {
            try {
                JSONObject o = new JSONObject();
                o.put("ok", true);
                o.put("server", serverName);
                o.put("version", version);
                o.put("tools", tools.defs().size());
                return Res.json(200, o.toString());
            } catch (Exception e) {
                return Res.json(500, "{\"ok\":false}");
            }
        }
        if (!api) return Res.json(404, err(null, -32601, "Not Found").toString());

        if (!authorized(req)) {
            return Res.json(401, err(null, -32001, "Unauthorized: missing or bad bearer token").toString())
                    .h("WWW-Authenticate", "Bearer");
        }
        if (req.method.equals("GET")) {
            return Res.json(405, err(null, -32600, "Only POST is supported on this endpoint").toString())
                    .h("Allow", "POST");
        }
        if (req.method.equals("DELETE")) return Res.empty(200);
        if (!req.method.equals("POST")) {
            return Res.json(405, err(null, -32600, "Only POST is supported on this endpoint").toString())
                    .h("Allow", "POST");
        }

        String contentType = req.header("content-type");
        if (contentType != null) {
            String type = contentType.split(";")[0].trim().toLowerCase(Locale.US);
            if (!type.equals("application/json")) {
                return Res.json(415, err(null, -32600, "Content-Type must be application/json").toString());
            }
        }

        JSONObject msg;
        try {
            String text = new String(req.body, java.nio.charset.StandardCharsets.UTF_8);
            if (text.trim().startsWith("[")) {
                return Res.json(400, err(null, -32600, "Batches are not supported").toString());
            }
            msg = new JSONObject(text);
        } catch (Throwable t) {
            return Res.json(400, err(null, -32700, "Parse error").toString());
        }
        return handleRpc(msg, req);
    }

    private boolean authorized(Req req) {
        String want = token;
        if (want == null || want.isEmpty()) return true;
        String auth = req.header("authorization");
        if (auth != null && auth.trim().equalsIgnoreCase("Bearer " + want)) return true;
        String q = req.query == null ? "" : req.query;
        for (String part : q.split("&")) {
            int eq = part.indexOf('=');
            if (eq > 0 && part.substring(0, eq).equals("token")) {
                String v = part.substring(eq + 1);
                try {
                    v = java.net.URLDecoder.decode(v, "UTF-8");
                } catch (Throwable ignored) {
                }
                if (v.equals(want)) return true;
            }
        }
        return false;
    }

    // ---------------------------------------------------------------- JSON-RPC

    private Res handleRpc(JSONObject msg, Req req) {
        String jsonrpc = msg.optString("jsonrpc", "");
        String method = msg.optString("method", null);
        Object id = msg.opt("id");

        if (!"2.0".equals(jsonrpc)) {
            return Res.json(400, err(id, -32600, "Not a JSON-RPC 2.0 message").toString());
        }
        if (method == null) {
            // 客户端对我们请求的回应（我们不请求）或坏消息
            if (msg.has("result") || msg.has("error")) return Res.empty(202);
            return Res.json(400, err(id, -32600, "Missing method").toString());
        }
        if (id == null || id == JSONObject.NULL) {
            // 通知：notifications/initialized 之类，收下不回内容
            return Res.empty(202);
        }

        try {
            JSONObject params = msg.optJSONObject("params");
            if (params == null) params = new JSONObject();

            if (method.equals("initialize")) {
                String asked = params.optString("protocolVersion", LEGACY_VERSION);
                String negotiated = LEGACY_VERSIONS.contains(asked) ? asked
                        : MODERN_VERSIONS.contains(asked) ? LEGACY_VERSION : LEGACY_VERSION;
                JSONObject client = params.optJSONObject("clientInfo");
                log.log("客户端连接: " + (client == null ? "未命名" : client.optString("name", "?"))
                        + " 协议 " + asked + " → " + negotiated);
                JSONObject result = new JSONObject();
                result.put("protocolVersion", negotiated);
                result.put("capabilities", capabilities());
                result.put("serverInfo", serverInfo());
                result.put("instructions", instructions == null ? "" : instructions);
                return ok(id, result);
            }
            if (method.equals("server/discover")) {
                JSONArray versions = new JSONArray();
                for (String v : MODERN_VERSIONS) versions.put(v);
                for (String v : LEGACY_VERSIONS) versions.put(v);
                JSONObject result = new JSONObject();
                result.put("supportedVersions", versions);
                result.put("capabilities", capabilities());
                result.put("instructions", instructions == null ? "" : instructions);
                return ok(id, result);
            }
            if (method.equals("ping")) return ok(id, new JSONObject());
            if (method.equals("tools/list")) {
                JSONArray arr = new JSONArray();
                for (Def d : tools.defs()) arr.put(d.toJson());
                JSONObject result = new JSONObject();
                result.put("tools", arr);
                return ok(id, result);
            }
            if (method.equals("tools/call")) {
                return callTool(id, params);
            }
            return Res.json(200, err(id, -32601, "Method not found: " + method).toString());
        } catch (Exception e) {
            log.log("RPC 出错 " + method + ": " + e);
            return Res.json(500, err(id, -32603, "Internal error: " + e).toString());
        }
    }

    private Res callTool(Object id, JSONObject params) throws Exception {
        String name = params.optString("name", "");
        if (name.isEmpty()) return Res.json(400, err(id, -32602, "params.name must be a string").toString());
        boolean known = false;
        for (Def d : tools.defs()) if (d.name.equals(name)) known = true;
        if (!known) return Res.json(400, err(id, -32602, "Unknown tool: " + name).toString());

        JSONObject args = params.optJSONObject("arguments");
        if (args == null) args = new JSONObject();

        final String toolName = name;
        final JSONObject toolArgs = args;
        final long t0 = System.currentTimeMillis();
        log.log("→ " + toolName + " " + brief(args));
        JSONObject structured;
        boolean failed = false;
        String text;
        try {
            final JSONObject[] holder = new JSONObject[1];
            final Throwable[] boom = new Throwable[1];
            Runnable job = () -> {
                try {
                    holder[0] = tools.call(toolName, toolArgs);
                } catch (Throwable t) {
                    boom[0] = t;
                }
            };
            Thread t = new Thread(job, "mcp-tool");
            t.setDaemon(true);
            t.start();
            t.join();
            if (boom[0] != null) throw boom[0];
            structured = holder[0] == null ? new JSONObject() : holder[0];
            text = structured.toString(2);
        } catch (Throwable t) {
            failed = true;
            structured = new JSONObject();
            structured.put("error", String.valueOf(t.getMessage() == null ? t : t.getMessage()));
            text = "工具执行失败: " + (t.getMessage() == null ? t.toString() : t.getMessage());
        }
        long ms = System.currentTimeMillis() - t0;
        log.log((failed ? "✗ " : "✓ ") + toolName + " " + ms + "ms"
                + (failed ? " " + brief(structured) : ""));

        JSONObject result = new JSONObject();
        JSONArray content = new JSONArray();
        JSONObject c = new JSONObject();
        c.put("type", "text");
        c.put("text", text);
        content.put(c);
        result.put("content", content);
        result.put("structuredContent", structured);
        result.put("isError", failed);
        return ok(id, result);
    }

    private JSONObject capabilities() throws Exception {
        JSONObject caps = new JSONObject();
        JSONObject t = new JSONObject();
        t.put("listChanged", false);
        caps.put("tools", t);
        return caps;
    }

    private JSONObject serverInfo() throws Exception {
        JSONObject o = new JSONObject();
        o.put("name", serverName);
        o.put("title", serverTitle);
        o.put("version", version);
        return o;
    }

    private static Res ok(Object id, JSONObject result) {
        try {
            JSONObject o = new JSONObject();
            o.put("jsonrpc", "2.0");
            o.put("id", id == null ? JSONObject.NULL : id);
            o.put("result", result);
            return Res.json(200, o.toString());
        } catch (Exception e) {
            return Res.json(500, "{\"jsonrpc\":\"2.0\",\"error\":{\"code\":-32603,\"message\":\"internal\"}}");
        }
    }

    private static JSONObject err(Object id, int code, String message) {
        JSONObject o = new JSONObject();
        try {
            o.put("jsonrpc", "2.0");
            if (id != null) o.put("id", id);
            JSONObject e = new JSONObject();
            e.put("code", code);
            e.put("message", message);
            o.put("error", e);
        } catch (Exception ignored) {
        }
        return o;
    }

    private static String brief(JSONObject o) {
        String s = o == null ? "" : o.toString();
        return s.length() <= 300 ? s : s.substring(0, 300) + "…";
    }
}
