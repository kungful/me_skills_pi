/**
 * pi-web HTTP 客户端。
 * pi-web 在 Proxy 层对 /api/* 接受 Basic Auth（用户名固定 pi），见 proxy.ts:53。
 * Basic 认证成功不会累加限流计数（proxy.ts:61 只在失败时 recordAuthFailure），
 * 所以守护进程可以放心地每 15s 轮询。
 */
import { config, piWebUrl } from "../config.mjs";

/**
 * pi-web 的密码鉴权失败（401 / 429）。
 *
 * 为什么需要专门的错误类型：pi-web 的鉴权限流是**全局共享**的
 * （lib/auth-throttle.ts：所有失败共用一个计数器，且默认它需要 5 分钟无失败
 * 才重置；被限流期间**连正确密码也一律拒给访问**）。而看门狗每 15s 就要打一次 API，
 * 所以一旦 local.json 里的密码与 PI_WEB_PASSWORD 不一致，看门狗会把限流刷满，
 * 后果是**用户自己用浏览器也登不进 pi-web**。
 * 见 proxy.ts:53 —— 命中限流时直接返回 429，不验密码。
 */
export class PiWebAuthError extends Error {
  constructor(status, retryAfterMs, detail) {
    super(detail);
    this.name = "PiWebAuthError";
    this.status = status;
    this.retryAfterMs = retryAfterMs;
    this.throttled = status === 429;
  }
}

function headers(extra = {}) {
  const h = { ...extra };
  if (config.piWeb.password) {
    h.Authorization = `Basic ${Buffer.from(`pi:${config.piWeb.password}`, "utf8").toString("base64")}`;
  }
  return h;
}

async function request(path, { method = "GET", body, timeoutMs = 8_000 } = {}) {
  const response = await fetch(piWebUrl(path), {
    method,
    headers: headers(body ? { "Content-Type": "application/json" } : {}),
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(timeoutMs),
  });
  const text = await response.text();

  if (response.status === 401 || response.status === 429) {
    const retryAfterMs = Number(response.headers.get("retry-after") ?? 0) * 1000;
    throw new PiWebAuthError(
      response.status,
      Number.isFinite(retryAfterMs) ? retryAfterMs : 0,
      `pi-web ${method} ${path} → HTTP ${response.status}: ${text.slice(0, 200)}`,
    );
  }

  if (!response.ok) {
    const error = new Error(`pi-web ${method} ${path} → HTTP ${response.status}: ${text.slice(0, 300)}`);
    error.status = response.status;
    throw error;
  }
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`pi-web ${method} ${path} 返回的不是 JSON: ${text.slice(0, 200)}`);
  }
}

/**
 * GET /api/sessions 一次拿全：
 *   sessions[]                        — id / path / cwd / modified / messageCount / firstMessage
 *   runningSessionIds[]               — 进程内真相：此刻真正在跑的会话
 *   completionNotificationSuppressedSessionIds[] — 子代理等被抑制推送的会话
 */
export function listSessions() {
  return request("/api/sessions", { timeoutMs: 15_000 });
}

/** 轻量心跳，只想知道 pi-web 还活着没 */
export function getRunning() {
  return request("/api/agent/running", { timeoutMs: 5_000 });
}

/**
 * 派发新会话：POST /api/agent/new
 * 注意 cwd 必须真实存在，否则 400。
 */
export function startSession({ cwd, message, provider, modelId, thinkingLevel, toolNames }) {
  const body = { cwd, type: "prompt", message };
  if (provider && modelId) Object.assign(body, { provider, modelId });
  if (thinkingLevel) body.thinkingLevel = thinkingLevel;
  if (toolNames) body.toolNames = toolNames;
  return request("/api/agent/new", { method: "POST", body, timeoutMs: 30_000 });
}

/** 往已有会话追加一条 prompt（接力派发） */
export function sendToSession(sessionId, message) {
  return request(`/api/agent/${encodeURIComponent(sessionId)}`, {
    method: "POST",
    body: { type: "prompt", message },
    timeoutMs: 30_000,
  });
}
