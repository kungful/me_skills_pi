#!/bin/sh
# /etc/alert.sh —— CPE140 断网告警（独立组件）
#
# 设计原则（安全为上）:
#   * 只「读」netguard 的状态文件与网络连通性, 绝不改动 netfix/netguard
#     -> 因此不可能弄坏现有自愈逻辑
#   * 不写 flash（除 /etc/alert.* 自己的配置文件外, 状态全放 /tmp）
#   * 默认不启用任何外发: WEBHOOK 为空则只写本地日志
#
# 为什么是「恢复时汇报」:
#   上行断掉时设备本身没有网, 告警发不出去。所以:
#     - 断网 -> 记下时间, 本地记录
#     - 恢复 -> 汇报「中断了 X 分钟」 (此刻有网, 发得出去)
#     - 门户误判(有网但上不了) -> 立刻告警, 因为此刻其实有网
#
# 用法:
#   /etc/alert.sh           跑一次(cron 用)
#   /etc/alert.sh status    看状态
#   /etc/alert.sh log       看日志
#   /etc/alert.sh test      发一条测试告警
#   /etc/alert.sh reset     清掉「断网中」标记

NAME=alert
CONF=/etc/alert.conf
LOG_FILE=/tmp/$NAME.log
STATE=/tmp/$NAME.state            # up | down
DOWN_AT=/tmp/$NAME.down_at        # 断网开始时间(epoch)
LAST_SEND=/tmp/$NAME.last         # 上次发送时间(epoch)
TMP=/tmp/$NAME.tmp

# ---- 可覆盖参数 -------------------------------------------------------------
WEBHOOK=${WEBHOOK:-}                                    # 为空 = 不外发
WEBHOOK_STYLE=${WEBHOOK_STYLE:-json}                    # json | form | raw
TARGETS=${TARGETS:-223.5.5.5 114.114.114.114}
FAIL_NEED=${FAIL_NEED:-5}                               # 与 netguard 阈值一致
COOLDOWN=${COOLDOWN:-1800}                              # 重复提醒冷却(秒)
REPORT_RECOVERY=${REPORT_RECOVERY:-1}
[ -f "$CONF" ] && . "$CONF"

now() { date +%s; }
log() {
	echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG_FILE"
	# 自动截断, 防 tmpfs 膨胀
	n=$(wc -l < "$LOG_FILE" 2>/dev/null || echo 0)
	[ "$n" -gt 200 ] && tail -100 "$LOG_FILE" > "$TMP" && mv "$TMP" "$LOG_FILE"
	return 0
}

net_ok() {   # 任一目标 ping 通 -> 0
	for t in $TARGETS; do
		ping -c 1 -W 2 "$t" >/dev/null 2>&1 && return 0
	done
	return 1
}

gw_state() {
	gw=$(ip route 2>/dev/null | awk '/^default/{print $3; exit}')
	[ -z "$gw" ] && { echo "无默认路由"; return; }
	if ping -c 1 -W 2 "$gw" >/dev/null 2>&1; then echo "网关 $gw 通"; else echo "网关 $gw 不通"; fi
}

ng_fails() {   # 读 netguard 的失败计数(只读!)
	f=$(cat /tmp/netguard.fails 2>/dev/null)
	case $f in ''|*[!0-9]*) f=0 ;; esac
	echo "$f"
}

send() {   # $1=标题 $2=正文
	body="[CPE140@$(uname -n)] $1
$2
时间: $(date '+%Y-%m-%d %H:%M:%S')
$WAN_SSID_TXT"
	log "SEND: $1 | $(echo "$2" | tr '\n' ' ')"
	echo "$(now)" > "$LAST_SEND"
	[ -z "$WEBHOOK" ] && { log "(WEBHOOK 未配置, 只记本地)"; return 0; }
	case $WEBHOOK_STYLE in
		raw)  data="$body" ;;
		form) data="text=$(echo "$body" | sed 's/ /+/g')" ;;
		*)    # json: 转义双引号和换行
		      esc=$(printf '%s' "$body" | sed 's/\\/\\\\/g; s/"/\\"/g' | awk 'BEGIN{ORS="\\n"}{print}')
		      esc=$(printf '%s' "$esc" | sed 's/\\n$//')
		      data="{\"text\":\"$esc\"}" ;;
	esac
	if [ "$WEBHOOK_STYLE" = form ]; then
		wget -q -O /dev/null -T 10 --post-data="$data" "$WEBHOOK" 2>/dev/null \
			|| wget -q -O /dev/null -T 10 "$WEBHOOK" 2>/dev/null
	else
		wget -q -O /dev/null -T 10 --header='Content-Type: application/json' \
			--post-data="$data" "$WEBHOOK" 2>/dev/null \
			|| wget -q -O /dev/null -T 10 --post-data="$data" "$WEBHOOK" 2>/dev/null \
			|| wget -q -O /dev/null -T 10 "$WEBHOOK" 2>/dev/null
	fi
	rc=$?
	[ $rc = 0 ] && log "webhook 发送成功" || log "webhook 发送失败(rc=$rc) —— 断网中属正常"
	return 0
}

wan_txt() {
	ssid=$(iw dev apcli0 link 2>/dev/null | awk '/SSID/{print $2}')
	sig=$(iw dev apcli0 link 2>/dev/null | awk '/signal/{print $2" "$3}')
	if [ -n "$ssid" ]; then WAN_SSID_TXT="上行: $ssid  信号: $sig"; else WAN_SSID_TXT="上行: 未连接"; fi
}

show_status() {
	echo "== alert 状态 =="
	echo "标记        : $(cat $STATE 2>/dev/null || echo '(空, 视为 up)')"
	echo "断网起点    : $( [ -f $DOWN_AT ] && date -d @$(cat $DOWN_AT) '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo '(无)' )"
	echo "netguard 失败计数: $(ng_fails)/$FAIL_NEED"
	echo "当前连通    : $(net_ok && echo 通 || echo 不通)"
	echo "$(gw_state)"
	wan_txt; echo "$WAN_SSID_TXT"
	if [ -z "$WEBHOOK" ]; then echo "WEBHOOK     : (未配置 —— 只写本地日志)"; else echo "WEBHOOK     : $WEBHOOK  ($WEBHOOK_STYLE)"; fi
	echo "冷却        : ${COOLDOWN}s   报告恢复: $REPORT_RECOVERY"
}

# ---- 主流程 -----------------------------------------------------------------
case x$1 in
xstatus) show_status; exit 0 ;;
xlog)    tail -40 "$LOG_FILE" 2>/dev/null || echo '(还没有日志)'; exit 0 ;;
xreset)  echo up > "$STATE"; rm -f "$DOWN_AT"; log '手动重置为 up'; echo 'reset -> up'; exit 0 ;;
xtest)   wan_txt; send '测试告警' '这是一条测试消息, 收到即说明告警通道可用。'; echo "测试已发出 (webhook='$WEBHOOK')"; exit 0 ;;
esac

prev=$(cat "$STATE" 2>/dev/null); [ -z "$prev" ] && prev=up
fails=$(ng_fails)
# 先信 netguard 的计数, 再自己探一次
if [ "$fails" -ge "$FAIL_NEED" ]; then down=1; else net_ok && down=0 || down=1; fi
wan_txt

if [ "$down" = 1 ]; then
	[ -f "$DOWN_AT" ] || echo "$(now)" > "$DOWN_AT"
	if [ "$prev" != down ]; then
		echo down > "$STATE"
		# 断网中大概率发不出去, 也试一次(可能是门户误判, 其实有网)
		send '网络中断' "netguard 连续失败 $fails/$FAIL_NEED 次。$(gw_state)\n$WAN_SSID_TXT"
	else
		last=$(cat "$LAST_SEND" 2>/dev/null); case $last in ''|*[!0-9]*) last=0 ;; esac
		if [ $(( $(now) - last )) -ge "$COOLDOWN" ]; then
			d=$(( ($(now) - $(cat $DOWN_AT 2>/dev/null || echo $(now))) / 60 ))
			send '仍处于断网' "已中断约 ${d} 分钟。$(gw_state)\n$WAN_SSID_TXT"
		fi
	fi
else
	if [ "$prev" = down ] && [ "$REPORT_RECOVERY" = 1 ]; then
		st=$(cat "$DOWN_AT" 2>/dev/null); case $st in ''|*[!0-9]*) st=$(now) ;; esac
		m=$(( ($(now) - st) / 60 )); s=$(( $(now) - st - m*60 ))
		send '网络已恢复' "中断时长约 ${m} 分 ${s} 秒。$WAN_SSID_TXT"
		log "恢复, 中断 ${m}分${s}秒"
	fi
	echo up > "$STATE"; rm -f "$DOWN_AT"
fi
exit 0
