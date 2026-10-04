---
name: xgc-image-run
description: 仙宫云 GPU 跑图一条龙 —— 自动开机 → 自动连进容器 → 跑 ComfyUI 出图 → 把图拉回本地 → 立刻销毁实例。当用户说"跑图/出图/生图/生成一张图/用仙宫云跑/用 ComfyUI 出图/用 Krea2 跑/拿我的 4090 跑一张/跑完就销毁/省钱的跑图方式"，或者要用**本地部署的模型**（Krea2、自训 LoRA、ControlNet、图生图、参考图）出图时使用。目标是花**两三分钱**而不是开一天机（开机不计费，只在实例「运行中」期间按秒收费）。纯 API 出图（gpt-image / nano-banana）不走这里，用 grsai-image-2-5 或 grsai-nano-banana。
compatibility: Python 3.9+；OpenSSH 客户端在 PATH 里；可选 paramiko（仅密钥登录失败时回退密码登录用）；出站 HTTPS 到 api.xiangongyun.com
allowed-tools: Bash, Read, Write
---

# 仙宫云跑图一条龙

**一句话：有跑图需求 → 开机器 → 出图 → 拉图 → 立刻销毁。全程无人值守，异常也销毁。**

```bash
S=~/.pi/agent/skills/xgc-image-run/scripts/xgc_run_image.py

python "$S" --status                                  # 先看有没有在烧钱的机器（永远先跑这个）
python "$S" --prompt "..." --dry-run                  # 演练：只打印 payload，不开机
python "$S" --prompt "..." --yes                      # 真跑（唯一会花钱的调用）
python "$S" --prompt "..." --size 1536x1024 --yes     # 指定尺寸
python "$S" --prompt "..." --open --yes               # 跑完自动用看图器打开
```

## Hard Rules

1. **先 `--status`，永远。** 有实例在跑就是在烧钱。脚本自己也挡了一道：默认拒绝在已有
   `running` 实例时并行开工，除非显式 `--allow-parallel`。
2. **`--yes` 代表"我批准这次花钱"。** 用户没说跑，就不要加。用户说"跑一张"就等于批准
   **一次**；改主意了、要跑第二张，重新确认。
3. **销毁是默认行为，不是选项。** 脚本用 `try/finally` 保证出图失败 / 下载失败 / Ctrl-C /
   超时都会销毁。`--keep` 是给调试用的，用了必须大声警告用户"还在烧钱"，并给出销毁命令。
4. **慢 ≠ 贵 —— 开机不计费。** 平台只在实例达到 `运行中` 之后才开始按秒计费，铺镜像、起容器
   全部免费。实测：首次部署这张 49 GB 镜像壁钟 141 秒，只扣 ¥0.0075（≈17 秒）。
   - **别因为「等太久」中断部署** —— 等待免费，首次部署几分钟很正常。
   - **别为了「省开机时间」把实例留着不销毁** —— 开机本来就免费，空闲的 `运行中` 实例才是纯亏。要复用就重新部署，不要养着。
   - **别用壁钟乘单价算钱**，会虚报 20%+。要看余额差额 —— 脚本已经从「运行中」开始算了。
5. **部署「失败」就停下报告，绝不盲目重试。** 但要区分两件事：**慢**（正常，等）和**报错**（停）。
   脚本对二者的处理不同 —— 慢会一直等，报错直接退出。混淆二者是浪费钱的常见方式。
6. **永不删除镜像。** 本技能只销毁实例，不碰镜像接口。要删镜像让用户自己去控制台。
7. **不要打印 `password` / `ssh_port` / `jupyter_token` / `xgcos_token`。** 脚本内部用
   `scrub()` 过滤，自己手动查 API 时也要过滤。
8. **令牌当账号用。** 在 `~/.xgc_token`，不进聊天、不进仓库、不 echo。

## 成本模型（实测校准）

**平台只在实例「运行中」期间计费。** dry-run 原话：`billed per second from the moment
it reaches 运行中, until destroyed`。deploy 到「运行中」这段 —— 包括铺 49 GB 镜像 —— **不花钱**。

实测校准：第一次部署这张镜像时壁钟 141 秒，实际只扣 **¥0.0075**（≈17 秒）；镜像缓存后
只等 12 秒。**所以别用壁钟乘单价 —— 那会虚报 ~20%。要用余额差额算。**
（`xgc_run_image.py` 已经从「运行中」开始计了。）

单张 1536×1024 实测拆解（**计费窗口内**）：

| 阶段 | 耗时 | 折算 | 占比 |
|---|---|---|---|
| SSH 就绪 | ~15s | ¥0.0066 | 27% |
| ComfyUI 就绪 | 5s | ¥0.0022 | 9% |
| **GPU 实际出图** | **21.1s** | **¥0.0093** | **38%** |
| 下载 2.2 MB | ~5s | ¥0.0022 | 9% |
| 销毁 | ~10s | ¥0.0044 | 18% |
| **计费合计** | **56s** | **¥0.0247** | 100% |
| ~~开机等待~~ | ~~12s~~ | ~~免费~~ | — |

### 两个结论

**1. 出图只占 38%。** 把出图优化到 0 秒最多省 ¥0.009。所以「换更快的模型」「换更吊的显卡」
都不是主战场 —— 固定开销那一坨才是。

**2. 批量才是主战场。** 固定开销被摊薄：

| 一次开机跑几张 | 计费时长 | 总花费 | 单张 |
|---|---|---|---|
| 1 张 | 56s | ¥0.0247 | ¥0.0247 |
| 4 张 | 119s | ¥0.0526 | ¥0.0132 |
| 8 张 | 204s | ¥0.0901 | ¥0.0113 |

（首次出图含模型加载 ≈ 21s；第 2 张起模型是热的，可能只要 ~10s —— **待实测**。）

### 为什么「换更贵的显卡」反而亏

贵卡的开机/就绪/销毁时间也按贵价计费。假设快 2 倍、贵 2 倍（¥3.18/h）：

```
非出图开销 34.9s  ¥0.0154  ->  ¥0.0308   涨一倍
出图 21.1s->10.5s ¥0.0093  ->  ¥0.0093   一分不省
合计             ¥0.0247  ->  ¥0.0401   贵 62%
```

**只有「提速倍数 > 涨价倍数」才划算**，而对一个 38% 是实际计算的流程，这个门槛很高。

### 对照

```
忘记销毁挂一整天    ¥38.16   是一张图的 1545 倍
余额 ¥16           ≈ 跑 650 张图，但只够裸挂 10 小时
```

所以「跑完立刻销毁」不是洁癖，是这个技能的全部价值。

## 前置条件

```bash
# 访问令牌（一次性）
echo -n '<访问令牌>' > ~/.xgc_token        # https://www.xiangongyun.com/console/user/accesstoken

# 默认参数（可选，脚本有内置兜底）
cat > ~/.xgc_defaults.json <<'EOF'
{
  "default_image": "f0cbf8c7-96c7-4010-a645-1898927c33ea",
  "default_gpu": "NVIDIA GeForce RTX 4090 D",
  "ssh_private_key": "~/.ssh/piwebui.pem",
  "workflow_txt2img": "/root/ComfyUI/user/default/workflows/Krea2_Turbo_文生图.json",
  "comfy_port": 8188
}
EOF
```

镜像 `f0cbf8c7-96c7-4010-a645-1898927c33ea`（名字「agent调用此镜像跑图」）里已经装好：
ComfyUI 0.37 + Krea 2 Turbo fp8 + qwen3vl_4b 文本编码器 + qwen_image_vae，以及开机自启脚本。
**换镜像只需要改 `default_image`**，脚本其余部分不关心镜像里是什么。

## 这条流水线在脚本里怎么走

```
[1/7] deploy          转交 xgc.py（带 --yes 双确认 + 写入 ~/.xgc_history.jsonl）
[2/7] 等 running       轮询 /open/instances，拿到 ssh_domain / ssh_port / price_per_hour
                      ← 到这里为止一分钱没花，计费从「运行中」开始
[3/7] SSH              密钥 ~/.ssh/piwebui.pem；密钥不通自动回退容器密码（paramiko）
                      ⚠ 实测：这张镜像里**没有**这把公钥（容器开机时会用平台的 ssh_key 配置
                      重置 authorized_keys，手工写的保不住）。所以走的是密码回退这条路。
                      想用密钥登录：deploy 时带 --ssh-key（见“密钥登录”一节）
[4/7] 等 ComfyUI       curl /system_stats 直到返回 200。**SSH 通了不等于它起来了** ——
                      早期版本没等这一步，直接吃 [Errno 111] 拒绝连接，白花 ¥0.06。
[5/7] 出图             把远端 python 脚本通过 stdin 喂给 `python3 -`（绕开 shell 转义地狱）
                       UI 工作流 json → API 格式 → POST /prompt → 轮询 /history
[6/7] 下载             远端 base64 回传，写本地文件
[7/7] destroy          finally 块，无条件执行 ← 计费在这一刻停止
```

## 参数

| 参数 | 说明 |
|---|---|
| `--prompt` | 提示词（英文更稳，qwen3vl 也吃中文） |
| `--size` | `宽x高`，如 `1536x1024`。默认 `1024x1024` |
| `--steps` `--cfg` | Krea2 Turbo 用 `8` / `1.0`，**不要**加 FluxGuidance |
| `--seed` | 固定种子复现 |
| `--batch` | 一次出几张 |
| `--prefix` | 输出文件名前缀 |
| `--out` | 本地保存目录，默认当前目录 |
| `--gpu` `--image` | 覆盖默认 GPU / 镜像 |
| `--workflow` | 换工作流，如 `/root/ComfyUI/user/default/workflows/Krea2_Turbo_图生图.json` |
| `--open` | 跑完用系统看图器打开 |
| `--keep` | **不销毁（烧钱）**，仅调试 |
| `--allow-parallel` | 已有实例在跑时也继续 |
| `--status` | 只看状态然后退出 |
| `--dry-run` | 只打印 payload，不开机 |
| `--yes` | 确认花钱 |

## 密钥登录（可选，目前用不上）

实测结论：**手工把公钥写进容器的 `authorized_keys` 是白费的**。容器每次开机都会用平台的
`ssh_key` 配置重置它 —— 我写过一次、存了镜像、下次开机又没了。所以 `xgc-image-run` 默认
**靠容器密码回退登录**，这条路径实测稳定，不需要任何额外配置（密码由 API 的
`GET /open/instances` 提供，脚本自己取，不落盘、不打印）。

要真用上密钥，必须在 `deploy` 时绑：

```bash
python ~/.pi/agent/skills/xgc-api/scripts/xgc.py deploy \
    --gpu "NVIDIA GeForce RTX 4090 D" --count 1 \
    --image f0cbf8c7-96c7-4010-a645-1898927c33ea --image-type private \
    --ssh-key "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIA5O7jntM3DXbtsiN+dOcmSWYAtDd9N0HHM0z9qBIkYP piwebui" \
    --dry-run
```

**这条路径还没实测过**（要花 ~¥0.03 开一次机验证）。在验证之前，不要向用户承诺密钥登录可用。

## 故障排查

| 现象 | 原因 / 处理 |
|---|---|
| `已有实例正在运行` | 先销毁旧的，或 `--allow-parallel` |
| `SSH 连不上（360s）` | 镜像里没有公钥。脚本会回退到容器密码；仍失败就查 `ssh_port`/`ssh_domain` |
| 远端 `出图失败` | 工作流节点名对不上。看返回的 ComfyUI 报错原文 |
| `ComfyUI 执行出错` | 多半是模型没加载完或显存不够，看 `status.messages` |
| deploy 后看不到新实例 | 去控制台确认。**别重试** |
| 销毁失败 | 立刻 `python <xgc-api>/scripts/xgc.py destroy <id> --yes`，或控制台手动关 |

## 独立验证（不懂脚本内部也能查）

```bash
python ~/.pi/agent/skills/xgc-api/scripts/xgc.py instances --running    # 还有谁在烧钱
python ~/.pi/agent/skills/xgc-api/scripts/xgc.py history                # 本工具发过的所有写操作
```
