#!/bin/bash
# ==============================================================================
#  pi-web-ui 一键部署（XGC / x-gpu 容器）
#  做四件事：全局 npm 安装（固定版本）→ 写自启配置 → 部署自启脚本 → 写动态白名单
#  幂等：可重复执行。版本用变量控制，别用 @latest。
#
#  用法：
#    bash install.sh
#    PIWEB_VERSION=0.99.0 PI_SDK_VERSION=1.0.2 bash install.sh
#    PIWEB_CWD=/root/某项目 bash install.sh
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PIWEB_VERSION="${PIWEB_VERSION:-0.99.0}"
PI_SDK_VERSION="${PI_SDK_VERSION:-1.0.2}"
PIWEB_CWD="${PIWEB_CWD:-$HOME}"
PIWEB_PORT="${PIWEB_PORT:-8787}"
STARTD_DIR="${STARTD_DIR:-/scripts/start.d}"
ENV_FILE="${ENV_FILE:-/scripts/pi-web-ui.env}"

log() { printf '[install] %s\n' "$*"; }

# ---- 0. 环境检查 ----
command -v npm >/dev/null 2>&1 || { echo "缺少 npm，请先装 Node.js" >&2; exit 1; }
NPM_BIN_DIR="$(npm prefix -g)/bin"
log "node global bin: $NPM_BIN_DIR"

# ---- 1. 全局安装（固定版本，禁止 @latest）----
log "安装 @earendil-works/pi-coding-agent@$PI_SDK_VERSION 与 pi-web-ui@$PIWEB_VERSION …"
npm i -g --allow-scripts=node-pty,@google/genai,protobufjs \
  "@earendil-works/pi-coding-agent@${PI_SDK_VERSION}" \
  "pi-web-ui@${PIWEB_VERSION}"

PIWEB_BIN="$NPM_BIN_DIR/pi-web-ui"
[ -x "$PIWEB_BIN" ] || { echo "安装后找不到 $PIWEB_BIN" >&2; exit 1; }
log "pi-web-ui: $($PIWEB_BIN --version 2>/dev/null || echo '?')   pi: $(pi --version 2>/dev/null || echo '?')"

# ---- 2. 自启配置（不覆盖已有）----
if [ -f "$ENV_FILE" ]; then
  log "已存在 $ENV_FILE，保留不覆盖"
else
  mkdir -p "$(dirname "$ENV_FILE")"
  sed -e "s#\\\$HOME#$HOME#g" -e "s#^PIWEB_PORT=.*#PIWEB_PORT=\"$PIWEB_PORT\"#" \
      -e "s#^PIWEB_CWD=.*#PIWEB_CWD=\"$PIWEB_CWD\"#" \
      "$SCRIPT_DIR/pi-web-ui.env.example" > "$ENV_FILE"
  log "已生成 $ENV_FILE（如需口令/端口请自行编辑）"
fi

# ---- 3. 部署自启脚本 ----
mkdir -p "$STARTD_DIR"
install -m 0755 "$SCRIPT_DIR/start.d-pi-web-ui.sh" "$STARTD_DIR/pi-web-ui.sh"
log "已部署自启脚本到 $STARTD_DIR/pi-web-ui.sh"

# ---- 4. 写动态白名单到 .bashrc（手动前台启动也生效）----
BASHRC="$HOME/.bashrc"
MARK="# >>> pi-web-ui dynamic host allow-list >>>"
if [ -f "$BASHRC" ] && grep -qF "$MARK" "$BASHRC"; then
  log ".bashrc 已有白名单块，跳过"
else
  cat >> "$BASHRC" <<'EOF'

# >>> pi-web-ui dynamic host allow-list >>>
# 实例 ID 每次重建容器都会变，按当前 XGC_INSTANCE_ID 动态生成，别写死。
if [ -n "${XGC_INSTANCE_ID:-}" ]; then
  _piweb_domain="${XGC_INSTANCE_ID}-8787.container.x-gpu.com"
  export PI_WEB_ALLOW_HOSTS="${_piweb_domain},localhost,127.0.0.1"
  export PI_WEB_ALLOW_ORIGINS="https://${_piweb_domain},http://${_piweb_domain},http://localhost:8787,http://127.0.0.1:8787"
  unset _piweb_domain
else
  export PI_WEB_ALLOW_HOSTS="localhost,127.0.0.1"
  export PI_WEB_ALLOW_ORIGINS="http://localhost:8787,http://127.0.0.1:8787"
fi
# <<< pi-web-ui dynamic host allow-list <<<
EOF
  log "已写入 $BASHRC 动态白名单块"
fi

# ---- 5. 启动 ----
log "启动服务…"
bash "$STARTD_DIR/pi-web-ui.sh" || true

cat <<EOF

[install] 完成。
  访问地址 : $(cat "$HOME/.pi-web-ui.url" 2>/dev/null || echo '见 /var/log/pi-web.log')
  看日志   : tail -f /var/log/pi-web.log
  进现场   : screen -r piweb
  备份配置 : bash "$SCRIPT_DIR/pi-web-config-tool.sh" backup
EOF
