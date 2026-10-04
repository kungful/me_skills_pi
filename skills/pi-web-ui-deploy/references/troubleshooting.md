# pi-web-ui 排障手册

## 1. 浏览器报 `host not allowed`

**现象**：用 `https://<实例ID>-8787.container.x-gpu.com/` 打开，页面空白/直接显示 `host not allowed`；
本地 `curl -H 'Host: localhost'` 却正常。

**原因**：pi-web-ui 的 Host 守卫 `dist/server/host-guard.js`（`httpHostAllowed`）在没有 token 时
只放行 loopback（`localhost`、`127.0.0.0/8`、`[::1]`）和私网（10/8、172.16/12、192.168/16、
169.254/16、fe80::/10、fc00::/7）。公网域名不属于这些，被 403 拒绝。这是**防 DNS rebinding**，
不是 bug。

**修复**：把公网域名加进白名单（严格模式下白名单之外一律拒绝，所以本机也要列上）：

```bash
export PI_WEB_ALLOW_HOSTS="${XGC_INSTANCE_ID}-8787.container.x-gpu.com,localhost,127.0.0.1"
export PI_WEB_ALLOW_ORIGINS="https://${XGC_INSTANCE_ID}-8787.container.x-gpu.com,http://${XGC_INSTANCE_ID}-8787.container.x-gpu.com,http://localhost:8787,http://127.0.0.1:8787"
```

WebSocket 侧的 `originAllowed()` 也复用同一白名单，且**要求 Host 的主机名在 `PI_WEB_ALLOW_HOSTS` 里**，
所以只设 `ORIGINS` 不够，两个都要设。改完重启服务。

> 实例 ID 每次重建容器都会变。永远别写死，用 `XGC_INSTANCE_ID` 动态拼（见 `start.d-pi-web-ui.sh`）。

## 2. 设了 `PI_WEB_TOKEN` 却像没生效

**原因**：`/scripts/pi-web-ui.env` 是被 `. file`（source）读入的。`PI_WEB_TOKEN="x"` 只是当前 shell
变量，**不 export 就不会传给 `pi-web-ui` 进程**。从而 `AUTH_TOKEN` 为空，守卫走「无 token」分支。

**修复**：写成 `export PI_WEB_TOKEN="..."`，重启。验证：

```bash
pid=$(pgrep -f "pi-web-ui --host" | head -1)
tr '\0' '\n' < /proc/$pid/environ | grep PI_WEB_TOKEN
```

注意：启用后所有 HTTP/WS 都要带 `Authorization: Bearer`、`X-PI-Token` 头、`?token=` 查询参数或
`pi_web_token` cookie 之一。

## 3. 重启后版本又变了

**来源**（三者任一）：
1. 手动/脚本执行了 `npm i -g pi-web-ui@latest`（历史里常见）。
2. pi 的 `~/.pi/agent/settings.json` 含 `packages: ["npm:pi-web-ui"]` —— pi 启动时会把它当包自动装到
   `~/.pi/agent/npm`，范围是 `^x.y.z`，会漂小版本。
3. pi-web-ui 应用内「更新」按钮（`managed.js`：`npm i -g pi-web-ui@latest`）。

**修复**：
- 安装用**固定版本**，不要 `@latest`。
- 在 `/scripts/pi-web-ui.env` 里 `export PI_WEB_MANAGED=1` —— 服务端拒绝 `check_update` /
  `check_updates_all` / `install_pi_agent` / `plugin_catalog_add` / `plugin_job` / `plugin_catalog_sync`，
  界面也不再显示更新入口。代价：插件市场也一并禁用。
- 仍在漂移：检查并清理 `settings.json` 的 `packages`，或把依赖钉死。

## 4. 模型「需要重新配置」（列表空 / 选中被重置 / key 要重填）

先分清是**真丢**还是**看着像丢**：

```bash
cat ~/.pi/agent/models.json | head            # 自定义服务商（含 apiKey）
cat ~/.pi-web/client-state.json               # __settings__.projectModels 里是每个项目的选中模型
tr '\0' '\n' < /proc/$(pgrep -f 'pi-web-ui --host'|head -1)/environ | grep PI_CODING_AGENT_DIR
```

- 这些文件在 `/root`（或 `$HOME`）下，**持久化，容器重建不丢**。若文件在，多半是升级后引擎/界面
  重新扫描导致的显示重置，重选一次即可。
- 若确实为空/损坏：`bash pi-web-config-tool.sh restore` 回滚到最近备份。
- 选定模型存在 `client-state.json` 的 `__settings__.projectModels["<cwd>"]`；只要 `--cwd` 没变就应保留。

## 5. 启动慢 / 扫描卡住

日志提示 `工作区为...目录扫描可能因外部卷/同步盘挂载而长时间阻塞`。若 `PIWEB_CWD` 指向含网盘挂载的
目录（如 `~/cloud`），首屏会慢。把 `PIWEB_CWD` 换成具体项目目录。

## 6. 没有 systemd，怎么自启？

`pi-web-ui server install` 只写 systemd unit，本环境 PID 1 是 docker-init，`systemctl` offline，必失败。
唯一入口是 `/scripts/start.sh` 里遍历 `/scripts/start.d/*` 的循环。所以必须把启动逻辑写成
`/scripts/start.d/` 下的**一次性幂等脚本**（本 skill 的 `start.d-pi-web-ui.sh` 即为此设计）。

## 7. 备用通道：SSH 端口转发

平台域名出问题时，可绕过代理直连本机端口：

```bash
ssh -L 8787:127.0.0.1:8787 root@<平台SSH地址> -p <SSH端口>
# 然后浏览器访问 http://localhost:8787/
```

此时 Host 是 `localhost`，本来就在白名单内。
