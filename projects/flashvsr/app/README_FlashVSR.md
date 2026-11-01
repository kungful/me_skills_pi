# FlashVSR+ 视频超分镜像

镜像与代码版本：

| 镜像 | 内容 |
| --- | --- |
| `d6895c78-66cb-455c-8a4e-82cf77038593`（v5，2026-11-01 11:35） | 含长片自动分片解码（修 OOM）；**不含文件库 / 删除 / preset 修复** |
| v4 `937aa22e-a471-4802-a366-655336e6bfb1` | 旧版，2K 长片会 OOM，别用 |

⚠️ 文件库、删除、`resolve_preset` 这些改动目前只在 `15nfp4tydm76nnt0` 这台实例上，
**还没存成镜像** —— 下次存的时候记得命名为 v6。

容器里的 WebUI 代码 = `/root/app/app.py`（+ `uploader.py`/`simple.html`），本地副本 = 本目录。

开箱即用的视频超分（Video Super-Resolution / 高清放大）环境，基于
[OpenImagingLab/FlashVSR_Plus](https://github.com/OpenImagingLab/FlashVSR_Plus)，
自带 Gradio WebUI 和 turbo / base 两套全量权重。

## 用法

1. 用本镜像开一台 **RTX 4090 / 4090 D (24G)** 实例。
2. 浏览器打开（容器自启，等 30~40 秒）：

   ```
   https://<实例ID>-7860.container.x-gpu.com        # 精简版（默认，推荐）
   https://<实例ID>-7860.container.x-gpu.com/g      # Gradio 版（备用）
   https://<实例ID>-7860.container.x-gpu.com/up     # 分片上传台
   ```

3. 选/传视频 → 选分辨率 → 「开始放大」→ 看进度 → 播放/下载结果。

### 两个前端，选「精简版」更稳

| | 精简版 `/` | Gradio 版 `/g` |
| --- | --- | --- |
| 传输 | 纯 JSON 短请求（fetch + 重试） | Gradio queue，走 SSE |
| 抗代理掐连接 | ✅ 断了自动重试 | ❌ 会弹 `Connection to the server was lost` / `Unexpected end of JSON input` |
| 上传 | 2 MB 分片续传 | 整块 multipart（>20 MB 常失败） |

平台的反向代理不老实：实测随机 TLS EOF、随机掐长连接。Gradio 每个事件都要开一条 SSE
流，所以它在浏览器里会时好时坏；精简版的每个请求都是「一问一答」，抖一下就重试，用户无感。

### 传片子：别用 Gradio 版的内置上传（重要）

实测这台机器的公网 HTTP 代理只有 **~0.3 MB/s**，而且**单次请求时间一长就被掐断**——
Gradio 内置上传是「整块 multipart 一个请求」，传几十 MB 以上就会拿到空响应，
浏览器报 `Unexpected end of JSON input`。

两条可用路线（都比内置上传靠谱）：

1. **分片续传上传台**：`https://<实例ID>-7860.container.x-gpu.com/up`
   2 MB 一片、每片一个短请求，断了自动重试，刷新页面还能从断点续传。
2. **服务器直接拉**：WebUI 里「服务器下载」贴视频直链 / 站点链接（yt-dlp），
   机房下载速度 15 MB/s，下完在左侧下拉里选。

也可以 `scp/sftp` 传到 `/root/uploads`（SSH 端口见控制台），然后点「刷新列表」。

## 文件库（缩略图 / 预览 / 下载 / 删除，断了也能接着看）

精简版页面 `/s` 底部第 4 块是文件库，两个页签：**放大结果**（`/root/outputs`）和
**上传的原片**（`/root/uploads`）。每个文件一张缩略图 + 尺寸 + 时长 + 大小，点一下弹预览。

设计上专门对「代理会随机掰长连接」做了适配：

| 环节 | 做法 | 为何这样 |
| 缩略图 | 服务端 ffmpeg 取第 1 秒帧，`scale=420:420`，缓存到 `/root/thumbs` | 单张 8~15 KB，弱网也能刷开；按 md5(路径+mtime+size) 缓存，文件一变自动重算 |
| 加载 | `loading="lazy"` + 失败自动重试（最多 3 次，带 `&r=n` 绕缓存） | 网络抖了也不出空图 |
| 预览播放 | `FileResponse` 支持 **Range**（实测 206） | 20 MB 的片子支持边下边播、能拖进度，不用等整个文件 |
| 断线续看 | 进度存在浏览器 `localStorage`（`fv_pos:<文件名>`，每 3 秒存一次），下次打开自动 seek 回去 | 代理扼断后重开就能接着看；顶部还有「↻ 继续上次」 |
| 下载 | `/api/file?...”&dl=1`（`Content-Disposition: attachment`） | 想存本地时不被浏览器内联播放 |
| 深链 | `/s?open=<文件名或前缀>` | 把某个结果直接发给客户看预览 |
| 删除 | 预览弹窗里「删除」→ `POST /api/delete`，只限 outputs/uploads，`basename` 防目录穿越，正在被任务使用的文件拒删，顺带清缩略图缓存 | 清理废片不用进控制台 |
| 待跑预览 | 「视频来源」卡里会显示当前选中的文件（缩略图 + 尺寸/时长/大小），点一下直接播 | 跑之前先确认选对了片 |

### 两个已修的坑（2026-11-01）

**1. 图片被当视频跑，产出「只有一帧」。** 精简版「服务器上的文件」下拉框以前直接列
`/root/uploads` 里的所有文件，选了 `thumb.jpg` 也会提交；而且 **ffprobe 会把 .jpg 当成 1 帧的
mjpeg 流**（宽高/时长都有），所以光看宽高不能识别。现在三道防线：

- 下拉框只收 `kind == video`（`/api/files` 返回的 kind，按扩展名判）；
- `video_guard()`：扩展名是图片、或 `帧数 ≤ 1 / 时长 ≤ 0` → 直接拒，前端弹人话；
- `up_list()` 也加上了 `kind` 字段。

**2. 精简版选的分辨率被忽略。** Gradio 版传中文标签（`2K 级 2560×1408…`），精简版传短名
（`2560x1408`），而 `PRESETS` 只有中文键，`PRESETS.get("2560x1408")` 恒为 None → 静默
回退成“自动 2 倍”。现在用 `resolve_preset()` 两边通吃：中文标签 / 短名 / `宽x高` 都认，
非 128 倍数的自定义值才拒绝。

实测：同一张竖图，修前出 `512×896 · 1 帧`，修后直接拒；`preset=896x512` 出
`896×512 · 24 帧`（修前会变成自动算的 512×896）。

接口（都是短 JSON / 短请求，无 SSE）：

```
GET /api/files?which=out|up      → {dir, files:[{name,size,mtime,kind,w,h,dur,fps,frames,url,dl,thumb}]}
GET /thumb?which=out&name=x.mp4  → image/jpeg（420×420 内等比缩略图，缓存 7 天）
GET /api/file?which=out&name=x.mp4[&dl=1] → 原文件，支持 Range / inline 播放
POST /api/delete  {which,name}           → 删文件（含缩略图缓存）
```

实测：缩略图 8.8 KB / 3.3 s（首次，之后命中缓存）、公网 Range 请求 206、页面 20 KB 秒开。

### WebUI 是「后台任务 + 轮询」模式
点「开始」后推理在服务端独立线程里跑，**页面断了、网络抖了、关掉浏览器都不影响任务**，
回来看状态和结果就行（云厂商的反向代理会掐长连接，所以刻意不用 SSE 长连接）。

- **端口 7860**（写死的，改端口就要改公网地址）
- 大文件别用浏览器上传：先 `sftp` / Jupyter 传进 `/root/uploads`，再把绝对路径填到
  「容器内路径」那个框，绕开公网代理上传的坑。
- 「取消」按钮会 SIGINT 掉整组进程，显存立即释放。

## 关键路径

| 内容 | 路径 |
| --- | --- |
| 仓库 | `/root/FlashVSR_Plus` |
| 权重 | `/root/fv/ckpts`（仓库里 `ckpts` 是软链接） |
| WebUI | `/root/app/app.py`（日志 `/root/logs/webui.log`） |
| 单次任务日志 | `/root/logs/job_<月日-时分秒>.log` |
| 输出视频 | `/root/outputs` |
| 上传中转 | `/root/uploads` |
| 自启钩子 | `/scripts/start.d/flashvsr-webui.sh`（带 flock，只跑一个） |
| 分片上传台 | `uploader.py`，挂在同一进程的 `/up` 路径（平台只放行 7860 / 8888 端口） |
| Python | `/root/miniconda3/bin/python`（conda base，torch 2.6.0+cu124） |

## 命令行用法

```bash
cd /root/FlashVSR_Plus
/root/miniconda3/bin/python -m inference.run_stream \
  --input input.mp4 --output /root/outputs/out.mp4 \
  --mode turbo --height 1152 --width 2048 \
  --temporal-compression 4 --video-preset veryfast
```

**宽高必须是 128 的倍数**，所以没有 1920×1080 / 1280×720 这种尺寸，常见合法值：
`2048×1152`（16:9）、`2560×1408`、`3840×2176`、`1280×768`、`896×512`。

### ⚠️ 长片 / 大片一定要分片解码（2026-11-01 修好的坑）

`--decode-every auto`（整条解码）会把**整条片子**做成 float32 常驻内存，再加上时间维展开和
输出，实测 **594 帧 720×1280 → 2560×1408 需要 ≈60 GB，直接顶满容器 57 GB 上限被内核 OOM 杀掉**。
被 SIGKILL 的进程**不会有 traceback**，日志里就停在最后一行：

```
● Running inference...          ← 然后什么都没有，任务显示「失败」
```

诊断办法（容器里没有 dmesg 权限，看 cgroup 计数器）：

```bash
cat /sys/fs/cgroup/memory.events      # oom_kill 涨了就是被内核杀的
cat /sys/fs/cgroup/memory.peak        # 60129550336 = 顶满 57 GB
```

**WebUI 现在自己算这笔账**：按 `帧数 × 宽 × 高 × 3 × 4 字节 × 2.5` 估内存，超过内存预算的
35% 就自动改成 `--decode-every 8`（分片 32 帧、边算边写盘，内存恒定），并在任务日志第一行
写明「内存规划：…」。真被 OOM 杀掉时还会报人话（「进程被内核 OOM 杀掉」）并自动降级
（整条 → 8 → 4）重跑一次，不再静默失败。

实测（594 帧 720×1280 → 2560×1408，turbo，分片 8）：**505 s，峰值显存 11.9 GB，内存平稳，
上一条同参数的整条解码任务 100% 被 OOM 杀掉。**

只有想手动控制时才需要碰 `--decode-every`：

常用参数：

- `--mode turbo|base`：turbo 最快（默认）；base 是另一套权重（v1 权重未下载）。
- `--height/--width`：128 的倍数。
- `--temporal-compression 4|2|1`：1 = 最慢最稳。
- `--max-frames N`：只跑前 N 帧（试参数、切段处理长片）。
- `--decode-every auto|N`：**`auto` = 整条解码，吃内存**（594 帧 2K 要 60 GB，必 OOM）；
  给 4 的倍数可边读边解码、边算边写盘，内存恒定 —— WebUI 会自动选，超长片/大片不用管。
- `--cf`：低频色彩校正。
- `--cache-offload-mode auto|never|always`、`--tiny-decoder-mode auto|serial|parallel`：
  **4K 必须 `always` + `serial`，否则 OOM**（实测默认会爆，23032/24564 MiB）。
- 建议加 `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` 减少碎片（WebUI 已自动加）。

## 实测（RTX 4090 D 24G）

| 任务 | 耗时 | 峰值显存 |
| --- | --- | --- |
| turbo 768×512 · 9 帧 | 29 s（含 ~25 s 加载模型） | — |
| turbo 1280×768 · 93 帧（3.1s 片） | 38 s | ~10 GB |
| turbo 2048×1152 · 93 帧 | 42 s | 11.7 GB |
| turbo 2560×1408 · 93 帧 | 48 s | 15.2 GB |
| turbo 2560×1408 · 594 帧（19.8s 片，**分片 8**） | 505 s | 11.9 GB（整条解码会 OOM 到 60 GB） |
| turbo 3840×2176 · 93 帧（省显存模式） | 97 s | 23.4 GB（贴边） |
| base 768×512 · 9 帧 | 33 s | — |

**推荐上限是 2560×1408**：15 GB，余量充足。4K 靠 offload 硬扛到 23.4 GB，
换一个更复杂的片子仍可能 OOM，建议 4K 时配合 `--max-frames` 分段跑。

## 已装组件

torch 2.6.0+cu124、numpy 2.2.6、opencv-python-headless、imageio(+ffmpeg)、
flash-attn 2.7.4.post1（预编译 wheel，cxx11abi=FALSE）、flashvsr-attn（Triton 稀疏注意力，
`pip install -e`）、gradio 6.31.0、系统自带 ffmpeg/ffprobe。

## 权重清单（共 ~14 GB）

| 文件 | 大小 |
| --- | --- |
| `ckpts/TCDecoder.ckpt` | 0.19 GB |
| `ckpts/Wan2.1_VAE.pth` | 0.51 GB |
| `ckpts/turbo/dit.safetensors` | 5.68 GB |
| `ckpts/turbo/lq_proj_in.safetensors` | 1.15 GB |
| `ckpts/base/dit.safetensors` | 5.68 GB |
| `ckpts/base/lq_proj_in.safetensors` | 1.15 GB |

## 实测网络（2026-11-01）

| 路径 | 速度 |
| --- | --- |
| 公网 HTTP（7860，上/下行） | 0.2–0.32 MB/s |
| SSH/SFTP（控制台端口） | 0.20 MB/s 上行 / 0.13 MB/s 下行 |
| 机房 → HuggingFace（多线程） | 4–15 MB/s |
| 机房 → 一般站点（yt-dlp 直链） | 十几 MB/s |

结论：**大文件不要过浏览器上传**，用 `/up` 分片台或让服务器自己下载。

## 端口 / 路径

| 路径 | 说明 |
| --- | --- |
| `/` | 302 → `/s`，精简版页面 |
| `/s` | 精简版 HTML（`simple.html`） |
| `/up` | 分片续传上传台（2 MB 一片，可断点续） |
| `/api/submit` `/api/status` `/api/cancel` | 精简版用的 JSON 接口 |
| `/api/uploads` `/api/download` `/api/file` | 列表 / 服务端下载 / 取产物 |
| `/api/files` `/thumb` `/api/delete` | 文件库列表 / 缩略图 / 删文件 |
| `/g` | Gradio 版（`gr.mount_gradio_app`，root_path=/g） |

## 已知限制

- 本机房直连 huggingface.co 单连接只有 0.3–0.5 MB/s 且频繁 TLS EOF；
  多连接 + 无限重试可到 4–15 MB/s（用 `/root/build/dl.py`）。
- pip 走清华源；GitHub 直连。
- `v1` 权重（`JunhaoZhuang/FlashVSR-v1.1`）仓库文件 404，未下载，所以 WebUI 只提供 turbo/base。
- WebUI 单任务串行（同时点两次会被拦下并提示），下载任务也占用这个槽位。
- **整条解码（decode-every=auto）在大片/长片上会顶满 57 GB 内存被内核 OOM 杀掉，而且日志里
  没有任何报错**（SIGKILL）。WebUI 已改成自动分片 + 自动降级重试；手动跑命令行时请自己
  加 `--decode-every 8`。
- 平台代理只放行 7860 / 8888 端口，所以上传台挂在 7860 的 `/up` 子路径，别指望 7861。
- 容器时钟是 UTC，输出文件名里的时分秒按 UTC 显示。
