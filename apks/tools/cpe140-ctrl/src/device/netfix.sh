#!/bin/sh
#==============================================================================
#  CPE140 / BHU BXO2000n-2S-Lite   分级软修复  netfix
#
#  安装：/etc/netfix.sh        参数：/etc/netfix.conf（可用 /etc/netfix.local 覆盖）
#  用法：/etc/netfix.sh              按阶梯修，哪一步救回来就立刻停
#        /etc/netfix.sh check        只看现在通不通（不改任何东西）
#        /etc/netfix.sh step <名字>  只跑某一步（调试）
#        /etc/netfix.sh log          看日志
#        /etc/netfix.sh status       看配置
#        DRY=1 /etc/netfix.sh        干跑：只打印会做什么，绝不执行
#
#  阶梯（从最轻到最重；每一步之后都验证，通了就不做下一步）：
#    1 usr1        kill -USR1 detect_internet
#                  强制固件重新检测上网状态 —— 专治「门户劫持误判」这种假断网。零影响。
#    2 renew       ubus call network.interface.wan renew
#                  重新申请上行 DHCP（不动无线，不掉关联）
#    3 reassoc     killall -HUP wpa_supplicant
#                  让上行重新握手/关联（只短暂断 1-3 秒）
#    4 ifup        ifdown wan; sleep 2; ifup wan
#                  把上行接口整个重起一遍
#    5 wifireload  wifi reload
#                  重启整个无线栈（固件自己就是这么干的；设备自带的 AP 会闪一下）
#  五步都救不回来 -> 交给看门狗（netguard）按它自己的冷却/上限决定是否重启。
#
#  日志 /tmp/netfix.log（内存盘，零 flash 磨损，自动截断 200 行）
#==============================================================================

NAME=netfix
CONF=/etc/netfix.conf
[ -f $CONF ] && . $CONF
[ -f /etc/netfix.local ] && . /etc/netfix.local

LOG_FILE=/tmp/$NAME.log
LOG_TAIL=200

TARGETS=${TARGETS:-223.5.5.5 114.114.114.114}   # 判定「有没有网」
GW=${GW:-}                                      # 上游网关（留空则从路由表取）
SETTLE=${SETTLE:-4}                             # 每步之后等几秒再验证
STEPS=${STEPS:-usr1 renew reassoc ifup wifireload}
DRY=${DRY:-0}

log() {
	echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> $LOG_FILE
	[ -f $LOG_FILE ] || return 0
	if [ "$(wc -l < $LOG_FILE)" -gt $LOG_TAIL ]; then
		tail -n $LOG_TAIL $LOG_FILE > /tmp/$NAME.lt 2>/dev/null && mv /tmp/$NAME.lt $LOG_FILE
	fi
}

say() { log "$*"; echo "$*"; }

net_ok() {
	for t in $TARGETS; do
		ping -c 1 -W 2 $t >/dev/null 2>&1 && return 0
	done
	return 1
}

gw_of() {
	[ -n "$GW" ] && { echo $GW; return 0; }
	ip route 2>/dev/null | awk '/^default/ {print $3; exit}'
}

gw_ok() {
	g=$(gw_of)
	[ -n "$g" ] && ping -c 1 -W 2 $g >/dev/null 2>&1
}

# 固件的「强制门户」劫持规则在不在（在 = 它认为你没网，会把 DNS/HTTP 抢过去）
hijack_on() {
	iptables -t nat -S 2>/dev/null | grep -qE "detect_internet|lan_redirect|--dport 53 -j DNAT|--dport 80 -j DNAT"
}

netinfo() {
	echo "上行 $(iwinfo apcli0 info 2>/dev/null | sed -n '1p' | tr -d '\n')"
	echo "网关 $(gw_of) $(int_state)  互联网状态文件 $(cat /tmp/.internet_status 2>/dev/null)"
}

int_state() { gw_ok && echo '(通)' || echo '(不通)'; }

up_state() {
	ubus call network.interface.wan status 2>/dev/null \
		| tr -d ' \n' | sed -n 's/.*"ipv4-address":\[{"address":"\([^"]*\)".*/\1/p'
}

# ------------------------------------------------------------------ 各步动作

do_usr1() {
	pid=$(pidof detect_internet 2>/dev/null)
	if [ -z "$pid" ]; then echo "没找到 detect_internet，跳过"; return 1; fi
	kill -USR1 $pid 2>/dev/null && echo "已让它重新检测 (pid $pid)"
}

do_renew() {
	ubus call network.interface.wan renew >/dev/null 2>&1 && echo "已请求重新申请上行 DHCP" \
		|| echo "renew 失败"
}

do_reassoc() {
	killall -HUP wpa_supplicant 2>/dev/null && echo "已让 wpa_supplicant 重新握手" \
		|| echo "没找到 wpa_supplicant"
}

do_ifup() {
	ifdown wan >/dev/null 2>&1
	sleep 2
	ifup wan >/dev/null 2>&1 && echo "已重起上行接口 wan" || echo "ifup wan 失败"
}

do_wifireload() {
	wifi reload >/dev/null 2>&1 && echo "已 wifi reload（无线栈重启）" || echo "wifi reload 失败"
}

run_step() {
	case "$1" in
	xusr1) do_usr1 ;;
	xrenew) do_renew ;;
	xreassoc) do_reassoc ;;
	xifup) do_ifup ;;
	xwifireload) do_wifireload ;;
	*) echo "未知步骤 $1（可用: usr1 renew reassoc ifup wifireload）"; return 1 ;;
	esac
}

# ------------------------------------------------------------------ 子命令

case x$1 in
xcheck)
	if net_ok; then echo "互联网 通"; else echo "互联网 不通 (网关 $(gw_of) $(int_state))"; fi
	if hijack_on; then echo "注意: 检测到门户劫持规则（假断网状态）"; fi
	exit 0
	;;
xlog)
	cat $LOG_FILE 2>/dev/null || echo '(还没有日志)'
	exit 0
	;;
xstatus)
	echo '====== netfix 分级软修复 ======'
	echo "脚本      : /etc/netfix.sh"
	echo "阶梯顺序  : $STEPS"
	echo "探测目标  : $TARGETS"
	echo "网关      : $(gw_of) $(int_state)"
	echo "上行地址  : $(up_state)"
	echo "门户劫持  : $(hijack_on && echo '规则在（假断网）' || echo 无)"
	if net_ok; then echo '当前网络  : 通'; else echo '当前网络  : 不通'; fi
	if [ -f $LOG_FILE ]; then echo "日志行数  : $(wc -l < $LOG_FILE | tr -d ' ')"; else echo '日志行数  : 0'; fi
	exit 0
	;;
xstep)
	[ x$DRY = x1 ] && { echo "干跑：会执行步骤 $2"; exit 0; }
	run_step "$2"
	exit $?
	;;
esac

# ------------------------------------------------------------------ 主流程

log "--- netfix 开始 ($(netinfo | tr '\n' ' ')) ---"

if net_ok; then
	if hijack_on; then
		say "网络是通的，但检测到「门户劫持」规则——这就是典型的假断网。"
		if [ x$DRY = x1 ]; then
			echo "干跑：会执行 kill -USR1 detect_internet"
		else
			run_step usr1
			sleep 2
			if hijack_on; then
				say "劫持规则还在（固件认为没网）。建议关掉门户劫持："
				say "  uci set detect_internet.main.enable_redirect=0; /etc/init.d/detect_internet restart"
				exit 2
			fi
			say "劫持规则已清掉，网络恢复正常。"
		fi
		exit 0
	fi
	say "网络现在是通的，不需要修（什么都没做）。"
	exit 0
fi

say "互联网不通（网关 $(gw_of) $(int_state)）→ 开始分级软修复"

for s in $STEPS; do
	if [ x$DRY = x1 ]; then
		echo "干跑：会执行步骤 $s"
		continue
	fi
	log "执行步骤 $s"
	out=$(run_step "$s" 2>&1)
	say "  [$s] $out"
	sleep $SETTLE
	if net_ok; then
		say "✅ 第 $s 步就把网救回来了，后面的重手段不用做。"
		log "--- netfix 结束：$s 步修复成功 ---"
		exit 0
	fi
	say "  [$s] 还是不通，继续下一步"
done

if [ x$DRY = x1 ]; then
	echo "干跑结束（真跑的话，五步都不行就交给看门狗）"
	exit 0
fi
say "❌ 五步软修复都没救回来 —— 这多半是上游/运营商的问题，重启本机通常也没用。"
say "   交给看门狗按冷却与次数上限决定下一步。"
log "--- netfix 结束：全部软修复失败 ---"
exit 1
