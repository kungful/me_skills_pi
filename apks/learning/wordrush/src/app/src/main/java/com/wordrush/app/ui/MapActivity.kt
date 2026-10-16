package com.wordrush.app.ui

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.GridLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.wordrush.app.R
import com.wordrush.app.core.Edge
import com.wordrush.app.core.Prefs
import com.wordrush.app.data.Bank
import com.wordrush.app.data.ProgressStore
import com.wordrush.app.fx.Sfx
import com.wordrush.app.fx.Vib

class MapActivity : AppCompatActivity() {

    private lateinit var prefs: Prefs
    private lateinit var store: ProgressStore
    private lateinit var list: RecyclerView
    private lateinit var bankRow: LinearLayout
    private lateinit var adapter: LevelAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_map)
        Edge.install(this, findViewById(R.id.root))

        prefs = Prefs(this)
        store = ProgressStore(this)
        Sfx.enabled = prefs.soundOn
        Vib.enabled = prefs.vibrateOn

        list = findViewById(R.id.list)
        bankRow = findViewById(R.id.bankRow)
        adapter = LevelAdapter()
        list.layoutManager = GridLayoutManager(this, 3)
        list.adapter = adapter
        list.itemAnimator = null

        findViewById<View>(R.id.btnBack).setOnClickListener { finish() }
        buildBankRow()
    }

    override fun onResume() {
        super.onResume()
        refresh()
    }

    private fun buildBankRow() {
        bankRow.removeAllViews()
        for (info in Bank.INFO) {
            val tv = TextView(this)
            tv.text = info.name
            tv.textSize = 13f
            tv.gravity = android.view.Gravity.CENTER
            tv.setPadding(dp(16), dp(8), dp(16), dp(8))
            tv.isClickable = true
            tv.isFocusable = true
            tv.setOnClickListener {
                Sfx.play(Sfx.TAP)
                prefs.setBank(info.id)
                refresh()
            }
            val lp = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT
            )
            lp.marginEnd = dp(8)
            bankRow.addView(tv, lp)
        }
    }

    private fun refresh() {
        val bank = prefs.curBank()
        for (i in 0 until bankRow.childCount) {
            val tv = bankRow.getChildAt(i) as TextView
            val active = i == bank
            tv.setBackgroundResource(if (active) R.drawable.pill_cyan else R.drawable.btn_ghost)
            tv.setTextColor(if (active) 0xFF04121A.toInt() else 0xFFB6C2E0.toInt())
            tv.setTypeface(null, if (active) android.graphics.Typeface.BOLD else android.graphics.Typeface.NORMAL)
        }

        findViewById<TextView>(R.id.tvTitle).text = Bank.info(bank).name
        val total = Bank.levelCount(this, bank)
        val done = prefs.done(bank)
        findViewById<TextView>(R.id.tvStarSum).text = "${prefs.starSum(bank)} ★ / ${total * 3}"
        findViewById<TextView>(R.id.tvHint).text = "$total 关 · 每关 ${Bank.PER_LEVEL} 词 · 已通 $done 关"

        adapter.submit(total, done, prefs.stars(bank))
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density + 0.5f).toInt()

    private inner class LevelAdapter : RecyclerView.Adapter<LevelAdapter.VH>() {

        private var total = 0
        private var done = 0
        private var stars = IntArray(0)

        fun submit(total: Int, done: Int, stars: IntArray) {
            this.total = total
            this.done = done
            this.stars = stars
            notifyDataSetChanged()
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH =
            VH(LayoutInflater.from(parent.context).inflate(R.layout.item_level, parent, false))

        override fun getItemCount(): Int = total

        override fun onBindViewHolder(holder: VH, position: Int) {
            holder.bind(position)
        }

        inner class VH(v: View) : RecyclerView.ViewHolder(v) {
            val tvNo: TextView = v.findViewById(R.id.tvNo)
            val starRow: LinearLayout = v.findViewById(R.id.starRow)
            val ivLock: ImageView = v.findViewById(R.id.ivLock)
            val root: View = v

            fun bind(pos: Int) {
                val unlocked = pos <= done
                val star = stars.getOrElse(pos) { 0 }
                root.alpha = if (unlocked) 1f else 0.45f
                tvNo.text = "${pos + 1}"
                tvNo.setTextColor(
                    when {
                        !unlocked -> 0xFF5B6A92.toInt()
                        star > 0 -> 0xFFFFC93C.toInt()
                        else -> 0xFF35E0FF.toInt()
                    }
                )
                ivLock.visibility = if (unlocked) View.GONE else View.VISIBLE

                starRow.removeAllViews()
                for (i in 0 until 3) {
                    val iv = ImageView(root.context)
                    iv.setImageResource(if (i < star) R.drawable.ic_star else R.drawable.ic_star_empty)
                    val lp = LinearLayout.LayoutParams(dp(11), dp(11))
                    lp.marginStart = dp(1)
                    lp.marginEnd = dp(1)
                    starRow.addView(iv, lp)
                }

                root.setOnClickListener {
                    Sfx.play(Sfx.TAP)
                    Vib.tap(root.context)
                    if (!unlocked) {
                        Toast.makeText(root.context, "先通过第 $done 关才能解锁", Toast.LENGTH_SHORT).show()
                    } else {
                        val bank = prefs.curBank()
                        root.context.startActivity(
                            Intent(root.context, PlayActivity::class.java)
                                .putExtra(PlayActivity.EXTRA_MODE, PlayActivity.MODE_LEVEL)
                                .putExtra(PlayActivity.EXTRA_BANK, bank)
                                .putExtra(PlayActivity.EXTRA_LEVEL, pos)
                        )
                    }
                }
            }
        }
    }
}
