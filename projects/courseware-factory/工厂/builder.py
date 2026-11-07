# -*- coding: utf-8 -*-
"""课件工厂 · 装配器：project.json -> pptx"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Deck
from renderers import RENDERERS
from project import Project


def build(proj: Project, mode='sell', out=None, verbose=True):
    d = Deck(theme=proj.meta.get('theme'), brand=proj.meta.get('brand', '美育'),
             brand_en=proj.meta.get('brand_en', 'Art Education for Kids'))
    ctx = type('Ctx', (), {'P': staticmethod(proj.resolver(mode)), 'proj': proj})
    for i, p in enumerate(proj.pages):
        t = p.get('type', 'text_page')
        if t not in RENDERERS:
            raise ValueError('未知页型 %r（第%d页）。可用: %s' % (t, i + 1, ', '.join(sorted(RENDERERS))))
        fn = RENDERERS[t]
        if t == 'cover':
            s = d.page(show_bar=False, auto=False)
        else:
            s = d.page(chapter=p.get('chapter'), bg=None)
        fn(d, s, p, ctx)
        if verbose:
            print('  P%-2d %-16s %s' % (i + 1, t, (p.get('title') or p.get('question') or '')[:40]))
    out = out or proj.pptx()
    d.save(out)
    if verbose:
        print('装配完成 -> %s  (%.2f MB, %d 页)' % (out, os.path.getsize(out) / 1e6, len(proj.pages)))
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('project')
    ap.add_argument('--mode', default='sell', choices=['sell', 'hd'])
    ap.add_argument('--out')
    ap.add_argument('--no-compress', action='store_true',
                    help='默认会先压缩 img/ -> img_sell/（不然新出的图不会进 PPTX）')
    import ui
    ui.add_args(ap)
    a = ap.parse_args()
    pr = Project(a.project)
    # ★ 自动压缩：以前 CLI 直接 build，img_sell/ 还是旧图，
    #   表现为「明明重出了图，PDF 里还是老图」——必预压缩。
    if a.mode == 'sell' and not a.no_compress:
        import pipeline
        pipeline.compress(pr)
    build(pr, mode=a.mode, out=a.out)
    # ★ 装配完也自动开审图台，直接看图改文案/版式
    ui.maybe_open(a, a.project)
