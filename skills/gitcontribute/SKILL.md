---
name: gitcontribute
description: 用 GitContribute 做"给开源仓库贡献"的前期调研——判断某个 issue 还值不值得做、有没有人在做、适不适合外部贡献者、有没有足够证据动手，以及收集仓库贡献规范、相关 issue/PR、代码上下文和验证结果。当用户说"给这个仓库提个 PR / 这个 issue 我能做吗 / 找点能贡献的活 / 看看有没有重复实现 / 调研一下 owner/repo#123 / 提 PR 前先查清楚"时使用。它**从不写 GitHub**，只出本地调研和草稿。
metadata:
  source: https://github.com/morluto/gitcontribute
---

# GitContribute

GitHub 能告诉你有哪些 open issue，但**不能**告诉你：这个 issue 是否仍相关、是否已有人在实现、
是否适合外部贡献者、证据是否足够安全动手。GitContribute 把这些收进本地 SQLite 语料库：
仓库规范、相关 issue 与 PR、代码上下文、被接受的贡献模式、验证结果，并标出**缺失或过期的覆盖**。

流程：`找活 -> 理解它 -> 查有没有人在做 -> 证明改动 -> 准备交接`

> 硬约束：GitContribute **从不往 GitHub 写任何东西**。它只准备本地调研和草稿，由你复核。

## 先连上 / 安装

```sh
npx --yes gitcontribute@latest setup   # 选 MCP / CLI / Both；应用前会展示每一处改动
```

- 想给 agent 用 → 选 MCP。想用终端和 TUI → 选 CLI。都要 → Both。
- setup 里"添加仓库"**不会**联网、不会启动同步。
- 手动起 stdio server：`gitcontribute mcp serve --transport=stdio`
- 只读模式（去掉允许联网/本地写/执行的工具）：加 `--read-only`

MCP 端是一个统一目录；Codex / Claude Code 这类宿主能原生搜索大目录，所以不要求用户预先选能力档。

## 常用动作

| 任务 | Agent 说法 | CLI |
|---|---|---|
| 找候选贡献点 | 「在 owner/repo 找贡献候选，按 fit、证据、范围、协作风险排序」 | `gitcontribute archive sync owner/repo`<br>`gitcontribute radar owner/repo --limit 10` |
| 调研某个 issue | 「调研 owner/repo#42：规范、讨论、代码、既有修复、竞争工作、缺失证据」 | `gitcontribute archive sync owner/repo --numbers 42`<br>`gitcontribute research brief issue:owner/repo#42` |

## 纪律

- 输出必须带**来源引用、覆盖缺口和下一步建议**；覆盖不到就说覆盖不到。
- 别把"没搜到竞争工作"说成"没人做过"——那是覆盖缺口。
- GitHub 用户是一等 actor：身份、profile、社交账号、组织、pinned、仓库、贡献事实
  各自独立同步，各有自己的新鲜度。
- 需要联网同步或带 token 时，先跟用户说清楚要访问什么、用哪个 token 来源；
  不确定就用 `--token-source none`。
