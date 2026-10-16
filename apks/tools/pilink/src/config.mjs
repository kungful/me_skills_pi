/**
 * 安卓链路统一配置。
 *
 * 唯一的秘密来源是 ~/.pi/android-link/local.json（由 setup.ps1 生成，
 * 里面放 pi-web 密码 / 派发台令牌 / 中转地址）。本文件只负责读它 + 兜默认值。
 * 不要把这个 json 提交到任何仓库。
 */
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

export const HOME = homedir();
// 允许测试用隔离的状态目录，避免自检把真实状态搅坏
export const STATE_DIR = process.env.PI_ANDROID_LINK_STATE_DIR ?? join(HOME, ".pi", "android-link");
export const LOCAL_CONFIG = join(STATE_DIR, "local.json");

function readLocal() {
  if (!existsSync(LOCAL_CONFIG)) return {};
  try {
    // PowerShell 5.1 的 Set-Content -Encoding UTF8 会写 BOM，JSON.parse 会炸，先剥掉
    const text = readFileSync(LOCAL_CONFIG, "utf8").replace(/^\uFEFF/, "");
    return JSON.parse(text);
  } catch (error) {
    console.error(`[配置] ${LOCAL_CONFIG} 解析失败，用默认值继续:`, error.message);
    return {};
  }
}

const local = readLocal();

export const config = {
  // pi-web：进程内的真相来源（哪些会话正在跑）
  piWeb: {
    base: (local.piWeb?.base ?? "http://127.0.0.1:30141").replace(/\/$/, ""),
    // 只给 API 用；主界面走浏览器 cookie 登录
    password: local.piWeb?.password ?? process.env.PI_WEB_PASSWORD ?? "",
  },

  // 消息中转就在派发台里（console-server.mjs 的 /pi/*）。
  broker: {
    base: (local.broker?.base ?? `http://127.0.0.1:${local.lan?.consolePort ?? 8787}`).replace(/\/$/, ""),
    token: local.broker?.token ?? local.lan?.consoleToken ?? "",
  },

  // 手机侧要访问的地址（通知深链 / 控制台）
  lan: {
    host: local.lan?.host ?? "192.168.1.100",
    piWebPort: local.lan?.piWebPort ?? 30141,
    consolePort: local.lan?.consolePort ?? 8787,
    consoleToken: local.lan?.consoleToken ?? "",
  },

  // 异地（公网）可达性。目标：不买服务器、不租服务器、不注册账号，
  // 也能让手机在外面收到通知。见 lib/wan.mjs 顶部那段「为什么这样做」。
  wan: {
    // 总开关。关掉就完全不查公网 IP、不起隧道（也不开网关端口）。
    enabled: local.wan?.enabled ?? true,
    // 统一出口端口：派发台自己的 /pi/* 加上 pi-web 的反代都在它身上。
    // 公网候选地址一律用它，局域网候选继续用 8787（行为不变）。
    gatewayPort: local.wan?.gatewayPort ?? 8788,
    // 公网 IPv4 多久刷新一次。动态公网 IP（PPPoE 重播/换租期）会变，
    // 变了必须能被手机知道，所以定期刷新而不是只在启动时查一次。
    ipRefreshMs: local.wan?.ipRefreshMs ?? 10 * 60_000,
    // off | auto | cloudflared
    //   auto/cloudflared = 用 cloudflared 的 Quick Tunnel（免账号、免费、随机域名）
    //   off = 不用隧道，只靠 IPv6 / 端口映射 / 手填地址
    tunnel: local.wan?.tunnel ?? "auto",
    // 自定义隧道命令：{local} 会被替换成本地网关地址，
    // 命令把公网地址打印到 stdout/stderr 任意一处即可（我们抓第一个 https:// 开头的东西）。
    tunnelCommand: local.wan?.tunnelCommand ?? "",
    // cloudflared 可执行文件的绝对路径（默认在 PATH 里找，找不到就只用 IPv6/端口映射）
    cloudflaredPath: local.wan?.cloudflaredPath ?? "",
    // 手填的公网地址（自己已经有反向代理/内网穿透时用）。形如 "https://xxx.example.com"
    extraBases: local.wan?.extraBases ?? [],
    // 查公网 IP 的服务列表。留空数组 = 完全不查（离线环境）。
    ipServices: local.wan?.ipServices ?? [
      "https://api.ipify.org",
      "https://ifconfig.me/ip",
      "https://icanhazip.com",
      "https://ipinfo.io/ip",
      "https://api.ip.sb/ip",
      "https://myip.ipip.net",
    ],
    // 自检候选地址用的超时（毫秒）。要短 —— 手机端拿它做快速探测。
    probeTimeoutMs: local.wan?.probeTimeoutMs ?? 6_000,
    /**
     * 网关（也就是公网入口）是否允许在「pi-web 没有密码」时启动。
     * 默认 false：pi-web 能执行任意命令，无密码 + 公网可达 = 把整台机器交出去，
     * 所以这里宁可不做，也不给「顺手就开」留口子。隧道同样要求有密码。
     */
    gatewayWithoutPassword: local.wan?.gatewayWithoutPassword ?? false,
    // 通知里的深链是否优先用公网地址（默认否 —— 手机收到时会按「自己连上的那个出口」重写，
    // 留着这个开关只是为了万一你想要固定写死公网链接）
    preferPublicLinks: local.wan?.preferPublicLinks ?? false,
  },

  // 会话文件
  sessionsDir: local.sessionsDir ?? join(HOME, ".pi", "agent", "sessions"),
  stateFile: join(STATE_DIR, "state.json"),
  logFile: join(STATE_DIR, "watchdog.log"),

  // 判定节奏（均可用 local.json 覆写）
  pollMs: local.pollMs ?? 5_000, // 轮询间隔（判定延迟主要来自它，5s 够快也不吵）
  // 文件静默多久才认定"已定局"。分两档：
  //   末条 assistant 带【最终】stopReason（stop/length/error/aborted）
  //     → 文件里已经有硬证据说明本回合结束，只需极短静默防半行 → fastSettleMs
  //   末条停在 toolUse（工具可能还在跑）
  //     → 才用保守的 settleGraceMs
  // 以前不分档、一律等 20s，导致“会话跑完 → 手机上要 30 多秒才响”。
  settleGraceMs: local.settleGraceMs ?? 20_000,
  fastSettleMs: local.fastSettleMs ?? 1_500,
  hangMs: local.hangMs ?? 10 * 60_000, // 仍在 running 但文件 N 毫秒没动 → 疑似卡死
  recentSessionMs: local.recentSessionMs ?? 36 * 60 * 60_000, // 只看最近这段时间动过的会话
  tailBytes: local.tailBytes ?? 65_536, // 尾部判定的起始窗口（不够会自动放大，见 classify.mjs）
  // 鉴权失败后的最小退避。故意偏大：pi-web 的登录限流是全局共享的
  // （lib/auth-throttle.ts），连打会把限流刷满，导致用户自己的浏览器也登不进去。
  authRetryMs: local.authRetryMs ?? 60_000,

  // 手机派发
  defaultCwd: local.defaultCwd ?? "C:/pi-work",
  quickCommands: local.quickCommands ?? [
    { name: "status", label: "看看现在在跑什么", cwd: "C:/pi-work", prompt: "列出当前机器上正在运行的 pi 会话和它们的状态，用中文简述。" },
    { name: "render", label: "接着把渲染跑完", cwd: "C:/pi-work", prompt: "继续上一次未完成的任务，把渲染跑完并汇报结果。" },
  ],
};

export const piWebUrl = (path) => `${config.piWeb.base}${path}`;

/** 局域网候选地址（手机在家里用的那个，端口是派发台自己的） */
export const lanBase = () => `http://${config.lan.host}:${config.lan.consolePort}`;
/** 统一出口的本地地址（公网隧道/端口映射指向它；它同时反代 pi-web） */
export const gatewayLocalBase = () => `http://127.0.0.1:${config.wan.gatewayPort}`;
export const deepLink = (sessionId) =>
  `http://${config.lan.host}:${config.lan.piWebPort}/?session=${encodeURIComponent(sessionId)}`;
export const consoleLink = (query = "") => {
  const token = config.lan.consoleToken ? `t=${encodeURIComponent(config.lan.consoleToken)}` : "";
  const qs = [token, query].filter(Boolean).join("&");
  return `http://${config.lan.host}:${config.lan.consolePort}/${qs ? `?${qs}` : ""}`;
};
