package com.guantianxia.app.net

import com.guantianxia.app.core.Http
import java.util.Locale

/**
 * 油价 / 液化气。三个源，全部实测国内直连可用、服务端渲染、不需要 key：
 *
 *  - 各省成品油：汽油价格网 `qiyoujiage.com`（**只有 HTTP**，所以
 *    `network_security_config.xml` 里给这一个域名开了明文例外，别处仍然禁明文）
 *  - 国际原油 / 天然气：新浪外盘 `hf_*`（HTTPS，要带 Referer）
 *  - 液化石油气：新浪内盘期货 `nf_PG0`（元/吨，大商所）
 *
 * 为什么不用那些「免费油价 API」：oioweb / vvhan / 52vmy / jxcxin / pearktrue
 * 实测全部已死或直接返回空，反而是这个老网站的网页最稳（0.2s）。
 */
object FuelApi {

    /** 一行价格。up 只用来决定颜色 */
    data class Row(
        val name: String,
        val price: String,
        val unit: String,
        val up: Boolean
    )

    data class Province(val name: String, val slug: String)

    /** 31 个省级行政区。深圳页用的是 90/93/97 老标号且没有调价提示，不收 */
    val PROVINCES = listOf(
        Province("北京", "beijing"),
        Province("天津", "tianjin"),
        Province("河北", "hebei"),
        Province("山西", "shanxi"),
        Province("内蒙古", "neimenggu"),
        Province("辽宁", "liaoning"),
        Province("吉林", "jilin"),
        Province("黑龙江", "heilongjiang"),
        Province("上海", "shanghai"),
        Province("江苏", "jiangsu"),
        Province("浙江", "zhejiang"),
        Province("安徽", "anhui"),
        Province("福建", "fujian"),
        Province("江西", "jiangxi"),
        Province("山东", "shandong"),
        Province("河南", "henan"),
        Province("湖北", "hubei"),
        Province("湖南", "hunan"),
        Province("广东", "guangdong"),
        Province("广西", "guangxi"),
        Province("海南", "hainan"),
        Province("重庆", "chongqing"),
        Province("四川", "sichuan"),
        Province("贵州", "guizhou"),
        Province("云南", "yunnan"),
        Province("西藏", "xizang"),
        // 这个站给陕西用了带后缀的地址，别写成 shanxi（那是山西）
        Province("陕西", "shanxi-3"),
        Province("甘肃", "gansu"),
        Province("青海", "qinghai"),
        Province("宁夏", "ningxia"),
        Province("新疆", "xinjiang")
    )

    /** 默认广西 */
    const val DEFAULT_SLUG = "guangxi"

    fun provinceOf(slug: String): Province =
        PROVINCES.firstOrNull { it.slug == slug } ?: PROVINCES.first { it.slug == DEFAULT_SLUG }

    data class Fuel(
        val province: String,
        /** 92# 汽油 元/升 */
        val p92: String,
        val p95: String,
        val p98: String,
        /** 0# 柴油 元/升 */
        val p0: String,
        /** 例如「10月15日24时调整」 */
        val nextAdjust: String,
        /** 例如「油价搁浅调整，维持目前价格不变」 */
        val note: String
    )

    private val DL = Regex("<dt>([^<]{2,20})</dt>\\s*<dd>([0-9.]+)</dd>")
    private val SCRIPT = Regex("<script[\\s\\S]*?</script>")
    private val NEXT = Regex("下次油价\\s*([^<]{2,30})")
    private val RED = Regex("<span style=\"color:#F00;\">([^<]{2,80})</span>")

    /** 抓一个省的成品油价格 */
    fun loadProvince(slug: String): Fuel? {
        val html = Http.text("http://www.qiyoujiage.com/$slug.shtml") ?: return null
        // 页面里有一段 document.writeln 的红字，先去掉脚本，免得多抓
        val text = SCRIPT.replace(html, " ")
        val map = HashMap<String, String>(4)
        for (m in DL.findAll(text)) {
            val label = m.groupValues[1]
            val v = m.groupValues[2]
            when {
                label.contains("92#") -> map["92"] = v
                label.contains("95#") -> map["95"] = v
                label.contains("98#") -> map["98"] = v
                label.contains("0#") -> map["0"] = v
            }
        }
        if (map.isEmpty()) return null
        val next = NEXT.find(text)?.groupValues?.get(1)?.trim().orEmpty()
        val note = RED.find(text)?.groupValues?.get(1)?.trim().orEmpty()
        return Fuel(
            province = provinceOf(slug).name,
            p92 = map["92"] ?: "—",
            p95 = map["95"] ?: "—",
            p98 = map["98"] ?: "—",
            p0 = map["0"] ?: "—",
            nextAdjust = next,
            note = note
        )
    }

    private val SINA = Regex("var hq_str_([A-Za-z0-9_]+)=\"([^\"]*)\"")

    /** 国际原油 / 天然气：字段 0=现价 7=昨收 13=名称 */
    private val INTL = listOf(
        "hf_CL" to "WTI 原油",
        "hf_OIL" to "布伦特原油",
        "hf_NG" to "天然气"
    )

    fun loadIntl(): List<Row> {
        val url = "https://hq.sinajs.cn/list=" + INTL.joinToString(",") { it.first }
        val text = Http.text(url, referer = "https://finance.sina.com.cn") ?: return emptyList()
        val byCode = HashMap<String, String>()
        for (m in SINA.findAll(text)) byCode[m.groupValues[1]] = m.groupValues[2]
        val out = ArrayList<Row>(INTL.size)
        for ((code, label) in INTL) {
            val f = byCode[code]?.split(",") ?: continue
            if (f.size < 8) continue
            val price = f[0].toDoubleOrNull() ?: continue
            val prev = f[7].toDoubleOrNull() ?: 0.0
            out.add(
                Row(
                    name = label,
                    price = fmt(price),
                    unit = if (code == "hf_NG") "美元" else "美元/桶",
                    up = prev <= 0.0 || price >= prev
                )
            )
        }
        return out
    }

    /** 液化石油气期货（大商所）：0=名称 2=开 3=高 4=低 8=最新 10=昨结 */
    fun loadLpg(): Row? {
        val text = Http.text("https://hq.sinajs.cn/list=nf_PG0", referer = "https://finance.sina.com.cn")
            ?: return null
        val m = SINA.find(text) ?: return null
        val f = m.groupValues[2].split(",")
        if (f.size < 11) return null
        val price = f[8].toDoubleOrNull() ?: f[2].toDoubleOrNull() ?: return null
        val prev = f[10].toDoubleOrNull() ?: 0.0
        return Row("液化石油气", fmt(price), "元/吨", prev <= 0.0 || price >= prev)
    }

    private fun fmt(v: Double): String = String.format(Locale.US, "%,.2f", v)
}
