# -*- coding: utf-8 -*-
"""课件工厂 · 交付打包（卖货用的「一个课件 = 一个文件夹」）

把一套课件整理成可以直接上传网盘、单独发链接的交付包：

    项目/<课件>/交付/<课件名>/
        <课件名>.pdf          ← 卖家稿（26 页）
        原图/<槽位>.jpg        ← 出图原图（长边 1920，质量 92）
        manifest.json         ← 每个文件的 md5 / 尺寸 / 生成时间 / 品牌

为什么不直接把 img/*.png 塞给对方：
  - PNG 2.5MB×16 = 40MB，买家手机下载卡、网盘传得慢
  - 交付包里必须能一眼看出「哪些文件、什么版本、是不是我出的」→ manifest 存证

用法：
    python 工厂/deliver.py 项目/圣诞树-4-6岁/project.json
    python 工厂/deliver.py 项目/圣诞树-4-6岁/project.json --zip
    python 工厂/deliver.py 项目/圣诞树-4-6岁/project.json --long 2400 --quality 95
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import zipfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from project import Project  # noqa: E402

from PIL import Image  # noqa: E402


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def export_img(src, dst, long_edge, quality):
    im = Image.open(src).convert("RGB")
    w, h = im.size
    s = min(1.0, long_edge / max(w, h))
    if s < 1.0:
        im = im.resize((int(w * s), int(h * s)), Image.LANCZOS)
    im.save(dst, "JPEG", quality=quality, optimize=True)
    return im.size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--long", type=int, default=1920, help="原图长边像素（默认 1920）")
    ap.add_argument("--quality", type=int, default=92, help="JPG 质量（默认 92）")
    ap.add_argument("--zip", action="store_true", help="同时打一个 zip")
    ap.add_argument("--out", default="", help="自定义输出根目录（默认 项目/<课件>/交付）")
    a = ap.parse_args()

    proj = Project(a.project)
    pdf = proj.pdf()
    if not os.path.exists(pdf):
        print("[x] 还没有 PDF：%s" % pdf)
        print("    先跑：python 工厂/builder.py %s && python 工厂/exporter.py %s"
              % (a.project, a.project))
        return 2

    name = proj.name.replace("《", "").replace("》", "")   # 《圣诞树》4-6岁课件 -> 圣诞树4-6岁课件
    root = a.out or os.path.join(proj.dir, "交付")
    dst_dir = os.path.join(root, name)
    if os.path.isdir(dst_dir):
        shutil.rmtree(dst_dir)
    os.makedirs(os.path.join(dst_dir, "原图"), exist_ok=True)

    files = []
    # 1) 课件 PDF
    dst_pdf = os.path.join(dst_dir, name + ".pdf")
    shutil.copy2(pdf, dst_pdf)
    files.append(dict(rel=os.path.basename(dst_pdf), kind="课件PDF",
                      size=os.path.getsize(dst_pdf), md5=md5(dst_pdf)))

    # 2) 原图（按 chain 顺序在前，方便买家照着课本顺序看）
    order = proj.chain.get("order") or []
    slots = [s for s in order if proj.img_path(s, "hd")]
    slots += [im["slot"] for im in proj.images
              if im["slot"] not in slots and proj.img_path(im["slot"], "hd")]
    skipped = []
    for i, slot in enumerate(slots, 1):
        src = proj.img_path(slot, "hd")
        if not src:
            skipped.append(slot)
            continue
        dst = os.path.join(dst_dir, "原图", "%02d_%s.jpg" % (i, slot))
        size = export_img(src, dst, a.long, a.quality)
        files.append(dict(rel="原图/" + os.path.basename(dst), kind="原图", slot=slot,
                          size=os.path.getsize(dst), md5=md5(dst),
                          px=list(size), src=os.path.basename(src)))

    man = dict(
        deck=name, brand=proj.meta.get("brand"), age=proj.meta.get("age"),
        pages=len(proj.pages), images=len(files) - 1,
        long_edge=a.long, jpg_quality=a.quality,
        built_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        source_project=os.path.basename(proj.dir),
        note="本包为已售课件的交付副本，版权归作者所有，请勿二次分发。",
        files=files)
    with open(os.path.join(dst_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)

    total = sum(f["size"] for f in files)
    print("交付包: %s" % dst_dir)
    print("  %d 个文件（1 PDF + %d 原图）共 %.1f MB"
          % (len(files), len(files) - 1, total / 1e6))
    if skipped:
        print("  [!] 缺图槽位（未进包）: %s" % "、".join(skipped))

    if a.zip:
        zp = os.path.join(root, name + ".zip")
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            for f in files + [dict(rel="manifest.json")]:
                z.write(os.path.join(dst_dir, f["rel"]), os.path.join(name, f["rel"]))
        print("   zip: %s (%.1f MB)" % (zp, os.path.getsize(zp) / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
