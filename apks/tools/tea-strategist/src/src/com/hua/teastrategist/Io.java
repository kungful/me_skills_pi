package com.hua.teastrategist;

import android.content.Context;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;

/** 本地文档读写（客户台账等）。放在 App 私有目录，不需要存储权限。 */
final class Io {

    private Io() { }

    private static File dir(Context c) {
        File d = new File(c.getFilesDir(), "data");
        if (!d.exists()) d.mkdirs();
        return d;
    }

    static File file(Context c, String name) {
        String s = name.replaceAll("[\\\\/:*?\"<>|]", "_");
        if (s.length() > 60) s = s.substring(0, 60);
        return new File(dir(c), s);
    }

    static String read(Context c, String name) {
        try {
            File f = file(c, name);
            if (!f.exists()) return "";
            FileInputStream in = new FileInputStream(f);
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
            in.close();
            return new String(bo.toByteArray(), "UTF-8");
        } catch (Throwable t) {
            return "";
        }
    }

    static long write(Context c, String name, String text) throws Exception {
        File f = file(c, name);
        FileOutputStream fo = new FileOutputStream(f);
        fo.write(text.getBytes("UTF-8"));
        fo.flush();
        fo.close();
        return f.length();
    }
}
