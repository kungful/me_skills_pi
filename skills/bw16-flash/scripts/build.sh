#!/usr/bin/env bash
# 编译 BW16-Tools sketch -> $BUILD_DIR/km0_km4_image2.bin
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/_env.sh"

[ -x "$CLI" ] || { echo "!! 没有 arduino-cli，先跑 setup.sh"; exit 1; }
[ -s "$SKETCH/BW16-Tools.ino" ] || { echo "!! 找不到 sketch: $SKETCH"; exit 1; }

echo "== 编译 $SKETCH"
echo "   内核目录 $ARDUINO_DIRECTORIES_DATA/packages/realtek/hardware/AmebaD"
mkdir -p "$BUILD_DIR/arduino"

log="$BUILD_DIR/compile.log"
"$CLI" compile --fqbn "$FQBN" "$SKETCH" --warnings none \
       --build-path "$BUILD_DIR/arduino" >"$log" 2>&1
st=$?

grep -iE "^\S*error|Error during build" "$log" | grep -v "Werror" | head -20
grep -E "Sketch uses" "$log" | head -1

[ $st -ne 0 ] && { echo "!! 编译失败，完整日志: $log"; exit 1; }

# AmebaD 的 post-objcopy 钩子会把 bin 拷到 build.path
SRC="$BUILD_DIR/arduino/km0_km4_image2.bin"
if [ ! -s "$SRC" ]; then
    # 兜底：去 arduino 的 sketches 缓存里找最新的
    cache="$(cygpath -u "${LOCALAPPDATA:-$HOME/AppData/Local}" 2>/dev/null || echo "$HOME/AppData/Local")/arduino/sketches"
    SRC="$(find "$cache" -name km0_km4_image2.bin -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)"
fi
[ -s "$SRC" ] || { echo "!! 编译过了但找不到 km0_km4_image2.bin"; exit 1; }

cp -f "$SRC" "$BUILD_DIR/km0_km4_image2.bin"
echo "== 产物 $BUILD_DIR/km0_km4_image2.bin  ($(stat -c%s "$BUILD_DIR/km0_km4_image2.bin") 字节)"
for s in "BW16-Tools" "AP已重新拉起" "Deauth"; do
    printf "   含 %-14s : " "$s"
    grep -qa "$s" "$BUILD_DIR/km0_km4_image2.bin" && echo "是" || echo "否"
done
