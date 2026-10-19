/* 两条路线：
   A) 全靠主楼悬挑（地面零占用）——上斜撑锚在主楼墙上，锚点高度可变
   W) 贴墙立柱 + 悬挑（地面只有贴墙 0.5m 带）——柱脚受基础，上斜撑锚主楼
   硬约束：GB50017 受压构件 λ ≤ 150 */
const L = require('./plan_house_lib.js');
const S = L.S, RHO = 7850;
const X0 = 0.45, X1 = 9.45;

const BEAMS = ['Φ76x3.0','Φ89x3.0','Φ89x4.0','Φ114x4.0','Φ140x4.0','Φ140x5.0','Φ165x5.0',
               '□80x80x4','□100x100x4','□120x120x4','□150x150x5'];
const TIES  = ['Φ60x3.0','Φ76x3.0','Φ89x3.0','Φ89x4.0','Φ114x4.0','Φ140x4.0',
               '□60x60x3','□80x80x4','□100x100x4','□120x120x4'];
const get = n => S.PIPE_MAP[n] || S.SEC.round(76,3);
const mass = (sec, len) => sec.A * len * RHO;

const rows = [];
for (const mode of ['A', 'W'])
 for (const l of [4.0, 4.5, 5.0])
  for (const nn of [3, 4])
   for (const ZA of [4.4, 5.4, 6.3])
    for (const tb of BEAMS) for (const tc of TIES) {
      const cfg = { id:'X', n: nn, X0, X1, L: l, ZB: mode==='W' ? 3.0 : 3.05,
                    ZA, rigid: true, secBeam: tb, secTie: tc,
                    a: 0.35, nAnchor: 2, anchorCap: 60, over: {} };
      if (mode === 'W') { cfg.column = true; cfg.secCol = tb; cfg.hp = cfg.ZB; cfg.footB = 0.7; cfg.footH = 0.5; }
      let r; try { r = L.evaluate(cfg); } catch (e) { continue; }
      const sb = get(tb), st = get(tc), Ld = Math.hypot(l, ZA - cfg.ZB);
      const steel = nn*(mass(sb,l) + mass(st,Ld) + (mode==='W'? mass(sb,cfg.ZB):0)) + (X1-X0)*mass(sb,1.8);
      const conc = mode==='W' ? nn*(cfg.footB**2 * cfg.footH) : 0;
      const cost = steel*11 + conc*700 + nn*(mode==='W'?26+2:26)*18;
      rows.push({ mode, l, nn, ZA, tb, tc, u: r.u, who: r.who, vmax: r.vmax,
                  area: r.Area*nn, steel, conc, cost });
    }

const ok = rows.filter(r => r.u <= 0.95);
console.log(`扫描 ${rows.length} 组（含 λ≤150 限值），达标 ${ok.length} 组\n`);
for (const mode of ['A','W']) {
  const o = ok.filter(r => r.mode === mode).sort((a,b)=>a.cost-b.cost);
  console.log(`===== ${mode==='A' ? '路线A 全靠主楼悬挑（地面零占用）' : '路线W 贴墙立柱+悬挑（地面仅贴墙带）'} =====`);
  const seen = new Set(); let c = 0;
  for (const r of o) {
    const k = r.l+'|'+r.nn+'|'+r.ZA; if (seen.has(k)) continue; seen.add(k); c++;
    console.log(`  ${r.l.toFixed(1)}m×${r.nn}根 ${(r.area).toFixed(0)}m²  挑臂 ${r.tb.padEnd(11)} 斜撑 ${r.tc.padEnd(11)} 锚高 ${r.ZA}m`+
                ` | u=${r.u.toFixed(2)} 钢${r.steel.toFixed(0)}kg 砼${r.conc.toFixed(2)}m³ ≈¥${r.cost.toFixed(0)} 能扛${r.vmax.toFixed(0)}m/s [${r.who}]`);
    if (c >= 7) break;
  }
  console.log('');
}
