package org.opensource.lifealgo.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.State
import androidx.compose.runtime.collectAsState
import kotlinx.coroutines.flow.StateFlow

/** collectAsState 的带初值版本，避免每帧重建空集合。 */
@Composable
fun <T> StateFlow<T>.collectAsStateSafe(): State<T> = collectAsState(initial = value)
