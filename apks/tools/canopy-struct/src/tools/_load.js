/* 把 assets/*.js 里的 const 常量在 node 里挂到 global，供自测/调试用 */
const fs = require('fs'), path = require('path');
const dir = path.join(__dirname, '..', 'assets');
const MAP = { 'solver.js': 'SOLVER', 'wind.js': 'WIND', 'model.js': 'MODEL' };
function loadAssets(names) {
  for (const f of names) {
    const name = MAP[f];
    const src = fs.readFileSync(path.join(dir, f), 'utf8');
    const v = new Function('return (function(){' + src + '\n;return ' + name + ';})();')
      .call(global);
    global[name] = v;
  }
  return global;
}
module.exports = { loadAssets, dir };
