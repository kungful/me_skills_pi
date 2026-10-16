package com.hua.paintbox;

import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import android.provider.MediaStore;

import java.io.OutputStream;

/** Saves generated images straight into the phone's gallery (Pictures/跑图助手). */
public class Gallery {

    public static final String ALBUM = "跑图助手";

    /** Returns a human readable result; throws on failure. */
    public static String save(Context ctx, String displayName, byte[] data, String mime) throws Exception {
        ContentValues v = new ContentValues();
        v.put(MediaStore.Images.Media.DISPLAY_NAME, displayName);
        v.put(MediaStore.Images.Media.MIME_TYPE, mime == null ? "image/png" : mime);
        v.put(MediaStore.Images.Media.RELATIVE_PATH,
                android.os.Environment.DIRECTORY_PICTURES + "/" + ALBUM);
        v.put(MediaStore.Images.Media.IS_PENDING, 1);

        Uri uri = ctx.getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, v);
        if (uri == null) throw new Exception("MediaStore 插入失败");
        OutputStream os = ctx.getContentResolver().openOutputStream(uri);
        if (os == null) throw new Exception("打开写入流失败");
        try {
            os.write(data);
            os.flush();
        } finally {
            os.close();
        }
        v.clear();
        v.put(MediaStore.Images.Media.IS_PENDING, 0);
        ctx.getContentResolver().update(uri, v, null, null);
        return "图库/Pictures/" + ALBUM + "/" + displayName;
    }
}
