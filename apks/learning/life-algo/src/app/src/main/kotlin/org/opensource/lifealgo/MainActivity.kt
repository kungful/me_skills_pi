package org.opensource.lifealgo

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import org.opensource.lifealgo.ui.AppViewModel
import org.opensource.lifealgo.ui.LifeAlgoRoot
import org.opensource.lifealgo.ui.theme.LifeAlgoTheme

class MainActivity : ComponentActivity() {

    private val requestNotification =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val vm: AppViewModel = viewModel()
            val revision by vm.revision.collectAsStateWithLifecycle()
            val theme = remember(revision) { vm.themeMode }
            val font = remember(revision) { vm.fontScale }

            LifeAlgoTheme(themeMode = theme, fontScale = font) {
                Surface(color = MaterialTheme.colorScheme.background) {
                    LifeAlgoRoot(vm = vm)
                }
            }
        }
        maybeAskNotificationPermission()
    }

    override fun onResume() {
        super.onResume()
        // 跨天时刷新"今日"内容
        runCatching { (application as LifeAlgoApp) }
    }

    /** Android 13+ 通知需要运行时授权；不授权也不影响阅读，只是收不到每日提醒。 */
    private fun maybeAskNotificationPermission() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        val granted = ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.POST_NOTIFICATIONS,
        ) == PackageManager.PERMISSION_GRANTED
        if (!granted) {
            runCatching { requestNotification.launch(Manifest.permission.POST_NOTIFICATIONS) }
        }
    }
}
