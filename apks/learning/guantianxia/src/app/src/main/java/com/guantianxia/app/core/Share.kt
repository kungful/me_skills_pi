package com.guantianxia.app.core

import android.app.Activity
import android.content.ClipData
import android.content.ClipboardManager
import android.content.ComponentName
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.widget.Toast
import androidx.core.content.FileProvider
import java.io.File

/**
 * 分享。
 *
 * 好友分享走系统 ACTION_SEND（微信/QQ/微博自动出现在面板里，不用接 SDK）。
 *
 * 但「朋友圈」必须特殊处理：微信故意不把朋友圈注册进系统分享面板，
 * 只能显式指定 com.tencent.mm.ui.tools.ShareToTimeLineUI 拉起来，
 * 而且朋友圈不接受第三方预填文字，所以把标题渲染成卡片图一起发。
 */
object Share {

    // ---------------- 好友（系统分享面板） ----------------

    fun text(activity: Activity, title: String, url: String, chooserTitle: String = "分享到") {
        val body = if (title.isBlank()) url else "$title\n$url"
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_SUBJECT, title)
            putExtra(Intent.EXTRA_TEXT, body)
        }
        runCatching {
            activity.startActivity(Intent.createChooser(intent, chooserTitle))
        }.onFailure {
            toast(activity, "没有可用的分享应用")
        }
    }

    // ---------------- 朋友圈 ----------------

    /**
     * 分享到朋友圈：渲染卡片图 → 存相册（备用）→ 直接拉起朋友圈发布页。
     * 微信装不上 / 版本不认这个入口时，退化成「存相册 + 打开微信，手动选图」。
     */
    fun moments(
        activity: Activity,
        title: String,
        summary: String,
        source: String,
        url: String
    ) {
        val card = runCatching { ShareCard.render(title, summary, source, url) }.getOrNull()
        if (card == null) {
            text(activity, title, url) // 极端情况直接退回普通分享
            return
        }

        val uri = runCatching { cacheFile(activity, card) }.getOrNull()
        saveToAlbum(activity, card)

        val desc = if (title.isBlank()) url else "$title\n$url"
        if (uri != null && openTimeline(activity, uri, desc)) return

        // 退路：打开微信，提示从相册选图
        openWeChat(activity)
        toast(activity, "卡片已存到相册，进朋友圈后从相册选图即可")
    }

    /** 显式拉起微信「朋友圈」发布页。成功返回 true */
    private fun openTimeline(activity: Activity, uri: Uri, desc: String): Boolean {
        // 微信不同版本入口不一样，挨个试
        val entries = listOf(
            "com.tencent.mm.ui.tools.ShareToTimeLineUI",
            "com.tencent.mm.ui.tools.ShareScreenToTimeLineUI"
        )
        for (cls in entries) {
            val i = Intent(Intent.ACTION_SEND).apply {
                type = "image/*"
                putExtra(Intent.EXTRA_STREAM, uri)
                // 朋友圈的配文由用户在微信里自己写，EXTRA_TEXT 多数版本会被忽略，
                // Kdescription 是部分版本认的字段，一起塞进去不亏
                putExtra(Intent.EXTRA_TEXT, desc)
                putExtra("Kdescription", desc)
                component = ComponentName("com.tencent.mm", cls)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            if (runCatching { activity.startActivity(i) }.isSuccess) return true
        }
        return false
    }

    private fun openWeChat(activity: Activity) {
        val entries = listOf(
            "com.tencent.mm.ui.LauncherUI",
            "com.tencent.mm.ui.tools.ShareToTimeLineUI"
        )
        for (cls in entries) {
            val i = Intent().apply {
                component = ComponentName("com.tencent.mm", cls)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            if (runCatching { activity.startActivity(i) }.isSuccess) return
        }
        runCatching {
            activity.startActivity(
                activity.packageManager.getLaunchIntentForPackage("com.tencent.mm")
            )
        }
    }

    // ---------------- 其他 ----------------

    fun copy(context: Context, label: String, text: String) {
        val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        cm.setPrimaryClip(ClipData.newPlainText(label, text))
        toast(context, "已复制到剪贴板")
    }

    /** 卡片写进 cache，用 FileProvider 变成微信能读的 content:// */
    private fun cacheFile(context: Context, bmp: Bitmap): Uri {
        val dir = File(context.cacheDir, "share")
        if (!dir.exists()) dir.mkdirs()
        // 清掉旧卡片，别把 cache 撑爆
        runCatching {
            dir.listFiles()?.forEach { f ->
                if (System.currentTimeMillis() - f.lastModified() > 24 * 3600 * 1000L) f.delete()
            }
        }
        val file = File(dir, "gtx_${System.currentTimeMillis()}.png")
        file.outputStream().use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
        return FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
    }

    /** 存相册（朋友圈退路用）。Android 10+ 免权限；更老版本没权限就静默失败 */
    private fun saveToAlbum(context: Context, bmp: Bitmap) {
        runCatching {
            val name = "guanxia_${System.currentTimeMillis()}.png"
            val values = ContentValues().apply {
                put(MediaStore.Images.Media.DISPLAY_NAME, name)
                put(MediaStore.Images.Media.MIME_TYPE, "image/png")
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    put(
                        MediaStore.Images.Media.RELATIVE_PATH,
                        Environment.DIRECTORY_PICTURES + "/观天下"
                    )
                    put(MediaStore.Images.Media.IS_PENDING, 1)
                }
            }
            val resolver = context.contentResolver
            val uri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
                ?: return@runCatching
            resolver.openOutputStream(uri)?.use { out ->
                bmp.compress(Bitmap.CompressFormat.PNG, 100, out)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                values.clear()
                values.put(MediaStore.Images.Media.IS_PENDING, 0)
                resolver.update(uri, values, null, null)
            }
        }
    }

    private fun toast(context: Context, msg: String) {
        Toast.makeText(context, msg, Toast.LENGTH_SHORT).show()
    }
}
