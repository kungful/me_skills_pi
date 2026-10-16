package com.hua.paintbox;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Typeface;
import android.graphics.drawable.ColorDrawable;
import android.os.Bundle;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

public class MainActivity extends Activity {

    static final int REQ_PICK = 1001;

    private static final String[] TAB_LABEL = {"出图", "仙宫云", "ComfyUI", "设置"};
    private static final String[] TAB_ICON = {"✦", "☁", "🖼", "⚙"};

    private FrameLayout content;
    private LinearLayout tabBar;
    private final View[] pages = new View[4];
    private final LinearLayout[] tabs = new LinearLayout[4];
    private final TextView[] tabText = new TextView[4];
    private int current = 0;
    private String pendingComfyId;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);

        // ---- brand row
        LinearLayout brand = Ui.row(this);
        brand.setPadding(Ui.dp(this, 18), Ui.dp(this, 14), Ui.dp(this, 18), Ui.dp(this, 2));
        TextView logo = Ui.text(this, "✦", 18, true);
        logo.setTextColor(Theme.ACCENT);
        brand.addView(logo);
        TextView name = Ui.text(this, " 跑图助手", 17, true);
        name.setTextColor(Theme.TEXT);
        brand.addView(name, Ui.weight(1f));
        TextView tag = Ui.text(this, "grsai · 仙宫云 · ComfyUI", 10.5f, false);
        tag.setTextColor(Theme.MUTED);
        brand.addView(tag);
        root.addView(brand);

        // ---- segmented tabs
        tabBar = Ui.row(this);
        tabBar.setBackground(Theme.round(this, Theme.SURFACE, Theme.STROKE, 16, 1));
        int p = Ui.dp(this, 4);
        tabBar.setPadding(p, p, p, p);
        LinearLayout.LayoutParams blp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        blp.setMargins(Ui.dp(this, 14), Ui.dp(this, 8), Ui.dp(this, 14), Ui.dp(this, 4));
        tabBar.setLayoutParams(blp);
        for (int i = 0; i < TAB_LABEL.length; i++) {
            final int idx = i;
            LinearLayout item = Ui.col(this);
            item.setGravity(Gravity.CENTER);
            item.setPadding(0, Ui.dp(this, 9), 0, Ui.dp(this, 9));
            item.setClickable(true);
            TextView t = Ui.text(this, TAB_LABEL[i], 12.5f, true);
            t.setGravity(Gravity.CENTER);
            t.setTag(TAB_ICON[i]);
            item.addView(t);
            item.setOnClickListener(v -> show(idx));
            tabBar.addView(item, new LinearLayout.LayoutParams(
                    0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
            tabs[i] = item;
            tabText[i] = t;
        }
        root.addView(tabBar);

        content = new FrameLayout(this);
        root.addView(content, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        setContentView(root);

        if (b != null) current = b.getInt("tab", 0);
        show(current);
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        out.putInt("tab", current);
    }

    private void show(int idx) {
        boolean first = pages[idx] == null;
        if (first) pages[idx] = create(idx);
        content.removeAllViews();
        content.addView(pages[idx], new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        for (int i = 0; i < tabs.length; i++) {
            boolean sel = i == idx;
            tabText[i].setTextColor(sel ? 0xFFFFFFFF : Theme.MUTED);
            tabText[i].setText(TAB_ICON[i] + " " + TAB_LABEL[i]);
            tabs[i].setBackground(sel
                    ? Theme.ripple(this, Theme.gradient(this, Theme.GRAD_ACCENT, 12), 12)
                    : Theme.ripple(this, new ColorDrawable(0x00000000), 12));
        }
        current = idx;
        if (idx == 2 && pendingComfyId != null && pages[2] != null) {
            ((ComfyView) pages[2]).setInstanceId(pendingComfyId);
            pendingComfyId = null;
        }
    }

    private View create(int idx) {
        switch (idx) {
            case 0: return new GrsaiView(this);
            case 1: return new XgcView(this);
            case 2: return new ComfyView(this);
            default: return new SettingsView(this);
        }
    }

    /** Jump to the ComfyUI tab and load the instance's public 8188 URL. */
    public void showComfy(String instanceId) {
        pendingComfyId = instanceId;
        show(2);
    }

    public void pickImages() {
        Intent i = new Intent(Intent.ACTION_GET_CONTENT);
        i.setType("image/*");
        i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
        i.addCategory(Intent.CATEGORY_OPENABLE);
        try {
            startActivityForResult(Intent.createChooser(i, "选参考图"), REQ_PICK);
        } catch (Throwable t) {
            new AlertDialog.Builder(this).setTitle("没有可用的相册/文件选择器")
                    .setMessage(String.valueOf(t)).setPositiveButton("好", null).show();
        }
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req == REQ_PICK && res == RESULT_OK && pages[0] != null) {
            ((GrsaiView) pages[0]).onPickedImages(data);
        }
    }

    @Override
    public void onBackPressed() {
        if (current != 0) show(0);
        else super.onBackPressed();
    }
}
