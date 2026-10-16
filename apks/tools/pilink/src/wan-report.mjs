/**
 * 异地通知体检 —— 把「手机在外面能不能收到」这件事变成一份可读的报告。
 *
 * 背景：这套东西不租服务器、不买 VPS，公网入口只有四条路（见 lib/wan.mjs 顶部）：
 *   ① 免账号隧道（cloudflared Quick Tunnel）② 公网 IPv6 直连
 *   ③ 公网 IPv4 + 端口映射  ④ 手填地址
 * 到底哪条能用、为什么不能用，这个脚本一次说清。
 *
 * 用法：
 *   node wan-report.mjs            # 报告（优先读派发台写下的 endpoints.json）
 *   node wan-report.mjs --probe    # 逐个自检候选地址（从本机绕出去绕回来）
 *   node wan-report.mjs --json     # 机器可读
 *   node wan-report.mjs --urls     # 只打印地址，一行一个（方便粘到手机上）
 */
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { config, STATE_DIR } from "./config.mjs";
import { endpoints, fetchPublicIPv4, globalIPv6, gatewayBlockedReason, preferredPublicBase, probeBase } from "./lib/wan.mjs";

const argv = new Set(process.argv.slice(2));
const JSON_OUT = argv.has("--json");
const URLS_OUT = argv.has("--urls");
const DO_PROBE = argv.has("--probe");
const SNAPSHOT_FILE = join(STATE_DIR, "endpoints.json");

/** 派发台在跑的话直接问它（拿到的是活的状态，包括隧道当前域名） */
async function fromConsole() {
  const base = `http://127.0.0.1:${config.lan.consolePort}`;
  const token = config.lan.consoleToken;
  try {
    const response = await fetch(`${base}/pi/endpoints?t=${encodeURIComponent(token)}`, {
      signal: AbortSignal.timeout(3_000),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

function fromDisk() {
  if (!existsSync(SNAPSHOT_FILE)) return null;
  try {
    return JSON.parse(readFileSync(SNAPSHOT_FILE, "utf8").replace(/^\uFEFF/, ""));
  } catch {
    return null;
  }
}

let live = await fromConsole();
let data = live ?? fromDisk();
let source = live ? "派发台（:8787 /pi/endpoints）" : data ? "endpoints.json（派发台当前没跑）" : "";
if (!data) {
  // 派发台没跑：自己做一次性发现（不起隧道、不改任何东西）
  const publicIPv4 = await fetchPublicIPv4();
  const ipv6 = globalIPv6();
  const port = config.wan.gatewayPort;
  const list = [{ base: `http://${config.lan.host}:${config.lan.consolePort}`, kind: "lan", label: "局域网", detail: "", state: "ready" }];
  if (publicIPv4) {
    list.push({ base: `http://${publicIPv4}:${port}`, kind: "ipv4", label: "公网 IPv4（需端口映射）", detail: `需要在路由器把 TCP ${port} 转到本机`, state: "unknown" });
  }
  if (ipv6) {
    list.push({ base: `http://[${ipv6.addr}]:${port}`, kind: "ipv6", label: "公网 IPv6 直连", detail: `${ipv6.name} · 不需要端口映射`, state: "unknown" });
  }
  for (const base of config.wan.extraBases ?? []) {
    if (/^https?:\/\//i.test(base)) list.push({ base: String(base).replace(/\/$/, ""), kind: "custom", label: "手填地址", detail: "", state: "unknown" });
  }
  const remote = list.filter((e) => e.kind !== "lan");
  data = {
    enabled: config.wan.enabled,
    gatewayPort: port,
    gatewayBlocked: gatewayBlockedReason(),
    publicIPv4,
    cgnat: false,
    ipv6,
    tunnel: { status: "派发台没在跑，隧道没在运行", url: null },
    endpoints: list,
    preferred: remote[0]?.base ?? null,
  };
  source = "一次性发现（派发台未运行）";
}

if (DO_PROBE && !URLS_OUT) {
  for (const endpoint of data.endpoints ?? []) {
    if (endpoint.kind === "lan") continue;
    process.stdout.write(`自检 ${endpoint.base} … `);
    const ok = await probeBase(endpoint.base);
    process.stdout.write(ok ? "通\n" : "不通\n");
  }
  const fresh = endpoints();
  const remote = fresh.filter((e) => e.kind !== "lan");
  data = { ...data, endpoints: fresh, preferred: preferredPublicBase() ?? remote[0]?.base ?? null };
}

if (URLS_OUT) {
  for (const endpoint of data.endpoints ?? []) console.log(endpoint.base);
  process.exit(0);
}

if (JSON_OUT) {
  console.log(JSON.stringify(data, null, 2));
  process.exit(0);
}

const line = "─".repeat(66);
console.log(line);
console.log("  pi 异地通知体检");
console.log(line);
console.log(`  数据来源      ${source}`);
console.log(`  统一出口端口  ${data.gatewayPort}（派发台路由 + pi-web 反代）`);
console.log(`  网关状态      ${data.gatewayBlocked ? `未启用 —— ${data.gatewayBlocked}` : "已启用"}`);
console.log(`  公网 IPv4     ${data.publicIPv4 ?? "没查到（离线/被墙？）"}${data.cgnat ? "  ⚠ CGNAT 大内网" : ""}`);
console.log(`  公网 IPv6     ${data.ipv6 ? `${data.ipv6.addr}（${data.ipv6.name}）` : "没有（网卡上没有全球单播 IPv6）"}`);
console.log(`  隧道          ${data.tunnel?.status ?? "-"}${data.tunnel?.url ? ` → ${data.tunnel.url}` : ""}${data.tunnel?.error ? `（${data.tunnel.error}）` : ""}`);
console.log(`  首选公网地址  ${data.preferred ?? "（无 —— 手机只能在家里收）"}`);
console.log(line);
console.log("  候选地址（手机按这个顺序自己试）：");
for (const endpoint of data.endpoints ?? []) {
  const mark = { ready: "✓自检通", unknown: " 未自检", unverified: "✗自检不通" }[endpoint.state] ?? endpoint.state;
  console.log(`    [${endpoint.kind.padEnd(6)}] ${mark}  ${endpoint.base}`);
  if (endpoint.detail) console.log(`             ${endpoint.detail}`);
}
console.log(line);

const tips = [];
if (data.gatewayBlocked) {
  tips.push(`· 先解决这个：${data.gatewayBlocked}`);
  tips.push("· 修法：setup.ps1 -Force 重新生成（会写一个随机密码）→ 双击 run-pi-web.bat 重启 pi-web → 再跑一次本脚本");
} else {
  if (!data.publicIPv4) tips.push("· 查不到公网 IPv4：先确认这台机器能上外网（fetch 一下 ipify 之类）。");
  if (data.cgnat) tips.push("· 公网 IPv4 是 100.64/10（运营商 CGNAT）：端口映射这条路走不通，只能靠隧道或 IPv6。");
  if (!data.ipv6) tips.push("· 没有公网 IPv6：打运营商电话要，或看光猫/路由器有没有下发 IPv6 前缀。");
  if (data.tunnel?.status === "absent") {
    tips.push("· 想用免账号隧道：装 cloudflared（https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/），" +
      "装完重启 run-link.bat 即可，不用注册账号。");
  }
  if (data.tunnel?.status === "blocked") tips.push("· 隧道被安全阀拦住：pi-web 无密码时不允许开公网入口。");
  if (data.publicIPv4 && !data.cgnat) tips.push(`· 想用公网 IPv4：在路由器把 TCP ${data.gatewayPort} 转发到 ${config.lan.host}，并放行 Windows 防火墙。`);
  if (data.ipv6) tips.push(`· 想用 IPv6：路由器/光猫放行入站 TCP ${data.gatewayPort}（多数默认放行），手机也要有 IPv6。`);
  if (!tips.length) tips.push("· 一切就绪：手机 App 会自动在候选地址之间切换，出门也能收。");
}
console.log(tips.map((t) => `  ${t}`).join("\n"));
console.log(line);
console.log("  手机上：设置 → 当前状态 可以看到「出口地址」和候选清单。");
console.log(line);
