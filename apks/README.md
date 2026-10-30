# Pi 开发的 APK 软件包

本目录由 [`apk-github-sync`](../skills/apk-github-sync/) 自动从本机镜像同步。
最后同步：**2026-10-30 21:32:13**　|　共 **15** 个应用　|　APK 合计 **81.0 MB**

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
| **词打** | 1.5 | [`vocabtype.apk`](learning/vocabtype/vocabtype.apk) | [`src/`](learning/vocabtype/src/) | 39.8 MB | 打字记单词：播放器（列表/单组/随机循环、定时关闭、收藏、播放列表、快进快退）+ 后台锁屏播放 + 有道/百度/微软神经语音三种免费发音，中文可批量预合成 |

## 工具

| 应用 | 版本 | APK | 源码 | 体积 | 说明 |
|---|---|---|---|---|---|
| **CPE140 控制台 (PC)** | 1.4.0 | - | [`src/`](tools/cpe140-ctrl/src/) | 0 B | 逆向 CPE140/BHU BXO2000n-2S-Lite 中继器的完全控制台：免认证 Web API 读配置 + timectrl root 命令注入 RCE；CLI + tkinter GUI（六标签）；断网取证诊断 diagnose（逐层盘点 + 判定假断网/上行/宽带/DNS）+ 分级软修复 fix（六级阶梯从轻到重，一通就停）+ 断网看门狗（重启前先软修；30 分钟冷却 + 单次断网最多重启 3 次，超限转 6 小时长退避，不会无限重启）；新机器一键部署 provision（验注入通道 + 备份整片 flash + 装软修/看门狗 + 回读核对 + 可选挂 cron）；修回显通道丢失（/tmp/.cpeout 被清而 /www/.cpeout 符号链接还在 -> GET 回 404 网页，旧版会把 HTML 当命令输出；注意本工具 close() 退出时自己也会拆这条通道，手机 App 那头会因此撞上 404）；命令手册 howto；含脱敏报告 |
| **CPE140 控制台 (安卓)** | 1.4.2 | [`cpe140-ctrl-android.apk`](tools/cpe140-ctrl-android/cpe140-ctrl-android.apk) | [`src/`](tools/cpe140-ctrl-android/src/) | 5.3 MB | 手机版完全控制台：概览/客户端/配置/root 终端/维护（换新机器一键部署 + 一键断网诊断 + 分级软修救网 + 整片 flash 备份 + 断网看门狗自动重启 + 命令手册）；v1.4.2 修一个布局坑（BtnWide 的 0dp+weight 放进竖向卡片会被量成 0 宽 -> 有 4 个按钮一直看不见：「DHCP 客户端列表」「扫描周边 WiFi」「写入」「恢复出厂设置」；新增 BtnLine 样式修正）；v1.4.1 加「一键部署」（验型号/验注入通道/验 uid=0 → 装不加 flash 自分级软修+看门狗 → ls -l 回读核对 → 看连通性，默认落到只记录模式）；v1.4.0 修回显通道丢失（设备重启后 /tmp 被清、或 PC 工具退出时 rm -f /www/.cpeout，断链后 GET /.cpeout 回 404 网页而旧版当成命令输出显示）—— 现在认得出来并自动重铺通道、重读、必要时重跑命令，另加「重铺连接通道」与「看请求日志」两个手动按钮；看门狗重启前先软修、带重启上限防无限重启；纯 Java + SAF 零存储权限；深色自绘 UI |
| **Pi 通知 (piLink)** | 0.7.0 | [`pilink.apk`](tools/pilink/pilink.apk) | [`src/`](tools/pilink/src/) | 1.9 MB | 把 pi / pi-web 的通知与派发链路接到安卓手机 |
| **三角力学计算器** | 1.0 | [`trig-mech.apk`](tools/trig-mech/trig-mech.apk) | [`src/`](tools/trig-mech/src/) | 77.1 KB | 三角函数边长可视化求解 + 7 个建筑力学计算器（坡度/荷载/梁/截面/应力/斜杆/斜面），纯离线 |
| **太阳网控制器** | 1.0 | [`sunnet.apk`](tools/sunnet/sunnet.apk) | [`src/`](tools/sunnet/src/) | 777.6 KB | 风光雨自动控制：BLE / WiFi 控制 ESP32 太阳网节点 |
| **棚架受力分析** | 1.0 | [`canopy-struct.apk`](tools/canopy-struct/canopy-struct.apk) | [`src/`](tools/canopy-struct/src/) | 261.4 KB | L形墙内角太阳网车棚受力分析：GB50009风荷载 + 平面刚架矩阵位移法 + 柱脚/基础抗拔抗倾覆校核 + three.js三维可视化 |
| **茶叶军师** | 1.2 | [`tea-strategist.apk`](tools/tea-strategist/tea-strategist.apk) | [`src/`](tools/tea-strategist/src/) | 129.1 KB | 茶叶工厂的商业情报+决策台：行情/7×24全球快讯(含军事地缘)/财经要闻/新浪国际/百度热搜/汇率 六源聚合，自动打 8 类标签；本地规则引擎算「出口vs内销」权重与渠道优先级；客户台账(状态/报价/跟进提醒/导出CSV)；军师晨报(AlarmManager 定时在原生层生成 + 通知栏推送，连带到期客户提醒)；把梳子卖给和尚 12 招生成器；内置冰糖谱：海关出口数据/品类均价/市场分层/全渠道ROI地图。大模型走用户自填 API Key(DeepSeek/通义/智谱/Kimi/硅基流动/OpenAI)，情报一键翻译。纯 SDK 打包，离线可用 |
| **需求雷达** | - | [`demand-radar.apk`](tools/demand-radar/demand-radar.apk) | [`src/`](tools/demand-radar/src/) | 857.4 KB | 从公开渠道挖掘市场需求信号，打分聚簇出机会榜 |
