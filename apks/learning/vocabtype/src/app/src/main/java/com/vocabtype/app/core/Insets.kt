package com.vocabtype.app.core

import android.app.Activity
import android.view.View
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat

/**
 * targetSdk 35+ 之后系统强制 edge-to-edge：窗口一直铺到状态栏/导航栏下面，
 * 顶栏不管 insets 就会被状态栏盖住 —— 不只是难看，是**点不到**
 * （触摸事件先被 SystemUI 的状态栏窗口吃掉）。
 *
 * 所以每个 Activity 显式关掉 decorFitsSystemWindows，再把 insets 转成 padding。
 */
object Insets {

    /**
     * @param target 接 padding 的视图（主界面传 content，好让代码雨铺满全屏）
     * @param ime    软键盘也顶起布局（打字页要）
     * @param top    是否避让状态栏
     * @param bottom 是否避让导航栏
     */
    fun apply(
        activity: Activity,
        target: View,
        ime: Boolean = false,
        top: Boolean = true,
        bottom: Boolean = true
    ) {
        WindowCompat.setDecorFitsSystemWindows(activity.window, false)

        val l = target.paddingLeft
        val t = target.paddingTop
        val r = target.paddingRight
        val b = target.paddingBottom

        ViewCompat.setOnApplyWindowInsetsListener(target) { v, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            val kb = if (ime) insets.getInsets(WindowInsetsCompat.Type.ime()).bottom else 0
            v.setPadding(
                l,
                t + if (top) bars.top else 0,
                r,
                b + if (bottom) maxOf(bars.bottom, kb) else 0
            )
            insets
        }
        ViewCompat.requestApplyInsets(target)
    }
}
