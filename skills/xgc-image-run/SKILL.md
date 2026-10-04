---
name: xgc-image-run
description: 仙宫云 GPU 跑图一条龙 —— 自动开机 → 自动连进容器 → 跑 ComfyUI 出图 → 把图拉回本地 → 立刻销毁实例。当用户说"跑图/出图/生图/生成一张图/用仙宫云跑/用 ComfyUI 出图/用 Krea2 跑/拿我的 4090 跑一张/跑完就销毁/省钱的跑图方式"，或者要用**本地部署的模型**（Krea2、自训 LoRA、ControlNet、图生图、参考图）出图时使用。目标是花几毛钱而不是开一天机。纯 API 出图（gpt-image / nano-banana）不走这里，用 grsai-image-2-5 或 grsai-nano-banana。
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
4. **绝不重试 deploy。** 部署失败就停下报告 —— 盲目重试会重复扣费。
5. **永不删除镜像。** 本技能只销毁实例，不碰镜像接口。要删镜像让用户自己去控制台。
6. **不要打印 `password` / `ssh_port` / `jupyter_token` / `xgcos_token`。** 脚本内部用
   `scrub()` 过滤，自己手动查 API 时也要过滤。
7. **令牌当账号用。** 在 `~/.xgc_token`，不进聊天、不进仓库、不 echo。

## 成本模型（为什么这套值得做）

按秒计费。跑一张 1024² 只要十几秒，加上开机、加载 13 GB 模型、下载，整个流程通常
**2~4 分钟**，4090 D 约 ¥1.59/时 → **一张图不到一毛钱**。

对照：忘记销毁、挂一晚上 = **¥38**。所以「跑完立刻销毁」不是洁癖，是这个技能的核心价值。

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
[1/6] deploy          转交 xgc.py（带 --yes 双确认 + 写入 ~/.xgc_history.jsonl）
[2/6] 等 running       轮询 /open/instances，拿到 ssh_domain / ssh_port / price_per_hour
[3/6] SSH              密钥 ~/.ssh/piwebui.pem；密钥不通自动回退容器密码（paramiko）
[4/6] 出图             把远端 python 脚本通过 stdin 喂给 `python3 -`（绕开 shell 转义地狱）
                       UI 工作流 json → API 格式 → POST /prompt → 轮询 /history
[5/6] 下载             远端 base64 回传，写本地文件
[6/6] destroy          finally 块，无条件执行
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
