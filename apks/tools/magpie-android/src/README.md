# Magpie-Android

把 [magpie](https://github.com/yetone/magpie) 装进 Android 手机，让手机**自己给自己路由**：
一个鹅卵石大小的网关跑在手机里，手机上的 App / Termux 里的 CLI 连 `127.0.0.1:3425`，
用电脑上那些订阅和 key。

界面不用重写：官方 `magpie web` 的页面本来就是按手机做的 PWA（独立 tab 栏、加到主屏幕后没有浏览器地址栏），
这里直接用一个 WebView 把它装成 App。

## 结构

```
Magpie-Android/
  AndroidManifest.xml              extractNativeLibs=true（关键）+ specialUse 前台服务
  src/com/hua/magpie/
    MainActivity.java              WebView + 启停 + 日志查看
    GwService.java                 前台服务：exec libmagpie.so，wakelock，日志，崩溃重启
    BootReceiver.java              开机自启
  res/, tools/make_icon.py         图标
  tools/fetch-binary.sh            从官方 release 取 android/arm64 二进制 → payload/libmagpie.so
  payload/libmagpie.so             Go 二进制（被打进 APK 的 lib/arm64-v8a/）
  build.sh                         aapt2 + javac + d8 + apksigner，不用 Gradle
```

跑起来的东西：

```
libmagpie.so serve --web=127.0.0.1:3430
   ├── 网关    127.0.0.1:3425   （/v1/chat/completions、/v1/messages、/v1beta/…）
   └── 控制台  127.0.0.1:3430/?k=<MAGPIE_WEB_KEY>
```

一个进程两个端口，`MAGPIE_WEB_KEY` 固定，所以 WebView 的 cookie 重启后仍有效。

## 为什么二进制必须放 lib/arm64-v8a

Android 10（API 29）起禁止 exec 应用数据目录里的文件（W^X），只有安装器解出来的
`nativeLibraryDir` 能执行。所以把二进制命名成 `libmagpie.so` 塞进 `lib/arm64-v8a/`，
manifest 里 `android:extractNativeLibs="true"`，运行时从 `applicationInfo.nativeLibraryDir` 去 exec。
（Termux 之外这是唯一合法做法。）

## 构建 / 安装

```bash
bash tools/build-cgo.sh        # 先编 cgo 版二进制（必须，见下）
bash build.sh                  # 出 Magpie.apk（约 25MB）
bash build.sh -i               # 打包 + adb install + 启动
```

> vivo/部分国产 ROM 的安装器会拦一道「已安装相同版本 / 外部来源应用」：
> 每次发版把 `AndroidManifest.xml` 和 `build.sh` 里的 `versionCode` 加一，
> 然后 `adb shell settings put global verifier_verify_adb_installs 0`，
> 再按屏幕提示点「继续安装」。

## ⚠️ 必须用 cgo 编（官方二进制在手机上解析不了 DNS）

官方 release 的 `magpie-cli-android-arm64` 用 `CGO_ENABLED=0` 编（releases 仓库 release.yml：
"The terminal-only magpie (no GUI, no cgo)"），二进制里查不到 `getaddrinfo`、也不依赖 `libc.so`。
Go 源码 `net/conf.go` 写得很直接：*"DNS requests don't work on Android, so prefer the cgo resolver"*（issue #10714）——
纯 Go 解析器要读 `/etc/resolv.conf`，Android 没有这个文件（DNS 由 netd 管），于是回落到
`127.0.0.1:53` / `[::1]:53`，全部解析失败。真机实测：

```
dial tcp: lookup models.dev on [::1]:53: read udp [::1]:…->[::1]:53: read: connection refused
dial tcp: lookup api.anthropic.com on [::1]:53: … connection refused
```

连带症状：插件页里 WorkBuddy 显示「即将上线」。那其实是 `plugins.js:495` 的
`t("Coming soon")`（title 是 `Not on npm yet`），触发条件是
`listed && !listed.github && !listed.npm?.version` —— 也就是问 npm 要版本时没问到。
DNS 一好，同一个按钮立刻变「安装」。

正确做法：`bash tools/build-cgo.sh`（需要 Go 1.26+ 和 Android NDK，脚本里默认路径
`/c/mbuild/toolchain/{go,ndk}`）。编出来 62MB，走 bionic 的 `getaddrinfo`，DNS 原生正常。

插件运行时是 Bun，magpie 也已支持 Android（`internal/plugin/bun.go` 里
`case "android": bun-linux-<arch>-android`，`BunVersion = 1.4.2`），所以插件在手机上跑得起来。

## 常驻与耗电

- 前台服务 + `PARTIAL_WAKE_LOCK`；通知栏有「停止」。
- 国产 ROM 还要手动打开：自启动、后台运行、关闭电池优化。
- 开机自启走 `BootReceiver`（可以用 `pm disable` 关掉）。
- 一天几个百分点电，重度使用建议插着电。


## 后台保活（Android 的后台很凶，尤其国产 ROM）

跑起来之后又崩又掉，查下来是两层：

1. **孤儿进程**：装新 APK 时系统只杀应用主进程，`libmagpie.so` 子进程会活下来继续占着
   3425/3430，新实例只能 `bind: address already in use` 退出，页面还会说
   "another magpie serves the gateway here"。现在启动前会扫 `/proc` 把同 uid 的
   `libmagpie.so` / `magpie-bun` 全部 `kill -9` 再等端口释放；`ensureRunning()` 也加了锁
   （onStartCommand / 看门狗 / 网络回调 / 崩后重启 四条线并发会起两个子进程）。
2. **ROM 的进程清理器（pruner）**：`dumpsys activity exit-info` 显示
   `reason=3 (LOW_MEMORY) description=pruner`，即使进程是前台服务（`importance=125`）也照杀。
   代码挡不住，只能"被杀后尽快复活"：

| 手段 | 周期 | 说明 |
|---|---|---|
| 独立进程 `:gw` | — | UI 进程死/冻不影响网关 |
| 看门狗 | 20 秒 | `/api/hello` 连续两次不应答 → 清整棵进程树重启 |
| 深探 | 60 秒 | `/api/plugins/market`，抓"网关活着但 Bun 插件宿主卡死" |
| AlarmManager 闹钟 | 2 分钟 | `setAndAllowWhileIdle`，idle 时系统降到 ~9 分钟；投递时会解冻应用 |
| JobScheduler | 15 分钟 | `setPersisted`，进程被杀、闹钟被清也还会被叫醒 |
| 网络回调 | 事件 | Wi-Fi↔4G 切换后等 6+6 秒再判，仍死才重启（避免误杀） |
| onTaskRemoved | 事件 | 划掉最近任务后重排闹钟 |
| onResume | 事件 | 回到 App 自动探活 + 重载 |

**仍然必须手动开的**（adb 改不了）：

- 设置 → 电池 → 后台耗电管理 → 允许后台高耗电
- i管家 → 应用管理 → 自启动管理 → 打开（iQOO/vivo）
- 最近任务卡片下拉 → 锁定

`adb shell cmd deviceidle whitelist +com.hua.magpie` 已经把 app 放进 Doze 白名单
（`standby-bucket=5 EXEMPTED`），但 pruner 不认它。

## 更新

上游自更新用不了（那是桌面 launcher 的逻辑）。换版本：`bash tools/fetch-binary.sh vX.Y.Z` → `bash build.sh -i`。
注意 `versionCode` 固定为 1，`adb install -r` 覆盖安装即可。
