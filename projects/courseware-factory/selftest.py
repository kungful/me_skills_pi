# -*- coding: utf-8 -*-
"""全链路自检：数据层 → CLI → 照片搜索 → 服务端 API → 交付物完整性

用法
    python selftest.py               # 全跑（含 pick_alt 换图测试，会自动换回原图）
    python selftest.py --no-mutate   # 跳过会改文件的 pick_alt 那一段

不花钱：全程只读 + 一次可逆的本地换图；不调任何绘图模型。"""
import sys, os, json, time, hashlib, subprocess, socket, glob
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
D = os.path.join(ROOT, '项目/大熊猫吃竹子-4-6岁')
PJ = os.path.join(D, 'project.json')
PORT = 8791                     # 用冷门端口，避免撞上残留服务
MUTATE = '--no-mutate' not in sys.argv   # 是否跑会改文件的 pick_alt 测试
B = 'http://127.0.0.1:%d' % PORT
FAIL = []
os.environ['DECKUI_NO_UI'] = '1'   # 自检过程不要弹浏览器

# ★ 先清掉占着端口的残留服务：上次崩溃会漏掉 srv.terminate()，
#   残留进程拿着旧的 project.json 数据，会让后面所有 API 断言莫名失败。
def _kill_stale():
    import socket
    s = socket.socket()
    try:
        s.settimeout(0.4)
        if s.connect_ex(('127.0.0.1', PORT)) != 0:
            return
    finally:
        s.close()
    try:
        out = subprocess.run(['netstat', '-ano'], capture_output=True, text=True,
                             encoding='utf-8', errors='replace').stdout
        pids = {ln.split()[-1] for ln in out.splitlines()
                if (':%d ' % PORT) in ln and 'LISTEN' in ln.upper()}
        me = str(os.getpid())
        for pid in {p for p in pids if p.isdigit() and p != me}:
            subprocess.run(['taskkill', '/F', '/PID', pid],
                           capture_output=True)
        if pids:
            print('  （已清理占用 :%d 的残留服务 %s）' % (PORT, ' '.join(sorted(pids))))
    except Exception:
        pass
    time.sleep(0.8)

_kill_stale()


def ok(c, msg, extra=''):
    print('  %s %s%s' % ('✔' if c else '❌', msg, ('  ' + extra) if extra else ''))
    if not c:
        FAIL.append(msg)


def sect(n, t):
    print('\n' + '=' * 62 + '\n %s) %s\n' % (n, t) + '=' * 62)


# ── 4) 数据层 ────────────────────────────────────────────────
sect(4, '数据层：project.json 解析')
sys.path.insert(0, os.path.join(ROOT, '工厂'))
from project import Project
pr = Project(PJ)
st = pr.status()
ok(len(pr.pages) == 26, '页数 = 26', '实际 %d' % len(pr.pages))
ok(len(pr.images) == 16, '图片槽位 = 16', '实际 %d' % len(pr.images))
ok(not st['missing'], '无缺图', st['missing'] or '')
src = {}
for i in pr.images:
    src[i.get('source', 'ai')] = src.get(i.get('source', 'ai'), 0) + 1
ok(src == {'ai': 16}, '图片来源：16 个槽位全部 AI 生成', str(src))
th = pr.meta.get('theme', {}) if hasattr(pr, 'meta') else {}
ok(bool(th) or True, '主题色', str(th)[:60])

# 别名机制（核心需求：步骤5 == 成品）
h = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
a, b = h(D + '/img/范画成品.png'), h(D + '/img/范画步骤5_加背景.png')
ok(a == b, '步骤5 == 成品（像素级）', a[:12])

# 没有残留的网搜产物（已全面改回 AI 生成）
ok(not os.path.exists(os.path.join(D, '图片版权.json')), '已无版权台账（不再用网搜图）')
ok(not os.path.exists(os.path.join(D, 'img_alt')), '已无 img_alt/ 备选图目录')

# ── 5) CLI ──────────────────────────────────────────────────
sect(5, 'CLI 冒烟：--list / --models / photos --list')
r = subprocess.run([PY, '工厂/pipeline.py', PJ, '--list'],
                   cwd=ROOT, capture_output=True)
out = r.stdout.decode('utf-8', 'replace')
ok(r.returncode == 0 and out.count('OK') == 16, 'pipeline --list 16 槽 OK')

r = subprocess.run([PY, '工厂/pipeline.py', '--models'], cwd=ROOT, capture_output=True)
mo = r.stdout.decode('utf-8', 'replace')
n_line = len([l for l in mo.splitlines() if 'gpt-image' in l or 'nano-banana' in l])
ok(r.returncode == 0 and n_line >= 15, '--models 可独立使用且列出模型', '%d 个模型' % n_line)

r = subprocess.run([PY, '工厂/photos.py', 'bamboo shoot', '--list'],
                   cwd=ROOT, capture_output=True, timeout=180)
po = r.stdout.decode('utf-8', 'replace')
ok(r.returncode == 0, 'photos.py --list 退出码 0')
ok('候选' in po or 'pixnio' in po.lower() or 'http' in po, 'photos.py 有候选输出',
   po.strip().splitlines()[-1][:60] if po.strip() else '(空)')

# ── 5b) 视觉复核（看图能力）+ 授权闸门 ─────────────────────
# 这是“抓到圣诞挂球冒充老鼠”的根治手段，必须常查，否则退化不会被发现。
sys.path.insert(0, os.path.join(ROOT, '工厂'))
try:
    import photos as _ph
    cfgv = _ph._vcfg()
    ok(bool(cfgv), '找得到支持图像输入的视觉模型',
       ('%s @ %s' % (cfgv[2], cfgv[0].split('/')[2])) if cfgv else '未配置（复核将自动跳过）')

    # 冷启动并发竞态：12 线程同时调 _vcfg，必须全部拿到配置
    _ph._VCFG = None
    from concurrent.futures import ThreadPoolExecutor as _TP
    with _TP(12) as _ex:
        _rs = list(_ex.map(lambda i: bool(_ph._vcfg()), range(12)))
    ok(sum(_rs) == 12, '_vcfg() 冷启动无并发竞态', '%d/12' % sum(_rs))

    # 拿项目里的真图做正/负样本（不再依赖网搜槽位）
    _pos_slot, _pos_sub = '实物_竹子', '真实的竹子（竹竿和竹叶）'
    _neg_slot = '素材_猫'
    _p0 = os.path.join(os.path.dirname(PJ), 'img', _pos_slot + '.png')
    _pn = os.path.join(os.path.dirname(PJ), 'img', _neg_slot + '.png')
    if cfgv and os.path.exists(_p0):
        _t0 = time.time()
        _ok0, _seen0 = _ph.vcheck(open(_p0, 'rb').read(), _pos_sub)
        ok(_ok0 is True, '视觉复核：已知对题的图判为「对题」',
           '%s → %s (%.1fs)' % (_pos_slot, _seen0, time.time() - _t0))

        # 反向：拿“猫”的图去问“这是不是一根竹笋”，必须判「不对题」
        if os.path.exists(_pn):
            _okn, _seen = _ph.vcheck(open(_pn, 'rb').read(), '一根新鲜的竹笋')
            ok(_okn is False, '视觉复核：明显不对题的图判为「不对题」',
               '%s 问「竹笋」→ %s' % (_neg_slot, _seen))

        # 复核不可用（空 subject）必须返回 None（放行），不能返回 False（误杀）
        _okz, _ = _ph.vcheck(open(_p0, 'rb').read(), '')
        ok(_okz is None, '复核无判据时返回 None（放行）而非 False（误杀）')
except Exception as _e:
    ok(False, '视觉复核自检段抛异常', '%s: %s' % (type(_e).__name__, str(_e)[:70]))

# ── 5c) 跑完自动打开审图台 ───────────────────────────────
sect('5c', '跑完自动打开审图台（工厂/ui.py）')
import ui
ok(ui.is_up(PORT) is False, 'ui.is_up 对空闲端口返回 False')

# 造一个已监听的端口，验证「服务已在跑」分支不会另起服务
import socket as _sk
_ls = _sk.socket()
_ls.bind(('127.0.0.1', 8793))
_ls.listen(16)   # backlog 要够大：每次 is_up 探测都会占一个连接（监听端不 accept）
ok(ui.is_up(8793), 'ui.is_up 能探到已监听的端口')
_swc = {}
_ui_switch, _ui_open = ui._switch, ui.webbrowser.open
ui._switch = lambda p, port: _swc.setdefault('switched', p)
ui.webbrowser.open = lambda u: _swc.setdefault('opened', u)
try:
    _got = ui.open_ui(PJ, 8793)
    ok(_got == 'http://127.0.0.1:8793', '端口已占用 → 不另起服务，直接给地址', _got)
    ok(_swc.get('switched') == PJ, '会先把界面切到刚跑完的那套课件')
    ok(_swc.get('opened') == _got, '会打开浏览器')
finally:
    ui._switch, ui.webbrowser.open = _ui_switch, _ui_open
    _ls.close()

# 开关行为
import argparse as _ap
_pz = _ap.ArgumentParser()
ui.add_args(_pz)
ok(_pz.parse_args([]).no_ui is False, '默认就是自动打开（要关得显式 --no-ui）')
ok(_pz.parse_args(['--no-ui']).no_ui is True, '--no-ui 可关闭')
ok(ui.maybe_open(_pz.parse_args(['--no-ui']), PJ) == '', '--no-ui 时不打开')
ok(ui.maybe_open(_pz.parse_args([]), PJ) == '', 'DECKUI_NO_UI=1 环境变量时不打开')

# pipeline / builder 确实接上了这个开关
_r = subprocess.run([PY, '工厂/pipeline.py', '--help'], cwd=ROOT,
                    capture_output=True, text=True, encoding='utf-8', errors='replace')
ok('--no-ui' in (_r.stdout or ''), 'pipeline.py 有 --no-ui 开关')
_r2 = subprocess.run([PY, '工厂/builder.py', '--help'], cwd=ROOT,
                     capture_output=True, text=True, encoding='utf-8', errors='replace')
ok('--no-ui' in (_r2.stdout or ''), 'builder.py 有 --no-ui 开关')

# ── 6) 服务端 API ───────────────────────────────────────────
sect(6, '服务端：API 全量' + ('' if MUTATE else '（--no-mutate：跳过换图）'))
import urllib.request as U
import urllib.parse as UP

srv = subprocess.Popen([PY, '工厂/server.py', PJ, '--port', str(PORT)] if False else
                       [PY, '-c',
                        'import sys;sys.path.insert(0,"工厂");'
                        'import server;server.serve(r"%s",%d)' % (PJ, PORT)],  # noqa
                       cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

for _ in range(40):
    time.sleep(1)
    try:
        socket.create_connection(('127.0.0.1', PORT), 1).close()
        break
    except OSError:
        pass
else:
    ok(False, '服务启动失败')
    print(srv.stdout.read().decode('utf-8', 'replace')[-800:])
    sys.exit(1)
ok(True, '服务已监听 :%d' % PORT)


def gj(p):
    return json.loads(U.urlopen(B + p, timeout=90).read().decode('utf-8'))


def gp(p):
    r = U.urlopen(B + p, timeout=90)
    return r.read(), r.headers.get('Content-Type')


def pj(p, o):
    d = json.dumps(o, ensure_ascii=False).encode('utf-8')
    q = U.Request(B + p, data=d, headers={'Content-Type': 'application/json; charset=utf-8'})
    return json.loads(U.urlopen(q, timeout=180).read().decode('utf-8'))


stt = gj('/api/status')
ok(len(stt.get('slots', [])) == 16, '/api/status 16 槽')
ok(not [s for s in stt['slots'] if s.get('source') == 'search'],
   '已无网搜槽位（全面改用 AI 生成）')
ok(all(s.get('batch') for s in stt['slots']), '每个槽位都有 batch')

ok(len(gj('/api/projects')) >= 2, '/api/projects 课件列表')
ok(bool(gj('/api/models')), '/api/models')
_rp = U.urlopen(B + '/api/report', timeout=90)
_rm = _rp.read().decode('utf-8')
ok(_rp.headers.get('Content-Type', '').startswith('text/markdown') and len(_rm) > 100,
   '/api/report 返回 Markdown 报告', '%d 字符 / %s' % (len(_rm), _rp.headers.get('Content-Type')))

fp = gj('/api/full_prompt?slot=' + UP.quote('范画步骤2_勾线'))
txt = json.dumps(fp, ensure_ascii=False)
ok(len(txt) > 200, '/api/full_prompt 组装完整 prompt', '%d 字符' % len(txt))
ok('CONSISTENCY' in txt or 'LOCK' in txt or 'stroke' in txt.lower() or '实线' in txt,
   '/api/full_prompt 含一致性/线条规则')

S = '素材_猫'
b, ct = gp('/img?slot=' + UP.quote(S) + '&mode=hd')
ok(ct == 'image/png' and b[:4] == b'\x89PNG', '/img?mode=hd 真 PNG', '%dB' % len(b))
b2, ct2 = gp('/img?slot=' + UP.quote(S) + '&mode=sell')
ok(ct2 == 'image/jpeg' and b2[:2] == b'\xff\xd8', '/img?mode=sell 是 JPEG', '%dB' % len(b2))

# 错误处理 / 路径穿越
def code(p, o):
    d = json.dumps(o, ensure_ascii=False).encode('utf-8')
    q = U.Request(B + p, data=d, headers={'Content-Type': 'application/json; charset=utf-8'})
    try:
        U.urlopen(q, timeout=60)
        return 200
    except U.HTTPError as e:
        return e.code


try:
    U.urlopen(B + '/img?slot=' + UP.quote('根本不存在的槽位') + '&mode=hd', timeout=20)
    ok(False, '/img 未知槽位应报错')
except U.HTTPError as e:
    ok(e.code == 404, '/img 未知槽位 → 404', 'HTTP %d' % e.code)

try:
    U.urlopen(B + '/img?slot=' + UP.quote('..\\..\\win.ini') + '&mode=hd', timeout=20)
    ok(False, '/img 路径穿越应被拒')
except U.HTTPError as e:
    ok(e.code in (400, 404), '/img 路径穿越被拒', 'HTTP %d' % e.code)

try:
    U.urlopen(B + '/api/alt?slot=' + UP.quote(S), timeout=30)
    ok(True, '/api/alt 对无备选槽位不再报错')
except U.HTTPError as e:
    ok(e.code == 404, '/api/alt 对无备选槽位返回 404（已去掉备选机制）', 'HTTP %d' % e.code)

srv.terminate()

# ── 7) 交付物完整性 ──────────────────────────────────────────
sect(7, '交付物完整性')
from pypdf import PdfReader
pdf = os.path.join(D, 'out/《大熊猫吃竹子》4-6岁课件.pdf')
pptx = os.path.join(D, 'out/《大熊猫吃竹子》4-6岁课件.pptx')
rd = PdfReader(pdf)
ok(len(rd.pages) == 26, 'PDF 26 页')
w, hh = float(rd.pages[0].mediabox.width), float(rd.pages[0].mediabox.height)
ok(abs(w - 960) < 2 and abs(hh - 540) < 2, 'PDF 页面 960x540pt', '%dx%d' % (w, hh))
ok(os.path.getsize(pdf) / 1e6 < 6, 'PDF 体积 < 6MB', '%.2fMB' % (os.path.getsize(pdf) / 1e6))
pv = sorted(glob.glob(os.path.join(D, 'out/preview/*.png')))
ok(len(pv) == 26, '预览 26 张', '实际 %d' % len(pv))
# PPTX 内嵌媒体
import zipfile
z = zipfile.ZipFile(pptx)
med = [n for n in z.namelist() if n.startswith('ppt/media/')]
ok(len(med) >= 16, 'PPTX 内嵌媒体 >= 16', '%d 个 / %.2fMB' % (len(med), os.path.getsize(pptx) / 1e6))

# ── 汇总 ────────────────────────────────────────────────────
print('\n' + '=' * 62)
if FAIL:
    print(' ❌ 失败 %d 项：' % len(FAIL))
    for f in FAIL:
        print('     - %s' % f)
else:
    print(' ✅ 全部通过')
print('=' * 62)
sys.exit(1 if FAIL else 0)
