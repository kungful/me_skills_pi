package com.wordrush.app.ui

import android.annotation.SuppressLint
import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.wordrush.app.R
import com.wordrush.app.core.Edge
import com.wordrush.app.core.Prefs
import com.wordrush.app.core.Speaker
import com.wordrush.app.data.ProgressStore
import com.wordrush.app.data.Word
import com.wordrush.app.fx.Sfx
import com.wordrush.app.fx.Vib

class WrongActivity : AppCompatActivity() {

    private lateinit var prefs: Prefs
    private lateinit var store: ProgressStore
    private lateinit var speaker: Speaker
    private lateinit var adapter: Adapter
    private var shown: List<Word> = emptyList()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_wrong)
        Edge.install(this, findViewById(R.id.root))

        prefs = Prefs(this)
        store = ProgressStore(this)
        speaker = Speaker(this)
        Sfx.enabled = prefs.soundOn
        Vib.enabled = prefs.vibrateOn

        adapter = Adapter()
        val list = findViewById<RecyclerView>(R.id.list)
        list.layoutManager = LinearLayoutManager(this)
        list.adapter = adapter

        findViewById<View>(R.id.btnBack).setOnClickListener { finish() }
        findViewById<View>(R.id.btnPractice).setOnClickListener {
            Sfx.play(Sfx.TAP)
            if (shown.isEmpty()) return@setOnClickListener
            startActivity(
                Intent(this, PlayActivity::class.java)
                    .putExtra(PlayActivity.EXTRA_MODE, PlayActivity.MODE_WRONG)
                    .putExtra(PlayActivity.EXTRA_BANK, prefs.curBank())
            )
        }
        findViewById<View>(R.id.btnClear).setOnClickListener {
            AlertDialog.Builder(this)
                .setTitle("清空错题本？")
                .setMessage("所有单词的错误次数会归零，掌握进度保留。")
                .setPositiveButton("清空") { _, _ ->
                    for (r in store.map.values) r.wrong = 0
                    store.markDirty()
                    store.save()
                    refresh()
                }
                .setNegativeButton("取消", null)
                .show()
        }
    }

    override fun onResume() {
        super.onResume()
        refresh()
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

    private fun refresh() {
        shown = store.wrongWords(this)
        findViewById<TextView>(R.id.tvTitle).text = "错题本 · ${shown.size}"
        findViewById<TextView>(R.id.tvHint).text =
            if (shown.isEmpty()) "还没有错题，保持住！"
            else "按错误次数排序，答对后会自动淡化，直到掌握"
        adapter.notifyDataSetChanged()
    }

    private inner class Adapter : RecyclerView.Adapter<Adapter.VH>() {
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
                val r = store.rec(w.id)
                tvEn.text = w.en
                tvIpa.text = if (w.ipa.isEmpty()) "" else "/${w.ipa}/"
                tvZh.text = "${w.zh}   ·   错 ${r?.wrong ?: 0} 次"
                dot.setBackgroundColor(0xFFFB5B5B.toInt())
                ivSpeak.setOnClickListener { speaker.say(w.en) }
                root.setOnClickListener {
                    speaker.say(w.en)
                    AlertDialog.Builder(this@WrongActivity)
                        .setTitle(w.en)
                        .setMessage((if (w.ipa.isEmpty()) "" else "/${w.ipa}/\n") + w.zh)
                        .setPositiveButton("知道了", null)
                        .show()
                }
            }
        }
    }
}
