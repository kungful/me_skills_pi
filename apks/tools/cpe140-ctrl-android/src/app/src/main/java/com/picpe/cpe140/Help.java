package com.picpe.cpe140;

import android.app.Activity;
import android.app.AlertDialog;
import android.graphics.Typeface;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.core.content.ContextCompat;

import java.util.ArrayList;
import java.util.List;
import java.util.function.Consumer;

/**
 * 「命令手册 / 教程」—— 给不会 Linux 的人看的。
 *
 * 每个人命令都带一句人话说明；点一下就把命令填进终端输入框（不自动执行，留给你确认）。
 * 这里只放本设备（BHU BXO2000n-2S-Lite / OpenWrt 19.07 / busybox）真的有的东西。
 */
public final class Help {

    private Help() {
    }

    /** 一节：标题 + 若干条命令。每条是 {命令, 说明, 等级}，等级 "!" = 会断网/危险。 */
    public static class Sec {
        final String name;
        final String note;
        final String[][] items;

        Sec(String name, String note, String[][] items) {
            this.name = name;
            this.note = note;
            this.items = items;
        }
    }

    private static final String[] TIPS = {
            "命令就是「程序名 空格 参数」，例如 uptime、df -h、cat /etc/config/network。",
            "竖线 | 把前一个命令的输出交给后一个：logread | tail -40（只看最后 40 行）。",
            "cat 文件 = 显示文件内容；ls 目录 = 列目录；ps w = 看进程。",
            "点下面的命令会先填进输入框，你可以改几个字，再点「运行」。",
            "跑完 1～3 秒出结果；设备慢的时候要等，别重复点。",
            "带 ⚠ 的会断网或搞坏配置，除非你清楚在干什么，不然别点。",
            "断网先别急着重启：去「维护」点「一键诊断」（只读取证）或「立即救网」（分级软修复，从轻到重试）。",
    };

    private static final List<Sec> SECTIONS = new ArrayList<>();

    static {
        SECTIONS.add(new Sec("先认识这台设备", "最安全的几条，随便跑。", new String[][]{
                {"uname -a", "内核版本 + 硬件架构（mips）", ""},
                {"uptime", "开机多久了 + 系统负载", ""},
                {"free", "内存用了多少、还剩多少", ""},
                {"df -h", "各个分区空间（/tmp 是内存盘）", ""},
                {"cat /proc/cpuinfo | head -20", "CPU 型号与频率", ""},
                {"cat /etc/openwrt_release", "固件版本（它是 OpenWrt 19.07 改的）", ""},
                {"cat /proc/mtd", "flash 分区表（救砖要用它）", ""},
                {"cat /proc/loadavg", "一秒内的负载压力", ""},
        }));

        SECTIONS.add(new Sec("看网络", "查是谁在占带宽、通不通。", new String[][]{
                {"ip a", "所有网卡和 IP 地址", ""},
                {"ip route", "路由表（默认网关是谁）", ""},
                {"cat /proc/net/arp", "在线设备的 IP + MAC", ""},
                {"cat /proc/net/nf_conntrack | wc -l", "当前连接数（几千就有点多了）", ""},
                {"netstat -an | head -30", "正在监听的端口", ""},
                {"ping -c 3 223.5.5.5", "测外网通不通（3 个包）", ""},
                {"ping -c 3 192.168.1.1", "测上游光猫通不通", ""},
        }));

        SECTIONS.add(new Sec("看无线 / WiFi", "信号差、掉线时看这里。", new String[][]{
                {"iwconfig", "无线网卡状态（信号/速率）", ""},
                {"cat /proc/net/wireless", "信号强度原始值", ""},
                {"wifi status", "OpenWrt 的无线总览 JSON", ""},
                {"uci show wireless | head -40", "无线配置（含明文口令，别外发）", ""},
                {"cat /proc/net/wireless | tail -5", "再确认一次信号质量", ""},
        }));

        SECTIONS.add(new Sec("看日志 / 进程", "排查「为什么卡/重启」的第一手材料。", new String[][]{
                {"logread | tail -40", "系统日志最后 40 行", ""},
                {"logread | grep -i -E 'error|fail|reset' | tail -20", "只看报错和复位记录", ""},
                {"dmesg | tail -30", "内核日志（无线驱动消息在这）", ""},
                {"ps w", "正在跑的进程列表", ""},
                {"cat /proc/meminfo | head -5", "内存明细", ""},
        }));

        SECTIONS.add(new Sec("文件与配置", "看/备份设备里的东西。", new String[][]{
                {"ls -la /etc/config", "配置文件目录", ""},
                {"cat /etc/config/network", "网络配置（LAN/WAN）", ""},
                {"cat /etc/config/wireless", "无线配置（含口令）", ""},
                {"cat /etc/crontabs/root", "定时任务（定时重启就在这）", ""},
                {"ls -la /www", "网页目录（44 个文件）", ""},
                {"cp /etc/shadow /tmp/shadow.bak", "备份文件到内存盘（重启就没了）", ""},
        }));

        SECTIONS.add(new Sec("断网看门狗", "断网自动重启：连续 N 分钟不通 → 重启自己；两次至少隔 30 分钟；单次断网最多重启 3 次，之后每 6 小时才试一次（不会无限重启）。", new String[][]{
                {"/etc/netguard.sh status", "看门狗状态（计数/上次重启时间）", ""},
                {"/etc/netguard.sh test", "干跑：只算不重启", ""},
                {"/etc/netguard.sh check", "只 ping 一次看通不通", ""},
                {"/etc/netguard.sh reset", "把失败计数清零", ""},
                {"/etc/netguard.sh log", "看它的日志", ""},
                {"/etc/netguard.sh cron off", "停用（脚本保留）", ""},
                {"/etc/netguard.sh cron on", "启用（每 2 分钟巡检）", ""},
        }));

        SECTIONS.add(new Sec("分级软修复 netfix", "断网时从最轻的动作开始逐级试（强制重新检测 → 放开被固件禁用的上行 → 重拨 DHCP → 重新关联 → 重起接口 → wifi reload），网络一通就立刻停，比重启温和得多。", new String[][]{
                {"/etc/netfix.sh status", "看状态：阶梯顺序 / 当前网络 / 门户劫持 / 上行禁用旗", ""},
                {"/etc/netfix.sh check", "只查现在通不通、有没有门户劫持（不改任何东西）", ""},
                {"/etc/netfix.sh", "按阶梯修一次：哪一步救回来就立刻停", ""},
                {"DRY=1 /etc/netfix.sh", "干跑：只打印会做什么，绝不执行", ""},
                {"/etc/netfix.sh step unstuck", "只跑某一步（例：放开被固件自己立旗禁用的上行）", ""},
                {"/etc/netfix.sh log", "看它的日志", ""},
        }));

        SECTIONS.add(new Sec("⚠ 危险操作", "会断网 / 会丢配置，想清楚再动。", new String[][]{
                {"reboot", "立刻重启：断网约 40 秒", "!"},
                {"wifi reload", "重载无线：本机 WiFi 会断几秒", "!"},
                {"jffs2reset -y", "清空全部配置并重启 = 恢复出厂", "!"},
                {"mtd -r erase rootfs_data", "抹掉 overlay 分区（救砖级）", "!"},
        }));
    }

    /** 弹出「命令手册」。点某条命令 → 回填到输入框。 */
    public static void show(Activity a, Consumer<String> onPick) {
        int pad = dp(a, 14);
        LinearLayout box = new LinearLayout(a);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setBackgroundColor(ContextCompat.getColor(a, R.color.bg));
        box.setPadding(pad, pad, pad, pad);

        TextView head = new TextView(a);
        head.setText("怎么用这个终端");
        head.setTextColor(ContextCompat.getColor(a, R.color.cyan));
        head.setTextSize(13);
        head.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        box.addView(head);

        for (String t : TIPS) {
            TextView v = new TextView(a);
            v.setText("· " + t);
            v.setTextColor(ContextCompat.getColor(a, R.color.dim));
            v.setTextSize(11.5f);
            v.setPadding(0, dp(a, 5), 0, 0);
            v.setLineSpacing(dp(a, 2), 1f);
            box.addView(v);
        }

        for (Sec s : SECTIONS) {
            TextView h = new TextView(a);
            h.setText("// " + s.name);
            h.setTextColor(ContextCompat.getColor(a, R.color.violet));
            h.setTextSize(12);
            h.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
            h.setPadding(0, dp(a, 16), 0, dp(a, 6));
            box.addView(h);

            if (!TextUtils.isEmpty(s.note)) {
                TextView n = new TextView(a);
                n.setText(s.note);
                n.setTextColor(ContextCompat.getColor(a, R.color.dim));
                n.setTextSize(11);
                n.setPadding(0, 0, 0, dp(a, 6));
                box.addView(n);
            }

            for (final String[] it : s.items) {
                boolean dangerous = it.length > 2 && "!".equals(it[2]);
                LinearLayout row = new LinearLayout(a);
                row.setOrientation(LinearLayout.VERTICAL);
                row.setBackgroundResource(R.drawable.bg_card);
                row.setPadding(dp(a, 10), dp(a, 9), dp(a, 10), dp(a, 9));
                LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
                lp.bottomMargin = dp(a, 6);
                row.setLayoutParams(lp);

                TextView c = new TextView(a);
                c.setText((dangerous ? "⚠  " : "$  ") + it[0]);
                c.setTextColor(ContextCompat.getColor(a, dangerous ? R.color.red : R.color.cyan));
                c.setTextSize(12.5f);
                c.setTypeface(Typeface.MONOSPACE);
                row.addView(c);

                TextView d = new TextView(a);
                d.setText(it[1]);
                d.setTextColor(ContextCompat.getColor(a, R.color.text2));
                d.setTextSize(11);
                d.setPadding(dp(a, 18), dp(a, 3), 0, 0);
                row.addView(d);

                row.setOnClickListener(v -> {
                    onPick.accept(it[0]);
                    DialogHolder.dismiss();
                });
                box.addView(row);
            }
        }

        TextView tail = new TextView(a);
        tail.setText("点任意一条 = 填进输入框（不自动跑）。\n"
                + "想自己敲也行：输入框里打字，然后点「运行」。");
        tail.setTextColor(ContextCompat.getColor(a, R.color.dim));
        tail.setTextSize(11);
        tail.setGravity(Gravity.START);
        tail.setPadding(0, dp(a, 18), 0, 0);
        box.addView(tail);

        ScrollView sc = new ScrollView(a);
        sc.setBackgroundColor(ContextCompat.getColor(a, R.color.bg));
        sc.addView(box);

        AlertDialog d = new AlertDialog.Builder(a)
                .setTitle("命令手册 / 教程")
                .setView(sc)
                .setPositiveButton("关闭", null)
                .create();
        DialogHolder.current = d;
        d.show();
    }

    /** 存一下，让条目点击能关掉对话框。 */
    private static final class DialogHolder {
        static AlertDialog current;

        static void dismiss() {
            if (current != null && current.isShowing()) {
                current.dismiss();
            }
            current = null;
        }
    }

    private static int dp(Activity a, int v) {
        return Math.round(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v,
                a.getResources().getDisplayMetrics()));
    }
}
