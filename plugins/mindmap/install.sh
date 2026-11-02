#!/usr/bin/env bash
# 把「脑图」界面插件装到本机 pi-web-ui：
#   ~/pi-mindmap-plugin                 代码副本（可改）
#   $DATA_DIR/plugins/mindmap -> 上面   宿主的插件目录（默认 ~/.pi-web/plugins）
#
# 用法：bash install.sh [目标目录]
#   PI_WEB_DATA_DIR=/path 可覆盖宿主数据目录（默认 ~/.pi-web）
set -euo pipefail

DATA_DIR="${PI_WEB_DATA_DIR:-$HOME/.pi-web}"
PLUGIN_DIR="${1:-$HOME/pi-mindmap-plugin}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "$PLUGIN_DIR" in
	"$SRC_DIR"|"$SRC_DIR"/*)
		echo "目标目录不能是源码目录本身或其子目录：$PLUGIN_DIR" >&2
		echo "用法：bash install.sh [目标目录]（默认 ~/pi-mindmap-plugin）" >&2
		exit 1
		;;
esac

mkdir -p "$DATA_DIR/plugins" "$PLUGIN_DIR"
if [ "$SRC_DIR" != "$PLUGIN_DIR" ]; then
	cp -r "$SRC_DIR"/. "$PLUGIN_DIR"/
	rm -f "$PLUGIN_DIR/.pi-approved"   # 宿主的权限批准缓存，跟机器相关
fi
ln -sfn "$PLUGIN_DIR" "$DATA_DIR/plugins/mindmap"

echo "已安装：$DATA_DIR/plugins/mindmap -> $PLUGIN_DIR"
echo "刷新浏览器（或 设置 › 界面插件 → 重新加载）后：顶栏多一个 🧠 脑图 tab，输入框控制条左侧多一个 🧠 脑图 按钮"
echo "AI 生成复用宿主自带 pi SDK CLI；找不到时用 PI_MINDMAP_PI_CLI 指定 cli.js 路径"
echo "单测：node --test $PLUGIN_DIR/tests/*.test.mjs"
