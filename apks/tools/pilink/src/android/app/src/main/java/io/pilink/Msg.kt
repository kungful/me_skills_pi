package io.pilink

import org.json.JSONArray
import org.json.JSONObject

/** 通知里的一个动作按钮（只看 view：交给浏览器打开） */
data class MsgAction(val label: String, val url: String)

/** 一条通知。字段名沿用最早的线上格式，所以解析/历史/通知这几层没被换协议影响过。 */
data class Msg(
    val id: String,
    val time: Long,
    val title: String,
    val body: String,
    val priority: Int,
    val click: String?,
    val actions: List<MsgAction>,
    val group: String?,
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("id", id)
        // 【必须存秒】fromJson 会把 time 当成“秒”再乘 1000。
        // 之前这里存的是毫秒，于是历史每读一次就被乘一次 1000 ——
        // 屏幕上就会出现 04-23、07-09 这种乱日期（今日的消息显示成别的日子）。
        put("time", time / 1000L)
        put("title", title)
        put("body", body)
        put("priority", priority)
        put("click", click ?: JSONObject.NULL)
        put("group", group ?: JSONObject.NULL)
        put("actions", JSONArray().apply {
            actions.forEach {
                put(JSONObject().apply { put("label", it.label); put("url", it.url) })
            }
        })
    }

    companion object {
        fun fromJson(o: JSONObject): Msg? {
            val id = o.optString("id", "")
            if (id.isEmpty()) return null

            val actions = ArrayList<MsgAction>()
            o.optJSONArray("actions")?.let { arr ->
                for (i in 0 until arr.length()) {
                    val a = arr.optJSONObject(i) ?: continue
                    val url = a.optString("url", "")
                    if (url.isEmpty()) continue
                    actions.add(MsgAction(a.optString("label", "打开"), url))
                }
            }

            return Msg(
                id = id,
                // 服务端的 time 是秒，fromJson 统一乘 1000 转成毫秒；
                // 所以 toJson 存回去时也必须存秒（否则每读一次历史就放大 1000 倍）
                time = o.optLong("time", 0L) * 1000L,
                title = o.optString("title", "Pi"),
                body = o.optString("message", ""),
                priority = o.optInt("priority", 3),
                click = o.optString("click", "").ifEmpty { null },
                actions = actions,
                group = o.optString("group", "").ifEmpty { null },
            )
        }
    }
}

/**
 * 推送流（NDJSON）上会来三种行：
 *   event=open / keepalive  → 链路活着的信号（也算"收到帧"，但不当消息）
 *   event=message           → 真消息
 * 任何一帧都要刷新"最近收到帧"的时间戳，判活用。
 */
object Frames {
    fun parse(json: String): Msg? = try {
        Msg.fromJson(JSONObject(json))
    } catch (e: Exception) {
        null
    }
}
