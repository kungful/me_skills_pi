/* 三柱（三根管子）方案的加固对比 —— 带反算风速 */
require('./_load').loadAssets(['solver.js', 'wind.js', 'model.js']);

const base = {};
const DECKS = [
  { id: '原方案', note: '3柱 Φ89 + ⌀12 拉索 + 0.8m 基础', over: {} },
  { id: '②加强管', note: 'Φ219×6 + 刚性下撑 r=1.2', over: {
      secCol: 'Φ219x6.0', secBeam: 'Φ219x6.0', secDiag: '□80x80x4',
      diagType: 'below', diagCable: false, r: 1.2 } },
  { id: '③+降标高', note: '②再把挑梁标高降到 2.2m', over: {
      secCol: 'Φ219x6.0', secBeam: 'Φ219x6.0', secDiag: '□80x80x4',
      diagType: 'below', diagCable: false, r: 1.2, h: 2.2 } },
  { id: '④+大基础', note: '③再把基础加到 1.6×1.6×1.0', over: {
      secCol: 'Φ219x6.0', secBeam: 'Φ219x6.0', secDiag: '□80x80x4',
      diagType: 'below', diagCable: false, r: 1.2, h: 2.2, footB: 1.6, footH: 1.0 } },
  { id: '⑤+柱脚外移', note: '④再把柱脚移到离墙 1.2m（挑出 2.8m）', over: {
      secCol: 'Φ219x6.0', secBeam: 'Φ219x6.0', secDiag: '□80x80x4',
      diagType: 'below', diagCable: false, r: 1.2, h: 2.2, footB: 1.6, footH: 1.0, wallGap: 1.2 } },
  { id: '⑥方管版', note: '□200×200×6 代替 Φ219×6', over: {
      secCol: '□200x200x6', secBeam: '□200x200x6', secDiag: '□80x80x4',
      diagType: 'below', diagCable: false, r: 1.2, h: 2.2, footB: 1.6, footH: 1.0 } },
  { id: '⑦省一点', note: '□150×150×8 + 大基础', over: {
      secCol: '□150x150x8', secBeam: '□150x150x8', secDiag: '□80x80x4',
      diagType: 'below', diagCable: false, r: 1.6, h: 2.2, footB: 1.8, footH: 1.0 } },
];

console.log('设计风 = 广州 50 年 w0=0.60 kN/m² → 31 m/s（11 级）\n');
console.log('方案                  能扛风      风级       强度利用率  挠度利用率  钢材   砼     估算     控制点');
for (const d of DECKS) {
  const P = Object.assign(MODEL.defaults(), d.over);
  const R = MODEL.run(P);
  const steel = R.geo.cols.length * (R.secs.secCol.A * P.h + R.secs.secBeam.A * R.geo.cols.reduce((a, c) => a + c.L, 0) / R.geo.cols.length + R.secs.secDiag.A * 3) * 7850;
  const conc = P.footB * P.footB * P.footH * R.geo.cols.length;
  const cost = steel * 9 + conc * 600;
  console.log(
    d.id.padEnd(9) +
    (R.vmax.toFixed(1) + ' m/s').padStart(11) +
    (' ' + WIND.beaufort(R.vmax)).padEnd(11) +
    (R.uMax.toFixed(2)).padStart(8) +
    (R.dMax.toFixed(2)).padStart(11) +
    (steel.toFixed(0) + 'kg').padStart(9) +
    (conc.toFixed(2) + 'm³').padStart(8) +
    ('¥' + cost.toFixed(0)).padStart(9) + '  ' +
    (R.vGovern || '—'));
}
console.log('\n各方案下三根柱的分担：');
for (const d of DECKS) {
  const P = Object.assign(MODEL.defaults(), d.over);
  const R = MODEL.run(P);
  console.log('  ' + d.id.padEnd(9) + R.geo.cols.map(c => `${c.id}:悬臂${c.L.toFixed(2)}m/分担${c.tw.toFixed(2)}m`).join('  ') +
    '   风吸上抬合计 ' + (R.W.qUp * R.geo.area).toFixed(1) + ' kN');
}
