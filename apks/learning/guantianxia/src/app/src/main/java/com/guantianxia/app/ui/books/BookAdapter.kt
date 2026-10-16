package com.guantianxia.app.ui.books

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.ImageButton
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import com.guantianxia.app.R
import com.guantianxia.app.net.BooksApi

class BookAdapter(
    private val onOpen: (BooksApi.Book) -> Unit,
    private val onDownload: (BooksApi.Book) -> Unit,
    private val onShare: (BooksApi.Book) -> Unit
) : RecyclerView.Adapter<BookAdapter.VH>() {

    private val items = ArrayList<BooksApi.Book>()

    fun submit(list: List<BooksApi.Book>) {
        items.clear()
        items.addAll(list)
        notifyDataSetChanged()
    }

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val title: TextView = v.findViewById(R.id.tv_title)
        val meta: TextView = v.findViewById(R.id.tv_meta)
        val open: Button = v.findViewById(R.id.btn_open)
        val download: Button = v.findViewById(R.id.btn_download)
        val share: ImageButton = v.findViewById(R.id.btn_share)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH =
        VH(LayoutInflater.from(parent.context).inflate(R.layout.item_book, parent, false))

    override fun getItemCount(): Int = items.size

    override fun onBindViewHolder(holder: VH, position: Int) {
        val b = items[position]
        holder.title.text = b.title
        holder.meta.text = b.author.ifBlank { "佚名" }

        holder.open.setOnClickListener { onOpen(b) }
        holder.share.setOnClickListener { onShare(b) }

        if (b.epubUrl == null) {
            holder.download.isEnabled = false
            holder.download.text = holder.itemView.context.getString(R.string.book_no_epub)
            holder.download.setOnClickListener(null)
        } else {
            holder.download.isEnabled = true
            holder.download.text = holder.itemView.context.getString(R.string.book_download)
            holder.download.setOnClickListener { onDownload(b) }
        }
    }
}
