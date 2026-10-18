#!/usr/bin/env bash
# 烧录 BW16：擦除 + 写入 + 校验，全自动（不需要按任何按键）
#   bash flash.sh                     # 用 $BUILD_DIR/km0_km4_image2.bin
#   bash flash.sh /path/to/xxx.bin    # 指定固件
#   bash flash.sh --factory           # 刷回卖家英文固件（保底）
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/_env.sh"

[ -x "$FLASHTOOL/upload_image.exe" ] || { echo "!! 缺烧录器，先跑 setup.sh"; exit 1; }

case "${1:-}" in
    --factory) BIN="$BUILD_DIR/factory_en_backup.bin" ;;
    "")        BIN="$BUILD_DIR/km0_km4_image2.bin" ;;
    *)         BIN="$1" ;;
esac
[ -s "$BIN" ] || { echo "!! 找不到固件: $BIN（先跑 build.sh）"; exit 1; }

PORT="$(bw16_find_port)" || exit 1
echo "== 设备 $PORT   固件 $BIN ($(stat -c%s "$BIN") 字节)"

cp -f "$BIN" "$FLASHTOOL/km0_km4_image2.bin"
cd "$FLASHTOOL"

echo "== 步骤 1/2  擦除 flash + 送 download bootloader"
./upload_image_tool_windows.exe ./ "$PORT" Ai-Thinker_BW16 Enable Enable 1500000 2>&1 | tail -6

echo "== 步骤 2/2  写入镜像并校验"
out="$(./upload_image.exe ./ "$PORT" 2>&1)"
echo "$out" | tail -14

if echo "$out" | grep -qE "verifying.*ok"; then
    echo "== 烧录成功 ✅"
else
    echo "== !! 烧录失败（没看到 verifying ... ok）"
    echo "   常见原因：串口被别的程序占用 / 不是 BW16 / 没进下载模式"
    exit 1
fi
