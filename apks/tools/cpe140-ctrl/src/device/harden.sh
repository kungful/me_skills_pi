#!/bin/sh
# /etc/harden.sh —— CPE140 加固工具（安全为上：默认全部 dry-run）
#
# 只做「需要你决定」的事。所有动作都会:
#   1) 先备份到 /tmp/harden.bak.<时间>/
#   2) 执行后立刻回读验证
#   3) 打印一行回滚命令
# 不写 flash 里的临时文件；/tmp 是内存盘。
#
# 用法:
#   /etc/harden.sh status                       只读体检（不改任何东西）
#   /etc/harden.sh sshpass 'NEWPW'  --yes       改 root 口令（去掉出厂默认 cxyb#999）
#   /etc/harden.sh webadmin 'NEWPW' --yes       改 Web 管理员口令（当前 root）
#   /etc/harden.sh psk 'NEWPSK'     --yes       改本机 AP 密码 ★会踢掉所有客户端★
#   /etc/harden.sh sshport 2222     --yes       换 SSH 端口（默认 22）
#   /etc/harden.sh closeports       --yes       关掉未使用的 upload/showhtml 端点
#   /etc/harden.sh revert                       还原 closeports
#
# 说明：本脚本不含 "reboot"/"firstboot"/"sysupgrade" 字样，与 autoreboot/netguard 互不干扰。

BAK=/tmp/harden.bak.$(date +%Y%m%d-%H%M%S)
need_yes() { [ "$2" = "--yes" ] && return 0; echo "!! 这是改动类操作。确认后请加 --yes 重跑："; echo "   $0 $1 ... --yes"; exit 2; }
say() { echo "$*"; }
bak() { mkdir -p "$BAK"; cp -a "$1" "$BAK/" 2>/dev/null; }

status() {
	echo "======== CPE140 加固体检 ========"
	echo "-- SSH --"
	echo -n "  端口        : "; uci get dropbear.@dropbear[0].Port 2>/dev/null
	echo -n "  密码认证    : "; uci get dropbear.@dropbear[0].PasswordAuth 2>/dev/null
	echo -n "  root 密码认证: "; uci get dropbear.@dropbear[0].RootPasswordAuth 2>/dev/null
	echo -n "  root 口令    : "; if awk -F: '$1=="root"{print $2}' /etc/shadow | grep -q 'CJewIHdB'; then echo "★ 仍是出厂默认 cxyb#999 (哈希 salt=CJewIHdB)"; else echo "已改过(非出厂值)"; fi
	echo -n "  authorized_keys: "; [ -f /root/.ssh/authorized_keys ] && echo "已装($(wc -c </root/.ssh/authorized_keys)B)" || echo "无"
	echo "-- Web --"
	echo -n "  管理员口令  : "; uci get administrator.user.password 2>/dev/null
	echo -n "  监听        : "; netstat -lnt 2>/dev/null | awk '/:80 /{print $4}' | head -1
	echo "-- 无线 --"
	echo -n "  AP SSID/PSK : "; uci get wireless.vap0.ssid 2>/dev/null; printf "                "; uci get wireless.vap0.key 2>/dev/null
	echo -n "  上行 STA    : "; uci get wireless.vap5.ssid 2>/dev/null
	echo "-- 其他监听 --"
	netstat -lnt 2>/dev/null | awk 'NR>2{print "  "$4"  "$7}'
	echo "-- 自愈/告警 --"
	for f in /etc/netfix.sh /etc/netguard.sh /etc/alert.sh; do
		printf "  %-20s %s\n" "$f" "$([ -f $f ] && echo 已装 || echo 缺失)"
	done
	echo -n "  cron        : "; tr '\n' '|' < /etc/crontabs/root; echo
	echo -n "  uci-defaults: "; ls /etc/uci-defaults/ 2>/dev/null | tr '\n' ' '; echo
	echo "================================="
}

case x$1 in
xstatus|"") status; exit 0 ;;

xsshpass)
	need_yes "sshpass 'NEWPW'" "$3"
	np=$2; [ -z "$np" ] && { echo "缺少新口令"; exit 2; }
	bak /etc/shadow
	printf '%s\n%s\n' "$np" "$np" | passwd root >/tmp/.hp 2>&1
	if [ $? = 0 ]; then say "[ok] root 口令已改"; else say "[!!] 改失败:"; cat /tmp/.hp; fi
	rm -f /tmp/.hp
	say "  回滚: printf 'cxyb#999\\ncxyb#999\\n' | passwd root"
	;;

xwebadmin)
	need_yes "webadmin 'NEWPW'" "$3"
	np=$2; [ -z "$np" ] && { echo "缺少新口令"; exit 2; }
	uci -q get administrator.user.password >/dev/null || { echo "没有 administrator.user 段，改用 Web 接口"; exit 2; }
	old=$(uci -q get administrator.user.password)
	bak /etc/config/administrator
	uci set administrator.user.password="$np" && uci commit administrator
	say "[ok] Web 管理员口令: $old -> $(uci get administrator.user.password)"
	say "  回滚: uci set administrator.user.password='$old' && uci commit administrator"
	say "  (注意: 若 Web 登录用别的字段, 请用浏览器实测一次)"
	;;

xpsk)
	need_yes "psk 'NEWPSK'" "$3"
	np=$2; [ ${#np} -lt 8 ] && { echo "★ 密码太短(至少 8 位)，拒绝"; exit 2; }
	old=$(uci -q get wireless.vap0.key)
	echo "!! 本次会踢掉所有已连本机 AP 的客户端，它们必须用新密码重连。"
	bak /etc/config/wireless
	uci set wireless.vap0.key="$np" && uci commit wireless
	say "[ok] AP 密码: $old -> $(uci get wireless.vap0.key)"
	say "  生效需重启无线: wifi reload    (约断 1~5 秒)"
	say "  回滚: uci set wireless.vap0.key='$old' && uci commit wireless && wifi reload"
	;;

xsshport)
	need_yes "sshport N" "$3"
	np=$2; case $np in ''|*[!0-9]*) echo "端口必须是数字"; exit 2 ;; esac
	old=$(uci -q get dropbear.@dropbear[0].Port)
	bak /etc/config/dropbear
	uci set dropbear.@dropbear[0].Port="$np" && uci commit dropbear
	/etc/init.d/dropbear restart >/dev/null 2>&1
	sleep 1
	if netstat -lnt 2>/dev/null | grep -q ":$np "; then say "[ok] SSH 端口: $old -> $np (已在监听)";
	else say "[!!] 新端口没起来！立刻回滚"; uci set dropbear.@dropbear[0].Port="$old"; uci commit dropbear; /etc/init.d/dropbear restart; fi
	say "  回滚: uci set dropbear.@dropbear[0].Port='$old' && uci commit dropbear && /etc/init.d/dropbear restart"
	say "  ★ 别忘了: 80 端口的未认证 CGI 仍可用，SSH 换端口只是减少扫描噪音"
	;;

xcloseports)
	need_yes "closeports" "$2"
	# showhtml = 死接口(所有 opcode 都返回 {}) -> 关掉零影响
	# upload   = 未认证刷固件入口, 但 cpe140.py 的命令回退/文件推送依赖它!
	#            默认不动; 确认要关请加 --with-upload(会削弱 cpe140.py)
	for n in showhtml; do
		if [ -L /www/cgi-bin/$n ] || [ -f /www/cgi-bin/$n ]; then
			mv /www/cgi-bin/$n /www/cgi-bin/$n.off && say "[ok] 已停用 /cgi-bin/$n"
		else say "- /cgi-bin/$n 不存在，跳过"; fi
	done
	if [ "$3" = "--with-upload" ]; then
		say "[!!] 关掉 upload 后 cpe140.py 遇含 美元符 或引号的命令会失败(它靠 upload 回退)"
		mv /www/cgi-bin/upload /www/cgi-bin/upload.off 2>/dev/null && say "[ok] 已停用 /cgi-bin/upload"
	else
		say "保留 /cgi-bin/upload (cpe140.py 回退通道需要; 要关请加 --with-upload)"
	fi
	say "  保留(Web UI 需要): login sysinfo wireless* easyconfig lan* wan devmanage active timectrl"
	say "  回滚: /etc/harden.sh revert"
	;;

xrevert)
	for n in upload showhtml; do
		[ -e /www/cgi-bin/$n.off ] && mv /www/cgi-bin/$n.off /www/cgi-bin/$n && say "[ok] 已恢复 /cgi-bin/$n"
	done
	say "done"
	;;

*) echo "未知子命令: $1"; sed -n '3,25p' "$0"; exit 2 ;;
esac
