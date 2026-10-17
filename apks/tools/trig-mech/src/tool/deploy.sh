#!/usr/bin/env bash
# 一键部署到手机（USB 或无线调试都行）
#   bash tool/deploy.sh          编译 + 安装 + 启动
#   bash tool/deploy.sh --list   只看连了哪些设备
#   D=192.168.31.200:45115 bash tool/deploy.sh   指定设备
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PKG=com.hua.trigmech

ADB="${ADB:-}"
if [ -z "$ADB" ]; then
  for c in "$HOME/Documents/platform-tools/adb" "$HOME/AppData/Local/Android/Sdk/platform-tools/adb" adb; do
    if command -v "$c" >/dev/null 2>&1 || [ -x "$c" ]; then ADB="$c"; break; fi
  done
fi
[ -n "$ADB" ] || { echo "找不到 adb，用 ADB=/path/to/adb 指定"; exit 1; }

# 无线调试端口会变，用 mDNS 自己找
find_dev() {
  "$ADB" devices | awk 'NR>1 && $2=="device" {print $1; exit}'
}

if [ "${1:-}" = "--list" ]; then
  echo "已连接:"; "$ADB" devices | tr -d '\r'
  echo "mDNS 发现:"; "$ADB" mdns services 2>/dev/null | tr -d '\r' | grep adb-tls-connect || true
  exit 0
fi

DEV="${D:-$(find_dev)}"
if [ -z "$DEV" ]; then
  echo "没有可用设备，试着自己连一下："
  "$ADB" mdns services 2>/dev/null | tr -d '\r' | grep adb-tls-connect || echo "  (mDNS 也没发现，确认手机开着「无线调试」且和电脑同一 WiFi)"
  for hp in $("$ADB" mdns services 2>/dev/null | tr -d '\r' | awk '/adb-tls-connect/{print $3}'); do
    echo "  尝试 adb connect $hp"; "$ADB" connect "$hp" >/dev/null 2>&1
    DEV="$(find_dev)"; [ -n "$DEV" ] && break
  done
fi
[ -n "$DEV" ] || { echo "还是没连上。手机解锁、保持亮屏，再跑一次。"; exit 2; }
echo "设备: $DEV"

bash "$ROOT/tool/build.sh" || exit 1
APK="$(ls -t "$ROOT"/dist/*.apk | head -1)"
echo "安装: $(basename "$APK")"
"$ADB" -s "$DEV" install -r -d "$APK" 2>&1 | tr -d '\r' | grep -v "^$"
"$ADB" -s "$DEV" shell am force-stop "$PKG"
"$ADB" -s "$DEV" shell am start -n "$PKG/.MainActivity" >/dev/null 2>&1
sleep 1
"$ADB" -s "$DEV" logcat -d -t 200 2>/dev/null | grep -iE "FATAL EXCEPTION|$PKG.*(crash|Error)" | tr -d '\r' | head -5
echo "已启动。看日志: $ADB -s $DEV logcat | grep -i trigmech"
