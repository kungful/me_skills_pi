/* =====================================================================
   solver.js —— 平面杆系直接刚度法（矩阵位移法）+ 截面库 + 稳定系数
   单位统一：力 N，长度 m，应力 Pa
   节点 3 个自由度：u(全局 x)、v(全局 y)、θ(逆时针正)
   杆端力 p = k·u + f固端  （p = 节点作用在单元上的力）
   内力符号：弯矩下侧受拉为正（sagging+），轴力拉为正
   ===================================================================== */
const SOLVER = (function () {

  /* ---------------- 线性方程组：高斯消元（列主元） ---------------- */
  function solveLin(A, b) {
    const n = b.length;
    const M = [];
    for (let i = 0; i < n; i++) M.push(A[i].slice(0, n).concat([b[i]]));
    for (let c = 0; c < n; c++) {
      let piv = c;
      for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[piv][c])) piv = r;
      if (Math.abs(M[piv][c]) < 1e-13) continue;      // 奇异（机构）→ 该自由度置 0
      if (piv !== c) { const t = M[piv]; M[piv] = M[c]; M[c] = t; }
      const d = M[c][c];
      for (let r = c + 1; r < n; r++) {
        const f = M[r][c] / d;
        if (f === 0) continue;
        for (let k = c; k <= n; k++) M[r][k] -= f * M[c][k];
      }
    }
    const x = new Array(n).fill(0);
    for (let r = n - 1; r >= 0; r--) {
      let s = M[r][n];
      for (let c = r + 1; c < n; c++) s -= M[r][c] * x[c];
      x[r] = Math.abs(M[r][r]) < 1e-13 ? 0 : s / M[r][r];
    }
    return x;
  }

  /* ---------------- 单元局部刚度 6×6 ---------------- */
  function kLocal(E, A, I, L) {
    const ea = E * A / L, e1 = 12 * E * I / (L ** 3),
          e2 = 6 * E * I / (L * L), e3 = 4 * E * I / L, e4 = 2 * E * I / L;
    return [
      [ ea,   0,   0, -ea,   0,   0],
      [  0,  e1,  e2,   0, -e1,  e2],
      [  0,  e2,  e3,   0, -e2,  e4],
      [-ea,   0,   0,  ea,   0,   0],
      [  0, -e1, -e2,   0,  e1, -e2],
      [  0,  e2,  e4,   0, -e2,  e3],
    ];
  }
  /* 固端力：局部 +y 方向均布 w（N/m，向上为正） */
  function fFixed(w, L) {
    return [0, -w * L / 2, -w * L * L / 12, 0, -w * L / 2, w * L * L / 12];
  }
  function Tmat(c, s) {
    return [
      [ c,  s, 0, 0, 0, 0],
      [-s,  c, 0, 0, 0, 0],
      [ 0,  0, 1, 0, 0, 0],
      [ 0,  0, 0, c,  s, 0],
      [ 0,  0, 0,-s,  c, 0],
      [ 0,  0, 0, 0, 0, 1],
    ];
  }
  function mmul(A, B) {
    const C = [];
    for (let i = 0; i < A.length; i++) {
      C.push(new Array(B[0].length).fill(0));
      for (let j = 0; j < B[0].length; j++) {
        let s = 0; for (let t = 0; t < B.length; t++) s += A[i][t] * B[t][j];
        C[i][j] = s;
      }
    }
    return C;
  }
  const mvec = (A, v) => A.map(r => r.reduce((s, a, j) => s + a * v[j], 0));
  function mpT(A) {
    const C = [];
    for (let j = 0; j < A[0].length; j++) { C.push(new Array(A.length)); for (let i = 0; i < A.length; i++) C[j][i] = A[i][j]; }
    return C;
  }
  /* 端部释放（铰）静力凝聚 */
  function release(k, f, r) {
    const krr = k[r][r];
    if (Math.abs(krr) < 1e-18) return;
    const col = k.map(row => row[r]), row = k[r].slice();
    for (let i = 0; i < 6; i++) for (let j = 0; j < 6; j++) k[i][j] -= col[i] * row[j] / krr;
    for (let i = 0; i < 6; i++) f[i] -= col[i] * f[r] / krr;
    for (let i = 0; i < 6; i++) { k[r][i] = 0; k[i][r] = 0; }
    k[r][r] = 1; f[r] = 0;
  }

  /* ---------------- 主分析 ---------------- */
  function analyze(model) {
    const nodes = model.nodes, nd = nodes.length * 3;
    const elems = model.elems.filter(e => !e.dead);
    elems.forEach((e, i) => { if (e.idx === undefined) e.idx = i; });
    const udlOf = e => (model.udl || []).filter(u => u.elem === e.idx || u.elem === e.name)
                                      .reduce((a, u) => a + u.w, 0);

    for (let iter = 0; iter < 10; iter++) {
      const K = []; for (let i = 0; i < nd; i++) K.push(new Array(nd).fill(0));
      const F = new Array(nd).fill(0);
      for (const L of (model.loads || [])) {
        F[L.node * 3] += L.fx || 0; F[L.node * 3 + 1] += L.fy || 0; F[L.node * 3 + 2] += L.mz || 0;
      }
      const live = elems.filter(e => !e.off);
      for (const e of live) {
        const ni = nodes[e.i], nj = nodes[e.j];
        const dx = nj.x - ni.x, dy = nj.y - ni.y;
        const L = Math.hypot(dx, dy);
        if (L < 1e-9) continue;
        const c = dx / L, s = dy / L, T = Tmat(c, s);
        let k = kLocal(e.E, e.A, e.I, L);
        const w = udlOf(e);
        let ffe = fFixed(w, L);
        const k0 = k.map(r => r.slice()), f0 = ffe.slice();
        const pins = [];
        if (e.truss || e.pinI) pins.push(2);
        if (e.truss || e.pinJ) pins.push(5);
        for (const p of pins) release(k, ffe, p);
        const kG = mmul(mmul(mpT(T), k), T);
        const fG = mvec(mpT(T), ffe);              // 等效节点荷载 = -fG
        const ids = [e.i * 3, e.i * 3 + 1, e.i * 3 + 2, e.j * 3, e.j * 3 + 1, e.j * 3 + 2];
        for (let a = 0; a < 6; a++) {
          F[ids[a]] -= fG[a];
          for (let b = 0; b < 6; b++) K[ids[a]][ids[b]] += kG[a][b];
        }
        Object.assign(e, { _L: L, _c: c, _s: s, _T: T, _k0: k0, _ffe0: f0, _w: w, _pins: pins });
      }

      // 边界：大数法
      const BIG = 1e13;
      for (let i = 0; i < nodes.length; i++) {
        const fx = nodes[i].fix || [false, false, false];
        for (let d = 0; d < 3; d++) if (fx[d]) K[i * 3 + d][i * 3 + d] += BIG;
      }
      const U = solveLin(K, F);

      // 杆端力
      for (const e of live) {
        const ids = [e.i * 3, e.i * 3 + 1, e.i * 3 + 2, e.j * 3, e.j * 3 + 1, e.j * 3 + 2];
        const ug = ids.map(id => U[id]);
        const ul = mvec(e._T, ug);
        for (const p of e._pins) {
          const row = e._k0[p];
          let s = e._ffe0[p];
          for (let j = 0; j < 6; j++) if (j !== p) s += row[j] * ul[j];
          ul[p] = -s / row[p];
        }
        const fl = mvec(e._k0, ul);
        for (let i = 0; i < 6; i++) fl[i] += e._ffe0[i];
        for (const p of e._pins) fl[p] = 0;
        e._fl = fl; e._ul = ul; e._ug = ug;
      }

      // 仅受拉构件：受压则失效，去掉重算
      let dropped = false;
      for (const e of live) {
        if (!e.tensionOnly) continue;
        const N = -e._fl[0];
        if (N < -1e-3) { e.off = true; e.force = 0; e.dropped = true; dropped = true; }
        else { e.dropped = false; e.force = N; }
      }
      if (dropped) continue;

      // 内力取样
      const SEG = 24;
      for (const e of live) {
        const fl = e._fl;
        const pts = [];
        for (let k2 = 0; k2 <= SEG; k2++) {
          const x = e._L * k2 / SEG;
          pts.push({ x, N: -fl[0], V: fl[1] + e._w * x, M: -fl[2] + fl[1] * x + e._w * x * x / 2 });
        }
        let mx = pts[0], mv = pts[0], mn = pts[0];
        for (const p of pts) {
          if (Math.abs(p.M) > Math.abs(mx.M)) mx = p;
          if (Math.abs(p.V) > Math.abs(mv.V)) mv = p;
          if (Math.abs(p.N) > Math.abs(mn.N)) mn = p;
        }
        e.pts = pts; e.Mmax = mx; e.Vmax = mv; e.Nmax = mn;
        e.Mend = [-fl[2], -fl[5]];
      }

      // 支座反力： R = Σ(Tᵀp) - P_实荷载
      const R = [];
      for (let i = 0; i < nodes.length; i++) {
        const fx = nodes[i].fix || [false, false, false];
        if (!fx[0] && !fx[1] && !fx[2]) continue;
        let rx = 0, ry = 0, rz = 0;
        for (const e of live) {
          const pG = mvec(mpT(e._T), e._fl);
          if (e.i === i) { rx += pG[0]; ry += pG[1]; rz += pG[2]; }
          if (e.j === i) { rx += pG[3]; ry += pG[4]; rz += pG[5]; }
        }
        for (const L of (model.loads || [])) {
          if (L.node === i) { rx -= L.fx || 0; ry -= L.fy || 0; rz -= L.mz || 0; }
        }
        R.push({ node: i, fx: rx, fy: ry, mz: rz });
      }
      return { U, R, elems: live, dropped: elems.filter(e => e.off) };
    }
    return { U: [], R: [], elems: elems.filter(e => !e.off), dropped: elems.filter(e => e.off) };
  }

  /* ---------------- 截面库 ---------------- */
  const SEC = {
    round(D, t) {
      D /= 1000; t /= 1000;
      const d = D - 2 * t;
      const A = Math.PI * (D * D - d * d) / 4;
      const I = Math.PI * (D ** 4 - d ** 4) / 64;
      return { name: `圆管 Φ${(D * 1000).toFixed(0)}×${(t * 1000).toFixed(1)}`,
               A, I, W: I / (D / 2), i: Math.sqrt(I / A), D, d, t, kind: 'round', mass: A * 7850 };
    },
    square(a, t) {
      a /= 1000; t /= 1000;
      const b = a - 2 * t;
      const A = a * a - b * b;
      const I = (a ** 4 - b ** 4) / 12;
      return { name: `方管 □${(a * 1000).toFixed(0)}×${(t * 1000).toFixed(1)}`,
               A, I, W: I / (a / 2), i: Math.sqrt(I / A), D: a, d: b, t, kind: 'square', mass: A * 7850 };
    },
    bar(dmm) {
      const D = dmm / 1000;
      const A = Math.PI * D * D / 4;
      const I = Math.PI * D ** 4 / 64;
      return { name: `圆钢 ⌀${dmm}`, A, I, W: I / (D / 2), i: Math.sqrt(I / A), D, d: 0, t: D / 2, kind: 'bar', mass: A * 7850 };
    },
  };
  /* 常用规格下拉 */
  const PIPE_LIST = [
    ['Φ48x2.5', SEC.round(48, 2.5)], ['Φ60x2.5', SEC.round(60, 2.5)],
    ['Φ76x3.0', SEC.round(76, 3)], ['Φ89x3.0', SEC.round(89, 3)],
    ['Φ89x4.0', SEC.round(89, 4)], ['Φ114x4.0', SEC.round(114, 4)],
    ['Φ140x4.0', SEC.round(140, 4)], ['Φ140x5.0', SEC.round(140, 5)],
    ['Φ165x5.0', SEC.round(165, 5)], ['Φ219x6.0', SEC.round(219, 6)],
    ['□60x60x3', SEC.square(60, 3)], ['□80x80x3', SEC.square(80, 3)],
    ['□80x80x4', SEC.square(80, 4)], ['□100x100x4', SEC.square(100, 4)],
    ['□120x120x4', SEC.square(120, 4)], ['□120x120x6', SEC.square(120, 6)],
    ['□150x150x5', SEC.square(150, 5)], ['□150x150x8', SEC.square(150, 8)],
    ['□200x200x6', SEC.square(200, 6)], ['□200x200x8', SEC.square(200, 8)],
    ['⌀12', SEC.bar(12)], ['⌀14', SEC.bar(14)], ['⌀16', SEC.bar(16)],
    ['⌀20', SEC.bar(20)], ['⌀24', SEC.bar(24)], ['⌀30', SEC.bar(30)],
  ];
  const PIPE_MAP = {}; PIPE_LIST.forEach(p => PIPE_MAP[p[0]] = p[1]);

  /* 稳定系数 φ（欧规 b 类曲线，与 GB50017 b 类接近） */
  function phiBuckling(lam, fy) {
    if (!(lam > 0)) return 1;
    const lb = (lam / Math.PI) * Math.sqrt(fy / 2.06e11);
    if (lb <= 0.2) return 1;
    const phi0 = 0.5 * (1 + 0.34 * (lb - 0.2) + lb * lb);
    const v = phi0 * phi0 - lb * lb;
    return Math.min(1, 1 / (phi0 + Math.sqrt(Math.max(v, 0))));
  }

  return { analyze, solveLin, SEC, PIPE_LIST, PIPE_MAP, phiBuckling, mmul, mvec, mpT };
})();
if (typeof module !== 'undefined') module.exports = SOLVER;
