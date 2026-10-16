package com.guantianxia.app.net

import com.guantianxia.app.core.Http
import org.json.JSONObject
import java.net.URLEncoder

/**
 * 图书源（两个都实测直连可用，不需要代理）
 *  - Project Gutenberg：全球公版书，含大量中文公版（红楼梦、三国演义…）
 *  - ctext 中国哲学书电子化计划：先秦到清的中文典籍
 */
object BooksApi {

    data class Book(
        val id: String,
        val title: String,
        val author: String,
        /** 在线阅读地址 */
        val readUrl: String,
        /** EPUB 直链，null = 该源不提供 */
        val epubUrl: String?
    )

    fun searchGutenberg(query: String): List<Book> {
        val q = URLEncoder.encode(query, "UTF-8")
        val html = Http.text("https://www.gutenberg.org/ebooks/search/?query=$q") ?: return emptyList()
        val out = ArrayList<Book>()
        val chunks = html.split("class=\"booklink\"")
        for (i in 1 until chunks.size) {
            val chunk = chunks[i]
            val id = Regex("/ebooks/(\\d+)").find(chunk)?.groupValues?.get(1) ?: continue
            val title = Regex("class=\"title\">([^<]*)<")
                .find(chunk)?.groupValues?.get(1)?.let { unescape(it) }
            if (title.isNullOrBlank()) continue
            val author = Regex("class=\"subtitle\">([^<]*)<")
                .find(chunk)?.groupValues?.get(1)?.let { unescape(it) } ?: ""
            out.add(
                Book(
                    id = id,
                    title = title,
                    author = author,
                    readUrl = "https://www.gutenberg.org/ebooks/$id",
                    epubUrl = "https://www.gutenberg.org/ebooks/$id.epub.images"
                )
            )
            if (out.size >= 30) break
        }
        return out
    }

    fun searchCtext(query: String): List<Book> {
        val q = URLEncoder.encode(query, "UTF-8")
        val json = Http.text("https://api.ctext.org/searchtexts?title=$q") ?: return emptyList()
        val out = ArrayList<Book>()
        runCatching {
            val arr = JSONObject(json).optJSONArray("books") ?: return@runCatching
            for (i in 0 until arr.length()) {
                val o = arr.optJSONObject(i) ?: continue
                val urn = o.optString("urn")
                val title = o.optString("title")
                if (urn.isBlank() || title.isBlank()) continue
                out.add(
                    Book(
                        id = urn,
                        title = title,
                        author = "中国哲学书电子化计划",
                        readUrl = "https://ctext.org/" + urn.removePrefix("ctp:"),
                        epubUrl = null
                    )
                )
                if (out.size >= 30) break
            }
        }
        return out
    }

    private fun unescape(s: String): String =
        s.replace("&amp;", "&")
            .replace("&#39;", "'")
            .replace("&quot;", "\"")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .trim()
}
