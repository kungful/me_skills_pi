---
name: video-studio-mcp
description: 用脚本/AI 自动出片：剪辑引擎是开源 Concat（JSON-RPC），配音用免费 edge-tts，配乐从 AlgerMusicPlayer 本地接口下，字幕用本地 Whisper，混音走 ffmpeg（闪避/响度归一）。当用户说"剪个视频/自动剪辑/一键成片/给视频配音/加字幕/配背景音乐/把素材做成片/批量出片/用 Concat 剪/Concat MCP/concat-cli"，或要"发声/生成语音/文字转语音"，或要"下载背景音乐/找无版权 BGM"，或要"识别视频里的说话内容生成字幕"时使用。**注意：Concat 官方没有 MCP 服务**（文档写明 planned, not shipped），本 skill 自带那个 stdio 桥。纯做图/做课件不走这里。
compatibility: Windows（本机实测环境）；Python 3.10+；ffmpeg 在 PATH；Concat 0.2.7+ 且窗口里打开了「设置 › 远程」；配乐需要 AlgerMusicPlayer 在运行
allowed-tools: Bash, Read, Write, Edit
---

# VideoStudio-MCP · 自动出片流水线

**一句话：素材 + 解说词 + 配乐关键词 → 一条带配音、字幕、混音的成片 mp4，全程脚本化。**

代码在 `C:/Users/hua/Documents/备份代码/VideoStudio-MCP/`（MIT）。
它不是重写剪辑器 —— 剪辑仍然由 **Concat** 做，本项目只是把它当引擎使唤，并补齐了
「配音 / 配乐 / 字幕 / 混音」这四件 API 自己没有的事。

## 0. 先确认三件事（不然一定卡住）

```bash
cd "C:/Users/hua/Documents/备份代码/VideoStudio-MCP"
python cli.py doctor
```

1. **Concat 的远程口开着** → 窗口里 **设置 › 远程** 打开开关（地址 `127.0.0.1:7420`）。
   token 存在 `%APPDATA%\app.concat.editor\settings.json` 的 `server.token`，本项目会自动读。
   没开的话任何调用都会回 `连不上 Concat 的远程接口`。
2. **ffmpeg 在 PATH**（混音/探测都靠它）。
3. **配乐要 AlgerMusicPlayer 在跑** → 本地音乐 API `127.0.0.1:30488`（端口被占会 +1）。

## 1. 最快的三条命令

```bash
python cli.py demo                              # 造测试素材，端到端出一条片子（验证环境用）
python cli.py make scripts/example.json         # 按脚本出片
python cli.py make scripts/example.json --audio-only   # 只做声音+字幕，不碰 Concat
```

产物：项目文件夹 `~/Videos/ConcatEdits/<名字>/`（可在 Concat 窗口里继续手改）+ 成片 mp4。

## 2. 作为 MCP 用（推荐）

已注册（`~/.pi/agent/mcp.json` 里的 `videostudio`）时，25 个工具可直接调，典型顺序：

1. `studio_status` → 体检；`media_probe` → 看素材时长/分辨率
2. `tts_speak(text, voice="晓晓")` → 配音 + 逐词 SRT
3. `music_search` / `music_download(query, target_duration=片子长度)` → 配乐
4. `audio_mix(narration=[{file,at}], music={file,gain_db:-20,duck_db:-10})` → 混成一条轨
5. `studio_make(script)` 或细粒度：`project_new` → `add_clips` → `add_audio` → `add_captions` → `export`
6. `concat_call(method, params)` 是逃生口，能调 Concat 任意 API 方法

`studio_make_files(files, narration, music_query, name)` 是最省事的入口（素材+解说+配乐关键词）。

## 3. 脚本字段（写 `make` 的 JSON 用）

| 字段 | 默认 | 说明 |
|---|---|---|
| `name` / `location` | 未命名成片 / `~/Videos/ConcatEdits` | 项目名与所在地；**location 必须在用户目录下** |
| `clips[]` | — | `{file, in, out, volume}`，`in/out` 是原片里的秒 |
| `narration.pieces[]` | — | 一句解说的字符串或 `{text, voice, at, rate}` |
| `narration.voice` | `zh-CN-XiaoxiaoNeural`（别名「晓晓」） | 见 `cli.py voices` |
| `narration.overflow` | `tail` | 解说比画面长：`tail` 续镜头 / `trim` 按画面切 / `black` 留黑 |
| `music` | — | `{query}`（走 Alger）或 `{file}` 或 `{library}` 或 `{none:true}` |
| `subtitles.source` | `narration` | `narration`（配音时间戳）/`whisper`/`srt`/`none` |
| `export.output` / `skip` | 自动 / false | 路径要在 home 下；`skip:true` 只搭项目不导 |

## 4. 必须知道的坑（踩过一次就别再踩）

- **Concat 没有 MCP**。上游文档写明是 planned/not shipped（PR #69 关闭）。别去找
  `concat mcp` 子命令 —— 没有。本 skill 的 `mcp_server.py` 就是官方建议的那个桥。
- **Concat 只往用户目录写**：导出路径越界会被拒 `... is outside where this API writes`。
- **窗口正开着的项目，socket 改不动**；两边各开各的项目。
- **`batch` 里不能引用它自己刚造的 id** → 「加片段再按 clipId 裁切」必须拆两次调用。
- **`addClip` 没有时长参数**，长度=素材长度；裁切用 `trimClip(clipId, edge, delta)`。
- **重名项目不覆盖**，本项目自动加序号（`名字 2`）。
- **Whisper 模型从 ModelScope 下**（HF 在本机网络不通，hf-mirror 也超时）：
  `tiny` 78MB 花了约 4 分钟，中文建议 `small` 以上，先 `tiny` 试通道。
- **edge-tts 是非官方接口**，中文音色免费不限量，但要有网；断网场景用 `piper` 兜底。
  逐词时间戳要显式 `boundary="WordBoundary"`（本项目已处理），而且它不带标点，
  本项目按原文把标点还回去再断句。
- **配乐版权**：Alger 取的是网易云公开资源，只用于个人创作/学习；商用换本地授权曲库。
- **Concat 自带的 TTS / 声音克隆 / 自动字幕只有窗口里有，API 没暴露**，脚本用不了。

## 5. 自测

```bash
python tests/selftest.py            # 离线 32 项（假 Concat + 假音乐服务 + 真 ffmpeg）
python tests/selftest.py --online   # 36 项（加 edge-tts 与 Alger 真接口）
```

## 6. 和别的 skill 的分工

- 取素材（GoPro 无线拉片）→ `Concat-GoProBridge/gopro_concat.py`（姊妹项目）。
- 手机端卡点剪辑 → `AutoCut-Android/`。
- 从 GoPro Quik 逆出来的自动挑片段算法 → `_rea/quik/`（**还没接进来，是下一步**）。
- 只出单张图/封面 → `grsai-image-2-5`；发小红书 → `xhs-courseware-post` 那一套。
