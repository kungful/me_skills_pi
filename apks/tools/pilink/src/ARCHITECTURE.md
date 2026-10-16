# 链路说明：从电脑推送消息到手机接收

一句话：`pi-web` 里的会话状态 → `watchdog` 判定 → `派发台` 中转 → `Pi 通知` App 弹系统通知。
全程无第三方推送服务、无账号、无证书；局域网直连，出门在外靠电脑自己的公网地址（隧道 / IPv6 / 端口映射）。

参数值均取自代码（`config.mjs` / `Prefs.kt` / `console-server.mjs`），改动代码请同步本文。

---

## 1. 全景

```
┌─ PC 192.168.1.100 ─────────────────────────────────────────────────────────┐
│                                                                           │
│  pi-web :30141                       派发台 :8787（0.0.0.0，局域网可达）  │
│  ├ 会话真相来源                       ├ 消息中转 /pi/*                    │
│  │  GET /api/sessions                 │   · POST /pi/publish   收通知     │
│  │  runningSessionIds                 │   · GET  /pi/stream    推通知     │
│  │  sessions[].path/.modified         │   · GET  /pi/messages  补收       │
│  └ /api/dispatch 派发新会话            ├ 手机派发台 UI（/）               │
│         ▲                              ├ 装机引导页（/app）+ APK（/apk）  │
│         │                              └ 环形缓存 messages.jsonl（500 条）│
│         │                                                                 │
│  watchdog（常驻进程，每 5s）                                              │
│   ├ 读 /api/sessions 拿 runningSessionIds                                 │
│   ├ 读会话文件尾部 → 判定 完成/报错/中止/截断/工具中断/卡死               │
│   └ 命中就 POST /pi/publish ─────────────────────────────────┐            │
└──────────────────────────────────────────────────────────────┼────────────┘
                                                               │
                            局域网 HTTP（明文，用令牌鉴权）     │
                                                               ▼
┌─ 安卓手机 OPPO K13 Turbo Pro / Android 16 ────────────────────────────────┐
│  Pi 通知 App（前台服务 + 一条 NDJSON 长连接）                             │
│   ├ 主通道：GET /pi/stream?since=<游标>&ka=20   实时收                    │
│   ├ 兜底：  GET /pi/messages?since=<游标>        每 30s 拉一次             │
│   ├ 收到即弹系统通知（可带 3 个动作按钮）                                 │
│   └ 收到即回执：POST /pi/ack                                              │
│  Chrome → http://192.168.1.100:30141  完整 pi-web UI / 派发               │
│  Chrome → http://192.168.1.100:8787   轻量派发台                          │
└───────────────────────────────────────────────────────────────────────────┘
```

## 2. 四个角色

| 组件 | 位置 | 职责 | 没有了会怎样 |
|---|---|---|---|
| **pi-web** | PC `:30141` | 跑 agent、写会话文件；`/api/sessions` 给出「哪些会话正在跑」 | 判定层没有数据来源 |
| **watchdog** | PC 常驻进程 | 判定会话结局并发布通知 | **一条通知都没有** |
| **派发台** | PC `:8787`（另有统一出口 `:8788`） | 消息中转 + 手机派发台 UI + 装机页 + **异地发现（`lib/wan.mjs`）** | 手机收不到；派发台界面也没了；没有异地地址 |
| **Pi 通知 App** | 手机 | 保持订阅、弹系统通知、回执、**在候选出口之间自动切换** | 看不到通知 |

四个角色**每个都只能有一个实例**（否则消息会被劈成两份）：watchdog 与派发台各自用锁文件互斥。

## 3. 一条通知的完整旅程

以「会话正常跑完」为例（延迟为实测值）：

| # | 时刻 | 发生什么 | 实测耗时 |
|---|---|---|---|
| 1 | T+0 | agent 写出本回合最后一条消息，会话文件停止增长 | — |
| 2 | T+1.5s | watchdog 的下一次轮询读到文件尾部，判定 `complete` | 1.5~6.5s |
| 3 | T+1.5s | `POST /pi/publish` 落到派发台，分配 `id`/`seq`，写缓存并扇出给已连接的流 | <10ms |
| 4 | T+1.6s | 手机的流上收到这一行 JSON，弹系统通知 | 0.1~1.1s |
| 5 | T+1.6s | 手机 `POST /pi/ack`，派发台记一行到 `acks.jsonl` | <10ms |

**检测 1.5~6.5 秒 + 传输 0.1~1.1 秒 ≈ 4~5 秒到手机。**

判定为 `toolUse`（工具可能还在跑）时不用快档，等满 20 秒静默期——这是唯一需要保守的情况。

## 4. 协议（派发台 `/pi/*`）

| 端点 | 方法 | 鉴权 | 作用 |
|---|---|---|---|
| `/pi/publish` | POST | 令牌 | 发一条通知；返回 `{ok, id, seq, time, streams}` |
| `/pi/stream?since=&ka=` | GET | 令牌 | NDJSON 长连接：先补发、再实时推、每 `ka` 秒一条 keepalive |
| `/pi/messages?since=` | GET | 令牌 | 只返回缓存（轮询兜底 / 断线补收） |
| `/pi/ack` | POST | **免令牌** | 送达回执，只追加一行 `acks.jsonl` |
| `/pi/ping` | GET | 令牌 | 便宜的探测端点：手机挨个试候选出口时用，顺带回一份 `bases` |
| `/pi/endpoints` | GET | 令牌 | 候选出口的完整视图（kind / 自检状态 / 说明），排障用 |

令牌 = `~/.pi/android-link/local.json` 里的 `lan.consoleToken`，用 `?t=<令牌>` 传。

**消息字段**（`POST /pi/publish` 的 body，字段名沿用最早版本，解析层不受影响）：

```json
{
  "title": "demo-repo · 只回复两个字：收到",
  "message": "任务完成 · 正常收尾",
  "priority": 3,
  "click": "http://192.168.1.100:30141/?session=<id>",
  "actions": [
    { "action": "view", "label": "打开会话",     "url": "…" },
    { "action": "view", "label": "派发台",       "url": "…" },
    { "action": "view", "label": "让它继续跑",   "url": "…" }
  ],
  "group": "pi-web"
}
```

- `priority` 决定走哪条通知渠道：`>=4` 走「Pi 报错 / 中断」（高优先级、响铃+震动），否则走「Pi 任务完成」
- `actions` 最多取 3 个，只支持 `view`
- 服务端补上 `id`（10 位随机）、`seq`（递增）、`time`（秒级 Unix 时间）

**游标语义**（`since=`）：

| 值 | 含义 |
|---|---|
| `none`（默认） | 不补发历史，只收新的 |
| `all` | 全部缓存 |
| `<消息 id>` | 该 id 之后的消息 |
| `10m` / `1h` / `2d` | 时间窗内的消息 |
| 未知 id | 全部缓存（宁可重复不可丢；App 按 id 去重） |

**推送流的报文**（一行一个 JSON 对象，NDJSON，不是数组）：

```
{"event":"open","time":…,"origin":"…","bases":[…],"preferred":"…"}   ← 建立后立刻一帧（带候选出口清单）
{"id":"…","seq":…,"time":…,"title":"…","message":"…","bases":[…],"event":"message"}
{"event":"keepalive","time":…}                                       ← 每 ka 秒一帧，用于判活
{"event":"keepalive","time":…,"bases":[…],"preferred":"…"}           ← 每 10 帧带一次清单
```

**链接是投递时重写的**：缓存里存的是局域网地址，但发给手机前会按**本次请求的来源**
换掉域名与端口（`console-server.mjs` 的 `rewriteUrl`）。所以手机从隧道拿到通知时，
点「打开会话」打开的就是隧道域名下的那个 pi-web —— 而隧道域名的根路径反代给了 pi-web。

## 5. 手机端

**通知**：三条渠道，均由 App 首次启动时创建。

| 渠道 | 重要性 | 用途 |
|---|---|---|
| `pilink-alert`「Pi 报错 / 中断」 | 高（响铃 + 震动 + 横幅可选） | 报错、工具中断、卡死、pi-web 失联 |
| `pilink-done`「Pi 任务完成」 | 默认 | 正常结束 |
| `pilink-service`「连接状态（常驻）」 | 最低（静默） | 前台服务的常驻通知 |

- 动作按钮**不带图标**（SystemUI 对矢量图标支持不好）；`PendingIntent` 用随机 requestCode
- `VISIBILITY_PUBLIC`：锁屏直接显示正文；`CATEGORY_ERROR` / `CATEGORY_STATUS` 按语义分类
- 点通知打开 `click`；长按卡片复制全文；App 内列表保留最近 50 条（离线可查）
- 系统把通知关掉时，App 首屏会显示橙色告警条并给出跳转

**必须设置**：把 App 加入**电池优化白名单**（设置 → 应用管理 → Pi 通知 → 耗电管理 → 允许后台活动），
并允许**自启动**、在最近任务里**加锁**。不加白名单会导致息屏闲置后系统断网。
ColorOS 的通知页里建议把**「横幅」**打开（不加就只进通知栏和锁屏，不弹出来）。

## 5b. 异地（公网）这条支线

```
                    lib/wan.mjs（跑在派发台进程里）
   ┌────────────────────────────────────────────────────────────┐
   │ 每 ipRefreshMs：并发问几个「我是谁」服务 → 公网 IPv4       │
   │ 一次：os.networkInterfaces() → 全球单播 IPv6                │
   │ 一次：spawn cloudflared tunnel --url http://127.0.0.1:8788 │
   │       从 stdout/stderr 抓第一个 https://… → 候选地址        │
   │ 每个候选自检一次 GET {base}/pi/ping → 标 ready/unverified  │
   │ 结果写 ~/.pi/android-link/endpoints.json（给 wan-report 看）│
   └───────────────┬────────────────────────────────────────────┘
                   │ bases[]（局域网、隧道、IPv6、IPv4、手填）
   派发台 :8787 ───┴──► 手机 App（EndpointManager 挨个试，连不上的换下一个）
   统一出口 :8788 = 派发台自己的路由 + 其余一切反代给 pi-web（注入 Basic 认证）
                   ▲
                   └── 隧道 / IPv6 / 端口映射 都只指向这一个端口
```

**几个必须记住的事实：**

| 事实 | 原因 |
|---|---|
| pi-web 只信任 `localhost` / `.localhost` / IP 字面量 / `PI_WEB_ALLOWED_HOSTS` 里的主机名 | `.next/server/middleware.js` 的 `r()`。隧道域名不在里面 → 直接 403 `Untrusted request` |
| 所以反代时必须改写 `Host` **和** `Origin` | 同一处还有 CSRF 检查：`Origin` 必须等于 `${proto}//${Host}`。两个一起改写才自洽 |
| 反代要注入 `Authorization: Basic` | 否则公网上的浏览器还要手输一次 pi-web 密码 |
| 响应头要丢 `content-encoding` / `content-length` | `fetch` 已经解开 gzip，且流式转发时长度会变 |
| 无密码时**不开**统一出口和隧道 | `gatewayBlockedReason()`：能执行任意命令的 agent 不能裸奔到公网 |
| 统一出口的 `/` 是 pi-web，派发台页面挪到 `/console` | 两边都需要根路径；`/pi/*`、`/apk`、`/app` 仍然走派发台 |
| 候选是「候选」不是「真相」 | 本机没法从公网给自己发包（NAT 回环不一定支持），自检失败只标 `unverified`，仍然发布 —— 手机探测才是裁判 |

## 6. 可靠性设计

| 机制 | 做法 | 解决什么 |
|---|---|---|
| **游标补收** | 每条消息更新 `lastId`，重连/轮询都带 `since=<lastId>` | 断线期间的消息不丢，只迟到 |
| **首次定基** | 首次运行把游标设成「当前最新那条」 | 既不会一次弹 50 条历史，此后每条也不丢 |
| **断线即时补收** | 流一断立刻拉一次 `/pi/messages` | 不必等下一个轮询周期 |
| **双通道** | NDJSON 长连接（主）+ HTTP 轮询（兜底，已连 30s / 断开 10s） | 流被掐时仍能收 |
| **原子去重** | 加锁后再查/写「已见 id 集合」 | 主通道与兜底同时拿到同一条时不会弹两次 |
| **重连阶梯** | 1/2/3/5/8/13/21/30 秒退避，连上即重置 | 快速恢复且不狂打 |
| **不设读超时** | `readTimeout(0)`，判死交给 90 秒静默看门狗 | 网络抖一下不会把自己杀死 |
| **服务端 keepalive** | 每 `ka` 秒推一帧（`ka` 由 App 指定，默认 20s） | 保活 + 让 App 知道链路活着 |
| **自愈闹钟** | 每 5 分钟检查一次，静默未超阈值就不动它 | 进程被系统压制后能自己回来 |
| **单实例锁** | `watchdog.lock` / `console.lock`（独占创建 + PID 存活校验），**不用端口** | 避免两个实例把消息劈成两半 |
| **登录保护** | 连续 3 次鉴权失败即告警并停手 30 分钟 | 不把 pi-web 的登录限流刷满 |
| **长连接不被 Node 掐** | `server.requestTimeout = 0` | Node 18+ 默认 300 秒会掐断流 |

## 7. 参数

| 参数 | 默认 | 位置 | 说明 |
|---|---|---|---|
| `pollMs` | 5000 | `config.mjs` | watchdog 扫描间隔 |
| `fastSettleMs` | 1500 | `config.mjs` | 末条 assistant 带最终 `stopReason` 时的静默期 |
| `settleGraceMs` | 20000 | `config.mjs` | 末条停在 `toolUse` 时的静默期 |
| `hangMs` | 600000 | `config.mjs` | 仍在 running 但文件 10 分钟没动 → 判卡死 |
| `tailBytes` | 65536 | `config.mjs` | 读文件尾部的窗口（不够会自动放大） |
| `recentSessionMs` | 36h | `config.mjs` | 只看最近这段时间动过的会话 |
| 心跳 `ka` | 20s（5~300） | App 设置页 | 服务端 keepalive 间隔 |
| 静默判死 | 90s（30~900） | App 设置页 | 两条路都静默这么久才强制重连 |
| 轮询·已连接 | 30s（10~600） | App 设置页 | 兜底通道频率 |
| 轮询·未连接 | 10s（5~300） | App 设置页 | 断线重试频率 |
| 出口冷却 | 20s | `EndpointManager.kt` | 某个出口刚失败就不马上重试 |
| 候选清单刷新 | 每次建连 + 每 10 个心跳 | `console-server.mjs` | 隧道换域名、公网 IP 变化时手机能学到 |
| `wan.ipRefreshMs` | 600000 | `config.mjs` | 公网 IPv4 刷新间隔（动态 IP 会变） |
| `wan.gatewayPort` | 8788 | `config.mjs` | 统一出口端口，公网只暴露它 |

服务端参数可在 `~/.pi/android-link/local.json` 里覆盖（同名键），改完重启对应进程：

```json
{ "pollMs": 3000, "fastSettleMs": 800 }
```

## 8. 运维

**进程与启动**（当前不注册开机自启；需要时手动双击 BAT）

| 启动脚本 | 进程 |
|---|---|
| `run-link.bat`（经 `link-supervisor.mjs` 同时拉起下面两个，一棵进程树） | watchdog + 派发台（含中转） |
| 调试单组件：`node watchdog.mjs` / `node console-server.mjs` 前台直跑 | 同上（不再保留单独的 `.bat`，2026-09-24 已清理） |
| `run-pi-web.bat --silent` | pi-web |

**端口**：`30141` pi-web（局域网）· `8787` 派发台（0.0.0.0，局域网手机连它）· `8788` 统一出口（派发台路由 + pi-web 反代，**公网地址全部指向它**）

**文件**（都在 `~/.pi/android-link/`）

| 文件 | 内容 |
|---|---|
| `local.json` | 唯一密钥来源：密码、令牌、局域网地址、可选覆盖参数 |
| `messages.jsonl` | 消息环形缓存（最近 500 条，重启不丢） |
| `acks.jsonl` | 送达回执（每次手机收到一条追加一行） |
| `state.json` | watchdog 状态：已通知过的条目、prime 标记、鉴权失败计数 |
| `watchdog.log` / `console.log` | 结构化日志（判定、断连、推送、回执） |
| `watchdog.lock` / `console.lock` | 单实例锁 |

**验收**（改完代码/配置都跑一遍）

```bash
node verify.mjs                 # 39 项：判定逻辑、中转链路、看门狗、派发台、pi-web、手动启动检查、鉴权安全阀
node android/verify-apk.mjs     # 35 项：APK 清单断言 + 中转协议契约
```

**装/更新手机端**

```
手机浏览器打开  http://192.168.1.100:8787/app
  ① 下载 APK            （短地址 /apk，永远给目录里最新那个）
  ② 一键配置并启动       （深链 pilink://setup，自动写入地址+令牌+回执）
  ③ 电池白名单：允许
```

**手动调试**

```bash
node watchdog.mjs --once --dry            # 只判定不推送，看它会推什么
node watchdog.mjs --simulate model_error  # 把某一种判定走一遍真实发布
curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"title":"测试","message":"链路测试","priority":4}' \
  'http://127.0.0.1:8787/pi/publish?t=<令牌>'
```

## 9. 故障速查

| 症状 | 先看哪里 | 常见原因 |
|---|---|---|
| 一条通知都没有 | `watchdog.log` 有没有 `推送失败` | 看门狗是改动前启动的旧进程（未重启）；或 `派发台` 没跑 |
| 手机收不到但日志显示已推送 | `console.log` 里发布时的 `(推送流 N 条)` | `N=0` 表示手机当时没连上——会由游标补收，或检查电池白名单 |
| 通知到了但不响 | 系统通知设置（渠道重要性 / 横幅 / 免打扰） | 渠道被设为「关闭」或静默 |
| 通知延迟很久 | `watchdog.log` 的 `轮询完成` 时间戳 | `pollMs` 被调大，或 `toolUse` 情况在等 20 秒静默期 |
| 怀疑跑了两份 | `verify.mjs` 的 C6 / 进程里监听者个数 | 锁文件被删导致重复启动 |
| 什么都正常但就是不弹 | App 首屏有没有橙色告警条 | `POST_NOTIFICATIONS` 被拒 / 总开关被关 |
| 出门在外收不到 | `node wan-report.mjs` | 一个异地出口都没有（没装 cloudflared / 没 IPv6 / 没做端口映射）；或公网 IP 是 `100.64.x.x`（CGNAT，端口映射无效） |
| 统一出口 8788 没起来 | `fix-split-brain.bat` 第 7 步 / `console.log` | 多半是 `local.json` 的 `piWeb.password` 为空 —— 安全阀硬拦了（这是故意的） |
| 从公网点「打开会话」 403 | 直接开网关地址试 | 反代改写失效：pi-web 只信任 localhost/IP 字面量（见 5b 节那张表） |
