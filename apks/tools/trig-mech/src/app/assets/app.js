/* ===== 界面 / 路由 ===== */
const $ = s => document.querySelector(s);
const $$ = s => Array.prototype.slice.call(document.querySelectorAll(s));

function toast(m) {
  const t = $('#toast');
  t.textContent = m;
  t.classList.add('show');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove('show'), 1600);
}
function nat(fn, arg) {
  try { if (window.Native && Native[fn]) Native[fn](arg); } catch (e) { }
}
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/* ---------------- 状态 ---------------- */
const ST = {
  tab: (location.hash || '').replace('#', '') || localStorage.getItem('tm_tab') || 'tri',
  tri: { mode: 'ab', ref: 'A', ratio: null, v: {} },
  ratio: { theta: 30, k: 'sin' },
};

/* 已知量：比值 → 涉及哪两条边（随参考角变化，这就是关键） */
function sidesOf(k, ref) {
  const opp = ref === 'A' ? 'a' : 'b';
  const adj = ref === 'A' ? 'b' : 'a';
  if (k === 'sin') return [opp, 'c'];
  if (k === 'cos') return [adj, 'c'];
  return [opp, adj];
}

/* ================================================================
   视图 1：三角
   ================================================================ */
const VTRI = {
  html() {
    return `
    <div class="card">
      <h3>实时三角形</h3>
      <div class="hint">角一定要先认准：<b>看哪个角，哪条边才是「对边」</b>。切换下面两个按钮，看标签怎么换。</div>
      <div class="chips" id="triRef" style="margin-bottom:9px">
        <div class="chip" data-r="A">以 A 角看</div>
        <div class="chip" data-r="B">以 B 角看</div>
      </div>
      <div class="triwrap" id="triSvg"></div>
      <div class="legend">
        <div class="lg"><i style="background:var(--opp)"></i>对边（对着参考角的边）</div>
        <div class="lg"><i style="background:var(--adj)"></i>邻边（挨着参考角的直角边）</div>
        <div class="lg"><i style="background:var(--hyp)"></i>斜边（对着直角的边）</div>
      </div>
      <div class="chips blue" id="triHot" style="margin-top:4px">
        <div class="chip" data-k="sin">sin 看哪两条</div>
        <div class="chip" data-k="cos">cos 看哪两条</div>
        <div class="chip" data-k="tan">tan 看哪两条</div>
      </div>
    </div>

    <div class="card">
      <h3>已知条件</h3>
      <div class="chips" id="triModes" style="margin-bottom:10px"></div>
      <div class="grid2" id="triInputs"></div>
      <div id="triErr"></div>
    </div>

    <div class="card sub">
      <h3>结果</h3>
      <div class="big" id="triBig"></div>
      <div id="triRows"></div>
      <div id="triSteps"></div>
    </div>

    <div class="card">
      <h3>三条边到底是哪三条</h3>
      <div id="triExplain"></div>
    </div>
    <div class="foot">全部离线计算 · 单位可混用，只要两两同名</div>`;
  },

  init() {
    // 默认值
    T.modes.forEach(m => { m.fields.forEach(f => { if (ST.tri.v[f.k] == null) ST.tri.v[f.k] = f.k === 'A' ? 30 : 1; }); });
    ST.tri.v.a = 3; ST.tri.v.b = 4; ST.tri.v.c = 5; ST.tri.v.A = 30;
    if (!ST.tri.mode) ST.tri.mode = 'ab';

    $('#triModes').innerHTML = T.modes.map(m =>
      `<div class="chip ${m.id === ST.tri.mode ? 'on' : ''}" data-m="${m.id}">${m.label}</div>`).join('');
    $('#triModes').addEventListener('click', e => {
      const c = e.target.closest('[data-m]'); if (!c) return;
      ST.tri.mode = c.dataset.m; ST.tri.ratio = null;
      $$('#triModes .chip').forEach(x => x.classList.toggle('on', x.dataset.m === ST.tri.mode));
      VTRI.paint(true);
    });
    $('#triRef').addEventListener('click', e => {
      const c = e.target.closest('[data-r]'); if (!c) return;
      ST.tri.ref = c.dataset.r; nat('buzz', 12);
      $$('#triRef .chip').forEach(x => x.classList.toggle('on', x.dataset.r === ST.tri.ref));
      VTRI.legend(); VTRI.paint();
    });
    $('#triHot').addEventListener('click', e => {
      const c = e.target.closest('[data-k]'); if (!c) return;
      ST.tri.ratio = (ST.tri.ratio === c.dataset.k) ? null : c.dataset.k;
      $$('#triHot .chip').forEach(x => x.classList.toggle('on', x.dataset.k === ST.tri.ratio));
      VTRI.paint();
    });
    $$('#triRef .chip').forEach(x => x.classList.toggle('on', x.dataset.r === ST.tri.ref));
    VTRI.buildInputs();
    VTRI.paint(true);
  },

  mode() { return T.modes.filter(m => m.id === ST.tri.mode)[0]; },

  buildInputs() {
    const m = VTRI.mode();
    $('#triInputs').innerHTML = m.fields.map(f =>
      `<div class="field"><label>${f.label}${f.unit ? ' <span class="u">' + f.unit + '</span>' : ''}</label>
        <input type="number" inputmode="decimal" data-k="${f.k}" value="${ST.tri.v[f.k]}" placeholder="${f.ph || ''}"></div>`).join('');
    $$('#triInputs input').forEach(el => {
      el.addEventListener('input', () => {
        ST.tri.v[el.dataset.k] = el.value === '' ? 0 : (parseFloat(el.value) || 0);
        VTRI.paint();
      });
      el.addEventListener('focus', () => el.parentNode.classList.add('foc'));
      el.addEventListener('blur', () => el.parentNode.classList.remove('foc'));
    });
    $('#triErr').innerHTML = `<div class="hint" style="margin:8px 0 0">${m.hint}</div>`;
  },

  calc() { return VTRI.mode().solve(ST.tri.v); },

  legend() {
    /* 参考角变了，对边/邻边互换 —— 在提示里点出来 */
    $('#triHot').classList.toggle('dis', false);
  },

  paint(rebuild) {
    if (rebuild) VTRI.buildInputs();
    const r = VTRI.calc();
    const ref = ST.tri.ref;
    const ratioAngle = r && !r.err ? (ref === 'A' ? r.A : r.B) : 0;
    let hot = [];
    if (ST.tri.ratio && r && !r.err) hot = sidesOf(ST.tri.ratio, ref);

    if (r && r.err) {
      $('#triSvg').innerHTML = `<div style="padding:34px 12px;text-align:center;color:#FF9B9B;font-size:13px">${esc(r.err)}</div>`;
      $('#triBig').innerHTML = ''; $('#triRows').innerHTML = ''; $('#triSteps').innerHTML = '';
      return;
    }
    $('#triSvg').innerHTML = T.draw({ a: r.a, b: r.b, c: r.c, A: r.A, B: r.B, ref: ref, hot: hot });

    const opp = ref === 'A' ? r.a : r.b, adj = ref === 'A' ? r.b : r.a;
    $('#triBig').innerHTML = [
      ['对边', T.len(opp), 'opposite'], ['邻边', T.len(adj), 'adjacent'], ['斜边', T.len(r.c), 'hypotenuse'],
    ].map(x => `<div class="b"><div class="t">${x[0]}</div><div class="n">${x[1]}</div><div class="s">${x[2]}</div></div>`).join('');

    const rt = T.ratio(ratioAngle);
    $('#triRows').innerHTML = [
      [`参考角 ∠${ref}`, T.fmt(ratioAngle, 3) + '°'],
      ['另一个锐角', T.fmt(ref === 'A' ? r.B : r.A, 3) + '°'],
      ['sin ∠' + ref, T.fmt(rt.sin, 5) + '  (= 对边/斜边)'],
      ['cos ∠' + ref, T.fmt(rt.cos, 5) + '  (= 邻边/斜边)'],
      ['tan ∠' + ref, (isFinite(rt.tan) ? T.fmt(rt.tan, 5) : '∞') + '  (= 对边/邻边)'],
      ['验算 sin²+cos²', T.fmt(rt.sin * rt.sin + rt.cos * rt.cos, 6)],
      ['a² + b²', T.len(r.a * r.a + r.b * r.b) + '   c² = ' + T.len(r.c * r.c)],
    ].map(x => `<div class="kv"><span class="k">${x[0]}</span><span class="v">${x[1]}</span></div>`).join('');

    $('#triSteps').innerHTML = '<ul class="steps">' +
      r.steps.map(s => `<li><b>${s[0]}</b>：${s[1]}</li>`).join('') + '</ul>';

    /* 解释卡 */
    const o = ref === 'A' ? r.a : r.b, ad = ref === 'A' ? r.b : r.a;
    $('#triExplain').innerHTML = `
      <div class="kv"><span class="k"><span class="pill o">对边</span> ${ref === 'A' ? 'a' : 'b'} = ${T.len(o)}</span>
        <span class="v" style="color:var(--opp)">正对着 ∠${ref}</span></div>
      <div class="kv"><span class="k"><span class="pill a">邻边</span> ${ref === 'A' ? 'b' : 'a'} = ${T.len(ad)}</span>
        <span class="v" style="color:var(--adj)">挨着 ∠${ref}，且不是斜边</span></div>
      <div class="kv"><span class="k"><span class="pill h">斜边</span> c = ${T.len(r.c)}</span>
        <span class="v" style="color:var(--hyp)">永远对着直角 C，永远最长</span></div>
      <div class="hint" style="margin-top:10px">现在以 <b>${ref} 角</b>为准：
        对边 ÷ 邻边 = ${T.len(o)} ÷ ${T.len(ad)} = <b>${T.fmt(o / ad, 4)}</b>，取反正切就是 ${T.fmt(ratioAngle, 2)}°。
        ${ref === 'A' ? '点上面的「以 B 角看」，你会发现 b 变成对边、a 变成邻边 —— 边没变，是「参照的角」变了。' : '这就是混淆的根源：同一条边，换个角看身份就换了。'}</div>`;
  },
};

/* ================================================================
   视图 2：比值
   ================================================================ */
const VRATIO = {
  html() {
    return `
    <div class="card">
      <h3>拖一动，看三条边怎么变</h3>
      <div class="hint">下面这个三角形，<b>斜边固定 = 1</b>。拖角度，看对边和邻边此消彼长 ——
        比值就是「两边谁比谁」，不是「哪条边多长」。</div>
      <div class="triwrap" id="rSvg"></div>
      <div class="legend">
        <div class="lg"><i style="background:var(--opp)"></i>对边 = sinθ</div>
        <div class="lg"><i style="background:var(--adj)"></i>邻边 = cosθ</div>
        <div class="lg"><i style="background:var(--hyp)"></i>斜边 = 1</div>
      </div>
      <div class="inline" style="justify-content:space-between">
        <span style="font-size:12.5px;color:var(--dim)">角度 θ</span>
        <b id="rTheta" style="font-size:17px">30°</b>
      </div>
      <input type="range" id="rRange" min="1" max="89" step="0.5" value="30">
      <div class="chips" id="rQuick" style="margin-top:8px">
        ${[10, 15, 30, 45, 60, 75, 80].map(a => `<div class="chip" data-a="${a}">${a}°</div>`).join('')}
      </div>
    </div>

    <div class="card sub">
      <h3>三兄弟，谁比谁</h3>
      <div class="hint">点卡片 → 上面图里对应的两条边会亮起来。<b>斜边只出现在 sin / cos 里，tan 里没有斜边。</b></div>
      <div id="rCards"></div>
      <div id="rBars" style="margin-top:12px"></div>
    </div>

    <div class="card">
      <h3>已知比值 → 反求角度</h3>
      <div class="hint">工地上量出来的是两条边的长度，比值算出来以后要用反正弦/反余弦/反正切换回角度。</div>
      <div class="chips blue" id="rInvK" style="margin-bottom:9px">
        <div class="chip on" data-k="sin">arcsin（对边/斜边）</div>
        <div class="chip" data-k="cos">arccos（邻边/斜边）</div>
        <div class="chip" data-k="tan">arctan（对边/邻边）</div>
      </div>
      <div class="grid2">
        <div class="field"><label>对边 <span class="u">任意单位</span></label><input type="number" inputmode="decimal" id="rInvA" value="3"></div>
        <div class="field"><label id="rInvBLabel">斜边 <span class="u">任意单位</span></label><input type="number" inputmode="decimal" id="rInvB" value="5"></div>
      </div>
      <div id="rInvOut"></div>
    </div>

    <div class="card">
      <h3>为什么老混？把雷排掉</h3>
      <div class="hint" style="color:var(--opp);font-weight:600">${DATA.mnemonic.main}</div>
      <div class="hint">${DATA.mnemonic.short}</div>
      <ul class="steps">
        ${DATA.mnemonic.hooks.map(h => `<li>${h}</li>`).join('')}
      </ul>
      <div style="margin-top:14px"></div>
      ${DATA.mnemonic.mistakes.map(m => `
        <div class="verdict bad" style="margin-top:8px"><b>✗ ${m[0]}</b><br>${m[1]}</div>`).join('')}
    </div>`;
  },

  init() {
    $('#rRange').addEventListener('input', e => {
      ST.ratio.theta = parseFloat(e.target.value);
      VRATIO.paint();
    });
    $('#rQuick').addEventListener('click', e => {
      const c = e.target.closest('[data-a]'); if (!c) return;
      ST.ratio.theta = parseInt(c.dataset.a, 10);
      $('#rRange').value = ST.ratio.theta;
      VRATIO.paint();
    });
    $('#rInvK').addEventListener('click', e => {
      const c = e.target.closest('[data-k]'); if (!c) return;
      ST.ratio.k = c.dataset.k;
      $$('#rInvK .chip').forEach(x => x.classList.toggle('on', x.dataset.k === ST.ratio.k));
      VRATIO.invLabels(); VRATIO.inv();
    });
    ['rInvA', 'rInvB'].forEach(id => $('#' + id).addEventListener('input', () => VRATIO.inv()));
    VRATIO.invLabels();
    VRATIO.paint();
    VRATIO.inv();
  },

  invLabels() {
    const k = ST.ratio.k;
    $('#rInvBLabel').innerHTML = (k === 'tan' ? '邻边' : '斜边') + ' <span class="u">任意单位</span>';
  },

  inv() {
    const k = ST.ratio.k;
    const A = parseFloat($('#rInvA').value) || 0, B = parseFloat($('#rInvB').value) || 0;
    const out = $('#rInvOut');
    if (!(A > 0) || !(B > 0)) { out.innerHTML = '<div class="hint">填入两个正数</div>'; return; }
    const x = A / B;
    let deg, fn, extra = '';
    if (k === 'sin') { if (x > 1) { out.innerHTML = `<div class="verdict bad">sin 不可能大于 1 —— 对边是直角边，一定比斜边短。检查是不是把两条边填反了。</div>`; return; } deg = T.deg(Math.asin(x)); fn = 'arcsin'; }
    else if (k === 'cos') { if (x > 1) { out.innerHTML = `<div class="verdict bad">cos 不可能大于 1 —— 邻边一定比斜边短。</div>`; return; } deg = T.deg(Math.acos(x)); fn = 'arccos'; }
    else { deg = T.deg(Math.atan(x)); fn = 'arctan'; }
    out.innerHTML = `
      <div class="kv"><span class="k">比值 ${k}θ = ${A} / ${B}</span><span class="v">${T.fmt(x, 6)}</span></div>
      <div class="kv"><span class="k">角度 θ = ${fn}(${T.fmt(x, 6)})</span><span class="v" style="color:var(--opp)">${T.fmt(deg, 3)}°</span></div>
      <div class="hint" style="margin-top:8px">反过来验算：${k} ${T.fmt(deg, 3)}° = ${T.fmt(k === 'sin' ? T.sin(deg) : k === 'cos' ? T.cos(deg) : T.tan(deg), 6)} ✓
        ${k === 'tan' && x > 1 ? '（tan > 1 说明对边比邻边长，角大于 45°）' : ''}
        ${k === 'tan' && x < 1 ? '（tan < 1 说明对边比邻边短，角小于 45°）' : ''}</div>`;
  },

  paint() {
    const th = ST.ratio.theta;
    const s = T.sin(th), co = T.cos(th);
    $('#rTheta').textContent = T.fmt(th, 1) + '°';
    const hot = ST.ratio.hot || [];
    $('#rSvg').innerHTML = T.draw({ a: s, b: co, c: 1, A: th, B: 90 - th, ref: 'A', hot: hot });

    const tan = Math.abs(co) < 1e-9 ? Infinity : s / co;
    $('#rCards').innerHTML = DATA.ratios.map(r => {
      const num = r.k === 'sin' ? s : r.k === 'cos' ? co : tan;
      const on = ST.ratio.active === r.k;
      return `<div class="rc ${on ? 'on' : ''}" data-k="${r.k}">
        <div class="fn">${r.fn}</div>
        <div class="mid">
          <div class="f1">${r.cn} = <span class="pill ${r.k === 'sin' ? 'o' : r.k === 'cos' ? 'a' : 'h'}">${r.pair[0]}</span>
            ÷ <span class="pill ${r.pair[1] === '斜边' ? 'h' : r.pair[1] === '邻边' ? 'a' : 'o'}">${r.pair[1]}</span></div>
          <div class="f2">${r.en} · ${r.say}</div>
        </div>
        <div class="rt">${isFinite(num) ? T.fmt(num, 4) : '∞'}<small>${r.k} ${T.fmt(th, 1)}°</small></div>
      </div>`;
    }).join('');
    $$('#rCards .rc').forEach(el => {
      el.addEventListener('click', () => {
        const k = el.dataset.k;
        ST.ratio.active = (ST.ratio.active === k) ? null : k;
        ST.ratio.hot = ST.ratio.active ? sidesOf(k, 'A') : [];
        nat('buzz', 12);
        VRATIO.paint();
      });
    });

    /* 条形图：把三条边的实际长度画出来 */
    const bar = (name, val, col, note, max) => {
      const w = Math.max(1.5, Math.min(100, val / max * 100));
      return `<div class="barrow">
        <div class="t"><span>${name}</span><span style="color:${col};font-weight:700">${T.fmt(val, 4)}</span></div>
        <div class="bar"><i style="width:${w}%;background:${col}"></i></div>
        ${note ? `<div class="tag" style="margin-top:3px">${note}</div>` : ''}
      </div>`;
    };
    let bh = bar('斜边（基准 = 1）', 1, 'var(--hyp)', '斜边永远是基准，也是最长的一条');
    bh += bar('对边 = 1 × sinθ', s, 'var(--opp)', `= 斜边的 ${T.fmt(s * 100, 1)}%（就是 sinθ 本身）`);
    bh += bar('邻边 = 1 × cosθ', co, 'var(--adj)', `= 斜边的 ${T.fmt(co * 100, 1)}%（就是 cosθ 本身）`);
    bh += `<div class="hint" style="margin-top:6px">θ 从 ${T.fmt(th, 1)}° 变大 →
      对边变长、邻边变短 → <b>tanθ = 对边/邻边</b> 迅速变大（现在 ${T.fmt(tan, 4)}）。
      θ = 45° 时两者相等，tan = 1，正好是对半分界点。</div>`;
    $('#rBars').innerHTML = bh;
  },
};

/* ================================================================
   通用计算器渲染（力学 / 坡度）
   ================================================================ */
const CALCV = {};

function initCalc(c) {
  const o = {};
  c.inputs.forEach(f => { o[f.k] = f.def; });
  CALCV[c.id] = o;
}

function calcCardHTML(c) {
  return `<div class="card" id="cc_${c.id}">
      <h3>${c.title}</h3>
      <div class="hint">${c.hint}</div>
      <div class="grid2" data-in="${c.id}"></div>
      <div data-out="${c.id}" style="margin-top:10px"></div>
    </div>`;
}

function runCalc(c) {
  const v = CALCV[c.id];
  const vv = M.coerce(c, CALCV[c.id]);
  let res;
  try { res = c.calc(vv); } catch (e) { res = { err: '计算出错：' + e.message }; }
  const box = document.querySelector(`[data-out="${c.id}"]`);
  if (!box) return;
  if (res.err) { box.innerHTML = `<div class="verdict bad">${esc(res.err)}</div>`; return; }
  let h = '';
  if (res.head) h += '<div class="big">' + res.head.map(x =>
    `<div class="b"><div class="t">${x[0]}</div><div class="n">${x[1]}</div>${x[2] ? `<div class="s">${x[2]}</div>` : ''}</div>`).join('') + '</div>';
  if (res.rows) h += res.rows.map(r =>
    `<div class="kv"><span class="k">${r[0]}</span><span class="v">${r[1]}</span></div>`).join('');
  if (res.steps && res.steps.length) h += '<ul class="steps">' +
    res.steps.map(s => `<li><b>${s[0]}</b>：${s[1]}</li>`).join('') + '</ul>';
  if (c.actions) h += '<div class="chips" style="margin-top:10px">' +
    c.actions.map((a, i) => `<div class="chip" data-act="${i}">${a.label}</div>`).join('') + '</div>';
  if (res.verdict) h += `<div class="verdict ${res.verdict.cls}">${res.verdict.html}</div>`;
  box.innerHTML = h;

  if (c.actions) {
    box.querySelectorAll('[data-act]').forEach(el => {
      el.addEventListener('click', () => {
        const a = c.actions[parseInt(el.dataset.act, 10)];
        const msg = a.run(CALCV[c.id]);
        if (msg) { toast(msg); return; }
        fillCalcInputs(c);
        runCalc(c);
        nat('buzz', 15);
        toast(a.done || '已带入');
      });
    });
  }
}

function fillCalcInputs(c) {
  const box = document.querySelector(`[data-in="${c.id}"]`);
  if (!box) return;
  const v = CALCV[c.id];
  const selKey = (c.inputs.filter(f => f.sel)[0] || {}).k;
  const typeVal = selKey ? v[selKey] : null;
  let h = '';
  c.inputs.forEach(f => {
    if (f.show && typeVal && f.show.indexOf(typeVal) < 0) return;
    if (f.sel) {
      h += `<div class="field" style="grid-column:1/-1"><label>${f.label}</label>
        <div class="chips blue" style="margin-top:5px" data-sel="${f.k}">` +
        f.opts.map(o => `<div class="chip ${o.v === v[f.k] ? 'on' : ''}" data-v="${o.v}">${o.t}</div>`).join('') +
        `</div></div>`;
    } else {
      h += `<div class="field"><label>${f.label}${f.unit ? ` <span class="u">${f.unit}</span>` : ''}</label>
        <input type="number" inputmode="decimal" data-k="${f.k}" value="${v[f.k]}"></div>`;
    }
  });
  box.innerHTML = h;

  box.querySelectorAll('[data-sel]').forEach(g => {
    g.addEventListener('click', e => {
      const chip = e.target.closest('[data-v]'); if (!chip) return;
      const k = g.dataset.sel;
      CALCV[c.id][k] = chip.dataset.v;
      fillCalcInputs(c);
      runCalc(c);
    });
  });
  box.querySelectorAll('input[data-k]').forEach(el => {
    el.addEventListener('input', () => {
      CALCV[c.id][el.dataset.k] = el.value === '' ? 0 : (parseFloat(el.value) || 0);
      runCalc(c);
    });
    el.addEventListener('focus', () => el.parentNode.classList.add('foc'));
    el.addEventListener('blur', () => el.parentNode.classList.remove('foc'));
  });
}

/* ================================================================
   视图 3：坡度
   ================================================================ */
const VSLOPE = {
  html() {
    return calcCardHTML(M.calcs[0]) + `
    <div class="card">
      <h3>建筑常用坡度</h3>
      <div class="hint">照着抄就行，别自己拍脑袋定。</div>
      <table>
        <tr><th>部位</th><th>坡度</th><th>角度</th></tr>
        ${DATA.slopes.map(s => `<tr><td>${s.n}</td><td class="mono">${s.v}</td><td class="mono">${s.a}</td></tr>`).join('')}
      </table>
    </div>
    <div class="card sub">
      <h3>坡度 = tan θ（就是那个「对角比」）</h3>
      <div class="hint">把坡看成直角三角形：水平距离是<b>邻边</b>，升高是<b>对边</b>，坡面是<b>斜边</b>。</div>
      <ul class="steps">
        <li><b>坡度 i</b>：i = 高 ÷ 水平 = 对边 ÷ 邻边 = <code>tanθ</code> —— 这正好是 tan 的定义</li>
        <li><b>百分比</b>：i × 100%，比如 i = 0.02 就是 2%</li>
        <li><b>1:x 形式</b>：1 : (1/i)，比如 1:50 就是每 50 m 升 1 m</li>
        <li><b>斜长</b>：S = 水平 ÷ cosθ = √(水平² + 高²)</li>
        <li><b>下料</b>：斜杆长度 = 水平 ÷ cosθ；竖向高 = 斜长 × sinθ</li>
      </ul>
      <div class="hint" style="margin-top:8px">记不住就用一句话：<b>坡度就是 tan，百分比就是 tan 乘 100</b>。</div>
    </div>`;
  },
  init() { initCalc(M.calcs[0]); fillCalcInputs(M.calcs[0]); runCalc(M.calcs[0]); },
};

/* ================================================================
   视图 4：力学
   ================================================================ */
const VMECH = {
  html() {
    return `<div class="card" style="background:linear-gradient(135deg,#1B2430,#161C24)">
      <h3>建筑力学常用算</h3>
      <div class="hint">七个计算器，都是工地上真会遇到的。每个都带<b>计算过程</b>和<b>合格判定</b>，不是只给个数字。</div>
      <div class="chips">
        ${M.calcs.filter(c => c.id !== 'slope').map(c => `<div class="chip" data-go="${c.id}">${c.title.split(' ')[0]}</div>`).join('')}
      </div>
    </div>
    ` + M.calcs.filter(c => c.id !== 'slope').map(calcCardHTML).join('') + `
    <div class="foot">公式按 GB 50017 / GB 50010 / GB 50068 常用形式，<br>实际工程请以设计图与现行规范为准</div>`;
  },
  init() {
    M.calcs.filter(c => c.id !== 'slope').forEach(c => { initCalc(c); fillCalcInputs(c); runCalc(c); });
    $$('[data-go]').forEach(el => el.addEventListener('click', () => {
      const t = $('#cc_' + el.dataset.go);
      if (t) t.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }));
  },
};

/* ================================================================
   视图 5：速查
   ================================================================ */
const VREF = {
  html() {
    return `
    <div class="card">
      <h3>一句话记住三兄弟</h3>
      <div class="hint" style="font-size:14px;color:var(--opp);font-weight:700;line-height:1.9">
        ${DATA.mnemonic.main}<br><span style="color:var(--dim);font-weight:400;font-size:12.5px">${DATA.mnemonic.short}</span>
      </div>
      <div class="hint" style="margin-top:6px">只有 <b>sin / cos</b> 里有斜边；<b>tan 里没有斜边</b>。斜边永远最长，所以 sin、cos 永远 ≤ 1；tan 可以大于 1。</div>
      <ul class="steps">
        ${DATA.mnemonic.hooks.map(h => `<li>${h}</li>`).join('')}
      </ul>
    </div>

    <div class="card sub">
      <h3>特殊角速查</h3>
      <table>
        <tr><th>角度</th><th>sin</th><th>cos</th><th>tan</th></tr>
        ${DATA.special.map(s => `<tr><td class="mono">${s.d}°</td><td class="mono">${s.sin}</td><td class="mono">${s.cos}</td><td class="mono">${s.tan}</td></tr>`).join('')}
      </table>
    </div>

    <div class="card">
      <h3>三角公式</h3>
      <table>
        ${DATA.formulas.map(f => `<tr><td style="white-space:nowrap">${f[0]}</td><td class="mono">${f[1]}</td></tr>`).join('')}
      </table>
      <div class="hint" style="margin-top:8px">${DATA.formulas.map(f => `<b>${f[0]}</b>：${f[2]}`).join('；')}</div>
    </div>

    <div class="card">
      <h3>材料强度参考（设计值）</h3>
      <table>
        <tr><th>材料</th><th>抗弯 f</th><th>抗剪</th><th>E</th><th>容重</th></tr>
        ${DATA.materials.map(m => `<tr><td>${m.n}<div class="tag">${m.note}</div></td>
          <td class="mono">${m.fb}</td><td class="mono">${m.fv}</td><td class="mono">${m.E}</td><td class="mono">${m.g}</td></tr>`).join('')}
      </table>
      <div class="hint" style="margin-top:6px">单位：强度 MPa，E 为 MPa，容重 kN/m³。数值为常用参考值，实际按规范取值。</div>
    </div>

    <div class="card">
      <h3>挠度限值参考</h3>
      <table>
        <tr><th>构件</th><th>限值</th></tr>
        ${DATA.deflect.map(d => `<tr><td>${d.n}</td><td class="mono">L/${d.v}</td></tr>`).join('')}
      </table>
      <div class="hint" style="margin-top:6px">悬臂梁按悬臂长度的 2 倍作为计算跨度 L 代入。</div>
    </div>

    <div class="card">
      <h3>截面惯性矩 / 抵抗矩公式</h3>
      <table>
        <tr><th>截面</th><th>I</th><th>W</th></tr>
        ${DATA.sectionFormulas.map(s => `<tr><td>${s.n}</td><td class="mono">${s.I}</td><td class="mono">${s.W}</td></tr>`).join('')}
      </table>
    </div>

    <div class="card">
      <h3>单位换算</h3>
      ${DATA.units.map(u => `<div style="margin-bottom:8px">
        <div class="tag" style="margin-bottom:3px">${u.n}</div>
        <table>${u.v.map(x => `<tr><td class="mono">${x[0]}</td><td class="mono">${x[1]}</td></tr>`).join('')}</table>
      </div>`).join('')}
    </div>

    <div class="foot">三角力学计算器 · 全离线<br>公式按常用工程做法整理，重要构件请复核</div>`;
  },
  init() { },
};

/* ================================================================
   路由
   ================================================================ */
const VIEWS = { tri: VTRI, ratio: VRATIO, slope: VSLOPE, mech: VMECH, ref: VREF };

function show(tab) {
  if (!VIEWS[tab]) tab = 'tri';
  ST.tab = tab;
  localStorage.setItem('tm_tab', tab);
  try { if (location.hash !== '#' + tab) history.replaceState(null, '', '#' + tab); } catch (e) { }
  $$('#tabs .tab').forEach(x => x.classList.toggle('on', x.dataset.t === tab));
  $('#view').innerHTML = VIEWS[tab].html();
  $('#view').scrollTop = 0;
  window.scrollTo(0, 0);
  VIEWS[tab].init();
}
window.addEventListener('load', () => {
  $$('#tabs .tab').forEach(x => x.addEventListener('click', () => show(x.dataset.t)));
  show(ST.tab);
});

/* 安卓返回键：不在第一个页签就回第一个，否则退出 */
window.__back = function () {
  if (ST.tab !== 'tri') { show('tri'); return; }
  nat('exit');
};
