# -*- coding: utf-8 -*-
"""一键启动审图台（由 启动审图台.bat 调用）。所有中文提示都在这里，避免 cmd 编码问题。"""
import os, sys, subprocess, time, webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, '工厂'))

LINE = '=' * 62
BANNER = LINE + """
  课件工厂 · 审图台
""" + LINE


def ensure_deps():
    miss = []
    for mod, pkg in [('pptx', 'python-pptx'), ('PIL', 'pillow'), ('pypdf', 'pypdf'),
                     ('win32com', 'pywin32')]:
        try:
            __import__(mod)
        except ImportError:
            miss.append(pkg)
    if miss:
        print('[!] 缺少依赖：%s，正在自动安装…' % ', '.join(miss))
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q'] + miss)
    return miss


def main():
    print(BANNER)
    print(' Python : %s' % sys.executable)
    miss = ensure_deps()
    if miss:
        print(' 依赖安装完成，重新检查…')

    from project import find_projects
    cands = find_projects()
    if not cands:
        print('[x] 在 项目/ 下找不到 project.json')
        return 1
    proj = sys.argv[1] if len(sys.argv) > 1 else cands[0]
    port = int(os.environ.get('DECKUI_PORT', '8777'))

    print(' 项目   : %s' % os.path.basename(os.path.dirname(proj)))
    print(' 地址   : http://127.0.0.1:%d' % port)
    print(' 说明   : 本窗口是服务端，关掉它就关闭审图台')
    print(LINE)
    print(' 正在启动…')
    sys.stdout.flush()

    import threading
    def open_later():
        time.sleep(1.8)
        webbrowser.open('http://127.0.0.1:%d' % port)
    threading.Thread(target=open_later, daemon=True).start()

    import server
    server.PORT = port
    try:
        server.serve(proj, port)
    except OSError as e:
        print('\n[x] 端口 %d 被占用（可能审图台已经在运行）。' % port)
        print('    直接打开 http://127.0.0.1:%d 即可；或先关掉那个窗口。' % port)
        print('    原始错误：%s' % e)
        webbrowser.open('http://127.0.0.1:%d' % port)
        return 1
    except KeyboardInterrupt:
        print('\n已停止。')
    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
