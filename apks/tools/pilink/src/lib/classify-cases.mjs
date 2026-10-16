/**
 * 判定逻辑的共享断言集。verify.mjs 用它做判定单元断言（旧 selftest.mjs 已删除，并入 verify.mjs）。
 */

export const CLASSIFY_CASES = [
  ["正常收尾 stop + 无 toolCall", "complete",
    [{ type: "message", id: "a1", message: { role: "assistant", stopReason: "stop", content: [{ type: "text" }] } }]],
  ["模型报错（带 errorMessage）", "model_error",
    [{ type: "message", id: "a2", message: { role: "assistant", stopReason: "error", errorMessage: "Connection error.", content: [] } }]],
  ["工具没返回结果", "interrupted_tool",
    [{ type: "message", id: "a3", message: { role: "assistant", stopReason: "toolUse", content: [{ type: "toolCall" }] } }]],
  ["工具返回了但 agent 没接上（末条 toolResult）", "interrupted_tool",
    [{ type: "message", id: "a4", message: { role: "assistant", stopReason: "toolUse", content: [{ type: "toolCall" }] } },
     { type: "message", id: "t1", message: { role: "toolResult", toolName: "bash" } }]],
  ["末条是元数据写入，要往前找 assistant", "complete",
    [{ type: "message", id: "a5", message: { role: "assistant", stopReason: "stop", content: [{ type: "text" }] } },
     { type: "model_change", id: "m1", provider: "x", modelId: "y" },
     { type: "thinking_level_change", id: "l1", thinkingLevel: "high" }]],
  ["被中止", "aborted",
    [{ type: "message", id: "a6", message: { role: "assistant", stopReason: "aborted", content: [{ type: "thinking" }] } }]],
  ["stop=stop 却挂着 toolCall（落盘被切断）", "interrupted_tool",
    [{ type: "message", id: "a7", message: { role: "assistant", stopReason: "stop", content: [{ type: "toolCall" }] } }]],
  ["输出超长被截断", "truncated",
    [{ type: "message", id: "a8", message: { role: "assistant", stopReason: "length", content: [{ type: "text" }] } }]],
  ["全是元数据、没有 assistant", null,
    [{ type: "model_change", id: "m2" }, { type: "thinking_level_change", id: "l2" }]],
];

/** @param {(entries: unknown[]) => {kind: string} | null} classify */
export function runClassifyCases(classify) {
  const results = CLASSIFY_CASES.map(([name, expect, entries]) => {
    let got = null;
    try {
      got = classify(entries)?.kind ?? null;
    } catch (error) {
      got = `抛异常: ${error.message}`;
    }
    return { name, expect, got, ok: got === expect };
  });
  return { results, failed: results.filter((r) => !r.ok).length };
}
