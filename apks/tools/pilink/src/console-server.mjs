/**
 * 手机派发台 —— 一个单文件 HTTP 服务，纯局域网、纯 HTTP，不需要证书。
 *
 * 为什么不用 PWA / Web Push：安卓的 Chrome 在 http:// (非 secure context) 下不暴露
 * serviceWorker 和 PushManager，所以推送那条路走不通。
 * 但"派发工作"这件事不需要推送，只需要一个能点的网页 —— 那就没必要上 HTTPS。
 *
 * 路由：
 *   GET  /                      手机控制台（要 ?t=<token>，成功后写 cookie）
 *   GET  /?do=resume&session=ID 让某个会话继续跑（手机通知的按钮用这个）
 *   GET  /?do=<快捷指令名>       跑一条预设指令
 *   GET  /api/state             运行时状态 JSON
 *   POST /api/dispatch          新开一个会话
 *   POST /api/send              往已有会话追加 prompt
 *
 * 用法：node console-server.mjs
 */
import { createServer } from "node:http";
import { randomBytes } from "node:crypto";
import { appendFileSync, createReadStream, existsSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { Readable } from "node:stream";
import { basename, join } from "node:path";

// 免令牌的 APK 分发目录：手机直接输网址就能下，不用记令牌。
// 放的是公开安装包，没有任何秘密。
const APK_DIR = join(import.meta.dirname, "apk");

// 派发台自己的图标 / PWA 清单（由 make-icons.mjs 生成），放 web/ 里纯静态。
// 和 APK 一样免令牌：桌面快捷方式取图标时不一定带着 cookie。
const WEB_DIR = join(import.meta.dirname, "web");
const WEB_FILES = {
  "/favicon.ico": ["favicon.png", "image/png"],
  "/favicon.png": ["favicon.png", "image/png"],
  "/apple-touch-icon.png": ["apple-touch-icon.png", "image/png"],
  "/icon-192.png": ["icon-192.png", "image/png"],
  "/icon-512.png": ["icon-512.png", "image/png"],
  "/icon-maskable-512.png": ["icon-maskable-512.png", "image/png"],
  "/manifest.webmanifest": ["manifest.webmanifest", "application/manifest+json; charset=utf-8"],
};

/** 加在页面 <head> 里的一串图标声明（三个页面共用） */
const ICON_HEAD = `<link rel="icon" href="/favicon.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="#14161a">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="派发台">`;

// ══════════════════════════════════════════════════════════════════════════
// 消息中转（自研，不依赖任何第三方推送服务）
//
// 为什么把它并进派发台而不是再起一个进程：
//   通知的发送方（watchdog）和接收方（手机 App）本来就都在这台机器/这个网里，
//   中转只需要「一个带游标的环形缓存 + 一条长连接」。多一个进程、多一份配置、
//   多一个开机自启项，换不来任何东西。
//
// 协议（字段名从上一版沿用，这样 App 的解析/历史/通知都不用改）：
//   POST /pi/publish          发一条消息（要令牌）
//   GET  /pi/stream?since=&ka=  NDJSON 长连接：先补发 since 之后的，再实时推（要令牌）
//   GET  /pi/messages?since=   只拿缓存（轮询/补收用，要令牌）
//   POST /pi/ack               送达回执（免令牌，只追加一行日志）
//
// 游标语义：since=none → 不补旧消息（首次安装，别一次弹 55 条）；
//           since=<id> → 给该 id 之后的；游标不在缓存里（被轮转掉）→ 全给，宁可重复不可丢。
// ══════════════════════════════════════════════════════════════════════════
const MESSAGES_FILE = join(STATE_DIR, "messages.jsonl");
const MAX_CACHE = 500;
let msgs = [];
let seqCounter = 0;
/** 当前活着的推送流：{ res, ka } */
const streams = new Set();

(function loadMessages() {
  if (!existsSync(MESSAGES_FILE)) return;
  try {
    const lines = readFileSync(MESSAGES_FILE, "utf8").split("\n").filter(Boolean);
    for (const line of lines.slice(-MAX_CACHE)) {
      const m = JSON.parse(line);
      msgs.push(m);
      seqCounter = Math.max(seqCounter, m.seq ?? 0);
    }
    console.log(`[中转] 消息缓存载入 ${msgs.length} 条，seq 到 ${seqCounter}`);
  } catch (error) {
    console.error(`[中转] 缓存载入失败：${error.message}`);
  }
})();

function newMessageId() {
  return randomBytes(8).toString("base64url").slice(0, 10);
}

function publishMessage(body) {
  const msg = {
    id: newMessageId(),
    seq: (seqCounter += 1),
    time: Math.floor(Date.now() / 1000),
    title: String(body.title ?? "Pi"),
    message: String(body.message ?? ""),
    priority: Number(body.priority ?? 3),
    click: body.click ? String(body.click) : null,
    actions: Array.isArray(body.actions) ? body.actions.slice(0, 3) : [],
    group: body.group ? String(body.group) : null,
    tags: Array.isArray(body.tags) ? body.tags : [],
  };
  msgs.push(msg);
  if (msgs.length > MAX_CACHE) msgs = msgs.slice(-MAX_CACHE);
  try {
    appendFileSync(MESSAGES_FILE, `${JSON.stringify(msg)}\n`);
  } catch (error) {
    console.error(`[中转] 消息落盘失败：${error.message}`);
  }

  const line = `${JSON.stringify({ ...msg, event: "message" })}\n`;
  for (const stream of [...streams]) {
    try {
      stream.res.write(line);
    } catch {
      streams.delete(stream);
    }
  }
  return msg;
}

function messagesSince(since) {
  if (!since || since === "none") return [];
  if (since === "all") return msgs.slice();
  // 时间窗写法：10m / 1h / 2d —— 只看这段时间内的
  const win = /^(\d+)([smhd])$/.exec(since);
  if (win) {
    const mult = { s: 1, m: 60, h: 3600, d: 86400 }[win[2]];
    const cutoff = Math.floor(Date.now() / 1000) - Number(win[1]) * mult;
    return msgs.filter((m) => m.time >= cutoff);
  }
  const idx = msgs.findIndex((m) => m.id === since);
  if (idx < 0) return msgs.slice();
  return msgs.slice(idx + 1);
}

function ndjson(res, status, chunks) {
  const body = chunks.join("");
  res.writeHead(status, {
    "Content-Type": "application/x-ndjson; charset=utf-8",
    "Cache-Control": "no-store",
    "Content-Length": Buffer.byteLength(body),
  });
  res.end(body);
}

/** 目录里最新的那个 .apk：/apk 短地址和 /app 引导页都用它 */
function newestApk() {
  if (!existsSync(APK_DIR)) return null;
  const newest = readdirSync(APK_DIR)
    .filter((f) => f.toLowerCase().endsWith(".apk"))
    .map((f) => ({ f, m: statSync(join(APK_DIR, f)).mtimeMs }))
    .sort((a, b) => b.m - a.m)[0];
  return newest ? newest.f : null;
}

import { config, deepLink, STATE_DIR } from "./config.mjs";
import { acquireSingleInstance } from "./lib/single-instance.mjs";
import { listSessions, sendToSession, startSession } from "./lib/piweb.mjs";
import { createLogger } from "./lib/store.mjs";
import {
  bases as wanBases, endpoints as wanEndpoints, gatewayBlockedReason,
  preferredPublicBase, publishSnapshot, snapshot as wanSnapshot,
  startWan, stopWan,
} from "./lib/wan.mjs";

const log = createLogger("console.log");

const TOKEN = config.lan.consoleToken;
const COOKIE = "pi_console";

/**
 * 手机回报「已送达」用的地址。
 * 必须带上令牌 —— /api/ack 原本在鉴权后面，而 App 是从后台线程发的请求，
 * 既没有派发台的 cookie，也不应该把令牌另存一份。（现在 /api/ack 已经改成免令牌，
 * 但这里仍然带上，方便以后想收紧时直接改回鉴权后面。）
 */
function ackUrl() {
  const base = `http://${config.lan.host}:${config.lan.consolePort}/api/ack`;
  return TOKEN ? `${base}?t=${TOKEN}` : base;
}

/** 派发台/中转自己占的路径（网关上的其余路径归 pi-web） */
const CONSOLE_ROUTES = new Set([
  "/pi/publish", "/pi/stream", "/pi/messages", "/pi/ack", "/pi/ping", "/pi/endpoints",
  "/api/state", "/api/dispatch", "/api/send", "/api/ack", "/api/pilink-config",
  "/app", "/console", "/console/",
]);
const isConsoleRoute = (pathname) =>
  CONSOLE_ROUTES.has(pathname) || pathname.startsWith("/pi/") || pathname.startsWith("/apk");

function authorized(req, url) {
  if (!TOKEN) return true;
  if (url.searchParams.get("t") === TOKEN) return true;
  return (req.headers.cookie ?? "")
    .split(";")
    .some((part) => part.trim() === `${COOKIE}=${TOKEN}`);
}

// ══════════════════════════════════════════════════════════════════════════
// 「从哪个地址连进来的」→ 把通知里的链接改成那个地址
//
// 问题：看门狗发布时只能写死局域网地址（http://192.168.1.x:30141/?session=…）。
// 手机在外面时点通知会打不开 —— 那个地址只在家里有意义。
//
// 做法：投递时按【这次请求的来源】重写。于是
//   · 手机从局域网连的 → 链接就是局域网地址（和以前一模一样）
//   · 手机从隧道连的   → 链接就是 https://xxx.trycloudflare.com/…
//   · 手机从公网 IPv6 连的 → 链接就是 http://[240e:…]:8788/…
// 也就是「从哪来回哪去」，不需要服务端猜手机现在在哪。
// ══════════════════════════════════════════════════════════════════════════
const HOP_BY_HOP = new Set([
  "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
  "te", "trailer", "transfer-encoding", "upgrade", "host", "content-length",
]);

/** 隧道/反代会带 x-forwarded-proto；没有就是明文 http */
function requestOrigin(req) {
  const proto = String(req.headers["x-forwarded-proto"] ?? "http").split(",")[0].trim() || "http";
  const host = String(req.headers.host ?? `${config.lan.host}:${config.lan.consolePort}`);
  return `${proto}://${host.replace(/\/$/, "")}`;
}

/** 会被重写的「内网出身」前缀：局域网 IP / 127.0.0.1 + pi-web 或派发台端口 */
const LOCAL_ORIGINS = [
  `http://${config.lan.host}:${config.lan.piWebPort}`,
  `http://${config.lan.host}:${config.lan.consolePort}`,
  `http://127.0.0.1:${config.lan.piWebPort}`,
  `http://127.0.0.1:${config.lan.consolePort}`,
  `http://localhost:${config.lan.piWebPort}`,
  `http://localhost:${config.lan.consolePort}`,
];

function rewriteUrl(url, origin) {
  if (!url || !origin) return url;
  for (const local of LOCAL_ORIGINS) {
    if (url.startsWith(local)) return origin + url.slice(local.length);
  }
  return url;
}

/**
 * 投递给手机前的一道处理：重写链接 + 带上候选地址清单。
 * `bases` 是手机能连上这台机器的**所有**地址（局域网 / 隧道 / IPv6 / IPv4）。
 * 手机 App 把它存下来，某个地址失效就自己换下一个 —— 这是「不用服务器也能异地通知」的关键。
 */
function decorate(msg, origin) {
  return {
    ...msg,
    click: rewriteUrl(msg.click, origin),
    actions: (msg.actions ?? []).map((a) => ({ ...a, url: rewriteUrl(a.url, origin) })),
    bases: wanBases(),
  };
}

function json(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    "Content-Length": Buffer.byteLength(payload),
  });
  res.end(payload);
}

function html(res, status, body, extraHeaders = {}) {
  res.writeHead(status, {
    "Content-Type": "text/html; charset=utf-8",
    "Cache-Control": "no-store",
    ...extraHeaders,
  });
  res.end(body);
}

async function readJsonBody(req, limit = 256 * 1024) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > limit) throw new Error("请求体过大");
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

// ── 页面 ────────────────────────────────────────────────────────────────
function page({ running = [], recent = [], quick = [], banner = "" }) {
  const rows = (items, showResume) => items.map((s) => {
    const project = (s.cwd ?? "").split(/[\\/]/).filter(Boolean).at(-1) ?? "?";
    const text = String(s.firstMessage ?? "(无内容)").replace(/\s+/g, " ").slice(0, 70);
    const when = new Date(s.modified).toLocaleString("zh-CN", { hour12: false });
    return `<li class="s">
      <div class="meta"><b>${esc(project)}</b><span>${when}</span></div>
      <div class="txt">${esc(text)}</div>
      <div class="ops">
        <a class="b" href="${deepLink(s.id)}">打开</a>
        ${showResume ? `<button class="b g" data-resume="${esc(s.id)}">继续</button>` : ""}
      </div>
    </li>`;
  }).join("");

  const remote = wanEndpoints().filter((e) => e.kind !== "lan");

  return `<!doctype html><html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
${ICON_HEAD}
<title>pi 派发台</title>
<style>
:root{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;padding:16px 14px 60px;background:#14161a;color:#e8eaed;
     font:15px/1.5 -apple-system,"Noto Sans SC","Microsoft YaHei",sans-serif}
h1{font-size:17px;margin:0 0 4px}
h2{font-size:14px;margin:26px 0 10px;color:#9aa0a6;font-weight:600;
   text-transform:none;letter-spacing:.02em}
.hint{font-size:12px;color:#7d838a;margin:0 0 4px}
ul{list-style:none;padding:0;margin:0}
li.s{background:#1e2126;border:1px solid #2a2e34;border-radius:12px;
     padding:12px;margin-bottom:10px}
.meta{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.meta b{font-size:14px}
.meta span{font-size:11px;color:#7d838a;flex-shrink:0}
.txt{font-size:13px;color:#b6bcc4;margin:6px 0 10px;word-break:break-word}
.ops{display:flex;gap:8px;flex-wrap:wrap}
a.b,button.b{display:inline-block;padding:9px 16px;border-radius:9px;border:0;
  background:#2f3339;color:#e8eaed;font-size:13px;text-decoration:none;cursor:pointer}
a.b:active,button.b:active{background:#3a3f46}
button.b.g{background:#1c3b2a;color:#8ce0b0}
button.b.p{background:#1d3a5c;color:#9ecbf5}
textarea,input{width:100%;background:#1e2126;border:1px solid #2a2e34;border-radius:10px;
  color:#e8eaed;padding:11px;font-size:14px;font-family:inherit;margin-bottom:9px}
textarea{min-height:76px;resize:vertical}
.row{display:flex;gap:8px;flex-wrap:wrap}
.row button{flex:1;min-width:120px}
.banner{background:#3a2a1a;border:1px solid #5a4020;color:#f0c070;
  border-radius:10px;padding:10px 12px;font-size:13px;margin-bottom:14px}
.toast{position:fixed;left:14px;right:14px;bottom:16px;background:#1d3a5c;color:#cfe6fb;
  padding:12px 14px;border-radius:10px;font-size:13px;opacity:0;transition:opacity .2s;
  pointer-events:none;z-index:9}
.toast.on{opacity:1}
.empty{color:#6b7178;font-size:13px;padding:8px 2px}
</style></head><body>
<h1>pi 派发台</h1>
<p class="hint">${esc(config.lan.host)} · 电脑上的 pi-web 会话</p>
${remote.length ? `<p class="hint">出门在外可用：${remote.map((e) => `<code>${esc(e.base)}</code>${e.state === "ready" ? "✓" : ""}`).join(" · ")}</p>` : ""}
${banner ? `<div class="banner">${esc(banner)}</div>` : ""}

<h2>正在跑 (${running.length})</h2>
${running.length ? `<ul>${rows(running, false)}</ul>` : `<p class="empty">当前没有会话在运行</p>`}

<h2>派发新任务</h2>
<textarea id="msg" placeholder="要让它干什么？"></textarea>
<input id="cwd" value="${esc(config.defaultCwd)}" placeholder="工作目录">
<button class="b p" style="width:100%;padding:12px" id="go">派发</button>

<h2>快捷指令</h2>
<div class="row">${quick.map((q) => `<button class="b" data-quick="${esc(q.name)}">${esc(q.label)}</button>`).join("")}</div>

<h2>最近会话</h2>
${recent.length ? `<ul>${rows(recent, true)}</ul>` : `<p class="empty">（无）</p>`}

<div class="toast" id="toast"></div>
<script>
const $ = (s) => document.querySelector(s);
let timer;
function say(t, ok = true) {
  const el = $("#toast");
  el.textContent = t;
  el.style.background = ok ? "#1d3a5c" : "#4a1f1f";
  el.style.color = ok ? "#cfe6fb" : "#f5b0b0";
  el.classList.add("on");
  clearTimeout(timer);
  timer = setTimeout(() => el.classList.remove("on"), 4000);
}
async function post(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || j.error) throw new Error(j.error || ("HTTP " + r.status));
  return j;
}
$("#go").onclick = async () => {
  const message = $("#msg").value.trim();
  if (!message) return say("先写点什么", false);
  $("#go").disabled = true;
  try {
    const j = await post("/api/dispatch", { cwd: $("#cwd").value.trim(), message });
    say("已派发：" + (j.sessionId || "ok"));
    $("#msg").value = "";
    setTimeout(() => location.reload(), 900);
  } catch (e) { say("派发失败：" + e.message, false); }
  finally { $("#go").disabled = false; }
};
document.addEventListener("click", async (ev) => {
  const q = ev.target.closest("[data-quick]");
  if (q) {
    try {
      await post("/api/dispatch", { quick: q.dataset.quick });
      say("已派发：" + q.textContent);
      setTimeout(() => location.reload(), 900);
    } catch (e) { say("派发失败：" + e.message, false); }
    return;
  }
  const r = ev.target.closest("[data-resume]");
  if (r) {
    try {
      await post("/api/send", { sessionId: r.dataset.resume, message: "继续" });
      say("已让它继续跑");
      setTimeout(() => location.reload(), 900);
    } catch (e) { say("失败：" + e.message, false); }
  }
});
setInterval(() => {
  if (document.visibilityState === "visible") fetch("/api/state").then(r => r.json())
    .then(j => { if (!j.error) document.title = "pi 派发台" + (j.running.length ? " · " + j.running.length + " 在跑" : ""); })
    .catch(() => {});
}, 10000);
</script></body></html>`;
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}

// ── 数据 ────────────────────────────────────────────────────────────────
async function snapshot(limit = 20) {
  const data = await listSessions();
  const running = new Set(data.runningSessionIds ?? []);
  const sessions = (data.sessions ?? []).filter((s) => s.transient !== true);
  const byModified = (a, b) => Date.parse(b.modified) - Date.parse(a.modified);
  return {
    running: sessions.filter((s) => running.has(s.id)).sort(byModified),
    recent: sessions.filter((s) => !running.has(s.id)).sort(byModified).slice(0, limit),
  };
}

async function dispatch({ cwd, message, quick }) {
  let target = cwd?.trim() || config.defaultCwd;
  let prompt = message?.trim();
  if (quick) {
    const entry = config.quickCommands.find((q) => q.name === quick);
    if (!entry) throw new Error(`未知快捷指令: ${quick}`);
    prompt = entry.prompt;
    target = entry.cwd || target;
  }
  if (!prompt) throw new Error("message 不能为空");
  const result = await startSession({ cwd: target, message: prompt });
  return { sessionId: result?.sessionId ?? result?.id ?? null, raw: result };
}

// ── 服务器 ──────────────────────────────────────────────────────────────
/**
 * @param {boolean} gateway true = 这是 :8788 那个「统一出口」监听器。
 *   它除了派发台自己的路由，还把其余一切反代给 pi-web —— 这样一个公网地址
 *   （隧道 / IPv6 / 端口映射）就同时有了：/pi/* 中转 + 完整 pi-web UI。
 */
const handleRequest = async (req, res, gateway = false) => {
  const url = new URL(req.url ?? "/", `http://${req.headers.host ?? "localhost"}`);

  // 免令牌：APK 分发（手机浏览器直接下）
  if (req.method === "GET" && (url.pathname === "/apk" || url.pathname.startsWith("/apk/"))) {
    let name = basename(decodeURIComponent(url.pathname.slice("/apk/".length)));
    // 短地址支持：/apk 或 /apk/ 直接给目录里最新那个 .apk，
    // 省得在手机上敲一长串文件名。
    if (!name) name = newestApk();
    const file = join(APK_DIR, name || "_none_");
    if (!name || name.includes("..") || !file.startsWith(APK_DIR) || !existsSync(file)) {
      // 把可用文件列出来：旧版本号的链接失效是很常见的事（每次构建会删掉上一个包），
      // 让 404 自己说清楚，而不是让人去猜。
      return json(res, 404, {
        error: "没有这个文件",
        requested: name || "(空)",
        available: existsSync(APK_DIR)
          ? readdirSync(APK_DIR).filter((f) => f.toLowerCase().endsWith(".apk"))
          : [],
        hint: "用短地址 /apk 永远拿到最新那个",
      });
    }
    const stat = statSync(file);
    res.writeHead(200, {
      "Content-Type": "application/vnd.android.package-archive",
      "Content-Length": stat.size,
      "Content-Disposition": `attachment; filename="${name}"`,
      "Cache-Control": "no-store",
    });
    createReadStream(file).pipe(res);
    return;
  }

  // 免令牌：派发台自己的图标 / PWA 清单
  // （网关 :8788 上让给 pi-web —— 那边自己有 /favicon.ico 和 /manifest.webmanifest）
  if (req.method === "GET" && !gateway && WEB_FILES[url.pathname]) {
    const [name, type] = WEB_FILES[url.pathname];
    const file = join(WEB_DIR, name);
    if (!existsSync(file)) {
      return json(res, 404, { error: "图标还没生成", hint: "在 pi-android-link 下跑 node make-icons.mjs" });
    }
    const stat = statSync(file);
    res.writeHead(200, {
      "Content-Type": type,
      "Content-Length": stat.size,
      "Cache-Control": "public, max-age=86400",
    });
    createReadStream(file).pipe(res);
    return;
  }

  // 免令牌：自研订阅端 pilink 的安装引导页。
  // 核心是一条 pilink://setup 深链 —— 点一下就填好服务器+主题+回执地址，
  // 彻底避免「topic 手打错」那种「界面显示已连接、其实一条都收不到」的隐蔽故障。
  if (req.method === "GET" && url.pathname === "/app") {
    const server = `http://${config.lan.host}:${config.lan.consolePort}`;
    const ack = ackUrl();
    const apk = newestApk();
    // 一并把候选地址传给 App（它会存成“备用出口”）。出门前在家点一下这个深链就行，
    // 以后地址变了 App 也会自己从通知里学到新的。
    const basesParam = wanBases().map(encodeURIComponent).join(",");
    const deep = `pilink://setup?base=${encodeURIComponent(server)}`
      + `&token=${encodeURIComponent(TOKEN)}`
      + `&ack=${encodeURIComponent(ack)}`
      + `&bases=${encodeURIComponent(basesParam)}`;
    const remote = wanEndpoints().filter((e) => e.kind !== "lan");
    const blocked = gatewayBlockedReason();
    const remoteHtml = remote.length
      ? remote.map((e) => `<div class="row"><div class="k">${esc(e.label)}${e.state === "ready" ? " · 自检通" : e.state === "unverified" ? " · 自检不通" : ""}</div>
        <div class="v"><code>${esc(e.base)}</code></div>
        <div class="k" style="margin-top:4px">${esc(e.detail ?? "")}</div></div>`).join("")
      : `<div class="warn">还没有任何异地地址。启动时至少要有一条：装 cloudflared（免账号隧道）、给宽带要个 IPv6、或在路由器做端口映射。详见 README 的「异地通知」一节。</div>`;
    return html(res, 200, `<!doctype html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
${ICON_HEAD}
<title>装 Pi 通知</title><style>
:root{color-scheme:dark}*{box-sizing:border-box}
body{margin:0;padding:20px 16px 50px;background:#14161a;color:#e8eaed;
     font:15px/1.6 -apple-system,"Noto Sans SC","Microsoft YaHei",sans-serif}
h1{font-size:19px;margin:0 0 8px}
a.big{display:block;text-align:center;background:#1d3a5c;color:#cfe6fb;text-decoration:none;
      padding:18px;border-radius:12px;font-size:17px;font-weight:600;margin:14px 0}
a.big:active{background:#264a72}
a.dl{display:block;text-align:center;background:#1c3b2a;color:#8ce0b0;text-decoration:none;
      padding:16px;border-radius:12px;font-size:16px;font-weight:600;margin:10px 0}
code{background:#1e2126;padding:2px 6px;border-radius:5px;font-size:13px;word-break:break-all}
.row{background:#1e2126;border:1px solid #2a2e34;border-radius:10px;padding:12px;margin:10px 0}
.k{color:#7d838a;font-size:12px}.v{font-size:14px;word-break:break-all;margin-top:3px}
.warn{background:#3a2a1a;border:1px solid #5a4020;color:#f0c070;border-radius:10px;
      padding:12px;font-size:13px;margin:16px 0}
ol{padding-left:22px}li{margin-bottom:9px}
</style></head><body>
<h1>装 Pi 通知（自研订阅端）</h1>
<p style="color:#7d838a;font-size:13px;margin:0 0 14px">
派发台同时承担消息中转 —— 不需要任何第三方推送服务。</p>

${apk ? `<a class="dl" href="/apk">① 下载 APK（最新：${esc(apk)}）</a>` : `<div class="warn">apk 目录是空的</div>`}
<a class="big" href="${deep}">② 点这里一步配置并启动 →</a>

<div class="row"><div class="k">派发台（同时是消息中转）</div><div class="v"><code>${esc(server)}</code></div></div>
<div class="row"><div class="k">令牌</div><div class="v"><code>${esc(TOKEN)}</code></div></div>
<div class="row"><div class="k">送达回执</div><div class="v"><code>${esc(ack)}</code></div></div>

<h1 style="font-size:16px;margin-top:26px">异地（出门在外也能收）</h1>
<p style="color:#7d838a;font-size:13px">
不用买服务器、不用注册账号。App 手里有一份候选地址清单，谁通用谁；
地址变了（换宽带 IP、隧道换域名）下一条通知会自己把新地址带过去。
</p>
${remoteHtml}
${blocked ? `<div class="warn">统一出口（:${config.wan.gatewayPort}）没启用：${esc(blocked)}</div>` : ""}

<div class="warn">
第 ② 步没反应就手动填 <b>派发台地址</b> 和 <b>令牌</b>（令牌在 <code>~/.pi/android-link/local.json</code> 的 <code>lan.consoleToken</code>）。
</div>

<h1 style="font-size:16px;margin-top:26px">ColorOS（OPPO）必须放行三件事</h1>
<ol>
<li>设置 → 应用管理 → Pi 通知 → 耗电管理 → 允许<b>「允许后台活动 / 允许后台运行」</b></li>
<li>同页 → <b>自启动</b> → 允许</li>
<li>最近任务里把这个卡片<b>下拉加锁</b>（防手滑清理）</li>
</ol>
<p style="color:#7d838a;font-size:13px">不需要「闹钟和提醒」这类特殊权限 —— 重连靠常驻协程 + 非精确闹钟自愈。</p>
</body></html>`);
  }

  // 免令牌：手机送回来的「送达回执」（/api/ack 是旧名字，保留兼容）。
  // 为什么免令牌：回执是 App 后台线程发的，它没有派发台的 cookie、也不应该另存一份令牌；
  // 而且这个端点只往 acks.jsonl 追加一行，不读也不改任何状态，局域网内放行是合理的。
  // （仍然接受 ?t=<令牌>，方便以后想收紧就直接把它挪回鉴权后面。）
  if (req.method === "POST" && (url.pathname === "/api/ack" || url.pathname === "/pi/ack")) {
    try {
      const body = await readJsonBody(req);
      const t = Number(body.time ?? 0);
      const lag = t > 0 ? Date.now() - t * 1000 : null;
      appendFileSync(
        join(STATE_DIR, "acks.jsonl"),
        `${JSON.stringify({ ...body, receivedAt: new Date().toISOString() })}\n`,
      );
      log(`送达回执 ${body.id ?? "?"} topic=${body.topic ?? "-"}${lag === null ? "" : ` 服务端发出→手机收到 ${(lag / 1000).toFixed(1)}s`}`);
      return json(res, 200, { ok: true });
    } catch (error) {
      return json(res, 400, { error: error?.message ?? "回执体解析失败" });
    }
  }

  // 网关（:8788）上「不是我们自己的路径」→ 直接转给 pi-web，**不经过派发台令牌校验**。
  // 为什么：浏览器里打开的是一个完整 pi-web，它自己的 Basic 认证在代理里就完成了
  // （服务端注入），让手机上的浏览器再手输一次令牌是不能的。
  if (gateway && !isConsoleRoute(url.pathname)) {
    return await proxyPiWeb(req, res, url, requestOrigin(req));
  }

  if (!authorized(req, url)) {
    return html(res, 401,
      `<meta charset="utf-8"><body style="font:15px sans-serif;background:#14161a;color:#e8eaed;padding:24px">
       <h3>需要访问令牌</h3><p>在地址后面加上 <code>?t=&lt;令牌&gt;</code>。
       令牌在 <code>~/.pi/android-link/local.json</code> 的 <code>lan.consoleToken</code>。</p></body>`);
  }

  const setCookie = { "Set-Cookie": `${COOKIE}=${TOKEN}; Path=/; Max-Age=31536000; SameSite=Lax` };

  try {
    // GET
    if (req.method === "GET") {
      if (url.pathname === "/api/state") {
        const snap = await snapshot();
        return json(res, 200, { running: snap.running, recent: snap.recent, quick: config.quickCommands });
      }
      // 订阅端的配置事实源：手机 App 可以拉这个而不是靠手打
      if (url.pathname === "/api/pilink-config") {
        return json(res, 200, {
          base: `http://${config.lan.host}:${config.lan.consolePort}`,
          token: TOKEN,
          ackUrl: ackUrl(),
          stream: "/pi/stream",
          messages: "/pi/messages",
          apk: newestApk(),
          // 异地能力：候选地址清单（手机拿它做自动切换）
          bases: wanBases(),
          preferred: preferredPublicBase(),
        });
      }

      /**
       * 便宜的探测端点：手机拿它快速判断「这个地址还能不能连」。
       * 必须便宜 —— 候选地址可能有四五个，手机每换一个都要探一次。
       * 顺带把候选清单回传，所以「探测」和「同步地址」一步完成。
       */
      if (url.pathname === "/pi/ping") {
        return json(res, 200, {
          ok: true,
          time: Math.floor(Date.now() / 1000),
          origin: requestOrigin(req),
          bases: wanBases(),
          preferred: preferredPublicBase(),
          gateway: Boolean(gateway),
        });
      }

      /** 异地候选地址的完整视图（带 kind / 自检状态 / 说明），排障用 */
      if (url.pathname === "/pi/endpoints") {
        return json(res, 200, wanSnapshot());
      }

      // 推送流：一条 NDJSON 长连接。先补发 since 之后的，再实时推，每 ka 秒一条 keepalive。
      if (url.pathname === "/pi/stream") {
        const since = url.searchParams.get("since") ?? "none";
        const ka = Math.min(120, Math.max(5, Number(url.searchParams.get("ka")) || 20));
        const origin = requestOrigin(req);
        const catchUp = messagesSince(since);
        res.writeHead(200, {
          "Content-Type": "application/x-ndjson; charset=utf-8",
          "Cache-Control": "no-store",
          "X-Accel-Buffering": "no",
        });
        // open 帧带候选地址清单：手机每次建连都会把自己那份清单刷新一遍
        res.write(`${JSON.stringify({
          event: "open",
          time: Math.floor(Date.now() / 1000),
          origin,
          bases: wanBases(),
          preferred: preferredPublicBase(),
        })}\n`);
        for (const m of catchUp) res.write(`${JSON.stringify({ ...decorate(m, origin), event: "message" })}\n`);

        const entry = { res, ka, origin };
        streams.add(entry);
        let done = false;
        const cleanup = () => {
          if (done) return;
          done = true;
          clearInterval(timer);
          streams.delete(entry);
          log(`推送流断开，剩 ${streams.size} 条`);
          try {
            res.end();
          } catch {
            /* 已经断了 */
          }
        };
        let beat = 0;
        const timer = setInterval(() => {
          try {
            // 每 10 个心跳带一次候选清单：隧道换域名、手机换了网络之后都能学到
            const frame = beat % 10 === 0
              ? { event: "keepalive", time: Math.floor(Date.now() / 1000), bases: wanBases(), preferred: preferredPublicBase() }
              : { event: "keepalive", time: Math.floor(Date.now() / 1000) };
            beat += 1;
            res.write(`${JSON.stringify(frame)}\n`);
          } catch {
            cleanup();
          }
        }, ka * 1000);
        req.on("close", cleanup);
        req.on("error", cleanup);
        res.on("error", cleanup);
        try {
          req.socket?.setNoDelay(true);
        } catch {
          /* 无所谓 */
        }
        log(`推送流已连接（since=${since} keepalive=${ka}s 补发 ${catchUp.length} 条），当前 ${streams.size} 条`);
        return;
      }

      // 只拿缓存：轮询兜底 + 断线补收
      if (url.pathname === "/pi/messages") {
        const since = url.searchParams.get("since") ?? "none";
        const origin = requestOrigin(req);
        const list = messagesSince(since);
        return ndjson(res, 200, list.map((m) => `${JSON.stringify({ ...decorate(m, origin), event: "message" })}\n`));
      }
      if (url.pathname !== "/" && !(gateway && (url.pathname === "/console" || url.pathname === "/console/"))) {
        // 网关（:8788）上的其余一切 —— 包括 / —— 都交给 pi-web 反代，
        // 于是隧道地址直接就是一个完整的 pi-web，通知里的「打开会话」也能点。
        if (gateway) return await proxyPiWeb(req, res, url, requestOrigin(req));
        return html(res, 404, "<meta charset='utf-8'>404");
      }
      if (url.pathname !== "/") url.pathname = "/";

      let banner = "";
      const action = url.searchParams.get("do");
      const session = url.searchParams.get("session");
      if (action === "resume" && session) {
        try {
          await sendToSession(session, "继续");
          banner = `已让会话 ${session.slice(0, 8)} 继续跑。`;
        } catch (error) {
          banner = `接力失败：${error.message}`;
        }
      } else if (action) {
        try {
          const result = await dispatch({ quick: action });
          banner = `已派发快捷指令「${action}」：${result.sessionId ?? "ok"}`;
        } catch (error) {
          banner = `派发失败：${error.message}`;
        }
      }

      const snap = await snapshot();
      return html(res, 200, page({ ...snap, quick: config.quickCommands, banner }), setCookie);
    }

    // POST
    if (req.method === "POST") {
      const body = await readJsonBody(req);
      // 消息中转的入口：watchdog 把通知发到这里，由我们扇出给手机
      if (url.pathname === "/pi/publish") {
        const msg = publishMessage(body);
        log(`中转发布 ${msg.id} [p${msg.priority}] ${String(msg.title).slice(0, 30)}（推送流 ${streams.size} 条）`);
        return json(res, 200, { ok: true, id: msg.id, seq: msg.seq, time: msg.time, streams: streams.size });
      }
      if (url.pathname === "/api/dispatch") {
        const result = await dispatch(body);
        log(`派发：cwd=${body.cwd ?? config.defaultCwd} quick=${body.quick ?? "-"} → ${result.sessionId}`);
        return json(res, 200, result);
      }
      if (url.pathname === "/api/send") {
        if (!body.sessionId || !body.message) throw new Error("需要 sessionId 和 message");
        const result = await sendToSession(body.sessionId, body.message);
        log(`接力：${body.sessionId} ← ${String(body.message).slice(0, 40)}`);
        return json(res, 200, { ok: true, raw: result });
      }
      // 网关上的其余 /api/* 一律是 pi-web 自己的（/api/agent、/api/sessions…）
      if (gateway) return await proxyPiWeb(req, res, url, requestOrigin(req));
      return json(res, 404, { error: "未知路由" });
    }

    return json(res, 405, { error: "方法不允许" });
  } catch (error) {
    log(`控制台请求异常 ${req.method} ${url.pathname}: ${error?.message}`);
    if ((req.headers.accept ?? "").includes("text/html") && url.pathname === "/") {
      const snap = await snapshot().catch(() => ({ running: [], recent: [] }));
      return html(res, 200, page({ ...snap, quick: config.quickCommands, banner: `出错：${error.message}` }), setCookie);
    }
    return json(res, 500, { error: error?.message ?? String(error) });
  }
};

const server = createServer((req, res) => { handleRequest(req, res, false); });

// ── 统一出口（:8788）= 派发台 + pi-web 反代 ─────────────────────────────
// 为什么需要它：pi-web 自己能执行任意命令、深链也在它身上，而中转/派发台在 8787。
// 异地只应该暴露**一个**端口 —— 隧道、IPv6、端口映射全指向它，
// 手机在公网上拿到的就是一个地址：/pi/* 收通知 + / 打开完整 pi-web。
const gatewayBlocked = gatewayBlockedReason();
let gateway = null;
if (!gatewayBlocked) {
  gateway = createServer((req, res) => { handleRequest(req, res, true); });
  // 同理：长连接不能被 Node 的默认超时掉
  gateway.requestTimeout = 0;
  gateway.headersTimeout = 60_000;
  gateway.keepAliveTimeout = 65_000;
}

/**
 * 把请求转给 pi-web（127.0.0.1:30141）。
 *
 * 两个必须处理的细节（不处理就是 403 "Untrusted request"）：
 *  1. pi-web 的 middleware 只信任 Host 为 localhost / .localhost / IP 字面量
 *     / PI_WEB_ALLOWED_HOSTS 里的主机名（.next/server/middleware.js）。
 *     隧道域名（如 xxx.trycloudflare.com）不在里面 → 直接被当不可信请求拒掉。
 *     所以这里把 Host 改写成 pi-web 自己的本地 origin。
 *  2. 同一处还有 CSRF 检查：Origin 必须等于 `${proto}//${host}`。
 *     改写 Host 的同时把 Origin 一起改写，两个就仍然一致（同源）。
 * 认证方面：服务端直接带上 Basic（用户名固定 pi），所以公网上不用再登一次。
 */
async function proxyPiWeb(req, res, url, origin) {
  const target = new URL(url.pathname + url.search, config.piWeb.base);
  const headers = {};
  for (const [key, value] of Object.entries(req.headers)) {
    if (HOP_BY_HOP.has(key)) continue;
    headers[key] = value;
  }
  const local = new URL(config.piWeb.base);
  headers.host = local.host;
  headers.origin = local.origin;
  headers["x-forwarded-host"] = safeHost(origin);
  headers["x-forwarded-proto"] = origin.startsWith("https") ? "https" : "http";
  if (config.piWeb.password) {
    headers.authorization = `Basic ${Buffer.from(`pi:${config.piWeb.password}`).toString("base64")}`;
  }

  const hasBody = !["GET", "HEAD"].includes(req.method);
  try {
    const upstream = await fetch(target, {
      method: req.method,
      headers,
      body: hasBody ? Readable.toWeb(req) : undefined,
      duplex: hasBody ? "half" : undefined,
      redirect: "manual",
    });
    const out = {};
    upstream.headers.forEach((value, key) => {
      // fetch 已经解开了 gzip，且流式转发时长度会变 —— 这两个头必须丢掉
      if (HOP_BY_HOP.has(key) || key === "content-encoding") return;
      out[key] = value;
    });
    res.writeHead(upstream.status, out);
    if (!upstream.body) return res.end();
    await new Promise((resolve) => {
      const stream = Readable.fromWeb(upstream.body);
      stream.on("error", () => { try { res.end(); } catch { /* 已断 */ } resolve(); });
      res.on("close", () => { stream.destroy(); resolve(); });
      stream.pipe(res);
      res.on("finish", resolve);
    });
  } catch (error) {
    log(`pi-web 反代失败 ${req.method} ${url.pathname}: ${error?.message}`);
    if (!res.headersSent) json(res, 502, { error: `pi-web 反代失败：${error?.message}` });
    else res.end();
  }
}

function safeHost(origin) {
  try {
    return new URL(origin).host;
  } catch {
    return "";
  }
}

// Node 18+ 默认 requestTimeout=300s，会把我们这条长连接在 5 分钟处碋掉。必须关掉。
server.requestTimeout = 0;
server.headersTimeout = 60_000;
server.keepAliveTimeout = 65_000;

// ── 单实例互斥：绝不允许同时跑两个中转 ──────────────────────────────────
// 为什么不能用端口当互斥：Windows 上 Node 的 net 默认带 SO_REUSEADDR，
// **两个进程能绑同一个 :8787 且都成功** —— 那会变成两台中转各拿一半消息，
// 手机只看到一半（跟 pi-web 的"双实例脑裂"同一个坑）。
// 所以用锁文件（exclusive create + PID 存活校验），原因详见 lib/single-instance.mjs。
const instance = acquireSingleInstance(join(STATE_DIR, "console.lock"));
if (!instance.ok) {
  console.error(`[派发台] 已有实例在跑（pid=${instance.holderPid ?? "?"}），本次退出`);
  console.error("         如果要重启：先停掉旧进程，或删掉 " + join(STATE_DIR, "console.lock"));
  process.exit(0);
}
const releaseInstance = () => instance.release();
process.on("exit", () => {
  releaseInstance();
  stopWan();
});
for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(signal, () => {
    releaseInstance();
    stopWan();
    process.exit(0);
  });
}

server.listen(config.lan.consolePort, "0.0.0.0", () => {
  log(`派发台已监听 http://0.0.0.0:${config.lan.consolePort} 手机访问 http://${config.lan.host}:${config.lan.consolePort}/${TOKEN ? `?t=${TOKEN}` : ""}`);
});

if (gateway) {
  gateway.on("error", (error) => {
    log(`★★★ 统一出口 :${config.wan.gatewayPort} 起不来：${error.message}（异地通知会退回到局域网/已有地址）`);
    gateway = null;
  });
  gateway.listen(config.wan.gatewayPort, "0.0.0.0", () => {
    log(`统一出口已监听 http://0.0.0.0:${config.wan.gatewayPort}（派发台路由 + pi-web 反代，异地地址都指向它）`);
  });
} else {
  log(`不启统一出口 :${config.wan.gatewayPort} —— ${gatewayBlocked}`);
}

// 异地发现：公网 IPv4 / IPv6 / 隧道。周期性刷新，并把候选写进 endpoints.json。
startWan({
  onLog: (line) => {
    log(line);
    publishSnapshot();
  },
});
