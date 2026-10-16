package com.demandradar

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** 本地存储：采集到的屏幕、素材、以及聚合出的机会主题 */
class Store private constructor(ctx: Context) :
    SQLiteOpenHelper(ctx.applicationContext, "demand_radar.db", null, 1) {

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            """
            CREATE TABLE items (
              id         INTEGER PRIMARY KEY AUTOINCREMENT,
              source     TEXT NOT NULL,
              ext_id     TEXT NOT NULL,
              pkg        TEXT DEFAULT '',
              app_name   TEXT DEFAULT '',
              title      TEXT DEFAULT '',
              body       TEXT DEFAULT '',
              url        TEXT DEFAULT '',
              author     TEXT DEFAULT '',
              lang       TEXT DEFAULT 'zh',
              ts         INTEGER DEFAULT 0,
              weight     REAL DEFAULT 1.0,
              heat       REAL DEFAULT 0.0,
              prior      REAL DEFAULT 0.45,
              demand     REAL DEFAULT 0.0,
              pain       REAL DEFAULT 0.0,
              pay        REAL DEFAULT 0.0,
              urgency    REAL DEFAULT 0.0,
              signals    TEXT DEFAULT '[]',
              keywords   TEXT DEFAULT '[]',
              categories TEXT DEFAULT '[]',
              UNIQUE(source, ext_id)
            )
            """.trimIndent(),
        )
        db.execSQL("CREATE INDEX idx_items_demand ON items(demand DESC)")
        db.execSQL("CREATE INDEX idx_items_ts ON items(ts DESC)")
        db.execSQL(
            """
            CREATE TABLE topics (
              slug       TEXT PRIMARY KEY,
              label      TEXT,
              score      REAL DEFAULT 0,
              evidence   INTEGER DEFAULT 0,
              money      TEXT DEFAULT '',
              pain       REAL DEFAULT 0,
              pay        REAL DEFAULT 0,
              diversity  REAL DEFAULT 0,
              payload    TEXT DEFAULT '{}',
              updated_at INTEGER DEFAULT 0
            )
            """.trimIndent(),
        )
    }

    override fun onUpgrade(db: SQLiteDatabase, old: Int, new: Int) {
        db.execSQL("DROP TABLE IF EXISTS items")
        db.execSQL("DROP TABLE IF EXISTS topics")
        onCreate(db)
    }

    // ------------------------------------------------------------ 写入

    /** 返回 true 表示是新的屏幕（内容没重复过） */
    fun saveScreen(pkg: String, appName: String, text: String, it: Item): Boolean {
        val extId = "scr_" + sha1(text).take(20)
        if (exists(it.source, extId)) return false
        val v = ContentValues().apply {
            put("source", it.source)
            put("ext_id", extId)
            put("pkg", pkg)
            put("app_name", appName)
            put("title", it.title)
            put("body", it.body)
            put("url", it.url)
            put("author", it.author)
            put("lang", it.lang)
            put("ts", it.ts)
            put("weight", it.weight)
            put("heat", it.heat)
            put("prior", it.prior)
            put("demand", it.demand)
            put("pain", it.pain)
            put("pay", it.pay)
            put("urgency", it.urgency)
            put("signals", JSONArray(it.signals).toString())
            put("keywords", JSONArray(it.keywords).toString())
            put("categories", JSONArray(it.categories).toString())
        }
        return writableDatabase.insertWithOnConflict(
            "items", null, v, SQLiteDatabase.CONFLICT_IGNORE,
        ) > 0
    }

    private fun exists(source: String, extId: String): Boolean =
        readableDatabase.rawQuery(
            "SELECT 1 FROM items WHERE source=? AND ext_id=? LIMIT 1",
            arrayOf(source, extId),
        ).use { it.moveToFirst() }

    fun saveTopics(topics: List<Topic>) {
        val db = writableDatabase
        db.beginTransaction()
        try {
            db.delete("topics", null, null)
            for (t in topics) {
                val v = ContentValues().apply {
                    put("slug", t.slug)
                    put("label", t.label)
                    put("score", t.score)
                    put("evidence", t.itemIds.size)
                    put("money", t.money)
                    put("pain", t.pain)
                    put("pay", t.pay)
                    put("diversity", t.diversity)
                    put("payload", toJson(t).toString())
                    put("updated_at", System.currentTimeMillis())
                }
                db.insertWithOnConflict("topics", null, v, SQLiteDatabase.CONFLICT_REPLACE)
            }
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    // ------------------------------------------------------------ 读取

    fun loadItems(days: Int = 90): List<Item> {
        val since = System.currentTimeMillis() - days * 86_400_000L
        val out = ArrayList<Item>()
        readableDatabase.rawQuery(
            "SELECT source, ext_id, title, body, url, author, lang, ts, weight, heat, prior " +
                "FROM items WHERE ts>=? ORDER BY ts DESC LIMIT 20000",
            arrayOf(since.toString()),
        ).use { c ->
            while (c.moveToNext()) {
                out.add(
                    Item(
                        source = c.getString(0),
                        extId = c.getString(1),
                        title = c.getString(2) ?: "",
                        body = c.getString(3) ?: "",
                        url = c.getString(4) ?: "",
                        author = c.getString(5) ?: "",
                        lang = c.getString(6) ?: "zh",
                        ts = c.getLong(7),
                        weight = c.getDouble(8),
                        heat = c.getDouble(9),
                        prior = c.getDouble(10),
                    ),
                )
            }
        }
        return out
    }

    fun loadTopics(): List<Topic> {
        val out = ArrayList<Topic>()
        readableDatabase.rawQuery(
            "SELECT payload FROM topics ORDER BY score DESC",
            null,
        ).use { c ->
            while (c.moveToNext()) {
                runCatching { fromJson(JSONObject(c.getString(0))) }.getOrNull()?.let { out.add(it) }
            }
        }
        return out
    }

    fun recentScreens(limit: Int = 100): List<Pair<String, String>> {
        val out = ArrayList<Pair<String, String>>()
        readableDatabase.rawQuery(
            "SELECT app_name, body FROM items WHERE source='android_screen' ORDER BY ts DESC LIMIT ?",
            arrayOf(limit.toString()),
        ).use { c ->
            while (c.moveToNext()) out.add((c.getString(0) ?: "") to (c.getString(1) ?: ""))
        }
        return out
    }

    fun stats(): Stats {
        val todayStart = System.currentTimeMillis() - System.currentTimeMillis() % 86_400_000L
        fun one(sql: String, vararg args: String): Int =
            readableDatabase.rawQuery(sql, args).use { if (it.moveToFirst()) it.getInt(0) else 0 }
        return Stats(
            screens = one("SELECT COUNT(*) FROM items WHERE source='android_screen'"),
            items = one("SELECT COUNT(*) FROM items"),
            todayScreens = one("SELECT COUNT(*) FROM items WHERE source='android_screen' AND ts>=?", todayStart.toString()),
            topics = one("SELECT COUNT(*) FROM topics"),
            highValue = one("SELECT COUNT(*) FROM items WHERE demand>=25"),
        )
    }

    class Stats(
        val screens: Int,
        val items: Int,
        val todayScreens: Int,
        val topics: Int,
        val highValue: Int,
    )

    // ------------------------------------------------------------ 导出（可拷回电脑深度分析）

    fun exportJson(): String {
        val root = JSONObject()
        val arr = JSONArray()
        readableDatabase.rawQuery(
            "SELECT source, ext_id, pkg, app_name, title, body, url, author, lang, ts, weight, heat, prior " +
                "FROM items ORDER BY ts DESC",
            null,
        ).use { c ->
            while (c.moveToNext()) {
                arr.put(
                    JSONObject().apply {
                        put("source", c.getString(0))
                        put("ext_id", c.getString(1))
                        put("pkg", c.getString(2) ?: "")
                        put("app_name", c.getString(3) ?: "")
                        put("title", c.getString(4) ?: "")
                        put("body", c.getString(5) ?: "")
                        put("url", c.getString(6) ?: "")
                        put("author", c.getString(7) ?: "")
                        put("lang", c.getString(8) ?: "zh")
                        put("ts", iso(c.getLong(9)))
                        put("weight", c.getDouble(10))
                        put("heat", c.getDouble(11))
                        put("prior", c.getDouble(12))
                    },
                )
            }
        }
        root.put("exported_at", iso(System.currentTimeMillis()))
        root.put("items", arr)
        return root.toString()
    }

    companion object {
        private val ISO = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)
        private fun iso(ms: Long): String = synchronized(ISO) { ISO.format(Date(ms)) }

        @Volatile private var inst: Store? = null
        fun get(ctx: Context): Store = inst ?: synchronized(this) {
            inst ?: Store(ctx).also { inst = it }
        }

        fun sha1(s: String): String =
            java.security.MessageDigest.getInstance("SHA-1")
                .digest(s.toByteArray()).joinToString("") { "%02x".format(it) }

        fun toJson(t: Topic): JSONObject = JSONObject().apply {
            put("slug", t.slug)
            put("label", t.label)
            put("score", t.score)
            put("pain", t.pain)
            put("pay", t.pay)
            put("urgency", t.urgency)
            put("diversity", t.diversity)
            put("heat", t.heat)
            put("authors", t.authors)
            put("money", t.money)
            put("first_seen", iso(t.firstSeen))
            put("last_seen", iso(t.lastSeen))
            put("keywords", JSONArray(t.keywords))
            put("categories", JSONArray(t.categories))
            put("sources", JSONObject(t.sources as Map<*, *>))
            put("item_ids", JSONArray(t.itemIds))
            put("validation", JSONArray(t.validation))
            put(
                "samples",
                JSONArray().apply {
                    t.samples.forEach { s ->
                        put(
                            JSONObject().apply {
                                put("source", s.source); put("author", s.author); put("url", s.url)
                                put("ts", iso(s.ts)); put("text", s.text); put("score", s.score)
                            },
                        )
                    }
                },
            )
        }

        fun fromJson(o: JSONObject): Topic {
            fun strList(a: JSONArray?): List<String> =
                if (a == null) emptyList() else (0 until a.length()).map { a.optString(it) }
            val samples = ArrayList<Sample>()
            o.optJSONArray("samples")?.let { a ->
                for (i in 0 until a.length()) {
                    val s = a.optJSONObject(i) ?: continue
                    samples.add(Sample(s.optString("source"), s.optString("author"), s.optString("url"), 0L, s.optString("text"), s.optDouble("score")))
                }
            }
            return Topic(
                slug = o.optString("slug"),
                label = o.optString("label"),
                keywords = strList(o.optJSONArray("keywords")),
                categories = strList(o.optJSONArray("categories")),
                itemIds = strList(o.optJSONArray("item_ids")),
                sources = o.optJSONObject("sources")?.let { j -> j.keys().asSequence().associateWith { j.optInt(it) } } ?: emptyMap(),
                authors = o.optInt("authors"),
                score = o.optDouble("score"),
                pain = o.optDouble("pain"),
                pay = o.optDouble("pay"),
                urgency = o.optDouble("urgency"),
                diversity = o.optDouble("diversity"),
                heat = o.optDouble("heat"),
                firstSeen = 0L,
                lastSeen = 0L,
                money = o.optString("money"),
                validation = strList(o.optJSONArray("validation")),
                samples = samples,
            )
        }
    }
}
