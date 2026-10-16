package io.pilink

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import java.util.Random

object Notifier {

    const val CH_ALERT = "pilink-alert"      // 报错 / 中断 / 失联 → 高优先级
    const val CH_DONE = "pilink-done"        // 正常完成 → 普通
    const val CH_SERVICE = "pilink-service"  // 常驻连接状态（前台服务）
    const val FGS_ID = 1001
    private const val GROUP = "pilink"
    private const val ACCENT = 0xFF0F766E.toInt()

    fun ensureChannels(ctx: Context) {        val nm = ctx.getSystemService(NotificationManager::class.java) ?: return
        // 渠道属性（重要性/声音/震动）在首次创建后就锁死，App 改不了、只能用户改，
        // 所以这三条参数必须一次定对。声音故意【不】显式设：不调用 setSound 时
        // IMPORTANCE_HIGH 渠道就用系统默认提示音，且用户仍然可以自己换。
        nm.createNotificationChannel(
            NotificationChannel(CH_ALERT, "Pi 报错 / 中断", NotificationManager.IMPORTANCE_HIGH).apply {
                description = "会话报错、工具中断、卡死、pi-web 失联。会响铃并震动。"
                enableVibration(true)
                enableLights(true)
                setShowBadge(true)
            }
        )
        nm.createNotificationChannel(
            NotificationChannel(CH_DONE, "Pi 任务完成", NotificationManager.IMPORTANCE_DEFAULT).apply {
                description = "会话正常结束"
            }
        )
        nm.createNotificationChannel(
            NotificationChannel(CH_SERVICE, "连接状态（常驻）", NotificationManager.IMPORTANCE_MIN).apply {
                description = "保持与通知服务器的连接。删掉这个通知连接就会断。"
                setShowBadge(false)
            }
        )
    }

    /** 前台服务的常驻通知：它同时也是"连接是否健康"的仪表盘 */    fun service(ctx: Context, text: String): Notification =
        Notification.Builder(ctx, CH_SERVICE)
            .setSmallIcon(R.drawable.ic_pilink)
            .setContentTitle(ctx.getString(R.string.app_name))
            .setContentText(text)
            .setOngoing(true)
            .setShowWhen(false)
            .setContentIntent(openApp(ctx))
            .build()

    fun updateService(ctx: Context, text: String) {
        val nm = ctx.getSystemService(NotificationManager::class.java) ?: return
        nm.notify(FGS_ID, service(ctx, text))
    }

    /**
     * 消息通知。
     *
     * 动作按钮的构造刻意对齐上一版第三方客户端 —— 因为它在这台 ColorOS 上
     * 确实能显示三个按钮，差别只在细节上：
     *   · 动作【不带图标】（旧版用的是 `NotificationCompat.Action.Builder(0, …)`）。
     *     实测我们之前给动作传了一个矢量图标，结果只出来第一个按钮。
     *   · Intent 要带 GRANT_READ_URI_PERMISSION | NEW_TASK | CLEAR_TASK
     *   · PendingIntent 用随机 requestCode（避免不同 URL 被当成同一个 PI 复用）
     *   · setOnlyAlertOnce(true)：同一条通知更新时不再响铃/震动
     */
    fun post(ctx: Context, m: Msg) {
        val nm = ctx.getSystemService(NotificationManager::class.java) ?: return
        val alert = m.priority >= 4
        val channel = if (alert) CH_ALERT else CH_DONE
        val id = m.id.hashCode()

        val builder = Notification.Builder(ctx, channel)
            .setSmallIcon(R.drawable.ic_pilink)
            .setColor(ACCENT)
            .setContentTitle(m.title)
            .setContentText(m.body)
            .setStyle(Notification.BigTextStyle().bigText(m.body))
            .setWhen(if (m.time > 0) m.time else System.currentTimeMillis())
            .setShowWhen(true)
            .setOnlyAlertOnce(true)
            .setAutoCancel(true)
            // 锁屏直接显示内容。默认是 VISIBILITY_PRIVATE，锁屏上只显示“内容已隐藏”——
            // 而“息屏/锁屏能不能一眼看到是什么事”才是这个 App 的用处。
            .setVisibility(Notification.VISIBILITY_PUBLIC)
            // 语义正确的分类：报错类走 CATEGORY_ERROR，完成类走 CATEGORY_STATUS。
            // 部分 ROM 会据此调整排序/分组。
            .setCategory(if (alert) Notification.CATEGORY_ERROR else Notification.CATEGORY_STATUS)
            .setGroup(m.group ?: GROUP)

        m.click?.let { builder.setContentIntent(pi(ctx, it)) }

        m.actions.take(3).forEach { action ->
            if (action.url.isNotEmpty()) builder.addAction(actionButton(action.label, pi(ctx, action.url)))
        }

        nm.notify(id, builder.build())
    }

    /** 没有图标的动作按钮。图标一律不看：SystemUI 在动作位上对矢量图标支持不好。 */
    @Suppress("DEPRECATION")
    private fun actionButton(label: String, pendingIntent: PendingIntent): Notification.Action =
        Notification.Action.Builder(0, label, pendingIntent).build()

    private fun pi(ctx: Context, url: String): PendingIntent {
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
            addFlags(
                Intent.FLAG_GRANT_READ_URI_PERMISSION or
                    Intent.FLAG_ACTIVITY_NEW_TASK or
                    Intent.FLAG_ACTIVITY_CLEAR_TASK
            )
        }
        return PendingIntent.getActivity(ctx, Random().nextInt(), intent, PendingIntent.FLAG_IMMUTABLE)
    }

    private fun openApp(ctx: Context): PendingIntent {
        val intent = Intent(ctx, MainActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        }
        return PendingIntent.getActivity(ctx, 0, intent, PendingIntent.FLAG_IMMUTABLE)
    }

    /**
     * 系统是不是会静默丢弃我们的通知？返回原因，没事就返回 null。
     *
     * 为什么必须有它：“消息到了 App（历史列表里看得见）但一条弹窗都没有”——
     * 这时 Transport 完全正常，是 NotificationManager.notify() 被系统默默扔了：
     * 它不报错、不抛异常，所以只能在发之前先问一句。
     */
    fun blockedReason(ctx: Context): String? {
        val nm = ctx.getSystemService(NotificationManager::class.java) ?: return "拿不到通知服务"
        if (!nm.areNotificationsEnabled()) return "系统里把本应用的通知关掉了"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ctx.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            return "通知权限未授予（POST_NOTIFICATIONS）"
        }
        for (id in listOf(CH_ALERT, CH_DONE)) {
            val channel = runCatching { nm.getNotificationChannel(id) }.getOrNull() ?: continue
            if (channel.importance == NotificationManager.IMPORTANCE_NONE) return "渠道「${channel.name}」被设为「关闭」"
        }
        return null
    }
}
