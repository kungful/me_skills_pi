---
name: mcp-registry
description: 从本机 Pi 的 skills 仓库还原/补齐整套 MCP 服务（playwright 浏览器自动化、blender、kicad、freecad、solidcraft、videostudio、douyin、xiaohongshu、aihot）。当用户说"装 MCP / 装 playwright MCP / 还原 MCP 配置 / mcp.json 备份到仓库 / 换机器把 MCP 一起部署 / 有哪些 MCP 服务能用 / 这个仓库里的 MCP 怎么装"时使用。
---

# MCP 服务注册表（mcp-registry）

Pi 用的 MCP 服务**唯一事实源是一份 JSON**，跟着 skills 仓库一起走：

| 位置 | 作用 |
|---|---|
| `<repo>/mcp/index.json` | 注册表：每个服务的 launch 方式、依赖、工具数、注意事项 |
| `<repo>/mcp/install.py` | 安装器：体检 → 幂等合并进 `~/.pi/agent/mcp.json` |
| `<repo>/mcp/README.md` | 人读的完整说明 |
| `~/.pi/agent/mcp.json` | Pi 实际读取的配置（安装器的目标） |

本机仓库路径：`~/.pi/skills-repo`（远端 `github.com/kungful/me_skills_pi`）。
换机器就 `git clone` 后跑下面的命令，别手抄配置。

## 安装 / 补齐（最常用）

```bash
R=<repo>            # 本机是 ~/.pi/skills-repo
python $R/mcp/install.py --list                  # 清单
python $R/mcp/install.py                         # 预演：能装哪些、缺什么
python $R/mcp/install.py --apply                 # 写进 ~/.pi/agent/mcp.json
python $R/mcp/install.py --apply --install-deps   # 顺手 npm i -g 缺的包
python $R/mcp/install.py --show playwright       # 看单个服务的完整要求
```

行为保证：默认只预演；写前自动备份 `mcp.json.bak-<时间戳>`；**同名条目绝不覆盖**（除非 `--force`）；
`localOnly` 的服务只体检不写坏路径。装完在 pi 里 `/reload`，再 `pi mcp list` 验证。

## 现有服务一览

| 服务 | 工具 | 可移植 | 干什么 |
|---|---:|---|---|
| `playwright` | 25 | ✅ | 真实 Chrome：点击/填表/多标签/截图/读无障碍树/跑 JS/看 console 与 XHR |
| `blender` | 9 | ✅ | 控制 Blender 场景（addon socket 127.0.0.1:9876） |
| `xiaohongshu` | 18 | ✅* | 小红书发布/搜索/评论（本机 127.0.0.1:18060 服务需在跑） |
| `aihot` | 8 | ✅ | AI 资讯（远程） |
| `kicad` | 233 | ⚠️ | KiCad PCB 全流程 + Gerber/BOM 导出 |
| `freecad` | 17 | ⚠️ | FreeCAD 参数化建模 + FEM |
| `solidcraft` | 15 | ⚠️ | 参数化 3D CAD → STEP/3MF/STL/URDF |
| `videostudio` | 28 | ⚠️ | 自动剪辑：Concat + edge-tts + 配乐 + Whisper 字幕 |
| `douyin` | 29 | ⚠️ | 抖音解析/下载/转文案/发布/数据/评论 |

⚠️ 的用 `--var NAME=VALUE` 或环境变量喂占位符，见 `index.json` 里对应的 `requires.placeholders`。

## playwright 换模式（改 args 即可）

`--browser chrome`（默认，复用系统 Chrome）· `--headless` · `--isolated` ·
`--cdp-endpoint <url>`（接管正在用的 Chrome，带登录态）· `--mobile` ·
`--snapshot-mode none`（大页面省 token）· `--output-dir <path>` · `--proxy-server` · `--secrets <dotenv>`

## 给脚本/agent 的接口

```bash
python $R/mcp/install.py --json    # stdout 纯 JSON：written[]/blocked[]/servers[]{status,missing,config}
python $R/mcp/install.py --quiet   # 最后一行 [mcp-install] RESULT applied|no-change|dry-run|failed
```

## 加新服务

在 `index.json` 的 `servers[]` 追加一条（`launch.type` ∈ `npm-global-bin` / `uvx` / `http` / `static`），
本机专属的标 `localOnly: true` + `requires.placeholders`，然后
`python mcp/install.py --show <name>` 验证，提交推送。不要手改别处的配置副本。
