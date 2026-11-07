# -*- coding: utf-8 -*-
"""
课件工厂 · WebUI 审图台
启动： python 工厂/server.py 项目/大熊猫吃竹子-4-6岁/project.json
浏览器打开 http://127.0.0.1:8777
审图 → 改 prompt → 重跑单张 → 重新装配 PDF → 刷新预览，闭环都在浏览器里完成。
"""
import os, sys, json, time, threading, traceback, uuid, io, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote
sys.stdout.reconfigure(encoding='utf-8')

from project import Project, find_project_paths
import pipeline, builder, exporter

PORT = int(os.environ.get('DECKUI_PORT', '8777'))
WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJ_DIR = os.path.join(ROOT, '项目')
PROJ = None
JOBS = {}
LOCK = threading.Lock()


def proj_path(dirname):
    """目录名 -> project.json 路径（防目录穿越）"""
    d = os.path.basename(str(dirname).rstrip('/\\'))
    return os.path.join(PROJ_DIR, d, 'project.json')


def set_current(path):
    """切换当前正在审图的课件"""
    global PROJ
    PROJ = Project(path)
    return PROJ


def new_job(name):
    jid = uuid.uuid4().hex[:8]
    with LOCK:
        JOBS[jid] = dict(id=jid, name=name, state='running', log=[], result=None,
                         t0=time.time(), t1=None)
    return jid


def jlog(jid, msg):
    print(msg, flush=True)
    with LOCK:
        if jid in JOBS:
            JOBS[jid]['log'].append(str(msg))


def finish(jid, result=None, error=None):
    with LOCK:
        j = JOBS.get(jid)
        if not j:
            return
        j['state'] = 'error' if error else 'done'
        j['result'] = result
        j['t1'] = time.time()
        if error:
            j['log'].append('!! ' + str(error))


def run_bg(name, fn):
    jid = new_job(name)

    def go():
        try:
            finish(jid, fn(lambda m: jlog(jid, m)))
        except Exception as e:
            traceback.print_exc()
            finish(jid, error='%s: %s' % (type(e).__name__, e))
    threading.Thread(target=go, daemon=True).start()
    return jid


# ---------------- 任务实现 ----------------
def job_regen(slots, force=True, model=None, prompts=None, size=None):
    def fn(log):
        n_ok = 0
        for s in slots:
            im = PROJ.by_slot.get(s)
            if not im:
                log('跳过未知槽位 %s' % s); continue
            pr = (prompts or {}).get(s) or None
            im = PROJ.by_slot.get(s)
            if pr and im is not None:
                # UI 只传“这一步该画什么”的 prompt 字段；把它写回槽位，
                # 然后交给 build_prompt() 重新组装完整 prompt（LOCK+style+stroke+参考图+一致性）。
                # 旧写法 gen_one(prompt=pr) 会把 LOCK 等全部丢掉，导致 WebUI 重跑的东西
                # 跟批量生成的不是一个东西。
                im = dict(im); im['prompt'] = pr
                im['anchor'] = True
            try:
                dst, _ = pipeline.gen_one(PROJ, im, force=force, prompt=None, model=model,
                                          size=size, log=log)
            except Exception as ex:
                log('[EXC ] %s -> %s: %s' % (s, type(ex).__name__, ex))
                dst = None
            n_ok += 1 if dst else 0
        log('重跑完成 %d/%d' % (n_ok, len(slots)))
        if not n_ok:
            log('（失败或全部跳过，不重新装配）')
            return dict(regen=0)
        log('--- 正在压缩并重新装配 ---')
        pipeline.compress(PROJ, log=log)
        pptx = builder.build(PROJ, mode='sell', verbose=False)
        exporter.export(PROJ, pptx, log=log)
        log('全部完成，预览已刷新')
        return dict(regen=n_ok, pptx=pptx, pdf=PROJ.pdf())
    return fn


def job_after_image(slot):
    """换图/重搜之后：压缩 + 重装 + 导 PDF

    分步打日志：导出要调 PowerPoint COM，若被占用/卡住会长时间无响应，
    日志不写清楚就会表现为「一直 running，不知道卡在哪」。"""
    def fn(log):
        t0 = time.time()
        log('图片已更新：%s' % slot)
        log('[1/3] 压缩图片 → img_sell/ ...')
        pipeline.compress(PROJ, log=log)
        log('[2/3] 装配 pptx ...')
        pptx = builder.build(PROJ, mode='sell', verbose=False)
        log('[3/3] 导出 PDF（调 PowerPoint，若 Office 弹窗或文件被占用会卡住）...')
        exporter.export(PROJ, pptx, log=log)
        log('全部完成，预览已刷新（共 %.0f 秒）' % (time.time() - t0))
        return dict(slot=slot, pdf=PROJ.pdf())
    return fn


def job_build():
    def fn(log):
        pipeline.compress(PROJ, log=log)
        pptx = builder.build(PROJ, mode='sell', verbose=True)
        exporter.export(PROJ, pptx, log=log)
        return dict(pptx=pptx, pdf=PROJ.pdf())
    return fn


def job_export_only():
    def fn(log):
        return dict(pdf=exporter.export(PROJ, PROJ.pptx(), log=log))
    return fn


# ---------------- 批量操作（多课件） ----------------
BATCH_OPS = {}
BATCH_NAMES = {'set_brand': '统一品牌名', 'set_model': '统一出图模型',
               'set_stroke': '统一线条规范', 'replace': '批量查找替换文案',
               'build': '批量重新装配+导出', 'export': '批量仅重导 PDF',
               'reset_review': '批量清空审图标记'}


def bop(name):
    def deco(f):
        BATCH_OPS[name] = f
        return f
    return deco


def _sub_strings(node, find, repl):
    """递归把结构里所有字符串做替换，返回命中次数"""
    n = 0
    if isinstance(node, str):
        if find in node:
            return node.replace(find, repl), node.count(find)
        return node, 0
    if isinstance(node, list):
        out = []
        for x in node:
            v, c = _sub_strings(x, find, repl)
            out.append(v); n += c
        return out, n
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            v2, c = _sub_strings(v, find, repl)
            out[k] = v2; n += c
        return out, n
    return node, 0


@bop('set_brand')
def _b_brand(pr, val, log):
    pr.data.setdefault('meta', {})['brand'] = val
    log('  meta.brand → %s' % val)
    return 1


@bop('set_model')
def _b_model(pr, val, log):
    n = 0
    for im in pr.images:
        if im.get('alias'):        # 别名图不出图，不用管模型
            continue
        im['model'] = val
        n += 1
    log('  %d 个槽位（跳过别名图）→ %s' % (n, val))
    return n


@bop('set_stroke')
def _b_stroke(pr, val, log):
    pr.data.setdefault('common', {})['stroke'] = val
    log('  common.stroke 已更新（%d 字符，全链条共用）' % len(val))
    return 1


@bop('replace')
def _b_replace(pr, val, log):
    find = (val or {}).get('find', '')
    repl = (val or {}).get('repl', '')
    if not find:
        raise ValueError('要替换的文字为空')
    n = 0
    for pg in pr.pages:
        for k in list(pg.keys()):
            pg[k], c = _sub_strings(pg[k], find, repl)
            n += c
    log('  "%s" → "%s"，命中 %d 处' % (find, repl, n))
    return n


@bop('reset_review')
def _b_reset(pr, val, log):
    n = len(pr.review())
    pr.save_review({})
    log('  已清空 %d 条审图标记' % n)
    return n


@bop('build')
def _b_build(pr, val, log):
    return 1


@bop('export')
def _b_export(pr, val, log):
    return 1


def _save(pr):
    with open(pr.path, 'w', encoding='utf-8') as f:
        json.dump(pr.data, f, ensure_ascii=False, indent=2)


def job_batch(dirs, op, val, rebuild=True):
    """对多个课件依次执行同一个操作
    op: set_brand/set_model/set_stroke/replace/reset_review/build/export
    rebuild: 改完是否自动压缩+重装配+导出
    """
    def fn(log):
        ok, bad = [], []
        for i, dname in enumerate(dirs, 1):
            log('── [%d/%d] %s' % (i, len(dirs), dname))
            try:
                pr = Project(proj_path(dname))
                f = BATCH_OPS.get(op)
                if not f:
                    raise ValueError('未知操作 %s' % op)
                n = f(pr, val, log)
                if op not in ('build', 'export'):
                    _save(pr)
                if op in ('build', 'export') or rebuild:
                    if op == 'export':
                        pptx = pr.pptx()
                        if not os.path.exists(pptx):
                            log('  没有 pptx，改为完整装配')
                            pipeline.compress(pr, log=log)
                            pptx = builder.build(pr, mode='sell', verbose=False)
                    else:
                        pipeline.compress(pr, log=log)
                        pptx = builder.build(pr, mode='sell', verbose=False)
                    exporter.export(pr, pptx, log=log)
                ok.append(dict(dirname=dname, changed=n,
                               pdf=pr.pdf(), pptx=pr.pptx()))
            except Exception as e:
                log('[FAIL] %s: %s' % (dname, e))
                bad.append(dict(dirname=dname, error='%s: %s' % (type(e).__name__, e)))
        log('批量完成：成功 %d / 失败 %d' % (len(ok), len(bad)))
        # 如果批量动到了「当前正在看的」课件，重新加载，否则界面会拿到旧数据
        if PROJ is not None and PROJ.dirname in dirs:
            set_current(PROJ.path)
            log('（当前课件已重新加载）')
        return dict(op=op, opname=BATCH_NAMES.get(op, op), ok=ok, fail=bad)
    return fn


def report_md():
    st = PROJ.status()
    rev = st['review']
    L = ['# %s · 审图报告' % st['name'], '',
         '- 目录：`%s`' % st['dir'], '- 页数：%d' % len(st['pages']),
         '- 图片槽位：%d（缺图 %d）' % (len(st['slots']), len(st['missing'])), '']
    if st['missing']:
        L += ['## 缺失图片', ''] + ['- `%s`' % m for m in st['missing']] + ['']
    groups = {}
    for s in st['slots']:
        r = rev.get(s['slot'], {})
        groups.setdefault(r.get('status', 'todo'), []).append((s, r))
    names = {'todo': '未审', 'ok': '通过', 'fix': '需小改', 'redo': '需重跑'}
    for k in ('redo', 'fix', 'todo', 'ok'):
        if k not in groups:
            continue
        L += ['## %s（%d）' % (names[k], len(groups[k])), '']
        for s, r in groups[k]:
            tags = ' '.join('#%s' % t for t in r.get('tags', []))
            L.append('- `%s`（%s）%s' % (s['slot'], s['batch'], tags))
            if r.get('note'):
                L.append('    - 说明：%s' % r['note'])
            if r.get('prompt'):
                L.append('    - 改后 prompt：%s' % r['prompt'][:400].replace('\n', ' / '))
        L.append('')
    return '\n'.join(L)


# ---------------- HTTP ----------------
class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype='application/json; charset=utf-8', extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        elif isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode('utf-8'))

    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query); path = u.path
        try:
            if path in ('/', '/index.html'):
                with open(os.path.join(WEB, 'index.html'), encoding='utf-8') as f:
                    return self._send(200, f.read(), 'text/html; charset=utf-8')
            if path == '/api/projects':
                # 课件列表（多项目工作台）
                cur = PROJ.dirname if PROJ else ''
                out = []
                for f in find_project_paths():
                    try:
                        s = Project(f).summary()
                        s['current'] = (s['dirname'] == cur)
                        out.append(s)
                    except Exception as e:
                        out.append(dict(dirname=os.path.basename(os.path.dirname(f)),
                                        name=os.path.basename(os.path.dirname(f)),
                                        error=str(e)))
                return self._send(200, dict(projects=out, current=cur,
                                            total=len(out),
                                            batch_ops=BATCH_NAMES))
            if path == '/api/thumb':
                d = q.get('p', [''])[0]
                f = proj_path(d)
                if not os.path.exists(f):
                    return self._send(404, {'error': 'no project'})
                t = Project(f).thumb()
                if not t:
                    return self._send(404, {'error': 'no thumb'})
                with open(t, 'rb') as fh:
                    data = fh.read()
                ct = 'image/png' if t.lower().endswith('.png') else 'image/jpeg'
                return self._send(200, data, ct)
            if path == '/api/alt':
                # 网搜照片的备选图（img_alt/<slot>_NN.png）
                slot = q.get('slot', [''])[0]
                d = PROJ.alt_dir
                names = PROJ.alts(slot)
                return self._send(200, dict(slot=slot, n=len(names),
                                            names=names,
                                            ts=int(os.path.getmtime(d)) if os.path.isdir(d) else 0))
            if path == '/api/altimg':
                # 直接吐备选图字节
                slot = q.get('slot', [''])[0]
                nm = os.path.basename(q.get('f', [''])[0])
                if not nm or not nm.startswith(slot + '_')                         or not nm.lower().endswith(('.png', '.jpg')):
                    return self._send(400, {'error': 'bad name'})
                f = os.path.join(PROJ.alt_dir, nm)
                if not os.path.exists(f):
                    return self._send(404, {'error': 'no file'})
                ct = 'image/png' if nm.lower().endswith('.png') else 'image/jpeg'
                with open(f, 'rb') as fh:
                    return self._send(200, fh.read(), ct)
            if path == '/api/status':
                st = PROJ.status()
                st['chain_order'] = list(PROJ.chain.get('order', []))
                st['anchor'] = PROJ.chain.get('anchor') or (st['chain_order'][0] if st['chain_order'] else '')
                # 把“真实生效的参考图”算出来给前端（含自动注入的成品锚点），
                # 否则界面上显示的 refs 是假的，看不出链条到底怎么串
                for sl in st['slots']:
                    im = PROJ.by_slot.get(sl['slot'])
                    eff = []
                    if im:
                        for p in pipeline.refs_for(PROJ, im):
                            eff.append(os.path.splitext(os.path.basename(p))[0])
                    sl['eff_refs'] = eff
                return self._send(200, st)
            if path == '/api/report':
                md = report_md().encode('utf-8')
                return self._send(200, md, 'text/markdown; charset=utf-8',
                                  {'Content-Disposition': 'attachment; filename="review.md"'})
            if path == '/api/full_prompt':
                s = q.get('slot', [''])[0]
                im = PROJ.by_slot.get(s)
                if not im:
                    return self._send(404, {'error': 'unknown slot'})
                try:
                    im2 = dict(im); im2['prompt'] = q.get('p', [im['prompt']])[0]
                    return self._send(200, {'slot': s, 'text': pipeline.build_prompt(PROJ, im2)})
                except Exception as e:
                    return self._send(500, {'error': str(e)})
            if path == '/api/models':
                return self._send(200, pipeline.CATALOG)
            if path == '/api/outputs':
                import glob
                files = []
                for f in sorted(glob.glob(os.path.join(PROJ.out_dir, '*'))):
                    if os.path.isfile(f):
                        files.append(dict(name=os.path.basename(f),
                                          size=os.path.getsize(f), mtime=os.path.getmtime(f)))
                return self._send(200, dict(dir=PROJ.out_dir, files=files))
            if path == '/download':
                which = q.get('f', ['pdf'])[0]
                f = PROJ.pdf() if which == 'pdf' else PROJ.pptx()
                if not os.path.exists(f):
                    return self._send(404, {'error': '还没有导出，先点「重新装配 + 导出」'})
                with open(f, 'rb') as fh:
                    data = fh.read()
                fn = quote(os.path.basename(f).encode('utf-8'))
                return self._send(200, data, 'application/octet-stream',
                                  {'Content-Disposition':
                                   "attachment; filename*=UTF-8''" + fn})
            if path == '/api/job':
                with LOCK:
                    return self._send(200, JOBS.get(q.get('id', [''])[0], {'state': 'unknown'}))
            if path == '/img':
                slot = q.get('slot', [''])[0]
                mode = q.get('mode', ['sell'])[0]
                p = PROJ.img_path(slot, mode)
                if not p:
                    return self._send(404, {'error': 'no image %s' % slot})
                with open(p, 'rb') as f:
                    data = f.read()
                ct = 'image/png' if p.lower().endswith('.png') else 'image/jpeg'
                if q.get('dl'):
                    # 单张下载：作为附件返回，浏览器直接存盘
                    fn = quote(os.path.basename(p).encode('utf-8'))
                    return self._send(200, data, ct,
                                      {'Content-Disposition':
                                       "attachment; filename*=UTF-8''" + fn})
                return self._send(200, data, ct)
            if path == '/zip_images':
                # 全部图片打包成 zip 下载（老师拿去单独用图）
                import zipfile, io as _io
                buf = _io.BytesIO()
                with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
                    for im in PROJ.images:
                        s = im['slot']
                        for m, sub in (('hd', ''), ('sell', '供货版_压缩/')):
                            p = PROJ.img_path(s, m)
                            if p and os.path.exists(p):
                                z.write(p, os.path.join(sub, os.path.basename(p)))
                data = buf.getvalue()
                fn = quote(('%s_全部图片.zip' % PROJ.name).encode('utf-8'))
                return self._send(200, data, 'application/zip',
                                  {'Content-Disposition':
                                   "attachment; filename*=UTF-8''" + fn})
            if path.startswith('/preview/'):
                f = os.path.join(PROJ.preview_dir, os.path.basename(path))
                if not os.path.exists(f):
                    return self._send(404, {'error': 'no preview'})
                with open(f, 'rb') as fh:
                    return self._send(200, fh.read(), 'image/png')
            return self._send(404, {'error': 'not found'})
        except Exception as e:
            traceback.print_exc()
            return self._send(500, {'error': str(e)})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            b = self._body()
            if path == '/api/review':
                PROJ.save_review(b)
                return self._send(200, {'ok': True, 'saved': PROJ.review_file})
            if path == '/api/prompt':
                slot, pr = b['slot'], b['prompt']
                PROJ.by_slot[slot]['prompt'] = pr
                with open(PROJ.path, 'w', encoding='utf-8') as f:
                    json.dump(PROJ.data, f, ensure_ascii=False, indent=2)
                return self._send(200, {'ok': True})
            if path == '/api/regen':
                slots = b.get('slots') or []
                if not slots:
                    return self._send(400, {'error': 'no slots'})
                for s, pr in (b.get('prompts') or {}).items():
                    if s in PROJ.by_slot:
                        PROJ.by_slot[s]['prompt'] = pr
                with open(PROJ.path, 'w', encoding='utf-8') as f:
                    json.dump(PROJ.data, f, ensure_ascii=False, indent=2)
                jid = run_bg('重跑 %d 张' % len(slots),
                             job_regen(slots, b.get('force', True), b.get('model'),
                                       b.get('prompts'), b.get('size')))
                return self._send(200, {'job': jid})
            if path == '/api/regen_chain':
                order = list(PROJ.chain.get('order', []))
                if not order:
                    return self._send(400, {'error': 'project.json 里没定义 chain.order'})
                if b.get('prompts'):
                    for s, pr in b['prompts'].items():
                        if s in PROJ.by_slot:
                            PROJ.by_slot[s]['prompt'] = pr
                    with open(PROJ.path, 'w', encoding='utf-8') as f:
                        json.dump(PROJ.data, f, ensure_ascii=False, indent=2)
                n_alias = sum(1 for s in order if PROJ.by_slot[s].get('alias'))
                price = (pipeline.model_info(b.get('model') or pipeline.DEF['model'])
                         .get('price') or 0)
                jid = run_bg('重跑整条链 %d 张（%d 张别名复制不花钱 + %d 张真出图 ≈ ¥%.2f）'
                             % (len(order), n_alias, len(order) - n_alias,
                                price * (len(order) - n_alias)),
                             job_regen(order, True, b.get('model'), b.get('prompts'), b.get('size')))
                return self._send(200, {'job': jid, 'order': order,
                                        'alias': n_alias,
                                        'cost': price * (len(order) - n_alias)})
            if path == '/api/pick_alt':
                # 把某张备选图提升为当前槽位的主图
                slot = b.get('slot') or ''
                nm = os.path.basename(b.get('f') or '')
                im = PROJ.by_slot.get(slot)
                if not im:
                    return self._send(400, {'error': 'no such slot'})
                if not nm or not nm.startswith(slot + '_')                         or not nm.lower().endswith(('.png', '.jpg')):
                    return self._send(400, {'error': 'bad name'})
                src = os.path.join(PROJ.alt_dir, nm)
                if not os.path.exists(src):
                    return self._send(404, {'error': 'no alt file'})
                dst = os.path.join(PROJ.img_dir, slot + '.png')
                # 真·交换：备选图转回【真 PNG】当主图，旧主图降级成 JPEG 备选。
                # 不能直接 copy：备选是 JPEG，塞进 .png 里扩展名就骗人了。
                from PIL import Image
                new = Image.open(src).convert('RGB')
                if os.path.exists(dst):
                    old = Image.open(dst).convert('RGB')
                    old.save(src, 'JPEG', quality=88, optimize=True, progressive=True)
                new.save(dst, 'PNG', optimize=True)
                jid = run_bg('换图 %s <- %s' % (slot, nm),
                             job_after_image(slot))
                return self._send(200, {'ok': True, 'slot': slot, 'job': jid})
            if path == '/api/search_photo':
                # 对某个槽位重新联网搜图（可临时换关键词）
                slot = b.get('slot') or ''
                im = PROJ.by_slot.get(slot)
                if not im:
                    return self._send(400, {'error': 'no such slot'})
                qs = b.get('queries')
                if qs:
                    im['query'] = qs if isinstance(qs, list) else [qs]
                im['source'] = 'search'
                with open(PROJ.path, 'w', encoding='utf-8') as f:
                    json.dump(PROJ.data, f, ensure_ascii=False, indent=2)
                jid = run_bg('联网搜图 %s' % slot, job_regen([slot], True))
                return self._send(200, {'ok': True, 'job': jid,
                                        'query': im.get('query')})
            if path == '/api/switch':
                d = b.get('project') or ''
                f = proj_path(d)
                if not os.path.exists(f):
                    return self._send(404, {'error': '找不到课件 %s' % d})
                set_current(f)
                print('切换到：%s' % PROJ.name, flush=True)
                return self._send(200, {'ok': True, 'name': PROJ.name,
                                        'dir': PROJ.dir,
                                        'pages': len(PROJ.pages),
                                        'images': len(PROJ.images)})
            if path == '/api/batch':
                dirs = b.get('projects') or []
                op = b.get('op')
                if not dirs:
                    return self._send(400, {'error': '没选课件'})
                if op not in BATCH_OPS:
                    return self._send(400, {'error': '未知操作 %s' % op})
                jid = run_bg('批量%s × %d 个课件'
                             % (BATCH_NAMES.get(op, op), len(dirs)),
                             job_batch(dirs, op, b.get('value'),
                                       rebuild=b.get('rebuild', True)))
                return self._send(200, {'job': jid, 'op': op, 'count': len(dirs)})
            if path == '/api/openfolder':
                target = b.get('dir') or PROJ.out_dir
                os.startfile(target)
                return self._send(200, {'ok': True, 'dir': target})
            if path == '/api/build':
                return self._send(200, {'job': run_bg('重新装配 + 导出 PDF', job_build())})
            if path == '/api/export':
                return self._send(200, {'job': run_bg('仅重新导出 PDF', job_export_only())})
            return self._send(404, {'error': 'not found'})
        except Exception as e:
            traceback.print_exc()
            return self._send(500, {'error': str(e)})


def _already_running(port):
    """检测端口上是不是已经有一个审图台在跑（Windows 下 SO_REUSEADDR 允许
    重复绑定同一端口，会静默变成「旧代码在响应新请求」，很坑）"""
    import urllib.request
    try:
        r = urllib.request.urlopen('http://127.0.0.1:%d/api/status' % port, timeout=2)
        d = json.loads(r.read().decode('utf-8'))
        return bool(d.get('name') or d.get('slots') is not None)
    except Exception:
        return False


def _free_port(port, tries=12):
    import socket
    for i in range(tries):
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        try:
            s.bind(('127.0.0.1', port + i))
            s.close()
            return port + i
        except OSError:
            s.close()
    return port


def serve(project_path, port=PORT):
    if project_path and os.path.isdir(project_path):
        project_path = os.path.join(project_path, 'project.json')
    if project_path and not os.path.exists(project_path):
        cand = proj_path(project_path)
        if os.path.exists(cand):
            project_path = cand
    # ★ 已经有审图台在跑 → 不要再起一个（否则新代码永远不会被调用，
    #   表现为「我改了代码/重启了服务，界面还是老样子」）
    if _already_running(port):
        print('=' * 62)
        print(' 已经在跑了：http://127.0.0.1:%d' % port)
        print(' 直接用浏览器打开上面这个地址就行（不用再启动一次）。')
        print(' 如果界面还是旧的，请先关掉那个运行中的窗口/进程再重开。')
        print('=' * 62)
        return port
    port = _free_port(port)
    set_current(project_path)
    n_all = len(find_project_paths())
    print('=' * 62)
    print(' 课件工厂 · 审图台（多课件工作台）')
    print(' 当前：%s   (%d 页 / %d 张图)' % (PROJ.name, len(PROJ.pages), len(PROJ.images)))
    print(' 缺图：%s' % (PROJ.status()['missing'] or '无'))
    print(' 共发现 %d 套课件，可在界面顶栏「📚 课件列表」里切换/批量改' % n_all)
    print(' 打开：http://127.0.0.1:%d' % port)
    print(' （本窗口是服务端，关掉它就关闭审图台）')
    print('=' * 62)
    srv = ThreadingHTTPServer(('127.0.0.1', port), H)
    srv.serve_forever()
    return port


if __name__ == '__main__':
    if len(sys.argv) < 2:
        cands = find_project_paths()
        if not cands:
            sys.exit('用法: python 工厂/server.py [项目目录名或 project.json]')
        p = cands[0]
        print('未指定课件，自动打开第一套：%s' % os.path.basename(os.path.dirname(p)))
    else:
        p = sys.argv[1]
    serve(p)
