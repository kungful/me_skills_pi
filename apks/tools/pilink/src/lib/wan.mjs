/**
 * 异地（公网）可达性 —— 不买服务器、不租服务器、不注册账号的前提下，
 * 让手机在在外面也能收到 pi 的通知。
 *
 * ── 为什么能不用服务器 ────────────────────────────────────────────────
 * 通知这条路本身是「电脑 → 手机」的单向推送，中间那台机器完全不必是我们自己的：
 * 只要**电脑自己有一个从公网能连进来的地址**就够了。四条路，按可靠度排：
 *
 *   1. 隧道（cloudflared Quick Tunnel）
 *      官方提供的「临时域名」通道，**不要账号、不要信用卡**，起一条命令就有
 *      https://<随机词>.trycloudflare.com。电脑在 NAT 后面照样能收。
 *      代价：进程重启域名就变。所以本模块会把新域名推给手机（见下面「手机怎么知道」）。
 *   2. 公网 IPv6 直连
 *      宽带基本都下发了 /64，手机也有 IPv6 → 电脑的全球单播地址可以直接被访问，
 *      **不需要端口映射、不需要第三方**。缺点：光猫/路由器得放行入站（多数默认放行 IPv6）。
 *   3. 公网 IPv4 + 端口映射
 *      最老实的办法。前提是运营商给你的是真公网 IP（不是 CGNAT 大内网），
 *      并且你在路由器上把 gatewayPort 转到这台机器。
 *   4. 手填地址（extraBases）
 *      已经有反向代理/别的穿透时用。
 *
 * ── 手机怎么知道新地址（这是唯一真正的难点）────────────────────────────
 * 服务端不可能主动联系一部在外面的手机（那就变成要账号的推送服务了）。所以做法是
 * **让手机自己手里有一份候选清单，谁通用谁**：
 *   · 每条推送流建立时（event=open）和每 10 条 keepalive 里都带 `bases`（候选地址清单）
 *   · 轮询兜底 /pi/messages 回来的每条消息里也带 `bases`
 *   · 手机 App 把清单存下来，失败一个就换下一个（lib 见 App 侧 EndpointManager.kt）
 * 于是「电脑重启、隧道换了域名」这件事，只要手机还能连上其中任何一个地址，
 * 下一条通知就会把新域名带过去；一个都连不上时（比如隧道和 IPv6 同时换了），
 * 退回到还有映射的 IPv4 或上次学到的地址。
 *
 * ── 为什么地址是「候选」而不是「一个」────────────────────────────────
 * 本机没法从公网给自己发包验证（除非绕出去再绕回来，NAT 回环并不总是支持），
 * 所以「这个地址手机能不能用」最终由手机探测决定。服务端只负责：
 *   发现候选 → 自检一遍（能自检通就标 ready，通不了标 unknown）→ 推给手机。
 */
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { networkInterfaces } from "node:os";
import { join } from "node:path";
import { config, gatewayLocalBase, lanBase, STATE_DIR } from "../config.mjs";

/** 出口种类。手机端按这个排优先级，别的工具也靠它认人。 */
export const KIND = {
  LAN: "lan",       // 局域网（手机在家时用，端口是派发台自己的）
  TUNNEL: "tunnel", // 免账号隧道（trycloudflare 之类）
  IPV6: "ipv6",     // 公网 IPv6 直连
  IPV4: "ipv4",     // 公网 IPv4 + 端口映射
  CUSTOM: "custom", // 手填
};

const IPV4_RE = /\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b/;
const TUNNEL_URL_RE = /https?:\/\/[^\s"'<>`)\]]+/i;

/** 运行时状态（只读快照由 snapshot() 给出） */
const state = {
  publicIPv4: null,
  publicIPv4At: 0,
  /** 100.64.0.0/10 = 运营商 CGNAT，这种 IP 端口映射了也没用，必须说清楚 */
  cgnat: false,
  ipv6: null,
  tunnel: { mode: "off", status: "off", url: null, error: null, restarts: 0, since: 0, probed: null },
  /** base -> 自检结果：true=自检通，false=自检不通，null=还没自检 */
  probes: new Map(),
  lastError: null,
};

let timers = [];
let child = null;
let tunnelStopRequested = false;
let logSink = () => {};

function say(line) {
  const stamp = new Date().toISOString();
  const text = `[公网] ${line}`;
  state.lastError = null;
  try {
    logSink(text);
  } catch {
    /* 日志坏了也不能影响发现 */
  }
  if (process.env.PI_WAN_VERBOSE !== "0") console.log(text, stamp.slice(11, 19));
}

// ── 公网 IPv4 ───────────────────────────────────────────────────────────
function isPrivateV4(ip) {
  const m = IPV4_RE.exec(ip);
  if (!m) return true;
  const [a, b] = [Number(m[1]), Number(m[2])];
  if (a === 10 || a === 127 || a === 0) return true;
  if (a === 192 && b === 168) return true;
  if (a === 172 && b >= 16 && b <= 31) return true;
  if (a === 169 && b === 254) return true;
  return false;
}

/** 100.64/10：运营商级 NAT。这段 IP 端口映射了也出不去，只能靠隧道或 IPv6。 */
function isCgnatV4(ip) {
  const m = IPV4_RE.exec(ip);
  if (!m) return false;
  return Number(m[1]) === 100 && Number(m[2]) >= 64 && Number(m[2]) <= 127;
}

/**
 * 并发问几个「我是谁」服务，谁先给出合法 IPv4 就用谁。
 * 全部失败时保留上一次的结果（宁可给旧地址也不要给空）。
 */
export async function fetchPublicIPv4(services = config.wan.ipServices) {
  const list = (Array.isArray(services) ? services : []).filter(Boolean);
  if (!list.length) return null;
  const attempt = async (url) => {
    const response = await fetch(url, {
      headers: { accept: "text/plain, application/json" },
      signal: AbortSignal.timeout(5_000),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const text = (await response.text()).slice(0, 400);
    const m = IPV4_RE.exec(text);
    if (!m) throw new Error("响应里没有 IPv4");
    const ip = m[0];
    if (isPrivateV4(ip)) throw new Error(`只拿到内网地址 ${ip}`);
    return ip;
  };
  const results = await Promise.allSettled(list.map(attempt));
  const ip = results.find((r) => r.status === "fulfilled")?.value ?? null;
  const failures = results.filter((r) => r.status === "rejected");
  if (!ip && failures.length) {
    const why = failures.map((f) => f.reason?.message ?? "?").slice(0, 2).join(" / ");
    state.lastError = `公网 IPv4 查询失败：${why}`;
  }
  return ip;
}

// ── 公网 IPv6 ───────────────────────────────────────────────────────────
/**
 * 从网卡里挑一个「全球单播」IPv6。
 * 排除：fe80::/10（链路本地，需要 %网卡 后缀，公网用不上）、
 *       fc00::/7（ULA，内网）、::1、IPv4 映射的 ::ffff:x.x.x.x。
 */
export function globalIPv6() {
  const out = [];
  for (const [name, infos] of Object.entries(networkInterfaces())) {
    for (const info of infos ?? []) {
      if (info.family !== "IPv6" && info.family !== 6) continue;
      const addr = String(info.address ?? "").split("%")[0].toLowerCase();
      if (!addr || addr === "::1") continue;
      if (addr.startsWith("fe80") || addr.startsWith("fc") || addr.startsWith("fd")) continue;
      if (addr.startsWith("::ffff")) continue;
      out.push({ name, addr, internal: Boolean(info.internal) });
    }
  }
  // 有对外 IPv4 的网卡上的 IPv6 更可能真的是「宽带下发的那个」，排前面
  out.sort((a, b) => Number(a.internal) - Number(b.internal));
  return out[0] ?? null;
}

// ── 候选清单 ────────────────────────────────────────────────────────────
function probeStateOf(base) {
  const v = state.probes.get(base);
  return v === undefined ? null : v;
}

/**
 * 所有候选地址。给 /pi/endpoints、/app 页面、wan-report.mjs 用。
 * state: ready（自检通）/ unknown（还没验）/ unverified（自检不通但仍发布，手机自己会探）
 */
export function endpoints() {
  const port = config.wan.gatewayPort;
  const list = [
    { base: lanBase(), kind: KIND.LAN, label: "局域网", detail: "手机连同一个 WiFi 时用", state: "ready" },
  ];

  // 安全阀：pi-web 无密码时公网入口根本不开（统一出口没监听）。
  // 这时候再发布公网地址就是发布一堆「一定连不上」的候选 —— 手机会白试、白等。
  // 所以直接只留局域网那一条，并在详情里说清楚为什么没有异地地址。
  const blocked = gatewayBlockedReason();
  if (blocked) {
    list[0].detail = `只有局域网可用：${blocked}`;
    return list;
  }

  const tunnel = state.tunnel;
  if (tunnel.url) {
    const probed = probeStateOf(tunnel.url);
    list.push({
      base: tunnel.url,
      kind: KIND.TUNNEL,
      label: "免账号隧道",
      detail: tunnel.status === "running" ? `cloudflared · 第 ${tunnel.restarts + 1} 次拉起` : String(tunnel.error ?? tunnel.status),
      state: probed === true ? "ready" : probed === false ? "unverified" : "unknown",
    });
  }

  if (state.ipv6) {
    const base = `http://[${state.ipv6.addr}]:${port}`;
    const probed = probeStateOf(base);
    list.push({
      base,
      kind: KIND.IPV6,
      label: "公网 IPv6 直连",
      detail: `${state.ipv6.name} · 不需要端口映射，${state.ipv6.internal ? "⚠ 网卡被标成 internal" : "运营商下发的全球地址"}`,
      state: probed === true ? "ready" : probed === false ? "unverified" : "unknown",
    });
  }

  if (state.publicIPv4) {
    const base = `http://${state.publicIPv4}:${port}`;
    const probed = probeStateOf(base);
    list.push({
      base,
      kind: KIND.IPV4,
      label: "公网 IPv4（需端口映射）",
      detail: state.cgnat
        ? "⚠ 这是运营商 CGNAT 大内网地址，端口映射出不去 —— 只能靠隧道或 IPv6"
        : `需要在路由器把 TCP ${port} 转到本机`,
      state: probed === true ? "ready" : probed === false ? "unverified" : "unknown",
    });
  }

  for (const base of config.wan.extraBases ?? []) {
    const clean = String(base).trim().replace(/\/$/, "");
    if (!/^https?:\/\//i.test(clean)) continue;
    if (list.some((e) => e.base === clean)) continue;
    const probed = probeStateOf(clean);
    list.push({
      base: clean,
      kind: KIND.CUSTOM,
      label: "手填地址",
      detail: "来自 local.json 的 wan.extraBases",
      state: probed === true ? "ready" : probed === false ? "unverified" : "unknown",
    });
  }
  return list;
}

/** 只给手机用的候选清单（纯地址数组，局域网永远排第一） */
export function bases() {
  return endpoints().map((e) => e.base);
}

/**
 * 「最该给手机用」的公网地址。
 * 顺序 = 可靠度：隧道（不怕 NAT、不怕端口映射）→ IPv6（不用第三方）→ IPv4（要映射）→ 手填。
 * 每一档里先取自检通过的；都没有就退而取第一个存在的（手机自己会探，探不通会自己换）。
 */
export function preferredPublicBase() {
  const order = [KIND.TUNNEL, KIND.IPV6, KIND.IPV4, KIND.CUSTOM];
  const list = endpoints().filter((e) => e.kind !== KIND.LAN);
  for (const kind of order) {
    const same = list.filter((e) => e.kind === kind);
    const ready = same.find((e) => e.state === "ready");
    if (ready) return ready.base;
  }
  return list[0]?.base ?? null;
}

/** 隧道/网关能不能开：pi-web 无密码时绝不开公网入口 */
export function gatewayBlockedReason() {
  if (!config.wan.enabled) return "wan.enabled=false（已关闭）";
  if (!config.piWeb.password && !config.wan.gatewayWithoutPassword) {
    return "pi-web 没有密码（local.json 的 piWeb.password 为空）—— 公网入口能执行任意命令，拒绝启动";
  }
  return null;
}

export function snapshot() {
  return {
    enabled: config.wan.enabled,
    gatewayPort: config.wan.gatewayPort,
    gatewayBlocked: gatewayBlockedReason(),
    publicIPv4: state.publicIPv4,
    publicIPv4At: state.publicIPv4At,
    cgnat: state.cgnat,
    ipv6: state.ipv6,
    tunnel: { ...state.tunnel },
    endpoints: endpoints(),
    preferred: preferredPublicBase(),
    lastError: state.lastError,
  };
}

// ── 自检 ────────────────────────────────────────────────────────────────
/**
 * 从本机绕出去再绕回来探一下这个地址。
 * 注意：这一步**只能算参考**。NAT 回环（hairpin）不是所有路由器都支持，
 * 自检失败≠手机一定连不上，所以失败时只标 unverified，照样发布给手机。
 */
export async function probeBase(base, { token = config.lan.consoleToken, timeoutMs = config.wan.probeTimeoutMs } = {}) {
  const url = `${base}/pi/ping${token ? `?t=${encodeURIComponent(token)}` : ""}`;
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.probes.set(base, true);
    say(`自检通过 ${base}`);
    return true;
  } catch (error) {
    state.probes.set(base, false);
    say(`自检不通 ${base}：${error?.message ?? error}（不发布为 ready，手机会自己探）`);
    return false;
  }
}

// ── 隧道 ────────────────────────────────────────────────────────────────
function which(cmd) {
  try {
    const r = spawnSync(process.platform === "win32" ? "where" : "which", [cmd], { encoding: "utf8" });
    const first = (r.stdout ?? "").split(/\r?\n/).map((s) => s.trim()).filter(Boolean)[0];
    return first ?? null;
  } catch {
    return null;
  }
}

function findCloudflared() {
  if (config.wan.cloudflaredPath) return config.wan.cloudflaredPath;
  return which("cloudflared") ?? which("cloudflared.exe");
}

function tunnelSpec() {
  const mode = String(config.wan.tunnel ?? "auto").toLowerCase();
  if (mode === "off" || mode === "none" || mode === "false") return null;

  const blocked = gatewayBlockedReason();
  if (blocked) {
    state.tunnel = { ...state.tunnel, mode, status: "blocked", error: blocked, url: null };
    say(`不启动隧道：${blocked}`);
    return null;
  }

  if (config.wan.tunnelCommand) {
    const local = gatewayLocalBase();
    const cmd = String(config.wan.tunnelCommand)
      .replaceAll("{local}", local)
      .replaceAll("{port}", String(config.wan.gatewayPort));
    return { mode: "custom", bin: null, args: [], command: cmd };
  }

  if (mode === "auto" || mode === "cloudflared") {
    const bin = findCloudflared();
    if (!bin) {
      state.tunnel = {
        ...state.tunnel,
        mode,
        status: "absent",
        error: "PATH 里没有 cloudflared —— 隧道这条路先不可用（IPv6 / 端口映射 / 手填地址仍然可用）",
        url: null,
      };
      say(state.tunnel.error);
      return null;
    }
    return {
      mode: "cloudflared",
      bin,
      args: ["tunnel", "--no-autoupdate", "--url", gatewayLocalBase()],
    };
  }
  return null;
}

function stopChild() {
  const proc = child;
  child = null;
  if (!proc) return;
  try {
    if (process.platform === "win32") spawnSync("taskkill", ["/PID", String(proc.pid), "/T", "/F"], { encoding: "utf8" });
    else proc.kill("SIGTERM");
  } catch {
    /* 已经没了 */
  }
}

function launchTunnel() {
  const spec = tunnelSpec();
  if (!spec) return;
  const started = Date.now();
  state.tunnel = { ...state.tunnel, mode: spec.mode, status: "starting", error: null, url: null, since: started };
  say(`启动隧道（${spec.mode}）→ ${gatewayLocalBase()}`);

  const consume = (chunk) => {
    for (const line of String(chunk).split(/\r?\n/)) {
      const hit = TUNNEL_URL_RE.exec(line);
      if (!hit) continue;
      const url = hit[0].replace(/[.,]$/, "");
      if (!/^https?:/i.test(url)) continue;
      if (state.tunnel.url === url) continue;
      state.tunnel = { ...state.tunnel, url, status: "running", error: null };
      say(`隧道就绪：${url}`);
      // 自检要等隧道热一下，所以延后一点再探
      setTimeout(() => { if (state.tunnel.url === url) probeBase(url); }, 3_000).unref?.();
    }
  };

  let proc;
  try {
    proc = spec.command
      ? spawn(spec.command, { shell: true, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] })
      : spawn(spec.bin, spec.args, { windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
  } catch (error) {
    state.tunnel = { ...state.tunnel, status: "error", error: String(error?.message ?? error) };
    say(`隧道起不来：${state.tunnel.error}`);
    return;
  }
  child = proc;
  proc.stdout?.on("data", consume);
  proc.stderr?.on("data", consume);
  proc.on("error", (error) => {
    state.tunnel = { ...state.tunnel, status: "error", error: String(error?.message ?? error) };
    say(`隧道进程报错：${state.tunnel.error}`);
  });
  proc.on("exit", (code, signal) => {
    child = null;
    if (tunnelStopRequested) return;
    state.tunnel = {
      ...state.tunnel,
      status: "exited",
      error: `隧道进程退出了（code=${code} signal=${signal ?? "-"}）`,
      url: null,
    };
    const backoff = Math.min(60_000, 5_000 * 2 ** Math.min(state.tunnel.restarts, 4));
    state.tunnel.restarts += 1;
    say(`${state.tunnel.error} → ${Math.round(backoff / 1000)}s 后重拉（第 ${state.tunnel.restarts} 次）`);
    const timer = setTimeout(launchTunnel, backoff);
    timer.unref?.();
    timers.push(timer);
  });
}

// ── 启动 / 停止 ─────────────────────────────────────────────────────────
/**
 * 开始周期性发现。onLog 用来把发现过程写进 console.log。
 * 幂等：重复调用只会重新绑定日志出口，不会起第二套定时器。
 */
export function startWan({ onLog } = {}) {
  if (typeof onLog === "function") logSink = onLog;
  if (timers.length) return;
  if (!config.wan.enabled) {
    say("异地通知已关闭（local.json 的 wan.enabled=false）");
    return;
  }

  const refreshIp = async () => {
    state.ipv6 = globalIPv6();
    const ip = await fetchPublicIPv4();
    if (ip) {
      const changed = ip !== state.publicIPv4;
      state.publicIPv4 = ip;
      state.publicIPv4At = Date.now();
      state.cgnat = isCgnatV4(ip);
      say(changed ? `公网 IPv4：${ip}${state.cgnat ? "（CGNAT 大内网，端口映射无效）" : ""}` : `公网 IPv4 未变：${ip}`);
      if (!state.cgnat) probeBase(`http://${ip}:${config.wan.gatewayPort}`).catch(() => {});
    } else if (!state.publicIPv4) {
      say(state.lastError ?? "公网 IPv4 没查到（离线？被墙？）—— 隧道和 IPv6 仍然可用");
    }
    if (state.ipv6) probeBase(`http://[${state.ipv6.addr}]:${config.wan.gatewayPort}`).catch(() => {});
    publishSnapshot();
  };

  refreshIp().catch(() => {});
  const ipTimer = setInterval(() => { refreshIp().catch(() => {}); }, Math.max(60_000, config.wan.ipRefreshMs));
  ipTimer.unref?.();
  timers.push(ipTimer);

  launchTunnel();
  publishSnapshot();
}

export function stopWan() {
  tunnelStopRequested = true;
  for (const t of timers) clearInterval(t);
  timers = [];
  stopChild();
}

/** 把当前候选写到磁盘：给 wan-report.mjs / 排障时看（不必先知道端口） */
export function publishSnapshot() {
  try {
    mkdirSync(STATE_DIR, { recursive: true });
    writeFileSync(join(STATE_DIR, "endpoints.json"), `${JSON.stringify(snapshot(), null, 2)}\n`, "utf8");
  } catch (error) {
    say(`候选清单落盘失败（不影响功能）：${error?.message ?? error}`);
  }
}
