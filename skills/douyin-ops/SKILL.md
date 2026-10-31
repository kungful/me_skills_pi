---
name: douyin-ops
description: 运营抖音账号的一整套能力：解析/无水印下载抖音作品、爆款拆解（数据+前3秒钩子+口播结构+热评需求）、热榜选题、视频转文案(ASR)、扫码登录、自动发布视频/图文（含定时与预览）、读我的作品数据与账号数据、评论互动、发布队列。当用户说"发抖音/发布视频/发一条抖音/运营抖音号/抖音选题/拆解这条爆款/下载抖音无水印/抖音文案提取/看我的抖音数据/回抖音评论/定时发抖音"时使用。注意：这是抖音（中国区），不是 TikTok，也不是小红书（那个用 xiaohongshu MCP）。
---

# 抖音运营（douyin-ops MCP）

MCP 服务器名：**`douyin`**（29 个工具，全部以 `douyin_` 前缀）。
实现：`C:\Users\hua\Documents\备份代码\douyin-mcp-fusion`（Node + 系统 Chrome，登录态持久化在 `data/browser-profile`）。

## 先用哪条路

| 用户想干什么 | 调什么 |
|---|---|
| 给个分享链接，看是什么、要无水印视频 | `douyin_parse` → `douyin_download` |
| 下载某个博主的一堆作品 | `douyin_batch_download({source:'user', target:'主页链接', limit:10})` |
| 今天发什么 | `douyin_trending({board:'hot', videos:10})` |
| 这条为什么爆 / 我要模仿它 | `douyin_breakdown({target})` |
| 把视频里的话抄下来 | `douyin_transcribe({target})` |
| 发一条视频 / 图文 | 先 `douyin_login_status`，再 `douyin_publish_video({...,dryRun:true})` |
| 排一周的内容 | `douyin_queue_add` × N（或 `douyin_queue_run` 手动跑到期） |
| 我的数据怎么样 | `douyin_my_videos` + `douyin_account_overview` |
| 回评论 / 点赞 / 看通知 | `douyin_comments_list` → `douyin_comment_publish`；`douyin_notifications` |

## 登录（一次性）

发布、搜索、看数据、写互动都要登录。**登录态是持久的**，别每次都让用户扫。

```
douyin_login_status({})                       # 先看，已登录就别打扰用户
douyin_login_qrcode({ waitSeconds: 120 })     # 返回二维码文件路径 + base64，等用户扫
```
- 二维码在**用户自己的 Chrome 窗口**里也看得见，直接让用户看屏幕扫最省事。
- 扫完后 `douyin_login_status` 应该同时 `wwwLoggedIn: true` 和 `creatorLoggedIn: true`。

## 发布（务必先预览）

```
douyin_publish_preflight({kind:'video', files:[绝对路径]})       # 规格自查，有问题先修
douyin_publish_video({
  file, title, desc, topics:['话题1','话题2'],
  cover, scheduleAt:'2026-11-05 19:30',
  dryRun: true            # ← 第一次一定先 true
})
```
- `dryRun:true` 会一路填到"发布按钮就在眼前"，返回截图路径 + 页面文本 + `steps`。**看完截图再说要发。**
- 确认无误后 `dryRun:false` 重跑同一份参数即可真发。
- 发布失败时返回值里有 `stage`（preflight / login / upload-input / uploading / submit / published）和 `steps`，直接照着定位，不要瞎试。
- 中途弹验证码 → 让用户在 Chrome 窗口里手动过，然后重试。

## 已验证 / 已知限制（2026-10-31 实测）

- ✅ 解析、下载、评论读、热榜、搜索、我的作品数据、账号概览、扫码登录
- ✅ 发视频（标题+描述+话题，已真发）、发图文（预览通过）、定时发布
- ✅ 发评论（走作品页 UI，输入回车，读回验证过）
- ⚠️ 点赞：页面只暴露 0×0 的隐藏节点，偶发点了不动，重试一次
- ❌ 自定义封面：平台弹窗要人工裁切，自动「完成」不生效；失败会自动关弹窗，不挡发布
- ⚠️ 抖音 Web 写接口（comment/publish、digg）被风控（status_code 8/4），所以互动走 UI；连续高频会被限流

## 合规边界（先看这条）

本 MCP 只能用于**用户本人的账号**和**用户拥有权利的内容**。
如果用户要求：刷量刷赞、批量养号/多号矩阵、绕过验证码或风控、大规模抓取并转售数据、搬运他人作品去发布、发违法违规内容 —— **直接拒绝，并说明这违反平台协议与法律**（详见项目 `DISCLAIMER.md`）。
发布前默认先 `dryRun: true` 并把截图给用户确认；"代点发布"这件事的后果由用户承担。

## 铁律

1. **别开无头**。抖音对 headless 必然下验证码；本项目默认有头 Chrome。
2. **批量要慢**。`douyin_batch_download` 内部已限速，单次 `limit` 别超 30；连续操作之间隔几秒。
3. **`stats.play` 为 null 是正常的**：别人作品的播放量不公开，只有 `douyin_my_videos` 有真值。
4. **不要拿它刷量**：会限流封号；点赞评论工具是用来做真实互动的。
5. 遇到 `captcha` / `risk` 类报错：先让用户过验证码或等几分钟，不要连续重试打满风控。
6. 一句话别调 4 个以上重工具：Chrome 上下文串行执行，慢且容易被判定异常。

## 常用命令（本地）

```bash
cd "C:\Users\hua\Documents\备份代码\douyin-mcp-fusion"
npm run smoke                 # 免登录能力自检
npm run smoke -- --full       # 加下载 + 转写
node scripts/login.js         # 命令行扫码登录（agent 不在时）
npm run queue                 # 定时发布守护进程（30s 轮询）
node scripts/protocol-test.js # MCP 协议自检
```

数据都在 `data/`：`browser-profile`（登录态，别删）、`downloads`、`shots`（截图）、`queue.json`、`manifest.json`（下载去重）。

## 和其他技能的分工

- 剪片/配音/字幕 → `videostudio`（本 MCP 只负责抖音侧的采集、发布、数据）
- 小红书 → `xiaohongshu` MCP
- 静态图/封面 → `grsai-image-2-5`
