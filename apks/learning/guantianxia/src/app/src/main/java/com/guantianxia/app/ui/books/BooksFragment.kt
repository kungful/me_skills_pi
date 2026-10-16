package com.guantianxia.app.ui.books

import android.os.Bundle
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.chip.Chip
import com.google.android.material.chip.ChipGroup
import com.guantianxia.app.R
import com.guantianxia.app.net.BooksApi
import com.guantianxia.app.ui.ArticleActions
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

class BooksFragment : Fragment(R.layout.fragment_books) {

    private lateinit var adapter: BookAdapter
    private var source: String = SRC_GUTENBERG

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        val et = view.findViewById<EditText>(R.id.et_query)
        val btn = view.findViewById<Button>(R.id.btn_search)
        val chips = view.findViewById<ChipGroup>(R.id.source_chips)
        val status = view.findViewById<TextView>(R.id.tv_status)
        val rv = view.findViewById<RecyclerView>(R.id.rv_books)

        adapter = BookAdapter(
            onOpen = { b -> ArticleActions.open(requireContext(), b.title, b.readUrl) },
            onDownload = { b -> download(b, status) },
            onShare = { b ->
                ArticleActions.shareDialog(
                    requireActivity(),
                    "《${b.title}》",
                    if (b.author.isBlank()) "" else "作者：${b.author}",
                    "观天下 · 书架",
                    b.readUrl
                )
            }
        )
        rv.layoutManager = LinearLayoutManager(requireContext())
        rv.adapter = adapter

        buildChips(chips)

        btn.setOnClickListener { search(et.text.toString(), status) }
        et.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_SEARCH) {
                search(et.text.toString(), status)
                true
            } else {
                false
            }
        }

        status.text = "公版书源：Project Gutenberg（含大量中文公版），中文典籍源：ctext。直连可用，无需代理。"
        et.setText("红楼梦")
        search("红楼梦", status)
    }

    private fun buildChips(group: ChipGroup) {
        val items = listOf(
            SRC_GUTENBERG to getString(R.string.book_source_pd),
            SRC_CTEXT to getString(R.string.book_source_ctext)
        )
        for ((key, label) in items) {
            val chip = Chip(requireContext())
            chip.id = View.generateViewId()
            chip.text = label
            chip.isCheckable = true
            chip.tag = key
            group.addView(chip)
        }
        (group.getChildAt(0) as? Chip)?.isChecked = true
        group.setOnCheckedChangeListener { g, id ->
            source = (g.findViewById<Chip>(id)?.tag as? String) ?: SRC_GUTENBERG
        }
    }

    private fun search(query: String, status: TextView) {
        val q = query.trim()
        if (q.isEmpty()) {
            Toast.makeText(requireContext(), "先输入书名或作者", Toast.LENGTH_SHORT).show()
            return
        }
        val src = source
        viewLifecycleOwner.lifecycleScope.launch {
            status.text = "搜索「$q」…"
            val list = withContext(Dispatchers.IO) {
                if (src == SRC_CTEXT) BooksApi.searchCtext(q) else BooksApi.searchGutenberg(q)
            }
            if (!isAdded) return@launch
            adapter.submit(list)
            status.text = if (list.isEmpty()) {
                "没搜到「$q」。Gutenberg 用英文关键词命中率更高（如 journey to the west）；中文典籍用简体书名。"
            } else {
                "找到 ${list.size} 本 · 来源：${if (src == SRC_CTEXT) "ctext" else "Project Gutenberg"}"
            }
        }
    }

    private fun download(book: BooksApi.Book, status: TextView) {
        val url = book.epubUrl ?: return
        viewLifecycleOwner.lifecycleScope.launch {
            status.text = "下载中：${book.title} …"
            val dir = requireContext().getExternalFilesDir("books") ?: requireContext().filesDir
            val name = book.title.replace(Regex("[\\\\/:*?\"<>|]"), "_").take(60) + ".epub"
            val file = File(dir, name)
            val ok = withContext(Dispatchers.IO) {
                com.guantianxia.app.core.Http.download(url, false, file)
            }
            if (!isAdded) return@launch
            status.text = if (ok) {
                "已下载：${file.absolutePath}（${file.length() / 1024} KB）"
            } else {
                "下载失败：$url"
            }
        }
    }

    private fun openUrl(url: String) {
        ArticleActions.openInBrowser(requireContext(), url)
    }

    companion object {
        private const val SRC_GUTENBERG = "gutenberg"
        private const val SRC_CTEXT = "ctext"
    }
}
