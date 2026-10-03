---
name: xgc-api
description: Manage 仙宫云 / XGC cloud GPU instances through its Open API - check identity and balance, list instances, deploy a GPU container, get its public URL, shut down / boot / destroy it, look up images, order recharge. Use when the user mentions 仙宫云 / Xiangongyun / XGC, asks to 开一台机子/租GPU/部署实例/跑图容器/销毁实例/查余额, or wants to automate anything on api.xiangongyun.com. Every money-spending or destructive command requires explicit user approval.
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