package com.vocabtype.app.fx

import android.content.Context
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator

object Vib {

    var enabled = true

    private var vib: Vibrator? = null

    fun bind(ctx: Context) {
        if (vib == null) {
            vib = ctx.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
        }
    }

    fun tick() = run(12)
    fun ok() = run(28)
    fun bad() = run(60)

    private fun run(ms: Long) {
        if (!enabled) return
        val v = vib ?: return
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                v.vibrate(VibrationEffect.createOneShot(ms, VibrationEffect.DEFAULT_AMPLITUDE))
            } else {
                @Suppress("DEPRECATION")
                v.vibrate(ms)
            }
        } catch (_: Exception) {
        }
    }
}
