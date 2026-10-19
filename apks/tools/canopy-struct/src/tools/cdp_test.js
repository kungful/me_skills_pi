/* 用 Chrome DevTools Protocol 跑 e2e（headless 下比 --dump-dom 可靠）
   node tools/cdp_test.js [页面相对路径]                                        */
const { spawn } = require('child_process');
const http = require('http');
const path = require('path');
const fs = require('fs');

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const PORT = 9333;
const page = process.argv[2] || 'assets/_e2e.html';
const url = 'file:///' + path.resolve(__dirname, '..', page).replace(/\\/g, '/');

function get(p) {
  return new Promise((res, rej) => {
    http.get({ host: '127.0.0.1', port: PORT, path: p }, r => {
      let b = ''; r.on('data', d => b += d); r.on('end', () => res(b));
    }).on('error', rej);
  });
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const prof = path.join(require('os').tmpdir(), 'cscdp' + Date.now());
  const args = ['--headless=new', `--remote-debugging-port=${PORT}`, '--no-sandbox',
    '--allow-file-access-from-files', '--disable-extensions', '--no-first-run',
    `--user-data-dir=${prof}`, '--window-size=900,1000', url];
  const chrome = spawn(CHROME, args, { stdio: 'ignore' });
  let list = null;
  for (let i = 0; i < 60; i++) {
    await sleep(300);
    try {
      const j = JSON.parse(await get('/json/list'));
      const pg = j.find(t => t.type === 'page' && t.webSocketDebuggerUrl);
      if (pg) { list = pg; break; }
    } catch (e) { }
  }
  if (!list) { console.log('启动 Chrome 失败'); chrome.kill(); process.exit(1); }

  const ws = new WebSocket(list.webSocketDebuggerUrl);
  let id = 0; const pending = {}; const logs = [];
  const send = (method, params) => new Promise(res => { const i = ++id; pending[i] = res; ws.send(JSON.stringify({ id: i, method, params })); });
  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending[m.id]) { pending[m.id](m.result); delete pending[m.id]; }
    else if (m.method === 'Runtime.consoleAPICalled') {
      logs.push('[console.' + m.params.type + '] ' + m.params.args.map(a => a.value !== undefined ? a.value : a.description).join(' '));
    } else if (m.method === 'Runtime.exceptionThrown') {
      const d = m.params.exceptionDetails;
      logs.push('[exception] ' + d.text + ' ' + (d.exception && d.exception.description ? d.exception.description.split('\n').slice(0, 3).join(' | ') : ''));
    }
  };
  await new Promise(r => ws.onopen = r);
  await send('Runtime.enable');
  await send('Page.enable');
  await sleep(2500);

  const expr = `
    new Promise(function(res){
      setTimeout(async function(){
        var ST=window.__ST, errs=[], log=[];
        var sleep=function(ms){return new Promise(function(r){setTimeout(r,ms)})};
        // 离屏容器：不要把测试用的 canvas 塞进 body（body 是 flex 列，会把主视图挤没）
        var host=document.getElementById('testcv');
        if(!host){host=document.createElement('div');host.id='testcv';
          host.style.cssText='position:fixed;left:-99999px;top:0;width:760px;height:760px';
          document.body.appendChild(host);}
        window.tcv=function(w,h){var c=document.createElement('canvas');c.width=w;c.height=h;
          c.style.width=w+'px';host.appendChild(c);return c;};
        function T(n,f){ try{ var r=f(); log.push('OK   '+n+(r===undefined?'':'  '+r)); }
                         catch(e){ log.push('FAIL '+n+': '+e.message); errs.push(n+': '+e.message); } }
        try{
          T('注：本次为浏览器内检查', function(){ return location.href.split('/').pop(); });
          T('model.run', function(){ if(!ST||!ST.R) throw new Error('no R'); return 'uMax='+ST.R.uMax.toFixed(3); });
          T('R 数值健全', function(){ var R=ST.R;
            if(!(R.uMax>0)) throw new Error('uMax');
            if(!isFinite(R.vmax)) throw new Error('vmax');
            if(!(R.geo.area>10)) throw new Error('area='+R.geo.area);
            if(R.checks.length<30) throw new Error('checks='+R.checks.length);
            return 'v_max='+R.vmax.toFixed(2)+' 控制='+R.vGovern; });
          T('3D WebGL 可用', function(){ if(!V3.isOk()) throw new Error('未初始化: '+V3.whyNot());
            var c=document.querySelector('#cv3'); if(!c) throw new Error('没有 canvas');
            if(c.clientWidth<10) throw new Error('canvas 尺寸 0');
            return c.clientWidth+'x'+c.clientHeight; });
          T('3D 建模', function(){ V3.build(ST.R, {showNet:true,deflScale:0,caseKey:'up'}); });
          T('3D 变形放大100', function(){ V3.build(ST.R, {showNet:true,deflScale:100,caseKey:'up'}); });
          T('3D 视角', function(){ V3.topView(); V3.frontView(); V3.endView(); V3.resetView(); });
          T('2D 平面图', function(){ var c=tcv(640,420); V2.plan(c, ST.R, {}); });
          T('2D 立面(三工况)', function(){ var c=tcv(640,320);
            ['up','down','wind'].forEach(function(k){ V2.elev(c, ST.R, 1, k, {hpx:300}); }); });
          T('2D 传力路径', function(){ var c=tcv(640,340); V2.path(c, ST.R, {}); });
          T('参数面板', function(){ var h=UI.paramsHTML(MODEL.defaults()); if(h.length<800) throw new Error('short'); return h.length+'B'; });
          T('校核表', function(){ var h=UI.checksHTML(ST.R); if(h.length<800) throw new Error('short'); return ST.R.checks.length+'条'; });
          T('结论', function(){ var h=UI.verdictHTML(ST.R); if(h.length<200) throw new Error('short'); return h.replace(/<[^>]+>/g,'').slice(0,90); });
          T('方案对比', function(){ var r=MODEL.compare({}); return r.length+'方案 · 最好 '+(r[0].vmax||0).toFixed(1)+' m/s'; });
          T('自动找方案', function(){ var a=MODEL.autofix({}); return a.length+'个可行'; });
          T('三维页来回切换后 canvas 还在', function(){
            function clk(t){Array.prototype.find.call(document.querySelectorAll('#tabs .tab'),function(x){return x.dataset.t===t;}).click();}
            clk('s3'); clk('s2'); clk('s3'); clk('chk'); clk('s3');
            var c=document.querySelector('#cv3');
            if(!c) throw new Error('canvas 丢了');
            if(c.clientWidth<10||c.clientHeight<10) throw new Error('canvas 尺寸 0');
            return c.clientWidth+'x'+c.clientHeight;
          });
          ['s3','s2','par','chk','cmp','doc'].forEach(function(t){
            T('tab '+t, function(){
              var b=Array.prototype.find.call(document.querySelectorAll('#tabs .tab'),function(x){return x.dataset.t===t;});
              b.click(); var v=document.querySelector('#view');
              if(!v.innerHTML||v.innerHTML.length<60) throw new Error('空白');
              return v.innerHTML.length+'B'; });
          });
          T('滑杆→重算', function(){
            var b=Array.prototype.find.call(document.querySelectorAll('#tabs .tab'),function(x){return x.dataset.t==='par';}); b.click();
            var s=document.querySelector('input[data-k="netW"]'); s.value='3'; s.dispatchEvent(new Event('input',{bubbles:true}));
          });
          T('柱位滑杆', function(){ var s=document.querySelector('input[data-tx="1"]');
            s.value='2.5'; s.dispatchEvent(new Event('input',{bubbles:true})); });
          T('固化档位：套用 P3', function(){
            var b=Array.prototype.find.call(document.querySelectorAll('#tabs .tab'),function(x){return x.dataset.t==='par';}); b.click();
            var chip=document.querySelector('.pchip[data-p=\"H1\"]'); if(!chip) throw new Error('没有档位按钮');
            chip.click();
            return 'P3 套用后 v_max='+ST.R.vmax.toFixed(1)+' m/s, u='+ST.R.uMax.toFixed(2);
          });
          T('固化档位：P5', function(){
            var chip=document.querySelector('.pchip[data-p=\"H4\"]'); if(!chip) throw new Error('no chip');
            chip.click();
            if(chip.classList.contains('on')===false) throw new Error('未高亮');
            return 'P5 v_max='+ST.R.vmax.toFixed(1)+' m/s, 悬臂='+ST.R.geo.cols.map(function(c){return c.L.toFixed(1)}).join('/');
          });
          await sleep(1200);
          T('固化档位：对比页表格', function(){
            window.__presets=null;
            var b=Array.prototype.find.call(document.querySelectorAll('#tabs .tab'),function(x){return x.dataset.t==='cmp';}); b.click();
            var rows=document.querySelectorAll('tr.prow'); if(rows.length<5) throw new Error('档位行 '+rows.length);
            return rows.length+' 行';
          });
          T('固化档位：点表格行', function(){
            var r=document.querySelector('tr.prow[data-p=\"H3\"]'); if(!r) throw new Error('no row'); r.click();
            return '点 P1 后 v_max='+ST.R.vmax.toFixed(1);
          });
          T('换管截面', function(){
            var bt=Array.prototype.find.call(document.querySelectorAll('#tabs .tab'),function(x){return x.dataset.t==='par';}); bt.click();
            var s=document.querySelector('select[data-k="secBeam"]');
            s.value='□150x150x5'; s.dispatchEvent(new Event('input',{bubbles:true})); });
        }catch(e){ errs.push('外层异常 '+e.message+' | '+(e.stack||'').split('\\n')[1]); }
        res(log.join('\\n')+'\\n---- 页面内错误 ----\\n'+(errs.join('\\n')||'(无)')+'\\n---- 结论 ----\\n'+(errs.length?('FAIL '+errs.length):'ALL PASS'));
      }, 1200);
    })`;
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  console.log(r.result && r.result.value !== undefined ? r.result.value : JSON.stringify(r));
  if (logs.length) console.log('\n---- 浏览器日志 ----\n' + logs.slice(-25).join('\n'));

  // 截图
  try {
    const shot = await send('Page.captureScreenshot', { format: 'png' });
    if (shot && shot.data) {
      const out = path.resolve(__dirname, '..', '截图');
      if (!fs.existsSync(out)) fs.mkdirSync(out, { recursive: true });
      fs.writeFileSync(path.join(out, 'e2e-3d.png'), Buffer.from(shot.data, 'base64'));
      console.log('\n截图已存 截图/e2e-3d.png');
    }
  } catch (e) { }

  ws.close(); chrome.kill();
  process.exit(0);
})();
