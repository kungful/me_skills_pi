// 方案包格式自测（node tools/pack-test.js）
// 在 Node 里跑 bom.js + pack.js，不依赖浏览器和真机。
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const root = path.join(__dirname, '..');
const store = {};
const ctx = {
  console,
  localStorage: {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: (k) => { delete store[k]; },
  },
};
ctx.window = ctx;
ctx.globalThis = ctx;
vm.createContext(ctx);

for (const f of ['assets/bom.js', 'assets/pack.js']) {
  const p = path.join(root, f);
  vm.runInContext(fs.readFileSync(p, 'utf8'), ctx, { filename: p });
}
const ev = (code) => vm.runInContext(code, ctx);

let fail = 0;
function ok(name, cond, extra) {
  if (cond) { console.log('  ok   ' + name); }
  else { fail++; console.log('  FAIL ' + name + (extra ? '  → ' + extra : '')); }
}
function eq(name, got, want) {
  ok(name + ' = ' + JSON.stringify(want), JSON.stringify(got) === JSON.stringify(want), 'got ' + JSON.stringify(got));
}
function throws(name, code, needle) {
  try { ev(code); fail++; console.log('  FAIL ' + name + ' → 没报错（本该报错）'); }
  catch (e) { ok(name + ' → ' + e.message.slice(0, 60), String(e.message).indexOf(needle) >= 0, 'got: ' + e.message); }
}

console.log('\n[1] 内置方案包（bom.js → pack.js 归一化）');
eq('groups 数量', ev('buildDefaultPack().groups.length'), 4);
eq('清单条目(方案A)', ev('buildDefaultPack().groups[0].items.length'), 17);
eq('方案B/D 条目读得到 name', ev('buildDefaultPack().groups[3].items[0].name'),
   ev('BOM_D[0][0]'));
eq('方案A 全部有 volt', ev('buildDefaultPack().groups[0].items.filter(i=>i.volt).length'), 17);
eq('电压分层行数', ev('buildDefaultPack().volt.rows.length'), 4);
eq('接线行数', ev('buildDefaultPack().wiring.length'), 14);
eq('接线有 mod/gpio', ev('buildDefaultPack().wiring[0].mod + "|" + buildDefaultPack().wiring[0].gpio'),
   ev('WIRING[0][1] + "|" + WIRING[0][2]'));
eq('步骤数', ev('buildDefaultPack().steps.length'), 13);
eq('注意条数', ev('buildDefaultPack().notes.length'), 7);
eq('对比表 3 列', ev('buildDefaultPack().compare.head.length'), 3);
eq('power 非空', ev('buildDefaultPack().power.length > 100'), true);
eq('pinPatch 非空', ev('buildDefaultPack().pinPatch.indexOf("MOTOR_IN1") >= 0'), true);
eq('skip 列表', ev('buildDefaultPack().groups[0].skip'), ev('BOM_MIN_SKIP'));
eq('kind=check 只有第一组', ev('buildDefaultPack().groups.filter(g=>g.kind==="check").length'), 1);

console.log('\n[2] 导出 → 再导入（round-trip）');
eq('round-trip 不丢组数',
   ev('normalizePack(JSON.parse(packJson(packExportable.call(null)||{}))).groups.length').constructor.name === 'Number',
   true);
eq('round-trip 条目名一致',
   ev('(function(){const p=buildDefaultPack();packSave(p);const t=JSON.stringify(packExportable());' +
      'const q=normalizePack(t);return q.groups[0].items[0].name===p.groups[0].items[0].name;})()'), true);
eq('round-trip 价格还是数字',
   ev('(function(){packSave(buildDefaultPack());const q=normalizePack(JSON.stringify(packExportable()));' +
      'return typeof q.groups[0].items[0].price;})()'), 'number');

console.log('\n[3] 容错：AI 常见的输出毛病');
eq('```json 围栏能剥掉',
   ev('parsePackText("```json\\n{\\"format\\":\\"sunnet.pack\\",\\"ver\\":1,\\"groups\\":[{\\"items\\":[{\\"name\\":\\"a\\"}]}]}\\n```").groups.length'), 1);
eq('前后有废话也行',
   ev('parsePackText("好的，这是方案：\\n{\\"groups\\":[{\\"items\\":[{\\"name\\":\\"a\\"}]}]}\\n希望有帮助！").groups[0].items[0].name'), 'a');
eq('尾逗号能修',
   ev('parsePackText("{\\"groups\\":[{\\"items\\":[{\\"name\\":\\"a\\"},]},]}").groups[0].items.length'), 1);
eq('中文引号/逗号能修',
   ev('parsePackText("{\\u201cgroups\\u201d:[{\\u201citems\\u201d:[{\\u201cname\\u201d:\\u201ca\\u201d}]}]}").groups[0].items[0].name'), 'a');
eq('数组简写条目',
   ev('normalizePack({groups:[{items:[["电机驱动","DRV8871 模块",1,32,"12V"]]}]}).groups[0].items[0].kw'), 'DRV8871 模块');
eq('数组简写接线',
   ev('normalizePack({groups:[{items:[{name:"a"}]}],wiring:[["U3 IN1","DRV8871","GPIO4","3.3V","PWM"]]}).wiring[0].note'), 'PWM');
eq('没写 id 自动补且唯一',
   ev('normalizePack({groups:[{items:[{name:"a"},{name:"b"}]}]}).groups[0].items.map(i=>i.id)'), ['g0-1', 'g0-2']);
eq('只给 name 也能过',
   ev('(function(){const p=normalizePack({groups:[{items:[{name:"光敏模块"}]}]});const it=p.groups[0].items[0];' +
      'return [it.qty,it.price,it.kw,it.volt,it.why].join("|");})()'), '1|0|||');
eq('qty 写 "2 个" 也能拿 2', ev('normalizePack({groups:[{items:[{name:"a",qty:"2 个"}]}]}).groups[0].items[0].qty'), 2);
eq('XSS 被转义', ev('richText("<img src=x onerror=alert(1)>")'), '&lt;img src=x onerror=alert(1)&gt;');
eq('白名单标签保留', ev('richText("供电 <b>5V</b> 别接 <code>12V</code>")'), '供电 <b>5V</b> 别接 <code>12V</code>');

console.log('\n[4] 报错信息（要能看懂）');
throws('顶层不是对象', 'normalizePack([1,2])', '顶层必须是一个 JSON 对象');
throws('format 写错', 'normalizePack({format:"my.pack",groups:[{items:[{name:"a"}]}]})', 'format 必须是');
throws('ver 太新', 'normalizePack({ver:99,groups:[{items:[{name:"a"}]}]})', '比本 App 支持的');
throws('没有 groups', 'normalizePack({meta:{title:"x"}})', '缺少 groups');
throws('groups 是空数组', 'normalizePack({groups:[]})', '缺少 groups');
throws('items 空', 'normalizePack({groups:[{title:"x",items:[]}]})', 'items 为空');
throws('条目没名字', 'normalizePack({groups:[{items:[{qty:2}]}]})', '缺少 name');
throws('JSON 语法错', 'parsePackText("{groups:[}")', 'JSON 语法错误');
throws('不是 JSON', 'parsePackText("你好")', '没找到 JSON 对象');
throws('volt.rows 不是对象', 'normalizePack({groups:[{items:[{name:"a"}]}],volt:{rows:[5]}})', 'volt.rows[0] 不是对象');

console.log('\n[5] 导入示例：另一个产品（阳台自动浇花）');
const exPath = path.join(root, '示例-阳台自动浇花.json');
if (fs.existsSync(exPath)) {
  ctx.__example = fs.readFileSync(exPath, 'utf8');
  eq('示例能导入', ev('normalizePack(__example).meta.title.length > 0'), true);
  eq('示例 条目数', ev('normalizePack(__example).groups.reduce((a,g)=>a+g.items.length,0)'), ev('(function(){const p=normalizePack(__example);return p.groups.reduce((a,g)=>a+g.items.length,0);})()'));
  eq('示例 wiring/steps', ev('[normalizePack(__example).wiring.length, normalizePack(__example).steps.length].join("|")'),
     ev('[normalizePack(__example).wiring.length, normalizePack(__example).steps.length].join("|")'));
  ok('示例导入后 UI 会用到的手段都有', ev('(function(){const p=normalizePack(__example);' +
     'return !!(p.groups.length && p.volt.rows.length && p.wiring.length && p.steps.length && p.notes.length && p.pinPatch && p.compare.rows.length);})()'));
  eq('示例 title', ev('normalizePack(__example).meta.title'), '阳台自动浇花系统 · 散装方案');
} else {
  console.log('  (跳过：没有 ' + exPath + ')');
}

console.log('\n' + (fail ? '✘ ' + fail + ' 项失败' : '✔ 全部通过'));
process.exit(fail ? 1 : 0);
