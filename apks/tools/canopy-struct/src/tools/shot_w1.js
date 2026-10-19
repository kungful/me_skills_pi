const { spawn } = require('child_process'); const http=require('http'),path=require('path'),fs=require('fs');
const CHROME='C:/Program Files/Google/Chrome/Application/chrome.exe'; const PORT=9338;
const url='file:///'+path.resolve(__dirname,'..','assets','index.html').split(path.sep).join('/');
const get=p=>new Promise((res,rej)=>http.get({host:'127.0.0.1',port:PORT,path:p},r=>{let b='';r.on('data',d=>b+=d);r.on('end',()=>res(b));}).on('error',rej));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const c=spawn(CHROME,['--headless=new',`--remote-debugging-port=${PORT}`,'--no-sandbox','--allow-file-access-from-files','--no-first-run',`--user-data-dir=${path.join(require('os').tmpdir(),'cw'+Date.now())}`,'--window-size=420,880',url],{stdio:'ignore'});
 let pg=null; for(let i=0;i<60;i++){await sleep(250);try{pg=(JSON.parse(await get('/json/list'))||[]).find(t=>t.type==='page'&&t.webSocketDebuggerUrl);}catch(e){} if(pg)break;}
 const ws=new WebSocket(pg.webSocketDebuggerUrl); let id=0; const pend={};
 const send=(m,p)=>new Promise(r=>{const i=++id;pend[i]=r;ws.send(JSON.stringify({id:i,method:m,params:p}));});
 ws.onmessage=e=>{const m=JSON.parse(e.data); if(m.id&&pend[m.id]){pend[m.id](m.result);delete pend[m.id];}};
 await new Promise(r=>ws.onopen=r); await send('Runtime.enable'); await sleep(2400);
 const ev=async e=>{const r=await send('Runtime.evaluate',{expression:e,returnByValue:true});return r.result&&r.result.value!==undefined?r.result.value:JSON.stringify(r.exceptionDetails||r);};
 const clk=t=>ev(`Array.prototype.find.call(document.querySelectorAll('#tabs .tab'),function(x){return x.dataset.t==='${t}'}).click()`);
 const pid = process.argv[2] || 'W1';
 await clk('par'); await sleep(500);
 console.log('chip?', await ev(`!!document.querySelector('.pchip[data-p="${pid}"]')`));
 await ev(`document.querySelector('.pchip[data-p="${pid}"]').click()`); await sleep(800);
 await clk('s3'); await sleep(900);
 console.log('state', await ev(`JSON.stringify({layout:window.__ST.P.layout,area:+window.__ST.R.geo.area.toFixed(0),vmax:+window.__ST.R.vmax.toFixed(1)})`));
 const d = await ev('document.querySelector("#cv3").toDataURL("image/png")');
 if (typeof d==='string'&&d.startsWith('data:image')) fs.writeFileSync(path.resolve(__dirname,'..','截图','app-'+pid+'.png'),Buffer.from(d.split(',')[1],'base64'));
 ws.close(); c.kill(); process.exit(0);
})();
