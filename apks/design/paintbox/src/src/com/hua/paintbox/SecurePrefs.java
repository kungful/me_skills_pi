package com.hua.paintbox;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.security.KeyStore;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/**
 * Keys/tokens live in private SharedPreferences, encrypted with an AES-GCM key held by the
 * Android Keystore (hardware-backed where available). If the Keystore is unavailable the value
 * is stored unencrypted so the app still works - call {@link #encrypted()} to tell the user.
 */
public class SecurePrefs {

    private static final String STORE = "paintbox";
    private static final String KS = "AndroidKeyStore";
    private static final String ALIAS = "paintbox_master_key";
    private static final String PREFIX = "enc1:";

    private final SharedPreferences sp;
    private final SecretKey key;

    public SecurePrefs(Context c) {
        sp = c.getApplicationContext().getSharedPreferences(STORE, Context.MODE_PRIVATE);
        key = loadKey();
    }

    public boolean encrypted() {
        return key != null;
    }

    private static SecretKey loadKey() {
        try {
            KeyStore ks = KeyStore.getInstance(KS);
            ks.load(null);
            java.security.KeyStore.Entry e = ks.getEntry(ALIAS, null);
            if (e instanceof KeyStore.SecretKeyEntry) return ((KeyStore.SecretKeyEntry) e).getSecretKey();
            KeyGenerator kg = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KS);
            kg.init(new KeyGenParameterSpec.Builder(ALIAS,
                    KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setKeySize(256)
                    .build());
            return kg.generateKey();
        } catch (Throwable t) {
            return null;
        }
    }

    public String get(String k, String def) {
        String v = sp.getString(k, null);
        if (v == null) return def;
        if (v.startsWith(PREFIX)) {
            try {
                return decrypt(v.substring(PREFIX.length()));
            } catch (Throwable t) {
                return def;
            }
        }
        return v;
    }

    public void put(String k, String v) {
        if (v == null) v = "";
        if (key != null) {
            try {
                sp.edit().putString(k, PREFIX + encrypt(v)).apply();
                return;
            } catch (Throwable ignored) {
            }
        }
        sp.edit().putString(k, v).apply();
    }

    public boolean getBool(String k, boolean def) {
        try {
            String v = get(k, def ? "1" : "0");
            return "1".equals(v);
        } catch (Throwable t) {
            return def;
        }
    }

    public void putBool(String k, boolean v) {
        put(k, v ? "1" : "0");
    }

    private String encrypt(String plain) throws Exception {
        Cipher c = Cipher.getInstance("AES/GCM/NoPadding");
        c.init(Cipher.ENCRYPT_MODE, key);
        byte[] iv = c.getIV();
        byte[] ct = c.doFinal(plain.getBytes("UTF-8"));
        byte[] out = new byte[iv.length + ct.length];
        System.arraycopy(iv, 0, out, 0, iv.length);
        System.arraycopy(ct, 0, out, iv.length, ct.length);
        return Base64.encodeToString(out, Base64.NO_WRAP);
    }

    private String decrypt(String b64) throws Exception {
        byte[] all = Base64.decode(b64, Base64.NO_WRAP);
        byte[] iv = new byte[12];
        System.arraycopy(all, 0, iv, 0, 12);
        Cipher c = Cipher.getInstance("AES/GCM/NoPadding");
        c.init(Cipher.DECRYPT_MODE, key, new GCMParameterSpec(128, iv));
        return new String(c.doFinal(all, 12, all.length - 12), "UTF-8");
    }
}
