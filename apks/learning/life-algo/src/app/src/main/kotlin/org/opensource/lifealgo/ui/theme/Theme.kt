package org.opensource.lifealgo.ui.theme

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat

/* 配色：深墨蓝（理性/工具感）+ 琥珀（行动/提醒） */
private val Indigo = Color(0xFF1E3A5F)
private val IndigoLight = Color(0xFF9DC0E8)
private val Amber = Color(0xFFC08029)
private val AmberLight = Color(0xFFE8B65C)
private val PaperLight = Color(0xFFF6F6F3)
private val InkLight = Color(0xFF15171A)
private val PaperDark = Color(0xFF0F1114)
private val InkDark = Color(0xFFE7E8E6)

private val LightColors = lightColorScheme(
    primary = Indigo,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFDCE6F3),
    onPrimaryContainer = Color(0xFF0E2439),
    secondary = Color(0xFF4A6B57),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFDCEAE0),
    onSecondaryContainer = Color(0xFF1B3226),
    tertiary = Amber,
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFF7E3C4),
    onTertiaryContainer = Color(0xFF46300E),
    background = PaperLight,
    onBackground = InkLight,
    surface = Color(0xFFFCFCFA),
    onSurface = InkLight,
    surfaceVariant = Color(0xFFE9E9E3),
    onSurfaceVariant = Color(0xFF45474A),
    surfaceContainerLow = Color(0xFFF1F1EC),
    surfaceContainer = Color(0xFFEBEBE6),
    outline = Color(0xFFB4B6B2),
    outlineVariant = Color(0xFFD8D8D2),
    error = Color(0xFFB3261E),
)

private val DarkColors = darkColorScheme(
    primary = IndigoLight,
    onPrimary = Color(0xFF0B1F33),
    primaryContainer = Color(0xFF2A4A73),
    onPrimaryContainer = Color(0xFFD6E4F7),
    secondary = Color(0xFFA6CDB4),
    onSecondary = Color(0xFF10281B),
    secondaryContainer = Color(0xFF2C4A38),
    onSecondaryContainer = Color(0xFFD3EBDC),
    tertiary = AmberLight,
    onTertiary = Color(0xFF3A2405),
    tertiaryContainer = Color(0xFF5A4120),
    onTertiaryContainer = Color(0xFFF8E4C6),
    background = PaperDark,
    onBackground = InkDark,
    surface = Color(0xFF16181C),
    onSurface = InkDark,
    surfaceVariant = Color(0xFF26282D),
    onSurfaceVariant = Color(0xFFC6C8C5),
    surfaceContainerLow = Color(0xFF1B1D21),
    surfaceContainer = Color(0xFF202328),
    outline = Color(0xFF6A6D71),
    outlineVariant = Color(0xFF35383D),
    error = Color(0xFFF2B8B5),
)

private val AppTypography = Typography(
    displaySmall = TextStyle(fontSize = 30.sp, fontWeight = FontWeight.Bold, lineHeight = 38.sp),
    headlineMedium = TextStyle(fontSize = 25.sp, fontWeight = FontWeight.SemiBold, lineHeight = 33.sp),
    headlineSmall = TextStyle(fontSize = 21.sp, fontWeight = FontWeight.SemiBold, lineHeight = 29.sp),
    titleLarge = TextStyle(fontSize = 18.sp, fontWeight = FontWeight.SemiBold, lineHeight = 26.sp),
    titleMedium = TextStyle(fontSize = 16.sp, fontWeight = FontWeight.Medium, lineHeight = 24.sp),
    titleSmall = TextStyle(fontSize = 14.sp, fontWeight = FontWeight.Medium, lineHeight = 20.sp),
    bodyLarge = TextStyle(fontSize = 15.5.sp, lineHeight = 26.sp),
    bodyMedium = TextStyle(fontSize = 14.sp, lineHeight = 23.sp),
    bodySmall = TextStyle(fontSize = 12.5.sp, lineHeight = 19.sp),
    labelLarge = TextStyle(fontSize = 13.sp, fontWeight = FontWeight.Medium),
    labelMedium = TextStyle(fontSize = 11.5.sp, fontWeight = FontWeight.Medium),
    labelSmall = TextStyle(fontSize = 11.sp, fontWeight = FontWeight.Medium),
)

@Composable
fun LifeAlgoTheme(
    themeMode: String = "system",
    fontScale: Float = 1f,
    content: @Composable () -> Unit,
) {
    val dark = when (themeMode) {
        "dark" -> true
        "light" -> false
        else -> isSystemInDarkTheme()
    }
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as? Activity)?.window ?: return@SideEffect
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !dark
        }
    }
    MaterialTheme(
        colorScheme = if (dark) DarkColors else LightColors,
        typography = scaleTypography(AppTypography, fontScale),
        content = content,
    )
}

private fun scaleTypography(base: Typography, scale: Float): Typography {
    if (scale == 1f) return base
    fun TextStyle.s() = copy(fontSize = fontSize * scale, lineHeight = lineHeight * scale)
    return Typography(
        displaySmall = base.displaySmall.s(),
        headlineMedium = base.headlineMedium.s(),
        headlineSmall = base.headlineSmall.s(),
        titleLarge = base.titleLarge.s(),
        titleMedium = base.titleMedium.s(),
        titleSmall = base.titleSmall.s(),
        bodyLarge = base.bodyLarge.s(),
        bodyMedium = base.bodyMedium.s(),
        bodySmall = base.bodySmall.s(),
        labelLarge = base.labelLarge.s(),
        labelMedium = base.labelMedium.s(),
        labelSmall = base.labelSmall.s(),
    )
}

/** 把 "#3B6FE0" 解析成 Color；解析失败给个中性色。 */
fun parseAccent(hex: String, fallback: Color = Indigo): Color = runCatching {
    val h = hex.removePrefix("#")
    val v = h.toLong(16)
    when (h.length) {
        6 -> Color(0xFF000000 or v)
        8 -> Color(v)
        else -> fallback
    }
}.getOrDefault(fallback)
