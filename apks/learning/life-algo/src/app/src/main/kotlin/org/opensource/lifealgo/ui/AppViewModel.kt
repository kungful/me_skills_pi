package org.opensource.lifealgo.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import org.opensource.lifealgo.LifeAlgoApp
import org.opensource.lifealgo.data.Article
import org.opensource.lifealgo.data.Category
import org.opensource.lifealgo.data.DailyEngine
import org.opensource.lifealgo.data.DailyPlan
import org.opensource.lifealgo.data.Reaction
import org.opensource.lifealgo.data.ReactionResult
import org.opensource.lifealgo.data.SearchHit
import org.opensource.lifealgo.data.SelfControl
import org.opensource.lifealgo.data.SelfControlState
import org.opensource.lifealgo.data.Slip
import org.opensource.lifealgo.data.TrackedGoal
import org.opensource.lifealgo.data.UrgeEvent
import org.opensource.lifealgo.data.UserStateRepository
import org.opensource.lifealgo.reminder.ReminderScheduler

data class Profile(
    val sex: String,
    val age: Int,
    val heightCm: Float,
    val weightKg: Float,
    val activity: Float,
    val goal: String,
    val waistCm: Float,
)

class AppViewModel(app: Application) : AndroidViewModel(app) {

    private val appRef = LifeAlgoApp.from(app)
    private val content = appRef.content
    private val settings = appRef.settings
    private val userState = appRef.userState

    val categories: List<Category> = content.categories
    val articles: List<Article> = content.articles
    val byId: Map<String, Article> = content.byId()

    /* ----------------------------- 用户数据 ----------------------------- */

    val favorites: StateFlow<Set<String>> = userState.favorites
        .map { it.toSet() }
        .stateIn(viewModelScope, SharingStarted.Eagerly, emptySet())

    val readIds: StateFlow<Set<String>> = userState.readIds
        .map { it.toSet() }
        .stateIn(viewModelScope, SharingStarted.Eagerly, emptySet())

    val readCount: StateFlow<Int> = userState.readCount
        .stateIn(viewModelScope, SharingStarted.Eagerly, 0)

    val streak: StateFlow<Int> = userState.dayLogs
        .map { UserStateRepository.computeStreak(it) }
        .stateIn(viewModelScope, SharingStarted.Eagerly, 0)

    val totalDays: StateFlow<Int> = userState.dayLogs
        .map { it.size }
        .stateIn(viewModelScope, SharingStarted.Eagerly, 0)

    /* ------------------------------ 设置 ------------------------------ */

    /** 设置变动计数，用来驱动主题/字号重组 */
    private val _revision = MutableStateFlow(0)
    val revision: StateFlow<Int> = _revision.asStateFlow()

    var themeMode: String = settings.themeMode
        private set

    var fontScale: Float = settings.fontScale
        private set

    var reminderEnabled: Boolean = settings.reminderEnabled
        private set

    var reminderHour: Int = settings.reminderHour
        private set

    var reminderMinute: Int = settings.reminderMinute
        private set

    var reminderCategories: Set<String> = settings.reminderCategories
        .split(',').map { it.trim() }.filter { it.isNotEmpty() }.toSet()
        private set

    private val _profile = MutableStateFlow(readProfile())
    val profile: StateFlow<Profile> = _profile.asStateFlow()

    /* --------------------------- 反应力测试 --------------------------- */

    private val _reactionLog = MutableStateFlow(settings.reactionLog)
    val reactionLog: StateFlow<String> = _reactionLog.asStateFlow()

    /* --------------------------- 戒除与自控 --------------------------- */

    private val _selfControl = MutableStateFlow(SelfControl.decode(settings.selfControlRaw))
    val selfControl: StateFlow<SelfControlState> = _selfControl.asStateFlow()

    /* ------------------------------ 每日 ------------------------------ */

    private val _daily = MutableStateFlow(buildDaily())
    val daily: StateFlow<DailyPlan> = _daily.asStateFlow()

    /* ------------------------------ 搜索 ------------------------------ */

    private val _query = MutableStateFlow("")
    val query: StateFlow<String> = _query.asStateFlow()

    private val _results = MutableStateFlow<List<SearchHit>>(emptyList())
    val results: StateFlow<List<SearchHit>> = _results.asStateFlow()

    /* ------------------------------ 提示 ------------------------------ */

    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    init {
        viewModelScope.launch(Dispatchers.IO) {
            runCatching { userState.touchToday() }
        }
    }

    /* ----------------------------- 行为 ----------------------------- */

    fun refreshDaily() {
        _daily.value = buildDaily()
    }

    fun touchToday() {
        viewModelScope.launch(Dispatchers.IO) {
            runCatching { userState.touchToday() }
        }
    }

    fun toggleFavorite(id: String) {
        viewModelScope.launch {
            val now = userState.toggleFavorite(id)
            _message.value = if (now) "已收藏" else "已取消收藏"
        }
    }

    fun openArticle(id: String) {
        viewModelScope.launch(Dispatchers.IO) {
            runCatching {
                userState.markRead(id)
                userState.bumpTodayRead()
            }
        }
    }

    fun search(q: String) {
        _query.value = q
        _results.value = if (q.isBlank()) emptyList() else content.search(q)
    }

    fun clearSearch() {
        _query.value = ""
        _results.value = emptyList()
    }

    fun consumeMessage() {
        _message.value = null
    }

    /* ----------------------------- 设置写入 ----------------------------- */

    fun setTheme(mode: String) {
        settings.themeMode = mode
        themeMode = mode
        _revision.value++
    }

    fun setFontScale(scale: Float) {
        settings.fontScale = scale
        fontScale = settings.fontScale
        _revision.value++
    }

    fun setReminderEnabled(on: Boolean) {
        settings.reminderEnabled = on
        reminderEnabled = on
        val ctx = getApplication<Application>()
        if (on) ReminderScheduler.schedule(ctx, reminderHour, reminderMinute)
        else ReminderScheduler.cancel(ctx)
        _revision.value++
    }

    fun setReminderTime(hour: Int, minute: Int) {
        settings.reminderHour = hour
        settings.reminderMinute = minute
        reminderHour = settings.reminderHour
        reminderMinute = settings.reminderMinute
        if (reminderEnabled) {
            ReminderScheduler.schedule(getApplication(), reminderHour, reminderMinute)
        }
        _revision.value++
    }

    fun toggleReminderCategory(id: String) {
        val next = reminderCategories.toMutableSet()
        if (!next.remove(id)) next.add(id)
        reminderCategories = next
        settings.reminderCategories = next.joinToString(",")
        refreshDaily()
        if (reminderEnabled) {
            ReminderScheduler.schedule(getApplication(), reminderHour, reminderMinute)
        }
        _revision.value++
    }

    fun updateProfile(block: (Profile) -> Profile) {        val next = block(_profile.value)
        settings.sex = next.sex
        settings.age = next.age
        settings.heightCm = next.heightCm
        settings.weightKg = next.weightKg
        settings.activity = next.activity
        settings.goal = next.goal
        settings.waistCm = next.waistCm
        if (!settings.profileReady) settings.profileReady = true
        _profile.value = next
        refreshDaily()
    }

    /* --------------------------- 反应力测试 --------------------------- */

    fun saveReaction(result: ReactionResult) {
        val next = Reaction.appendLog(settings.reactionLog, result)
        settings.reactionLog = next
        _reactionLog.value = next
        _message.value = "已记录：${result.avgMs} ms"
    }

    fun clearReactionHistory() {
        settings.reactionLog = ""
        _reactionLog.value = ""
        _message.value = "测评记录已清空"
    }

    /* --------------------------- 戒除与自控 --------------------------- */

    private fun commitSelfControl(next: SelfControlState, toast: String? = null) {
        settings.selfControlRaw = SelfControl.encode(next)
        _selfControl.value = next
        _revision.value++
        if (toast != null) _message.value = toast
    }

    fun addGoal(id: String, name: String) {
        val cur = _selfControl.value
        if (cur.goals.any { it.id == id }) {
            _message.value = "已经在对「$name」打卡了"
            return
        }
        val goal = TrackedGoal(id = id, name = name, since = System.currentTimeMillis())
        commitSelfControl(cur.copy(goals = cur.goals + goal), "已开始记录：$name")
    }

    fun removeGoal(id: String) {
        val cur = _selfControl.value
        commitSelfControl(
            cur.copy(goals = cur.goals.filterNot { it.id == id }),
            "已移除该目标（历史记录保留在冲动里）",
        )
    }

    /** 记录一次失误。不断开“累计”，只断开“连续”。 */
    fun recordSlip(goalId: String, trigger: String, note: String) {
        val cur = _selfControl.value
        val now = System.currentTimeMillis()
        val goals = cur.goals.map { g ->
            if (g.id == goalId) g.copy(slips = g.slips + Slip(now, trigger, note)) else g
        }
        commitSelfControl(cur.copy(goals = goals), "已记录。累计天数保留，只看接下来的 2 小时。")
    }

    /** 撤销最近一次失误记录（记错了用） */
    fun undoLastSlip(goalId: String) {
        val cur = _selfControl.value
        val goals = cur.goals.map { g ->
            if (g.id == goalId && g.slips.isNotEmpty()) g.copy(slips = g.slips.dropLast(1)) else g
        }
        commitSelfControl(cur.copy(goals = goals), "已撤销上一条记录")
    }

    /** 主动重新开始计时（不算失误） */
    fun restartGoal(goalId: String) {
        val cur = _selfControl.value
        val now = System.currentTimeMillis()
        val goals = cur.goals.map { g -> if (g.id == goalId) g.copy(since = now, slips = emptyList()) else g }
        commitSelfControl(cur.copy(goals = goals), "已重新开始计时")
    }

    fun addUrge(goalId: String, trigger: String, before: Int, after: Int) {
        val cur = _selfControl.value
        val e = UrgeEvent(System.currentTimeMillis(), goalId, trigger, before, after)
        commitSelfControl(cur.copy(urges = cur.urges + e), "记录了一次成功的冲动应对")
    }

    fun toggleChecklist(id: String) {
        val cur = _selfControl.value
        val next = if (id in cur.checklist) cur.checklist - id else cur.checklist + id
        commitSelfControl(cur.copy(checklist = next))
    }

    fun setIfThen(ifPlan: String, thenPlan: String) {
        commitSelfControl(_selfControl.value.copy(ifPlan = ifPlan, thenPlan = thenPlan), "计划已保存")
    }

    fun clearSelfControl() {
        commitSelfControl(SelfControlState(), "戒除数据已清空")
    }

    /* ----------------------------- 内部 ----------------------------- */

    private fun buildDaily(): DailyPlan = DailyEngine.plan(
        now = System.currentTimeMillis(),
        categories = content.categories,
        articles = content.articles,
        enabledCategoryIds = settings.reminderCategories
            .split(',').map { it.trim() }.filter { it.isNotEmpty() }.toSet(),
    )

    private fun readProfile(): Profile = Profile(
        sex = settings.sex,
        age = settings.age,
        heightCm = settings.heightCm,
        weightKg = settings.weightKg,
        activity = settings.activity,
        goal = settings.goal,
        waistCm = settings.waistCm,
    )

    fun category(id: String): Category? = content.category(id)

    fun article(id: String): Article? = byId[id]

    fun byCategory(id: String): List<Article> = content.byCategory(id)

    fun related(article: Article): List<Article> = content.related(article)
}
