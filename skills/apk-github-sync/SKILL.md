---
name: apk-github-sync
description: 把本机 Pi 开发出来的 Android APK 软件包和源代码镜像备份到 GitHub 仓库（自动提交 + 推送 + 定时/实时自动备份）。当用户说"备份 apk / 把 apk 传到 GitHub / apk 自动上传 / 新做的安卓 app 传上去 / 备份安卓源码 / apks 文件夹更新一下 / 查 apk 备份状态"时使用。和 skills-github-sync 是姊妹技能，共用同一个仓库。
---

# APK 自动上云（apk-github-sync）

把本机 Pi 开发出来的 **APK + 源代码** 镜像到 GitHub 仓库的 `apks/` 目录，
按分类 + 应用分子文件夹存放，并在每次编译出新 APK 后自动提交推送。

跟 [`skills-github-sync`](../skills-github-sync/) 是同一套设计（镜像 / 幂等 / 无感 / 四条触发链路），
两个技能**共用同一个仓库和同一把锁**：`apks/` 与 `skills/` 互不干扰，
同一时刻只有一个同步进程会真正提交。

## 目录结构（仓库里）

```
apks/
  README.md              # 自动生成：按分类列出每个 app
  index.json             # 自动生成：机器可读清单
  <分类>/
    <slug>/
      <slug>.apk         # 编译产物
      meta.json          # 版本 / 体积 / sha256 / 来源路径 / 编译时间
      src/               # 源代码快照（已剔除 build、缓存、运行期数据）
```

当前分类：`learning`（学习/科普）、`tools`（工具）、`design`（设计与演示）。

## 本机文件

| 位置 | 作用 |
|---|---|
| `~/.pi/agent/apk-sync.json` | 唯一配置：远端、仓库、**app 注册表**、排除规则 |
| `~/.pi/skills-repo/` | 本地 git 仓库（和 skills 共用），`apks/` 在里面 |
| `~/.pi/agent/skills/apk-github-sync/scripts/apk_sync.py` | 同步引擎 |
| `~/.pi/agent/skills/apk-github-sync/scripts/install-autostart.ps1` | 计划任务安装脚本 |
| `~/.pi/agent/extensions/apk-autosync.ts` | Pi / pi-web 扩展：实时 + 轮询 + 启动对账 |
| `~/.pi/agent/apk-sync.log` | 同步日志 |
| `~/.pi/agent/apk-autosync.log` | 扩展触发日志 |

## 日常使用

```bash
S=~/.pi/agent/skills/apk-github-sync/scripts/apk_sync.py

python $S              # 同步 + 提交 + 推送（最常用）
python $S --status     # 看登记了哪些 app、APK 找没找到
python $S --dry-run    # 只看会同步什么，不动文件
python $S --no-push    # 只提交到本地仓库
python $S --quiet      # 静默：stdout 只输出 RESULT 行
```

**机器可读结果**：`--quiet` 时 stdout 最后一行固定为 `[apk-sync] RESULT <state>`，
state ∈ `pushed` / `committed` / `no-change` / `busy` / `dry-run` / `no-apps` /
`unconfigured` / `failed`。扩展和计划任务靠这一行判断该不该弹提示。

退出码：`0` 成功/无变化，`1` 推送失败，`2` 未配置远端。

## 加一个新 app（重点）

编辑 `~/.pi/agent/apk-sync.json` 的 `apps` 数组，加一条：

```json
{
  "slug": "my-app",
  "title": "我的应用",
  "category": "tools",
  "categoryTitle": "工具",
  "package": "com.hua.myapp",
  "version": "1.0",
  "notes": "一句话说明",
  "source": "C:/Users/hua/Documents/备份代码/MyApp",
  "apk": "C:/Users/hua/Documents/备份代码/MyApp/dist/*.apk"
}
```

- `apk` 可以是具体文件，也可以带 `*` 通配符；**多个匹配时取 mtime 最新那个**——
  所以重新编译（改了文件名也行）下次同步自动带上新包。
- `source` 是项目根；同步时会递归拷贝到 `src/`，自动剔除
  `build`、`.gradle`、`.kotlin`、`node_modules`、`dist`、`__pycache__` 等，
  以及 `*.apk`、`*.log`、`local.properties`、`local.json`、`*.db` 等文件，
  再加上配置里的 `excludeDirs`（默认 `data`、`logs`、`screens`、`vendor`）。
- 配置里删掉一条，仓库里对应目录也会被删（`git log` 里仍可找回）。

### 自动发现没登记的 APK（可选）

`scan.enabled` 设为 `true` 后，脚本会按 `scan.globs` 扫 APK，
没被 `apps` 收录（按 sha256 去重）的会放进 `apks/_auto/`，方便兜底备份。
建议发现后手动登记进 `apps`，命名和分类更清楚。

## 自动触发（四条链路，互为兜底）

`~/.pi/agent/extensions/apk-autosync.ts` 同时跑四条链路：

| 链路 | 间隔 | 作用 |
|---|---|---|
| ① fs.watch 实时 | 变化后 **8 秒** | 递归监听每个 app 的源码目录 + APK 输出目录 |
| ② 指纹轮询兜底 | 每 **45 秒** | 稳。Windows 的 fs.watch 会静默丢事件，全靠它兜底 |
| ③ 启动对账 | 会话启动后 **15 秒** | 补齐上次没传上去的改动 |
| ④ Windows 计划任务 | 每 30 分钟 | pi-web 完全没开也在跑 |

四条链路和 skills 同步的完全一致（为什么不用 `pi.exec`、为什么要所有权令牌、
为什么 Windows 上传时不再弹终端窗口 —— 这些坑都在
[`skills-github-sync` 的 SKILL.md](../skills-github-sync/SKILL.md#自动触发四条链路互为兜底) 里写清楚了，此处不重复）。

手动触发：`/apk-sync`；只看状态：`/apk-sync status`。

### Windows 计划任务（④）

```powershell
powershell -ExecutionPolicy Bypass -File `
  "$HOME\.pi\agent\skills\apk-github-sync\scripts\install-autostart.ps1" -EveryMinutes 30
```

任务名 `PiApkGitHubSync`。卸载：加 `-Uninstall`。
立即跑：`Start-ScheduledTask -TaskName PiApkGitHubSync`。

## 和 skills 同步的关系（重要）

- **共用一个本地仓库** `~/.pi/skills-repo`，共用一把锁 `~/.pi/agent/skills-sync.lock`。
- `apk_sync.py` 只写 `apks/`；`sync.py` 只写 `skills/` + 根 `README.md` / `index.json`，
  所以文件层面互不覆盖。
- 两个脚本都会在推送前 `fetch + pull --rebase --autostash`，
  抢跑导致 non-fast-forward 时会自动重试。
- 谁先拿到锁谁先跑，另一个会输出 `RESULT busy` 静默跳过，下一轮（≤45 秒）再来。

## 常见问题

**仓库是公开的** → `apks/README.md` 里有醒目提醒：源码可能带本地签名的 keystore。
不想公开就把仓库改成 private，或在本机配置里加排除规则。

**某个 app 不想备份** → 从 `apps` 里删掉即可，仓库对应目录下次同步会被清掉。

**单文件超过 100 MB** → GitHub 会拒收。APK 太大时考虑 `git-lfs`，或只备份源码。
（`apk_sync.py` 目前不做 LFS，超限会在推送时报错并写日志。）

**改完扩展没生效** → 在 pi / pi-web 里执行 `/reload`。新建会话会自动加载。

**同步失败会重试** → 推送失败时不更新指纹，轮询每 45 秒重试；
同样的报错 10 分钟内不重复弹通知。

**中文日志乱码** → 已强制 UTF-8；旧 cmd 里先 `chcp 65001`。
