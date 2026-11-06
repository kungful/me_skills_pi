# MCP 服务套件

本机 Pi 用的 MCP（Model Context Protocol）服务全集，**clone 本仓库就能在另一台机器还原同一套工具**。

- 注册表（机器可读）：[`index.json`](index.json) —— 每个服务的启动方式、依赖、可用工具数、注意事项
- 安装器：[`install.py`](install.py) —— 体检 + 幂等合并进 `~/.pi/agent/mcp.json`
- 不需要 Pi 也能读：`index.json` 是纯 JSON，任何 agent 直接 grep 名字/描述/tags 就能找到该装什么

## 一条命令装齐

```bash
git clone <本仓库> /tmp/pi-repo

# 只装可移植的（不碰本机专属服务）
python /tmp/pi-repo/mcp/install.py --list                    # 看有什么
python /tmp/pi-repo/mcp/install.py                           # 预演，什么都不改
python /tmp/pi-repo/mcp/install.py --apply                   # 真的写进 ~/.pi/agent/mcp.json
python /tmp/pi-repo/mcp/install.py --apply --install-deps    # 顺手 npm i -g 缺的包
```

装完在 pi 里 `/reload`（或重开会话），再 `pi mcp list` 确认连上。

**安全**：默认只预演；写之前会自动把原 `mcp.json` 备份成 `mcp.json.bak-<时间戳>`；
**同名条目一律不覆盖**（除非 `--force`）；从不改注册表和其它文件。

## 服务清单

| 服务 | 传输 | 工具 | 可移植 | 干什么 |
|---|---|---:|---|---|
| `playwright` | stdio | 25 | ✅ | 真实 Chrome：点击/填表/多标签/截图/读无障碍树/跑 JS/看 console 与 XHR。后台无 API 的站、渲染后抓数据、前端 bug 复现 |
| `blender` | stdio | 9 | ✅ | 经 addon socket 控制 Blender 场景 |
| `xiaohongshu` | http | 18 | ✅* | 小红书发布/搜索/评论（需本机 127.0.0.1:18060 服务在跑） |
| `aihot` | http | 8 | ✅ | AI 资讯（远程，无本地依赖） |
| `kicad` | stdio | 233 | ⚠️ | KiCad PCB 全流程：器件/布线/DRC/导出 Gerber/BOM/JLCPCB 库 |
| `freecad` | stdio | 17 | ⚠️ | FreeCAD 参数化建模 + FEM（需本机装 FreeCAD 与 RPC addon） |
| `solidcraft` | stdio | 15 | ⚠️ | 参数化 3D CAD，导出 STEP/3MF/STL/URDF |
| `videostudio` | stdio | 28 | ⚠️ | 自动剪辑：Concat + edge-tts + 配乐 + Whisper 字幕 + ffmpeg |
| `douyin` | stdio | 29 | ⚠️ | 抖音解析/下载/转文案/发布/数据/评论 |

✅ = 纯依赖公共包或远程地址，`--apply` 直接可用
⚠️ = `localOnly`，需要本机先备好源码或可执行文件；安装器只体检，**不会**替你写坏路径

## 本机专属服务怎么装

每个 `localOnly` 服务在 `index.json` 里都有一组 `{占位符}` 和 `requires.placeholders` 说明。给它赋值即可：

```bash
python mcp/install.py --all --apply \
  --var KICAD_MCP_SERVER="C:/path/to/KiCAD-MCP-Server" \
  --var KICAD_PYTHON="D:/app/kicad/bin/python.exe" \
  --var KICAD_PYTHONPATH="D:/app/kicad/bin/Lib/site-packages"
```

也可以走环境变量（同名优先）：

```bash
set DOUYIN_MCP=C:/Users/hua/Documents/备份代码/douyin-mcp-fusion
python mcp/install.py --server douyin --apply
```

`--var` 也可以用来看某个服务的完整要求：

```bash
python mcp/install.py --show kicad
```

## 给其它 agent 的接口

```bash
python mcp/install.py --json          # stdout 是纯 JSON 报告（RESULT 行让位到 stderr）
python mcp/install.py --list          # 人类可读清单
python mcp/install.py --show NAME     # 单个服务的配置片段 + 缺什么
```

`--json` 报告字段：`configPath` / `applied` / `backup` / `written[]` / `blocked[]` / `servers[]{name,status,missing[],config}`
`status` ∈ `ready` | `exists` | `blocked`。

进度输出带 `--quiet` 时只留最后一行 `[mcp-install] RESULT <state>`，
state ∈ `applied` / `no-change` / `dry-run` / `failed`，方便脚本判断。
退出码：`0` 就绪或无变化，`1` 有服务装不上，`2` 注册表/配置读写失败。

## playwright 服务的常用开关

配置里 `args` 换一行就能换模式（改完 `--apply --force --server playwright` 或手改 `mcp.json`）：

| 开关 | 作用 |
|---|---|
| `--browser chrome` | **默认**。复用系统已装 Chrome/Edge，不用下 Chromium（省 200MB+） |
| `--headless` | 无头，不弹窗 |
| `--isolated` | profile 只放内存，用完即忘 |
| `--cdp-endpoint <url>` | **接管你正在用的 Chrome**，带全部登录态 |
| `--extension` | 连已有浏览器实例（需装 Playwright Extension） |
| `--mobile` / `--device "iPhone 15"` | 移动端页面，顺带省 token |
| `--snapshot-mode none` | 大页面时省 token，配合 `browser_evaluate` 定向取数据 |
| `--output-dir <path>` | 截图/快照别落到启动目录的 `.playwright-mcp/` |
| `--proxy-server socks5://...` | 走代理 |
| `--secrets <dotenv>` + `--redact-url-params` | 密码/token 不进模型上下文 |
| `--caps vision,pdf,devtools` | 开 PDF、devtools 等额外能力 |

**它不做的事**：不解验证码、不保证过风控与指纹检测、默认不带你日常浏览器的登录态（要共用走 `--cdp-endpoint`）、单浏览器串行不是并发爬虫。

## 新增服务进这个注册表

1. 在 `index.json` 的 `servers[]` 里加一条（照现有格式抄），`launch.type` 支持
   `npm-global-bin` / `uvx` / `http` / `static`
2. 本机专属的写 `localOnly: true` + `requires.placeholders`
3. 验证：`python mcp/install.py --show <name>` 和 `python mcp/install.py --server <name>`
4. 提交推上去，别的机器就有
