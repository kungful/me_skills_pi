package com.wordrush.app.core

import android.app.Activity
import android.view.View
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat

/**
 * targetSdk 35+ 强制 edge-to-edge，内容会画到状态栏/导航栏下面，
 * 必须自己把系统栏高度补成内边距。
 * 国产 ROM 的 systemBars() 有时给 0，所以几个来源一起取最大值。
 */
object Edge {

    fun install(activity: Activity, root: View) {
        val controller = WindowInsetsControllerCompat(activity.window, root)
        controller.isAppearanceLightStatusBars = false
        controller.isAppearanceLightNavigationBars = false

        ViewCompat.setOnApplyWindowInsetsListener(root) { _, insets ->
            val status = insets.getInsets(WindowInsetsCompat.Type.statusBars())
            val nav = insets.getInsets(WindowInsetsCompat.Type.navigationBars())
            val gesture = insets.getInsets(WindowInsetsCompat.Type.mandatorySystemGestures())
            val ime = insets.getInsets(WindowInsetsCompat.Type.ime())
            root.setPadding(
                maxOf(status.left, nav.left, gesture.left),
                maxOf(status.top, nav.top, gesture.top),
                maxOf(status.right, nav.right, gesture.right),
                maxOf(nav.bottom, gesture.bottom, ime.bottom)
            )
            insets
        }
        ViewCompat.requestApplyInsets(root)
    }
}
