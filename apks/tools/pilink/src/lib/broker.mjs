/**
 * 消息出口：发到派发台自己的中转（/pi/publish），不经过任何第三方推送服务。
 *
 * 字段名沿用之前的线上格式（title/message/priority/click/actions/group），
 * 所以 App 的解析、历史、通知那几层一行都没改。
 *
 * publish() 绝不抛异常：看门狗不能因为推不出去就崩掉。
 */
import { config } from "../config.mjs";

/** 与 pi 的会话状态一一对应，故意和 pi-web 只有一句"任务已完成"的文案区分开 */
export const KIND_STYLE = {
  complete: { priority: 3, tags: ["white_check_mark"], label: "任务完成" },
  model_error: { priority: 5, tags: ["rotating_light"], label: "模型/请求报错中断" },
  aborted: { priority: 2, tags: ["octagonal_sign"], label: "已中止" },
  truncated: { priority: 3, tags: ["scissors"], label: "输出被截断" },
  interrupted_tool: { priority: 5, tags: ["warning"], label: "工具阶段异常中断" },
  stall: { priority: 4, tags: ["snail"], label: "疑似卡死" },
  piweb_down: { priority: 5, tags: ["skull"], label: "pi-web 进程失联" },
  auth_failed: { priority: 5, tags: ["key"], label: "pi-web 认证失败" },
  test: { priority: 3, tags: ["test_tube"], label: "链路测试" },
};

/**
 * @param {object} message
 * @param {string} message.title
 * @param {string} message.body
 * @param {keyof typeof KIND_STYLE} [message.kind]
 * @param {number} [message.priority]
 * @param {string[]} [message.tags]
 * @param {string} [message.click]        点击通知后打开的 URL（深链）
 * @param {Array<object>} [message.actions] 通知动作按钮
 * @param {string} [message.group]        通知分组
 * @returns {Promise<{ok:boolean, id?:string, error?:string}>}
 */
export async function publish(message) {
  const style = KIND_STYLE[message.kind] ?? KIND_STYLE.test;
  const payload = {
    title: message.title,
    message: message.body,
    priority: message.priority ?? style.priority,
    tags: message.tags ?? style.tags,
    click: message.click ?? null,
    actions: message.actions ?? [],
    group: message.group ?? null,
  };

  const base = config.broker.base;
  const query = config.broker.token ? `?t=${encodeURIComponent(config.broker.token)}` : "";
  try {
    const response = await fetch(`${base}/pi/publish${query}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(10_000),
    });
    const text = await response.text();
    if (!response.ok) return { ok: false, error: `HTTP ${response.status}: ${text.slice(0, 200)}` };
    let id;
    try {
      id = JSON.parse(text).id;
    } catch {
      /* 无所谓，只要 2xx */
    }
    return { ok: true, id };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : String(error) };
  }
}
