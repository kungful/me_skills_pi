#!/usr/bin/env bash
# BW16 工具链一键搭建（幂等：已装的部分自动跳过）
#   bash setup.sh            # 补齐所有缺失组件
#   bash setup.sh --force    # 忽略已有安装重新拉一遍
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/_env.sh"
FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

CORE_VER="3.1.7-build20240216"
CORE_FILE="ameba_d-3.1.7-build20240216.tar.gz"
CORE_SHA="80d0fdf4bafee466f9b8ed45b2133b1900a46b0a744fbf105563b4e0ea8bc8e2"
TC_FILE="ameba_d_toolchain_windows-1.0.1.tar.bz2"
TC_SHA="1157b225e207bcf4703aaeb42acbb4b10d1c0efa0696005d2e000866ba1249f0"
TL_FILE="ameba_d_tools_windows-1.1.3.tar.gz"
TL_SHA="e864b707aa9794b7530d6c5913ceacf67930b3dd64a92953ca029e8a136df2c9"
REL="https://github.com/Ameba-AIoT/ameba-arduino-d/raw/dev/Arduino_package/release"
INDEX_URL="file:///$HERE/../assets/package_realtek_amebad_index.json"
FLASHTOOL_ZIP_URL="https://github.com/xwd0/bw16-flash-tool/releases/download/release_v1.0/BW16-flash-tool_win_v1.3.zip"

ok()   { echo "  [OK]   $*"; }
skip() { echo "  [skip] $*"; }
info() { echo "== $*"; }

sha256_of() {
    if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1
    else "$PY" -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$1"; fi
}

mkdir -p "$BW16_HOME" "$ARDUINO_DIRECTORIES_DATA/staging/packages" \
         "$ARDUINO_DIRECTORIES_USER/libraries" "$BUILD_DIR" "$BW16_HOME/pyenv"

# ---------------------------------------------------------------- 1. arduino-cli
info "1/6 arduino-cli"
if [ -x "$CLI" ] && [ "$FORCE" = 0 ]; then skip "已有 $CLI"
else
    mkdir -p "$BW16_HOME/toolchain/arduino-cli"
    tmp="$BW16_HOME/toolchain/arduino-cli.zip"
    echo "  从 downloads.arduino.cc 下载..."
    curl -fsSL --max-time 900 -o "$tmp" \
        "https://downloads.arduino.cc/arduino-cli/arduino-cli_latest_Windows_64bit.zip" \
      || { echo "!! 下载失败"; exit 1; }
    "$PY" -c "import zipfile,sys;zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
        "$tmp" "$BW16_HOME/toolchain/arduino-cli"
    rm -f "$tmp"
    ok "装好 $( ("$CLI" version 2>/dev/null | head -1) || echo arduino-cli )"
fi

# ------------------------------------------------- 2. AmebaD 内核（含工具链）
info "2/6 AmebaD 内核 $CORE_VER"
if [ -d "$ARDUINO_DIRECTORIES_DATA/packages/realtek/hardware/AmebaD/$CORE_VER" ] && [ "$FORCE" = 0 ]; then
    skip "已有 $CORE_VER"
else
    for pair in "$CORE_FILE|$CORE_SHA|$REL" "$TC_FILE|$TC_SHA|$REL" "$TL_FILE|$TL_SHA|$REL"; do
        IFS='|' read -r f s base <<< "$pair"
        dst="$ARDUINO_DIRECTORIES_DATA/staging/packages/$f"
        if [ -s "$dst" ] && [ "$(sha256_of "$dst")" = "$s" ]; then skip "$f 已在 staging"; continue; fi
        echo "  取 $f"
        gh_download "$base/$f" "$dst" || exit 1
        got="$(sha256_of "$dst")"
        [ "$got" = "$s" ] && ok "$f 校验通过" || { echo "!! $f 校验失败"; exit 1; }
    done
    cp -f "$HERE/../assets/package_realtek_amebad_index.json" \
          "$ARDUINO_DIRECTORIES_DATA/package_realtek_amebad_index.json"
    "$CLI" config set library.enable_unsafe_install true >/dev/null 2>&1 || true
    echo "  安装内核（离线暂存已命中，不会去连 GitHub）..."
    "$CLI" core install "realtek:AmebaD@$CORE_VER" --additional-urls "$INDEX_URL" 2>&1 \
        | grep -viE "^\s*INFO|Checking signature" | tail -6
    [ -d "$ARDUINO_DIRECTORIES_DATA/packages/realtek/hardware/AmebaD/$CORE_VER" ] \
        && ok "内核装好" || { echo "!! 内核安装失败"; exit 1; }
fi

# ------------------------------------------------------------ 3. sketch 源码
info "3/6 BW16-Tools 源码"
if [ -s "$SKETCH/BW16-Tools.ino" ] && [ "$FORCE" = 0 ]; then skip "已有 $SKETCH"
else
    tmpd="$BW16_HOME/.src-tmp"; rm -rf "$tmpd"; mkdir -p "$tmpd"
    cloned=0
    for g in "https://gitclone.com/github.com/FlyingIceyyds/BW16-Tools" \
             "https://gitee.com/mirrors_FlyingIceyyds/BW16-Tools" \
             "https://github.com/FlyingIceyyds/BW16-Tools"; do
        echo "  尝试 git clone $g"
        if git clone --depth 1 -q "$g" "$tmpd/BW16-Tools" 2>/dev/null; then cloned=1; break; fi
        rm -rf "$tmpd/BW16-Tools"
    done
    [ "$cloned" = 1 ] || { echo "!! 源码 clone 失败，请手动放置到 $SKETCH"; exit 1; }
    rm -rf "$SKETCH"; mkdir -p "$(dirname "$SKETCH")"
    cp -r "$tmpd/BW16-Tools/src/BW16-Tools" "$SKETCH"
    ok "源码 $(find "$SKETCH" -type f | wc -l) 个文件"
fi

# -------------------------------------------------------------- 4. 依赖库
info "4/6 Arduino 依赖库"
lidir="$ARDUINO_DIRECTORIES_USER/libraries"
need_libs=1
for L in Adafruit_BusIO Adafruit_GFX_Library Adafruit_SSD1306 U8g2_for_Adafruit_GFX; do
    ls -d "$lidir/$L"* >/dev/null 2>&1 || { need_libs=0; break; }
done
if [ "$need_libs" = 1 ] && [ "$FORCE" = 0 ]; then skip "4 个库都在"
else
    zdir=""
    for c in "$BW16_HOME/.src-tmp/BW16-Tools/libraries" "$BW16_HOME/recovery/BW16-Tools/libraries"; do
        [ -d "$c" ] && { zdir="$c"; break; }
    done
    [ -n "$zdir" ] || { echo "  本地没有库 zip，重新 clone 取...";
        tmpd="$BW16_HOME/.src-tmp"; mkdir -p "$tmpd"
        git clone --depth 1 -q "https://gitclone.com/github.com/FlyingIceyyds/BW16-Tools" "$tmpd/BW16-Tools" 2>/dev/null || true
        zdir="$tmpd/BW16-Tools/libraries"; }
    [ -d "$zdir" ] || { echo "!! 拿不到依赖库"; exit 1; }
    for f in "$zdir"/*.zip; do
        echo "  装 $(basename "$f")"
        "$CLI" lib install --zip-path "$f" 2>&1 | grep -viE "^\s*INFO" | tail -1
    done
    ok "库安装完成"
fi

# ------------------------------------------------------------- 5. 烧录工具
info "5/6 烧录器（卖家工具包）"
if [ -x "$FLASHTOOL/upload_image.exe" ] && [ "$FORCE" = 0 ]; then skip "已有 $FLASHTOOL"
else
    for c in "$BW16_HOME/recovery/win_tool/tool" "$BW16_HOME/recovery"; do
        if [ -x "$c/upload_image.exe" ]; then
            mkdir -p "$FLASHTOOL"; cp -rf "$c"/* "$FLASHTOOL"/ 2>/dev/null || true
            break
        fi
    done
    if [ ! -x "$FLASHTOOL/upload_image.exe" ]; then
        z="$BW16_HOME/toolchain/win-flashtool.zip"
        echo "  下载卖家工具包（6.5MB）..."
        gh_download "$FLASHTOOL_ZIP_URL" "$z" || exit 1
        t="$BW16_HOME/.wtmp"; rm -rf "$t"; mkdir -p "$t"
        "$PY" -c "import zipfile,sys;zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$z" "$t"
        mkdir -p "$FLASHTOOL"; cp -rf "$t/tool"/* "$FLASHTOOL"/
        rm -rf "$t" "$z"
    fi
    [ -x "$FLASHTOOL/upload_image.exe" ] && ok "烧录器就绪" || { echo "!! 烧录器缺失"; exit 1; }
fi
# 卖家包里自带的英文固件留着当「保底固件」
[ -s "$FLASHTOOL/km0_km4_image2.bin" ] && cp -f "$FLASHTOOL/km0_km4_image2.bin" "$BUILD_DIR/factory_en_backup.bin" || true

# ------------------------------------------------------------- 6. python 环境
info "6/6 python + pyserial"
if "$PY" -c "import serial" 2>/dev/null; then skip "pyserial 可用（$PY）"
else
    pv="$BW16_HOME/pyenv"
    if [ ! -x "$pv/Scripts/python.exe" ] && [ ! -x "$pv/bin/python" ]; then
        basepy="$(bw16_find_python)" || { echo "!! 找不到可用的 python（Store 的 WindowsApps 占位不行）"; exit 1; }
        echo "  用 $basepy 创建 venv"
        # 原生 python.exe 认不得 /c/... 这种 MSYS 路径，先转成 Windows 路径
        pv_arg="$pv"
        if command -v cygpath >/dev/null; then pv_arg="$(cygpath -w "$pv")"; fi
        "$basepy" -m venv "$pv_arg" 2>&1 | tail -3 || true
    fi
    if   [ -x "$pv/Scripts/python.exe" ]; then PY="$pv/Scripts/python.exe"
    elif [ -x "$pv/bin/python" ];        then PY="$pv/bin/python"
    fi
    echo "  用 $PY 装 pyserial"
    "$PY" -m pip install -q pyserial 2>&1 | tail -2 || true
    "$PY" -c "import serial" 2>/dev/null && ok "pyserial 装好" || echo "!! pyserial 未装（verify.py 会不可用）"
fi

echo
info "全部就绪"
cat <<EOF
  BW16_HOME      = $BW16_HOME
  arduino-cli    = $CLI
  内核           = $CORE_VER
  sketch         = $SKETCH
  烧录器         = $FLASHTOOL
  产物目录       = $BUILD_DIR
  串口           = $(PORT="${PORT:-}" bw16_find_port 2>/dev/null || echo "未检测到")
EOF
