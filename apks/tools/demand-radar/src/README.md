# 需求雷达 · demand-radar

自动从**公开渠道**挖掘真实市场需求信号，打分、聚簇成「机会主题」，输出带原始证据的
Markdown / HTML 报告 —— 用来看**该做什么产品、能怎么收钱**。

> 核心逻辑：需求不是靠猜的，是**别人已经说出口的抱怨、搜索、求助、求替代**。
> 把散落在各处的这些话收集起来，按痛感 / 付费意愿 / 跨源证据量排序，就是机会榜。

---

## 一、5 分钟上手

```bash
cd demand-radar

# Windows 用自带的 venv Python（已装好 jieba / rich / Flask / lxml）
set PY=C:\Users\hua\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe

%PY% -m demand_radar run          # 一键：采集 → 打分 → 聚簇 → 出报告
%PY% -m demand_radar top -n 20    # 终端里直接看机会榜
%PY% -m demand_radar report --open  # 生成报告并用浏览器打开看板
```

或者双击 `run.bat`（等价于 `run`）。

首次安装依赖：

```bash
pip install -r requirements.txt      # requests PyYAML lxml jieba Flask flask-cors
```

---

## 二、命令一览

| 命令 | 作用 |
|---|---|
| `run` | 一键：采集 + 分析 + 生成报告 |
| `collect [--only a,b] [--loop --interval 30]` | 只采集；`--loop` 常驻定时采集（interval 单位=分钟） |
| `analyze [--days 90]` | 对库里素材重新打分并聚合主题（改词典后必跑） |
| `report [--days 90 --top 30 --open]` | 生成 `.md` / `.html` / `.csv` 报告 |
| `top [-n 20]` | 终端机会榜 |
| `watch [--interval 3 --duration 600]` | **监听手机屏幕**（人机协作采集） |
| `capture [--save]` | 抓一次手机当前屏幕并试打分 |
| `phone` | 检查手机连接状态 |
| `sources` | 查看采集源开关与权重 |
| `status` | 查看库存数据情况 |
| `serve [--port 8787 --open]` | 启动本地 Web 看板（含后台跑采集的按钮） |

入口统一是 `python -m demand_radar <命令>`。

---

## 三、数据源（全部是公开信息 / 自己账号）

| 源 | 内容 | 默认 | 为什么有价值 |
|---|---|---|---|
| `baidu_sug` | 百度搜索下拉联想词 | ✅ | **最直接的隐性需求**：人搜什么，就是想解决什么 |
| `appstore` | App Store 中国区「差评 + 求功能」评论 | ✅ | 差评 = 别人做烂了但需求真实存在 = 你的机会 |
| `github_issues` | GitHub Issue 里的 "is there a tool / I wish" | ✅ | 开发者工具类需求，付费能力强 |
| `hackernews` | HN Algolia 搜索需求句式 | ✅ | 英文市场同类需求，可做海外产品 |
| `douyin_hot` / `baidu_hot` | 热搜榜 | ✅ | 情绪与话题热度，判断时机 |
| `juejin` / `rss` | 掘金推荐流、少数派 / 36氪 RSS | ✅ | 行业风向、工具评测里的痛点 |
| `android_screen` | **手机屏幕抓取**（ADB） | ✅ | 小红书 / 抖音 / 闲鱼等封闭 App 的唯一合规入口 |
| `weibo` | 微博关键词搜索 | ⭕ 关闭 | 需自己填 Cookie，默认关闭 |

抓不了的源（Google / Reddit / V2EX 等在当前网络不可达）会自动跳过，不影响整体运行。

---

## 四、手机采集（人机协作，不碰风控红线）

设计上**不做全自动刷 App**——封闭平台全自动 UI 操作有封号 + 法律风险。
本工具采用「**你刷，我读**」：你正常用手翻内容，工具定时读当前屏幕文本。

```bash
# 1. 手机开 USB 调试，插上电脑，弹窗点「允许」
python -m demand_radar phone      # 确认连上

# 2. 手动翻小红书/闲鱼/抖音，遇到高价值内容停一下
python -m demand_radar capture --save     # 抓当前屏幕并入库

# 3. 或者挂着监听，你正常刷，它自动记录每一屏
python -m demand_radar watch --interval 3 --duration 900
```

原理：`adb shell uiautomator dump` 取 UI 文本；若文本为空（Canvas/Flutter 类页面），
自动回退到 `adb exec-out screencap -p` + Windows 自带 OCR（`zh-Hans-CN`），无需装额外 OCR。

**无线模式（不用一直插线）**

```bash
python -m demand_radar wireless          # 插一次线，切成无线 ADB
python -m demand_radar wireless --scan   # 手机换 IP / 掉线后，扫网段自动找回来
```

vivo 等机型息屏久了会自己关掉无线调试，掉线就重跑 `wireless --scan`（或再插一次线）。

### 4.1 手机 App（不用电脑，无障碍读屏）

上面的方案需要插线/连 ADB。**手机版 App** 用 Android 无障碍服务直接读屏，
装到手机上就能独立跑：不需要电脑、不需要 root、不需要 ADB、不需要联网。

```bash
# 构建（产出 app-debug.apk）
C:\Users\hua\dev\demand-radar-android\build.bat

# 构建并安装到手机
C:\Users\hua\dev\demand-radar-android\build.bat install
```

装好后在手机上：
1. 打开「需求雷达」→ 点「① 开启无障碍读屏权限」→ 已下载的服务 → 需求雷达 → 打开
2. 正常刷小红书 / 闲鱼 / 转转（抖音这类娱乐流一般没需求信号，抓到但分数低，正常）
3. 回 App 点「重新分析」看机会榜；点「导出数据」把素材导成 JSON

**权限与边界**
- 只用无障碍 **读取**屏幕文字，从不模拟点击/滑动/翻页（服务里没有任何 `dispatchGesture`）。
- 默认**只采白名单 App**（13 个）；桌面/系统 UI/输入法/本 App 一律跳过。
- 同一 App 1.5 秒节流 + 内容哈希去重 + 相邻屏重合度 >75% 视为重复；全程本机 SQLite，不联网上传。
- App 内置「运行日志」，每一屏为什么被采、为什么被跳过都看得到。

**手机版与电脑版的关系**
共用同一份 `config/keywords.yaml`（构建时打包成 `assets/keywords.json`），
词表与打分公式完全一致，所以手机导出的 JSON 拷回电脑可与网络源数据合并分析。

**合规边界（内置约束）**
- 只读当前屏幕，不模拟点击、不批量拉取；`auto_swipe` 自动翻页**默认关闭**，开启前请自行评估风险。
- 只用公开信息与自己账号可见的内容，不抓私密数据。
- 各源都做了请求间隔限制（`min_interval`），不并发轰站。

---

## 五、打分与聚簇（可解释，不含玄学）

**单条素材**
```
显式信号 = 痛点句式权重和（求推荐/有没有/太麻烦/求替代/愿意付费/I wish there was…）
隐含需求 = 源先验（搜索联想 0.75、差评 0.6、需求检索 0.8、热榜 0.25…）
raw = 0.52*显式信号 + 0.16*付费意愿 + 0.12*源先验 + 0.12*源热度 + 0.08*命中领域词
需求分 = raw × 源权重 × 文本质量系数
痛感 = max(显式痛点分, 源先验×80)     ← 搜索/差评本身就是需求，不该因为"没写痛点词"被埋没
```

**机会主题**（按领域词分桶，一个桶 = 一个可落地赛道）
```
raw = 0.38*痛感 + 0.20*付费 + 0.09*紧迫 + 0.13*证据量 + 0.11*跨源多样性 + 0.05*热度 + 0.04*新鲜度
score = raw × 信号门槛 × 证据门槛 × 增长趋势 × 蓝海加成
  信号门槛 = 0.30 + 0.70*clamp(痛感/0.5)      ← 没有需求信号的主题直接压到很低
  证据门槛 = 0.45 + 0.55*证据量              ← 只有一两条证据的，标记为「待验证」
```
- 证据 < 2 条的主题不进入主榜（`thresholds.min_topic_items`）。
- 「零散需求信号 · 待归类」是未成规模的池子，强制排在最后。
- 通用词（工具/软件/AI/API…）**不能**单独当主题，只能做辅助关键词。

**变现路径不是猜的**：`config/keywords.yaml` 里每个赛道都写了 `money` 字段
（如 `记账 → 订阅 ¥12-29/月；表格模板包 ¥9.9-29`），报告里直接给出定价区间。
`mat` 字段标记成熟度（0=蓝海，1=可做，2=红海），红海赛道会明确提示。

---

## 六、目录结构

```
demand-radar/
├── run.bat                     # 双击一键跑
├── requirements.txt
├── config/
│   ├── sources.yaml            # 采集源开关 / 权重 / 限额 / 关键词种子
│   └── keywords.yaml           # 大脑：痛点句式 + 领域词典 + 变现地图 + 验证手册
├── demand_radar/
│   ├── cli.py  hub.py  score.py  report.py  web.py
│   ├── db.py  models.py  textutil.py  config.py
│   ├── ocr_win.ps1             # Windows OCR 兜底（零额外依赖）
│   └── collectors/             # 每个数据源一个文件
├── data/radar.db               # SQLite（WAL）
├── reports/                    # 需求雷达-YYYY-MM-DD.{md,html,csv} + 最新报告.md + index.html
├── 需求雷达.apk                 # 手机版安装包（构建产物拷过来的）
└── android/  →  C:\Users\hua\dev\demand-radar-android
    ├── build.bat               # 双击构建；build.bat install 构建+安装
    └── app/src/main/
        ├── assets/keywords.json          # 由 config/keywords.yaml 构建时生成
        ├── res/xml/accessibility_service_config.xml
        └── java/com/demandradar/
            ├── Lexicon.kt  Scorer.kt     # 词典 + 打分（与 Python 版公式一致）
            ├── Store.kt  Hub.kt  Models.kt   # SQLite 入库 / 清洗 / 聚合
            └── ScreenReaderService.kt    # 无障碍读屏（核心）
```

> 为什么 android 放外面？工程路径含中文时 Gradle 会报 `non-ASCII characters` 错误，
> 所以真身放在纯 ASCII 路径，用目录链接（junction）链回项目里。

---

## 七、Web 看板

```bash
python -m demand_radar serve --port 8787 --open
```
- 浏览 `reports/` 里所有历史报告，可排序 / 筛选 / 搜索主题。
- `/api/topics`、`/api/stats` JSON 接口，页面上的按钮可后台触发一次采集+分析。

---

## 八、怎么用它赚钱（推荐流程）

1. **看榜**：`top -n 20`，挑 2-3 个「痛感高 + 有付费意愿 + 来源分散」的主题。
2. **反向验证**：把报告里的「典型原话」丢进百度 / 闲鱼 / 小红书，看有没有人已经在做、卖多少钱。
3. **付费测试**：一页落地页 + 收款码（或预售），48 小时内有没有 3 个人真付钱。
4. **人工 MVP**：先手动服务 3 个客户收全价，跑通了再写代码。
5. **迭代词典**：把你验证成功/失败的关键词补进 `keywords.yaml`（好的加 `mat: 0`，
   被证伪的标 `mat: 2`），跑 `analyze` 重新排序 —— **词典越用越准**。

---

## 九、已知限制

- 微信 / 小红书 / 抖音**没有**公开 API，只能靠第四节的人机协作屏幕采集。
- 部分源需要 Cookie（微博）或受速率限制（GitHub 未授权搜索 10 次/分钟），失败会自动跳过并记录。
- 分桶用的是「最具体的领域关键词」，新概念（词典里没有的词）会先落到「零散需求信号 · 待归类」，
  需要你把它补进 `keywords.yaml` 才会成为独立赛道。
- 打分是透明的加权公式，不是模型预测；它负责**把值得看的东西排到前面**，不负责替你判断真假。
