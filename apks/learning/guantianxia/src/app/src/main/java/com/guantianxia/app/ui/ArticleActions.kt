package com.guantianxia.app.ui

import android.app.Activity
import android.content.Context
import android.content.Intent
import androidx.appcompat.app.AlertDialog
import com.guantianxia.app.R
import com.guantianxia.app.core.Share
import com.guantianxia.app.data.Article
import com.guantianxia.app.data.Db

/**
 * 列表项的统一行为：点开站内预览 / 长按出菜单 / 分享到微信朋友圈、好友等。
 */
object ArticleActions {

    fun open(context: Context, article: Article) {
        context.startActivity(
            ArticleActivity.intent(
                context, article.title, article.url, article.summary, article.sourceName
            )
        )
    }

    fun open(context: Context, title: String, url: String) {
        context.startActivity(ArticleActivity.intent(context, title, url))
    }

    fun openInBrowser(context: Context, url: String) {
        runCatching {
            context.startActivity(Intent(Intent.ACTION_VIEW, android.net.Uri.parse(url)))
        }
    }

    /**
     * 分享选择：朋友圈 / 系统分享面板 / 复制链接。
     * 朋友圈单独列出来是因为它不在系统分享面板里。
     */
    fun shareDialog(
        activity: Activity,
        title: String,
        summary: String,
        source: String,
        url: String
    ) {
        val items = arrayOf(
            activity.getString(R.string.share_timeline),
            activity.getString(R.string.share_friend),
            activity.getString(R.string.action_copy_link)
        )
        AlertDialog.Builder(activity)
            .setTitle(R.string.action_share)
            .setItems(items) { _, which ->
                when (which) {
                    0 -> Share.moments(activity, title, summary, source, url)
                    1 -> Share.text(activity, title, url)
                    else -> Share.copy(activity, "链接", url)
                }
            }
            .show()
    }

    fun shareDialog(activity: Activity, article: Article) =
        shareDialog(activity, article.title, article.summary, article.sourceName, article.url)

    /** 长按菜单 */
    fun showMenu(activity: Activity, article: Article, db: Db, onChanged: () -> Unit) {
        val labels = arrayOf(
            if (article.saved) "取消收藏" else "收藏",
            activity.getString(R.string.share_timeline),
            activity.getString(R.string.share_friend),
            activity.getString(R.string.action_copy_link),
            activity.getString(R.string.action_open_browser)
        )
        AlertDialog.Builder(activity)
            .setTitle(article.title.take(40))
            .setItems(labels) { _, which ->
                when (which) {
                    0 -> {
                        db.setSaved(article.id, !article.saved)
                        onChanged()
                    }

                    1 -> Share.moments(
                        activity, article.title, article.summary, article.sourceName, article.url
                    )

                    2 -> Share.text(activity, article.title, article.url)
                    3 -> Share.copy(activity, "链接", article.url)
                    else -> openInBrowser(activity, article.url)
                }
            }
            .show()
    }
}
