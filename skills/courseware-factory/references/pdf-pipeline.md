# PDF 生产链 · 代码级实现说明

> 这份文档讲**代码怎么把 `project.json` 变成 PDF**。SKILL.md 讲"流程该按什么顺序跑"，这里讲
> "每一层是谁、有哪些参数、改动会牵连到哪"。改 `工厂/*.py` 之前先读这里，不要凭印象改。
>
> 引擎装在 `工厂/`（不在本 skill 目录里，路径见 SKILL.md「第一件事：确认工作根目录」）。
> 所有行号/默认值取自当前版本，若与实际代码不一致，**以代码为准并回来更新本文**。

## 0. 一句话结构

```
project.json  →  Project（读数据/解路径）  →  builder（逐页）  →  renderers（18 种页型的画法）
                                                   ↓                 ↓
                                              engine.Deck（画布/字体/页码/装饰）
                                                   ↓
                                              out/*.pptx  →  exporter  →  out/*.pdf + out/preview/NN.png
```

PPTX 是中间产物，PDF 是交付物；两者都是 `project.json` 的**派生物**，所以改内容后必须重跑装配 + 导出。

## 1. 五个文件的职责与边界

| 文件 | 管什么 | 关键符号 | 改它的风险 |
|---|---|---|---|
| `project.py` | 解析 `project.json`；图片路径回落（`img_sell/` 优先、其次 `img/`）；审图状态；项目列表/缩略图 | `Project`、`img_path(mode)`、`resolve()`、`status()`、`find_project_paths()` | 低。但路径顺序改错会"改了图不生效" |
| `engine.py` | 版式原语：13.3333×7.5 英寸画布、字体注入（`a:ea` 东亚字形）、页骨架（顶栏/章节标签/页码）、`rect/oval/text/pic`、`title_bar`、`deco` | `SW/SH`、`BAR_H`、`MARGIN`、`FONT`、`DEFAULT_THEME`、`Deck`、`style()`、`_ea()` | **高**。所有页型共用，改一个默认值 = 26 页全变 |
| `renderers.py` | 18 种页型的画法 + `text_page` 兜底；`RENDERERS` 注册表 | `@renderer('name')`、`card()`、`head_chip()`、`tip_block()` | **高**。每页的字段名就是 `project.json` 的契约 |
| `builder.py` | 装配：读页 → 找渲染器 → 建 slide → 保存 pptx；CLI 默认先 `pipeline.compress()` | `build(proj, mode)`、`Ctx.P` | 中。装配顺序/封面特例错会让页码、页码条错位 |
| `exporter.py` | PPTX→PDF（PowerPoint COM `SaveAs(pdf, 32)`，失败退 LibreOffice）+ 逐页 1400px PNG 预览 | `via_powerpoint()`、`via_libreoffice()`、`export()` | 中。预览宽度、清理旧图、COM 初始化都是踩过的坑 |

配套（不在本链条内核，但同目录、会读写同一批产物）：

| 文件 | 作用 | 与 PDF 的关系 |
|---|---|---|
| `pipeline.py` | 出图 + `compress()` | 第 2 步，生成 PPTX 实际吃的 `img_sell/` |
| `layout_check.py` | 读 pptx 的 shape 几何做排版自检 | 不渲染、不依赖 PDF |
| `preflight.py` | 出图质检（要不要重画） | 看 `img/`，与 PDF 无关 |
| `deliver.py` | 卖货交付包（PDF + 原图 JPG + manifest） | 消费 `out/*.pdf` + `img/` |

## 2. 数据模型：`project.json` 怎么被读

`Project.__init__` 只做四件事：`json.load` → 拆 `meta/images/pages/common/chain/lock` →
建 `by_slot = {images[].slot: image}` → 记住自身路径。没有 schema 校验，字段错了要到渲染时才炸。

派生属性（改目录结构会一起变）：

```
project.dir      = project.json 所在目录
project.img_dir  = <dir>/img          # PNG 高清（审图 / 交付原图）
project.sell_dir = <dir>/img_sell     # JPG ≤1600 q88（只给 PPTX）
project.out_dir  = <dir>/out          # pptx / pdf / preview / review.json
project.preview_dir = <dir>/out/preview   # NN.png，审图台与排版自检都看这里
project.name     = meta.name，缺省用目录名（pptx/pdf 文件名都用它）
```

图片解析（两条路，别混）：

```python
proj.img_path(slot, mode='sell')   # 固定槽位查找
#   sell: img_sell/<slot>.{jpg,jpeg,png,webp} → 再 img/<slot>.*
#   hd  : img/<slot>.* → 再 img_sell/<slot>.*
proj.resolve(name, mode='sell')    # 页面里写的图片名
#   先按槽位名找；找不到再当文件名在 img_sell / img / 项目根目录里找 png/jpg/jpeg
proj.resolver(mode)                # 返回 lambda，builder 里就是 ctx.P
```

`mode='sell'` 是默认（PPTX 用小图）；`--mode hd` 才走高清。**这是"改了图不生效"的第一现场**：
`img_sell/` 没更新，PPTX 就还用旧 JPG。

## 3. `engine.py`：版式原语

### 3.1 常量（改任何一个都要全链条跟改）

| 符号 | 值 | 含义 |
|---|---|---|
| `SW, SH` | `13.3333, 7.5` 英寸 | 16:9 画布 → 导出 PDF **960 × 540 pt** |
| `BAR_H` | `0.62` | 顶部品牌条高度 |
| `MARGIN` | `0.62` | 左右页边距，所有页型默认对齐它 |
| `FONT` | `'微软雅黑'` | 唯一正文字体（见 3.2） |
| `DEFAULT_THEME` | `primary=77A65A dark=578B18 light=BED0B5 accent=F9A605 text=354253 cream=FAF7F0 grey=595959` | 默认配色，`project.json` 的 `meta.theme` 逐键覆盖 |

### 3.2 字体注入 `_ea()`（必须走 `style()`，不要手搓）

`run.font.name = '微软雅黑'` 只写 `a:latin`，中文会 falls back 到宋体。`style()` 会额外往 `rPr`
里塞 `<a:ea typeface="微软雅黑"/>` 和 `<a:cs .../>`，这才是 PowerPoint/WPS/导出 PDF 都认的东亚字形声明。

```python
style(run, size=18, bold=False, color=None, font=FONT, italic=False)   # 唯一的设置入口
```

新加 run 的两种安全写法：`d.rect(..., text='...')`（内部已用 style）、`d.text(...)`；
自己 `tf.add_run()` 就必须过一遍 `engine.style()`。

### 3.3 `Deck` 的 API

一个 `Deck` = 一个 `Presentation`（整册），**不是一页**。注释里"一页一个 Deck"是旧说法，
实际 `builder.build()` 只 `new` 一次，然后逐页 `d.page()` 追加 slide。

| 方法 | 签名要点 | 行为 |
|---|---|---|
| `page(chapter=None, bg=None, show_bar=True, page_label=True, auto=True)` | 返回 slide | 白底 `CREAM`；`show_bar` 画 0.62 白条 + 0.02 灰线 + 右侧品牌（`brand`/`brand_en`）；`chapter` 画左下圆角标签；`auto=True` 时 `page_no += 1`，`page_label` 在右下写 `"{n}页"` |
| `rect(s, L,T,W,H, fill, line, shape, lw=1.0, radius, text, size=14, bold=True, tcolor, align, dash)` | 英寸坐标 | 通用形状；`fill=None` 透明、`line=None` 无描边、`shadow.inherit=False`；`ROUNDED_RECTANGLE` 用 `radius` 调圆角 |
| `oval(...)` | 同上 | `rect` 的 `OVAL` 快捷 |
| `text(s, L,T,W,H, lines, align, anchor, spacing=1.15, space_after=6, color)` | `lines` 支持 `str` / `[str]` / `[[(text, {size,bold,color,...}), ...]]` | 文本框，边距清零；每个元素一段 |
| `pic(s, path, L,T,W,H, border=None, missing=None)` | 等比 **contain** 居中 | 图不存在 → 画虚线圆角占位框，写 `【待生成】<missing/文件名>`（**PDF 里出现这行字=漏图**） |
| `title_bar(s, text, L=MARGIN, W=7.6, T=1.02, H=0.66, fill=LIGHT, size=19)` | 圆角 0.28 | 页标题条，文字用 `DARK` |
| `deco(s)` | 无参 | 右上两颗小圆点 + **右下大圆（0.86，坐标在页内）**。历史上用负坐标做出血，导出后是被裁一半的绿块，看着像漏图 —— 别改回负坐标 |
| `save(path)` | | 建目录并保存 pptx |

### 3.4 页码规则（不是 off-by-one）

`page(auto=False)` 不递增也不写页码 —— 只有封面这么用。所以第 2 张 slide 的页脚是「1页」。
这是母版设计。任何"修页码"的改动都会让 26 页集体错位。

## 4. `renderers.py`：18 种页型 + 兜底

注册方式：

```python
@renderer('step')
def r_step(d, s, p, ctx): ...
# d=Deck, s=slide, p=该页的 dict, ctx.P(name)=解析图片路径, ctx.proj=Project
```

`builder` 里 `t not in RENDERERS` 直接抛错并列出可用页型 —— 所以新增页型必须同时注册。

### 4.1 逐页字段契约（`p` 里必须有什么）

| type | 必填字段 | 可选字段 | 版式要点 |
|---|---|---|---|
| `cover` | `title` `subtitle` `image` | `slogan[]` | 左文右图；右侧 6.4" 米色块放 5.6" 方图；顶部 0.14 主色条；**不画顶栏、不编号** |
| `intro` | `cards[{head,items[]}]`（4 张） | `image` `image_head` `title` | 左 2×2 卡片（4.05×2.15/1.90），右侧课效展示卡 |
| `knowing` | `items[]` | `title` | 序号圆 + 长条卡，行高 `min(0.78, 4.6/n-0.14)`，整块垂直居中 |
| `quiz` | `question` `images[2]` | `answer` `title_L` `title_W` | 两图 VS，中间橙色 VS 块；标题条默认居中偏右 |
| `knowledge` | `title` `image` `lines[]` | `img_w` `title_W` | 左图 7.1×4.35，右文字卡 3.5 高 |
| `real_object` | `title` `image` `tasks[{tag,text}]` | `image2` `img_h` `img2_h` `task_head` `title_W` | 左大图（可叠小图），右侧观察任务卡；行距 `min(0.72, 3.9/n)` |
| `materials` | `title` `image` `schemes[{head,items[]}]` | `title_W` | 左图；右侧 1 或 2 张方案卡（2 张时各 2.05 高） |
| `observe_tags` | `title` `image` `tags[]` | `cols`(默认2) `title_W` | 左图 6.4 宽，右侧标签网格 0.75 高 / 行距 0.95 |
| `parts_diagram` | `title` `parts[{name,desc}]` | `shapes[]`（新）/`figure{}`（老）/`figure_note` `title_W` | 左卡画矢量图（`kind`: `tri/rect/oval/star5`）；老格式 `figure` 全是椭圆（糖葫芦系列依赖它，别删）；说明文字占 y=2.02，图形坐标由 `shapes[].x/y/w/h` 给（画到 2.10 会压住那行字） |
| `poses` | `title` `items[{image,label}]` | `title_W` | 等宽分栏，图下白底标签条 |
| `idea_list` | `title` `image` `items[]` | `list_head` `title_W` | 左图 7.0；右侧条卡，行距 `min(0.80, 4.0/n)` |
| `color_swatches` | `title` `swatches[{hex,name,use}]` `note_head` `note` | `title_W` | 等宽色块 2.15 高 + 底部说明卡 |
| `contrast_blank` | `title` `figure{body,head,eyes[],legs[]}` `figure_note` `tips[{no,text}]` | `figure.tail` `title_W` | 左卡矢量小动物（可加大尾巴，向后兼容）；右侧编号要点 |
| `refs` | `images[]` | `head` `hint` | 等宽并排 4.30 高，顶部提示行 |
| `tools_dual` | `title` `schemes[{head,tools[{no,name,desc}]}]` | `title_W` | 两列工具卡，行距 `min(1.20, 4.6/n)` |
| `step` | `title` `image` `text` | `tips[]` `img_w` `title_W` | **核心页**：左大图 7.5×4.30，右侧 `tip_block`（正文 + 橙色短线 + 要点） |
| `final_dual` | `title` `items[{image,label}]` `note` | `hint` `title_W` | 双风格成品对照 + 底部强调条 |
| `share_summary` | `share[]` `summary[]` | `share_head` `summary_head` | 上分享表达（浅色块 2.35 高）、下课后总结卡 2.85 高 |
| `text_page` | `lines[]` | `title` `title_W` | 兜底页；卡片高度跟行数走（`min(4.20, 0.75+0.40n)`）并垂直居中，避免大片空白 |

值一律是英寸。公共零件：`card()`（白底 + `LIGHT` 描边圆角）、`head_chip()`（主色圆角标签，宽度按字数估）、
`tip_block()`（正文 + 橙线 + 要点）。

### 4.2 新增一种页型

1. `renderers.py` 里写 `@renderer('xxx')` 函数，只接受 `(d, s, p, ctx)`；
2. 字段命名跟现有页型对齐（`title/image/items/text/tips/...`）；
3. 在 `project.json` 的 `pages` 里用 `{"type":"xxx", ...}`；
4. 重跑 builder + exporter + `layout_check.py`；
5. 回本表补一行契约。

## 5. `builder.py`：装配

```python
def build(proj, mode='sell', out=None, verbose=True):
    d = Deck(theme=proj.meta.get('theme'), brand=meta.brand, brand_en=meta.brand_en)
    ctx = type('Ctx', (), {'P': staticmethod(proj.resolver(mode)), 'proj': proj})
    for i, p in enumerate(proj.pages):
        t = p.get('type', 'text_page')
        fn = RENDERERS[t]                     # 未知页型 → ValueError（带可用列表）
        s = d.page(show_bar=False, auto=False) if t == 'cover' else d.page(chapter=p.get('chapter'))
        fn(d, s, p, ctx)
    d.save(out or proj.pptx())
```

要点：

* **封面特例**：`show_bar=False, auto=False`（不画顶栏、不占页码）。其它页一律带顶栏和章节标签。
* `ctx` 是个一次性鸭子类型，只有 `P` 和 `proj` 两个属性 —— 渲染器里别指望别的。
* `out` 默认 `proj.pptx()` → `<out>/<name>.pptx`。
* CLI：

```bash
python 工厂/builder.py 项目/<课题>/project.json                # 默认 sell 模式
python 工厂/builder.py ... --mode hd                          # 用 img/ 高清（体积大，内部用）
python 工厂/builder.py ... --no-compress                      # 跳过 img→img_sell（会用到旧图！）
```

CLI 在 `mode='sell'` 时**先跑 `pipeline.compress(pr)`** 再装配。脚本里直接 `from builder import build`
不会自动压缩 —— 这是"重出了图但 PDF 还是老图"的主因。装配完会 `ui.maybe_open()` 弹审图台。

## 6. `exporter.py`：PPTX → PDF + 预览

```python
export(proj, pptx, pdf=None, previews=True, log=print)
```

1. **优先 PowerPoint COM**（`via_powerpoint`）：

   ```python
   pythoncom.CoInitialize()                       # 后台线程必须；否则 COM 静默失败
   app  = win32.Dispatch('PowerPoint.Application')
   pres = app.Presentations.Open(abspath(pptx), WithWindow=False)
   pres.SaveAs(abspath(pdf), 32)                  # 32 = ppSaveAsPDF
   for i, sl in enumerate(pres.Slides, 1):        # 预览：逐页导出
       sl.Export(preview_dir/'%02d.png', 'PNG', 1400, 0)   # 宽 1400px，高按比例
   pres.Close()
   ```

   导出前会**清空 `preview/*.png`**，避免残留旧页。

2. **失败退 LibreOffice**（`via_libreoffice`）：

   ```bash
   soffice --headless --convert-to pdf --outdir out/ out/xxx.pptx
   pdftoppm -png -r 110 out/xxx.pdf out/preview/p      # 预览退化成 p-01.png 命名
   ```

   LibreOffice 的排版与 PowerPoint 有细微差异（字距、行距、圆角），**能装 PowerPoint 就不要用它**。
   两者都没有 → 没有真渲染器，PDF 造不出来（不要用截图拼）。

3. 返回 pdf 路径并打印 `[pdf] ... 预览 N 页`。

## 7. 尺寸 / 字号速查（抄版式时用）

| 用途 | 数值 |
|---|---|
| 画布 | 13.3333 × 7.5 in（960 × 540 pt） |
| 顶栏 / 页边距 | 0.62 / 0.62 in |
| 标题条 | y=1.02，高 0.66，宽默认 7.6（`title_bar`） |
| 正文起始 | y≈1.95–2.15（各页型固定） |
| 正文区高度 | 4.30–4.35 in |
| 页脚 | 页码 y=`SH-0.56`，章节标签 y=`SH-0.60` |
| 字号 | 封面标题 42 / 页标题 19 / 小节 22 / 正文 16 / 卡片 12 / 要点 11–13 / 页脚 11 |
| 圆角 | 卡片 0.06，标签条 0.28，色块 0.08 |

## 8. 改代码 → 重跑哪一步

| 改了什么 | 必须重跑 | 说明 |
|---|---|---|
| `project.json` 文案/页码顺序 | 3 → 4 → 5 | 只跑 builder 会留旧 PDF |
| 换了/新出了图 | 2 → 3 → 4 | `pipeline.compress()` → builder → exporter |
| `renderers.py` / `engine.py` | 3 → 4 → 5 | 并跑一次 `layout_check.py` 看溢出 |
| 只改 PDF 导出参数 | 4 | 预览宽度、COM 退路 |
| 改画布尺寸 | 全局 | `SW/SH` + 所有硬编码坐标 + `layout_check` 阈值 |

重跑命令（Windows，在仓库根）：

```bash
python 工厂/pipeline.py 项目/<课题>/project.json --batch chain
python 工厂/builder.py  项目/<课题>/project.json
python 工厂/exporter.py 项目/<课题>/project.json
python 工厂/layout_check.py 项目/<课题>/project.json
```

## 9. 代码级翻车点（都真实发生过）

| 现象 | 代码位置 | 原因 |
|---|---|---|
| PDF 里中文变宋体 | `engine._ea` | 新 run 没走 `style()`，缺 `a:ea` |
| 右下角出现半个绿圆，像漏图 | `engine.deco` | 装饰圆用了负坐标出血，导出被裁 |
| 每页页脚数字差 1 | `engine.page` | 给封面传了 `auto=True`，或手动"修"页码 |
| 图片被裁掉主体 | `engine.pic` | contain 是等比居中；框比例与图差太多就要改 `img_w/img_h`，不是改算法 |
| 明明重画了，PDF 还是老图 | `builder` CLI / `pipeline.compress` | 走了 `build()` 直调，`img_sell/` 没更新 |
| `【待生成】xxx` 出现在交付稿 | `engine.pic` 占位分支 | 槽位没图或 `resolve()` 没找到（名字与文件不一致） |
| 页数比 `pages` 少 | `exporter` | 导的是旧 pptx；先 builder 再 exporter |
| 预览 PNG 张数不对 | `exporter.via_powerpoint` | 上次导出中断留下垃圾；正常会先清空 `preview/*.png` |
| `[export] COM 失败` | `exporter.via_powerpoint` | 没装 PowerPoint / 后台线程没 `CoInitialize` / 文档被占用 |
| 文字压到下一块 | `renderers` 的固定卡片高 | 先压文案；改高度会影响同页型所有课件 |

## 10. 与自检/交付的分工

* `layout_check.py` 读 **pptx** 的 shape 几何（不渲染、不耗 GPU）：文字溢出、越界、缺图、空页。
* `preflight.py` 只看 **img/**：图对不对题、起形是否彩色、涂色页背景、与成品边缘相似度。
* `deliver.py` 消费 **out/*.pdf** + `img/*`，转 JPG（长边 1920 / q92）并写 `manifest.json`（md5 存证）。
* 审图台（WebUI）读 `out/preview/NN.png` + `out/review.json`，改状态不重排 PDF。

一句话：**PDF 只由 `builder` + `exporter` 产出；其它脚本都是"看"或"打包"，不许自己去拼 PDF。**
