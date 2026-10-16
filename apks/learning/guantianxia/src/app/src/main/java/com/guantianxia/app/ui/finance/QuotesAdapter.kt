package com.guantianxia.app.ui.finance

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.RecyclerView
import com.guantianxia.app.R
import com.guantianxia.app.net.QuotesApi

class QuotesAdapter : RecyclerView.Adapter<QuotesAdapter.VH>() {

    private val items = ArrayList<QuotesApi.Quote>()

    fun submit(list: List<QuotesApi.Quote>) {
        items.clear()
        items.addAll(list)
        notifyDataSetChanged()
    }

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val name: TextView = v.findViewById(R.id.tv_name)
        val price: TextView = v.findViewById(R.id.tv_price)
        val change: TextView = v.findViewById(R.id.tv_change)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH =
        VH(LayoutInflater.from(parent.context).inflate(R.layout.item_quote, parent, false))

    override fun getItemCount(): Int = items.size

    override fun onBindViewHolder(holder: VH, position: Int) {
        val q = items[position]
        val ctx = holder.itemView.context
        holder.name.text = q.name
        holder.price.text = q.price
        holder.change.text = q.change
        val color = when {
            q.change == "汇率" -> R.color.flat
            q.up -> R.color.up
            else -> R.color.down
        }
        holder.change.setTextColor(ContextCompat.getColor(ctx, color))
        holder.price.setTextColor(ContextCompat.getColor(ctx, color))
    }
}
