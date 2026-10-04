---
name: pi-web-ui-deploy
description: Deploy and stabilize pi-web-ui (pi 编码代理的 Web UI) inside an XGC / x-gpu container — global npm install, screen + /scripts/start.d autostart, dynamic Host allow-list (fixes "host not allowed"), version freeze to stop upgrade drift, and pi model-config backup/restore. Use when installing pi-web-ui on a fresh container, when the browser shows "host not allowed", when a restart changes the pi-web-ui version and model settings need reconfiguring, or when backing up/restoring the pi model config.
argument-hint: "[install|fix-host|freeze|backup|restore]"
---

# pi-web-ui 部署与稳定化（XGC / x-gpu 容器）

目标：在一台 XGC 容器里把 `pi-web-ui` 装好、开机自启、公网可访问，并且**重启后版本不乱变、模型配置不丢**。

本 skill 目录下的文件：

- `scripts/install.sh` — 一键安装（全局 npm 安装 + 部署自启 + 写白名单）
- `scripts/start.d-pi-web-ui.sh` — 开机自启脚本，部署到 `/scripts/start.d/pi-web-ui.sh`
- `scripts/pi-web-ui.env.example` — 自启配置模板，部署到 `/scripts/pi-web-ui.env`
- `scripts/pi-web-config-tool.sh` — 模型/界面配置的备份与恢复
- `references/troubleshooting.md` — "host not allowed" 等原因与处置

## 关键事实（先读，避免走弯路）

- 本环境**没有 systemd**（PID 1 是 docker-init）。`pi-web-ui server install` 会失败。真正的开机自启入口是 `/scripts/start.sh` 里的 `for script in /scripts/start.d/*; do "$script" & done`。
- **实例 ID 每次重建容器都会变**（`XGC_INSTANCE_ID`）。公网域名是 `${XGC_INSTANCE_ID}-8787.container.x-gpu.com`。任何写死旧 ID 的 Host 白名单都会过期 → 报 `host not allowed`。必须动态生成。
- pi-web-ui 的 Host 守卫（`dist/server/host-guard.js`）在**没有 token**时只放行 loopback / 私网 Host；公网域名必须写进 `PI_WEB_ALLOW_HOSTS`，WebSocket 侧还要 `PI_WEB_ALLOW_ORIGINS`。
- `npm i -g ...@latest`、pi 设置里的 `packages:["npm:pi-web-ui"]`、以及**应用内升级按钮**都会让版本漂移。要稳定就冻结版本 + 设 `PI_WEB_MANAGED=1`。
- `/scripts/*.env` 是被 `. file` 读入的：**里面要 `export` 才会传给服务进程**，否则值（如 token）静默不生效。

## 步骤

### 1. 安装（默认冻结版本）

```bash
# 用本 skill 自带的一键脚本（可传版本；默认是已知稳定的 pin）
bash scripts/install.sh
# 或显式指定版本：
PIWEB_VERSION=0.99.0 PI_SDK_VERSION=1.0.2 bash scripts/install.sh
```

脚本会：
1. `npm i -g --allow-scripts=node-pty,@google/genai,protobufjs @earendil-works/pi-coding-agent@<ver> pi-web-ui@<ver>`（用固定版本，不用 `@latest`）。
2. 若 `/scripts/pi-web-ui.env` 不存在则从模板生成（含 `export PI_WEB_MANAGED=1`）。
3. 部署 `/scripts/start.d/pi-web-ui.sh` 并 `chmod +x`。
4. 往 `~/.bashrc` 写入**动态**白名单块（手动前台启动时也生效），已存在则跳过。
5. 立即启动一次并打印访问地址。

手工等价命令（不想用脚本时）：

```bash
npm i -g --allow-scripts=node-pty,@google/genai,protobufjs \
  @earendil-works/pi-coding-agent@1.0.2 pi-web-ui@0.99.0
```

### 2. 配置自启

```bash
cp scripts/pi-web-ui.env.example /scripts/pi-web-ui.env   # 按需改端口/token/cwd
install -m 0755 scripts/start.d-pi-web-ui.sh /scripts/start.d/pi-web-ui.sh
```

`.env` 里三个要点：
- `PIWEB_HOST=0.0.0.0`（平台 8787 代理需要）；
- `export PI_WEB_MANAGED=1`（冻结更新；去掉即恢复应用内升级）；
- `PI_WEB_TOKEN` 若要用，**必须写成 `export PI_WEB_TOKEN=...`**，否则不生效。

自启脚本会自动按 `XGC_INSTANCE_ID` 生成 `PI_WEB_ALLOW_HOSTS` / `PI_WEB_ALLOW_ORIGINS`，用 `screen -dmS piweb` 拉起，带日志轮转与重复启动保护。

### 3. 立即启动 / 重启

```bash
bash /scripts/start.d/pi-web-ui.sh          # 幂等，端口已占用会跳过
screen -r piweb                             # 进现场看日志
screen -S piweb -X quit                     # 停止
tail -f /var/log/pi-web.log                 # 看日志
```

启动后访问地址写在 `~/.pi-web-ui.url`。

### 4. 验证

```bash
# 进程里应能看到动态白名单（和 PI_WEB_MANAGED）
pid=$(pgrep -f "pi-web-ui --host" | head -1)
tr '\0' '\n' < /proc/$pid/environ | grep -E "PI_WEB_ALLOW_HOSTS|PI_WEB_MANAGED"

# 用当前实例域名请求健康检查，应为 200
dom="${XGC_INSTANCE_ID}-8787.container.x-gpu.com"
curl -s -o /dev/null -w '%{http_code}\n' -H "Host: $dom" http://127.0.0.1:8787/api/health

# 故意用坏 Host，应被 403 拒绝（防 DNS rebinding 仍有效）
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: evil.example.com' http://127.0.0.1:8787/api/health
```

### 5. 备份 / 恢复模型配置

pi 的模型配置**在磁盘上是持久的**，通常不丢；但升级/重建后界面可能看起来被重置，所以定期备份：

```bash
bash scripts/pi-web-config-tool.sh backup          # 备份到 ~/pi-web-config-backups/<时间戳>
bash scripts/pi-web-config-tool.sh restore         # 从最近一次恢复（会先另存当前状态）
bash scripts/pi-web-config-tool.sh list
```

备份内容：`~/.pi/agent/{models.json,provider-keys.json,auth.json,models-store.json,settings.json}` 与 `~/.pi-web/{client-state.json,...}`。恢复后 `bash /scripts/start.d/pi-web-ui.sh` 重启生效。

## 决策规则

- **只有公网域名报 `host not allowed`** → 白名单问题，用本 skill 的动态生成逻辑（第 2 步），别写死实例 ID。
- **重启后版本变了** → 关掉 `@latest` 安装、`export PI_WEB_MANAGED=1`；仍漂移就查 pi 的 `~/.pi/agent/settings.json` 是否含 `npm:pi-web-ui`。
- **要更新版本** → 手动 `npm i -g pi-web-ui@<明确版本>`，改完 `install.sh` 里的 pin，重启；不要用 UI 的升级按钮（已被 MANAGED 拦住）。
- **想真正启用访问口令** → 把 `PI_WEB_TOKEN` 改成 `export PI_WEB_TOKEN=...`，之后访问必须带 `?token=`；否则 token 不生效且任何人拿到地址都能进。
- **工作目录扫描慢**（`/root` 下有网盘挂载）→ 把 `PIWEB_CWD` 指到具体项目目录。

## 分享提醒

Skill 是「说明 + 可执行脚本」。拷到其他服务器前请先审阅 `scripts/` 内容；`install.sh` 会执行 `npm i -g` 并写 `/scripts/start.d/`，需要 root 且会改动系统级目录。
