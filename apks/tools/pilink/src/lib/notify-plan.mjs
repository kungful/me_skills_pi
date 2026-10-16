/**
 * 「判定结果 → 手机上那句话」的纯函数映射。
 *
 * 单独抽出来是为了能被 verify.mjs 逐个断言：完整链路测试只能覆盖到
 * 近期真实存在的会话，而 36 小时窗口里恰好全是 complete，覆盖不到
 * 报错/中止/工具中断这几条。判定逻辑不靠"恰好跑到了"来验证。
 */
import { basename } from "node:path";

/** 判定结果 → 通知正文前缀 */
export const KIND_LABEL = {
  complete: "任务完成",
  model_error: "模型/请求报错中断",
  aborted: "已中止",
  truncated: "输出被截断",
  interrupted_tool: "异常中断",
};

/**
 * 标题：项目名 · 首条消息摘要。
 * 手机锁屏上一眼能认出是哪个项目的哪个活。
 */
export function notificationTitle(session, header) {
  const project = basename(header?.cwd ?? session?.cwd ?? "?") || "?";
  const first = String(session?.firstMessage ?? "").replace(/\s+/g, " ").trim();
  const snippet = first.length > 26 ? `${first.slice(0, 26)}…` : first;
  return snippet ? `${project} · ${snippet}` : project;
}

/**
 * @param {{kind:string, reason:string}} verdict 来自 lib/classify.mjs
 * @returns {null | {kind:string, title:string, body:string}}
 */
export function planNotification(verdict, session, header) {
  const label = KIND_LABEL[verdict?.kind];
  if (!label) return null;
  return {
    kind: verdict.kind,
    title: notificationTitle(session, header),
    body: `${label} · ${verdict.reason}`,
  };
}

export function planStall(session, header, quietMinutes) {
  return {
    kind: "stall",
    title: notificationTitle(session, header),
    body: `疑似卡死 · 会话仍在运行，但已经 ${quietMinutes} 分钟没有任何写入`,
  };
}

export function planPiWebDown(runningCount, firstSessionId) {
  return {
    kind: "piweb_down",
    title: "pi-web 进程失联",
    body: `有 ${runningCount} 个会话正在跑，但 pi-web 已经连不上了。大概率是进程被杀或机器重启。`,
    sessionId: firstSessionId,
  };
}

/**
 * 密码/鉴权出问题。这条很重要：pi-web 的登录限流是全局共享的，
 * 看门狗如果拿着错密码持续轮询，会把限流刷满，导致用户自己也无法用浏览器登录。
 * 所以必须在通知里说清楚原因，并提醒检查 local.json 与 PI_WEB_PASSWORD 是否一致。
 */
export function planAuthFailed({ throttled, attempts, passwordConfigured, configPath }) {
  return {
    kind: "auth_failed",
    title: "pi-web 认证失败，看门狗已停手",
    body: throttled
      ? `连续 ${attempts} 次被 pi-web 的登录限流拦住（HTTP 429）。为避免把限流刷满（连你自己浏览器都登不进去），看门狗已主动暂停 30 分钟。修法：对齐 ${configPath} 的 piWeb.password 与 pi-web 的 PI_WEB_PASSWORD，然后带 --force 重启看门狗。`
      : `连续 ${attempts} 次密码被拒（HTTP 401）。${passwordConfigured ? "local.json 里的密码与 pi-web 启动时的 PI_WEB_PASSWORD 不一致。" : "看门狗没配密码，但 pi-web 要求鉴权。"}看门狗已主动暂停 30 分钟。修法：对齐 ${configPath} 的 piWeb.password 与 pi-web 的 PI_WEB_PASSWORD，然后带 --force 重启看门狗。`,
  };
}
