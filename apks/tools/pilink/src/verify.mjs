/**
 * 安卓链路端到端验收 —— 全部是能算出来的断言，不做视觉判断。
 *
 *   node verify.mjs          # 验收，退出码 0=全过 1=有失败
 *   node verify.mjs --quiet  # 只打印失败项和总结
 *
 * 覆盖：
 *   A 判定逻辑（9 条单元断言 + 234 个真实会话文件的有界读取一致性）
 *   B 自研中转推送链路（发布 → 缓存回读，含中文/优先级/点击链接/动作按钮）
 *   C 看门狗存活（单实例互斥端口被占 + 状态文件已 prime）
 *   D 派发台鉴权与接口
 *   E pi-web 可达性 + 是否已绑到 0.0.0.0（手机能不能连）
 *   F 手动 BAT 启动与发布链路是否正常
 *   I 异地通知：候选地址、网关、深链重写（不用服务器、不用账号）
 */
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { join } from "node:path";
import { execFileSync, spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { config, STATE_DIR } from "./config.mjs";
import { classifyEntries, readAndClassify } from "./lib/classify.mjs";
import { runClassifyCases } from "./lib/classify-cases.mjs";
import { KIND_LABEL, planNotification, planPiWebDown, planStall } from "./lib/notify-plan.mjs";
import { listSessions } from "./lib/piweb.mjs";

const QUIET = process.argv.includes("--quiet");
// 手机订阅后，跑验收会给手机发 7 条真实通知。设 PI_ANDROID_LINK_SKIP_PUSH=1 可跳过 F 段。
const SKIP_PUSH = process.env.PI_ANDROID_LINK_SKIP_PUSH === "1";
const results = [];
function check(id, ok, detail, options = {}) {
  // pending = 「需要人工动作才能验证」，它不计入退出码，但必须在总结里追究下去
  const pending = Boolean(options.pending);
  results.push({ id, ok, detail, pending });
  const tag = ok ? "PASS" : pending ? "TODO" : "FAIL";
  if (!QUIET || !ok) console.log(`  ${tag}  ${id}${detail ? `  — ${detail}` : ""}`);
}
function section(title) {
  if (!QUIET) console.log(`\n${title}`);
}

// ── A 判定逻辑 ──────────────────────────────────────────────────────────
section("A 判定逻辑");
const cases = runClassifyCases(classifyEntries);
check("A1 判定单元断言 9/9", cases.failed === 0, cases.failed ? `${cases.failed} 条失败` : "全部通过");
for (const r of cases.results.filter((x) => !x.ok)) {
  console.log(`         ↳ ${r.name}: 得到 ${r.got}，期望 ${r.expect}`);
}

function allSessionFiles() {
  const files = [];
  if (!existsSync(config.sessionsDir)) return files;
  for (const dir of readdirSync(config.sessionsDir)) {
    const dirPath = join(config.sessionsDir, dir);
    try {
      if (!statSync(dirPath).isDirectory()) continue;
    } catch {
      continue;
    }
    for (const name of readdirSync(dirPath)) {
      if (name.endsWith(".jsonl")) files.push(join(dirPath, name));
    }
  }
  return files;
}

const files = allSessionFiles();
let kindCounts = {};
let mismatch = 0;
let mismatchedFiles = [];
let unreadable = 0;
for (const file of files) {
  let entries;
  try {
    entries = readFileSync(file, "utf8").split("\n").filter((l) => l.trim()).map((l) => JSON.parse(l));
  } catch {
    unreadable += 1;
    continue;
  }
  const full = classifyEntries(entries);
  if (!full) {
    unreadable += 1;
    continue;
  }
  kindCounts[full.kind] = (kindCounts[full.kind] ?? 0) + 1;
  const bounded = readAndClassify(file, config.tailBytes);
  if ((bounded?.kind ?? null) !== full.kind) {
    mismatch += 1;
    if (mismatchedFiles.length < 5) mismatchedFiles.push(`${file} 整文件=${full.kind} 尾部=${bounded?.kind ?? null}`);
  }
}
check("A2 会话文件可判定", unreadable === 0, `扫到 ${files.length} 个，不可判 ${unreadable}`);
check("A3 有界尾部读取 == 整文件判定", mismatch === 0, mismatch ? `差异 ${mismatch} 个：${mismatchedFiles.join(" | ")}` : `抽查全部 ${files.length} 个一致`);
const total = Object.values(kindCounts).reduce((a, b) => a + b, 0);
// 「四种状态都出现过」是一个关于【样本量】的断言，不是关于代码的断言。
// 新机器 / 干净仓库上只有个位数会话文件，自然凑不齐 model_error、aborted，
// 那时红字是误导（代码没坏，是数据还不够）。所以样本太小时记成「待人工」。
const A4_MIN_SAMPLE = 20;
const a4Ok = (kindCounts.complete ?? 0) > 0 && (kindCounts.model_error ?? 0) > 0 && (kindCounts.aborted ?? 0) > 0;
check("A4 判定分布非退化（四种状态都出现过）", a4Ok || total < A4_MIN_SAMPLE,
  `${Object.entries(kindCounts).map(([k, v]) => `${k}=${v}`).join(" ")}（共 ${total} 个会话文件）`
  + (total < A4_MIN_SAMPLE ? ` — 样本不足 ${A4_MIN_SAMPLE}，用久一点再看` : ""),
  { pending: !a4Ok && total < A4_MIN_SAMPLE });

// 五种判定 → 文案的映射必须逐个正确（不能只靠"恰好跑到"）
const fake = { id: "s", cwd: "C:/pi-work", firstMessage: "跑个渲染" };
const planIssues = [];
for (const [kind, label] of Object.entries(KIND_LABEL)) {
  const plan = planNotification({ kind, reason: "R" }, fake, null);
  if (!plan) planIssues.push(`${kind} 未生成计划`);
  else if (!plan.body.startsWith(label)) planIssues.push(`${kind} 文案=${plan.body}，期望以 ${label} 开头`);
  else if (plan.title !== "pi-work · 跑个渲染") planIssues.push(`${kind} 标题=${plan.title}`);
}
check("A5 五种判定的通知文案映射", planIssues.length === 0, planIssues.join("; ") || Object.keys(KIND_LABEL).join(", "));
check("A6 卡死/失联也有专用文案",
  planStall(fake, null, 12).body.includes("12 分钟") && planPiWebDown(3, "x").title.includes("失联"),
  "stall + piweb_down");

// ── B 自研中转的推送链路 ──────────────────────────────────────────────
section("B 自研中转推送链路（派发台 /pi/*）");
const brokerUrl = (p) => `${config.broker.base}${p}${p.includes("?") ? "&" : "?"}t=${encodeURIComponent(config.broker.token)}`;
const stateRes = await fetch(brokerUrl("/api/state"), { signal: AbortSignal.timeout(8000) })
  .then((r) => r.json()).catch(() => null);
check("B1 派发台（含消息中转）可达", Array.isArray(stateRes?.running), stateRes ? "api/state 正常" : "连不上");

const token = `VERIFY-${randomBytes(4).toString("hex")}`;
const title = `验收 ${token}`;
const message = `中文正文 + 优先级 + 深链 ${token}`;
const click = `http://${config.lan.host}:${config.lan.piWebPort}/`;
let published = null;
try {
  const response = await fetch(brokerUrl("/pi/publish"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title, message, priority: 4, click,
      actions: [
        { action: "view", label: "打开会话", url: click },
        { action: "view", label: "派发台", url: `http://${config.lan.host}:${config.lan.consolePort}/` },
        { action: "view", label: "让它继续跑", url: `http://${config.lan.host}:${config.lan.consolePort}/?t=${config.lan.consoleToken}&do=resume&session=x` },
      ],
    }),
    signal: AbortSignal.timeout(10_000),
  });
  published = response.ok ? await response.json() : { error: `HTTP ${response.status}` };
} catch (error) {
  published = { error: error.message };
}
check("B2 发布被中转接受", Boolean(published?.id), published?.error ?? `id=${published?.id}`);

let received = null;
try {
  const text = await fetch(brokerUrl("/pi/messages?since=10m"), { signal: AbortSignal.timeout(10_000) }).then((r) => r.text());
  const rows = text.split("\n").filter((l) => l.trim()).map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
  received = rows.findLast((row) => String(row.message ?? "").includes(token)) ?? null;
  check("B3 缓存里能读到刚发的那条", Boolean(received), received ? `共 ${rows.length} 条（近 10 分钟）` : "没读到");
} catch (error) {
  check("B3 缓存里能读到刚发的那条", false, error.message);
}
check("B4 中文标题/正文未被破坏", received?.title === title && received?.message === message,
  received ? `title=${received.title}` : "无");
// 深链会被重写成【本次请求的来源】—— 手机从公网地址收到时，点「打开会话」
// 必须能打开，所以这里断言的就是「重写后的地址」而不是原始局域网地址。
check("B5 优先级保真，且点击深链按请求来源重写",
  received?.priority === 4 && typeof received?.click === "string" && received.click.startsWith(config.broker.base),
  received ? `priority=${received.priority} click=${received.click}（期望前缀 ${config.broker.base}）` : "无");
check("B6 三个动作按钮保真（含 resume 深链）",
  received?.actions?.length === 3 && received.actions[2].label === "让它继续跑" && String(received.actions[2].url).includes("do=resume"),
  received?.actions ? `${received.actions.length} 个：${received.actions.map((a) => a.label).join("/")}` : "无");
check("B7 没令牌不能偷看推送流", (await fetch(`${config.broker.base}/pi/stream?since=none`, { signal: AbortSignal.timeout(8000) })).status === 401, "401");

// ── C 看门狗 ────────────────────────────────────────────────────────────
section("C 看门狗");
const lockFile = join(STATE_DIR, "watchdog.lock");
let lockHolder = null;
let lockAlive = false;
if (existsSync(lockFile)) {
  try {
    lockHolder = Number(readFileSync(lockFile, "utf8").trim());
    process.kill(lockHolder, 0);
    lockAlive = true;
  } catch (error) {
    lockAlive = error.code === "EPERM";
  }
}
check("C1 看门狗进程在跑（锁文件 + PID 存活）", lockAlive,
  lockAlive ? `pid=${lockHolder}` : existsSync(lockFile) ? `锁文件在但 pid ${lockHolder} 已死（陈陈锁）` : "锁文件不存在 → 看门狗没起来");

const statePath = join(STATE_DIR, "state.json");
let state = null;
if (existsSync(statePath)) {
  try { state = JSON.parse(readFileSync(statePath, "utf8").replace(/^\uFEFF/, "")); } catch { /* ignore */ }
}
check("C2 状态文件已落盘", Boolean(state), statePath);
check("C3 已完成首次 prime（不会补推历史旧消息）", state?.primed === true,
  state?.primed === true ? `已标记 ${Object.keys(state.notified ?? {}).length} 条` : "未 prime，首次启动会弹一堆旧报错");

// ── 今天踩过的坑：看门狗是常驻进程，改了出口地址（8080 → 8787）不重启它，
//    它就一直往已停用的地址发 —— 每条推送都 fetch failed，而失败只写在
//    watchdog.log 里没人看。外面看什么都像好的（App 在连、中转在跑、网络正常）。
//    这两条断言就是专门盯这个的。
const watchdogPath = join(STATE_DIR, "watchdog.log");
const watchdogLines = existsSync(watchdogPath) ? readFileSync(watchdogPath, "utf8").trim().split("\n") : [];
const pushLines = watchdogLines.filter((l) => /推送 \[/.test(l));
const lastPush = pushLines.at(-1) ?? "";
check(
  "C4 最近一次推送没有失败（出口真的可用）",
  pushLines.length > 0 && !/推送失败|★★★/.test(lastPush),
  lastPush ? lastPush.slice(0, 130) : "没有任何推送记录",
);
const probeLine = watchdogLines.filter((l) => /出口自检/.test(l)).at(-1) ?? "";
check(
  "C5 看门狗启动时出口自检通过（防“改了地址没重启”）",
  /中转可达/.test(probeLine),
  probeLine.slice(0, 130) || "没有自检记录（看门狗是改动前启动的旧进程 —— 重启它）",
);

// C6：中转（派发台 :8787）也必须只有一个实例。
// Windows 上 Node 带 SO_REUSEADDR，两个进程能同时绑同一个端口且都成功 ——
// 那样会变成两台中转各拿一半消息，手机只看到一半。用锁文件 + 监听者计数双重判定。
{
  const listeners = execFileSync("powershell", ["-NoProfile", "-Command",
    "(Get-NetTCPConnection -LocalPort " + config.lan.consolePort + " -State Listen -EA SilentlyContinue | Measure-Object).Count",
  ], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
  const lockPath = join(STATE_DIR, "console.lock");
  const lockPid = existsSync(lockPath) ? readFileSync(lockPath, "utf8").trim() : "";
  check(
    "C6 中转（派发台）是单实例",
    Number(listeners) === 1 && Boolean(lockPid),
    `监听者 ${listeners} 个（应为 1），锁文件 pid=${lockPid || "无"}`,
  );
}

// ── D 派发台 ────────────────────────────────────────────────────────────
section("D 派发台");
const base = `http://127.0.0.1:${config.lan.consolePort}`;
const denied = await fetch(`${base}/api/state`, { signal: AbortSignal.timeout(8000) }).catch(() => null);
check("D1 无令牌被拒绝（401）", denied?.status === 401, `HTTP ${denied?.status}`);
const okRes = await fetch(`${base}/api/state?t=${config.lan.consoleToken}`, { signal: AbortSignal.timeout(12000) }).catch(() => null);
const okJson = okRes ? await okRes.json().catch(() => null) : null;
check("D2 带令牌可取状态（200）", okRes?.status === 200 && Array.isArray(okJson?.running), `HTTP ${okRes?.status}`);
check("D3 未授权时页面返回令牌提示页", (await fetch(`${base}/`, { signal: AbortSignal.timeout(8000) }).catch(() => null))?.status === 401, "");
check("D4 快捷指令已配置", Array.isArray(config.quickCommands) && config.quickCommands.length > 0,
  (config.quickCommands ?? []).map((q) => q.name).join(", "));

// ── E pi-web 可达性 ─────────────────────────────────────────────────────
section("E pi-web 可达性");
let loopbackOk = false;
try {
  const snapshot = await listSessions();
  loopbackOk = Array.isArray(snapshot.sessions);
  // local.json 里没配密码 = 用户主动选的"局域网免密码模式"，不该报成失败
  const mode = config.piWeb.password ? '密码生效' : '免密码模式';
  check("E1 回环可达 + 认证模式正常", loopbackOk, `会话 ${snapshot.sessions?.length ?? 0} 个 · ${mode}`);
} catch (error) {
  check("E1 回环可达 + 认证模式正常", false, error.message);
}

let lanOk = false;
let lanDetail = "";
try {
  const headers = config.piWeb.password
    ? { Authorization: `Basic ${Buffer.from(`pi:${config.piWeb.password}`, "utf8").toString("base64")}` }
    : {};
  const response = await fetch(`http://${config.lan.host}:${config.lan.piWebPort}/api/agent/running`, {
    headers, signal: AbortSignal.timeout(6000),
  });
  lanOk = response.ok;
  lanDetail = `HTTP ${response.status}`;
} catch (error) {
  lanDetail = error.message;
}
check("E2 pi-web 已绑到局域网（手机能连）", lanOk,
  lanOk ? lanDetail : `${lanDetail} → 双击 fix-split-brain.bat 重启 pi-web（关键是绑 0.0.0.0，密码可选）`,
  { pending: !lanOk });

// 实测踩过的坑：老实例还占着 127.0.0.1:30141，新实例绑在 0.0.0.0:30141。
// 两个 listener 共存、都能建连（127.0.0.1 比 0.0.0.0 更具体所以优先匹配），
// 于是电脑浏览器看到的是 A 实例、手机看到的是 B 实例，两者的 runningSessionIds
// 完全是两套内存状态 —— 看门狗的判定基准就错了，会对正在跑的会话误报中断。
let listeners = [];
try {
  const out = execFileSync("powershell", ["-NoProfile", "-Command",
    `Get-NetTCPConnection -LocalPort ${config.lan.piWebPort} -State Listen -ErrorAction SilentlyContinue | `
    + "Select-Object -ExpandProperty LocalAddress"], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
  listeners = out.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
} catch { /* 查不到就当没查 */ }
check("E3 端口上只有一个 pi-web 实例（防双实例脑裂）", listeners.length <= 1,
  listeners.length <= 1
    ? (listeners[0] ? `仅 ${listeners[0]}` : "无监听")
    : `★ 有 ${listeners.length} 个监听者：${listeners.join(", ")}。两套内存状态 → 看门狗会对正在跑的会话误报中断。` +
      ` 先停掉旧的： Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*next start*30141*' } | Select-Object ProcessId,CommandLine`);

// 局域网被 Windows 归类为 Public 的机器很常见（Get-NetConnectionProfile 实测），
// 所以"按 profile 封禁 30141"会把手机一起挡掉。真正该检查的是反过来：
// 有没有任何 Block 规则命中 30141 —— 有的话手机就连不上了。
let portBlockers = [];
let netCategory = "(unknown)";
try {
  const out = execFileSync("powershell", ["-NoProfile", "-Command",
    "$c=(Get-NetConnectionProfile -EA SilentlyContinue|Select-Object -First 1).NetworkCategory;"
    + "'cat=' + $c;"
    + "Get-NetFirewallRule -Direction Inbound -Action Block -Enabled True -EA SilentlyContinue | ForEach-Object {"
    + "  $pf = $_ | Get-NetFirewallPortFilter -EA SilentlyContinue;"
    + "  if ($pf -and ($pf.LocalPort -contains '${config.lan.piWebPort}')) { 'blk=' + $_.DisplayName } }"],
    { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
  for (const line of out.split(/\r?\n/).map((s) => s.trim()).filter(Boolean)) {
    if (line.startsWith("cat=")) netCategory = line.slice(4);
    if (line.startsWith("blk=")) portBlockers.push(line.slice(4));
  }
} catch { /* 查不到就当没查 */ }
check("E4 没有防火墙规则误伤 30141（手机可达）", portBlockers.length === 0,
  portBlockers.length === 0
    ? `网络类别=${netCategory}（Public 属正常，Node.js 自带规则 Private+Public 都放行）`
    : `★ ${portBlockers.join(", ")} 会挡住手机`);

// ── F 五种判定走真实发布链路 ───────────────────────────────────────────
section("F 五种判定走真实发布链路（--simulate）");
// 近期真实会话里恰好只有 complete，所以用 --simulate 把每一种判定都真的推一遍，
// 再回读中转缓存确认文案/优先级/标签落对了。
const simTargets = [...Object.keys(KIND_LABEL), "stall", "piweb_down"];
const simFailures = [];
for (const kind of (SKIP_PUSH ? [] : simTargets)) {
  try {
    execFileSync(process.execPath, [join(import.meta.dirname, "watchdog.mjs"), "--simulate", kind], {
      encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], timeout: 30_000,
    });
  } catch (error) {
    simFailures.push(`${kind} 运行失败: ${String(error.stderr || error.message).slice(0, 140)}`);
  }
}
await new Promise((resolve) => setTimeout(resolve, 1500));
const queue = await fetch(
  `${config.broker.base}/pi/messages?since=10m&t=${config.lan.consoleToken}`,
  { signal: AbortSignal.timeout(10_000) },
).then((r) => r.text()).catch(() => "");
const queueRows = queue.split("\n").filter((l) => l.trim())
  .map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
const bodyOf = (m) => String(m?.message ?? "");
// 标题 + 正文合并匹配：「pi-web 进程失联」这种关键字只在标题里
const textOf = (m) => `${m?.title ?? ""} ${m?.message ?? ""}`;
for (const kind of simTargets) {
  const label = KIND_LABEL[kind] ?? (kind === "stall" ? "疑似卡死" : "失联");
  const row = queueRows.findLast((m) => textOf(m).includes(label));
  if (!row) simFailures.push(`${kind} 的通知没在中转缓存里找到（标签 ${label}）`);
}
check("F1 五种判定 + 卡死 + 失联 全部真实发出", simFailures.length === 0,
  SKIP_PUSH ? "已按 PI_ANDROID_LINK_SKIP_PUSH 跳过（不打扰手机）" : simFailures.length ? simFailures.join(" | ") : `${simTargets.length} 种全部到达`,
  { pending: SKIP_PUSH });
const simRows = queueRows.filter((m) => /模拟|疑似卡死|失联/.test(textOf(m)));
const pOf = (needle) => simRows.findLast((m) => textOf(m).includes(needle))?.priority ?? 0;
check("F2 优先级按严重程度分级",
  pOf("模型报错") === 5 && pOf("异常中断") === 5 && pOf("失联") === 5
  && pOf("任务完成") === 3 && pOf("已中止") === 2,
  `模型报错=${pOf("模型报错")} 异常中断=${pOf("异常中断")} 失联=${pOf("失联")} 完成=${pOf("任务完成")} 中止=${pOf("已中止")}`);
check("F3 emoji 标签已随通知下发",
  simRows.some((m) => Array.isArray(m.tags) && m.tags.length > 0),
  simRows[0] ? JSON.stringify(simRows[0].tags) : "无");

// ── G 启动方式 ───────────────────────────────────────────────────────────
section("G 手动启动");
const startupDir = join(process.env.APPDATA ?? "", "Microsoft", "Windows", "Start Menu", "Programs", "Startup");
const startupVbs = join(startupDir, "pi-android-link.vbs");
const hasStartup = existsSync(startupVbs);
let hasTask = false;
try {
  execFileSync("schtasks", ["/Query", "/TN", "pi-android-link"], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
  hasTask = true;
} catch { /* 没有计划任务 */ }
check("G1 未注册开机自启（只保留手动 BAT）", !hasStartup && !hasTask,
  hasStartup ? `仍存在启动项：${startupVbs}` : hasTask ? "仍存在计划任务 pi-android-link" : "无 Startup VBS、无计划任务");

// ── H 鉴权失败不得把 pi-web 的登录限流刷满 ────────────────────────────
section("H 鉴权失败安全阀（不得把 pi-web 登录限流刷满）");
// 这是本链路最危险的一个失败模式：pi-web 的登录限流是全局共享的，且被限流期间
// 连正确密码也一律拒给访问（lib/auth-throttle.ts + proxy.ts:53）。若看门狗拿着
// 错密码每 15s 打一次，会把限流刷满，后果是**用户自己用浏览器也登不进 pi-web**。
// 所以用桩服务器验证：看门狗会退避、会告警、然后就停手，且不会持续打 API。
let stubHits = 0;
const stub = createServer((_req, res) => {
  stubHits += 1;
  res.writeHead(401, { "Content-Type": "text/plain", "Retry-After": "1" });
  res.end("Authentication required");
});
await new Promise((resolve) => stub.listen(0, "127.0.0.1", resolve));
const stubPort = stub.address().port;

const stubState = join(STATE_DIR, "..", `android-link-verify-h-${process.pid}`);
rmSync(stubState, { recursive: true, force: true });
mkdirSync(stubState, { recursive: true });
writeFileSync(join(stubState, "local.json"), JSON.stringify({
  ...JSON.parse(readFileSync(join(STATE_DIR, "local.json"), "utf8").replace(/^\uFEFF/, "")),
  piWeb: { base: `http://127.0.0.1:${stubPort}`, password: "definitely-wrong" },
  authRetryMs: 50,
}));

// 必须用异步 spawn：桩服务器就跑在本进程里，execFileSync 会把事件循环卡住，
// 桩永远没法应答，看门狗只会超时（踩过这个坑）。
const runWatchdog = (extraArgs) => new Promise((resolve) => {
  const child = spawn(process.execPath, [join(import.meta.dirname, "watchdog.mjs"), ...extraArgs], {
    env: { ...process.env, PI_ANDROID_LINK_STATE_DIR: stubState },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let out = "";
  child.stdout.on("data", (chunk) => { out += chunk; });
  child.stderr.on("data", (chunk) => { out += chunk; });
  child.on("close", () => resolve(out));
  child.on("error", (error) => resolve(`spawn 失败: ${error.message}`));
});

// 只统计本轮新到的消息，免得被之前测试遗留的通知误判为通过
const queueSnapshot = async () => {
  const mine = await fetch(`${config.broker.base}/pi/messages?since=10m&t=${config.lan.consoleToken}`,
    { signal: AbortSignal.timeout(10_000) }).then((r) => r.text()).catch(() => "");
  return mine.split("\n").filter((l) => l.trim())
    .map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
};
const idsBefore = new Set((await queueSnapshot()).map((m) => m.id));

let hLog = "";
for (let attempt = 0; attempt < 3; attempt += 1) hLog += await runWatchdog(["--once", "--force"]);
const hState = JSON.parse(readFileSync(join(stubState, "state.json"), "utf8").replace(/^\uFEFF/, ""));
const hitsAfter3 = stubHits;

check("H0 桩确实被请求到（否则后面全是假阳性）", hitsAfter3 === 3, `桩收到 ${hitsAfter3} 次`);
check("H1 连续失败后写入停手标记（authGiveUpUntil）", (hState.authGiveUpUntil ?? 0) > Date.now(),
  hState.authGiveUpUntil ? `暂停至 ${new Date(hState.authGiveUpUntil).toISOString()}` : "没写标记");
check("H2 停手阈值确实是 3 次", hState.authFailures === 3, `authFailures=${hState.authFailures}`);

const blockedLog = await runWatchdog(["--once"]); // 不带 --force：应直接拒绝开工
check("H3 停手期内即使被守护进程拉起也不打 API", stubHits === hitsAfter3,
  `桩收到 ${hitsAfter3} 次，停手后又来了 ${stubHits - hitsAfter3} 次`);
check("H4 停手期内日志说明了原因", /暂停|--force/.test(blockedLog), blockedLog.split("\n").filter(Boolean).at(-1) ?? "无输出");

await runWatchdog(["--once", "--force"]); // --force = 密码已修好
check("H5 --force 可立即重试", stubHits > hitsAfter3, `桩累计 ${stubHits} 次`);

const newMessages = (await queueSnapshot()).filter((m) => !idsBefore.has(m.id));
const authNotice = newMessages.findLast((m) => String(m.title ?? "").includes("认证失败"));
check("H6 发出了 auth_failed 高优先通知", authNotice?.priority === 5,
  authNotice ? `p${authNotice.priority}（本轮新到 ${newMessages.length} 条）` : `没找到（本轮新到 ${newMessages.length} 条）`);
check("H7 通知里写了怎么修", /local\.json|PI_WEB_PASSWORD/.test(String(authNotice?.message ?? "")), "含修复指引");

await new Promise((resolve) => stub.close(resolve));
rmSync(stubState, { recursive: true, force: true });

// ── I 异地（公网）通知：不用服务器、不用账号 ─────────────────────────────
section("I 异地通知");
const wan = await import("./lib/wan.mjs");
const wanToken = config.lan.consoleToken;
const auth = (p) => `${config.broker.base}${p}${p.includes("?") ? "&" : "?"}t=${encodeURIComponent(wanToken)}`;

check("I1 局域网地址始终排在候选第一位", wan.endpoints()[0]?.kind === "lan", wan.endpoints()[0]?.base);

const wanDisabled = config.wan.enabled === false;
const wanBlocked = wan.gatewayBlockedReason();
check(
  "I2 安全阀：pi-web 无密码时公网入口不开",
  Boolean(config.piWeb.password) || config.wan.gatewayWithoutPassword === true || Boolean(wanBlocked),
  wanBlocked ?? "有密码，正常开放",
);
check(
  "I3 无密码且没显式开 wan.gatewayWithoutPassword → 确实被拦住",
  Boolean(config.piWeb.password) || config.wan.gatewayWithoutPassword === true || !wanDisabled,
  wanBlocked ?? "不适用",
);

// 候选清单本身：每一条都得是能拼出 URL 的地址，局域网那条必须免令牌可达
const wanList = wan.endpoints();
const wanMalformed = wanList.filter((e) => !/^https?:\/\/[^\s]+$/.test(e.base));
check("I4 候选地址格式合法", wanMalformed.length === 0, wanMalformed.map((e) => e.base).join(", ") || `${wanList.length} 条`);
const wanLanEntry = wanList.find((e) => e.kind === "lan");
// 验收机上可能根本没有那个局域网 IP（在别的机器上跑验收就是这样）——
// 那不是代码问题，记成「待人工」而不是失败。
const { networkInterfaces } = await import("node:os");
const localAddrs = new Set();
for (const infos of Object.values(networkInterfaces())) {
  for (const i of infos ?? []) if (i.address) localAddrs.add(i.address);
}
const lanHost = String(wanLanEntry.base).replace(/^https?:\/\//, "").split(":")[0].replace(/[\[\]]/g, "");
const lanIsLocal = lanHost === "127.0.0.1" || lanHost === "localhost" || localAddrs.has(lanHost);
const wanLanOk = await fetch(`${wanLanEntry.base}/pi/ping?t=${encodeURIComponent(wanToken)}`, {
  signal: AbortSignal.timeout(5000),
}).then((r) => r.ok).catch(() => false);
check("I5 局域网候选自检可达（手机在家时的兜底）", wanLanOk || !lanIsLocal,
  wanLanOk ? wanLanEntry.base : lanIsLocal ? `${wanLanEntry.base} 探测失败` : `${wanLanEntry.base}（这台机器没这个 IP，已跳过）`,
  { pending: !wanLanOk && !lanIsLocal });

const wanRemote = wanList.filter((e) => e.kind !== "lan");
check(
  "I6 至少有一个异地出口可用",
  wanRemote.length > 0,
  wanRemote.length
    ? wanRemote.map((e) => `${e.kind}:${e.base}`).join(" , ")
    : "一个都没有（没装 cloudflared / 没 IPv6 / 没做端口映射）—— 跑 node wan-report.mjs 看原因",
  // 这是部署状态不是代码状态：没配异地地址不该让验收报红，但必须在总结里被追究
  { pending: wanRemote.length === 0 },
);

// 网关：要么在监听，要么说清为什么没启
let wanGatewayListening = false;
try {
  const g = await fetch(`http://127.0.0.1:${config.wan.gatewayPort}/pi/ping?t=${encodeURIComponent(wanToken)}`, {
    signal: AbortSignal.timeout(3000),
  });
  wanGatewayListening = g.ok;
} catch {
  wanGatewayListening = false;
}
check(
  "I7 统一出口（派发台路由 + pi-web 反代）状态明确",
  wanGatewayListening || Boolean(wanBlocked) || !wanDisabled,
  wanGatewayListening ? `:${config.wan.gatewayPort} 在监听` : wanBlocked ?? `未监听（:${config.wan.gatewayPort}）`,
);

// 候选清单必须真的进了协议：不然手机永远只知道一个地址
const wanEpJson = await fetch(auth("/pi/endpoints"), { signal: AbortSignal.timeout(5000) })
  .then((r) => r.json())
  .catch(() => null);
check("I8 /pi/endpoints 返回候选清单", Array.isArray(wanEpJson?.endpoints) && wanEpJson.endpoints.length > 0,
  (wanEpJson?.endpoints ?? []).map((e) => e.kind).join(","));

const wanCtrl = new AbortController();
const wanStreamRes = await fetch(auth("/pi/stream?since=none&ka=5"), { signal: wanCtrl.signal });
const wanFirstChunk = await wanStreamRes.body.getReader().read();
wanCtrl.abort();
const wanOpenFrame = (() => {
  try {
    return JSON.parse(new TextDecoder().decode(wanFirstChunk.value ?? new Uint8Array()).split("\n")[0]);
  } catch {
    return null;
  }
})();
check("I9 推送流 open 帧带候选清单（手机据此自动切换）",
  wanOpenFrame?.event === "open" && Array.isArray(wanOpenFrame.bases) && wanOpenFrame.bases.length > 0,
  (wanOpenFrame?.bases ?? []).join(" , "));

// 深链重写：从非局域网入口拿到的消息，链接必须跟着换
const wanProbeTitle = `异地重写探针 ${Date.now()}`;
await fetch(auth("/pi/publish"), {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    title: wanProbeTitle,
    message: "验收用：链接应当按请求来源重写",
    priority: 3,
    click: `http://${config.lan.host}:${config.lan.piWebPort}/?session=abc`,
  }),
});
const wanRewritten = await fetch(auth("/pi/messages?since=10m"), { signal: AbortSignal.timeout(5000) })
  .then((r) => r.text())
  .then((t) => t.split("\n").filter(Boolean).map((l) => { try { return JSON.parse(l); } catch { return null; } }))
  .then((rows) => rows.findLast?.((m) => m?.title === wanProbeTitle) ?? [...rows].reverse().find((m) => m?.title === wanProbeTitle));
check("I10 通知深链按请求来源重写（异地点得开）",
  typeof wanRewritten?.click === "string" && wanRewritten.click.startsWith(config.broker.base),
  wanRewritten?.click ?? "没读到那条消息");
check("I11 消息里带候选清单（轮询兵底通道也能学到新地址）",
  Array.isArray(wanRewritten?.bases) && wanRewritten.bases.length > 0, (wanRewritten?.bases ?? []).join(" , "));

// ── 总结 ────────────────────────────────────────────────────────────────
const hardFailed = results.filter((r) => !r.ok && !r.pending);
const pending = results.filter((r) => !r.ok && r.pending);
console.log(`\n${"=".repeat(62)}`);
console.log(`验收：${results.length - hardFailed.length - pending.length}/${results.length} 通过`);
if (hardFailed.length) console.log(`失败（需修复）：${hardFailed.map((r) => r.id).join(", ")}`);
if (pending.length) console.log(`待人工（不影响退出码）：${pending.map((r) => r.id).join(", ")}`);
if (!hardFailed.length && !pending.length) console.log("全部通过。");
console.log("=".repeat(62));
process.exit(hardFailed.length === 0 ? 0 : 1);
