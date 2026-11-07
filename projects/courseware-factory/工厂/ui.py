# -*- coding: utf-8 -*-
"""跑完自动打开审图台（WebUI）——出图/装配之后直接进「精细化修改」闭环。

设计目标：**幂等**。
  - 审图台已经在跑  → 只把浏览器顶到前台，不再起第二个服务（否则端口冲突 + 数据不同步）
  - 还没跑          → 后台拉起 工厂/server.py（独立控制台窗口），等端口就绪再开浏览器

被 pipeline.py / builder.py 调用。可用 --no-ui 关掉（自检、CI、批量脚本都该关）。
"""
import os
import subprocess
import sys
import time
import webbrowser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 仓库根
PORT = int(os.environ.get('DECKUI_PORT', '8777'))


def is_up(port=None, timeout=0.4):
    """端口上已经有审图台在监听？"""
    import socket
    s = socket.socket()
    try:
        s.settimeout(timeout)
        return s.connect_ex(('127.0.0.1', port or PORT)) == 0
    finally:
        s.close()


def _switch(project, port):
    """服务已在跑时，让界面切到目标课件。

    否则你刚给「小兔子」出完图，界面却还停在上一次的「大熊猫」上——
    看起来像「跑完了但图没变」。
    """
    if not project:
        return
    try:
        import json as _j
        import urllib.request as _u
        d = os.path.basename(os.path.dirname(os.path.abspath(project)))
        req = _u.Request('http://127.0.0.1:%d/api/switch' % port,
                         data=_j.dumps({'project': d}).encode('utf-8'),
                         headers={'Content-Type': 'application/json; charset=utf-8'})
        _u.urlopen(req, timeout=10).read()
    except Exception:
        pass


def open_ui(project, port=None, wait=25, log=print):
    """跑完自动打开审图台。返回服务地址；失败也不抛异常（不能因为开不出界面就毁掉出图结果）。

    project: project.json 路径 / 项目目录 / None（让服务端自己挑第一套）
    """
    port = port or PORT
    url = 'http://127.0.0.1:%d' % port

    # ① 服务已在跑 → 先切到目标课件，再开浏览器
    if is_up(port):
        log('')
        log('[UI] 审图台已在运行 → 切到本课件并打开：%s' % url)
        _switch(project, port)
        try:
            webbrowser.open(url)
        except Exception:
            pass
        return url

    # ② 后台拉起服务。用独立控制台窗口，方便用户随时关掉，
    #    也避免它继承父进程的 stdout 把日志搅在一起。
    args = [sys.executable, '-c',
            'import sys;sys.path.insert(0,%r);import server;server.serve(%r,%d)'
            % (os.path.join(ROOT, '工厂'), str(project) if project else None, port)]
    log('')
    log('[UI] 正在启动审图台…  %s' % url)
    try:
        flags = 0
        if os.name == 'nt':
            flags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
        subprocess.Popen(args, cwd=ROOT, creationflags=flags,
                         stdout=None if flags else subprocess.DEVNULL,
                         stderr=None if flags else subprocess.DEVNULL)
    except Exception as e:
        log('[UI] 启动失败（不影响出图结果）：%s' % e)
        return ''

    t0 = time.time()
    while time.time() - t0 < wait:
        if is_up(port):
            log('[UI] 已就绪，打开浏览器（刷新页面即可看到刚出的图）')
            try:
                webbrowser.open(url)
            except Exception:
                pass
            return url
        time.sleep(0.4)

    log('[UI] 启动超时，请手动双击「启动审图台.bat」，或访问 %s' % url)
    return ''


def add_args(ap, default_on=True):
    """给 argparse 加统一开关。default_on=True 时默认开，用 --no-ui 关。"""
    ap.add_argument('--no-ui', action='store_true',
                    help='跑完不自动打开审图台' + ('' if default_on else '（默认就不开）'))
    ap.add_argument('--ui-port', type=int, default=PORT)
    return ap


def maybe_open(a, project, log=print):
    """按 --no-ui / --ui-port 决定是否打开。

    ★ 默认就开，不做 isatty 判断 —— 脚本/Agent 帮忙跑的时候，用户同样希望
      界面弹出来（这正是「跑完了还得自己去双击 bat」的痛点）。
      要关就显式传 --no-ui（selftest 与批量脚本已经这么做）。
    """
    if getattr(a, 'no_ui', False):
        return ''
    if os.environ.get('DECKUI_NO_UI') == '1':
        return ''
    return open_ui(project, getattr(a, 'ui_port', None), log=log)
