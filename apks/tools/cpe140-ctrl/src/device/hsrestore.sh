#!/bin/sh
# hsrestore.sh — 把 wifi 恢复到「老家能上网」的状态。幂等，可反复调用。
# 任何跳信道/换信道抓包结束后都必须调它；netguard 也会在标记残留时调它。
LOG=/tmp/hsrestore.log
ts() { date '+%H:%M:%S'; }

echo "$(ts) --- restore 开始 (state=$([ -f /etc/hssweep.state ] && echo yes || echo no))" >> "$LOG"

up_ok() {
	# 上行 STA 连上 + 本机 AP 起来了，才算真恢复
	iw dev apcli0 link 2>/dev/null | grep -q '^Connected to' || return 1
	iw dev wlan0 info >/dev/null 2>&1 || return 1
	return 0
}

once() {
	wifi down >/dev/null 2>&1
	sleep 2
	wifi up   >/dev/null 2>&1
	i=0
	while [ $i -lt 30 ]; do
		if up_ok; then return 0; fi
		sleep 2
		i=$((i+1))
	done
	return 1
}

ok=0
for n in 1 2 3; do
	echo "$(ts) 第 $n 次恢复尝试" >> "$LOG"
	if once; then ok=1; break; fi
	echo "$(ts) 第 $n 次失败" >> "$LOG"
done

if [ "$ok" != "1" ]; then
	echo "$(ts) 三次 wifi 重启都失败 -> 重启网络栈" >> "$LOG"
	/etc/init.d/network restart >/dev/null 2>&1
	sleep 15
	if up_ok; then
		ok=1
	else
		echo "$(ts) 网络栈重启也无效 -> 重启设备" >> "$LOG"
		rm -f /etc/hssweep.state
		sync
		reboot
		exit 0
	fi
fi

rm -f /etc/hssweep.state
echo "$(ts) --- 恢复成功: $(iw dev apcli0 link 2>/dev/null | head -1)" >> "$LOG"
