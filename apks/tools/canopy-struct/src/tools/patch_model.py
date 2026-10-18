#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 model.js 的「反算 / 结论」段换成 ULS+SLS 分开的版本 + 加 compare()。"""
import io, re, sys

p = 'assets/model.js'
s = io.open(p, encoding='utf-8').read()

a = s.index('    /* ---- 反算')
b = s.index('    /* ---- 文字建议')
new = r'''    /* ---- 反算：能扛多大风（强度 / 挠度 分开算） ---- */
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
            const N = -fr.diag._fl[0];
            const du = N > 0
              ? N / (secDiag.A * P.fd * 1e6)
              : Math.abs(N) / (SOLVER.phiBuckling(P.kBeam * fr.diag._L / secDiag.i, P.fy * 1e6) * secDiag.A * P.fd * 1e6);
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
      // 锚栓：随风力按 √(1+mult)/√2 那样不是线性，这里用比例放大（保守取线性）
      let tu = 0;
      for (let ci = 0; ci < foot.length; ci++) {
        const f0 = foot[ci];
        if (f0.Tbolt > 0) tu = Math.max(tu, (f0.Tbolt * Math.max(mult, 0.001) / Math.max(mult, 0.001)) / (P.anchorCap * 1000));
      }
      for (let ci = 0; ci < foot.length; ci++) {
        const f0 = foot[ci];
        const t2 = f0.Tbolt / (P.anchorCap * 1000);
        // 设计风时 util=1 对应 mult=1；锚栓拉力基本随风压线性
        if (tu > 0 && t2 * mult > us) { us = t2 * mult; who = '锚栓(' + f0.col.id + ')'; }
      }
      return { us, ud, who };
    };
    let vStr = 0, vDef = 0, vStrWho = '—';
    {
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
    const vmax = Math.max(0, Math.min(vStr || 0, vDef || 0));
    const vGovern = (vStr && vStr <= (vDef || 1e9)) ? vStrWho : '端部挠度（正常使用）';

'''
s = s[:a] + new + s[b:]

# 结论：强度为准，挠度单独给
s = s.replace("""    /* ---- 分区结论 ---- */
    const verdicts = checks.map(c => c.verdict);
    const worstUtil = Math.max(...checks.map(c => c.ratio));
    const state = worstUtil <= 0.85 ? 'ok' : worstUtil <= 1.0 ? 'warn' : 'bad';""",
"""    /* ---- 分区结论 ---- */
    const ulsChk = checks.filter(c => c.uls);
    const slsChk = checks.filter(c => !c.uls);
    const uMax = ulsChk.reduce((a, c) => Math.max(a, c.ratio), 0);
    const dMax = slsChk.reduce((a, c) => Math.max(a, c.ratio), 0);
    const worstUtil = Math.max(uMax, dMax);
    const stateStrength = uMax <= 0.85 ? 'ok' : uMax <= 1.0 ? 'warn' : 'bad';
    const stateService = dMax <= 0.85 ? 'ok' : dMax <= 1.0 ? 'warn' : 'bad';
    const state = stateStrength;""")

s = s.replace("""      vmax, worstUtil, state,
      secs: { secCol, secBeam, secDiag, secLong },""",
"""      vmax, vStr, vDef, vGovern, worstUtil, uMax, dMax, state,
      stateStrength, stateService,
      secs: { secCol, secBeam, secDiag, secLong },""")

# 加 compare()
s = s.replace("""  return { defaults, build, run, bracketFrame, solveCase, checkMember };""",
r'''  /* ------------------------------------------------------------------
     方案对比：把常见的几种"加固方向"各算一遍，按能否达标排序
     ------------------------------------------------------------------ */
  const SCHEMES = [
    { id: 'A', name: '原方案：3 柱 + Φ89 挑梁 + ⌀12 上斜拉', over: {} },
    { id: 'B', name: '加柱：4 柱均分', over: { nCol: 4, tipX: [0.4, 2.6, 4.9, 7.2], baseY: [2.4, 0.4, 0.4, 0.4] } },
    { id: 'C', name: '加柱：5 柱均分', over: { nCol: 5, tipX: [0.4, 2.2, 4.0, 5.8, 7.5], baseY: [2.4, 0.4, 0.4, 0.4, 0.4] } },
    { id: 'D', name: '换厚管：挑梁 Φ140×5 + 柱 Φ140×5', over: { secBeam: 'Φ140x5.0', secCol: 'Φ140x5.0' } },
    { id: 'E', name: '换方管：□120×120×6', over: { secBeam: '□120x120x6', secCol: '□120x120x6' } },
    { id: 'F', name: '加大基础：1.4×1.4×0.9', over: { footB: 1.4, footH: 0.9 } },
    { id: 'G', name: '缩短挑出：网 8×3', over: { netW: 3.0 } },
    { id: 'H', name: '下撑代替上斜拉（刚性管 + 下撑）', over: { diagType: 'below', diagCable: false, secDiag: 'Φ48x2.5' } },
    { id: 'I', name: '下撑 + 加柱 + 厚管 + 大基础（组合拳）',
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
      try { R = run(P); } catch (e) { out.push({ id: sc.id, name: sc.name, err: String(e) }); continue; }
      const steel = R.geo.cols.length *
        (R.secs.secCol.A * P.h + R.secs.secBeam.A * (R.geo.cols[0].L)) * RHO_STEEL;
      const concrete = P.footB * P.footB * P.footH * R.geo.cols.length;
      out.push({
        id: sc.id, name: sc.name, state: R.state,
        vmax: R.vmax, vStr: R.vStr, vDef: R.vDef, vGovern: R.vGovern,
        beaufort: WIND.beaufort(R.vmax),
        uMax: R.uMax, dMax: R.dMax,
        steel: steel, concrete: concrete,
        cost: steel * 9 + concrete * 600,
        R,
      });
    }
    return out.sort((a, b) => (b.vmax || 0) - (a.vmax || 0));
  }

  return { defaults, build, run, bracketFrame, solveCase, checkMember, compare, SCHEMES };''')

io.open(p, 'w', encoding='utf-8').write(s)
print('ok')
''')
