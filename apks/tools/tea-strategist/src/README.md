# 茶叶军师（TeaStrategist）

给茶叶工厂用的**商业情报 + 决策 + 客户台账**安卓 App。把「行情 / 全球快讯 / 军事地缘 / 关税 / 汇率 / 热搜」
抓在一起，自动分类打标，用本地规则引擎算渠道优先级，再用**你自己的大模型 API Key** 出研判、出方案。

包名 `com.hua.teastrategist`　应用名「茶叶军师」　版本 1.1

---

## 一、它能干什么

| 页面 | 作用 | 要不要 API Key |
|---|---|---|
| 🗺 舆图 | 首页。**军师晨报** + 产业链股价、汇率、出口均价、今日重点情报、AI 研判 | 研判要 |
| 📡 情报 | 5 个源实时汇总，自动打标：军事·地缘 / 关税·贸易 / 汇率·金融 / 航运·物流 / 政策·法规 / 茶业·同业 / 消费·市场 / 能源·大宗。点一条看详情、**一键译中文**、让军师分析 | 翻译/分析要 |
| ⚖️ 决策 | 填 6 项厂情 → 本地规则引擎算出「出口 vs 内销」权重 + 渠道优先级排序 | 详策要 |
| 📒 台账 | 客户/渠道台账：类型、状态、报价、数量、下次跟进、备注；到期自动置顶变红；导出 CSV；「问军师」看这个客户怎么推 | 问军师要 |
| 💡 妙计 | 「把梳子卖给和尚」——输入场景/人群，出 5 个具体卖法 + 话术 | 要 |
| 📜 兵法 | 内置离线知识库：全球盘面、出口盘面、品类均价、市场分层、全渠道 ROI 地图、出口前十省 | 不需要 |
| ⚙️ 设置 | API Key / 我的厂情 / 行情自选 / **军师晨报** / 数据源体检 | — |

**没填 Key 也能用**：行情、情报、决策排序、客户台账、兵法库全部本地可用。
填了 Key 才有：AI 研判、90 天作战计划、创造需求方案、情报翻译、客户话术。

### 军师晨报

每天定时在你设定的时间（默认 07:30）推送一条通知，内容是：

```
【茶叶军师 · 晨报 10月19日】

▎今天要跟进的客户
杭州外贸、××酒店(逾期)

▎要盯的事
1. 胡塞武装称沙特空袭也门北部致9死17伤　[军事·地缘]
2. 中欧启动关税磋商　[关税·贸易]
...

▎盘面
蜜雪集团 167.5 +0.78%　|　古茗 21.4 -0.65%
USD/CNY 6.7029

▎军师一句
（有 API Key 时，大模型给一句研判）
```

- 全程在**原生层**跑（`AlarmManager` + `BroadcastReceiver`），不依赖 App 是否打开。
- 开机后自动重排闹钟（`BootReceiver`）。
- 点通知直接跳进 App 展开晨报。
- 会连带提醒台账里**今天到期/已逾期**的客户。

### 客户台账

字段：客户名 / 类型（批发商·新茶饮餐饮·企业采购·外贸出口·商超渠道·电商直播）/ 状态（待跟进·已报价·成交·流失·复购）/ 联系人 / 电话 / 品类 / 报价 / 数量 / 下次跟进 / 备注。

- 到期的自动排到最前面并标红，晨报里也会带上。
- 一键「+7 天」推下一次跟进。
- 导出 CSV（带 BOM，Excel 直接打开不乱码）。
- 存 `getFilesDir()/data/ledger.json`，App 私有目录，不需要存储权限。

### 情报翻译

- 自动识别外文条目（中文字符在「中文+字母」里占比低于一半），标题旁标「外文」。
- 点进去单独译，或一键「全部译中文」（一次最多 12 条）。
- 译文会缓存到本地，不重复花钱。

---

## 二、数据源（全部免费、无需 key，已实测）

| 数据 | 接口 | 说明 |
|---|---|---|
| 实时行情 | `qt.gtimg.cn` | 腾讯行情。**GBK 编码**。A股/HK/US 都支持 |
| 7×24 全球快讯 | `np-weblist.eastmoney.com` | 东财。含军事冲突、关税、能源、航运 |
| 财经要闻 | `np-listapi.eastmoney.com` | 东财 |
| 全网热讯 | `feed.mix.sina.com.cn` lid=2509 | 新浪滚播 |
| 国际要闻 | `feed.mix.sina.com.cn` lid=2511 | 新浪国际 |
| 百度热搜 | `top.baidu.com/api/board` | 实时热榜 |
| 汇率 | `open.er-api.com` | 含全球货币，算出口报价用 |

> ⚠️ 微博热搜、新华网 RSS、中新网军事 RSS 都试过，要么 403 要么停更（2020/2022），已弃用。

---

## 三、大模型接入

设置页选服务商，填 Key 即可。预设：DeepSeek（推荐）、通义千问、智谱 GLM、Kimi、硅基流动、OpenAI，或自定义 URL。

- Key 存在 Android `SharedPreferences`（本地），**只用于直连你选的那家接口**，不经任何第三方服务器。
- 接口按 OpenAI `chat/completions` 格式调用，所以任何兼容该格式的服务都能用。

---

## 四、构建

```bash
cd TeaStrategist-Android

bash build.sh          # 只打包 → 茶叶军师.apk
bash build.sh -i       # 打包 + 装到手机 + 启动
```

不用 Gradle、不联网，只用 Android SDK 的 build-tools（aapt2 / d8 / zipalign / apksigner）。
首次构建若没有 `debug.keystore` 会自动用 keytool 生成。

**依赖**：Android SDK（platform 34-36 + build-tools 36）、JDK、Python3 + Pillow（生成图标）。
JDK 必须用 **21**（脚本会自动找 `~/.gradle/jdks/eclipse_adoptium-21-*`）；
系统默认的 JDK 24 跑 apksigner 会受 native-access 限制。

### 自测

```bash
node tools/selftest.js
```

把三个前端文件拼起来在 Node 里跑（DOM 打桩、网络走真 fetch），验证 5 个数据源的
抓取+解析、情报打标、决策引擎、Markdown 渲染。当前 **11/11 通过**。

---

## 五、工程结构

```
TeaStrategist-Android/
├── build.sh                    纯 SDK 打包脚本
├── AndroidManifest.xml
├── res/values/                 主题（墨绿+鎏金）
├── res/mipmap-*/               图标（帅印金环 + 交叉茶叶令旗）
├── tools/make_icon.py          纯 PIL 画图标（4 倍超采样后 LANCZOS 缩回），无字体依赖
├── tools/selftest.js           逻辑自测（15 项）
├── src/com/hua/teastrategist/
│   ├── MainActivity.java       WebView 壳子 + 通知权限 + 通知点击落地
│   ├── Bridge.java             JS ↔ 原生 的唯一通道
│   ├── Net.java                原生 HTTP（无跨域、自动 GBK 探测、gzip）
│   ├── Io.java                 本地文档读写（客户台账）
│   ├── Briefing.java           军师晨报：抓数据→打标排序→可选 AI→通知
│   ├── BriefingReceiver.java   闹钟触发
│   └── BootReceiver.java       开机重排闹钟
└── assets/
    ├── index.html              7 个页面 + 底部弹层
    ├── style.css
    ├── transport.js            TeaAPI.invoke / http / store / readDoc / briefing / notify
    ├── kb.js                   ★ 内置「兵法库」：海关数据、品类均价、渠道 ROI、12 招、决策规则
    └── app.js                  ★ 各模块逻辑（含 Ledger / Brief / 情报翻译 / Sheet）
```

### 为什么网络要放原生层

WebView 里的 `fetch`/`XHR` 受同源策略限制，抓不了腾讯行情、东财、新浪这些接口。
放到 Java 层就完全没有跨域问题，还能顺手处理 GBK 编码。

### 内侧函数名注意

`window.Tea` 是原生桥对象（`@JavascriptInterface`），**不能覆盖**。
页面里的模块叫 `Tea`（模块级 const），内联 `onclick` 里要用 `window.TeaAPI`。
所有模块都在 `app.js` 末尾 `Object.assign(window, {...})` 挂出去，内联事件才拿得到。

### 新增一个原生能力

1. `Bridge.java` 的 `switch (op)` 里加 case
2. `transport.js` 里包一层
3. `assets/` 里调用

不需要重编 Java 的改动（纯 JS/CSS）只需重新打包，秒级完成。

---

## 六、踩过的坑（重要）

1. **别把变量命名为 `TMP` / `TEMP`**。它们是 Windows/JVM 的临时目录环境变量；
   bash 对**已导出的**变量赋值会保持导出，于是 apksigner 拿到 `TMP=<输出路径>` 后
   会先把那个路径建成**目录**，再往里写文件 → `FileNotFoundException: 拒绝访问`。
   这个坑排查了很久，脚本里现在叫 `SIGNED_PKG`。
2. **`apksigner.bat` 别在 git-bash 下用**。它的 `set params=%params% %1` 参数重建会出问题。
   直接 `java -jar $BT/lib/apksigner.jar`。
3. **JDK 24 跑 apksigner 会崩**（`System::loadLibrary` native-access 限制）。用 21。
4. **腾讯行情是 GBK**，不转码就是乱码。`Net.java` 里做了 charset 探测 + 回退重解。
5. 图标里的中文字需要字体，所以图标用纯几何图形画（帅印金环 + 两片茶叶交叉成令旗）。
6. **`const` 不会被挂到 `window` 上**，内联 `onclick="Foo.bar()"` 里的 `Foo` 虽然是全局 `const`
   通常也能解析到，但不保险；本项目统一在 `app.js` 末尾 `Object.assign(window, {...})` 显式导出。
   且**千万别导出 `Tea`** —— `window.Tea` 是原生桥对象，覆盖了 App 就再也连不上网。
7. 通知权限（API 33+ 的 `POST_NOTIFICATIONS`）不在 Manifest 里声明就能用，**必须运行时申请**，
   否则晨报发了也看不见。

---

## 七、GitHub 备份

已登记进 `apk-github-sync`（`~/.pi/agent/apk-sync.json` 的 `apps`），源与 APK 镜像到：

```
https://github.com/kungful/me_skills_pi → apks/tools/tea-strategist/
```

改完代码重新编出 APK 后，同步会自动带上新包（脚本按 mtime 取最新的 `*.apk`）。
手动同步：

```bash
python ~/.pi/agent/skills/apk-github-sync/scripts/apk_sync.py
```

> ⚠️ 仓库是**公开**的，`debug.keystore` 会被一起同步（密码是公开的 `android`）。
> 如果哪天要用它做正式发布签名，先把 keystore 换成自己的并移出源码目录。
