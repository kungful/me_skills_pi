#!/usr/bin/env bash
# 一键打包 + 安装到手机
#
#   用法：
#     bash tools/install.sh              # 打 release 包并安装
#     bash tools/install.sh debug        # 打 debug 包并安装
#     bash tools/install.sh release w    # 只打包，不安装（w = wifi 安装提示）
#
# 手机没连上时会把 APK 路径打印出来，可以手动拷进手机点安装。

set -e
cd "$(dirname "$0")/.."

VARIANT="${1:-release}"
ADB="${ADB:-$HOME/Documents/platform-tools/adb.exe}"
[ -x "$ADB" ] || ADB="adb"

if [ "$VARIANT" = "debug" ]; then
  TASK=":app:assembleDebug"
  APK="app/build/outputs/apk/debug/app-debug.apk"
else
  TASK=":app:assembleRelease"
  APK="app/build/outputs/apk/release/app-release.apk"
fi

echo "==> 打包 $VARIANT ..."
./gradlew "$TASK" --offline --console=plain

echo
echo "==> APK: $(pwd)/$APK"
ls -lh "$APK"

echo
echo "==> 检查设备 ..."
"$ADB" start-server >/dev/null 2>&1 || true
DEV=$("$ADB" devices | awk 'NR>1 && $2=="device" {print $1; exit}')

if [ -z "$DEV" ]; then
  echo
  echo "！！没有检测到已授权的设备。"
  echo
  echo "   USB 方式：插上数据线 -> 手机弹「允许 USB 调试」-> 点允许 -> 重跑本脚本"
  echo "   无线方式：手机【开发者选项 -> 无线调试】-> 用配对码配对："
  echo "       $ADB pair <手机IP:配对端口>"
  echo "       出现 Enter pairing code: 时输入手机上的 6 位配对码"
  echo "     配对成功后再连接（端口用「无线调试」页面上那个，不是配对端口）："
  echo "       $ADB connect <手机IP:端口>"
  echo
  echo "   也可以把 APK 直接拷到手机上手动安装："
  echo "       $(pwd)/$APK"
  exit 0
fi

echo "==> 安装到 $DEV ..."
"$ADB" -s "$DEV" install -r -d "$APK"

echo "==> 启动 ..."
"$ADB" -s "$DEV" shell monkey -p com.wordrush.app -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1 || true
echo "==> 完成"
