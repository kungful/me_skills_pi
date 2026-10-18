/* 调试台：node tools/dbg.js '{"nCol":5}' */
require('./_load').loadAssets(['solver.js', 'wind.js', 'model.js']);
const R = MODEL.run(process.argv[2] ? JSON.parse(process.argv[2]) : {});
console.log('状态', R.state, ' 最不利利用率', R.worstUtil.toFixed(3), ' v_max', R.vmax.toFixed(2), 'm/s');
console.log('最不利:', R.worst.col, R.worst.name, R.worst.u.toFixed(3));
console.log('风: wk=', R.W.wk.toFixed(4), 'qUp=', R.W.qUp.toFixed(4), 'qDown=', R.W.qDown.toFixed(4), 'qDrag=', R.W.qDrag.toFixed(4));
console.log('几何:', R.geo.cols.map(c => `${c.id} x=${c.tip.x} y=${c.base.y} L=${c.L.toFixed(2)} tw=${c.tw.toFixed(2)}`).join(' | '));
console.log('上抬合计', (R.totalUplift / 1000).toFixed(2), 'kN,  配重合计', (R.totalBallast / 1000).toFixed(2), 'kN');
R.foot.forEach(f => console.log(`  基础 ${f.col.id}: 配重${(f.ballast/1000).toFixed(1)}kN 拔${(f.uplift/1000).toFixed(1)}kN K拔=${f.kUp.toFixed(2)} K倾=${f.kOver.toFixed(2)} p=${(f.pMax/1000).toFixed(0)}kPa 锚栓${(f.Tbolt/1000).toFixed(1)}kN`));
console.log('\n最不利 12 条校核:');
R.checks.slice().sort((a, b) => b.ratio - a.ratio).slice(0, 12)
  .forEach(c => console.log(`  [${c.verdict}] ${c.group} ${c.name} = ${(+c.value).toFixed(2)} ${c.unit} (限 ${(+c.limit).toFixed(2)})  比 ${c.ratio.toFixed(2)}`));
console.log('\n提示:'); R.warn.forEach(w => console.log('  ·', w));
