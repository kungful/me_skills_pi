#!/bin/sh
# /etc/wake.sh —— CPE140 局域网 Wake-on-LAN 工具
#
# 依赖 /usr/bin/etherwake（OpenWrt 官方 mips_24kc 包，已装；实测 EtherType 0x0842、
# payload = 6×FF + 16×MAC，输出 "Sendto worked ! 116"）。
#
# 用法:
#   /etc/wake.sh add <名字> <MAC> [IP]   注册目标（写入 /etc/wake.conf）
#   /etc/wake.sh del <名字>              注销
#   /etc/wake.sh list                    列出已注册目标 + 在线状态
#   /etc/wake.sh wake <名字|MAC>         发魔术包
#   /etc/wake.sh online <名字|MAC>       目标在线吗（先 ARP/DHCP 再 ping）
#   /etc/wake.sh auto                    对所有"不在线"的目标发一次（给 cron；带冷却）
#   /etc/wake.sh log                     看日志
#
# 怎么远程触发（不需要新开端口）：
#   python cpe140.py sh "/etc/wake.sh wake pc"
#   —— 走的是设备已有的 CGI 通道，任何能访问 192.168.188.254 的地方都行。

CONF=/etc/wake.conf
LOG=/tmp/wake.log
COOLDIR=/tmp/wake.last          # 冷却标记目录
COOLDOWN=${COOLDOWN:-600}       # auto 模式下同一目标最短重发间隔(秒)
IFACE=${IFACE:-br-lan}
EW=${EW:-/usr/bin/etherwake}

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }

norm_mac() { echo "$1" | tr 'a-z' 'A-Z'; }

valid_mac() { echo "$1" | grep -qE '^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$'; }

# 按名字取 MAC / IP
lookup_mac() {
	echo "$1" | grep -qE '^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$' && { norm_mac "$1"; return; }
	[ -f "$CONF" ] && awk -v n="$1" '$1==n{print toupper($2); exit}' "$CONF"
}
lookup_ip() {
	[ -f "$CONF" ] && awk -v n="$1" '$1==n{print $3; exit}' "$CONF"
}
lookup_name() {
	[ -f "$CONF" ] && awk -v m="$(norm_mac "$1")" 'toupper($2)==m{print $1; exit}' "$CONF"
}

do_wake() {
	mac=$(lookup_mac "$1")
	if [ -z "$mac" ]; then echo "找不到目标: $1（用 add 注册，或直接给 MAC）"; return 2; fi
	if ! valid_mac "$mac"; then echo "MAC 格式不对: $mac"; return 2; fi
	[ -x "$EW" ] || { echo "缺少 $EW"; return 3; }
	# 目标不在 ARP 表里时先加一条静态表项，避免 etherwake 找不到路径（不影响唤醒）
	$EW -i "$IFACE" "$mac" >/dev/null 2>&1
	rc=$?
	if [ $rc = 0 ]; then
		echo "已发送魔术包 -> $mac  (接口 $IFACE)"
		log "wake $1 ($mac) rc=0"
		date +%s > "$COOLDIR.$mac"
	else
		echo "发送失败 rc=$rc"
		log "wake $1 ($mac) rc=$rc FAILED"
	fi
	return $rc
}

is_online() {
	mac=$(lookup_mac "$1"); ip=$(lookup_ip "$1")
	# 1) ARP 表里有 -> 在线
	if [ -n "$mac" ] && grep -qi "$mac" /proc/net/arp 2>/dev/null; then echo online; return 0; fi
	# 2) DHCP 租约里有且未过期 -> 在线
	if [ -n "$mac" ] && grep -qi "$mac" /tmp/dhcp.leases 2>/dev/null; then echo online; return 0; fi
	# 3) ping 一下
	if [ -n "$ip" ] && ping -c 1 -W 2 "$ip" >/dev/null 2>&1; then echo online; return 0; fi
	echo offline; return 1
}

cd_state() {
	f="$COOLDIR.$1"
	[ -f "$f" ] || return 1
	l=$(cat "$f" 2>/dev/null); case $l in ''|*[!0-9]*) return 1 ;; esac
	[ $(( $(date +%s) - l )) -lt "$COOLDOWN" ]
}

case x$1 in
xadd)
	n=$2; m=$3; ip=$4
	[ -z "$n" ] || [ -z "$m" ] && { echo "用法: wake.sh add <名字> <MAC> [IP]"; exit 2; }
	valid_mac "$m" || { echo "MAC 格式不对: $m"; exit 2; }
	m=$(norm_mac "$m")
	[ -f "$CONF" ] || { echo "# 名字 MAC [IP]" > "$CONF"; }
	sed -i "/^$n /d" "$CONF" 2>/dev/null
	echo "$n $m $ip" >> "$CONF"
	echo "已注册 $n -> $m ${ip:+($ip)}"
	;;
xdel)
	n=$2; [ -z "$n" ] && { echo "用法: wake.sh del <名字>"; exit 2; }
	sed -i "/^$n /d" "$CONF" 2>/dev/null; echo "已删除 $n"
	;;
xlist)
	echo "== 已注册目标 ($CONF) =="
	if [ -f "$CONF" ]; then
		grep -v '^#' "$CONF" | grep -v '^$' | while read -r n m ip; do
			printf "  %-12s %-18s %-16s %s\n" "$n" "$m" "${ip:--}" "$(is_online "$n")"
		done
	else echo "  (还没有目标，用 wake.sh add 添加)"; fi
	echo
	echo "== 当前 LAN 客户端（来自 DHCP 租约，可用来注册）=="
	awk '{printf "  ip=%-16s mac=%-18s host=%s\n", $3, toupper($2), $4}' /tmp/dhcp.leases 2>/dev/null | head -10
	;;
xwake) shift; [ -z "$1" ] && { echo "用法: wake.sh wake <名字|MAC>"; exit 2; }; do_wake "$1"; exit $? ;;
xonline)
	[ -z "$2" ] && { echo "用法: wake.sh online <名字|MAC>"; exit 2; }
	echo "$2: $(is_online "$2")"
	;;
xauto)
	n=0
	[ -f "$CONF" ] || { echo "没有目标"; exit 0; }
	grep -v '^#' "$CONF" | grep -v '^$' | while read -r name mac ip; do
		[ -z "$name" ] && continue
		if [ "$(is_online "$name")" = online ]; then
			log "auto: $name 在线，跳过"
		else
			if cd_state "$mac"; then
				log "auto: $name 不在线，但冷却中，跳过"
			else
				log "auto: $name 不在线 -> 唤醒"
				$EW -i "$IFACE" "$mac" >/dev/null 2>&1 && date +%s > "$COOLDIR.$mac"
			fi
		fi
	done
	echo "auto 完成（详情看 /etc/wake.sh log）"
	;;
xlog) tail -40 "$LOG" 2>/dev/null || echo "(还没有日志)" ;;
"")
	echo "用法: /etc/wake.sh {add|del|list|wake|online|auto|log}"; exit 0
	;;
*) echo "未知子命令: $1"; exit 2 ;;
esac
