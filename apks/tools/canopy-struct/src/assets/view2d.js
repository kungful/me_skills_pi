/* =====================================================================
   view2d.js —— 平面图 / 立面内力图 / 传力路径图（纯 canvas 2D）
   ===================================================================== */
const V2 = (function () {

  const COL = {
    bg: '#0A0F13', grid: '#131D24', line: '#2A3A45', dim: '#6E8492', dim2: '#4A5B67', text: '#C8D6DF',
    wall: '#8b6a58', wall2: '#4A5B67', net: '#2FBF9B', steel: '#9FB4C2', acc: '#44C7A9',
    bad: '#FF6B6B', warn: '#FFB84D', blue: '#5CC8FF', load: '#FF9F43', reac: '#5CC8FF', mm: '#5CC8FF',
  };

  function prep(cv, hpx) {
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    const w = Math.max(220, cv.clientWidth || cv.parentElement && cv.parentElement.clientWidth || 320);
    const h = hpx || Math.round(w * 0.62);
    cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
    cv.style.height = h + 'px';
    const g = cv.getContext('2d');
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    g.fillStyle = COL.bg; g.fillRect(0, 0, w, h);
    return { g, w, h };
  }

  function fit(w, h, x0, x1, y0, y1, pad) {
    pad = pad === undefined ? 26 : pad;
    const s = Math.min((w - pad * 2) / Math.max(x1 - x0, .001), (h - pad * 2) / Math.max(y1 - y0, .001));
    const ox = (w - (x1 - x0) * s) / 2 - x0 * s;
    const oy = (h + (y1 - y0) * s) / 2 + y0 * s;
    return { s, X: x => ox + x * s, Y: y => oy - y * s };
  }

  function arrow(g, x1, y1, x2, y2, col, wid, head) {
    wid = wid || 2; head = head || 7;
    const a = Math.atan2(y2 - y1, x2 - x1);
    g.strokeStyle = col; g.fillStyle = col; g.lineWidth = wid; g.lineCap = 'round';
    g.beginPath(); g.moveTo(x1, y1); g.lineTo(x2 - Math.cos(a) * head * .8, y2 - Math.sin(a) * head * .8); g.stroke();
    g.beginPath(); g.moveTo(x2, y2);
    g.lineTo(x2 - Math.cos(a - .42) * head, y2 - Math.sin(a - .42) * head);
    g.lineTo(x2 - Math.cos(a + .42) * head, y2 - Math.sin(a + .42) * head);
    g.closePath(); g.fill();
  }
  function txt(g, s, x, y, col, size, align, bold) {
    g.fillStyle = col || COL.dim;
    g.font = (bold ? '600 ' : '') + (size || 11) + 'px -apple-system,"Microsoft YaHei",sans-serif';
    g.textAlign = align || 'left'; g.textBaseline = 'middle';
    g.fillText(s, x, y);
  }
  function vtxt(g, s, x, y, col, size) {
    g.save(); g.translate(x, y); g.rotate(-Math.PI / 2);
    txt(g, s, 0, 0, col, size || 10.5, 'center'); g.restore();
  }
  function dimLine(g, f, x1, y1, x2, y2, off, col) {
    const ax = f.X(x1), ay = f.Y(y1), bx = f.X(x2), by = f.Y(y2);
    const dx = bx - ax, dy = by - ay, L = Math.hypot(dx, dy) || 1;
    const nx = -dy / L * (off || 0), ny = dx / L * (off || 0);
    g.strokeStyle = col || COL.line; g.lineWidth = 1; g.setLineDash([]);
    g.beginPath();
    g.moveTo(ax, ay); g.lineTo(ax + nx, ay + ny);
    g.moveTo(bx, by); g.lineTo(bx + nx, by + ny);
    g.moveTo(ax + nx, ay + ny); g.lineTo(bx + nx, by + ny);
    g.stroke();
    // 端头小撇
    const ux = dx / L, uy = dy / L;
    g.beginPath();
    g.moveTo(ax + nx - ux * 3, ay + ny - uy * 3); g.lineTo(ax + nx + ux * 3, ay + ny + uy * 3);
    g.moveTo(bx + nx - ux * 3, by + ny - uy * 3); g.lineTo(bx + nx + ux * 3, by + ny + uy * 3);
    g.stroke();
    return { mx: (ax + bx) / 2 + nx, my: (ay + by) / 2 + ny, vert: Math.abs(dy) > Math.abs(dx) };
  }

  /* ==================== 平面图 ==================== */
  function plan(cv, R, opt) {
    opt = opt || {};
    const { g, w, h } = prep(cv, opt.hpx);
    const geo = R.geo, P = R.P;
    const x1 = Math.max(P.Wx, geo.netL) + 0.45, y1 = Math.max(P.Wy, geo.netW) + 1.30;
    const f = fit(w, h, -0.8, x1, -0.75, y1, 26);

    g.strokeStyle = COL.grid; g.lineWidth = 1;
    for (let i = 0; i <= Math.ceil(x1); i++) { g.beginPath(); g.moveTo(f.X(i), f.Y(-0.75)); g.lineTo(f.X(i), f.Y(y1)); g.stroke(); }
    for (let j = 0; j <= Math.ceil(y1); j++) { g.beginPath(); g.moveTo(f.X(-0.8), f.Y(j)); g.lineTo(f.X(x1), f.Y(j)); g.stroke(); }

    // 网面
    g.fillStyle = 'rgba(47,191,155,.16)';
    g.fillRect(f.X(0), f.Y(geo.netW), geo.netL * f.s, geo.netW * f.s);
    g.strokeStyle = 'rgba(47,191,155,.24)'; g.lineWidth = 1;
    for (let i = .5; i < geo.netL; i += .5) { g.beginPath(); g.moveTo(f.X(i), f.Y(0)); g.lineTo(f.X(i), f.Y(geo.netW)); g.stroke(); }
    for (let j = .5; j < geo.netW; j += .5) { g.beginPath(); g.moveTo(f.X(0), f.Y(j)); g.lineTo(f.X(geo.netL), f.Y(j)); g.stroke(); }
    g.strokeStyle = COL.net; g.lineWidth = 2;
    g.strokeRect(f.X(0), f.Y(geo.netW), geo.netL * f.s, geo.netW * f.s);
    txt(g, `太阳网 ${geo.area.toFixed(1)} m²　透风率 ${(P.porosity * 100).toFixed(0)}%`,
        f.X(geo.netL / 2), f.Y(geo.netW * 0.60), COL.net, 12, 'center', true);

    // 分担边界
    const xs = geo.cols.map(c => c.tip.x).slice().sort((a, b) => a - b);
    const bd = [0];
    for (let i = 0; i < xs.length - 1; i++) bd.push((xs[i] + xs[i + 1]) / 2);
    bd.push(geo.netL);
    g.strokeStyle = 'rgba(255,184,77,.5)'; g.lineWidth = 1; g.setLineDash([5, 4]);
    for (let i = 1; i < bd.length - 1; i++) {
      g.beginPath(); g.moveTo(f.X(bd[i]), f.Y(-0.15)); g.lineTo(f.X(bd[i]), f.Y(geo.netW)); g.stroke();
    }
    g.setLineDash([]);
    geo.cols.forEach(c => {
      const k = xs.indexOf(c.tip.x);
      txt(g, c.tw.toFixed(2) + 'm', f.X((bd[k] + bd[k + 1]) / 2), f.Y(geo.netW) + 12, COL.warn, 10.5, 'center', true);
    });

    // L 形墙
    g.strokeStyle = COL.wall; g.lineWidth = 8; g.lineCap = 'butt';
    g.beginPath(); g.moveTo(f.X(0), f.Y(0)); g.lineTo(f.X(P.Wx), f.Y(0)); g.stroke();
    g.beginPath(); g.moveTo(f.X(0), f.Y(0)); g.lineTo(f.X(0), f.Y(P.Wy)); g.stroke();
    g.strokeStyle = '#c39a80'; g.lineWidth = 1.5; g.setLineDash([3, 3]);
    g.beginPath(); g.moveTo(f.X(0), f.Y(0)); g.lineTo(f.X(P.Wx), f.Y(0)); g.stroke();
    g.beginPath(); g.moveTo(f.X(0), f.Y(0)); g.lineTo(f.X(0), f.Y(P.Wy)); g.stroke();
    g.setLineDash([]);
    txt(g, `长边墙 ${P.Wx.toFixed(1)} m　墙高 ${P.Hw.toFixed(1)} m`, f.X(P.Wx / 2), f.Y(0) + 15, COL.wall, 10.5, 'center');
    vtxt(g, `短边墙 ${P.Wy.toFixed(1)} m`, f.X(0) - 15, f.Y(P.Wy / 2), COL.wall, 10.5);

    // 柱与挑梁
    geo.cols.forEach((c, ci) => {
      const bx = f.X(c.base.x), by = f.Y(c.base.y), tx = f.X(c.tip.x), ty = f.Y(c.tip.y);
      g.strokeStyle = COL.steel; g.lineWidth = 4; g.lineCap = 'round';
      g.beginPath(); g.moveTo(bx, by); g.lineTo(tx, ty); g.stroke();
      g.fillStyle = '#22303B'; g.strokeStyle = COL.steel; g.lineWidth = 1.6;
      const r = 7;
      g.beginPath(); g.rect(bx - r, by - r, r * 2, r * 2); g.fill(); g.stroke();
      g.beginPath(); g.arc(tx, ty, 4.5, 0, 6.3); g.fillStyle = COL.acc; g.fill();
      txt(g, c.id, bx + (c.base.y > geo.netW * 0.5 ? 14 : 0), by + (c.base.y > geo.netW * 0.5 ? -13 : 16),
          COL.text, 11, c.base.y > geo.netW * 0.5 ? 'left' : 'center', true);
      vtxt(g, `悬臂 ${c.L.toFixed(2)}m`, tx + 9, (by + ty) / 2, COL.dim, 9.5);
    });

    // 风箭头
    const cx = geo.netL / 2, cy = geo.netW + 0.72;
    for (let k = 0; k < 3; k++) {
      const ox = (k - 1) * geo.netL / 4.2;
      arrow(g, f.X(cx + ox), f.Y(cy + 0.36), f.X(cx + ox), f.Y(cy - 0.30), COL.blue, 2, 8);
    }
    txt(g, `${R.W.v.toFixed(0)} m/s · w=${R.W.wk.toFixed(2)} kN/m²`, f.X(cx), f.Y(cy + 0.62), COL.blue, 11, 'center', true);

    // 尺寸
    const d1 = dimLine(g, f, 0, geo.netW, geo.netL, geo.netW, -16, COL.dim2);
    txt(g, `${geo.netL.toFixed(1)} m`, d1.mx, d1.my - 8, COL.dim, 10.5, 'center');
    const d2 = dimLine(g, f, geo.netL, 0, geo.netL, geo.netW, 20, COL.dim2);
    vtxt(g, `挑出 ${geo.netW.toFixed(2)} m`, d2.mx + 12, d2.my, COL.dim, 10.5);

    txt(g, '平面示意（非施工图）', 8, h - 9, COL.dim2, 10);
    return f;
  }

  /* ==================== 立面 + 弯矩图 ==================== */
  function elev(cv, R, colIdx, caseKey, opt) {
    opt = opt || {};
    const { g, w, h } = prep(cv, opt.hpx || 262);
    const P = R.P, c = R.geo.cols[colIdx];
    const row = R.perCol[colIdx].cases[caseKey];
    const fr = row.frame, L = c.L, hh = P.h;
    const r = (P.diagType === 'none' ? 0 : P.r);
    const yA0 = P.diagType === 'below' ? hh - r : hh + r;
    const x0 = -1.95, x1 = L + 0.95, y0 = -1.05, y1 = Math.max(hh + r + 1.45, 4.1);
    const f = fit(w, h, x0, x1, y0, y1, 26);

    const mxM = Math.max(Math.abs(fr.beam.Mmax.M), Math.abs(fr.colM.M), 1);
    const kM = (opt.mScale || 1) * (0.52 / mxM);   // 最大弯矩画成 0.52m 的偏移

    // 地面
    g.fillStyle = '#101820'; g.fillRect(0, f.Y(0), w, h - f.Y(0));
    g.strokeStyle = COL.line; g.lineWidth = 1.4;
    g.beginPath(); g.moveTo(0, f.Y(0)); g.lineTo(w, f.Y(0)); g.stroke();
    // 斜影线
    g.strokeStyle = '#1B2731';
    for (let x = -10; x < w; x += 9) { g.beginPath(); g.moveTo(x, f.Y(0)); g.lineTo(x + 8, f.Y(0) + 8); g.stroke(); }

    // 砖墙
    if (P.Hw > 0) {
      g.fillStyle = 'rgba(139,106,88,.35)';
      g.fillRect(f.X(-1.72), f.Y(P.Hw), 0.46 * f.s, P.Hw * f.s);
      g.strokeStyle = 'rgba(139,106,88,.8)'; g.lineWidth = 1;
      g.strokeRect(f.X(-1.72), f.Y(P.Hw), 0.46 * f.s, P.Hw * f.s);
      vtxt(g, `砖墙 ${P.Hw.toFixed(1)}m`, f.X(-1.49), f.Y(P.Hw / 2), COL.wall, 10);
    }

    // 弯矩图
    const dirs = { col: [0, 1], beam: [1, 0], diag: null };
    fr.res.elems.forEach(e => {
      if (e.name.indexOf('立柱') !== 0 && e.name !== '挑梁') return;
      const a = fr.nodes[e.i], b = fr.nodes[e.j];
      const Lx = e._L, ux = (b.x - a.x) / Lx, uy = (b.y - a.y) / Lx;
      const nx = -uy, ny = ux;
      g.beginPath();
      g.moveTo(f.X(a.x), f.Y(a.y));
      let mx = 0, mxAt = null;
      for (const p of e.pts) {
        const px = a.x + ux * p.x, py = a.y + uy * p.x;
        const mm = -p.M * kM;                        // 下侧受拉画在构件下侧
        g.lineTo(f.X(px + nx * mm), f.Y(py + ny * mm));
        if (Math.abs(p.M) > Math.abs(mx)) { mx = p.M; mxAt = p; }
      }
      g.lineTo(f.X(b.x), f.Y(b.y));
      g.closePath();
      g.fillStyle = 'rgba(92,200,255,.16)';
      g.strokeStyle = 'rgba(92,200,255,.7)'; g.lineWidth = 1.2;
      g.fill(); g.stroke();
      if (mxAt && Math.abs(mx) > mxM * 0.25) {
        const px = a.x + ux * mxAt.x, py = a.y + uy * mxAt.x;
        const ox = f.X(px + nx * (-mx * kM)), oy = f.Y(py + ny * (-mx * kM));
        g.fillStyle = COL.mm;
        g.beginPath(); g.arc(ox, oy, 2.6, 0, 6.3); g.fill();
        txt(g, (mx / 1000).toFixed(2), ox + 5, oy - 7, COL.mm, 9.5, 'left');
      }
    });

    // 构件
    g.lineCap = 'round';
    const uc = u => u > 1 ? COL.bad : u > 0.85 ? COL.warn : COL.acc;
    const cc = uc(row.col.sigmaUtil), bc = uc(row.beam.sigmaUtil);
    fr.res.elems.filter(e => e.name.indexOf('立柱') === 0).forEach(e => {
      const a = fr.nodes[e.i], b = fr.nodes[e.j];
      g.strokeStyle = cc; g.lineWidth = 5;
      g.beginPath(); g.moveTo(f.X(a.x), f.Y(a.y)); g.lineTo(f.X(b.x), f.Y(b.y)); g.stroke();
    });
    g.strokeStyle = bc; g.lineWidth = 5;
    g.beginPath(); g.moveTo(f.X(0), f.Y(hh)); g.lineTo(f.X(L), f.Y(hh)); g.stroke();
    // 斜杆
    if (r > 0) {
      const live = fr.diag && !fr.diagDropped;
      g.strokeStyle = live ? COL.acc : '#46555f';
      g.lineWidth = live ? 3.2 : 2;
      g.setLineDash(live ? [] : [6, 5]);
      g.beginPath(); g.moveTo(f.X(0), f.Y(yA0)); g.lineTo(f.X(L), f.Y(hh)); g.stroke();
      g.setLineDash([]);
      if (live) {
        const N = -fr.diag._fl[0];
        txt(g, '斜杆 ' + (N > 0 ? '拉' : '压') + (Math.abs(N) / 1000).toFixed(1) + 'kN',
            f.X(L * 0.62) + 6, f.Y((yA0 + hh) / 2) + (P.diagType === 'below' ? 12 : -10), COL.acc, 10.2, 'left', true);
      }
    }
    // 节点
    g.fillStyle = '#0A0F13'; g.strokeStyle = COL.steel; g.lineWidth = 1.6;
    [[0, 0], [0, hh], [L, hh]].forEach(p => { g.beginPath(); g.arc(f.X(p[0]), f.Y(p[1]), 3.4, 0, 6.3); g.fill(); g.stroke(); });
    // 柱脚固定符号
    g.strokeStyle = COL.reac; g.lineWidth = 2;
    g.beginPath(); g.moveTo(f.X(0) - 12, f.Y(0) + 9); g.lineTo(f.X(0) + 12, f.Y(0) + 9); g.stroke();
    for (let i = -10; i <= 10; i += 6) { g.beginPath(); g.moveTo(f.X(0) + i, f.Y(0) + 9); g.lineTo(f.X(0) + i - 5, f.Y(0) + 17); g.stroke(); }

    // 网面（沿悬臂的网布线）
    g.strokeStyle = 'rgba(47,191,155,.85)'; g.lineWidth = 2.4;
    g.beginPath(); g.moveTo(f.X(0), f.Y(hh)); g.lineTo(f.X(L), f.Y(hh)); g.stroke();
    g.strokeStyle = 'rgba(47,191,155,.4)'; g.lineWidth = 1;
    for (let i = 0; i <= 14; i++) {
      const t = i / 14;
      g.beginPath(); g.moveTo(f.X(L * t), f.Y(hh)); g.lineTo(f.X(L * t), f.Y(hh + 0.14)); g.stroke();
    }

    // 荷载
    const Pv = -row.Pvert, Fx = row.Fx;
    if (Math.abs(Pv) > 1) {
      const up = Pv > 0;
      arrow(g, f.X(L), f.Y(hh + (up ? 0.92 : -1.15)), f.X(L), f.Y(hh + (up ? 0.16 : -0.16)), COL.load, 2.6, 9);
      txt(g, `${up ? '↑ 风吸' : '↓ 风压'} ${(Math.abs(Pv) / 1000).toFixed(2)} kN`, f.X(L) - 8, f.Y(hh + (up ? 1.10 : -1.02)), COL.load, 11, 'right', true);
    }
    if (Math.abs(Fx) > 1) {
      const right = Fx > 0;
      arrow(g, f.X(L + (right ? -0.85 : 0.85)), f.Y(hh + 0.34), f.X(L + (right ? -0.09 : 0.09)), f.Y(hh + 0.34), COL.blue, 2.2, 8);
      txt(g, `水平风 ${(Math.abs(Fx) / 1000).toFixed(2)} kN`, f.X(L), f.Y(hh - 0.48), COL.blue, 10.5, 'center');
    }
    // 支反力
    const b = row.base;
    if (b.N < 0) {
      arrow(g, f.X(0), f.Y(0.72), f.X(0), f.Y(0.10), COL.bad, 3, 9);
      txt(g, `↑ 上拔 ${(Math.abs(b.N) / 1000).toFixed(2)} kN`, f.X(0) + 10, f.Y(0.80), COL.bad, 11, 'left', true);
    } else {
      arrow(g, f.X(0), f.Y(-0.95), f.X(0), f.Y(-0.08), COL.reac, 3, 9);
      txt(g, `↓ 压力 ${(b.N / 1000).toFixed(2)} kN`, f.X(0) + 10, f.Y(-1.02), COL.reac, 11, 'left', true);
    }
    if (Math.abs(b.M) > 1) {
      g.strokeStyle = COL.blue; g.lineWidth = 1.6;
      g.beginPath(); g.arc(f.X(0), f.Y(0), 16, -Math.PI * .52, Math.PI * .06); g.stroke();
      txt(g, `柱底弯矩 ${(Math.abs(b.M) / 1000).toFixed(2)} kN·m`, f.X(0) + 22, f.Y(-0.10), COL.blue, 10.5, 'left', true);
    }

    // 尺寸
    const d1 = dimLine(g, f, 0, hh, L, hh, -15, COL.dim2);
    txt(g, `悬臂 ${L.toFixed(2)} m`, (d1.mx + f.X(L)) / 2, d1.my - 9, COL.dim, 10.5, 'center');
    const d2 = dimLine(g, f, 0, 0, 0, hh, -32, COL.dim2);
    vtxt(g, `柱高 ${hh.toFixed(2)} m`, d2.mx - 12, d2.my, COL.dim, 10.5);
    if (r > 0) {
      const yy = Math.min(hh, yA0);
      const d3 = dimLine(g, f, 0, yy, 0, Math.max(hh, yA0), 40, COL.acc);
      vtxt(g, `三角高 ${r.toFixed(2)} m`, d3.mx + 13, d3.my, COL.acc, 10.5);
    }

    // 顶部结论块
    const be = row.beam;
    const lines = [
      `挑梁 M=${(Math.abs(be.mom) / 1000).toFixed(2)} kN·m　N=${(be.axial / 1000).toFixed(2)} kN　应力比 ${be.sigmaUtil.toFixed(2)}`,
      `立柱 M=${(Math.abs(row.col.mom) / 1000).toFixed(2)} kN·m　N=${(row.col.axial / 1000).toFixed(2)} kN　λ=${row.col.lam.toFixed(0)} φ=${row.col.phi.toFixed(2)}　应力比 ${row.col.sigmaUtil.toFixed(2)}`,
      `端部挠度 ${(row.defl * 1000).toFixed(1)} mm（限 ${(row.deflLim * 1000).toFixed(0)}，比 ${row.deflUtil.toFixed(2)}）`,
    ];
    g.fillStyle = 'rgba(10,15,19,.86)';
    g.fillRect(0, 0, w, 50);
    g.strokeStyle = COL.line; g.beginPath(); g.moveTo(0, 50); g.lineTo(w, 50); g.stroke();
    lines.forEach((s, i) => txt(g, s, 8, 11 + i * 14, i === 0 ? bc : i === 1 ? cc : COL.dim, 10.2, 'left'));
    txt(g, '弯矩图（蓝）', w - 8, h - 9, COL.dim2, 10, 'right');
    return f;
  }

  /* ==================== 传力路径 ==================== */
  function path(cv, R, opt) {
    opt = opt || {};
    const { g, w, h } = prep(cv, opt.hpx || 330);
    const P = R.P, W = R.W;
    const c = R.geo.cols.reduce((a, b) => b.tw > a.tw ? b : a, R.geo.cols[0]);
    const ci = R.geo.cols.indexOf(c);
    const row = R.perCol[ci];
    const f0 = R.foot[ci];

    const bw = Math.min(150, w - 40), bh = 38;
    const cx = w / 2;
    const rows = [
      ['风', `${W.v.toFixed(0)} m/s　w=${W.wk.toFixed(2)} kN/m²`, COL.blue],
      ['太阳网', `吸 ${(W.qUp * R.geo.area).toFixed(1)} / 压 ${(W.qDown * R.geo.area).toFixed(1)} kN`, COL.net],
      ['张拉绳 · 边梁 · 挑梁', `最大柱分担 ${c.tw.toFixed(2)} m 宽 · 悬臂 ${c.L.toFixed(2)} m`, COL.steel],
      ['三角斜撑 + 立柱', `柱底弯矩 ${(Math.abs(row.cases.up.base.M) / 1000).toFixed(1)} kN·m`, COL.steel],
      ['柱脚底板 / 锚栓', `长 ${(f0.Tbolt / 1000).toFixed(1)} kN`, COL.warn],
      ['基础配重 / 土', `配重 ${(f0.ballast / 1000).toFixed(1)} kN　K拔 ${f0.kUp > 90 ? '—' : f0.kUp.toFixed(2)}　K倾 ${f0.kOver > 90 ? '—' : f0.kOver.toFixed(2)}`, COL.bad],
    ];
    const gap = Math.min(46, (h - 56) / rows.length);
    let y = 10;
    rows.forEach((rw, i) => {
      g.fillStyle = '#121A20'; g.strokeStyle = rw[2]; g.lineWidth = 1.4;
      const rr = 9, x = cx - bw / 2;
      g.beginPath();
      g.moveTo(x + rr, y);
      g.arcTo(x + bw, y, x + bw, y + bh, rr); g.arcTo(x + bw, y + bh, x, y + bh, rr);
      g.arcTo(x, y + bh, x, y, rr); g.arcTo(x, y, x + bw, y, rr);
      g.closePath(); g.fill(); g.stroke();
      txt(g, rw[0], cx, y + bh / 2 - 8, COL.text, 11.5, 'center', true);
      txt(g, rw[1], cx, y + bh / 2 + 9, COL.dim, 10, 'center');
      if (i < rows.length - 1) arrow(g, cx, y + bh + 2, cx, y + gap - 3, rw[2], 1.8, 6);
      y += gap;
    });
    g.strokeStyle = COL.line; g.lineWidth = 1;
    g.beginPath(); g.moveTo(6, h - 44); g.lineTo(w - 6, h - 44); g.stroke();
    const notes = [
      '砖墙只帮“往下压”的忙，帮不了“往上拔”',
      '沿墙方向的风靠纵梁 + 平面斜撑（最大柱距 ' + R.spanMax.toFixed(2) + ' m）',
      '柱子贴墙 → 抗倾覆力臂只有基础半个边长',
    ];
    notes.forEach((n, i) => txt(g, '· ' + n, 8, h - 32 + i * 14, COL.dim, 10.2, 'left'));
    return null;
  }

  return { plan, elev, path, prep, fit, arrow, txt, COL };
})();
