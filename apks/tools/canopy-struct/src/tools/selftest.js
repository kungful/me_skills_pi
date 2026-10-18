/* 力学自测：用解析解校核刚度法求解器。node tools/selftest.js */
const path = require('path');
const fs = require('fs');
const dir = path.join(__dirname, '..', 'assets');
function load(f) {
  const src = fs.readFileSync(path.join(dir, f), 'utf8');
  const m = { exports: {} };
  new Function('module', 'exports', 'require', src)(m, m.exports, require);
  return m.exports;
}
const SOLVER = load('solver.js');
global.SOLVER = SOLVER;
// wind/model 用 const 声明，需要挂到全局
for (const f of ['wind.js', 'model.js']) {
  const src = fs.readFileSync(path.join(dir, f), 'utf8');
  new Function('SOLVER', src + `\n;this.${f === 'wind.js' ? 'WIND' : 'MODEL'}=${f === 'wind.js' ? 'WIND' : 'MODEL'};`).call(global, SOLVER);
}
const { WIND, MODEL } = global;

let fails = 0;
function ok(name, got, want, tol) {
  const rel = Math.abs(got - want) / Math.max(Math.abs(want), 1e-9);
  const pass = rel <= (tol || 0.01);
  if (!pass) fails++;
  console.log(`${pass ? '  ✓' : '  ✗'} ${name}: ${got.toPrecision(6)}  期望 ${want.toPrecision(6)}  (误差 ${(rel*100).toFixed(3)}%)`);
}

function okAbs(name, got, want, tol) {
  const pass = Math.abs(got - want) <= tol;
  if (!pass) fails++;
  console.log(`${pass ? '  ✓' : '  ✗'} ${name}: ${got.toPrecision(5)}  期望 ${want}±${tol}  (实测偏差 ${(got-want).toPrecision(3)})`);
}
const E = 2.06e11, A = 1.5e-3, I = 1e-6;

console.log('\n[1] 悬臂梁：端部集中力 P=5000N, L=2m');
{
  const m = { nodes: [{ x: 0, y: 0, fix: [1,1,1] }, { x: 2, y: 0 }],
    elems: [{ i: 0, j: 1, E, A, I, idx: 0 }], loads: [{ node: 1, fy: -5000 }] };
  const r = SOLVER.analyze(m);
  const tip = r.U[4];
  ok('端部挠度 PL³/3EI', Math.abs(tip), 5000*8/(3*E*I), 0.001);
  ok('固端弯矩 PL', Math.abs(r.elems[0].Mend[0]), 5000*2, 0.001);
  ok('支座反力 y', r.R[0].fy, 5000, 0.001);
}

console.log('\n[2] 简支梁 + 均布荷载 w=1000N/m(向下), L=3m');
{
  const m = { nodes: [{ x: 0, y: 0, fix: [1,1] }, { x: 1.5, y: 0 }, { x: 3, y: 0, fix: [0,1] }],
    elems: [{ i: 0, j: 1, E, A, I, idx: 0 }, { i: 1, j: 2, E, A, I, idx: 1 }],
    loads: [], udl: [{ elem: 0, w: -1000 }, { elem: 1, w: -1000 }] };
  const r = SOLVER.analyze(m);
  ok('跨中弯矩 wL²/8', Math.abs(r.elems[0].Mmax.M), 1000*9/8, 0.002);
  ok('跨中挠度 5wL⁴/384EI', Math.abs(r.U[4]), 5*1000*81/(384*E*I), 0.01);
}

console.log('\n[3] 两端固定梁 + 均布 w=1000N/m, L=3m');
{
  const m = { nodes: [{ x: 0, y: 0, fix: [1,1,1] }, { x: 3, y: 0, fix: [1,1,1] }],
    elems: [{ i: 0, j: 1, E, A, I, idx: 0 }], loads: [], udl: [{ elem: 0, w: -1000 }] };
  const r = SOLVER.analyze(m);
  ok('固端弯矩 wL²/12', Math.abs(r.elems[0].Mend[0]), 1000*9/12, 0.002);
  ok('固端弯矩 wL²/12 (右)', Math.abs(r.elems[0].Mend[1]), 1000*9/12, 0.002);
  ok('跨中弯矩 wL²/24', Math.abs(r.elems[0].pts[12].M), 1000*9/24, 0.003);
}

console.log('\n[4] 铰接桁架：三杆对称，验证轴力');
{
  // 三角桁架，顶点受竖向力，检查轴力符号与静力平衡
  const m = { nodes: [{x:0,y:0,fix:[1,1,1]},{x:2,y:0,fix:[1,1,1]},{x:1,y:1,fix:[0,0,1]}],
    elems: [{i:0,j:2,E,A,I,truss:true,idx:0},{i:1,j:2,E,A,I,truss:true,idx:1}],
    loads: [{node:2,fy:-1000}] };
  const r = SOLVER.analyze(m);
  const n = -r.elems[0]._fl[0];
  ok('左斜杆压力 N=-P√2/2', n, -1000*Math.SQRT2/2, 0.01);
  okAbs('顶点竖向反力≈0（罚函数残差 < 2N）', r.R[2].fy, 0, 2);
  ok('两铰支座竖向合计 = P', r.R[0].fy + r.R[1].fy, 1000, 0.01);
  ok('左支座竖向', r.R[0].fy, 500, 0.01);
}

console.log('\n[5] 斜撑悬臂（三角托架）：下撑点距梁 1m，悬臂 2m，端部 P=4000N');
{
  const m = { nodes: [{x:0,y:0,fix:[1,1,1]},{x:0,y:2},{x:2,y:2},{x:0,y:1}],
    elems: [{i:0,j:3,E,A,I,idx:0},{i:3,j:1,E,A,I,idx:1},{i:1,j:2,E,A,I,idx:3},
            {i:3,j:2,E,A,I,truss:true,idx:2}],
    loads: [{node:2,fy:-4000}] };
  const r = SOLVER.analyze(m);
  const c = 2.2360679;
  const strut = r.elems.find(e => e.idx === 2);
  const Ns = -strut._fl[0];
  // 刚接节点的斜撑是超静定的：内力 > 静定桁架解 P·c/r，但同量级、且必受压
  ok('下撑受压（N<0）', Ns < 0 ? 1 : 0, 1, 0);
  console.log(`     下撑轴力 ${(Math.abs(Ns)/1000).toFixed(2)} kN（静定桁架解 ${(4000*c/1000).toFixed(2)} kN，刚接实际偏大）`);
  ok('柱底弯矩 P·L = 8000', Math.abs(r.R[0].mz), 8000, 0.02);
  ok('竖向反力合计 = P', r.R[0].fy, 4000, 0.02);
}

console.log('\n[6] 上斜拉（拉索，仅受拉）：风吸反向 → 应自动退出工作');
{
  const m = { nodes: [{x:0,y:0,fix:[1,1,1]},{x:0,y:2},{x:2,y:2},{x:0,y:3}],
    elems: [{i:0,j:1,E,A,I,idx:0},{i:1,j:2,E,A,I,idx:1},
            {i:3,j:2,E,A,I,truss:true,tensionOnly:true,idx:2}],
    loads: [{node:2,fy:4000}] };      // 向上抬
  const r = SOLVER.analyze(m);
  ok('斜拉索已退出（挑梁独扛 PL）', Math.abs(r.R[0].mz), 8000, 0.02);
}

console.log('\n[7] 风荷载');
{
  const W = WIND.calc({ w0: 0.60, rough: 'C', z: 3.0, porosity: 0.5, cManual: false });
  ok('μz(C类, z≤5m 取 5m 值)', W.muz, 0.65, 1e-6);
  ok('βgz(C类, z≤5m 取 5m 值)', W.bgz, 1.95, 1e-6);
  ok('w_k = βgz·μz·w0', W.wk, 1.95*0.65*0.6, 1e-9);
  ok('风速 v=√(1600w0)', W.v, Math.sqrt(1600*0.6), 1e-9);
  console.log('    风级:', W.beaufort, ' Cn吸=', W.cUp.toFixed(3), ' q吸=', W.qUp.toFixed(3), 'kN/m²');
}

console.log('\n[8] 整体模型：默认 L 形墙 3 柱方案');
{
  const R = MODEL.run({});
  console.log('    网面积', R.geo.area.toFixed(2), 'm²   ωk=', R.W.wk.toFixed(3), 'kN/m²  q吸=', R.W.qUp.toFixed(3));
  console.log('    各柱分担宽度:', R.geo.cols.map(c => `${c.id}=${c.tw.toFixed(2)}m/${c.L.toFixed(2)}m悬臂`).join('  '));
  console.log('    风吸总上抬 ', (R.totalUplift/1000).toFixed(2), 'kN   总配重', (R.totalBallast/1000).toFixed(2), 'kN');
  console.log('    最不利:', R.worst.col, R.worst.name, ' 利用率', R.worst.u.toFixed(3));
  console.log('    反算可扛风速 v_max =', R.vmax.toFixed(1), 'm/s  (', WIND.beaufort(R.vmax), ')');
  console.log('    结论:', R.state);
  console.log('    校核条目数:', R.checks.length, ' 不通过:', R.checks.filter(c=>c.verdict==='bad').length);
  const bad = R.checks.filter(c => c.verdict === 'bad').slice(0, 8);
  bad.forEach(c => console.log(`      ✗ [${c.group}] ${c.name} = ${c.value.toFixed(2)} ${c.unit} (限值 ${c.limit.toFixed(2)}) 比 ${c.ratio.toFixed(2)}`));
  if (!isFinite(R.vmax) || isNaN(R.vmax)) { fails++; console.log('  ✗ vmax 非法'); }
  if (R.vmax > 0 && R.vmax < 5) { fails++; console.log('  ✗ vmax 太小，模型可能有问题'); }
}

console.log('\n[9] 参数敏感性：加柱 / 加配重 / 收网');
{
  const base = MODEL.run({});
  const five = MODEL.run({ nCol: 5, tipX: [0.4, 2.2, 4.0, 5.8, 7.4], baseY: [2.4, 0.4, 0.4, 0.4, 0.4] });
  const stow = MODEL.run({ netDeployed: false });
  const big = MODEL.run({ footB: 1.4, footH: 0.8 });
  console.log('    3柱 v_max', base.vmax.toFixed(1), ' 5柱 v_max', five.vmax.toFixed(1),
              ' 收网 v_max', stow.vmax.toFixed(1), ' 大基础 v_max', big.vmax.toFixed(1));
}

console.log('\n' + (fails === 0 ? '全部通过 ✅' : `有 ${fails} 项不通过 ❌`));
process.exit(fails === 0 ? 0 : 1);
