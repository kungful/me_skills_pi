#!/bin/bash
# ==============================================================================
#  pi-web-ui 开机自启（部署到 /scripts/start.d/pi-web-ui.sh）
#  入口：/scripts/start.sh 遍历 /scripts/start.d/* ，chmod +x 后逐个后台执行。
#  本环境没有 systemd，`pi-web-ui server install` 只会写 systemd unit，一定失败。
#
#  三个坑（本脚本已处理）：
#    1) pi-web-ui 装在 node 全局 bin（如 /usr/local/nodejs/bin），该目录只在 .bashrc
#       里进 PATH；start.d 是非交互 shell，不读 .bashrc → 必须用绝对路径。
#    2) 公网域名 = ${XGC_INSTANCE_ID}-<port>.container.x-gpu.com，实例 ID 每次重建容器
#       都会变；写死白名单重启后就过期，直接报 "host not allowed"。这里动态生成。
#    3) 不能用 `bash -lc` 起服务：登录 shell 会 source ~/.bashrc 里可能过期的白名单。
#       必须用非登录 shell `bash -c`。
#
#  日常：screen -r piweb | screen -S piweb -X quit | bash <本脚本> 手动重启
# ==============================================================================

# ---- 默认配置：/scripts/pi-web-ui.env 里的值会覆盖这些 ----
PIWEB_BIN="${PIWEB_BIN:-/usr/local/nodejs/bin/pi-web-ui}"
PIWEB_PORT="${PIWEB_PORT:-8787}"
PIWEB_HOST="${PIWEB_HOST:-0.0.0.0}"
PIWEB_CWD="${PIWEB_CWD:-$HOME}"
PIWEB_SCREEN="${PIWEB_SCREEN:-piweb}"
PIWEB_LOG="${PIWEB_LOG:-/var/log/pi-web.log}"
PIWEB_ENV_FILE="${PIWEB_ENV_FILE:-/scripts/pi-web-ui.env}"
PIWEB_URL_FILE="${PIWEB_URL_FILE:-$HOME/.pi-web-ui.url}"
PIWEB_LOG_MAX_BYTES="${PIWEB_LOG_MAX_BYTES:-$((5 * 1024 * 1024))}"

# ---- 载入外部配置（token / 端口 / 工作目录）----
# shellcheck disable=SC1090
[ -f "$PIWEB_ENV_FILE" ] && . "$PIWEB_ENV_FILE"

# ---- 补 PATH（坑 1）----
export PATH="$(dirname "$PIWEB_BIN"):$PATH"

# ---- 按当前实例 ID 动态重建域名白名单（坑 2）----
XGPU_DOMAIN=""
if [ -n "${XGC_INSTANCE_ID:-}" ]; then
  XGPU_DOMAIN="${XGC_INSTANCE_ID}-${PIWEB_PORT}.container.x-gpu.com"
fi

if [ -n "$XGPU_DOMAIN" ]; then
  export PI_WEB_ALLOW_HOSTS="$XGPU_DOMAIN,localhost,127.0.0.1"
  export PI_WEB_ALLOW_ORIGINS="https://$XGPU_DOMAIN,http://$XGPU_DOMAIN,http://localhost:${PIWEB_PORT},http://127.0.0.1:${PIWEB_PORT}"
else
  export PI_WEB_ALLOW_HOSTS="localhost,127.0.0.1"
  export PI_WEB_ALLOW_ORIGINS="http://localhost:${PIWEB_PORT},http://127.0.0.1:${PIWEB_PORT}"
fi

# ---- 重复启动保护：start.d 会被反复触发，必须幂等 ----
if pgrep -f "pi-web-ui .*--port ${PIWEB_PORT}" >/dev/null 2>&1; then
  echo "[pi-web-ui] 已有实例在跑（端口 ${PIWEB_PORT}），跳过自启。"
  exit 0
fi
if ss -ltn 2>/dev/null | grep -q ":${PIWEB_PORT}[[:space:]]"; then
  echo "[pi-web-ui] 端口 ${PIWEB_PORT} 已被占用，跳过自启。"
  exit 0
fi

# 清掉上次残留的死 screen 会话
screen -S "$PIWEB_SCREEN" -X quit >/dev/null 2>&1
screen -wipe >/dev/null 2>&1

# ---- 前置检查 ----
if [ ! -x "$PIWEB_BIN" ]; then
  echo "[pi-web-ui] 找不到可执行文件：$PIWEB_BIN（npm 全局安装可能失败）" >&2
  exit 0
fi
if [ ! -d "$PIWEB_CWD" ]; then
  echo "[pi-web-ui] 工作目录不存在：$PIWEB_CWD" >&2
  exit 0
fi

# ---- 日志：轮转 + 收紧权限（里面有 token 和访问地址）----
mkdir -p "$(dirname "$PIWEB_LOG")"
if [ -f "$PIWEB_LOG" ] && [ "$(stat -c%s "$PIWEB_LOG" 2>/dev/null || echo 0)" -gt "$PIWEB_LOG_MAX_BYTES" ]; then
  mv -f "$PIWEB_LOG" "${PIWEB_LOG}.1"
fi
touch "$PIWEB_LOG"
chmod 600 "$PIWEB_LOG"

# ---- 组装访问地址，落盘，省得下次翻历史 ----
if [ -n "$XGPU_DOMAIN" ]; then
  PIWEB_URL="http://${XGPU_DOMAIN}:${PIWEB_PORT}/"
else
  PIWEB_URL="http://localhost:${PIWEB_PORT}/"
fi
[ -n "${PI_WEB_TOKEN:-}" ] && PIWEB_URL="${PIWEB_URL}?token=${PI_WEB_TOKEN}"
printf '%s\n' "$PIWEB_URL" > "$PIWEB_URL_FILE"
chmod 600 "$PIWEB_URL_FILE"

{
  echo ""
  echo "===== pi-web-ui 自启 $(date '+%F %T') ====="
  echo "实例 ID   : ${XGC_INSTANCE_ID:-（无，非平台环境）}"
  echo "访问地址  : $PIWEB_URL"
  echo "允许域名  : $PI_WEB_ALLOW_HOSTS"
  echo "工作目录  : $PIWEB_CWD"
  echo "日志      : $PIWEB_LOG"
  echo "进现场    : screen -r $PIWEB_SCREEN"
  echo "-------------------------------------------"
} >> "$PIWEB_LOG"

# ---- 拉起（坑 3：非登录 shell bash -c）----
screen -dmS "$PIWEB_SCREEN" bash -c \
  "exec '$PIWEB_BIN' --host '$PIWEB_HOST' --port '$PIWEB_PORT' --cwd '$PIWEB_CWD' --no-browser >>'$PIWEB_LOG' 2>&1"

# ---- 起后自检：只看 HTTP 有没有应答（带 token 时 /api/health 401 也算活着）----
for _ in 1 2 3 4 5 6 7 8 9 10; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "http://127.0.0.1:${PIWEB_PORT}/" 2>/dev/null)
  if [ -n "$code" ] && [ "$code" != "000" ]; then
    echo "[pi-web-ui] 已启动：$PIWEB_URL"
    echo "[pi-web-ui] 地址已写入 $PIWEB_URL_FILE"
    exit 0
  fi
  sleep 1
done

echo "[pi-web-ui] 起来后 10 秒仍未响应，请进现场排查：screen -r $PIWEB_SCREEN" >&2
exit 0
