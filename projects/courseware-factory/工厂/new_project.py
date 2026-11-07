# -*- coding: utf-8 -*-
"""
课件工厂 · 新建课件脚手架
把「26页教学链条 + 17个图片槽位」的结构整个复制出来，只换主题。
用法：
    python 工厂/new_project.py "小兔子吃萝卜" --age 4-6岁
    python 工厂/new_project.py "小兔子吃萝卜" --age 4-6岁 --blank   # 清空 prompt，从零写
"""
import os, sys, json, shutil, argparse
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEF_TPL = os.path.join(ROOT, '项目', '大熊猫吃竹子-4-6岁', 'project.json')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('name', help='课题名，如 小兔子吃萝卜')
    ap.add_argument('--age', default='4-6岁')
    ap.add_argument('--from', dest='src', default=DEF_TPL, help='模板 project.json')
    ap.add_argument('--blank', action='store_true', help='清空所有 AI prompt（从零写）')
    ap.add_argument('--dir', help='输出目录名（默认 项目/<课题>-<年龄>）')
    a = ap.parse_args()

    with open(a.src, encoding='utf-8') as f:
        data = json.load(f)

    d = a.dir or '%s-%s' % (a.name.replace('《', '').replace('》', ''), a.age)
    dst = os.path.join(ROOT, '项目', d)
    if os.path.exists(dst) and os.listdir(dst):
        sys.exit('目录已存在且非空：%s' % dst)
    for sub in ('img', 'img_sell', 'out'):
        os.makedirs(os.path.join(dst, sub), exist_ok=True)

    data['meta']['name'] = '《%s》%s课件' % (a.name.strip('《》'), a.age)
    data['meta']['age'] = a.age
    for p in data['pages']:
        if p.get('type') == 'cover':
            p['title'] = '《%s》' % a.name.strip('《》')
            p['subtitle'] = data['meta'].get('subtitle') or p.get('subtitle', '')
        p['uses'] = [u for u in p.get('uses', [])]
    if a.blank:
        for im in data['images']:
            im['prompt'] = ''
    else:
        for im in data['images']:
            im['prompt'] = '【改我】' + im.get('prompt', '')

    with open(os.path.join(dst, 'project.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print('已创建：%s' % dst)
    print('  %d 页 / %d 个图片槽位' % (len(data['pages']), len(data['images'])))
    print('  下一步：python 工厂/server.py "%s"' % os.path.join('项目', d, 'project.json'))


if __name__ == '__main__':
    main()
