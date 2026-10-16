package com.guantianxia.app.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.View
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.google.android.material.bottomnavigation.BottomNavigationView
import com.guantianxia.app.R
import com.guantianxia.app.core.EdgeToEdge
import com.guantianxia.app.core.Prefs
import com.guantianxia.app.ui.books.BooksFragment
import com.guantianxia.app.ui.finance.FinanceFragment
import com.guantianxia.app.ui.news.NewsFragment

class MainActivity : AppCompatActivity() {

    private val tags = arrayOf("news", "finance", "books")

    /** 首次启动申请一次通知权限（Android 13+） */
    private val askNotify =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            prefs.askedNotify = true
            if (!granted) prefs.notifyEnabled = false
        }

    private val prefs by lazy { Prefs(this) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // targetSdk 35+ 系统强制 edge-to-edge，必须自己补系统栏内边距
        val root = findViewById<View>(R.id.root)
        EdgeToEdge.install(this, root) { b -> root.setPadding(b.l, b.t, b.r, b.b) }

        maybeAskNotificationPermission()

        val nav = findViewById<BottomNavigationView>(R.id.bottom_nav)
        nav.setOnItemSelectedListener { item ->
            val index = when (item.itemId) {
                R.id.nav_finance -> 1
                R.id.nav_books -> 2
                else -> 0
            }
            show(index)
            true
        }
        if (savedInstanceState == null) {
            nav.selectedItemId = R.id.nav_news
        }
    }

    private fun maybeAskNotificationPermission() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        if (prefs.askedNotify) return
        if (!prefs.notifyEnabled) return
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
            == PackageManager.PERMISSION_GRANTED
        ) return
        askNotify.launch(Manifest.permission.POST_NOTIFICATIONS)
    }

    /** 手动切 Fragment（不用 Navigation 组件，少依赖、可控） */
    private fun show(index: Int) {
        val fm = supportFragmentManager
        val tx = fm.beginTransaction()
        fm.fragments.toList().forEach { tx.hide(it) }

        val tag = tags[index]
        val existing = fm.findFragmentByTag(tag)
        if (existing == null) {
            val f = when (index) {
                1 -> FinanceFragment()
                2 -> BooksFragment()
                else -> NewsFragment()
            }
            tx.add(R.id.container, f, tag)
        } else {
            tx.show(existing)
        }
        tx.commit()
    }
}
