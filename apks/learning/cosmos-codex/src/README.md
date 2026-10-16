# 万物原理 · CosmosCodex

给"化学白痴"写的**宇宙运行手册** Android App。11 个学科、85 课、170 道题，全部离线内置。
纯 WebView 外壳 + 纯静态前端，**不需要 Gradle / AndroidX**，用 `aapt2 + javac + d8 + zipalign + apksigner` 手动构建。

## 里面有什么

| | 学科 | 课数 | 覆盖 |
|---|---|---|---|
| 🌌 | 宇宙 | 7 | 大爆炸、光速、时间、熵、暗物质 |
| ⚛️ | 物理 | 8 | 牛顿三定律、能量、热力学、相对论、量子、四大力 |
| ⚗️ | 化学 | 9 | 原子、周期表、化学键、配平、摩尔、酸碱、氧化还原、有机 |
| 🧬 | 生命 | 6 | 细胞、DNA、演化、ATP、神经、免疫 |
| 📐 | 数学 | 8 | 算术→代数→函数→几何→微积分→概率→统计→信息论 |
| 🧠 | 逻辑学 | 7 | 有效推理、谬误、归纳、悖论、决策模型 |
| 🔌 | 电子 | 7 | 欧姆定律、二极管、三极管、逻辑门、单片机 |
| 🕯️ | 哲学 | 7 | 本体论、认识论、自由意志、伦理、科学划界、意义 |
| ⚖️ | 资本与共产 | 10 | 稀缺、供需、货币、资本增殖、剩余价值、计划 vs 市场、阶级、全球化 |
| ⚔️ | 兵法与军事 | 8 | 孙子、战略/战术、后勤、情报、战争形态、名将、认知战 |
| 🔥 | 勇气与铁血 | 8 | 恐惧生理学、血性、系统＞决心、韧性、身体底座、复利 |

每一课结构固定：**一句话本质 → 打个比方 → 一步步拆开 → 想再深一点 → 常见误解 → 记住这句话 → 2 道测验**

功能：熔炉（随机 8 题 / 每题 20 秒）、全文搜索、进度与连击天数（原生 SharedPreferences 持久化）、铁血宣言。

## 目录结构

```
app/
  AndroidManifest.xml          包名 com.hua.cosmos，minSdk 21 / target 34
  java/com/hua/cosmos/MainActivity.java   WebView 外壳 + Native 桥
  res/                         主题、字符串、各密度图标
  assets/www/
    index.html                 按顺序加载 data/m01..m11 + app.js
    app.css  app.js            SPA 引擎
    data/m01..m11-*.js         全部课程内容（85 课 / 170 题）
tool/
  build.sh                     全离线构建（6 步）
  mkzip.py                     把 classes.dex 放进 APK 根目录
  make_icon.py                 PIL 生成各密度图标
  verify.js                    内容校验：模块数/课程字段/答案下标/题目完整性
  install.sh                   安装到手机（USB 或无线调试）
dist/万物原理.apk              产物
```

## 构建

```bash
bash tool/build.sh          # → dist/万物原理.apk
node tool/verify.js         # 校验内容完整性（改内容后先跑这个）
```

> `aapt2` 不认非 ASCII 路径，所以 `build.sh` 会先复制到 `C:/ccbuild` 构建，再把 APK 拷回 `dist/`。
> 依赖：Android SDK build-tools、JDK 21、Python 3、Node。

## 安装

```bash
bash tool/install.sh                       # USB 已连接
bash tool/install.sh 192.168.31.200:5555   # 无线调试（adb connect）
bash tool/install.sh pair 192.168.31.x:37xxx 123456   # 首次配对
```

或在手机上直接打开 `dist/万物原理.apk` 手动安装。

## 内容约定（改内容前必读）

- 数据格式：`window.COSMOS.modules.push({id,name,icon,hue,tag,blurb,lessons:[...]})`
- 一课 = `{id,title,essence,analogy,steps:[{h,p}],deep,myths:[{q,a}],remember,quiz:[{q,opts,a,why}]}`
- **`steps[].p` 和 `deep` 是原始 HTML**；其余字段走 `esc()`，只放行 `<b>` / `<em>`
- 用 `<b>` 加粗，不要用 Markdown 的 `**`
- 正文里不要出现裸 `<` 字符（会被当成标签起始），需要时写"小于"
- JS 单引号字符串，正文里不要出现 ASCII 单引号

## 调试

`MainActivity` 里开了 WebView 远程调试，网页 `console` 输出会打到 logcat：

```bash
adb logcat -s CosmosJS                       # 看网页 console
adb shell cat /proc/net/unix | grep webview_devtools_remote
adb forward tcp:9222 localabstract:webview_devtools_remote_<pid>
curl http://127.0.0.1:9222/json              # 列出可调试页面
```

真机已验证（vivo V2452A / iQOO Z10 Turbo，Android 16 / API 36）：11 个学科渲染、
课程页与测验、熔炉计时、搜索、原生桥写入 SharedPreferences、冷启动后进度恢复。
