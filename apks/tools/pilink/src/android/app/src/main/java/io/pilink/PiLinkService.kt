package io.pilink

import android.app.AlarmManager
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.os.SystemClock
import android.util.Log

/**
 * 常驻订阅服务。
 *
 * 两个刻意的设计决定：
 *  · foregroundServiceType = specialUse（见清单注释）—— 不是 dataSync，
 *    避开 Android 15+ 对 dataSync 的每 24 小时 6 小时超时限制。
 *  · 自愈闹钟用 setAndAllowWhileIdle，**不用 setExact** —— 不需要
 *    SCHEDULE_EXACT_ALARM 特殊权限，也就不会重复旧客户端"权限缺失就静默放弃重连"那个坑。
 */
class PiLinkService : Service() {

    private lateinit var prefs: Prefs
    private var subscriber: Subscriber? = null
    private var wakeLock: PowerManager.WakeLock? = null

    override fun onCreate() {
        super.onCreate()
        prefs = Prefs(this)
        Notifier.ensureChannels(this)
        try {
            val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
            wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "pilink:subscriber").apply {
                setReferenceCounted(false)
                acquire()
            }
        } catch (e: Exception) {
            Log.w(TAG, "WakeLock 未取得：${e.message}")
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                shutdown()
                return START_NOT_STICKY
            }
            ACTION_KICK -> {
                Log.i(TAG, "自愈闹钟/界面要求体检")
                // 走 healthCheck 而不是 kick：链路正常时不要动它。
                // 以前无条件 kick 等于每 5 分钟自己把健康的流掐一次。
                subscriber?.healthCheck()
                scheduleSelfHeal()
                return START_STICKY
            }
            ACTION_RELOAD -> {
                // 设置页改了心跳/轮询参数后走这里：把旧的订阅端拆掉重建，让新值立刻生效。
                Log.i(TAG, "参数已修改，重建订阅端")
                startAsForeground("重载参数…")
                rebuild()
                scheduleSelfHeal()
                return START_STICKY
            }
        }

        startAsForeground(prefs.status)
        if (subscriber == null) rebuild()
        scheduleSelfHeal()
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    /** 从最近任务里划掉时，1 秒后把自己拉回来（这套是上一版在 ColorOS 上验证过能活的写法） */
    override fun onTaskRemoved(rootIntent: Intent?) {
        val pi = PendingIntent.getService(
            this,
            RC_RESTART,
            Intent(this, PiLinkService::class.java).setAction(ACTION_START),
            PendingIntent.FLAG_ONE_SHOT or PendingIntent.FLAG_IMMUTABLE,
        )
        try {
            val am = getSystemService(Context.ALARM_SERVICE) as AlarmManager
            am.set(AlarmManager.ELAPSED_REALTIME, SystemClock.elapsedRealtime() + 1_000, pi)
        } catch (e: Exception) {
            Log.w(TAG, "onTaskRemoved 重排失败：${e.message}")
        }
    }

    override fun onDestroy() {
        subscriber?.stop()
        subscriber = null
        try {
            wakeLock?.let { if (it.isHeld) it.release() }
        } catch (e: Exception) {
            // 忽略
        }
        super.onDestroy()
    }

    // ── 内部 ───────────────────────────────────────────────────────────────

    private fun rebuild() {
        subscriber?.stop()
        subscriber = null
        prefs.enabled = true
        subscriber = Subscriber(this, prefs, ::deliver, ::setStatus).also { it.start() }
    }

    private fun deliver(msg: Msg) {
        Log.i(TAG, "通知 [${msg.priority}] ${msg.title} — ${msg.body}")
        Notifier.post(this, msg)
        prefs.addHistory(msg)
    }

    private fun setStatus(text: String) {
        prefs.status = text
        Notifier.updateService(this, text)
    }

    private fun startAsForeground(text: String) {
        val notification = Notifier.service(this, text)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(Notifier.FGS_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        } else {
            startForeground(Notifier.FGS_ID, notification)
        }
    }

    /**
     * 周期性自愈：即使常驻协程因为任何原因没在跑，这个闹钟也会在 5 分钟内把服务
     * 重新拉起来一次（然后 onStartCommand 会重新排下一条，形成闭环）。
     * setAndAllowWhileIdle 不需要特殊权限；因为本进程是前台服务，系统不会把它压到很久以后。
     */
    private fun scheduleSelfHeal() {
        val pi = PendingIntent.getService(
            this,
            RC_HEAL,
            Intent(this, PiLinkService::class.java).setAction(ACTION_KICK),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        try {
            val am = getSystemService(Context.ALARM_SERVICE) as AlarmManager
            am.setAndAllowWhileIdle(
                AlarmManager.ELAPSED_REALTIME_WAKEUP,
                SystemClock.elapsedRealtime() + SELF_HEAL_MS,
                pi,
            )
        } catch (e: Exception) {
            Log.w(TAG, "自愈闹钟排不上：${e.message}")
        }
    }

    private fun shutdown() {
        prefs.enabled = false
        subscriber?.stop()
        subscriber = null
        try {
            (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).cancel(Notifier.FGS_ID)
        } catch (e: Exception) {
            // 忽略
        }
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    companion object {
        private const val TAG = "PiLink"
        const val ACTION_START = "io.pilink.START"
        const val ACTION_STOP = "io.pilink.STOP"
        const val ACTION_KICK = "io.pilink.KICK"
        const val ACTION_RELOAD = "io.pilink.RELOAD"
        private const val SELF_HEAL_MS = 5 * 60_000L
        private const val RC_HEAL = 2001
        private const val RC_RESTART = 2002

        fun start(ctx: Context) = send(ctx, ACTION_START)

        fun stop(ctx: Context) = send(ctx, ACTION_STOP)

        fun kick(ctx: Context) = send(ctx, ACTION_KICK)

        /** 参数改了之后重建订阅端，让新的心跳/轮询间隔立刻生效 */
        fun reload(ctx: Context) = send(ctx, ACTION_RELOAD)

        private fun send(ctx: Context, action: String) {
            val intent = Intent(ctx, PiLinkService::class.java).setAction(action)
            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) ctx.startForegroundService(intent)
                else ctx.startService(intent)
            } catch (e: Exception) {
                // Android 12+ 的后台启动前台服务限制：由守护路径（开机/自愈闹钟）触发时可能被拒，
                // 这不是致命错误——START_STICKY 和自愈闹钟会补上。
                Log.w(TAG, "发送 $action 失败：${e.message}")
            }
        }
    }
}
