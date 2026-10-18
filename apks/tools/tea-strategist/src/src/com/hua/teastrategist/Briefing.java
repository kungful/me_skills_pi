package com.hua.teastrategist;

import android.app.AlarmManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.Collections;
import java.util.Comparator;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 军师晨报 —— 每天定时抓一遍情报 + 行情，本地打标排序，
 * 有 API Key 就再让大模型写一段研判，然后发通知。
 *
 * 全程在原生层跑，不依赖 WebView 是否活着。
 */
final class Briefing {

    static final String CHANNEL = "briefing";
    static final int NOTI_ID = 8801;
    static final String SP = "teastrategist";
    static final String KEY_LATEST = "briefing.latest";
    static final String KEY_TIME = "briefing.latestTime";

    private Briefing() { }

    // =====================================================================
    // 关键词打标（和前端 kb.js 的 TAGS 保持一致的精简版）
    // =====================================================================
    private static final Object[][] TAGS = {
        { "军事·地缘", 9, "冲突,袭击,开战,军演,导弹,无人机,停火,制裁,封锁,海峡,红海,霍尔木兹,胡塞,以军,俄军,乌军,北约,国防,武器,驻军,撤离,政变,枪击" },
        { "关税·贸易", 10, "关税,加征,贸易战,反倾销,出口管制,禁运,配额,自贸,RCEP,通关,报关,转口,特保" },
        { "汇率·金融", 8, "汇率,人民币,美元指数,降息,加息,美联储,央行,贬值,升值,结汇" },
        { "航运·物流", 8, "运价,航运,海运,运费,港口,集装箱,苏伊士,巴拿马,罢工,塞港,班轮" },
        { "政策·法规", 7, "国常会,新规,条例,标准,农残,限量,检测,认证,补贴,乡村振兴,农业,茶叶" },
        { "茶业·同业", 10, "茶,茶叶,茶园,茶饮,奶茶,普洱,龙井,绿茶,红茶,乌龙,白茶,茉莉,抹茶" },
        { "消费·市场", 6, "消费,零售,电商,直播,出海,新茶饮,健康,养生,控糖,无糖" },
        { "能源·大宗", 6, "油价,原油,天然气,煤炭,大宗,期货,农产品,化肥" },
    };

    static class Item {
        String title = "";
        String time = "";
        String src = "";
        String tag = "";
        int weight = 0;
    }

    private static Item tag(String title) {
        Item it = new Item();
        it.title = title == null ? "" : title;
        String s = it.title;
        for (Object[] t : TAGS) {
            String[] kws = ((String) t[2]).split(",");
            for (String k : kws) {
                if (!k.isEmpty() && s.contains(k)) {
                    it.tag = (String) t[0];
                    it.weight = (Integer) t[1];
                    return it;
                }
            }
        }
        return it;
    }

    // =====================================================================
    // 采集
    // =====================================================================
    private static List<Item> fetchNews() {
        List<Item> out = new ArrayList<>();
        // 东财 7x24（含军事/关税/能源/航运）
        try {
            Net.Res r = Net.fetch(
                "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
                    + "?client=web&biz=web_news_col&fastColumn=102&sortEnd=&pageSize=40&req_trace=1",
                "GET", null, null, null, 12);
            JSONObject j = new JSONObject(r.body);
            JSONArray arr = j.getJSONObject("data").getJSONArray("fastNewsList");
            for (int i = 0; i < arr.length(); i++) {
                JSONObject o = arr.getJSONObject(i);
                Item it = tag(o.optString("title", ""));
                it.time = o.optString("showTime", "");
                it.src = "全球快讯";
                if (!it.title.isEmpty()) out.add(it);
            }
        } catch (Throwable ignored) { }
        // 新浪国际
        try {
            Net.Res r = Net.fetch(
                "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2511&k=&num=30&page=1",
                "GET", null, null, null, 12);
            JSONObject j = new JSONObject(r.body);
            JSONArray arr = j.getJSONObject("result").getJSONArray("data");
            for (int i = 0; i < arr.length(); i++) {
                JSONObject o = arr.getJSONObject(i);
                Item it = tag(o.optString("title", ""));
                it.time = "";
                it.src = "国际要闻";
                if (!it.title.isEmpty()) out.add(it);
            }
        } catch (Throwable ignored) { }
        return out;
    }

    private static String fetchQuotes(Context c) {
        try {
            SharedPreferences sp = c.getSharedPreferences(SP, Context.MODE_PRIVATE);
            String watch = sp.getString("watch", "");
            if (watch == null || watch.trim().isEmpty()) return "";
            StringBuilder codes = new StringBuilder();
            for (String line : watch.split("\n")) {
                String t = line.trim();
                if (t.isEmpty()) continue;
                String code = t.split("\\s+")[0];
                if (codes.length() > 0) codes.append(',');
                codes.append(code);
                if (codes.length() > 200) break;
            }
            if (codes.length() == 0) return "";
            Net.Res r = Net.fetch("https://qt.gtimg.cn/q=" + codes, "GET",
                    null, null, "GBK", 12);
            List<String> parts = new ArrayList<>();
            for (String line : r.body.split(";")) {
                int a = line.indexOf("=\"");
                int b = line.lastIndexOf('"');
                if (a < 0 || b <= a) continue;
                String[] f = line.substring(a + 2, b).split("~");
                if (f.length < 6) continue;
                try {
                    double price = Double.parseDouble(f[3]);
                    double prev = Double.parseDouble(f[4]);
                    double pct = prev == 0 ? 0 : (price - prev) / prev * 100;
                    parts.add(f[1] + " " + trim(price) + " " + (pct >= 0 ? "+" : "") + round2(pct) + "%");
                } catch (Throwable ignored) { }
            }
            return join(parts, "　|　");
        } catch (Throwable t) {
            return "";
        }
    }

    private static String fetchFx() {
        try {
            Net.Res r = Net.fetch("https://open.er-api.com/v6/latest/USD", "GET", null, null, null, 12);
            JSONObject j = new JSONObject(r.body);
            JSONObject rt = j.getJSONObject("rates");
            return "USD/CNY " + round4(rt.optDouble("CNY", 0))
                 + "　EUR " + round4(rt.optDouble("EUR", 0))
                 + "　JPY " + round4(rt.optDouble("JPY", 0));
        } catch (Throwable t) {
            return "";
        }
    }

    /** 台账里今天/逾期要跟进的客户 */
    private static String fetchDue(Context c) {
        try {
            String json = Io.read(c, "ledger.json");
            if (json == null || json.trim().isEmpty()) return "";
            JSONArray arr = new JSONArray(json);
            String today = new SimpleDateFormat("yyyy-MM-dd").format(new Date());
            List<String> due = new ArrayList<>();
            for (int i = 0; i < arr.length(); i++) {
                JSONObject o = arr.getJSONObject(i);
                String nx = o.optString("next", "");
                String st = o.optString("status", "");
                if (nx.isEmpty()) continue;
                if ("成交".equals(st) || "流失".equals(st)) continue;
                if (nx.compareTo(today) <= 0) {
                    due.add(o.optString("name", "?") + (nx.compareTo(today) < 0 ? "(逾期)" : ""));
                }
            }
            if (due.isEmpty()) return "";
            return join(due, "、");
        } catch (Throwable t) {
            return "";
        }
    }

    // =====================================================================
    // 生成晨报
    // =====================================================================
    static String build(Context c, boolean wantAi) {
        List<Item> news = fetchNews();

        // 去重 + 排序
        Map<String, Item> byTitle = new HashMap<>();
        for (Item it : news) {
            String k = it.title.length() > 18 ? it.title.substring(0, 18) : it.title;
            Item old = byTitle.get(k);
            if (old == null || it.weight > old.weight) byTitle.put(k, it);
        }
        List<Item> list = new ArrayList<>(byTitle.values());
        Collections.sort(list, new Comparator<Item>() {
            public int compare(Item a, Item b) {
                if (a.weight != b.weight) return b.weight - a.weight;
                return b.time.compareTo(a.time);
            }
        });

        String quotes = fetchQuotes(c);
        String fx = fetchFx();
        String due = fetchDue(c);

        String day = new SimpleDateFormat("M月d日").format(new Date());
        StringBuilder sb = new StringBuilder();
        sb.append("【茶叶军师 · 晨报 ").append(day).append("】\n");

        if (!due.isEmpty()) {
            sb.append("\n▎今天要跟进的客户\n").append(due).append('\n');
        }

        sb.append("\n▎要盯的事\n");
        int n = 0;
        for (Item it : list) {
            if (n >= 6) break;
            if (it.weight < 7) continue;
            sb.append(++n).append(". ").append(it.title);
            if (!it.tag.isEmpty()) sb.append("　[").append(it.tag).append(']');
            sb.append('\n');
        }
        if (n == 0) sb.append("（今天没有高优先级情报）\n");

        if (!quotes.isEmpty()) sb.append("\n▎盘面\n").append(quotes).append('\n');
        if (!fx.isEmpty()) sb.append(fx).append('\n');

        String head = sb.toString();

        if (wantAi) {
            String ai = aiComment(c, head, list);
            if (ai != null && !ai.isEmpty()) {
                head = head + "\n▎军师一句\n" + ai + "\n";
            }
        }
        return head.trim();
    }

    private static String aiComment(Context c, String head, List<Item> list) {
        SharedPreferences sp = c.getSharedPreferences(SP, Context.MODE_PRIVATE);
        String url = sp.getString("mUrl", "");
        String model = sp.getString("mModel", "");
        String key = sp.getString("mKey", "");
        if (url.isEmpty() || key.isEmpty() || model.isEmpty()) return null;
        try {
            StringBuilder news = new StringBuilder();
            for (int i = 0; i < list.size() && i < 15; i++) {
                news.append("- ").append(list.get(i).title)
                    .append(" [").append(list.get(i).tag).append("]\n");
            }
            String sys = "你是茶叶工厂的军师，能从财经、关税、汇率、航运、地缘军事局势里读出对茶叶出口与内销的影响。"
                       + "回答要短、要具体、不要客套，不要编数字。";
            String ask = "【今日情报】\n" + news + "\n【盘面】\n" + head
                       + "\n\n用 2~3 句话告诉我：今天这些事里，哪一条最影响我的茶叶生意，我该做什么动作。不超过 120 字。";
            JSONObject body = new JSONObject();
            body.put("model", model);
            body.put("temperature", 0.5);
            JSONArray msgs = new JSONArray();
            msgs.put(new JSONObject().put("role", "user").put("content", sys + "\n\n" + ask));
            body.put("messages", msgs);

            Map<String, String> h = new HashMap<>();
            h.put("Content-Type", "application/json");
            h.put("Authorization", "Bearer " + key);
            Net.Res r = Net.fetch(url, "POST", h, body.toString(), null, 60);
            if (r.status >= 400) return null;
            JSONObject j = new JSONObject(r.body);
            String t = j.getJSONArray("choices").getJSONObject(0)
                        .getJSONObject("message").getString("content");
            return t == null ? null : t.trim();
        } catch (Throwable t) {
            return null;
        }
    }

    // =====================================================================
    // 通知
    // =====================================================================
    static void ensureChannel(Context c) {
        if (Build.VERSION.SDK_INT < 26) return;
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) return;
        if (nm.getNotificationChannel(CHANNEL) != null) return;
        NotificationChannel ch = new NotificationChannel(CHANNEL, "军师晨报", NotificationManager.IMPORTANCE_DEFAULT);
        ch.setDescription("每天定时推送的茶叶生意情报与研判");
        nm.createNotificationChannel(ch);
    }

    static void notify(Context c, String title, String text) {
        try {
            ensureChannel(c);
            NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm == null) return;
            Intent i = new Intent(c, MainActivity.class);
            i.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
            i.putExtra("showBriefing", true);
            int flags = PendingIntent.FLAG_UPDATE_CURRENT;
            if (Build.VERSION.SDK_INT >= 23) flags |= PendingIntent.FLAG_IMMUTABLE;
            PendingIntent pi = PendingIntent.getActivity(c, 1, i, flags);

            Notification n;
            if (Build.VERSION.SDK_INT >= 26) {
                n = new Notification.Builder(c, CHANNEL)
                    .setSmallIcon(android.R.drawable.stat_notify_more)
                    .setContentTitle(title)
                    .setContentText(firstLine(text))
                    .setStyle(new Notification.BigTextStyle().bigText(text))
                    .setAutoCancel(true)
                    .setContentIntent(pi)
                    .build();
            } else {
                n = new Notification.Builder(c)
                    .setSmallIcon(android.R.drawable.stat_notify_more)
                    .setContentTitle(title)
                    .setContentText(firstLine(text))
                    .setStyle(new Notification.BigTextStyle().bigText(text))
                    .setAutoCancel(true)
                    .setContentIntent(pi)
                    .build();
            }
            nm.notify(NOTI_ID, n);
        } catch (Throwable ignored) { }
    }

    // =====================================================================
    // 定时
    // =====================================================================
    static void schedule(Context c) {
        SharedPreferences sp = c.getSharedPreferences(SP, Context.MODE_PRIVATE);
        boolean on = sp.getBoolean("briefing.on", false);
        AlarmManager am = (AlarmManager) c.getSystemService(Context.ALARM_SERVICE);
        if (am == null) return;
        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= 23) flags |= PendingIntent.FLAG_IMMUTABLE;
        Intent i = new Intent(c, BriefingReceiver.class);
        PendingIntent pi = PendingIntent.getBroadcast(c, 2, i, flags);

        if (!on) { am.cancel(pi); return; }

        String hhmm = sp.getString("briefing.time", "07:30");
        int hh = 7, mm = 30;
        try {
            String[] p = hhmm.split(":");
            hh = Integer.parseInt(p[0].trim());
            mm = Integer.parseInt(p[1].trim());
        } catch (Throwable ignored) { }

        Calendar cal = Calendar.getInstance();
        cal.set(Calendar.HOUR_OF_DAY, hh);
        cal.set(Calendar.MINUTE, mm);
        cal.set(Calendar.SECOND, 0);
        cal.set(Calendar.MILLISECOND, 0);
        if (cal.getTimeInMillis() <= System.currentTimeMillis()) cal.add(Calendar.DAY_OF_YEAR, 1);

        am.setInexactRepeating(AlarmManager.RTC_WAKEUP, cal.getTimeInMillis(),
                AlarmManager.INTERVAL_DAY, pi);
    }

    static void run(Context c) {
        try {
            SharedPreferences sp = c.getSharedPreferences(SP, Context.MODE_PRIVATE);
            boolean wantAi = sp.getBoolean("briefing.ai", true);
            String text = build(c, wantAi);
            sp.edit()
              .putString(KEY_LATEST, text)
              .putString(KEY_TIME, new SimpleDateFormat("yyyy-MM-dd HH:mm").format(new Date()))
              .apply();
            if (sp.getBoolean("briefing.notify", true)) notify(c, "军师晨报", text);
        } catch (Throwable t) {
            notify(c, "军师晨报", "生成失败：" + t);
        }
    }

    // =====================================================================
    private static String firstLine(String s) {
        if (s == null) return "";
        for (String l : s.split("\n")) {
            String t = l.trim();
            if (!t.isEmpty()) return t.length() > 60 ? t.substring(0, 60) + "…" : t;
        }
        return "";
    }
    private static String trim(double d) {
        if (Math.abs(d - Math.rint(d)) < 1e-9) return String.valueOf((long) d);
        return String.valueOf(Math.round(d * 1000) / 1000.0);
    }
    private static String round2(double d) { return String.valueOf(Math.round(d * 100.0) / 100.0); }
    private static String round4(double d) { return String.valueOf(Math.round(d * 10000.0) / 10000.0); }
    private static String join(List<String> a, String sep) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < a.size(); i++) { if (i > 0) sb.append(sep); sb.append(a.get(i)); }
        return sb.toString();
    }
}
