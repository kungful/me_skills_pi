# -*- coding: utf-8 -*-
"""课件工厂 · 项目模型：读取 project.json，解析路径、图片槽位、审图状态"""
import os, json, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Project:
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.dir = os.path.dirname(self.path)
        with open(self.path, encoding='utf-8') as f:
            self.data = json.load(f)
        self.meta = self.data.get('meta', {})
        self.images = self.data.get('images', [])
        self.pages = self.data.get('pages', [])
        self.lock = self.data.get('lock', '')
        self.common = self.data.get('common', {})
        self.chain = self.data.get('chain', {})
        self.by_slot = {im['slot']: im for im in self.images}

    # ---------- 路径 ----------
    @property
    def name(self):
        return self.meta.get('name') or os.path.basename(self.dir)

    @property
    def img_dir(self):
        return os.path.join(self.dir, 'img')

    @property
    def sell_dir(self):
        return os.path.join(self.dir, 'img_sell')

    @property
    def out_dir(self):
        d = os.path.join(self.dir, 'out')
        os.makedirs(d, exist_ok=True)
        return d

    @property
    def preview_dir(self):
        d = os.path.join(self.out_dir, 'preview')
        os.makedirs(d, exist_ok=True)
        return d

    def img_path(self, slot, mode='sell'):
        """mode: sell=压缩图优先(交付/预览)，hd=高清原图优先(审图)"""
        order = ('sell', 'hd') if mode == 'sell' else ('hd', 'sell')
        for m in order:
            d = self.sell_dir if m == 'sell' else self.img_dir
            for ext in ('.jpg', '.jpeg', '.png', '.webp'):
                p = os.path.join(d, slot + ext)
                if os.path.exists(p):
                    return p
        return None

    def resolve(self, name, mode='sell'):
        """页面里的图片名：先当槽位名找，找不到再当文件名找"""
        slot = os.path.splitext(name)[0]
        p = self.img_path(slot, mode)
        if p:
            return p
        for base in (self.sell_dir, self.img_dir, self.dir):
            for ext in ('.png', '.jpg', '.jpeg'):
                q = os.path.join(base, slot + ext)
                if os.path.exists(q):
                    return q
        return None

    def resolver(self, mode='sell'):
        return lambda n: self.resolve(n, mode)

    # ---------- 产物 ----------
    def pptx(self, tag=''):
        return os.path.join(self.out_dir, '%s%s.pptx' % (self.name, tag))

    def pdf(self, tag=''):
        return os.path.join(self.out_dir, '%s%s.pdf' % (self.name, tag))

    # ---------- 审图状态 ----------
    @property
    def review_file(self):
        return os.path.join(self.out_dir, 'review.json')

    def review(self):
        if os.path.exists(self.review_file):
            with open(self.review_file, encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_review(self, obj):
        with open(self.review_file, 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        return self.review_file

    # ---------- 状态汇总 ----------
    def status(self):
        slots = []
        for im in self.images:
            s = im['slot']
            hd, sell = self.img_path(s, 'hd'), self.img_path(s, 'sell')
            slots.append(dict(slot=s, batch=im.get('batch', ''), model=im.get('model', ''),
                              prompt=im.get('prompt', ''), has_hd=bool(hd), has_sell=bool(sell),
                              alias=im.get('alias'), refs=im.get('refs', []),
                              source=im.get('source'), query=im.get('query'),
                              alts=self.alts(s)))
        pages = []
        for i, p in enumerate(self.pages):
            pages.append(dict(index=i + 1, type=p.get('type'),
                              title=p.get('title') or p.get('question') or p.get('head') or '',
                              uses=p.get('uses', []),
                              preview=os.path.join(self.preview_dir, '%02d.png' % (i + 1))))
        return dict(name=self.name, dir=self.dir, meta=self.meta,
                    missing=[s['slot'] for s in slots if not s['has_hd']],
                    slots=slots, pages=pages, review=self.review())

    # ---------- 多项目工作台用 ----------
    @property
    def dirname(self):
        return os.path.basename(self.dir)

    @property
    def alt_dir(self):
        """网搜照片的备选图目录（img_alt/）"""
        return os.path.join(self.dir, 'img_alt')

    def alts(self, slot):
        """某个槽位的备选图文件名列表（img_alt/<slot>_NN.png）"""
        d = self.alt_dir
        if not os.path.isdir(d):
            return []
        out = []
        for f in sorted(os.listdir(d)):
            if f.startswith(slot + '_') and f.lower().endswith(('.png', '.jpg')):
                out.append(f)
        return out

    @property
    def brand(self):
        return self.meta.get('brand', '')

    def thumb(self):
        """列表缩略图：优先 PDF 首页预览，其次封面图，再次任意一张"""
        p = os.path.join(self.preview_dir, '01.png')
        if os.path.exists(p):
            return p
        for im in self.images:
            q = self.img_path(im['slot'], 'sell')
            if q:
                return q
        return None

    def summary(self):
        """轻量汇总（给课件列表用，不做全量 status）"""
        pdf, pptx = self.pdf(), self.pptx()
        miss = 0
        for im in self.images:
            if not self.img_path(im['slot'], 'hd'):
                miss += 1
        rev = self.review()
        n_redo = sum(1 for v in rev.values() if v.get('status') == 'redo')
        n_fix = sum(1 for v in rev.values() if v.get('status') == 'fix')
        return dict(dirname=self.dirname, name=self.name, brand=self.brand,
                    age=self.meta.get('age', ''), pages=len(self.pages),
                    images=len(self.images), missing=miss, redo=n_redo, fix=n_fix,
                    has_pdf=os.path.exists(pdf),
                    pdf_size=os.path.getsize(pdf) if os.path.exists(pdf) else 0,
                    has_pptx=os.path.exists(pptx),
                    pptx_size=os.path.getsize(pptx) if os.path.exists(pptx) else 0,
                    has_thumb=bool(self.thumb()), mtime=os.path.getmtime(self.path))


def find_project_paths(root=ROOT):
    return sorted(glob.glob(os.path.join(root, '项目', '*', 'project.json')))


def find_projects():
    """兼容旧调用：返回 project.json 路径列表"""
    return find_project_paths()
