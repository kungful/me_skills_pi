package com.guantianxia.app.core

import android.content.Context
import android.content.SharedPreferences
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.net.InetSocketAddress
import java.net.Proxy
import java.util.concurrent.TimeUnit

/**
 * 极简 HTTP 层：OkHttp 单例 + 可选代理 + GBK/UTF-8 自动解码。
 * 国际源在国内直连不通，所以支持「每个源单独决定是否走代理」。
 */
object Http {

    /** 干净的移动版 Chrome UA（不带 WebView 的 "wv" 标记，避免被网站拦截） */
    const val MOBILE_UA =
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"

    /** HTTP 请求（RSS / 接口）用的 UA */
    const val UA = MOBILE_UA

    private val base: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(12, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .callTimeout(50, TimeUnit.SECONDS)
        .followRedirects(true)
        .followSslRedirects(true)
        .build()

    @Volatile
    private var proxyHost: String = ""
    @Volatile
    private var proxyPort: Int = 0

    fun setProxy(host: String, port: Int) {
        proxyHost = host.trim()
        proxyPort = port
    }

    val proxyConfigured: Boolean
        get() = proxyHost.isNotEmpty() && proxyPort > 0

    private fun client(useProxy: Boolean): OkHttpClient {
        if (!useProxy || !proxyConfigured) return base
        val p = Proxy(Proxy.Type.HTTP, InetSocketAddress(proxyHost, proxyPort))
        return base.newBuilder().proxy(p).build()
    }

    /** 元器件：请求成功 + 拿到了新内容 / 304 没变 / 失败，三种情形分开 */
    data class Fetched(
        val ok: Boolean,
        /** 304：服务端说内容没变，不用重新下载和解析 */
        val notModified: Boolean,
        val body: String?,
        /** 下次带着这个值来问（If-None-Match） */
        val etag: String?
    )

    /**
     * 带 ETag 的条件请求。
     *
     * 学 AIHOT 的 `docs/agent` 说明：内容没变时服务端只回一个很小的 304，
     * 不重复下正文。定时刷新每半小时跑一次、几十个源，这一下省很多流量和电。
     */
    fun fetch(
        url: String,
        useProxy: Boolean = false,
        referer: String? = null,
        etag: String? = null
    ): Fetched {
        return try {
            val b = Request.Builder().url(url).header("User-Agent", UA)
            if (referer != null) b.header("Referer", referer)
            if (!etag.isNullOrBlank()) b.header("If-None-Match", etag)
            client(useProxy).newCall(b.build()).execute().use { resp ->
                if (resp.code == 304) return Fetched(true, true, null, etag)
                if (!resp.isSuccessful) return Fetched(false, false, null, null)
                val bytes = resp.body?.bytes() ?: return Fetched(false, false, null, null)
                Fetched(true, false, decode(bytes), resp.header("ETag"))
            }
        } catch (t: Throwable) {
            Fetched(false, false, null, null)
        }
    }

    /** 取文本，失败返回 null（不抛异常，源坏了就跳过） */
    fun text(url: String, useProxy: Boolean = false, referer: String? = null): String? {
        return try {
            val b = Request.Builder().url(url).header("User-Agent", UA)
            if (referer != null) b.header("Referer", referer)
            client(useProxy).newCall(b.build()).execute().use { resp ->
                if (!resp.isSuccessful) return null
                val bytes = resp.body?.bytes() ?: return null
                decode(bytes)
            }
        } catch (t: Throwable) {
            null
        }
    }

    /** 下载到文件，成功返回 true */
    fun download(url: String, useProxy: Boolean, dest: File): Boolean {
        return try {
            val b = Request.Builder().url(url).header("User-Agent", UA)
            client(useProxy).newCall(b.build()).execute().use { resp ->
                if (!resp.isSuccessful) return false
                val body = resp.body ?: return false
                dest.parentFile?.mkdirs()
                body.byteStream().use { input ->
                    dest.outputStream().use { output -> input.copyTo(output, 64 * 1024) }
                }
                dest.length() > 0
            }
        } catch (t: Throwable) {
            dest.delete()
            false
        }
    }

    /** 国内不少财经接口是 GBK */
    private fun decode(bytes: ByteArray): String {
        val utf8 = String(bytes, Charsets.UTF_8)
        if (utf8.indexOf('\uFFFD') < 0) return utf8
        return runCatching { String(bytes, charset("GBK")) }.getOrDefault(utf8)
    }
}

/** 本地设置：代理、过滤阈值等 */
class Prefs(context: Context) {

    private val sp: SharedPreferences =
        context.getSharedPreferences("gtx", Context.MODE_PRIVATE)

    var proxyHost: String
        get() = sp.getString("proxy_host", "") ?: ""
        set(v) = sp.edit().putString("proxy_host", v).apply()

    var proxyPort: Int
        get() = sp.getInt("proxy_port", 0)
        set(v) = sp.edit().putInt("proxy_port", v).apply()

    var useProxyForIntl: Boolean
        get() = sp.getBoolean("proxy_intl", false)
        set(v) = sp.edit().putBoolean("proxy_intl", v).apply()

    /**
     * 是否抓「外网源」（BBC/NYT/Defense News 等）。
     * 手机上有系统级 VPN/代理时默认开着 —— 不用填代理地址，OkHttp 的流量会自动走隧道。
     */
    var intlEnabled: Boolean
        get() = sp.getBoolean("intl_enabled", true)
        set(v) = sp.edit().putBoolean("intl_enabled", v).apply()

    /** 垃圾新闻过滤阈值：低于这个分数直接丢弃 */
    var junkThreshold: Int
        get() = sp.getInt("junk_threshold", 45)
        set(v) = sp.edit().putInt("junk_threshold", v).apply()

    /** 重大新闻通知开关 */
    var notifyEnabled: Boolean
        get() = sp.getBoolean("notify_enabled", true)
        set(v) = sp.edit().putBoolean("notify_enabled", v).apply()

    /** 重要度阈值：达到才发通知（默认 62） */
    var notifyThreshold: Int
        get() = sp.getInt("notify_threshold", 62)
        set(v) = sp.edit().putInt("notify_threshold", v).apply()

    /** 上次发通知的时间，用于限频（默认 15 分钟内不重复打扰） */
    var lastNotify: Long
        get() = sp.getLong("last_notify", 0L)
        set(v) = sp.edit().putLong("last_notify", v).apply()

    /** 是否已经弹过通知权限申请 */
    var askedNotify: Boolean
        get() = sp.getBoolean("asked_notify", false)
        set(v) = sp.edit().putBoolean("asked_notify", v).apply()

    var lastRefresh: Long
        get() = sp.getLong("last_refresh", 0L)
        set(v) = sp.edit().putLong("last_refresh", v).apply()

    /** 上次刷新时外网（代理/VPN）是否可用，仅用于界面提示 */
    var lastIntl: Boolean
        get() = sp.getBoolean("last_intl", false)
        set(v) = sp.edit().putBoolean("last_intl", v).apply()

    /** 上一次刷新里抓成功的外网源个数（-1 = 还没抓过） */
    var intlOkCount: Int
        get() = sp.getInt("intl_ok", -1)
        set(v) = sp.edit().putInt("intl_ok", v).apply()

    /** 累计刷新轮数 */
    var refreshRounds: Int
        get() = sp.getInt("rounds", 0)
        set(v) = sp.edit().putInt("rounds", v).apply()

    /** 后台常驻服务（前台服务）是否开启。默认开：用户明确要「关屏也能收到重大新闻」 */
    var bgEnabled: Boolean
        get() = sp.getBoolean("bg_enabled", true)
        set(v) = sp.edit().putBoolean("bg_enabled", v).apply()

    /** 油价默认看哪个省（默认广西） */
    var fuelProvince: String
        get() = sp.getString("fuel_province", "guangxi") ?: "guangxi"
        set(v) = sp.edit().putString("fuel_province", v).apply()

    /** 前台服务被系统「配额用尽」暂停过（Android 15+ 每天 6 小时上限） */
    var bgPaused: Boolean
        get() = sp.getBoolean("bg_paused", false)
        set(v) = sp.edit().putBoolean("bg_paused", v).apply()
}
