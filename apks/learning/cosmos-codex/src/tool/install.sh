#!/usr/bin/env bash
# 安装到手机：优先 USB，其次无线调试
#   bash tool/install.sh              # 插着 USB 直接装
#   bash tool/install.sh 192.168.31.50:37xxx        # 已配对过的无线调试
#   bash tool/install.sh pair 192.168.31.50:37xxx 123456   # 首次配对
set -euo pipefail
ROOT="C:/Users/hua/Documents/备份代码/CosmosCodex"
APK="$ROOT/dist/万物原理.apk"

if [ "${1:-}" = "pair" ]; then
  echo "配对 $2 ..."
  adb pair "$2" "${3:?需要配对码}"
  exit 0
fi

if [ -n "${1:-}" ]; then
  echo "连接 $1 ..."
  adb connect "$1"
  sleep 2
fi

echo "=== 设备列表 ==="
adb devices -l
if ! adb devices | grep -q "device$"; then
  echo "❌ 没有可用设备。请插上 USB，或先在手机上打开【开发者选项 → 无线调试】"
  exit 1
fi

echo "=== 安装 ==="
adb install -r -d "$APK"
echo "=== 启动 ==="
adb shell am start -n com.hua.cosmos/.MainActivity
echo "✅ 已安装并启动：万物原理"
