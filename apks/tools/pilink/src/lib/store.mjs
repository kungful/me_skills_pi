/**
 * 看门狗状态落盘 + 日志。
 *
 * 状态必须落在进程外（~/.pi/android-link/state.json），
 * 这样 PC 重启/看门狗自己崩掉之后，还能发现"上次有个会话没收尾"。
 */
import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { config, STATE_DIR } from "../config.mjs";

const EMPTY_STATE = {
  version: 1,
  /** 首次运行是否已把历史尾部标记为已知（避免启动时补推一堆旧消息） */
  primed: false,
  /** ${sessionId}:${entryId} → 通知时间戳，保证同一个尾部只推一次 */
  notified: {},
  /** ${sessionId} → { modified, since } 用于卡死检测 */
  active: {},
  /** ${sessionId} → { modified, verdict } 判定缓存，文件没变就不重读 */
  tailCache: {},
  /** 上一次成功轮询时正在跑的会话 id */
  lastRunning: [],
  /** pi-web 连续失败次数 */
  piWebFailures: 0,
  /** 已就 pi-web 失联告警过（避免刷屏） */
  piWebDownNotified: false,
  /** 鉴权连续失败次数（见 lib/piweb.mjs 的 PiWebAuthError 注释） */
  authFailures: 0,
  /** 已就鉴权失败告警过 */
  authNotified: false,
  /** 鉴权失败主动暂停到这个时间戳（毫秒），0 = 没暂停 */
  authGiveUpUntil: 0,
  updatedAt: null,
};

export function loadState() {
  mkdirSync(STATE_DIR, { recursive: true });
  if (!existsSync(config.stateFile)) return structuredClone(EMPTY_STATE);
  try {
    return { ...structuredClone(EMPTY_STATE), ...JSON.parse(readFileSync(config.stateFile, "utf8")) };
  } catch {
    return structuredClone(EMPTY_STATE);
  }
}

export function saveState(state) {
  state.updatedAt = new Date().toISOString();
  // notified 是无界增长的，只留最近 2000 条
  const keys = Object.keys(state.notified);
  if (keys.length > 2000) {
    const trimmed = keys.sort((a, b) => state.notified[a] - state.notified[b]).slice(-1000);
    state.notified = Object.fromEntries(trimmed.map((key) => [key, state.notified[key]]));
  }
  try {
    mkdirSync(dirname(config.stateFile), { recursive: true });
    writeFileSync(config.stateFile, JSON.stringify(state, null, 2), "utf8");
  } catch (error) {
    log(`状态落盘失败: ${error.message}`);
  }
}

export const log = createLogger("watchdog.log");

/**
 * 每个服务写自己的结构化日志，免得三个进程抢同一个文件看不清。
 * @param {string} fileName 相对 STATE_DIR
 */
export function createLogger(fileName) {
  const path = join(STATE_DIR, fileName);
  return function logTo(line) {
    const stamped = `[${new Date().toISOString()}] ${line}`;
    console.log(stamped);
    try {
      mkdirSync(STATE_DIR, { recursive: true });
      appendFileSync(path, `${stamped}\n`, "utf8");
    } catch {
      /* 日志写不进去也不能影响主流程 */
    }
  };
}
