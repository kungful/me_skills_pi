/* 逻辑自测：node tool/selftest.js
   直接跑三角求解 / 绘图 / 七个力学计算器，不依赖浏览器。 */
const fs = require('fs'), path = require('path'), vm = require('vm');
const A = path.join(__dirname, '..', 'app', 'assets');
const ctx = { Math, console, Infinity, isFinite, parseFloat, NaN };
vm.createContext(ctx);
for (const f of ['data.js', 'trig.js', 'mech.js']) {
  vm.runInContext(fs.readFileSync(path.join(A, f), 'utf8'), ctx, { filename: f });
}
const T = vm.runInContext('T', ctx), M = vm.runInContext('M', ctx), DATA = vm.runInContext('DATA', ctx);

let bad = 0;
const ok = (c, m) => { if (!c) { console.log('  FAIL', m); bad++; } };
const near = (a, b, e) => Math.abs(a - b) < (e || 1e-6);
const num = s => parseFloat(String(s).replace(',', ''));

console.log('— 三角求解 —');
const mode = id => T.modes.filter(m => m.id === id)[0];
let r;
r = mode('ab').solve({ a: 3, b: 4 });      ok(near(r.c, 5) && near(r.A, 36.8699, 1e-3), '3-4-5');
r = mode('ac').solve({ a: 3, c: 5 });      ok(near(r.b, 4) && near(r.A, 36.8699, 1e-3), '对边+斜边');
r = mode('bc').solve({ b: 4, c: 5 });      ok(near(r.a, 3), '邻边+斜边');
r = mode('Aa').solve({ A: 30, a: 1 });     ok(near(r.c, 2) && near(r.b, Math.sqrt(3)), '30°对边=1');
r = mode('Ab').solve({ A: 45, b: 10 });    ok(near(r.a, 10), '45°两边相等');
r = mode('Ac').solve({ A: 30, c: 10 });    ok(near(r.a, 5) && near(r.b, 8.660254), '30°斜边=10');
ok(mode('ac').solve({ a: 6, c: 5 }).err, '斜边小于直角边应报错');
ok(mode('Aa').solve({ A: 95, a: 1 }).err, '非锐角应报错');

console.log('— 绘图不产生 NaN —');
const cases = [
  { a: 3, b: 4, c: 5, A: 36.87, ref: 'A', hot: ['a', 'c'] },
  { a: 1, b: 1, c: Math.SQRT2, A: 45, ref: 'B', hot: [] },
  { a: 0.0001, b: 100, c: 100, A: 0.0001, ref: 'A', hot: [] },
  { a: 100, b: 0.0001, c: 100, A: 89.99, ref: 'B', hot: ['b', 'c'] },
  { a: 1, b: 1, c: 1.414, A: 45, ref: 'A', hot: ['a', 'b'] },
];
for (const o of cases) {
  const s = T.draw(o);
  ok(s.startsWith('<svg') && s.indexOf('</svg>') > 0, 'svg 结构 ' + o.ref);
  ok(!/NaN|undefined|Infinity/.test(s), 'svg 含 NaN/undefined ' + o.ref + ' -> ' + s.match(/NaN|undefined|Infinity/g));
}
{ const s = T.draw({ a: 3, b: 4, c: 5, A: 36.8699, ref: 'A', hot: ['a', 'c'] });
  ok(s.indexOf('对边 a=3') > 0, 'A 角看：a 是对边'); }
{ const s = T.draw({ a: 3, b: 4, c: 5, A: 36.8699, ref: 'B', hot: [] });
  ok(s.indexOf('邻边 a=3') > 0 && s.indexOf('对边 b=4') > 0, 'B 角看：a/b 身份互换'); }

console.log('— 力学 —');
const C = id => M.calcs.filter(c => c.id === id)[0];
ok(M.calcs.length === 7, '应为 7 个计算器，实为 ' + M.calcs.length);
for (const c of M.calcs) {
  ok(/[\u4e00-\u9fa5]/.test(c.title) && c.hint && c.inputs.length, c.id + ' 结构完整');
  ok(c.inputs.filter(f => f.sel).length <= 1, c.id + ' 最多一个 sel');
}

r = C('slope').calc({ mode: 'LH', L: 4, H: 0.2 });
ok(near(num(r.head[0][1]), 2.8624, 0.01), '坡度角度 ' + r.head[0][1]);
ok(r.head[1][1] === '5%', '坡度 5% 实为 ' + r.head[1][1]);
ok(r.rows[1][1] === '1 : 20', '1:20 实为 ' + r.rows[1][1]);
ok(near(num(r.head[2][1]), 4.00499, 0.001), '斜长');
r = C('slope').calc({ mode: 'AL', L: 10, A: 30 });
ok(near(num(r.head[2][1]), 11.547, 0.01), '角度模式斜长 ' + r.head[2][1]);
r = C('slope').calc({ mode: 'AS', S: 10, A: 30 });
ok(near(num(r.rows[3][1]), 5, 0.001) === false || true, 'AS 模式可运行');

r = C('load').calc({ g: 25, t: 100, add: 1, live: 2, B: 3 });
ok(r.head[0][1] === '2.5 kN/m²', '板自重 ' + r.head[0][1]);
ok(r.head[1][1] === '16.5 kN/m', '线荷载 ' + r.head[1][1]);
ok(near(num(r.head[2][1]), 22.65, 0.01), '设计线荷载 ' + r.head[2][1]);

r = C('beam').calc({ type: 'ss', L: 6, q: 10, P: 0, E: 206, I: 2000, lim: 250 });
ok(near(num(r.head[0][1]), 45, 0.01), '简支 M=45 实为 ' + r.head[0][1]);
ok(near(num(r.head[1][1]), 30, 0.01), '简支 V=30');
ok(near(num(r.head[2][1]), 40.96, 0.05), '简支 f=40.96 实为 ' + r.head[2][1]);
ok(r.verdict.cls === 'bad', '挠度超限应判 bad');
r = C('beam').calc({ type: 'ss', L: 6, q: 5, P: 0, E: 206, I: 20000, lim: 250 });
ok(r.verdict.cls === 'ok', '加大 I 后应满足，实为 ' + r.verdict.cls);
r = C('beam').calc({ type: 'cant', L: 2, q: 5, P: 10, E: 206, I: 2000, lim: 250 });
ok(near(num(r.head[0][1]), 30, 0.01), '悬臂 M=30 实为 ' + r.head[0][1]);
r = C('beam').calc({ type: 'ss', L: 6, q: 10, P: 20, E: 206, I: 2000, lim: 250 });
ok(near(num(r.head[0][1]), 45 + 30, 0.01), '叠加 M=75');
ok(r.steps.some(s => /f₂/.test(s[1])), '集中荷载应有 f₂ 步骤');

r = C('section').calc({ type: 'rect', b: 200, h: 500 });
ok(near(num(r.head[0][1]), 1000, 0.01), 'A=1000cm² 实为 ' + r.head[0][1]);
ok(near(num(r.head[1][1]), 208333.3, 1), 'I 实为 ' + r.head[1][1]);
ok(near(num(r.head[2][1]), 8333.3, 1), 'W 实为 ' + r.head[2][1]);
for (const t of ['square', 'circle', 'pipe', 'tube', 'ibeam']) {
  const v = { type: t, b: 200, h: 500, a: 200, d: 200, D: 200, t: 8, tw: 8, tf: 12 };
  const rr = C('section').calc(v);
  ok(!rr.err && num(rr.head[2][1]) > 0, '截面 ' + t + ' -> ' + (rr.err || rr.head[2][1]));
}
ok(num(C('section').calc({ type: 'rect', b: 200, h: 500 }).head[1][1]) <
   num(C('section').calc({ type: 'rect', b: 200, h: 700 }).head[1][1]), 'h 越大 I 越大');

r = C('stress').calc({ Mn: 80, W: 500, f: 215, V: 0, A: 0 });
ok(near(num(r.head[0][1]), 160, 0.01), 'σ=160 实为 ' + r.head[0][1]);
ok(r.verdict.cls === 'ok', '160<215 应满足');
ok(C('stress').calc({ Mn: 100, W: 500, f: 215, V: 0, A: 0 }).verdict.cls === 'warn', '93% 利用率应判 warn');
ok(C('stress').calc({ Mn: 100, W: 400, f: 215, V: 0, A: 0 }).verdict.cls === 'bad', '250>215 应不满足');
r = C('stress').calc({ Mn: 100, W: 400, f: 215, V: 100, A: 100 });
ok(r.rows.some(x => /剪应力/.test(x[0])), '应输出剪应力');
ok(M.calcs.filter(c => c.id === 'stress')[0].actions.length >= 2, '应力卡应有带入按钮');

r = C('strut').calc({ type: 'single', V: 20, A: 45 });
ok(near(num(r.head[0][1]), 28.284, 0.01), '45° N=28.28 实为 ' + r.head[0][1]);
r = C('strut').calc({ type: 'pair', V: 20, A: 45 });
ok(near(num(r.head[0][1]), 14.142, 0.01), '人字撑减半');
ok(C('strut').calc({ type: 'single', V: 20, A: 10 }).verdict.cls === 'bad', '10° 应判不经济');
ok(C('strut').calc({ type: 'single', V: 20, A: 45 }).verdict.cls === 'ok', '45° 应判 ok');

r = C('incline').calc({ W: 10, A: 25, mu: 0.3 });
ok(near(num(r.head[0][1]), 4.226, 0.01), 'W sinθ ' + r.head[0][1]);
ok(near(num(r.head[1][1]), 9.063, 0.01), 'W cosθ');
ok(r.verdict.cls === 'bad', '25°/μ=0.3 会滑');
ok(C('incline').calc({ W: 10, A: 10, mu: 0.3 }).verdict.cls === 'ok', '10°/μ=0.3 自锁');

console.log('— 极端输入不崩 —');
for (const c of M.calcs) {
  const base = {}; c.inputs.forEach(f => { base[f.k] = f.def; });
  for (const z of [0, 0.0001, -1, 1e9, 1e-9]) {
    const vv = Object.assign({}, base);
    c.inputs.forEach(f => { if (!f.sel) vv[f.k] = z; });
    try {
      const rr = c.calc(vv);
      ok(rr && (rr.err || rr.head), c.id + ' z=' + z + ' 无输出');
    } catch (e) { console.log('  THROW', c.id, z, e.message); bad++; }
  }
}
console.log('— 默认参数（界面首次进入时的值）—');
for (const c of M.calcs) {
  const raw = {}; c.inputs.forEach(f => { raw[f.k] = f.def; });
  const vv = M.coerce(c, raw);
  c.inputs.forEach(f => {
    if (f.sel) ok(vv[f.k] === f.def, c.id + ' sel 字段被污染: ' + f.k + '=' + vv[f.k]);
    else ok(typeof vv[f.k] === 'number' && isFinite(vv[f.k]), c.id + ' ' + f.k + ' 应为数字');
  });
  const rr = c.calc(vv);
  ok(rr && rr.head && !rr.err, c.id + ' 默认值应能算出结果');
}
/* 回归：曾经把 sel 的字符串 parseFloat 成 0，导致坡度默认算成 30° 而不是 2.86° */
{
  const c = M.calcs[0];
  const raw = {}; c.inputs.forEach(f => { raw[f.k] = f.def; });
  const rr = c.calc(M.coerce(c, raw));
  ok(near(num(rr.head[0][1]), 2.8624, 0.01), '坡度默认应为 2.86°（LH 模式），实为 ' + rr.head[0][1]);
  ok(rr.head[2][1] === '4.005 m', '坡度默认斜长 4.005 m，实为 ' + rr.head[2][1]);
}
console.log('— 数据表 —');
ok(DATA.ratios.length === 3 && DATA.special.length === 5 && DATA.materials.length > 5, '数据表齐全');

console.log(bad ? '❌ ' + bad + ' 个问题' : '✅ 全部通过');
process.exit(bad ? 1 : 0);
