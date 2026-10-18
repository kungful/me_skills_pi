#!/usr/bin/env bash
# 共用环境解析 —— 其他脚本 source 本文件
# 用法: . "$(dirname "$0")/_env.sh"
# 注意：本文件是库，**不设置 shell 选项**（否则二次 source 会覆盖调用方的 set -e/-u）

# ---------- BW16_HOME：优先复用已装好的，否则用 ~/.bw16 ----------
if [ -z "${BW16_HOME:-}" ]; then
    for cand in "$HOME/Documents/备份代码/bw16" "$HOME/bw16" "$HOME/.bw16"; do
        if [ -d "$cand/toolchain/arduino15" ]; then BW16_HOME="$cand"; break; fi
    done
fi
: "${BW16_HOME:=$HOME/.bw16}"
export BW16_HOME

export ARDUINO_DIRECTORIES_DATA="$BW16_HOME/toolchain/arduino15"
export ARDUINO_DIRECTORIES_USER="$BW16_HOME/toolchain/sketchbook"
export ARDUINO_DIRECTORIES_DOWNLOADS="$ARDUINO_DIRECTORIES_DATA/staging"

# arduino-cli 可执行文件
if   [ -x "$BW16_HOME/toolchain/arduino-cli/arduino-cli.exe" ]; then export CLI="$BW16_HOME/toolchain/arduino-cli/arduino-cli.exe"
elif [ -x "$BW16_HOME/toolchain/arduino-cli/arduino-cli" ];     then export CLI="$BW16_HOME/toolchain/arduino-cli/arduino-cli"
else export CLI="$BW16_HOME/toolchain/arduino-cli/arduino-cli.exe"; fi

export FLASHTOOL="$BW16_HOME/flashtool"
export BUILD_DIR="$BW16_HOME/build"
export FQBN="realtek:AmebaD:Ai-Thinker_BW16"
export SKETCH="${SKETCH:-$ARDUINO_DIRECTORIES_USER/BW16-Tools}"
export PORT="${PORT:-}"

# 镜像（GitHub 被墙时用）
export MIRRORS=("https://ghfast.top/" "https://ghproxy.net/" "https://gh-proxy.com/")

# ---------------------------------------------------------------- 工具函数

# 找一个【真正的】python：跳过 Microsoft Store 的 WindowsApps 占位 stub（它建不了 venv）
bw16_find_python() {
    local c la
    for c in "$BW16_HOME/pyenv/Scripts/python.exe" "$BW16_HOME/pyenv/bin/python"; do
        [ -x "$c" ] && { echo "$c"; return 0; }
    done
    if command -v py >/dev/null 2>&1; then
        la="$(py -3 -c 'import sys;print(sys.executable)' 2>/dev/null | tr -d '\r')"
        if [ -n "$la" ] && [ -x "$la" ]; then echo "$la"; return 0; fi
    fi
    for c in "${LOCALAPPDATA:-$HOME/AppData/Local}"/Programs/Python/Python3*/python.exe; do
        [ -x "$c" ] && { echo "$c"; return 0; }
    done
    for c in $(command -v python3 python python.exe 2>/dev/null); do
        case "$c" in *WindowsApps*|*windowsapps*) continue ;; esac
        [ -x "$c" ] && { echo "$c"; return 0; }
    done
    return 1
}

if [ -z "${PY:-}" ]; then
    PY="$(bw16_find_python)" || PY="python"
fi
export PY

# 带镜像回退的下载： gh_download <github原始url> <输出文件>
gh_download() {
    local url="$1" out="$2" m
    for m in "${MIRRORS[@]}"; do
        if curl -fsSL --max-time 900 -o "$out" "${m}${url}" 2>/dev/null && [ -s "$out" ]; then
            echo "   [下载OK] ${m}${url}" >&2
            return 0
        fi
    done
    if curl -fsSL --max-time 900 -o "$out" "$url" 2>/dev/null && [ -s "$out" ]; then
        return 0
    fi
    echo "   [下载失败] $url" >&2
    return 1
}

# 找一个 CH340 串口；优先 PORT 环境变量
bw16_find_port() {
    if [ -n "${PORT:-}" ]; then echo "$PORT"; return 0; fi
    local p
    p=$(powershell -NoProfile -Command \
        "(Get-CimInstance Win32_PnPEntity | Where-Object { \$_.PNPDeviceID -like '*VID_1A86*' } | ForEach-Object { \$_.Name })" \
        2>/dev/null | tr -d '\r' | grep -oE 'COM[0-9]+' | head -1) || true
    if [ -n "$p" ]; then echo "$p"; return 0; fi
    echo "!! 没找到 CH340 设备（VID_1A86）。检查 USB 线和 CH340 驱动。" >&2
    echo "!! 当前所有串口：" >&2
    powershell -NoProfile -Command \
        "(Get-CimInstance Win32_PnPEntity | Where-Object { \$_.Name -match '\(COM[0-9]+\)' } | ForEach-Object { \$_.Name })" \
        2>/dev/null | tr -d '\r' | sed 's/^/     /' >&2 || true
    return 1
}
