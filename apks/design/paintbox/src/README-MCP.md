# 跑图助手 · MCP 版

在原来的「跑图助手」（grsai + 仙宫云 + ComfyUI）基础上加了一个**内置 MCP 服务器**：
手机上的 AI agent（Mika 等）通过 `http://127.0.0.1:8766/mcp` 就能自己出图、取图，
不用再截图点击。出图仍然走 `https://grsai.dakka.com.cn/v1/draw/completions`，用「设置」里那份 Key。

```
bash build.sh      # 只依赖 Android SDK build-tools，产出 PaintBox.apk
```

## MCP 工具

| 工具 | 作用 |
| --- | --- |
| `list_models` | 模型 × quality 档位 × 是否支持透明背景，当前线路 |
| `draw_image` | 提交 `/v1/draw/completions`（`webHook=-1` 立即拿 id）→ 轮询 `/v1/draw/result` → 下载 → 存相册 `Pictures/跑图助手` |
| `draw_status` | 按 task_id 继续等 / 取图 |

`draw_image` 参数：`prompt`（必填）、`model`、`quality`、`aspect`、`count`(1–4)、`background`、
`ref_urls[]`、`ref_paths[]`（本机路径 / content:// 会转 base64 data URI）、`wait_seconds`(0–240)、`save_gallery`。

一次调用最多等 240 秒；超时就返回 `status=running` + `task_id`，再 `draw_status` 接着等（不重复提交，不重复扣费）。
返回里带 `url`（有效期 2 小时）与相册路径，`url` 可以直接喂给「PDF 工厂」的 `images_to_pdf`。

## 实现要点（照 Mika 的 MCP 原理）

* `Mcp.java` —— 极简 Streamable HTTP 服务端：一个端口、每连接一线程、连接数与正文大小有上限、
  `Content-Length` / `chunked` 都认、只回单个 JSON（不开 SSE 流）、不发会话编号（完全无状态）。
  老协议先 `initialize`（回 `2025-03-26`，正是 Mika `HttpMcpEndpoint` 要的版本），
  新协议的 `_meta` 版本号也认；`server/discover`、`ping` 一并支持。
* `PaintBoxTools.java` —— 工具定义 + 执行，`structuredContent` 与文本内容一起给。
* `McpService.java` —— 前台服务保活（specialUse），通知栏可一键关。
* `McpView.java` —— 「MCP」页签：开关、端口、只本机/局域网、令牌（可留空）、URL、工具清单、给 Mika 的配置 JSON。

## 接到 Mika

1. 装 APK，进「设置」填 grsai API Key（出图要靠它）。
2. 进「MCP」页签 → 打开开关（先在通知权限弹窗点允许）。
3. Mika → 设置 → 外部 MCP 服务器 → 添加：
   * 传输：`streamable-http`
   * URL：`http://127.0.0.1:8766/mcp`
   * 打开「允许本地 http」（Mika 对 http 明文默认是拒的）
   * 令牌：App 里填了就填同一个；留空则不用
   * 超时：调大到 `240` 秒（出图比普通工具慢）

页签里的「复制给 Mika」直接给出一份 JSON，可对照着填。

协议层已用 Mika 相同握手流程（`initialize`→`notifications/initialized`→`tools/list`→`tools/call`）在
JVM 上跑过一遍回归，含 401/405/未知工具/工具报错等分支。
