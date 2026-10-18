---
name: awesome-reverse-engineering
description: 逆向工程工具与学习资源选型索引（二进制、App、固件、文件格式、协议）。当需要"逆向 / 反编译 / 反汇编 / 脱壳 / 抓包分析协议 / 分析固件 / 分析恶意样本 / 该用哪个工具 / 有没有 xx 逆向工具"，或要在 IDA、Ghidra、radare2、Frida、JADX、Hopper、x64dbg、dnSpy、Wireshark、binwalk、QEMU 之间做选择时使用。也可用于查逆向学习路线与练习靶场。
metadata:
  source: https://github.com/morluto/awesome-reverse-engineering
  vendored: references/FULL-LIST.md
---

# Awesome Reverse Engineering（选型索引）

这是 morluto 维护的逆向工具清单在本地的离线副本，作用是**先选对工具/路线，再动手**。
它本身不执行任何分析；要真正跑 REA 走 `reverse-engineer-anything` 技能。

## 怎么用

1. **按任务找工具**：先读 [references/FULL-LIST.md](references/FULL-LIST.md) 的
   `## Start here` 表——它把"我要做的事"映射到章节。
2. **按章节取工具**：`grep` 章节标题定位，例如要读原生代码就查 `## Native analysis`
   与 `## Debuggers`。
3. **需要更细的取舍**时再读补充材料：
   - [references/priority-candidates.md](references/priority-candidates.md)：候选工具优先级评估
   - [references/list-review.md](references/list-review.md)：清单质量复核记录
   - [references/browser-tools-review.md](references/browser-tools-review.md)：浏览器/Web 逆向工具评测
4. **确认工具仍可用**：清单是快照。真正安装或下载前，用 `web-browse` 或
   `git ls-remote`/`curl` 核对上游是否还在维护，别把过时工具当现成方案报给用户。

## 章节速查

| 你的任务 | 章节 |
|---|---|
| 学汇编与逆向基础 | Learning → Books |
| 判断文件类型与能力 | File identification and triage |
| 读原生代码 / 单步调试 | Native analysis、Debuggers |
| 跟踪调用、插桩运行中的程序 | Dynamic instrumentation and tracing |
| 分析可疑文件、进程、内存镜像 | Malware analysis |
| APK / .NET / Java | Android and managed code |
| iOS、macOS、Apple 固件 | iOS and macOS |
| Python、Go、Unity、Godot、混淆 .NET 脱壳 | Language runtimes and packagers |
| 浏览器行为、未公开协议 | Web and protocols |
| 固件提取、硬件、二进制格式 | Firmware and hardware、File formats |
| 版本对比、自动化分析框架 | Diffing and analysis frameworks |
| LLM 辅助分析 | AI-assisted analysis |
| 练习靶场与社区 | Practice and communities |

## 约定

- 清单里标 **commercial** 的是商业工具；推荐前先说明这一点（涉及花钱要用户同意）。
- 工具未经验证就不要说"能直接拿来用"。未实测的能力、未跑过的命令，都要标成"未验证"。
- 本技能只做选型与路线建议；具体证据链、覆盖缺口、可信度标注按
  `reverse-engineer-anything` 的规则来。
