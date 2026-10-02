---
name: skills-github-sync
description: 把本机 Pi skills 镜像同步到 GitHub 仓库（自动提交 + 推送），并在仓库里维护 README 清单。当用户说"同步 skills 到 GitHub / 上传 skills / 备份 skills / 新建一个 skill 顺手传上去 / skills 自动上传 / 仓库里的 skills 更新一下"，或需要初始化一个 skills 仓库、配置自动上传、排查同步失败时使用。
---

# skills 自动上云（skills-github-sync）

把 `~/.pi/agent/skills`（以及可选的 `~/.agents/skills`）**镜像**到一个 GitHub 仓库。
仓库里也包含本技能自身，所以是"自己传自己"：新增任何 skill，下一次同步就会自动出现在仓库里。

## 目录与文件

| 位置 | 作用 |
|---|---|
| `~/.pi/agent/skills-sync.json` | 唯一配置：远端地址、分支、源目录、repoDir、token |
| `~/.pi/skills-repo/` | 本地 git 仓库（镜像目标），可随时删掉重来 |
| `~/.pi/agent/skills-sync.log` | 同步日志 |
| `~/.pi/agent/extensions/skills-autosync.ts` | Pi / pi-web 扩展：监听 skills 目录，变了就自动同步 |
| `scripts/sync.py` | 同步引擎（本技能的核心） |
| `scripts/install-autostart.ps1` | 可选：注册 Windows 计划任务，Pi 没开也定时同步 |

## 当前已配置状态（本机）

| 项 | 值 |
|---|---|
| 远端 | `https://github.com/kungful/me_skills_pi.git` |
| 分支 | `main` |
| 源 | `~/.pi/agent/skills` + `~/.agents/skills`（共 8 个 skill） |
| 鉴权 | 走 Git Credential Manager（已存 GitHub 凭据），无需 token |
| 仓库文件 | `skills/<名字>/...` + `README.md` + `index.json` |
| 实时自动上传 | ✓ 扩展 `skills-autosync.ts` 已生效 |
| 定时自动上传 | ✓ 计划任务 `PiSkillsGitHubSync`（每 30 分钟 + 登录时） |

## 三个问题先问清楚

1. **远端**：仓库地址 `https://github.com/<owner>/<repo>.git`（是否想让脚本自动创建？）
2. **鉴权**：优先用已有的 GitHub 凭据（Git Credential Manager / `git credential fill` 能取到就不用 token）；
   否则给 GitHub PAT（classic，勾 `repo`）。token 不落盘到 git config，也可用环境变量 `GITHUB_TOKEN`
3. **源**：默认 `~/.pi/agent/skills` + `~/.agents/skills`，要不要加减？

## 第一次配置（一次性）

```bash
# 有 token 时可用 --token（还能自动建远端仓库）；
# 没有 token 但本机已存 GitHub 凭据时，直接跑即可：
python ~/.pi/agent/skills/skills-github-sync/scripts/sync.py \
  --init --repo <owner>/<repo> [--token <PAT>]
```

`--init` 会：写配置 → `git init` → **对齐远端已有历史**（避免首次推送 non-fast-forward）
→ 镜像 skills → 首次提交 → 推送。

## 日常使用

```bash
S=~/.pi/agent/skills/skills-github-sync/scripts/sync.py

python $S                # 同步 + 提交 + 推送（最常用）
python $S --dry-run      # 只看会同步哪些，不动任何文件
python $S --no-push      # 只提交到本地仓库
python $S --status       # 看配置、源、发现的 skill、未提交变更
python $S --quiet        # 静默：进度只进日志，stdout 只回一行结果
```

**机器可读结果**：`--quiet` 时 stdout 最后一行固定为 `[skills-sync] RESULT <state>`，
state ∈ `pushed` / `committed` / `no-change` / `busy` / `dry-run` / `no-skills` /
`unconfigured` / `failed`。扩展和定时任务就靠这一行判断该不该弹提示。

退出码：`0` 成功/无变化，`1` 推送失败，`2` 未配置远端。

**重复跑不会产生空提交**：skills 内容没变时既不重写 README 也不 commit。

## 自动触发（两套，可同时开）

### 1. Pi / pi-web 扩展（实时，推荐）

`~/.pi/agent/extensions/skills-autosync.ts` 已经装好。它会在：
- Pi/pi-web 会话启动后 12 秒做一次对账同步（补齐上次没传上去的改动）；
- 递归监听源目录，**新增/修改/删除 skill 后 8 秒**自动同步（防抖 + 文件锁 + 锁排队）。

生效方式：新建的 pi-web 会话自动加载（实测：本会话内改 skill，~9 秒后就出现在 GitHub 上）。
若旧会话没加载，**重启 pi-web**（或 pi TUI 里 `/reload`）。
手动触发：`/skills-sync`；只看状态：`/skills-sync status`。

> 没有配置远端时扩展会静默跳过，不会每次启动都弹错。

### 2. Windows 计划任务（Pi 没开也在跑）

```powershell
powershell -ExecutionPolicy Bypass -File `
  "$HOME\.pi\agent\skills\skills-github-sync\scripts\install-autostart.ps1" -EveryMinutes 30
```

注册一个"每 30 分钟 + 每次登录"运行 `sync.py` 的计划任务（用 `pyw.exe -3` 无窗口跑）。
卸载：加 `-Uninstall`。立即跑：`Start-ScheduledTask -TaskName PiSkillsGitHubSync`。
脚本会自动找 Python：`py.exe` 启动器 → `LOCALAPPDATA\Programs\Python\Python3*\pythonw.exe` → PATH。
也可用 `-PythonExe` 手动指定。

> 注意：`New-ScheduledTaskTrigger -AtLogOn` 必须带 `-User`，否则需要管理员权限（Access denied）。

## 镜像规则（重要）

- 源目录**只读**，绝不修改源；仓库里是副本。
- 源里删掉的 skill，仓库里对应目录也会删（`git log` 里仍可找回）。
- 忽略：`__pycache__`、`*.pyc`、`node_modules`、`.venv`、`*.log`、`.DS_Store` 等。
- 跨源重名：自动加源后缀（如 `kicad-agents`）。
- 仓库根 `README.md` + `index.json` 每次同步自动重写，别手改。
- 无变化时**不会**产生空提交。

## 常见问题

**中文日志乱码** → 已强制 UTF-8；若在旧 cmd 里仍乱码，先 `chcp 65001`。

**推送 403 / 认证失败** → token 过期或权限不足，检查是 classic PAT 且勾了 `repo`；
或远端地址是 HTTPS 但本机代理不通（本机 git 已配 `http.https://github.com.proxy`）。

**non-fast-forward** → `sync.py` 会自动 `pull --rebase --autostash` 再重试一次；
`--init` 时如果远端已有历史（比如 GitHub 建仓时生成的 `Initial commit`），
会先 `git fetch` + `git reset --mixed origin/<branch>` 对齐，不会冲突。
仍失败就手动 `git -C ~/.pi/skills-repo pull --rebase origin main`。

**不想让某个 skill 上传** → 在该 skill 目录放一个名为 `.nosync` 的空文件（脚本会跳过，并在日志里提示）。

**要换仓库** → 改 `skills-sync.json` 的 `remote`，删掉 `~/.pi/skills-repo`，重新 `--init`。
