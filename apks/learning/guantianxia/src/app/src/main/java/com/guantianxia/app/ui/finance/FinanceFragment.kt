package com.guantianxia.app.ui.finance

import android.os.Bundle
import android.view.View
import android.widget.TextView
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.GridLayoutManager
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import com.guantianxia.app.R
import com.guantianxia.app.core.Http
import com.guantianxia.app.core.Prefs
import com.guantianxia.app.core.TimeUtil
import com.guantianxia.app.data.Category
import com.guantianxia.app.data.Db
import com.guantianxia.app.net.QuotesApi
import com.guantianxia.app.ui.ArticleActions
import com.guantianxia.app.ui.news.NewsAdapter
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class FinanceFragment : Fragment(R.layout.fragment_finance) {

    private val db by lazy { Db(requireContext().applicationContext) }
    private val prefs by lazy { Prefs(requireContext().applicationContext) }

    private lateinit var quoteAdapter: QuotesAdapter
    private lateinit var flashAdapter: NewsAdapter

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        val swipe = view.findViewById<SwipeRefreshLayout>(R.id.swipe)
        val rvQuotes = view.findViewById<RecyclerView>(R.id.rv_quotes)
        val rvFlash = view.findViewById<RecyclerView>(R.id.rv_flash)
        val tvTime = view.findViewById<TextView>(R.id.tv_quote_time)

        quoteAdapter = QuotesAdapter()
        rvQuotes.layoutManager = GridLayoutManager(requireContext(), 2)
        rvQuotes.adapter = quoteAdapter
        rvQuotes.isNestedScrollingEnabled = false

        flashAdapter = NewsAdapter(
            onOpen = { a -> ArticleActions.open(requireContext(), a) },
            onShare = { a -> ArticleActions.shareDialog(requireActivity(), a) },
            onMore = { a ->
                ArticleActions.showMenu(requireActivity(), a, db) { loadFlash() }
            }
        )
        rvFlash.layoutManager = LinearLayoutManager(requireContext())
        rvFlash.adapter = flashAdapter
        rvFlash.isNestedScrollingEnabled = false

        swipe.setOnRefreshListener { loadAll(swipe, tvTime) }
        loadAll(swipe, tvTime)
    }

    private fun loadAll(swipe: SwipeRefreshLayout, tvTime: TextView) {
        viewLifecycleOwner.lifecycleScope.launch {
            Http.setProxy(prefs.proxyHost, prefs.proxyPort)
            val useProxy = Http.proxyConfigured && prefs.useProxyForIntl

            val quotes = withContext(Dispatchers.IO) {
                val list = ArrayList<QuotesApi.Quote>()
                list.addAll(QuotesApi.loadIndices())
                list.addAll(QuotesApi.loadCrypto(useProxy))
                list.addAll(QuotesApi.loadFx())
                list
            }
            if (!isAdded) return@launch
            quoteAdapter.submit(quotes)
            swipe.isRefreshing = false

            val tail = if (useProxy) "" else "（加密货币需在设置里配代理）"
            tvTime.text = "更新于 ${TimeUtil.nowText()} · 腾讯行情 / frankfurter $tail"

            loadFlash()
        }
    }

    private fun loadFlash() {
        if (!isAdded) return
        viewLifecycleOwner.lifecycleScope.launch {
            val list = withContext(Dispatchers.IO) { db.query(Category.FINANCE, false, 80) }
            if (!isAdded) return@launch
            flashAdapter.submit(list)
        }
    }

    private fun openUrl(url: String) {
        ArticleActions.openInBrowser(requireContext(), url)
    }
}
