---
name: xhs-courseware-post
description: 把课件工厂产出的课件一条龙发到小红书（选图 → 补 3:4 封面 → 生成文案 → 发布 → 核实 → 回评论）。**作用域仅限「已有课件的发布与运营」，不做课件本身。** 用于：把课件发小红书/发笔记/上架；给课件写小红书文案、起标题、配话题标签；挑图、补封面、去重图；发出去以后核实、看通知、回评论。要做课件本身（做课件/改课件/导 PDF）用 courseware-factory。
---

# 小红书发课件 · 一条龙

把 `courseware-factory` 产出的 `project.json` 变成一条真发出去的小红书图文笔记，并负责发完之后的核实与回评论。

**一句话流程**：`prep_post.py`（选图+补封面+生成文案草稿）→ **人工/agent 改两处文案** → `publish_post.py`（发布+核实）→ `replies.py`（回评论）。

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

- 没登录 / 掉登录 → 跑 `C:\Users\hua\tools\xiaohongshu-mcp\xiaohongshu-login.exe`（会弹原生 Chrome 扫码窗）。
- **不要用网页版小红书**（`/api/v1/login/qrcode` 那个接口的图是透明底小图，扫不出来，而且会和 MCP 抢登录态）。
- 脚本自己会检查服务与登录态，连不上会直接报错提示，不用你手动 curl。

## 一条龙：四步

### 第 1 步 · 生成草稿

```bash
cd "C:/Users/hua/Documents/备份代码/小红书卖课件"
python "C:/Users/hua/.pi/agent/skills/xhs-courseware-post/scripts/prep_post.py" "项目/小象洗澡-4-6岁/project.json"
```

它会自动做四件事，并打印一份**选图理由报告**（哪张图因为什么被选中/丢弃）：

1. **按页面语义选图**：成品（封面）→ 范画每一步 → 知识页素材（优先「面部/特写」）→ 实物观察 → 材料工具；默认最多 9 张，超了从最不重要的开始丢（材料 → 实物 → 素材 → 步骤），封面永远保留。
2. **md5 去重**：三套课件都有「范画步骤5_加背景」与「范画成品」**内容完全相同**的坑，会自动跳过后一张。
3. **复制到纯 ASCII 暂存目录** `C:\Users\hua\tools\xiaohongshu-mcp\upload\<slug>\`，命名 `01_cover.jpg`、`02.jpg`…（**中文路径会导致发布失败**，必须转存）。
4. **封面补成 3:4**（首页瀑布流按 3:4 裁切，1536x1024 的横图会被切掉两边）：取四边像素中位色做背景补边，接缝看不出来，输出 1080x1440。

输出 `项目/<课件>/post.json`：`title` / `title_alt` / `content` / `tags` / `images` / `visibility`。

常用参数：`--cap 12`（多放几张）、`--slug xxx`（指定暂存目录名）、`--visibility` 见第 3 步。

### 第 2 步 · 改两处文案（**别跳，这一步决定点击率**）

脚本只能生成机械的那 80%，`content` 里留了**两个 `【】` 占位**，必须改掉：

1. **开头钩子** —— 第一行，决定别人点不点。写画面里最抓人的那个细节，不要写"这是一套课件"。
2. **「这个课题好上的地方」** —— 写 2~3 条，站在买课件的老师角度：形体好不好抓形 / 实物观察是不是真东西 / 颜色挑不挑笔。

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

1. **中文路径不能进发布请求**。图片必须先转存到 ASCII 目录（`prep_post.py` 已经做了，别绕开它手拼 `images`）。
2. **品牌名占位符（`【你的机构名】`）的课件直接拒绝发布** —— 品牌会印在每一页页脚，发出去就是废品。先改 `project.json` 的 `meta.brand`，再重跑 `工厂/builder.py` + `工厂/exporter.py`，然后才发。硬要发加 `--allow-placeholder-brand`。
3. **标题 ≤20 字、正文 ≤1000 字、标签 ≤10 个、图文 ≤18 张**（服务端会截断标签、拒绝超长正文，脚本前置就拦）。
4. **默认发「仅自己可见」，验证过再转公开**。公开版建议对标题/正文做点微调，避免和测试笔记撞重复检测。
5. **不要用个人生活号发课件**。笔记会被推给关注你生活内容的粉丝，画像乱掉、转化极差 —— 要用垂直号。当前 `xiaohongshu-mcp` 登录的号是不是垂直号，发之前确认一下。
6. 一条龙里 `工厂/pipeline.py`、`工厂/builder.py` 等**必须带 `--no-ui`**（否则会弹浏览器窗口）。
7. 别动用户的 WPS 文档；`out/` 里的 pptx/pdf 常被 WPS 锁住，写不进去就交付到 `out_new/`。

## 命令速查

| 目的 | 命令 |
| --- | --- |
| 生成草稿 | `python .../scripts/prep_post.py 项目/<课件>/project.json [--cap 12] [--slug x]` |
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
- **`/api/v1/login/status` 要 10 秒以上**（它会拉起浏览器校验），超时小于 10 秒会误报"没登录"。
- 这个 MCP 的响应常常**套两层** `data.data`（通知未读数、笔记列表都是），取数据要往里挖一层。
- 通知列表结构：`data.data.{tab,filtered,items[]}`，item 形如 `{id,type,title,time,from:{user_id,nickname,xsec_token},feed_id,feed_title}`。
- **`范画步骤5_加背景` 和 `范画成品` md5 相同**（三套课件都这样），不去重会发两张一样的图。
- 封面必须 3:4；直接裁会切掉两边，要**补边**（取边缘中位色）。
- Windows 控制台是 GBK，脚本里打印 emoji 会 `UnicodeEncodeError` —— 脚本已做 `utf-8` 重定向，自己加打印时注意。
- `.ps1` 存成 UTF-8 **带 BOM**；`.cmd` 存成纯 ASCII **不带 BOM**（带 BOM 的 cmd 会执行失败）。
- 解析课件数据时注意：`images[]` 里是 **`slot`** 字段（没有 id/filename），实际路径规则是 `img_sell/<slot>.jpg` 优先、其次 `img/<slot>.png`，跟 `工厂/project.py` 一致。
- 课件名字里带年龄（`《小象洗澡》4-6岁课件`），剥名字拼标题时**必须先把年龄去掉**，否则会拼出《小象洗澡46岁》。
- 没有"删除笔记"的接口/工具 —— 发错了只能去 App 里手动删。

## 目录

```text
C:/Users/hua/.pi/agent/skills/xhs-courseware-post/
├── SKILL.md
└── scripts/
    ├── xhs.py             HTTP 封装 + 标题字数算法（镜像服务端 Go 实现）+ 规则校验
    ├── prep_post.py       project.json -> post.json（选图/去重/补封面/生成文案）
    ├── publish_post.py    发布 + 回主页 diff 核实
    └── replies.py         未读/通知/评论/回复/账号数据

C:/Users/hua/tools/xiaohongshu-mcp/          ← MCP 本体 + 图片 ASCII 暂存区
├── xiaohongshu-mcp.exe / xiaohongshu-login.exe
├── 启动MCP.cmd / 停止MCP.cmd / 查看状态.cmd
└── upload/<slug>/        ← prep_post.py 转存出来的图
```
