package com.guantianxia.app.repo

import android.content.Context
import com.guantianxia.app.core.Http
import com.guantianxia.app.core.Prefs
import com.guantianxia.app.core.TimeUtil
import com.guantianxia.app.data.Article
import com.guantianxia.app.data.Db
import com.guantianxia.app.data.FeedSource
import com.guantianxia.app.data.Kind
import com.guantianxia.app.filter.Classify
import com.guantianxia.app.filter.Cluster
import com.guantianxia.app.filter.Importance
import com.guantianxia.app.filter.JunkFilter
import com.guantianxia.app.filter.SimHash
import com.guantianxia.app.core.Notify
import com.guantianxia.app.net.FeedParser
import com.guantianxia.app.net.HtmlList
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.withContext

/**
 * 抓取 → 打分 → 去重 → 入库
 */
class FeedRepo(private val ctx: Context) {

    private val db = Db(ctx)
    private val prefs = Prefs(ctx)
    private val lock = Any()

    data class Stats(
        var sources: Int = 0,
        var ok: Int = 0,
        var failed: Int = 0,
        var fetched: Int = 0,
        var kept: Int = 0,
        var junk: Int = 0,
        var dup: Int = 0,
        var notified: Int = 0
    )

    suspend fun refresh(
        allowNotify: Boolean = true,
        onStatus: (String) -> Unit = {}
    ): Stats = coroutineScope {
        Http.setProxy(prefs.proxyHost, prefs.proxyPort)

        // 外网源：手机带系统级 VPN/代理时直接抓；也能用内置代理地址。
        // 这里不用「探针 URL」预检（gstatic 之类常被单独拦，会误判成外网不通），
        // 改成看上一轮的真实成绩：连续多轮一个外网源都没成功，才认定外网不通并跳过，
        // 避免每次刷新白等一大堆超时。
        val intlOff = !prefs.intlEnabled && !Http.proxyConfigured
        val intlDead = !intlOff && prefs.intlOkCount == 0 && prefs.refreshRounds >= 3
        val threshold = prefs.junkThreshold
        val sources = db.sources().filter { it.enabled && (intlOff || intlDead || !it.needsProxy) }
        val stats = Stats(sources = sources.size)
        if (sources.isEmpty()) return@coroutineScope stats
        if (!intlOff && intlDead) onStatus("外网不通，本轮只刷国内源")

        val seen = ArrayList<Long>()
        seen.addAll(db.recentHashes(3000).toList())

        val batch = ArrayList<Article>()
        val sem = Semaphore(6)
        val okIds = HashSet<String>()
        val etagToSave = HashMap<String, String>()

        val jobs = sources.map { src ->
            async(Dispatchers.IO) {
                sem.withPermit {
                    onStatus("抓取 ${src.name} …")
                    // 一个源可以是多个页面（空格分隔）
                    val raws = ArrayList<FeedParser.Raw>()
                    // 有源回了 304（内容没变）就不算失败
                    var anyNotModified = false
                    val urls = src.url.split(" ")
                    for ((idx, u) in urls.withIndex()) {
                        if (u.isBlank()) continue
                        // 带上上次的 ETag：内容没变服务端只回 304，不用重下也不用重新解析。
                        // 多页面的源只有第一页带（ETag 是整份响应的，不能混用）
                        val cached = if (idx == 0) src.etag else ""
                        val r = Http.fetch(u, useProxy = src.needsProxy, etag = cached)
                        if (r.notModified) {
                            // 内容没变，直接当这个源抓成功（没新东西）
                            anyNotModified = true
                            synchronized(lock) {
                                stats.ok++
                                okIds.add(src.id)
                            }
                            continue
                        }
                        if (!r.ok || r.body == null) continue
                        if (idx == 0 && !r.etag.isNullOrBlank()) etagToSave[src.id] = r.etag!!
                        raws.addAll(fetch(src, r.body))
                    }
                    if (raws.isEmpty()) {
                        // 304 说明源是好的，没新内容而已，不能记成失败
                        if (!anyNotModified) synchronized(lock) { stats.failed++ }
                        return@withPermit
                    }
                    synchronized(lock) {
                        stats.ok++
                        stats.fetched += raws.size
                        okIds.add(src.id)
                    }
                    val local = ArrayList<Article>()
                    for (r in raws) {
                        val sc = JunkFilter.score(r.title, r.desc, src)
                        if (JunkFilter.isJunk(sc, threshold)) {
                            synchronized(lock) { stats.junk++ }
                            continue
                        }
                        val sh = SimHash.of(r.title)
                        val isDup = synchronized(lock) {
                            if (sh == 0L) {
                                false
                            } else if (seen.any { SimHash.isDup(it, sh) }) {
                                true
                            } else {
                                seen.add(sh)
                                false
                            }
                        }
                        if (isDup) {
                            synchronized(lock) { stats.dup++ }
                            continue
                        }
                        val pub = if (r.ts > 0L) {
                            r.ts
                        } else {
                            TimeUtil.parse(r.date).let { if (it > 0L) it else System.currentTimeMillis() }
                        }
                        val cat = if (r.category.isNotBlank()) r.category else src.category
                        local.add(
                            Article(
                                title = r.title,
                                url = r.link,
                                summary = r.desc.take(220),
                                sourceId = src.id,
                                sourceName = src.name,
                                category = cat,
                                publishedAt = pub,
                                score = sc,
                                simhash = sh
                            )
                        )
                    }
                    synchronized(lock) { batch.addAll(local) }
                }
            }
        }
        jobs.awaitAll()

        val inserted = withContext(Dispatchers.IO) { db.insertArticles(batch) }
        stats.kept = inserted.size
        // 保存本轮的 ETag，下轮刷新就能走 304
        withContext(Dispatchers.IO) {
            for ((id, e) in etagToSave) runCatching { db.setSourceEtag(id, e) }
        }
        prefs.lastRefresh = System.currentTimeMillis()
        // 学 AIHOT：把同一件事的多篇报道归成一个事件，并统计有几个独立来源在说
        val srcCounts = withContext(Dispatchers.IO) {
            runCatching { db.clusterNewly(inserted) }.getOrDefault(emptyMap())
        }
        // 记下这轮外网源的成绩，供下一轮判断外网是否真的不通
        synchronized(lock) {
            if (intlDead) {
                // 本轮直接跳过了外网：给它 3 轮冷却后再试。
                // 不能只是不更新 intlOkCount，否则「0 + rounds>=3」会一直成立 → 外网永久不抓。
                prefs.refreshRounds = 0
            } else {
                prefs.intlOkCount = sources.count { it.needsProxy && okIds.contains(it.id) }
                prefs.refreshRounds += 1
            }
            prefs.lastIntl = !intlOff && !intlDead
        }

        if (allowNotify) stats.notified = notifyImportant(sources, inserted, srcCounts)

        withContext(Dispatchers.IO) { db.prune(21) }
        stats
    }

    /** 按源的类型选解析器；每个源最多取 20 条（外网源一刷几十条，不限制会撑爆库） */
    private fun fetch(src: FeedSource, body: String): List<FeedParser.Raw> = when (src.kind) {
        Kind.GUANCHA -> HtmlList.guancha(body, limit = 40)
        else -> FeedParser.parse(body, limit = 20)
    }

    /**
     * 从本次新入库的新闻里挑出「重大新闻」发通知。
     * 限频：两条通知之间至少隔 [NOTIFY_GAP]（避免下拉刷新时反复弹）。
     * 返回实际通知的条数。
     */
    private fun notifyImportant(
        sources: List<FeedSource>,
        inserted: List<Article>,
        srcCounts: Map<Long, Int>
    ): Int {
        if (inserted.isEmpty()) return 0
        if (!prefs.notifyEnabled) return 0
        if (!Notify.canPost(ctx)) return 0

        val now = System.currentTimeMillis()
        if (now - prefs.lastNotify < NOTIFY_GAP) return 0

        val byId = sources.associateBy { it.id }
        val threshold = prefs.notifyThreshold

        val picked = inserted
            // 旧文不刷屏（AIHOT 同款规则）：发布超 48 小时的不推送
            .filter { Cluster.isFresh(it.publishedAt, now) }
            .mapNotNull { a ->
                val src = byId[a.sourceId] ?: return@mapNotNull null
                // 多家独立媒体报道 = 更可能是真大事，把它当作一个重要信号
                val imp = Importance.score(
                    a.title, a.summary, src, a.score,
                    srcCounts[a.id] ?: 0
                )
                if (Importance.isImportant(imp, threshold)) a to imp else null
            }
            .sortedByDescending { it.second }
            .take(3)
            .map { it.first }

        if (picked.isEmpty()) return 0
        Notify.important(ctx, picked)
        prefs.lastNotify = now
        return picked.size
    }

    companion object {
        /** 通知限频间隔 */
        const val NOTIFY_GAP = 15L * 60 * 1000
    }
}
