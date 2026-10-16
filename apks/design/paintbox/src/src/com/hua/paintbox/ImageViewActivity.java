package com.hua.paintbox;

import android.app.Activity;
import android.graphics.BitmapFactory;
import android.os.Bundle;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Full-screen viewer for the last generated image (bytes handed over in {@link #LAST}). */
public class ImageViewActivity extends Activity {

    public static byte[] LAST;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        root.setBackgroundColor(0xFF000000);

        ImageView iv = new ImageView(this);
        iv.setAdjustViewBounds(true);
        iv.setScaleType(ImageView.ScaleType.FIT_CENTER);
        if (LAST != null) {
            iv.setImageBitmap(BitmapFactory.decodeByteArray(LAST, 0, LAST.length));
        }
        root.addView(iv, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        TextView t = new TextView(this);
        t.setText("点一下返回 · 已自动存进 图库/Pictures/" + Gallery.ALBUM);
        t.setTextColor(0xFFCCCCCC);
        t.setGravity(Gravity.CENTER);
        t.setPadding(0, Ui.dp(this, 12), 0, Ui.dp(this, 12));
        root.addView(t);

        setContentView(root);
        root.setOnClickListener(v -> finish());
    }
}
