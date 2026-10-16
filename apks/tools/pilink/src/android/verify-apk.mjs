/**
 * Pi 通知（pilink）APK 的确定性验收。
 *
 * 为什么值得写：这个 APK 存在的唯一理由是「比上一版第三方客户端更能活下来」，
 * 而那件事在源码里是可以被断言成事实的，不需要靠观感：
 *   · 必须【不】声明 SCHEDULE_EXACT_ALARM —— 一旦声明了，就说明有人又把它写回了
 *     旧客户端那条「权限缺失就静默放弃重连」的老路。
 *   · 必须声明 specialUse 前台服务类型 —— 不能用 dataSync（Android 15+ 有 6 小时超时）。
 *   · 必须 usesCleartextTraffic=true —— 订阅端是家里的 http://，明文。
 *
 * 用法：node android/verify-apk.mjs [--quiet] [任意一个 .apk 路径]
 * 不传路径时默认找 gradle 的输出：android/app/build/outputs/apk/debug/app-debug.apk
 */
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { inflateRawSync } from "node:zlib";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const QUIET = process.argv.includes("--quiet");

function sdkDir() {
  if (process.env.ANDROID_HOME) return process.env.ANDROID_HOME;
  if (process.env.ANDROID_SDK_ROOT) return process.env.ANDROID_SDK_ROOT;
  const localProps = join(HERE, "local.properties");
  if (existsSync(localProps)) {
    const m = readFileSync(localProps, "utf8").match(/sdk\.dir=(.+)/);
    // local.properties 里是 Java properties 转义：D\:\\AndroidSDK → <ANDROID_SDK>
    if (m) return m[1].trim().replace(/\\\\/g, "\\").replace(/\\:/g, ":");
  }
  throw new Error("找不到 Android SDK：设置 ANDROID_HOME 或 android/local.properties 里的 sdk.dir");
}

function findAapt2() {
  const sdk = sdkDir();
  const buildTools = join(sdk, "build-tools");
  if (!existsSync(buildTools)) throw new Error(`没有 ${buildTools}`);
  const versions = readdirSync(buildTools).sort((a, b) =>
    b.localeCompare(a, undefined, { numeric: true }),
  );
  for (const v of versions) {
    const p = join(buildTools, v, "aapt2.exe");
    if (existsSync(p)) return p;
    const p2 = join(buildTools, v, "aapt2");
    if (existsSync(p2)) return p2;
  }
  throw new Error("build-tools 里没有 aapt2");
}

/**
 * 从 APK（其实就是个 zip）里取出某个条目的原始字节。
 * 自己实现是为了不引依赖，也不依赖系统里有没有 unzip。
 */
function readZipEntry(apkPath, entryName) {
  const buf = readFileSync(apkPath);
  let eocd = -1;
  for (let i = buf.length - 22; i >= 0 && i > buf.length - 66_000; i -= 1) {
    if (buf.readUInt32LE(i) === 0x06054b50) {
      eocd = i;
      break;
    }
  }
  if (eocd < 0) throw new Error("APK 里找不到 zip EOCD");
  const count = buf.readUInt16LE(eocd + 10);
  let off = buf.readUInt32LE(eocd + 16);
  for (let i = 0; i < count; i += 1) {
    if (buf.readUInt32LE(off) !== 0x02014b50) throw new Error("zip 中央目录损坏");
    const method = buf.readUInt16LE(off + 10);
    const compSize = buf.readUInt32LE(off + 20);
    const nameLen = buf.readUInt16LE(off + 28);
    const extraLen = buf.readUInt16LE(off + 30);
    const commentLen = buf.readUInt16LE(off + 32);
    const localOff = buf.readUInt32LE(off + 42);
    const name = buf.toString("utf8", off + 46, off + 46 + nameLen);
    if (name === entryName) {
      const lNameLen = buf.readUInt16LE(localOff + 26);
      const lExtraLen = buf.readUInt16LE(localOff + 28);
      const start = localOff + 30 + lNameLen + lExtraLen;
      const data = buf.subarray(start, start + compSize);
      return method === 0 ? data : inflateRawSync(data);
    }
    off += 46 + nameLen + extraLen + commentLen;
  }
  return null;
}

// 可以显式传 APK 路径（例如验收分享包里预置的 apk/pilink-*.apk）
const APK_ARG = process.argv.slice(2).find((a) => a.toLowerCase().endsWith(".apk"));
const APK = APK_ARG ? resolve(process.cwd(), APK_ARG) : resolve(HERE, "app/build/outputs/apk/debug/app-debug.apk");
const results = [];
function check(id, ok, detail) {
  results.push({ id, ok, detail });
  if (!QUIET || !ok) console.log(`${ok ? "PASS" : "FAIL"}  ${id}${detail ? ` — ${detail}` : ""}`);
}

if (!existsSync(APK)) {
  console.log(`FAIL  A0 APK 存在 — ${APK} 不存在，先跑：gradle assembleDebug`);
  process.exit(1);
}
check("A0 APK 存在且非空", statSync(APK).size > 500_000, `${(statSync(APK).size / 1024 / 1024).toFixed(2)} MB`);

const aapt2 = findAapt2();
const badging = execFileSync(aapt2, ["dump", "badging", APK], { encoding: "utf8", maxBuffer: 1 << 24 });
const manifest = execFileSync(aapt2, ["dump", "xmltree", "--file", "AndroidManifest.xml", APK], {
  encoding: "utf8",
  maxBuffer: 1 << 24,
});

const pkgName = (badging.match(/package: name='([^']+)'/) ?? [])[1];
const versionName = (badging.match(/versionName='([^']+)'/) ?? [])[1];
const targetSdk = (badging.match(/targetSdkVersion:'(\d+)'/) ?? [])[1];
const minSdk = (badging.match(/(?:min)?[sS]dkVersion:'(\d+)'/) ?? [])[1];
const perms = [...badging.matchAll(/uses-permission: name='([^']+)'/g)].map((m) => m[1]);

check("A1 包名", pkgName === "io.pilink", pkgName);
check("A2 版本号可读", Boolean(versionName), `versionName=${versionName} targetSdk=${targetSdk} minSdk=${minSdk}`);
check("A3 targetSdk ≥ 34（Android 14 行为可控）", Number(targetSdk) >= 34, `targetSdk=${targetSdk}`);
check("A4 minSdk 26（机型 K13 Turbo Pro 远高于此）", Number(minSdk) === 26, `minSdk=${minSdk}`);

for (const need of [
  "android.permission.INTERNET",
  "android.permission.POST_NOTIFICATIONS",
  "android.permission.FOREGROUND_SERVICE",
  "android.permission.FOREGROUND_SERVICE_SPECIAL_USE",
  "android.permission.WAKE_LOCK",
  "android.permission.RECEIVE_BOOT_COMPLETED",
]) {
  check(`A5 声明 ${need}`, perms.includes(need), "");
}

check(
  "A6 【关键】不声明 SCHEDULE_EXACT_ALARM",
  !perms.includes("android.permission.SCHEDULE_EXACT_ALARM"),
  perms.includes("android.permission.SCHEDULE_EXACT_ALARM")
    ? "声明了！重连逻辑可能又依赖精确闹钟权限了"
    : "重连不依赖任何特殊权限",
);
check(
  "A7 【关键】前台服务类型是 specialUse(0x40000000) 而不是 dataSync",
  /foregroundServiceType\(0x01010599\)=0x40000000/.test(manifest),
  (manifest.match(/foregroundServiceType\(0x01010599\)=(\S+)/) ?? [])[1] ?? "没读到",
);
check(
  "A8 specialUse 的用途说明已声明（Android 14 必需）",
  manifest.includes("android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE"),
  "",
);
check(
  "A9 【关键】usesCleartextTraffic=true（明文访问家里的 http 服务端）",
  /usesCleartextTraffic\(0x010104ec\)=true/.test(manifest),
  "",
);
check("A10 服务与开机接收器都在清单里", /E: service/.test(manifest) && /E: receiver/.test(manifest), "");
check("A11 开机广播已注册", manifest.includes("android.intent.action.BOOT_COMPLETED"), "");
check(
  "A12 pilink:// 深链已注册（派发台 /app 页一键配置用）",
  manifest.includes('"pilink"'),
  manifest.includes('"pilink"') ? "" : "没注册深链，派发台的一键配置会点不动",
);
check(
  "A13 设置页已注册且不导出（编辑型控件收在内部页，不进首屏）",
  manifest.includes("io.pilink.SettingsActivity"),
  "",
);

// A14/A15：参数不只要写在 Prefs 里，还得真的编进 dex。
// 这两条防的是「声明了设置项、但 Subscriber 里没人读」这种错——
// 它编译得过、跑起来不报错，只是参数完全不起作用。
const dexText = ["classes.dex", "classes2.dex", "classes3.dex"]
  .map((n) => {
    try {
      const d = readZipEntry(APK, n);
      return d ? d.toString("latin1") : "";
    } catch {
      return "";
    }
  })
  .join("");
const tuningKeys = [
  // 真正必须由代码产出的字符串：设置项键名 + 游标定基函数名。
  // 诊断字段（batteryWhitelisted/screenOn/heldBySystem…）随诊断层一起移除了，
  // 不能再断言它们存在 —— 否则断言会对着一个已经删掉的功能报错。
  "pingSeconds", "staleSeconds", "pollSeconds", "idlePollSeconds", "resetTuning",
  "primeCursorIfNeeded",
  // 异地通知（2026-09-26 加）：候选地址清单必须真的编进 dex。
  // 少了这几条，App 会退回到「死死连一个地址」的行为 —— 表现为出门就收不到，
  // 而代码里看起来一切正常（这正是要断言拦住的那类错）。
  "EndpointManager", "autoSwitch", "activeBase", "learnBases", "pi/ping", "endpoints",
];
const missingKeys = dexText ? tuningKeys.filter((k) => !dexText.includes(k)) : tuningKeys;
check(
  "A14 心跳/轮询参数已编进 dex（不是只写在文档里）",
  dexText.length > 0 && missingKeys.length === 0,
  dexText.length === 0 ? "dex 读不出来" : missingKeys.length ? `缺 ${missingKeys.join(",")}` : tuningKeys.join(", "),
);
check(
  "A15 电池白名单引导已编进去（Doze 断网只能靠它）",
  dexText.includes("whitelistAsked"),
  "",
);
// A16：应用图标必须是自适应图标（mipmap + adaptive-icon），不能直接拿一个裸矢量图当图标——
// 那样 ColorOS 会把它塞进白圈里，看起来像“没有图标”。
const appIcon = (badging.match(/application-icon-\d+'([^']+)'/) ?? [])[1]
  ?? (badging.match(/application:.*icon='([^']+)'/) ?? [])[1]
  ?? "";
check(
  "A16 应用图标是自适应图标（mipmap/ic_launcher.xml）",
  /ic_launcher\.xml$/.test(appIcon),
  appIcon || "badging 里没读到 application-icon",
);
// A17：清单里的 icon / roundIcon 必须都指向那个 mipmap。
// 注意 aapt2 在 xmltree 里把资源写成 id（@0x7f…）而不是名字，所以先从资源表把 id 查出来再数引用次数。
const resourcesDump = execFileSync(aapt2, ["dump", "resources", APK], { encoding: "utf8", maxBuffer: 1 << 26 });
const mipmapId = (resourcesDump.match(/resource (0x[0-9a-f]+) mipmap\/ic_launcher\b/) ?? [])[1] ?? "";
const iconRefs = mipmapId ? manifest.split(`=@${mipmapId}`).length - 1 : 0;
check(
  "A17 清单里的 icon / roundIcon 都指向 mipmap/ic_launcher",
  iconRefs >= 2,
  `mipmap id=${mipmapId || "?"} 被引用 ${iconRefs} 次（应为 2）`,
);

// ── B 组：客户端 ↔ 自研中转的协议契约 ─────────────────────────────────────
// 协议是我们自己的，最容易悄悄漂移的就是它。尤其是「NDJSON 一行一个对象」
// 这条：客户端若用 JSONArray 解析会静默失效（曾经真的这么错过），必须断言拦住。
const localPath = join(
  process.env.PI_ANDROID_LINK_STATE_DIR ?? join(homedir(), ".pi", "android-link"),
  "local.json",
);

if (!existsSync(localPath)) {
  check("B0 找得到 local.json", false, localPath);
} else {
  const local = JSON.parse(readFileSync(localPath, "utf8").replace(/^\uFEFF/, ""));
  const base = `http://127.0.0.1:${local.lan?.consolePort ?? 8787}`;
  const token = local.lan?.consoleToken ?? "";
  // 本机真实的局域网地址（看门狗发布通知时用的就是它）
  const lanConsole = `http://${local.lan?.host ?? "127.0.0.1"}:${local.lan?.consolePort ?? 8787}`;
  const lanPiWeb = `http://${local.lan?.host ?? "127.0.0.1"}:${local.lan?.piWebPort ?? 30141}/`;
  const auth = (p) => `${base}${p}${p.includes("?") ? "&" : "?"}t=${encodeURIComponent(token)}`;

  const req = async (url, init) => {
    const res = await fetch(url, { ...init, signal: AbortSignal.timeout(8000) });
    return { status: res.status, text: await res.text() };
  };
  const lines = async (url) => {
    const r = await req(url);
    return { ...r, lines: r.text.split("\n").filter((l) => l.trim()) };
  };
  const parse = (s) => {
    try {
      return JSON.parse(s);
    } catch {
      return null;
    }
  };

  try {
    const state = await req(auth("/api/state"));
    check("B1 派发台可达", state.status === 200, `${base} → HTTP ${state.status}`);

    const before = await lines(auth("/pi/messages?since=all"));
    const probeTitle = `验收探针 ${Date.now()}`;
    const pub = await req(auth("/pi/publish"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: probeTitle,
        message: "验收用：中文、优先级、点击链接、三个动作按钮都要保真",
        priority: 4,
        // 故意用「局域网出身」的地址：服务端只在投递时把它重写成请求来源，
        // 所以这里必须取 local.json 里的真实 lan.host —— 写死 192.168.1.100 的话，
        // 换了网段的机器上就不会被重写，B6b 会假失败。
        click: lanPiWeb,
        actions: [
          { action: "view", label: "打开会话", url: lanPiWeb },
          { action: "view", label: "派发台", url: `${lanConsole}/` },
          { action: "view", label: "让它继续跑", url: `${lanConsole}/?do=resume` },
        ],
        group: "pi-verify",
      }),
    });
    const pubJson = parse(pub.text);
    check("B2 发布被中转接受（要令牌）", pub.status === 200 && pubJson?.ok === true, pubJson?.id ? `id=${pubJson.id}` : `HTTP ${pub.status} ${pub.text.slice(0, 60)}`);

    const after = await lines(auth("/pi/messages?since=all"));
    check("B3 缓存里多了一条", after.lines.length === before.lines.length + 1, `${before.lines.length} → ${after.lines.length}`);

    const last = parse(after.lines[after.lines.length - 1] ?? "");
    check("B4 返回的是 NDJSON（一行一个对象，不是 JSON 数组）", last !== null && !Array.isArray(last), last === null ? `首行不是合法 JSON：${(after.lines[after.lines.length - 1] ?? "").slice(0, 80)}` : "");
    const missing = ["id", "time", "title", "message", "priority"].filter((k) => !(last && k in last));
    check("B5 客户端要的字段齐全", missing.length === 0, missing.length ? `缺 ${missing.join(",")}` : "id/time/title/message/priority ✓");
    check(
      "B6 中文 / 优先级 / 三个动作保真",
      last?.title === probeTitle && last?.priority === 4 && last?.actions?.length === 3 && last.actions[2].label === "让它继续跑",
      `title=${last?.title === probeTitle} priority=${last?.priority} actions=${last?.actions?.length}`,
    );
    // 异地能力的核心：通知里的链接按【本次请求的来源】重写。
    // 从 127.0.0.1 拉的，click 就必须是 127.0.0.1 那个，不能还是局域网 IP ——
    // 否则手机从公网地址收到通知时，点「打开会话」会打到一个它连不上的地址。
    check(
      "B6b 点击深链按请求来源重写（异地才点得开）",
      last?.click === `${base}/` && last?.actions?.[0]?.url === `${base}/`,
      `click=${last?.click}（应为 ${base}/）`,
    );

    const none = await lines(auth("/pi/messages?since=none"));
    check("B7 since=none 返回空（首装不弹旧消息）", none.lines.length === 0, `${none.lines.length} 条`);

    const cursor = await lines(auth(`/pi/messages?since=${pubJson?.id}`));
    check("B8 游标：since=<刚发的 id> 之后为空", cursor.lines.length === 0, `${cursor.lines.length} 条`);

    // 游标补收：拿倒数第三条当游标，应该正好拿到它之后的那些。
    // 缓存里不足 3 条时用最早那条（否则下标为负，取到空行，断言会假失败）。
    const olderIdx = Math.max(0, after.lines.length - 3);
    const older = parse(after.lines[olderIdx] ?? "");
    const back = await lines(auth(`/pi/messages?since=${older?.id ?? "none"}`));
    check("B9 游标补收：since=<倒数第三条> 之后正好 2 条", back.lines.length === after.lines.length - olderIdx - 1, `${back.lines.length} 条`);

    const noAuth = await req(`${base}/pi/stream?since=none`);
    check("B10 没令牌不能偷看推送流（401）", noAuth.status === 401, `HTTP ${noAuth.status}`);

    // 推送流是永不结束的响应，所以只读第一块然后主动掐断
    const controller = new AbortController();
    const streamRes = await fetch(auth("/pi/stream?since=none&ka=5"), { signal: controller.signal });
    const reader = streamRes.body.getReader();
    const firstChunk = await reader.read();
    controller.abort();
    const firstLine = new TextDecoder().decode(firstChunk.value ?? new Uint8Array()).split("\n")[0];
    check("B11 推送流能建立且首帧是 open", streamRes.status === 200 && parse(firstLine)?.event === "open", `HTTP ${streamRes.status} 首帧=${firstLine.slice(0, 60)}`);

    const ack = await req(`${base}/pi/ack`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: pubJson?.id ?? "x", time: Math.floor(Date.now() / 1000) }),
    });
    check("B12 回执端点免令牌可用（手机后台线程才能回报）", ack.status === 200, `HTTP ${ack.status}`);

    // ── C 组：异地（公网）能力的协议契约 ─────────────────────────────────
    // 这一组拦的是“文档写了异地、手机却只会连一个地址”这种错。
    const ping = parse((await req(auth("/pi/ping"))).text);
    check("C1 /pi/ping 可用（手机拿它快速探测候选地址）", ping?.ok === true, JSON.stringify(ping?.ok));
    check(
      "C2 /pi/ping 至少回一个局域网地址（手机配置时的主地址）",
      Array.isArray(ping?.bases) && ping.bases.some((b) => /^http:\/\/(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|127\.)/.test(b)),
      (ping?.bases ?? []).join(" , ") || "没有 bases",
    );
    const eps = parse((await req(auth("/pi/endpoints"))).text);
    check(
      "C3 /pi/endpoints 给出带类型的候选清单（排障/手机显示用）",
      Array.isArray(eps?.endpoints) && eps.endpoints.every((e) => typeof e.base === "string" && typeof e.kind === "string"),
      (eps?.endpoints ?? []).map((e) => `${e.kind}:${e.base}`).join(" , "),
    );
    const noTokenPing = await req(`${base}/pi/ping`);
    check("C4 /pi/ping 也要令牌（它是公网入口，不能裸奔）", noTokenPing.status === 401, `HTTP ${noTokenPing.status}`);

    // 推送流的 open 帧必须带 bases —— 这是手机学到新地址的唯一途径
    const controller2 = new AbortController();
    const stream2 = await fetch(auth("/pi/stream?since=none&ka=5"), { signal: controller2.signal });
    const first2 = await stream2.body.getReader().read();
    controller2.abort();
    const openFrame = parse(new TextDecoder().decode(first2.value ?? new Uint8Array()).split("\n")[0]);
    check(
      "C5 推送流 open 帧带候选地址清单",
      openFrame?.event === "open" && Array.isArray(openFrame.bases) && openFrame.bases.length > 0,
      `bases=${(openFrame?.bases ?? []).join(" , ") || "无"}`,
    );
    // 网关（:8788）是公网入口：要么真在监听，要么明确说清为什么没启。
    // 两种都不接受：「没启但也没说原因」= 手机在外面一条都收不到而没人知道。
    const gatewayPort = Number(local.wan?.gatewayPort ?? 8788);
    let gatewayListening = false;
    try {
      const g = await fetch(`http://127.0.0.1:${gatewayPort}/pi/ping?t=${encodeURIComponent(token)}`, {
        signal: AbortSignal.timeout(3000),
      });
      gatewayListening = g.ok;
    } catch {
      gatewayListening = false;
    }
    check(
      "C6 网关要么在监听、要么明确说明为什么没启",
      gatewayListening || typeof eps?.gatewayBlocked === "string",
      gatewayListening
        ? `:${gatewayPort} 在监听`
        : eps?.gatewayBlocked
          ? `未启用：${eps.gatewayBlocked}`
          : `未监听但也没说原因（:${gatewayPort}）`,
    );
  } catch (error) {
    check("B1 派发台可达", false, `连不上 ${base}：${error.message}`);
  }
}

const failedTotal = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failedTotal}/${results.length} 通过${failedTotal ? `，${failedTotal} 项失败` : "，全部通过"}`);
process.exit(failedTotal ? 1 : 0);
