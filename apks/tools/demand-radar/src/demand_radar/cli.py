"""命令行入口：python -m demand_radar <命令>"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from datetime import datetime
from typing import List

from . import db
from . import hub
from . import report as rp
from .config import REPORT_DIR, sources_cfg
from .collectors import all_names


def _open(path: str) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
    except Exception:
        pass


def cmd_run(a) -> int:
    only = a.only.split(",") if a.only else None
    hub.run_all(only=only, days=a.days, quiet=False)
    if a.open:
        _open(str(REPORT_DIR / "index.html"))
    return 0


def cmd_collect(a) -> int:
    only = a.only.split(",") if a.only else None
    if a.loop:
        while True:
            hub.collect(only=only)
            hub.analyze(quiet=False)
            rp.write_reports(_topics())
            print(f"—— 等待下一轮（{a.interval} 分钟）——", flush=True)
            time.sleep(a.interval * 60)
    hub.collect(only=only)
    return 0


def cmd_analyze(a) -> int:
    hub.analyze(days=a.days, quiet=False)
    return 0


def cmd_report(a) -> int:
    from . import score as sc

    con = db.connect()
    rows = db.fetch_items_since(con, a.days, 20000)
    if not rows:
        print("库里没有数据，先跑 collect")
        return 1
    models = hub.load_models(con, a.days)
    topics = sc.filter_topics(sc.build_topics(models), sc.min_topic_items())
    files = rp.write_reports(topics, top_n=a.top)
    print(f"Markdown: {files['md']}")
    print(f"看板    : {files['html']}")
    print(f"CSV     : {files['csv']}")
    if a.open:
        _open(files["html"])
    return 0


def _topics(limit: int = 40):
    from . import score as sc

    con = db.connect()
    models = hub.load_models(con, 90)
    if not models:
        return []
    return sc.filter_topics(sc.build_topics(models), sc.min_topic_items())[:limit]


def cmd_top(a) -> int:
    topics = _topics(a.n)
    if not topics:
        print("暂无数据。先运行：python -m demand_radar run")
        return 1
    try:
        from rich.console import Console
        from rich.table import Table

        c = Console()
        t = Table(title=f"需求雷达 · Top {len(topics)} 机会", show_lines=False)
        t.add_column("#", width=3)
        t.add_column("需求主题", style="bold")
        t.add_column("机会分", justify="right")
        t.add_column("证据", justify="right")
        t.add_column("来源", justify="right")
        t.add_column("痛感", justify="right")
        t.add_column("付费", justify="right")
        t.add_column("变现路径", overflow="fold", max_width=46)
        for i, x in enumerate(topics, 1):
            color = "red" if x.score >= 55 else ("yellow" if x.score >= 35 else "cyan")
            t.add_row(str(i), x.label, f"[{color}]{x.score:.0f}[/{color}]",
                      str(len(x.item_ids)), str(len(x.sources)), f"{x.pain:.0f}", f"{x.pay:.0f}",
                      x.money.split("] ", 1)[-1])
        c.print(t)
        c.print("[dim]详情看板：python -m demand_radar report --open[/dim]")
    except Exception:
        for i, x in enumerate(topics, 1):
            print(f"{i:>2}. [{x.score:5.1f}] {x.label}  证据{len(x.item_ids)} 源{len(x.sources)} "
                  f"痛{x.pain:.0f} 付费{x.pay:.0f} | {x.money.split('] ', 1)[-1][:50]}")
    return 0


def cmd_watch(a) -> int:
    hub.watch(interval=a.interval, duration=a.duration)
    return 0


def cmd_capture(a) -> int:
    """抓取手机当前屏幕一次，看看能拿到什么"""
    from .collectors.android_screen import AndroidScreen

    cfg = dict(((sources_cfg().get("sources") or {}).get("android_screen") or {}))
    cfg["only_listed_apps"] = False
    col = AndroidScreen(cfg)
    if not col.refresh_device():
        print("未检测到手机。请检查：USB 已插好 / 开发者选项里已开 USB 调试 / 手机上已点『允许』")
        print("排查命令：adb kill-server && adb devices")
        return 1
    cap = col.capture_once()
    if not cap:
        print("没抓到文字（可能是空屏或以图片为主）。")
        return 1
    if cap.get("skipped"):
        reason = cap.get("reason")
        if reason == "system-ui":
            print(f"当前在系统/桌面界面（{cap.get('pkg')}），这里没有需求信息。")
            print("请先打开 小红书 / 闲鱼 / 抖音 / 转转 等 App 的具体内容页，再抓一次。")
        elif reason == "app-not-monitored":
            print(f"当前 App（{cap.get('pkg')}）不在监听名单里。")
            print("要加的话：config/sources.yaml → android_screen → apps 里补一行「包名: 名字」。")
        else:
            print(f"已跳过：{reason}")
        return 1
    print(f"前台 App : {cap['app']} ({cap['pkg']}/{cap['act']})")
    print(f"取字方式 : {cap['method']}")
    print(f"文本长度 : {len(cap['text'])}")
    print("-" * 60)
    print(cap["text"][:2000])
    print("-" * 60)
    from . import score as scorer

    items = col.emit_screen(cap)
    for it in items:
        scorer.score_item(it)
    items.sort(key=lambda x: -x.demand)
    print("需求打分预览：")
    for it in items[:6]:
        flag = "★" if it.demand >= 25 else " "
        print(f" {flag} {it.demand:5.1f} | {it.body[:70].replace(chr(10),' ')}")
        if it.signals:
            print(f"        信号：{', '.join(it.signals[:4])}")
    if items and max(x.demand for x in items) < 20:
        print("\n（这一屏没有明显需求信号，属正常——抓到的多是导航/标题文字。）")
    if a.save:
        import hashlib

        con = db.connect()
        for it in items:
            scorer.score_item(it)
        db.upsert_items(con, items)
        db.record_screen(
            con,
            hashlib.sha1(cap["text"].encode("utf-8", "ignore")).hexdigest()[:20],
            cap["pkg"],
            cap["app"],
            cap["text"],
        )
        print(f"已写入数据库（{len(items)} 条）")
    return 0


def cmd_phone(a) -> int:
    info = hub.phone_status()
    if info["connected"]:
        mode = "无线" if info.get("wireless") else "USB"
        print(f"✅ 手机已连接（{mode}）")
        for k in ("devices", "serial", "brand", "android", "size"):
            if info.get(k):
                print(f"   {k}: {info[k]}")
        if not info.get("wireless"):
            print("\n提示：跑 `python -m demand_radar wireless` 可切换无线模式，拔掉数据线。")
        print("\n用法：")
        print("  python -m demand_radar watch      # 你刷手机，它自动抓需求")
        print("  python -m demand_radar capture    # 只抓当前一屏试试")
    else:
        print("❌ 未检测到设备")
        print("   1) 数据线插好，手机选『传输文件』模式")
        print("   2) 设置 → 开发者选项 → USB 调试 打开")
        print("   3) 手机上弹出『允许 USB 调试吗』点允许")
        print("   4) 还不行：adb kill-server && adb devices")
    return 0 if info["connected"] else 1


def _wifi_ip(serial: str) -> str:
    """拿手机当前 WiFi 的 IPv4"""
    from .collectors.android_screen import adb

    for cmd in (
        ["shell", "ip", "-4", "addr", "show", "wlan0"],
        ["shell", "ip", "route"],
        ["shell", "ifconfig", "wlan0"],
    ):
        out = adb(cmd, serial=serial) or ""
        m = re.search(r"inet (?:addr:)?([0-9]{1,3}(?:\.[0-9]{1,3}){3})", out)
        if not m:
            m = re.search(r"src ([0-9]{1,3}(?:\.[0-9]{1,3}){3})", out)
        if m and not m.group(1).startswith("127."):
            return m.group(1)
    return ""


def _my_subnet() -> str:
    """本机在哪个网段，例如 192.168.31"""
    import socket

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip.rsplit(".", 1)[0]
    except Exception:
        return ""


def _scan_subnet(port: int, timeout: float = 0.4) -> List[str]:
    """扫本网段看谁开着 ADB 端口（手机换 IP 后靠这个找回来）"""
    import socket
    from concurrent.futures import ThreadPoolExecutor

    base = _my_subnet()
    if not base:
        return []

    def probe(i: int) -> str:
        ip = f"{base}.{i}"
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return f"{ip}:{port}"
        except Exception:
            return ""

    with ThreadPoolExecutor(max_workers=64) as ex:
        return sorted(x for x in ex.map(probe, range(1, 255)) if x)


def _connect_existing(port: int) -> List[str]:
    """手机换了 IP 时，扫网段把无线设备重新连上"""
    from .collectors.android_screen import adb

    found = _scan_subnet(port)
    live = []
    for addr in found:
        out = adb(["connect", addr]) or ""
        if "connected to" in out:
            live.append(addr)
            print(f"  已连上 {addr}")
    return live


def cmd_wireless(a) -> int:
    """把手机切成无线 ADB，拔掉数据线也能继续采集"""
    from .collectors.android_screen import ADB, adb

    print(f"adb: {ADB}")
    devs = []
    for line in adb(["devices"]).splitlines()[1:]:
        p = line.split()
        if len(p) >= 2 and p[1] == "device":
            devs.append(p[0])

    usb = [d for d in devs if ":" not in d]
    tcp = [d for d in devs if ":" in d]

    # 已经无线连着，但有线也插着 → 顺手刷新一下 IP（换网/重连后旧地址会失效）
    if tcp and not a.redo:
        print(f"已经是无线模式：{', '.join(tcp)}")
        if usb:
            ip = _wifi_ip(usb[0])
            cur = _wifi_ip(tcp[0])
            if ip and ip != cur:
                print(f"手机 IP 已变成 {ip}，重新连接…")
                adb(["disconnect", tcp[0]])
                print((adb(["connect", f"{ip}:{a.port}"]) or "").strip())
        return 0

    if not devs:
        # 没设备：大概率是手机换了 IP，扫一遍网段
        if a.scan or a.ip:
            print(f"正在扫网段找无线设备（端口 {a.port}）…")
            if a.ip:
                print((adb(["connect", f"{a.ip}:{a.port}"]) or "").strip())
            if _connect_existing(a.port):
                print("\n✅ 无线 ADB 已恢复（手机换了 IP 的话记住加 --scan）。")
                return 0
            print("\n❌ 网段里没找到开着的 ADB 设备。")
            print("   可能手机息屏/关 Wi-Fi 后系统把无线调试关了 —— 插一次数据线重跑本命令即可。")
            return 1
        print("没检测到手机。可能原因：")
        print("  1) 手机息屏/关 Wi-Fi 后，系统关掉了无线调试（vivo 常见）")
        print("  2) 手机换了 IP（路由器重新分配）")
        print("  → 插上数据线跑一次，或试：python -m demand_radar wireless --scan")
        return 1

    if not usb:
        print("没看到 USB 连接的设备。无线配对必须先插一次数据线。")
        return 1

    serial = usb[0]
    adb(["tcpip", "5555"], serial=serial)
    time.sleep(3)
    ip = a.ip or _wifi_ip(serial)
    if not ip:
        print("没拿到手机 WiFi IP。请确认手机连着 WiFi，或手动指定：--ip 192.168.x.x")
        return 1

    addr = f"{ip}:{a.port}"
    print((adb(["connect", addr]) or "").strip() or f"connecting → {addr}")
    time.sleep(1.5)
    now = [ln.split()[0] for ln in adb(["devices"]).splitlines()[1:] if "device" in ln.split()[1:2]]
    if addr in now:
        print(f"\n✅ 无线 ADB 已就绪：{addr}")
        print("   现在可以拔掉数据线了（手机和电脑要在同一个 WiFi）。")
        print("   采集照常用：python -m demand_radar watch / capture")
        print("   注意：手机重启/息屏久了无线调试会失效，重连用：wireless --scan")
        return 0
    print("\n❌ 连接失败。常见原因：手机和电脑不在同一个 WiFi / 路由器开了 AP 隔离。")
    return 1


def cmd_serve(a) -> int:
    from .web import app

    url = f"http://127.0.0.1:{a.port}"
    print(f"需求雷达看板：{url}")
    if a.open:
        import threading

        threading.Timer(1.2, lambda: _open(url)).start()
    app.run(host=a.host, port=a.port, debug=False, threaded=True)
    return 0


def cmd_sources(a) -> int:
    cfg = (sources_cfg().get("sources") or {})
    print(f"{'采集源':<16}{'状态':<8}权重")
    print("-" * 34)
    for name in all_names():
        c = cfg.get(name) or {}
        on = "✅ 启用" if c.get("enabled") else "⭕ 关闭"
        print(f"{name:<16}{on:<8}{c.get('weight', '-')}")
    print("\n配置：config/sources.yaml ｜ 词典：config/keywords.yaml")
    return 0


def cmd_status(a) -> int:
    con = db.connect()
    s = db.stats(con)
    print("需求雷达 · 数据状态")
    print(f"  素材总数 : {s['items']}")
    print(f"  需求主题 : {s['topics']}")
    print(f"  屏幕快照 : {s['screens']}")
    print(f"  最近采集 : {s['last_run'] or '从未'}")
    if s["by_source"]:
        print("  各来源：")
        for k, v in s["by_source"].items():
            print(f"    - {k}: {v}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="demand_radar",
        description="需求雷达 · 自动挖掘市场需求的赚钱系统",
    )
    sub = p.add_subparsers(dest="cmd")

    def add(name, fn, help_, **kw):
        sp = sub.add_parser(name, help=help_, **kw)
        sp.set_defaults(func=fn)
        return sp

    sp = add("run", cmd_run, "一键：采集 + 分析 + 生成报告")
    sp.add_argument("--only", help="只跑指定采集源，逗号分隔")
    sp.add_argument("--days", type=int, default=90)
    sp.add_argument("--open", action="store_true", help="完成后打开看板")

    sp = add("collect", cmd_collect, "只采集")
    sp.add_argument("--only")
    sp.add_argument("--loop", action="store_true", help="循环采集")
    sp.add_argument("--interval", type=float, default=30, help="循环间隔（分钟）")

    sp = add("analyze", cmd_analyze, "重新打分并聚合主题")
    sp.add_argument("--days", type=int, default=90)

    sp = add("report", cmd_report, "生成报告")
    sp.add_argument("--days", type=int, default=90)
    sp.add_argument("--top", type=int, default=40)
    sp.add_argument("--open", action="store_true")

    sp = add("top", cmd_top, "终端里看机会榜")
    sp.add_argument("-n", type=int, default=20)

    sp = add("watch", cmd_watch, "监听手机屏幕（人机协作采集）")
    sp.add_argument("--interval", type=float, default=4.0, help="抓屏间隔秒")
    sp.add_argument("--duration", type=float, default=0, help="监听时长秒（0=直到 Ctrl+C）")

    sp = add("capture", cmd_capture, "抓手机当前屏幕并试打分")
    sp.add_argument("--save", action="store_true", help="写入数据库")

    add("phone", cmd_phone, "检查手机连接状态")

    sp = add("wireless", cmd_wireless, "切换无线 ADB（掉线后 --scan 自动找回来）")
    sp.add_argument("--ip", help="手动指定手机 IP")
    sp.add_argument("--port", type=int, default=5555)
    sp.add_argument("--scan", action="store_true", help="扫本网段自动找手机（换 IP 后用）")
    sp.add_argument("--redo", action="store_true", help="已是无线也重新配对")
    add("sources", cmd_sources, "查看采集源开关")
    add("status", cmd_status, "查看数据状态")

    sp = add("serve", cmd_serve, "启动 Web 看板")
    sp.add_argument("--port", type=int, default=8787)
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--open", action="store_true")

    return p


def main(argv=None) -> int:
    p = build_parser()
    a = p.parse_args(argv)
    if not getattr(a, "func", None):
        p.print_help()
        print("\n最常用：python -m demand_radar run --open")
        return 0
    return a.func(a) or 0


if __name__ == "__main__":
    raise SystemExit(main())
