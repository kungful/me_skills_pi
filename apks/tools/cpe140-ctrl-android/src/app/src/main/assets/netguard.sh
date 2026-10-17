#!/bin/sh
#==============================================================================
#  CPE140 / BHU BXO2000n-2S-Lite   断网看门狗  netguard
#
#  安装：/etc/netguard.sh        参数：/etc/netguard.conf
#  调用：crontab 每 2 分钟一次  ->  */2 * * * * /etc/netguard.sh >/dev/null 2>&1
#
#  它干什么
#    · 每次醒来 ping 几个互联网目标（默认 223.5.5.5 / 114.114.114.114）。
#    · 只要有一个通 -> 认为网络正常，计数清零，什么都不做。
#    · 全都不通   -> 计数 +1；连续 FAIL_NEED 次（默认 5 次 × 2 分 = 10 分钟）
#      才认定「真断网 / 中继器卡死」，然后：
#         配了 RECOVER  -> 先试一次轻量恢复，再宽限一轮；救得回来就不重启。
#                            （强烈建议配 /etc/netfix.sh —— 那是分级软修复阶梯：
#                             先强制固件重新检测、再放开被固件自己立旗禁用的上行、
#                             再重拨 DHCP / 重新关联 / 重起接口 / wifi reload，
#                             哪一步救回来就停，比重启温和得多）
#         没配 / 恢复过仍不通 -> 写日志 + 重启设备。
#    · 与上次自动重启的间隔必须超过 COOLDOWN（默认 1800 秒 = 30 分钟），
#      防止「上游光猫真的坏了」时无限重启。
#    · 一次「持续断网事件」里最多自动重启 MAX_REBOOT 次（默认 3 次，约 1 小时）。
#      超过后不再频繁重启：每 LONG_WAIT 秒（默认 6 小时）才允许再试一次。
#      网络一恢复，本次事件的计数自动清零，下次断网重新给满 3 次机会。
#    · 日志里还会顺带记录上游网关通不通，方便区分「光猫挂」还是「中继器挂」。
#
#  与「定时重启」的关系：完全独立
#    定时重启走 crontab 里另一条 `sleep 5 && touch /etc/banner && reboot` 行，
#    由 /etc/init.d/autoreboot 维护，并且它会 `sed -i /reboot/d` 清理自己的行。
#    本脚本文件名/命令行里都不含 reboot 字样，所以两边互不误删；
#    本脚本也不看时间、只在「网络真不通」时动作。
#    设备重启后 /tmp 里的计数自动归零，所以定时重启不会触发误判。
#
#  手动用
#    /etc/netguard.sh              巡检一次（cron 就是这么调的）
#    /etc/netguard.sh test         干跑：只打印判断结果，绝不重启、不执行恢复
#    /etc/netguard.sh check        只探测一次连通性
#    /etc/netguard.sh status       看状态
#    /etc/netguard.sh log          看日志
#    /etc/netguard.sh reset        计数清零
#    /etc/netguard.sh cron on|off  启用 / 停用（增删 crontab 那一行）
#
#  没有 flash 磨损顾虑：计数/日志都在 /tmp（tmpfs），只有真的重启才写
#  一次 /etc/netguard.last。
#==============================================================================

NAME=netguard
CONF=/etc/netguard.conf
[ -f $CONF ] && . $CONF
[ -f /etc/netguard.local ] && . /etc/netguard.local

FAIL_FILE=/tmp/$NAME.fails
UP_FILE=/tmp/$NAME.up
REC_FILE=/tmp/$NAME.rec
LOG_FILE=/tmp/$NAME.log
LAST_FILE=/etc/$NAME.last
CNT_FILE=/etc/$NAME.reboots      # 本次断网事件里已自重启次数（重启也保留）
CRON_LINE='*/2 * * * * /etc/netguard.sh >/dev/null 2>&1'
LOG_TAIL=200

# ---- 可调参数（写进 /etc/netguard.conf 即可覆盖）-----------------------------
WAN_TARGETS=${WAN_TARGETS:-223.5.5.5 114.114.114.114}
GW=${GW:-192.168.1.1}
FAIL_NEED=${FAIL_NEED:-5}        # 连续失败次数阈值
COOLDOWN=${COOLDOWN:-1800}       # 两次自动重启最小间隔（秒）
MAX_REBOOT=${MAX_REBOOT:-3}      # 一次持续断网最多自动重启几次（之后转长退避）
LONG_WAIT=${LONG_WAIT:-21600}    # 超过上面次数后的重试间隔（秒，默认 6 小时）
MODE=${MODE:-reboot}             # reboot=到点重启 / log=只记录不动手
RECOVER=${RECOVER:-}             # 可选轻量恢复命令，默认空

log() {
	echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> $LOG_FILE
	[ -f $LOG_FILE ] || return 0
	if [ "$(wc -l < $LOG_FILE)" -gt $LOG_TAIL ]; then
		tail -n $LOG_TAIL $LOG_FILE > /tmp/$NAME.lt 2>/dev/null && mv /tmp/$NAME.lt $LOG_FILE
	fi
}

net_ok() {   # 任一互联网目标通 -> 0
	for t in $WAN_TARGETS; do
		ping -c 1 -W 2 $t >/dev/null 2>&1 && return 0
	done
	return 1
}

gw_state() { # 上游网关通不通（只用于日志/状态）
	ping -c 1 -W 2 $GW >/dev/null 2>&1 && echo 通 || echo 不通
}

get_fails() {
	f=$(cat $FAIL_FILE 2>/dev/null)
	case $f in ''|*[!0-9]*) f=0 ;; esac
	echo $f
}

cron_state() {
	grep -q netguard /etc/crontabs/root 2>/dev/null && echo 已启用 || echo 未启用
}

cron_on() {
	sed -i '/netguard/d' /etc/crontabs/root 2>/dev/null
	echo "$CRON_LINE" >> /etc/crontabs/root
	[ -x /etc/init.d/cron ] && /etc/init.d/cron restart >/dev/null 2>&1
	log '看门狗已启用'
	echo '看门狗已启用：每 2 分钟巡检一次'
}

cron_off() {
	sed -i '/netguard/d' /etc/crontabs/root 2>/dev/null
	[ -x /etc/init.d/cron ] && /etc/init.d/cron restart >/dev/null 2>&1
	log '看门狗已停用'
	echo '看门狗已停用（脚本还在，随时可再开）'
}

show_status() {
	upt=$(cut -d. -f1 /proc/uptime 2>/dev/null)
	f=$(get_fails)
	dn=0
	[ -f $CNT_FILE ] && dn=$(cat $CNT_FILE 2>/dev/null)
	case $dn in ''|*[!0-9]*) dn=0 ;; esac
	echo '====== netguard 断网看门狗 ======'
	if [ -x /etc/netguard.sh ]; then echo '脚本      : /etc/netguard.sh (已安装)'; else echo '脚本      : 缺失!'; fi
	echo "定时任务  : $(cron_state)"
	echo "参数      : 每2分钟一次 / 连续 $FAIL_NEED 次算断网 / 冷却 $COOLDOWN 秒 / MODE=$MODE"
	echo "重启上限  : 单次断网最多 $MAX_REBOOT 次，超限后改每 $((LONG_WAIT / 3600)) 小时一次"
	if [ x$RECOVER = x ]; then echo '轻量恢复  : (未配置，到点直接重启)'; else echo "轻量恢复  : $RECOVER"; fi
	echo "探测目标  : $WAN_TARGETS  (网关 $GW)"
	echo "当前计数  : $f / $FAIL_NEED"
	echo "本次断网  : 已自重启 $dn / $MAX_REBOOT 次"
	if net_ok; then echo '当前网络  : 通'; else echo "当前网络  : 不通 (网关 $(gw_state))"; fi
	[ -f $UP_FILE ] && echo '本次开机  : 已经通过（计数可信）' || echo '本次开机  : 还没通过'
	if [ -f $LAST_FILE ] && [ -n "$(cat $LAST_FILE 2>/dev/null)" ]; then
		e=$(cat $LAST_FILE 2>/dev/null)
		h=$(date -d @$e '+%Y-%m-%d %H:%M:%S' 2>/dev/null)
		[ -z "$h" ] && h=$e
		echo "上次自重启: $h（$(( $(date +%s) - e )) 秒前）"
	else
		echo '上次自重启: 从未'
	fi
	echo "运行时长  : ${upt}秒"
	if [ -f $LOG_FILE ]; then
		echo "日志行数  : $(wc -l < $LOG_FILE | tr -d ' ')"
	else
		echo '日志行数  : 0 (还没有日志)'
	fi
}

case x$1 in
xtest)
	DRY=1
	;;
xcheck)
	if net_ok; then echo "网络通 (网关 $(gw_state))"; else echo "网络不通 (网关 $(gw_state))"; fi
	exit 0
	;;
xstatus)
	show_status
	exit 0
	;;
xlog)
	cat $LOG_FILE 2>/dev/null || echo '(还没有日志)'
	exit 0
	;;
xreset)
	echo 0 > $FAIL_FILE
	rm -f $REC_FILE $CNT_FILE
	echo '计数已清零（本次断网的自动重启次数也归零）'
	exit 0
	;;
xcron)
	case x$2 in
	xon) cron_on ;;
	xoff) cron_off ;;
	*) echo '用法: netguard.sh cron on|off' ;;
	esac
	exit 0
	;;
esac

# ------------------------------- 主流程 --------------------------------------
fail=$(get_fails)

if net_ok; then
	if [ "$fail" -gt 0 ]; then
		log "网络恢复（之前连续失败 $fail 次，网关 $(gw_state)）"
	fi
	echo 0 > $FAIL_FILE
	: > $UP_FILE
	[ -f $CNT_FILE ] && rm -f $CNT_FILE      # 网络恢复 -> 本次断网事件结束，重新给满次数
	[ x$DRY = x1 ] && echo '干跑结果: 网络通，计数清零，不动作'
	exit 0
fi

gws=$(gw_state)
fail=$((fail + 1))
echo $fail > $FAIL_FILE
log "第 $fail/$FAIL_NEED 次探测失败（网关 $gws，目标 $WAN_TARGETS）"

if [ x$DRY = x1 ]; then
	echo "干跑结果: 网络不通（第 $fail/$FAIL_NEED 次，网关 $gws）"
	if [ "$fail" -ge "$FAIL_NEED" ]; then
		dnx=0
		[ -f $CNT_FILE ] && dnx=$(cat $CNT_FILE 2>/dev/null)
		case $dnx in ''|*[!0-9]*) dnx=0 ;; esac
		echo '          —— 已达到阈值：真实运行时这一步会' \
			"$( [ x$RECOVER = x ] && echo 重启设备 || echo 尝试轻量恢复 )"
		echo "          —— 本次断网已自重启 $dnx/$MAX_REBOOT 次（超限后改为每 $((LONG_WAIT / 3600)) 小时一次）"
	else
		echo "          —— 还没到阈值，真实运行时不动作（还差 $((FAIL_NEED - fail)) 次）"
	fi
	exit 0
fi

[ "$fail" -lt "$FAIL_NEED" ] && exit 0

# ---- 到阈值：先可选的轻量恢复（每次开机只试一次）----
if [ x$RECOVER != x ] && [ ! -f $REC_FILE ]; then
	log "尝试轻量恢复: $RECOVER"
	touch $REC_FILE
	sh -c "$RECOVER" >> $LOG_FILE 2>&1
	exit 0
fi

# ---- 重启 ----
if [ x$MODE = xlog ]; then
	log "已达到阈值，但 MODE=log：只记录，不重启"
	exit 0
fi

now=$(date +%s)
last=0
[ -f $LAST_FILE ] && last=$(cat $LAST_FILE 2>/dev/null)
case $last in ''|*[!0-9]*) last=0 ;; esac
if [ "$now" -lt "$last" ]; then last=0; fi

done_n=0
[ -f $CNT_FILE ] && done_n=$(cat $CNT_FILE 2>/dev/null)
case $done_n in ''|*[!0-9]*) done_n=0 ;; esac

# 本次断网已经重启满 MAX_REBOOT 次 -> 冷却加长到 LONG_WAIT，不再频繁重启
cd_eff=$COOLDOWN
if [ "$done_n" -ge "$MAX_REBOOT" ]; then cd_eff=$LONG_WAIT; fi

if [ $((now - last)) -lt $cd_eff ]; then
	log "已达到阈值，但距上次自动重启仅 $((now - last)) 秒（冷却 $cd_eff 秒，本次断网已重启 $done_n/$MAX_REBOOT 次），跳过"
	exit 0
fi

log "持续断网 $fail 次（网关 $gws）→ 自动重启设备（本次断网第 $((done_n + 1)) 次，上限 $MAX_REBOOT 次）"
echo $now > $LAST_FILE
echo $((done_n + 1)) > $CNT_FILE
sync
sleep 3
reboot
