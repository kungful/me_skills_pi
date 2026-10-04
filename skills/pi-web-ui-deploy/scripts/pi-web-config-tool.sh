#!/bin/bash
# ==============================================================================
#  pi-web-ui / pi agent 配置备份与恢复
#  用途：升级或重建容器后模型配置若被打乱，可一键恢复到已知状态。
#  用法：
#    bash pi-web-config-tool.sh backup            # 备份当前配置
#    bash pi-web-config-tool.sh restore           # 从最近一次备份恢复
#    bash pi-web-config-tool.sh restore <目录>     # 从指定备份目录恢复
#    bash pi-web-config-tool.sh list              # 列出所有备份
#  恢复前会先把「当前状态」也备份一次，防止覆盖后无法回退。
#  路径遵循 pi 的默认/环境变量：
#    agentDir = $PI_CODING_AGENT_DIR 或 $HOME/.pi/agent
#    dataDir  = $PI_WEB_DATA_DIR    或 $HOME/.pi-web
# ==============================================================================
set -euo pipefail

BACKUP_ROOT="${PIWEB_BACKUP_ROOT:-$HOME/pi-web-config-backups}"
AGENT_DIR="${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"
WEB_DIR="${PI_WEB_DATA_DIR:-$HOME/.pi-web}"

AGENT_FILES="models.json provider-keys.json auth.json models-store.json settings.json"
WEB_FILES="client-state.json subagent-templates.seeded.json approval-rules.seeded.json plans.json composer-drafts.json"

backup() {
  local ts dest
  ts="$(date +%F_%H%M%S)"
  dest="$BACKUP_ROOT/$ts"
  mkdir -p "$dest/agent" "$dest/pi-web"
  for f in $AGENT_FILES; do
    [ -f "$AGENT_DIR/$f" ] && cp -a "$AGENT_DIR/$f" "$dest/agent/" || true
  done
  for f in $WEB_FILES; do
    [ -f "$WEB_DIR/$f" ] && cp -a "$WEB_DIR/$f" "$dest/pi-web/" || true
  done
  ln -sfn "$dest" "$BACKUP_ROOT/latest"
  echo "[backup] 已备份到 $dest"
  echo "  agent : $(ls "$dest/agent" 2>/dev/null | tr '\n' ' ')"
  echo "  pi-web: $(ls "$dest/pi-web" 2>/dev/null | tr '\n' ' ')"
}

restore() {
  local src="${1:-$BACKUP_ROOT/latest}"
  if [ ! -d "$src" ]; then
    echo "[restore] 找不到备份目录：$src" >&2
    exit 1
  fi
  echo "[restore] 先把当前状态另存一份，避免覆盖后无法回退…"
  backup >/dev/null
  for f in $AGENT_FILES; do
    [ -f "$src/agent/$f" ] && cp -a "$src/agent/$f" "$AGENT_DIR/$f" || true
  done
  for f in $WEB_FILES; do
    [ -f "$src/pi-web/$f" ] && cp -a "$src/pi-web/$f" "$WEB_DIR/$f" || true
  done
  echo "[restore] 已从 $src 恢复。"
  echo "[restore] 重启服务生效：bash /scripts/start.d/pi-web-ui.sh"
}

list_backups() {
  echo "[list] 备份目录：$BACKUP_ROOT"
  ls -1 "$BACKUP_ROOT" 2>/dev/null | grep -v '^latest$' || echo "  (还没有备份)"
}

case "${1:-backup}" in
  backup)  backup ;;
  restore) restore "${2:-}" ;;
  list)    list_backups ;;
  *) echo "用法: $0 {backup|restore [备份目录]|list}" ;;
esac
