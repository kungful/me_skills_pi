package com.guantianxia.app.work

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.guantianxia.app.repo.FeedRepo

/** 后台定时抓取（30 分钟一次，由 WorkManager 调度） */
class RefreshWorker(context: Context, params: WorkerParameters) :
    CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        return try {
            FeedRepo(applicationContext).refresh()
            Result.success()
        } catch (t: Throwable) {
            Result.retry()
        }
    }
}
