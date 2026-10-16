# pi-android-link

> **分享版入口**：第一次拿到这个包，请先读 [SHARE-README.md](SHARE-README.md)（5 分钟部署 + 必改的 3 个地方 + 文件清单）。
> 隐私处理记录见 [DE-PRIVACY.md](DE-PRIVACY.md)。本文是完整手册。

pi-web 会话状态 → 安卓手机推送，手机 → 一键派发工作。**零账号、零证书；局域网直接用，出门在外靠电脑自己的公网地址（不买服务器、不租服务器）。**

> **整条链路的原理与参数见 [ARCHITECTURE.md](ARCHITECTURE.md)**（从电脑推送消息到手机接收的完整说明）；本文讲部署与日常使用。

```
┌─ PC (192.168.1.100) ──────────────────────────────────────────────┐
│                                                                   │
│  pi-web :30141                        派发台 :8787                │
│  ├ 全功能 UI / 派发 ────► 手机浏览器  ├ 手机派发台（新建/接力）    │
│  └ /api/agent/running（进程内真相）    └ 消息中转 /pi/*（自研）    │
│         ▲                                   ▲                     │
│         │ GET /api/sessions                 │ POST /pi/publish    │
│         │                                   │ NDJSON /pi/stream   │
│  watchdog ◄─────────────────┐               │                     │
│  进程外守护：读会话文件尾部 → 判定收尾/中断 ┴► 环形缓存 500 条     │
│                                              (~/.pi/android-link) │
└───────────────────────────────────────────────────────────────────┘
                              ▲  局域网 HTTP
                              │
┌─ 安卓手机 ────────────────────────────────────────────────────────┐
│  「Pi 通知」App（自研）                  ← 收通知 + 三个动作按钮   │
│  Chrome → http://192.168.1.100:30141      ← 完整 pi-web UI / 派发  │
│  Chrome → http://192.168.1.100:8787/?t=…  ← 轻量派发台             │
└───────────────────────────────────────────────────────────────────┘
```

---

## 为什么是这个形状

| 别的方案 | 为什么不用 |
|---|---|
| **Tailscale** | 要注册账号 |
| **pi-web 内建 Web Push** | Push API / Service Worker 需要 secure context。`http://192.168.1.100:30141` 下 `navigator.serviceWorker` 是 `undefined`，手机端 `isPushSupported()` 直接返回 false —— 只有电脑自己的 localhost 能用。要它就得先上 HTTPS（证书链、iOS 信任位、自签 CA 的坑） |
| **Cloudflare Tunnel（命名域名）/ ngrok** | 命名域名要账号；**但 Quick Tunnel 不要账号、不要信用卡** —— 所以 2026-09-26 起把它当成异地链路的一条（见下面「异地通知」）|
| **MQTT / Redis** | 单机单消费者，pub/sub 只带来运维负担，零收益 |
| **自研订阅端 + 派发台自带中转** | ✅ 用这个（2026-09-24 起）。原生 App 走自己的长连接，不受 secure context 限制，因此**不需要 HTTPS**；中转就是那个你本来就要跑的派发台进程，没有第三方组件 |

**代价（诚实说）**：中转本身只在局域网（`192.168.1.100`）。手机离开这个 WiFi 时能不能收到，取决于**这台电脑自己有没有一个公网地址** —— 现在不再自动有了，而是由你选一条路（隧道 / IPv6 / 端口映射），见下一节。

---

## 异地通知：出门在外也能收到（不买服务器、不租服务器、不注册账号）

一句话：**通知是「电脑推给手机」，中间不需要任何第三方服务器 —— 只要电脑自己有公网地址。** 电脑有四条路可以拿到它，程序会同时把它们都发给手机，手机自己挨个试。

```
                              公网（四选一，都免费）
   ① 免账号隧道  cloudflared Quick Tunnel → https://随机词.trycloudflare.com
   ② 公网 IPv6   宽带下发的全球地址      → http://[240e:xxxx::1]:8788   ← 不用端口映射
   ③ 公网 IPv4   路由器把 8788 转到本机   → http://116.x.x.x:8788
   ④ 手填地址    已有反向代理/别的穿透     → https://xxx.example.com
                                    │
             全部指向同一个「统一出口」:8788（派发台路由 + pi-web 反代）
                                    │
                    ┌───────────────┴───────────────┐
              局域网 :8787                    公网 :8788 / 隧道域名
                    └───────────────┬───────────────┘
                            ┌───────┴────────┐
                     消息中转 /pi/*      pi-web 完整 UI（反代）
                            └───────┬────────┘
                            手机 App：手里有一份候选清单，谁通用谁
```

### 零服务器的关键：让「地址」变成一份清单，而不是一个值

服务端没法主动联系一部在外面的手机（那就变成要账号的推送服务了）。所以反过来：**电脑把「所有能连到它的地址」都告诉手机**，手机自己试：

| 什么时候 | 候选清单从哪来 |
|---|---|
| `/app` 页「一键配置」 | 深链参数 `bases=`（出门前在家点一下就预置好了） |
| 每次推送流建立 | `event=open` 帧里的 `bases` |
| 每 10 个心跳 | keepalive 帧里也带一份（所以隧道换域名能学到） |
| 轮询兵底通道 | 每条消息里都带 `bases` |

App 把清单存下来（`SharedPreferences`），**连不上就换下一个，连通就记住**。切换逻辑在 `EndpointManager.kt`，不需要额外的探测请求 —— 重连循环本身就是探测，不耗电。

通知里的「打开会话 / 派发台 / 让它继续跑」三个按钮也做了**按来源重写**：从哪个地址连进来的，链接就写成那个地址（`console-server.mjs` 的 `rewriteUrl`）。所以手机从隧道收到通知时，点「打开会话」直接就是隧道域名下的那个 pi-web。

### 安全阀：pi-web 没密码时，公网入口根本不开

pi-web 能执行任意命令。所以 `lib/wan.mjs` 的 `gatewayBlockedReason()` 会在 **`local.json` 的 `piWeb.password` 为空** 时拒绝启动统一出口和隧道（除非你显式写 `wan.gatewayWithoutPassword: true`）。这不是「提醒」，是硬拦 —— 宁可没功能，不要把整台机器交出去。

### 怎么用

```bash
node wan-report.mjs            # 体检：公网 IP / IPv6 / 隧道 / 端口映射 各是什么状态、为什么不能用
node wan-report.mjs --probe    # 逐个自检候选地址
node wan-report.mjs --urls     # 只打印地址（一行一个）
```

四条路怎么开（按推荐度）：

| 路 | 怎么开 | 注意 |
|---|---|---|
| ① 隧道 | 装 `cloudflared`（PATH 里能搜到就行），重启 `run-link.bat` | 免账号。**进程重启域名就变**，靠上面的 `bases` 机制同步给手机；出门前建议先 `wan-report` 确认它已就绪 |
| ② IPv6 | 通常什么都不用做（宽带默认下发），需要路由器放行入站 TCP 8788 | 手机也得有 IPv6。地址形态是 `http://[240e:…]:8788` |
| ③ IPv4 | 路由器把 TCP 8788 转发到本机 + 放行 Windows 防火墙 | 先看 `wan-report` 报的 IP 是不是 `100.64.x.x` —— 那是运营商 CGNAT，转发也没用 |
| ④ 手填 | `local.json` 的 `wan.extraBases: ["https://…"]` | 已经有反向代理/内网穿透时用 |

`local.json` 里可调的键（都有默认值，不写也能跑）：

```json
"wan": {
  "enabled": true,          // 关掉就完全不查公网 IP、不起隧道、不开网关
  "gatewayPort": 8788,      // 统一出口端口（公网只暴露这一个）
  "tunnel": "auto",         // off | auto | cloudflared
  "tunnelCommand": "",      // 自定义隧道：{local} 会被替换成本地网关地址
  "cloudflaredPath": "",    // cloudflared 不在 PATH 里时写绝对路径
  "extraBases": [],         // 手填的公网地址
  "ipRefreshMs": 600000,    // 公网 IP 多久刷一次（动态 IP 会变）
  "gatewayWithoutPassword": false
}
```

### 手机上怎么看

App 设置页 →「异地通知」：开关自动切换、候选清单（哪个在用、哪个连不上）、`挨个探测`（当场挨个 ping 一遍）、`添加并启用`（手填地址）。主界面第二行会显示当前出口，并标出「异地」。

### 诚实说的三条限制

1. **隧道域名会变**：cloudflared Quick Tunnel 每次重启换域名。手机上靠 `bases` 机制自动更新；但如果你出门前电脑正好重启过、而手机手里一个地址都不通，那就得回家点一次 `/app` 的「一键配置」。
2. **自检不等于真相**：本机没法从公网给自己发包（NAT 回环不是所有路由器都支持），所以 `ready` 只是参考。真正的裁判是手机探测 —— 这也是为什么清单是「候选」而不是「真相」。
3. **公网可达 ≠ 安全**：统一出口会把 pi-web 暴露到公网。令牌 + pi-web 密码 + 建议给路由器只放行必要端口，是这套东西的底线。真要更严，就只留隧道（随机域名 + 无端口映射）。


---

## 我实测过的事实（不是推测）

| 事实 | 证据 |
|---|---|
| pi-web 内建推送只在进程内发 | `pi-web/lib/rpc-manager.ts:2143` → `lib/web-push.ts`；进程被杀就发不出任何东西 |
| 它只有一句"任务已完成" | `lib/web-push.ts` 只导出 `notifySessionComplete`，无法区分成功/失败 |
| 真实会话里失败不罕见 | 234 个会话文件：`complete=208`、`model_error=14`、`aborted=7`、`interrupted_tool=5`。**那 26 个都会被告知"任务已完成"** |
| 它推的是 10 分钟空闲也会关会话 | `PI_WEB_IDLE_TIMEOUT_MS` 默认 `600000` |
| 子代理会话完全不推 | `rpc-manager.ts:2148` `suppressCompletionNotifications: Boolean(subagentResources)` |
| "等待你操作"只在标签页活着时弹 | `components/AppShell.tsx:928` → `lib/browser-notifications.ts`，服务端没有这条推送出口 |
| Windows 上端口不能当互斥锁 | Node 的 `net` 默认带 `SO_REUSEADDR`，两个进程能绑同一个 `addr:port` 且都成功 → 见 `lib/single-instance.mjs` |
| 启动器不用 `.cmd` 纯 ASCII | 试过 `.cmd` + 纯 ASCII（英文注释），但中文写不了，看着费劲。现统一用 `.bat`（UTF-8 无 BOM + 首行 `chcp 65001`），中英文照常写。坑：`Set-Content -Encoding OEM` 会写 BOM/转码落盘成乱码，必须显式字节写无 BOM UTF-8（见 `setup.ps1` 的 `Write-BatFile`） |
| pi-web 登录限流是**全局共享**的 | `lib/auth-throttle.ts`：所有失败共用一个计数器；**被限流期间连正确密码也拒绝**（`proxy.ts:53`），需 5 分钟无失败才重置。详见下面「安全阀」 |

---

## 部署

```powershell
cd C:\pi-link
powershell -ExecutionPolicy Bypass -File setup.ps1
```

它会：生成 `~/.pi/android-link/local.json`（pi-web 密码 / 派发台令牌 / 中转地址）→
写 `run-link.bat` + `run-pi-web.bat` 启动脚本 → 放行防火墙 → 跑一遍验收。

**当前不注册开机自启。** 需要服务时手动双击 `run-link.bat`；需要 pi-web 时再双击 `run-pi-web.bat`。两个窗口都是前台窗口，关闭对应窗口会停止对应服务。

`setup.ps1 -Force` 会重新生成 pi-web 密码和派发台令牌（手机上要重新点一次「一键配置」）。

### 让 pi-web 绑到局域网

双击 `run-pi-web.bat`，它做三件事：

```cmd
set PI_WEB_PASSWORD=<local.json 里的那个>
set PI_WEB_NO_OPEN=1
pi-web -H 0.0.0.0 -p 30141
```

> ⚠️ 必须带密码。pi-web 能执行任意命令，无密码绑 `0.0.0.0` 等于把整台机器交给同一 WiFi 上的任何人。
> API 客户端用 Basic 认证，用户名固定 `pi`（`lib/web-auth.ts: PI_WEB_AUTH_USERNAME`）。

启动时会看到 pi-web 自己的警告，这是**预期内的**：

```
Warning: pi-web is listening on 0.0.0.0 with password authentication over HTTP.
         Use HTTPS or a trusted VPN to protect the password in transit.
```

纯 HTTP 下 Basic 头里的密码对同网段可见。家用 WPA2 WiFi 需要先拿到 PSK 才能嗅探，
配合 32 位随机密码可以接受。真要收口就上自建 WireGuard（自己生成密钥，零账号）或反代 TLS。

### ⚠️ 只能有一个 pi-web 实例（双实例脑裂）

实测踩过的坑：旧实例还占着 `127.0.0.1:30141`，新实例绑到 `0.0.0.0:30141`。
两个 listener 共存且都能建连（`127.0.0.1` 比 `0.0.0.0` 更具体，优先匹配）：

- 电脑浏览器开 `localhost` → **老实例**
- 手机开 `192.168.1.100` → **新实例**

两者是**两套独立的内存状态**（实测：老实例 `runningSessionIds` 有 1 个，新实例 0 个），
会话文件却是同一个目录。后果是看门狗的判定基准变成错的那一半，**会对正在跑的会话误报“异常中断”**。

先查再停（启动新的之前一定要先停旧的）：

```powershell
# 查：应该只列出一个
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*30141*' } |
  Where-Object { $_.CommandLine -like '*next*' -or $_.CommandLine -like '*pi-web*' } |
  Select-Object ProcessId,CommandLine | Format-List

# 停：把老的 127.0.0.1 那两个（pi-web.js 壳 + next start）一起停掉
Stop-Process -Id <老实例的 pid> -Force
```

`verify.mjs` 的 **E3** 会直接抓这个问题（统计端口上的 listener 个数）。

> 停掉老实例会终止它正在跑的那些会话（包括你正在对话的这个）。会话已落盘，
> 刷新到新实例后从 `/resume` 或会话列表里接回来就行。

### 手机装「Pi 通知」App

一条路，最稳：

```
手机浏览器打开  http://192.168.1.100:8787/app
  ① 点「下载 APK」        —— 短地址 /apk，永远给目录里最新那个
  ② 点「一键配置并启动」   —— 深链 pilink://setup，自动写好地址+令牌+回执
  ③ 弹「电池白名单」就点「去设置」并允许
```

APK 由派发台的 `/apk` 路由分发（目录里最新的那个，按 mtime）。换版本：把新 APK 丢进 `apk/` 即可，
手机不用换链接 —— 短地址永远指向最新。

> 安卓会报"未知来源"或"Play 保护机制已阻止"，选"仍然安装"即可。

### 手机端必做的三件事（不做等于没装）

1. **电池白名单** —— 设置 → 应用管理 → Pi 通知 → 耗电管理 → 允许后台活动
2. **自启动** —— 同页 → 自启动 → 允许
3. **锁后台** —— 最近任务里把这个卡片下拉加锁（防手滑清理）

**为什么白名单是硬要求**：Android 息屏闲置后进 Doze，会**给所有应用断网**，只有白名单里的被豁免。
实测（当时服务端统计）：手机放下 1 分钟内两个客户端一起掉。不白名单，服务端推得再勤也到不了手机。

**不需要**「闹钟和提醒」这类特殊权限 —— 重连靠常驻协程 + 非精确闹钟自愈，不依赖任何权限。

---

## 日常使用

### 通知长什么样

```
┌──────────────────────────────────────┐
│ ✅ demo-repo  · 帮我把渲染跑完      │  ← 项目名 · 首条消息摘要
│ 任务完成 · 正常收尾                   │
│                                      │
│  [打开会话]  [派发台]  [让它继续跑]    │  ← 三个按钮
└──────────────────────────────────────┘
```

- **点通知本体** → 直接跳到那个会话 `http://192.168.1.100:30141/?session=<id>`
- **[打开会话]** → 同上
- **[派发台]** → 轻量派发页
- **[让它继续跑]** → 给那个会话追加一句"继续"

### 判定表

看门狗按这张表推，**不看"最后一行是什么"，而是往前找最后一条 assistant 消息**：

| 尾部形态 | 判定 | 优先级 |
|---|---|---|
| `assistant` `stop=stop` 且无 toolCall | ✅ 任务完成 | 3 |
| `assistant` `stop=error` | 🚨 模型/请求报错中断（带 `errorMessage`） | 5 |
| `assistant` `stop=aborted` | ⏹ 已中止 | 2 |
| `assistant` `stop=length` | ✂️ 输出被截断 | 3 |
| `assistant` `stop=toolUse` 但没接上 | ⚠️ 工具阶段异常中断 | 5 |
| 排在 `runningSessionIds` 里但文件 10 分钟没动 | 🐌 疑似卡死 | 4 |
| 上一轮有会话在跑、这一轮 pi-web 连不上 | 💀 pi-web 进程失联 | 5 |
| Basic 认证连续失败 3 次 | 🔑 认证失败，看门狗停手 | 5 |

另有 11 个会话末条是 `model_change` / `thinking_level_change` / `custom` 这类元数据写入 —— 只看最后一行会误判，往前找 assistant 就对了。

### 派发台

手机开 `http://192.168.1.100:8787/?t=<令牌>`（第一次带令牌，之后写 cookie，可加书签）：

- 正在跑的会话（带进度）/ 最近会话，每条都能「打开」或「继续」
- 文本框 + 工作目录 → 派发新会话
- 快捷指令按钮（在 `local.json` 的 `quickCommands` 里配）
- 未带令牌一律 401 —— 这东西能启动 agent，必须锁

底层就是一个 HTTP 接口，你也可以自己接：

```bash
curl -u pi:<密码> -X POST http://127.0.0.1:30141/api/agent/new \
  -H 'Content-Type: application/json' \
  -d '{"cwd":"C:/pi-work","type":"prompt","message":"把渲染跑完"}'
```

---

## 安全阀：绝不会把你锁在自己的 pi-web 外面

这是这套东西里最危险的一个失败模式，实测踩过：

pi-web 的登录限流是**全局共享**的（单操作者设计），而且**被限流期间连正确密码也一律拒绝**，
需要 5 分钟没有任何失败才重置。看门狗每 15 秒要打一次 API —— 如果
`local.json` 里的密码和 pi-web 启动时的 `PI_WEB_PASSWORD` 不一致，它会把限流刷满，
**结果是你自己用浏览器也登不进 pi-web**。

所以 `lib/piweb.mjs` 专门抛 `PiWebAuthError`，看门狗对此：

1. 退避重试（至少 60s，并尊重 `Retry-After`），绝不打连发
2. 连续 3 次 → 推一条 p5 的「认证失败」通知，写清怎么修
3. **主动停手 30 分钟**，其间即使被守护进程反复拉起也拒绝开工（不打一个字）

改好密码后用 `--force` 立即重试：

```bash
node watchdog.mjs --force
```

---

## 登录 pi-web 用什么

绑定到 `0.0.0.0` 并设密码后，浏览器会弹一个 **HTTP Basic 对话框**（Chrome 中文界面就显示「用户名 / 密码」）。
凭据存在 `~/.pi/android-link/local.json`：

| 项 | 值 |
|---|---|
| 用户名 | **`pi`**（固定，见 `lib/web-auth.ts` 的 `PI_WEB_AUTH_USERNAME`） |
| 密码 | `local.json` 里的 `piWeb.password` |
| 地址 | `http://<本机IP>:30141`，本机也可 `http://localhost:30141` |

三处都能拿到这个密码：

1. `fix-split-brain.bat` 的报告结尾会直接印出来
2. 文件 `~/.pi/android-link/local.json`
3. 一条命令：
   ```powershell
   # 注意必须用 ReadAllText + UTF8：Get-Content -Raw 会按 ANSI(GBK) 解这个无 BOM 的
   # UTF-8 文件，中文字段变乱码 → ConvertFrom-Json 直接抛 ArgumentException（实测踩过）
   ([System.IO.File]::ReadAllText("$env:USERPROFILE\.pi\android-link\local.json", [System.Text.Encoding]::UTF8) | ConvertFrom-Json).piWeb.password
   ```

> 不想看 Basic 对话框的话，直接开 `http://<IP>:30141/login` —— 那个页面只要填密码，
> 登录后会写 cookie（30 天）。Basic 框是因为页面里的 `/api/*` 请求先吃了个 401，
> 浏览器自己把认证框弹出来的。

## 两种认证模式（自己选）

| | 带密码（默认） | **局域网免密码** |
|---|---|---|
| 启动参数 | `PI_WEB_PASSWORD=<随机>` | 不设 |
| 浏览器体验 | 会弹 HTTP Basic 框（或走 `/login` 写 30 天 cookie） | **打开就用，什么都不用填** |
| 手机扫码/书签 | 要输密码，PWA 里也麻烦 | 直接收藏即可 |
| pi-web 启动时会警告 | `... with password authentication over HTTP` | `... without authentication. Only use this on a trusted network.` |

### 切到免密码：`setup.ps1 -NoPassword -ScriptsOnly` + 双击 `fix-split-brain.bat`

它会：

1. 把 `local.json` 的 `piWeb.password` 置空，并重新生成 `run-pi-web.bat`（不再设 `PI_WEB_PASSWORD`）
2. 重启 pi-web（隐藏窗口，绑 `0.0.0.0`）
3. 体检 + 写报告

想换回带密码：`setup.ps1 -Force -ScriptsOnly` 重新生成一个随机密码，然后再双击一次 `fix-split-brain.bat`。

### 免密码到底安全吗

我实测确认两件事：

1. **pi-web 不会拒绍**，只是警告一句。`bin/pi-web.js` 里只有 `console.warn`，没有硬校验
2. **CSRF 防护在无密码时仍然生效** —— `proxy.ts` 里 Host / Origin / `Sec-Fetch-Site` 检查（31-40 行）排在密码检查（42-48 行）**之前**，
   无密码只是提前 `return NextResponse.next()`。所以**不会**变成“你随便打开个恶意网页就能向 pi-web POST 命令”

真正的暴露面只剩一条：**同一层二层的设备能直接访问这个端口**。家用 WPA2 下，攻击者得先拿到 WiFi PSK。
威胁模型里真正现实的两个场景：

- **你自己的物联网设备被拿下**（电视、摄像头、已 root 的手机）—— 那它本来就在你网内
- **这台机器以后接进了不受信任的网络**（酒店/公司/手机热点）—— 这个是**真会发生的**，而且你不会注意到

### ⚠️ 不要按 profile 加封禁规则（本机实测会误伤手机）

我一开始想加「Public 网络下封禁 30141」，**结果查了一下发现这台机器的局域网自己就是 Public 类别**：

```
Get-NetConnectionProfile
Name        InterfaceAlias  NetworkCategory
ZTE-ZRHY5k  以太网 2         Public        <- 不是 Private
```

Windows 只是没把 ZTE 这台路由器的网段认成"专用网络"，加了那条规则**手机会直接被挡在外面**。
现在手机能通，靠的正是 Node.js 自带的入站规则（`Profile = Private, Public` 都 Allow）。

所以本套脚本**故意不加任何端口级封禁规则**，只做反向检查：有没有 Block 规则误伤 30141。
`verify.mjs` 的 **E4** 和 `fix-split-brain.bat` 都在查这个。

台式机固定不动、路由器也没有端口映射到这台机器，所以暴露面就是自家局域网，可以接受。
真要收紧就按**来源网段**做，不要按 profile：

```powershell
# 想看现在有哪些 Block 规则可能命中 30141
Get-NetFirewallRule -Direction Inbound -Action Block -Enabled True |
  Where-Object { ($_ | Get-NetFirewallPortFilter).LocalPort -contains '30141' } |
  Select-Object DisplayName, Profile
```

> 不管选哪种模式，**单实例防脑裂**和**看门狗**都是独立的，不受影响。
> `verify.mjs` 的 **E4** 会检查上面那条 Public 封禁规则在不在。

## 一键脚本

不想敲命令就双击这几个（都在项目根目录）：

| 双击这个 | 干什么 |
|---|---|
| **`fix-split-brain.bat`** | 体检 + 自动修好。只要不是「唯一实例 + 绑局域网 + 认证模式正常」就全停重来（隐藏窗口启动，不会被手滑关掉）；顺便体检消息中转（＝派发台）、看门狗、认证、防火墙；结尾把登录凭据印出来。执行前用 `Read-Host` 问 `YES` |
| **`run-link.bat`** | **日常就用这一个**：一个终端同时跑 watchdog + 派发台（经 `link-supervisor.mjs` 监管，任一崩溃自动重启） |
| `run-pi-web.bat` | 手动前台启动 pi-web（`0.0.0.0`）。⚠️ **这个窗口关掉 = pi-web 死掉**，窗口标题已经写了警告 |

当前不设置开机自启。需要完整服务时手动双击 `run-link.bat` 和 `run-pi-web.bat`；只想启动推送链路时运行 `run-link.bat` 即可。

输出会**同时**打到窗口和 TXT：

```
C:\pi-link\fix-split-brain-report.txt
```

> ⚠️ 这份报告里含 pi-web 密码，`.gitignore` 已排除（`*report*.txt`），别外传。

带参数的用法（在控制台里跑）：

```powershell
.\fix-split-brain.bat -DryRun      # 只诊断，不动任何进程（想先看看就用这个）
.\fix-split-brain.bat -Force       # 不询问，直接执行
.\fix-split-brain.bat -NoStart     # 只清理，不自动启动 pi-web
```

退出码：`0` 已正常 / `1` dry run / `2` 仍有问题 / `99` 脚本异常。

### 为什么「关窗口」是个坑

实测踩过：`run-pi-web.bat` 是前台托管 pi-web 的，**关掉那个控制台窗口就会杀死 pi-web**。
更阴的是 pi-web CLI 默认绑 `127.0.0.1`，于是用户随手再双击一下裸 `pi-web`
（或者它自己重生了）就又多出一个回环实例 —— 又变成脑裂。

现在两重防护：启动项用隐藏窗口启动；`run-pi-web.bat` 顶上有 `title` + 三行警告。


<details>
<summary>两个文件的编码不一样，这是故意的</summary>

| 文件 | 编码 | 原因 |
|---|---|---|
| `*.bat` | **UTF-8 无 BOM + 首行 `chcp 65001`** | 和桌面 `Pi Web.bat` 同一套写法，中英文照常写。`setup.ps1` 的 `Write-BatFile` 会校验这两项才落盘 |
| `*.ps1` | **UTF-8 带 BOM** | PowerShell 5.1 读无 BOM 的 UTF-8 会当 ANSI/GBK → 中文全乱码 |
</details>

## 排障

```bash
cd C:\pi-link
node verify.mjs          # 39 项确定性验收，退出码 0 = 全过
node verify.mjs --quiet  # 只看失败项
```

日志都在 `~/.pi/android-link/`：

| 文件 | 内容 |
|---|---|
| `watchdog.log` | 判定与通知的结构化记录（每次推送一条） |
| `watchdog.out.log` | 看门狗进程 stdout |
| `console.log` | 派发台的请求与派发记录 |
| `messages.jsonl` | **消息中转的环形缓存**（最近 500 条，重启不丢）|
| `acks.jsonl` | 送达回执（每次手机收到一条追加一行）|
| `state.json` | 已通知过的尾部、prime 状态、鉴权失败计数 |

常用命令：

```bash
node watchdog.mjs --once --dry          # 跑一轮，只打印不推送
node watchdog.mjs --once                # 跑一轮，真推
node watchdog.mjs --simulate model_error # 把某一种判定走一遍真实发布（发一条测试推送到手机）
```

| 症状 | 原因 |
|---|---|
| 手机收不到通知 | 1) App 没加**电池白名单**（息屏闲置会被系统断网）2) 派发台没跑 3) App 里还是旧的 :8080 配置 |
| 通知迟到几分钟 | 息屏时系统断网，重连后用游标补收 —— 加电池白名单能大幅减少 |
| 收得到但点不开 | 手机不在同一 WiFi；或 pi-web 还没用 `-H 0.0.0.0` 重启 |
| `verify.mjs` 报 E2 | 同上，这是**唯一需要你手动做的一步** |
| 第一次启动没被旧消息淹没 | 已实现 prime：首次运行把历史尾部标记为已知，不补推 |
| 通知推了两遍 | 检查是否重复启动了 `run-link.bat`（单实例锁应该拦住；看 `watchdog.log` 有没有“已有看门狗在跑”） |

---

## 验收覆盖

`node verify.mjs` 是 36 项可计算的断言，不做视觉判断：

- **A 判定逻辑** — 9 条单元断言；234 个真实会话文件全部「有界尾部读取 == 整文件判定」；五种判定的文案映射逐个校对
- **B 自研中转链路** — 发布→缓存回读；NDJSON 格式；中文标题/正文未被破坏；优先级、深链、三个动作按钮保真；无令牌取流必须 401
- **C 看门狗** — 锁文件 + PID 存活；状态已落盘；已 prime
- **D 派发台** — 无令牌 401、带令牌 200；快捷指令已配置
- **E pi-web** — 回环可达 + Basic 认证；是否已绑到局域网（**待人工**，不计入退出码）
- **F 真实发布链路** — 五种判定 + 卡死 + 失联，用 `--simulate` 逐个真推一遍，回读中转缓存确认文案/优先级/标签
- **G 启动方式** — 确认没有残留开机自启（只保留手动 `.bat`）
- **H 鉴权安全阀** — 拿桩服务器（返 401）验证：会退避、3 次后告警并停手、停手期内**一个字都不打出去**、`--force` 能立即重试
- **I 异地通知** — 候选地址清单格式合法、局域网候选自检可达、统一出口（:8788）在监听或说清为何没启、`/pi/ping` 与 `/pi/endpoints` 契约、推送流 `open` 帧带清单、**通知深链按请求来源重写**

> I6「至少有一个异地出口」在还没配公网入口的机器上是 `待人工`（不是失败）——
> 那是部署状态，不是代码状态。`node wan-report.mjs` 会告诉你缺哪一条、怎么补。

---

## 卸载

```powershell
Get-ScheduledTask -TaskName 'pi-android-link-*' -ErrorAction SilentlyContinue | Unregister-ScheduledTask -Confirm:$false
Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\pi-android-link.vbs" -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*pi-android-link*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Remove-Item "$env:USERPROFILE\.pi\android-link" -Recurse -Force
```

`local.json` 是本机唯一秘密来源，别提交到仓库。
