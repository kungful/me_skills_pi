const fs=require('fs'),path=require('path');
global.window={};
const dir='app/assets/www/data';
const files=fs.readdirSync(dir).sort();
let errs=[], totalL=0, totalQ=0;
for(const f of files){ eval(fs.readFileSync(path.join(dir,f),'utf8')); }
const mods=window.COSMOS.modules;
const ids=new Set();
mods.forEach(m=>{
  if(!m.id||!m.name||!m.icon||!m.hue||!m.tag||!m.blurb) errs.push(`模块字段缺失: ${m.id}`);
  if(!m.lessons||!m.lessons.length) errs.push(`模块无课程: ${m.id}`);
  (m.lessons||[]).forEach(l=>{
    totalL++;
    if(ids.has(l.id)) errs.push(`重复课程id: ${l.id}`); ids.add(l.id);
    ['title','essence','remember'].forEach(k=>{ if(!l[k]) errs.push(`${l.id} 缺 ${k}`); });
    if(!l.steps||l.steps.length<2) errs.push(`${l.id} steps 太少`);
    if(!l.quiz||l.quiz.length<2) errs.push(`${l.id} quiz 少于2题`);
    (l.quiz||[]).forEach((q,i)=>{
      totalQ++;
      if(!q.q||!q.opts||q.opts.length<2) errs.push(`${l.id} 第${i+1}题结构错误`);
      if(typeof q.a!=='number'||q.a<0||q.a>=q.opts.length) errs.push(`${l.id} 第${i+1}题答案越界`);
      if(!q.why) errs.push(`${l.id} 第${i+1}题缺解析`);
    });
  });
});
console.log('模块数:',mods.length);
mods.forEach(m=>console.log('  ',m.icon,m.name.padEnd(6),m.lessons.length,'课'));
console.log('课程总数:',totalL,' 题目总数:',totalQ);
console.log(errs.length? '❌ 问题:\n'+errs.join('\n') : '✅ 全部校验通过');
