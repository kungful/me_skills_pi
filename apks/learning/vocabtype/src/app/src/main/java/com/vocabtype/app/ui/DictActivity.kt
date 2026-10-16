package com.vocabtype.app.ui

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.ImageButton
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.vocabtype.app.R
import com.vocabtype.app.core.Insets
import com.vocabtype.app.core.Prefs
import com.vocabtype.app.data.DictMeta
import com.vocabtype.app.data.Dicts

class DictActivity : AppCompatActivity() {

    private lateinit var prefs: Prefs
    private var all: List<DictMeta> = emptyList()
    private var shown: List<DictMeta> = emptyList()
    private lateinit var rv: RecyclerView
    private lateinit var search: EditText
    private lateinit var tvCount: TextView
    private var sel = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_dict)
        prefs = Prefs(this)
        Insets.apply(this, findViewById(R.id.root), bottom = false)
        sel = prefs.dictId

        rv = findViewById(R.id.rv)
        search = findViewById(R.id.etSearch)
        tvCount = findViewById(R.id.tvCount)

        all = Dicts.index(this)
        shown = all
        rv.layoutManager = LinearLayoutManager(this)
        rv.adapter = Adapter()

        findViewById<ImageButton>(R.id.btnBack).setOnClickListener { finish() }
        findViewById<ImageButton>(R.id.btnClose).setOnClickListener { finish() }
        findViewById<ImageButton>(R.id.btnSearchClear).setOnClickListener { search.setText("") }

        search.addTextChangedListener(object : android.text.TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun afterTextChanged(s: android.text.Editable?) {
                val q = s?.toString()?.trim()?.lowercase() ?: ""
                shown = if (q.isEmpty()) all else all.filter { m ->
                    m.name.lowercase().contains(q) ||
                        m.name.replace(" ", "").contains(q) ||
                        cnAlias(m.name).contains(q)
                }
                rv.adapter?.notifyDataSetChanged()
                tvCount.text = "命中 ${shown.size} / ${all.size} 个词库"
            }
        })
        tvCount.text = "共 ${all.size} 个词库 · 长按可重置进度"
    }

    private fun cnAlias(n: String): String = when {
        n.contains("中考") -> "初中 中学"
        n.contains("高考") -> "高中"
        n.contains("四级") || n.contains("CET4", true) -> "四级 cet4 大学"
        n.contains("六级") || n.contains("CET6", true) -> "六级 cet6 大学"
        n.contains("考研") -> "研究生 kaoyan"
        n.contains("雅思") -> "ielts 出国"
        n.contains("托福") -> "toefl 出国"
        n.contains("新概念") -> "nce"
        n.contains("牛津") -> "oxford"
        n.contains("专升本") -> "升本"
        n.contains("VOA", true) -> "voa 新闻"
        n.contains("4000") -> "基础 核心"
        n.contains("926") -> "核心 基础"
        else -> ""
    }

    private inner class Adapter : RecyclerView.Adapter<Adapter.VH>() {

        inner class VH(v: View) : RecyclerView.ViewHolder(v) {
            val name: TextView = v.findViewById(R.id.tvName)
            val bar: TextView = v.findViewById(R.id.tvBar)
            val meta: TextView = v.findViewById(R.id.tvMeta)
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH =
            VH(LayoutInflater.from(parent.context).inflate(R.layout.item_dict, parent, false))

        override fun getItemCount(): Int = shown.size

        override fun onBindViewHolder(h: VH, position: Int) {
            val m = shown[position]
            val done = prefs.dictProgress(m.id).coerceIn(0, m.count.coerceAtLeast(1))
            val pct = if (m.count > 0) done * 100.0 / m.count else 0.0

            h.name.text = (if (m.id == sel) "▍ " else "  ") + m.name
            h.meta.text = String.format(java.util.Locale.US, "%d 词 · 已打到 %d (%.1f%%)", m.count, done, pct)
            h.bar.text = bar(pct)

            h.itemView.isSelected = m.id == sel
            h.itemView.setOnClickListener {
                prefs.dictId = m.id
                Toast.makeText(this@DictActivity, "已切到：${m.name}", Toast.LENGTH_SHORT).show()
                setResult(RESULT_OK, Intent())
                finish()
            }
            h.itemView.setOnLongClickListener {
                AlertDialog.Builder(this@DictActivity)
                    .setTitle("[ ${m.name} ]")
                    .setMessage("把这个词库的打字进度重置到第 1 个词？\n（错词本和累计统计不受影响）")
                    .setPositiveButton("重置") { _, _ ->
                        prefs.setDictProgress(m.id, 0)
                        notifyItemChanged(position)
                    }
                    .setNegativeButton("算了", null)
                    .show()
                true
            }
        }
    }

    private fun bar(pct: Double): String {
        val n = 22
        val on = ((pct / 100.0) * n).toInt().coerceIn(0, n)
        val sb = StringBuilder()
        for (i in 0 until n) sb.append(if (i < on) '█' else '░')
        return sb.toString()
    }
}
