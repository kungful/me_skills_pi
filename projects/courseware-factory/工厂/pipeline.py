# -*- coding: utf-8 -*-
"""
课件工厂 · 出图流水线
- 按 project.json 生成，天然支持 断点续跑 / 单张重跑 / 分批次指定模型
- 参考图自动串链（步骤N 引用 步骤N-1），保证同一只主角、同一构图
"""
import os, sys, subprocess, shutil, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from project import Project

GRSAI = os.path.join(os.path.expanduser('~'), '.pi', 'agent', 'skills',
                     'grsai-image-2-5', 'scripts', 'grsai.py')
NANO = os.path.join(os.path.expanduser('~'), '.pi', 'agent', 'skills',
                    'grsai-nano-banana', 'scripts', 'nano_banana.py')
PY = sys.executable
DEF = dict(model='gpt-image-2.5', quality='high', aspect='1536x1024')

# ============ 模型目录：cli=grsai(gpt-image系) / nano(nano-banana系) ============
# price = 每次调用的人民币参考价（积分/20000）
CATALOG = {
    # --- gpt-image 系（支持 WxH 尺寸 + quality）---
    'gpt-image-2.5':          dict(cli='grsai', price=0.03,  note='默认。1K，质量可用 high'),
    'gpt-image-2.5-flare':    dict(cli='grsai', price=0.10,  note='支持 1K/2K/4K，质量 low/medium/high'),
    'gpt-image-2.5-sunburst': dict(cli='grsai', price=0.12,  note='支持到 xhigh/max，最贵画质最好'),
    'gpt-image-2':            dict(cli='grsai', price=0.03,  note='老版 2.5 前代，仅 1K'),
    'gpt-image-2-vip':        dict(cli='grsai', price=0.10,  note='VIP 通道，支持透明背景'),
    # --- nano-banana 系（用 --size 1K/2K/4K + 比例 a:b）---
    'nano-banana-2-lite':     dict(cli='nano', price=0.022, size='1K', note='最便宜，适合素材照片'),
    'nano-banana-fast':       dict(cli='nano', price=0.022, size='1K', note='特价版，编辑能力强'),
    'nano-banana-2':          dict(cli='nano', price=0.06,  size='2K', note='稳定，1K/2K/4K 同价'),
    'nano-banana-pro':        dict(cli='nano', price=0.09,  size='2K', note='gemini-3-pro，稳定性最好'),
    'nano-banana-2-cl':       dict(cli='nano', price=0.30,  size='1K', note='稳定通道 1K'),
    'nano-banana-2-2k-cl':    dict(cli='nano', price=0.45,  size='2K', note='稳定通道 2K'),
    'nano-banana-2-4k-cl':    dict(cli='nano', price=0.65,  size='4K', note='稳定通道 4K'),
    'nano-banana-pro-cl':     dict(cli='nano', price=0.50,  size='1K', note='pro 稳定通道 1K'),
    'nano-banana-pro-vip':    dict(cli='nano', price=0.50,  size='2K', note='pro 高成本通道 1K/2K'),
    'nano-banana-pro-4k-vip': dict(cli='nano', price=0.90,  size='4K', note='pro 高成本通道 4K'),
}

# 画布尺寸(WxH) -> nano-banana 的 a:b 比例
ASPECT_MAP = {'1536x1024': '3:2', '1024x1536': '2:3', '1024x1024': '1:1',
              '1536x864': '16:9', '864x1536': '9:16', '1344x1024': '4:3', '1024x1344': '3:4'}


def model_info(m):
    return CATALOG.get(m, dict(cli='grsai', price=None, note='未登记'))


def build_cmd(model, prompt_file, out, refs, quality=None, aspect=None, size=None):
    """根据模型路由到对应 CLI"""
    info = model_info(model)
    if info['cli'] == 'nano':
        ratio = ASPECT_MAP.get(aspect or DEF['aspect'], '3:2')
        cmd = [PY, NANO, 'gen', '-p', prompt_file, '--model', model,
               '--size', size or info.get('size', '1K'), '--aspect', ratio,
               '--out', out, '--timeout', '600', '--quiet']
    else:
        cmd = [PY, GRSAI, 'gen', '-p', prompt_file, '--model', model,
               '--quality', quality or 'high', '--aspect', aspect or DEF['aspect'],
               '--out', out, '--timeout', '600']
    if refs:
        cmd += ['-r'] + list(refs)
    return cmd


def build_prompt(proj, im, refs=None):
    parts = []
    if im.get('lock') and proj.lock:
        parts.append(proj.lock)
    if proj.common.get('style'):
        parts.append(proj.common['style'])
    if im.get('style'):
        parts.append(im['style'])
    # ★ 线条语言：成品与所有步骤共用同一段文字，从根上消灭“成品毛线/步骤实线”的矛盾
    # （某张图显式写了 "stroke":"" 就是“不用这套线条”，比如水粉版自己有一套）
    stroke = im['stroke'] if 'stroke' in im else proj.common.get('stroke')
    if stroke:
        parts.append(stroke)
    parts.append(im['prompt'])
    if im.get('tail'):
        parts.append(im['tail'])
    # ★ 给参考图编号 + 强制一致性条款
    refs = refs_for(proj, im) if refs is None else refs
    if refs:
        parts.append(REF_BLOCK(proj, im, refs))
    return '\n\n'.join(x.strip() for x in parts if x and x.strip())


def REF_BLOCK(proj, im, refs):
    """把参考图逐张点名，并锁死一致性"""
    order = proj.chain.get('order', [])
    anchor = proj.chain.get('anchor') or (order[0] if order else None)
    s = im.get('slot')
    lines, has_anchor, has_prev = [], False, False
    for n, p in enumerate(refs, 1):
        name = os.path.splitext(os.path.basename(p))[0]
        if name == anchor and s != anchor:
            lines.append('  image %d = %s : THE FINISHED ARTWORK of this lesson. This is the TARGET.' % (n, name))
            has_anchor = True
        elif s in order and order.index(s) > 0 and name == order[order.index(s) - 1]:
            lines.append('  image %d = %s : the PREVIOUS step, continue directly from it.' % (n, name))
            has_prev = True
        else:
            lines.append('  image %d = %s : reference (character design / style to inherit).' % (n, name))
    b = ['REFERENCE IMAGES, in this exact order:', '\n'.join(lines)]
    rules = ['You are given %d reference image(s).' % len(refs)]
    if has_anchor:
        rules.append(
            'THE MOST IMPORTANT RULE: image 1 is the finished artwork. Your drawing must look like it was '
            'made in the very same session with the very same hand as image 1. Copy from image 1, do not '
            're-invent: the exact same line quality and line weight, the same way the outline behaves along the '
            'fur (where it breaks into short soft hairy strokes and where it stays one continuous line), the same '
            'eye / nose / cheek shapes and positions, the same character proportions and pose, the same palette '
            'and the same canvas layout at the same size and position on the paper.')
        rules.append(
            'The ONLY thing that may differ is HOW COMPLETE the drawing is. Do NOT jump ahead: render only '
            'the stage asked for above, and leave everything that comes later still blank paper.')
        if has_prev:
            rules.append(
                'image 2 (the previous step) shows exactly where to start. Keep every mark already present '
                'in it, then add ONLY the new marks described above, in the same hand.')
    else:
        rules.append('Inherit the character design and the drawing style of the reference image(s) exactly; '
                     'do not invent a different character.')
    rules.append('Absolutely no text, no captions, no watermark, no signature, no frame or border anywhere.')
    b.append('CONSISTENCY RULES:\n' + '\n'.join(rules))
    return '\n\n'.join(b)


def refs_for(proj, im):
    """解析参考图。顺序很重要：
       1) 链条锁定的【成品锚点】永远排第一 —— 保证每一步都看得见终点，不会逐级漂移
       2) 再排【上一步】—— 告诉模型从哪继续
       3) 最后才是显式 refs
    """
    out = []
    # 别名图（如“步骤5 加背景” = “成品”）直接用源图当参考
    al = im.get('alias')
    if al:
        p = proj.img_path(al, 'hd')
        return [p] if p else []
    order = proj.chain.get('order', [])
    s = im.get('slot')
    anchor = proj.chain.get('anchor') or (order[0] if order else None)
    in_chain = s in order
    if anchor and in_chain and s != anchor and im.get('anchor', True):
        p = proj.img_path(anchor, 'hd')
        if p:
            out.append(p)
    if im.get('ref_prev') and in_chain:
        i = order.index(s)
        if i > 0:
            p = proj.img_path(order[i - 1], 'hd')
            if p:
                out.append(p)
    for r in im.get('refs', []):
        if r == s:                        # 防自引用
            continue
        p = proj.resolve(r, 'hd')
        if p:
            out.append(p)
    seen, uniq = set(), []
    for p in out:
        if p not in seen:
            seen.add(p); uniq.append(p)
    return uniq


def gen_one(proj, im, out_dir=None, force=False, prompt=None, model=None,
            quality=None, aspect=None, size=None, log=print, credits=None):
    slot = im['slot']
    out_dir = out_dir or proj.img_dir
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, slot + '.png')

    # ★ 别名：像“步骤5 加背景”这种本来就应该等于“成品”的图，直接拷贝，
    #   架构上保证两者像素级一致，不再指望模型画两次能画得一模一样。
    al = im.get('alias')
    if al:
        src = proj.img_path(al, 'hd')
        if src and os.path.exists(src):
            if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
                log('[skip] %-16s （别名 = %s，内容一致）' % (slot, al))
                return dst, True
            shutil.copy2(src, dst)
            log('[alias] %-16s <- %s  （直接复用，不重画）' % (slot, al))
            return dst, False
        log('[WARN] %s 的别名 %s 不存在，退回正常生成' % (slot, al))

    if os.path.exists(dst) and not force:
        log('[skip] %s' % slot)
        return dst, True

    # ★ 实物照片：先联网搜真图（免费 / 真实 / 1 秒），搜不到才退回 AI 生成
    #   project.json 里给槽位写 "source": "search" + "query": ["中文词", "english"]
    if str(im.get('source', '')).lower() in ('search', 'photo', 'web'):
        import photos
        qs = im.get('query') or [slot]
        if isinstance(qs, str):
            qs = [qs]
        alt_dir = im.get('alt_dir') or os.path.join(
            os.path.dirname(out_dir.rstrip('/\\')), 'img_alt')
        p, _alts = photos.grab(
            qs, dst, alt_dir=alt_dir, log=log,
            n_alt=int(im.get('n_alt', 5)),
            min_w=int(im.get('min_w', 560)),
            min_h=int(im.get('min_h', 420)),
            allow_unknown=bool(im.get('allow_unknown', True)),
            subject=im.get('subject') or im.get('desc'),
            verify=bool(im.get('verify', True)),
            only_free=str(im.get('photo_policy',
                                 (proj.meta.get('photo_policy') or 'cc0'))).lower()
                      in ('cc0', 'free', 'safe'),
            credits=credits)
        if p:
            log('[photo] %-16s 用网搜真照片 %.2f MB' % (slot, os.path.getsize(p) / 1e6))
            return p, False
        log('[fallback] %s 没搜到合适真图 → 改用 AI 生成' % slot)

    model = model or im.get('model') or DEF['model']
    quality = quality or im.get('quality') or DEF['quality']
    aspect = aspect or im.get('aspect') or DEF['aspect']
    size = size or im.get('size')
    text = prompt if prompt is not None else build_prompt(proj, im)
    refs = refs_for(proj, im)
    tmp = os.path.join(out_dir, '_prompt_%s.txt' % slot)
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(text)
    cmd = build_cmd(model, tmp, dst, refs, quality, aspect, size)
    info = model_info(model)
    price = info.get('price')
    log('[gen ] %-18s %-24s refs=%d%s' % (slot, model, len(refs),
                                          '' if price is None else '  ~¥%.3f' % price))
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    try:
        os.remove(tmp)
    except OSError:
        pass
    if r.returncode != 0 or not os.path.exists(dst):
        log('[FAIL] %s\n%s\n%s' % (slot, (r.stdout or '')[-500:], (r.stderr or '')[-500:]))
        return None, False
    log('[ok  ] %-18s %.2f MB' % (slot, os.path.getsize(dst) / 1e6))
    return dst, False


def run(proj, batch=None, only=None, force=False, out_dir=None, log=print, **ov):
    todo = [im for im in proj.images
            if (batch is None or im.get('batch') == batch)
            and (only is None or im['slot'] in only)]
    if not todo:
        log('没有匹配的图片任务（batch=%s only=%s）' % (batch, only))
        return []
    log('批次 %s：%d 张' % (batch or 'all', len(todo)))
    credits = list(ov.pop('credits', None) or [])
    done = []
    for im in todo:
        f = force or (only is not None and im['slot'] in (only or []))
        dst, _ = gen_one(proj, im, out_dir=out_dir, force=f, log=log,
                         credits=credits, **ov)
        if dst:
            done.append(dst)
    # ★ 记下每张网搜图的来源与授权，卖课件时能拿来自证版权
    if credits and not ov.get('dry'):
        p = os.path.join(proj.dir, '图片版权.json')
        # 合并所有 sidecar（img_alt/*.credits.json）：即使某次没收集到 credits，
        # 也能从历史下载记录里重建完整版权清单
        side = []
        ad = os.path.join(proj.dir, 'img_alt')
        if os.path.isdir(ad):
            for f in sorted(os.listdir(ad)):
                if f.endswith('.credits.json'):
                    try:
                        side += json.load(open(os.path.join(ad, f), encoding='utf-8'))
                    except Exception:
                        pass
        old = []
        if os.path.exists(p):
            try:
                old = json.load(open(p, encoding='utf-8'))
            except Exception:
                old = []
        seen, merged = set(), []
        for c in credits + side + old:
            k = (c.get('slot'), c.get('url'))
            if k in seen:
                continue
            seen.add(k)
            merged.append(c)
        json.dump(merged, open(p, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=2)
        # 自愈：给缺 sidecar 的槽位补上（历史遗留 / 某次没跑到的情况）
        if os.path.isdir(ad):
            for sl in {c.get('slot') for c in merged if c.get('slot')}:
                f = os.path.join(ad, '%s.credits.json' % sl)
                if not os.path.exists(f):
                    try:
                        json.dump([c for c in merged if c.get('slot') == sl],
                                  open(f, 'w', encoding='utf-8'),
                                  ensure_ascii=False, indent=2)
                    except Exception:
                        pass
        n_un = sum(1 for c in merged if c.get('license') == '授权未知')
        cnt = {}
        for c in merged:
            k = c.get('license', '?')
            cnt[k] = cnt.get(k, 0) + 1
        log('版权清单 → %s（共 %d 条：%s）' % (
            os.path.basename(p), len(merged),
            '、'.join('%s %d' % (k, v) for k, v in sorted(cnt.items()))))
        if n_un:
            log('⚠️ 其中 %d 条**没有授权信息**（来源是搜索引擎），商用前请自己核对'
                % n_un)
    log('完成 %d/%d' % (len(done), len(todo)))
    return done


def compress(proj, maxw=1600, q=88, log=print):
    from PIL import Image
    os.makedirs(proj.sell_dir, exist_ok=True)
    a = b = 0
    for im in proj.images:
        src = proj.img_path(im['slot'], 'hd')
        if not src:
            log('[miss] %s' % im['slot']); continue
        dst = os.path.join(proj.sell_dir, im['slot'] + '.jpg')
        i = Image.open(src).convert('RGB')
        if i.width > maxw:
            i = i.resize((maxw, round(i.height * maxw / i.width)), Image.LANCZOS)
        i.save(dst, 'JPEG', quality=q, optimize=True, progressive=True)
        a += os.path.getsize(src); b += os.path.getsize(dst)
    for f in os.listdir(proj.dir):
        if f.lower().endswith(('.png', '.jpg')) and '封面' in f:
            dst = os.path.join(proj.sell_dir, os.path.splitext(f)[0] + '.jpg')
            i = Image.open(os.path.join(proj.dir, f)).convert('RGB')
            if i.width > maxw:
                i = i.resize((maxw, round(i.height * maxw / i.width)), Image.LANCZOS)
            i.save(dst, 'JPEG', quality=q, optimize=True, progressive=True)
    log('压缩 %.1fMB -> %.1fMB' % (a / 1e6, b / 1e6))
    return b


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('project', nargs='?',
                    help='project.json 路径或项目目录（--models 时可省略）')
    ap.add_argument('--batch')
    ap.add_argument('--only', nargs='*', help='只跑/重跑指定槽位')
    ap.add_argument('--force', action='store_true', help='已存在也重跑')
    ap.add_argument('--model'); ap.add_argument('--quality'); ap.add_argument('--aspect')
    ap.add_argument('--size', help='nano-banana 系：1K / 2K / 4K')
    ap.add_argument('--models', action='store_true', help='列出可用模型与定价')
    ap.add_argument('--list', action='store_true')
    import ui
    ui.add_args(ap)
    a = ap.parse_args()
    if a.models:
        print('%-26s %-6s %-8s %s' % ('模型', '通道', '价格', '说明'))
        print('-' * 78)
        for m, i in CATALOG.items():
            print('%-26s %-6s ¥%-7s %s' % (m, i['cli'], i.get('price', '?'), i.get('note', '')))
        sys.exit()
    if not a.project:
        ap.error('需要给出 project.json 路径（--models 例外）')
    proj = Project(a.project)
    if a.list:
        for im in proj.images:
            print('%-18s %-8s %-22s %s' % (im['slot'], im.get('batch', ''), im.get('model', ''),
                                           'OK' if proj.img_path(im['slot'], 'hd') else '--'))
        sys.exit()
    ov = {k: v for k, v in dict(model=a.model, quality=a.quality, aspect=a.aspect,
                                size=a.size).items() if v}
    run(proj, a.batch, a.only, a.force, **ov)
    # ★ 跑完自动打开审图台 —— 出图只是第一步，重跑/换 prompt/挑图要在界面里做
    ui.maybe_open(a, a.project)
