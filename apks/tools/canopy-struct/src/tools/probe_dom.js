const { spawn } = require('child_process'); const http = require('http'), path = require('path');
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'; const PORT = 9336;
const url = 'file:///' + path.resolve(__dirname, '..', 'assets', 'index.html').split(path.sep).join('/');
const get = p => new Promise((res, rej) => http.get({ host: '127.0.0.1', port: PORT, path: p }, r => { let b = ''; r.on('data', d => b += d); r.on('end', () => res(b)); }).on('error', rej));
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const c = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, '--no-sandbox', '--allow-file-access-from-files', '--no-first-run', `--user-data-dir=${path.join(require('os').tmpdir(), 'csp' + Date.now())}`, '--window-size=420,860', url], { stdio: 'ignore' });
  let pg = null; for (let i = 0; i < 60; i++) { await sleep(250); try { pg = (JSON.parse(await get('/json/list')) || []).find(t => t.type === 'page' && t.webSocketDebuggerUrl); } catch (e) { } if (pg) break; }
  const ws = new WebSocket(pg.webSocketDebuggerUrl); let id = 0; const pend = {};
  const send = (m, p) => new Promise(r => { const i = ++id; pend[i] = r; ws.send(JSON.stringify({ id: i, method: m, params: p })); });
  ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend[m.id]) { pend[m.id](m.result); delete pend[m.id]; } else if (m.method === 'Runtime.consoleAPICalled') console.log('[c]', m.params.args.map(a => a.value !== undefined ? a.value : a.description).join(' ')); };
  await new Promise(r => ws.onopen = r); await send('Runtime.enable'); await sleep(2200);
  const ev = async e => { const r = await send('Runtime.evaluate', { expression: e, returnByValue: true }); return r.result && r.result.value !== undefined ? r.result.value : JSON.stringify(r.exceptionDetails || r); };
  const R = `(function(){function d(s){var e=document.querySelector(s);if(!e)return s+':\u65e0';var r=e.getBoundingClientRect();return s+' '+Math.round(r.width)+'x'+Math.round(r.height)+' @'+Math.round(r.left)+','+Math.round(r.top)}return [d('#view'),d('.pane.on'),d('#s3wrap'),d('#cv3')].join(' | ')})()`;
  console.log('第1次三维:', await ev(R));
  console.log('同步连点后:', await ev(`(function(){function clk(t){Array.prototype.find.call(document.querySelectorAll('#tabs .tab'),function(x){return x.dataset.t===t}).click()}clk('s3');clk('s2');clk('s3');clk('chk');clk('s3');
    function d(s){var e=document.querySelector(s);if(!e)return s+':无';var r=e.getBoundingClientRect();return s+' '+Math.round(r.width)+'x'+Math.round(r.height)}return [d('#view'),d('.pane.on'),d('#s3wrap'),d('#cv3')].join(' | ')})()`));
  await sleep(600);
  console.log('600ms 后:', await ev(R));
  ws.close(); c.kill(); process.exit(0);
})();
