package com.guantianxia.app.ui

import android.annotation.SuppressLint
import android.graphics.Bitmap
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.webkit.CookieManager
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.ImageButton
import android.widget.ProgressBar
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import com.guantianxia.app.R
import com.guantianxia.app.core.EdgeToEdge
import com.guantianxia.app.core.Http

/**
 * 应用内预览：WebView 直接读全文，不用跳浏览器。
 * 顶栏可以分享（微信/QQ/微博…都走系统分享面板）、复制链接、跳浏览器。
 */
class ArticleActivity : AppCompatActivity() {

    private lateinit var web: WebView
    private lateinit var progress: ProgressBar
    private lateinit var errorPanel: View
    private lateinit var tvError: TextView

    private var currentUrl = ""
    private var shareTitle = ""
    private var shareSummary = ""
    private var shareSource = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_article)

        val root = findViewById<View>(R.id.root)
        val appbar = findViewById<View>(R.id.appbar)
        web = findViewById(R.id.web)
        progress = findViewById(R.id.progress)
        errorPanel = findViewById(R.id.error_panel)
        tvError = findViewById(R.id.tv_error)

        EdgeToEdge.install(this, root, lightStatusIcons = false) { b ->
            root.setPadding(b.l, 0, b.r, b.b)
            appbar.setPadding(0, b.t, 0, 0)
        }

        shareTitle = intent.getStringExtra(EXTRA_TITLE).orEmpty()
        shareSummary = intent.getStringExtra(EXTRA_SUMMARY).orEmpty()
        shareSource = intent.getStringExtra(EXTRA_SOURCE).orEmpty()
        val url = intent.getStringExtra(EXTRA_URL).orEmpty()
        currentUrl = url
        findViewById<TextView>(R.id.tv_title).text = shareTitle.ifBlank { "预览" }

        findViewById<ImageButton>(R.id.btn_back).setOnClickListener { finish() }
        findViewById<ImageButton>(R.id.btn_share).setOnClickListener {
            ArticleActions.shareDialog(this, shareTitle, shareSummary, shareSource, currentUrl)
        }
        findViewById<ImageButton>(R.id.btn_browser).setOnClickListener { openInBrowser() }
        findViewById<View>(R.id.btn_retry).setOnClickListener { load(url) }
        findViewById<View>(R.id.btn_open_browser).setOnClickListener { openInBrowser() }

        setupWebView(url)

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (web.canGoBack()) web.goBack() else finish()
            }
        })
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView(url: String) {
        val s = web.settings
        s.javaScriptEnabled = true
        s.domStorageEnabled = true
        s.loadWithOverviewMode = true
        s.useWideViewPort = true
        s.builtInZoomControls = true
        s.displayZoomControls = false
        s.setSupportZoom(true)
        // WebView 默认 UA 带 "wv"，部分网站会拦截，换成干净的移动版 Chrome UA
        s.userAgentString = Http.MOBILE_UA

        CookieManager.getInstance().setAcceptCookie(true)
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, true)

        web.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView?, u: String?, favicon: Bitmap?) {
                progress.visibility = View.VISIBLE
                errorPanel.visibility = View.GONE
            }

            override fun onPageFinished(view: WebView?, u: String?) {
                progress.visibility = View.GONE
                if (!u.isNullOrBlank()) currentUrl = u
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: WebResourceError?
            ) {
                if (request?.isForMainFrame == true) {
                    progress.visibility = View.GONE
                    errorPanel.visibility = View.VISIBLE
                    tvError.text = "加载失败：${error?.description ?: "网络错误"}\n\n$currentUrl"
                }
            }
        }

        if (url.isBlank()) {
            errorPanel.visibility = View.VISIBLE
            tvError.text = "没有可预览的链接"
        } else {
            load(url)
        }
    }

    private fun load(url: String) {
        progress.visibility = View.VISIBLE
        errorPanel.visibility = View.GONE
        web.loadUrl(url)
    }

    private fun openInBrowser() {
        runCatching {
            startActivity(
                android.content.Intent(android.content.Intent.ACTION_VIEW, Uri.parse(currentUrl))
            )
        }
    }

    companion object {
        const val EXTRA_TITLE = "title"
        const val EXTRA_URL = "url"
        const val EXTRA_SUMMARY = "summary"
        const val EXTRA_SOURCE = "source"

        fun intent(
            context: android.content.Context,
            title: String,
            url: String,
            summary: String = "",
            source: String = ""
        ) =
            android.content.Intent(context, ArticleActivity::class.java)
                .putExtra(EXTRA_TITLE, title)
                .putExtra(EXTRA_URL, url)
                .putExtra(EXTRA_SUMMARY, summary)
                .putExtra(EXTRA_SOURCE, source)
    }
}
