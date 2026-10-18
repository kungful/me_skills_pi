/* 逐 tab 截图：node tools/shots.js [宽] [高] */
const { spawn } = require('child_process');
const http = require('http'), path = require('path'), fs = require('fs');
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const PORT = 9334;
const url = 'file:///' + path.resolve(__dirname, '..', 'assets', 'index.html').replace(/\\/g, '/');
const W = +(process.argv[2] || 400), H = +(process.argv[3] || 820);
const OUT = path.resolve(__dirname, '..', '截图');
if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });

const get = p => new Promise((res, rej) => http.get({ host: '127.0.0.1', port: PORT, path: p }, r => {
  let b = ''; r.on('data', d => b += d); r.on('end', () => res(b));
}).on('error', rej));
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--no-sandbox',
    '--allow-file-access-from-files', '--no-first-run', '--hide-scrollbars',
    `--user-data-dir=${path.join(require('os').tmpdir(), 'csshot' + Date.now())}`,
    `--window-size=${W},${H}`, url], { stdio: 'ignore' });
  let pg = null;
  for (let i = 0; i < 60; i++) {
    await sleep(250);
    try { pg = (JSON.parse(await get('/json/list')) || []).find(t => t.type === 'page' && t.webSocketDebuggerUrl); } catch (e) { }
    if (pg) break;
  }
  if (!pg) { console.log('chrome 起不来'); chrome.kill(); process.exit(1); }
  const ws = new WebSocket(pg.webSocketDebuggerUrl);
  let id = 0; const pend = {};
  const send = (m, p) => new Promise(r => { const i = ++id; pend[i] = r; ws.send(JSON.stringify({ id: i, method: m, params: p })); });
  ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend[m.id]) { pend[m.id](m.result); delete pend[m.id]; } };
  await new Promise(r => ws.onopen = r);
  await send('Page.enable'); await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 2, mobile: true });
  await sleep(2600);

  const tabs = [['s3', '3d'], ['s2', '2d'], ['par', 'par'], ['chk', 'chk'], ['cmp', 'cmp'], ['doc', 'doc']];
  for (const [t, nm] of tabs) {
    await send('Runtime.evaluate', {
      expression: `(function(){var b=Array.prototype.find.call(document.querySelectorAll('#tabs .tab'),function(x){return x.dataset.t==='${t}';});b.click();return 1})()`,
      returnByValue: true,
    });
    await sleep(t === 'cmp' ? 2600 : 700);
    const s = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(OUT, `app-${nm}.png`), Buffer.from(s.data, 'base64'));
    console.log('截图 app-' + nm + '.png');
  }
  // 顺便多截两张：加大管材后的 3D、收网
  await send('Runtime.evaluate', {
    expression: `(function(){var ST=window.__ST;ST.P.secCol='\u25a1150x150x5';ST.P.secBeam='\u25a1150x150x5';ST.P.nCol=5;
      ST.P.tipX=[0.4,2.2,4.0,5.8,7.5];ST.P.baseY=[2.4,0.4,0.4,0.4,0.4];ST.P.footB=1.4;ST.P.footH=1.0;
      var b=Array.prototype.find.call(document.querySelectorAll('#tabs .tab'),function(x){return x.dataset.t==='chk';});b.click();
      document.dispatchEvent(new Event('x'));return 1})()`, returnByValue: true,
  });
  await sleep(400);
  await send('Runtime.evaluate', { expression: `(function(){window.__ST.P.netW=4;location.reload();})()` });
  await sleep(200);
  ws.close(); chrome.kill(); process.exit(0);
})();
