package com.guantianxia.app.ui.news

import android.content.res.ColorStateList
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageButton
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.RecyclerView
import com.guantianxia.app.R
import com.guantianxia.app.core.TimeUtil
import com.guantianxia.app.data.Article
import com.guantianxia.app.filter.JunkFilter

class NewsAdapter(
    private val onOpen: (Article) -> Unit,
    private val onShare: (Article) -> Unit,
    private val onMore: (Article) -> Unit
) : RecyclerView.Adapter<NewsAdapter.VH>() {

    private val items = ArrayList<Article>()

    fun submit(list: List<Article>) {
        items.clear()
        items.addAll(list)
        notifyDataSetChanged()
    }

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val title: TextView = v.findViewById(R.id.tv_title)
        val summary: TextView = v.findViewById(R.id.tv_summary)
        val meta: TextView = v.findViewById(R.id.tv_meta)
        val score: TextView = v.findViewById(R.id.tv_score)
        val ev: TextView = v.findViewById(R.id.tv_ev)
        val share: ImageButton = v.findViewById(R.id.btn_share)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH =
        VH(LayoutInflater.from(parent.context).inflate(R.layout.item_article, parent, false))

    override fun getItemCount(): Int = items.size

    override fun onBindViewHolder(holder: VH, position: Int) {
        val a = items[position]
        val ctx = holder.itemView.context

        holder.title.text = if (a.saved) "★ ${a.title}" else a.title
        holder.summary.text = a.summary
        holder.summary.visibility = if (a.summary.isBlank()) View.GONE else View.VISIBLE

        holder.meta.text = listOf(a.sourceName, TimeUtil.ago(a.publishedAt))
            .filter { it.isNotEmpty() }
            .joinToString(" · ")

        holder.score.text = "${a.score} ${JunkFilter.label(a.score)}"
        val color = when {
            a.score >= 85 -> R.color.score_good
            a.score >= 70 -> R.color.brand
            else -> R.color.score_bad
        }
        holder.score.backgroundTintList =
            ColorStateList.valueOf(ContextCompat.getColor(ctx, color))

        // 学 AIHOT：同一件事有多家独立媒体报道时标出来
        val n = a.sourceCount
        if (n >= 2) {
            holder.ev.text = ctx.getString(R.string.ev_sources, n)
            holder.ev.visibility = View.VISIBLE
        } else {
            holder.ev.visibility = View.GONE
        }

        holder.itemView.setOnClickListener { onOpen(a) }
        holder.itemView.setOnLongClickListener {
            onMore(a)
            true
        }
        holder.share.setOnClickListener { onShare(a) }
    }
}
