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
import com.guantianxia.app.net.FuelApi
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
    private lateinit var fuelAdapter: QuotesAdapter
    private lateinit var flashAdapter: NewsAdapter

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        val swipe = view.findViewById<SwipeRefreshLayout>(R.id.swipe)
        val rvQuotes = view.findViewById<RecyclerView>(R.id.rv_quotes)
        val rvFuel = view.findViewById<RecyclerView>(R.id.rv_fuel)
        val rvFlash = view.findViewById<RecyclerView>(R.id.rv_flash)
        val tvTime = view.findViewById<TextView>(R.id.tv_quote_time)
        val tvFuelTitle = view.findViewById<TextView>(R.id.tv_fuel_title)
        val tvFuelNote = view.findViewById<TextView>(R.id.tv_fuel_note)

        quoteAdapter = QuotesAdapter()
        rvQuotes.layoutManager = GridLayoutManager(requireContext(), 2)
        rvQuotes.adapter = quoteAdapter
        rvQuotes.isNestedScrollingEnabled = false

        fuelAdapter = QuotesAdapter()
        rvFuel.layoutManager = GridLayoutManager(requireContext(), 2)
        rvFuel.adapter = fuelAdapter
        rvFuel.isNestedScrollingEnabled = false

        // 点标题换省份（默认广西，选完记住）
        tvFuelTitle.setOnClickListener { pickProvince(tvFuelTitle, tvFuelNote) }
        tvFuelTitle.text = getString(
            R.string.fuel_title,
            FuelApi.provinceOf(prefs.fuelProvince).name
        )
        tvFuelNote.text = getString(R.string.fuel_loading)

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

        swipe.setOnRefreshListener { loadAll(swipe, tvTime, tvFuelTitle, tvFuelNote) }
        loadAll(swipe, tvTime, tvFuelTitle, tvFuelNote)
    }

    /** 切换省份：单选弹窗，选完重新拉油价并记住 */
    private fun pickProvince(title: TextView, note: TextView) {
        val names = FuelApi.PROVINCES.map { it.name }.toTypedArray()
        val cur = FuelApi.PROVINCES.indexOfFirst { it.slug == prefs.fuelProvince }
            .let { if (it < 0) 0 else it }
        androidx.appcompat.app.AlertDialog.Builder(requireContext())
            .setTitle(R.string.fuel_pick)
            .setSingleChoiceItems(names, cur) { d, which ->
                prefs.fuelProvince = FuelApi.PROVINCES[which].slug
                title.text = getString(R.string.fuel_title, FuelApi.PROVINCES[which].name)
                note.text = getString(R.string.fuel_loading)
                d.dismiss()
                loadFuel(title, note)
            }
            .show()
    }

    /** 油价：国内成品油（默认广西）+ 国际原油/天然气 + 液化气 */
    private fun loadFuel(title: TextView, note: TextView) {
        viewLifecycleOwner.lifecycleScope.launch {
            val slug = prefs.fuelProvince.ifBlank { FuelApi.DEFAULT_SLUG }
            val rows = withContext(Dispatchers.IO) {
                val out = ArrayList<QuotesApi.Quote>()
                val fuel = runCatching { FuelApi.loadProvince(slug) }.getOrNull()
                if (fuel != null) {
                    out.add(QuotesApi.Quote("92# 汽油", fuel.p92, "元/升", true))
                    out.add(QuotesApi.Quote("95# 汽油", fuel.p95, "元/升", true))
                    out.add(QuotesApi.Quote("98# 汽油", fuel.p98, "元/升", true))
                    out.add(QuotesApi.Quote("0# 柴油", fuel.p0, "元/升", true))
                }
                runCatching { FuelApi.loadIntl() }.getOrDefault(emptyList()).forEach {
                    out.add(QuotesApi.Quote(it.name, it.price, it.unit, it.up))
                }
                runCatching { FuelApi.loadLpg() }.getOrNull()?.let {
                    out.add(QuotesApi.Quote(it.name, it.price, it.unit, it.up))
                }
                out to fuel
            }
            if (!isAdded) return@launch
            fuelAdapter.submit(rows.first)
            val fuel = rows.second
            note.text = when {
                fuel == null -> getString(R.string.fuel_fail)
                fuel.nextAdjust.isNotEmpty() -> "下次油价 ${fuel.nextAdjust}" +
                    (if (fuel.note.isNotEmpty()) " · ${fuel.note}" else "")
                else -> "数据：汽油价格网 · 新浪行情"
            }
        }
    }

    private fun loadAll(
        swipe: SwipeRefreshLayout,
        tvTime: TextView,
        tvFuelTitle: TextView,
        tvFuelNote: TextView
    ) {
        viewLifecycleOwner.lifecycleScope.launch {
            Http.setProxy(prefs.proxyHost, prefs.proxyPort)
            val useProxy = Http.proxyConfigured && prefs.useProxyForIntl

            loadFuel(tvFuelTitle, tvFuelNote)

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
