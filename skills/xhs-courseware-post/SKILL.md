---
name: xhs-courseware-post
description: 把课件工厂产出的课件一条龙发到小红书（选图 → 补 3:4 封面 → 生成文案 → 发布 → 核实 → 回评论）。**作用域仅限「已有课件的发布与运营」，不做课件本身。** 默认「成品流」：只发成品+成品细节，不发步骤图；文案固定带购买引导（课件 / 做课件的工具），正文不写 AI 生成声明。用于：把课件发小红书/发笔记/上架；给课件写小红书文案、起标题、配话题标签；挑图、补封面、去重图；发出去以后核实、看通知、回评论。要做课件本身（做课件/改课件/导 PDF）用 courseware-factory。
---

# 小红书发课件 · 一条龙

把 `courseware-factory` 产出的 `project.json` 变成一条真发出去的小红书图文笔记，并负责发完之后的核实与回评论。

**一句话流程**：`published.py --list`（查台账，已发的课题不能发）→ **`netdisk_publish.py` 先把交付链接做好**（没链接别发笔记）→ `prep_post.py`（选图+补封面+打水印+生成文案）→ **人工/agent 改两处文案** → `publish_post.py`（发布+核实+登记台账）→ `replies.py`（回评论+成交后发链接）。

## 发布策略（2026-11 起，改策略先看这段）

1. **一个课题只发一次，一张图只出现一次**。发布台账 `发布台账.json`（在项目根）记录每个课题发过几篇、每张图的 md5。`prep_post.py` 发布前必查：课题已发 → 直接拒绝并列出未发课题；图片 md5 已用过 → 拒绝。用 `--next` 自动挑未发课题，别每次手选。
2. **只发成品，不发步骤图**。步骤图证明「这是套模板」，而且是最不好看的几张；成品图才是点击和转化的来源。默认选图 = 封面成品 + 从成品裁的局部特写 + 知识素材 / 实物 / 材料。要恢复老策略加 `--with-steps`。
3. **正文不写「AI 生成」**（用户 2026-11-07 定版）。`AI_DISCLOSURE` 已置空，`prep_post.py` 不再往正文加那句「画面由 AI 生成」；卖工具那条 CTA 也不带「AI 出图」字样。合规改走平台侧：发完去 App／创作中心看有没有「内容由 AI 生成」的标识开关要勾，那是平台级标注，不动正文也不影响转化。⚠️ 这是有意的取舍：正文不声明会少一层「AI 画的还卖钱」的挡箭牌，被举报时只能靠水印存证和原创声明，别再把这段自动加回来。
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

### 铁律：这个网盘是**售卖专用**，一个子文件夹只装一套课件

**网盘目录规范（2026-11-07 用户定版）**：

```text
/课件/小红书销售/                     ← 唯一的交付根目录（脚本默认 remote-root）
      ├── 西兰花出逃4-6岁课件/         ← 一个课题 = 一个文件夹 = 一条链接
      │   ├── 西兰花出逃4-6岁课件.pdf  ← 只能有 1 个 PDF
      │   ├── manifest.json
      │   └── 原图/01_范画成品.jpg ... 17 张
      └── 圣诞树4-6岁课件/            ← 另一套，独立链接
```

- **交付根目录 = `/课件/小红书销售`**（不是 `/课件`，也不是根目录的 `/小红书销售` —— 那个是空的，别用）。
- **文件夹命名 = `<课题>X-Y岁课件`**（去掉书名号，如 `西兰花出逃4-6岁课件`）。
  PDF 文件名必须与文件夹名**完全一致**（脚本会卡）。
- 一套课件一个链接，多套绝不合传 —— 买一套拿走全部是致命的。

把所有课件塞进同一个分享链接 = 买家买一套能看见全套 = 白送。所以：

```text
网盘 /课件/小红书销售/<课题>X-Y岁课件/   ← 这个文件夹 = 一条分享链接（带提取码）
      ├── <课题>X-Y岁课件.pdf            ← 只能有 1 个 PDF
      └── 原图/01_范画成品.jpg ... 16 张
```

**这套网盘里除了 `/课件/小红书销售/` 什么都不要放**（不放私人文件、不放素材仓、不放"全部课件"目录）。
一条链接 = 一套课件 = 一个买家。

`netdisk_publish.py` 已把这条规则做成**四道前置拦截 + 一道事后核对**，不用靠自觉：

| 闸门 | 拒什么 |
|---|---|
| 前置 1 | 交付包里 PDF 数量 ≠ 1（混进第二套 → 直接拒，并列出是哪几个） |
| 前置 2 | PDF 文件名 ≠ 课题文件夹名（发错商品、链接对不上） |
| 前置 3 | 文件夹名含「合集 / 全套 / 打包 / 系列 / bundle」 |
| 前置 4 | 文件数 > 40（单套约 17 个，明显是两套拼一起） |
| 事后核对 | 上传完、建链接**之前**再 `file_list` 数一遍远端该文件夹里的 PDF，≠1 就不建链接 |

另外两个容易漏的点，也已内置：

- **旧文件夹默认先移进回收站再重建**（`--keep-old` 可保留）。原因：`rtype=3` 只覆盖同名文件，
  上一版多出来的文件（比如 18 个 → 17 个）会**残留在链接里**，买家会看到两份不同版本的 PDF/图。
- **链接永久有效**（`--period 0`），有效期只给内测/临时用。买一次应该永远能下。

### 三条落地路径（选一条，规则都一样：一套一文件夹一链接）

| 路径 | 前提 | 命令 |
|---|---|---|
`A 开放平台 API`（推荐，全自动） | 百度账号**实名认证** → 控制台建应用 → 拿 `access_token` | `netdisk_publish.py <pj> --period 0` |
`B 网页版手动 + 记账`（今天就能用） | 已登录 pan.baidu.com | 手动拖文件夹上传 + 点分享，然后 `netdisk_publish.py <pj> --record "<链接>" --link-pwd 提取码` |
`C 网页版 DOM 自动化` | — | ❌ **别做**：虚拟列表 + 引导浮层 + 动态 DOM，逐点会一直失败 |

**实测卡点（2026-11）**：控制台「创建应用」返回 `errno 45018 user not auth, not allow create`
—— 百度网盘开放平台**要求账号实名认证**，没实名连应用都建不了，所以 A 路必须先让用户去实名。
在实名/审核完成之前，用 B 路：链接谁建的都行，`--record` 只做**记账**（仍会校验交付包里只有 1 个 PDF、
链接格式是网盘分享链接），把链接写进 `交付台账.json` + `分享链接.json`，后续发货/对账都读它。

#### ✅ 2026-11-07 已打通（实名 → 个人认证 → 应用 → token → 上传 → 链接）

**完整链路（照着抄）**：

| 步 | 动作 | 关键点 |
| --- | --- | --- |
| 1 | 账号实名（百度个人中心） | 只做完这步**没用**，控制台仍显示「未申请认证」 |
| 2 | **开放平台个人开发者认证** | 入口 `https://pan.baidu.com/union/apply` → 选「个人」→ 同意协议 → 填表 |
| 3 | 表单 | 姓名/身份证/手机号**从账号自动带出**；**密保邮箱必须先绑定**（去 `passport.baidu.com/v2/accountsecurity` 绑，短信验证） |
| 4 | 分类 | 一级「教育」→ 二级「在线教育」；提交后**立刻通过**（个人认证即时审核） |
| 5 | 控制台建应用 | `https://pan.baidu.com/union/console/applist` → 创建应用 → 分类「工具效率」 |
| 6 | **描述只能填汉字/字母/数字/空格** | 全角冒号括号会报「仅支持输入汉字、字母、数字、空格及常见标点符号」 |
| 7 | 拿 AppKey/SecretKey | 应用详情页是掩码，**直接调 API 取明文**：见下方命令 |
| 8 | 拿 access_token | **设备码模式**，不需要回调地址：`工厂/baidu_token_device.py`（浏览器里打开 verification_url → 输 user_code → 点「授权」） |
| 9 | 上传 | ⚠️ **开放平台没上传权限**，见下节 → 走网页版 API |
| 10 | 建分享 | 开放平台 `share?method=set` **正常可用**，period=0 = 永久 |

**取明文密钥（不用在页面上点「显示」）**：

```bash
# 应用详情页 URL 形如 /union/console/app/<appid>?data=...
# 打开详情页时浏览器会发这个请求，直接在浏览器里复现：
https://pan.baidu.com/rest/2.0/xpan/console/v1/appdetail?appid=<appid>&sign=<页面请求里的sign>&clienttype=0&app_id=250528&web=1
# 返回 JSON 里就有 appkey / secretkey / sign_key 明文
```

**拿 token（设备码模式，已写成脚本）**：

```bash
python 工厂/baidu_token_device.py
# → 打�� device_code + user_code + verification_url
#   在已登录百度的浏览器里打开 verification_url，输 user_code，点「授 权」
# → 脚本轮询换 token，自动写进 baidu-netdisk-mcp/.env
```

#### ⚠️ 开放平台「没有上传权限」（errno 31500 / 31064）

个人开发者的 token **能列目录、能建分享，但传不了文件**：

- `xpan/file?method=create` → `errno 31500`（precreate 成功、create 被拒）
- 老 PCS `pcs/file?method=upload` → `error_code 31064 file is not authorized`
- 但 `xpan/share?method=set` → **正常返回链接**

→ **上传改走网页版 API**（用 BDUSS cookie，不看应用权限），分享继续用开放平台接口。

**网页版上传（已跑通）**：直接用浏览器自己的上传器最省事，playwright 里：

```js
#### ✅ 2026-11-07 二次实测（照这段做，别踩重复的坑）

```js
// 1) 直接进目标目录（改 hash 里的 path 参数，比一层层点稳）
//    https://pan.baidu.com/disk/main#/index?category=all&path=<encodeURIComponent(远端绝对路径)>
// 2) 真实文件 input 的选择器是下面这个（上传按钮被它挡住，点按钮会 5s 超时）
//    input[type=file][name=html5uploader]   ← 带 multiple，一次塞完
// 3) 必须用 run_code_unsafe 的函数形式，且整段包在 async (page) => {...} 里
```

- **`browser_file_upload` 用不了**：报 `can only be used when there is related modal state present`。
  `browser_click` 点「上传」会被那个 input 拦截并超时（`subtree intercepts pointer events`）。直接 `setInputFiles`。
- **`run_code_unsafe` 的 code 必须是 `async (page) => {...}`**：写 `const ...` 或裸 `await page.xxx` 会
  `SyntaxError`，写 `(async () => {...})()` 会 `TypeError: __fn__ is not a function`。
- **同目录同名文件会变成 `xxx_20261107_220838.pdf`**，不是覆盖。所以上传前确保目录是空的，
  或传完把带时间戳的那份删掉（`file_del`），否则买家会看到两份 PDF —— 这是硬伤。
- **MCP 的 `baidu-netdisk_file_upload_local` 也报 31500**，但它返回 `isError: false`
  （`structuredContent` 里才是真 errno）→ **会被当成成功**。别用它传交付包，只用它读目录/建链接。
- **`baidu-netdisk_make_dir` 会给目录名加时间戳后缀**（`原图_20261107_220251`）。要么先建再 `file_rename` 去掉后缀
  （同名已存在时会变成 `原图(1)`，得再删），要么干脆先在网页版手动建好目录。
- **Git Bash 会把远端路径 `/课件` 转成 `C:/Program Files/Git/课件`**，导致报「文件夹命名中包含特殊字符」。
  所有带 `/课件...` 的命令前面加 `MSYS_NO_PATHCONV=1`。
- `netdisk_publish.py` 在 31500 失败时仍会先建目录，**会留下 `对称的美12-15岁课件_20261107_220005` 这类垃圾目录**，
  收尾时回 `/课件/小红书销售` 清一遍。

// 先进目标目录（双击进入，面包屑确认），再塞文件
await page.setInputFiles('input[type=file] >> nth=0', [绝对路径1, 绝对路径2, ...]);
// input 带 multiple，一次可以传 19 个
```

网页版接口与开放平台的差异（自己写 Python 版时必须补齐）：

```
precreate: POST https://pan.baidu.com/api/precreate
    ?rtype=1&bdstoken=<bdstoken>&app_id=250528&channel=chunlei&web=1&clienttype=0
    form: path=<远端完整路径>&autoinit=1&block_list=[md5...]&target_path=<目标目录>&local_mtime=<ts>
  → 少了 bdstoken / target_path 会返回 errno 404

create:    POST https://pan.baidu.com/api/create
    ?isdir=0&rtype=1&bdstoken=<bdstoken>&app_id=250528&channel=chunlei&web=1&clienttype=0
    form: path=&size=&uploadid=&block_list=&target_path=&local_mtime=

分片上传:  POST https://c5.pcs.baidu.com/rest/2.0/pcs/superfile2
    ?method=upload&app_id=250528&channel=chunlei&web=1&clienttype=0&path=<完整路径>&uploadid=<短id>
```

- `bdstoken`：从网盘页面 HTML 里正则抓（`bdstoken["\s:=]+([A-Za-z0-9]+)`），
  **不是** `window.locals.userInfo.bdstoken`（两个值不一样，页面实际用的是 HTML 里那个）。
- 返回 `return_type: 1` = 秒传，直接 create；`0` 才需要真传分片。
- 分享用开放平台 `xpan/share?method=set`（`fsid_list`、`period=0` 永久、`pwd` 4 位提取码）。

```bash
# 0) 先在工厂侧打交付包（PDF + 原图 + manifest）
python "C:/Users/hua/Documents/备份代码/小红书卖课件/工厂/deliver.py" "项目/<课题>/project.json" --zip

# 0.5) ⚠️ 上传：开放平台没有上传权限（31500）→ 用浏览器上传器（见上面「已打通」一节）
#       目标目录固定：/课件/小红书销售/<课题>X-Y岁课件/
#       上传完在网盘里核对：1 个 PDF + manifest.json + 原图/N 张
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

**上传完先自查**：`file_list /课件/小红书销售` 能看到该文件夹、点开里面是 1 个 PDF + manifest.json + 原图 16 张。
脚本已做校验：任何一个文件没传成功就**不建分享**，避免发出残缺链接。
（2026-11-07 实测：分享链接建好后**移动文件夹不影响链接** —— 链接跟 fsid 走，不跟路径走。）

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
3. **画材 + 适用学段（必查）** —— 模板会带上一套课件的口径，高年龄课件曾经被写成「马克笔」「幼儿园」。现在 `material_hint()` 从 `materials` 页读真实画材、`stage_hint()` 按年龄给学段（≥12 岁写「初中课堂」），但**出稿前仍要人眼扫一遍**。

**其余段落不要删**：`🖼 图上就是成品`、`🛒 想要这套`（三行 CTA）、`📎 品牌`。
`🤖 说明（AIGC）` 已经默认不生成（见上面第 3 条）。
CTA 文案在 `prep_post.py` 顶部常量里，要统一换说法改那里，不要每篇手改。

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
1. **网盘是售卖专用，一个子文件夹只装一套课件**。多套合传 = 买一套拿走全部；
   同一套换版时旧文件夹必须先清掉（脚本默认会做），否则链接里会残留旧版文件。
   脚本已内置 4 道前置拦截 + 建链接前的事后核对，别绕过它手搓上传。
1. **交付物没过自检不发**。发之前这两条都得干净（都属于 `courseware-factory`）：
   ```bash
   python 工厂/preflight.py   项目/<课题>/project.json    # 图：链条一致性 / 起形页上色 / 背景提前涂 / 缺图
   python 工厂/layout_check.py 项目/<课题>/project.json   # 版式：文字溢出 / 越界 / 缺图 / 空页
   ```
   理由很直接：笔记是给**还没买的人**看的，PDF 是给**已经付钱的人**看的；
   封面图好看但 PDF 里步骤和成品不是同一棵树（2026-11 真实踩过），退款和差评比少发一篇贵得多。
1. **同一课题 / 同一张图不能重发**。默认由台账拦截（课题名 + 图片 md5 双重）。不要习惯性用 `--allow-repeat` 重发已经发过的课题——粉丝认出「又是那只大象」比少发一篇伤得多。真要重发同一课题，必须重出图（新 md5）并重写文案。
2. **发布图不能是裸图**。默认已经打水印（平铺 + 右下角品牌条）；`--no-watermark` 只用于内部预览，正式发出去之前确认 `_prep.watermark.enabled = true`。原图会在 `img_orig/` 留一份带 md5 的存证，别删。
2. **正文不写 AI 生成（2026-11-07 定版），但要留平台侧的标识**。发完去 App 补勾 AIGC 标识；正文里不要再加回去。
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
| 打交付包（PDF+原图） | `python "C:/Users/hua/Documents/备份代码/小红书卖课件/工厂/deliver.py" "项目/<课题>/project.json" --zip` |
| 交付链接（先 dry） | `<网盘venv python> 工厂/netdisk_publish.py "项目/<课题>/project.json" --dry` |
| 交付链接（真上传） | `... 工厂/netdisk_publish.py "项目/<课题>/project.json" --period 0` |
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
- **MCP 发布接口没有 AIGC 标识字段**，正文也不写了（见规则 3）。发完必须去 App 看有没有「内容由 AI 生成」选项要补勾 —— 这是唯一剩下的标注动作。
- **封面必须 3:4**。`prep_post.py` 默认是「按边缘中位色补边」，横幅实拍图补出来是两条硬色带，
  而且平铺水印压在纯色带上特别显眼 → **一上手就该换掉**：从成品图**居中裁 3:4**（`1272x1696` 这种），
  满幅、不留色带。改完同步 `post.json` 的 `images` + `_prep.image_md5`，否则台账按 md5 去重会漏记。
  细节图本身裁成 3:4，不触发二次裁切。
- Windows 控制台是 GBK，脚本里打印 emoji 会 `UnicodeEncodeError` —— 脚本已做 `utf-8` 重定向，自己加打印时注意。
- `.ps1` 存成 UTF-8 **带 BOM**；`.cmd` 存成纯 ASCII **不带 BOM**（带 BOM 的 cmd 会执行失败）。
- 解析课件数据时注意：`images[]` 里是 **`slot`** 字段（没有 id/filename），实际路径规则是 `img_sell/<slot>.jpg` 优先、其次 `img/<slot>.png`，跟 `工厂/project.py` 一致。
- 课件名字里带年龄（`《小象洗澡》4-6岁课件`），剥名字拼标题时**必须先把年龄去掉**，否则会拼出《小象洗澡46岁》。
- 没有"删除笔记"的接口/工具 —— 发错了只能去 App 里手动删。
- **`PUBLISH_FAILED / 创作者中心登录失效，请重新扫码登录` 大概率是瞬时故障**，不是真的掉登录：`stop-mcp.ps1` → 起服务 → 重发一次即可（实测第二次 162s 发布成功，笔记数 +1）。**先重试，别急着换 cookie**。
- **百度网盘开放平台「上传」接口对个人开发者不放权**：create 报 `errno 31500`、老 PCS 报 `31064 file is not authorized`，
  但 share 接口正常。**上传必须走网页版 API（BDUSS cookie）+ 浏览器上传器**，分享才能用开放平台接口。细节见上面「已打通」一节。
- **git-bash 会把以 `/` 开头的命令行参数转成 Windows 路径**：`python 工厂/baidu_web_upload.py <本地> "/课件/xxx"`
  → 远端目录变成 `C:/Program Files/Git/课件/xxx`。传网盘路径要加 `MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*"`。
- **后台任务日志文件名用 ASCII**：中文名 `> logs/西兰花_chain.log` 在 bash 里会报 `No such file or directory`。
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
    ├── replies.py         未读/通知/评论/回复/账号数据
    └── netdisk_publish.py 交付链接脚本的备份副本（实跑工作根里的 工厂/netdisk_publish.py）

C:/Users/hua/Documents/备份代码/小红书卖课件/
├── 工厂/
│   ├── deliver.py           交付打包（PDF + 原图 + manifest）
│   └── netdisk_publish.py   上传网盘 + 每课题一条独立分享链接
├── 交付台账.json        ← 课题 → 链接 / 提取码，成交后要发的那一条就靠它
└── 发布台账.json         ← 已发课题 + 已用图片 md5（去重的唯一依据）

项目/<课件>/
├── img_orig/           ← 原图存证（img_orig/manifest.json 记 md5 / 尺寸 / 时间 / 发布记录）
└── 商品素材/            ← 商品主图 + 详情长图 + 上架文案（图片同样带水印）

C:/Users/hua/tools/xiaohongshu-mcp/          ← MCP 本体 + 图片 ASCII 暂存区
├── xiaohongshu-mcp.exe / xiaohongshu-login.exe
├── 启动MCP.cmd / 停止MCP.cmd / 查看状态.cmd
└── upload/<slug>/        ← prep_post.py 转存出来的图
```
