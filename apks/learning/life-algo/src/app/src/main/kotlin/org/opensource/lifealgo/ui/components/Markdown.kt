package org.opensource.lifealgo.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp

/**
 * 极简 Markdown：只支持写作时真正会用到的那几个符号，
 * 避免引第三方解析库，也避免内容作者写出一堆渲染不出来的花活。
 *
 *   **加粗**        `等宽`
 *   - 无序列表       1. 有序
 *   > 引用
 *   ### 小标题
 */
@Composable
fun MarkdownBody(
    text: String,
    modifier: Modifier = Modifier,
    baseColor: Color = MaterialTheme.colorScheme.onSurface,
) {
    val lines = text.trim().lines()
    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(6.dp)) {
        var i = 0
        while (i < lines.size) {
            val raw = lines[i]
            val line = raw.trim()
            when {
                line.isEmpty() -> Spacer(Modifier.padding(top = 2.dp))

                line.startsWith("### ") -> {
                    Text(
                        text = line.removePrefix("### "),
                        style = MaterialTheme.typography.titleSmall,
                        color = MaterialTheme.colorScheme.onSurface,
                        modifier = Modifier.padding(top = 6.dp),
                    )
                }

                line.startsWith("> ") -> {
                    Surface(
                        color = MaterialTheme.colorScheme.surfaceContainer,
                        shape = RoundedCornerShape(10.dp),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Row(Modifier.padding(horizontal = 12.dp, vertical = 9.dp)) {
                            Text(
                                "▎",
                                style = MaterialTheme.typography.bodyLarge,
                                color = MaterialTheme.colorScheme.tertiary,
                            )
                            Spacer(Modifier.width(6.dp))
                            Text(
                                buildInline(line.removePrefix("> "), baseColor),
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }

                line.startsWith("- ") || line.startsWith("* ") -> {
                    Row(Modifier.fillMaxWidth()) {
                        Text(
                            "•",
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.tertiary,
                            modifier = Modifier.width(16.dp),
                        )
                        Text(
                            buildInline(line.drop(2), baseColor),
                            style = MaterialTheme.typography.bodyLarge,
                            color = baseColor,
                        )
                    }
                }

                ORDERED.matches(line) -> {
                    val num = line.substringBefore('.').trim()
                    val rest = line.substringAfter('.').trim()
                    Row(Modifier.fillMaxWidth()) {
                        Text(
                            "$num.",
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = MaterialTheme.colorScheme.tertiary,
                            modifier = Modifier.width(22.dp),
                        )
                        Text(
                            buildInline(rest, baseColor),
                            style = MaterialTheme.typography.bodyLarge,
                            color = baseColor,
                        )
                    }
                }

                else -> Text(
                    buildInline(line, baseColor),
                    style = MaterialTheme.typography.bodyLarge,
                    color = baseColor,
                )
            }
            i++
        }
    }
}

private val ORDERED = Regex("^\\d+\\.\\s.*")

/** 处理 **加粗** 与 `等宽` */
@Composable
fun buildInline(src: String, baseColor: Color): AnnotatedString = buildAnnotatedString {
    var i = 0
    val bold = MaterialTheme.colorScheme.tertiary
    while (i < src.length) {
        when {
            src.startsWith("**", i) -> {
                val end = src.indexOf("**", i + 2)
                if (end < 0) {
                    append(src.substring(i)); break
                }
                withStyle(SpanStyle(fontWeight = FontWeight.Bold)) {
                    append(src.substring(i + 2, end))
                }
                i = end + 2
            }

            src[i] == '`' -> {
                val end = src.indexOf('`', i + 1)
                if (end < 0) {
                    append(src.substring(i)); break
                }
                withStyle(SpanStyle(fontWeight = FontWeight.Medium, color = bold)) {
                    append(src.substring(i + 1, end))
                }
                i = end + 1
            }

            else -> {
                append(src[i]); i++
            }
        }
    }
}
