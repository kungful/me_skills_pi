package com.vocabtype.app.core

import android.os.Handler
import android.os.Looper
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.net.HttpURLConnection
import java.net.URL

/**
 * 可选：接 DeepSeek 生成短句/长句 + 语法解析。
 * 不填 API Key 时完全走离线句子库，App 一样能用。
 */
object Ai {

    class Result(
        val shortEn: String, val shortZh: String, val shortGram: String,
        val complexEn: String, val complexZh: String, val complexGram: String
    )

    private const val ENDPOINT = "https://api.deepseek.com/chat/completions"
    private val handler = Handler(Looper.getMainLooper())

    @Volatile
    private var inflight = false

    val busy: Boolean get() = inflight

    fun generate(
        key: String,
        system: String,
        template: String,
        word: String,
        trans: String,
        onDone: (Result?) -> Unit
    ) {
        val k = key.trim()
        if (k.isEmpty()) {
            onDone(null)
            return
        }
        inflight = true
        Thread {
            var r: Result? = null
            try {
                r = call(k, system, template, word, trans)
            } catch (_: Exception) {
            } finally {
                inflight = false
            }
            handler.post { onDone(r) }
        }.start()
    }

    private fun call(key: String, system: String, template: String, word: String, trans: String): Result? {
        val prompt = template
            .replace("{word}", word)
            .replace("{trans}", trans.ifBlank { "(无)" })

        val body = JSONObject().apply {
            put("model", "deepseek-chat")
            put("temperature", 0.8)
            put("stream", false)
            put(
                "messages", JSONArray().apply {
                    put(JSONObject().put("role", "system").put("content", system))
                    put(JSONObject().put("role", "user").put("content", prompt))
                }
            )
        }.toString()

        val conn = (URL(ENDPOINT).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 20000
            readTimeout = 45000
            doOutput = true
            setRequestProperty("Content-Type", "application/json; charset=utf-8")
            setRequestProperty("Authorization", "Bearer $key")
        }
        try {
            conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            val code = conn.responseCode
            val text = (if (code in 200..299) conn.inputStream else conn.errorStream)
                ?.bufferedReader()?.use(BufferedReader::readText) ?: return null
            if (code !in 200..299) return null
            val root = JSONObject(text)
            val content = root.optJSONArray("choices")
                ?.optJSONObject(0)
                ?.optJSONObject("message")
                ?.optString("content") ?: return null
            val j = extractJson(content) ?: return null
            return Result(
                j.optString("short_sentence", j.optString("sentence", "")),
                j.optString("short_sentence_translation", j.optString("sentence_translation", "")),
                j.optString("short_sentence_grammar", j.optString("sentence_grammar", "")),
                j.optString("complex_sentence", ""),
                j.optString("complex_sentence_translation", ""),
                j.optString("complex_sentence_grammar", "")
            )
        } finally {
            runCatching { conn.disconnect() }
        }
    }

    /** 模型爱在 JSON 外面裹 ```json ... ```，去掉它 */
    private fun extractJson(s: String): JSONObject? {
        var t = s.trim()
        val i = t.indexOf('{')
        val j = t.lastIndexOf('}')
        if (i < 0 || j <= i) return null
        t = t.substring(i, j + 1)
        return try {
            JSONObject(t)
        } catch (_: Exception) {
            null
        }
    }
}
