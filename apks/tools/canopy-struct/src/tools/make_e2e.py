#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 assets/index.html 复制成 tools/e2e.html，并在后面挂一个同步自测脚本。"""
import io, os
here = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(here)
idx = io.open(os.path.join(root, 'assets', 'index.html'), encoding='utf-8').read()

TEST = r'''
<script>
function mkEl(id){const c=document.createElement('canvas');c.id=id;c.width=640;c.height=420;
  c.style.width='640px';document.body.appendChild(c);return c;}
(function(){
  var errs=[], log=[];
  window.onerror=function(m,src,l,c,err){errs.push('ERR '+m+' @'+l+':'+c+'
   '+(err&&err.stack?err.stack.split('
').slice(0,4).join('
   '):src));};
  window.addEventListener('unhandledrejection',function(e){errs.push('REJ '+e.reason);});
  function T(name,fn){ try{ var r=fn(); log.push('OK   '+name+(r===undefined?'':'  '+r)); }
                       catch(e){ log.push('FAIL '+name+': '+e.message); errs.push(name+': '+e.message); } }
  setTimeout(function(){
    var ST=window.__ST;
    T('model.run', function(){ if(!ST||!ST.R) throw new Error('no R'); return 'uMax='+ST.R.uMax.toFixed(3); });
    T('R 数值健全', function(){ var R=ST.R;
      if(!(R.uMax>0)) throw new Error('uMax');
      if(!isFinite(R.vmax)) throw new Error('vmax');
      if(Math.abs(R.geo.area-32)>0.01) throw new Error('area='+R.geo.area);
      return 'v_max='+R.vmax.toFixed(2)+' 控制='+R.vGovern; });
    T('平面图', function(){ V2.plan(document.querySelector('#cvP')||mkEl('cvP'), ST.R, {}); });
    T('立面 up', function(){ V2.elev(document.querySelector('#cvE')||mkEl('cvE'), ST.R, 1, 'up', {}); });
    T('立面 down', function(){ V2.elev(document.querySelector('#cvE')||mkEl('cvE'), ST.R, 1, 'down', {}); });
    T('立面 wind', function(){ V2.elev(document.querySelector('#cvE')||mkEl('cvE'), ST.R, 1, 'wind', {}); });
    T('传力路径图', function(){ V2.path(document.querySelector('#cvF')||mkEl('cvF'), ST.R, {}); });
    T('3D 初始化 (WebGL)', function(){
      var h=document.createElement('div'); h.style.width='600px'; h.style.height='380px';
      document.body.appendChild(h);
      var ok=V3.init(h);
      if(!ok) throw new Error('WebGLRenderer 建不起来');
      return 'canvas '+(h.querySelector('canvas')?h.querySelector('canvas').width+'x'+h.querySelector('canvas').height:'?');
    });
    T('3D 建模', function(){ V3.build(ST.R, {showNet:true,deflScale:0,caseKey:'up'}); });
    T('3D 视角切换', function(){ V3.topView(); V3.frontView(); V3.endView(); V3.resetView(); });
    T('3D 变形放大', function(){ V3.build(ST.R, {showNet:true,deflScale:100,caseKey:'up'}); });
    T('参数面板 HTML', function(){ var h=UI.paramsHTML(MODEL.defaults()); if(h.length<800) throw new Error('short'); return h.length+' 字节'; });
    T('结论 HTML', function(){ var h=UI.verdictHTML(ST.R); if(h.length<200) throw new Error('short'); });
    T('校核表 HTML', function(){ var h=UI.checksHTML(ST.R); if(h.length<800) throw new Error('short'); return ST.R.checks.length+' 条'; });
    T('方案对比', function(){ var r=MODEL.compare({}); if(r.length<5) throw new Error('few');
      return r.length+' 方案，最好 '+(r[0].vmax||0).toFixed(1)+' m/s'; });
    T('自动找方案', function(){ var a=MODEL.autofix({}); return a.length+' 个可行方案'; });
    T('说明书 HTML', function(){ if(UI.docHTML(ST.P).length<800) throw new Error('short'); });
    var tabs=['s3','s2','par','chk','cmp','doc'];
    tabs.forEach(function(t){ T('切换 tab '+t, function(){
      var btn=Array.prototype.find.call(document.querySelectorAll('#tabs .tab'),function(b){return b.dataset.t===t;});
      if(!btn) throw new Error('no tab');
      btn.click();
      var v=document.querySelector('#view');
      if(!v.innerHTML || v.innerHTML.length<60) throw new Error('空白面板 '+v.innerHTML.length);
      return v.innerHTML.length+' 字节';
    }); });
    T('拖滑杆（挑出）', function(){
      var btn=Array.prototype.find.call(document.querySelectorAll('#tabs .tab'),function(b){return b.dataset.t==='par';}); btn.click();
      var s=document.querySelector('input[data-k="netW"]'); if(!s) throw new Error('no slider');
      s.value='3'; s.dispatchEvent(new Event('input',{bubbles:true}));
    });
    T('柱位滑杆', function(){
      var s=document.querySelector('input[data-tx="1"]'); if(!s) throw new Error('no col slider');
      s.value='2.5'; s.dispatchEvent(new Event('input',{bubbles:true}));
    });
    T('换管截面', function(){
      var s=document.querySelector('select[data-k="secBeam"]'); if(!s) throw new Error('no sel');
      s.value='□150x150x5'; s.dispatchEvent(new Event('input',{bubbles:true}));
    });
    T('校核表已更新', function(){
      var btn=Array.prototype.find.call(document.querySelectorAll('#tabs .tab'),function(b){return b.dataset.t==='chk';}); btn.click();
      if(document.querySelector('#view').innerHTML.indexOf('校核条目')<0) throw new Error('no checks');
    });
    T('报告生成', function(){
      var btn=Array.prototype.find.call(document.querySelectorAll('#tabs .tab'),function(b){return b.dataset.t==='doc';}); btn.click();
      var d=document.querySelector('#doSave'); if(!d) throw new Error('no button');
    });
    var out=document.createElement('pre'); out.id='RESULT';
    out.textContent = log.join('\n') + '\n---- ERRORS ----\n' + (errs.join('\n')||'(none)')
      + '\n---- SUMMARY ----\n' + (errs.length? ('FAIL '+errs.length) : 'ALL PASS');
    document.body.appendChild(out);
  }, 1500);
})();
</script>
'''
idx = idx.replace('</body>', TEST + '</body>')
io.open(os.path.join(root, 'assets', '_e2e.html'), 'w', encoding='utf-8').write(idx)
print('assets/_e2e.html 已生成')
