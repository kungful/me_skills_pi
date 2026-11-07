# -*- coding: utf-8 -*-
"""课件工厂 · 导出器：PPTX -> PDF，并逐页导出 PNG 缩略图（供 WebUI 审图）"""
import os, sys, subprocess, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import pythoncom
except ImportError:
    pythoncom = None


def via_powerpoint(pptx, pdf, preview_dir=None, w=1400, h=0):
    import win32com.client as win32
    if pythoncom:
        pythoncom.CoInitialize()          # 后台线程里跑 COM 必须先初始化
    app = win32.Dispatch('PowerPoint.Application')
    pres = app.Presentations.Open(os.path.abspath(pptx), WithWindow=False)
    try:
        pres.SaveAs(os.path.abspath(pdf), 32)      # ppSaveAsPDF
        if preview_dir:
            os.makedirs(preview_dir, exist_ok=True)
            for f in os.listdir(preview_dir):
                if f.endswith('.png'):
                    os.remove(os.path.join(preview_dir, f))
            for i, sl in enumerate(pres.Slides, 1):
                sl.Export(os.path.join(preview_dir, '%02d.png' % i), 'PNG', w, h)
    finally:
        pres.Close()
    return True


def via_libreoffice(pptx, pdf, preview_dir=None):
    soffice = shutil.which('soffice') or r'C:\Program Files\LibreOffice\program\soffice.exe'
    outdir = os.path.dirname(os.path.abspath(pdf))
    subprocess.run([soffice, '--headless', '--convert-to', 'pdf', '--outdir', outdir,
                    os.path.abspath(pptx)], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if preview_dir and shutil.which('pdftoppm'):
        os.makedirs(preview_dir, exist_ok=True)
        subprocess.run(['pdftoppm', '-png', '-r', '110', pdf, os.path.join(preview_dir, 'p')])
    return os.path.exists(pdf)


def export(proj, pptx, pdf=None, previews=True, log=print):
    pdf = pdf or proj.pdf()
    pdir = proj.preview_dir if previews else None
    try:
        via_powerpoint(pptx, pdf, pdir)
        log('[export] PowerPoint COM OK')
    except Exception as e:
        log('[export] COM 失败：%s，改用 LibreOffice' % e)
        via_libreoffice(pptx, pdf, pdir)
        log('[export] LibreOffice OK')
    n = len([f for f in os.listdir(pdir) if f.endswith('.png')]) if pdir and os.path.isdir(pdir) else 0
    log('[pdf] %s  %.2f MB  预览 %d 页' % (pdf, os.path.getsize(pdf) / 1e6, n))
    return pdf


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    from project import Project
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('project'); ap.add_argument('--pptx'); ap.add_argument('--no-preview', action='store_true')
    a = ap.parse_args()
    p = Project(a.project)
    export(p, a.pptx or p.pptx(), previews=not a.no_preview)
