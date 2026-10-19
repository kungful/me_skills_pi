/* 三柱方案搜索：在"只有 3 根柱子"的约束下找最稳的配置 */
require('./_load').loadAssets(['solver.js', 'wind.js', 'model.js']);
const G = 9.81;

const SECS = ['Φ140x5.0', 'Φ165x5.0', 'Φ219x6.0', '□120x120x6', '□150x150x5', '□150x150x8',
              '□180x180x6', '□200x200x6', '□200x200x8'];
const DIAG = [
  { diagType: 'below', diagCable: false, secDiag: '□80x80x4', tag: '刚性下撑' },
  { diagType: 'above', diagCable: false, secDiag: '□80x80x4', tag: '刚性上斜撑' },
];
const FOOT = [0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0];
const RS = [0.8, 1.2, 1.6, 2.0];
const HS = [2.2, 2.4, 2.6];
const LEV = [0.4, 0.6, 0.8];
const ANC = [[35, 2], [60, 2], [60, 4], [80, 4]];

// 三根柱：两根靠长边墙、一根靠短边墙（拐角）
function pos3(netL, netW, gap, tipX) {
  return { nCol: 3, tipX: tipX || [gap, netL * 0.30, netL * 0.82], baseY: [Math.max(gap, netW - 1.6), gap, gap] };
}

const out = [];
let n = 0;
for (const sec of SECS)
  for (const dg of DIAG)
    for (const fb of FOOT)
      for (const r of RS)
        for (const hh of HS)
        for (const lev of LEV)
        for (const [ac, an] of ANC) {
          n++;
          const P = Object.assign(MODEL.defaults(), pos3(8, 4, 0.4), dg, {
            secCol: sec, secBeam: sec, footB: fb, footH: Math.max(0.5, Math.min(1.2, fb * 0.6)),
            r, h: hh, basePlateLever: lev, anchorCap: ac, anchorN: an,
          });
          let R;
          try { R = MODEL.run(P, { noBack: true }); } catch (e) { continue; }
          if (R.uMax > 1.6) continue;
          const steel = 3 * (R.secs.secCol.A * P.h + R.secs.secBeam.A * R.geo.cols[0].L) * 7850;
          const conc = fb * fb * P.footH * 3;
          out.push({ sec, dg: dg.tag, fb, r, h: hh, lev, ac, an, u: R.uMax, d: R.dMax,
                     gov: R.vGovern, steel, conc, cost: steel * 9 + conc * 600, R });
        }
console.log('扫描', n, '个组合，可行(≤1.6):', out.length);
const best = out.filter(o => o.u <= 1.0).sort((a, b) => a.cost - b.cost);
console.log('\n=== 能过关（利用率 ≤ 1.0）的三柱方案，按造价 ===');
best.slice(0, 12).forEach(o => console.log(
  `  ${o.sec.padEnd(12)} ${o.dg.padEnd(6)} 基础${o.fb}×${(o.fb*0.6).toFixed(2)} r=${o.r} h=${o.h} 锚栓${o.an}×[${o.ac}kN] a=${o.lev}` +
  `  u=${o.u.toFixed(2)} 钢${o.steel.toFixed(0)}kg 砼${o.conc.toFixed(2)}m³ ≈¥${o.cost.toFixed(0)}
         控制: ${o.gov}`));
console.log('\n=== 最接近但不达标的（看差多少） ===');
out.sort((a, b) => a.u - b.u).slice(0, 8).forEach(o => console.log(
  `  ${o.sec.padEnd(12)} ${o.dg.padEnd(6)} 基础${o.fb}m r=${o.r} h=${o.h} a=${o.lev} 锚栓${o.an}×[${o.ac}]  u=${o.u.toFixed(2)}  ${o.gov}`));
