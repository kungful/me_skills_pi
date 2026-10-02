---
name: courseware-factory
description: 生产小红书售卖的少儿美术课件（PPTX + PDF 双交付），含 WebUI 审图台 + 课件实物照片联网搜索下载。**作用域仅限「少儿美术课件生产」，不是通用找图/做图工具。** 用于：做新课件（“做课件/新课题/出一套 XX 岁课件/范画/教学课件”）；改已有课件的图片/版式/文案/品牌名；导出 PDF/PPTX/单张图；**给课件找/换实物照片（“给课件找张竹子的真照片 / 换掉课件里那张实物图 / 课件这张图能商用吗”）**。仅需生成普通图片、不动课件结构时用 grsai-image-2-5。
---

# 课件工厂 · 少儿美术课件生产线

## 作用域（先看这条）

**本 skill 只服务「少儿美术课件」生产，不是通用找图 / 做图 / 排版工具。**

产出物：**26 页教学链条 + 6 张 AI 范画链 + 10 张网搜真照片 + PPTX 源文件 + PDF 交付物 + 单张图/打包图导出**。

- 用户只是要一张普通图片、不涉及课件 → 别用本 skill，用 `grsai-image-2-5` / `grsai-nano-banana`。
- 用户只是想“随便找张照片”（跟课件无关）→ 也别用本 skill。
- `工厂/photos.py` 是**课件流水线的内部模块**（结果要进 `项目/<课件>/img/` 并计入版权台账），不是独立搜图工具。
- 一旦确认是课件需求，就**按下面的流程老老实实走完**（不要只出图不装配、不要跳过版权台账）。

## 第一件事：确认工作根目录

```text
C:/Users/hua/Documents/备份代码/小红书卖课件
├── 启动审图台.bat      ← 双击启动 WebUI（纯 ASCII，别加中文）
├── run_ui.py           ← 启动器（中文提示 + 依赖检查 + 开浏览器）
├── 工厂/               ← 引擎（别改散，都从这里跑）
│   ├── project.py      Project 类：读 project.json，解析图片路径
│   ├── engine.py       版式引擎（顶栏/章节标签/页码/标题条/主题色）
│   ├── renderers.py    18 种页型渲染器
│   ├── pipeline.py     出图流水线（模型路由 + 参考图链 + 别名机制 + 照片分支）
│   ├── photos.py       ★ 实物照片联网搜索/下载 + **视觉复核** + 授权闸门
│   ├── builder.py      装配 pptx
│   ├── exporter.py     pptx → pdf + 逐页 PNG 预览
│   ├── server.py       审图台后端
│   ├── web/index.html  审图台前端
│   └── new_project.py  新建课件脚手架
├── 项目/<课题>-<年龄>/   ← 每套课件一个目录
│   ├── project.json    唯一真源：内容 + 版式 + 出图参数
│   ├── img/            高清 PNG 存档（AI 出图 + 网搜主图）
│   ├── img_alt/        网搜备选图 JPEG + <slot>.credits.json 版权 sidecar
│   ├── img_sell/       压缩 JPG 供货版
│   ├── 图片版权.json    全套图片出处/授权台账（上架前必过）
│   └── out/            pptx / pdf / preview/
└── 模板/                母版参考（《跳伞的小浣熊》= 版式母版）
```

**仓库路径若变了，改这里**，并把 `工厂/*.py` 里的相对引用一起核对。

## 常见任务速查（先定位再动手）

| 用户要什么 | 跳去哪 |
|---|---|
| 做一套新课件 | 「标准流程」 |
| **给课件找/换实物照片** | 「实物照片：先联网搜真图」 |
| **课件里的图能不能商用** | 「⚠️ 卖钱课件的版权底线」 |
| 步骤图和成品不像 | 「参考图链」（八成要「重跑整条链」） |
| 线条不好看 | 「线条风格：干净实线」 |
| 导出 PDF / 单张图 | 「审图台」→ 导出入口 |
| 一次改好几套课件 | 「审图台」→ 多课件工作台 + 批量操作 |
| 报错了 | 「常见坑」（先查 `netstat` 看是不是僵尸服务） |
| **改完引擎/想确认没搞坏** | `python selftest.py`（全链路自检，不花钱） |
| **跟课件无关的找图/做图** | ❌ 不归本 skill，转 `grsai-image-2-5` |

## 自检（改完引擎先跑这个）

```bash
python selftest.py               # 全跑：数据层 → CLI → 照片搜索 → API → 交付物（约 2 分钟）
python selftest.py --no-mutate   # 只读版，不碰任何文件
```

覆盖 40+ 项：页数/槽位/缺图、**步骤5==成品 的 md5**、版权台账授权分布、
`--list`/`--models`/`photos --list`、`/api/status`/`/api/alt`/`/api/altimg`/`/api/full_prompt`、
`/img` 两种模式、**路径穿越防护**、`pick_alt` 真·交换 + **可逆性**（像素差应为 0）、
PDF 页数/尺寸/体积、PPTX 内嵌媒体。

**不花钱**：不调任何绘图模型。`pick_alt` 那节会自动换回原图。

## Python 环境（Windows 关键坑）

用 **venv** 的 python，系统 `Python311` **没装 python-pptx**：

```text
C:\Users\hua\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe
```

含 python-pptx / PIL / pypdf / pywin32。命令统一用 `python`（若 PATH 不对就写全路径）。

## 出图前必须先报参数

**任何花钱的操作前，先把参数报给用户确认**：模型 / 质量 / 比例 / 张数 / 预估花费。

- 默认：`gpt-image-2.5` / quality `high` / aspect `1536x1024`（横版）
- 封面方形：`1024x1024`
- 整套约 16 图 ≈ **¥0.5**；跑整条链 6 张 ≈ **¥0.15**
- **`source: "search"` 的槽位走网搜 → ¥0，不占用出图预算**（大熊猫那套 10 个槽位全走网搜，只剩 6 张范画要钱 ≈ ¥0.18）
- `python 工厂/pipeline.py --models` 列全部 15 个模型与价格

## 标准流程（做一套新课件）

```bash
# 1. 脚手架：复制 26 页结构 + 图片槽位，只换主题
python 工厂/new_project.py "小兔子吃萝卜" --age 4-6岁
#    加 --blank 清空所有 prompt（想从零写）
#    生成 项目/小兔子吃萝卜-4-6岁/project.json

# 2. 改 project.json
#    - meta.brand  ← 换成用户品牌名（必须！见下方红线）
#    - 每页 title/text/tips
#    - images[].prompt  ← 写这一步画什么（网搜槽位也要写，搜不到时当 AI 回退）
#    - common.stroke    ← 线条语言（全套共用）

# 2b. 实物/素材槽位加网搜（省钱 + 真照片，详见下下节）
#    "source": "search", "query": ["中文词", "english words"],
#    "subject": "这张图应该是什么（视觉复核的判据，必填）"

# 3. 出图（先报参数！）
python 工厂/pipeline.py 项目/小兔子吃萝卜-4-6岁/project.json --list
python 工厂/pipeline.py 项目/小兔子吃萝卜-4-6岁/project.json --batch chain
python 工厂/pipeline.py 项目/小兔子吃萝卜-4-6岁/project.json --batch real   # 网搜，¥0
python 工厂/pipeline.py 项目/小兔子吃萝卜-4-6岁/project.json --batch photo  # 网搜，¥0

# 4. 装配 pptx
python 工厂/builder.py 项目/小兔子吃萝卜-4-6岁/project.json

# 5. 导出 pdf + 预览
python 工厂/exporter.py 项目/小兔子吃萝卜-4-6岁/project.json
```

**推荐用审图台做 2~5 步**（可视化、可单张重跑、自动重装配导出）：

```bash
python run_ui.py 项目/小兔子吃萝卜-4-6岁/project.json
# 或双击 启动审图台.bat → http://127.0.0.1:8777
```

## 红线（违反会出事故）

1. **品牌名绝不能用「创享美育」**——那是版式母版原作者的名字，有侵权风险。默认占位符 `【你的机构名】美育`，**上架前必须换成用户自己的机构名**。
2. **一节链条里的图必须锁同一个模型**，否则画风不统一（成品和步骤像两套画）。
3. **改内容后必须重跑「装配 + 导出」**，pptx/pdf 不会自动更新。
4. **`.bat` 文件必须纯 ASCII**——里面写中文 + `chcp` 会让 cmd 解析崩溃。中文提示放 `run_ui.py`。

## 参考图链（一致性核心机制）

课件最难的是「成品 vs 步骤画风不一致」。靠这套机制解决：

```jsonc
"chain": {
  "order":  ["范画成品","范画步骤1_起形","范画步骤2_勾线","范画步骤3_涂黑","范画步骤4_上色","范画步骤5_加背景"],
  "anchor": "范画成品"          // 设计基准，自己出图、无参考、质量最高
}
```

- **anchor（成品）**：无参考图，独立生成 → 定义整幅画的设计
- **步骤 1~4**：参考图 = `[成品, 上一步]`（`refs_for()` 自动「锚点优先」拼接）
- **最后一步 = 成品的别名**（`"alias": "范画成品"`）→ **直接复制文件，像素级一致，0 成本**

```jsonc
// images[] 里最后一步这么写：
{ "slot": "范画步骤5_加背景", "batch": "chain", "alias": "范画成品" }
```

`alias` 机制的意义：**教学逻辑上"最后一步画完"就等于"成品"**，与其让模型画两次指望它像（永远不像），不如架构上保证一致。**不要在 UI 里重跑别名图**，改就改它的源。

`gen_one()` 里 alias 分支在最前面，命中即 `shutil.copy2` 返回，不碰模型。

## 线条风格：干净实线

`project.json` 的 `common.stroke` 是全链条共用的线条语言（成品 + 5 步都注入同一段文字），避免"成品毛线/步骤实线"的自相矛盾。

当前规范 = **干净实线**：一根连续实线、平涂实黑 + 小白高光，禁止毛边/虚线/双线/出头/铅笔线/晕染。**步骤 1（起形）有 EXCEPTION 豁免**（淡灰铅笔起形）。

改线感就改这一段，**别在各图 style 里单独写**（会造成矛盾）。想更硬朗可加重 `BLACK marker pen, thick tip, opaque ink, one unbroken stroke per contour`，或换 `gpt-image-2.5-sunburst`（¥0.12，画线最利落）。

## project.json 结构速查

```jsonc
{
  "meta":   { "name": "《大熊猫吃竹子》4-6岁课件", "brand": "【你的机构名】美育", "theme": {...} },
  "common": { "stroke": "线条语言（全链条共用）" },
  "lock":   "构图锁定文字",
  "images": [ { "slot":"范画成品", "batch":"chain", "prompt":"...", "style":"...",
                "stroke":"（可覆盖 common）", "refs":[...], "ref_prev":true,
                "model":"...", "quality":"...", "aspect":"1536x1024", "size":"1K",
                "alias":"..." } ],
  "chain":  { "order":[...], "anchor":"范画成品", "note":"..." },
  "pages":  [ { "type":"cover", "title":"...", "chapter":"...", "image":"槽位",
                "text":[...], "tips":[...], "uses":["槽位"] } ]
}
```

- `batch`（批次）：`chain` 范画链 / `real` 实物观察 / `photo` 素材 / `style` 风格
- `refs`：显式参考图槽位；`ref_prev`：自动加链上前一张
- `block.uses` 是「本页用到哪些槽位」，`/api/status` 靠它查缺图
- **`source: "search"` + `query: ["中文词", "english"]` + `subject: "应该是什么"`**：
  该槽位先**联网搜真照片 → 视觉复核 → 授权闸门**，都不行才回退 AI 生成（见下节）
- **`meta.photo_policy`**：`"cc0"`（默认，只留可商用）/ `"any"`（也收 Bing/百度，需人工核对）

### 18 种页型（`renderers.py`）

`cover` 封面 / `intro` 课程介绍 / `knowing` 今天可以知道 / `quiz` 考一考 / `knowledge` 主题知识 / `real_object` 实物观察 / `materials` 材料 / `observe_tags` 外形观察 / `parts_diagram` 形体拆解（矢量绘制，不耗出图额度）/ `poses` 姿态观察 / `idea_list` 联想创想 / `color_swatches` 同类色 / `contrast_blank` 黑白对比与留白 / `refs` 参考素材 / `tools_dual` 工具介绍 / `step` 绘画步骤 / `final_dual` 范画成品 / `share_summary` 分享表达+课后总结 / `text_page` 兜底

**26 页标准链条**：P1 封面 / P2 课程介绍 / P3 我们今天可以知道 / P4 考一考 / P5-7 主题知识 / P8 实物观察(真竹子+竹笋) / P9 实物观察(材料工具) / P10 外形观察 / P11 形体拆解 / P12 姿态观察 / P13 联想创想 / P14 同类色 / P15 黑白对比与留白 / P16-18 参考素材 / P19 工具介绍 / P20-24 步骤1-5 / P25 范画成品 / P26 分享表达+课后总结

**实物观察页（P8/P9）是差异化卖点**——真东西的照片，别的模板没有，别砍。

## 实物照片：搜 → **视觉复核** → 授权闸门 → 回退 AI

> 仅用于**课件里的实物观察页 / 参考素材页**。与课件无关的找图需求不归本 skill 管。

**为什么**：实物观察页要的是「真东西的照片」。AI 画出来的是**假照片**，还慢（约 90s）还花钱（¥0.03）；
联网搜 40 秒、免费、而且是真照片。

> ### ⚠️ 血泪教训：光靠关键词搜 = 抓到啥算啥
>
> 第一版只做了「搜 + 关键词过滤 + 域名黑名单」，没有看图能力。结果**两套课件共 20 张网搜图，
> 视觉复核后发现 20 张全错**：
>
> | 槽位 | 应该是什么 | 实际抓到 |
> |---|---|---|
> | 实物_竹子 | 竹子 | 穿婚纱的新娘 |
> | 实物_竹笋 | 竹笋 | 紫色钟形花 |
> | 实物_材料工具 | 儿童画材 | 钢琴键盘和乐谱 |
> | 素材_爬树 | 熊猫爬树 | 一只金毛犬 |
> | 素材_老鼠 | 老鼠 | 镂空圣诞挂球 |
> | 素材_吃胡萝卜 | 兔子吃胡萝卜 | 公鸡头部特写 |
>
> **根因**：`pixnio.com/?s=<词>` 搜不到时会返回**随机图池**（垃圾词也能出 48 张），
> 而代码把「授权最安全」的 pixnio 排在第一优先级 → 随机垃圾把所有好图挤掉。
> 更根本的是：**关键词、域名、尺寸，永远无法回答「这张图里到底是什么」**。
> 而 pixnio 的图片 URL 是日期编号，连描述 slug 都没有，从 URL 也无从验证。
>
> **解法 = 让视觉模型逐张看一眼**（见下下节「视觉复核」）。

用法：给槽位加 `"source": "search"` + `"query"`（中英双语关键词，前面命中率高）
+ **`"subject"`（这张图「应该是什么」，视觉复核的依据，必须写）**：

```jsonc
{ "slot": "实物_竹笋", "batch": "real", "source": "search",
  "query": ["竹笋 新鲜 实物", "bamboo shoot fresh", "bamboo shoots edible"],
  "subject": "新鲜竹笋（褐色笋壳包着的笋）",   // ← 视觉复核拿它当判据
  "prompt": "（这是 AI 回退用的 prompt，搜不到才会用）" }
```

完整流程（`photos.grab()`）：

```
搜（多源并行） → 下载（按授权等级轮转取名额） → 视觉复核（不对题当场淘汰）
   → 授权闸门（photo_policy=cc0 时只留 CC0） → 都不行就回退 AI 生成
```

排序键是 `(信任等级, 是否白名单, -面积)`，但**下载名额分层轮转**
（`_tier_mix`），否则 pixnio 的随机池会独占前 13 个名额、把 Bing/百度的好图全挤掉。

| 信任等级 | 来源 | 商用安全性 |
|---|---|---|
| `免费图库·可商用` | pixnio（CC0）等白名单域名 | ✅ 可直接用 |
| `Bing筛选·待核对` | Bing `&qft=filterui:license-L1/L2_L3_L4` | ⚠️ **不可全信**（实测把 699pic 摄图网也标成公版），要人工看一眼 |
| `授权未知·慎用` | 360 / 百度 | ⚠️ 无授权信息，商用前必须自查 |

**`photo_policy`（项目级，写在 `meta` 里）**：

| 值 | 行为 | 什么时候用 |
|---|---|---|
| `"cc0"`（**默认**） | 网搜只接受「**CC0 + 视觉复核通过**」的图；一张都没有就**回退 AI 生成** | **要卖的课件**——保证每张图都能商用 |
| `"any"` | 也接受 Bing/百度（授权需人工核对） | 自用/内部课件，图更真实但版权自负 |

> 在本机实测环境里，最终结果几乎总是「**CC0 闸门挡住 → 回退 AI**」：
> 每槽 7~8 个候选里只有 1~3 张是对的，而这 1~3 张**几乎从不是 CC0**（pixnio 那几张恰好都是假货）。
> 所以真实成本 ≈ **¥0.03/槽**（AI 生成），两套课件 20 槽 ≈ **¥0.6**。
> 这钱花得值：换来的是**每张图都对题 + 每张图都能商用**。

自动产出：`img/<slot>.png`（主图，真 PNG）、`img_alt/<slot>_NN.jpg`（备选 5 张，**JPEG**）、
`img_alt/<slot>.credits.json`（单槽版权）、`图片版权.json`（全套汇总台账）。

```bash
python 工厂/photos.py "bamboo shoot" -o out.png --alt img_alt -n 5   # 单测
python 工厂/photos.py "竹笋" --list                                  # 只看候选不下载
```

### 视觉复核（"看图"能力）——根治「牛头不对马嘴」

本会话的模型**读不了图**，但可以**调外部视觉模型代看**。`photos.vcheck(png_bytes, subject)`：

```python
import photos
ok, seen = photos.vcheck(open('img/素材_竹林.png','rb').read(), '成片的竹林')
# ok=True  → 对题，"成片高耸竹林与林间小路"
# ok=False → 不对题（如 "穿拖鞋的女人"）→ 淘汰
# ok=None  → 复核不可用 → **放行**（绝不能把好图误杀）
```

**配置来源（自动探测，不用手配）**：`~/.pi/agent/models.json` 里找第一个
`models[].input` 含 `"image"` 的 provider（本机是 `new-provider` / `deepseek/deepseek-v4-flash`）。
可用环境变量覆盖：`VISION_BASE` / `VISION_KEY` / `VISION_MODEL`。

**成本**：单张图约 **~¥0.0014**（640px 缩图 + ~500 token），60 张约 ¥0.08 —— 比一张 AI 图还便宜。

**四个必须知道的实现细节（都是踩过的坑）**：

1. **必须带浏览器 `User-Agent`**，否则 Cloudflare 直接 `403 error code: 1010`。
2. **模型是推理模型，会先把 token 烧在思考上**。`max_tokens` 给低了（如 200/900）会
   `finish_reason=length` + **正文空**。所以：`max_tokens=2400`，且
   **空响应必须当「结论不明 → 放行」，绝不能当「不匹配」**（否则好图被误杀）。
3. **`_vcfg()` 并发有竞态**：曾经把 `_VCFG = False` 当哨兵值，多线程同时调时后到的线程
   读到非 None 就以为「没配置」，随机几个槽位报 `no-vision`。已改成**双重检查 + 锁**。
4. **复核失败 ≠ 图不对**。看的是「图里主要的东西」，特写/组合图容易被误判（
   如「兔子抱胡萝卜的画 + 旁边有马克笔」被答成「兔子图画」）。所以复核只能当**过滤器**，
   不能当唯一真相；用户仍可一键换图。

### 图源实测结论（2025-10 实测，别再重复踩）

**先看命中率**（查询词 `white rabbit sitting`，期望「一只兔子」）：

| 图源 | 搜到 | 下载 | **视觉复核命中** | 耗时 | 结论 |
|---|---|---|---|---|---|
| **Bing** `cn.bing.com/images/async` | 34 | 10 | **10/10** ✅ | 57s | 抓得准，但**授权不可信** |
| **Bing 公版筛选** | 34 | 10 | **10/10** ✅ | 44s | 准度不降，但筛选结果依然不可全信 |
| **百度图片** | 12 | 11 | **11/11** ✅ | 59s | 抓得准，**无授权信息** |
| **360 图片** | 24 | 4 | 2/4 ⚠️ | 33s | 下载成功率低，准度一般 |
| **pixnio.com** | **1** | 1 | 1/1 ✅ | 24s | **搜不到就返回随机图池**，不可依赖 |

> **重要更正**：之前写「pixnio ✅ 唯一能用」是**只看「能不能下载」、没看「内容对不对」**得出的错结论。
> pixnio 只能当「**偶尔能捡到 CC0 真图**」的彩票，不能当主力；主力应该是 **Bing + 百度**。

| 图源 | 结论 |
|---|---|
| **pixnio.com** | ⚠️ CC0 可商用，但 **`?s=` 搜不到时返回随机图池**（垃圾词也能出 48 张），命中率极低。`https://pixnio.com/?s=<词>`，抓 `free-images/...jpg`，取最大尺寸变体。**只吃英文词** |
| **Bing** `cn.bing.com/images/async` | ✅ **命中率最高**；授权筛选参数能用但**结果不可信**（需人工核对） |
| **360 图片** `image.so.com/j` | ⚠️ 可达，`img` 字段是**原图**（尺寸与声明一致）；但下载成功率低（24 搜到只下成 4）；授信未知 |
| **百度图片** `acjson` | ✅ **命中率最高**；**必须先访问 `image.baidu.com` 拿 Cookie**（否则 `antiFlag`）；`middleURL` 被限宽 500-800px；授信未知 |
| pixabay / publicdomainpictures / stocksnap / freeimages / freerangestock | ❌ 403 |
| **Wikimedia Commons**（本来最理想：真 CC + 可查元数据） | ❌ **SSL 握手超时**（被墙，实测两次都失败） |
| Google / DuckDuckGo / geograph / Openverse / Flickr feed | ❌ 超时或被重置（被墙） |
| 搜狗图片 napi | ❌ 返回 0 条 |

### 五个必踩的坑

1. **pixnio 搜不到就返回随机图池**：实测垃圾词 `zzzqqqxxyy` 也能出 48 张，中文词同理。
   → 代码里 **pixnio 只接 ASCII 词**（`if not query.isascii(): return []`）。
   **但这只是减少浪费，根本解法是视觉复核**（ASCII 词照样会中招）。
2. **Bing 的 `site:` 在图片接口被忽略**：`site:pixabay.com` 会返回 cookipedia/cgtn。别指望它定向。
3. **百度网页能过 ≠ 图能下**：`middleURL` 声明 4000x3000 实下 667x500（`?w=800` 限宽，去参数/改 w=1600 都无效）。
   所以 360 优先（360 的 `img` 才是原图）。
4. **不要让「授权优先级」直接决定下载顺序**：pixnio 排第一时，它的随机垃圾会吃掉
   全部 13 个下载名额，Bing/百度的好图根本进不了复核环节。必须 `_tier_mix()` 分层轮转。
5. **视觉复核的空响应**：推理模型 token 烧光时 `content` 为空串，
   `'匹配：是' in ''` = False → 会把好图判成不对题。必须显式判 `'匹配' not in t → None`。

### 性能

搜索、下载、**视觉复核**都**并行**（`ThreadPoolExecutor`，搜索 6 / 下载 6 / 复核 6 线程）：
一个槽位约 **60-90 秒**（搜 + 下 + 复核）。10 个槽位约 12 分钟 + 回退 AI 的约 90s/张。

### ⚠️ 卖钱课件的版权底线

- 项目 `meta.photo_policy` 设成 **`"cc0"`**（默认）——这是**唯一能让每张图都敢商用**的配置。
- 只用 `免费图库·可商用` 的可以放心卖；其余一律回退 AI。
- `Bing筛选·待核对` / `授权未知·慎用` 的图**要么人工核对来源，要么换掉**
  （想用就显式改 `photo_policy: "any"`，风险自负）。
- 别用带水印的付费图库小样（alamy / freepik / 699pic / 摄图网 / tuchong …，已在 `STOCK_HOSTS` 黑名单）。
- 电商主图（1688 / alicdn / taobao / jd / amazon …）也在黑名单——又带水印又不适合当范画。
- 上架前把 `图片版权.json` 过一遍。
- **AI 生成的图是本项目的兜底**：对题 + 可商用 + 风格统一，¥0.03/张。别嫌它不「真」——
  一份卖 ¥9.9~29.9 的课件，花 ¥0.6 把 20 张图全搞定，是最划算的一笔。

## 审图台（WebUI）闭环

```bash
python run_ui.py [项目目录名或 project.json]      # 端口 8777，DECKUI_PORT 可覆盖
```

**多课件工作台**：顶栏「📚 课件列表」打开课件库，可预览列表、**切换当前课件**（不用重启服务）、**勾选多套做批量更改**。

批量操作：`set_brand` 统一品牌名 / `set_model` 统一出图模型 / `set_stroke` 统一线条规范 / `replace` 批量查找替换文案 / `build` 批量重新装配+导出 / `export` 批量仅重导 PDF / `reset_review` 批量清空审图标记。

除 build/export/reset_review 外都可勾选「改完自动重装配+导出」。

**上架前标准动作**：课件列表 → 全选 → ①统一品牌名 → 勾自动导出 → 执行。N 套一次性换好品牌并出 PDF。

界面能力：

- **左**：17 个图片卡片，鼠标悬停出 **⬇（高清 PNG）/ ▣（供货版 JPG）** 单张下载
- **中**：大图预览 + 审图标记（通过/待改/重画）+ 备注
- **右**：这一步的真实参考图链、状态、✅通过 / 🔁重跑这张 / 🏗重新装配+导出
- **顶栏**：模型下拉（15 个带价格 + 实时 `≈¥x/张`）、📂 打开输出文件夹、🖼 打包下载全部图片、⬇ 下载 PDF / PPTX
- **🔍 预览发给模型的完整 prompt**：点重跑前先看全文，避免"以为改了其实没生效"
- **🔗 重跑整条链（锚点先行）**：带花费确认弹窗，自动跳过 alias 图

### 表格要完整：完整 API 清单

`GET`：`/api/status`（含 `chain_order`/`anchor`/每 slot 的 `alias`/`eff_refs`/`source`/`query`/`alts`）、`/api/report`、`/api/models`、`/api/outputs`、`/api/projects`（课件列表）、`/api/thumb?p=<目录名>`、`/api/full_prompt?slot=&p=`、`/api/job?id=`、`/img?slot=&mode=hd|sell[&dl=1]`、`/zip_images`、`/preview/NN.png`、`/download?f=pdf|pptx`、**`/api/alt?slot=`**（某槽的备选图列表）、**`/api/altimg?slot=&f=`**（备选图字节）

`POST`：`/api/switch{project}`（切换当前课件）、`/api/batch{projects,op,value,rebuild}`（批量操作）、`/api/review`、`/api/prompt`、`/api/regen{slots,prompts,model,forced,size}`、`/api/regen_chain{model,force}`、`/api/build`、`/api/export`、`/api/openfolder`、**`/api/pick_alt{slot,f}`**（备选图升为主图，真交换）、**`/api/search_photo{slot,queries}`**（改关键词重搜）

### UI 设计约束（重要）

**UI 里只能编辑"这一步画什么"（裸 prompt）；完整 prompt 一律由服务端 `build_prompt()` 组装。**

理由：以前 UI 把 textarea 内容当整条 prompt 传下去，**绕过了 LOCK / stroke / 参考图编号 / CONSISTENCY 规则**，导致「改了 prompt 重跑却没变化」。

现在：`im['prompt'] = pr`，然后调 `gen_one(..., prompt=None)`，让服务端重新拼。

## 常见坑（都踩过）

| 现象 | 原因 | 处理 |
|---|---|---|
| **重跑整条链"没反应"** | `gen_one()` 里 `tmp` 未赋值 → `UnboundLocalError`，第一张就崩，整链死 | 已修；链条加了 per-slot `try/except`，单张挂不拖死全链 |
| **成品和步骤不像** | 链条从成品向左长，成品和最后一步是两次独立生成 | 用 `alias`：最后一步 = 成品副本 |
| **UI 改 prompt 重跑无效** | 裸 prompt 整段替换，跳过 `build_prompt()` | `gen_one(prompt=None)` 让服务端重组 |
| **等很久以为卡死** | **每张图 ≈90 秒**，且必须串行（步骤2 要等步骤1） | 整链 6 张 ≈ 8~9 分钟，正常。让用户看 WebUI 底部实时日志 |
| **`.bat` 双击报"系统找不到指定的路径"** | 文件里有中文 + `chcp` | `.bat` 保持纯 ASCII，中文提示放 `run_ui.py` |
| **系统 Python 缺 python-pptx** | 用了 `Python311` | 用 venv python（见上） |
| **重定向日志中文乱码** | 按 UTF-8 解码 | 按 **GBK** 解码；真实控制台走 `WriteConsoleW` 中文正常 |
| **`curl \| python` 报 JSON 错** | 走 GBK 解码 | 测试用 `python -c` + `urllib`，别用 curl 管道 |
| **视觉复核随机几个槽报 `no-vision`** | `_vcfg()` 把 `False` 当哨兵值，多线程读到中间态 | 已修：双重检查 + `threading.Lock()` |
| **视觉复核把好图判成「不对题」** | 推理模型 token 烧光 → `content=''` → `'匹配：是' in ''` = False | 已修：`max_tokens=2400`；`'匹配' not in t` 一律返回 `None`（放行） |
| **网搜图“牛头不对马嘴”** | pixnio 搜不到时返回**随机图池**，但优先级把它排第一 → 吃掉全部下载名额 | 已修：`_tier_mix()` 分层轮转 + `vcheck()` 视觉复核 + `photo_policy=cc0` 授权闸门 |
| **Windows 下 `printf` 吞 `\h`** | 转义 | 少用 printf |
| **Python `-c` 嵌套引号崩** | 引号地狱 | 改用 heredoc 或写临时脚本 |
| **已存在图片不重跑** | grsai 脚本自动 `[skip]` | 是特性（断点续跑）；要重跑加 `--force` |
| **汇报批量进度不能拿 `j.done` 判断** | 任务完成字段是 `state: done|error`，不是布尔 `done` | 轮询用 `st.get('state') in ('done','error')` |
| **批量改完界面还是旧数据** | 批量用独立 `Project` 实例，全局 `PROJ` 没刷新 | `job_batch` 结尾判断当前课件是否在列表里，是则 `set_current()` 重载 |
| **PPTX 体积过大** | 高清 PNG 直塞 | `img/` 高清 + `img_sell/` 压缩 JPG（≤1600px, q88），builder `--mode sell` |
| **重出了图但 PDF 里还是老图** | 只跑了 `builder.py`，没先压缩 → `img_sell/` 还是旧的 | 已修：`builder.py` CLI 现在默认先 `compress()`（`--no-compress` 可关） |
| **网搜图重跑后"图变了"** | `--only` 隐含 force，会重新下载并可能选中不同图 | 审好的图别再用 `--only` 碰；要保底就先备份 `img/` |
| **图片出处追不回来** | 版权清单只在 `run()` 末尾写，中途崩就丢 | 已修：每槽写 `img_alt/<slot>.credits.json` sidecar，`run()` 会合并 sidecar 自愈重建 |
| **备选图撑爆磁盘** | 备选图也存 2400px PNG → 50 张 116MB | 已改：备选图存 **JPEG 1600px**（15MB）；被选中时 `pick_alt` 会转回真 PNG 当主图 |
| **重启了服务但界面/接口还是老样子** | Windows 的 `SO_REUSEADDR` 允许**重复绑定同一端口**，旧进程继续响应 | 已修：`serve()` 先探 `/api/status`，已有实例就提示不叠加；换端口也会自动找空位。**排查时先 `netstat -ano \| grep 8777`** |
| **pixnio 搜中文出乱图** | pixnio 搜不到会返回随机图池（垃圾词也能出 48 张） | 代码里 pixnio **只接 ASCII 词**；中文词交给 Bing/360/百度 |
| **Bing 图片接口的 `site:` 无效** | 被忽略 | 别指望 `site:pixabay.com` 定向，会返回 cookipedia/cgtn |
| **百度图下载比声明小** | `middleURL` 被 `?w=800` 限宽 | 优先用 360 的 `img`（原图）；或接受 800px |

## 图片压缩与体积

- `img/` = 高清 PNG 存档（AI 出图 + 网搜主图，cap 2400px）
- `img_sell/` = JPEG 压缩（≤1600px, q88）→ 约 4.8MB，**供货版**
- `img_alt/` = 备选图 JPEG（≤1600px）→ 约 15MB（存 PNG 要 116MB，别改回去）
- `builder.py --mode sell`（默认，CLI 会自动先 `compress()`）用压缩版装 pptx
- 实测：PPTX ~4.7-4.9MB / PDF ~2.0-2.1MB（真照片比 AI 图更省），26 页，960×540pt

## 双通道模型路由（别搞混）

gpt-image 系和 nano-banana 系是**两套不同 CLI/参数**，由 `pipeline.build_cmd()` 按 `CATALOG[m]['cli']` 自动路由：

- **grsai**（`gpt-image-*`）：`--quality high --aspect 1536x1024`
  CLI: `~/.pi/agent/skills/grsai-image-2-5/scripts/grsai.py`
- **nano**（`nano-banana-*`）：`--size 1K|2K|4K --aspect 3:2`（`ASPECT_MAP` 转）
  CLI: `~/.pi/agent/skills/grsai-nano-banana/scripts/nano_banana.py`

密钥：`C:\Users\hua\.grsai_key`。UI 下拉统一选择，用户不用管通道。

## 交付物清单（上架前核对）

- [ ] `out/《课题》X-Y岁课件.pdf` ← **交付主文件**
- [ ] `out/《课题》X-Y岁课件.pptx` ← 可编辑源文件
- [ ] `meta.brand` 已换成用户品牌名（**不是「创享美育」**）
- [ ] PDF 里无缺图占位框（`/api/status` 报"无缺图"）
- [ ] 实物观察页有真实照片（`source: "search"`，不是 AI 画的假照片）
- [ ] **`图片版权.json` 已人工过一遍**；非「免费图库·可商用」的图都核对过或换掉了
- [ ] 步骤 1→5 逐级递进、最后一步 = 成品（alias）
- [ ] 线条是「干净实线」
- [ ] 实物观察页有**对题**的图（网搜图片必须过了视觉复核，或明说是 AI 兜底）
- [ ] 项目 `meta.photo_policy` = `"cc0"`（要卖钱就必须）
- [ ] 附：教案 Word / 家长话术 / 小红书商品页文案（可选增值）

## 视觉判断必须交给用户

**若当前模型不支持图像输入，不要假装能看图判断"好不好看/线感对不对/步骤是否递进"。**
所有视觉质量确认都由用户完成；你只负责事实（文件时间、md5、尺寸、页数、prompt 全文、成本）。

> **唯一例外**：网搜照片的**「对不对题」**——可以调 `photos.vcheck()` 让外部视觉模型代看
> （见「视觉复核」节）。因为这是**批量、有标准答案、错了代价高**的筛选（抓到圣诞挂球冒充老鼠）。
> 但**范画线条干不干净、步骤递进自不自然、版式好不好看**——这些仍然必须交给用户看。

**汇报用事实，别用猜测**：用户对"猜"很反感。先查文件 mtime / md5 / API 返回值，再下结论。

## 相关技能

- 出图底层：`grsai-image-2-5`（gpt-image 系）、`grsai-nano-banana`（nano 系）
