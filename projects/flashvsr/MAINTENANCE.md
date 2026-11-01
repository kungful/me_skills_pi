# 运维手册

日常会用到的一切：接口、路径、日志、排障、成本。部署步骤看 [DEPLOY.md](DEPLOY.md)。

---

## 1. 容器内速查表

| 东西 | 路径 |
| --- | --- |
| WebUI 代码 | `/root/app/app.py`（+ `simple.html` / `uploader.py` / `dl.py`） |
| WebUI 日志 | `/root/logs/webui.log` |
| 单次任务日志 | `/root/logs/job_<月日-时分秒>.log`（含实际命令行 + 完整输出） |
| 放大结果 | `/root/outputs/`（WebUI「文件库 → 放大结果」） |
| 上传的原片 | `/root/uploads/`（WebUI「文件库 → 上传的原片」） |
| 缩略图缓存 | `/root/thumbs/`（md5(路径+mtime+size).jpg，>5000 张自动清旧的） |
| 自启钩子 | `/scripts/start.d/flashvsr-webui.sh`（flock 单实例） |
| 构建脚本 | `/root/build/01_env.sh` … `04_weights.sh`、`restart_webui.sh` |
| FlashVSR 仓库 | `/root/FlashVSR_Plus` |
| 模型权重 | `/root/fv/ckpts`（`FlashVSR_Plus/ckpts` 是软链） |
| Python | `/root/miniconda3/bin/python`（conda base，torch 2.6.0+cu124） |
| 端口 | **7860**（WebUI，写死）、8888（Jupyter，平台放行） |

## 2. HTTP 接口

所有接口都是**短请求**（无 SSE / 无长连接），因为平台反向代理会掐长连接。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/s` | 精简版页面（默认，`/` 302 → `/s`） |
| GET | `/g` | Gradio 版（`gr.mount_gradio_app`，root_path=/g） |
| GET | `/up` | 分片续传上传台 |
| GET | `/api/status` | 当前任务状态：`{status,label,elapsed,pct,log,out,info,plan,tries}` |
| POST | `/api/submit` | 提交：`{src,preset,mode,mem,tcomp,max_frames,decode_every,colorfix,vpreset}` |
| POST | `/api/cancel` | 取消（`killpg(SIGINT)` 整组，显存立刻释放） |
| POST | `/api/download` | 服务器下载：`{url,maxh}`（`yt-dlp` / 多连接 `dl.py`） |
| GET | `/api/files?which=out\|up` | 文件库：`{dir,files:[{name,size,mtime,kind,which,w,h,dur,fps,frames,url,dl,thumb}]}` |
| GET | `/thumb?which=&name=` | 缩略图 jpeg（420×420 内等比，缓存 7 天） |
| GET | `/api/file?which=&name=[&dl=1]` | 原文件，**支持 Range（206）**；`dl=1` 强制下载 |
| POST | `/api/delete` | 删文件 `{which,name}`（含缩略图缓存，正在被任务使用的拒删） |
| GET/PUT | `/up/status` `/up/chunk` | 分片上传断点查询 / 写分片 |
| GET | `/api/uploads` | 老接口，列 `/root/uploads`（已带 `kind`） |

`preset` 三种写法都认：中文标签（`2K 级 2560×1408（~15 GB，推荐上限）`）、短名
（`2560x1408`）、`auto`。宽高必须都是 128 的倍数。

## 3. 参数与显存

| 参数 | 取值 | 说明 |
| --- | --- | --- |
| `--mode` | `turbo` / `base` | turbo 最快（官方推荐）；base 是另一套权重 |
| `--height/--width` | 128 的倍数 | 没有 1920×1080；常用 `2048×1152` / `2560×1408` / `3840×2176` / `1280×768` |
| `--temporal-compression` | 4 / 2 / 1 | 1 最慢最稳 |
| `--decode-every` | `auto` / 4 的倍数 | **`auto` = 整条解码，吃内存**；WebUI 自动选 |
| `--max-frames` | N | 只跑前 N 帧（试参数、切段） |
| `--cf` | 开关 | 低频色彩校正 |
| `--cache-offload-mode` | `auto`/`never`/`always` | 4K 必须 `always` |
| `--tiny-decoder-mode` | `auto`/`serial`/`parallel` | 4K 必须 `serial` |

自动决策（`app.py` 的 `plan_decode_every` / `mem_flags`）：

- 内存估算 = `帧数 × 宽 × 高 × 3 × 4 字节 × 2.5`；超过内存预算 35% → 自动 `--decode-every 8`
  （每次只算 32 帧，边算边写盘，内存恒定）。这行结论会写进任务日志第一行「内存规划：…」。
- 显存：自动模式下 ≥3 MP（非分片）或 ≥6 MP（分片）才开 `always + serial` offload。

## 4. 排障

### 4.1 任务「失败」但没有任何报错

```bash
cat /sys/fs/cgroup/memory.events     # oom_kill 涨了 = 被内核杀
cat /sys/fs/cgroup/memory.peak       # 60129550336 = 顶满 57 GB
tail -30 /root/logs/job_*.log
```

SIGKILL 不会留 traceback，日志停在 `● Running inference...` 就是它。
手工跑命令行时自己加 `--decode-every 8`。

### 4.2 显存被幽灵占用（`nvidia-smi` 有占用但没进程）

```bash
pkill -9 -f inference.run_stream; sleep 3
nvidia-smi --query-gpu=memory.used --format=csv,noheader     # 应该回到 1 MiB
```

还不行就重启实例（`shutdown_release_gpu` + `boot`，实例 id 不变，镜像里的东西都在）。

### 4.3 WebUI 起不来 / 页面 502

```bash
tail -50 /root/logs/webui.log
ss -ltnp | grep 7860
python -c "import ast;ast.parse(open('/root/app/app.py').read())"   # 语法错会直接崩
bash /root/build/restart_webui.sh
```

自启脚本是 `while true` 常驻：只要 `kill` 掉 `app.py`，5 s 后自动拉起新的。

### 4.4 网络类毛病

| 症状 | 判断 | 处理 |
| --- | --- | --- |
| 页面白屏 / 转圈很久 | 公网代理 0.2~0.3 MB/s | 正常，等；大文件走 `/up` 或 `scp` |
| `Unexpected end of JSON input` | Gradio 长请求被掐 | 用 `/s` 精简版 |
| `Connection to the server was lost` | SSE 被掐 | 同上 |
| 上传中断 | 单请求超时 | `/up` 2 MB 分片会自动续传，刷新页面也能续 |

### 4.5 出片只有一帧

源文件其实是图片。`ffprobe` 会把 `.jpg` 当成 1 帧 mjpeg 流（宽高/时长都有），
所以判定必须看扩展名 + 帧数 + 时长。已由 `video_guard()` 拦住，回归用例在
[DEPLOY.md §3.4](DEPLOY.md#34-端到端自测改完必跑)。

## 5. 成本实测（RTX 4090 D，¥1.59/h）

**只在实例达到「运行中」之后按秒计费**；部署、铺 33.6 GB 镜像、开机等待全免费。
不要用壁钟乘单价算钱（会虚报 20%+），要看余额差额。

单张 1536×1024（计费窗口 56 s）：

| 阶段 | 耗时 | 折算 | 占比 |
| --- | --- | --- | --- |
| SSH 就绪 | ~15 s | ¥0.0066 | 27% |
| WebUI/模型就绪 | 5 s | ¥0.0022 | 9% |
| GPU 实际出图 | 21.1 s | ¥0.0093 | 38% |
| 下载 2.2 MB | ~5 s | ¥0.0022 | 9% |
| 销毁 | ~10 s | ¥0.0044 | 18% |
| **合计** | **56 s** | **¥0.0247** | 100% |

结论：**固定开销占大头（62%），出图只占 38%** —— 换更快的卡没有意义（贵卡的开机/就绪/销毁
也按贵价计费，实测快 2 倍贵 2 倍反而贵 62%）；**批量才是主战场**（一次开机跑 8 张，单张降到 ¥0.0113）。

| 场景 | 花费 |
| --- | --- |
| 一张 1536×1024 | ¥0.0247 |
| 一条 20 s 片子 → 2K（594 帧，505 s 窗口） | ≈ ¥0.30 |
| 忘记关机挂一天 | ¥38 |
| 关机但保留 GPU（错误姿势） | 照原价 ¥1.59/h 继续烧 |
| 关机释放 GPU | 只剩磁盘 ¥0.00003/GB/h |

## 6. 备份与恢复

- **镜像就是备份**：`shutdown --release-gpu` 之后所有改动都还在（含 `/root/uploads`、
  `/root/outputs`、`/root/thumbs`）。所以"关掉省钱"和"保留现场"不冲突。
- **改代码后没存镜像** → 实例一旦 `destroy` 就全丢。存镜像流程见 [DEPLOY.md §5](DEPLOY.md#5-保存新镜像版本管理)。
- 权重 `/root/fv/ckpts` 是平台对象存储软链（`/.xgcos/.links/...`）。**不要 `cp` 覆盖**，
  重建软链用 `ln -sfn <目标> <文件>`。
- 本地源码本仓库就是权威版本：`projects/flashvsr/app/`。容器里的改动记得回传：

```bash
python scripts/xr.py get /root/app/app.py app/app.py
python scripts/xr.py get /root/app/simple.html app/simple.html
```
