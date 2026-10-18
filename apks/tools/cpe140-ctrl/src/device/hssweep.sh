#!/bin/sh
# hssweep.sh — 逐信道跳频抓包；无论怎么退出，最后都恢复「老家能上网」。
# 用法: hssweep.sh <每信道停留秒> <信道...>
#   例: hssweep.sh 4 1 2 3 4 5 6 7 8 9 10 11 12 13
#       hssweep.sh 60 6          （只抓 6 信道 60 秒）
#
# 安全设计（三层）:
#   1) 本脚本 trap EXIT/INT/TERM -> 必定调用 /etc/hsrestore.sh
#   2) /etc/hssweep.state 标记 + /tmp/hssweep.pid；netguard（每 2 分钟）发现
#      标记还在但没有活进程 -> 立刻恢复
#   3) /etc/hsrestore.sh 内部：wifi 重启 x3 -> 网络栈重启 -> 重启设备（最后手段）
DWELL="$1"; [ -z "$DWELL" ] && DWELL=4
shift 2>/dev/null
CHS="$*"; [ -z "$CHS" ] && CHS="1 2 3 4 5 6 7 8 9 10 11 12 13"

OUT=/tmp/cap
LOG=/tmp/hssweep.log
mkdir -p "$OUT"
STAMP=$(date +%Y%m%d-%H%M%S)
CHMAP="$OUT/sw-$STAMP.chmap"   # 结束时改名为 sweep-<stamp>.chmap
export LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH
TD=/usr/bin/tcpdump

echo "sweep $STAMP dwell=${DWELL}s chs=[$CHS]" > "$LOG"
echo $$ > /tmp/hssweep.pid
echo "start" > /tmp/hssweep.cur
touch /etc/hssweep.state

cleanup() {
	trap - EXIT INT TERM
	rm -f /tmp/hssweep.cur
	iw dev mon0 del 2>/dev/null
	echo "cleanup -> restore" >> "$LOG"
	sh /etc/hsrestore.sh
	rm -f /tmp/hssweep.pid
}
trap 'cleanup' EXIT INT TERM

# --- 停 wifi（此时老家开始断网）---
wifi down >/dev/null 2>&1
sleep 3
# 注意：wifi down 会把 netifd 建的 wlan0 一起删掉，所以不能用 wlan0 建 monitor，
# 要直接挂到 phy 上（phy0 永远在）。
iw dev mon0 del >/dev/null 2>&1
PHY=$(ls /sys/class/ieee80211/ 2>/dev/null | head -1)
[ -z "$PHY" ] && PHY=phy0
if ! iw phy "$PHY" interface add mon0 type monitor >/dev/null 2>&1; then
	echo "mon0 建不起来 (phy=$PHY)" >> "$LOG"
fi
ip link set mon0 up >/dev/null 2>&1
sleep 1
iw dev mon0 info 2>/dev/null | grep -q monitor || echo "mon0 状态异常" >> "$LOG"

# --- 逐信道 ---
FILES=""
for ch in $CHS; do
	if ! iw dev mon0 set channel "$ch" >/dev/null 2>&1; then
		echo "ch$ch: 信道设置失败，跳过" >> "$LOG"
		continue
	fi
	echo "$ch" > /tmp/hssweep.cur
	F="$OUT/sw-$STAMP-ch$ch.pcap"
	"$TD" -i mon0 -s 256 -U -w "$F" >/dev/null 2>&1 &
	TP=$!
	sleep "$DWELL"
	kill "$TP" 2>/dev/null
	wait "$TP" 2>/dev/null
	n=$("$TD" -nr "$F" 2>/dev/null | wc -l)
	echo "ch$ch: $n 帧" >> "$LOG"
	# 这个信道看到哪些 BSSID（给前端标注每个 AP 在哪条信道）
	if [ "$n" -gt 0 ]; then
		"$TD" -ne -r "$F" 2>/dev/null \
		  | sed -n 's/.*BSSID:\([0-9a-f:]*\) .*/\1/p' | sort -u \
		  | while read -r m; do [ -n "$m" ] && echo "$m $ch"; done >> "$CHMAP"
	fi
	FILES="$FILES $F"
done

# --- 合并成一个 pcap（cat 拼接对 pcap 是合法的）---
rm -f /tmp/hssweep.cur
FILES=$(echo "$FILES" | tr -s ' ')
MERGE="$OUT/sweep-$STAMP.pcap"
cat $FILES > "$MERGE" 2>/dev/null
rm -f $FILES
mv -f "$CHMAP" "$OUT/sweep-$STAMP.chmap" 2>/dev/null
echo "merged $MERGE $(wc -c < "$MERGE" 2>/dev/null) 字节，chmap $([ -f "$OUT/sweep-$STAMP.chmap" ] && wc -l < "$OUT/sweep-$STAMP.chmap" || echo 0) 条" >> "$LOG"
