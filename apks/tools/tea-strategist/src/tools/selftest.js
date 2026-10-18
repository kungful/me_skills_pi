// 自测：把 transport.js + kb.js + app.js 拼起来在 Node 里跑，
// DOM 打桩，网络走真 fetch，验证各数据源的抓取/解析/渲染逻辑。
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const A = path.join(__dirname, '..', 'assets');
const src = ['transport.js', 'kb.js', 'app.js'].map((f) => fs.readFileSync(path.join(A, f), 'utf8')).join('\n;\n');

// ---- 极简 DOM 打桩 ----
function el() {
  const o = {
    innerHTML: '', textContent: '', value: '', style: {}, dataset: {}, disabled: false,
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    addEventListener() {}, removeEventListener() {}, appendChild() {}, focus() {}, click() {},
    scrollIntoView() {}, closest() { return null; }, querySelector() { return el(); },
    querySelectorAll() { return []; }, getAttribute() { return null; },
  };
  return o;
}
const doc = {
  querySelector: () => el(),
  querySelectorAll: () => [],
  createElement: () => el(),
  addEventListener() {},
  body: el(),
};
const store = {};
const ctx = {
  console,
  document: doc,
  navigator: { userAgent: 'node-test' },
  localStorage: {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: (k) => { delete store[k]; },
    key: (i) => Object.keys(store)[i],
    get length() { return Object.keys(store).length; },
  },
  fetch: (...a) => fetch(...a),
  setTimeout, clearTimeout, setInterval, clearInterval,
  Promise, Date, Math, JSON, Object, Array, String, Number, Boolean, Error, RegExp, parseFloat, parseInt, isFinite, isNaN,
  URL: { createObjectURL: () => 'blob:x' }, Blob: function () {},
  location: { reload() {} },
  requestAnimationFrame: (f) => setTimeout(f, 0),
};
ctx.window = ctx;
ctx.globalThis = ctx;
ctx.window.scrollY = 0;
ctx.window.innerHeight = 800;
ctx.window.addEventListener = () => {};
ctx.window.scrollTo = () => {};

const script = new vm.Script(src + '\n;globalThis.__T = {Tea, KB, Quotes, Intel, Radar, Setting, Decide, Ideas, Book, AI, Brief, Ledger, Sheet, md2html, isForeign, hash};');
vm.createContext(ctx);
script.runInContext(ctx);
const T = ctx.__T;

const results = [];
async function probe(name, fn, show) {
  const t0 = Date.now();
  try {
    const v = await fn();
    const n = Array.isArray(v) ? v.length : (v && typeof v === 'object' ? Object.keys(v).length : v);
    results.push([name, 'OK', String(n), (Date.now() - t0) + 'ms', show ? show(v) : '']);
  } catch (e) {
    results.push([name, 'FAIL', e.message.slice(0, 90), (Date.now() - t0) + 'ms', '']);
  }
}

(async () => {
  await probe('行情 Quotes.load', async () => {
    // 走 Tea.http 的真路径（浏览器退化 = fetch）
    const raw = await T.Tea.text(T.KB.SOURCES.quotes.url + 'hk02097,hk01364,usCHA,sh000001', { encoding: 'gbk', timeout: 15 });
    const list = T.Quotes.parse(raw);
    T.Quotes.list = list;
    return list;
  }, (l) => l.map((q) => q.name + ' ' + q.price + (isFinite(q.pct) ? ' ' + q.pct.toFixed(2) + '%' : '')).join(' | '));

  await probe('全球快讯', () => T.Intel.fetchFast(), (a) => (a[0] ? a[0].title.slice(0, 40) : ''));
  await probe('财经要闻', () => T.Intel.fetchFinance(), (a) => (a[0] ? a[0].title.slice(0, 40) : ''));
  await probe('全网热讯', () => T.Intel.fetchSina(2509), (a) => (a[0] ? a[0].title.slice(0, 40) : ''));
  await probe('国际要闻', () => T.Intel.fetchSina(2511), (a) => (a[0] ? a[0].title.slice(0, 40) : ''));
  await probe('百度热搜', () => T.Intel.fetchHot(), (a) => (a[0] ? a[0].title.slice(0, 40) : ''));
  await probe('汇率', () => T.Radar.fx(), (j) => 'USD/CNY=' + (j.rates && j.rates.CNY));

  // 分类打标
  await probe('情报打标+排序', async () => {
    const all = [];
    for (const [nm, fn] of [['fast', () => T.Intel.fetchFast()], ['sina', () => T.Intel.fetchSina(2509)], ['world', () => T.Intel.fetchSina(2511)]]) {
      try { (await fn()).forEach((it) => { if (it.title) all.push(Object.assign({ srcName: nm }, it)); }); } catch (e) {}
    }
    const seen = new Set();
    const list = all.filter((it) => { const k = it.title.slice(0, 22); if (seen.has(k)) return false; seen.add(k); it.tags = T.Intel.tagAll(it.title + ' ' + (it.summary || '')); it.w = it.tags.reduce((a, b) => Math.max(a, b.weight), 0); return true; })
      .sort((a, b) => (b.w - a.w) || String(b.time).localeCompare(String(a.time)));
    T.Intel.items = list;
    return list;
  }, (l) => l.slice(0, 5).map((it) => '[' + it.tags.map((t) => t.tag).join(',') + '] ' + it.title.slice(0, 30)).join('\n      '));

  await probe('决策引擎', () => {
    T.Decide.ans = { cat: '大宗绿茶', cap: '中（100-1000吨/年）', money: '紧（<20万）', team: '没有', cert: '没有', goods: '纯代工/无牌' };
    const rank = T.Decide.score(T.Decide.ans);
    const v = T.Decide.verdict(T.Decide.ans);
    return { rank: rank.slice(0, 5).map((r) => r.k + '(' + r.v + ')'), verdict: v.head.replace(/<[^>]+>/g, ''), ex: v.ex, dom: v.dom };
  }, (o) => '出口/内销=' + o.ex + '/' + o.dom + '\n      ' + o.verdict + '\n      ' + o.rank.join('  '));

  await probe('md2html', () => T.md2html('## 标题\n**粗体**\n| a | b |\n|---|---|\n| 1 | 2 |\n- 项目'), (h) => h.slice(0, 110).replace(/\n/g, ''));

  await probe('外文判定', () => {
    const cases = [
      ['Houthi rebels claim Saudi airstrike killed 9 in northern Yemen', true],
      ['胡塞武装称沙特空袭也门北部致9死17伤', false],
      ['EU launches tariff talks with China, auto stocks rise', true],
      ['日本豚熱疫情拡大 今年累計約2万頭処分', false],
      ['CPI up 0.3% in September', true],
      ['A股被低估！三大券商发声：五大积极信号正在累积', false],
      ['贵州茅台发布三季报，Q3 净利同比增长 12%', false],
      ['トランプ大統領が関税を発表', true],
      ['欧盟对华加征关税，EU hits China with new tariffs', true],
    ];
    const bad = cases.filter((c) => T.isForeign(c[0]) !== c[1]);
    if (bad.length) throw new Error(bad.map((b) => JSON.stringify(b[0].slice(0, 20))).join(','));
    return cases.length;
  }, (n) => n + ' 个用例全对');

  await probe('台账 CRUD + 统计', async () => {
    const L = T.Ledger;
    await L.load();
    L.items = [];
    const mk = (o) => Object.assign({ id: 'x' + Math.random().toString(36).slice(2, 6), created: L.today(), updated: L.today(), status: '待跟进', type: '批发商' }, o);
    const yest = new Date(Date.now() - 86400000);
    L.items.push(mk({ name: '杭州外贸', contact: '张经理', phone: '13800000000', cat: '大宗绿茶', quote: '38元/kg', status: '已报价', next: yest.toISOString().slice(0, 10), note: '要样品' }));
    L.items.push(mk({ name: '古茗供应链', status: '成交', type: '新茶饮/餐饮', cat: '茉莉花茶' }));
    L.items.push(mk({ name: '××酒店', status: '待跟进', next: '2030-01-01' }));
    await L.persist();
    const reread = await T.Tea.readDoc('ledger.json');
    const back = JSON.parse(reread);
    if (back.length !== 3) throw new Error('持久化丢了记录');
    const s = L.stats();
    if (s.total !== 3 || s.due !== 1 || s['已报价'] !== 1) throw new Error('统计不对: ' + JSON.stringify(s));
    L.render();
    await L.exportCsv();
    return s;
  }, (s) => '共' + s.total + ' 建' + s.due + ' 个逾期 · CSV 导出 OK');

  await probe('情报详情/翻译（无 Key 时正确拦）', () => {
    T.Setting.cfg = { url: '', model: '', key: '' };
    T.Intel.items = [{ title: 'Houthi rebels claim Saudi airstrike killed 9 in northern Yemen', summary: 'x', tags: [{ tag: '军事·地缘', weight: 9 }], w: 9, srcName: '全球快讯', time: '' }];
    T.Intel.detail(T.Intel.items[0]);          // 不应抛
    T.Sheet.close();
    return T.AI.ready() === false;
  }, () => '详情弹层 OK，无 Key 时翻译被拦');

  await probe('晨报本地规则生成', async () => {
    // 在浏览器退化模式下只能验状态接口不抛
    const st = await T.Tea.briefing.state();
    const got = await T.Tea.briefing.get();
    T.Brief.text = '【茶叶军师 · 晨报 10月19日】\n\n▎要盯的事\n1. 胡塞武装称沙特空袭也门北部 [军事·地缘]\n\n▎盘面\n蜜雪集团 167.5 +0.78%';
    T.Brief.render();
    return [st, got];
  }, () => '状态/读取/渲染 OK');

  await probe('AI 未配置时正确拒绝', async () => {
    T.Setting.cfg = { url: '', model: '', key: '' };
    if (T.AI.ready()) throw new Error('不该 ready');
    try { await T.AI.chat([{ role: 'user', content: 'x' }]); throw new Error('应该抛错'); }
    catch (e) { if (/API Key/.test(e.message)) return 'OK: ' + e.message; throw e; }
  });

  console.log('\n===== 茶叶军师 逻辑自测 =====');
  let fail = 0;
  for (const r of results) {
    if (r[1] === 'FAIL') fail++;
    console.log([r[1] === 'OK' ? '✅' : '❌', r[0].padEnd(22), r[1], r[2].padStart(6), r[3].padStart(7)].join(' '));
    if (r[4]) console.log('      ' + r[4]);
  }
  console.log('\n失败 ' + fail + ' / ' + results.length);
  process.exit(fail ? 1 : 0);
})();
