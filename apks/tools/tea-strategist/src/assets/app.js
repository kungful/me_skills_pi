// ============================================================================
// app.js —— 茶叶军师 前端逻辑
// 模块：Router / Quotes / Intel / Radar / Decide / Ideas / Book / Setting / AI
// ============================================================================
'use strict';

const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
const esc = (s) => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

let toastTimer = null;
function toast(msg, ms) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.add('on');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('on'), ms || 2200);
}

function md2html(src) {
  if (!src) return '';
  let s = esc(src);
  const blocks = [];
  s = s.replace(/```([\s\S]*?)```/g, (m, c) => { blocks.push(c); return '\u0000B' + (blocks.length - 1) + '\u0000'; });

  // 表格（要先处理，否则会被段落拆散）
  s = s.replace(/(?:^\|.*\|[ \t]*$\n?)+/gm, (tbl) => {
    const rows = tbl.trim().split('\n').map((r) => r.replace(/^\||\|$/g, '').split('|').map((c) => c.trim()));
    if (rows.length < 2) return tbl;
    let h = '<table>';
    rows.forEach((r, i) => {
      if (i === 1 && r.every((c) => /^-{2,}$/.test(c.replace(/\s/g, '')))) return;
      h += '<tr>' + r.map((c) => (i === 0 ? '<th>' + c + '</th>' : '<td>' + c + '</td>')).join('') + '</tr>';
    });
    return h + '</table>' + (/\n$/.test(tbl) ? '\n' : '');
  });
  // 列表
  s = s.replace(/(?:^[ \t]*[-*+][ \t]+.+$\n?)+/gm, (blk) => '<ul>' +
    blk.trim().split('\n').map((l) => '<li>' + l.replace(/^[ \t]*[-*+][ \t]+/, '') + '</li>').join('') + '</ul>' + (/\n$/.test(blk) ? '\n' : ''));
  s = s.replace(/(?:^[ \t]*\d+[.、][ \t]+.+$\n?)+/gm, (blk) => '<ol>' +
    blk.trim().split('\n').map((l) => '<li>' + l.replace(/^[ \t]*\d+[.、][ \t]+/, '') + '</li>').join('') + '</ol>' + (/\n$/.test(blk) ? '\n' : ''));
  // 标题
  s = s.replace(/^[ \t]*#{1,6}[ \t]*(.+?)[ \t]*$/gm, '<h3>$1</h3>');
  // 行内
  s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/`([^`]+?)`/g, '<code>$1</code>');
  // 段落（块级元素不包 <p>）
  s = s.split(/\n{2,}/).map((p) => {
    const t = p.trim();
    if (!t) return '';
    if (/^<(h3|ul|ol|table|pre)/.test(t)) return t;
    return '<p>' + t.replace(/\n/g, '<br>') + '</p>';
  }).join('');
  return s.replace(/\u0000B(\d+)\u0000/g, (m, i) => '<pre><code>' + blocks[+i] + '</code></pre>');
}

// ============================================================================
// 路由
// ============================================================================
const Router = {
  cur: 'radar',
  hist: [],
  go(p, noHist) {
    if (!p) return;
    if (p !== this.cur && !noHist) this.hist.push(this.cur);
    this.cur = p;
    $$('.page').forEach((e) => e.classList.toggle('on', e.id === 'p-' + p));
    $$('nav a').forEach((e) => e.classList.toggle('on', e.dataset.p === p));
    window.scrollTo(0, 0);
    main.scrollTop = 0;
    if (p === 'book') Book.render();
    if (p === 'ideas') Ideas.init();
    if (p === 'ledger') Ledger.render();
    if (p === 'intel') Intel.feedClickInit();
  },
  back() { if (this.hist.length) this.go(this.hist.pop(), true); },
  init() {
    $$('nav a').forEach((a) => a.addEventListener('click', (e) => { e.preventDefault(); this.go(a.dataset.p); }));
  },
};
const main = $('main');
window.__back = () => Router.back();

// ============================================================================
// 设置
// ============================================================================
const DEFAULT_WATCH = 'hk02097 蜜雪集团\nhk01364 古茗\nhk02589 沪上阿姨\nusCHA 霸王茶姬\nhk02150 奈雪的茶\nsh600519 贵州茅台\nsh000001 上证指数\nhkHSI 恒生指数';

const Setting = {
  cfg: { url: '', model: '', key: '' },
  biz: {},

  async load() {
    const all = await Tea.store.all();
    this.cfg.url = all.mUrl || 'https://api.deepseek.com/chat/completions';
    this.cfg.model = all.mModel || 'deepseek-chat';
    this.cfg.key = all.mKey || '';
    this.cfg.provider = all.mProvider || 'deepseek';
    this.biz = {
      cat: all.bCat || '', cap: all.bCap || '', addr: all.bAddr || '', now: all.bNow || '',
    };
    const watch = all.watch || DEFAULT_WATCH;

    // 渲染
    const sel = $('#setModel');
    sel.innerHTML = KB.MODELS.map((m) => '<option value="' + m.id + '">' + esc(m.name) + '</option>').join('');
    sel.value = this.cfg.provider;
    $('#setUrl').value = this.cfg.url;
    $('#setModelName').value = this.cfg.model;
    $('#setKey').value = this.cfg.key;
    $('#setCat').value = this.biz.cat;
    $('#setCap').value = this.biz.cap;
    $('#setAddr').value = this.biz.addr;
    $('#setNow').value = this.biz.now;
    $('#setWatch').value = watch;

    // 晨报设置
    try {
      const bs = await Tea.briefing.state();
      pickInit('#setBriefOn', bs.on ? '1' : '0');
      pickInit('#setBriefAi', bs.ai === false ? '0' : '1');
      $('#setBriefTime').value = bs.time || '07:30';
      this.briefHints(bs);
    } catch (e) { pickInit('#setBriefOn', '0'); pickInit('#setBriefAi', '1'); $('#setBriefTime').value = '07:30'; }

    Tea.status().then((s) => {
      $('#aboutBox').innerHTML = '茶叶军师 v' + esc(s.version || '1.0') + '<br>运行于 ' + esc(s.model || '') +
        '<br>Android ' + esc(s.android || '') + ' (API ' + esc(s.sdk || '') + ')' +
        '<br><span class="tiny">行情/快讯/热搜/汇率全部直连公开接口；大模型走你自己填的 Key。</span>';
    }).catch(() => {});
  },

  modelChanged() {
    const id = $('#setModel').value;
    const m = KB.MODELS.find((x) => x.id === id);
    if (m && m.url) { $('#setUrl').value = m.url; $('#setModelName').value = m.model; }
    else { $('#setUrl').value = ''; $('#setModelName').value = ''; $('#setUrl').focus(); }
  },

  async save() {
    const id = $('#setModel').value;
    await Tea.store.set('mProvider', id);
    await Tea.store.set('mUrl', $('#setUrl').value.trim());
    await Tea.store.set('mModel', $('#setModelName').value.trim());
    await Tea.store.set('mKey', $('#setKey').value.trim());
    this.cfg = { provider: id, url: $('#setUrl').value.trim(), model: $('#setModelName').value.trim(), key: $('#setKey').value.trim() };
    toast('已保存');
  },

  async saveBiz() {
    await Tea.store.set('bCat', $('#setCat').value.trim());
    await Tea.store.set('bCap', $('#setCap').value.trim());
    await Tea.store.set('bAddr', $('#setAddr').value.trim());
    await Tea.store.set('bNow', $('#setNow').value.trim());
    this.biz = { cat: $('#setCat').value.trim(), cap: $('#setCap').value.trim(), addr: $('#setAddr').value.trim(), now: $('#setNow').value.trim() };
    toast('已保存，军师会记住你的厂情');
  },

  async saveWatch() {
    await Tea.store.set('watch', $('#setWatch').value.trim());
    toast('已保存');
    Quotes.load(true);
  },
  defaultWatch() { $('#setWatch').value = DEFAULT_WATCH; },

  async paste() { try { const r = await Tea.paste(); $('#setKey').value = (r.text || '').trim(); toast('已粘贴'); } catch (e) { toast(e.message); } },

  async saveBrief() {
    const on = pickVal('#setBriefOn') === '1';
    const tm = ($('#setBriefTime').value || '07:30').trim();
    if (!/^\d{1,2}:\d{2}$/.test(tm)) { toast('时间格式要像 07:30'); return; }
    await Tea.briefing.set({ on: on, time: tm, ai: pickVal('#setBriefAi') === '1', notify: true });
    if (on) await Tea.notifyPerm();
    const bs = await Tea.briefing.state();
    this.briefHints(bs);
    toast(on ? ('已开启，每天 ' + tm + ' 推晨报') : '已关闭晨报');
  },

  briefHints(bs) {
    const hint = $('#briefPermHint');
    if (!hint) return;
    if (!bs || !bs.on) { hint.innerHTML = '晨报当前是关闭的。'; return; }
    if (bs.perm === false) {
      hint.innerHTML = '<span style="color:var(--gold)">通知权限还没给，晨报发了你看不到。点「要通知权限」。</span>';
    } else {
      hint.innerHTML = '下一次推送：每天 ' + esc(bs.time || '07:30') + (bs.ai ? '（带 AI 研判）' : '（只要数据）');
    }
  },

  async notifyPerm() {
    await Tea.notifyPerm();
    setTimeout(async () => { try { this.briefHints(await Tea.briefing.state()); } catch (e) {} }, 1200);
  },

  async notifyTest() { await Tea.notifyTest(); toast('已发测试通知，看下拉栏'); },

  async test(btn) {
    btn = btn || { disabled: false, textContent: '' };
    btn.disabled = true; const old = btn.textContent; btn.textContent = '测试中…';
    try {
      const t = await AI.chat([{ role: 'user', content: '只回复两个字：可用' }]);
      toast('连接成功：' + t.slice(0, 20));
    } catch (e) { toast('失败：' + e.message, 4000); }
    btn.disabled = false; btn.textContent = old;
  },

  async clear() {
    const all = await Tea.store.all();
    for (const k in all) await Tea.store.del(k);
    toast('已清空，正在重载…');
    setTimeout(() => location.reload(), 700);
  },

  async diag() {
    const out = $('#diagOut');
    out.innerHTML = '<div class="muted">体检中… <span class="spin"></span></div>';
    const rows = [];
    const probe = async (name, fn) => {
      const t0 = Date.now();
      try { const n = await fn(); rows.push([name, '✅ ' + n + ' 条', (Date.now() - t0) + 'ms']); }
      catch (e) { rows.push([name, '❌ ' + e.message.slice(0, 50), (Date.now() - t0) + 'ms']); }
      out.innerHTML = '<table><tr><th>数据源</th><th>结果</th><th>耗时</th></tr>' +
        rows.map((r) => '<tr><td>' + esc(r[0]) + '</td><td>' + esc(r[1]) + '</td><td>' + esc(r[2]) + '</td></tr>').join('') + '</table>';
    };
    await probe('行情', async () => (await Quotes.load(true)).length);
    await probe('全球快讯', async () => (await Intel.fetchFast()).length);
    await probe('全网新闻', async () => (await Intel.fetchSina(2509)).length);
    await probe('国际要闻', async () => (await Intel.fetchSina(2511)).length);
    await probe('财经要闻', async () => (await Intel.fetchFinance()).length);
    await probe('百度热搜', async () => (await Intel.fetchHot()).length);
    await probe('汇率', async () => Object.keys((await Radar.fx()).rates || {}).length);
  },
};

// ============================================================================
// 行情
// ============================================================================
const Quotes = {
  list: [],
  async load(force) {
    let txt = $('#setWatch').value.trim();
    if (!txt) txt = (await Tea.store.get('watch', DEFAULT_WATCH)) || DEFAULT_WATCH;
    const codes = txt.split('\n').map((l) => l.trim()).filter(Boolean)
      .map((l) => l.split(/\s+/)[0]).filter(Boolean);
    if (!codes.length) return [];
    const raw = await Tea.text(KB.SOURCES.quotes.url + codes.join(','), { encoding: 'gbk', timeout: 12 });
    this.list = this.parse(raw);
    this.render();
    return this.list;
  },
  parse(raw) {
    const out = [];
    (raw || '').split(';').forEach((line) => {
      const m = line.match(/v_([A-Za-z0-9_]+)="(.*)"\s*$/) || line.match(/v_([A-Za-z0-9_]+)="(.*)"/);
      if (!m) return;
      const f = m[2].split('~');
      if (f.length < 6) return;
      const price = parseFloat(f[3]);
      const prev = parseFloat(f[4]);
      if (!isFinite(price)) return;
      const chg = isFinite(prev) ? price - prev : NaN;
      out.push({
        code: m[1], name: f[1] || m[1], sub: f[2] || '',
        price: price, prev: prev, chg: chg,
        pct: isFinite(chg) && prev ? (chg / prev * 100) : NaN,
      });
    });
    return out;
  },
  render() {
    const box = $('#radarQuotes');
    if (!box) return;
    if (!this.list.length) { box.innerHTML = '<div class="empty">没取到行情（检查网络或自选代码）</div>'; return; }
    box.innerHTML = this.list.map((q) => {
      const up = q.pct >= 0;
      const cls = up ? 'up' : 'down';
      const sign = up ? '+' : '';
      return '<div class="quote"><div class="nm"><b>' + esc(q.name) + '</b><span>' + esc(q.code.toUpperCase()) + '</span></div>' +
        '<div class="px"><b>' + q.price.toFixed(q.price >= 100 ? 2 : 3) + '</b>' +
        '<span class="' + cls + '">' + (isFinite(q.pct) ? sign + q.pct.toFixed(2) + '%' : '—') + '</span></div></div>';
    }).join('');
    $('#quoteTime').textContent = new Date().toTimeString().slice(0, 5);
  },
};

// ============================================================================
// 情报
// ============================================================================
const Intel = {
  items: [],
  filter: '全部',
  onlyRelated: true,
  loaded: false,
  tr: {},

  tagAll(text) {
    const hits = [];
    KB.TAGS.forEach((t) => {
      for (const k of t.kw) {
        if (text.indexOf(k) >= 0) { hits.push({ tag: t.tag, weight: t.weight, kw: k }); return; }
      }
    });
    return hits;
  },

  // ---- 东财 7x24 全球快讯 ----
  async fetchFast() {
    const j = await Tea.json(KB.SOURCES.fastNews.url, { timeout: 15 });
    const arr = (j && j.data && j.data.fastNewsList) || [];
    return arr.map((it) => ({
      title: it.title || (it.summary || '').slice(0, 40),
      summary: (it.summary || '').replace(/^【[^】]*】/, ''),
      time: it.showTime || '', src: '全球快讯',
    }));
  },
  // ---- 东财 财经要闻 ----
  async fetchFinance() {
    const j = await Tea.json(KB.SOURCES.finance.url, { timeout: 15 });
    const arr = (j && j.data && j.data.list) || [];
    return arr.map((it) => ({ title: it.title || '', summary: it.summary || '', time: it.showTime || '', src: it.mediaName || '财经要闻' }));
  },
  // ---- 新浪滚播 ----
  async fetchSina(lid) {
    const url = 'https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=' + lid + '&k=&num=30&page=1';
    const j = await Tea.json(url, { timeout: 15 });
    const arr = (j && j.result && j.result.data) || [];
    return arr.map((it) => {
      let t = '';
      try { t = new Date(parseInt(it.ctime, 10) * 1000).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }); } catch (e) {}
      return { title: it.title || '', summary: (it.intro || '').slice(0, 120), time: t, src: (lid === 2511 ? '国际要闻' : '全网热讯'), url: it.url || it.wapurl || '' };
    });
  },
  // ---- 百度热搜 ----
  async fetchHot() {
    const j = await Tea.json(KB.SOURCES.hot.url, { timeout: 15 });
    const out = [];
    const walk = (o) => {
      if (!o) return;
      if (Array.isArray(o)) { o.forEach(walk); return; }
      if (typeof o === 'object') {
        if (typeof o.word === 'string' && o.word.length > 3) out.push({ title: o.word, summary: o.desc || '', time: '', src: '热搜' });
        Object.keys(o).forEach((k) => walk(o[k]));
      }
    };
    walk(j);
    return out;
  },

  async load(force) {
    if (this.loaded && !force) { this.render(); return; }
    $('#intelFeed').innerHTML = '<div class="empty">正在探报… <span class="spin"></span></div>';
    const tasks = [
      ['全球快讯', () => this.fetchFast()],
      ['财经要闻', () => this.fetchFinance()],
      ['全网热讯', () => this.fetchSina(2509)],
      ['国际要闻', () => this.fetchSina(2511)],
      ['百度热搜', () => this.fetchHot()],
    ];
    const all = [];
    const errs = [];
    await Promise.all(tasks.map(async ([nm, fn]) => {
      try { (await fn()).forEach((it) => { if (it.title) all.push(Object.assign({ srcName: nm }, it)); }); }
      catch (e) { errs.push(nm + '：' + e.message); }
    }));

    const seen = new Set();
    this.items = all.filter((it) => {
      const k = it.title.slice(0, 22);
      if (seen.has(k)) return false;
      seen.add(k);
      it.tags = this.tagAll(it.title + ' ' + (it.summary || ''));
      it.w = it.tags.reduce((a, b) => Math.max(a, b.weight), 0);
      return true;
    }).sort((a, b) => (b.w - a.w) || String(b.time).localeCompare(String(a.time)));

    this.loaded = true;
    this.render();
    this.feedClickInit();
    if (errs.length) toast('部分源失败：' + errs.length + ' 个', 3000);
  },

  render() {
    const box = $('#intelFeed');
    let list = this.items;
    if (this.filter !== '全部') list = list.filter((it) => it.tags.some((t) => t.tag === this.filter));
    if (this.onlyRelated) list = list.filter((it) => it.w >= 6);

    const chips = ['全部'].concat(KB.TAGS.map((t) => t.tag));
    const cf = $('#intelFilter');
    if (cf && cf.dataset.done !== '1') {
      cf.dataset.done = '1';
      cf.innerHTML = chips.map((c) => '<div class="o' + (c === '全部' ? ' on' : '') + '" data-c="' + esc(c) + '">' + esc(c) + '</div>').join('');
      cf.addEventListener('click', (e) => {
        const o = e.target.closest('.o'); if (!o) return;
        $$('.o', cf).forEach((x) => x.classList.remove('on'));
        o.classList.add('on');
        this.filter = o.dataset.c;
        this.render();
      });
    }
    const br = $('#btnRelated');
    if (br) br.classList.toggle('pri', this.onlyRelated);

    $('#intelCount').textContent = list.length + ' / ' + this.items.length + ' 条';
    if (!list.length) { box.innerHTML = '<div class="empty">没有命中的情报（试试关掉「只看相关」）</div>'; return; }
    box.innerHTML = list.slice(0, 120).map((it) => {
      const tagHtml = it.tags.slice(0, 3).map((t) =>
        '<span class="tag w' + t.weight + (t.tag.indexOf('军事') === 0 ? ' mil' : '') + (t.tag.indexOf('关税') === 0 ? ' tar' : '') + '">' + esc(t.tag) + '</span>').join('');
      const i = this.items.indexOf(it);
      const zh = this.tr[hash(it.title)];
      return '<div class="item' + (it.w >= 9 ? ' hit' : '') + '" data-i="' + i + '">' +
        '<div class="t">' + esc(it.title) + '</div>' +
        (zh ? '<div class="tiny" style="color:var(--bamboo);margin-top:3px">译：' + esc(zh) + '</div>' : '') +
        '<div class="m">' + tagHtml + '<span>' + esc(it.srcName || it.src || '') + '</span>' +
        (it.time ? '<span>' + esc(it.time) + '</span>' : '') +
        (isForeign(it.title) ? '<span style="color:var(--gold)">外文</span>' : '') + '</div></div>';
    }).join('');
  },

  feedClickInit() {
    const box = $('#intelFeed');
    if (!box || box.dataset.wired === '1') return;
    box.dataset.wired = '1';
    box.addEventListener('click', (e) => {
      const el = e.target.closest('.item'); if (!el) return;
      const it = this.items[+el.dataset.i];
      if (it) this.detail(it);
    });
  },

  detail(it) {
    const zh = this.tr[hash(it.title)] || '';
    const tags = it.tags.map((t) => '<span class="tag w' + t.weight + '">' + esc(t.tag) + '</span>').join(' ');
    Sheet.open(
      '<h2>情报详情</h2>' +
      '<div class="md" style="font-size:14px">' + esc(it.title) + '</div>' +
      (it.summary ? '<div class="muted" style="margin-top:8px">' + esc(it.summary) + '</div>' : '') +
      (zh ? '<div class="verdict" style="margin-top:10px">译：' + esc(zh) + '</div>' : '') +
      '<div class="m" style="margin-top:10px">' + tags + ' <span class="tiny">' + esc(it.srcName || '') + ' ' + esc(it.time || '') + '</span></div>' +
      '<div class="row grow" style="margin-top:14px">' +
      '<button class="btn pri sm" onclick="Intel.ai(\'' + hash(it.title) + '\')">让军师分析</button>' +
      '<button class="btn sm gho" onclick="Intel.translate(\'' + hash(it.title) + '\')">译成中文</button>' +
      '<button class="btn sm gho" onclick="TeaAPI.copy(' + JSON.stringify(JSON.stringify(it.title)) + ');toast(\'已复制\')">复制</button>' +
      '<button class="btn sm gho" onclick="Sheet.close()">关闭</button>' +
      '</div>'
    );
  },

  find(h) { return this.items.find((x) => hash(x.title) === h); },

  async translate(h) {
    const it = this.find(h); if (!it) return;
    if (this.tr[h]) { toast('已经译过了'); return; }
    if (!AI.ready()) { toast('翻译需要 API Key（设置页）'); return; }
    Sheet.open('<h2>翻译中</h2><div class="md"><span class="muted">译中… <span class="spin"></span></span></div>');
    try {
      const t = await AI.chat([{ role: 'user', content: '把下面这条新闻标题翻译成简体中文，只输出译文，不要解释、不要引号：\n' + it.title }]);
      this.tr[h] = t.trim();
      Tea.store.set('tr.' + h, this.tr[h]);
      Sheet.close(); this.render(); toast('已翻译');
    } catch (e) { Sheet.close(); toast('翻译失败：' + e.message, 3500); }
  },

  async translateAll(btn) {
    if (!AI.ready()) { toast('翻译需要 API Key（设置页）'); return; }
    const targets = this.items.filter((it) => isForeign(it.title) && !this.tr[hash(it.title)]).slice(0, 12);
    if (!targets.length) { toast('当前没有需要翻译的外文情报'); return; }
    btn.disabled = true; const old = btn.textContent;
    let ok = 0;
    for (let i = 0; i < targets.length; i++) {
      btn.textContent = '译 ' + (i + 1) + '/' + targets.length;
      try {
        const t = await AI.chat([{ role: 'user', content: '把下面这条新闻标题翻译成简体中文，只输出译文，不要解释、不要引号：\n' + targets[i].title }]);
        this.tr[hash(targets[i].title)] = t.trim();
        Tea.store.set('tr.' + hash(targets[i].title), t.trim());
        ok++;
      } catch (e) { /* 跳过 */ }
    }
    btn.disabled = false; btn.textContent = old;
    this.render();
    toast('译了 ' + ok + '/' + targets.length + ' 条');
  },

  async ai(h) {
    const it = this.find(h); if (!it) return;
    if (!AI.ready()) { toast('先去「设置」填 API Key'); return; }
    Sheet.open('<h2>军师读情报</h2><div id="intelAi" class="md"><span class="muted">推演中… <span class="spin"></span></span></div>');
    try {
      const b = Setting.biz;
      const p = '【我的厂情】品类 ' + (b.cat || '未填') + '；产能 ' + (b.cap || '未填') + '；所在地 ' + (b.addr || '未填') + '；现销路 ' + (b.now || '未填') +
        '\n【这条情报】' + it.title + (it.summary ? '\n' + it.summary : '') +
        '\n\n请你以军师身份：①这条消息对我的茶叶生意到底有没有实质影响（没影响就直说没影响，别硬找）？②如果有，传导链条是什么、大概多久到；③我明天该做什么动作，或者该盯什么信号。250 字内。';
      const t = await AI.chat([{ role: 'system', content: KB.SYSTEM }, { role: 'user', content: p }]);
      $('#intelAi').innerHTML = md2html(t);
    } catch (e) { $('#intelAi').innerHTML = '<span class="muted">失败：' + esc(e.message) + '</span>'; }
  },
};

// ============================================================================
// 舆图（首页）
// ============================================================================
const Radar = {
  fxData: null,
  async fx() {
    if (this.fxData && Date.now() - this.fxData.t < 600000) return this.fxData.v;
    const j = await Tea.json(KB.SOURCES.fx.url, { timeout: 15 });
    this.fxData = { t: Date.now(), v: j };
    return j;
  },

  async refresh(force) {
    $('#radarMetrics').innerHTML = '<div class="metric"><div class="k">正在探报…</div><div class="v"><span class="spin"></span></div></div>';
    await Promise.all([
      Quotes.load(force).catch(() => {}),
      this.fx().catch(() => null),
      Intel.load(force).catch(() => {}),
    ]);
    this.renderMetrics();
    this.renderHot();
    $('#radarTime').textContent = new Date().toTimeString().slice(0, 5);

    const sub = $('#hdSub');
    const q = Quotes.list[0];
    sub.innerHTML = q ? (esc(q.name) + ' ' + q.price + (isFinite(q.pct) ? ' <span class="' + (q.pct >= 0 ? 'up' : 'down') + '">' + (q.pct >= 0 ? '+' : '') + q.pct.toFixed(2) + '%</span>' : '')) : '帐中看舆图';
  },

  renderMetrics() {
    const fx = this.fxData && this.fxData.v;
    const cny = fx && fx.rates ? fx.rates.CNY : null;
    const q = (code) => Quotes.list.find((x) => x.code.toLowerCase() === code);
    const mixue = q('hk02097'), gumu = q('hk01364');
    const m = [
      { k: '美元/人民币', v: cny ? cny.toFixed(3) : '—', s: '' },
      { k: '茶叶出口均价', v: KB.EXPORT.avg_price_usd_kg, s: '美元/kg', cls: 'down' },
      { k: '蜜雪集团', v: mixue ? mixue.price.toFixed(2) : '—', s: mixue && isFinite(mixue.pct) ? (mixue.pct >= 0 ? '+' : '') + mixue.pct.toFixed(2) + '%' : '', cls: mixue && mixue.pct >= 0 ? 'up' : 'down' },
      { k: '古茗', v: gumu ? gumu.price.toFixed(2) : '—', s: gumu && isFinite(gumu.pct) ? (gumu.pct >= 0 ? '+' : '') + gumu.pct.toFixed(2) + '%' : '', cls: gumu && gumu.pct >= 0 ? 'up' : 'down' },
      { k: '全球市场 CAGR', v: KB.GLOBAL.market_cagr + '%', s: '至2032' },
      { k: '中国绿茶占出口', v: KB.EXPORT.green.pct_vol + '%', s: '数量占比' },
    ];
    $('#radarMetrics').innerHTML = m.map((x) =>
      '<div class="metric"><div class="k">' + esc(x.k) + '</div><div class="v">' + esc(String(x.v)) +
      (x.s ? '<small class="' + (x.cls || '') + '">' + esc(x.s) + '</small>' : '') + '</div></div>').join('');
  },

  renderHot() {
    const hot = Intel.items.filter((it) => it.w >= 8).slice(0, 6);
    const box = $('#radarHot');
    if (!hot.length) { box.innerHTML = '<div class="muted">暂无高优先级情报。</div>'; return; }
    box.innerHTML = hot.map((it) => {
      const tag = it.tags[0] || { tag: '—', weight: 5 };
      return '<div class="item' + (it.w >= 9 ? ' hit' : '') + '"><div class="t">' + esc(it.title) + '</div>' +
        '<div class="m"><span class="tag w' + tag.weight + '">' + esc(tag.tag) + '</span>' +
        (it.time ? '<span>' + esc(it.time) + '</span>' : '') + '</div></div>';
    }).join('');
  },

  snapshot() {
    const fx = (this.fxData && this.fxData.v && this.fxData.v.rates) || {};
    const qs = Quotes.list.map((q) => q.name + ' ' + q.price + (isFinite(q.pct) ? ' (' + q.pct.toFixed(2) + '%)' : '')).join('；');
    const news = Intel.items.slice(0, 22).map((it, i) => (i + 1) + '. ' + it.title + ' [' + it.tags.map((t) => t.tag).join('/') + ']').join('\n');
    const b = Setting.biz;
    return [
      '【我的厂情】品类：' + (b.cat || '未填') + '；产能：' + (b.cap || '未填') + '；所在地：' + (b.addr || '未填') + '；目前销路：' + (b.now || '未填'),
      '【实时行情】' + (qs || '未取到'),
      '【汇率】USD/CNY ' + (fx.CNY || '?') + '，EUR ' + (fx.EUR || '?') + '，JPY ' + (fx.JPY || '?') + '，RUB ' + (fx.RUB || '?'),
      '【行业底盘】2025 中国茶叶出口 ' + KB.EXPORT.vol_wan_tons + ' 万吨(+' + KB.EXPORT.vol_yoy + '%)、' +
        KB.EXPORT.val_usd_yi + ' 亿美元(+' + KB.EXPORT.val_yoy + '%)，均价 ' + KB.EXPORT.avg_price_usd_kg + ' 美元/kg；' +
        '全球产量 ' + KB.GLOBAL.prod_wan_tons + ' 万吨，市场 CAGR ' + KB.GLOBAL.market_cagr + '%',
      '【今日情报】\n' + (news || '未取到'),
    ].join('\n\n');
  },

  async analyse() {
    const box = $('#radarVerdict');
    if (!AI.ready()) { box.innerHTML = '<span class="muted">还没填 API Key —— 去「设置」页填一个（推荐 DeepSeek）。</span>'; return; }
    box.innerHTML = '<span class="muted">军师正在看舆图… <span class="spin"></span></span>';
    try {
      const prompt = this.snapshot() + '\n\n请以军师身份给出今天的研判：'
        + '①今天这几条情报里，哪几条真正会影响我的茶叶生意，为什么，我该做什么动作；'
        + '②结合当前行情与汇率，我现在最该抓的一个机会是什么；'
        + '③一个具体到明天就能动手的动作。控制在 350 字内，不要客套。';
      const t = await AI.chat([{ role: 'system', content: KB.SYSTEM }, { role: 'user', content: prompt }]);
      box.innerHTML = '<div class="verdict md">' + md2html(t) + '</div>';
    } catch (e) {
      box.innerHTML = '<span class="muted">失败：' + esc(e.message) + '</span>';
    }
  },
};

// ============================================================================
// 决策
// ============================================================================
const Decide = {
  ans: {},
  render() {
    const box = $('#decideForm');
    box.innerHTML = KB.DECIDE.questions.map((q) =>
      '<label>' + esc(q.q) + '</label><div class="pick" data-k="' + esc(q.key) + '">' +
      q.opts.map((o) => '<div class="o" data-v="' + esc(o) + '">' + esc(o) + '</div>').join('') + '</div>').join('');
    box.addEventListener('click', (e) => {
      const o = e.target.closest('.o'); if (!o) return;
      const p = o.parentElement;
      $$('.o', p).forEach((x) => x.classList.remove('on'));
      o.classList.add('on');
      this.ans[p.dataset.k] = o.dataset.v;
    });
  },
  reset() { this.ans = {}; $$('#decideForm .o').forEach((o) => o.classList.remove('on')); $('#decideOut').style.display = 'none'; $('#decideAI').style.display = 'none'; },

  score(a) {
    const s = {};
    KB.DECIDE.rules.forEach((r) => {
      let hit = false;
      try { hit = r.when(a); } catch (e) { hit = false; }
      if (hit) for (const k in r.score) s[k] = (s[k] || 0) + r.score[k];
    });
    return Object.keys(s).map((k) => ({ k: k, v: s[k] })).sort((x, y) => y.v - x.v);
  },

  verdict(a) {
    let ex = 0, dom = 0;
    const why = [];
    if (a.cert === '齐备') { ex += 35; why.push('认证齐备，出口门槛这一关你已经过了'); }
    if (a.cert === '没有') { ex -= 10; dom += 10; why.push('没有出口认证，先别碰欧盟/日本，那是白跑'); }
    if (a.money === '宽') { ex += 15; why.push('资金够，可以做长线的品牌和独立站'); }
    if (a.money === '紧') { dom += 15; why.push('资金紧，先做回款快的内销代工，别烧跨境电商广告'); }
    if (a.team === '没有' || a.team === '有1-2人') { dom += 12; why.push('没有内容团队，B2C 直播会很吃力，先走 B2B'); }
    if (a.team === '有成熟团队') { ex += 12; why.push('有团队，跨境电商和内容电商可以抓紧上'); }
    if (a.cat === '白茶/普洱') { ex += 20; why.push('白茶/普洱在海外是高溢价品类（均价 11~30 美元/kg），值得直接卖终端'); }
    if (a.cat === '大宗绿茶') { dom += 12; why.push('大宗绿茶出口均价只有 3.4 美元/kg，出海等于白干，不如转做新茶饮原料'); }
    if (a.cat === '红茶/黑茶') { ex += 10; why.push('红茶在中亚/俄罗斯有结构性空档（西方品牌撤出）'); }
    if (a.cat === '乌龙/茉莉') { ex += 12; why.push('乌龙/茉莉在日韩与北美有稳定溢价'); }
    if (a.goods === '有区域品牌') { dom += 10; why.push('已有区域品牌，内销做私域复购成本最低'); }

    const total = Math.abs(ex) + Math.abs(dom) || 1;
    const exPct = Math.round(Math.max(0, ex) / total * 100);
    const domPct = Math.round(Math.max(0, dom) / total * 100);
    let head;
    if (ex >= dom + 15) head = '<b>结论：主攻出口。</b>你现在的牌面更适合往外打。';
    else if (dom >= ex + 15) head = '<b>结论：主攻国内。</b>先把内销的结构升级了，再谈出海。';
    else head = '<b>结论：两条腿走。</b>出口小步试探（一个市场、一个品类），内销同步升级渠道。';

    return { head: head, why: why, ex: exPct, dom: domPct };
  },

  async run() {
    const a = this.ans;
    const miss = KB.DECIDE.questions.filter((q) => !a[q.key]);
    if (miss.length) { toast('还有 ' + miss.length + ' 项没选：' + miss[0].q, 2600); return; }

    const rank = this.score(a);
    const v = this.verdict(a);
    const max = rank.length ? rank[0].v : 1;

    let html = '<h2>军师定策</h2>';
    html += '<div class="verdict">' + v.head + '</div>';
    html += '<h3>出口 / 内销 权重</h3>';
    html += '<div class="tiny">出口 ' + v.ex + '%</div><div class="bar"><i style="width:' + v.ex + '%"></i></div>';
    html += '<div class="tiny" style="margin-top:6px">内销 ' + v.dom + '%</div><div class="bar"><i style="width:' + v.dom + '%"></i></div>';
    if (v.why.length) html += '<h3>依据</h3><ul class="muted">' + v.why.map((w) => '<li>' + esc(w) + '</li>').join('') + '</ul>';

    html += '<h3>先打哪一仗（按优先级）</h3>';
    html += rank.slice(0, 7).map((r, i) =>
      '<div class="rank"><div class="no">' + (i + 1) + '</div><div class="bd"><b>' + esc(r.k) + '</b>' +
      '<div class="bar"><i style="width:' + Math.round(r.v / max * 100) + '%"></i></div></div>' +
      '<div class="sc">' + r.v + '</div></div>').join('');

    $('#decideOut').innerHTML = html;
    $('#decideOut').style.display = 'block';
    $('#decideOut').scrollIntoView({ behavior: 'smooth', block: 'start' });

    // AI 详策
    if (AI.ready()) {
      $('#decideAI').style.display = 'block';
      $('#decideAIBody').innerHTML = '<span class="muted">军师正在推演… <span class="spin"></span></span>';
      try {
        const prompt = '【我的情况】\n' + KB.DECIDE.questions.map((q) => q.q + ' ' + (a[q.key] || '')).join('\n') +
          '\n\n【规则引擎给出的排序】' + rank.slice(0, 7).map((r, i) => (i + 1) + '.' + r.k + '(' + r.v + ')').join('，') +
          '\n\n【行业底盘】2025 中国出口 ' + KB.EXPORT.vol_wan_tons + ' 万吨、均价 ' + KB.EXPORT.avg_price_usd_kg +
          ' 美元/kg；绿茶占 ' + KB.EXPORT.green.pct_vol + '%；品类均价：绿茶 3.4 / 乌龙 7.4 / 茉莉 8.5 / 白茶 11.2 / 熟普 30.1（美元/kg）；' +
          '全球市场 CAGR ' + KB.GLOBAL.market_cagr + '%；2026 年出口环境受关税/转口监管/汇率主导。' +
          '\n\n请你做三件事：' +
          '①指出上面这个排序里哪一条我认为最优先、但其实是个坑；' +
          '②给出未来 90 天的具体动作（分月，带可验证的数字目标）；' +
          '③用「把梳子卖给和尚」的思路，给我 3 个别人想不到的卖法，每个都要具体到客户是谁、话术怎么说。' +
          '不要客套，不要重复我已知的常识。';
        const t = await AI.chat([{ role: 'system', content: KB.SYSTEM }, { role: 'user', content: prompt }]);
        $('#decideAIBody').innerHTML = md2html(t);
      } catch (e) {
        $('#decideAIBody').innerHTML = '<span class="muted">AI 推演失败：' + esc(e.message) + '</span>';
      }
    } else {
      $('#decideAI').style.display = 'block';
      $('#decideAIBody').innerHTML = '<span class="muted">去「设置」填个 API Key，军师还能给你 90 天作战计划和 3 个旁人想不到的卖法。</span>';
    }
  },
};

// ============================================================================
// 妙计（把梳子卖给和尚）
// ============================================================================
const Ideas = {
  last: '',
  init() {
    const box = $('#trickList');
    if (box.dataset.done === '1') return;
    box.dataset.done = '1';
    box.innerHTML = KB.TRICKS.map((t, i) =>
      '<div class="rank" data-i="' + i + '" style="cursor:pointer"><div class="no">' + (i + 1) + '</div>' +
      '<div class="bd"><b>' + esc(t.t) + '</b><div class="tiny">' + esc(t.scene) + ' · ' + esc(t.who) + '</div>' +
      '<div class="muted lv" style="display:none">' + esc(t.line) + '</div></div></div>').join('');
    box.addEventListener('click', (e) => {
      const r = e.target.closest('.rank'); if (!r) return;
      const d = r.querySelector('.lv'); if (d) d.style.display = d.style.display === 'none' ? 'block' : 'none';
    });
  },
  pick() {
    const t = KB.TRICKS[Math.floor(Math.random() * KB.TRICKS.length)];
    $('#ideaInput').value = '我想试试：' + t.scene + '（对象：' + t.who + '）';
    toast('换个场景试试');
  },
  basePrompt(scene) {
    const b = Setting.biz;
    return '【我的厂情】品类 ' + (b.cat || '未填') + '；产能 ' + (b.cap || '未填') + '；所在地 ' + (b.addr || '未填') + '；现在销路 ' + (b.now || '未填') +
      '\n【我要攻克的对象】' + (scene || '未指定') +
      '\n\n请用「把梳子卖给和尚」的思路给方案。硬要求：' +
      '①先拆解这个对象真正的痛点是什么（不要假设他需要茶）；' +
      '②给出 5 个具体卖法，每个必须写明：卖给谁（决策人角色）、卖的是什么（不是茶本身，是解决方案）、报价锚点、第一句话怎么说；' +
      '③指出哪一个最容易先跑通（投入最小、回款最快），以及第一步怎么做；' +
      '④提醒我 1 个容易踩的坑。用短标题 + 表格，不要空话。';
  },
  async gen() {
    const scene = $('#ideaInput').value.trim();
    if (!scene) { toast('先写个场景或人群'); return; }
    if (!AI.ready()) { toast('先去「设置」填 API Key'); return; }
    const box = $('#ideaOut');
    box.style.display = 'block';
    $('#ideaBody').innerHTML = '<span class="muted">军师正在想妙计… <span class="spin"></span></span>';
    try {
      const t = await AI.chat([{ role: 'system', content: KB.SYSTEM }, { role: 'user', content: this.basePrompt(scene) }]);
      this.last = t;
      $('#ideaBody').innerHTML = md2html(t);
    } catch (e) { $('#ideaBody').innerHTML = '<span class="muted">失败：' + esc(e.message) + '</span>'; }
  },
  async save() {
    if (!this.last) { toast('先生成再说'); return; }
    const r = await Tea.save('茶叶军师-妙计-' + Date.now() + '.md', '# 把梳子卖给和尚\n\n' + this.last);
    toast('已存到：' + (r.path || '').split('/').slice(-2).join('/'));
  },
  async share() { if (this.last) { await Tea.share('茶叶军师·妙计', this.last); } else toast('先生成再说'); },
};

// ============================================================================
// 兵法（知识库）
// ============================================================================
const Book = {
  rendered: false,
  render() {
    if (this.rendered) return;
    this.rendered = true;
    const g = KB.GLOBAL, e = KB.EXPORT;
    $('#kbGlobal').innerHTML = [
      ['全球产量', g.prod_wan_tons, '万吨', g.prod_yoy >= 0 ? 'up' : 'down'],
      ['亚洲占比', g.asia_pct + '%', '', ''],
      ['2025 市场', g.market_usd_yi_2025, '亿美元', ''],
      ['2032 预计', g.market_usd_yi_2032, '亿美元', 'up'],
    ].map((x) => '<div class="metric"><div class="k">' + x[0] + '</div><div class="v">' + x[1] + (x[2] ? '<small>' + x[2] + '</small>' : '') + '</div></div>').join('');
    $('#kbVerdict').textContent = g.note;

    $('#kbExport').innerHTML = [
      ['出口量', e.vol_wan_tons, '万吨 +' + e.vol_yoy + '%', 'up'],
      ['出口额', e.val_usd_yi, '亿美元 +' + e.val_yoy + '%', 'up'],
      ['出口均价', e.avg_price_usd_kg, '美元/kg', 'down'],
      ['绿茶占比', e.green.pct_vol + '%', '数量', ''],
    ].map((x) => '<div class="metric"><div class="k">' + x[0] + '</div><div class="v">' + x[1] + '<small class="' + x[3] + '">' + x[2] + '</small></div></div>').join('');

    const maxP = 40;
    $('#kbPrice').innerHTML = KB.PRICE.map((p) =>
      '<div class="rank"><div class="no" style="width:auto;flex:0 0 76px;font-size:12px">' + esc(p.cat) + '</div>' +
      '<div class="bd"><div class="bar"><i style="width:' + Math.round(p.usd / maxP * 100) + '%"></i></div>' +
      '<div class="tiny">' + esc(p.note) + '</div></div>' +
      '<div class="sc">$' + p.usd + '</div></div>').join('');

    $('#kbMarkets').innerHTML = KB.MARKETS.map((m) =>
      '<div style="padding:9px 0;border-bottom:1px solid var(--line)">' +
      '<b style="font-size:13.5px">' + esc(m.region) + '</b> <span class="tag w6">' + esc(m.level) + '</span> <span class="tag w5">风险' + esc(m.risk) + '</span>' +
      '<div class="tiny" style="margin-top:3px">品类：' + esc(m.cat) + '　动作：' + esc(m.action) + '</div>' +
      '<div class="muted" style="margin-top:2px">' + esc(m.note) + '</div></div>').join('');

    $('#kbChannels').innerHTML = KB.CHANNELS.map((c) =>
      '<h3>' + esc(c.g) + '</h3>' + c.items.map((it) =>
        '<div class="rank"><div class="no" style="width:34px;flex:0 0 34px;font-size:11px;color:' +
        (it.roi >= 5 ? 'var(--red)' : it.roi >= 4 ? 'var(--gold)' : 'var(--faint)') + '">' + '★'.repeat(Math.min(5, it.roi)) + '</div>' +
        '<div class="bd"><b>' + esc(it.n) + '</b><div class="tiny">' + esc(it.note) + '</div></div></div>').join('')).join('');

    $('#kbProv').innerHTML = KB.EXPORT.provinces.map((p, i) =>
      '<div class="rank"><div class="no">' + (i + 1) + '</div><div class="bd"><b>' + esc(p.name) + '</b>' +
      (p.note ? '<div class="tiny">' + esc(p.note) + '</div>' : '') + '</div>' +
      '<div class="sc">' + (p.vol != null ? p.vol + '万吨' : (p.val != null ? p.val + '亿美元' : '—')) + '</div></div>').join('');
  },
};

// ============================================================================
// 通用：底部弹层 / 单选组 / 外文判定
// ============================================================================
const Sheet = {
  open(html) { $('#sheetBody').innerHTML = html; $('#sheet').classList.add('on'); },
  close() { $('#sheet').classList.remove('on'); $('#sheetBody').innerHTML = ''; },
};
function pickInit(sel, val, cb) {
  const box = $(sel); if (!box) return;
  const v = String(val === true ? '1' : val === false ? '0' : (val == null ? '' : val));
  $$('.o', box).forEach((o) => o.classList.toggle('on', o.dataset.v === v));
  box.onclick = (e) => {
    const o = e.target.closest('.o'); if (!o) return;
    $$('.o', box).forEach((x) => x.classList.remove('on'));
    o.classList.add('on');
    if (cb) cb(o.dataset.v);
  };
}
function pickVal(sel) { const o = $('.o.on', $(sel)); return o ? o.dataset.v : ''; }

/** 判断是不是外文（中文字符占比太低就是） */
function isForeign(s) {
  if (!s) return false;
  const cjk = (s.match(/[\u4e00-\u9fff]/g) || []).length;
  const letters = (s.match(/[A-Za-z\u0400-\u04ff\u0600-\u06ff]/g) || []).length;
  // 假名/谚文出现就是外文（日/韩），不用看比例
  const jk = (s.match(/[\u3040-\u30ff\uac00-\ud7af]/g) || []).length;
  if (s.length < 8) return false;
  if (jk >= 6) return true;
  if (letters < 10) return false;
  // 中文字在「中文+字母」里的占比，低于一半就算外文
  return cjk / (cjk + letters) < 0.5;
}
function hash(s) { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) >>> 0; return h.toString(36); }

// ============================================================================
// 军师晨报
// ============================================================================
const Brief = {
  text: '', time: '',
  async load() {
    const r = await Tea.briefing.get();
    this.text = r.text || ''; this.time = r.time || '';
    this.render();
  },
  render() {
    const box = $('#briefBody'); if (!box) return;
    $('#briefTime').textContent = this.time || '未生成';
    if (!this.text) {
      box.className = 'md muted';
      box.innerHTML = '还没有晨报。可以现在生成一份，或去「设置」开启每天定时推送。';
      return;
    }
    box.className = 'md';
    box.innerHTML = md2html(this.text);
  },
  async gen(btn) {
    btn = btn || {}; const old = btn.textContent;
    if (btn.textContent !== undefined) { btn.disabled = true; btn.textContent = '生成中…'; }
    try {
      const r = await Tea.briefing.run(true);
      this.text = r.text || ''; this.time = r.time || '';
      this.render();
      toast('晨报已生成');
    } catch (e) { toast('生成失败：' + e.message, 3500); }
    if (old !== undefined) { btn.disabled = false; btn.textContent = old; }
  },
  async copy() { if (!this.text) return toast('还没有晨报'); await Tea.copy(this.text); toast('已复制'); },
  async share() { if (!this.text) return toast('还没有晨报'); await Tea.share('茶叶军师·晨报', this.text); },
  open() {
    Router.go('radar');
    setTimeout(() => { const c = $('#briefCard'); if (c) c.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, 120);
  },
};
window.__showBriefing = () => Brief.open();

// ============================================================================
// 客户台账
// ============================================================================
const Ledger = {
  items: [], filter: '全部', onlyDue: false, loaded: false,
  TYPES: ['批发商', '新茶饮/餐饮', '企业采购', '外贸/出口', '商超/渠道', '电商/直播', '其他'],
  STAT: ['待跟进', '已报价', '成交', '流失', '复购'],

  async load() {
    try { const t = await Tea.readDoc('ledger.json'); this.items = t ? JSON.parse(t) : []; }
    catch (e) { this.items = []; }
    if (!Array.isArray(this.items)) this.items = [];
    this.loaded = true;
  },
  async persist() { await Tea.writeDoc('ledger.json', JSON.stringify(this.items)); },

  today() { const d = new Date(); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); },
  isDue(it) {
    if (!it.next) return false;
    if (it.status === '成交' || it.status === '流失') return false;
    return it.next <= this.today();
  },

  stats() {
    const s = { total: this.items.length, due: 0 };
    this.STAT.forEach((k) => { s[k] = 0; });
    this.items.forEach((it) => {
      if (it.status in s) s[it.status]++;
      if (this.isDue(it)) s.due++;
    });
    return s;
  },

  render() {
    if (!this.loaded) return;
    const s = this.stats();
    $('#ledgerStat').textContent = '共 ' + s.total + ' 个客户';
    $('#ledgerMetrics').innerHTML = [
      { k: '待跟进', v: s['待跟进'], c: '' },
      { k: '已报价', v: s['已报价'], c: '' },
      { k: '成交', v: s['成交'] + s['复购'], c: 'up' },
      { k: '该联系了', v: s.due, c: s.due ? 'down' : '' },
    ].map((x) => '<div class="metric"><div class="k">' + x.k + '</div><div class="v ' + x.c + '">' + x.v + '</div></div>').join('');

    const fb = $('#ledgerFilter');
    if (fb && fb.dataset.done !== '1') {
      fb.dataset.done = '1';
      fb.innerHTML = ['全部'].concat(this.STAT).map((c) => '<div class="o" data-c="' + c + '">' + c + '</div>').join('')
        + '<div class="o" data-c="逾期">逾期/今天</div>';
      fb.addEventListener('click', (e) => {
        const o = e.target.closest('.o'); if (!o) return;
        $$('.o', fb).forEach((x) => x.classList.remove('on')); o.classList.add('on');
        this.filter = o.dataset.c; this.onlyDue = o.dataset.c === '逾期'; this.render();
      });
    }

    const q = ($('#ledgerSearch').value || '').trim().toLowerCase();
    let list = this.items.slice();
    if (this.onlyDue || this.filter === '逾期') list = list.filter((it) => this.isDue(it));
    else if (this.filter !== '全部') list = list.filter((it) => it.status === this.filter);
    if (q) list = list.filter((it) => [it.name, it.contact, it.cat, it.note, it.phone, it.type].join(' ').toLowerCase().indexOf(q) >= 0);

    list.sort((a, b) => {
      const da = this.isDue(a) ? 0 : 1, db = this.isDue(b) ? 0 : 1;
      if (da !== db) return da - db;
      return String(b.updated || '').localeCompare(String(a.updated || ''));
    });

    $('#ledgerCount').textContent = list.length + ' / ' + this.items.length;
    const box = $('#ledgerList');
    if (!list.length) { box.innerHTML = '<div class="empty">没有匹配的客户</div>'; return; }
    const si = (st) => Math.max(0, this.STAT.indexOf(st));
    box.innerHTML = list.map((it) => {
      const due = this.isDue(it);
      const info = [
        it.type ? '类型 ' + esc(it.type) : '',
        it.cat ? '品类 ' + esc(it.cat) : '',
        it.quote ? '报价 ' + esc(it.quote) : '',
        (it.contact || it.phone) ? '联系人 ' + esc(it.contact || '') + (it.phone ? ' ' + esc(it.phone) : '') : '',
        it.next ? '下次 ' + esc(it.next) + (due ? ' ⚠' : '') : '',
        it.note ? esc(it.note) : '',
      ].filter(Boolean).join('　·　');
      return '<div class="lead' + (due ? ' due' : '') + '">' +
        '<div class="top"><b>' + esc(it.name) + '</b>' +
        '<span class="sp st s' + si(it.status) + '">' + esc(it.status || '待跟进') + '</span></div>' +
        '<div class="info">' + info + '</div>' +
        '<div class="acts">' +
        '<button class="btn sm gho" onclick="Ledger.edit(\'' + it.id + '\')">编辑</button>' +
        (it.phone ? '<button class="btn sm gho" onclick="TeaAPI.open(\'tel:' + esc(it.phone) + '\')">拨号</button>' : '') +
        '<button class="btn sm gho" onclick="Ledger.next(\'' + it.id + '\')">+7天</button>' +
        '<button class="btn sm gho" onclick="Ledger.askAI(\'' + it.id + '\')">问军师</button>' +
        '</div></div>';
    }).join('');
  },

  async next(id) {
    const it = this.items.find((x) => x.id === id); if (!it) return;
    const d = it.next ? new Date(it.next + 'T00:00:00') : new Date();
    d.setDate(d.getDate() + (it.next ? 7 : 3));
    it.next = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
    it.updated = new Date().toISOString().slice(0, 10);
    await this.persist(); this.render();
    toast('下次跟进改到 ' + it.next);
  },

  edit(id) {
    const it = id ? this.items.find((x) => x.id === id) : null;
    const v = (k, d) => esc(it && it[k] != null ? it[k] : (d || ''));
    const opt = (arr, cur) => arr.map((x) => '<option value="' + esc(x) + '"' + (x === cur ? ' selected' : '') + '>' + esc(x) + '</option>').join('');
    Sheet.open(
      '<h2>' + (it ? '编辑客户' : '新增客户') + '</h2>' +
      '<div class="overlay-form">' +
      '<div class="full"><label>客户/渠道名称 *</label><input type="text" id="lName" value="' + v('name') + '" placeholder="例：杭州××外贸公司"></div>' +
      '<div><label>类型</label><select id="lType">' + opt(this.TYPES, it ? it.type : '批发商') + '</select></div>' +
      '<div><label>状态</label><select id="lStatus">' + opt(this.STAT, it ? it.status : '待跟进') + '</select></div>' +
      '<div><label>联系人</label><input type="text" id="lContact" value="' + v('contact') + '"></div>' +
      '<div><label>电话</label><input type="text" id="lPhone" value="' + v('phone') + '" inputmode="tel"></div>' +
      '<div><label>品类</label><input type="text" id="lCat" value="' + v('cat') + '" placeholder="例：大宗绿茶/白茶"></div>' +
      '<div><label>报价</label><input type="text" id="lQuote" value="' + v('quote') + '" placeholder="例：38元/kg 含税"></div>' +
      '<div><label>数量</label><input type="text" id="lQty" value="' + v('qty') + '" placeholder="例：20吨/年"></div>' +
      '<div><label>下次跟进</label><input type="text" id="lNext" value="' + v('next') + '" placeholder="2026-11-01"></div>' +
      '<div class="full"><label>备注</label><textarea class="sm" id="lNote" placeholder="聊到哪了、对方关心什么、谁拍板">' + v('note') + '</textarea></div>' +
      '</div>' +
      '<div class="row grow" style="margin-top:14px">' +
      '<button class="btn pri" onclick="Ledger.saveForm(\'' + (it ? it.id : '') + '\')">保存</button>' +
      (it ? '<button class="btn gho" style="flex:0 0 auto" onclick="Ledger.del(\'' + it.id + '\')">删除</button>' : '') +
      '<button class="btn gho" style="flex:0 0 auto" onclick="Sheet.close()">取消</button>' +
      '</div>'
    );
  },

  async saveForm(id) {
    const name = $('#lName').value.trim();
    if (!name) { toast('客户名不能空'); return; }
    const data = {
      name: name, type: $('#lType').value, status: $('#lStatus').value,
      contact: $('#lContact').value.trim(), phone: $('#lPhone').value.trim(),
      cat: $('#lCat').value.trim(), quote: $('#lQuote').value.trim(), qty: $('#lQty').value.trim(),
      next: $('#lNext').value.trim(), note: $('#lNote').value.trim(),
    };
    if (id) { const it = this.items.find((x) => x.id === id); Object.assign(it, data); it.updated = this.today(); }
    else { data.id = 'c' + Date.now().toString(36) + Math.random().toString(36).slice(2, 5); data.created = this.today(); data.updated = this.today(); this.items.push(data); }
    await this.persist();
    Sheet.close(); this.render();
    toast('已保存');
  },

  async del(id) {
    const it = this.items.find((x) => x.id === id);
    if (!confirm('删除「' + (it ? it.name : '') + '」？')) return;
    this.items = this.items.filter((x) => x.id !== id);
    await this.persist(); Sheet.close(); this.render();
    toast('已删除');
  },

  showDue() {
    this.onlyDue = true; this.filter = '逾期';
    const fb = $('#ledgerFilter');
    if (fb) $$('.o', fb).forEach((x) => x.classList.toggle('on', x.dataset.c === '逾期'));
    this.render();
    const s = this.stats();
    toast(s.due ? (s.due + ' 个客户该联系了') : '没有到期要跟进的客户');
  },

  async exportCsv() {
    if (!this.items.length) return toast('台账是空的');
    const head = ['客户', '类型', '状态', '联系人', '电话', '品类', '报价', '数量', '下次跟进', '备注', '更新'];
    const q = (s) => '"' + String(s == null ? '' : s).replace(/"/g, '""') + '"';
    const rows = this.items.map((it) => [it.name, it.type, it.status, it.contact, it.phone, it.cat, it.quote, it.qty, it.next, it.note, it.updated].map(q).join(','));
    const csv = '\uFEFF' + [head.map(q).join(',')].concat(rows).join('\r\n');
    const r = await Tea.save('客户台账-' + this.today() + '.csv', csv);
    toast('已导出：' + String(r.path || '').split('/').slice(-2).join('/'), 3500);
  },

  async askAI(id) {
    const it = this.items.find((x) => x.id === id); if (!it) return;
    if (!AI.ready()) return toast('先去「设置」填 API Key');
    Sheet.open('<h2>军师看这个客户</h2><div id="lAsk" class="md"><span class="muted">推演中… <span class="spin"></span></span></div>');
    try {
      const b = Setting.biz;
      const p = '【我的厂情】品类 ' + (b.cat || '未填') + '；产能 ' + (b.cap || '未填') + '；所在地 ' + (b.addr || '未填') +
        '\n【这个客户】' + JSON.stringify(it, null, 1) +
        '\n\n请你以军师身份：①判断这个客户现在处于什么阶段、真正的顾虑是什么；②给我下一步话术（直接能发出去的），尤其如何从「要样品/压价」推到「下单」；③这个客户还有没有我没看到的第二需求（用把梳子卖给和尚的思路）；④提醒我 1 个可能被他套路的地方。控制在 350 字内。';
      const t = await AI.chat([{ role: 'system', content: KB.SYSTEM }, { role: 'user', content: p }]);
      $('#lAsk').innerHTML = md2html(t);
    } catch (e) { $('#lAsk').innerHTML = '<span class="muted">失败：' + esc(e.message) + '</span>'; }
  },
};

// ============================================================================
// 大模型
// ============================================================================
const AI = {
  ready() { return !!(Setting.cfg.url && Setting.cfg.key && Setting.cfg.model); },
  async chat(messages) {
    const c = Setting.cfg;
    if (!c.key) throw new Error('没填 API Key（设置页）');
    if (!c.url) throw new Error('没填接口地址（设置页）');
    const body = JSON.stringify({ model: c.model, messages: messages, temperature: 0.6, stream: false });
    const r = await Tea.http(c.url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + c.key },
      body: body, timeout: 120,
    });
    if (r.status >= 400) {
      let msg = (r.body || '').slice(0, 220);
      try { const j = parseLoose(r.body); if (j.error && j.error.message) msg = j.error.message; } catch (e) {}
      throw new Error('HTTP ' + r.status + ' ' + msg);
    }
    let j;
    try { j = parseLoose(r.body); } catch (e) { throw new Error('返回不是 JSON：' + (r.body || '').slice(0, 120)); }
    const t = j && j.choices && j.choices[0] && j.choices[0].message && j.choices[0].message.content;
    if (!t) throw new Error('接口没返回内容：' + (r.body || '').slice(0, 160));
    return t;
  },
};

// ============================================================================
// 暴露给内联 onclick
// 注意不要导出 Tea —— window.Tea 是原生桥对象，覆盖了就没法联网。
// ============================================================================
Object.assign(window, {
  Router: Router, Setting: Setting, Quotes: Quotes, Intel: Intel, Radar: Radar,
  Decide: Decide, Ideas: Ideas, Book: Book, Ledger: Ledger, Brief: Brief,
  Sheet: Sheet, AI: AI, KB: KB, md2html: md2html, toast: toast,
});

// ============================================================================
// 启动
// ============================================================================
(async function boot() {
  Router.init();
  Decide.render();
  Ideas.init();

  const br = $('#btnRelated');
  if (br) br.addEventListener('click', () => { Intel.onlyRelated = !Intel.onlyRelated; Intel.render(); });

  await Setting.load();

  // 没有 Key 时给个提示
  if (!AI.ready()) {
    $('#radarVerdict').innerHTML = '<span class="muted">还没填大模型 API Key。<br>可以先去「设置」填一个（推荐 DeepSeek，便宜且国内直连），填完这里的研判、决策详策、妙计、翻译就都能用了。<br><br>不填也能用：行情、情报、决策排序、客户台账、兵法库全部本地可用。</span>';
  }

  // 台账
  await Ledger.load();

  // 晨报（已有就直接展示）
  Brief.load();

  // 翻译缓存
  try {
    const all = await Tea.store.all();
    Object.keys(all).forEach((k) => { if (k.indexOf('tr.') === 0) Intel.tr[k.slice(3)] = all[k]; });
  } catch (e) {}

  Radar.refresh();
  Intel.feedClickInit();

  // 从通知点进来 → 直接展开晨报
  Tea.onEvent((name, data) => {
    if (name === 'notifyPerm') toast(data === 'granted' ? '通知权限已给' : '通知权限被拒，只能进 App 看晨报');
  });

  // 手柄：下拉到底部自动刷新情报
  let lastScroll = 0;
  window.addEventListener('scroll', () => {
    const y = window.scrollY + window.innerHeight;
    const h = document.body.scrollHeight;
    if (Router.cur === 'intel' && y > h - 120 && Date.now() - lastScroll > 8000) { lastScroll = Date.now(); Intel.load(true); }
  });
})();
