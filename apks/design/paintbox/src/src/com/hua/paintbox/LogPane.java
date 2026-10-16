package com.hua.paintbox;

import android.content.Context;
import android.graphics.Typeface;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/** Collapsible dark log console; {@link #log(String)} is safe from any thread. */
public class LogPane extends LinearLayout {

    private final TextView body;
    private final ScrollView sv;
    private final LinearLayout header;
    private final SimpleDateFormat fmt = new SimpleDateFormat("HH:mm:ss", Locale.US);
    private boolean open;

    public LogPane(Context c) {
        this(c, false);
    }

    public LogPane(Context c, boolean startOpen) {
        super(c);
        setOrientation(VERTICAL);

        header = Ui.row(c);
        TextView chev = Ui.text(c, "›", 16, true);
        chev.setTextColor(Theme.MUTED);
        TextView title = Ui.text(c, "运行日志", 12.5f, true);
        title.setTextColor(Theme.MUTED);
        title.setLetterSpacing(0.06f);
        LinearLayout.LayoutParams tlp = Ui.weight(1f);
        tlp.setMargins(Ui.dp(c, 8), 0, 0, 0);
        header.addView(title, tlp);
        TextView clear = Ui.text(c, "清空", 12, false);
        clear.setTextColor(Theme.ACCENT);
        clear.setPadding(Ui.dp(c, 10), Ui.dp(c, 6), 0, Ui.dp(c, 6));
        header.addView(clear);
        TextView copy = Ui.text(c, "复制", 12, false);
        copy.setTextColor(Theme.ACCENT);
        copy.setPadding(Ui.dp(c, 12), Ui.dp(c, 6), Ui.dp(c, 2), Ui.dp(c, 6));
        header.addView(copy);
        header.setPadding(Ui.dp(c, 6), Ui.dp(c, 6), Ui.dp(c, 6), Ui.dp(c, 6));
        addView(header);

        body = new TextView(c);
        body.setTextSize(TypedValue.COMPLEX_UNIT_SP, 11);
        body.setTypeface(Typeface.MONOSPACE);
        body.setTextColor(0xFFB6C3D6);
        body.setTextIsSelectable(true);
        body.setPadding(Ui.dp(c, 12), Ui.dp(c, 10), Ui.dp(c, 12), Ui.dp(c, 10));
        body.setLineSpacing(Ui.dp(c, 2), 1f);

        sv = new ScrollView(c);
        sv.setBackground(Theme.round(c, 0xFF0E131C, Theme.STROKE, 14, 1));
        sv.addView(body, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));
        addView(sv, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(c, 168)));
        sv.setVisibility(startOpen ? VISIBLE : GONE);
        open = startOpen;
        chev.setRotation(startOpen ? 90 : 0);

        header.setOnClickListener(v -> {
            open = !open;
            sv.setVisibility(open ? VISIBLE : GONE);
            chev.animate().rotation(open ? 90 : 0).setDuration(140).start();
        });
        clear.setOnClickListener(v -> body.setText(""));
        copy.setOnClickListener(v -> Ui.copy(c, "log", body.getText().toString()));
        log("就绪 · " + (new SimpleDateFormat("MM-dd HH:mm", Locale.US)).format(new Date()));
    }

    public void log(final String s) {
        post(() -> {
            body.append(fmt.format(new Date()) + "  " + s + "\n");
            if (open) sv.post(() -> sv.fullScroll(ScrollView.FOCUS_DOWN));
        });
    }

    public void clear() {
        post(() -> body.setText(""));
    }
}
