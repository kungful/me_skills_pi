/* =====================================================================
   app.js —— 状态 / 路由 / 渲染
   ===================================================================== */
(function () {
  const $ = s => document.querySelector(s);
  const $$ = s => Array.prototype.slice.call(document.querySelectorAll(s));
  const LS = 'canopystruct.p.v1';

  const ST = {
    P: MODEL.defaults(),
    R: null,
    tab: localStorage.getItem('cs.tab') || 's3',
    col: 0, caseKey: 'up',
    v3: { showNet: true, showWind: true, showLoad: true, showReac: true, showFound: true, showLabel: true, defl: 0 },
    ready: false,
  };

  /* ---------------- 原生桥 ---------------- */
  const cb = {};
  let seq = 1;
  function nat(op, args) {
    return new Promise((res, rej) => {
      if (!window.Hua || !window.Hua.invoke) { rej('no native'); return; }
      const id = 'r' + (seq++);
      cb[id] = (ok, payload) => ok ? res(payload) : rej(payload);
      window.Hua.invoke(id, op, JSON.stringify(args || {}));
    });
  }
  window.__apiResult = function (id, ok, payload) { const f = cb[id]; delete cb[id]; if (f) f(!!ok, payload); };
  function toast(m) {
    const t = $('#toast'); t.textContent = m; t.classList.add('show');
    clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove('show'), 1800);
  }
  function busy(on, txt) {
    $('#busy').classList.toggle('show', on);
    if (txt) $('#busy').querySelector('span').textContent = txt;
  }

  /* ---------------- 计算 ---------------- */
  let dirtyTimer = 0;
  function recompute(now) {
    clearTimeout(dirtyTimer);
    const go = () => {
      const t0 = performance.now();
      try {
        ST.R = MODEL.run(ST.P);
      } catch (e) {
        toast('算错了：' + e);
        console.error(e);
        return;
      }
      const ms = performance.now() - t0;
      console.log('run ' + ms.toFixed(0) + 'ms  uMax=' + ST.R.uMax.toFixed(2) + ' v=' + ST.R.vmax.toFixed(1));
      header();
      renderTab(ST.tab);
    };
    if (now) go(); else dirtyTimer = setTimeout(go, 90);
  }

  function header() {
    const R = ST.R;
    const v = $('#verdict');
    v.className = 'chip ' + R.state;
    v.textContent = R.state === 'ok' ? '能过关' : R.state === 'warn' ? '临界' : '不够';
    $('#vmaxv').textContent = R.vmax.toFixed(1) + ' m/s';
    $('#vmaxb').textContent = WIND.beaufort(R.vmax);
    $('#vgov').textContent = (R.vGovern || '—').replace(' · 工况① 风吸上抬（网被掀起）', ' · 风吸').replace(' · 工况② 风压向下（网被压下）', ' · 风压').replace(' · 工况③ 水平风（整体倾覆）', ' · 水平风');
  }

  /* ---------------- tab 切换 ---------------- */
  function go(tab) {
    ST.tab = tab; localStorage.setItem('cs.tab', tab);
    $$('#tabs .tab').forEach(t => t.classList.toggle('on', t.dataset.t === tab));
    const wrap = $('#view');
    wrap.className = '';
    wrap.innerHTML = '';
    const pane = document.createElement('div');
    pane.className = 'pane on';
    wrap.appendChild(pane);
    renderTab(tab, pane);
    if (tab === 's3' && V3.isOk()) setTimeout(() => V3.resize(), 40);
  }

  function renderTab(tab, pane) {
    pane = pane || $('.pane');
    const R = ST.R;
    if (!R) return;
    if (!pane) return;                       // 启动阶段还没有面板，先不算
    if (tab === 's3') return render3D(pane, R);
    if (tab === 's2') return render2D(pane, R);
    if (tab === 'par') return renderParams(pane, R);
    if (tab === 'chk') return renderChecks(pane, R);
    if (tab === 'cmp') return renderCompare(pane, R);
    if (tab === 'doc') return renderDoc(pane, R);
  }

  /* ---------------- 三维 ---------------- */
  function render3D(pane, R) {
    pane.style.padding = '0';
    pane.innerHTML = `
      <div id="s3wrap"></div>
      <div id="tools3">
        <button data-a="reset">复位</button>
        <button data-a="top">俯视</button>
        <button data-a="front">正视</button>
        <button data-a="end">侧视</button>
        <button data-a="net" class="on">网面</button>
        <button data-a="wind" class="on">风</button>
        <button data-a="load" class="on">荷载</button>
        <button data-a="reac" class="on">反力</button>
        <button data-a="label" class="on">标签</button>
        <button data-a="defl">放大变形×0</button>
      </div>
      <div id="legend3">
        <div><i style="background:#44C7A9"></i>应力比 ≤0.85</div>
        <div><i style="background:#FFB84D"></i>0.85~1.0</div>
        <div><i style="background:#FF5A5A"></i>&gt;1.0 不够</div>
        <div style="color:#5F7381;margin-top:3px">颜色=杆件利用率</div>
      </div>
      <div id="hint3">单指拖动旋转 · 双指捏合缩放</div>`;
    const host = pane.querySelector('#s3wrap');
    if (!V3.isOk()) V3.init(host); else V3.attach(host);
    if (!V3.isOk()) { pane.querySelector('#tools3').style.display = 'none'; return; }
    publish3D();
    pane.querySelectorAll('#tools3 button').forEach(b => b.addEventListener('click', () => {
      const a = b.dataset.a;
      if (a === 'reset') V3.resetView();
      else if (a === 'top') V3.topView();
      else if (a === 'front') V3.frontView();
      else if (a === 'end') V3.endView();
      else if (a === 'defl') {
        ST.v3.defl = ST.v3.defl === 0 ? 100 : ST.v3.defl === 100 ? 20 : 0;
        b.textContent = '放大变形×' + ST.v3.defl;
        publish3D();
      } else {
        const K = { net: 'showNet', wind: 'showWind', load: 'showLoad', reac: 'showReac', label: 'showLabel' };
        ST.v3[K[a]] = !ST.v3[K[a]];
        b.classList.toggle('on');
        publish3D();
      }
    }));
  }
  function publish3D() {
    if (!ST.R || !V3.isOk()) return;
    V3.build(ST.R, Object.assign({}, ST.v3, { caseKey: ST.caseKey === 'wind' ? 'wind' : 'up' }));
  }

  /* ---------------- 二维 ---------------- */
  let cvP, cvE, cvF, fPlan;
  function render2D(pane, R) {
    pane.classList.add('scroll');
    pane.innerHTML = `
      <div class="segs" id="segCase"></div>
      <div class="cvbox"><canvas id="cvP"></canvas>
        <div class="cap">平面支点示意：绿框是太阳网，橙色虚线是每根柱子分担的网宽，柱脚方块到端点圆点就是三角挑梁的悬臂。
        柱子全部贴墙 → 抵抗倾覆的力臂很短，这是本方案最要命的地方。</div></div>
      <div class="cvbox"><canvas id="cvE"></canvas>
        <div class="cap">立面 + 弯矩图（蓝色填充，比例自动缩放）。箭头是施加的荷载与柱底反力；虚线斜杆表示该工况下斜杆退出工作。</div></div>
      <div class="cvbox"><canvas id="cvF"></canvas>
        <div class="cap">传力路径：从风到土，哪一环断掉整个棚子就出事。</div></div>`;

    const segs = pane.querySelector('#segCase');
    const cases = [['up', '① 风吸上抬'], ['down', '② 风压向下'], ['wind', '③ 水平风']];
    R.geo.cols.forEach((c, i) => {
      // 柱选择放在第二行
    });
    let h = '';
    h += cases.map(c => `<button class="${ST.caseKey === c[0] ? 'on' : ''}" data-c="${c[0]}">${c[1]}</button>`).join('');
    h += R.geo.cols.map((c, i) => `<button class="${ST.col === i ? 'on' : ''}" data-i="${i}">${c.id}</button>`).join('');
    segs.innerHTML = h;
    segs.querySelectorAll('[data-c]').forEach(b => b.addEventListener('click', () => { ST.caseKey = b.dataset.c; renderTab('s2'); publish3D(); }));
    segs.querySelectorAll('[data-i]').forEach(b => b.addEventListener('click', () => { ST.col = +b.dataset.i; renderTab('s2'); }));

    cvP = pane.querySelector('#cvP'); cvE = pane.querySelector('#cvE'); cvF = pane.querySelector('#cvF');
    redraw2D();
  }
  function redraw2D() {
    if (!ST.R || !cvP) return;
    V2.plan(cvP, ST.R, {});
    V2.elev(cvE, ST.R, Math.min(ST.col, ST.R.geo.cols.length - 1), ST.caseKey, { hpx: 300 });
    V2.path(cvF, ST.R, { hpx: 300 });
  }

  /* ---------------- 参数 ---------------- */
  function renderParams(pane, R) {
    pane.classList.add('scroll');
    if (!pane.querySelector('#parBody')) {
      pane.innerHTML = `<div id="parBody"></div>`;
      const body = pane.querySelector('#parBody');
      body.innerHTML = UI.paramsHTML(ST.P);
      UI.bindParams(body, ST.P, () => { save(); recompute(); });
      const btn = document.createElement('div');
      btn.className = 'card';
      btn.innerHTML = `<h3>柱位（各柱挑梁端部）</h3><div id="colPos"></div>
        <div class="btns"><button id="even">均分柱位</button><button id="shrink">挑出减 0.5m</button><button class="gho" id="resetAll">全部恢复默认</button></div>
        <div class="hint">柱子 x 是挑梁端部在长边墙上的位置。第三根默认放在靠短边墙的拐角处，悬臂较短。</div>`;
      body.appendChild(btn);
      pane.addEventListener('click', e => {
        if (e.target.id === 'even') {
          const n = ST.P.nCol;
          ST.P.tipX = []; ST.P.baseY = [];
          for (let i = 0; i < n; i++) ST.P.tipX.push(+(ST.P.netL * (i + 0.5) / n).toFixed(2));
          for (let i = 0; i < n; i++) ST.P.baseY.push(ST.P.wallGap);
          save(); recompute(true);
        }
        if (e.target.id === 'shrink') { ST.P.netW = Math.max(1, ST.P.netW - 0.5); save(); syncParamUI(); recompute(true); }
        if (e.target.id === 'resetAll') { ST.P = MODEL.defaults(); save(); go('par'); recompute(true); }
      });
    }
    renderColPos();
  }
  function renderColPos() {
    const box = document.querySelector('#colPos');
    if (!box) return;
    const n = ST.P.nCol;
    let h = '';
    for (let i = 0; i < n; i++) {
      const tx = ST.P.tipX[i] !== undefined ? ST.P.tipX[i] : (ST.P.netL * (i + 0.5) / n);
      const by = ST.P.baseY[i] !== undefined ? ST.P.baseY[i] : ST.P.wallGap;
      h += `<div class="row"><label>C${i + 1}　端部 x (m)</label><div class="ctl">
        <input type="range" data-tx="${i}" min="0" max="${ST.P.netL}" step="0.1" value="${tx}">
        <output>${(+tx).toFixed(1)}</output></div></div>
        <div class="row"><label>C${i + 1}　柱脚离墙 y (m)</label><div class="ctl">
        <input type="range" data-by="${i}" min="0.1" max="${Math.max(0.2, ST.P.netW - 0.2)}" step="0.1" value="${by}">
        <output>${(+by).toFixed(1)}</output><span class="tag">悬臂 ${(ST.P.netW - by).toFixed(2)}m</span></div></div>`;
    }
    box.innerHTML = h;
    box.querySelectorAll('[data-tx]').forEach(el => el.addEventListener('input', () => {
      const i = +el.dataset.tx;
      if (!ST.P.tipX) ST.P.tipX = [];
      ST.P.tipX[i] = parseFloat(el.value);
      el.parentElement.querySelector('output').textContent = (+el.value).toFixed(1);
      save(); recompute();
    }));
    box.querySelectorAll('[data-by]').forEach(el => el.addEventListener('input', () => {
      const i = +el.dataset.by;
      if (!ST.P.baseY) ST.P.baseY = [];
      ST.P.baseY[i] = parseFloat(el.value);
      el.parentElement.querySelector('output').textContent = (+el.value).toFixed(1);
      const t = el.parentElement.querySelector('.tag');
      if (t) t.textContent = '悬臂 ' + (ST.P.netW - el.value).toFixed(2) + 'm';
      save(); recompute();
    }));
  }
  function syncParamUI() {
    const body = document.querySelector('#parBody');
    if (!body) return;
    body.querySelectorAll('[data-k]').forEach(el => {
      const k = el.dataset.k;
      if (el.type === 'range' && ST.P[k] !== undefined) {
        if (el.value !== String(ST.P[k])) el.value = ST.P[k];
        const o = body.querySelector(`[data-o="${k}"]`);
        const spec = UI.SPEC.flatMap(s => s.items).find(s => s.k === k);
        if (o && spec) o.textContent = spec.pct ? (ST.P[k] * 100).toFixed(0) + '%' : (+ST.P[k]).toFixed(spec.d === undefined ? 2 : spec.d);
      } else if (el.tagName === 'SELECT' && ST.P[k] !== undefined) {
        el.value = String(ST.P[k]);
      }
    });
    renderColPos();
  }

  /* ---------------- 校核 ---------------- */
  function renderChecks(pane, R) {
    pane.classList.add('scroll');
    pane.innerHTML = UI.verdictHTML(R) + UI.checksHTML(R);
  }

  /* ---------------- 对比 ---------------- */
  let cmpRows = null;
  function renderCompare(pane, R) {
    pane.classList.add('scroll');
    UI.setR0(R);
    if (!cmpRows) {
      busy(true, '算 10 个方案…');
      setTimeout(() => {
        try { cmpRows = MODEL.compare(ST.P); } catch (e) { toast('对比失败'); }
        busy(false);
        cmpRows = cmpRows || [];
        renderCompare(pane, ST.R);
      }, 30);
      pane.innerHTML = `<div class="card"><h3>方案对比</h3><div class="hint">正在算…</div></div>`;
      return;
    }
    pane.innerHTML = UI.compareHTML(cmpRows, window.__auto || null);
    pane.addEventListener('click', e => {
      if (e.target.id === 'doAuto') {
        busy(true, '扫方案…');
        setTimeout(() => {
          let a = [];
          try { a = MODEL.autofix(ST.P); } catch (err) { toast('扫描失败'); }
          window.__auto = a; busy(false);
          renderCompare(pane, ST.R);
        }, 40);
      }
    });
  }

  /* ---------------- 说明 ---------------- */
  function renderDoc(pane, R) {
    pane.classList.add('scroll');
    pane.innerHTML = UI.docHTML(ST.P);
    pane.addEventListener('click', async e => {
      if (e.target.id === 'doSave' || e.target.id === 'doShare' || e.target.id === 'doCopy') {
        const txt = report();
        if (e.target.id === 'doCopy') {
          try { await nat('copy', { text: txt.slice(0, 4000) }); toast('结论已复制'); } catch (err) { toast('复制失败'); }
        } else if (e.target.id === 'doSave') {
          try { const r = JSON.parse(await nat('save', { name: '棚架受力报告.md', text: txt })); toast('已存到：' + r.path); }
          catch (err) { toast('保存失败'); }
        } else {
          try { await nat('share', { title: '棚架受力分析报告', text: txt.slice(0, 6000) }); }
          catch (err) { toast('分享失败'); }
        }
      }
      if (e.target.id === 'doReset') { ST.P = MODEL.defaults(); save(); go('par'); recompute(true); }
    });
  }

  /* ---------------- 报告 ---------------- */
  function report() {
    const R = ST.R, P = ST.P;
    const L = [];
    L.push('# 棚架受力分析报告');
    L.push('');
    L.push('> 由「棚架受力分析」App 生成（简化手算模型，不是施工图，请交结构工程师复核）');
    L.push('');
    L.push('## 一、方案');
    L.push(`- 场地：${P.region}　基本风压 w₀=${P.w0} kN/m²（重现期系数 ${P.w0Factor}）　粗糙度 ${P.rough} 类　计算高度 z=${P.z} m`);
    L.push(`- L 形墙：长边 ${P.Wx} m × 短边 ${P.Wy} m，墙高 ${P.Hw} m`);
    L.push(`- 太阳网：${P.netL} × ${P.netW} = ${R.geo.area.toFixed(2)} m²，透风率 ${(P.porosity * 100).toFixed(0)}%，坡度 ${P.slopeDeg}°`);
    L.push(`- 立柱：${R.geo.cols.length} 根 ${P.secCol}，柱高 ${P.h} m，挑梁 ${P.secBeam}，斜杆 ${P.secDiag}（${P.diagType}${P.diagCable ? '，拉索' : '，刚性'}）`);
    L.push(`- 基础：${P.footB}×${P.footB}×${P.footH} m，地基承载力 ${P.soilFa} kPa，单锚栓 [T]=${P.anchorCap} kN`);
    L.push('');
    L.push('## 二、风荷载');
    L.push(`- μz=${R.W.muz.toFixed(3)}　βgz=${R.W.bgz.toFixed(3)}　w_k=${R.W.wk.toFixed(3)} kN/m²`);
    L.push(`- 风速 v=√(1600w₀)=${R.W.v.toFixed(1)} m/s（${R.W.beaufort}）`);
    L.push(`- 风吸面压 ${R.W.qUp.toFixed(3)} kN/m² → 合力 ${(R.W.qUp * R.geo.area).toFixed(2)} kN`);
    L.push(`- 风压面压 ${R.W.qDown.toFixed(3)} kN/m² → 合力 ${(R.W.qDown * R.geo.area).toFixed(2)} kN`);
    L.push('');
    L.push('## 三、结论');
    L.push(`- 设计风下承载力最大利用率 **${(R.uMax * 100).toFixed(0)}%**，结论：${R.state === 'ok' ? '通过' : R.state === 'warn' ? '临界' : '不通过'}`);
    L.push(`- 安全上限风速 **${R.vmax.toFixed(1)} m/s（${WIND.beaufort(R.vmax)}）**`);
    L.push(`- 控制点：${R.vGovern}`);
    L.push(`- 最不利：${R.worst.col}　${R.worst.name}`);
    L.push(`- 风吸总上抬力 ${(R.totalUplift / 1000).toFixed(2)} kN，柱脚总配重 ${(R.totalBallast / 1000).toFixed(2)} kN`);
    L.push('');
    L.push('## 四、各柱');
    L.push('| 柱 | 端部x | 悬臂长 | 分担宽 | 上拔力 | 基础配重 | K拔 | K倾 | 锚栓拉力 |');
    L.push('|---|---|---|---|---|---|---|---|---|');
    R.foot.forEach(f => {
      L.push(`| ${f.col.id} | ${f.col.tip.x.toFixed(2)} | ${f.col.L.toFixed(2)} | ${f.col.tw.toFixed(2)} | ${(f.uplift / 1000).toFixed(2)} kN | ${(f.ballast / 1000).toFixed(2)} kN | ${f.kUp > 90 ? '—' : f.kUp.toFixed(2)} | ${f.kOver > 90 ? '—' : f.kOver.toFixed(2)} | ${(f.Tbolt / 1000).toFixed(1)} kN |`);
    });
    L.push('');
    L.push('## 五、不通过项（利用率 > 1）');
    const bad = R.checks.filter(c => c.ratio > 1).sort((a, b) => b.ratio - a.ratio);
    if (!bad.length) L.push('无。');
    bad.slice(0, 30).forEach(c => L.push(`- [${c.group}] ${c.name}：${c.value.toFixed(2)} ${c.unit} / 限 ${c.limit.toFixed(2)}　→ ${(c.ratio * 100).toFixed(0)}%　（${c.note || ''}）`));
    L.push('');
    L.push('## 六、提醒');
    (R.warn || []).forEach(w => L.push('- ' + w));
    L.push('- 本模型为简化平面杆系手算模型，未做整体空间分析、节点刚度、二阶效应和网面张拉找形。');
    L.push('- 镀锌管焊接后必须重新防腐。基础土参数须现场确认。');
    L.push('- 请交结构工程师或专业车棚厂家复核后再施工。');
    return L.join('\n');
  }

  /* ---------------- 存取 ---------------- */
  function save() { try { localStorage.setItem(LS, JSON.stringify(ST.P)); } catch (e) { } }
  function load() {
    try {
      const s = localStorage.getItem(LS);
      if (s) ST.P = Object.assign(MODEL.defaults(), JSON.parse(s));
    } catch (e) { }
  }

  /* ---------------- 启动 ---------------- */
  function boot() {
    load();
    $$('#tabs .tab').forEach(t => t.addEventListener('click', () => go(t.dataset.t)));
    window.addEventListener('resize', () => {
      if (ST.tab === 's3') V3.resize();
      else if (ST.tab === 's2') redraw2D();
    });
    window.addEventListener('orientationchange', () => setTimeout(() => {
      if (ST.tab === 's3') V3.resize(); else if (ST.tab === 's2') redraw2D();
    }, 260));
    window.__back = function () {
      if (ST.tab !== 's3') { go('s3'); return; }
      try { nat('exit'); } catch (e) { }
    };
    // 先算一遍再进第一个 tab
    recompute(true);
    go(ST.tab);
    ST.ready = true;
  }
  document.addEventListener('DOMContentLoaded', boot);
  if (document.readyState !== 'loading') boot();

  window.__ST = ST;
})();
