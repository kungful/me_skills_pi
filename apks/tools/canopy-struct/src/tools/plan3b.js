/* 三管方案精修：锚固、基础形式、柱位再分配、挑出长度 */
require('./_load').loadAssets(['solver.js', 'wind.js', 'model.js']);

function show(id, note, over) {
  const P = Object.assign(MODEL.defaults(), over);
  const R = MODEL.run(P);
  const steel = R.geo.cols.reduce((a, c) => a + R.secs.secCol.A * P.h + R.secs.secBeam.A * c.L, 0) * 7850
              + R.secs.secDiag.A * 3.7 * 3 * 7850;
  const conc = R.P.footB * R.P.footB * R.P.footH * R.geo.cols.length;
  console.log(
    (id + ' ' + note).padEnd(30) +
    (R.vmax.toFixed(1) + ' m/s').padStart(10) +
    (' ' + WIND.beaufort(R.vmax).replace(/ /g, '')).padEnd(10) +
    ('u=' + R.uMax.toFixed(2)).padStart(9) +
    ('钢' + steel.toFixed(0) + 'kg').padStart(10) +
    ('砼' + conc.toFixed(2) + 'm³').padStart(10) +
    ('¥' + (steel * 9 + conc * 600).toFixed(0)).padStart(8) + '  ' + (R.vGovern || '—'));
  console.log('     各柱: ' + R.geo.cols.map(c =>
    `${c.id} 悬臂${c.L.toFixed(2)} 分担${c.tw.toFixed(2)} 上拔${(Math.max(0, -R.perCol[R.geo.cols.indexOf(c)].cases.up.base.N) / 1000).toFixed(1)}kN 柱底M${(Math.abs(R.perCol[R.geo.cols.indexOf(c)].cases.up.base.M) / 1000).toFixed(1)}kN·m`).join(' | '));
}

const TUBE = { secCol: 'Φ219x6.0', secBeam: 'Φ219x6.0', secDiag: '□80x80x4', diagType: 'below', diagCable: false, r: 1.2, h: 2.2 };
const ANCH = { basePlateLever: 0.60, anchorCap: 60, anchorN: 2 };
// 按"各柱悬臂长度成反比"重新分配（短的担得多）
const X3 = { tipX: [0.4, 3.0, 6.6], baseY: [2.4, 0.4, 0.4] };

console.log('=== 逐个加码，看每一步涨多少 ===');
show('①原方案', 'Φ89+拉索', {});
show('②换 Φ219×6', '+刚性下撑 r1.2', Object.assign({}, TUBE, X3));
show('③+大基础', '1.6×1.6×1.0', Object.assign({}, TUBE, X3, { footB: 1.6, footH: 1.0 }));
show('④+好锚固', 'a=0.6 [60kN]×2', Object.assign({}, TUBE, X3, { footB: 1.6, footH: 1.0 }, ANCH));
show('⑤+柱位再分配', 't=[0.4,3.0,6.6]', Object.assign({}, TUBE, X3, { footB: 1.6, footH: 1.0 }, ANCH));

console.log('\n=== 再动几何 ===');
show('⑥挑出减到 3.0m', '网 8×3=24m²', Object.assign({}, TUBE, X3, ANCH, { footB: 1.5, footH: 1.0, netW: 3.0 }));
show('⑦挑出 3.0+柱脚外移0.8', '离墙 1.2m', Object.assign({}, TUBE, X3, ANCH, { footB: 1.5, footH: 1.0, netW: 3.0, baseY: [1.8, 1.2, 1.2] }));
show('⑧方管版 3.0m 挑出', '□200×200×6', Object.assign({}, TUBE, X3, ANCH,
  { secCol: '□200x200x6', secBeam: '□200x200x6', footB: 1.5, footH: 1.0, netW: 3.0 }));

console.log('\n=== 极端配置（看上限在哪） ===');
show('⑨全开', 'Φ219×6 + 1.8基础 + a0.8/80kN', Object.assign({}, TUBE, X3,
  { footB: 1.8, footH: 1.0, basePlateLever: 0.8, anchorCap: 80, anchorN: 4, netW: 3.0 }));
show('⑩全开+柱外移', '离墙1.2m', Object.assign({}, TUBE, X3,
  { footB: 1.5, footH: 1.0, basePlateLever: 0.8, anchorCap: 80, anchorN: 4, netW: 3.0, baseY: [1.8, 1.2, 1.2] }));
