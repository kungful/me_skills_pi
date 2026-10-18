---
name: morluto-reversing-index
description: morluto（REA 作者）整个逆向工具与知识库生态的导航索引——要装/要连什么、有哪些配套技能、以及 80+ 个逆向与安全资源清单在哪个仓库。当用户说"morluto 还有别的逆向工具吗 / REA 生态 / 装 REA / 有哪些逆向 MCP / 找个逆向知识库 / 这套逆向工具配套都有啥"时使用，或当 `reverse-engineer-anything` 需要配合其它证据工具（性能、崩溃、token、贡献调研）时先读它。
metadata:
  source: https://github.com/morluto
  catalog: references/catalog.md
---

# morluto 逆向生态索引

作者：[morluto](https://github.com/morluto)。代表作 **REA**（`reverse-engineer-anything`）。
本机已经把这条工具链按技能装好了，本技能负责"该用哪个 + 怎么装"。

## 本机已装技能 ↔ 上游仓库

| 技能 | 上游 | 它负责什么 |
|---|---|---|
| `reverse-engineer-anything` | [rea](https://github.com/morluto/rea) | 逆向主力：原生/托管/Electron/JS/固件/浏览器目标，静态 + 运行时证据 |
| `awesome-reverse-engineering` | [awesome-reverse-engineering](https://github.com/morluto/awesome-reverse-engineering) | 逆向工具选型与学习路线（离线清单） |
| `flameox` | [flameox](https://github.com/morluto/flameox) | 有界运行时证据：profiler / benchmark / trace 采集与对比 |
| `smokinggun` | [smokinggun](https://github.com/morluto/smokinggun) | 复杂度热点候选 + 导入式优化证据管理（只读扫描） |
| `leantoken` | [leantoken](https://github.com/morluto/leantoken) | 本地代码索引与省 token 检索 |
| `internalcot` | [internalcot](https://github.com/morluto/internalcot) | 显式开关的"可见思维链"模式（用户明确要求才开） |
| `gitcontribute` | [gitcontribute](https://github.com/morluto/gitcontribute) | 给开源仓库做贡献前的本地调研 |
| `jacobian-math` | [jacobian](https://github.com/morluto/jacobian) | 类型化数学操作库（精确计算 / 结构分析） |
| `generate-social-preview` | [generate-social-preview](https://github.com/morluto/generate-social-preview) | 生成仓库社交预览图（GitHub 社交卡片） |

## 装与连

这些项目统一是 **npm/uvx 一条命令 + MCP server** 形态，且都遵守同一套安全约定：
**先 dry-run 出计划 → 用户同意 → 才写配置**；setup 会把版本钉住；不碰项目文件。

```bash
npx -y rea-agents@latest doctor --client codex --json        # 诊断
npx -y rea-agents@latest setup  --client codex --dry-run --json   # 计划
npx -y rea-agents@latest setup  --client codex --yes         # 执行（需同意）
npx flameox@latest setup
npx leantoken setup && npx leantoken doctor
npx --yes gitcontribute@latest setup
npx internalcot@latest setup
npx smokinggun            # 或 npx --yes --package=smokinggun -- smokinggun scan .
```

**不要自作主张装包。** 缺工具时说明缺哪个、给出确切命令、等用户同意。

## 不在本机技能里的部分

作者还 fork 了 **80+ 个逆向 / 安全资源清单**（web 逆向、Apple 安全、嵌入式安全、
Android AI 逆向、漏洞检测技能目录、红队资源、LLM 辅助逆向、Ghidra 等）。
它们本身是**别人的清单**，逐条做成技能只会污染技能路由，所以统一收录在
[references/catalog.md](references/catalog.md) 里按名字可查。

要用某个清单时：先在 catalog 里定位仓库名，再用 `web-browse` 或
`git clone --depth 1` 取回来读；**不要**凭清单标题猜内容。

另外，`rea` 仓库里还带 4 个**面向 REA 自身开发**的技能（上游路径 `rea/.agents/skills/`）：
`rea-tool-design`（设计 REA 工具与 CLI/MCP 契约）、`rea-analysis-optimization`（分析链路优化）、
`rea-ci-tests-audit`（CI/测试套件审计）、`rea-changelog-update`（发布日志）。
它们只在你改 REA 本体时有用，日常逆向用不到，所以没有装到本机；需要时从那 4 个目录直接读。

## 纪律

- REA 是主力，其它是证据侧翼。性能/复杂度结论走 flameox / smokinggun，
  找代码走 leantoken，**别让 REA 干这些**。
- 所有证据分 `observed` / `derived` / `inferred`；覆盖缺口不能报成"干净"。
- 清单类仓库是**快照**，条目可能已过时；引用前核对上游是否还活着。
