# -*- coding: utf-8 -*-
"""
仙宫云批量出图 —— 一次开机跑完整套课件的全部槽位
流程: deploy -> running -> SSH -> ComfyUI 就绪 -> 上传参考图 -> 逐槽位出图 -> 拉图 -> 销毁
与 xgc_run_image.py 的区别: 那个是「一条 prompt 一次开机」，这个是「16 条一次开机」。
"""
import os, sys, json, time, base64, argparse, subprocess
sys.path.insert(0, os.path.expanduser('~/.pi/agent/skills/xgc-image-run/scripts'))
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "xgcri", os.path.expanduser("~/.pi/agent/skills/xgc-image-run/scripts/xgc_run_image.py"))
X = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(X)   # 复用 instances/balance/xgc/Remote

FACT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, FACT)
from project import Project
from pipeline import build_prompt, refs_for

# 本次出图落在 img_xgc/，把 img_dir 指过去，refs_for/img_path 就能解析到刚生成的图
_XGC_IMGDIR = [None]
Project.img_dir = property(lambda self: _XGC_IMGDIR[0] or os.path.join(self.dir, 'img'))

WF_TXT = '/root/ComfyUI/user/default/workflows/Krea2_Turbo_文生图.json'
WF_IMG = '/root/ComfyUI/user/default/workflows/Krea2_Turbo_图生图.json'
# 必须放 ComfyUI/input/（LoadImage 只认这个目录），且文件名必须纯 ASCII
# —— 中文字符会让 LoadImage 报 "Invalid image file"
REFDIR = '/root/ComfyUI/input'
REMOTE_OUT = '/root/ComfyUI/output'

# 远端出图脚本：cfg = {prompt,width,height,steps,cfg,seed,prefix,workflow,ref_files}
REMOTE_PY = r'''
import json, sys, time, uuid, base64, urllib.request, urllib.parse
CFG = json.loads(base64.b64decode("__CFG_B64__").decode())
HOST = "http://127.0.0.1:8188"

def get(path):
    last=None
    for _ in range(10):
        try:
            return json.loads(urllib.request.urlopen(HOST+path, timeout=60).read())
        except Exception as e:
            last=e; time.sleep(4)
    raise RuntimeError("ComfyUI GET %s 失败: %s" % (path,last))

def post(path,data):
    req=urllib.request.Request(HOST+path, data=json.dumps(data).encode(),
                               headers={"Content-Type":"application/json"})
    last=None
    for _ in range(10):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError("HTTP %s\n%s"%(e.code,e.read().decode('utf-8','replace')[:3000]))
        except Exception as e:
            last=e; time.sleep(4)
    raise RuntimeError("POST %s 失败: %s"%(path,last))

WIDGETS = {
  "UNETLoader": lambda i,w: {"unet_name":w[0],"weight_dtype":w[1]},
  "CLIPLoader": lambda i,w: {"clip_name":w[0],"type":w[1],"device":w[2]},
  "VAELoader": lambda i,w: {"vae_name":w[0]},
  "CLIPTextEncode": lambda i,w: {"text":w[0]},
  "ConditioningZeroOut": lambda i,w: {},
  "ReferenceLatent": lambda i,w: {},
  "VAEEncode": lambda i,w: {},
  "LoadImage": lambda i,w: {"image":w[0]},
  "FluxKontextMultiReferenceLatentMethod": lambda i,w: {"reference_latents_method":w[1]},
  "EmptyLatentImage": lambda i,w: {"width":w[0],"height":w[1],"batch_size":w[2]},
  "KSampler": lambda i,w: {"seed":w[0],"steps":w[2],"cfg":w[3],
                           "sampler_name":w[4],"scheduler":w[5],"denoise":w[6]},
  "VAEDecode": lambda i,w: {},
  "SaveImage": lambda i,w: {"filename_prefix":w[0]},
}
SKIP = ("Note","Reroute","PrimitiveNode","Bookmark")

def ui_to_api(wf):
    link_src={}
    for l in wf.get("links",[]):
        if isinstance(l,list) and len(l)>=5:
            link_src[l[0]]=(l[1],l[2])
    prompt={}
    for n in wf["nodes"]:
        t=n.get("type")
        if not t or t.endswith(SKIP) or t=="MarkdownNote":
            continue
        inputs={}
        for inp in n.get("inputs") or []:
            lk=inp.get("link")
            if lk is not None and lk in link_src:
                src=link_src[lk]
                inputs[inp["name"]]=[str(src[0]),src[1]]
        wv=n.get("widgets_values") or []
        fn=WIDGETS.get(t)
        if fn:
            try: inputs.update(fn(inputs,wv))
            except Exception: pass
        prompt[str(n["id"])]={"class_type":t,"inputs":inputs}
    return prompt

try:
    wf=json.load(open(CFG["workflow"], encoding="utf-8"))
    refs=CFG.get("ref_files") or []
    ri=0
    n_text=n_size=n_save=n_samp=n_load=0
    for n in wf["nodes"]:
        t=n.get("type")
        if t=="CLIPTextEncode":
            n["widgets_values"]=[CFG["prompt"]]; n_text+=1
        elif t=="EmptyLatentImage":
            n["widgets_values"]=[CFG["width"],CFG["height"],1]; n_size+=1
        elif t=="SaveImage":
            n["widgets_values"]=[CFG["prefix"]]; n_save+=1
        elif t=="LoadImage":
            if ri < len(refs):
                n["widgets_values"]=[refs[ri]]
            ri+=1; n_load+=1
        elif t=="KSampler":
            wv=list(n.get("widgets_values") or [])
            while len(wv)<7: wv.append("")
            if CFG.get("seed") is not None: wv[0]=CFG["seed"]
            wv[2],wv[3]=CFG["steps"],CFG["cfg"]
            n["widgets_values"]=wv; n_samp+=1
    if not (n_text and n_save and n_samp):
        raise RuntimeError("工作流缺节点 text=%s save=%s sampler=%s"%(n_text,n_save,n_samp))
    # 图生图工作流走 LoadImage + VAEEncode，没有 EmptyLatentImage，也不需要尺寸
    if not refs and not n_size:
        raise RuntimeError("文生图工作流缺 EmptyLatentImage 尺寸节点")
    if refs and n_load < len(refs):
        raise RuntimeError("图生图工作流只有 %d 个 LoadImage，装不下 %d 张参考图"%(n_load,len(refs)))
    graph=ui_to_api(wf)
    r=post("/prompt",{"prompt":graph,"client_id":str(uuid.uuid4())})
    pid=r["prompt_id"]
    t0=time.time()
    while time.time()-t0<1200:
        time.sleep(2)
        h=get("/history/"+pid)
        if pid in h:
            out=h[pid]; st=out.get("status",{})
            if st.get("status_str")=="error":
                raise RuntimeError("ComfyUI 执行出错: "+json.dumps(st,ensure_ascii=False)[:2500])
            imgs=[]
            for _nid,o in (out.get("outputs") or {}).items():
                for im in o.get("images",[]): imgs.append(im)
            if imgs:
                im=imgs[0]
                sys.stdout.write("\n__XGC_RESULT__"+json.dumps({
                    "ok":True,"filename":im["filename"],
                    "type":im.get("type","output"),
                    "subfolder":im.get("subfolder") or "",
                    "seconds":round(time.time()-t0,1)})+"\n")
                sys.exit(0)
    raise RuntimeError("出图超时(1200s)")
except Exception as e:
    sys.stdout.write("\n__XGC_RESULT__"+json.dumps({"ok":False,"error":str(e)[:3000]})+"\n")
    sys.exit(1)
'''


class _Uploader(object):
    """走 SFTP 传参考图 / 拉成品图。
    为什么不用 `echo <base64> > file`：密码模式下 Remote.run 会把整条命令塞进
    paramiko exec_command，1.7MB 的图 → 2.3MB base64 命令行，直接把连接撑爆（EOFError）。
    为什么也不用 base64 回传成品图：paramiko 的 exec_command 通道会把 2~3MB 的单行
    stdout 截断，json 解析就报 Unterminated string（已踩过）—— 一律走 SFTP。"""

    def __init__(self, rm):
        self.rm = rm
        self.pk = rm._paramiko()
        self.sftp = None

    def _c(self):
        if self.sftp is None:
            self.sftp = self.pk.open_sftp()
        return self.sftp

    def put(self, local, remote):
        self._c().put(local, remote)

    def get(self, remote, local):
        self._c().get(remote, local)


def _shrink_ref(path, tmpdir):
    """参考图缩到长边 1024 再传：图生图只用构图，尺寸越小上传越快失败率越低。"""
    from PIL import Image
    os.makedirs(tmpdir, exist_ok=True)
    dst = os.path.join(tmpdir, os.path.splitext(os.path.basename(path))[0] + '.jpg')
    im = Image.open(path).convert('RGB')
    w, h = im.size
    m = max(w, h)
    if m > 1024:
        im = im.resize((int(w * 1024 / m), int(h * 1024 / m)), Image.LANCZOS)
    im.save(dst, 'JPEG', quality=88)
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True)
    ap.add_argument('--outdir', default=None, help='默认 <project>/img_xgc')
    ap.add_argument('--batch', default=None,
                    help='只跑指定批次，逗号分隔：chain / real / photo / style')
    ap.add_argument('--only', nargs='*', default=None, help='只跑指定槽位（配合 --batch）')
    ap.add_argument('--into-img', action='store_true',
                    help='跑完把图拷进 <project>/img/（这样装配器才吃得到）')
    ap.add_argument('--size', default='1536x1024')
    ap.add_argument('--steps', type=int, default=8)
    ap.add_argument('--cfg', type=float, default=1.0)
    ap.add_argument('--gpu', default=None)
    ap.add_argument('--keep', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--yes', action='store_true')
    a = ap.parse_args()

    proj = Project(a.project)
    pdir = os.path.dirname(os.path.abspath(a.project))
    outdir = a.outdir or os.path.join(pdir, 'img_xgc')
    os.makedirs(outdir, exist_ok=True)
    _XGC_IMGDIR[0] = outdir

    # ---- 组装任务表（按链条顺序） ----
    batches = None
    if a.batch:
        batches = [x.strip() for x in a.batch.split(',') if x.strip()]

    def want(im):
        return ((batches is None or im.get('batch') in batches)
                and (not a.only or im['slot'] in a.only))

    order = proj.chain.get('order') or [i['slot'] for i in proj.images]
    byname = {i['slot']: i for i in proj.images}
    tasks = []
    for slot in order:
        im = byname[slot]
        if im.get('alias') or not want(im):
            continue
        tasks.append(dict(slot=slot, im=im))
    for im in proj.images:
        if im['slot'] not in order and want(im):
            tasks.append(dict(slot=im['slot'], im=im))
    alias_jobs = [i for i in proj.images if i.get('alias') and want(i)]
    if batches:
        print('>>> 只跑批次: %s' % ','.join(batches))

    print('=== 任务表（%d 出图 + %d 本地别名）===' % (len(tasks), len(alias_jobs)))
    for t in tasks:
        print('  %-18s  prompt=%d字' % (t['slot'], len(build_prompt(proj, t['im']))))
    for i in alias_jobs:
        print('  %-18s [alias -> %s]  不出图' % (i['slot'], i['alias']))
    print('\n输出目录: %s' % outdir)

    if a.dry_run:
        for t in tasks:
            print('\n' + '=' * 70 + '\n### %s\n%s' % (t['slot'], build_prompt(proj, t['im'])))
        return

    # 参考图链：refs_for 依赖 img/ 下已存在的图（链条靠它串起来）。
    # 出图结果写在 img_xgc，已在上面把 Project.img_dir 指过去。

    d = X.load_defaults()
    gpu = a.gpu or d['default_gpu']
    image = d['default_image']
    keyfile = os.path.expanduser(d.get('ssh_private_key') or '~/.ssh/piwebui.pem')
    w, h = (int(x) for x in a.size.lower().split('x'))

    running = [i for i in X.instances() if i.get('status') == 'running']
    if running:
        die = '已有实例在跑，先处理: ' + ', '.join(i['id'] for i in running)
        sys.exit(die)

    before = {i['id'] for i in X.instances()}
    inst_id = None; t_running = None; rate = 0.0; destroyed = False
    t_start = time.time()
    try:
        print('\n[1/7] 开机 ...')
        rc, out, _ = X.xgc('deploy', '--gpu', gpu, '--count', '1', '--image', image,
                           '--image-type', 'private', '--name', 'cw-batch', '--yes')
        if rc != 0:
            sys.exit('部署失败（不重试）:\n' + out)
        for _ in range(30):
            time.sleep(3)
            new = [i for i in X.instances() if i['id'] not in before]
            if new:
                inst_id = new[0]['id']; break
        sys.exit('部署了但没看到实例，去控制台确认') if not inst_id else None
        print('      实例 %s' % inst_id)

        print('[2/7] 等运行中 ...')
        info = None
        for _ in range(180):
            time.sleep(5)
            me = [i for i in X.instances() if i['id'] == inst_id]
            if me and me[0].get('status') == 'running':
                info = me[0]; break
        if not info:
            sys.exit('实例没到 running')
        rate = float(info.get('price_per_hour') or 0)
        t_running = time.time()
        print('      CNY %s/h  ← 计费开始' % rate)

        print('[3/7] SSH ...')
        host = info.get('ssh_domain') or '%s-22.container.x-gpu.com' % inst_id
        rm = X.Remote(host, int(info['ssh_port']), info.get('ssh_user') or 'root',
                      keyfile, info.get('password'))
        if not rm.wait_ready(360):
            sys.exit('SSH 连不上')
        print('      认证 %s' % rm.mode)

        cport = int(d.get('comfy_port') or 8188)
        print('[4/7] 等 ComfyUI 就绪 ...')
        probe = ("curl -s -o /dev/null -w '%{http_code}' -m 5 "
                 "http://127.0.0.1:" + str(cport) + "/system_stats")
        t0 = time.time(); ok = False
        while time.time() - t0 < 600:
            o = rm.run(probe, timeout=30, check=False)
            if o.strip().endswith('200'):
                ok = True; break
            time.sleep(5)
        if not ok:
            sys.exit('ComfyUI 600s 未就绪')
        print('      就绪（%ds）' % int(time.time() - t0))

        print('[5/7] 准备远端目录 ...')
        rm.run('mkdir -p %s && ls /root/ComfyUI/user/default/workflows/' % REFDIR)
        up = _Uploader(rm)
        tmpdir = os.path.join(pdir, '.xgc_tmp')
        os.makedirs(tmpdir, exist_ok=True)

        uploaded = {}
        done = 0; total = len(tasks)
        for t in tasks:
            dst = os.path.join(outdir, t['slot'] + '.png')
            if os.path.exists(dst) and os.path.getsize(dst) > 10000:
                print('  [skip] %s' % t['slot']); continue
            # ★ 每张实时解析参考图：此时前面的槽位已经落盘，链条才连得上
            refs = refs_for(proj, t['im'])
            # 镜像里的图生图工作流只有 1 个 LoadImage（多参考节点存在但没连线）。
            # 所以参考图只取 1 张：链条的锚点（成品）本来就是设计基准，
            # 多一张“上一步”反而可能让模型跟着残缺的铅笔稿跑偏。
            if len(refs) > 1:
                anchor = proj.chain.get('anchor')
                ap_ = proj.img_path(anchor, 'hd') if anchor else None
                refs = [ap_] if ap_ else refs[:1]
            prompt = build_prompt(proj, t['im'], refs=refs)
            for p in refs:
                if p not in uploaded:
                    small = _shrink_ref(p, tmpdir)
                    name = 'cwref%03d.jpg' % (len(uploaded) + 1)
                    up.put(small, REFDIR + '/' + name)
                    uploaded[p] = name
                    print('      ↑ 参考图 %s <- %s (%.2fMB -> %.2fMB)'
                          % (name, os.path.basename(p),
                             os.path.getsize(p) / 2**20, os.path.getsize(small) / 2**20))
            wf = WF_IMG if refs else WF_TXT
            cfg = dict(prompt=prompt, width=w, height=h, steps=a.steps, cfg=a.cfg,
                       seed=None, prefix='cw_%02d' % done, workflow=wf,
                       ref_files=[uploaded[p] for p in refs])
            code = REMOTE_PY.replace('__CFG_B64__', base64.b64encode(
                json.dumps(cfg, ensure_ascii=False).encode('utf-8')).decode())
            done += 1
            print('  [%d/%d] %-18s refs=%d ...' % (done, total, t['slot'], len(refs)), flush=True)
            try:
                out = rm.run(stdin=code, timeout=1300)
            except Exception as e:
                print('      SSH 异常: %s  跳过该槽位' % e); continue
            res = None
            for line in out.splitlines():
                if line.startswith('__XGC_RESULT__'):
                    res = json.loads(line[len('__XGC_RESULT__'):])
            if not res or not res.get('ok'):
                print('      失败: %s' % (res or {}).get('error', out[-500:]))
                continue
            rpath = '%s/%s%s' % (REMOTE_OUT, res.get('subfolder') or '', res['filename'])
            try:
                up.get(rpath, dst)
            except Exception as e:
                print('      SFTP 下载失败 %s: %s' % (rpath, e))
                continue
            print('      OK %ss  %.1f MB' % (res['seconds'], os.path.getsize(dst) / 2**20))

        for i in alias_jobs:
            src = proj.img_path(i['alias'], 'hd')
            if src and os.path.exists(src):
                import shutil
                shutil.copy2(src, os.path.join(outdir, i['slot'] + '.png'))
                print('  [alias] %s <- %s' % (i['slot'], i['alias']))
        print('[6/7] 全部拉回本地')
        if a.into_img:
            import shutil
            imgdir = os.path.join(pdir, 'img')
            os.makedirs(imgdir, exist_ok=True)
            n = 0
            for t in tasks:
                src = os.path.join(outdir, t['slot'] + '.png')
                if os.path.exists(src) and os.path.getsize(src) > 10000:
                    shutil.copy2(src, os.path.join(imgdir, t['slot'] + '.png')); n += 1
            for i in alias_jobs:
                src = os.path.join(outdir, i['slot'] + '.png')
                if os.path.exists(src):
                    shutil.copy2(src, os.path.join(imgdir, i['slot'] + '.png')); n += 1
            print('      已拷入 img/：%d 张' % n)
    finally:
        if inst_id and not a.keep:
            print('[7/7] 销毁实例 ...')
            rc, out, _ = X.xgc('destroy', inst_id, '--yes')
            destroyed = rc == 0
            print('      ' + ('已销毁' if destroyed else '销毁失败！' + out))
        elif inst_id:
            print('!! --keep：%s 还在烧钱 CNY %s/h' % (inst_id, rate))
        if inst_id:
            t_stop = time.time()
            billed = int(t_stop - t_running) if t_running else 0
            print('\n=== 本次花费 ===')
            print('  计费 %d分%d秒 x CNY %s/h = CNY %.4f' % (billed // 60, billed % 60, rate,
                                                             billed / 3600 * rate))
            b = X.balance()
            if b is not None:
                print('  余额 CNY %.2f' % b)


if __name__ == '__main__':
    main()