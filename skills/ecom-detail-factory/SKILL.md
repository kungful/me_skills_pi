---
name: ecom-detail-factory
description: 生产电商商品详情页（长图 + 分屏 + 主图 + PPTX + PDF + ZIP），含 WebUI 精修台。**作用域仅限「电商详情页生产」，不是通用做图/排版工具。** 用于：做商品详情页（“做个详情页/详情页长图/宝贝详情/主图+详情图”）；改已有详情页的文案/版式/配色/顺序；出白底主图、场景图、卖点配图；按淘宝/拼多多/抖音/京东/小红书/亚马逊规格导出。仅需生成一张普通图片、不排详情页时用 grsai-image-2-5。
---

# 详情页工厂 · 电商详情页生产线

## 作用域（先看这条）

**本 skill 只服务「电商详情页」生产。**

- 用户只是要一张普通图 → 用 `grsai-image-2-5` / `grsai-nano-banana`，别用本 skill。
- 一旦确认是详情页需求 → **按下面的流程走完**（别只出图不装配、别跳过精修和导出）。
- 出图要走 `grsai-image-2-5` 的硬规则：**先说清模型 + 质量 + 张数，拿到用户 OK 再提交**。

## 工作根目录

```text
C:/Users/hua/Documents/备份代码/电商详情页工厂/
├── 新建项目.bat      ← 把 1~8 张产品图拖上来，一键建项目
├── 启动精修台.bat    ← 双击开 WebUI（纯 ASCII 文件名）
├── run_ui.py         启动器
├── selftest.py       自检 70 项（不花钱）
├── 工厂/             引擎（别改散，都从这里跑）
│   ├── theme.py      12 主题 / 7 平台 / 字体 / CJK 排版
│   ├── product.py    product.json 单一真源
│   ├── layouts.py    8 套骨架
│   ├── copywriter.py 10 行业词库 + 文案公式
│   ├── analyze.py    产品图分析 + 一键建项目
│   ├── renderers.py  14 种模块渲染器
│   ├── render.py     渲染调度 + 缓存 + 长图/分屏
│   ├── pipeline.py   AI 出图（外观锁定 + 两段式）
│   ├── exporter.py   长图/分屏/主图/PPTX/PDF/ZIP
│   ├── server.py     WebUI 后端
│   └── web/index.html 精修台前端
└── 项目/<产品名>/     product.json + sources/ + img/ + out/
```

**仓库路径若变了，改这里**，并把 `run_ui.py` / `selftest.py` 里的 `工厂` 相对引用一起核对。

## 常见任务速查

| 用户要什么 | 跳去哪 |
|---|---|
| 做个新详情页 | 「标准流程」 |
| 只改文案/换图/调顺序 | 「精修闭环」 |
| 出白底主图 / 场景图 | 「出图」 |
| 换平台尺寸（淘宝 750 / 京东 790 / 小红书 1242） | 「平台预设」 |
| 换风格（黑金/北欧/国潮…） | 「主题」 |
| 导出交付物 | 「导出」 |
| 报错了 | 「常见坑」 |
| 改完引擎想确认没搞坏 | `python selftest.py` |

## 标准流程

```text
① 产品图到位          用户拖图 / 丢路径 / 我用已有素材
      ↓
② 建项目 + 图分析     python 工厂/analyze.py 图.jpg … --name X --category home
                     → 算白底占比/清晰度/主色/比例，白底图直接当首屏
      ↓
③ 填产品档案          name / brand / price / category / selling（3~4 个核心卖点）
                     ★ 这一步我（agent）来做：我看图 + 读用户给的规格，写真卖点。
                       不让脚本猜语义，脚本只给初稿。
      ↓
④ 选骨架 + 主题       标准转化型 + 简约白（默认）；按品类/品牌调
      ↓
⑤ 出图                python 工厂/pipeline.py X --draft     ← 先草稿看构图
                     python 工厂/pipeline.py X --final     ← 确认后终稿
      ↓
⑥ 铺文案              精修台「铺文案」，再逐条改成人话
      ↓
⑦ 精修                启动精修台.bat → 逐屏改
      ↓
⑧ 导出                精修台「导出」/ python 工厂/exporter.py X
```

## 精修闭环（改已有详情页）

```bash
python run_ui.py <项目名>       # 或双击 启动精修台.bat
```

WebUI 能做的事：拖拽排序、显示隐藏、增删/复制模块、一键换骨架、一键换肤、换平台宽度、
逐字段改文案、增删卖点条目/参数行/FAQ、每个图位上传或 AI 重出、查看该图位的完整出图提示词、
看产物文件列表并下载。

改字段 → 自动存 `product.json` → **只重渲染那一屏** → 预览秒级刷新（局部约 0.7 秒）。

## 出图

```bash
python 工厂/pipeline.py X --plan      # 只列待补槽位，不花钱
python 工厂/pipeline.py X --draft     # 草稿 ≈¥0.022/张
python 工厂/pipeline.py X --final     # 终稿 ≈¥0.10/张（gpt-image-2.5-flare）
python 工厂/pipeline.py X --final --alt 3   # 每槽位 3 张候选
python 工厂/pipeline.py --models      # 模型与价格表
```

铁律（已写进 `pipeline.py` 的 `LOCK` / `NEG`，别删）：
1. **产品本体必须与实物一致** —— 外观/颜色/材质/结构/部件数/logo 位置都不许改，不许重新设计。
2. **画面里不许出现文字、字母、数字、水印、二维码、价格标签、假 logo。**
3. AI 只负责背景/场景/氛围，不负责「产品长什么样」。

已填图的槽位不会被重复出图，所以反复点不会反复扣费。

## 主题 / 平台

- 主题（12）：`minimal` 简约白、`luxe` 轻奢黑金、`nordic` 北欧原木、`guochao` 国潮、
  `tech` 科技感、`maternal` 母婴柔光、`beauty` 美妆质感、`food` 食品暖调、
  `digital` 3C 参数硬核、`vivid` 活力撞色、`medical` 专业洁净、`outdoor` 户外硬核
- 骨架（8）：`standard` 标准转化型、`minimal` 极简高端、`seed` 种草叙事型、`spec` 参数硬核型、
  `scene` 场景沉浸型、`fast` 爆款速成型、`brand` 品牌故事型、`newbie` 新手友好型
- 平台（7）：淘宝天猫 750 / 拼多多 750 / 抖音小店 750 / 京东 790 / 小红书 1242 / 亚马逊 A+ 970 / Shopee 750
- 行业（10）：`3c` `beauty` `food` `home` `baby` `apparel` `sports` `jewelry` `medical` `default`
  （决定文案词库、参数表字段、信任点、FAQ 模板）

## 导出

```bash
python 工厂/exporter.py X
```

产出（`项目/X/out/`）：`详情页长图-750.jpg` / `详情页长图.png` / `分屏/屏NN.jpg` /
`白底主图.jpg` / `详情页.pptx`（每屏一页，可二次改）/ `详情页.pdf` / `X-详情页.zip`。

## 自检（改完引擎先跑）

```bash
python selftest.py
```

70 项：12 主题、7 平台、14 渲染器、8 骨架、文案引擎、缓存命中/失效、长图宽度、分屏数量、
导出全套、脏数据不崩、目录穿越防护、出图命令构造、提示词铁律、图片分析。
**全程不调绘图模型、不花钱。**

## 写作纪律（详情页文案）

- 每条卖点必须落到「用户能得到什么」，不写「高品质」「匠心」这种空话。
- **参数宁缺毋错**：脚本生成的参数表里不确定的一律「待填写」，必须补真值或删掉该行。
  错参数（尺寸/材质/承重）是实打实的退货和差评风险。
- 不承诺做不到的事（发货时效、质保年限要跟店铺实际一致）。
- 不写「全网最低」「第一品牌」这类违反广告法的表述。
- 详情页图不许过度美化到货不对板，必要处写明「实物为准」。

## 常见坑

| 现象 | 原因 / 解法 |
|---|---|
| 端口 8788 被占用 | 精修台已在运行，直接开浏览器；或先关掉旧窗口（`netstat -ano \| findstr 8788` + `taskkill /F /PID`） |
| 预览只剩一屏 | 旧版 bug，已修：局部重渲只强制重画那一屏，长图永远由全部可见屏拼成 |
| 文案是「待填写」 | 正常，那是给真参数留的位置，必须补或删 |
| 图是豆腐块/方框 | 字体缺字形。图标已改矢量绘制，文字缺字形就换 `theme.FAMILIES` 里的字体 |
| 出图和实物不像 | 参考图没带上（`sources/` 空）或产品本身不适合 AI 场景图 → 直接用原图 |
| 出图带文字/水印 | 检查 `pipeline.LOCK` / `NEG` 是否被改过 |
| 改完没生效 | 浏览器缓存，`Ctrl+F5`；或删 `out/cache/` 让它全量重画 |
| 中文乱码 | 命令行用 `python -X utf8`，或 `chcp 65001` |

## Python 环境（Windows）

用 **venv 的 python**（系统 Python 没装 Pillow）：

```text
C:\Users\hua\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe
```

`run_ui.py` 会自己找并自动装依赖。字体依赖 `C:/Windows/Fonts/msyh.ttc` 等系统字体。
