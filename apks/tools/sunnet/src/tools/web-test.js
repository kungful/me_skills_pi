// 用真 Chrome 跑一遍 App 的「散装」页（同一个 index.html / app.js / pack.js）
// 原生桥 window.SunNet 用假实现补上：paste / pick / copy / open 都返回固定内容。
// 跑法： node tools/web-test.js        （需要 C:/Users/hua/pwqa/node_modules 里的 puppeteer-core）
const path = require('path');
const fs = require('fs');
const puppeteer = require('C:/Users/hua/pwqa/node_modules/puppeteer-core');

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const root = path.join(__dirname, '..');
const shotDir = path.join(root, '截图');
const EXAMPLE = fs.readFileSync(path.join(root, '示例-阳台自动浇花.json'), 'utf8');
const CLIP = { text: EXAMPLE, pick: EXAMPLE };

let fail = 0;
const ok = (name, cond, extra) => {
  if (cond) console.log('  ok   ' + name);
  else { fail++; console.log('  FAIL ' + name + (extra ? '  → ' + extra : '')); }
};

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--allow-file-access-from-files', '--no-sandbox', '--window-size=430,900',
           '--force-device-scale-factor=2'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 430, height: 900, deviceScaleFactor: 2 });
  page.on('pageerror', (e) => { fail++; console.log('  FAIL 页面 JS 报错: ' + e.message); });
  page.on('console', (m) => { if (m.type() === 'error') console.log('  (console) ' + m.text()); });

  // 把示例文本送进页面，供假桥返回
  await page.evaluateOnNewDocument((ex) => { window.__CLIP = { text: ex, pick: ex }; }, EXAMPLE);
  // 假原生桥
  await page.evaluateOnNewDocument(() => {
    window.__calls = [];
    window.SunNet = {
      invoke(reqId, op, argsJson) {
        let args = {};
        try { args = JSON.parse(argsJson || '{}'); } catch (e) {}
        window.__calls.push({ op, args });
        let ok = 1, payload = {};
        if (op === 'paste') payload = { ok: true, text: window.__CLIP.text };
        else if (op === 'pick') payload = window.__CLIP.pick ? { ok: true, name: 'x.json', text: window.__CLIP.pick } : null;
        else if (op === 'copy') payload = { ok: true };
        else if (op === 'open') payload = { ok: true };
        else if (op === 'status') payload = { mode: 'none' };
        else if (op === 'get') payload = { ok: true, ver: '1.0.0', state: 'idle' };
        else payload = { ok: true };
        if (payload === null) { ok = 0; payload = '已取消'; }
        setTimeout(() => window.__apiResult(reqId, ok, JSON.stringify(payload)), 0);
      },
    };
  });

  const url = 'file:///' + path.join(root, 'assets/index.html').replace(/\\/g, '/');
  await page.goto(url, { waitUntil: 'load' });
  await new Promise((r) => setTimeout(r, 500));

  const $ = (sel) => page.$eval(sel, (e) => e.textContent.trim());
  const count = (sel) => page.$$eval(sel, (a) => a.length);
  const tapJs = (sel) => page.$eval(sel, (e) => e.click());
  const lastCall = (op) => page.evaluate((o) => {
    const a = window.__calls.filter((c) => c.op === o);
    return a.length ? a[a.length - 1] : null;
  }, op);
  const clearCalls = () => page.evaluate(() => { window.__calls.length = 0; });

  console.log('\n[1] 打开 散装 页（内置方案）');
  await tapJs('[data-tab="diy"]');
  await new Promise((r) => setTimeout(r, 300));
  ok('页签切到散装', await page.$eval('section[data-tab="diy"]', (e) => e.classList.contains('act')));
  ok('清单 17 行', (await count('#bomList .bomrow')) === 17, '实际 ' + (await count('#bomList .bomrow')));
  ok('每行都有电压徽标', (await count('#bomList .bv')) === 17, '实际 ' + (await count('#bomList .bv')));
  ok('每行都有 4 个按钮', (await count('#bomList .bbar button')) === 17 * 4, '实际 ' + (await count('#bomList .bbar button')));
  ok('电压分层表 4 行（原 bug：空白）', (await count('#voltTable .wirerow')) === 4, '实际 ' + (await count('#voltTable .wirerow')));
  ok('接线表 14 行（原 bug：全空）', (await count('#wireTable .wirerow')) === 14, '实际 ' + (await count('#wireTable .wirerow')));
  ok('接线表有 GPIO 徽标', (await count('#wireTable .gpio')) > 10);
  ok('步骤 13 步', (await count('#stepList .step')) === 13, '实际 ' + (await count('#stepList .step')));
  ok('注意 7 条', (await count('#noteList .note')) === 7, '实际 ' + (await count('#noteList .note')));
  ok('对比表 6 行(含表头)', (await count('#cmpTable .tr')) === 6, '实际 ' + (await count('#cmpTable .tr')));
  ok('对比表有绿色高亮', (await count('#cmpTable .ok')) >= 3);
  ok('电源走线图非空', (await $('#powerText')).length > 100);
  ok('引脚表非空', (await $('#pinPatch')).indexOf('MOTOR_IN1') >= 0);
  ok('方案 B/C/D 卡片 = 3', (await count('#altCards .card')) === 3, '实际 ' + (await count('#altCards .card')));
  ok('方案 B 条目有名字（原 bug：undefined）', (await $('#altCards .bomrow .bn')).indexOf('undefined') < 0,
     await $('#altCards .bomrow .bn'));
  ok('合计 = 220', (await $('#bomTotal')).indexOf('¥220') >= 0, await $('#bomTotal'));

  await page.screenshot({ path: path.join(shotDir, 'web-01-diy.png'), fullPage: false });

  console.log('\n[2] 勾选一行 → 合计/计数变化 + 进度存本地');
  await page.$eval('#bomList .bomrow', (e) => e.click());
  await new Promise((r) => setTimeout(r, 200));
  ok('计数变 1/17', (await $('#bomCount')).indexOf('1/17') >= 0, await $('#bomCount'));
  ok('已买金额 > 0', (await $('#bomTotal')).indexOf('已买 ¥0') < 0, await $('#bomTotal'));
  ok('勾选存进 localStorage', await page.evaluate(() => !!localStorage.getItem('sunnet.got.sunnet')));
  await page.$eval('#btnClearBom', (e) => e.click());
  await new Promise((r) => setTimeout(r, 200));
  ok('清空勾选生效', (await $('#bomCount')).indexOf('0/17') >= 0);

  console.log('\n[3] 只买最小集');
  await page.$eval('#btnSkipBom', (e) => e.click());
  await new Promise((r) => setTimeout(r, 200));
  ok('最小集 = 14/17', (await $('#bomCount')).indexOf('14/17') >= 0, await $('#bomCount'));
  await page.$eval('#btnClearBom', (e) => e.click());
  await new Promise((r) => setTimeout(r, 200));

  console.log('\n[4] 导入别的产品（从剪贴板）');
  await page.$eval('#btnPackOpen', (e) => e.click());
  await new Promise((r) => setTimeout(r, 200));
  ok('抽屉打开了', await page.$eval('#packDrawer', (e) => e.classList.contains('on')));
  await page.$eval('#btnPackPaste', (e) => e.click());
  await new Promise((r) => setTimeout(r, 400));
  ok('剪贴板内容进了文本框', (await page.$eval('#packIn', (e) => e.value.length)) > 5000);
  await page.$eval('#btnPackDo', (e) => e.click());
  await new Promise((r) => setTimeout(r, 500));
  const msg = await $('#packErr');
  ok('导入成功提示', msg.indexOf('导入成功') >= 0, msg);
  ok('标题换成浇花方案', (await $('#bomTitle')).indexOf('散装采购清单') >= 0, await $('#bomTitle'));
  ok('条目换成 12 行', (await count('#bomList .bomrow')) === 12, '实际 ' + (await count('#bomList .bomrow')));
  ok('电压表换 4 行', (await count('#voltTable .wirerow')) === 4);
  ok('接线表换 8 行', (await count('#wireTable .wirerow')) === 8, '实际 ' + (await count('#wireTable .wirerow')));
  ok('步骤换 10 步', (await count('#stepList .step')) === 10, '实际 ' + (await count('#stepList .step')));
  ok('注意换 6 条', (await count('#noteList .note')) === 6, '实际 ' + (await count('#noteList .note')));
  ok('额外卡片 1 张', (await count('#extraCards .card')) === 1);
  ok('meta 显示 id=watering', (await $('#packMeta')).indexOf('id=watering') >= 0, await $('#packMeta'));
  ok('元信息标为「导入的」', (await $('#packMeta')).indexOf('导入的') >= 0);
  ok('该方案价格合计 ≈ ¥179', (await $('#bomTotal')).indexOf('¥179') >= 0, await $('#bomTotal'));
  ok('勾选进度分开了（浇花 = 0/x）', (await $('#bomCount')).indexOf('0/12') >= 0, await $('#bomCount'));
  await page.screenshot({ path: path.join(shotDir, 'web-02-imported.png'), fullPage: false });

  console.log('\n[5] 导入后刷新页面：数据要留下来');
  await page.reload({ waitUntil: 'load' });
  await new Promise((r) => setTimeout(r, 400));
  await tapJs('[data-tab="diy"]');
  await new Promise((r) => setTimeout(r, 300));
  ok('重开还是浇花方案', (await $('#packMeta')).indexOf('浇花') >= 0, await $('#packMeta'));
  ok('清单还是 12 行', (await count('#bomList .bomrow')) === 12);

  console.log('\n[6] 选文件导入（第二条路）');
  await page.evaluate(() => { localStorage.removeItem('sunnet.pack.current'); });
  await page.reload({ waitUntil: 'load' });
  await new Promise((r) => setTimeout(r, 400));
  await tapJs('[data-tab="diy"]');
  await new Promise((r) => setTimeout(r, 300));
  ok('回到内置 17 行', (await count('#bomList .bomrow')) === 17);
  await page.$eval('#btnPackOpen', (e) => e.click());
  await page.$eval('#btnPackFile', (e) => e.click());
  await new Promise((r) => setTimeout(r, 400));
  ok('文件内容读进文本框', (await page.$eval('#packIn', (e) => e.value.length)) > 5000);
  ok('提示读到文件名', (await $('#packErr')).indexOf('x.json') >= 0, await $('#packErr'));
  await page.$eval('#btnPackDo', (e) => e.click());
  await new Promise((r) => setTimeout(r, 400));
  ok('导入生效', (await count('#bomList .bomrow')) === 12);

  console.log('\n[7] 坏数据要拦住，且不能弄坏当前方案');
  await page.$eval('#packIn', (e) => { e.value = '{"format":"sunnet.pack","ver":1,"groups":[]}'; });
  await page.$eval('#btnPackDo', (e) => e.click());
  await new Promise((r) => setTimeout(r, 300));
  ok('报错信息是中文', (await $('#packErr')).indexOf('导入失败') >= 0, await $('#packErr'));
  ok('页面仍是 12 行（没被清掉）', (await count('#bomList .bomrow')) === 12);
  await page.$eval('#packIn', (e) => { e.value = '随便写的废话，不是 JSON'; });
  await page.$eval('#btnPackDo', (e) => e.click());
  await new Promise((r) => setTimeout(r, 300));
  ok('非 JSON 也被拦住', (await $('#packErr')).indexOf('没找到 JSON') >= 0, await $('#packErr'));
  ok('页面仍是 12 行', (await count('#bomList .bomrow')) === 12);
  await page.screenshot({ path: path.join(shotDir, 'web-03-error.png'), fullPage: false });

  console.log('\n[8] 恢复内置');
  await page.$eval('#btnPackReset', (e) => e.click());
  await new Promise((r) => setTimeout(r, 400));
  ok('回到 17 行', (await count('#bomList .bomrow')) === 17, '实际 ' + (await count('#bomList .bomrow')));
  ok('meta 标回内置', (await $('#packMeta')).indexOf('内置') >= 0);
  ok('文本框清空', (await page.$eval('#packIn', (e) => e.value)) === '');

  console.log('\n[9] 复制 / 跳店（走原生桥）');
  await clearCalls();
  await page.$eval('#bomList button.kw', (e) => e.click());
  await new Promise((r) => setTimeout(r, 200));
  const cp = await lastCall('copy');
  ok('复制关键词调了 copy', !!cp && cp.args.text.length > 2, JSON.stringify(cp));
  await clearCalls();
  await page.$eval('#bomList button.tb', (e) => e.click());
  await new Promise((r) => setTimeout(r, 200));
  const o = await lastCall('open');
  ok('淘宝按钮调了 open', !!o);
  ok('候选链接 3 条（深链→网页）', o.args.urls.length === 3 && o.args.urls[0].indexOf('taobao://') === 0 &&
     o.args.urls[2].indexOf('https://') === 0, JSON.stringify(o.args.urls));
  await clearCalls();
  await page.$eval('#bomList button.pdd', (e) => e.click());
  await new Promise((r) => setTimeout(r, 150));
  ok('拼多多深链', (await lastCall('open')).args.urls[0].indexOf('pinduoduo://') === 0);
  await clearCalls();
  await page.$eval('#bomList button.ali', (e) => e.click());
  await new Promise((r) => setTimeout(r, 150));
  ok('1688 深链', (await lastCall('open')).args.urls[0].indexOf('openapp://') === 0);
  await clearCalls();
  await page.$eval('#btnCopyBom', (e) => e.click());
  await new Promise((r) => setTimeout(r, 200));
  ok('复制清单按钮有内容', ((await lastCall('copy')).args.text || '').length > 500);
  await clearCalls();
  await page.$eval('#btnPackSpec', (e) => e.click());
  await new Promise((r) => setTimeout(r, 200));
  ok('复制格式说明（发给 AI）内容够长', (await page.evaluate(() => {
    const t = window.__calls.filter((c) => c.op === 'copy').pop();
    return !!t && t.args.text.indexOf('sunnet.pack') >= 0 && t.args.text.length > 500;
  })) === true);

  console.log('\n[10] XSS：恶意名字不能被当 HTML 执行');
  await page.$eval('#packIn', (e) => {
    e.value = JSON.stringify({
      format: 'sunnet.pack', ver: 1,
      meta: { id: 'x', title: '<img src=x onerror="window.__pwned=1">' },
      groups: [{ id: 'A', title: 'T', kind: 'check', items: [{ id: 'a', name: '<script>window.__pwned=1<\/script>', kw: 'k' }] }],
    });
  });
  await page.$eval('#btnPackDo', (e) => e.click());
  await new Promise((r) => setTimeout(r, 400));
  ok('导入成功（标签当文字）', (await $('#packErr')).indexOf('导入成功') >= 0, await $('#packErr'));
  ok('没有注入出 <img>', (await count('#bomList img')) === 0 && (await count('#bomList script')) === 0);
  ok('window.__pwned 没被设置', await page.evaluate(() => typeof window.__pwned === 'undefined'));

  await page.screenshot({ path: path.join(shotDir, 'web-04-xss.png'), fullPage: false });
  await browser.close();
  console.log('\n' + (fail ? '✘ ' + fail + ' 项失败' : '✔ 全部通过'));
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error('跑挂了：', e); process.exit(2); });
