/* =====================================================================
   ui.js —— 参数面板 / 校核表 / 方案对比 / 说明书
   ===================================================================== */
const UI = (function () {

  const $ = s => document.querySelector(s);
  const $$ = s => Array.prototype.slice.call(document.querySelectorAll(s));
  const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const f2 = v => (Math.abs(v) >= 1000 ? v.toFixed(0) : Math.abs(v) >= 100 ? v.toFixed(1) : v.toFixed(2));
  const pct = r => r >= 99.9 ? '>9999%' : r >= 9.99 ? '>' + (Math.floor(r * 100) / 100 * 100).toFixed(0) + '%' : (r * 100).toFixed(0) + '%';

  const SEL = k => SOLVER.PIPE_MAP[k] ? k : 'Φ89x3.0';
  const REG = Object.keys(WIND.REGIONS);

  /* ---------------- 参数表结构 ---------------- */
  const SPEC = [
    { g: '场地与风荷载', hint: '风和地区参数决定一切。w_k = βgz·μz·μs·w0', items: [
      { k: 'region', t: 'sel', label: '地区（自动给 w0）', opts: REG.map(r => [r, r + (r === '自定义' ? '' : '  ' + WIND.REGIONS[r].toFixed(2))]) },
      { k: 'w0', t: 'rng', label: '基本风压 w0 (kN/m²)', min: .20, max: 1.20, step: .05, d: 2 },
      { k: 'w0Factor', t: 'sel', label: '重现期', opts: [['1', '50 年（规范标准）'], ['0.75', '10 年'], ['0.6', '5 年']], num: 1 },
      { k: 'rough', t: 'sel', label: '地面粗糙度', opts: Object.keys(WIND.ROUGH).map(k => [k, WIND.ROUGH[k].t]) },
      { k: 'z', t: 'rng', label: '计算高度 z (m)', min: 3, max: 20, step: .5, d: 1 },
      { k: 'porosity', t: 'rng', label: '网布透风率', min: 0, max: .85, step: .05, pct: 1 },
      { k: 'cManual', t: 'bool', label: '手动指定体型系数' },
      { k: 'Cup', t: 'rng', label: '　风吸系数 μs吸', min: .05, max: 1.6, step: .05, d: 2, dep: 'cManual' },
      { k: 'Cdown', t: 'rng', label: '　风压系数 μs压', min: .02, max: 1.0, step: .02, d: 2, dep: 'cManual' },
      { k: 'Cdrag', t: 'rng', label: '　水平风系数 μs横', min: .05, max: 1.8, step: .05, d: 2, dep: 'cManual' },
    ]},
    { g: '几何尺寸', hint: 'L 形墙 + 网面 + 柱高。挑出越大、柱越稀，越难扛。', items: [
      { k: 'Wx', t: 'rng', label: '长边墙长 (m)', min: 3, max: 15, step: .5, d: 1 },
      { k: 'Wy', t: 'rng', label: '短边墙长 (m)', min: 2, max: 15, step: .5, d: 1 },
      { k: 'Hw', t: 'rng', label: '墙高 (m)', min: .8, max: 3.2, step: .1, d: 1 },
      { k: 'netL', t: 'rng', label: '网沿墙长度 (m)', min: 2, max: 15, step: .5, d: 1 },
      { k: 'netW', t: 'rng', label: '★ 向院内挑出 (m)', min: 1, max: 6, step: .25, d: 2 },
      { k: 'slopeDeg', t: 'rng', label: '网面排水坡度 (°)', min: 0, max: 15, step: 1, d: 0 },
      { k: 'h', t: 'rng', label: '★ 挑梁标高 / 柱高 (m)', min: 2, max: 4, step: .1, d: 1 },
      { k: 'r', t: 'rng', label: '三角挑梁高度 r (m)', min: 0, max: 3, step: .1, d: 1 },
      { k: 'nCol', t: 'rng', label: '★ 立柱根数', min: 2, max: 6, step: 1, d: 0 },
      { k: 'wallGap', t: 'rng', label: '柱脚离墙距离 (m)', min: .1, max: 1.2, step: .05, d: 2 },
      { k: 'netDeployed', t: 'bool', label: '网已张开（不开＝已收网）' },
      { k: 'stowFactor', t: 'rng', label: '　收网后受风折减', min: .05, max: .6, step: .05, pct: 1, dep: 'stowInverse' },
    ]},
    { g: '构件截面（镀锌管）', hint: '焊接三角挑梁。悬臂弯矩 = P·L，截面 W 不够就白搭。', items: [
      { k: 'secCol', t: 'sel', label: '立柱管', opts: SOLVER.PIPE_LIST.map(p => [p[0], p[0] + '  W=' + (p[1].W * 1e9).toFixed(1) + 'cm³']) },
      { k: 'secBeam', t: 'sel', label: '挑梁管', opts: SOLVER.PIPE_LIST.map(p => [p[0], p[0] + '  W=' + (p[1].W * 1e9).toFixed(1) + 'cm³']) },
      { k: 'secDiag', t: 'sel', label: '斜杆', opts: SOLVER.PIPE_LIST.map(p => [p[0], p[0] + '  A=' + (p[1].A * 1e6).toFixed(0) + 'mm²']) },
      { k: 'secLong', t: 'sel', label: '纵梁/边梁', opts: SOLVER.PIPE_LIST.map(p => [p[0], p[0]]) },
      { k: 'diagType', t: 'sel', label: '三角斜撑形式', opts: [['above', '上斜拉（挑梁上方）'], ['below', '下撑（挑梁下方）'], ['none', '不设斜撑']] },
      { k: 'diagCable', t: 'bool', label: '斜杆当拉索（只能受拉）' },
      { k: 'kCol', t: 'rng', label: '柱计算长度系数 k', min: 1, max: 2.5, step: .1, d: 1 },
      { k: 'kBeam', t: 'rng', label: '挑梁计算长度系数 k', min: 1, max: 2.5, step: .1, d: 1 },
      { k: 'fy', t: 'sel', label: '钢材牌号', opts: [['235', 'Q235（f=215MPa）'], ['345', 'Q355（f=305MPa）']], num: 1 },
    ]},
    { g: '柱脚基础与锚固', hint: '★ 风吸工况下，基础配重和锚固往往才是真正卡脖子的地方。', items: [
      { k: 'footB', t: 'rng', label: '★ 独立基础边长 (m)', min: .4, max: 3, step: .1, d: 1 },
      { k: 'footH', t: 'rng', label: '★ 基础厚度/埋深 (m)', min: .25, max: 1.5, step: .05, d: 2 },
      { k: 'footN', t: 'rng', label: '每柱基础个数', min: 0.5, max: 2, step: 0.5, d: 1 },
      { k: 'soilFa', t: 'rng', label: '地基承载力 fa (kPa)', min: 40, max: 300, step: 10, d: 0 },
      { k: 'anchorCap', t: 'rng', label: '单锚栓抗拔设计值 (kN)', min: 8, max: 120, step: 2, d: 0 },
      { k: 'anchorN', t: 'rng', label: '受拉侧锚栓数', min: 1, max: 8, step: 1, d: 0 },
      { k: 'basePlateLever', t: 'rng', label: '锚栓力臂 a (m)', min: .15, max: 1.0, step: .05, d: 2 },
    ]},
    { g: '墙与网的关系', hint: '砖墙只能帮“往下压”的忙，帮不了“往上拔”。', items: [
      { k: 'wallAnchored', t: 'bool', label: '网有锚固在砖墙上' },
      { k: 'wallShare', t: 'rng', label: '　墙分担竖向荷载比例', min: 0, max: .6, step: .05, pct: 1, dep: 'wallAnchored' },
      { k: 'netMass', t: 'rng', label: '网自重 (kg/m²)', min: .02, max: .5, step: .01, d: 2 },
    ]},
    { g: '分项系数', hint: 'GB50009 / GB50017 常用取值。', items: [
      { k: 'gammaG', t: 'rng', label: '永久荷载分项系数 γG', min: 1, max: 1.5, step: .05, d: 2 },
      { k: 'gammaW', t: 'rng', label: '风荷载分项系数 γW', min: 1, max: 1.8, step: .05, d: 2 },
    ]},
  ];

  /* ---------------- 渲染参数面板 ---------------- */
  function paramsHTML(P) {
    let h = '';
    for (const sec of SPEC) {
      h += `<div class="card"><h3>${sec.g}<span class="sub">${esc(sec.hint || '')}</span></h3>`;
      for (const it of sec.items) {
        const v = P[it.k];
        h += `<div class="row" data-k="${it.k}" data-dep="${it.dep || ''}"><label>${esc(it.label)}</label><div class="ctl">`;
        if (it.t === 'rng') {
          h += `<input type="range" data-k="${it.k}" min="${it.min}" max="${it.max}" step="${it.step}" value="${v}">`
             + `<output data-o="${it.k}">${fmtV(it, v)}</output>`;
        } else if (it.t === 'sel') {
          h += `<select data-k="${it.k}">` + it.opts.map(o =>
            `<option value="${o[0]}"${String(o[0]) === String(v) ? ' selected' : ''}>${esc(o[1])}</option>`).join('') + `</select>`;
        } else if (it.t === 'bool') {
          h += `<select data-k="${it.k}" data-bool="1"><option value="1"${v ? ' selected' : ''}>是</option><option value="0"${!v ? ' selected' : ''}>否</option></select>`;
        }
        h += `</div></div>`;
      }
      h += `</div>`;
    }
    return h;
  }
  function fmtV(it, v) {
    if (it.pct) return (v * 100).toFixed(0) + '%';
    const d = it.d === undefined ? 2 : it.d;
    return (+v).toFixed(d);
  }

  function bindParams(root, P, onChange) {
    root.querySelectorAll('[data-k]').forEach(el => {
      const k = el.dataset.k;
      if (el.tagName === 'INPUT' || el.tagName === 'SELECT') {
        el.addEventListener('input', () => {
          let v;
          if (el.dataset.bool) v = el.value === '1';
          else if (el.type === 'range') v = parseFloat(el.value);
          else if (el.tagName === 'SELECT') {
            v = el.value;
            if (k === 'fy' || k === 'w0Factor') v = parseFloat(v);
            if (k === 'region') { P.w0 = WIND.REGIONS[v]; }
          } else v = el.value;
          P[k] = v;
          const o = root.querySelector(`[data-o="${k}"]`);
          if (o) {
            const spec = SPEC.flatMap(s => s.items).find(s => s.k === k);
            o.textContent = fmtV(spec, v);
          }
          if (k === 'fy') { P.fd = (v === 345 ? 305 : 215); P.fv = (v === 345 ? 175 : 125); }
          if (k === 'w0' || k === 'region') {
            const wi = root.querySelector('[data-k="w0"]');
            if (wi && k === 'region') { wi.value = P.w0; root.querySelector('[data-o="w0"]').textContent = (+P.w0).toFixed(2); }
          }
          bindDeps(root, P);
          onChange(k);
        });
      }
    });
    bindDeps(root, P);
  }
  function bindDeps(root, P) {
    root.querySelectorAll('[data-k][data-dep]').forEach(row => {
      const d = row.dataset.dep;
      if (!d) return;
      const dep = d === 'stowInverse' ? !P.netDeployed : !!P[d];
      row.style.display = dep ? '' : 'none';
    });
  }


  /* ---------------- 加固档位（预设） ---------------- */
  function presetBarHTML(cur) {
    let h = `<div class="card"><h3>加固档位<span class="sub">点一下直接套用</span></h3>
      <div class="chips">`;
    for (const p of MODEL.PRESETS) {
      h += `<button class="pchip" data-p="${p.id}">${p.name.replace('★', '★ ')}</button>`;
    }
    h += `</div><div class="hint" id="pdesc">档位从“原方案”一档一档加上去：每加一档都实算一遍，
      能看到风从 5 级一路涨到 14 级。具体数值见「对比」页。</div></div>`;
    return h;
  }
  function presetDesc(id) {
    const p = MODEL.PRESETS.find(x => x.id === id);
    return p ? `${p.name}：${p.desc}` : '';
  }

  /* ---------------- 加固档位表（对比页） ---------------- */
  function presetTable(rows, curId) {
    let h = `<div class="card"><h3>加固档位：每一步值多少<span class="sub">同一套参数实算</span></h3>
      <div class="tw"><table><tr><th>档位</th><th class="num">能扛</th><th class="num">风级</th>
      <th class="num">利用率</th><th class="num">钢材</th><th class="num">砼</th><th class="num">估算</th></tr>`;
    rows.forEach(r => {
      const col = r.u <= 0.85 ? '#44C7A9' : r.u <= 1.0 ? '#FFB84D' : '#FF6B6B';
      h += `<tr class="prow${r.id === curId ? ' pick' : ''}" data-p="${r.id}">
        <td><b>${r.id}</b> ${esc(r.name)}<br><span style="color:#5F7381;font-size:10px">${esc(r.desc)}</span></td>
        <td class="num" style="color:${col};font-weight:600">${r.vmax.toFixed(1)}</td>
        <td class="num">${esc(r.beaufort)}</td>
        <td class="num">${(r.u * 100).toFixed(0)}%</td>
        <td class="num">${r.steel.toFixed(0)}kg</td>
        <td class="num">${r.conc.toFixed(2)}</td>
        <td class="num">${r.cost.toFixed(0)}</td></tr>`;
    });
    h += `</table></div>
      <div class="hint">点任意一行就套用这个档位。<b>注意卡口会搬家</b>：先是管子截面 → 然后是基础配重 →
      然后是柱脚锚栓 → 最后才轮到“挑出长度”。所以只换粗管子没用，得一路做到底。<br>
      P3（★完整三管方案）= Φ219×6 管子 + 刚性下撑 + 1.6m 独立基础 + 做足柱脚锚固，
      <b>三根柱子就能扛 12 级飓风</b>，钢材约 630kg、混凝土约 7.7m³。</div></div>`;
    return h;
  }

  /* ---------------- 结论文字 ---------------- */
  function rootCause(R) {
    const gov = R.vGovern || '';
    // 优先用"反算出来的控制点"，它才是决定能扛多大风的那一项
    let c = null;
    if (gov && gov !== '—') {
      c = R.checks.filter(x => x.uls).find(x => gov.indexOf(x.group) === 0 && gov.indexOf(x.name.split(' ')[0]) >= 0)
        || R.checks.filter(x => x.uls).find(x => gov.indexOf(x.group) === 0);
    }
    if (!c) c = R.checks.filter(x => x.uls && x.ratio > 1).sort((a, b) => b.ratio - a.ratio)[0];
    if (!c) return null;
    const g = c.group;
    let s = '';
    if (g === '立柱') s = '立柱管截面太小 —— 柱底弯矩几乎全靠这根管子的抗弯截面 W 扛，管壁一薄就顶不住。换大方管/厚壁管比加锚栓有用得多。';
    else if (g === '挑梁') s = '挑梁管的抗弯截面不够 —— 悬臂越长越吃亏（弯矩 ≈ 竖向力 × 悬臂长度），或者挑梁根部没有有效斜撑。';
    else if (g === '斜杆') s = '斜杆不够 —— 三角高度 r 越小，斜杆内力越大（≈ 竖向力 × 斜长 / r）。加大 r 或换粗管。';
    else if (g === '基础' && c.name.indexOf('抗拔') >= 0) s = '柱脚压不住 —— 风吸把整片网连同柱子往上提，基础配重/入土深度不够，得靠配重或地锚把结构“拽在地上”。';
    else if (g === '基础' && c.name.indexOf('抗倾覆') >= 0) s = '柱脚绕边倾覆 —— 柱子贴着墙、力臂短，上抬力和悬臂形成很大的倾覆力矩，基础太小压不住。';
    else if (g === '基础') s = '基础底面积不够，地基压力超了，基础会不均匀下沉。';
    else if (g === '柱脚') s = '柱脚锚栓扛不住拉力 —— 底座和锚栓要能把这个弯矩传进混凝土，M/a 就是锚栓要受的力。';
    else if (g === '整体') s = '整体抗倾覆不足 —— 柱子全贴墙，抵抗力臂很短，只能靠配重。';
    else if (g === '纵梁') s = '沿墙方向的纵梁/平面外支撑不够，横向风会让柱列侧向失稳。';
    return { c, s };
  }

  function verdictHTML(R) {
    const rc = rootCause(R);
    const cls = R.state === 'ok' ? 'ok' : R.state === 'warn' ? 'warn' : 'bad';
    const v = R.W.v, bf = R.W.beaufort;
    let h = `<div class="banner ${cls}">`;
    if (R.state === 'ok') {
      h += `<b>按现有参数，这套方案能过关。</b><br>设计风（${bf}，${v.toFixed(0)} m/s）下，最大承载力利用率 ${pct(R.uMax)}；
      反算能扛 <b>${R.vmax.toFixed(1)} m/s（${WIND.beaufort(R.vmax)}）</b>。<br>
      控制点：${esc(R.vGovern || '—')}。`;
    } else if (R.vmax <= 0) {
      h += `<b>自重状态下就已经不满足了。</b>参数里有硬伤，先把最不利项改掉。`;
    } else {
      h += `<b>这套方案扛不住设计风。</b><br>
      设计风是 ${v.toFixed(0)} m/s（${bf}，w₀=${R.W.w0.toFixed(2)} kN/m²），而按现在的柱、管、基础，
      <b>大约 ${R.vmax.toFixed(1)} m/s（${WIND.beaufort(R.vmax)}）就会出现第一个破坏点</b>：<br>
      <span style="color:#fff">${esc(R.vGovern || '—')}</span>，利用率 ${pct(R.uMax)}。`;
      if (rc) h += `<br><br><b>根因：</b>${esc(rc.s)}`;
    }
    h += `<br><br>风吸总上抬力 <b>${(R.W.qUp * R.geo.area).toFixed(1)} kN</b>（≈ ${(R.W.qUp * R.geo.area * 100).toFixed(0)} kg 往上提）。`;
    if (R.P.layout === 'house') {
      h += `这一侧<b>全部交给主楼的混凝土框架</b>：不需要基础，地面一根柱子都没有。`;
    } else {
      h += `柱脚总配重 ${(R.totalBallast / 1000).toFixed(1)} kN —— 2 m 砖围墙帮不了上拔，只能靠基础自重扛。`;
    }
    if (R.deflFailAtRest) h += `<br>另外：φ 管太软，连自重下的悬臂端挠度都超 L/150，网会明显下垂（正常使用极限状态，不致命但难看）。`;
    h += `</div>`;
    return h;
  }

  /* ---------------- 校核表 ---------------- */
  function checksHTML(R) {
    const groups = ['挑梁', '立柱', '斜杆', '柱脚', '基础', '整体', '纵梁'];
    let h = '';
    h += `<div class="card"><h3>关键数字<span class="sub">当前参数</span></h3>`;
    const kv = [
      ['网面积', R.geo.area.toFixed(2) + ' m²'],
      ['基本风压 w₀', R.W.w0.toFixed(2) + ' kN/m²'],
      ['风压 w_k=βgz·μz·w₀', R.W.wk.toFixed(3) + ' kN/m²'],
      ['风速 v=√(1600w₀)', R.W.v.toFixed(1) + ' m/s · ' + R.W.beaufort],
      ['风吸面压 μs·w_k', R.W.qUp.toFixed(3) + ' kN/m²'],
      ['风吸合力', (R.W.qUp * R.geo.area).toFixed(2) + ' kN'],
      ['各柱分担宽度', R.geo.cols.map(c => c.tw.toFixed(2)).join(' / ') + ' m'],
      ['最大悬臂', Math.max(...R.geo.cols.map(c => c.L)).toFixed(2) + ' m'],
      ['承载力最大利用率', (R.uMax * 100).toFixed(0) + '%'],
      ['挠度最大利用率', (R.dMax * 100).toFixed(0) + '%'],
      ['强度控制点', R.vGovern],
      ['能扛风速', R.vmax.toFixed(1) + ' m/s（' + WIND.beaufort(R.vmax) + '）'],
    ];
    kv.forEach(r => h += `<div class="kv"><span class="kk">${esc(r[0])}</span><span class="vv">${esc(r[1])}</span></div>`);
    h += `</div>`;

    if (R.warn && R.warn.length) {
      h += `<div class="card"><h3>要注意的地方</h3><div class="warnlist">` +
        R.warn.map(w => `<div>${esc(w)}</div>`).join('') + `</div></div>`;
    }

    h += `<div class="card"><h3>全部校核条目<span class="sub">共 ${R.checks.length} 条</span></h3>`;
    for (const g of groups) {
      const cs = R.checks.filter(c => c.group === g);
      if (!cs.length) continue;
      h += `<div class="grp">${g}</div>`;
      cs.forEach(c => {
        const barw = Math.min(c.ratio, 1.6) / 1.6 * 100;
        h += `<div class="chk">
          <div class="nm">${esc(c.name)}<small>${esc(c.note || '')}　${esc(c.formula || '')}</small>
            <div class="bar"><i class="${c.verdict}" style="width:${barw.toFixed(0)}%"></i></div></div>
          <div class="val">${f2(c.value)}<small>/${f2(c.limit)}</small><br>
            <span class="tag">${pct(c.ratio)}</span></div>
        </div>`;
      });
    }
    h += `</div>`;
    return h;
  }

  /* ---------------- 方案对比 ---------------- */
  function compareHTML(rows, auto) {
    let h = '';
    h += verdictCompare(rows);
    h += `<div class="card"><h3>方案对比<span class="sub">按能扛风速排序</span></h3>
      <div class="tw"><table><tr><th>方案</th><th class="num">能扛</th><th class="num">风级</th><th class="num">利用率</th><th class="num">钢材</th><th class="num">混凝土</th></tr>`;
    rows.forEach((r, i) => {
      const cls = r.state === 'ok' ? 'ok' : r.state === 'warn' ? 'warn' : 'bad';
      h += `<tr${i === 0 ? ' class="pick"' : ''}>
        <td><b>${r.id}</b> ${esc(r.name)}</td>
        <td class="num" style="color:${r.state === 'ok' ? '#44C7A9' : r.state === 'warn' ? '#FFB84D' : '#FF6B6B'}">${(r.vmax || 0).toFixed(1)}</td>
        <td class="num">${esc(r.beaufort || '')}</td>
        <td class="num">${pct(r.uMax)}</td>
        <td class="num">${(r.steel || 0).toFixed(0)}kg</td>
        <td class="num">${(r.concrete || 0).toFixed(2)}m³</td></tr>`;
    });
    h += `</table></div><div class="hint">钢材约 9 元/kg、混凝土约 600 元/m³（含开挖浇筑），只做量级参考。加柱/换管/加大基础三件事里，<b>加大基础</b>对“不被掀翻”最直接，<b>加柱 + 缩短悬臂</b>对“管子受力”最直接。</div></div>`;

    h += `<div class="card"><h3>自动找方案<span class="sub">在设计风下各校核 ≤ 0.9</span></h3>`;
    if (!auto) {
      h += `<div class="hint">点下面按钮，在「加柱 / 换管 / 加大基础 / 改斜撑」的组合里扫一遍，按造价从低到高列出来。</div>`;
    } else if (!auto.length) {
      h += `<div class="banner bad">在当前设计风下，扫遍所有组合都过不了。说明<b>这片 32 m² 的网在 ${R0v()} 级风下根本不该张开</b>——先考虑大风前收网，或者把网做小。</div>`;
    } else {
      h += `<div class="tw"><table><tr><th>方案</th><th class="num">利用率</th><th class="num">钢材</th><th class="num">混凝土</th><th class="num">估算</th></tr>`;
      auto.forEach(a => {
        h += `<tr class="pick"><td><b>${a.n} 柱</b> ${esc(a.sec)}　基础 ${a.fb}×${a.fb}×${a.P.footH.toFixed(2)} m　${esc(a.dg)}</td>
          <td class="num">${pct(a.uMax)}</td>
          <td class="num">${a.steel.toFixed(0)}kg</td>
          <td class="num">${a.conc.toFixed(2)}m³</td>
          <td class="num">≈¥${a.cost.toFixed(0)}</td></tr>`;
      });
      h += `</table></div><div class="hint">这是<b>满足设计风</b>的最低配组合（不是施工图）。真做的时候钢材规格、焊缝、锚栓还要按实际产品参数复算。</div>`;
    }
    h += `<div class="btns"><button class="pri" id="doAuto">开始自动找方案</button></div></div>`;
    return h;
  }
  let _R0 = null;
  function R0v() { return _R0 ? _R0.W.beaufort : ''; }
  function verdictCompare(rows) {
    if (!rows.length) return '';
    const best = rows[0];
    const a = rows.find(r => r.id === 'A') || best;
    let h = '';
    const cls = a.state === 'ok' ? 'ok' : a.state === 'warn' ? 'warn' : 'bad';
    h += `<div class="banner ${cls}"><b>原方案（3 柱 + Φ89 挑梁 + 拉索）只能扛 ${(a.vmax || 0).toFixed(1)} m/s（${esc(a.beaufort || '')}）。</b><br>
      单看某一项加固：加柱、换管、加大基础、收网，效果差别很大 —— 下面按能扛风速排序。
      ${best && best.id !== 'A' ? `其中最有效的单项是 <b>${esc(best.name)}</b>（${(best.vmax || 0).toFixed(1)} m/s）。` : ''}
      注意：<b>收网只能减小受风面积，替代不了结构设计</b>，而且突发阵风可能来不及收。</div>`;
    return h;
  }
  function setR0(R) { _R0 = R; }

  /* ---------------- 说明书 ---------------- */
  function docHTML(P) {
    return `
<div class="card doc">
  <h3>这个 App 在算什么</h3>
  <p>它把「主楼前院子 + 太阳网车棚」变成一个小型平面刚架有限元模型，按 GB 50009 / GB 50017
  的体系算风荷载、算内力、算截面应力和稳定，再校核墙锚固或柱脚基础。</p>

  <h4>1. 场地（按 Blender 模型实测）</h4>
  <ul>
    <li><b>主楼</b> 9.6 × 10 m，13.6 m 高，4 层混凝土框架。楼板/圈梁在 <code>z = 2.75~3.40 / 6.24~6.40 / 9.24~9.40</code>
      —— 这是最好的锚固位置（必须锚进梁柱，不能锚在窗下填充墙上）。</li>
    <li><b>院子</b> 约 11.7 × 9.8 m（约 115 m²）。</li>
    <li><b>围墙</b> 2.0 m 高。它只帮「往下压」的忙，<b>帮不了「往上拔」</b>——所以靠围墙那侧只能做小挑檐。</li>
  </ul>

  <h4>2. 两种支承，差别极大</h4>
  <ul>
    <li><b>靠主楼悬挑</b>（推荐）：托架锚在主楼墙上，上抬和下压都变成一对力偶交给 4 层框架。
      <b>不需要任何基础，地面零占用</b>。挑出 4~4.5 m 轻松扛 17 级。</li>
    <li><b>靠围墙立柱</b>：2 m 砖墙帮不了上拔，柱脚要吃 <code>M = P·L</code> 的倾覆，基础会很大，
      挑出只能做到 <b>2 m 左右</b>。</li>
  </ul>

  <h4>3. 钢丝绳能不能用？</h4>
  <p><b>能，但必须上下各一根。</b>一根绳只能受拉：</p>
  <ul>
    <li>下压工况 → <b>上面的绳</b>受拉，管用；</li>
    <li>风吸上抬 → 上面的绳受压失效，必须靠 <b>下面的绳</b>受拉把网拽住。</li>
  </ul>
  <p>App 里 <code>H4 钢丝绳·上下双拉</code> 能扛 13 级；<code>H4b 只上拉</code> 只有 8 级。
  而<b>一根刚性管上下都管用</b>，所以更推荐刚性斜撑（17 级）。</p>

  <h4>4. 风荷载</h4>
  <p><code>w_k = β_gz · μ_s · μ_z · w_0</code>；μ_z/β_gz 按 A/B/C/D 粗糙度查表，μ_s 按网布透风率折减。
  三个工况：① 风吸上抬 ② 风压向下 ③ 水平风。</p>

  <h4>5. 内力与校核</h4>
  <p>平面<b>直接刚度法</b>：节点 3 自由度、2 节点 6 自由度梁单元，端部释放用静力凝聚，
  受拉构件用「仅受拉迭代」（受压就退出重算）。校核：
  <code>σ = N/(φA) + M/W ≤ f</code>、<code>τ ≈ 2V/A ≤ f_v</code>、<code>δ ≤ L/150</code>、
  <code>λ ≤ 150</code>、墙锚栓 <code>T = 斜撑轴力</code> 与 <code>T = M/a − N/2</code>。</p>

  <h4>6. 它算不了什么（重要）</h4>
  <ul>
    <li>不是有限元软件，<b>不替代结构工程师</b>；没做整体空间分析、二阶效应、网面张拉找形。</li>
    <li>体型系数是工程近似，不是风洞数据。</li>
    <li>焊缝、锚栓长期耐久、防水、施工质量都没算。</li>
  </ul>
  <p style="color:#FFB84D"><b>施工前请把结果拿给结构工程师或做车棚的厂家复核。</b>
  尤其在主楼墙上打化学锚栓这件事，必须先确认那面墙是混凝土梁柱还是砌体填充墙。</p>

  <h4>7. 现在的参数</h4>
  <p style="font-size:11.5px">${esc(JSON.stringify({
    布局: P.layout === 'house' ? '靠主楼悬挑' : '靠墙立柱',
    风压: P.w0, 粗糙度: P.rough,
    网: P.netL + '×' + P.netW,
    标高: P.layout === 'house' ? P.wallZs : P.h,
    锚高: P.anchorZ,
    挑臂: P.secBeam, 斜撑: P.secDiag + (P.diagCable ? '(绳)' : '(刚性)'),
  }))}</p>
</div>
<div class="card"><h3>导出</h3>
  <div class="btns">
    <button class="pri" id="doSave">导出计算报告 (md)</button>
    <button id="doShare">分享报告</button>
    <button id="doCopy">复制结论</button>
    <button id="doReset">恢复默认参数</button>
  </div>
  <div class="hint">报告存到 App 的「导出」目录，也可以在系统分享里发出去。</div>
</div>`;
  }

  return { paramsHTML, bindParams, checksHTML, compareHTML, docHTML, verdictHTML, setR0, rootCause, f2, esc, SPEC,
           presetBarHTML, presetDesc, presetTable, bindDeps };
})();
