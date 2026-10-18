# 茶叶军师（TeaStrategist）

给茶叶工厂用的**商业情报 + 决策**安卓 App。把「行情 / 全球快讯 / 军事地缘 / 关税 / 汇率 / 热搜」
抓在一起，自动分类打标，再用**你自己的大模型 API Key** 出研判、出方案。

包名 `com.hua.teastrategist`　应用名「茶叶军师」

---

## 一、它能干什么

| 页面 | 作用 | 要不要 API Key |
|---|---|---|
| 🗺 舆图 | 首页。产业链股价、汇率、出口均价、今日重点情报 | 不需要（研判那栏要） |
| 📡 情报 | 5 个源实时汇总，自动打标：军事·地缘 / 关税·贸易 / 汇率·金融 / 航运·物流 / 政策·法规 / 茶业·同业 / 消费·市场 / 能源·大宗 | 不需要 |
| ⚖️ 决策 | 填 6 项厂情 → 本地规则引擎算出「出口 vs 内销」权重 + 渠道优先级排序 | 不需要（"军师详策"要） |
| 💡 妙计 | 「把梳子卖给和尚」——输入场景/人群，出 5 个具体卖法 + 话术 | 要 |
| 📜 兵法 | 内置离线知识库：全球盘面、出口盘面、品类均价、市场分层、全渠道地图、出口前十省 | 不需要 |
| ⚙️ 设置 | API Key / 我的厂情 / 行情自选 / 数据源体检 | — |

**没填 Key 也能用**：行情、情报、决策排序、兵法库全部本地可用。
填了 Key 才有：AI 研判、90 天作战计划、创造需求方案。

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
├── res/mipmap-*/               图标（帅印 + 交叉令旗）
├── tools/make_icon.py          纯 PIL 画图标，无字体依赖
├── tools/selftest.js           逻辑自测
├── src/com/hua/teastrategist/
│   ├── MainActivity.java       WebView 壳子
│   ├── Bridge.java             JS ↔ 原生 的唯一通道
│   └── Net.java                原生 HTTP（无跨域、自动 GBK 探测、gzip）
└── assets/
    ├── index.html              6 个页面
    ├── style.css
    ├── transport.js            Tea.invoke / http / store / save / share
    ├── kb.js                   ★ 内置「兵法库」：海关数据、品类均价、渠道 ROI、12 招、决策规则
    └── app.js                  ★ 各模块逻辑
```

### 为什么网络要放原生层

WebView 里的 `fetch`/`XHR` 受同源策略限制，抓不了腾讯行情、东财、新浪这些接口。
放到 Java 层就完全没有跨域问题，还能顺手处理 GBK 编码。

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
