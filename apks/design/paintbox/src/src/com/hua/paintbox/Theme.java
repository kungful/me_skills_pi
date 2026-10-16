package com.hua.paintbox;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.drawable.ClipDrawable;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.LayerDrawable;
import android.graphics.drawable.RippleDrawable;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.animation.DecelerateInterpolator;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;

/** Design kit: one dark, modern look shared by every screen (no AndroidX, pure SDK). */
public class Theme {

    public static final int BG = 0xFF0B0E14;
    public static final int SURFACE = 0xFF141A24;
    public static final int SURFACE2 = 0xFF1C2430;
    public static final int SURFACE3 = 0xFF232D3C;
    public static final int STROKE = 0xFF29323F;
    public static final int TEXT = 0xFFEAF0F8;
    public static final int MUTED = 0xFF8C97AB;
    public static final int ACCENT = 0xFF4C7DFF;
    public static final int ACCENT2 = 0xFF9B5CFF;
    public static final int OK = 0xFF3DD68C;
    public static final int WARN = 0xFFFFB020;
    public static final int DANGER = 0xFFFF5A5F;
    public static final int RIPPLE = 0x40FFFFFF;

    public static final int[] GRAD_ACCENT = {ACCENT, ACCENT2};

    // ------------------------------------------------------------------ shapes

    public static GradientDrawable round(Context c, int fill, float radiusDp) {
        return round(c, fill, 0, radiusDp, 0);
    }

    public static GradientDrawable round(Context c, int fill, int strokeColor, float radiusDp, float strokeDp) {
        GradientDrawable g = new GradientDrawable();
        g.setShape(GradientDrawable.RECTANGLE);
        g.setColor(fill);
        g.setCornerRadius(Ui.dp(c, radiusDp));
        if (strokeDp > 0) g.setStroke(Ui.dp(c, strokeDp), strokeColor);
        return g;
    }

    public static GradientDrawable gradient(Context c, int[] colors, float radiusDp) {
        GradientDrawable g = new GradientDrawable(GradientDrawable.Orientation.LEFT_RIGHT, colors);
        g.setShape(GradientDrawable.RECTANGLE);
        g.setCornerRadius(Ui.dp(c, radiusDp));
        return g;
    }

    public static Drawable ripple(Context c, Drawable content, float radiusDp) {
        GradientDrawable mask = round(c, 0xFFFFFFFF, radiusDp);
        return new RippleDrawable(ColorStateList.valueOf(RIPPLE), content, mask);
    }

    public static void elevate(View v, float dp) {
        v.setElevation(Ui.dp(v.getContext(), dp));
    }

    public static void press(View v) {
        v.setOnTouchListener((view, e) -> {
            if (e.getAction() == android.view.MotionEvent.ACTION_DOWN) {
                view.animate().scaleX(0.97f).scaleY(0.97f).setDuration(90).start();
            } else if (e.getAction() == android.view.MotionEvent.ACTION_UP
                    || e.getAction() == android.view.MotionEvent.ACTION_CANCEL) {
                view.animate().scaleX(1f).scaleY(1f).setDuration(120)
                        .setInterpolator(new DecelerateInterpolator()).start();
            }
            return false;
        });
    }

    // ------------------------------------------------------------------ text

    public static TextView title(Context c, String s) {
        TextView t = Ui.text(c, s, 21, true);
        t.setTextColor(TEXT);
        return t;
    }

    public static TextView section(Context c, String s) {
        TextView t = Ui.text(c, s, 14.5f, true);
        t.setTextColor(TEXT);
        t.setLetterSpacing(0.01f);
        return t;
    }

    public static TextView label(Context c, String s) {
        TextView t = Ui.text(c, s.toUpperCase(), 11, true);
        t.setTextColor(MUTED);
        t.setLetterSpacing(0.08f);
        t.setPadding(Ui.dp(c, 2), Ui.dp(c, 12), 0, Ui.dp(c, 6));
        return t;
    }

    public static TextView body(Context c, String s) {
        TextView t = Ui.text(c, s, 13, false);
        t.setTextColor(TEXT);
        t.setLineSpacing(Ui.dp(c, 2), 1f);
        return t;
    }

    public static TextView note(Context c, String s) {
        TextView t = Ui.text(c, s, 11.5f, false);
        t.setTextColor(MUTED);
        t.setLineSpacing(Ui.dp(c, 1.5f), 1f);
        return t;
    }

    public static TextView pill(Context c, String text, int color) {
        TextView t = Ui.text(c, text, 11, true);
        t.setTextColor(color);
        t.setPadding(Ui.dp(c, 10), Ui.dp(c, 4), Ui.dp(c, 10), Ui.dp(c, 4));
        GradientDrawable bg = round(c, blend(0x22000000 | (color & 0xFFFFFF), color, 0.16f), 999);
        bg.setStroke(Ui.dp(c, 1), blend(BG, color, 0.45f));
        t.setBackground(bg);
        return t;
    }

    /** Simple alpha blend of two ARGB ints (t=0 -> a, t=1 -> b). */
    public static int blend(int a, int b, float t) {
        int aa = (a >>> 24) & 0xFF, ar = (a >> 16) & 0xFF, ag = (a >> 8) & 0xFF, ab = a & 0xFF;
        int ba = (b >>> 24) & 0xFF, br = (b >> 16) & 0xFF, bg2 = (b >> 8) & 0xFF, bb = b & 0xFF;
        return (((int) (aa + (ba - aa) * t)) << 24) | (((int) (ar + (br - ar) * t)) << 16)
                | (((int) (ag + (bg2 - ag) * t)) << 8) | ((int) (ab + (bb - ab) * t));
    }

    // ------------------------------------------------------------------ containers

    public static LinearLayout screen(Context c) {
        LinearLayout l = Ui.col(c);
        l.setPadding(Ui.dp(c, 16), Ui.dp(c, 12), Ui.dp(c, 16), Ui.dp(c, 28));
        return l;
    }

    public static LinearLayout card(Context c) {
        LinearLayout l = Ui.col(c);
        l.setBackground(round(c, SURFACE, STROKE, 18, 1));
        l.setPadding(Ui.dp(c, 16), Ui.dp(c, 14), Ui.dp(c, 16), Ui.dp(c, 16));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, Ui.dp(c, 7), 0, Ui.dp(c, 7));
        l.setLayoutParams(lp);
        l.setElevation(Ui.dp(c, 2));
        return l;
    }

    /** Gradient hero header: big title, subtitle, optional right-aligned badge. */
    public static LinearLayout hero(Context c, String title, String sub, String badge) {
        LinearLayout l = Ui.col(c);
        GradientDrawable g = gradient(c, new int[]{0xFF1B2A4A, 0xFF2A2350, 0xFF12203C}, 20);
        l.setBackground(g);
        l.setPadding(Ui.dp(c, 18), Ui.dp(c, 16), Ui.dp(c, 18), Ui.dp(c, 16));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, Ui.dp(c, 6), 0, Ui.dp(c, 10));
        l.setLayoutParams(lp);
        l.setElevation(Ui.dp(c, 3));

        LinearLayout top = Ui.row(c);
        TextView t = Ui.text(c, title, 22, true);
        t.setTextColor(0xFFFFFFFF);
        top.addView(t, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        if (badge != null) {
            TextView b = Ui.text(c, badge, 10.5f, true);
            b.setTextColor(0xFFDCE6FF);
            GradientDrawable bg = round(c, 0x332F6FEB, 0x664C7DFF, 999, 1);
            b.setBackground(bg);
            b.setPadding(Ui.dp(c, 10), Ui.dp(c, 4), Ui.dp(c, 10), Ui.dp(c, 4));
            b.setLetterSpacing(0.06f);
            top.addView(b);
        }
        l.addView(top);
        TextView s = Ui.text(c, sub, 12.5f, false);
        s.setTextColor(0xFFB9C6DE);
        s.setLineSpacing(Ui.dp(c, 2), 1f);
        s.setPadding(0, Ui.dp(c, 6), 0, 0);
        l.addView(s);
        return l;
    }

    public static View divider(Context c) {
        View v = new View(c);
        v.setBackgroundColor(STROKE);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Math.max(1, Ui.dp(c, 0.6f)));
        lp.setMargins(0, Ui.dp(c, 12), 0, Ui.dp(c, 4));
        v.setLayoutParams(lp);
        return v;
    }

    public static View spacer(Context c, int h) {
        View v = new View(c);
        v.setLayoutParams(new LinearLayout.LayoutParams(1, Ui.dp(c, h)));
        return v;
    }

    // ------------------------------------------------------------------ inputs

    public static EditText input(Context c, String hint, boolean multi, int lines) {
        EditText e = new EditText(c);
        e.setHint(hint);
        e.setHintTextColor(blend(MUTED, BG, 0.15f));
        e.setTextColor(TEXT);
        e.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14.5f);
        e.setBackground(round(c, SURFACE2, STROKE, 14, 1));
        e.setPadding(Ui.dp(c, 14), Ui.dp(c, 12), Ui.dp(c, 14), Ui.dp(c, 12));
        e.setMinHeight(Ui.dp(c, 46));
        if (multi) {
            e.setSingleLine(false);
            e.setInputType(android.text.InputType.TYPE_CLASS_TEXT
                    | android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE
                    | android.text.InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
            e.setMinLines(lines);
            e.setGravity(Gravity.TOP | Gravity.START);
        }
        return e;
    }

    public static EditText secret(Context c, String hint) {
        EditText e = input(c, hint, false, 1);
        e.setInputType(android.text.InputType.TYPE_CLASS_TEXT
                | android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD);
        return e;
    }

    public static CheckBox check(Context c, String text) {
        CheckBox b = new CheckBox(c);
        b.setText(text);
        b.setTextColor(TEXT);
        b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12.5f);
        b.setButtonTintList(new ColorStateList(
                new int[][]{new int[]{android.R.attr.state_checked}, new int[]{}},
                new int[]{ACCENT, blend(MUTED, BG, 0.3f)}));
        return b;
    }

    // ------------------------------------------------------------------ buttons

    public static Button primary(Context c, String s) {
        Button b = base(c, s, 15f);
        b.setTextColor(0xFFFFFFFF);
        b.setBackground(ripple(c, gradient(c, GRAD_ACCENT, 16), 16));
        b.setTypeface(b.getTypeface(), android.graphics.Typeface.BOLD);
        elevate(b, 2);
        press(b);
        return b;
    }

    public static Button ghost(Context c, String s) {
        Button b = base(c, s, 12.5f);
        b.setTextColor(TEXT);
        b.setBackground(ripple(c, round(c, SURFACE2, STROKE, 12, 1), 12));
        press(b);
        return b;
    }

    public static Button danger(Context c, String s) {
        Button b = base(c, s, 12.5f);
        b.setTextColor(0xFFFFFFFF);
        b.setBackground(ripple(c, round(c, DANGER, blend(DANGER, 0xFF000000, 0.25f), 12, 1), 12));
        press(b);
        return b;
    }

    public static Button small(Context c, String s) {
        Button b = ghost(c, s);
        b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 11.5f);
        b.setPadding(Ui.dp(c, 10), Ui.dp(c, 4), Ui.dp(c, 10), Ui.dp(c, 4));
        b.setMinHeight(Ui.dp(c, 30));
        return b;
    }

    private static Button base(Context c, String s, float sp) {
        Button b = new Button(c);
        b.setText(s);
        b.setAllCaps(false);
        b.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        b.setMinWidth(0);
        b.setMinimumWidth(0);
        b.setMinHeight(Ui.dp(c, 44));
        b.setMinimumHeight(Ui.dp(c, 44));
        b.setPadding(Ui.dp(c, 16), Ui.dp(c, 8), Ui.dp(c, 16), Ui.dp(c, 8));
        b.setStateListAnimator(null);
        return b;
    }

    // ------------------------------------------------------------------ chips

    /** Horizontally scrollable pill selector - replaces the stock Spinner. */
    public static class Chips extends HorizontalScrollView {

        public interface OnPick {
            void onPick(String value, int index);
        }

        private final LinearLayout row;
        private final List<TextView> views = new ArrayList<>();
        private String[] items;
        private int sel = 0;
        private OnPick onPick;

        public Chips(Context c, String[] items, String selected, OnPick pick) {
            super(c);
            this.items = items;
            this.onPick = pick;
            setHorizontalScrollBarEnabled(false);
            setClipToPadding(false);
            int pad = Ui.dp(c, 2);
            setPadding(pad, pad, pad, pad);
            row = Ui.row(c);
            addView(row, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));
            setItems(items, selected);
        }

        public void setItems(String[] items, String selected) {
            this.items = items;
            row.removeAllViews();
            views.clear();
            Context c = getContext();
            int idx = 0;
            for (int i = 0; i < items.length; i++) if (items[i].equals(selected)) idx = i;
            for (int i = 0; i < items.length; i++) {
                final int fi = i;
                TextView t = Ui.text(c, items[i], 12.5f, false);
                t.setPadding(Ui.dp(c, 15), Ui.dp(c, 9), Ui.dp(c, 15), Ui.dp(c, 9));
                LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
                lp.setMargins(0, 0, Ui.dp(c, 8), 0);
                t.setLayoutParams(lp);
                t.setClickable(true);
                t.setOnClickListener(v -> select(fi, true));
                row.addView(t);
                views.add(t);
            }
            sel = idx;
            paint();
        }

        public void select(String value) {
            for (int i = 0; i < items.length; i++) {
                if (items[i].equals(value)) {
                    select(i, false);
                    return;
                }
            }
        }

        public void select(int i, boolean notify) {
            if (i < 0 || i >= views.size()) return;
            sel = i;
            paint();
            if (notify && onPick != null) onPick.onPick(items[i], i);
        }

        public String value() {
            return items == null || items.length == 0 ? "" : items[sel];
        }

        public int index() {
            return sel;
        }

        private void paint() {
            Context c = getContext();
            for (int i = 0; i < views.size(); i++) {
                TextView t = views.get(i);
                if (i == sel) {
                    t.setTextColor(0xFFFFFFFF);
                    t.setTypeface(t.getTypeface(), android.graphics.Typeface.BOLD);
                    t.setBackground(ripple(c, gradient(c, GRAD_ACCENT, 999), 999));
                } else {
                    t.setTextColor(MUTED);
                    t.setTypeface(t.getTypeface(), android.graphics.Typeface.NORMAL);
                    t.setBackground(ripple(c, round(c, SURFACE2, STROKE, 999, 1), 999));
                }
            }
        }
    }

    // ------------------------------------------------------------------ progress

    public static ProgressBar progress(Context c) {
        ProgressBar p = new ProgressBar(c, null, android.R.attr.progressBarStyleHorizontal);
        p.setMax(100);
        GradientDrawable track = round(c, SURFACE3, 999);
        GradientDrawable fill = gradient(c, GRAD_ACCENT, 999);
        LayerDrawable ld = new LayerDrawable(new Drawable[]{
                track, new ClipDrawable(fill, Gravity.START, ClipDrawable.HORIZONTAL)});
        ld.setId(0, android.R.id.background);
        ld.setId(1, android.R.id.progress);
        p.setProgressDrawable(ld);
        p.setMinimumHeight(Ui.dp(c, 8));
        p.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(c, 8)));
        return p;
    }

    public static int colorFor(String status) {
        if (status == null) return MUTED;
        if (status.contains("运行中") || status.contains("计费")) return DANGER;
        if (status.contains("关机")) return OK;
        if (status.contains("开机") || status.contains("创建")) return WARN;
        return MUTED;
    }
}
