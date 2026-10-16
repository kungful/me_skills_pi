package com.wordrush.app.ui

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.GridLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.wordrush.app.R
import com.wordrush.app.core.Edge
import com.wordrush.app.core.Prefs
import com.wordrush.app.data.Achievement
import com.wordrush.app.data.Achievements
import com.wordrush.app.data.Ctx
import com.wordrush.app.data.ProgressStore
import com.wordrush.app.fx.Sfx

class AchieveActivity : AppCompatActivity() {

    private lateinit var prefs: Prefs
    private lateinit var store: ProgressStore
    private lateinit var data: List<Achievement>

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_achieve)
        Edge.install(this, findViewById(R.id.root))

        prefs = Prefs(this)
        store = ProgressStore(this)
        Sfx.enabled = prefs.soundOn
        data = Achievements.ALL

        findViewById<View>(R.id.btnBack).setOnClickListener { finish() }
        val c = Ctx(prefs, store, this)
        findViewById<TextView>(R.id.tvTitle).text =
            "成就 · ${Achievements.unlockedCount(c)} / ${data.size}"

        val list = findViewById<RecyclerView>(R.id.list)
        list.layoutManager = GridLayoutManager(this, 2)
        list.adapter = Adapter(Ctx(prefs, store, this))
        list.itemAnimator = null
    }

    private inner class Adapter(private val c: Ctx) : RecyclerView.Adapter<Adapter.VH>() {

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH =
            VH(LayoutInflater.from(parent.context).inflate(R.layout.item_achieve, parent, false))

        override fun getItemCount(): Int = data.size

        override fun onBindViewHolder(holder: VH, position: Int) = holder.bind(data[position])

        inner class VH(v: View) : RecyclerView.ViewHolder(v) {
            val tvIcon: TextView = v.findViewById(R.id.tvIcon)
            val tvName: TextView = v.findViewById(R.id.tvName)
            val tvDesc: TextView = v.findViewById(R.id.tvDesc)
            val tvState: TextView = v.findViewById(R.id.tvState)
            val root: View = v

            fun bind(a: Achievement) {
                val ok = a.check(c)
                tvIcon.text = if (ok) a.icon else "\uD83D\uDD12"
                tvName.text = a.name
                tvDesc.text = a.desc
                root.alpha = if (ok) 1f else 0.55f
                if (ok) {
                    tvState.text = "已解锁"
                    tvState.setTextColor(0xFF34D399.toInt())
                } else {
                    val p = (a.progress(c).coerceIn(0f, 1f) * 100).toInt()
                    tvState.text = "进度 $p%"
                    tvState.setTextColor(0xFF8494BD.toInt())
                }
            }
        }
    }

    override fun onPause() {
        super.onPause()
        store.saveIfDirty()
    }
}
