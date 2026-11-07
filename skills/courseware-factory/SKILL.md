---
name: courseware-factory
description: 生产小红书售卖的少儿美术课件（PPTX + PDF 双交付），含 WebUI 审图台 + 多课件工作台。**作用域仅限「少儿美术课件生产」，不是通用找图/做图工具。** 用于：做新课件（“做课件/新课题/出一套 XX 岁课件/范画/教学课件”）；改已有课件的图片/版式/文案/品牌名；导出 PDF/PPTX/单张图/打包下载。仅需生成普通图片、不动课件结构时用 grsai-image-2-5。
---

# 课件工厂 · 少儿美术课件生产线

## 作用域（先看这条）

**本 skill 只服务「少儿美术课件」生产，不是通用找图 / 做图 / 排版工具。**

产出物：**26 页教学链条 + 16 张 AI 配图（6 张范画链 + 10 张实物/素材图）+ PPTX 源文件 + PDF 交付物 + 单张图/打包图导出**。

- 用户只是要一张普通图片、不涉及课件 → 别用本 skill，用 `grsai-image-2-5` / `grsai-nano-banana`。
- 用户只是想“随便找张照片”（跟课件无关）→ 也别用本 skill。
- `工厂/photos.py` 是**课件流水线的内部模块**（结果要进 `项目/<课件>/img/` 并计入版权台账），不是独立搜图工具。
- 一旦确认是课件需求，就**按下面的流程老老实实走完**（不要只出图不装配、不要跳过版权台账）。
- 课件做完了要**发到小红书**（选图 / 补 3:4 封面 / 写文案 / 发布 / 回评论）→ 用配套 skill `xhs-courseware-post`，它直接读本 skill 产出的 `project.json`。

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
│   ├── photos.py       可选：联网搜图 + 视觉复核（**默认不用**，见下节）
│   ├── builder.py      装配 pptx
│   ├── exporter.py     pptx → pdf + 逐页 PNG 预览
│   ├── server.py       审图台后端
│   ├── web/index.html  审图台前端
│   ├── web/pick.html    选题台前端（--mode pick 的弹窗）
│   ├── new_project.py  新建课件脚手架
│   └── 选题.py          第 0 步：爆款选题 + 自检（auto / 弹窗人工）
├── 选题/<时间戳>/       选题候选（候选.json + 候选.md），最新.json = 最近一次
├── 选题结果.json        定稿记录 + history（每套课件为什么选这个题的证据链）
├── 项目/<课题>-<年龄>/   ← 每套课件一个目录
│   ├── project.json    唯一真源：内容 + 版式 + 出图参数
│   ├── img/            高清 PNG 存档（AI 出图）
│   ├── img_sell/       压缩 JPG 供货版
│   └── out/            pptx / pdf / preview/
└── 模板/                母版参考（《跳伞的小浣熊》= 版式母版）
```

**仓库路径若变了，改这里**，并把 `工厂/*.py` 里的相对引用一起核对。

## 常见任务速查（先定位再动手）

| 用户要什么 | 跳去哪 |
|---|---|
| **做新课件之前：选题 + 自检** | 「第 0 步」→ `python 工厂/选题.py`（默认全自动，`--mode pick` 弹窗人工选） |
| 做一套新课件 | 「标准流程」 |
| **课件里的图能不能商用** | 「⚠️ 卖钱课件的版权底线」 |
| 步骤图和成品不像 | 「参考图链」（八成要「重跑整条链」） |
| 线条不好看 | 「线条风格：干净实线」 |
| 导出 PDF / 单张图 | 「审图台」→ 导出入口 |
| **做完要卖 → 打交付包（PDF+原图）** | `python 工厂/deliver.py 项目/<课题>/project.json --zip` |
| **出图后跑自检（必须）** | `python 工厂/preflight.py 项目/<课题>/project.json` |
| **导出后跑排版自检（必须）** | `python 工厂/layout_check.py 项目/<课题>/project.json` |
| **PDF 到底怎么生成的** | 「PDF 是怎么造出来的」章节（生产链 + 硬规范 + 故障表） |
| **要改 `工厂/*.py` / 加页型 / 查某页要哪些字段** | `references/pdf-pipeline.md`（五个文件的职责、`Deck` API、18 页型字段契约、导出细节） |
| **先看别人什么在跑量再选题** | 「选题」章节 + `python 挖爆款.py` |
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
- **全部槽位都是 AI 生成，没有免费槽位**（曾试过网搜真照片，已废弃，见下节）
- `python 工厂/pipeline.py --models` 列全部 15 个模型与价格

## 标准流程（做一套新课件）

```bash
# 0. 选题 + 自检（别跳过，这是「闭门造车」的唯一解药）
python 工厂/选题.py --list              # 先看候选和自检报告
python 工厂/选题.py --mode pick --go     # 人工挑一个 → 自动建脚手架
python 工厂/选题.py --go                # 或者全自动（默认）选定 top1 → 建脚手架

# 1. 脚手架：复制 26 页结构 + 图片槽位，只换主题
python 工厂/new_project.py "小兔子吃萝卜" --age 4-6岁
#    加 --blank 清空所有 prompt（想从零写）
#    生成 项目/小兔子吃萝卜-4-6岁/project.json

# 2. 改 project.json
#    - meta.brand  ← 换成用户品牌名（必须！见下方红线）
#    - 每页 title/text/tips
#    - images[].prompt  ← 写这一步画什么（**每个槽位都要写**）
#    - common.stroke    ← 线条语言（全套共用）
#    ⚠️ 不要加 "source": "search" —— 图片一律 AI 生成，详见下节

# 3. 出图（先报参数！）
python 工厂/pipeline.py 项目/小兔子吃萝卜-4-6岁/project.json --list
python 工厂/pipeline.py 项目/小兔子吃萝卜-4-6岁/project.json --batch chain
python 工厂/pipeline.py 项目/小兔子吃萝卜-4-6岁/project.json --batch real   # 实物/素材 10 张
python 工厂/pipeline.py 项目/小兔子吃萝卜-4-6岁/project.json --batch photo

# 4. 出图后先自检（★ 必须，别急着装配）
python 工厂/preflight.py 项目/小兔子吃萝卜-4-6岁/project.json

# 5. 装配 pptx
python 工厂/builder.py 项目/小兔子吃萝卜-4-6岁/project.json

# 6. 导出 pdf + 预览（exporter.py 没有 --no-ui 参数，别加）
python 工厂/exporter.py 项目/小兔子吃萝卜-4-6岁/project.json

# 7. 排版自检（导出后跑：文字溢出 / 越界 / 缺图 / 空页）
python 工厂/layout_check.py 项目/小兔子吃萝卜-4-6岁/project.json

# 8. 交付打包（卖货用，一步出「一个课件 = 一个文件夹」）
python 工厂/deliver.py 项目/小兔子吃萝卜-4-6岁/project.json --zip
```

### ★ 跑完自动弹审图台（已内置，不要跳过）

**`pipeline.py` / `builder.py` 跑完会自动启动审图台并打开浏览器**，并**自动切到刚跑完的那套课件**。
出图只是第一步，真正的“精细化修改”（换 prompt 重跑单张、改文案、调版式）要在界面里做 ——
所以**不要跑完就完事，不要叫用户自己去双击 `启动审图台.bat`**（这就是用户提的痛点）。

| 情况 | 行为 |
|---|---|
| 服务没在跑 | 后台拉起 `工厂/server.py`（独立控制台窗口），端口就绪后开浏览器 |
| 服务已在跑 | **不另起**（否则端口冲突 + 两份数据不同步），只切到目标课件 + 把浏览器顶到前台 |
| 想静默 | `--no-ui`，或环境变量 `DECKUI_NO_UI=1`（selftest 与批量脚本必须加） |
| 换端口 | `--ui-port 8888` 或 `DECKUI_PORT` |

> **坑（已踩）**：服务只有一份进程。你刚给「小兔子」出完图，界面却停在上一次的「大熊猫」上
> —— **看起来就像“跑完了但图没变”**。所以 `ui.open_ui()` 会先 POST `/api/switch` 切课件。
> 另一个坑：判端口是否占用时要用 `connect_ex` 探，**不能看进程名**（同名 python 进程一大把）。

**推荐直接全程在审图台里做 2~5 步**（可视化、可单张重跑、自动重装配导出）：

```bash
python run_ui.py 项目/小兔子吃萝卜-4-6岁/project.json
# 或双击 启动审图台.bat → http://127.0.0.1:8777
```

## 红线（违反会出事故）

1. **品牌名绝不能用「创享美育」**——那是版式母版原作者的名字，有侵权风险。默认占位符 `【你的机构名】美育`，**上架前必须换成用户自己的机构名**。
2. **一节链条里的图必须锁同一个模型**，否则画风不统一（成品和步骤像两套画）。
3. **改内容后必须重跑「装配 + 导出」**，pptx/pdf 不会自动更新。
4. **`.bat` 文件必须纯 ASCII**——里面写中文 + `chcp` 会让 cmd 解析崩溃。中文提示放 `run_ui.py`。
5. **脚本调用 `pipeline.py`/`builder.py` 必须加 `--no-ui`**——否则会不断弹浏览器（也污染自动化输出）。

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
- **⚠️ 步骤 1 必须自己挂上成品**（默认它是 `refs: []`、`ref_prev: false`，等于**从零发明**）：
  实测「从零画铅笔稿」的形一定和成品不一样（多出底座/托盘、彩球画成螺旋串、树更胖），
  而步骤 2→4 全跟着这个错骨架走，于是**成品和步骤变成两棵树**，老师上课会发现画不出来。
  正确写法：`refs: ["范画成品"]` + prompt 写成「把参考图**降级**成淡灰铅笔骨架，几何完全不变、只去掉颜色和粗线」，
  即“在成品上做减法”，而不是“另画一张”。同理，涂色步骤要写死 `background stays pure blank white paper`，
  否则模型会提前把天空涂了（实测）。
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
- **不要写 `source` 字段** —— 加了就变网搜槽位。图片一律 AI 生成（见下节）

### 18 种页型（`renderers.py`）

`cover` 封面 / `intro` 课程介绍 / `knowing` 今天可以知道 / `quiz` 考一考 / `knowledge` 主题知识 / `real_object` 实物观察 / `materials` 材料 / `observe_tags` 外形观察 / `parts_diagram` 形体拆解（矢量绘制，不耗出图额度）/ `poses` 姿态观察 / `idea_list` 联想创想 / `color_swatches` 同类色 / `contrast_blank` 黑白对比与留白 / `refs` 参考素材 / `tools_dual` 工具介绍 / `step` 绘画步骤 / `final_dual` 范画成品 / `share_summary` 分享表达+课后总结 / `text_page` 兜底

每种页型**必须给哪些字段**、坐标和行距公式见 `references/pdf-pipeline.md` §4.1（改 project.json 或加页型前查这张表）。

**26 页标准链条**：P1 封面 / P2 课程介绍 / P3 我们今天可以知道 / P4 考一考 / P5-7 主题知识 / P8 实物观察(真竹子+竹笋) / P9 实物观察(材料工具) / P10 外形观察 / P11 形体拆解 / P12 姿态观察 / P13 联想创想 / P14 同类色 / P15 黑白对比与留白 / P16-18 参考素材 / P19 工具介绍 / P20-24 步骤1-5 / P25 范画成品 / P26 分享表达+课后总结

**实物观察页（P8/P9）是差异化卖点**——真东西的照片，别的模板没有，别砍。

## 图片一律 AI 生成（**不要联网搜图**）

### 铁律

**所有图片槽位统一用 AI 生成**（`gpt-image-2.5` / quality `high` / `1536x1024`，封面 `1024x1024`）。
**不要**给槽位加 `"source": "search"`。成本 ¥0.03/张，16 张 ≈ ¥0.5/套 —— 不用省这点钱。

### 为什么（实测教训，别再试一遍）

早期版本认真做过「联网搜实物照片 → 视觉复核 → 授权闸门 → 回退 AI」，**结论是废弃**：

| 问题 | 实测 |
|---|---|
| **图文不符** | 搜索引擎不知道图里是什么。视觉模型复核搜来的 20 张 → **20/20 全错**（搜「熊猫爬树」给金毛犬；搜「大熊猫面部特写」给花丛里的女性肖像；搜「竹子」给穿婚纱的新娘） |
| **授权不可信** | Bing「可商用筛选」把**摄图网**标成公版；百度/360 无授权字段；pixnio 搜不到就返回**随机图池** |
| **干净源被墙** | Wikimedia Commons（真 CC）SSL 握手超时；pixabay/openverse 403/超时 |
| **命中率极低** | CC0 闸门几乎总是全挡 → 最终还是回退 AI，白等 12 分钟 |

**判定准则**：关键词、域名、尺寸、`alt` 文本**永远无法回答「图里画的是什么」**。唯一可靠的是视觉模型看图，而它给出的结论也不便宜/不稳定。

### 保留的可选工具：`工厂/photos.py`

**默认不用**，但代码保留（自用/不卖钱时可调用），自带视觉复核：

```bash
python 工厂/photos.py "大熊猫 坐着 实拍" "giant panda sitting" -o out.png --alt alt_dir -n 5
python 工厂/photos.py "竹子" --list
```

```python
import photos
ok, seen = photos.vcheck(open('x.png','rb').read(), '真实的竹子（竹竿和竹叶）')
# True=对题 / False=不对题淘汰 / None=复核不可用→**必须放行**（别把失败当不匹配误杀）
```

配方（若要修它）：`POST {BASE}/chat/completions`，OpenAI 格式带 `image_url`（data:image/jpeg;base64），**`max_tokens` 给足 2400**（推理模型会烧光 token 返回空正文），**必须带浏览器 User-Agent**（否则 Cloudflare 1010 403），图片压到 640px JPEG q78。

**但：要卖钱的课件，一张都不要用。**

## 第 0 步：选题 + 自检（`工厂/选题.py`）

**做新课件之前先选题，不要想到什么做什么。** 这一环把「小红书爆款证据」变成候选，
自检过了才进生产流程 —— 对应「选择主题然后自检」这个目标。

```bash
python 工厂/选题.py --list                # 只看候选 + 自检报告（不花钱、不定稿）
python 工厂/选题.py                       # 全自动（**默认**）：按评分取第 1 名
python 工厂/选题.py --mode pick           # 人工：弹小窗口由人选，点完窗口自动消失
python 工厂/选题.py --mode pick --go      # 人工选完直接建脚手架 → 进生产流程
python 工厂/选题.py --age 6-8岁 --n 10     # 偏好年龄段 / 更多候选
python 工厂/选题.py --use 3               # 按编号直接选（复现、脚本化）
```

| 模式 | 什么时候用 | 行为 |
|---|---|---|
| `--mode auto`（默认） | 用户说「你定 / 全自动 / 挑个能卖的」 | 按评分取第一个非 FAIL 的候选 |
| `--mode pick` | 用户说「给我几个选题我挑」 | 起本地服务 + Edge/Chrome `--app` 小窗，**点一张卡即定稿，窗口自动关闭**；超时自动回退全自动 |
| `--go` | 定稿后要直接开工 | 调 `new_project.py` 建 26 页脚手架，并把选题记录写进 `project.json` |
| `--list` | 只是给用户看候选 | 只打印 + 落盘，不定稿 |

**候选怎么来的（不是拍脑袋）**：

1. **爆款证据**：题材必须在 `参考/爆款库/index.json` 的标题里真实出现过，卡片上直接引用哪条笔记、多少赞多少藏。没有证据的题材一律不生成。
2. **评分 5 项**：赛道证据 40（点赞对数归一 + **收藏率**——收藏/点赞高说明观众想学着做，这正是卖课件的信号）/ 新鲜度 20（题材做过就扣到底）/ 配方适配 15（AI 能不能稳定出图）/ 卖点 15 / 年龄段 10。
3. **爆款配方**：6 个 preset（`marker_flat` / `collage_mixed` / `darkline_doodle` / `gradient_dot` / `clay_relief` / `chalk_board`），按题材映射，不是随机抽。
4. **年龄段不设限**：简单题给 4-6，中题 4-6/6-8，难题 6-8/7-9，并强制候选覆盖 2~3 个年龄段；`--age` 只是**偏好**（一半候选跟它，一半按题材难度铺开），不做一刀切。
5. **多样性硬约束**：同一题材最多 1 个（否则 8 个候选全是「西兰花」——这是实际踩到的）、同一类别不超过一半、同一情境最多 2 个（别全是「出逃」）。

**自检 7 项**（FAIL 的候选不会进下一步）：

| 项 | 判据 | FAIL 条件 |
|---|---|---|
| 爆款有据 | 引到的最高赞 | < 300（300~1000 只 WARN） |
| 不重复 | 与已做课题（当前 36 套）的 bigram 相似度 | ≥ 0.5 |
| 非照抄 | 与爆款标题是否同题（如「3-6岁：胡萝卜出逃」） | 生成阶段就直接跳过撞题组合，自检里的 WARN 只是兜底 |
| 题目长度 | 4~10 字（封面/文件夹都用它） | —（WARN） |
| 可出图 | 配方是否需要「真材料实拍」才像 | —（WARN，加「像真做过」提示） |
| 年龄段 | 在 3-6/4-6/5-7/6-8/7-9 内 | 非法值 |
| 爆款铁律 | 命中 7 条铁律里几条 | 命中 < 2 |

**产出**：

- `选题/<时间戳>/候选.md` ← 人读版（为什么能卖 / 画面公式 / 出图要点 / 爆款依据 / 自检），直接发用户看
- `选题/最新.json` ← 最近一次候选
- `选题结果.json` ← 定稿记录 + `history`（最后 50 次）；`--go` 时整条写进 `project.json` 的 `meta.selection`，并把 preset 写进 `common.style_preset`

> `meta.selection` 是「这套课件为什么是这个题」的证据链。卖完复盘（发布台账 → 数据）时按它归类，
> 才知道哪类选题真能卖，而不是凭感觉继续加课。
>
> ⚠️ `common.style_preset` 目前只是**记录**：`pipeline.py` 还没按它自动注入线条/装饰语汇，
> 出图仍然走 `common.stroke` + 各槽位 prompt。要真正落地配方，得把 preset 映射写进 pipeline
> （见下方「线条风格」与 `参考/爆款攻略.md` 第三节的 6 个配方）。

**改了题材库/评分/自检后**：`python 工厂/选题.py --list` 跑一遍看排序是否合理；
选题器不花钱、不写 `项目/`，可以随便试。

## 选题：先看别人什么在跑量（**别闭门造车**）

做新课题前先跑一遍本地爆款库，别凭感觉选题：

```bash
python 挖爆款.py                 # 抓「少儿美术课件」赛道爆款到 参考/爆款库/
python 看爆款.py --imgs 1        # 封面逐张过视觉模型，产结构化标签
```

分析结论写在 `参考/爆款攻略.md`（6 个风格配方 + 7 条出图铁律 + 标题词频）。
**2026-11 实测的选品结论**（180 条样本，别再重复踩）：

| 现象 | 数据 | 该怎么做 |
|---|---|---|
| 标题里写「课件/PPT/可编辑」的，数据普遍差 | 37 条含「课件」的笔记里，除 1 条 1.5 万藏外，其余多在 500 藏以下 | 标题别硬卖「课件」，写**具体课题名 + 画面卖点** |
| 吃量的是「作品好看 + 干货」型 | 草丛 6 种画法 11.6 万赞 / 墙边的花 9.4 万赞 / 刺猬的秋天 8817 藏 | 做「N 种画法」「生活小景」这类**成品即封面**的题 |
| 名画 / 艺术家 IP 是赛道高频词 | 「蒙德里安」出现 15 次；红黄蓝构成 529 藏 | 梵高星月夜、莫奈睡莲、蒙德里安这类**现成 IP** 优先排课 |
| 买家是老师，最关心「能不能直接上」 | 「公开课」出现 9 次 | 标题/正文强调**一节课走完 + 26 页排好版** |

> 数据来源是 `参考/爆款库/index.json`（去重后 180 条）。分析脚本见本 skill 的「选品分析」示例：按 `collects` 排序看头部，再去标题词频看赛道用词。

## PDF 是怎么造出来的（**唯一生产链，别绕开**）

课件不是「画图 + 拼图」，是一条从数据到交付物的固定链。**唯一真源是 `project.json`**，
PPTX 和 PDF 都是它的派生物，所以改任何文案/版式/换图之后，都必须从第 3 步重跑。

> **代码级实现说明**在 [`references/pdf-pipeline.md`](references/pdf-pipeline.md)：
> 五个文件各管什么、`Deck` 的全部原语与常量、18 种页型的必填字段、
> PPTX→PDF 的 COM 细节与预览规格、改哪层要重跑哪步。**动 `工厂/*.py` 之前先读它。**

```text
project.json（内容 + 版式 + 出图参数）
   │
   ├─[1] pipeline.py ──────────→ 项目/img/<槽位>.png          ← AI 出图（16 张，¥0.03/张）
   ├─[2] pipeline.compress() ──→ 项目/img_sell/<槽位>.jpg     ← ≤1600px / q88（PPTX 体积就靠它）
   │        ↑ builder.py 的 CLI 会自动调它
   ├─[3] builder.py ───────────→ 项目/out/《课题》.pptx        ← engine 画版式 + renderers 画 18 种页型
   ├─[4] exporter.py ──────────→ 项目/out/《课题》.pdf         ← PowerPoint COM SaveAs(32) / LibreOffice
   │                          └→ 项目/out/preview/NN.png     ← 1400px 宽，供审图/排版自检
   ├─[5] layout_check.py ──────→ 报告 + out/_排版检查/*.jpg    ← 读 pptx 的 shape 几何，不消耗渲染
   ├─[6] deliver.py ───────────→ 项目/<课件>/交付/<名>/        ← PDF + 原图 JPG + manifest.json
   └─[7] netdisk_publish.py ───→ 网盘独立子文件夹 + 分享链接    ← 见 xhs-courseware-post
```

| 步 | 命令 | 输入 | 输出 | 依赖 / 退路 |
|---|---|---|---|---|
| 1 出图 | `pipeline.py <pj> --batch chain\|real\|photo` | `images[]` 的 prompt | `img/*.png` | grsai CLI + `~/.grsai_key`；单张失败就从日志拿 id `poll` 续拉，别重画 |
| 2 压缩 | 由 builder 自动调 | `img/*.png` | `img_sell/*.jpg` | PIL；`--no-compress` 可关，但**关掉后 PDF 里会是旧图** |
| 3 装配 | `builder.py <pj>` | project.json + img_sell | `out/*.pptx` | python-pptx；`--mode hd` 用高清图（体积大，仅内部） |
| 4 导出 | `exporter.py <pj>` | pptx | `out/*.pdf` + `preview/` | **必须装 PowerPoint**（COM）；没装就自动退 `soffice --convert-to pdf`，预览退 `pdftoppm` |
| 5 排版自检 | `layout_check.py <pj>` | pptx | 报告 + 印样 | python-pptx 读几何，不需要渲染 |
| 6 交付打包 | `deliver.py <pj> --zip` | pdf + img | `交付/<名>/` | PIL 转 JPG（长边 1920 / q92） |
| 7 上链分享 | `netdisk_publish.py <pj>` | 交付包 | 分享链接 | 见 `xhs-courseware-post`（一个课件一条链接，上传到 `/课件/小红书销售/`） |

### 硬规范（改代码前先看，这些是有实测依据的）

1. **画布 13.3333 × 7.5 英寸（16:9），导出的 PDF 是 960×540pt**（`engine.SW/SH`）。
   改尺寸要同步改 `renderers.py` 里所有硬编码的 0.62/13.333 系布局，不要只改一处。
2. **字体统一微软雅黑，并且必须注入东亚字体**（`engine._ea()` 往 rPr 里塞 `a:ea`/`a:cs`）。
   只设 `run.font.name` 的话，中文在没装该字体的机器上会掉回宋体 —— 自己新加 run 时用 `engine.style()` 或 `d.text()`，别手搓。
3. **图片双份，各管一头**：`img/` 是 PNG 高清（审图 + 交付原图用）、`img_sell/` 是 JPG ≤1600/q88（**只给 PPTX 用**）。
   PPTX 体积因此稳在 ~4.4MB、PDF ~3.1MB；直接把 2.5MB 的 PNG 塞进 PPTX 会变 40MB。
4. **页码 = 页序 − 1**：封面 `page(show_bar=False, auto=False)` 不编号，所以第 2 页页脚写「1页」。
   这是母版设计（封面不占页码），不是 off-by-one，别去"修"。
5. **PDF 里不能有水印、不能有占位品牌名**。水印只打在**展示图**上（`watermark.py`，发布侧）；
   交付给买家的 PDF 是干净的。品牌取 `meta.brand`，占位符 `【你的机构名】`/`创享美育` 会被 `published.py`/`publish_post.py` 拦。
6. **正文文字溢出是版式问题、不是内容问题**：`intro` 卡片文字区固定 1.25\"，每条 ≤16 字；
   其它页型同理，先压文案，再考虑改卡片高度（改高度会影响所有同页型）。
7. **装配/导出必须重跑，不会自动更新**。只改了 `project.json` 或 `renderers.py` 而没重跑 3、4 步，
   PDF 就还是旧的 —— 这是"改了没生效"的第一大原因。

### PDF 相关故障速查

| 现象 | 原因 | 处理 |
|---|---|---|
| 重出了图，PDF 里还是老图 | 只跑了 builder，`img_sell/` 没更新（CLI 默认会压缩，但脚本里直接调 `build()` 就不会） | 先 `pipeline.compress(proj)`，再 builder；或直接用 CLI |
| PDF 页数 ≠ `pages` 页数 | 导的是上一次的 pptx | 先 `builder.py` 再 `exporter.py`；`layout_check` 会较这个 |
| 页面里出现「【待生成】槽位名」 | 该槽位没图（或路径解析不到） | `pipeline.py <pj> --list` 看哪个槽位是 `--`，补跑 |
| 中文变宋体 / 排版跑位 | 新增 run 没注入东亚字体 | 用 `d.text()` / `engine.style()`，别直接 `run.font.name=...` |
| `[export] COM 失败` | 没装 PowerPoint 或 COM 被占 | 自动退 LibreOffice；两者都没有就装一个（PDF 必须有真渲染器） |
| 预览 PNG 数量不对 | 上次预览没清干净 / 导出中断 | `preview/` 会被 exporter 清空重导，别手动往里塞文件 |
| 文字跑出卡片、压到下一块 | 文案超长 | `layout_check.py` 会报「需要 x" 只有 y"」，压短文案 |
| 图片被裁掉主体 | `d.pic()` 是等比居中填充，框比例和图片比例差太多 | 调 `img_h`/框宽比，或换 3:2 以外的图 |

## 出图自检：`工厂/preflight.py`（**跑完出图第一件事**）

```bash
python 工厂/preflight.py 项目/<课题>/project.json            # 看报告
python 工厂/preflight.py ... --json r.json                  # 机器可读
python 工厂/preflight.py ... --no-pdf --sheet off           # 还没导出 PDF / 不要印样
python 工厂/preflight.py ... --strict                        # WARN 也当失败（上架前用）
```

**它抓 7 类错**（都是“不盯图看不出来、发出去就是废品”那种）：

| 检查 | 能抓住什么 | 级别 |
|---|---|---|
| 结构 | pages 为空/不足 26、页面 `uses` 引用不存在的槽位、槽位没被任何页用到、`brand` 还是占位符 | FAIL/WARN |
| 链条 | **步骤1 的 `refs` 里没有成品** → 会从零发明骨架（本轮最大坑，100% 抓得） | FAIL |
| 链条 | 涂色页 prompt 没写死背景留白；LOCK 没禁止底座/托盘 | WARN |
| 图像 | 起形页彩色占比 >3%（应该是淡灰铅笔） | FAIL |
| 图像 | 勾线页偏彩色（>6%） | WARN |
| 图像 | **涂色/加深页四边彩色 >10%** → 背景被提前涂了（实测能抓到） | WARN |
| 图像 | alias 图与源图 md5 不一致（alias 没生效） | FAIL |
| 图像 | 与成品的**边缘图**相似度 <0.60 → 可能不是同一张画 | WARN |

**厚度细节**：指标不是拍脑袋 —— 先把纸从“木桌俯拍”里裁出来（`paper_box()`：亮且低饱和的区域），
再在纸内算饱和像素占比；一致性用 **边缘图** NCC 而不是灰度 NCC（成品深蓝满屏 vs 步骤白底，
灰度 NCC 会把同一棵树判成两张画，实测 0.46 → 边缘 0.73）。

**它拓不住的**（这两条必须人眼，不要假装能自动）：

1. **图不对题**：例如材料工具页跑出一张画着小象的儿童画（模型自由发挥）。
2. **小元素错**：步骤1 自己多出一个底座/托盘（整体轮廓像，边缘相似度反而更高）。

所以 `--sheet` 会自动出一张**接触印样** `out/_自检_全部图.jpg`（4列、带 `c=`（彩色占比）/`b=`（四边占比）、
有问题的标红框）。人的动作就是“扫一眼这张图”，而不是点开 16 张。
**汇报给用户时直接把这张印样发给他**（不要只说“图都好了”）。

## 排版自检：`工厂/layout_check.py`（**导出 PDF 后必跑**）

`preflight.py` 管图，这个管**版式**。图再对，文字跑出卡片压到下一块也是废品。

```bash
python 工厂/layout_check.py 项目/<课题>/project.json
python 工厂/layout_check.py ... --json r.json
python 工厂/layout_check.py ... --sheet off     # 不要接触印样
```

| 检查 | 判据 | 级别 |
|---|---|---|
| 越界 | shape 超出页面边界；**小幅出血**（≤0.6\" 且面积 ≤1.6 平方英寸）只算 WARN，大概率是装饰 | FAIL/WARN |
| **文字溢出** | 按字号/字宽/行距估算所需高度 > 文本框高 ×1.12 | WARN |
| 缺图 | shape 文本里出现 `【待生成】` | FAIL |
| 空页 | 整页内容块 < 3 个（漏图/漏内容） | WARN |

外加把 `out/preview/*.png` 拼成 `out/_排版检查/排版_N.jpg`（2×3 六页一张，有问题的页标红）。

**实测有效**：把 P2 原来那份长文案注入回去，它报「需要 1.60\" 只有 1.25\"」，
和实际渲染的溢出量对得上；本机这套定稿报 `0 FAIL / 0 WARN`。

### 排版上真踩过的三个坑

1. **`intro` 卡片装不下长句**：卡片文字区只有 1.25\" 高（12pt），大约装 5 行。
   每条超过 ~18 个中文字就会挤到 2 行、第 3 条直接跑出卡片压在下面那块。
   → 文案每条压到 **≤16 字**，或改 `r_intro` 的卡片高度。
2. **`parts_diagram` 用椭圆画"三个三角形叠成树"**：椭圆堆起来像蛋塔，而且顶上的椭圆会**盖住 figure_note 那行字**。
   → 已支持 `shapes` 数组（`tri` / `rect` / `oval` / `star5`，可带 `fill`/`line`/`lw`），
   用真三角形按「底→中→顶→树干→星星→彩球→礼物」的画序（后画的压上面）。
   老写法（`figure` 里一堆椭圆）仍然兼容，糖葫芦那套不受影响。
3. **`engine.deco()` 的出血装饰**：原来在 `x=-0.35` 画半个椭圆，导出后是被裁掉一半的绿块，
   看着像漏图。→ 已改成页面内的淡色圆。

### 视觉判断仍然交给人（不要假装能自动）

- 遮挡/拥挤/留白是否难看 → 看接触印样，一屏扫完 6 页
- 配色是否刺眼、图片裁切是否切到主体 → 看原尺寸 PNG
- **文字溢出只是估算**，边界情况（1.1 倍左右）要人眼确认再决定压不压文案

## 交付打包：一个课件 = 一个文件夹（`工厂/deliver.py`）

```bash
python 工厂/deliver.py 项目/<课题>/project.json --zip     # 默认长边 1920 / q92
python 工厂/deliver.py ... --long 2400 --quality 95      # 要更清晰
```

产出 `项目/<课题>/交付/<课题>X-Y岁课件/`：

```text
<课题>X-Y岁课件.pdf      ← 卖家稿（26 页，无水印）
原图/01_范画成品.jpg ...  ← 16 张出图原图（按 chain 顺序编号）
manifest.json            ← 每个文件的 md5 / 尺寸 / 时间 / 品牌（维权存证）
```

**为什么要它**：`img/*.png` 是 2.5MB×16=40MB 的 PNG，买家手机下载卡、网盘传得慢；
交付包统一压成 JPG 后 16 张约 6MB，加 PDF 共约 10MB，一套一发、干净利落。

**没有 PDF 时脚本会直接拒绝**，并提示先跑 builder + exporter —— 这是刻意的：
实测 38 套课题里只有 5 套真的导出过 PDF，剩下的「做过图的」并不能卖。

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

`GET`：`/api/status`（含 `chain_order`/`anchor`/每 slot 的 `alias`/`eff_refs`/`batch`）、`/api/report`、`/api/models`、`/api/outputs`、`/api/projects`（课件列表）、`/api/thumb?p=<目录名>`、`/api/full_prompt?slot=&p=`、`/api/job?id=`、`/img?slot=&mode=hd|sell[&dl=1]`、`/zip_images`、`/preview/NN.png`、`/download?f=pdf|pptx`、`/api/alt?slot=`（无备选图时返回 404）

`POST`：`/api/switch{project}`（切换当前课件）、`/api/batch{projects,op,value,rebuild}`（批量操作）、`/api/review`、`/api/prompt`、`/api/regen{slots,prompts,model,forced,size}`、`/api/regen_chain{model,force}`、`/api/build`、`/api/export`、`/api/openfolder`、`/api/pick_alt{slot,f}`、`/api/search_photo{slot,queries}`（网搜已废弃，保留入口）

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
| **网搜图“牛头不对马嘴”** | 搜索引擎按关键词返回，**不知道图里是什么**；pixnio 搜不到就返回随机图池 | **已彻底废弃网搜**：全部改 AI 生成。详见上节「图片一律 AI 生成」 |
| **Windows 下 `printf` 吞 `\h`** | 转义 | 少用 printf |
| **Python `-c` 嵌套引号崩** | 引号地狱 | 改用 heredoc 或写临时脚本 |
| **已存在图片不重跑** | grsai 脚本自动 `[skip]` | 是特性（断点续跑）；要重跑加 `--force` |
| **汇报批量进度不能拿 `j.done` 判断** | 任务完成字段是 `state: done|error`，不是布尔 `done` | 轮询用 `st.get('state') in ('done','error')` |
| **批量改完界面还是旧数据** | 批量用独立 `Project` 实例，全局 `PROJ` 没刷新 | `job_batch` 结尾判断当前课件是否在列表里，是则 `set_current()` 重载 |
| **PPTX 体积过大** | 高清 PNG 直塞 | `img/` 高清 + `img_sell/` 压缩 JPG（≤1600px, q88），builder `--mode sell` |
| **重出了图但 PDF 里还是老图** | 只跑了 `builder.py`，没先压缩 → `img_sell/` 还是旧的 | 已修：`builder.py` CLI 现在默认先 `compress()`（`--no-compress` 可关） |
| **网搜图重跑后"图变了"** | `--only` 隐含 force，会重新下载并可能选中不同图 | 审好的图别再用 `--only` 碰；要保底就先备份 `img/` |
| **重启了服务但界面/接口还是老样子** | Windows 的 `SO_REUSEADDR` 允许**重复绑定同一端口**，旧进程继续响应 | 已修：`serve()` 先探 `/api/status`，已有实例就提示不叠加；换端口也会自动找空位。**排查时先 `netstat -ano \| grep 8777`** |
| **pixnio 搜中文出乱图** | pixnio 搜不到会返回随机图池（垃圾词也能出 48 张） | 代码里 pixnio **只接 ASCII 词**；中文词交给 Bing/360/百度 |
| **Bing 图片接口的 `site:` 无效** | 被忽略 | 别指望 `site:pixabay.com` 定向，会返回 cookipedia/cgtn |
| **百度图下载比声明小** | `middleURL` 被 `?w=800` 限宽 | 优先用 360 的 `img`（原图）；或接受 800px |
| **某张图 3 次全 `generate image failed`（秒失败，不是超时）** | 服务端**内容过滤**：prompt 里同时出现 `close-up portrait` + `face` + `front teeth` 这类人脸词易被拒 | 改写措辞（实测改成 `A close-up wildlife photograph of a red squirrel in the forest, showing its head and shoulders...` 一次过）。判定方法：先用无关 prompt（如 “a red apple”）跑一发 —— 能过就是 prompt 被拒，不是服务端挂了 |
| **图生成成功但 `[saved]` 不打印、脚本卡住** | 下载 CDN 慢/断 | 从日志里拿到 `[result] https://fileN.aitohumanize.com/...` 直接 `curl --max-time 300 --retry 3 -o img/<slot>.png <url>`，再补一个 `<slot>.png.url.txt` 就完事（别重画，省一张钱） |
| **单张图超 600 秒被判 FAIL** | `grsai.py` 默认 `--timeout 600`，**任务在服务端还在跑** | 别重画：从日志拿 `[submit] ... id=X`，`grsai.py poll --id X --out img/<slot>.png` 续拉（实测续拉 3 分钟拿到） |
| **重跑了但图"没变"** | `gen_one()` 不覆盖已有文件，会存成 `<槽位>-1.png`、`-2.png`（防误覆盖） | 审图看 `-N`；定稿后把 `-N` 挪成正式名、旧的移进 `img_alt/`（别删，作备选）。**看 mtime 判断有没有重画会踩空** |
| **项目是半成品跑不出来** | `pages: []` + 只有 6 张 chain 图 | 先补齐：追加 real/photo 槽位 + 26 页 pages（拿已完成的课题当骨架，只换文案/槽位），再 `--list` 确认槽位与页面 `uses` 完全对得上 |
| **某一步出图失败，后面几步全错** | 步骤 N 报 `WinError 10054 远程主机强迫关闭`/超时；缺失后步骤 N+1 的 `refs=2` 只剩成品一张参考 | **`--only 步骤N 步骤N+1 步骤N+2` 一起重跑**（`--only` 隐含 force）。只补失败那张会让链条跳级、风格断层 |
| **`exporter.py` 报 `unrecognized arguments: --no-ui`** | exporter 不走 `ui.add_args` | 只有 `pipeline.py` / `builder.py` 认 `--no-ui`，exporter 直接跑 |
| **一次出 10 张要等 40 分钟** | `pipeline.py` 没有并发参数 | 可以**多路后台并发**（只会写不同的图，`project.json` 只在启动时规范化一次、过程中不改）：`nohup python -u 工厂/pipeline.py <proj> --only 槽A 槽B --no-ui > /tmp/x.log 2>&1 &`。**关键：必须 nohup 脱离终端**，否则外部命令一被中断，整个进程组一起被杀、日志还是空的（已踩） |
| **选题台弹窗关不掉 / 选完窗口没消失** | 用默认浏览器开的是普通标签页，`window.close()` 不允许关非脚本打开的窗口 | 本机有 Edge/Chrome 时走 `--app` 小窗（能真正关掉）；没有就手动关，结果已保存（页面会提示） |
| **选题候选全是同一个题材** | 只按分数排序，同题材 8 个情境分数都最高 | 已修：同一题材最多 1 个 + 类别/情境上限；改题材库后跑 `--list` 验证 |
| **选题台 15 分钟没人点** | 人工模式没人理 | 超时自动回退全自动 top1，`选题结果.json` 里 `how=timeout-fallback` 可查 |

## 图片压缩与体积

- `img/` = 高清 PNG 存档（AI 出图 + 网搜主图，cap 2400px）
- `img_sell/` = JPEG 压缩（≤1600px, q88）→ 约 4.8MB，**供货版**
- `builder.py --mode sell`（默认，CLI 会自动先 `compress()`）用压缩版装 pptx
- 实测：PPTX ~4.3-4.7MB / PDF ~2.8-3.1MB（全 AI 图），26 页，960×540pt

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
- [ ] `项目/<课题>/交付/<课题>.../` 已用 `工厂/deliver.py` 打出来（PDF + 原图 + manifest）
- [ ] 网盘已上传成**独立子文件夹**并拿到**单独分享链接**（`工厂/netdisk_publish.py`，见 `xhs-courseware-post`）
- [ ] **上传位置 = `/课件/小红书销售/<课题>X-Y岁课件/`**（2026-11-07 定版：交付根目录固定 `/课件/小红书销售`，文件夹名 = `<课题>X-Y岁课件`，PDF 名与文件夹名一致）
- [ ] **一个子文件夹里只有 1 个 PDF**（网盘是售卖专用，一套一链接；脚本会拦多 PDF/合集名/超 40 文件）
- [ ] `meta.brand` 已换成用户品牌名（**不是「创享美育」**）
- [ ] PDF 里无缺图占位框（`/api/status` 报"无缺图"）
- [ ] 实物观察页的图**对题**（AI 生成的一定对题；若混用了网搜图，必须过视觉复核）
- [ ] 全部图片均为 AI 生成，无第三方版权风险
- [ ] **展示图先过水印**：发小红书 / 商品页前用 `xhs-courseware-post/scripts/watermark.py`（`prep_post.py` 已自动调用）打平铺 + 右下角品牌条；原图自动存到 `项目/<课件>/img_orig/` 并记 md5
- [ ] **交付给买家的 PPTX/PDF 不带水印** —— 水印只打在展示图/商品图上，不能打进交付物
- [ ] 步骤 1→5 逐级递进、最后一步 = 成品（alias）
- [ ] 线条是「干净实线」
- [ ] 附：教案 Word / 家长话术 / 小红书商品页文案（可选增值）

## 视觉判断必须交给用户

**若当前模型不支持图像输入，不要假装能看图判断"好不好看/线感对不对/步骤是否递进"。**
所有视觉质量确认都由用户完成；你只负责事实（文件时间、md5、尺寸、页数、prompt 全文、成本）。

> **唯一例外**：网搜照片的**「对不对题」**——可以调 `photos.vcheck()` 让外部视觉模型代看
> （见「视觉复核」节）。因为这是**批量、有标准答案、错了代价高**的筛选（抓到圣诞挂球冒充老鼠）。
> 但**范画线条干不干净、步骤递进自不自然、版式好不好看**——这些仍然必须交给用户看。

**汇报用事实，别用猜测**：用户对"猜"很反感。先查文件 mtime / md5 / API 返回值，再下结论。

## 相关技能
- 发布与运营：`xhs-courseware-post`（读 `project.json` 一条龙发小红书：选图、补 3:4 封面、裁成品细节、**打水印 + 原图存证**、出文案、发布、核实、回评论）
- 出图底层：`grsai-image-2-5`（gpt-image 系）、`grsai-nano-banana`（nano 系）
- **代码备份**：本工程源码镜像在 GitHub `kungful/me_skills_pi` 的 `projects/courseware-factory/`
  （只含代码/文档/小数据，课件图片与母版 pptx 按规则排除；`_mirror.json` 记录源路径与跳过统计）。
  同步：`python ~/.pi/agent/skills/skills-github-sync/scripts/projects_sync.py`
