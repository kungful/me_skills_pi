package com.demandradar

import android.content.Context
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** 采集 + 分析的调度中心 */
object Hub {

    private val WS = Regex("[ \\t\\u00a0\\u3000]+")
    private val NL = Regex("\\n{2,}")
    private val TAG = Regex("<[^>]{1,200}>")
    private val NOISE = Regex(
        "(点击(查看|下载|了解)更多|扫码关注|长按识别|关注公众号|转载请|版权归|" +
            "\\b(read more|click here|subscribe now)\\b)",
        RegexOption.IGNORE_CASE,
    )

    /** 屏幕上常见的无信息量 UI 文案，留着只会稀释信号 */
    private val UI_JUNK = setOf(
        "首页", "推荐", "关注", "消息", "我", "返回", "取消", "确定", "完成", "搜索", "更多",
        "分享", "评论", "点赞", "收藏", "转发", "设置", "登录", "注册", "同意", "允许", "拒绝",
        "下一步", "跳过", "关闭", "全部", "综合", "视频", "图文", "用户", "直播", "已选中",
        "未选中状态", "加载中", "下拉刷新", "查看更多", "暂无数据", "没有更多了",
    )

    // 控件噪音：资源 ID / 类名 / 按钮状态后缀
    private val ID_RE = Regex("^(?:[A-Za-z0-9_\\-+/=]{16,}|O1CN\\w+|pic\\w{16,})$")
    private val CLASS_RE = Regex(
        "^(?:(?:android|androidx|com|org|java|kotlin)\\.[\\w.\$]+|" +
            "[\\w.\$]*(?:WebView|Layout|RecyclerView|ViewGroup|ImageView|TextView|ViewPager|Fragment|DecorView))$",
    )
    private val CHROME_RE = Regex("(?:[，,]?\\s*(?:已选中|未选中状态|选中状态|未读消息数\\d+|按钮|可点击))+$")
    private val NO_CJK_NO_WORD = Regex("^(?![\\s\\S]*[\\u4e00-\\u9fff])(?![\\s\\S]*[A-Za-z]{3,})[\\s\\S]*$")

    fun clean(text: String): String {
        var t = text.replace(TAG, " ").replace("\r", "\n")
        t = NOISE.replace(t, " ")
        t = t.filter { it == '\n' || !it.isISOControl() }
        t = WS.replace(t, " ")
        t = NL.replace(t, "\n")
        return t.trim()
    }

    /** 把无障碍拿到的一堆文本整理成一段有信息量的正文 */
    fun shape(raw: List<String>): String {
        val seen = HashSet<String>()
        val lines = ArrayList<String>()
        for (s in raw) {
            var t = clean(s)
            if (t.isEmpty()) continue
            t = CHROME_RE.replace(t, "").trim()
            if (t.startsWith("pic") && t.length > 3) t = t.substring(3)   // 图片 alt 前缀，后面正文要留
            if (t.length < 2 || t in UI_JUNK) continue
            if (ID_RE.matches(t) || CLASS_RE.matches(t)) continue
            if (NO_CJK_NO_WORD.matches(t)) continue
            if (!seen.add(t)) continue
            lines.add(t)
        }
        return lines.joinToString("\n").take(4000)
    }

    /** 两屏内容重合度太高就不重复记（刷屏时会连续抓到几乎一样的屏） */
    fun tooSimilar(a: Set<String>, b: Set<String>): Boolean {
        if (a.isEmpty() || b.isEmpty()) return false
        val inter = a.count { b.contains(it) }
        val union = a.size + b.size - inter
        return union > 0 && inter.toDouble() / union > 0.75
    }

    fun lineSet(text: String): Set<String> =
        text.lineSequence().filter { it.length >= 6 }.toSet()

    // 每个 App 单独记最近几屏，避免切 App 时互相误判成重复
    private val recent = HashMap<String, ArrayDeque<Set<String>>>()

    /** 采集一屏。返回 null 表示这一屏没价值（太短/重复/和刚才那屏太像） */
    fun ingest(ctx: Context, pkg: String, appName: String, rawTexts: List<String>): Item? {
        val text = shape(rawTexts)
        if (text.length < 12) return null

        // 刷屏时会连续抓到几乎一样的屏，重合度太高就不重复记
        val ls = lineSet(text)
        val q = recent.getOrPut(pkg) { ArrayDeque() }
        if (q.any { tooSimilar(it, ls) }) return null
        q.addLast(ls)
        while (q.size > 6) q.removeFirst()

        val lex = Lexicon.get(ctx)
        val it = Item(
            source = "android_screen",
            extId = "scr_" + Store.sha1(text).take(20),
            title = text.lineSequence().firstOrNull()?.take(60) ?: "",
            body = text,
            author = "",
            ts = System.currentTimeMillis(),
            weight = 1.0,
            heat = 0.0,
            // 手动刷到的内容质量高但含噪音，先验取配置值
            prior = lex.sourcePrior("android_screen", 0.5),
        )
        Scorer.scoreItem(it, lex)

        val fresh = Store.get(ctx).saveScreen(pkg, appName, text, it)
        return if (fresh) it else null
    }

    /** 重新打分 + 聚合主题 + 落库 */
    fun analyze(ctx: Context, days: Int = 90): List<Topic> {
        val lex = Lexicon.get(ctx)
        val items = Store.get(ctx).loadItems(days)
        if (items.isEmpty()) return emptyList()
        for (it in items) Scorer.scoreItem(it, lex)
        val all = Scorer.buildTopics(items, lex)
        val topics = Scorer.filterTopics(all, lex.minTopicItems)
        Store.get(ctx).saveTopics(topics)
        return topics
    }

    fun stamp(ms: Long): String {
        if (ms <= 0) return "-"
        return SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()).format(Date(ms))
    }
}
