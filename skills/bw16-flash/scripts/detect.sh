#!/usr/bin/env bash
# 识别接上的 BW16 设备：串口、芯片、当前固件状态
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/_env.sh"

echo "== 1. 所有串口"
powershell -NoProfile -Command \
  "chcp 65001 | Out-Null; Get-CimInstance Win32_PnPEntity | Where-Object { \$_.Name -match '\(COM[0-9]+\)' } | ForEach-Object { \$_.Name + '  ||  ' + \$_.PNPDeviceID }" \
  2>/dev/null | tr -d '\r' | sed 's/^/   /' || true
echo "   （VID_1A86:PID_7523 = CH340，是 BW16 的桥接芯片）"
echo "   （ACPI\\PNP0501 = 主板自带串口，不是设备）"

echo
echo "== 2. 判定"
P="$(bw16_find_port)" || exit 1
echo "   CH340 串口: $P"
echo "   芯片: Realtek RTL8720DN (AmebaD) —— 不是 ESP，esptool 连不上"

echo
echo "== 3. 读启动日志"
"$PY" "$HERE/verify.py" "$P" 8
rc=$?
echo
case $rc in
    0) echo "== 设备可用 ✅";;
    1) echo "== 有问题，见上面判定（多数情况直接 bash flash.sh 能解决）";;
    *) echo "== 读不到设备";;
esac
exit $rc
