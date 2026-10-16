package com.wordrush.app.ui

import android.annotation.SuppressLint
import android.content.Intent
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.wordrush.app.R
import com.wordrush.app.core.Edge
import com.wordrush.app.core.Prefs
import com.wordrush.app.core.Speaker
import com.wordrush.app.data.Bank
import com.wordrush.app.data.ProgressStore
import com.wordrush.app.data.Srs
import com.wordrush.app.data.Word
import com.wordrush.app.fx.Sfx
import com.wordrush.app.fx.Vib

class BankActivity : AppCompatActivity() {

    private lateinit var prefs: Prefs
    private lateinit var store: ProgressStore
    private lateinit var speaker: Speaker
    private lateinit var list: RecyclerView
    private lateinit var filterRow: LinearLayout
    private lateinit var adapter: WordAdapter

    private var bank = 0
    private var filter = 0
    private var query = ""
    private var shown: List<Word> = emptyList()

    private val filters = listOf("全部", "未学", "学习中", "已掌握", "收藏")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_bank)
        Edge.install(this, findViewById(R.id.root))

        prefs = Prefs(this)
        store = ProgressStore(this)
        speaker = Speaker(this)
        Sfx.enabled = prefs.soundOn
        Vib.enabled = prefs.vibrateOn
        bank = prefs.curBank()

        list = findViewById(R.id.list)
        filterRow = findViewById(R.id.filterRow)
        adapter = WordAdapter()
        list.layoutManager = LinearLayoutManager(this)
        list.adapter = adapter

        findViewById<View>(R.id.btnBack).setOnClickListener { finish() }
        findViewById<View>(R.id.btnPractice).setOnClickListener {
            tap()
            val pool = shown.take(20)
            if (pool.isEmpty()) return@setOnClickListener
            startActivity(
                Intent(this, PlayActivity::class.java)
                    .putExtra(PlayActivity.EXTRA_MODE, PlayActivity.MODE_CUSTOM)
                    .putExtra(PlayActivity.EXTRA_BANK, bank)
                    .putExtra(PlayActivity.EXTRA_IDS, pool.map { it.id }.toIntArray())
            )
        }

        findViewById<EditText>(R.id.etSearch).addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun afterTextChanged(s: Editable?) {
                query = s?.toString()?.trim() ?: ""
                apply()
            }
        })

        buildFilters()
        // 首次加载词库数据（解 JSON）
        Bank.words(this, bank)
        apply()
    }

    override fun onResume() {
        super.onResume()
        apply()
    }

    override fun onPause() {
        super.onPause()
        speaker.stop()
        store.saveIfDirty()
    }

    override fun onDestroy() {
        super.onDestroy()
        speaker.shutdown()
    }

    private fun tap() {
        Sfx.play(Sfx.TAP)
        Vib.tap(this)
    }

    private fun buildFilters() {
        filterRow.removeAllViews()
        for (i in filters.indices) {
            val tv = TextView(this)
            tv.text = filters[i]
            tv.textSize = 13f
            tv.gravity = android.view.Gravity.CENTER
            tv.setPadding(dp(14), dp(7), dp(14), dp(7))
            tv.isClickable = true
            tv.isFocusable = true
            tv.setOnClickListener {
                tap()
                filter = i
                apply()
            }
            val lp = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT
            )
            lp.marginEnd = dp(8)
            filterRow.addView(tv, lp)
        }
    }

    private fun apply() {
        for (i in 0 until filterRow.childCount) {
            val tv = filterRow.getChildAt(i) as TextView
            val active = i == filter
            tv.setBackgroundResource(if (active) R.drawable.pill_purple else R.drawable.btn_ghost)
            tv.setTextColor(if (active) 0xFFFFFFFF.toInt() else 0xFFB6C2E0.toInt())
        }

        val base = store.byState(this, bank, filter)
        shown = if (query.isEmpty()) base else base.filter {
            it.en.contains(query, true) || it.zh.contains(query, true)
        }
        findViewById<TextView>(R.id.tvTitle).text = "${Bank.info(bank).name} · ${shown.size} 词"
        findViewById<TextView>(R.id.tvEmpty).visibility = if (shown.isEmpty()) View.VISIBLE else View.GONE
        adapter.notifyDataSetChanged()
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density + 0.5f).toInt()

    private fun openDetail(w: Word) {
        val view = LayoutInflater.from(this).inflate(R.layout.dialog_word, null)
        view.findViewById<TextView>(R.id.dEn).text = w.en
        view.findViewById<TextView>(R.id.dIpa).text = if (w.ipa.isEmpty()) "" else "/${w.ipa}/"
        view.findViewById<TextView>(R.id.dZh).text = w.zh
        val r = store.rec(w.id)
        val meta = when {
            r == null -> "还没有练过 · 点「朗读」听发音"
            else -> "记忆等级 ${r.lvl}/7 · 对 ${r.correct} / 错 ${r.wrong}" +
                if (r.mastered) " · 已掌握" else ""
        }
        view.findViewById<TextView>(R.id.dMeta).text = meta
        speaker.say(w.en)

        val fav = store.recOrNew(w.id).fav
        AlertDialog.Builder(this)
            .setView(view)
            .setPositiveButton(if (fav) "取消收藏" else "收藏") { _, _ ->
                store.recOrNew(w.id).fav = !fav
                store.markDirty()
                apply()
            }
            .setNegativeButton("朗读") { _, _ -> speaker.say(w.en) }
            .setNeutralButton("关闭", null)
            .show()
    }

    private inner class WordAdapter : RecyclerView.Adapter<WordAdapter.VH>() {

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH =
            VH(LayoutInflater.from(parent.context).inflate(R.layout.item_word, parent, false))

        override fun getItemCount(): Int = shown.size

        override fun onBindViewHolder(holder: VH, position: Int) = holder.bind(shown[position])

        inner class VH(v: View) : RecyclerView.ViewHolder(v) {
            val dot: View = v.findViewById(R.id.dot)
            val tvEn: TextView = v.findViewById(R.id.tvEn)
            val tvIpa: TextView = v.findViewById(R.id.tvIpa)
            val tvZh: TextView = v.findViewById(R.id.tvZh)
            val ivSpeak: ImageView = v.findViewById(R.id.ivSpeak)
            val root: View = v

            @SuppressLint("SetTextI18n")
            fun bind(w: Word) {
                tvEn.text = w.en
                tvIpa.text = if (w.ipa.isEmpty()) "" else "/${w.ipa}/"
                tvZh.text = w.zh
                val r = store.rec(w.id)
                dot.setBackgroundColor(
                    when {
                        r == null -> 0xFF3A4A72.toInt()
                        r.mastered -> 0xFF34D399.toInt()
                        r.lvl == 0 -> 0xFFFB5B5B.toInt()
                        else -> 0xFF35E0FF.toInt()
                    }
                )
                ivSpeak.setOnClickListener { speaker.say(w.en) }
                root.setOnClickListener { openDetail(w) }
            }
        }
    }
}
