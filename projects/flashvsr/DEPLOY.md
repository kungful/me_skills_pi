# 部署手册

目标：任何一台电脑，从零把 FlashVSR+ 视频超分实例跑起来；或者接着改代码。

全文命令都在 **bash** 里写的（Windows 用 Git Bash / WSL 都一样）。

---

## 0. 前置条件

### 0.1 账号侧（一次性）

1. 注册 [仙宫云](https://www.xiangongyun.com/)，充值（跑一条几十秒的片子大约 ¥0.02~0.3，
   充 ¥10 能玩很久）。
2. 确认有 **RTX 4090 D** 的 GPU 配额（新号可能需要实名/排队）。
3. 拿**访问令牌**：<https://www.xiangongyun.com/console/user/accesstoken>

```bash
echo -n '<访问令牌>' > ~/.xgc_token     # 别提交进 git，别贴进聊天
```

### 0.2 本机侧（只有"部署/改代码"才需要，纯使用不需要）

| 需求 | 说明 |
| --- | --- |
| Python 3.9+ | 跑脚本 |
| `pip install paramiko` | `xr.py` 用密码 SSH 进容器（密钥登录在这张镜像上不可靠，见坑 #6） |
| `curl` | 手工调 API / 验收 |
| OpenSSH 客户端 | 可选，`scp` 传大文件 |

`xgc.py`（仙宫云 Open API 的薄封装）在本仓库的 [`../../skills/xgc-api/scripts/xgc.py`](../../skills/xgc-api/scripts/xgc.py)。
如果只 clone 了 `projects/flashvsr`，也可以完全不用它——下面每个操作都给了**裸 curl 等价命令**。

```bash
# 统一用这个变量，后面命令都靠它
X=~/.pi/agent/skills/xgc-api/scripts/xgc.py      # 或你 clone 下来的路径
TOK=$(cat ~/.xgc_token)
API=https://api.xiangongyun.com
```

---

## 1. 最快路径：直接开一台用现成镜像

镜像里已经装好 ComfyUI 无关的完整环境：`FlashVSR_Plus` 代码 + 14 GB 权重 +
torch 2.6.0+cu124 + flash-attn 2.7.4.post1 + triton 稀疏注意力算子 + WebUI（开机自启）。

### 1.1 当前能用的镜像

| 镜像 id | 保存时间 | 内容 |
| --- | --- | --- |
| **`d6895c78-66cb-455c-8a4e-82cf77038593`** | 2026-11-01 11:35 | **v5：修了长片/大片 OOM 静默失败（自动分片解码）** |
| `4fd35473-415a-47eb-ac2b-d917d9da0396` | 2026-11-01 10:56 | v4：视频超分 WebUI 初版 |
| `937aa22e-a471-4802-a366-655336e6bfb1` | 2026-11-01 10:34 | 中间版本 |
| `0b8b0a19-f4b8-4c23-b5e4-58eb7bacee1d` | 2026-11-01 09:35 | v2：抗断连 WebUI |
| `ed73b8ff-1e5c-4f39-9d80-e10ac79bef82` | 2026-10-31 | v1：裸环境 |

⚠️ **文件库（缩略图/预览/删除）、`resolve_preset` 修复目前还没进镜像**，
只存在于实例 `15nfp4tydm76nnt0` 上，见 [§5 保存镜像](#5-保存新镜像版本管理)。
最新版镜像 id 永远记在 [CHANGELOG.md](CHANGELOG.md)。

### 1.2 开机器

```bash
python "$X" deploy \
  --gpu "NVIDIA GeForce RTX 4090 D" --count 1 \
  --image d6895c78-66cb-455c-8a4e-82cf77038593 --image-type private \
  --datacenter 1 --yes
```

裸 API 等价：

```bash
curl -sS -X POST "$API/open/instance/deploy" \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"gpu_model":"NVIDIA GeForce RTX 4090 D","gpu_count":1,"data_center_id":1,
       "image":"d6895c78-66cb-455c-8a4e-82cf77038593","image_type":"private"}'
```

⚠️ **`--image-type private`**：自己保存的镜像必须写 `private`，写 `public` 会报找不到镜像。

### 1.3 等它起来（这段时间不花钱）

```bash
# 轮询到 status = running；首次铺镜像可能要 2~3 分钟，别中断
watch -n 5 'python "$X" instance <实例id> | grep -E "\"(status|ssh_domain|ssh_port|price_per_hour)\""'
```

拿到 `running` 之后，**计费才开始**。WebUI 还要再等 ~40 s（容器自启脚本）：

```bash
B=https://<实例id>-7860.container.x-gpu.com
curl -sS -o /dev/null -w '%{http_code}\n' --max-time 10 "$B/s"      # 等到 200
```

### 1.4 用

浏览器打开 `$B/s`（精简版），或 `$B/g`（Gradio 版）。

- 传片子：**别用内置上传**（公网代理只有 ~0.3 MB/s 且会掐长请求）。
  用 `$B/up`（2 MB 分片续传）或 `scp` 到 `/root/uploads`，或者在「链接」页签里让服务器自己下。
- 跑完在「4. 文件库」里看缩略图、在线播（支持 Range，可拖进度）、下载、删除。

### 1.5 收工：关机停止计费

```bash
python "$X" shutdown <实例id> --release-gpu --yes     # GPU 停计费，磁盘保留（几毛钱/天）
# 彻底不要了：
python "$X" destroy <实例id> --yes                    # 数据全丢
```

裸 API 等价：

```bash
curl -sS -X POST "$API/open/instance/shutdown_release_gpu" \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d '{"id":"<实例id>"}'
```

⚠️ **按量计费实例不要用 `/open/instance/shutdown`**（那是预付费接口）：它会返回
`按量计费实例不支持本接口`，而如果它"成功"了也仍然按原价计费。必须用 `shutdown_release_gpu`。

---

## 2. 换一台电脑 / 换一个账号

没有"迁移"这回事——所有状态都在云上。新电脑只要：

1. 按 §0 配好 `~/.xgc_token` 和 `paramiko`；
2. 按 §1 用镜像 id 开一台（镜像在你账号里是**私有**的：
   别人账号看不到你的镜像，自己在新账号里重建见 §4）；
3. 浏览器打开新地址。

**唯一会遇到差异的是镜像权限**：私有镜像只能同账号用。要给别人用，有两条路：

- 让对方自己按 §4 从零构建（40 分钟，一次性）；
- 或把镜像设为公开（控制台 → 镜像 → 可见性）。公开前先确认里面没有你的数据/密钥：
  容器里只有 `/root/uploads` 和 `/root/outputs` 是用户内容，存镜像前建议清空。

---

## 3. 改代码热更新（另一台电脑接着干）

WebUI 的全部代码在 `app/`（容器里对应 `/root/app/`）。改完不需要重启机器，
只要把文件推上去、杀掉进程让自启脚本拉起来（约 20 s）。

### 3.1 一次性准备

```bash
git clone <repo-url> flashvsr-repo && cd flashvsr-repo/projects/flashvsr
pip install paramiko

export XGC_INST=<实例id>          # xr.py 默认连的实例，可用环境变量覆盖
ls app/ scripts/
```

`scripts/xr.py` 走 **SSH + 容器密码**：密码从 `GET /open/instances` 里取（`password` 字段），
不落盘不打印。所以只需要令牌，不需要任何 SSH 密钥配置。

```bash
python scripts/xr.py run 'nvidia-smi --query-gpu=memory.used --format=csv,noheader'
python scripts/xr.py run 'tail -20 /root/logs/webui.log'
python scripts/xr.py log webui 40         # tail 日志
python scripts/xr.py get /root/outputs/xxx.mp4 ./xxx.mp4
```

### 3.2 改 → 推 → 生效

```bash
# 1) 改本地 app/app.py 或 app/simple.html（改完双击本地看不了，得推）

# 2) 推上去（push.py 会自动把 CRLF 换成 LF，Windows 上必须有这一步）
python scripts/push.py

# 3) 杀掉 WebUI，自启脚本 5 s 后自动拉新的
python scripts/xr.py run "for p in \$(pgrep -f 'app[.]py'); do kill \$p; done"
sleep 22

# 4) 验收
python scripts/xr.py run "curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:7860/s"
```

`push.py` 里维护了一张「本地 → 容器」路径表，加文件要同步加一行。
想跳过 push.py、只传一个文件也可以：

```bash
python scripts/xr.py put app/simple.html /root/app/simple.html
```

### 3.3 自启是怎么组织的

| 位置 | 作用 |
| --- | --- |
| `/scripts/start.d/flashvsr-webui.sh` | 容器 PID 1 拉起，`while true` 常驻；用 `flock /var/lock/flashvsr-webui.lock` 保证只有一个 |
| 内容来源 | 本仓库 `scripts/flashvsr-webui.sh` |
| 日志 | `/root/logs/webui.log`（自启记录 + 应用输出） |
| 手动重启 | `bash /root/build/restart_webui.sh`（只杀 comm=python 的进程，不会误杀 SSH 会话） |

所以"杀进程"就是"重启"，**不要**手工 `nohup python app.py &`——会撞端口/抢锁。

### 3.4 端到端自测（改完必跑）

```bash
B=http://127.0.0.1:7860

# 页面 + 接口
curl -sS -o /dev/null -w 'page %{http_code}\n' $B/s
curl -sS "$B/api/files?which=out" | head -c 300

# 提交一个小任务（只跑 24 帧，约 40 s，¥0.02）
curl -sS -X POST -H 'Content-Type: application/json' \
  -d '{"src":"/root/uploads/34343.mp4","preset":"896x512","mode":"turbo","max_frames":24}' \
  $B/api/submit
sleep 45; curl -sS $B/api/status | head -c 400

# 图片必须被拒（这是"只跑一帧"那个 bug 的回归用例）
curl -sS -X POST -H 'Content-Type: application/json' \
  -d '{"src":"/root/uploads/thumb.jpg","preset":"896x512"}' $B/api/submit
# 期望：{"ok":false,"msg":"⚠️ 这是图片（.jpg）..."}
```

---

## 4. 从零构建镜像（没有现成镜像时）

前提：一台已经开好的 GPU 实例（用公共镜像如 `pytorch:2.x-cuda12` 起，
或者随便一个带 CUDA 的镜像即可），SSH 能进。整程约 40 分钟（大部分在下载 14 GB 权重）。

### 4.1 上传构建脚本+代码

```bash
export XGC_INST=<实例id>
python scripts/xr.py run 'mkdir -p /root/build /root/app /root/logs /root/outputs /root/uploads /root/fv/ckpts'
python scripts/push.py           # 一把推全部：构建脚本 + WebUI 代码（自动转 LF）
```

`push.py` 同时兼容两种目录布局（扇平的本地开发目录、本仓库的 `app/` + `scripts/`），
按文件名自动找。

### 4.2 stage 1：依赖（约 10 分钟，含 torch 2.7 GB + flash-attn 编译好的 wheel）

```bash
python scripts/xr.py run 'bash /root/build/01_env.sh 2>&1 | tail -40'
```

它做的事：clone `FlashVSR_Plus` → `torch==2.6.0`(cu124) → `flash-attn 2.7.4.post1`
预编译 wheel（按 `_GLIBCXX_USE_CXX11_ABI` 自动选 cxx11abi 变体）→ `requirements.txt` →
`pip install -e .` → `pip install -e operators/flashvsr_attn`（Triton 稀疏注意力）→ `gradio`。

### 4.3 stage 2：权重（约 20 分钟，14 GB）

机房到 HuggingFace 单连接只有 0.3~0.5 MB/s 且频繁 TLS EOF，
`02_weights.sh`（wget 单连接，走 hf-mirror）经常啃不完，实际用的是
**多连接 + 无限重试** 的 `04_weights.sh`：

```bash
python scripts/xr.py run 'WITH_BASE=1 bash /root/build/04_weights.sh 2>&1 | tail -20'
# 期望最后一行 ### WEIGHTS_ALL_DONE，且 /root/fv/ckpts 约 14 GB
python scripts/xr.py run 'du -sh /root/fv/ckpts/*; find /root/fv/ckpts -type f -size -1k'
```

| 文件 | 大小 |
| --- | --- |
| `TCDecoder.ckpt` | 0.19 GB |
| `Wan2.1_VAE.pth` | 0.51 GB |
| `turbo/dit.safetensors` | 5.68 GB |
| `turbo/lq_proj_in.safetensors` | 1.15 GB |
| `base/dit.safetensors` | 5.68 GB（base 预设才用，可不下） |
| `base/lq_proj_in.safetensors` | 1.15 GB |

`FlashVSR_Plus/ckpts` 是软链到 `/root/fv/ckpts` 的（平台对象存储用软链指向
`/.xgcos/.links/...`，**别用 `cp` 破坏它**，要动就用 `ln -sfn`）。

`v1` 权重（`JunhaoZhuang/FlashVSR-v1.1`）仓库文件 404，下不到，WebUI 因此只提供 turbo/base。

### 4.4 stage 3：冒烟测试

```bash
python scripts/xr.py run 'bash /root/build/03_smoke.sh 2>&1 | tail -30'
```

跑一条 turbo 小尺寸 + 一条 1080p，记录显存峰值。参考值（RTX 4090 D 24G）：

| 任务 | 耗时 | 峰值显存 |
| --- | --- | --- |
| turbo 768×512 · 9 帧 | 29 s（含 ~25 s 加载模型） | — |
| turbo 2048×1152 · 93 帧 | 42 s | 11.7 GB |
| turbo 2560×1408 · 93 帧 | 48 s | 15.2 GB |
| turbo 3840×2176 · 93 帧（省显存模式） | 97 s | 23.4 GB（贴边） |

### 4.5 装 WebUI + 自启

```bash
# 代码
python scripts/push.py                      # 全部脚本 + WebUI 代码

# 自启钩子（平台约定：/scripts/start.d/*.sh 开机执行）
python scripts/xr.py run 'mkdir -p /scripts/start.d'
python scripts/xr.py put scripts/flashvsr-webui.sh /scripts/start.d/flashvsr-webui.sh
python scripts/xr.py run 'chmod +x /scripts/start.d/flashvsr-webui.sh; cd /root/app && nohup setsid /root/miniconda3/bin/python /root/app/app.py >> /root/logs/webui.log 2>&1 & sleep 20; curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:7860/s'
```

WebUI 端口写死 **7860**（平台只放行 7860 / 8888，改端口公网就进不去）。

### 4.6 保存成镜像

见 §5。**保存前先关机**，平台要求。

---

## 5. 保存新镜像（版本管理）

改完代码、验收通过后：

```bash
# 1) 必须先关机（释放 GPU 也顺便停止计费）
python "$X" shutdown <实例id> --release-gpu --yes
#    等 status 从 shutdown_backing_up 变成 shutdown（约 30~60 s）

# 2) 保存镜像
python "$X" saveimage <实例id> \
  --name "FlashVSR+ 视频超分 v6" \
  --description "v6: 文件库(缩略图/预览/删除) + 图片拒绝 + preset 修复" --yes

# 3) 记下新 image id
python "$X" images | grep -i <新id>
```

裸 API：

```bash
curl -sS -X POST "$API/open/instance/saveimage" \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"id":"<实例id>","name":"FlashVSR+ 视频超分 v6","description":"..."}'
```

三个坑：

1. **不关机就保存** → `code=1000 请关机后执行储存镜像操作`。
2. **刚关机马上保存** → `code=1000 该实例暂时无法进行操作`，等 30~60 s 到 `status=shutdown`。
3. **镜像显示名不可改**：`/open/image/*` 的改名接口全 405，控制台也按实例名生成名字。
   API 里 `name` 字段回读出来常常就是 uuid，**认 id 不认名字**。

保存完别忘了把新 id 写进 [CHANGELOG.md](CHANGELOG.md) 和 [§1.1](#11-当前能用的镜像)。

---

## 6. 验收清单（部署完逐条打勾）

```bash
B=https://<实例id>-7860.container.x-gpu.com
```

- [ ] `GET $B/s` → 200（精简版页面，约 20 KB）
- [ ] `GET $B/g` → 200/307（Gradio 版）
- [ ] `GET $B/api/status` → `{"status":"idle",...}`
- [ ] `GET $B/api/files?which=out` → JSON，`dir` 是 `/root/outputs`
- [ ] `GET $B/thumb?which=out&name=<某个mp4>` → 200，几 KB 的 jpeg
- [ ] `GET $B/api/file?which=out&name=<某个mp4>` 带 `Range: bytes=0-99` → **206**
- [ ] 传一个短视频（几秒即可）跑完 → 文件库里出现缩略图、能播、能下载
- [ ] 选个 `.jpg` 提交 → 被拒（不再产出"只有一帧"的废片）
- [ ] `nvidia-smi` 显存释放干净（没有残留 python 进程）
- [ ] 收工：`shutdown --release-gpu` 后 `xgc.py instance <id>` → `status=shutdown`

---

## 7. 坑清单（都是真踩过的）

| # | 现象 | 原因 / 处理 |
| --- | --- | --- |
| 1 | 任务显示「失败」，日志停在 `● Running inference...`，**一行报错都没有** | 被内核 OOM 杀掉（SIGKILL 没有 traceback）。查 `cat /sys/fs/cgroup/memory.events`（`oom_kill` 涨了就是它）和 `memory.peak`。根因是 `--decode-every auto` 整条解码吃掉 ~60 GB RAM。WebUI 已改成自动分片 + 自动降级重试；手工跑命令行要自己加 `--decode-every 8` |
| 2 | 出图/出片只有一帧 | 源文件其实是图片。**ffprobe 会把 .jpg 当成 1 帧 mjpeg 流**（宽高/时长都有），必须查扩展名 + 帧数 + 时长三重判定。已修（`video_guard`） |
| 3 | 选了 2560×1408 但产物尺寸不是它 | 精简版传短名 `2560x1408`，而 `PRESETS` 只有中文键 → 静默回退"自动 2 倍"。已修（`resolve_preset`） |
| 4 | Gradio 版弹 `Connection to the server was lost` / `Unexpected end of JSON input` | 平台反向代理会掐 SSE 长连接和大 multipart。用 `/s` 精简版（短 JSON + 重试）和 `/up` 分片上传 |
| 5 | 浏览器上传几十 MB 以上必失败 | 公网代理 ~0.3 MB/s 且掐长请求。用 `/up` 分片续传，或 `scp` 到 `/root/uploads`，或让服务器自己下（15 MB/s） |
| 6 | 密钥登录容器失败 | 容器每次开机会用平台 `ssh_key` 配置**重置** `authorized_keys`，手写进去的白写。用 `xr.py` 的密码登录（密码来自 API），或 deploy 时带 `--ssh-key` |
| 7 | `shutdown` 报「按量计费实例不支持本接口」 | 用 `shutdown_release_gpu`，见 §1.5 |
| 8 | `saveimage` 报「请关机」 | 先关机再存，见 §5 |
| 9 | 部署后 `instances` 列表里全是 `?` | `xgc.py instances` 的表格字段和当前 API 返回不一致（脚本待修）；用 `xgc.py instance <id>` 或裸 API 看详情 |
| 10 | 想开 7861 端口失败 | 平台只放行 7860 / 8888。所有子功能（`/up`、`/g`、`/api/*`）都挂在 7860 的路径下 |
| 11 | 端口 7860 被占 / 起不来 | 先用 `flock` 的自启脚本，别手工 `nohup`。`ss -ltnp \| grep 7860` 查占用，`bash /root/build/restart_webui.sh` 重启 |
| 12 | 显存被幽灵进程占着（`nvidia-smi` 有占用但没有进程） | 上次被 SIGKILL 的进程没释放。杀掉残留 `pkill -9 -f inference.run_stream`，必要时重启实例 |
| 13 | 4K 爆显存（23032/24564 MiB） | 4K 必须 `--cache-offload-mode always --tiny-decoder-mode serial`，WebUI 自动模式下 ≥6 MP 会自己加 |
| 14 | 长片很慢 | 8 分钟一条 20 秒的 2K 片是正常的（594 帧 × 2.6 s/帧级）。要快就降分辨率、`--max-frames` 分段、或只处理关键片段 |
| 15 | 容器时间是 UTC | 输出文件名里的时分秒按 UTC，日志也是（`webui.log` 里 start.d 那行例外，用 `TZ=Asia/Shanghai`） |
