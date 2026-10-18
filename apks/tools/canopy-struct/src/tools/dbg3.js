const { spawn } = require('child_process'); const http = require('http'), path = require('path');
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'; const PORT = 9335;
const url = 'file:///' + path.resolve(__dirname, '..', 'assets', 'index.html').split(path.sep).join('/');
const get = p => new Promise((res, rej) => http.get({ host: '127.0.0.1', port: PORT, path: p }, r => { let b = ''; r.on('data', d => b += d); r.on('end', () => res(b)); }).on('error', rej));
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const c = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--no-sandbox',
    '--allow-file-access-from-files', '--no-first-run',
    `--user-data-dir=${path.join(require('os').tmpdir(), 'csd' + Date.now())}`, '--window-size=420,860', url], { stdio: 'ignore' });
  let pg = null;
  for (let i = 0; i < 60; i++) { await sleep(250); try { pg = (JSON.parse(await get('/json/list')) || []).find(t => t.type === 'page' && t.webSocketDebuggerUrl); } catch (e) { } if (pg) break; }
  const ws = new WebSocket(pg.webSocketDebuggerUrl); let id = 0; const pend = {};
  const send = (m, p) => new Promise(r => { const i = ++id; pend[i] = r; ws.send(JSON.stringify({ id: i, method: m, params: p })); });
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.id && pend[m.id]) { pend[m.id](m.result); delete pend[m.id]; }
    else if (m.method === 'Runtime.exceptionThrown') console.log('EXC', m.params.exceptionDetails.text, (m.params.exceptionDetails.exception || {}).description);
    else if (m.method === 'Runtime.consoleAPICalled') console.log('[c]', m.params.args.map(a => a.value !== undefined ? a.value : a.description).join(' '));
  };
  await new Promise(r => ws.onopen = r); await send('Runtime.enable');
  await sleep(2600);
  const ev = async (e) => { const r = await send('Runtime.evaluate', { expression: e, returnByValue: true }); return r.result && r.result.value !== undefined ? r.result.value : JSON.stringify(r.exceptionDetails || r); };
  console.log('debug  :', await ev('JSON.stringify(V3.debug())'));
  console.log('投影   :', await ev('V3.probe()'));
  console.log('canvas :', await ev('(function(){var c=document.querySelector("#cv3");if(!c)return"no canvas";return c.width+"x"+c.height+" css "+c.clientWidth+"x"+c.clientHeight+" rect "+JSON.stringify(c.getBoundingClientRect())})()'));
  console.log('pixels :', await ev('(function(){var c=document.querySelector("#cv3");var g=c.getContext("webgl2");if(!g)return "no gl";var px=new Uint8Array(4);g.readPixels(Math.floor(c.width/2),Math.floor(c.height/2),1,1,g.RGBA,g.UNSIGNED_BYTE,px);return Array.from(px).join(",")})()'));
  console.log('bodies :', await ev('(function(){var o=[];document.querySelectorAll("#s3wrap,#tools3,#legend3").forEach(function(e){var r=e.getBoundingClientRect();o.push(e.id+" "+Math.round(r.left)+","+Math.round(r.top)+" "+Math.round(r.width)+"x"+Math.round(r.height))});return o.join(" | ")})()'));
  // 直接把 WebGL canvas 存成 PNG（headless 截图抓不到 WebGL，只能这样）
  const fs2 = require('fs');
  const shots = [['默认视角', null], ['俯视', 'V3.topView()'], ['正视', 'V3.frontView()'],
                 ['侧视', 'V3.endView()'], ['变形放大100', 'window.__ST.v3.defl=100;V3.build(window.__ST.R,{showNet:true,deflScale:100,caseKey:"up"})']];
  for (const [nm, code] of shots) {
    if (code) { await send('Runtime.evaluate', { expression: code }); await sleep(400); }
    const d = await ev('document.querySelector("#cv3").toDataURL("image/png")');
    if (typeof d === 'string' && d.startsWith('data:image')) {
      const f = path.resolve(__dirname, '..', '截图', 'gl-' + nm + '.png');
      fs2.writeFileSync(f, Buffer.from(d.split(',')[1], 'base64'));
      console.log('写入', 'gl-' + nm + '.png', fs2.statSync(f).size, 'B');
    } else console.log(nm, 'toDataURL 失败', String(d).slice(0, 60));
  }
  ws.close(); c.kill(); process.exit(0);
})();
