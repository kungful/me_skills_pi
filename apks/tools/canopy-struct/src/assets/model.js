/* =====================================================================
   model.js —— 把「L 形墙内角 + 三柱 + 镀锌管三角挑梁 + 太阳网」
   变成一个可算的力学模型：几何 → 荷载 → 杆系有限元 → 校核 → 反算
   ===================================================================== */
const MODEL = (function () {

  const G = 9.81, RHO_STEEL = 7850;

  /* ------------------------------------------------------------------
     默认参数：按用户说的条件——L 形墙 8m + 5m，墙高 2m，网 8×4=32m²，
     三根柱子贴墙，镀锌管焊三角挑梁，上斜拉，太阳网可收
     ------------------------------------------------------------------ */
  function defaults() {
    return {
      /* 场地 */
      region: '广州', w0: 0.60, w0Factor: 1.0, rough: 'C', z: 3.0,
      /* 几何 */
      Wx: 8.0, Wy: 5.0, Hw: 2.0,
      netL: 8.0, netW: 4.0, slopeDeg: 4,
      h: 2.6,                       // 挑梁标高（柱顶）
      wallGap: 0.4,                 // 柱脚离墙面
      nCol: 3,
      tipX: [0.4, 2.2, 6.2],        // 各柱挑梁端部 x
      baseY: [2.4, 0.4, 0.4],       // 各柱柱脚 y
      r: 0.8,                       // 三角高（斜拉杆锚点在挑梁上方 r）
      diagType: 'above',            // above | below | none
      diagCable: true,              // true=拉索/圆钢（仅受拉），false=刚性管
      /* 构件 */
      secCol: 'Φ89x3.0', secBeam: 'Φ89x3.0', secDiag: '⌀12',
      secLong: 'Φ60x2.5',
      kCol: 2.0, kBeam: 2.0,        // 计算长度系数
      /* 材料 */
      fy: 235, fd: 215, fv: 125,
      /* 网 */
      netMass: 0.06,                // kg/m²
      porosity: 0.50,               // 透风率
      cManual: false, Cup: 1.1, Cdown: 0.5, Cdrag: 1.3,
      /* 墙 */
      wallAnchored: true, wallShare: 0.35,
      /* 基础 */
      footB: 0.8, footH: 0.6, footN: 1, soilFa: 100,
      anchorCap: 35,                // 单锚栓抗拔设计值 kN（M16 化学锚栓 C30 ≈ 30~40kN）
      anchorN: 2,                   // 柱脚受拉侧锚栓数
      basePlateLever: 0.40,         // 受拉锚栓到压区合力的距离 m（底板越大越好）
      /* 规范 */
      gammaG: 1.3, gammaW: 1.5,
      windDirDeg: 90,               // 90 = 垂直长边墙（沿挑梁方向）
      netDeployed: true,            // 网是否张开（收起时受风面积折减）
      stowFactor: 0.15,
    };
  }

  /* ---------------- 几何 ---------------- */
  function build(P) {
    const netW = P.netW, slope = P.slopeDeg * Math.PI / 180;
    const rise = netW * Math.sin(slope);                 // 网外侧比墙侧低/高
    // 网面：y=0（墙侧）z=P.h，y=netW（外侧）z=P.h - rise（向外排水，外侧低）
    const cols = [];
    const n = Math.max(2, Math.min(6, P.nCol | 0));
    for (let i = 0; i < n; i++) {
      let tx = P.tipX[i] !== undefined ? P.tipX[i] : (P.netL * (i + 0.5) / n);
      let by = P.baseY[i] !== undefined ? P.baseY[i] : P.wallGap;
      // 柱脚 x：默认与挑梁端部同 x（正挑），第三根（靠短墙）也照此
      let bx = tx;
      if (by > P.netW - 0.05) by = P.netW - 0.05;
      const L = Math.hypot(tx - bx, by * 0 + (netW - by));      // 悬臂水平长度
      cols.push({
        i, id: 'C' + (i + 1),
        base: { x: bx, y: by }, tip: { x: tx, y: netW },
        L: Math.max(0.05, netW - by),
        h: P.h, r: P.r,
        zTip: P.h - (netW - by) / netW * rise,
      });
    }
    // 分担宽度（外边缘 0..netL 上的 Voronoi）
    const xs = cols.map(c => c.tip.x).slice().sort((a, b) => a - b);
    const bounds = [0];
    for (let i = 0; i < xs.length - 1; i++) bounds.push((xs[i] + xs[i + 1]) / 2);
    bounds.push(P.netL);
    cols.forEach(c => {
      let k = xs.indexOf(c.tip.x);
      c.tw = Math.max(0.05, bounds[k + 1] - bounds[k]);
    });
    const sumTw = cols.reduce((a, c) => a + c.tw, 0);
    cols.forEach(c => c.share = c.tw / sumTw);
    return {
      cols, netL: P.netL, netW, rise, slope,
      area: P.netL * netW,
      walls: [
        { x1: 0, y1: 0, x2: P.Wx, y2: 0, len: P.Wx, id: '长边墙' },
        { x1: 0, y1: 0, x2: 0, y2: P.Wy, len: P.Wy, id: '短边墙' },
      ],
      Hw: P.Hw,
    };
  }

  /* ---------------- 单榀（柱 + 挑梁 + 斜杆）平面刚架 ---------------- */
  function bracketFrame(P, geo, c, tipP, tipFx, cableActive) {
    const S = SOLVER;
    const secCol = S.PIPE_MAP[P.secCol] || S.SEC.round(89, 3);
    const secBeam = S.PIPE_MAP[P.secBeam] || S.SEC.round(89, 3);
    const secDiag = S.PIPE_MAP[P.secDiag] || S.SEC.bar(12);
    const E = 2.06e11;
    const L = c.L, h = P.h, r = (P.diagType === 'none' ? 0 : P.r);

    const nodes = [
      { x: 0, y: 0, fix: [true, true, true] },   // 0 柱脚
      { x: 0, y: h },                            // 1 柱顶/挑梁根
      { x: L, y: h },                            // 2 挑梁端
    ];
    const elems = [
      { i: 0, j: 1, E, A: secCol.A, I: secCol.I, name: '立柱', sec: secCol, idx: 0 },
      { i: 1, j: 2, E, A: secBeam.A, I: secBeam.I, name: '挑梁', sec: secBeam, idx: 1 },
    ];
    let nDiag = -1;
    if (r > 0.01) {
      const yA = (P.diagType === 'below') ? h - r : h + r;
      nodes.push({ x: 0, y: yA });               // 3 斜杆锚点
      const kA = nodes.length - 1;
      const kMidLow = (P.diagType === 'below') ? 1 : 0;
      // 柱分成两段：柱脚 ↔ 锚点 ↔ 柱顶
      if (P.diagType === 'below') {
        elems[0] = { i: 0, j: kA, E, A: secCol.A, I: secCol.I, name: '立柱(下段)', sec: secCol, idx: 0 };
        elems.push({ i: kA, j: 1, E, A: secCol.A, I: secCol.I, name: '立柱(上段)', sec: secCol, idx: 3 });
      } else {
        elems.push({ i: 1, j: kA, E, A: secCol.A, I: secCol.I, name: '立柱(上段)', sec: secCol, idx: 3 });
      }
      elems.push({ i: kA, j: 2, E, A: secDiag.A, I: secDiag.I, name: '斜杆', sec: secDiag,
                   truss: true, tensionOnly: P.diagCable && cableActive !== false, idx: 4 });
      nDiag = elems.length - 1;
    }
    // 自重
    const colMass = secCol.A * RHO_STEEL * h * G;          // N
    const udlBeam = -secBeam.A * RHO_STEEL * G;            // N/m（局部 +y 向上）
    const loads = [{ node: 2, fx: tipFx, fy: tipP }];
    for (const e of elems) {
      if (e.i === 0 || (e.j !== 2 && e.i !== 2)) { /* 柱段自重挂给节点1 */ }
    }
    loads.push({ node: 1, fy: -colMass });
    const udl = elems.filter(e => e.idx === 1).map(e => ({ elem: e.idx, w: udlBeam }));

    const res = S.analyze({ nodes, elems, loads, udl });
    const get = nm => res.elems.find(e => e.name === nm);
    const colSegs = res.elems.filter(e => e.name.indexOf('立柱') === 0);
    const beam = get('挑梁');
    const diag = get('斜杆');
    const maxOf = (arr, key) => arr.reduce((m, e) => Math.abs(e[key].M) > Math.abs(m.M) ? e[key] : m, arr[0][key]);

    // 柱脚反力
    const R = res.R[0] || { fx: 0, fy: 0, mz: 0 };
    // 柱身最大弯矩/轴力
    let colM = { M: 0, x: 0 }, colN = { N: 0 }, colV = { V: 0 };
    for (const s of colSegs) {
      if (Math.abs(s.Mmax.M) > Math.abs(colM.M)) colM = s.Mmax;
      if (Math.abs(s.Nmax.N) > Math.abs(colN.N)) colN = s.Nmax;
      if (Math.abs(s.Vmax.V) > Math.abs(colV.V)) colV = s.Vmax;
    }
    const tip = res.U;
    const tipDefl = tip[2 * 3 + 1] || 0, tipDeflX = tip[2 * 3] || 0;

    return {
      res, nodes, elems, secCol, secBeam, secDiag,
      beam, diag, colSegs,
      colM, colN, colV,
      base: { N: R.fy, V: R.fx, M: -R.mz },      // N 压为正（R.fy 是支座的向上的反力）
      tipDefl, tipDeflX,
      udlBeam, diagForce: diag ? (diag.dropped ? 0 : -diag._fl[0]) : 0,
      diagDropped: diag ? !!diag.dropped : false,
      diagTension: diag ? (-diag._fl[0] > 0) : false,
    };
  }

  /* ---------------- 工况求解 ---------------- */
  function solveCase(P, geo, W, kind, opts) {
    opts = opts || {};
    const cols = geo.cols;
    const out = [];
    const stow = P.netDeployed ? 1 : P.stowFactor;
    let wallShare = P.wallAnchored ? P.wallShare : 0;
    if (kind === 'up') wallShare = 0;              // 风吸：砖墙拉不住，不能帮忙
    if (!P.wallAnchored) wallShare = 0;

    for (const c of cols) {
      const A = c.tw * geo.netW;                                  // 该柱分担网面积 m²
      const gNet = P.netMass * G / 1000;                          // kN/m²
      let qv = 0;                                                 // 竖向（kN/m²，向上为负）
      if (kind === 'up') qv = -W.qUp * stow * Math.cos(geo.slope);
      else if (kind === 'down') qv = W.qDown * stow * Math.cos(geo.slope);
      const qNet = P.gammaG * gNet;
      // 竖向合力（N），向下为正
      let Pvert = (P.gammaG * gNet + P.gammaW * qv) * A * 1000 * (1 - wallShare);
      if (kind === 'wind') Pvert = P.gammaG * gNet * A * 1000 * (1 - wallShare);
      // 水平力（沿挑梁方向，指向院内为 +），N
      let Fx = 0;
      if (kind === 'up' || kind === 'down') {
        const sgn = (kind === 'up') ? -1 : 1;
        Fx = P.gammaW * (W.qUp * stow) * Math.sin(geo.slope) * A * 1000 * (sgn);
      } else if (kind === 'wind') {
        const hFront = geo.netW * Math.sin(geo.slope) + 0.30;
        Fx = P.gammaW * W.qDrag * stow * c.tw * hFront * 1000;
      }
      // bracketFrame 的竖向荷载用「向上为正」，而 Pvert 是「向下为正」→ 取负
      const fr = bracketFrame(P, geo, c, -Pvert, Fx, opts.cable !== false);
      out.push({ col: c, A, Pvert, Fx, frame: fr, kind });
    }
    return out;
  }

  /* ---------------- 构件校核 ---------------- */
  function checkMember(sec, M, N, V, L, opts) {
    const S = SOLVER;
    const f = opts.fd * 1e6, fv = opts.fv * 1e6;      // MPa → Pa
    const lam = (opts.k || 1) * L / sec.i;
    const phi = S.phiBuckling(lam, opts.fy * 1e6);
    const Nabs = Math.abs(N);
    const sig = Nabs / (phi * sec.A) + Math.abs(M) / sec.W;
    const sigAx = Nabs / (phi * sec.A);
    const tau = 2 * Math.abs(V) / sec.A;
    return {
      sigma: sig, sigmaAx: sigAx, sigmaUtil: sig / f, tau, tauUtil: tau / fv, phi, lam,
      axial: N, mom: M, shear: V, sec,
    };
  }

  /* ---------------- 主入口 ---------------- */
  function run(P0, opts) {
    opts = opts || {};
    const P = Object.assign(defaults(), P0 || {});
    const geo = build(P);
    const W = WIND.calc(P);
    const S = SOLVER;
    const checks = [];
    const warn = [];

    const secCol = S.PIPE_MAP[P.secCol] || S.SEC.round(89, 3);
    const secBeam = S.PIPE_MAP[P.secBeam] || S.SEC.round(89, 3);
    const secDiag = S.PIPE_MAP[P.secDiag] || S.SEC.bar(12);
    const secLong = S.PIPE_MAP[P.secLong] || S.SEC.round(60, 2.5);

    const cases = {
      up:   { key: 'up',   name: '工况① 风吸上抬（网被掀起）', color: '#ff6b6b',
              desc: '风垂直网面向上的吸力。砖墙拉不住，全部上抬力只能由柱脚基础/配重扛——这是最容易被忽略、也最容易出事的工况。' },
      down: { key: 'down', name: '工况② 风压向下（网被压下）', color: '#ffb84d',
              desc: '风垂直网面向下压。挑梁受弯最大，与自重同向叠加。' },
      wind: { key: 'wind', name: '工况③ 水平风（整体倾覆）', color: '#5cc8ff',
              desc: '水平风对网面和框架的水平推力。控制柱底弯矩、整体抗倾覆和锚栓。' },
    };

    const results = {};
    for (const k of ['up', 'down', 'wind']) {
      results[k] = solveCase(P, geo, W, k);
    }

    /* ---- 每根柱：挑梁 / 立柱 / 斜杆 ---- */
    const perCol = [];
    for (let ci = 0; ci < geo.cols.length; ci++) {
      const c = geo.cols[ci];
      const row = { col: c, cases: {} };
      for (const k of ['up', 'down', 'wind']) {
        const fr = results[k][ci].frame;
        const beam = checkMember(secBeam, fr.beam.Mmax.M, fr.beam.Nmax.N, fr.beam.Vmax.V, c.L, { fd: P.fd, fv: P.fv, fy: P.fy, k: P.kBeam });
        const col = checkMember(secCol, fr.colM.M, fr.colN.N, fr.colV.V, P.h, { fd: P.fd, fv: P.fv, fy: P.fy, k: P.kCol });
        let diag = null;
        if (fr.diag && !fr.diagDropped) {
          const N = -fr.diag._fl[0];
          diag = { N, sec: secDiag, L: fr.diag._L,
                   util: N > 0 ? N / (secDiag.A * P.fd * 1e6)
                               : (() => { const lam = P.kBeam * fr.diag._L / secDiag.i;
                                          const phi = S.phiBuckling(lam, P.fy * 1e6);
                                          return Math.abs(N) / (phi * secDiag.A * P.fd * 1e6); })(),
                   tension: N > 0 };
        }
        const deflLim = c.L / 150;
        row.cases[k] = {
          beam, col, diag, frame: fr,
          defl: Math.abs(fr.tipDefl), deflLim, deflUtil: Math.abs(fr.tipDefl) / deflLim,
          Pvert: results[k][ci].Pvert, Fx: results[k][ci].Fx, A: results[k][ci].A,
          base: fr.base,
        };
      }
      perCol.push(row);
    }

    /* ---- 汇总最不利 ---- */
    const util = (r) => Math.max(r.beam.sigmaUtil, r.col.sigmaUtil, r.deflUtil,
                                 r.diag ? Math.max(r.diag.util, 0) : 0);
    let worst = { u: -1 };
    for (const row of perCol) for (const k of ['up', 'down', 'wind']) {
      const u = util(row.cases[k]);
      if (u > worst.u) worst = { u, col: row.col.id, caseKey: k, name: cases[k].name, r: row.cases[k] };
    }

    /* ---- 基础 / 抗拔 / 抗倾覆（逐柱） ---- */
    const foot = [];
    for (const row of perCol) {
      const c = row.col;
      const Wf = P.footB * P.footB * P.footH * 25 * 1000 * P.footN;   // N（混凝土 25kN/m³）
      const Wcol = secCol.A * RHO_STEEL * P.h * G;
      const r = row.cases.up;
      const Nup = -r.base.N;                                  // 上拔力（N，正=拔）
      const upliftCol = Nup > 0 ? Nup : 0;
      const ballast = Wf + Wcol;
      // 绕“靠挑梁那一侧的基础边”倾覆：力臂 = L - B/2
      const leverUp = Math.max(c.L - P.footB / 2, 0.01);
      const Mup = upliftCol * leverUp;
      const Mres = ballast * (P.footB / 2);
      const kOver = Mup > 0 ? Mres / Mup : 99;
      const kUp = upliftCol > 0 ? ballast / upliftCol : 99;
      // 风压/水平风下的地基压力
      const rd = row.cases.wind;
      const Nd = Math.max(0, rd.base.N) + Wf;
      const Md = Math.abs(rd.base.M) + Math.abs(rd.base.V) * P.footH;
      const e = Nd > 0 ? Md / Nd : 99;
      const B = P.footB;
      let pMax;
      if (e <= B / 6) pMax = Nd / (B * B) * (1 + 6 * e / B);
      else if (e < B / 2) pMax = 2 * Nd / (3 * B * (B / 2 - e));
      else pMax = 999e3;
      const pLim = P.soilFa * 1000;
      // 锚栓拉力（柱脚底板）：T = M/a − N/2
      const lever = P.basePlateLever;
      let Tbolt = 0;
      for (const k of ['up', 'down', 'wind']) {
        const b = row.cases[k].base;
        const t = Math.abs(b.M) / lever - b.N / 2;
        if (t > Tbolt) Tbolt = t;
      }
      const TboltEach = Tbolt / Math.max(1, P.anchorN);
      foot.push({
        col: c, Wf, Wcol, ballast, uplift: upliftCol, kUp, Mup, Mres, kOver, leverUp,
        pMax, pLim, e, B, Tbolt: TboltEach, TanchorLim: P.anchorCap * 1000,
        Tutil: TboltEach / (P.anchorCap * 1000),
        pUtil: pMax / pLim, overUtil: 1.5 / Math.max(kOver, 1e-6),
        upUtil: upliftCol > 0 ? 1.5 / Math.max(kUp, 1e-6) : 0,
      });
    }

    /* ---- 整体抗倾覆（绕墙线） ---- */
    const totalUplift = results.up.reduce((a, r) => a + Math.max(0, -r.frame.base.N), 0);
    const totalBallast = foot.reduce((a, f) => a + f.ballast, 0);
    const kWall = totalUplift > 0 ? totalBallast / totalUplift : 99;
    // 绕 y=0（墙线）的水平风力倾覆
    const Mot = results.wind.reduce((a, r) => a + Math.abs(r.Fx) * P.h, 0);
    const MresG = totalBallast * P.wallGap + (P.wallAnchored ? 0 : 0);
    const kGlobal = Mot > 0 ? MresG / Mot : 99;

    /* ---- 纵梁（柱间沿墙方向） ---- */
    const xs = geo.cols.map(c => c.tip.x).sort((a, b) => a - b);
    let spanMax = 0;
    for (let i = 0; i < xs.length - 1; i++) spanMax = Math.max(spanMax, xs[i + 1] - xs[i]);
    // 纵向风：把网面迎风投影的水平力，按柱距当简支梁估（N/m）
    const hFrontT = geo.netW * Math.sin(geo.slope) + 0.30;
    const Flong = P.gammaW * W.qDrag * 1000 * geo.netL * hFrontT;   // N（整体）
    const qLong = Flong / Math.max(1, geo.netL);                    // N/m
    const Mlong = qLong * spanMax * spanMax / 8;
    const longChk = checkMember(secLong, Mlong, 0, qLong * spanMax / 2, spanMax, { fd: P.fd, fv: P.fv, fy: P.fy, k: 1 });

    /* ---- 校核清单 ---- */
    const add = (group, name, value, unit, limit, ratio, note, formula, uls) =>
      checks.push({ group, name, value, unit, limit, ratio, note, formula, uls: uls !== false,
                    verdict: ratio <= 0.85 ? 'ok' : ratio <= 1.0 ? 'warn' : 'bad' });

    for (const row of perCol) for (const k of ['up', 'down', 'wind']) {
      const r = row.cases[k], tag = `${row.col.id} · ${cases[k].name.split(' ')[0]}`;
      add('挑梁', `${tag} 抗弯+压弯应力比`, r.beam.sigma / 1e6, 'MPa', P.fd, r.beam.sigmaUtil,
          `N=${(r.beam.axial/1000).toFixed(2)}kN, M=${(r.beam.mom/1000).toFixed(2)}kN·m, W=${(secBeam.W*1e9).toFixed(0)}cm³`,
          'σ = N/(φA) + M/W ≤ f');
      add('挑梁', `${tag} 抗剪应力比`, r.beam.tau / 1e6, 'MPa', P.fv, r.beam.tauUtil,
          `V=${(r.beam.shear/1000).toFixed(2)}kN`, 'τ ≈ 2V/A ≤ fv');
      add('挑梁', `${tag} 端部挠度比`, r.defl * 1000, 'mm', r.deflLim * 1000, r.deflUtil,
          '悬臂端竖向位移（正常使用极限状态）', 'δ ≤ L/150', false);
      add('立柱', `${tag} 压弯稳定应力比`, r.col.sigma / 1e6, 'MPa', P.fd, r.col.sigmaUtil,
          `λ=${r.col.lam.toFixed(0)}, φ=${r.col.phi.toFixed(2)}, N=${(r.col.axial/1000).toFixed(2)}kN, M=${(r.col.mom/1000).toFixed(2)}kN·m`,
          'σ = N/(φA) + M/W ≤ f');
      if (r.diag) add('斜杆', `${tag} 斜杆应力比`, Math.abs(r.diag.N) / 1000, 'kN', secDiag.A * P.fd / 1000, r.diag.util,
          r.diag.tension ? '受拉' : '受压（稳定控制）', '拉：N/A ≤ f；压：N/(φA) ≤ f');
      else if (P.diagType !== 'none' && P.diagCable) add('斜杆', `${tag} 斜杆`, 0, 'kN', 1, 0, '该工况下斜杆退出工作（拉索不能受压）', '—');
    }
    for (const f of foot) {
      add('基础', `${f.col.id} 抗拔（配重/锚固）`, f.uplift / 1000, 'kN', f.ballast / 1000 / 1.5,
          f.upUtil, `基础+柱自重 = ${(f.ballast/1000).toFixed(2)}kN，需 ≥ 1.5×上拔力`, 'K = (G柱+G基)/N拔 ≥ 1.5');
      add('基础', `${f.col.id} 抗倾覆（上抬绕柱脚）`, f.Mup / 1000, 'kN·m', f.Mres / 1000 / 1.5,
          f.overUtil, `抵抗力矩 = ${(f.Mres/1000).toFixed(2)}kN·m`, 'K = G·B/2 / M ≥ 1.5');
      add('基础', `${f.col.id} 地基压力`, f.pMax / 1000, 'kPa', P.soilFa, f.pUtil,
          `e=${f.e.toFixed(3)}m, B=${P.footB.toFixed(2)}m`, 'p_max ≤ fa');
      add('柱脚', `${f.col.id} 锚栓抗拔`, f.Tbolt / 1000, 'kN', P.anchorCap, f.Tutil,
          `每栓；M/lever - N/2，共 ${P.anchorN} 栓/受拉侧`, 'T = M/a - N/2 ≤ [T]');
    }
    add('整体', '整体抗倾覆（绕墙线）', Mot / 1000, 'kN·m', MresG / 1000 / 1.5, Mot > 0 ? 1.5 / Math.max(kGlobal, 1e-6) : 0,
        `抵抗 ${(MresG/1000).toFixed(2)} kN·m；柱子贴墙 → 力臂只有 ${P.wallGap} m`, 'K = Σ(G·d)/Σ(M风) ≥ 1.5');
    add('整体', '风吸总上抬力 / 总配重', totalUplift / 1000, 'kN', totalBallast / 1000 / 1.5, 1.5 / Math.max(kWall, 1e-6),
        `总配重 ${(totalBallast/1000).toFixed(2)} kN`, 'K ≥ 1.5');
    add('纵梁', '柱间纵梁应力比（平面外）', longChk.sigma / 1e6, 'MPa', P.fd, longChk.sigmaUtil,
        `最大柱距 ${spanMax.toFixed(2)} m；平面外风靠纵梁+平面斜撑`, 'σ = M/W ≤ f');

    /* ---- 反算：能扛多大风（强度 / 挠度 分开算） ---- */
    const utilsAt = (mult) => {
      const W2 = Object.assign({}, W);
      Object.assign(W2, { qUp: W.qUp * mult, qDown: W.qDown * mult, qDrag: W.qDrag * mult });
      let us = 0, ud = 0, who = '—';
      for (const k of ['up', 'down', 'wind']) {
        const rr = solveCase(P, geo, W2, k);
        for (let ci = 0; ci < rr.length; ci++) {
          const fr = rr[ci].frame, c0 = geo.cols[ci];
          const bm = checkMember(secBeam, fr.beam.Mmax.M, fr.beam.Nmax.N, fr.beam.Vmax.V, c0.L,
                                 { fd: P.fd, fv: P.fv, fy: P.fy, k: P.kBeam });
          const cc = checkMember(secCol, fr.colM.M, fr.colN.N, fr.colV.V, P.h,
                                 { fd: P.fd, fv: P.fv, fy: P.fy, k: P.kCol });
          const cand = [[bm.sigmaUtil, '挑梁应力(' + c0.id + ')'],
                        [cc.sigmaUtil, '立柱应力(' + c0.id + ')']];
          if (fr.diag && !fr.diagDropped) {
            const NN = -fr.diag._fl[0];
            const du = NN > 0
              ? NN / (secDiag.A * P.fd * 1e6)
              : Math.abs(NN) / (SOLVER.phiBuckling(P.kBeam * fr.diag._L / secDiag.i, P.fy * 1e6) * secDiag.A * P.fd * 1e6);
            cand.push([du, '斜杆(' + c0.id + ')']);
          }
          if (k === 'up') {
            const f0 = foot[ci], upN = Math.max(0, -fr.base.N);
            if (upN > 0) {
              cand.push([1.5 * upN / f0.ballast, '基础抗拔(' + c0.id + ')']);
              cand.push([1.5 * upN * f0.leverUp / f0.Mres, '基础抗倾覆(' + c0.id + ')']);
            }
          }
          for (const cp of cand) if (cp[0] > us) { us = cp[0]; who = cp[1] + ' · ' + cases[k].name.split(' ')[0]; }
          ud = Math.max(ud, Math.abs(fr.tipDefl) / (c0.L / 150));
        }
      }
      // 锚栓拉力基本随风压线性放大
      for (let ci = 0; ci < foot.length; ci++) {
        const f0 = foot[ci];
        const t2 = f0.Tbolt / (P.anchorCap * 1000);
        if (t2 > 0 && t2 * mult > us) { us = t2 * mult; who = '锚栓(' + f0.col.id + ')'; }
      }
      return { us, ud, who };
    };
    let vStr = 0, vDef = 0, vStrWho = '—';
    if (!opts.noBack) {
      const u0 = utilsAt(0);
      if (u0.us < 1) {
        let a = 0, b = 8;
        for (let i = 0; i < 40; i++) { const m = (a + b) / 2; if (utilsAt(m).us < 1) a = m; else b = m; }
        vStr = WIND.w2v(P.w0 * a); vStrWho = utilsAt(a).who;
      }
      if (u0.ud < 1) {
        let a = 0, b = 8;
        for (let i = 0; i < 40; i++) { const m = (a + b) / 2; if (utilsAt(m).ud < 1) a = m; else b = m; }
        vDef = WIND.w2v(P.w0 * a);
      }
    }
    // 安全性（承载力）才是"会不会塌"的判据；挠度只影响观感，单独列
    const vmax = vStr || 0;
    const vGovern = vStrWho;
    const deflFailAtRest = (vDef || 0) <= 0;

    /* ---- 文字建议 ---- */
    if (W.wk * W.cUp * geo.area * 1000 / 1000 > 8) warn.push(
      `风吸上抬力约 ${(W.qUp * geo.area).toFixed(1)} kN（≈${(W.qUp * geo.area * 100).toFixed(0)} kg 往上提）。这个量级靠膨胀螺栓钉在普通地坪上是压不住的。`);
    if (perCol.length >= 3) {
      const tmax = Math.max(...perCol.map(p => p.col.tw));
      if (tmax > 3.0) warn.push(
        `最大一根柱要管 ${tmax.toFixed(1)} m 宽的网（${(tmax*geo.netW).toFixed(1)} m²），三柱在 8 m 长边上还是偏稀。`);
    }
    if (P.diagType === 'above' && P.diagCable) warn.push(
      '上斜拉用拉索/圆钢只能受拉：风压向下那一工况斜杆会退出工作，挑梁要单独扛住 P·L 的悬臂弯矩。斜杆是冗余，不能当主受力构件算。');
    if (P.wallAnchored) warn.push(
      '网绑在 2 m 砖墙顶：墙只能帮"向下"的忙，帮不了"向上"的忙。风吸工况已按墙不参与计算。');

    /* ---- 分区结论：强度为准，挠度单独给 ---- */
    const ulsChk = checks.filter(c => c.uls);
    const slsChk = checks.filter(c => !c.uls);
    const uMax = ulsChk.reduce((a, c) => Math.max(a, c.ratio), 0);
    const dMax = slsChk.reduce((a, c) => Math.max(a, c.ratio), 0);
    const worstUtil = Math.max(uMax, dMax);
    const state = uMax <= 0.85 ? 'ok' : uMax <= 1.0 ? 'warn' : 'bad';
    const stateStrength = state;
    const stateService = dMax <= 0.85 ? 'ok' : dMax <= 1.0 ? 'warn' : 'bad';

    return {
      P, geo, W, cases, perCol, foot, checks, warn, results,
      worst, spanMax, longChk, totalUplift, totalBallast, kWall, Mot, MresG, kGlobal,
      vmax, vStr, vDef, vGovern, deflFailAtRest, worstUtil, uMax, dMax, state,
      stateStrength, stateService,
      secs: { secCol, secBeam, secDiag, secLong },
    };
  }

  /* ------------------------------------------------------------------
     方案对比：把常见的几种"加固方向"各算一遍，按能扛的风速排序
     ------------------------------------------------------------------ */
  const SCHEMES = [
    { id: 'A', name: '原方案：3 柱 + Φ89 挑梁 + ⌀12 上斜拉', over: {} },
    { id: 'B', name: '加柱：4 柱均分', over: { nCol: 4, tipX: [0.4, 2.6, 4.9, 7.2], baseY: [2.4, 0.4, 0.4, 0.4] } },
    { id: 'C', name: '加柱：5 柱均分', over: { nCol: 5, tipX: [0.4, 2.2, 4.0, 5.8, 7.5], baseY: [2.4, 0.4, 0.4, 0.4, 0.4] } },
    { id: 'D', name: '换厚管：挑梁/柱 Φ140×5', over: { secBeam: 'Φ140x5.0', secCol: 'Φ140x5.0' } },
    { id: 'E', name: '换方管：□120×120×6', over: { secBeam: '□120x120x6', secCol: '□120x120x6' } },
    { id: 'F', name: '加大基础：1.4×1.4×0.9', over: { footB: 1.4, footH: 0.9 } },
    { id: 'G', name: '缩短挑出：网改成 8×3', over: { netW: 3.0 } },
    { id: 'H', name: '下撑代替上斜拉（刚性管）', over: { diagType: 'below', diagCable: false, secDiag: 'Φ48x2.5' } },
    { id: 'I', name: '组合拳：下撑+5柱+Φ140×5+1.2m基础',
      over: { diagType: 'below', diagCable: false, secDiag: 'Φ48x2.5',
              nCol: 5, tipX: [0.4, 2.2, 4.0, 5.8, 7.5], baseY: [2.4, 0.4, 0.4, 0.4, 0.4],
              secBeam: 'Φ140x5.0', secCol: 'Φ140x5.0', footB: 1.2, footH: 0.8 } },
    { id: 'J', name: '大风前收网（受风面积折到 15%）', over: { netDeployed: false } },
  ];

  function compare(P0) {
    const base = Object.assign(defaults(), P0 || {});
    const out = [];
    for (const sc of SCHEMES) {
      const P = Object.assign({}, base, sc.over);
      let R;
      try { R = run(P); } catch (e) { out.push({ id: sc.id, name: sc.name, err: String(e), vmax: 0 }); continue; }
      const steel = R.geo.cols.length *
        (R.secs.secCol.A * P.h + R.secs.secBeam.A * R.geo.cols[0].L) * RHO_STEEL;
      const concrete = P.footB * P.footB * P.footH * R.geo.cols.length;
      out.push({
        id: sc.id, name: sc.name, state: R.state,
        vmax: R.vmax, vStr: R.vStr, vDef: R.vDef, vGovern: R.vGovern,
        beaufort: WIND.beaufort(R.vmax),
        uMax: R.uMax, dMax: R.dMax,
        steel, concrete, cost: steel * 9 + concrete * 600,
        R,
      });
    }
    return out.sort((a, b) => (b.vmax || 0) - (a.vmax || 0));
  }

  /* ------------------------------------------------------------------
     自动找方案：在"加柱 / 换管 / 加大基础 / 改斜撑"里扫一遍，
     挑出在"设计风"下各校核都过关（≤0.9）且造价最低的组合
     ------------------------------------------------------------------ */
  const SEC_CAND = ['Φ89x3.0', 'Φ114x4.0', 'Φ140x4.0', 'Φ140x5.0', 'Φ165x5.0', 'Φ219x6.0',
                    '□80x80x4', '□100x100x4', '□120x120x4', '□120x120x6',
                    '□150x150x5', '□150x150x8', '□200x200x6', '□200x200x8'];

  function colPositions(n, wallGap, netL) {
    const tipX = [], baseY = [];
    if (n === 3) { tipX.push(wallGap, 2.2, 6.2); baseY.push(2.4, wallGap, wallGap); }
    else {
      tipX.push(wallGap); baseY.push(2.4);
      const rest = n - 1;
      for (let i = 0; i < rest; i++) { tipX.push(1.6 + (netL - 2.0) * (rest === 1 ? 0.5 : i / (rest - 1))); baseY.push(wallGap); }
    }
    return { tipX, baseY };
  }

  function autofix(P0, target) {
    const base = Object.assign(defaults(), P0 || {});
    const aim = target || 0.9;
    const out = [];
    const ns = [3, 4, 5, 6];
    const diags = [
      { diagType: 'below', diagCable: false, secDiag: 'Φ60x2.5', tag: '刚性下撑' },
      { diagType: 'above', diagCable: false, secDiag: 'Φ60x2.5', tag: '刚性上斜撑' },
      { diagType: 'above', diagCable: true, secDiag: '⌀16', tag: '拉索上斜拉' },
      { diagType: 'none', tag: '无斜撑' },
    ];
    const foots = [0.8, 1.0, 1.2, 1.5, 1.8, 2.2];
    for (const n of ns) {
      const pos = colPositions(n, base.wallGap, base.netL);
      for (const dg of diags) {
        for (const fb of foots) {
          for (const sec of SEC_CAND) {
            const P = Object.assign({}, base, pos, dg, {
              nCol: n, secCol: sec, secBeam: sec, footB: fb, footH: Math.max(0.5, Math.min(1.2, fb * 0.7)),
            });
            let R;
            try { R = run(P, { noBack: true }); } catch (e) { continue; }
            if (R.uMax <= aim) {
              const steel = n * (R.secs.secCol.A * P.h + R.secs.secBeam.A * R.geo.cols[0].L) * RHO_STEEL;
              const conc = fb * fb * P.footH * n;
              out.push({ P, R, n, sec, fb, dg: dg.tag, steel, conc, cost: steel * 9 + conc * 600, uMax: R.uMax });
            }
          }
        }
      }
    }
    out.sort((a, b) => a.cost - b.cost);
    return out.slice(0, 12);
  }

  return { defaults, build, run, bracketFrame, solveCase, checkMember, compare, autofix, colPositions, SCHEMES };
})();
if (typeof module !== 'undefined') module.exports = MODEL;
