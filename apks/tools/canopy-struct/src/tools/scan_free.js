/* 硬条件：地面零占用。全靠主楼悬挑 —— 按"最省钱"挑，不是按利用率挑 */
const L = require('./plan_house_lib.js');
const S = L.S;
const X0 = 0.45, X1 = 9.45, ZB = 3.05, ZA = 6.30, RHO = 7850;
const LS  = [3.2, 4.0, 4.5, 5.0];
const NS  = [3, 4, 5];
const TUBES = ['Φ48x2.5','Φ60x3.0','Φ76x3.0','Φ89x3.0','Φ89x4.0','Φ114x4.0',
               '□50x50x3','□60x60x3','□80x80x3','□80x80x4','□100x100x4'];
const CHK  = ['Φ42x2.5','Φ48x2.5','Φ60x3.0','Φ76x3.0','Φ89x3.0',
              '□40x40x3','□50x50x3','□60x60x3','□80x80x3'];
const get = n => S.PIPE_MAP[n] || S.SEC.round(76,3);

const rows = [];
for (const l of LS) for (const nn of NS) {
  const tw = (X1 - X0) / nn;
  for (const tb of TUBES) for (const tc of CHK) {
    const cfg = { id:'X', n: nn, X0, X1, L: l, ZB, ZA, rigid: true,
                  secBeam: tb, secTie: tc, a: 0.35, nAnchor: 2, anchorCap: 60, over: {} };
    let r; try { r = L.evaluate(cfg); } catch (e) { continue; }
    const sb = get(tb), st = get(tc);
    const Ld = Math.hypot(l, ZA - ZB);
    const mBeam = nn * l * sb.A * RHO;
    const mTie  = nn * Ld * st.A * RHO;
    const mEdge = (X1 - X0) * (sb.A + st.A) * 0.9 * RHO;   // 边梁 + 贴墙纵梁（估）
    const steel = mBeam + mTie + mEdge;
    const cost = steel * 11 + nn * 26 * 18;                 // 钢 11 元/kg + 锚栓/底板 26 个位
    rows.push({ l, nn, tb, tc, u: r.u, who: r.who, vmax: r.vmax, area: tw*l*nn, steel, cost });
  }
}
const ok = rows.filter(r => r.u <= 0.95);
console.log(`扫描 ${rows.length} 组，达标(设计风下 ≤0.95)：${ok.length} 组\n`);
ok.sort((a,b) => a.cost - b.cost);
console.log('=== 最省钱 TOP 12（同一挑出+根数只留最省的一行）===');
const seen = new Set();
let c = 0;
for (const r of ok) {
  const k = r.l + '|' + r.nn;
  if (seen.has(k)) continue; seen.add(k); c++;
  console.log(`  ${r.l.toFixed(1)}m × ${r.nn}根 = ${r.area.toFixed(0)}m²  挑臂 ${r.tb.padEnd(11)} 斜撑 ${r.tc.padEnd(11)}`+
              ` u=${r.u.toFixed(2)}  钢 ${r.steel.toFixed(0)}kg  ≈¥${r.cost.toFixed(0)}  能扛 ${r.vmax.toFixed(0)}m/s`);
  if (c >= 12) break;
}
console.log('\n=== 想要"能盖住车"(挑出≥4.5m)的三档 ===');
for (const l of [4.5, 5.0]) {
  const c2 = ok.filter(r => r.l === l).sort((a,b)=>a.cost-b.cost)[0];
  if (c2) console.log(`  ★ 挑出 ${l}m：${c2.nn} 根 ${c2.tb} + ${c2.tc}  ${c2.area.toFixed(0)}m²  钢 ${c2.steel.toFixed(0)}kg  ≈¥${c2.cost.toFixed(0)}  u=${c2.u.toFixed(2)}  能扛 ${c2.vmax.toFixed(0)}m/s`);
}
