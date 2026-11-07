# -*- coding: utf-8 -*-
"""工厂/photos.py —— 实物照片联网搜索 / 下载

⚠️ 作用域：本模块是**少儿美术课件流水线的内部模块**（供 `pipeline.py` 调用），
   不是通用搜图工具。产出会写进 `项目/<课件>/img/` 与 `图片版权.json`。

核心思路
    实物观察页要的是「真照片」。AI 画的是假照片，还慢（90s）还要钱（¥0.03/张）。
    联网搜 = 真实 + 免费 + 1 秒。搜不到才由 pipeline 退回 AI 生成。

数据源优先级（实测结论，2025-xx 国内网络）
    0. pixnio.com       → CC0 可商用，**唯一能直抓的外网免费图库**（只吃 ASCII 词）
    1. Bing 授权筛选  cn.bing.com / www.bing.com
         · license-L1        → 公有领域（Public Domain），**商用最安全**
         · license-L2_L3_L4  → 可商用（CC 等，需署名时会在 credits 里留来源）
         · 再加 imagesize-large 过滤小图
    2. 360 图片 / 百度图片  —— 中文专有题材（竹笋、马克笔…）命中率更高，但**无授权信息**
    3. 都不行 → 返回 None，pipeline 自动退回 AI 生成

不可用（被墙，别再试）：Wikimedia、Openverse、Google、DuckDuckGo
可连但需 key：Pexels / Unsplash / Pixabay（有 key 可加成，见 LIB_KEYS）

命令行
    python 工厂/photos.py "bamboo shoot" -o out.png --alt alt_dir
    python 工厂/photos.py "竹笋" --list              # 只看候选不下载
    python 工厂/photos.py "panda" -o a.png --no-unknown   # 只用有授权的图
"""
import os
import io
import ssl
import sys
import json
import html
import hashlib
import urllib.parse
import urllib.request
import http.cookiejar

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

_OP = None
_WARM = set()

# 信任等级：数字越小越安全。★ Bing 的授权筛选不可全信（实测把摄图网/alamy
# 这类付费图库也标成「公有领域」），所以只对**已知免费图库整站**给最高信任。
TRUST_FREE = 0     # 已知免费/公版图库（pixabay、publicdomainpictures…）→ 商用安全
TRUST_FILTER = 1   # Bing 授权筛选命中，但域名不在白名单 → **需人工核对**
TRUST_UNKNOWN = 2  # 国内源，无任何授权信息 → 自用可以，售卖慎用
TRUST_NAME = {TRUST_FREE: '免费图库·可商用',
              TRUST_FILTER: 'Bing筛选·待核对',
              TRUST_UNKNOWN: '授权未知·慎用'}


# ============================================================ 视觉复核
# 为什么必须有这一步：实测「white rabbit sitting」这类明确词，Bing/百度命中率
# 很高，但 pixnio 搜不到时会吐回**随机图池**（抓到过圣诞挂球、公鸡、相机快门）。
# 光靠关键词、域名、尺寸**永远无法判断图里到底是什么**。所以下完以后，
# 让视觉模型看一眼，只说一句「这是不是 X」，不对题的当场淘汰。
#
# 成本：单张 ~¥0.0014（60 张约 ¥0.08），比一张 AI 图（¥0.03）还便宜。
_VCFG = None
_VCACHE = {}
_VCACHE_LK = None


def _vcfg():
    """从 pi 的 provider 配置里找一个支持图像输入的模型。找不到返回 False。

    ⚠ 必须加锁：多线程同时调时，不能让"正在算"的中间态（False 哨兵）被别的线程读到，
      否则会出现随机几个槽位报 no-vision 的间歇性 bug。
    """
    global _VCFG, _VCACHE_LK
    import threading
    if _VCACHE_LK is None:
        _VCACHE_LK = threading.Lock()
    if _VCFG is not None:
        return _VCFG
    with _VCACHE_LK:
        if _VCFG is not None:          # 双重检查：锁内再确认一次
            return _VCFG
        cfg = False
        try:
            if os.environ.get('VISION_BASE') and os.environ.get('VISION_KEY'):
                cfg = (os.environ['VISION_BASE'].rstrip('/'), os.environ['VISION_KEY'],
                       os.environ.get('VISION_MODEL', 'deepseek/deepseek-v4-flash'))
            else:
                p = os.path.join(os.path.expanduser('~'), '.pi', 'agent', 'models.json')
                d = json.load(open(p, encoding='utf-8'))
                for _n, pr in (d.get('providers') or {}).items():
                    if not (pr.get('apiKey') and pr.get('baseUrl')):
                        continue
                    vis = [m['id'] for m in (pr.get('models') or [])
                           if 'image' in (m.get('input') or [])]
                    if not vis:
                        continue
                    want = os.environ.get('VISION_MODEL')
                    cfg = (pr['baseUrl'].rstrip('/'), pr['apiKey'],
                           want if want in vis else vis[0])
                    break
        except Exception:
            cfg = False
        _VCFG = cfg
        return _VCFG


def vcheck(png_bytes, subject, timeout=90):
    """看一眼：图里最主要的东西是不是「subject」？

    返回 (ok, seen)：
        (True,  '一只白兔')      → 对题，可用
        (False, '圣诞挂球')      → 不对题，淘汰
        (None,  'no-vision')     → 复核不可用，调用方应放行（不要把功能搞死）
    """
    cfg = _vcfg()
    if not cfg or not subject:
        return None, 'no-vision'
    key_md5 = hashlib.md5(png_bytes[:4096]).hexdigest() + '|' + subject
    if key_md5 in _VCACHE:
        return _VCACHE[key_md5]
    base, key, model = cfg
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(png_bytes)).convert('RGB')
        im.thumbnail((640, 640))          # 640px 足够判断"是什么"，还省 token
        b = io.BytesIO()
        im.save(b, 'JPEG', quality=78)
        url = 'data:image/jpeg;base64,' + __import__('base64').b64encode(
            b.getvalue()).decode()
        q = ('图里最主要的东西是什么？只按这个格式回答两行，不要别的话：\n'
             '看到：<20 字以内，说清是什么>\n'
             '匹配：<是 或 否>（判断它是不是「%s」）' % subject)
        body = json.dumps({'model': model, 'max_tokens': 2400, 'messages': [
            {'role': 'user', 'content': [
                {'type': 'text', 'text': q},
                {'type': 'image_url', 'image_url': {'url': url}}]}]}).encode('utf-8')
        r = urllib.request.Request(base + '/chat/completions', data=body, headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + key,
            'Accept': 'application/json',
            'User-Agent': UA})
        j = json.loads(urllib.request.urlopen(r, timeout=timeout).read().decode('utf-8'))
        t = (j['choices'][0]['message']['content'] or '').strip()
        seen = ''
        for ln in t.splitlines():
            if ln.lstrip().startswith('看到'):
                seen = ln.split('：', 1)[-1] if '：' in ln else ln.split(':', 1)[-1]
                seen = seen.strip()
        # ★ 关键：模型是**推理模型**，token 烧光时会返回空正文（finish_reason=length）。
        #   此时绝不能当成"不匹配" —— 那会把好图误杀。没拿到判定就返回 None（放行）。
        if '匹配' not in t:
            out = (None, 'no-verdict' + ((':' + seen) if seen else ''))
        else:
            ok = ('匹配：是' in t) or ('匹配:是' in t) or ('匹配: 是' in t)
            out = (ok, seen or t.replace('\n', ' ')[:60])
    except Exception as e:
        out = (None, '%s: %s' % (type(e).__name__, str(e)[:60]))
    _VCACHE[key_md5] = out
    return out


def _tier_mix(cands, n):
    """按授权等级**轮转**取样，别让某一层（尤其 pixnio 的随机池）霸占下载名额。

    license 优先仍然有效，但每一层都有机会被下载 + 复核 —— 好图本来多在 Bing/百度。
    """
    tiers = {}
    for c in cands:
        tiers.setdefault(c.get('lic', TRUST_UNKNOWN), []).append(c)
    order = [TRUST_FREE, TRUST_FILTER, TRUST_UNKNOWN]
    picked, i = [], 0
    while len(picked) < n:
        added = False
        for t in order:
            lst = tiers.get(t) or []
            if i < len(lst):
                picked.append(lst[i])
                added = True
                if len(picked) >= n:
                    break
        if not added:
            break
        i += 1
    return picked


def _opener():
    global _OP
    if _OP is None:
        cj = http.cookiejar.CookieJar()
        _OP = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cj),
            urllib.request.HTTPSHandler(context=_CTX))
    return _OP


def _get(url, ref=None, timeout=25):
    h = {'User-Agent': UA, 'Accept': '*/*',
         'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'}
    if ref:
        h['Referer'] = ref
    return _opener().open(urllib.request.Request(url, headers=h),
                          timeout=timeout).read()


def _warm(url):
    """百度必须先访问首页拿 Cookie，否则返回 antiFlag=1 Forbid spider access"""
    if url in _WARM:
        return
    try:
        _get(url, timeout=20)
    except Exception:
        pass
    _WARM.add(url)


def _q(s):
    return urllib.parse.quote(s)


def _txt(b):
    return b.decode('utf-8', 'replace')


# ------------------------------------------------------------- Bing（带授权筛选）
_BING_HOSTS = ('cn.bing.com', 'www.bing.com')


def search_bing(query, n=35, lic=None, host=None, size_large=True):
    """lic: None=不限 / 'L1'=公有领域 / 'L23'=可商用。返回候选（带信任等级）"""
    import re
    out = []
    if lic == 'L1':
        qft, lv = '+filterui:license-L1', TRUST_FILTER
    elif lic == 'L23':
        qft, lv = '+filterui:license-L2_L3_L4', TRUST_FILTER
    else:
        qft, lv = '', TRUST_UNKNOWN
    if size_large:
        qft += '+filterui:imagesize-large' if qft else '+filterui:imagesize-large'

    for hs in ([host] if host else _BING_HOSTS):
        try:
            _warm('https://%s/' % hs)
            ref = 'https://%s/images/search?q=%s' % (hs, _q(query))
            u = ('https://%s/images/async?q=%s&first=1&count=%d&mmasync=1%s'
                 % (hs, _q(query), n, qft))
            h = _txt(_get(u, ref=ref))
            for m in re.finditer(r'class="iusc"[^>]*?m="([^"]+)"', h):
                try:
                    d = json.loads(html.unescape(m.group(1)))
                except Exception:
                    continue
                murl = d.get('murl')
                if not murl or not murl.startswith('http'):
                    continue
                out.append({'url': murl, 'w': 0, 'h': 0,
                            'title': (d.get('t') or '')[:70],
                            'page': d.get('purl') or '', 'src': 'bing',
                            'lic': lv, 'ref': ref})
            if not out:   # 退一步：老式 murl&quot; 抓法
                for m in re.finditer(r'murl&quot;:&quot;(.*?)&quot;', h):
                    url = (m.group(1).replace('&amp;', '&')
                           .replace('\\u002f', '/').replace('\\/', '/'))
                    if url.startswith('http'):
                        out.append({'url': url, 'w': 0, 'h': 0, 'title': '',
                                    'page': '', 'src': 'bing', 'lic': lv,
                                    'ref': ref})
            if out:
                break
        except Exception:
            continue
    return out


# ------------------------------------------------------------- 360 图片
def search_360(query, n=30, **kw):
    out = []
    try:
        u = ('https://image.so.com/j?q=%s&src=srp&sn=0&pn=%d' % (_q(query), n))
        d = json.loads(_txt(_get(u, ref='https://image.so.com/')))
        for it in (d.get('list') or []):
            url = it.get('img') or it.get('https')
            if not url:
                continue
            if url.startswith('http://'):
                url = 'https://' + url[7:]
            out.append({'url': url, 'w': int(it.get('width') or 0),
                        'h': int(it.get('height') or 0),
                        'title': (it.get('title') or '').strip()[:70],
                        'page': it.get('link') or '', 'src': '360',
                        'lic': TRUST_UNKNOWN, 'ref': 'https://image.so.com/'})
    except Exception:
        pass
    return out


# ---------------------------------------------------- pixnio（CC0 免费图库，直抓）
def search_pixnio(query, n=30, **kw):
    """pixnio.com 是 CC0 图库（可商用、无需署名），搜索页可直抓，无需 key。
    实测是唯一能直抓的外网免费图库（pixabay/publicdomainpictures 均 403）

    ⚠ 只接英文关键词：实测 pixnio 对非 ASCII 词（如「黑熊」）会直接
       返回随机/最新图池（垃圾词 zzzqqqxxyy 也能出 48 张），图不对题。
    """
    import re
    if not query.isascii():        # 中文词 → 跳过，交给 Bing/360/百度
        return []
    out = []
    try:
        h = _txt(_get('https://pixnio.com/?s=' + _q(query),
                      ref='https://pixnio.com/'))
        best = {}
        for m in re.finditer(
                r'https://pixnio\.com/free-images/[\w\-./]+\.(?:jpg|jpeg|png)', h):
            url = m.group(0)
            mm = re.search(r'-([\d]+)x([\d]+)\.[a-z]+$', url)
            if mm:
                w, hh = int(mm.group(1)), int(mm.group(2))
                base = url[:mm.start()]
            else:
                w = hh = 0
                base = url.rsplit('.', 1)[0]
            if base not in best or w * hh > best[base]['w'] * best[base]['h']:
                best[base] = {'url': url, 'w': w, 'h': hh}
        for base, d in list(best.items())[:n]:
            out.append({'url': d['url'], 'w': d['w'], 'h': d['h'],
                        'title': base.rsplit('/', 1)[-1][:70], 'page': base,
                        'src': 'pixnio', 'lic': TRUST_FREE,
                        'ref': 'https://pixnio.com/'})
    except Exception:
        pass
    return out


# ------------------------------------------------------------- 百度图片
def search_baidu(query, n=30, **kw):
    out = []
    try:
        _warm('https://image.baidu.com/')
        ref = 'https://image.baidu.com/search/index?tn=baiduimage&word=' + _q(query)
        u = ('https://image.baidu.com/search/acjson?tn=resultjson_com&logid=1&ipn=rj'
             '&ct=201326592&is=&fp=result&word=%s&pn=0&rn=%d&gsm=1e' % (_q(query), n))
        d = json.loads(_txt(_get(u, ref=ref)))
        if d.get('antiFlag'):
            return []
        for it in (d.get('data') or []):
            if not isinstance(it, dict):
                continue
            url = it.get('middleURL') or it.get('thumbURL')
            if not url:
                continue
            if url.startswith('http://'):
                url = 'https://' + url[7:]
            out.append({'url': url, 'w': int(it.get('width') or 0),
                        'h': int(it.get('height') or 0),
                        'title': (it.get('fromPageTitleEnc') or '').strip()[:70],
                        'page': it.get('fromURL') or '', 'src': 'baidu',
                        'lic': TRUST_UNKNOWN, 'ref': 'https://image.baidu.com/'})
    except Exception:
        pass
    return out


# 噪声词：明显不是「实物照片」的
BAD_WORDS = ('gif', '.svg', 'logo', 'icon', 'sprite', 'pngimg', '表情包',
             '矢量', 'iconfont', '剪影', 'silhouette', 'coloring', '涂色',
             '简笔画', '卡通', '素材网', '千库', '昵图', '壁纸', 'avatar',
             'clipart', 'vector', 'watermark')
BAD_HOSTS = ('bing.com/th', 'gstatic', 'lookaside', 'favicon',
             'qhimgs', '/t01', '/t02', '/t04')

# ★ 图库站黑名单：Bing 的授权筛选会混进这些站的「水印小样」，一律剔除
STOCK_HOSTS = (
    'alamy', 'shutterstock', 'freepik', 'istockphoto', 'gettyimages', 'dreamstime',
    '123rf', 'stock.adobe', 'depositphotos', 'vecteezy', 'canstockphoto',
    'colourbox', 'bigstock', 'stockfresh', 'pixta', 'pond5', 'envato',
    'creativemarket', 'rf123', 'agefotostock', 'westend61', 'imagebroker',
    'turbosquid', 'zcool', '51yuansu', 'seeklogo', 'vectorstock',
    'freepngimg', 'svgsilh', 'pngwing', 'pngtree', 'lovepik', 'hiclipart',
    'clipartmax', 'kindpng', 'pngitem', 'cleanpng', 'pngall', 'stickpng',
    # 国内付费图库（Bing 授权筛也会误标成公版，必须剔）
    '699pic', 'tuchong', 'veer.com', '58pic', 'nipic', 'photophoto', 'huitu',
    'tukuppt', 'sucai999', 'aigei', 'zhituwang', 'tooopen', 'sucaijiang',
    '51yuansu', 'ooopic', 'ibaotu', '51miz', 'pixmiller', 'chuangkit',
    'gaoding', 'uisdc', 'zitiguanjia', '!detail', '!middle', '!w',
    # 电商产品图（1688/淘宝/京东 主图，不适合做课件）
    'alicdn', '1688.com', 'taobao', 'tmall', 'jd.com', '360buyimg',
    'aliexpress', 'amazon.', 'ebay.', 'alibaba.com', 'made-in-china',
)

# ★ 已知免费/公版图库：优先选（授权干净、无水印、画质高）
GOOD_HOSTS = (
    'cdn.pixabay.com', 'pixabay.com', 'img.rawpixel.com', 'images.rawpixel.com',
    'publicdomainpictures.net', 'pixnio.com', 'goodfreephotos.com', 'peakpx.com',
    'geograph.org.uk', 'openclipart.org', 'freeimages', 'stocksnap.io',
    'burst.shopify', 'kaboompics', 'picjumbo', 'lifeofpix', 'skuawk',
    'publicdomainfiles', 'pdphoto', 'freerangestock', 'negativespace',
    'commons.wikimedia', 'upload.wikimedia', 'picsum.photos',
)


def _host(u):
    i = u.find('://')
    if i < 0:
        return ''
    s = u[i + 3:]
    return s.split('/')[0].split(':')[0].lower()


def _is_good(u):
    h = _host(u)
    return any(g in h for g in GOOD_HOSTS)


def _ok(c, min_w, min_h, max_ratio=2.8):
    u = (c.get('url') or '').lower()
    if not u.startswith('http'):
        return False
    if any(b in u for b in BAD_WORDS) or any(b in u for b in BAD_HOSTS):
        return False
    if any(s in u for s in STOCK_HOSTS):      # 水印图库站，直接毙
        return False
    t = (c.get('title') or '').lower()
    if any(b in t for b in BAD_WORDS):
        return False
    w, h = c.get('w', 0), c.get('h', 0)
    if w and h:
        if w < min_w or h < min_h:
            return False
        r = w / float(h)
        if r > max_ratio or r < 1.0 / max_ratio:
            return False
    return True


def search(queries, per_src=30, min_w=560, min_h=420, log=None,
           allow_unknown=True, budget=70, workers=6):
    """多关键词 × 多数据源 **并行** 搜 → 去重 → 授权优先、再按尺寸排序

    串行发 12 次请求要 100 秒，并行（6 线程）约 20 秒。
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if isinstance(queries, str):
        queries = [queries]
    # 百度/Bing 必须先拿 Cookie，先串行热一下，避免多线程重复热场
    try:
        _warm('https://cn.bing.com/')
    except Exception:
        pass
    if allow_unknown:
        try:
            _warm('https://image.baidu.com/')
        except Exception:
            pass

    srcs = [('pixnio', search_pixnio, {}),
            ('bing公版', search_bing, {'lic': 'L1'}),
            ('bing可商用', search_bing, {'lic': 'L23'})]
    if allow_unknown:
        srcs += [('bing不限', search_bing, {'lic': None}),
                 ('360', search_360, {}),
                 ('baidu', search_baidu, {})]

    seen, out = set(), []

    def add(cands, tag, q):
        for c in cands:
            if not _ok(c, min_w, min_h):
                continue
            if not allow_unknown and c.get('lic', TRUST_UNKNOWN) >= TRUST_FILTER:
                continue
            key = c['url'].split('?')[0]
            if key in seen:
                continue
            seen.add(key)
            if _is_good(c['url']):        # 已知免费图库 → 直接给最高信任
                c['lic'] = TRUST_FREE
            out.append(c)
        if log and cands:
            log('  [搜] %-12s %-14s → %d 条' % (tag, q[:14], len(cands)))

    jobs = [(tag, fn, kw, q) for q in queries for tag, fn, kw in srcs]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fn, q, per_src, **kw): (tag, q)
                for tag, fn, kw, q in jobs}
        for f in as_completed(futs):
            tag, q = futs[f]
            try:
                cands = f.result() or []
            except Exception:
                cands = []
            add(cands, tag, q)

    out.sort(key=lambda c: (c.get('lic', TRUST_UNKNOWN),
                            0 if _is_good(c['url']) else 1,
                            -(c['w'] * c['h'])))
    return out[:budget]


# ------------------------------------------------------------- 下载
def _shrink(png_bytes, max_side, fmt='JPEG'):
    """备选图瘦身：照片存 PNG 太浪费（50 张要 116MB），存 JPEG 只要 ~12MB。
    备选图只给人眼看一眼，被选中后 pick_alt 会转回真 PNG 当主图。"""
    from PIL import Image
    import io as _io
    i = Image.open(_io.BytesIO(png_bytes)).convert('RGB')
    if max(i.size) > max_side:
        k = max_side / float(max(i.size))
        i = i.resize((max(1, round(i.width * k)), max(1, round(i.height * k))),
                     Image.LANCZOS)
    o = _io.BytesIO()
    if fmt == 'JPEG':
        i.save(o, 'JPEG', quality=88, optimize=True, progressive=True)
    else:
        i.save(o, 'PNG', optimize=True)
    return o.getvalue()


def fetch(cand, max_side=2400, min_w=520, min_h=390):
    """下载 + PIL 校验 + 转 RGB + 统一成 PNG bytes。失败返回 None"""
    from PIL import Image
    url = cand['url'] if isinstance(cand, dict) else cand
    ref = cand.get('ref') if isinstance(cand, dict) else None
    try:
        data = _get(url, ref=ref, timeout=12)
    except Exception:
        return None
    if len(data) < 12 * 1024:
        return None
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:
        return None
    if im.width < min_w or im.height < min_h:
        return None
    if im.mode != 'RGB':
        im = im.convert('RGB')
    if max(im.size) > max_side:
        k = max_side / float(max(im.size))
        im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))),
                       Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, 'PNG', optimize=True)
    b = buf.getvalue()
    return b, im.size, hashlib.md5(b).hexdigest()


def grab(queries, dst, alt_dir=None, log=print, n_alt=5,
         min_w=560, min_h=420, max_side=2400, alt_side=1600, per_src=30,
         max_try=13, allow_unknown=True, credits=None,
         subject=None, verify=True, only_free=False):
    """搜→下→校验→**视觉复核**→**授权闸门**。第一张合格图写 dst（PNG），其余备用写 alt_dir。

    subject:   这张图"应该是什么"（如 "一只坐着的小兔子"）。给了就开视觉复核，
               不对题的候选当场淘汰。
    only_free: True = 只接受 CC0/免费图库（可商用）的图；没有就返回 None
               → pipeline 回退 AI 生成。**要卖钱的课件应该开这个。**
    返回 (dst 或 None, [备用图路径...])
    """
    if log:
        log('   [图搜] 关键词：%s' % ' / '.join(
            queries if isinstance(queries, list) else [queries]))
    cands = search(queries, per_src=per_src, min_w=min_w, min_h=min_h,
                   log=log, allow_unknown=allow_unknown)
    if not cands:
        if log:
            log('   [图搜] 没有候选（可能全被过滤或没联网）')
        return None, []
    if log:
        nf = sum(1 for c in cands if c['lic'] == TRUST_FREE)
        nfl = sum(1 for c in cands if c['lic'] == TRUST_FILTER)
        log('   [图搜] 候选 %d 个（免费图库·可商用 %d / Bing筛选·待核对 %d / 授权未知 %d）'
            % (len(cands), nf, nfl, len(cands) - nf - nfl))

    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    if alt_dir:
        os.makedirs(alt_dir, exist_ok=True)

    # ★ 并行下载（纯 I/O，4 线程足够）：串行下 13 张要 100s，并行约 25s
    from concurrent.futures import ThreadPoolExecutor, as_completed
    # 分层轮转取下载名额，否则 pixnio 的随机池会把 Bing/百度的好图全挤掉
    pool = _tier_mix(cands, max_try)
    res = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fetch, c, max_side, min_w, min_h): i
                for i, c in enumerate(pool)}
        for f in as_completed(futs):
            try:
                r = f.result()
            except Exception:
                r = None
            if r:
                res[futs[f]] = (r, pool[futs[f]])

    got, seen_md5 = [], set()
    for i in sorted(res):                      # 保持候选优先级顺序
        b, size, md5 = res[i][0]
        c = res[i][1]
        if md5 in seen_md5:
            continue
        seen_md5.add(md5)
        got.append((b, size, c))
        if log:
            log('   [下] %dx%d %-6s %s' % (size[0], size[1], c['src'],
                                           TRUST_NAME.get(c['lic'], '?')))
        if len(got) > n_alt + 2:      # 多下几张，给复核留淘汰余地
            break

    if not got:
        if log:
            log('   [图搜] %d 个候选全部下载/校验失败' % len(pool))
        return None, []

    # ★ 视觉复核：不对题的当场淘汰。这是"抓到圣诞挂球冒充老鼠"的根治手段。
    if verify and subject and _vcfg():
        with ThreadPoolExecutor(max_workers=6) as ex:
            futs = {ex.submit(vcheck, g[0], subject): i for i, g in enumerate(got)}
            verd = {}
            for f in as_completed(futs):
                try:
                    verd[futs[f]] = f.result()
                except Exception:
                    verd[futs[f]] = (None, 'err')
        kept, dropped = [], 0
        for i, g in enumerate(got):
            okk, seen = verd.get(i, (None, '?'))
            if okk is False:
                dropped += 1
                if log:
                    log('   [验] ✗ 淘汰（实际是：%s）' % seen)
            else:
                if log:
                    log('   [验] %s %dx%d %-6s → %s'
                        % ('✓' if okk else '⚠ 复核不可用，放行',
                           g[1][0], g[1][1], g[2]['src'], seen))
                kept.append(g)
        if dropped and log:
            log('   [验] 视觉复核淘汰 %d 张不对题的' % dropped)
        got = kept
        if not got:
            if log:
                log('   [图搜] 所有候选都没通过视觉复核 → 放弃网搜')
            return None, []
    elif verify and subject and log:
        log('   [验] 没找到可用的视觉模型，跳过复核（有抓错图的风险）')

    # ★ 授权闸门：要卖钱的课件只敢用 CC0/免费图库；其余一律不要，让 pipeline 退回 AI。
    #   实测 Bing 的「授权筛选」不可信（把摄图网也标成公版），360/百度则根本没有授权信息。
    # ★ 授权闸门：要卖钱的课件只敢用 CC0/免费图库当主图；其余不当主图，让 pipeline 退回 AI。
    #   实测 Bing 的「授权筛选」不可信（把摄图网也标成公版），360/百度则根本没有授权信息。
    #   ↓ 但**对题但授权不明**的真照片不应该白白丢掉——降级存成备选图，
    #     用户在审图台里能看见、能自己判断（每张都带 license 标注）。
    alt_only = False
    alt_extra = []
    if only_free:
        free = [g for g in got if g[2].get('lic') == TRUST_FREE]
        if not free:
            alt_only = True
            if log:
                log('   [授权] 复核通过的图都不是可商用授权（%s）→ 不采用为主图（退回 AI），'
                    '但降级存为备选图供人工取舍'
                    % '、'.join(sorted({TRUST_NAME.get(g[2].get('lic'), '?') for g in got})))
        else:
            # ★ 复核通过但授权待定的，不当主图，但**不能丢**：进备选池
            alt_extra = [g for g in got if g[2].get('lic') != TRUST_FREE]
            if alt_extra and log:
                log('   [授权] 主图只取可商用（%d 张）；另 %d 张对题图授权待核对，降级为备选'
                    % (len(free), len(alt_extra)))
            got = free

    base = os.path.splitext(os.path.basename(dst))[0]

    def record(c, size, picked=False):
        if credits is not None:
            credits.append({'slot': base, 'source': c['src'],
                            'license': TRUST_NAME.get(c['lic'], '?'),
                            'url': c['url'], 'page': c.get('page', ''),
                            'title': c.get('title', ''),
                            'size': '%dx%d' % size, 'query': c.get('q', ''),
                            'picked': bool(picked)})

    alts = []
    if alt_only:
        # 不写主图，只把这批「对题但授权待定」的真照片存成备选
        if not alt_dir:
            return None, []
        names = ['%s_%02d.jpg' % (base, i) for i in range(1, len(got) + 1)]
        for nm, (b, size, c) in zip(names, got[:max(n_alt, len(got))]):
            p = os.path.join(alt_dir, nm)
            with open(p, 'wb') as f:
                f.write(_shrink(b, alt_side, 'JPEG'))
            alts.append(p)
            record(c, size, picked=False)
        if log and alts:
            log('   [备] 另存 %d 张对题真照片作备选（授权待核对，用不用由你定）' % len(alts))
    else:
        b0, s0, c0 = got[0]
        with open(dst, 'wb') as f:
            f.write(b0)
        record(c0, s0, picked=True)
        if log:
            log('   [选] %s ← %dx%d %s（%s）' % (os.path.basename(dst), s0[0], s0[1],
                                                 c0['src'],
                                                 TRUST_NAME.get(c0['lic'], '?')))
            if c0['lic'] >= TRUST_FILTER:
                log('   [注意] 这张图**授权需人工核对**（%s），商用前请自己看一眼来源：%s'
                    % (TRUST_NAME.get(c0['lic'],'?'), c0['url'][:78]))
        if alt_dir:
            for i, (b, size, c) in enumerate((got[1:] + alt_extra)[:n_alt], 1):
                p = os.path.join(alt_dir, '%s_%02d.jpg' % (base, i))
                # 备选图只用于「人眼看一眼挑一张」，不需要 2400px 原图：
                # 存 1600px 能把 img_alt/ 从 116MB 压到 ~40MB（被选中后还会再压成供货版）
                with open(p, 'wb') as f:
                    f.write(_shrink(b, alt_side, 'JPEG'))
                alts.append(p)
                record(c, size, picked=False)
            if log and alts:
                log('   [备] 另存 %d 张备选图(JPEG)，可在审图台里一键换' % len(alts))
    # ★ 版权 sidecar：把每个槽位的来源写进 img_alt/<slot>.credits.json
    #   否则重跑一次、或忘了写汇总清单，图片出处就追不回来了（卖钱课件风险很大）
    if alt_dir and credits is not None:
        try:
            side = os.path.join(alt_dir, '%s.credits.json' % base)
            json.dump([c for c in credits if c.get('slot') == base],
                      open(side, 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=2)
        except Exception:
            pass
    if alt_only:
        return None, alts
    return dst, alts


# ------------------------------------------------------------- CLI
if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    import argparse
    ap = argparse.ArgumentParser(description='实物照片联网搜索/下载')
    ap.add_argument('query', nargs='+', help='关键词，多个会依次尝试')
    ap.add_argument('-o', '--out', help='主图输出路径（.png）')
    ap.add_argument('--alt', help='备选图目录')
    ap.add_argument('-n', '--alt-n', type=int, default=5)
    ap.add_argument('--list', action='store_true', help='只列候选，不下载')
    ap.add_argument('--no-unknown', action='store_true',
                    help='只使用带商用授权的图（排除「授权未知」）')
    ap.add_argument('--min-w', type=int, default=560)
    ap.add_argument('--min-h', type=int, default=420)
    a = ap.parse_args()
    au = not a.no_unknown

    if a.list:
        cs = search(a.query, min_w=a.min_w, min_h=a.min_h, log=print,
                    allow_unknown=au)
        print('候选 %d 个：' % len(cs))
        for c in cs[:30]:
            print('  %-10s %5dx%-5d %-22s %s'
                  % (TRUST_NAME.get(c['lic'], '?'), c['w'], c['h'],
                     (c['title'] or '')[:22], c['url'][:66]))
        sys.exit(0)

    if not a.out:
        ap.error('要么给 -o，要么用 --list')
    cred = []
    p, alts = grab(a.query, a.out, alt_dir=a.alt, n_alt=a.alt_n,
                   allow_unknown=au, credits=cred)
    if p:
        print('✔ 主图：%s (%.0f KB)' % (p, os.path.getsize(p) / 1024))
        for x in alts:
            print('  备选：%s (%.0f KB)' % (x, os.path.getsize(x) / 1024))
        print('  版权：%s' % json.dumps(cred, ensure_ascii=False)[:400])
    else:
        print('✘ 没搜到可用真图')
        sys.exit(1)
