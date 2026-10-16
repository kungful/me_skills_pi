package com.guantianxia.app.work

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import androidx.annotation.RequiresApi
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import com.guantianxia.app.R
import com.guantianxia.app.core.Http
import com.guantianxia.app.core.Notify
import com.guantianxia.app.core.Prefs
import com.guantianxia.app.data.Db
import com.guantianxia.app.repo.FeedRepo
import com.guantianxia.app.ui.MainActivity
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * 后台常驻服务（前台服务）—— 这是「关屏也能收到重大新闻」的主力。
 *
 * 为什么不用 WorkManager 单独撑着：国产 ROM（vivo/小米/OPPO）会把 WorkManager 的
 * 周期任务往后拖，甚至干脆不跑，表现就是「不打开 App 就永远不更新、不通知」。
 * 前台服务带常驻通知，系统按「用户可见的活进程」对待，存活率高得多。
 *
 * 注意：Android 15+ 给 dataSync 型前台服务加了「每天累计 6 小时」的上限，
 * 到点系统会回调 [onTimeout]，这里主动收摊（不然系统直接抛异常崩掉）。
 * 所以 WorkManager 仍然保留作兜底，见 App.applyRefreshPolicy()。
 */
class BgService : Service() {

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val timer = Handler(Looper.getMainLooper())

    @Volatile
    private var fetching = false

    /** 下一次抓取的时间点，用来在通知上显示真实倒计时 */
    @Volatile
    private var nextAt = 0L

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        val p = Prefs(this)
        Http.setProxy(p.proxyHost, p.proxyPort)
        Notify.ensureChannels(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!Prefs(this).bgEnabled || intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        // 先排下一次，nextAt 才会被更新，通知上的倒计时才准
        scheduleNow()
        if (!goForeground(getString(R.string.bg_running), 0)) {
            stopSelf()
            return START_NOT_STICKY
        }
        return START_STICKY
    }

    /**
     * Android 15+：dataSync 前台服务每天跑满 6 小时后系统回调这里，
     * 必须在几秒内停掉，否则抛 ForegroundServiceDidNotStopInTimeException。
     */
    @RequiresApi(Build.VERSION_CODES.VANILLA_ICE_CREAM)
    override fun onTimeout(startId: Int) {
        Prefs(this).bgPaused = true
        stopSelf()
    }

    override fun onDestroy() {
        timer.removeCallbacksAndMessages(null)
        scope.cancel()
        super.onDestroy()
    }

    private fun scheduleNow() = schedule(400L)

    private fun schedule(delay: Long) {
        timer.removeCallbacks(tick)
        nextAt = System.currentTimeMillis() + delay
        timer.postDelayed(tick, delay)
    }

    private val tick = Runnable {
        if (fetching) {
            schedule(INTERVAL_MS)
            return@Runnable
        }
        fetching = true
        if (!goForeground(getString(R.string.bg_fetching), -1)) {
            stopSelf()
            return@Runnable
        }
        scope.launch {
            var tail = ""
            try {
                val stats = FeedRepo(applicationContext).refresh(allowNotify = true)
                tail = " · " + getString(R.string.bg_new, stats.kept)
            } catch (t: Throwable) {
                tail = " · " + getString(R.string.bg_failed)
            }
            withContext(Dispatchers.Main) {
                fetching = false
                val total = runCatching { Db(applicationContext).articleCount() }.getOrDefault(0)
                val text = getString(R.string.bg_running) + tail +
                    " · " + getString(R.string.bg_total, total)
                // 同样：先 schedule 再刷通知，倒计时才是「距下次刷新」
                schedule(INTERVAL_MS)
                if (!goForeground(text, INTERVAL_MIN)) {
                    stopSelf()
                    return@withContext
                }
            }
        }
    }

    /** 真正把服务推成前台；失败返回 false（调用方要 stopSelf） */
    private fun goForeground(text: String, minutes: Int): Boolean {
        val body = if (minutes < 0) text else "$text · ${nextText(minutes)}"
        val n: Notification = NotificationCompat.Builder(this, Notify.CHANNEL_BG)
            .setSmallIcon(R.drawable.ic_news)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(body)
            .setOngoing(true)
            .setShowWhen(false)
            .setPriority(NotificationCompat.PRIORITY_MIN)
            .setSilent(true)
            .setContentIntent(
                PendingIntent.getActivity(
                    this, 0,
                    Intent(this, MainActivity::class.java)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
                    PendingIntent.FLAG_IMMUTABLE
                )
            )
            .addAction(
                0, getString(R.string.bg_stop),
                PendingIntent.getService(
                    this, 1,
                    Intent(this, BgService::class.java).setAction(ACTION_STOP),
                    PendingIntent.FLAG_IMMUTABLE
                )
            )
            .build()
        return try {
            ServiceCompat.startForeground(
                this, Notify.ID_BG, n,
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
                } else {
                    0
                }
            )
            true
        } catch (t: Throwable) {
            false
        }
    }

    /** 通知上那句话：优先显示相对真实剩余时间 */
    private fun nextText(minutes: Int): String {
        val left = if (nextAt > 0L) {
            ((nextAt - System.currentTimeMillis()) / 60_000L).toInt().coerceAtLeast(0)
        } else {
            minutes
        }
        return getString(R.string.bg_next, if (left <= 0) 1 else left)
    }

    companion object {
        private const val ACTION_STOP = "com.guantianxia.app.STOP_BG"

        /** 抓取间隔（分钟） */
        const val INTERVAL_MIN = 30
        private const val INTERVAL_MS = INTERVAL_MIN * 60_000L

        fun start(ctx: Context) {
            val i = Intent(ctx, BgService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) ctx.startForegroundService(i)
            else ctx.startService(i)
        }

        fun stop(ctx: Context) {
            runCatching { ctx.stopService(Intent(ctx, BgService::class.java)) }
        }
    }
}

/** 开机自启，免去每次手动点开关 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val a = intent.action ?: return
        if (a != Intent.ACTION_BOOT_COMPLETED && a != Intent.ACTION_MY_PACKAGE_REPLACED) return
        if (!Prefs(context).bgEnabled) return
        runCatching { BgService.start(context) }
    }
}
