package org.opensource.lifealgo.ui

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Calculate
import androidx.compose.material.icons.filled.GridView
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Today
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import org.opensource.lifealgo.ui.screens.ArticleScreen
import org.opensource.lifealgo.ui.screens.CategoriesScreen
import org.opensource.lifealgo.ui.screens.CategoryScreen
import org.opensource.lifealgo.ui.screens.ProfileScreen
import org.opensource.lifealgo.ui.screens.ReactionScreen
import org.opensource.lifealgo.ui.screens.SavedScreen
import org.opensource.lifealgo.ui.screens.SearchScreen
import org.opensource.lifealgo.ui.screens.SelfControlScreen
import org.opensource.lifealgo.ui.screens.TodayScreen
import org.opensource.lifealgo.ui.screens.ToolsScreen

private data class Tab(val route: String, val label: String, val icon: ImageVector)

private val TABS = listOf(
    Tab("today", "今日", Icons.Filled.Today),
    Tab("categories", "分类", Icons.Filled.GridView),
    Tab("search", "搜索", Icons.Filled.Search),
    Tab("tools", "工具", Icons.Filled.Calculate),
    Tab("profile", "我的", Icons.Filled.Person),
)

object Routes {
    const val TODAY = "today"
    const val CATEGORIES = "categories"
    const val SEARCH = "search"
    const val TOOLS = "tools"
    const val PROFILE = "profile"
    const val SAVED = "saved"
    const val REACTION = "reaction"
    const val SELFCONTROL = "selfcontrol"
    const val CATEGORY = "category/{categoryId}"
    const val ARTICLE = "article/{articleId}"

    fun category(id: String) = "category/$id"
    fun article(id: String) = "article/$id"
}

@Composable
fun LifeAlgoRoot(vm: AppViewModel) {
    val nav = rememberNavController()
    val snackbar = remember { SnackbarHostState() }
    val message by vm.message.collectAsStateSafe()
    val backStack by nav.currentBackStackEntryAsState()
    val currentRoute = backStack?.destination?.route
    val showBottomBar = currentRoute in TABS.map { it.route }

    LaunchedEffect(message) {
        message?.let {
            snackbar.showSnackbar(it)
            vm.consumeMessage()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbar) },
        bottomBar = {
            if (showBottomBar) {
                NavigationBar {
                    TABS.forEach { tab ->
                        val selected = backStack?.destination?.hierarchy
                            ?.any { it.route == tab.route } == true
                        NavigationBarItem(
                            selected = selected,
                            onClick = { nav.navigateTopLevel(tab.route) },
                            icon = { Icon(tab.icon, contentDescription = tab.label) },
                            label = { Text(tab.label) },
                        )
                    }
                }
            }
        },
    ) { padding ->
        NavHost(
            navController = nav,
            startDestination = Routes.TODAY,
            modifier = Modifier.padding(padding),
        ) {
            composable(Routes.TODAY) {
                TodayScreen(
                    vm = vm,
                    onOpenArticle = { nav.navigate(Routes.article(it)) },
                    onOpenCategory = { nav.navigate(Routes.category(it)) },
                )
            }
            composable(Routes.CATEGORIES) {
                CategoriesScreen(vm = vm, onOpenCategory = { nav.navigate(Routes.category(it)) })
            }
            composable(Routes.SEARCH) {
                SearchScreen(vm = vm, onOpenArticle = { nav.navigate(Routes.article(it)) })
            }
            composable(Routes.TOOLS) {
                ToolsScreen(
                    vm = vm,
                    onOpenReaction = { nav.navigate(Routes.REACTION) },
                    onOpenSelfControl = { nav.navigate(Routes.SELFCONTROL) },
                )
            }
            composable(Routes.PROFILE) {
                ProfileScreen(vm = vm, onOpenSaved = { nav.navigate(Routes.SAVED) })
            }
            composable(Routes.SAVED) {
                SavedScreen(vm = vm, onOpenArticle = { nav.navigate(Routes.article(it)) })
            }
            composable(Routes.REACTION) {
                ReactionScreen(
                    vm = vm,
                    onBack = { nav.popBackStack() },
                    onOpenArticle = { nav.navigate(Routes.article(it)) },
                )
            }
            composable(Routes.SELFCONTROL) {
                SelfControlScreen(
                    vm = vm,
                    onBack = { nav.popBackStack() },
                    onOpenArticle = { nav.navigate(Routes.article(it)) },
                )
            }
            composable(Routes.CATEGORY) { entry ->
                CategoryScreen(
                    vm = vm,
                    categoryId = entry.arguments?.getString("categoryId").orEmpty(),
                    onBack = { nav.popBackStack() },
                    onOpenArticle = { nav.navigate(Routes.article(it)) },
                    onOpenReaction = { nav.navigate(Routes.REACTION) },
                    onOpenSelfControl = { nav.navigate(Routes.SELFCONTROL) },
                )
            }
            composable(Routes.ARTICLE) { entry ->
                ArticleScreen(
                    vm = vm,
                    articleId = entry.arguments?.getString("articleId").orEmpty(),
                    onBack = { nav.popBackStack() },
                    onOpenArticle = { nav.navigate(Routes.article(it)) },
                )
            }
        }
    }
}

private fun NavHostController.navigateTopLevel(route: String) {
    navigate(route) {
        popUpTo(graph.findStartDestination().id) { saveState = true }
        launchSingleTop = true
        restoreState = true
    }
}
