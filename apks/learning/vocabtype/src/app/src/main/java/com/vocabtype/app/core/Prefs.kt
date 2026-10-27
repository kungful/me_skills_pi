package com.vocabtype.app.core

import android.content.Context

/**
 * 全部设置 + 累计统计 + 错词本，统一走 SharedPreferences。
 * 读非常频繁，所以内部加了一层内存缓存。
 */
class Prefs(ctx: Context) {

    private val sp = ctx.applicationContext.getSharedPreferences("vocabtype", Context.MODE_PRIVATE)

    // ---------------- 词库 / 进度 ----------------
    var dictId: Int
        get() = sp.getInt("dictId", 0)
        set(v) = sp.edit().putInt("dictId", v).apply()

    /** 当前词库打到第几个词了（断点续打） */
    var dictPos: Int
        get() = sp.getInt("pos_$dictId", 0)
        set(v) = sp.edit().putInt("pos_$dictId", v).apply()

    // ---------------- 模式 ----------------
    /** 0 = 单词, 1 = 短句, 2 = 长句 */
    var mode: Int
        get() = sp.getInt("mode", 0)
        set(v) = sp.edit().putInt("mode", v).apply()

    // ---------------- 训练控制 ----------------
    var strictTyping: Boolean
        get() = sp.getBoolean("strictTyping", true)
        set(v) = sp.edit().putBoolean("strictTyping", v).apply()

    /**
     * 输入框用「密码」类型。
     *
     * 中文输入法（讯飞/搜狗/百度）看到 textVisiblePassword 时不一定会切成英文，
     * 而看到 textPassword 会走系统密码键盘 —— 密码键盘天生就是英文 QWERTY，
     * 没有中文候选栏，这正是打字练习要的。
     * 输入框本身是 1dp 隐形的，所以「遮成圆点」对我们没影响。
     */
    var kbPassword: Boolean
        get() = sp.getBoolean("kbPassword", true)
        set(v) = sp.edit().putBoolean("kbPassword", v).apply()

    var autoClear: Boolean
        get() = sp.getBoolean("autoClear", false)
        set(v) = sp.edit().putBoolean("autoClear", v).apply()

    var dictationReview: Boolean
        get() = sp.getBoolean("dictationReview", true)
        set(v) = sp.edit().putBoolean("dictationReview", v).apply()

    var autoPlayWord: Boolean
        get() = sp.getBoolean("autoPlayWord", true)
        set(v) = sp.edit().putBoolean("autoPlayWord", v).apply()

    var autoPlaySentence: Boolean
        get() = sp.getBoolean("autoPlaySentence", true)
        set(v) = sp.edit().putBoolean("autoPlaySentence", v).apply()

    var loopAudio: Boolean
        get() = sp.getBoolean("loopAudio", false)
        set(v) = sp.edit().putBoolean("loopAudio", v).apply()

    var pauseLoopWhileTyping: Boolean
        get() = sp.getBoolean("pauseLoop", true)
        set(v) = sp.edit().putBoolean("pauseLoop", v).apply()

    var showPhonetic: Boolean
        get() = sp.getBoolean("showPhonetic", true)
        set(v) = sp.edit().putBoolean("showPhonetic", v).apply()

    var showTranslation: Boolean
        get() = sp.getBoolean("showTrans", true)
        set(v) = sp.edit().putBoolean("showTrans", v).apply()

    /** 0 顺序 1 随机 2 只复习错词 3 智能(错词优先) */
    var wordOrder: Int
        get() = sp.getInt("wordOrder", 0)
        set(v) = sp.edit().putInt("wordOrder", v).apply()

    // ---------------- 语音 ----------------
    var ttsRate: Float
        get() = sp.getFloat("ttsRate", 1.0f)
        set(v) = sp.edit().putFloat("ttsRate", v).apply()

    /** 发音引擎：0 = 系统 TTS，1 = 有道在线真人发音（无需 Key） */
    var voiceEngine: Int
        get() = sp.getInt("voiceEngine", 1)
        set(v) = sp.edit().putInt("voiceEngine", v).apply()

    /** 口音：1 = 英音，2 = 美音（有道 type=1/2，也用于系统 TTS 的 en-GB/en-US） */
    var accent: Int
        get() = sp.getInt("accent", 2)
        set(v) = sp.edit().putInt("accent", v).apply()

    /** 给单词自动配图（视觉绑定记忆） */
    var showPic: Boolean
        get() = sp.getBoolean("showPic", true)
        set(v) = sp.edit().putBoolean("showPic", v).apply()

    /** 微软神经语音（音质最好，需要联网，稍慢） */
    var edgeVoiceOn: Boolean
        get() = sp.getBoolean("edgeVoiceOn", false)
        set(v) = sp.edit().putBoolean("edgeVoiceOn", v).apply()

    /** 微软中文音色 id */
    var edgeZhVoice: String
        get() = sp.getString("edgeZhVoice", "zh-CN-XiaoxiaoNeural") ?: "zh-CN-XiaoxiaoNeural"
        set(v) = sp.edit().putString("edgeZhVoice", v).apply()

    /** 中文释义朗读：英文 → 释义（百度 zh） */
    var readZh: Boolean
        get() = sp.getBoolean("readZh", false)
        set(v) = sp.edit().putBoolean("readZh", v).apply()

    /** 后台播放：切出去/锁屏也继续朗读（前台服务） */
    var backgroundPlay: Boolean
        get() = sp.getBoolean("bgPlay", true)
        set(v) = sp.edit().putBoolean("bgPlay", v).apply()

    // ---------------- 播放器（自动连播）参数 ----------------
    /** 播放循环模式：0 列表循环 / 1 单组循环 / 2 顺序播完就停 / 3 随机循环 */
    var playMode: Int
        get() = sp.getInt("playMode", 0)
        set(v) = sp.edit().putInt("playMode", v).apply()

    /** 定时关闭（分钟，0 = 关） */
    var sleepMinutes: Int
        get() = sp.getInt("sleepMinutes", 0)
        set(v) = sp.edit().putInt("sleepMinutes", v).apply()

    /** 收藏的词 */
    fun favs(): MutableSet<String> =
        (sp.getStringSet("favs", emptySet()) ?: emptySet()).toMutableSet()

    fun saveFavs(s: Set<String>) {
        sp.edit().putStringSet("favs", s).apply()
    }

    fun isFav(w: String): Boolean = favs().contains(w.lowercase())

    fun toggleFav(w: String): Boolean {
        val s = favs()
        val k = w.lowercase()
        val now = if (s.contains(k)) {
            s.remove(k); false
        } else {
            s.add(k); true
        }
        saveFavs(s)
        return now
    }

    /** 连播顺序：0 顺序 / 1 随机 / 2 只练错词 / 3 只收藏 */
    var playOrder: Int
        get() = sp.getInt("playOrder", 0)
        set(v) = sp.edit().putInt("playOrder", v).apply()

    /** 每轮读哪些内容（1 = 开） */
    var playWord: Boolean
        get() = sp.getBoolean("playWord", true)
        set(v) = sp.edit().putBoolean("playWord", v).apply()

    var playZh: Boolean
        get() = sp.getBoolean("playZh", false)
        set(v) = sp.edit().putBoolean("playZh", v).apply()

    var playSentence: Boolean
        get() = sp.getBoolean("playSentence", true)
        set(v) = sp.edit().putBoolean("playSentence", v).apply()

    /** 每个词重复读几遍 */
    var playRepeat: Int
        get() = sp.getInt("playRepeat", 1)
        set(v) = sp.edit().putInt("playRepeat", v).apply()

    /** 词与词之间的停顿（毫秒） */
    var playGap: Int
        get() = sp.getInt("playGap", 500)
        set(v) = sp.edit().putInt("playGap", v).apply()

    /** 读中文时也放慢一点（中文信息密度高） */
    var playZhRate: Float
        get() = sp.getFloat("playZhRate", 0.9f)
        set(v) = sp.edit().putFloat("playZhRate", v).apply()

    /** 换词时后台预下载单词发音，点播放零等待 */
    var prefetchVoice: Boolean
        get() = sp.getBoolean("prefetchVoice", true)
        set(v) = sp.edit().putBoolean("prefetchVoice", v).apply()

    // ---------------- 反馈 ----------------
    var soundOn: Boolean
        get() = sp.getBoolean("sound", true)
        set(v) = sp.edit().putBoolean("sound", v).apply()

    var vibrateOn: Boolean
        get() = sp.getBoolean("vibrate", true)
        set(v) = sp.edit().putBoolean("vibrate", v).apply()

    // ---------------- 外观 ----------------
    var matrix: Boolean
        get() = sp.getBoolean("matrix", true)
        set(v) = sp.edit().putBoolean("matrix", v).apply()

    var upper: Boolean
        get() = sp.getBoolean("upper", true)
        set(v) = sp.edit().putBoolean("upper", v).apply()

    var fsType: Int
        get() = sp.getInt("fsType", 46)
        set(v) = sp.edit().putInt("fsType", v).apply()

    var fsSent: Int
        get() = sp.getInt("fsSent", 21)
        set(v) = sp.edit().putInt("fsSent", v).apply()

    var fsTrans: Int
        get() = sp.getInt("fsTrans", 17)
        set(v) = sp.edit().putInt("fsTrans", v).apply()

    // ---------------- 可选：DeepSeek 造句 ----------------
    var aiKey: String
        get() = sp.getString("aiKey", "") ?: ""
        set(v) = sp.edit().putString("aiKey", v).apply()

    var aiOn: Boolean
        get() = sp.getBoolean("aiOn", true)
        set(v) = sp.edit().putBoolean("aiOn", v).apply()

    var aiSystem: String
        get() = sp.getString("aiSystem", DEFAULT_AI_SYSTEM) ?: DEFAULT_AI_SYSTEM
        set(v) = sp.edit().putString("aiSystem", v).apply()

    var aiTemplate: String
        get() = sp.getString("aiTemplate", DEFAULT_AI_TEMPLATE) ?: DEFAULT_AI_TEMPLATE
        set(v) = sp.edit().putString("aiTemplate", v).apply()

    // ---------------- 累计统计 ----------------
    var totalTyped: Int
        get() = sp.getInt("tTyped", 0)
        set(v) = sp.edit().putInt("tTyped", v).apply()

    var totalCorrect: Int
        get() = sp.getInt("tCorrect", 0)
        set(v) = sp.edit().putInt("tCorrect", v).apply()

    var totalMistakes: Int
        get() = sp.getInt("tMistakes", 0)
        set(v) = sp.edit().putInt("tMistakes", v).apply()

    var totalWords: Int
        get() = sp.getInt("tWords", 0)
        set(v) = sp.edit().putInt("tWords", v).apply()

    var bestStreak: Int
        get() = sp.getInt("bestStreak", 0)
        set(v) = sp.edit().putInt("bestStreak", v).apply()

    var totalSeconds: Int
        get() = sp.getInt("tSeconds", 0)
        set(v) = sp.edit().putInt("tSeconds", v).apply()

    var sessions: Int
        get() = sp.getInt("sessions", 0)
        set(v) = sp.edit().putInt("sessions", v).apply()

    /** 练过的不同单词数 */
    var learned: Int
        get() = sp.getInt("learned", 0)
        set(v) = sp.edit().putInt("learned", v).apply()

    var practiceDays: Int
        get() = sp.getInt("days", 0)
        set(v) = sp.edit().putInt("days", v).apply()

    var lastDay: String
        get() = sp.getString("lastDay", "") ?: ""
        set(v) = sp.edit().putString("lastDay", v).apply()

    // ---------------- 错词本 ----------------
    /** word -> 错误次数 */
    fun mistakes(): MutableMap<String, Int> {
        val raw = sp.getString("mistakes", "") ?: ""
        return MistakeCodec.decode(raw)
    }

    fun saveMistakes(m: Map<String, Int>) {
        sp.edit().putString("mistakes", MistakeCodec.encode(m)).apply()
    }

    /** 复习队列（有序，最近错的在后面） */
    fun queue(): MutableList<String> {
        val raw = sp.getString("queue", "") ?: ""
        return if (raw.isBlank()) ArrayList() else ArrayList(raw.split('\u0001').filter { it.isNotBlank() })
    }

    fun saveQueue(q: List<String>) {
        sp.edit().putString("queue", q.joinToString("\u0001")).apply()
    }

    fun clearMistakes() {
        sp.edit().remove("mistakes").remove("queue").apply()
    }

    fun wipeAll() {
        sp.edit().clear().apply()
    }

    fun learnedSet(): MutableSet<String> {
        val raw = sp.getString("learnedSet", "") ?: ""
        return if (raw.isBlank()) HashSet() else HashSet(raw.split('\u0001').filter { it.isNotBlank() })
    }

    fun saveLearnedSet(s: Set<String>) {
        sp.edit().putString("learnedSet", s.joinToString("\u0001")).apply()
    }

    fun dictProgress(id: Int): Int = sp.getInt("pos_$id", 0)

    fun setDictProgress(id: Int, v: Int) {
        sp.edit().putInt("pos_$id", v).apply()
    }

    companion object {
        val DEFAULT_AI_SYSTEM = """你是一位英语老师。请根据用户给出的英语单词，输出 JSON。
只输出 JSON，不要 markdown 代码块，不要任何解释。
JSON 字段：
short_sentence: 一个 6-12 词的简单英文句子，必须用到该单词
short_sentence_translation: 上面句子的中文翻译
short_sentence_grammar: 上面句子的中文语法/用法讲解（1-3 句）
complex_sentence: 一个 20-35 词的复杂英文句子（要有从句），必须用到该单词
complex_sentence_translation: 上面句子的中文翻译
complex_sentence_grammar: 上面句子的中文语法讲解（1-3 句）"""

        val DEFAULT_AI_TEMPLATE = """单词：{word}
释义：{trans}
请严格按上面的 JSON 格式输出。"""
    }
}

/** 错词本序列化成一行行 "word\tcount"，比 JSON 快很多 */
internal object MistakeCodec {
    fun encode(m: Map<String, Int>): String {
        if (m.isEmpty()) return ""
        val sb = StringBuilder()
        for ((k, v) in m) {
            sb.append(k).append('\t').append(v).append('\n')
        }
        return sb.toString()
    }

    fun decode(raw: String): MutableMap<String, Int> {
        val out = HashMap<String, Int>()
        if (raw.isBlank()) return out
        for (line in raw.split('\n')) {
            if (line.isBlank()) continue
            val i = line.indexOf('\t')
            if (i <= 0) continue
            val w = line.substring(0, i)
            val c = line.substring(i + 1).toIntOrNull() ?: continue
            out[w] = c
        }
        return out
    }
}
