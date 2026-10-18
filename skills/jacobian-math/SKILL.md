---
name: jacobian-math
description: 当精确计算或结构分析能帮助解题时，用 Jacobian（`math.find` / `math.run`）的类型化数学操作。当用户说"精确算一下 / 符号计算 / 矩阵分解 / 组合枚举 / 数论 / 验证这个数学结论 / 有什么数学操作可用"时使用。Use Jacobian’s typed operations when exact computation or structural analysis can help solve a mathematical problem.
---

# Jacobian Math Tools

Jacobian is a local library of typed mathematical operations for computation and
structural analysis.

Use `math.find` as the library-navigation tool: search for a desired outcome,
browse an unfamiliar domain, or inspect an operation's schema and examples.
Use `math.run` to execute a selected operation and obtain its typed result.
Feed results into later reasoning, further Jacobian operations, or Python
scratch work as useful.

The operations are composable. Choose the representation, decomposition, order
of operations, and stopping point that fit the problem. Reach for the library
proactively when exact computation, finite search, or structural analysis may
help.
