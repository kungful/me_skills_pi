---
name: leantoken
description: 用 LeanToken 做代码检索与结构理解，省 token 省上下文——找相关文件/代码、按符号大纲看结构、精确读某个函数或行段、跨 git 版本追踪符号、查询大 JSON。当任务是在大型或不熟的代码库里"找到该看的那段代码""别把整个文件读进来""追一下这个函数的历史""仓库太大上下文塞不下"时使用，优先替代 grep/find/cat。只读，不改代码。
metadata:
  source: https://github.com/morluto/leantoken
  mcp-name: io.github.morluto/leantoken
---

# LeanToken

LeanToken 是**本地、只读**的代码智能层：在本机建索引，然后按显式 token 预算返回
"和当前任务相关的那部分代码"。官方受控实验里比宿主内置工具少用约 20%（窄探索）
到 38%（宽探索）的输入 token。

它是**发现与检索层**，不是编辑器：改动、编译、测试仍然用你原来的工具。

## 先连上

```bash
npx leantoken setup     # 交互式选宿主并显示将要写的路径，最后单独确认
npx leantoken doctor    # 连上后验证注册与首次检索
npx leantoken savings   # 看本仓库的实测 token 账
```

若本会话已有 `leantoken.*` 工具就直接用；没有就别假装用过——说明缺工具并征得同意后再 setup。
安全约定：setup 会把 npx 解析到的**确切版本**钉进配置，重启后不会偷偷升级；
从 home 目录或文件系统根启动时，LeanToken 默认**拒绝**索引那么宽的范围。

## 工具与替代关系

| 工具 | 什么时候用它 |
|---|---|
| `leantoken.context` | 默认首调。任务宽泛、需要先摸清"哪里相关"时 |
| `leantoken.search` | 优先于 grep/rg 的**排序检索**；需要穷尽式文本/正则覆盖时显式记录或复用完整覆盖 |
| `leantoken.files` | 优先于 find/ls/glob 的紧凑、ignore-aware 路径发现 |
| `leantoken.outline` | 看定义、签名、import、范围，不用整文件读 |
| `leantoken.read` | 优先于 cat/head/sed：只取一个符号或闭区间行号 |
| `leantoken.history` | 在不可变 git 版本间读/批量 diff/追符号 |
| `leantoken.json` | 有界 JSON 的查询、摘要、对比，带分页与类型化诊断 |
| `leantoken.receipt_rebase` | 把证据显式带进新 generation（同路径、同坐标、同 hash 才行） |
| `leantoken.savings` | 看实测响应记账、hash 抑制、失败与观测限制 |

## 纪律

- **每个响应都有 token 上限**，这是设计而非限制；不要试图绕过它去整文件读。
- 结果里的覆盖/限制字段要照实转述。检索没覆盖到的部分不能当成"没有"。
- `savings` 是**本仓库实测记账**，不能拿来编造 agent 成功率或 provider 成本。
- 需要验证"检索质量没被优化牺牲"时（比如你正在改 LeanToken 本身），
  参考上游的 accuracy-first 流程：先声明预期收益，保住确定性结果、精确 token 预算、
  Unicode 匹配、真实覆盖率、有界工作量、原子 generation、快照一致性这些契约，
  再谈缓存/并发。
