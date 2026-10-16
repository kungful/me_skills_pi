package com.guantianxia.app

import android.app.Application
import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.guantianxia.app.core.Notify
import com.guantianxia.app.core.Prefs
import com.guantianxia.app.work.BgService
import com.guantianxia.app.work.RefreshWorker
import java.util.concurrent.TimeUnit

class App : Application() {

    override fun onCreate() {
        super.onCreate()
        runCatching { Notify.ensureChannels(this) }
        fixDebugPrefs()
        applyRefreshPolicy(this)
    }

    /**
     * 修掉调试期间留下的异常值：通知阈值 0 会让「每条新闻都弹」。
     * 用户从没设置过阈值，所以这里直接拉回默认 62。
     */
    private fun fixDebugPrefs() {
        val p = Prefs(this)
        if (p.notifyThreshold <= 0) p.notifyThreshold = 62
    }

    companion object {

        /**
         * 双保险：
         *  - 开了「后台运行」→ 前台服务每 30 分钟抓一次（主力，存活率高）；
         *  - WorkManager 始终保留一个 60 分钟的周期任务作兜底（前台服务被系统杀/配额用尽时它还能顶）。
         * 两边同时抓到重复内容也没关系：URL 唯一 + SimHash 去重。
         */
        fun applyRefreshPolicy(ctx: Context) {
            val prefs = Prefs(ctx)
            if (prefs.bgEnabled) {
                runCatching { BgService.start(ctx) }
            } else {
                runCatching { BgService.stop(ctx) }
            }
            runCatching {
                val constraints = Constraints.Builder()
                    .setRequiredNetworkType(NetworkType.CONNECTED)
                    .build()
                val request = PeriodicWorkRequestBuilder<RefreshWorker>(60, TimeUnit.MINUTES)
                    .setConstraints(constraints)
                    .setBackoffCriteria(BackoffPolicy.LINEAR, 5, TimeUnit.MINUTES)
                    .build()
                WorkManager.getInstance(ctx).enqueueUniquePeriodicWork(
                    WORK_NAME,
                    ExistingPeriodicWorkPolicy.UPDATE,
                    request
                )
            }
        }

        private const val WORK_NAME = "gtx-refresh"
    }
}
