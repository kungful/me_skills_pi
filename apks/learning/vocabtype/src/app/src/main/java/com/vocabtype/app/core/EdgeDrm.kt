package com.vocabtype.app.core

/**
 * 微软 Edge「大声朗读」在线神经语音的 DRM 签名。
 *
 * 服务端要求 URL 带 Sec-MS-GEC，格式 "<16 hex>-<64 hex>"：
 *   - 时间片 = (unix + 11644473600) 向下取整到 300 秒，再 x 1e7
 *   - 明文   = 时间片 + TrustedClientToken
 *   - 它是变体 SHA256（自定义 initial state / schedule）加 CS64 摘要，
 *     不等于标准 SHA256，必须照原样实现，否则服务端回 403。
 *
 * 算法移植自开源项目 rany2/edge-tts（MIT）。32 位无符号运算用 Int + Long 模拟。
 */
object EdgeDrm {

    const val TRUSTED_CLIENT_TOKEN = "6A5AA1D4EAFF4E9FB37E23D68491D6F4"
    const val SEC_MS_GEC_VERSION = "2-143.0.3650.75"
    const val WSS_URL =
        "wss://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1" +
                "?TrustedClientToken=" + TRUSTED_CLIENT_TOKEN

    private const val WIN_EPOCH = 11644473600L

    private const val SIGMA1_ADJ = 0x000B92C0
    private const val SIGMA0_ADJ = 0x059C0B80
    private const val SHA256_ADJ = 0xC9DC06A7.toInt()
    private const val CS64_FACTOR = 0x82893933.toInt()
    private const val CS64_O0 = 0xEF0569FB.toInt()
    private const val CS64_O1 = 0xC31713DB.toInt()
    private const val CS64_A0 = 0xF2F90B1A.toInt()
    private const val CS64_A1 = 0x0B1A0000
    private const val CS64_M0 = 0x76F50F34.toInt()
    private const val CS64_M1 = 0xC3EFEA97.toInt()
    private const val CS64_M2 = 0x87B9A9A1.toInt()
    private const val CS64_M3 = 0x1B2C3D4E
    private const val CS64_M5 = 0x1881CE3C
    private const val CS64_M6 = 0x35BD1EC9
    private const val CS64_M7 = 0xCF98B111.toInt()
    private const val CS64_M8 = 0x87085B9F.toInt()
    private const val CS64_M9 = 0x12CEB96D
    private const val CS64_M10 = 0x257E1D83
    private const val CS64_M11 = 0xA27416F5.toInt()
    private const val CS64_M12 = 0xD38396FF.toInt()
    private const val CS64_M13 = 0x7C932B89
    private const val CS64_M14 = 0xBFA49F69.toInt()

    private fun u(x: Int): Long = x.toLong() and 0xFFFFFFFFL
    private fun m(x: Long): Int = (x and 0xFFFFFFFFL).toInt()

    private fun rol16(v: Int): Int {
        val x = u(v)
        return m((x shl 16) or (x ushr 16))
    }

    private fun sigma0(v: Int): Int {
        val x = u(v)
        return m((x ushr 7) xor (x shl 25) xor (x ushr 18) xor (x shl 14) xor (x ushr 3))
    }

    private fun sigma1(v: Int): Int {
        val x = u(v)
        return m((x ushr 17) xor (x shl 15) xor (x ushr 19) xor (x shl 13) xor (x ushr 10))
    }

    private val SHA256_INITIAL = intArrayOf(
            0x6A09E667.toInt(), 0xBB67AE85.toInt(), 0x3C6EF372.toInt(), 0xA54FF53A.toInt(), 0x510E527F.toInt(), 0x9B05688C.toInt(), 0x1F83D9AB.toInt(), 0x5BE0CD19.toInt()
    )

    private val SHA256_SCHEDULE = intArrayOf(
            0xEB24BF9E.toInt(), 0x1558691F.toInt(), 0xA0C09EE2.toInt(), 0x0CFA32BA.toInt(), 0xA622EE8C.toInt(), 0xD1DD9491.toInt(), 0xC0DD25A0.toInt(), 0xF9E70AB6.toInt(),
            0xF0C31573.toInt(), 0x7058CE4E.toInt(), 0x7188E606.toInt(), 0x00E5AB33.toInt(), 0xD258B060.toInt(), 0x72766564.toInt()
    )

    private val SHA256_STATE = intArrayOf(
            0xFD9FBEA2.toInt(), 0x91243CE7.toInt(), 0xBE499094.toInt(), 0xCD2E1E0A.toInt(), 0x6C006F49.toInt(), 0x04BD35AB.toInt(), 0xFEB0A7E4.toInt(), 0x03EFFBD2.toInt()
    )

    private val ROUND = intArrayOf(
            0x428A2F98.toInt(), 0x71374491.toInt(), 0xB5C0FBCF.toInt(), 0xE9B5DBA5.toInt(), 0x3956C25B.toInt(), 0x59F111F1.toInt(), 0x923F82A4.toInt(), 0xAB1C5ED5.toInt(),
            0xD807AA98.toInt(), 0x12835B01.toInt(), 0x243185BE.toInt(), 0x550C7DC3.toInt(), 0x72BE5D74.toInt(), 0x80DEB1FE.toInt(), 0x9BDC06A7.toInt(), 0xC19BF174.toInt(),
            0xE49B69C1.toInt(), 0xEFBE4786.toInt(), 0x0FC19DC6.toInt(), 0x240CA1CC.toInt(), 0x2DE92C6F.toInt(), 0x4A7484AA.toInt(), 0x5CB0A9DC.toInt(), 0x76F988DA.toInt(),
            0x983E5152.toInt(), 0xA831C66D.toInt(), 0xB00327C8.toInt(), 0xBF597FC7.toInt(), 0xC6E00BF3.toInt(), 0xD5A79147.toInt(), 0x06CA6351.toInt(), 0x14292967.toInt(),
            0x27B70A85.toInt(), 0x2E1B2138.toInt(), 0x4D2C6DFC.toInt(), 0x53380D13.toInt(), 0x650A7354.toInt(), 0x766A0ABB.toInt(), 0x81C2C92E.toInt(), 0x92722C85.toInt(),
            0xA2BFE8A1.toInt(), 0xA81A664B.toInt(), 0xC24B8B70.toInt(), 0xC76C51A3.toInt(), 0xD192E819.toInt(), 0xD6990624.toInt(), 0xF40E3585.toInt(), 0x106AA070.toInt(),
            0x19A4C116.toInt(), 0x1E376C08.toInt(), 0x2748774C.toInt(), 0x34B0BCB5.toInt(), 0x391C0CB3.toInt(), 0x4ED8AA4A.toInt(), 0x5B9CCA4F.toInt(), 0x682E6FF3.toInt(),
            0x748F82EE.toInt(), 0x78A5636F.toInt(), 0x84C87814.toInt(), 0x8CC70208.toInt(), 0x90BEFFFA.toInt(), 0xA4506CEB.toInt(), 0xBEF9A3F7.toInt(), 0xC67178F2.toInt()
    )

    private val BLOCK = intArrayOf(
            0x428A2F98.toInt(), 0x71374491.toInt(), 0xB5C0FBCF.toInt(), 0xE9B5DBA5.toInt(), 0x3956C25B.toInt(), 0x59F111F1.toInt(), 0x923F82A4.toInt(), 0xAB1C5ED5.toInt(),
            0xD807AA98.toInt(), 0x12835B01.toInt(), 0x243185BE.toInt(), 0x550C7DC3.toInt(), 0x72BE5D74.toInt(), 0x80DEB1FE.toInt(), 0xC9DC06A7.toInt(), 0xC19BF174.toInt(),
            0xE49B69C1.toInt(), 0xEFBE4786.toInt(), 0x0FC19DC6.toInt(), 0x240CA1CC.toInt(), 0x2DE92C6F.toInt(), 0x4A7484AA.toInt(), 0x5CB0A9DC.toInt(), 0x76F988DA.toInt(),
            0x983E5152.toInt(), 0xA831C66D.toInt(), 0xB00327C8.toInt(), 0xBF597FC7.toInt(), 0xC6E00BF3.toInt(), 0xD5A79147.toInt(), 0x06CA6351.toInt(), 0x14292967.toInt(),
            0x27B70A85.toInt(), 0x2E1B2138.toInt(), 0x4D2C6DFC.toInt(), 0x53380D13.toInt(), 0x650A7354.toInt(), 0x766A0ABB.toInt(), 0x81C2C92E.toInt(), 0x92722C85.toInt(),
            0xA2BFE8A1.toInt(), 0xA81A664B.toInt(), 0xC24B8B70.toInt(), 0xC76C51A3.toInt(), 0xD192E819.toInt(), 0xD6990624.toInt(), 0xF40E3585.toInt(), 0x106AA070.toInt(),
            0x19A4C116.toInt(), 0x1E376C08.toInt(), 0x2748774C.toInt(), 0x34B0BCB5.toInt(), 0x391C0CB3.toInt(), 0x4ED8AA4A.toInt(), 0x5B9CCA4F.toInt(), 0x682E6FF3.toInt(),
            0x748F82EE.toInt(), 0x78A5636F.toInt(), 0x84C87814.toInt(), 0x8CC70208.toInt(), 0x90BEFFFA.toInt(), 0xA4506CEB.toInt(), 0xBEF9A3F7.toInt(), 0xC67178F2.toInt()
    )

    private val CS64_COEF = arrayOf(
        intArrayOf(0xE82E91B1.toInt(), 0xB32700D0.toInt()),
        intArrayOf(0x44DE24C6.toInt(), 0x88DFF51D.toInt()),
        intArrayOf(0x3BEB65BC.toInt(), 0x29514038.toInt()),
        intArrayOf(0xC89C5933.toInt(), 0xB328CBDF.toInt()),
        intArrayOf(0x8D1EC211.toInt(), 0xD405B4D5.toInt()),
        intArrayOf(0x314EF5D5.toInt(), 0x26E55F3C.toInt()),
        intArrayOf(0xE92491B1.toInt(), 0x607801C6.toInt()),
        intArrayOf(0xF0A5B9D5.toInt(), 0x82B2C1FB.toInt()),
        intArrayOf(0x06064CF3.toInt(), 0xFA51A3DA.toInt()),
        intArrayOf(0xDA79FA60.toInt(), 0x207CC464.toInt()),
        intArrayOf(0xBED20560.toInt(), 0x3C3C74F3.toInt()),
        intArrayOf(0x89F9C9F8.toInt(), 0xD2D14B61.toInt()),
        intArrayOf(0x35FA38C6.toInt(), 0xBB04A2C1.toInt()),
        intArrayOf(0xCB49E3C6.toInt(), 0xC5626167.toInt())
    )

    private fun wordsLe4Even(data: ByteArray): IntArray {
        val n = (data.size + 3) / 4
        val out = ArrayList<Int>(n + 1)
        for (i in 0 until n) {
            var v = 0L
            for (b in 0 until 4) {
                val k = i * 4 + b
                if (k < data.size) v = v or ((data[k].toLong() and 0xFF) shl (b * 8))
            }
            out.add(m(v))
        }
        if (out.size % 2 == 1) out.add(0)
        return out.toIntArray()
    }

    private fun expand(words: IntArray, from: Int) {
        for (i in from until 64) {
            val x = u(words[i - 2])
            val y = u(words[i - 15])
            val s1 = (x ushr 17) xor (x shl 15) xor (x ushr 19) xor (x shl 13) xor (x ushr 10)
            val s0 = (y ushr 7) xor (y shl 25) xor (y ushr 18) xor (y shl 14) xor (y ushr 3)
            words[i] = m(s1 + u(words[i - 7]) + s0 + u(words[i - 16]))
        }
    }

    private fun sha256Init(data: ByteArray): IntArray {
        val w = IntArray(64)
        w[14] = ((data[0].toInt() and 0xFF) shl 16) or
                ((data[1].toInt() and 0xFF) shl 8) or
                (data[2].toInt() and 0xFF)
        w[15] = ((data[3].toInt() and 0xFF) shl 24) or
                ((data[4].toInt() and 0xFF) shl 16) or
                ((data[5].toInt() and 0xFF) shl 8) or
                (data[6].toInt() and 0xFF)
        for (i in 16 until 30) {
            var v = u(SHA256_SCHEDULE[i - 16])
            if (i - 2 >= 14) {
                v += if (i == 16) u(sigma1(w[i - 2]) xor SIGMA1_ADJ) else u(sigma1(w[i - 2]))
            }
            if (i - 7 >= 14) v += u(w[i - 7])
            if (i - 15 >= 14) {
                v += if (i == 29) u(sigma0(w[i - 15]) xor SIGMA0_ADJ) else u(sigma0(w[i - 15]))
            }
            w[i] = m(v)
        }
        w[30] = m(u(sigma1(w[28])) + u(w[23]) + u(sigma0(w[15])) + u(w[14]) +
                u(SHA256_ADJ) - u(ROUND[14]))
        expand(w, 31)
        val work = rounds(SHA256_STATE, w, 14)
        val out = IntArray(8)
        for (i in 0 until 8) out[i] = m(u(SHA256_INITIAL[i]) + u(work[i]))
        return out
    }

    private fun sha256Digest(data: ByteArray): ByteArray {
        val length = 57 + data.size
        // Kotlin 的 % 对负数返回负数，这里要 Python 那种非负取模
        val padLen = ((55 - length) % 64 + 64) % 64
        val rest = ByteArray(data.size - 7 + 1 + padLen + 8)
        System.arraycopy(data, 7, rest, 0, data.size - 7)
        var n = data.size - 7
        rest[n++] = 0x80.toByte()
        for (i in 0 until padLen) rest[n++] = 0
        val bits = length.toLong() * 8
        for (i in 7 downTo 0) rest[n++] = ((bits ushr (i * 8)) and 0xFF).toByte()

        var state = sha256Init(data)
        var off = 0
        while (off < rest.size) {
            val words = IntArray(64)
            for (i in 0 until 16) {
                val o = off + i * 4
                words[i] = ((rest[o].toInt() and 0xFF) shl 24) or
                        ((rest[o + 1].toInt() and 0xFF) shl 16) or
                        ((rest[o + 2].toInt() and 0xFF) shl 8) or
                        (rest[o + 3].toInt() and 0xFF)
            }
            expand(words, 16)
            val work = rounds(state, words, 0)
            for (i in 0 until 8) state[i] = m(u(state[i]) + u(work[i]))
            off += 64
        }
        val out = ByteArray(32)
        for (i in 0 until 8) {
            out[i * 4] = ((state[i] ushr 24) and 0xFF).toByte()
            out[i * 4 + 1] = ((state[i] ushr 16) and 0xFF).toByte()
            out[i * 4 + 2] = ((state[i] ushr 8) and 0xFF).toByte()
            out[i * 4 + 3] = (state[i] and 0xFF).toByte()
        }
        return out
    }

    private fun rounds(state: IntArray, words: IntArray, first: Int): IntArray {
        var a = state[0]
        var b = state[1]
        var c = state[2]
        var d = state[3]
        var e = state[4]
        var f = state[5]
        var g = state[6]
        var h = state[7]
        val k = if (first == 14) BLOCK else ROUND
        var i = first
        while (i < 64) {
            val rotE = u(e) * 0x100000001L
            val rotA = u(a) * 0x100000001L
            val t1 = u(h) + ((rotE ushr 6) xor (rotE ushr 11) xor (rotE ushr 25)) +
                    u(g xor (e and (f xor g))) + u(k[i]) + u(words[i])
            val t2 = ((rotA ushr 2) xor (rotA ushr 13) xor (rotA ushr 22)) +
                    u((a and b) or (c and (a or b)))
            val na = m(t1 + t2)
            val ne = m(u(d) + t1)
            d = c
            c = b
            b = a
            a = na
            h = g
            g = f
            f = e
            e = ne
            i++
        }
        return intArrayOf(a, b, c, d, e, f, g, h)
    }

    private fun cs64(data: ByteArray, digest: ByteArray): IntArray {
        var kA = (digest[0].toInt() and 0xFF) or
                ((digest[1].toInt() and 0xFF) shl 8) or
                ((digest[2].toInt() and 0xFF) shl 16) or
                ((digest[3].toInt() and 0xFF) shl 24)
        var kB = (digest[4].toInt() and 0xFF) or
                ((digest[5].toInt() and 0xFF) shl 8) or
                ((digest[6].toInt() and 0xFF) shl 16) or
                ((digest[7].toInt() and 0xFF) shl 24)
        kA = kA or 1
        kB = kB or 1
        val factors = longArrayOf(u(m(u(kA) * u(CS64_FACTOR))), u(m(u(kB) * u(CS64_FACTOR))))

        val terms = ArrayList<Long>(96)
        val offs = ArrayList<Long>(96)
        for (idx in CS64_COEF.indices) {
            val c = CS64_COEF[idx]
            terms.add(u(m(u(c[0]) * factors[idx % 2])))
            offs.add(u(c[1]))
        }
        val withNul = ByteArray(data.size + 1)
        System.arraycopy(data, 0, withNul, 1, data.size)
        val ws = wordsLe4Even(withNul)
        for (idx in ws.indices) {
            val word = ws[idx]
            var t = u(word) * (if (idx % 2 == 0) u(kA) else u(kB))
            var o = u(rol16(word)) * (if (idx % 2 == 0) u(CS64_O0) else u(CS64_O1))
            if (idx == 0) {
                t += u(CS64_A0) * factors[0]
                o += u(CS64_A1)
            }
            terms.add(u(m(t)))
            offs.add(u(m(o)))
        }

        var swapAcc = 0L
        var swapLast = 0L
        var state = 0L
        var acc = 0L
        var i = 0
        while (i < terms.size) {
            val x = terms[i]
            val y = terms[i + 1]

            var t = u(rol16(m(offs[i] + x)))
            var q = u(m(t.toLong() * u(CS64_M0)))
            swapAcc = u(m(swapAcc + u(m(u(rol16(m(q))) * u(CS64_M1) + q))))

            t = u(rol16(m(offs[i + 1] + y)))
            q = u(m(t.toLong() * u(CS64_M5)))
            swapLast = u(m(u(rol16(m(q))) * u(CS64_M6) + q))
            swapAcc = u(m(swapAcc + swapLast))

            state = u(m(state * u(kA) + x))
            state = u(m(u(rol16(m(state))) * u(CS64_M7)))
            state = u(m(u(rol16(m(state))) * u(CS64_M8)))
            state = u(m(u(rol16(m(state))) * u(CS64_M9)))
            state = u(m(u(rol16(m(state))) * u(CS64_M10)))
            acc = u(m(acc + state))

            t = u(m(state * u(kB) + y))
            t = u(m(u(rol16(m(t))) * u(CS64_M11)))
            t = u(m(u(rol16(m(t))) * u(CS64_M12)))
            state = u(m(u(rol16(m(u(m(u(rol16(m(t))) * u(CS64_M13)))))) * u(CS64_M14)))
            acc = u(m(acc + state))
            i += 2
        }
        val oa = u(m(swapLast xor state)).toInt()
        val ob = u(m(swapAcc xor acc)).toInt()
        return intArrayOf(oa, ob)
    }

    private fun hexAll(b: ByteArray): String {
        val sb = StringBuilder(b.size * 2)
        for (x in b) sb.append(String.format("%02X", x))
        return sb.toString()
    }

    private fun hexLe32(a: Int, b: Int): String {
        val sb = StringBuilder(16)
        for (v in intArrayOf(a, b)) {
            for (i in 0 until 4) sb.append(String.format("%02X", (v ushr (i * 8)) and 0xFF))
        }
        return sb.toString()
    }

    /** 自检：三个固定时间戳必须和 Python 端一致，不一致说明移植有错 */
    fun selfTest(): Boolean {
        val want = mapOf(
            1700000000L to "2CD23A2CA0B2595A-F3C846C370E05F9CC83ACC5F995C5F5D87A4D0F14CE8936A0F902E64099E38A2",
            1735689600L to "54404AFE67C9B44A-E72E51D8B4F5F75E9A96B7E20D7877227455BC310433BD30C817CD54A1D9313E",
            1767225600L to "723A6EBC411B23BB-214991EA6B1E401F3D777A699DDDEE75E29740EA7A5DCD1007366FA1090DD267"
        )
        for ((ts, exp) in want) {
            val got = generateSecMsGec(ts)
            if (got != exp) {
                android.util.Log.e("VTEDGE", "selfTest FAIL ts=$ts got=$got want=$exp")
                return false
            }
        }
        android.util.Log.i("VTEDGE", "selfTest OK")
        return true
    }

    fun generateSecMsGec(unixSeconds: Long = System.currentTimeMillis() / 1000L): String {
        var ticks = unixSeconds + WIN_EPOCH
        ticks -= ticks % 300
        ticks *= 10000000L
        val plain = (ticks.toString() + TRUSTED_CLIENT_TOKEN).toByteArray(Charsets.US_ASCII)
        val digest = sha256Digest(plain)
        val c = cs64(plain, digest)
        return hexLe32(c[0], c[1]) + "-" + hexAll(digest)
    }
}
