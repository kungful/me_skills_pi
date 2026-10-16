"""报告输出：Markdown / HTML 看板 / CSV"""
from __future__ import annotations

import csv
import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .config import REPORT_DIR
from .models import Topic

TOP_N = 40


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def write_reports(topics: List[Topic], top_n: int = TOP_N) -> Dict[str, str]:
    topics = topics[:top_n]
    md = REPORT_DIR / f"需求雷达-{_today()}.md"
    htmlf = REPORT_DIR / f"需求雷达-{_today()}.html"
    csvf = REPORT_DIR / f"需求雷达-{_today()}.csv"
    latest_md = REPORT_DIR / "最新报告.md"
    latest_html = REPORT_DIR / "index.html"

    md_text = render_markdown(topics)
    md.write_text(md_text, encoding="utf-8")
    latest_md.write_text(md_text, encoding="utf-8")

    html_text = render_html(topics)
    htmlf.write_text(html_text, encoding="utf-8")
    latest_html.write_text(html_text, encoding="utf-8")

    with csvf.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["排名", "需求主题", "机会分", "证据数", "来源数", "痛感", "付费意愿", "多样性",
                    "热度", "首次出现", "最近出现", "关键词", "变现路径", "典型原话"])
        for i, t in enumerate(topics, 1):
            w.writerow([
                i, t.label, t.score, len(t.item_ids), len(t.sources), t.pain, t.pay, t.diversity,
                t.heat, (t.first_seen or "")[:10], (t.last_seen or "")[:10],
                " ".join(t.keywords[:6]), t.money,
                (t.samples[0]["text"] if t.samples else "")[:150],
            ])

    return {"md": str(md), "html": str(htmlf), "csv": str(csvf), "latest": str(latest_html)}


# ---------------------------------------------------------------- Markdown

def render_markdown(topics: List[Topic]) -> str:
    L: List[str] = []
    L.append(f"# 需求雷达 · 市场机会报告（{_today()}）\n")
    L.append("> 由 demand-radar 自动生成。每条机会都附原始证据，先验证再投入。\n")
    if not topics:
        L.append("## 暂无命中数据\n\n请先运行 `python -m demand_radar run` 采集数据。\n")
        return "\n".join(L)

    L.append("## 一、机会总览\n")
    L.append("| # | 需求主题 | 机会分 | 证据 | 来源 | 痛感 | 付费 | 变现路径 |")
    L.append("|---|---------|-------|------|------|------|------|---------|")
    for i, t in enumerate(topics, 1):
        L.append(
            f"| {i} | **{t.label}** | **{t.score:.0f}** | {len(t.item_ids)} | {len(t.sources)} | "
            f"{t.pain:.0f} | {t.pay:.0f} | {t.money.split('] ', 1)[-1][:48]} |"
        )
    L.append("")

    L.append("## 二、机会详情（按分数排序）\n")
    for i, t in enumerate(topics[:20], 1):
        L.append(f"### {i}. {t.label} — 机会分 {t.score:.0f}\n")
        L.append(f"- **证据**：{len(t.item_ids)} 条素材，来自 {len(t.sources)} 个源（{', '.join(t.sources.keys())}），"
                 f"独立作者约 {t.authors} 人")
        L.append(f"- **信号**：痛感 {t.pain:.0f} / 付费意愿 {t.pay:.0f} / 紧迫 {t.urgency:.0f} / "
                 f"跨源多样性 {t.diversity:.0f}")
        L.append(f"- **赛道**：{'、'.join(t.categories) or '—'}｜关键词：{'、'.join(t.keywords[:6])}")
        if t.last_seen:
            L.append(f"- **时间**：{t.first_seen[:10]} ~ {t.last_seen[:10]}")
        L.append(f"- **变现路径**：{t.money}")
        L.append("- **验证动作**：")
        for v in t.validation:
            L.append(f"  - {v}")
        if t.samples:
            L.append("- **典型原话**：")
            for s in t.samples[:3]:
                src = s.get("source", "")
                link = s.get("url") or ""
                head = f"[{src}]" if not link else f"[{src}]({link})"
                L.append(f"  - {head} {s.get('text','')}")
        L.append("")

    L.append("## 三、下一步怎么做（赚钱路径）\n")
    L.append("""1. **选 3 条高分需求**，不要全做——同时开工等于全都不成。
2. **先卖后做**：给这 3 条各写一页落地页 / 一条小红书笔记 / 一个闲鱼链接，明码标价。
3. **人工交付 MVP**：有单后自己手动做，收全款。跑通 3 单再写代码自动化。
4. **定价套路**：工具类 ¥19.9 引流款 + ¥99 主力款 + ¥299 定制款；服务类先按次收费，再转包月。
5. **渠道复用**：同一个需求在 小红书 / 闲鱼 / 公众号 / 知乎 各发一次，看哪个渠道私信最多，All in 那个。
6. **每周复盘**：重跑一次雷达，只看「新出现的主题」和「分数上涨的主题」——那就是正在起飞的需求。
""")
    return "\n".join(L)


# ---------------------------------------------------------------- HTML

def render_html(topics: List[Topic]) -> str:
    e = html.escape
    cards = []
    for i, t in enumerate(topics, 1):
        bars = [
            ("痛感", t.pain, "#ff5470"),
            ("付费意愿", t.pay, "#00c48c"),
            ("跨源多样性", t.diversity, "#3b82f6"),
            ("紧迫度", t.urgency, "#f59e0b"),
            ("热度", t.heat, "#8b5cf6"),
        ]
        bar_html = "".join(
            f'<div class="bar"><span>{e(name)} <b>{val:.0f}</b></span>'
            f'<div class="track"><i style="width:{min(100, val):.0f}%;background:{color}"></i></div></div>'
            for name, val, color in bars
        )
        samples = "".join(
            f'<li><span class="tag">{e(s.get("source",""))}</span> '
            f'{"<a href=" + chr(34) + e(s["url"]) + chr(34) + " target=_blank>" if s.get("url") else ""}'
            f'{e(s.get("text",""))}'
            f'{"</a>" if s.get("url") else ""}</li>'
            for s in t.samples[:4]
        )
        val = "".join(f"<li>{e(v)}</li>" for v in t.validation)
        cats = "".join(f'<span class="chip">{e(c)}</span>' for c in t.categories)
        kws = "".join(f'<span class="chip soft">{e(k)}</span>' for k in t.keywords[:6])
        srcs = "".join(
            f'<span class="chip src">{e(k)} ×{v}</span>' for k, v in sorted(t.sources.items(), key=lambda x: -x[1])
        )
        hot = "hot" if t.score >= 55 else ("warm" if t.score >= 35 else "cold")
        cards.append(f"""
<article class="card {hot}" data-score="{t.score:.0f}" data-label="{e(t.label)}" data-cats="{e(','.join(t.categories))}">
  <header>
    <div class="rank">#{i}</div>
    <div class="title"><h3>{e(t.label)}</h3>
      <div class="chips">{cats}{kws}</div>
    </div>
    <div class="score"><b>{t.score:.0f}</b><span>机会分</span></div>
  </header>
  <div class="meta">
    证据 <b>{len(t.item_ids)}</b> 条 · 来源 <b>{len(t.sources)}</b> 个 · 独立作者 <b>{t.authors}</b> 人
    {(("· " + e(t.first_seen[:10]) + " ~ " + e(t.last_seen[:10])) if t.last_seen else "")}
  </div>
  <div class="bars">{bar_html}</div>
  <div class="sources">{srcs}</div>
  <div class="money"><span>💰 变现路径</span> {e(t.money)}</div>
  <details><summary>验证动作（点开照做）</summary><ol class="val">{val}</ol></details>
  <details open><summary>典型原话（点击可跳原帖）</summary><ul class="samples">{samples}</ul></details>
</article>""")

    table = "".join(
        f"<tr><td>{i}</td><td>{e(t.label)}</td><td class='num'>{t.score:.0f}</td>"
        f"<td class='num'>{len(t.item_ids)}</td><td class='num'>{len(t.sources)}</td>"
        f"<td class='num'>{t.pain:.0f}</td><td class='num'>{t.pay:.0f}</td>"
        f"<td>{e(t.money.split('] ',1)[-1][:60])}</td></tr>"
        for i, t in enumerate(topics, 1)
    )

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>需求雷达 · 市场机会看板 {_today()}</title>
<style>
:root{{--bg:#0b1220;--card:#121b2e;--card2:#0f1729;--fg:#e6edf7;--dim:#8fa3bf;--line:#1f2b45;
--hot:#ff5470;--warm:#f59e0b;--cold:#3b82f6}}
*{{box-sizing:border-box}}
body{{margin:0;background:linear-gradient(180deg,#080d18,#0b1220 400px);color:var(--fg);
font:14px/1.65 -apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:1180px;margin:0 auto;padding:28px 18px 80px}}
h1{{font-size:26px;margin:0 0 6px}}
.sub{{color:var(--dim);margin-bottom:18px}}
.toolbar{{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0 24px}}
input,select{{background:var(--card2);border:1px solid var(--line);color:var(--fg);
padding:9px 12px;border-radius:9px;font-size:13px}}
input{{min-width:240px}}
.card{{background:linear-gradient(180deg,var(--card),var(--card2));border:1px solid var(--line);
border-radius:14px;padding:16px 18px;margin-bottom:14px}}
.card.hot{{border-color:#4a2033;box-shadow:0 0 0 1px #3a1a28 inset}}
.card header{{display:flex;align-items:flex-start;gap:14px}}
.rank{{font-weight:700;color:var(--dim);font-size:15px;padding-top:4px;min-width:34px}}
.title{{flex:1}} h3{{margin:0 0 6px;font-size:17px}}
.score{{text-align:right;min-width:86px}}
.score b{{font-size:30px;line-height:1;display:block}}
.card.hot .score b{{color:var(--hot)}} .card.warm .score b{{color:var(--warm)}} .card.cold .score b{{color:var(--cold)}}
.score span{{font-size:11px;color:var(--dim)}}
.chips{{display:flex;gap:6px;flex-wrap:wrap;margin-top:4px}}
.chip{{font-size:11px;padding:2px 8px;border-radius:20px;background:#1b2740;color:#a9bede;border:1px solid #24314d}}
.chip.soft{{background:#141d31;color:#7f93b0}}
.chip.src{{background:#132a22;color:#63d3a6;border-color:#1c4536}}
.meta{{color:var(--dim);font-size:12.5px;margin:10px 0 12px}}
.bars{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:8px 16px;margin:10px 0}}
.bar span{{font-size:11.5px;color:var(--dim);display:flex;justify-content:space-between}}
.bar .track{{height:5px;background:#1a2338;border-radius:4px;overflow:hidden;margin-top:3px}}
.bar i{{display:block;height:100%;border-radius:4px}}
.sources{{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}}
.money{{background:#101c2e;border:1px dashed #2a3b5c;border-radius:10px;padding:10px 12px;margin:10px 0;font-size:13px}}
.money span{{color:#7fe3b8;margin-right:6px}}
details{{margin:8px 0}}
summary{{cursor:pointer;color:var(--dim);font-size:12.5px;padding:4px 0}}
summary:hover{{color:var(--fg)}}
ul.samples{{list-style:none;padding:0;margin:6px 0}}
ul.samples li{{padding:8px 10px;background:#0d1526;border-left:2px solid #2b3d5f;border-radius:0 8px 8px 0;margin-bottom:6px;font-size:13px;color:#c8d6ea}}
ul.samples a{{color:#9dc4ff;text-decoration:none}}
ol.val{{margin:6px 0 6px 20px;color:#b7c7dd;font-size:13px}}
table{{width:100%;border-collapse:collapse;margin-top:10px;font-size:13px}}
th,td{{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left}}
th{{color:var(--dim);font-weight:600;position:sticky;top:0;background:#0b1220}}
td.num{{text-align:right;font-variant-numeric:tabular-nums}}
.h2{{margin:34px 0 8px;font-size:19px}}
footer{{color:var(--dim);font-size:12px;margin-top:40px;border-top:1px solid var(--line);padding-top:14px}}
</style></head><body><div class="wrap">
<h1>🚀 需求雷达 · 市场机会看板</h1>
<div class="sub">生成时间 {datetime.now().strftime('%Y-%m-%d %H:%M')} ・ 共 {len(topics)} 个需求主题 ・ 按机会分排序
・ 分数 = 痛感26% + 证据量18% + 跨源多样性16% + 付费意愿14% + 热度/紧迫/新鲜度</div>
<div class="toolbar">
  <input id="q" placeholder="搜索主题 / 关键词 / 分类…">
  <select id="minScore">
    <option value="0">全部分数</option><option value="35">≥35 值得看</option>
    <option value="55">≥55 优先做</option><option value="70">≥70 立刻动手</option>
  </select>
  <select id="sortBy"><option value="score">按机会分</option><option value="pay">按付费意愿</option>
  <option value="evidence">按证据量</option><option value="diversity">按跨源多样性</option></select>
</div>
<div id="cards">{''.join(cards) or '<p>暂无数据，请先运行采集。</p>'}</div>

<h2 class="h2">📋 机会速查表</h2>
<table><thead><tr><th>#</th><th>需求主题</th><th>机会分</th><th>证据</th><th>来源</th><th>痛感</th><th>付费</th><th>变现路径</th></tr></thead>
<tbody>{table}</tbody></table>

<footer>demand-radar ・ 数据来自公开信息与本人账号可见内容，仅供选品与产品决策参考 ・
生成于 {datetime.now().isoformat(timespec='seconds')}</footer>
</div>
<script>
const cards=[...document.querySelectorAll('.card')];
const q=document.getElementById('q'),ms=document.getElementById('minScore'),sb=document.getElementById('sortBy');
function apply(){{
  const kw=q.value.trim().toLowerCase(), min=+ms.value;
  let vis=0;
  cards.forEach(c=>{{
    const okKw=!kw||c.innerText.toLowerCase().includes(kw);
    const okSc=+c.dataset.score>=min;
    c.style.display=(okKw&&okSc)?'':'none'; if(okKw&&okSc)vis++;
  }});
  const key={{score:'score',pay:'pay',evidence:'evidence',diversity:'div'}}[sb.value];
  cards.sort((a,b)=>{{
    const g=e=>+((e.querySelector('.bar b')&&0)||0);
    if(sb.value==='score')return b.dataset.score-a.dataset.score;
    const val=(el,i)=>{{
      const bars=[...el.querySelectorAll('.bar')];
      const name={{pay:'付费意愿',evidence:null,diversity:'跨源多样性'}}[sb.value];
      if(sb.value==='evidence')return +(el.querySelector('.meta b').textContent);
      const b=bars.find(x=>x.textContent.includes(name));return b?+b.querySelector('b').textContent:0;
    }};
    return val(b)-val(a);
  }});
  const box=document.getElementById('cards');cards.forEach(c=>box.appendChild(c));
}}
q.oninput=apply;ms.onchange=apply;sb.onchange=apply;
</script></body></html>"""
