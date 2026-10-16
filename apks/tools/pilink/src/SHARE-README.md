# pi-android-link · 分享版（电脑 → 手机 看门狗推送）

> 这是一份**去隐私**的整包：源码、启动 BAT、APK、自检脚本、文档都在里面，
> 不含原作者的任何 IP、路径、账号、密码、令牌。
> 拿到后先读本文，再按 [README.md](README.md) 看完整手册、按 [ARCHITECTURE.md](ARCHITECTURE.md) 看原理。

---

## 1. 这是什么

一个跑在 Windows 上的**看门狗**：它盯着 AI 编程会话（pi-web）的状态，一旦会话
**跑完 / 报错 / 被中止 / 卡死 / pi-web 挂了**，就往你安卓手机上推一条系统通知；
手机上还能一键「打开会话 / 派发台 / 让它继续跑」。

```
电脑                                        安卓手机
┌──────────────────────────────┐            ┌────────────────────┐
│ pi-web :30141                │            │ 「Pi 通知」App     │
│   会话真相来源                │  局域网 HTTP │   长连接收通知      │
│            │                  │ ─────────► │   3 个动作按钮      │
│ watchdog（进程外守护，5s 一轮）│            └────────────────────┘
│   读会话文件尾部 → 判定        │                  ▲
│            │ POST /pi/publish │            Chrome → :30141 / :8787
│ 派发台 :8787（自带消息中转）   │
└──────────────────────────────┘
```

零账号、零证书、零第三方推送服务。默认纯局域网；**出门在外也能收** —— 不用买服务器、
不租服务器、不注册账号，靠电脑自己的公网地址（免账号隧道 / 公网 IPv6 / 端口映射 / 手填地址），
程序会把这些地址作为一份清单下发给手机，手机自己挨个试。细节见 README 的「异地通知」一节。

没配任何公网地址时，行为和以前一样：手机离开这个 WiFi 就收不到，消息先存进服务端环形缓存，
回家重连后补收。

---

## 2. 5 分钟部署

### 前置

| 需要 | 说明 |
|---|---|
| Windows 10/11 + PowerShell 5.1 | 脚本用的都是内置能力 |
| Node.js 22+ | `node -v` 能跑；pi-web 需要 22 以上 |
| pi-web | `npm i -g @agegr/pi-web` |
| 安卓手机 | Android 8.0+（API 26） |
| 同一个 WiFi | 电脑与手机要在同一网段，且路由器没开 AP 隔离 |

### 步骤

```powershell
# 1) 生成配置 + 启动脚本（顺便放行防火墙、跑一遍验收）
cd <解压出来的目录>
powershell -ExecutionPolicy Bypass -File setup.ps1
```

记下它打印的**局域网地址**和**派发台令牌**（手机上要用）。

```powershell
# 2) 起链路：watchdog + 派发台（一个终端窗口）
.\run-link.bat

# 3) 想在手机浏览器里看完整 UI / 派活，再单独起 pi-web
.\run-pi-web.bat
```

> ⚠️ **只能有一个 pi-web 实例**。旧的还占着 `127.0.0.1:30141` 而你又起一个绑 `0.0.0.0`，
> 会「双实例脑裂」，看门狗会对正在跑的会话**误报中断**。
> 不确定就跑 `.\fix-split-brain.bat`（体检 + 修复），复查用 `node verify.mjs`（看 E3 项）。

### 手机装 App

```
手机浏览器打开  http://<你的局域网IP>:8787/app
  ① 点「下载 APK」        —— 短地址 /apk，永远给目录里最新那个
  ② 点「一键配置并启动」   —— 深链 pilink://setup，自动写好地址+令牌+回执
  ③ 弹「电池白名单」就点「去设置」并允许
```

APK 就在本包的 `apk/` 里，派发台的 `/apk` 路由直接分发它（永远取目录里 mtime 最新的那个）。
换版本：把新 APK 丢进 `apk/` 即可，手机链接不用改。

安卓会报「未知来源 / Play 保护机制已阻止」，选**仍然安装**。

### 手机端必做三件事（不做等于没装）

1. **电池白名单** —— 设置 → 应用管理 → Pi 通知 → 耗电管理 → 允许后台活动
2. **自启动** —— 同页 → 自启动 → 允许
3. **锁后台** —— 最近任务里把这个卡片下拉加锁

**白名单是硬要求**：Android 息屏闲置进 Doze 会给所有应用断网，只有白名单被豁免。

ColorOS / MIUI / EMUI 这类深度省电系统尤其凶，不做第 1 条基本必挂。

### 自检

```powershell
node verify.mjs                    # 端到端自检（含双实例脑裂 E3、判定覆盖、自检推送）
node android/verify-apk.mjs apk/pilink-0.6.0-debug.apk   # APK 清单 17 项断言（B 组要派发台在跑）
```

---

## 3. 拿到手必须改的 3 个地方

| 位置 | 改什么 | 不改的后果 |
|---|---|---|
| `~/.pi/android-link/local.json` → `lan.host` | 你这台机器的局域网 IP | 手机连不上；通知深链跳到不存在的地址 |
| `~/.pi/android-link/local.json` → `piWeb.password` | `setup.ps1` 随机生成，**别改成空** | 无密码绑 `0.0.0.0` = 把整台机器交给同 WiFi 的人（pi-web 能执行任意命令） |
| `~/.pi/android-link/local.json` → `defaultCwd` / `quickCommands[].cwd` | 你真正干活的目录 | 手机上「一键让它继续跑」会派到错目录 |

`local.json` 是**本机唯一秘密来源**，`setup.ps1` 会把它的 ACL 收到只有当前用户可读。
它不在本包里，模板见 [local.json.example](local.json.example)（里面全是占位值，**不要**照抄密码/令牌）。

想彻底免密码（只在自己信任的网络里）：`setup.ps1 -NoPassword -ScriptsOnly` + `fix-split-brain.bat`。

---

## 4. 文件清单

### 电脑端（跑看门狗和派发台）

| 文件 | 作用 |
|---|---|
| `watchdog.mjs` | **看门狗本体**：轮询会话 → 判定 → 推送 |
| `link-supervisor.mjs` | 监管 watchdog + 派发台，任一崩了自动重启 |
| `console-server.mjs` | 派发台：手机 UI + 自研消息中转 `/pi/*` + `/apk` 分发 |
| `config.mjs` | 统一读 `local.json`（含所有默认兜底值） |
| `lib/broker.mjs` | 推送出口（POST `/pi/publish`，永不抛异常） |
| `lib/classify.mjs` `lib/classify-cases.mjs` | 会话尾部文本 → 判定结果（完成/报错/中止/截断/工具中断/卡死） |
| `lib/notify-plan.mjs` | 判定结果 → 手机上那句话（纯函数，可断言） |
| `lib/piweb.mjs` | pi-web API 客户端（认证、限流退避） |
| `lib/store.mjs` | 环形缓存 500 条 + 游标（手机离线也不丢） |
| `lib/single-instance.mjs` | 单实例互斥（Windows 上端口不能当锁，必须用 socket） |
| `setup.ps1` | 一键部署：生成 `local.json`、写启动脚本、放行防火墙、跑验收 |
| `run-link.bat` | 启动器：watchdog + 派发台（一个窗口） |
| `run-pi-web.bat` | 启动器：pi-web 绑 `0.0.0.0:30141`（手机可达） |
| `pi-web-env.cjs` | 启动前注入 pi 包根目录（运行时用 `npm root -g` 推导，不写死路径） |
| `fix-split-brain.bat` / `.ps1` | pi-web 双实例脑裂体检 / 修复器 |
| `verify.mjs` | 端到端自检（确定性断言） |
| `web/` | 派发台的 PWA 图标与 manifest |
| `make-icons.mjs` | 重新生成 `web/` 图标 |

### 手机端

| 文件 | 作用 |
|---|---|
| `apk/pilink-0.6.0-debug.apk` | 预编译好的订阅端（debug 签名，**不能**上架应用商店） |
| `android/app/src/main/java/io/pilink/*.kt` | App 全部源码（前台服务 + NDJSON 长连接 + 系统通知） |
| `android/app/build.gradle.kts` 等 | Gradle 配置（只依赖 OkHttp + 协程） |
| `android/verify-apk.mjs` | APK 清单 17 项 + 协议契约断言 |

### 文档

| 文件 | 内容 |
|---|---|
| `README.md` | 完整手册：部署、判定表、认证模式、排障、卸载 |
| `ARCHITECTURE.md` | 链路原理、协议、可靠性设计、参数、故障速查 |
| `android/README.md` | App 侧设计、构建与装机 |
| `DE-PRIVACY.md` | **去隐私清单**：删了什么、替换成什么、你自己还要检查什么 |
| `local.json.example` | 配置模板（占位值） |

---

## 5. 目录里刻意**没有**的东西

- `local.json`（密码 + 令牌）—— 只在你机器的 `~/.pi/android-link/` 里
- `android/local.properties`（SDK 路径）—— 模板见 `android/local.properties.example`
- `android/.gradle/`、`android/app/build/` 构建产物与缓存
- 任何 `*.log`、`*report*.txt`（修复报告里含 pi-web 密码）

---

## 6. 许可与免责

源码随包附带使用，未附 LICENSE 文件：**你要用就自己加一个**（MIT / Apache-2.0 都行）。
APK 是 debug 签名，仅供自用与内部分发。

这套东西默认**只监听局域网**，并且 pi-web 本身能执行任意命令。

「异地通知」功能会把统一出口（:8788）暴露到公网（免账号隧道 / IPv6 / 端口映射）。
为了避免裸奔，它带一个**硬安全阀**：`local.json` 的 `piWeb.password` 为空时，
统一出口和隧道都拒绝启动（日志里会写明原因）。也就是说 —— **异地功能必须配密码才能用**，
这是有意的。想要更严就只留隧道（随机域名、无端口映射），或者自己套一层 VPN / TLS 反代。
