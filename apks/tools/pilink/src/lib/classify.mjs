/**
 * 会话尾部判定 —— 纯函数 + 一个有界读取器。这是整条链路的判据，不靠"看起来对"。
 *
 * 判据来自对 234 个真实会话文件（34903 条 message）的实测统计：
 *   197x  assistant(stop=stop,     toolCalls=0)   → 正常收尾
 *    13x  assistant(stop=error,    toolCalls=0)   → 模型/请求报错中断（带 errorMessage）
 *     7x  assistant(stop=aborted,  toolCalls=0)   → 被中止
 *     5x  assistant(stop=toolUse,  toolCalls>0)   → 工具阶段被打断（真·异常中断）
 *     1x  末条是 toolResult                       → 工具跑完了 agent 却没继续
 *  另有 11x 末条是 model_change / thinking_level_change / custom 等元数据写入，
 *  这些不算会话进度，往前找最后一条 assistant 判定。
 *
 * 核心思路：不要看"最后一行是什么"，而是**往前找最后一条 assistant 消息**，
 * 用它的 stopReason + 是否有未闭合的 toolCall 来判定。这样"末条是 toolResult"
 * 和"末条是带 toolCall 的 assistant"自然被同一条规则覆盖。
 */
import { closeSync, openSync, readSync, statSync } from "node:fs";

/** 不算会话进度的元数据条目，判定时跳过 */
const METADATA_TYPES = new Set([
  "model_change",
  "thinking_level_change",
  "session_info",
  "custom",
  "custom_message",
  "compaction",
]);

/** stopReason → 判定结果 */
const STOP_REASON_KIND = {
  stop: "complete",
  error: "model_error",
  aborted: "aborted",
  length: "truncated",
  toolUse: "interrupted_tool",
};

/**
 * @param {Array<Record<string, unknown>>} entries 会话文件按写入顺序解析出的条目
 * @returns {null | {
 *   kind: "complete"|"model_error"|"aborted"|"truncated"|"interrupted_tool",
 *   reason: string, entryId: string|null, stopReason: string|null,
 *   errorMessage: string|null, pendingToolCalls: number,
 *   turn: {entryId: string|null} | null,
 * }}
 */
export function classifyEntries(entries) {
  for (let index = entries.length - 1; index >= 0; index -= 1) {
    const entry = entries[index];
    const message = entry?.message;

    // 跳过元数据写入，继续往前找
    if (entry?.type !== "message" || message?.role !== "assistant") {
      if (entry?.type && METADATA_TYPES.has(entry.type)) continue;
      // 末条是 toolResult：说明工具已返回但 agent 没接上。继续往前找那条
      // toolUse 归属的 assistant，判定结果会是 interrupted_tool。
      if (entry?.type === "message" && message?.role === "toolResult") continue;
      if (entry?.type === "message") continue; // user / system 等，继续往前找
      continue;
    }

    const content = Array.isArray(message.content) ? message.content : [];
    const pendingToolCalls = content.filter((block) => block?.type === "toolCall").length;
    const stopReason = typeof message.stopReason === "string" ? message.stopReason : null;

    let kind = STOP_REASON_KIND[stopReason] ?? null;

    // stop=stop 却还挂着 toolCall → 落盘被切断，按异常处理
    if (kind === "complete" && pendingToolCalls > 0) kind = "interrupted_tool";
    // toolUse 但没有 toolCall 内容 → 数据异常，别乱报
    if (kind === "interrupted_tool" && pendingToolCalls === 0) kind = "complete";
    if (!kind) return null;

    // 末条 entry 是 toolResult 还是别的，决定中断发生在工具执行中还是之后
    const lastEntry = entries.at(-1);
    const lastIsToolResult =
      lastEntry?.type === "message" && lastEntry?.message?.role === "toolResult";

    let reason;
    switch (kind) {
      case "complete":
        reason = "正常收尾";
        break;
      case "model_error":
        reason = message.errorMessage ? `模型报错：${message.errorMessage}` : "模型报错中断";
        break;
      case "aborted":
        reason = message.errorMessage ? `已中止：${message.errorMessage}` : "已中止";
        break;
      case "truncated":
        reason = "输出达到长度上限被截断";
        break;
      case "interrupted_tool":
        reason = lastIsToolResult
          ? `${pendingToolCalls} 个工具已返回结果，但 agent 没有继续`
          : `${pendingToolCalls} 个工具调用没有返回结果`;
        break;
      default:
        reason = kind;
    }

    return {
      kind,
      reason,
      entryId: typeof entry.id === "string" ? entry.id : null,
      stopReason,
      errorMessage: typeof message.errorMessage === "string" ? message.errorMessage : null,
      pendingToolCalls,
      turn: lastEntry?.id ? { entryId: lastEntry.id } : null,
      interruptedAfterTool: kind === "interrupted_tool" && lastIsToolResult,
    };
  }
  return null;
}

/**
 * 只读文件尾部 windowBytes 字节，解析出条目。绝不整文件读进来。
 * 会话文件可能几十 MB（实测有一个 3.34MB 的），每 15s 读一次全量不可接受。
 */
function readWindow(filePath, windowBytes) {
  const fd = openSync(filePath, "r");
  try {
    const info = statSync(filePath);
    const start = Math.max(0, info.size - windowBytes);
    const buffer = Buffer.allocUnsafe(info.size - start);
    const read = readSync(fd, buffer, 0, buffer.length, start);
    if (read <= 0) return { entries: [], start, size: info.size, mtimeMs: info.mtimeMs };

    const lines = buffer.subarray(0, read).toString("utf8").split("\n");
    // 从文件中间切进来的第一行必然是残行，丢掉
    if (start > 0) lines.shift();
    if (lines.at(-1) === "") lines.pop();

    const entries = [];
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        entries.push(JSON.parse(line));
      } catch {
        // 正在写入的残行，忽略
      }
    }
    return { entries, start, size: info.size, mtimeMs: info.mtimeMs };
  } finally {
    closeSync(fd);
  }
}

/**
 * 自适应窗口的尾部判定。
 *
 * 为什么必须自适应：单条 JSON 条目可能比窗口还大。实测有一个会话的末条
 * assistant 消息有 85902 字节，而默认窗口是 65536 —— 整个窗口全落在那一条
 * 里面，split 出来全是残行，一条都解析不了，于是误判为 null（"无法判定"）。
 * 所以解析不出结论时把窗口乘 4 重试，直到够到文件头或封顶。
 *
 * @returns {null | object} 失败返回 null
 */
export function readAndClassify(filePath, initialBytes = 65_536, options = {}) {
  const maxBytes = options.maxBytes ?? 32 * 1024 * 1024;
  const growth = options.growth ?? 4;
  let window = initialBytes;

  for (;;) {
    let result;
    try {
      result = readWindow(filePath, window);
    } catch {
      return null;
    }
    const verdict = classifyEntries(result.entries);
    if (verdict) {
      return { ...verdict, size: result.size, mtimeMs: result.mtimeMs, windowUsed: window };
    }
    // 已读到文件头 / 已封顶 / 窗口已覆盖整个文件 → 再放大也没意义
    if (result.start === 0 || window >= maxBytes || result.size <= window) return null;
    window = Math.min(window * growth, maxBytes);
  }
}

/** 读取会话头部的 cwd / 创建时间（给通知标题用） */
export function readSessionHeader(filePath) {
  let fd;
  try {
    fd = openSync(filePath, "r");
    const buffer = Buffer.allocUnsafe(4096);
    const read = readSync(fd, buffer, 0, buffer.length, 0);
    const firstLine = buffer.subarray(0, read).toString("utf8").split("\n")[0];
    const header = JSON.parse(firstLine);
    return { id: header.id ?? null, cwd: header.cwd ?? null, createdAt: header.timestamp ?? null };
  } catch {
    return null;
  } finally {
    if (fd !== undefined) closeSync(fd);
  }
}
