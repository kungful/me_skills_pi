#!/usr/bin/env bash
# 把「脑图」界面插件装到本机 pi-web-ui：
#   ~/pi-mindmap-plugin                 代码副本（可改）
#   $DATA_DIR/plugins/mindmap -> 上面   宿主的插件目录（默认 ~/.pi-web/plugins）
#
# 用法：bash install.sh [目标目录]
set -euo pipefail

DATA_DIR="${PI_WEB_DATA_DIR:-$HOME/.pi-web}"
PLUGIN_DIR="${1:-$HOME/pi-mindmap-plugin}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$DATA_DIR/plugins"
if [ "$SRC_DIR" != "$PLUGIN_DIR" ]; then
	mkdir -p "$PLUGIN_DIR"
	cp -r "$SRC_DIR"/. "$PLUGIN_DIR"/
fi
ln -sfn "$PLUGIN_DIR" "$DATA_DIR/plugins/mindmap"

echo "已安装：$DATA_DIR/plugins/mindmap -> $PLUGIN_DIR"
echo "刷新浏览器（或 设置 › 界面插件 → 重新加载）后：顶栏多一个 🧠 脑图 tab，输入框控制条左侧多一个 🧠 脑图 按钮"
echo "AI 生成复用宿主自带 pi SDK CLI；找不到时用 PI_MINDMAP_PI_CLI 指定 cli.js 路径"
echo "单测：node --test $PLUGIN_DIR/tests/*.test.mjs"
