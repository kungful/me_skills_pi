package com.guantianxia.app.net

import com.guantianxia.app.core.Http
import org.json.JSONObject
import java.util.Locale

/**
 * 行情数据
 *  - A股/港股/美股指数与个股：腾讯行情（国内直连，GBK）
 *  - 加密货币：CoinGecko（需代理）
 *  - 汇率：frankfurter.app（直连）
 */
object QuotesApi {

    data class Quote(
        val name: String,
        val price: String,
        val change: String,
        val up: Boolean
    )

    private val INDEX_SYMBOLS = listOf(
        "sh000001" to "上证指数",
        "sz399001" to "深证成指",
        "sz399006" to "创业板指",
        "hkHSI" to "恒生指数",
        "usDJI" to "道琼斯",
        "usIXIC" to "纳斯达克",
        "usINX" to "标普 500",
        "sh600519" to "贵州茅台",
        "hk00700" to "腾讯控股",
        "usAAPL" to "苹果 AAPL"
    )

    private val TEN_VAR = Regex("v_([A-Za-z0-9]+)=\"([^\"]*)\"")

    /** 指数 + 个股，一次请求全拿到 */
    fun loadIndices(): List<Quote> {
        val url = "https://qt.gtimg.cn/q=" + INDEX_SYMBOLS.joinToString(",") { it.first }
        val text = Http.text(url) ?: return emptyList()
        val out = ArrayList<Quote>()
        for (m in TEN_VAR.findAll(text)) {
            val sym = m.groupValues[1]
            val fields = m.groupValues[2].split("~")
            if (fields.size < 6) continue
            val name = fields[1].ifBlank { sym }
            val price = fields[3].toDoubleOrNull() ?: continue
            val prev = fields[4].toDoubleOrNull() ?: 0.0
            if (prev <= 0.0) continue
            val chg = price - prev
            val pct = chg / prev * 100.0
            out.add(
                Quote(
                    name = name,
                    price = String.format(Locale.US, "%,.2f", price),
                    change = String.format(Locale.US, "%+.2f  %+.2f%%", chg, pct),
                    up = chg >= 0
                )
            )
        }
        return out
    }

    fun loadCrypto(useProxy: Boolean): List<Quote> {
        val text = Http.text(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd&include_24hr_change=true",
            useProxy = useProxy
        ) ?: return emptyList()
        val out = ArrayList<Quote>()
        runCatching {
            val root = JSONObject(text)
            val pairs = listOf("bitcoin" to "BTC", "ethereum" to "ETH", "solana" to "SOL")
            for ((id, label) in pairs) {
                val o = root.optJSONObject(id) ?: continue
                val p = o.optDouble("usd", 0.0)
                val c = o.optDouble("usd_24hr_change", 0.0)
                if (p <= 0.0) continue
                out.add(
                    Quote(
                        name = label,
                        price = String.format(Locale.US, "$%,.0f", p),
                        change = String.format(Locale.US, "%+.2f%%", c),
                        up = c >= 0
                    )
                )
            }
        }
        return out
    }

    fun loadFx(): List<Quote> {
        val text = Http.text("https://api.frankfurter.app/latest?from=USD&to=CNY,JPY,EUR,HKD,GBP")
            ?: return emptyList()
        val out = ArrayList<Quote>()
        runCatching {
            val rates = JSONObject(text).optJSONObject("rates") ?: return@runCatching
            val order = listOf("CNY" to "美元/人民币", "JPY" to "美元/日元", "EUR" to "美元/欧元",
                "HKD" to "美元/港币", "GBP" to "美元/英镑")
            for ((code, label) in order) {
                val v = rates.optDouble(code, 0.0)
                if (v <= 0.0) continue
                out.add(
                    Quote(
                        name = label,
                        price = String.format(Locale.US, "%.4f", v),
                        change = "汇率",
                        up = true
                    )
                )
            }
        }
        return out
    }
}
