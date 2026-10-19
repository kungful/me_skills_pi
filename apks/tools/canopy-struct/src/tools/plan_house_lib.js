/* =====================================================================
   新场地（主楼 9.6×10×13.6m + 11.7×9.8m 院子 + 2m 围墙）的方案对比
   关键差别：主楼是 4 层混凝土框架，楼板/圈梁在 z=2.75~3.40 / 6.24~6.40 / 9.24~9.40
             → 墙可以当"真正的支座"（拉得住、压得住），不像 2m 砖围墙
   用法：node tools/plan_house.js
   ===================================================================== */
require('./_load').loadAssets(['solver.js', 'wind.js', 'model.js']);
const S = SOLVER, W = WIND, M = MODEL;
const G = 9.81;

const P0 = Object.assign(M.defaults(), {
  region: '广州', w0: 0.60, rough: 'C', z: 3.0, porosity: 0.50,
  // 场地（Blender 实测）
  house: { x0: 0, x1: 9.6, y0: 0, y1: 10, h: 13.6, slabBands: [2.75, 3.40, 6.24, 6.40, 9.24, 9.40] },
  yard: { x0: -1.04, x1: 10.69, y0: -9.79, y1: 0 },
});
const Win = W.calc(P0);
const TAU = 0.5;      // 主楼分担比例（竖向，上下两个方向都算数）

/* ---------- 截面 ---------- */
const sec = n => S.PIPE_MAP[n] || S.SEC.round(76, 3);

/* ---------- 单榀：墙托架（可带外柱）平面刚架 ---------- */
function bracket(opt) {
  const { ZB, ZA, L, drop = 0.18, secBeam, secTie, secCol, column, rigid, below, E = 2.06e11 } = opt;
  const ZAef = below ? (ZB - ZA) : ZA;     // below=true → 斜杆锚在托架下方 ZB-ZA 处
  const ZT = ZB - drop;
  const nodes = [
    { x: 0, y: ZAef, fix: [1, 1, 1] },    // 0 墙上斜杆锚点
    { x: 0, y: ZB, fix: [1, 1, 1] },      // 1 墙根底板
    { x: L, y: ZT },                      // 2 挑臂外端
  ];
  const elems = [
    { i: 0, j: 2, E, A: secTie.A, I: secTie.I, truss: true, tensionOnly: !opt.rigid, name: '斜杆', idx: 0 },
    { i: 1, j: 2, E, A: secBeam.A, I: secBeam.I, name: '挑臂', idx: 1 },
  ];
  if (column) {
    nodes.push({ x: L, y: 0, fix: [1, 1, 1] });
    elems.push({ i: 3, j: 2, E, A: secCol.A, I: secCol.I, name: '外柱', idx: 2 });
  }
  const wBeam = -secBeam.A * 7850 * G;
  return { nodes, elems, ZT, wBeam };
}

function runBracket(opt, load) {
  const b = bracket(opt);
  const { nodes, elems, wBeam, ZT } = b;
  const loads = [{ node: 2, fx: load.Fh || 0, fy: -load.P }];   // P 向下为正 → fy 取负
  if (opt.column) loads.push({ node: 2, fy: -(opt.colWeight || 0) });
  const udl = [{ elem: 1, w: wBeam }];
  const r = S.analyze({ nodes, elems, loads, udl });
  const beam = r.elems.find(e => e.name === '挑臂');
  const tie = r.elems.find(e => e.name === '斜杆' || e.name === '拉杆');
  const col = r.elems.find(e => e.name === '外柱');
  const R0 = r.R[0] || { fx: 0, fy: 0, mz: 0 };   // 斜拉锚点
  const R1 = r.R[1] || { fx: 0, fy: 0, mz: 0 };   // 墙根底板
  const R3 = r.R[2] || { fx: 0, fy: 0, mz: 0 };   // 外柱脚
  return { r, beam, tie, col, R0, R1, R3, ZT, L: opt.L, wBeam };
}

/* ---------- 校核并反算最大风速 ---------- */
function evaluate(cfg) {
  const P = Object.assign({}, P0, cfg.over);
  const Wc = W.calc(P);
  const n = cfg.n, L = cfg.L;
  const X0 = cfg.X0, X1 = cfg.X1;
  const tw = (X1 - X0) / n;
  const Area = tw * L;
  const secBeam = sec(cfg.secBeam), secTie = sec(cfg.secTie);
  const secCol = cfg.secCol ? sec(cfg.secCol) : null;

  const compute = (mult) => {
    const out = { u: 0, who: '', defl: 0, results: {} };
    for (const kind of ['up', 'down', 'wind']) {
      let qv = 0, Fh = 0;
      const stow = P.netDeployed ? 1 : P.stowFactor;
      if (kind === 'up') qv = -Wc.qUp * mult * stow * Math.cos(P.slopeDeg * Math.PI / 180);
      if (kind === 'down') qv = Wc.qDown * mult * stow * Math.cos(P.slopeDeg * Math.PI / 180);
      const gNet = P.netMass * G / 1000;
      const gk = (P.gammaG * gNet + P.gammaW * qv) * Area * 1000 * (1 - TAU);
      const Pv = kind === 'wind' ? P.gammaG * gNet * Area * 1000 * (1 - TAU) : gk;
      if (kind === 'wind') Fh = P.gammaW * Wc.qDrag * mult * stow * tw * (L * Math.sin(P.slopeDeg * Math.PI / 180) + 0.30) * 1000;
      if (kind === 'up' || kind === 'down') Fh = P.gammaW * (kind === 'up' ? -1 : 1) * Wc.qUp * mult * stow * Math.sin(P.slopeDeg * Math.PI / 180) * Area * 1000;

      const res = runBracket(Object.assign({}, cfg, { secBeam, secTie, secCol }), { P: Pv, Fh });
      // 挑臂
      const bm = M.checkMember(secBeam, res.beam.Mmax.M, res.beam.Nmax.N, res.beam.Vmax.V, L, { fd: P.fd, fv: P.fv, fy: P.fy, k: 1.0 });
      const lamB = L / secBeam.i, lamBUtil = lamB / 150;   // GB50017 受压构件 λ≤150
      // 拉杆
      const Nt = res.tie ? -res.tie._fl[0] : 0;      // 拉索受压 → 退出工作，内力记 0
      const Ld = Math.hypot(L, Math.abs((cfg.below ? (cfg.ZB - cfg.ZA) : cfg.ZA) - cfg.ZB));
      const tieU = !res.tie ? 0
                 : Nt > 0 ? Nt / (secTie.A * P.fd * 1e6)
                 : Math.abs(Nt) / (S.phiBuckling(Ld / secTie.i, P.fy * 1e6) * secTie.A * P.fd * 1e6);
      // 墙锚栓：底板弯矩 T = M/a − N/2；斜拉锚点直接受 T
      const Tplate = Math.abs(res.R1.mz) / cfg.a - res.R1.fy / 2;
      const Tanchor = Math.max(Math.abs(res.R0.fx), Math.abs(res.R0.fy), 0) / cfg.nAnchor + Math.max(0, Tplate) / cfg.nAnchor;
      const wallU = Tanchor / (cfg.anchorCap * 1000);
      // 外柱
      let colU = 0, footU = 0;
      if (res.col) {
        const cm = M.checkMember(secCol, res.col.Mmax.M, res.col.Nmax.N, res.col.Vmax.V, P.hp || 2.2, { fd: P.fd, fv: P.fv, fy: P.fy, k: 2.0 });
        colU = cm.sigmaUtil;
        const up = Math.max(0, -res.R3.fy);
        const Gf = (cfg.footB || 1.0) ** 2 * (cfg.footH || 0.8) * 25 * 1000;
        footU = Math.max(up > 0 ? 1.5 * up / Gf : 0,
                         up > 0 ? 1.5 * up * res.L / (Gf * (cfg.footB || 1) / 2) : 0);
      }
      const defl = Math.abs(res.r.U[7] || 0);
      const lamT = Ld / secTie.i, lamTUtil = lamT / 150;
      const cand = [[bm.sigmaUtil, `挑臂应力·${kind}`], [lamBUtil, `挑臂长细比·${kind}`],
                    [tieU, `斜杆稳定·${kind}`], [lamTUtil, `斜杆长细比·${kind}`],
                    [wallU, `墙锚栓·${kind}`], [colU, `外柱应力·${kind}`], [footU, `柱基础·${kind}`]];
      for (const c of cand) if (c[0] > out.u) { out.u = c[0]; out.who = c[1]; }
      out.defl = Math.max(out.defl, defl / (L / 150));
      out.results[kind] = { P: Pv, Fh, res, bm, tieU, wallU, Tanchor, colU, footU, defl };
    }
    return out;
  };

  const u0 = compute(0);
  let mult = 0;
  if (u0.u < 1) {
    let a = 0, b = 12;
    for (let i = 0; i < 44; i++) { const m = (a + b) / 2; if (compute(m).u < 1) a = m; else b = m; }
    mult = a;
  }
  const vmax = W.w2v(P0.w0 * mult);
  const at1 = compute(1);
  return { cfg, P, W: Wc, tw, Area, u: at1.u, who: at1.who, vmax, mult,
           defl: at1.defl, at1, steel: null };
}


module.exports = { evaluate, P0, Win, TAU, sec, bracket, runBracket, S, W, M, G };
