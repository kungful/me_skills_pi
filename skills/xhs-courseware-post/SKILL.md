---
name: xhs-courseware-post
description: 把课件工厂产出的课件一条龙发到小红书（选图 → 补 3:4 封面 → 生成文案 → 发布 → 核实 → 回评论）。**作用域仅限「已有课件的发布与运营」，不做课件本身。** 默认「成品流」：只发成品+成品细节，不发步骤图；文案固定带 AIGC 声明与购买引导（课件 / 做课件的工具）。用于：把课件发小红书/发笔记/上架；给课件写小红书文案、起标题、配话题标签；挑图、补封面、去重图；发出去以后核实、看通知、回评论。要做课件本身（做课件/改课件/导 PDF）用 courseware-factory。
---

# 小红书发课件 · 一条龙

把 `courseware-factory` 产出的 `project.json` 变成一条真发出去的小红书图文笔记，并负责发完之后的核实与回评论。

**一句话流程**：`published.py --list`（查台账，已发的课题不能发）→ **`netdisk_publish.py` 先把交付链接做好**（没链接别发笔记）→ `prep_post.py`（选图+补封面+打水印+生成文案）→ **人工/agent 改两处文案** → `publish_post.py`（发布+核实+登记台账）→ `replies.py`（回评论+成交后发链接）。

## 发布策略（2026-11 起，改策略先看这段）

1. **一个课题只发一次，一张图只出现一次**。发布台账 `发布台账.json`（在项目根）记录每个课题发过几篇、每张图的 md5。`prep_post.py` 发布前必查：课题已发 → 直接拒绝并列出未发课题；图片 md5 已用过 → 拒绝。用 `--next` 自动挑未发课题，别每次手选。
2. **只发成品，不发步骤图**。步骤图证明「这是套模板」，而且是最不好看的几张；成品图才是点击和转化的来源。默认选图 = 封面成品 + 从成品裁的局部特写 + 知识素材 / 实物 / 材料。要恢复老策略加 `--with-steps`。
3. **必须写明 AI 生成**。画面是模型出的，正文里固定带 `AI_DISCLOSURE` 那段（「画面由 AI 生成，课题设计/教学流程/文字由人工编排校对」）。这段话有两个作用：平台 AIGC 合规，以及挡掉「AI 画的还卖钱」的举报。MCP 的发布接口**没有 AIGC 勾选字段**，所以只能写在正文；发完最好去 App/创作中心看有没有需要补的标识。
4. **必须有购买引导，但正文里不能写交易词**。正文固定带 `CTA_DECK` / `CTA_CUSTOM` / `CTA_TOOL` 三行，只允许说「主页 / 合集 / 评论区告诉我」，把成交留给私信和主页。**实测「课包 / 打包更划算 / 想要这套 / 私信『工具』」这类词会让发布按钮点下去不跳转**（MCP 只报 `PUBLISH_FAILED`，看不见真实原因）。
5. 三行 CTA 是常量（`prep_post.py` 顶部），改口播方式改那里，不要每次手改 post.json。
7. **默认只发 1 张成品图（2026-11 起）**。`--cap 1 --details 0`，封面就是成品本身。
   9 张图会让笔记像"资料包清仓"，而单张美图 + 一段能看懂的文字，点击和私信都更高。
   展示图必须带水印（防白嫖），原图进 `img_orig/` 留档，交付给买家的 PDF 不过水印。

## 作用域（先看这条）

- 本 skill **只负责"把已经做好的课件发出去"**，不生产课件内容，不改课件版式。
- 要做课件 / 改课件图 / 重出 PPTX·PDF → 用 `courseware-factory`，做完再回来发。
- 只想生成一张普通图片 → `grsai-image-2-5`。

## 前置：MCP 服务必须在跑并已登录

发布走的是本地 `xiaohongshu-mcp` 的 HTTP API（`http://127.0.0.1:18060`），**不走 MCP 客户端** —— 因为发布要 1~2 分钟，走 MCP 会被 60 秒单请求超时掐断。

```powershell
C:\Users\hua\tools\xiaohongshu-mcp\启动MCP.cmd      # 起服务（工作目录必须在这，cookies.json 按 CWD 解析）
C:\Users\hua\tools\xiaohongshu-mcp\查看状态.cmd      # 看状态
```

**必须带 `-headless=false` 启动**（`启动MCP.cmd` 已经带上了）。默认的 headless 模式在本机上会让指纹版 Chrome 卡在导航阶段，任何要拉浏览器的接口（`login/status`、`user/me`、`publish`）都在 30 秒死线超时后返回 `500 INTERNAL_ERROR`，而 `/health` 正常、`feeds/search` 正常 —— 看着像“掉登录”，其实是 headless 的锅。
判断标志：`mcp.err.log` 里 panic 栈 `rod utils.go:68 ← must.go:36 ← must.go:457 ← login.go:23`（`context deadline exceeded`），同时临时 profile 目录 `%LOCALAPPDATA%\Temp\rod\user-data\*` 里 Chrome 起来了、`DevToolsActivePort` 写了端口、`/json/list` 也能读到页面，但页面标题卡在 `about:blank`。
根治办法就是有头模式（会弹真窗口，别去关它）：
```powershell
Start-Process 'C:\Users\hua\tools\xiaohongshu-mcp\xiaohongshu-mcp.exe' `
  -ArgumentList '-headless=false' `
  -WorkingDirectory 'C:\Users\hua\tools\xiaohongshu-mcp' `
  -RedirectStandardError 'C:\Users\hua\tools\xiaohongshu-mcp\mcp.err.log' -WindowStyle Hidden
```

- 没登录 / 掉登录 → 跑 `C:\Users\hua\tools\xiaohongshu-mcp\xiaohongshu-login.exe`（会弹原生 Chrome 扫码窗）。
- **不要用网页版小红书**（`/api/v1/login/qrcode` 那个接口的图是透明底小图，扫不出来，而且会和 MCP 抢登录态）。
- 脚本自己会检查服务与登录态，连不上会直接报错提示，不用你手动 curl。

## 一条龙：四步

### 第 0 步 · 查台账（**先做这步，不然白干**）

```bash
cd "C:/Users/hua/Documents/备份代码/小红书卖课件"
python "C:/Users/hua/.pi/agent/skills/xhs-courseware-post/scripts/published.py" --list
```

- 已发过的课题会列出来，**默认拒绝再发**（粉丝会认出同一张图，平台也会判重）。
- 未发课题为 0 → 说明该出新课件了，用 `courseware-factory` 做新课，别硬重发。
- 台账第一次用要先从主页初始化：`published.py --sync`（历史笔记没有图片 md5，只能按课题名去重；新发的会自动记 md5）。

### 第 0.5 步 · 做交付链接（**卖的是链接，不是笔记**）

**先把「买家付钱后拿到什么」做好，再发笔记。** 顺序反了就会出现"有人问价、你没东西发"。

### 一个课件 = 一个子文件夹 = 一条独立链接

把所有课件塞进同一个分享链接 = 买家买一套能看见全套 = 白送。所以每套单独一条：

```text
网盘 /课件/<课题>X-Y岁课件/        ← 这个文件夹 = 一条分享链接（带提取码）
      ├── <课题>X-Y岁课件.pdf
      └── 原图/01_范画成品.jpg ... 16 张
```

```bash
# 0) 先在工厂侧打交付包（PDF + 原图 + manifest）
python "C:/Users/hua/Documents/备份代码/小红书卖课件/工厂/deliver.py" "项目/<课题>/project.json" --zip

# 1) 看计划（不联网、不花钱、先确认文件清单）
"C:/Users/hua/Documents/备份代码/baidu-netdisk-xianyu/baidu-netdisk-mcp/.venv/Scripts/python.exe" \
  "C:/Users/hua/Documents/备份代码/小红书卖课件/工厂/netdisk_publish.py" "项目/<课题>/project.json" --dry

# 2) 真上传 + 建分享（--period 0 永久 / 7 / 30 天）
... 工厂/netdisk_publish.py "项目/<课题>/project.json" --period 0
```

产出：

- 屏幕上的 `✅ 交付链接 + 提取码`（**这就是成交后要发的那一句**）
- `项目/<课件>/交付/<课题>.../分享链接.json`（链接 / 提取码 / 文件清单 / 时间）
- 仓库根 `交付台账.json`（所有课题 → 链接，别把链接弄丢）

**依赖（必须先配好，否则脚本直接报错退出，不会传一半）：**

```ini
# C:/Users/hua/Documents/备份代码/baidu-netdisk-xianyu/baidu-netdisk-mcp/.env
BAIDU_NETDISK_ACCESS_TOKEN=...   # 从 https://pan.baidu.com/union/console/applist 建应用 → OAuth → 回调地址里的 access_token
```

用它的 `.venv` python 跑（脚本 import 网盘 MCP 的 `server.py` 复用 API 层，不靠常驻 MCP 进程）。
不要用 MCP 工具逐个传：单文件超过 30 秒会被工具超时切断，大 PDF 必挂。

**上传完先自查**：`file_list /课件` 能看到该文件夹、点开里面是 1 个 PDF + 原图 16 张。
脚本已做校验：任何一个文件没传成功就**不建分享**，避免发出残缺链接。

## 第 1 步 · 生成草稿

```bash
cd "C:/Users/hua/Documents/备份代码/小红书卖课件"
python "C:/Users/hua/.pi/agent/skills/xhs-courseware-post/scripts/prep_post.py" --next
python .../prep_post.py "项目/圣诞树-4-6岁/project.json"      # 指定课题
```

它会自动做四件事，并打印一份**选图理由报告**（哪张图因为什么被选中/丢弃）：

1. **按页面语义选图（成品流）**：成品（封面）→ 其它成品视角 → 知识页素材（优先「面部/特写」）→ 实物观察 → 材料工具；**默认跳过 `step` 页**。默认最多 9 张，超了从最不重要的开始丢（材料 → 实物 → 素材），封面永远保留。
2. **md5 去重**：三套课件都有「范画步骤5_加背景」与「范画成品」**内容完全相同**的坑，会自动跳过后一张。
3. **复制到纯 ASCII 暂存目录** `C:\Users\hua\tools\xiaohongshu-mcp\upload\<slug>\`，命名 `01_cover.jpg`、`02_detail1.jpg`…（**中文路径会导致发布失败**，必须转存）。
4. **封面补成 3:4**（首页瀑布流按 3:4 裁切，1536x1024 的横图会被切掉两边）：取四边像素中位色做背景补边，接缝看不出来，输出 1080x1440。
5. **从成品裁细节图**：默认 2 张（`--details`），从成品图按不同区域裁 3:4 放大。取代步骤图的「凑图数」作用，还比步骤图好看。
6. **打水印 + 备原图**：每张发布图加全图平铺文字（默认 10% 透明度）和右下角品牌条（品牌 + 小红书号）；同时把原图复制到 `项目/<课件>/img_orig/`，写 `manifest.json`（md5 / 尺寸 / 时间 / 发布记录）。

输出 `项目/<课件>/post.json`：`title` / `title_alt` / `content` / `tags` / `images` / `visibility`。

常用参数：`--next`（自动挑未发课题）、`--cap 12`（多放几张）、`--details 3`（多裁几张成品细节）、`--with-steps`（也发步骤图，老策略）、`--allow-repeat`（确实要重发）、`--no-watermark`（内部预览）、`--wm-text` / `--wm-id` / `--wm-opacity`（改水印文案/账号号/透明度）、`--slug xxx`（指定暂存目录名）。

### 第 2 步 · 改两处文案（**别跳，这一步决定点击率**）

脚本只能生成机械的那 80%，`content` 里留了**两个 `【】` 占位**，必须改掉：

1. **开头钩子** —— 第一行，决定别人点不点。写画面里最抓人的那个细节 + 「一节课孩子能画成这样」，不要写"这是一套课件"。
2. **「这个课题好上的地方」** —— 写 2~3 条，站在买课件的老师角度：形体好不好抓形 / 实物观察是不是真东西 / 颜色挑不挑笔。

**其余段落不要删**：`🖼 图上就是成品`、`🛒 想要这套`（三行 CTA）、`🤖 说明（AIGC）`、`📎 品牌`。
其中 CTA 和 AIGC 声明的文案在 `prep_post.py` 顶部常量里，要统一换说法改那里，不要每篇手改。

**`publish_post.py` 看到正文里还有 `【】` 会拒绝发布**，改完再发。改的时候直接编辑 `post.json` 的 `content` 字段。

- 标题太长了从 `title_alt` 里挑一个（脚本已经按小红书算法算过字数，超 20 的一开始就不会生成）。
- 标题想更好：可以把 `26页` 换成卖点，比如 `《小象洗澡》4-6岁创意美术课件·实物观察`，但**必须 ≤20 字**（中文字按 1 字算，ASCII 按 0.5 算，脚本会自动核）。
- 标签最多 10 个，脚本已经凑满 10 个通用的，想换直接改 `tags`。

### 第 3 步 · 发布 + 自动核实

```bash
python "C:/Users/hua/.pi/agent/skills/xhs-courseware-post/scripts/publish_post.py" "项目/小象洗澡-4-6岁/post.json"
python .../publish_post.py <post.json> --visibility public    # 公开
python .../publish_post.py <post.json> --dry-run              # 只校验不发
```

- **默认可见范围是「仅自己可见」**（`prep_post.py` 写进 `post.json` 的），试跑零风险。确认无误再 `--visibility public`。
- 核实方式不是看接口返回的 `success`，而是**重新拉一遍我的主页，diff 出新增的那条笔记**，打印笔记 id 和链接。
- 三道拦截（都是踩过坑加的）：`【】`占位符未改 → 拒绝；主页已有同标题笔记 → 拒绝（防重复发布/被平台判重）；超小红书硬上限 → 拒绝。确实要硬发加 `--force`。

### 第 4 步 · 回评论

```bash
python .../replies.py unread                                    # 未读数
python .../replies.py list --tab mentions --limit 20            # 评论/@ 通知（带 comment_id）
python .../replies.py reply --id <comment_id> --text "谢谢喜欢～"
python .../replies.py note-comments <feed_id> [--token <xsec_token>]   # 看某条笔记下的评论
python .../replies.py stats                                     # 粉丝/赞藏/笔记数
```

回评论的规矩：

- **评论里绝对不能出现微信 / QQ / 电话 / 外链 / "加我"**（脚本会拦这些词）—— 站外引流在小红书是违规，轻则限流重则封号。想引流就引导"主页看更多"。
- 不要秒回一堆一模一样的（像机器人）。先看内容再答，问"多少钱/怎么买"才引导私信。
- 只回复、不刷屏。

## 红线

1. **没有交付链接就不发笔记**。买家问价时你必须 3 秒内能给出一条只含这套课件的链接；
   没有链接就发，等于把人骗进主页再让他空手走。用 `工厂/netdisk_publish.py` 先做好。
1. **同一课题 / 同一张图不能重发**。默认由台账拦截（课题名 + 图片 md5 双重）。不要习惯性用 `--allow-repeat` 重发已经发过的课题——粉丝认出「又是那只大象」比少发一篇伤得多。真要重发同一课题，必须重出图（新 md5）并重写文案。
2. **发布图不能是裸图**。默认已经打水印（平铺 + 右下角品牌条）；`--no-watermark` 只用于内部预览，正式发出去之前确认 `_prep.watermark.enabled = true`。原图会在 `img_orig/` 留一份带 md5 的存证，别删。
2. **AIGC 声明不能删、不能弱化**。画面是 AI 出的，正文里必须留 `🤖 说明` 那段。删了既不符合平台对 AI 内容的标注要求，也容易被同行举报「AI 生成还当原创课件卖」。
3. **CTA 不能出现微信 / QQ / 电话 / 外链 / "加我"**，也不能出现 **「课包 / 打包 / 想要这套 / 私信工具」这类交易词**（实测会被拦，笔记发不出去）。只留「主页 / 合集 / 评论区」。价格更不要写正文。
4. **中文路径不能进发布请求**。图片必须先转存到 ASCII 目录（`prep_post.py` 已经做了，别绕开它手拼 `images`）。
5. **品牌名占位符（`【你的机构名】`）的课件直接拒绝发布** —— 品牌会印在每一页页脚，发出去就是废品。先改 `project.json` 的 `meta.brand`，再重跑 `工厂/builder.py` + `工厂/exporter.py`，然后才发。硬要发加 `--allow-placeholder-brand`。
6. **标题 ≤20 字、正文 ≤1000 字、标签 ≤10 个、图文 ≤18 张**（服务端会截断标签、拒绝超长正文，脚本前置就拦）。
7. **默认发「仅自己可见」，验证过再转公开**。公开版建议对标题/正文做点微调，避免和测试笔记撞重复检测。
8. **不要用个人生活号发课件**。笔记会被推给关注你生活内容的粉丝，画像乱掉、转化极差 —— 要用垂直号。当前 `xiaohongshu-mcp` 登录的号是不是垂直号，发之前确认一下。
9. 一条龙里 `工厂/pipeline.py`、`工厂/builder.py` 等**必须带 `--no-ui`**（否则会弹浏览器窗口）。
10. 别动用户的 WPS 文档；`out/` 里的 pptx/pdf 常被 WPS 锁住，写不进去就交付到 `out_new/`。

## 命令速查

| 目的 | 命令 |
| --- | --- |
| 查台账（先做） | `python .../scripts/published.py --list` |
| 从主页初始化台账 | `python .../scripts/published.py --sync` |
| 生成草稿（自动挑未发） | `python .../scripts/prep_post.py --next` |
| 生成草稿（不打水印，仅预览） | `python .../scripts/prep_post.py 项目/<课件>/project.json --no-watermark` |
| 生成草稿（指定课题） | `python .../scripts/prep_post.py 项目/<课件>/project.json [--cap 12] [--details 3]` |
| 生成草稿（带步骤图） | `python .../scripts/prep_post.py 项目/<课件>/project.json --with-steps` |
| 发布被拦时诊断 | 删掉 🛒 整段 → 发「仅自己可见」，能发就是文案问题 |
| 校验（不发） | `python .../scripts/publish_post.py 项目/<课件>/post.json --dry-run` |
| 发（仅自己可见） | `python .../scripts/publish_post.py 项目/<课件>/post.json` |
| 发（公开） | `python .../scripts/publish_post.py 项目/<课件>/post.json --visibility public` |
| 看未读 | `python .../scripts/replies.py unread` |
| 看评论通知 | `python .../scripts/replies.py list --tab mentions` |
| 回评论通知 | `python .../scripts/replies.py reply --id <id> --text "..."` |
| 看笔记评论 | `python .../scripts/replies.py note-comments <feed_id>` |
| 看账号数据 | `python .../scripts/replies.py stats` |

（`...` = `C:/Users/hua/.pi/agent/skills/xhs-courseware-post`）

## 踩过的坑（改脚本前先看）

- **发布耗时 1~2 分钟**，是 HTTP 长请求，别设短超时、别中途 Ctrl-C。
- **`/api/v1/login/status` 要 15~25 秒**（它会拉起浏览器校验），超时小于 30 秒会误报"没登录"。这个耗时**每次都不一样**，偶发超 30 秒内部死线返回 500 —— 所以发布脚本的登录检查失败时**先重试 2~3 次**，不要立刻去挪 cookies。
- 排查这类问题的最小实验（比读源码快）：用指纹版 Chrome 自己拉一个页面，看加载要几秒。
  ```bash
  "C:/Users/hua/AppData/Local/xiaohongshu-mcp/browser/148.0.7778.215/browser/chrome.exe" \
    --headless --no-sandbox --no-first-run --user-data-dir="C:/Users/hua/temp_probe" \
    --remote-debugging-port=0 > /tmp/probe.out 2>&1 &
  # 端口从 /tmp/probe.out 的 "DevTools listening on ws://127.0.0.1:<port>/" 里读
  # 再用 python + websocket-client 连 page 的 webSocketDebuggerUrl（必须 suppress_origin=True，带 Origin 会被 403）
  # 轮询 document.readyState / title。实测：有头 6 秒 complete，headless 卡住不动
  ```
  ⚠️ Windows 的 Python **不认 git-bash 的 `/tmp/...` 路径**（会当成 `C:\tmp\...`），要写 Windows 真实路径。
- **「发布未确认成功：点击发布后未跳转离开发布页」= 内容被拦，不是接口坏了**。典型触发：正文里的交易词（课包/打包/私信工具/想要这套）、未开放类目下卖虚拟商品。
  - 判定方法（3 分钟）：把 CTA 整段删掉、换成保守版，发「仅自己可见」。能发 → 是文案问题，不是账号；还不行 → 账号/接口。
  - 反例：删掉 CTA 后 177 秒发布成功，同一批图同一标题。
- **标签联想全部失败（日志 `未找到标签联想选项`）也是风控信号**，通常紧接着发布被拦。别以为是网络问题。
- **发布成功但主页计数不 +1**：`/api/v1/user/me` 的 feeds 是分页的（最多 60 条）+ 仅自己可见不计入公开计数，用「新增笔记 id」判断，不要用总数。
- **`/api/v1/user/me` 会偶发返回空的 `data.data`**（风控/超时），看起来像「我一条笔记都没有」。`xhs.my_notes()` 已内置重试 3 次；自己写脚本拉主页时也要重试，别拿空结果去判重。
- 台账 key 的归一化（`published.norm`）会去掉年龄、页数、`创意美术`、`课件`、标点 —— 标题 `《小象洗澡》4-6岁创意美术课件26页` 和项目名 `小象洗澡-4-6岁` 会归一到同一个 key。改 `norm` 后必须重建台账（删掉 `发布台账.json` 再 `--sync`），否则旧 key 和 `--next` 对不上。
- 通知列表结构：`data.data.{tab,filtered,items[]}`，item 形如 `{id,type,title,time,from:{user_id,nickname,xsec_token},feed_id,feed_title}`。
- **`范画步骤5_加背景` 和 `范画成品` md5 相同**（三套课件都这样），不去重会发两张一样的图。
- **步骤图会让笔记像模板广告**：默认已经不发，别为了凑图数又把 `--with-steps` 打开；要凑图数用 `--details`。
- **MCP 发布接口没有 AIGC 标识字段**，AI 声明只能写正文（`AI_DISCLOSURE`）。发完去 App 看是否有「内容由 AI 生成」选项要补勾。
- **封面必须 3:4**；直接裁会切掉两边，要**补边**（取边缘中位色）。细节图本身裁成 3:4，不触发二次裁切。
- Windows 控制台是 GBK，脚本里打印 emoji 会 `UnicodeEncodeError` —— 脚本已做 `utf-8` 重定向，自己加打印时注意。
- `.ps1` 存成 UTF-8 **带 BOM**；`.cmd` 存成纯 ASCII **不带 BOM**（带 BOM 的 cmd 会执行失败）。
- 解析课件数据时注意：`images[]` 里是 **`slot`** 字段（没有 id/filename），实际路径规则是 `img_sell/<slot>.jpg` 优先、其次 `img/<slot>.png`，跟 `工厂/project.py` 一致。
- 课件名字里带年龄（`《小象洗澡》4-6岁课件`），剥名字拼标题时**必须先把年龄去掉**，否则会拼出《小象洗澡46岁》。
- 没有"删除笔记"的接口/工具 —— 发错了只能去 App 里手动删。
- **`PUBLISH_FAILED / 创作者中心登录失效，请重新扫码登录` 大概率是瞬时故障**，不是真的掉登录：`stop-mcp.ps1` → 起服务 → 重发一次即可（实测第二次 162s 发布成功，笔记数 +1）。**先重试，别急着换 cookie**。
  - 真掉登录的判断方法：`cookies.json` 里 17 条 cookie 且 `is_logged_in:true` 就是好的；cookie 里只有 `.xiaohongshu.com / edith.xiaohongshu.com / www.xiaohongshu.com` 三个域，**没有** `creator.xiaohongshu.com`，创作者中心靠的就是 web_session，所以别指望按域判断。
  - 真需要重新扫码时：`xiaohongshu-login.exe` 若已“登录状态: true”会**直接退出、不刷新 cookie**；把 `cookies.json` 挪走再跑，才会进扫码流程（注意：这样会换一个 fingerprint seed）。
  - 反过来，如果浏览器 profile 还登录着（窗口停在 `xiaohongshu.com/explore`），登录工具会**死等一个永远不出现的扫码事件**、`cookies.json` 只有 99 字节且 `cookies: []`。判断办法：`powershell "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\""` 找到带 `remote-debugging-port` 的进程，`netstat -ano | grep <PID>` 拿端口，再 `GET http://127.0.0.1:<port>/json/list` 看当前 URL；是 explore 就说明 profile 已登录，别等二维码。

## 目录

```text
C:/Users/hua/.pi/agent/skills/xhs-courseware-post/
├── SKILL.md
└── scripts/
    ├── xhs.py             HTTP 封装 + 标题字数算法（镜像服务端 Go 实现）+ 规则校验
    ├── published.py       发布台账：课题去重 / 图片 md5 去重 / --sync / --list
    ├── watermark.py       水印（平铺 + 右下角品牌条）+ 原图备份 + 版权存证 manifest
    ├── prep_post.py       project.json -> post.json（选图/去重/补封面/裁细节/水印/生成文案）
    ├── publish_post.py    发布 + 回主页 diff 核实 + 成功后登记台账
    └── replies.py         未读/通知/评论/回复/账号数据

C:/Users/hua/Documents/备份代码/小红书卖课件/
└── 发布台账.json         ← 已发课题 + 已用图片 md5（去重的唯一依据）

项目/<课件>/
├── img_orig/           ← 原图存证（img_orig/manifest.json 记 md5 / 尺寸 / 时间 / 发布记录）
└── 商品素材/            ← 商品主图 + 详情长图 + 上架文案（图片同样带水印）

C:/Users/hua/tools/xiaohongshu-mcp/          ← MCP 本体 + 图片 ASCII 暂存区
├── xiaohongshu-mcp.exe / xiaohongshu-login.exe
├── 启动MCP.cmd / 停止MCP.cmd / 查看状态.cmd
└── upload/<slug>/        ← prep_post.py 转存出来的图
```
