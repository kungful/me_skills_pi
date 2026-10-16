# Pi 开发的 APK 软件包

本目录由 [`apk-github-sync`](../skills/apk-github-sync/) 自动从本机镜像同步。
最后同步：**2026-10-16 23:55:41**　|　共 **10** 个应用　|　APK 合计 **41.5 MB**

每个应用一个子目录，里面有编译好的 APK 和对应的源代码：

```
apks/<分类>/<应用>/
  <slug>.apk     # 编译产物
  meta.json      # 版本 / 体积 / sha256 / 来源
  src/           # 源代码快照（已剔除 build、缓存等）
```

> ⚠️ 本仓库是**公开**的，源代码里可能带有本地签名用的 keystore。
> 如果不想公开，请把仓库改成 private，或在本机 `apk-sync.json` 里加排除规则。

## 设计与演示

| 应用 | 版本 | APK | 源码 | 体积 | 说明 |
|---|---|---|---|---|---|
| **跑图助手** | 1.0 | [`paintbox.apk`](design/paintbox/paintbox.apk) | [`src/`](design/paintbox/src/) | 96.9 KB | 连本机 ComfyUI / 跑图服务看图与下载 |
| **钢琴墙 3D** | 1.0 | [`pianowall.apk`](design/pianowall/pianowall.apk) | [`src/`](design/pianowall/src/) | 221.2 KB | 钢琴键盘图案墙的三维演示 + 全套带尺寸施工图 |

## 学习 / 科普

| 应用 | 版本 | APK | 源码 | 体积 | 说明 |
|---|---|---|---|---|---|
| **万物原理** | 1.0 | [`cosmos-codex.apk`](learning/cosmos-codex/cosmos-codex.apk) | [`src/`](learning/cosmos-codex/src/) | 249.9 KB | 宇宙运行手册：11 学科 85 课 170 题，纯离线 WebView |
| **单词突围** | 1.0 | [`wordrush.apk`](learning/wordrush/wordrush.apk) | [`src/`](learning/wordrush/src/) | 5.5 MB | 单词闯关游戏 |
| **生活算法** | 1.0.0 | [`life-algo.apk`](learning/life-algo/life-algo.apk) | [`src/`](learning/life-algo/src/) | 16.5 MB | 离线生活算法：穿搭/营养/睡眠/训练 + 各种计算器 |
| **观天下** | 1.0 | [`guantianxia.apk`](learning/guantianxia/guantianxia.apk) | [`src/`](learning/guantianxia/src/) | 9.4 MB | 新闻 / 财经 / 书架 聚合阅读 |
| **词打** | 1.0 | [`vocabtype.apk`](learning/vocabtype/vocabtype.apk) | [`src/`](learning/vocabtype/src/) | 6.8 MB | 单词打字背单词 |

## 工具

| 应用 | 版本 | APK | 源码 | 体积 | 说明 |
|---|---|---|---|---|---|
| **Pi 通知 (piLink)** | 0.7.0 | [`pilink.apk`](tools/pilink/pilink.apk) | [`src/`](tools/pilink/src/) | 1.9 MB | 把 pi / pi-web 的通知与派发链路接到安卓手机 |
| **太阳网控制器** | 1.0 | [`sunnet.apk`](tools/sunnet/sunnet.apk) | [`src/`](tools/sunnet/src/) | 57.1 KB | 风光雨自动控制：BLE / WiFi 控制 ESP32 太阳网节点 |
| **需求雷达** | - | [`demand-radar.apk`](tools/demand-radar/demand-radar.apk) | [`src/`](tools/demand-radar/src/) | 857.4 KB | 从公开渠道挖掘市场需求信号，打分聚簇出机会榜 |
