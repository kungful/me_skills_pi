/* =====================================================================
   model.js —— 把「L 形墙内角 + 三柱 + 镀锌管三角挑梁 + 太阳网」
   变成一个可算的力学模型：几何 → 荷载 → 杆系有限元 → 校核 → 反算
   ===================================================================== */
const MODEL = (function () {

  const G = 9.81, RHO_STEEL = 7850;

  /* ------------------------------------------------------------------
     真实场地（按用户在 Blender 里重建的模型量出来，单位 m）
     坐标系：x 沿主楼正面，y = 从主楼墙面向院子里的距离（正装在院子里）
     ------------------------------------------------------------------ */
  const SITE = {
    house: { x0: 0, x1: 9.6, y0: -10.0, y1: 0, h: 13.6 },      // 4 层主楼
    yard:  { x0: -1.04, x1: 10.69, y0: 0, y1: 9.79 },          // 门前院子 11.7 × 9.8
    wallS: { x0: -1.28, x1: 10.69, y: 9.79, h: 2.0 },          // 南围墙
    wallW: { x: -1.04, y0: 0, y1: 9.79, h: 2.0 },              // 西围墙
    wallN: { x0: -1.28, x1: 9.65, y: 10.95, h: 2.0 },          // 北围墙（主楼后）
    door:  { x0: 4.10, x1: 5.90 },                             // 大门位置（南面）
    slabZ: [3.40, 6.40, 9.40, 12.70],                          // 楼板/圈梁标高
    anchorOK: [[0, 4.0], [5.3, 6.9]],                          // z≈4.5 处的实体墙段（能打锚栓）
  };

  /* ------------------------------------------------------------------
     默认参数：按用户说的条件——L 形墙 8m + 5m，墙高 2m，网 8×4=32m²，
     三根柱子贴墙，镀锌管焊三角挑梁，上斜拉，太阳网可收
     ------------------------------------------------------------------ */
  function defaults() {
    return {
      /* 场地 */
      region: '广州', w0: 0.60, w0Factor: 1.0, rough: 'C', z: 3.0,
      /* 场地布局：'house' 靠主楼悬挑（地面零占用）| 'yard' 院子独立三柱 */
      layout: 'house',
      wallZs: 3.05,                 // 挑臂标高（靠主楼方案）
      anchorZ: 4.40,                // 刚性斜撑在墙上的锚固标高
      houseShare: 0.50,             // 主楼分担竖向荷载比例（4 层框架，上下都算数）
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
      diagCable: false,             // ★ 刚性斜撑（一根管上下都管用）
      diagBoth: false,              // 上下双钢丝绳：下压靠上绳、上抬靠下绳
      rDown: 1.30,                  // 下拉绳锚点比挑臂低多少
      /* 构件 */
      secCol: 'Φ89x3.0', secBeam: 'Φ89x3.0', secDiag: 'Φ114x4.0',
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
    if (P.layout === 'house') return buildHouse(P);
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
        { x1: 0, y1: 0, x2: P.netL, y2: 0, len: P.netL, id: '围墙' },
      ],
      Hw: P.Hw,
    };
  }

  /* ---------------- 靠主楼悬挑：墙面托架布置 ---------------- */
  function buildHouse(P) {
    const slope = P.slopeDeg * Math.PI / 180;
    const netW = P.netW, rise = netW * Math.sin(slope);
    const n = Math.max(2, Math.min(6, P.nCol | 0));
    const x0 = P.tipX0 !== undefined ? P.tipX0 : 0.45;
    const x1 = P.tipX1 !== undefined ? P.tipX1 : (SITE.house.x1 - 0.15);
    const tw = (x1 - x0) / n;
    const cols = [];
    for (let i = 0; i < n; i++) {
      const x = x0 + tw * (i + 0.5);
      cols.push({
        i, id: 'T' + (i + 1), kind: 'wall',
        base: { x, y: 0 }, tip: { x, y: netW },       // 墙面起挑 → 外端
        L: netW, h: P.wallZs, r: P.anchorZ - (P.wallZs - rise),
        anchorZ: P.anchorZ, tw,
      });
    }
    cols.forEach(c => c.share = c.tw / (x1 - x0));
    return {
      cols, netL: x1 - x0, netW, rise, slope, area: (x1 - x0) * netW,
      x0, x1, site: SITE, house: true,
      walls: [], Hw: 0,
    };
  }

  /* ---------------- 单榀（柱 + 挑梁 + 斜杆）平面刚架 ---------------- */
  function bracketFrame(P, geo, c, tipP, tipFx, cableActive) {
    const S = SOLVER;
    const secCol = S.PIPE_MAP[P.secCol] || S.SEC.round(89, 3);
    const secBeam = S.PIPE_MAP[P.secBeam] || S.SEC.round(89, 3);
    const secDiag = S.PIPE_MAP[P.secDiag] || S.SEC.bar(12);
    const E = 2.06e11;
    const L = c.L;
    if (c.kind === 'wall') return wallBracket(P, geo, c, tipP, tipFx);
    const h = P.h, r = (P.diagType === 'none' ? 0 : P.r);

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

  /* ---------------- 墙面托架（靠主楼悬挑）：墙上两个支座 + 一根斜撑 ---------------- */
  function wallBracket(P, geo, c, tipP, tipFx) {
    const S = SOLVER;
    const secBeam = S.PIPE_MAP[P.secBeam] || S.SEC.round(89, 3);
    const secDiag = S.PIPE_MAP[P.secDiag] || S.SEC.round(89, 3);
    const E = 2.06e11, L = c.L, ZB = c.h, ZA = c.anchorZ;
    const TIPZ = ZB - geo.rise;
    const nodes = [
      { x: 0, y: ZA, fix: [true, true, true] },   // 0 墙上斜撑锚点（可拉可压）
      { x: 0, y: ZB, fix: [true, true, true] },   // 1 墙根底板（弯矩+剪力+轴力）
      { x: L, y: TIPZ },                          // 2 挑臂外端
    ];
    const elems = [
      { i: 0, j: 2, E, A: secDiag.A, I: secDiag.I, truss: true,
        tensionOnly: !!(P.diagCable && P.diagType !== 'none'), name: '斜杆', sec: secDiag, idx: 0 },
      { i: 1, j: 2, E, A: secBeam.A, I: secBeam.I, name: '挑臂', sec: secBeam, idx: 1 },
    ];
    if (P.diagBoth) {
      nodes.push({ x: 0, y: ZB - (P.rDown || 1.3), fix: [true, true, true] });   // 3 下拉绳锚点
      elems.push({ i: 3, j: 2, E, A: secDiag.A, I: secDiag.I, truss: true,
                   tensionOnly: true, name: '斜杆下', sec: secDiag, idx: 2 });
    }
    const wBeam = -secBeam.A * RHO_STEEL * G;
    const loads = [{ node: 2, fx: tipFx, fy: tipP }];
    const res = S.analyze({ nodes, elems, loads, udl: [{ elem: 1, w: wBeam }] });
    const beam = res.elems.find(e => e.name === '挑臂');
    // 上下两根里，取"正在受力且更大"的那根做校核
    const cands = [res.elems.find(e => e.name === '斜杆'), res.elems.find(e => e.name === '斜杆下')]
      .filter(Boolean).sort((a, b) => Math.abs(-b._fl[0]) - Math.abs(-a._fl[0]));
    const diag = cands[0] || null;
    const diagDn = res.elems.find(e => e.name === '斜杆下') || null;
    const R0 = res.R[0] || { fx: 0, fy: 0, mz: 0 };   // 斜撑锚点
    const R1 = res.R[1] || { fx: 0, fy: 0, mz: 0 };   // 墙根底板
    const tip = res.U;
    return {
      res, nodes, elems, secBeam, secDiag, beam, diag, colSegs: [],
      colM: { M: 0, N: 0, V: 0 }, colN: { N: 0 }, colV: { V: 0 },
      wallAnchor: { M: -R1.mz, V: R1.fx, N: R1.fy },      // 墙根底板受力
      diagAnchor: { H: R0.fx, V: R0.fy },                 // 斜撑锚点受力
      base: { N: 0, V: 0, M: 0 },
      tipDefl: tip[2 * 3 + 1] || 0, tipDeflX: tip[2 * 3] || 0,
      udlBeam: wBeam, diagForce: diag ? (diag.dropped ? 0 : -diag._fl[0]) : 0,
      diagDropped: diag ? !!diag.dropped : false,
      diagTension: diag ? (-diag._fl[0] > 0) : false,
      diagDnForce: diagDn ? -diagDn._fl[0] : 0,
      wBeam,
    };
  }

  /* ---------------- 工况求解 ---------------- */
  function solveCase(P, geo, W, kind, opts) {
    opts = opts || {};
    const cols = geo.cols;
    const out = [];
    const stow = P.netDeployed ? 1 : P.stowFactor;
    let wallShare;
    if (P.layout === 'house') {
      wallShare = P.houseShare;                    // 主楼是 4 层框架，上下都能扛
    } else {
      wallShare = P.wallAnchored ? P.wallShare : 0;
      if (kind === 'up') wallShare = 0;            // 2m 砖墙拉不住，风吸时不算它
      if (!P.wallAnchored) wallShare = 0;
    }

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
        const kB = (c.kind === 'wall' ? 1.0 : P.kBeam);   // 墙托架的挑臂是桁架弦杆 → k=1.0
        const beam = checkMember(secBeam, fr.beam.Mmax.M, fr.beam.Nmax.N, fr.beam.Vmax.V, c.L, { fd: P.fd, fv: P.fv, fy: P.fy, k: kB });
        const col = checkMember(secCol, fr.colM.M, fr.colN.N, fr.colV.V, P.h, { fd: P.fd, fv: P.fv, fy: P.fy, k: P.kCol });
        let diag = null;
        if (fr.diag && !fr.diagDropped) {
          const N = -fr.diag._fl[0];
          diag = { N, sec: secDiag, L: fr.diag._L,
                   util: N > 0 ? N / (secDiag.A * P.fd * 1e6)
                               : (() => { const lam = fr.diag._L / secDiag.i;   // 桁架杆两端铰接 → k=1.0
                                          const phi = S.phiBuckling(lam, P.fy * 1e6);
                                          return Math.abs(N) / (phi * secDiag.A * P.fd * 1e6); })(),
                   tension: N > 0 };
        }
        const Ld = Math.hypot(c.L, (c.anchorZ !== undefined ? c.anchorZ : P.h + P.r) - c.h);
        const diagLam = fr.diag ? Ld / secDiag.i : 0;
        const wall = c.kind === 'wall' ? {
          plateM: Math.abs(fr.wallAnchor.M),
          plateV: Math.abs(fr.wallAnchor.V),
          plateN: fr.wallAnchor.N,
          anchorT: Math.hypot(fr.diagAnchor.H, fr.diagAnchor.V),
          diagLam,
        } : null;
        const deflLim = c.L / 150;
        row.cases[k] = {
          wall,
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
      if (c.kind === 'wall') {                       // 靠主楼悬挑：没有基础，只有墙锚
        let Tmax = 0, Mmax = 0, Vmax2 = 0, Nmin = 1e9, lamMax = 0;
        for (const k of ['up', 'down', 'wind']) {
          const w = row.cases[k].wall;
          Tmax = Math.max(Tmax, w.anchorT);
          Mmax = Math.max(Mmax, w.plateM);
          Vmax2 = Math.max(Vmax2, w.plateV);
          Nmin = Math.min(Nmin, w.plateN);
          lamMax = Math.max(lamMax, P.diagCable ? 0 : w.diagLam);   // 钢丝绳只受拉，不算长细比
        }
        const a = P.basePlateLever || 0.35;
        const Tplate = Mmax / a - Math.min(0, Nmin) / 2;      // 底板锚栓
        const Tbolt = Math.max(Tplate, 0) / Math.max(1, P.anchorN);
        const Tanchor = Tmax / Math.max(1, P.anchorN);
        foot.push({
          col: c, wall: true, Tbolt, Tanchor, Mmax, Vmax2, lamMax,
          ballast: 0, uplift: 0, kUp: 99, kOver: 99, Mup: 0, Mres: 0,
          pMax: 0, pLim: P.soilFa * 1000, e: 0, B: 0, leverUp: 0,
          Tutil: Math.max(Tbolt, Tanchor) / (P.anchorCap * 1000),
          pUtil: 0, overUtil: 0, upUtil: 0,
          lamUtil: lamMax / 150,
        });
        continue;
      }
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
    const kWall = totalBallast > 0 ? (totalUplift > 0 ? totalBallast / totalUplift : 99) : 99;
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
      if (f.wall) {
        add('墙锚固', `${f.col.id} 斜撑锚点抗拔`, f.Tanchor / 1000, 'kN', P.anchorCap, f.Tanchor / Math.max(1, P.anchorN) / (P.anchorCap * 1000),
            `锚进主楼混凝土梁/柱，${P.anchorN} 个 M16 化学锚栓`, 'T_锚 = 斜撑轴力，每个锚栓分摊');
        add('墙锚固', `${f.col.id} 墙根底板抗拔`, f.Tbolt / 1000, 'kN', P.anchorCap, f.Tbolt / (P.anchorCap * 1000),
            `底板弯矩 ${(f.Mmax / 1000).toFixed(2)} kN·m / 力臂 ${(P.basePlateLever || 0.35).toFixed(2)} m`, 'T = M/a − N/2');
        add('墙锚固', `${f.col.id} 斜撑长细比 λ`, f.lamMax, '—', 150, f.lamUtil,
            'GB50017 受压构件 λ ≤ 150', 'λ = L斜 / i');
        add('墙锚固', `${f.col.id} 墙根剪力`, f.Vmax2 / 1000, 'kN', P.anchorCap * P.anchorN, f.Vmax2 / (P.anchorCap * P.anchorN * 1000),
            '底板抗剪（锚栓受剪 + 摩擦）', 'V ≤ [V]');
        continue;
      }
      add('基础', `${f.col.id} 抗拔（配重/锚固）`, f.uplift / 1000, 'kN', f.ballast / 1000 / 1.5,
          f.upUtil, `基础+柱自重 = ${(f.ballast/1000).toFixed(2)}kN，需 ≥ 1.5×上拔力`, 'K = (G柱+G基)/N拔 ≥ 1.5');
      add('基础', `${f.col.id} 抗倾覆（上抬绕柱脚）`, f.Mup / 1000, 'kN·m', f.Mres / 1000 / 1.5,
          f.overUtil, `抵抗力矩 = ${(f.Mres/1000).toFixed(2)}kN·m`, 'K = G·B/2 / M ≥ 1.5');
      add('基础', `${f.col.id} 地基压力`, f.pMax / 1000, 'kPa', P.soilFa, f.pUtil,
          `e=${f.e.toFixed(3)}m, B=${P.footB.toFixed(2)}m`, 'p_max ≤ fa');
      add('柱脚', `${f.col.id} 锚栓抗拔`, f.Tbolt / 1000, 'kN', P.anchorCap, f.Tutil,
          `每栓；M/lever - N/2，共 ${P.anchorN} 栓/受拉侧`, 'T = M/a - N/2 ≤ [T]');
    }
    if (P.layout === 'house') {
      const tot = W.qUp * geo.area;
      add('整体', '风吸总上抬力 → 交给主楼', tot, 'kN', 1e5, tot / 5e4,
          `主楼是 4 层混凝土框架：${tot.toFixed(1)} kN 上抬力对它可忽略（但锚栓必须打进混凝土梁柱）`,
          '自平衡 / 传给主楼');
    } else {
      add('整体', '整体抗倾覆（绕墙线）', Mot / 1000, 'kN·m', MresG / 1000 / 1.5, Mot > 0 ? 1.5 / Math.max(kGlobal, 1e-6) : 0,
          `抵抗 ${(MresG/1000).toFixed(2)} kN·m；柱子贴墙 → 力臂只有 ${P.wallGap} m`, 'K = Σ(G·d)/Σ(M风) ≥ 1.5');
      add('整体', '风吸总上抬力 / 总配重', totalUplift / 1000, 'kN', totalBallast / 1000 / 1.5, 1.5 / Math.max(kWall, 1e-6),
          `总配重 ${(totalBallast/1000).toFixed(2)} kN`, 'K ≥ 1.5');
    }
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
                                 { fd: P.fd, fv: P.fv, fy: P.fy, k: (c0.kind === 'wall' ? 1.0 : P.kBeam) });
          const cc = checkMember(secCol, fr.colM.M, fr.colN.N, fr.colV.V, P.h,
                                 { fd: P.fd, fv: P.fv, fy: P.fy, k: P.kCol });
          const cand = [[bm.sigmaUtil, '挑梁应力(' + c0.id + ')'],
                        [cc.sigmaUtil, '立柱应力(' + c0.id + ')']];
          if (fr.diag && !fr.diagDropped) {
            const NN = -fr.diag._fl[0];
            const du = NN > 0
              ? NN / (secDiag.A * P.fd * 1e6)
              : Math.abs(NN) / (SOLVER.phiBuckling(fr.diag._L / secDiag.i, P.fy * 1e6) * secDiag.A * P.fd * 1e6);
            cand.push([du, '斜杆(' + c0.id + ')']);
          }
          if (k === 'up') {
            const f0 = foot[ci], upN = Math.max(0, -fr.base.N);
            if (f0 && f0.wall) {
              const w = rr[ci] && null;
            } else if (upN > 0) {
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
        const t2 = Math.max(f0.Tbolt, f0.Tanchor || 0) / (P.anchorCap * 1000);
        if (t2 > 0 && t2 * mult > us) { us = t2 * mult; who = (f0.wall ? '墙锚栓(' : '锚栓(') + f0.col.id + ')'; }
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
    const house = base.layout === 'house';
    const SECS = ['Φ76x3.0', 'Φ89x3.0', 'Φ114x4.0', 'Φ140x4.0', 'Φ140x5.0', 'Φ165x5.0',
                  '□80x80x4', '□100x100x4', '□120x120x4', '□150x150x5'];
    const DIAG = [
      { secDiag: 'Φ89x3.0', diagCable: false, diagBoth: false, tag: '刚性斜撑 Φ89' },
      { secDiag: 'Φ114x4.0', diagCable: false, diagBoth: false, tag: '刚性斜撑 Φ114' },
      { secDiag: '⌀12', diagCable: true, diagBoth: true, tag: '钢丝绳上下双拉' },
      { secDiag: '⌀12', diagCable: true, diagBoth: false, tag: '钢丝绳只上拉' },
    ];
    for (const n of [3, 4, 5]) {
      const nws = house ? [3.5, 4.0, 4.5, 5.0] : [3.0, 3.5, 4.0];
      for (const nw of nws) {
        for (const dg of DIAG) {
          for (const sec of SECS) {
            const foots = house ? [null] : [1.0, 1.2, 1.5, 1.8];
            for (const fb of foots) {
              const P = Object.assign({}, base, dg, {
                nCol: n, netW: nw, secBeam: sec,
                secCol: house ? sec : sec, secDiag: dg.secDiag,
              });
              if (!house) { P.footB = fb; P.footH = Math.max(0.5, Math.min(1.2, fb * 0.7)); }
              let R;
              try { R = run(P, { noBack: true }); } catch (e) { continue; }
              if (R.uMax > aim) continue;
              const ldx = house
                ? Math.hypot(P.netW, P.anchorZ - (P.wallZs - R.geo.rise))
                : 3.7;
              const steel = R.geo.cols.reduce((a2, c) => a2 + R.secs.secBeam.A * c.L + R.secs.secCol.A * (house ? 0 : c.h), 0) * RHO_STEEL
                          + R.secs.secDiag.A * ldx * R.geo.cols.length * RHO_STEEL;
              const conc = house ? 0 : P.footB * P.footB * P.footH * R.geo.cols.length;
              out.push({ P, R, n, nw, sec, fb, dg: dg.tag, steel, conc,
                         cost: steel * 11 + conc * 700, uMax: R.uMax, vmax: R.vmax });
            }
          }
        }
      }
    }
    out.sort((a2, b2) => a2.cost - b2.cost);
    const top = out.slice(0, 12);
    for (const o of top) {                       // 给前 12 个补上反算风速
      try { o.vmax = run(o.P).vmax; } catch (e) { o.vmax = 0; }
    }
    return top;
  }

  const PRESETS = [
    { id: 'H1', name: '★ 靠主楼悬挑（推荐）', desc: '3 根托架，挑出 4.0m，Φ89×3 挑臂 + Φ114×4 刚性斜撑，斜撑锚在主楼墙 4.4m。地面零柱子。',
      over: { layout: 'house', nCol: 3, netW: 4.0, wallZs: 3.05, anchorZ: 4.40,
              secBeam: 'Φ89x3.0', secDiag: 'Φ114x4.0', diagCable: false, diagBoth: false } },
    { id: 'H2', name: '加大：挑出 4.5m', desc: '同样 3 根，换 Φ114×4 挑臂 + Φ114×4 斜撑，能盖住整车。',
      over: { layout: 'house', nCol: 3, netW: 4.5, wallZs: 3.05, anchorZ: 4.40,
              secBeam: 'Φ114x4.0', secDiag: 'Φ114x4.0', diagCable: false, diagBoth: false } },
    { id: 'H3', name: '4 根托架（更稳）', desc: '挑出 4.0m，4 根分担，每根少担 25%。',
      over: { layout: 'house', nCol: 4, netW: 4.0, wallZs: 3.05, anchorZ: 4.40,
              secBeam: 'Φ89x3.0', secDiag: 'Φ114x4.0', diagCable: false, diagBoth: false } },
    { id: 'H4', name: '钢丝绳·上下双拉', desc: '斜撑换成钢丝绳，但必须上下各一根：下压靠上绳、上抬靠下绳。',
      over: { layout: 'house', nCol: 3, netW: 4.0, wallZs: 3.05, anchorZ: 4.40,
              secBeam: 'Φ114x4.0', secDiag: '⌀12', diagCable: true, diagBoth: true, rDown: 1.30 } },
    { id: 'H4b', name: '钢丝绳·只上拉（✗不行）', desc: '只拉一根上绳：风吸时绳受压失效，挑臂独扛 P·L —— 只能扛 8 级风。',
      over: { layout: 'house', nCol: 3, netW: 4.0, wallZs: 3.05, anchorZ: 4.40,
              secBeam: 'Φ114x4.0', secDiag: '⌀12', diagCable: true, diagBoth: false } },
    { id: 'H5', name: '低成本版 Φ89×3 全用', desc: '挑臂和斜撑都用 Φ89×3，更省钱但余量小。',
      over: { layout: 'house', nCol: 3, netW: 4.0, wallZs: 3.05, anchorZ: 4.40,
              secBeam: 'Φ89x3.0', secDiag: 'Φ89x3.0', diagCable: false, diagBoth: false } },
    { id: 'H6', name: '降低标高 2.6m', desc: '挑臂压到 2.6m（车顶 1.5m 够用），风更小、更好看。',
      over: { layout: 'house', nCol: 3, netW: 4.0, wallZs: 2.60, anchorZ: 4.40,
              secBeam: 'Φ89x3.0', secDiag: 'Φ114x4.0', diagCable: false, diagBoth: false } },
    { id: 'H7', name: '大风前收网', desc: 'H1 不动结构，只加一条：预报大风就把网收起来。',
      over: { layout: 'house', nCol: 3, netW: 4.0, wallZs: 3.05, anchorZ: 4.40,
              secBeam: 'Φ89x3.0', secDiag: 'Φ114x4.0', diagCable: false, diagBoth: false, netDeployed: false } },
    { id: 'W1', name: '靠围墙挑檐 2.0m（上斜杆）', desc: '3 根 □120×120×4 立柱贴围墙，立柱往上伸 0.8m，上斜杆拉到挑臂端；1.0×0.8m 基础。',
      over: { layout: 'yard', nCol: 3, netL: 8.0, netW: 2.0, h: 2.60, r: 0.80,
              diagType: 'above', diagCable: false,
              secCol: '□120x120x4', secBeam: '□120x120x4', secDiag: '□120x120x4',
              footB: 1.0, footH: 0.8, basePlateLever: 0.60, anchorCap: 60,
              tipX: [1.6, 4.0, 6.4], baseY: [0.45, 0.45, 0.45] } },
    { id: 'W2', name: '靠围墙挑檐 2.5m（上斜杆·加大）', desc: '换 □150×150×5 + 1.2×0.9m 基础，挑 2.5m。2m 砖墙扛不了上拔，基础必须做大。',
      over: { layout: 'yard', nCol: 3, netL: 8.0, netW: 2.5, h: 2.60, r: 0.80,
              diagType: 'above', diagCable: false,
              secCol: '□150x150x5', secBeam: '□150x150x5', secDiag: '□150x150x5',
              footB: 1.2, footH: 0.9, basePlateLever: 0.60, anchorCap: 60,
              tipX: [1.6, 4.0, 6.4], baseY: [0.45, 0.45, 0.45] } },
    { id: 'O1', name: '旧：L形围墙三柱（对比）', desc: '院子中间三根 Φ219×6 柱 + 大基础，地面被占。留作对比。',
      over: { layout: 'yard', nCol: 3, netW: 4.0, h: 2.2, r: 1.2, diagType: 'below', diagCable: false,
              secCol: 'Φ219x6.0', secBeam: 'Φ219x6.0', secDiag: '□80x80x4',
              footB: 1.6, footH: 1.0, basePlateLever: 0.60, anchorCap: 60 } },
  ];
  function applyPreset(id, cur) {
    const pr = PRESETS.find(p => p.id === id);
    if (!pr) return cur;
    return Object.assign(defaults(), cur, pr.over);
  }
  function presetSummary() {
    return PRESETS.map(p => {
      const R = run(applyPreset(p.id, defaults()));
      let steel = 0;
      if (R.P.layout === 'house') {
        const Ld = Math.hypot(R.geo.netW, R.P.anchorZ - (R.P.wallZs - R.geo.rise));
        steel = R.geo.cols.length * (R.secs.secBeam.A * R.geo.netW + R.secs.secDiag.A * Ld) * RHO_STEEL
              + R.geo.netL * (R.secs.secBeam.A + R.secs.secDiag.A) * 0.9 * RHO_STEEL;
      } else {
        steel = R.geo.cols.reduce((a2, c) => a2 + R.secs.secCol.A * c.h + R.secs.secBeam.A * c.L, 0) * RHO_STEEL
              + R.secs.secDiag.A * 3.7 * R.geo.cols.length * RHO_STEEL;
      }
      const conc = R.P.layout === 'house' ? 0 : R.P.footB * R.P.footB * R.P.footH * R.geo.cols.length;
      return { id: p.id, name: p.name, desc: p.desc, vmax: R.vmax, u: R.uMax,
               beaufort: WIND.beaufort(R.vmax), gov: R.vGovern, steel, conc,
               cost: steel * 11 + conc * 700, state: R.state };
    });
  }

  return { defaults, build, run, bracketFrame, solveCase, checkMember, compare, autofix, colPositions, SCHEMES, PRESETS, applyPreset, presetSummary };
})();
if (typeof module !== 'undefined') module.exports = MODEL;
