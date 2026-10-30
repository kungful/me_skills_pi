# 订阅猎手 · SubHunter

把**公开公益节点的订阅源**抓下来、去重、测活，然后一键变成 Clash / v2ray 两种订阅，
还能**每天自动同步**一次——外网断了、常用机场跑了，至少手上还有一份能用的备用节点。

- 包名：`com.hua.subhunter`
- APK：`dist/subhunter-1.0.0.apk`（约 110 KB，debug 签名，可直接安装 / 覆盖升级）
- 最低系统：Android 5.0（API 21），targetSdk 34
- 零第三方依赖：不用 Gradle、不用 AndroidX、不引任何 jar

```bash
./build.sh                                   # 打包
adb install -r dist/subhunter-1.0.0.apk      # 安装
```

![icon](res/mipmap-xxxhdpi/ic_launcher.png)

---

## 它到底做了什么

```
内置公益源 ──► 并发抓取（直连失败自动换 jsDelivr / ghproxy 镜像）
      ──► 解析 vmess / vless / trojan / ss / hysteria2 / tuic，
            Clash 名单里的 proxies 也能直接吃
      ──► 按「协议+服务器+端口+凭据」去重（1212 条原始 → 约 650 个不重复节点）
      ──► 分批 TCP 测活，按延迟排序，留下最快的 N 个
      ──► 生成两份产物：mihomo YAML + v2ray base64
```

结果全部落到本地（`clash.yaml` / `v2ray.txt` / `nodes.lst`），**没有网也能复制**——
这就是「应急备用」的字面意思。

## 四种用法（都只要一次点击）

| 客户端 | 怎么拿到订阅 |
|---|---|
| **v2rayNG / NekoBox** | 订阅页 →`复制订阅`→ 客户端「订阅分组 → + → **从剪贴板导入订阅**」 |
| **Clash Meta / mihomo** | 打开「本机订阅服务」→ `复制地址` → Clash 里「配置 → 新建 → 从 URL 导入」 |
| 任意客户端（一次性） | `复制完整 YAML` / `导出 yaml 到下载`，手动导入文件 |
| 单条节点 | 「节点」页点任意一行 → 复制该节点的分享链接 |

**本机订阅服务**是长期方案：App 起一个只监听 `127.0.0.1:8791` 的小 HTTP 服务，
`/clash` 给 mihomo、`/v2ray` 给 v2rayNG。客户端里填一次地址，以后每天点一次
「更新订阅」就吃到当天最新的一批节点（App 每天自动抓，客户端只管拉）。

> 端口可在设置里改；Android 系统杀掉 App 进程后服务会停，重新打开 App 会自动拉起来。

## 每日自动抓取

- 主调度：`AlarmManager` 每天固定时刻（默认 **04:30**）打一枪，重启后由 `BootReceiver` 重新排上
- 兜底：`JobScheduler` 24h 周期任务（Doze 下比 Alarm 可靠），开机再补跑一次
- 抓完如果发现**新节点**（按 协议+地址 比对上一轮），发通知告诉你加了几个
- 电源：抓取期间持 `PARTIAL_WAKE_LOCK`，不会半路被休眠掐断

## 「源」怎么配

内置 6 个默认启用 + 3 个备用（都在公开 GitHub 仓库，raw 地址），
抓取时每个地址都会自动展开成候选链：

```
raw.githubusercontent.com/...  →  cdn.jsdelivr.net  →  fastly / gcore
→  ghproxy.net / ghfast.top / gh-proxy.com / raw.gitmirror.com / moeyy / ghproxy.cc
```

**上次走通的镜像会被记住**，下次直接先试它，所以第二轮往往 5 秒就抓完了。
单个源最多耗 45 秒，6 个源并发 4 线程——某个源挂了不影响整体出结果。

也可以自己加源（支持：明文链接列表、整段 base64、Clash YAML 的 `proxies:` 段）。

## Clash 产物长什么样

标准 mihomo 配置：`mixed-port 7890`、fake-ip DNS、`sniffer`、
三个策略组（🚀 手动选择 / ♻️ 自动 url-test / 🔯 故障转移）、
分流规则 `LAN/CN 直连 → 其余走代理`。节点名去重、超长截断，保证 Clash 不报重名。

## 代码结构

| 文件 | 作用 |
|---|---|
| `src/.../Util.java` | Base64 / URL 解码 / 扁平 JSON / YAML 引号（纯 Java，可桌面跑） |
| `Parse.java` | 分享链接解析 + Clash `proxies:` 解析（块式 / 流式都吃） |
| `Node.java` | 节点模型：`→ Clash 条目` 与 `→ 分享链接` 双向转换 |
| `Engine.java` | 主流水线：并发抓取 → 去重 → 分批测活 → 排序截断 → 生成 |
| `Gen.java` | mihomo YAML / v2ray base64 生成，策略组与规则 |
| `LocalServer.java` | 本机订阅 HTTP 服务（127.0.0.1） |
| `Store.java` / `Worker.java` | 持久化与后台抓取（Job / 广播 / 前台服务共用） |
| `Sched.java` / `AutoJobService.java` / `AutoReceiver.java` / `BootReceiver.java` | 每日定时、通知、开机恢复 |
| `SubService.java` | 前台服务：托住本机订阅服务 + 执行自动抓取 |
| `Bridge.java` / `MainActivity.java` | WebView UI 与原生桥（复制 / 分享 / 导出 / 设置） |
| `assets/index.html` | 整个界面（暗色，四个页签，无外部资源） |

界面是 WebView + `file:///android_asset/index.html`，所以整套 UI 改起来像改网页一样快；
重活全在 Java 侧，`state()` 一个方法喂完所有渲染。

## 桌面自测（不用装机）

核心流水线是纯 Java，直接跑真源验证：

```bash
JH=/home/hua/toolchain/jdkroot/usr/lib/jvm/java-21-openjdk
$JH/bin/javac -encoding UTF-8 -d /tmp/core src/com/hua/subhunter/{Util,Node,Parse,Gen,Sources,Fetcher,Health,Engine,LocalServer}.java
$JH/bin/javac -encoding UTF-8 -cp /tmp/core -d /tmp/core tools/CoreTest.java tools/ServerTest.java
$JH/bin/java -cp /tmp/core com.hua.subhunter.CoreTest          # 抓真源，产物写 /tmp/out
$JH/bin/java -cp /tmp/core com.hua.subhunter.CoreTest --ping 60 # 带测活
$JH/bin/java -cp /tmp/core com.hua.subhunter.ServerTest         # 本机订阅服务 HTTP 冒烟
$JH/bin/java -cp /tmp/core com.hua.subhunter.ClashTest          # Clash 名单解析专项
```

生成的配置可以直接用 mihomo 本体校验（实测通过）：

```bash
mihomo -t -d /tmp/mihomo-test -f /tmp/out/clash.yaml
# configuration file /tmp/out/clash.yaml test is successful
```

## 必须知道的几件事

- **测活 ≠ 能用**。这里只做 TCP 握手（能连上端口），不代表节点真的能连外网；
  有些节点的端口是通的但协议/密码早就废了。
- **公益节点是黑盒**。它们由匿名第三方维护，可能记录流量、注入内容、随时跑路。
  不要用它们登录网银 / 主邮箱 / 任何塞了真实身份的账号。
- **节点来源合法性与可用性波动很大**。内置源随时可能改名、删库、换分支；
  失效就在「源」页关掉，或自己加一个。
- 本项目**不提供节点、不代理流量**，只做"抓取公开信息 + 格式转换 + 定时备份"。
  请遵守你所处地区的法律法规，风险自担。

## 版本

- `1.0.3` — 真机（iQOO Z10 / Android 16）实测修正：
  - **配置不再依赖 geo 数据库**：去掉 `dns.fallback` 与 `GEOIP` 规则后，mihomo 加载从 89 秒降到 **121 毫秒**，手机首次导入不会再因「下载 geoip 超时」判定配置失败
  - **抓取中切后台不再卡死**：`runFetch()` 返回是否真的启动，页面据此恢复按钮；加 20 秒无进度看门狗；`onResume` 强制与原生状态对齐
  - **`__fetchDone` 保证送达**：状态序列化失败也照样回调，按钮不会永远停在⏳
  - **Android 15+ 前台服务 6 小时上限**：实现 `onTimeout` 主动收工并保存，不再 RemoteServiceException 崩溃
- `1.0.0` — 首版：6+3 源、去重测活、Clash/v2ray 双产物、本机订阅服务、每日自动抓取与通知、离线缓存。
