package com.vocabtype.app.core

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.drawable.Icon
import android.os.Build
import android.os.IBinder

/**
 * 后台朗读用的前台服务。
 *
 * 为什么必须有它：Activity 一退到后台就可能被冻结，里面跑的 MediaPlayer / TTS
 * 会被系统掐掉。前台服务带常驻通知，进程被提到前台优先级，锁屏也照常出声。
 *
 * 播放器本身是进程内单例 [VoiceBox]，服务只负责「保活 + 通知 + 遥控按钮」，
 * 所以界面上的播放/暂停和服务里的操作都是同一个实例，不会打架。
 */
class SpeakService : Service() {

    companion object {
        const val CH = "vt_speak"
        const val ID = 1001

        const val A_TOGGLE = "com.vocabtype.app.SPEAK_TOGGLE"
        const val A_STOP = "com.vocabtype.app.SPEAK_STOP"

        @Volatile
        var alive = false
            private set

        /** 起服务（幂等）。Android 12+ 不允许后台启动前台服务，所以只在界面里调 */
        fun ensure(ctx: Context) {
            if (alive) return
            runCatching {
                val i = Intent(ctx, SpeakService::class.java)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    ctx.startForegroundService(i)
                } else {
                    ctx.startService(i)
                }
            }
        }

        fun stopService(ctx: Context) {
            runCatching { ctx.stopService(Intent(ctx, SpeakService::class.java)) }
        }
    }

    private lateinit var prefs: Prefs
    private var speaker: Speaker? = null

    /** 用固定引用，方便解绑 */
    private val stateHook: () -> Unit = { post() }

    override fun onCreate() {
        super.onCreate()
        alive = true
        prefs = Prefs(this)
        createChannel()
        speaker = VoiceBox.get(this, prefs)
        speaker?.addStateListener(stateHook)
        startForegroundCompat(build())
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            A_TOGGLE -> {
                val s = speaker ?: VoiceBox.get(this, prefs)
                if (s.nowPlaying) s.pause() else s.resume()
            }

            A_STOP -> {
                speaker?.stop()
            }
        }
        post()
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        alive = false
        speaker?.removeStateListener(stateHook)
        super.onDestroy()
    }

    // ------------------------------------------------------------ 通知

    private fun createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = getSystemService(NotificationManager::class.java) ?: return
        if (nm.getNotificationChannel(CH) != null) return
        val ch = NotificationChannel(CH, "后台朗读", NotificationManager.IMPORTANCE_LOW).apply {
            description = "循环朗读单词和句子时显示"
            setShowBadge(false)
            enableVibration(false)
            setSound(null, null)
        }
        nm.createNotificationChannel(ch)
    }

    private fun icon(name: String): Int =
        resources.getIdentifier(name, "drawable", packageName)

    private fun build(): Notification {
        val s = speaker
        val playing = s?.nowPlaying == true
        val label = s?.nowLabel?.take(48).orEmpty()
        val open = Intent(this, Class.forName("com.vocabtype.app.ui.MainActivity"))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        val pi = PendingIntent.getActivity(
            this, 0, open,
            PendingIntent.FLAG_UPDATE_CURRENT or
                    (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0)
        )

        val b = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, CH)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
        }
        b.setContentTitle(if (playing) "词打 · 朗读中" else "词打 · 已暂停")
            .setContentText(if (label.isBlank()) "点开继续练" else label)
            .setSmallIcon(icon("ic_notif"))
            .setContentIntent(pi)
            .setOngoing(playing)
            .setOnlyAlertOnce(true)
            .setShowWhen(false)

        // 暂停/继续
        val toggle = if (playing) "ic_pause" else "ic_play_small"
        val toggleLabel = if (playing) "暂停" else "继续"
        b.addAction(action(toggle, toggleLabel, A_TOGGLE))
        b.addAction(action("ic_close", "停止", A_STOP))
        return b.build()
    }

    private fun action(iconName: String, title: String, act: String): Notification.Action {
        val i = Intent(this, SpeakService::class.java).setAction(act)
        val p = PendingIntent.getService(
            this, act.hashCode(), i,
            PendingIntent.FLAG_UPDATE_CURRENT or
                    (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0)
        )
        val iconId = icon(iconName)
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            Notification.Action.Builder(Icon.createWithResource(this, iconId), title, p).build()
        } else {
            @Suppress("DEPRECATION")
            Notification.Action.Builder(iconId, title, p).build()
        }
    }

    private fun post() {
        if (!alive) return
        runCatching {
            val nm = getSystemService(NotificationManager::class.java)
            nm?.notify(ID, build())
        }
    }

    private fun startForegroundCompat(n: Notification) {
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK)
        } else {
            startForeground(ID, n)
        }
    }
}
