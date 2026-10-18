---
name: flameox
description: 用 Flameox 采集有界、可复现的运行时证据——CPU/内存/GPU/推理栈的性能剖析，或把一条命令的输出抓成结构化 artifact 供后续分析比对。当用户说"profile 一下 / 性能剖析 / 火焰图 / 找性能瓶颈 / 跑个 benchmark 采数据 / 追踪 trace / 抓一次运行证据 / 对比优化前后"时使用。是 REA 的运行时证据采集侧翼（REA 偏静态与动态逆向，Flameox 偏性能证据）。只做证据采集与对比，不改代码、不下结论。
metadata:
  source: https://github.com/morluto/flameox
  upstream-dir: /tmp 之外的 clone 见仓库 docs/interfaces.md
  mcp-name: io.github.morluto/flameox
---

# Flameox

Flameox 把 profiler、benchmark 工具、trace 处理器和本地目标**收进一个有界的证据边界**：
把明确的 artifact 路径或一条明确的命令，变成带 provenance、覆盖率和限制说明的类型化证据。
它**不执行仓库工作流的编排、不改工程文件、不提供托管服务**。

关键边界：
- 证据分 `observed` / `derived` / `inferred` 三类，报告里必须分开写。
- profile 只能**指导探索**，不能确立因果关系，也不能证明性能提升。
- 要下确定性结论，必须有代表性 workload、声明的指标与 estimand、可比的 identity、
  保留的样本，以及一个语义 oracle。缺哪样就明说缺哪样。

## 先连上

Flameox 是 MCP server + CLI。若本会话里已经有 Flameox 工具，直接用；
没有就告诉用户以下任一条恢复路径（涉及联网/装包，**要用户同意**）：

```bash
npx flameox@latest setup          # 交互式配置 MCP 客户端
npx flameox@latest update --check # 只看有没有新版本，不改配置
uvx flameox mcp serve             # 手动起 stdio MCP server
```

诊断个别客户端：`npx -y flameox@latest setup --client codex --dry-run`（先出计划，不写入）。

## 直接 CLI

```bash
uvx flameox analyze <operation> /absolute/path/to/artifact.json
uvx flameox capture --provider direct --cwd "$PWD" -- python benchmark.py
uvx flameox mcp inspect                       # 看当前工具目录与 schema
uvx flameox mcp inspect --tool <TOOL_NAME>    # 看单个工具的输入/输出
```

**capture 收的是 argv 数组，不是 shell 字符串**；`--cwd` 必须是绝对路径。
要 shell 语义就自己显式套 `sh -c`。

## 工具目录怎么读

- 分析类工具只读且幂等，参数以 `sources` + 操作专属字段 + 可选 `continuation`/`limits`/`page_size` 出现。
- 可采集的操作会同时暴露 `capture_and_<task>`。
- 生命周期工具：`prepare_providers`、`preserve_evidence`、`rescue_evidence`、`query_evidence`、`inspect_evidence`。
- 没有网关工具、没有不透明 options 包。用 `mcp inspect --full` 拿全量 schema，不要凭记忆猜工具名。

## 结果怎么用

- 结果**内联完整返回**（可能有 `next_page`）。有 `next_page` 时按它给的 analysis 工具和参数
  **原样重放**；continuation 只读已采集 artifact，不会重跑目标。
- 有 `evidence_id` 的是持久化证据，用 `inspect_evidence` 取脱敏元数据与重放源。
- `page_size` 是 `limits.max_rows` 的简写，两者同时给必须一致。
- **失败也是类型化产品状态**，不是错误旁路。失败结果里的
  `details.analysis_source_count` 区分"可重放的输入"和"只有诊断、需要先修采集器"。
- 保留证据是**可选**的；不保留时 `analysis_id` 只在会话内有效，server 一停就没了。

## 报告纪律

写结论时保持这些分类可见：静态发现 / 估算 / 实测 / 行为检查 / 未知。
覆盖率缺失或失败**不能报成"干净覆盖"**。不要因为一次 profile 就断言整体加速或复杂度上界。
