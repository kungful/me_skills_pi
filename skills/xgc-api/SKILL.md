---
name: xgc-api
description: Manage 仙宫云 / XGC cloud GPU instances through its Open API - check identity and balance, list instances, deploy a GPU container, get its public URL, shut down / boot / destroy it, look up images, order recharge. Use when the user mentions 仙宫云 / Xiangongyun / XGC, asks to 开一台机子/租GPU/部署实例/跑图容器/销毁实例/查余额, or wants to automate anything on api.xiangongyun.com. Every money-spending or destructive command requires explicit user approval. **For the end-to-end 跑图 flow (开机→出图→拉图→销毁) use the companion skill `xgc-image-run`; this skill records the canonical image id, GPU and other defaults it depends on, so read the 跑图一条龙 section below before changing anything.**
license: MIT
compatibility: Python 3.9+ (standard library only); outbound HTTPS to api.xiangongyun.com; headless Chrome optional (only for scraping the public image table).
allowed-tools: Bash, Read, Grep
---

# 仙宫云 / XGC OpenAPI

Manage GPU instances from the command line.

```bash
X=~/.pi/agent/skills/xgc-api/scripts/xgc.py
python "$X" --help          # and per command: python "$X" deploy --help
```

Base URL `https://api.xiangongyun.com` · Auth `Authorization: Bearer <访问令牌>` ·
Docs UI https://api-playground.xiangongyun.com

## Hard Rules

0. **NEVER DELETE AN IMAGE. Ever. The user deletes images by hand, in the console, or not at
   all.** This is a standing instruction from the user and it is enforced in code: `api()` refuses
   any request to `/open/image/destroy` (and `/open/image/delete`, `/open/image/remove`,
   `/open/images/destroy`) before it leaves the process, exit code 3. Do not add a flag for it, do
   not bypass it, do not "helpfully" clean up images to save storage quota. If an image really has
   to go, tell the user to delete it themselves at
   https://www.xiangongyun.com/console/user/image and stop. Images cost nothing to keep.
   *Destroying a container instance is a different operation and is still allowed - it does not
   touch any image.* `python "$X" policy` prints this policy.
1. **Money. Deploy/destroy/recharge always need explicit approval in the current turn.**
   The script enforces this twice: it refuses to send the request without `--yes`, and it prints
   the exact JSON body first. Never add `--yes` on your own initiative - show the user the payload
   and wait. If the user said "开一台" earlier in the session but changed the plan, re-confirm.
2. **Billing is per second and unforgiving.** Billing starts when the instance reaches `运行中`
   and stops only when it is destroyed. `shutdown` keeps billing; `shutdown_release_gpu` stops GPU
   billing but the system disk keeps billing ¥0.00003/GB/h. Balance is charged *after* use: going
   negative auto-destroys the container, unrecoverably.
3. **Start every session with `instances --running`.** Anything running is billing right now.
   Report it to the user before doing anything else, and offer to destroy leftovers.
4. **Always finish what you start.** If you deploy, you owe the user a `destroy` afterwards
   (or at minimum a loud warning if they want to keep it). Never leave a machine running
   "for later".
5. **Token hygiene.** The token equals full account control. Read it from `~/.xgc_token` or
   `$XGC_TOKEN`; never echo it, never paste it into a command that logs, never commit it.
   `xgc.py token` prints only a masked fingerprint. If a token leaks into the transcript or a
   repo, tell the user to rotate it at
   https://www.xiangongyun.com/console/user/accesstoken.
6. **Do not print secrets from responses.** `GET /open/instances` returns `password`,
   `ssh_port`, `jupyter_token`, `xgcos_token`. Filter them out before showing anything.
7. **One write at a time, and report the raw response.** Never retry a deploy blindly - a retry
   can double-charge. If a call fails, show the error and ask.
8. **Stay in scope.** Only this API. Do not touch the console UI, do not buy 包日/包周/包月 plans,
   do not change account settings or payment methods.

## Setup

```bash
echo -n '<访问令牌>' > ~/.xgc_token     # from the console's 访问令牌 page
python "$X" token                       # verifies it: prints a masked fingerprint + auth check
```

Read-only commands fail cleanly with `code=1000 msg=访问令牌为空` when the token is missing.

## Read-only commands (always safe)

```bash
python "$X" whoami                  # GET /open/whoami
python "$X" balance                 # GET /open/balance  (warns when <= 0)
python "$X" instances               # table: id / status / name / gpu / ¥per hour
python "$X" instances --running     # only the ones billing right now
python "$X" instance <id>           # full detail
python "$X" images                  # GET /open/images  (your private images)
python "$X" image <id>
python "$X" docs-images             # public image table, scraped from the docs (no token)
python "$X" url <instance_id> [port]
python "$X" history                 # local log of every write this tool sent
```

Add `--json` to any of them for raw output.

`images` / `image <id>` **list** images only. There is deliberately no way to delete one from this
tool (see Hard Rule 0); `python "$X" policy` shows the blocklist.

## Write commands (need `--yes`)

```bash
# deploy - SPENDS MONEY
python "$X" deploy --gpu "NVIDIA GeForce RTX 4090" --count 1 \
    --image <image_id> --image-type public --dry-run     # 1. inspect the payload
# show the user the payload, get approval, then:
python "$X" deploy --gpu "NVIDIA GeForce RTX 4090" --count 1 \
    --image <image_id> --image-type public --yes

python "$X" shutdown <id> --yes                  # stop, keep GPU (STILL BILLS)
python "$X" shutdown <id> --release-gpu --yes    # stop, free GPU (disk still bills)
python "$X" shutdown <id> --and-destroy --yes    # stop and delete
python "$X" boot <id> --yes                     # start again
python "$X" destroy <id> --yes                  # delete; data is gone
python "$X" saveimage <id> --name my-img --yes
python "$X" recharge <amount> alipay --yes       # real money
```

There is **no** image-delete command and none may be added (Hard Rule 0).

`deploy` flags: `--gpu` (`NVIDIA GeForce RTX 4090` / `... 4090 D` / `... 4090 D 48G`),
`--count` 0-8, `--datacenter` (default 1), `--image`, `--image-type public|community|private`,
`--storage` + `--storage-path`, `--ssh-key`, `--name`, `--disk-size` (bytes).

## Canonical workflow

```bash
python "$X" instances --running        # 1. anything billing right now?
python "$X" token && python "$X" balance
python "$X" docs-images                # 2. pick an image id (or the user's own: images)
# 3. show this payload to the user and WAIT for approval:
python "$X" deploy --gpu "NVIDIA GeForce RTX 4090" --count 1 --image <id> --dry-run
python "$X" deploy ... --yes           # 4. only after explicit approval
python "$X" instances                  # 5. read the new id / status / price_per_hour
python "$X" url <id> 8188              # 6. ComfyUI -> https://<id>-8188.container.x-gpu.com
# ... user runs their work ...
python "$X" destroy <id> --yes         # 7. ALWAYS finish: stop the meter
```

## 跑图一条龙（默认参数 / canonical defaults）

用户要跑图（出图、生图、用 ComfyUI / Krea2 / 本地模型出图）时，**不要手搓上面这套流程** ——
用配套技能 **`xgc-image-run`**，它把「开机 → 连进容器 → 出图 → 拉回本地 → 立刻销毁」
封成一条命令，`try/finally` 保证异常也销毁：

```bash
S=~/.pi/agent/skills/xgc-image-run/scripts/xgc_run_image.py
python "$S" --status                       # 先看有没有在烧钱
python "$S" --prompt "..." --dry-run       # 演练
python "$S" --prompt "..." --yes           # 真跑
```

**这套默认值是本技能的权威来源，改动请改这里**（同时同步 `~/.xgc_defaults.json`）。
`xgc-image-run` 的脚本读 `~/.xgc_defaults.json`，读不到就用自己内置的兜底值：

| 项 | 值 | 备注 |
|---|---|---|
| 跑图镜像 | `f0cbf8c7-96c7-4010-a645-1898927c33ea` | 名字「agent调用此镜像跑图」。49.1 GB。用户手工维护的**唯一**跑图镜像，见下方警告 |
| 默认 GPU | `NVIDIA GeForce RTX 4090 D` | ¥1.59/时 |
| SSH 私钥 | `~/.ssh/piwebui.pem` | 公钥已塞进上面那张镜像的 `authorized_keys`；不通时脚本回退容器密码 |
| ComfyUI 端口 | `8188` | 已公网暴露 |
| 文生图工作流 | `/root/ComfyUI/user/default/workflows/Krea2_Turbo_文生图.json` | 同目录还有 `Krea2_Turbo_图生图.json`、`Krea2_Turbo_参考图生成.json` |
| 模型栈 | Krea2 Turbo fp8 + qwen3vl_4b(type=krea2) + qwen_image_vae | steps 8 / cfg 1.0，**不要**加 FluxGuidance |
| 一张图耗时 | 1024² 约 16 秒；1536×1024 约 30~60 秒 | 加开机+模型加载，整个流程 2~4 分钟 < ¥0.1 |

**为什么强调「立刻销毁」**：按秒计费，跑一张不到一毛钱，但忘记销毁挂一晚上是 **¥38**。
所以 `xgc-image-run` 把销毁放在 `finally` 里，不是放在流程末尾。

**镜像卫生（重要）**：用户会自己在控制台整理镜像 —— 他曾经把新存的镜像内容**覆盖回**
`f0cbf8c7` 并删掉中间产物。所以：

- `f0cbf8c7` 是**可变的**，内容会随用户维护而变，不要假设它等同于某个历史快照；
- 任何写死镜像 ID 的地方都可能过期。镜像不存在时不要猜，先 `xgc.py images` 列出来问用户；
- **永远不要删镜像**（Hard Rule 0）。用户手工删了一个临时镜像，那是平台自己的生命周期，
  不构成「可以删镜像」的先例。

## Reaching the app inside the container

```
public      https://{实例ID}-{端口}.container.x-gpu.com
in-network  http://{实例ID}-{端口}.c.x-gpu.com      (from inside the container)
loopback    http://127.0.0.1:{端口}
```
Common ports: ComfyUI `8188`, SD WebUI `7860`, Jupyter `8888`, SSH `22`. Confirm with
`xgc.py instance <id> --json` (it returns `jupyter_url`, `ssh_port`, `ssh_user`, ...).
The instance ID is also the env var `XGC_INSTANCE_ID` inside the container.

For 跑图 (image generation) the usual path is a ComfyUI community image, expose port 8188, then
drive it over that URL. Pair this skill with `web-browse` if you need to read a UI in the browser.

## Pricing model (from the site's 计费方式 page)

- 按量: per-second billing from `运行中` until destroyed; charged hourly in arrears.
- 包日/包周/包月: prepaid, auto-destroyed at expiry, cannot be recovered (100 GB data disk included).
- After GPU release: system disk keeps billing **¥0.00003/GB/h**.
- Exact GPU rates are only visible in the logged-in console - ask the user, do not guess.

## Failure modes

| Output | Meaning / action |
|---|---|
| `code=1000 msg=访问令牌为空` | token missing or not loaded -> setup above |
| `code=1000 msg=未找到访问令牌` | token invalid -> regenerate it |
| `instances` empty but the console shows one | wrong account/token |
| deploy succeeds, instance stuck not-运行中 | provisioning; poll `instance <id>` - **it starts billing once 运行中** |
| overdraw / auto-destroy | balance went negative; only a new deploy fixes it |