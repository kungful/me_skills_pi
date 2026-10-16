package com.guantianxia.app.core

import android.app.Activity
import android.content.res.Configuration
import android.view.View
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat

/**
 * targetSdk 35+ 起系统强制 edge-to-edge，内容会画到状态栏/导航栏底下，
 * 必须自己把系统栏尺寸补成内边距，否则内容会被挡住。
 *
 * 注意：部分国产 ROM（实测 vivo 双键导航）systemBars() 给的底部 inset 是 0，
 * 所以这里把 navigationBars / mandatorySystemGestures / ime 一起取最大值。
 */
object EdgeToEdge {

    data class Bars(val l: Int, val t: Int, val r: Int, val b: Int)

    private fun compute(insets: WindowInsetsCompat): Bars {
        val status = insets.getInsets(WindowInsetsCompat.Type.statusBars())
        val nav = insets.getInsets(WindowInsetsCompat.Type.navigationBars())
        val gesture = insets.getInsets(WindowInsetsCompat.Type.mandatorySystemGestures())
        val ime = insets.getInsets(WindowInsetsCompat.Type.ime())
        return Bars(
            l = maxOf(status.left, nav.left, gesture.left),
            t = maxOf(status.top, nav.top, gesture.top),
            r = maxOf(status.right, nav.right, gesture.right),
            b = maxOf(nav.bottom, gesture.bottom, ime.bottom)
        )
    }

    /**
     * @param lightStatusIcons true = 状态栏用深色图标（浅色背景时用）；
     *                         null = 跟随系统深浅色
     * @param sink 拿到最终内边距，自行决定加到哪个 View 上
     */
    fun install(
        activity: Activity,
        root: View,
        lightStatusIcons: Boolean? = null,
        sink: (Bars) -> Unit
    ) {
        val night = (activity.resources.configuration.uiMode and
            Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES

        val controller = WindowInsetsControllerCompat(activity.window, root)
        controller.isAppearanceLightStatusBars = lightStatusIcons ?: !night
        controller.isAppearanceLightNavigationBars = !night

        ViewCompat.setOnApplyWindowInsetsListener(root) { _, insets ->
            sink(compute(insets))
            insets
        }
        ViewCompat.requestApplyInsets(root)
    }
}
