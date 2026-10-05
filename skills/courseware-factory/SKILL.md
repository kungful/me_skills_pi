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
│   └── new_project.py  新建课件脚手架
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
| 做一套新课件 | 「标准流程」 |

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
- **全部槽位都是 AI 生成，没有免费槽位**（曾试过网搜真照片，已废弃，见下节）
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
#    - images[].prompt  ← 写这一步画什么（**每个槽位都要写**）
#    - common.stroke    ← 线条语言（全套共用）
#    ⚠️ 不要加 "source": "search" —— 图片一律 AI 生成，详见下节

# 3. 出图（先报参数！）
python 工厂/pipeline.py 项目/小兔子吃萝卜-4-6岁/project.json --list
python 工厂/pipeline.py 项目/小兔子吃萝卜-4-6岁/project.json --batch chain
python 工厂/pipeline.py 项目/小兔子吃萝卜-4-6岁/project.json --batch real   # 实物/素材 10 张
python 工厂/pipeline.py 项目/小兔子吃萝卜-4-6岁/project.json --batch photo

# 4. 装配 pptx
python 工厂/builder.py 项目/小兔子吃萝卜-4-6岁/project.json

# 5. 导出 pdf + 预览
python 工厂/exporter.py 项目/小兔子吃萝卜-4-6岁/project.json
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
| **一次出 10 张要等 40 分钟** | `pipeline.py` 没有并发参数 | 可以**多路后台并发**（只会写不同的图，`project.json` 只在启动时规范化一次、过程中不改）：`nohup python -u 工厂/pipeline.py <proj> --only 槽A 槽B --no-ui > /tmp/x.log 2>&1 &`。**关键：必须 nohup 脱离终端**，否则外部命令一被中断，整个进程组一起被杀、日志还是空的（已踩） |

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
- [ ] `meta.brand` 已换成用户品牌名（**不是「创享美育」**）
- [ ] PDF 里无缺图占位框（`/api/status` 报"无缺图"）
- [ ] 实物观察页的图**对题**（AI 生成的一定对题；若混用了网搜图，必须过视觉复核）
- [ ] 全部图片均为 AI 生成，无第三方版权风险
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
- 发布与运营：`xhs-courseware-post`（读 `project.json` 一条龙发小红书：选图、补 3:4 封面、出文案、发布、核实、回评论）
- 出图底层：`grsai-image-2-5`（gpt-image 系）、`grsai-nano-banana`（nano 系）
