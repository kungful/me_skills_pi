#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp/install.py — 从本仓库还原一整套 Pi MCP 服务。

设计
  * 只读注册表：mcp/index.json 是唯一事实源，脚本不写它。
  * 幂等合并：写 ~/.pi/agent/mcp.json 时只补缺的名字，已有的绝不覆盖（除非 --force）。
  * 先体检后落盘：默认 dry-run，跑一遍告诉你哪些能装、缺什么、哪些是本机专属。
  * 占位符：{NAME} 用 环境变量 NAME 或 --var NAME=VALUE 解析；解析不出来就跳过并报缺什么。
  * 机器可读：--json 出完整报告；--quiet 时 stdout 最后一行固定 [mcp-install] RESULT <state>。

用法
  python mcp/install.py                     # 体检 + 预演（不改任何文件）
  python mcp/install.py --apply             # 把能装的写进 ~/.pi/agent/mcp.json
  python mcp/install.py --apply --install-deps   # 同时 npm -g 安装缺的包
  python mcp/install.py --server playwright --apply
  python mcp/install.py --list              # 只看清单
  python mcp/install.py --show playwright   # 打印这个服务可直接粘贴的配置片段
  python mcp/install.py --check             # 只体检（含已装服务的连通性提示）

退出码：0 = 一切就绪 / 无变化；1 = 有服务装不上或缺依赖；2 = 注册表或配置读写失败。
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HERE = Path(__file__).resolve().parent
REGISTRY = HERE / "index.json"
HOME = Path(os.path.expanduser("~"))
DEFAULT_CONFIG = HOME / ".pi" / "agent" / "mcp.json"
IS_WIN = platform.system() == "Windows"
LOG_TAG = "[mcp-install]"

RESULT = "no-change"


# --------------------------------------------------------------------------- 工具

def log(msg: str = "", quiet: bool = False) -> None:
    if not quiet:
        print(msg, flush=True)


def die(msg: str, code: int = 2) -> "NoReturn":  # type: ignore[name-defined]
    print(f"{LOG_TAG} 错误: {msg}", file=sys.stderr, flush=True)
    print(f"{LOG_TAG} RESULT failed", flush=True)
    raise SystemExit(code)


def run(cmd: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.SubprocessError) as e:
        return 127, str(e)


def which(name: str) -> str | None:
    return shutil.which(name)


def npm_global_bin_dir() -> Path | None:
    code, out = run(["npm", "prefix", "-g"], timeout=60)
    if code != 0 or not out.strip():
        return None
    prefix = Path(out.strip().splitlines()[-1].strip())
    return prefix if IS_WIN else prefix / "bin"


# ------------------------------------------------------------------------ 占位符

PLACEHOLDER_RE = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")


def collect_placeholders(obj, found: set[str] | None = None) -> set[str]:
    found = found if found is not None else set()
    if isinstance(obj, str):
        found.update(PLACEHOLDER_RE.findall(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            collect_placeholders(v, found)
    elif isinstance(obj, list):
        for v in obj:
            collect_placeholders(v, found)
    return found


def substitute(obj, values: dict[str, str]):
    if isinstance(obj, str):
        return PLACEHOLDER_RE.sub(lambda m: values.get(m.group(1), m.group(0)), obj)
    if isinstance(obj, dict):
        return {k: substitute(v, values) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute(v, values) for v in obj]
    return obj


# --------------------------------------------------------------------- 依赖体检

def resolve_launch(srv: dict, values: dict[str, str], deps_wanted: bool) -> tuple[dict | None, list[str], list[str]]:
    """返回 (pi 配置片段, 缺失项, 备注). 片段为 None 表示这个服务暂时装不了。"""
    launch = srv.get("launch") or {}
    ltype = launch.get("type")
    missing: list[str] = []
    notes: list[str] = []

    if ltype == "npm-global-bin":
        pkg, binname = launch["pkg"], launch["bin"]
        bino = which(binname)
        bindir = npm_global_bin_dir()
        if bino:
            command = bino
        elif bindir:
            cand = bindir / (binname + (".cmd" if IS_WIN else ""))
            cand2 = bindir / binname
            command = str(cand) if cand.is_file() else (str(cand2) if cand2.is_file() else None)
        else:
            command = None
        if not command:
            missing.append(f"npm 包未安装：{pkg}  →  npm i -g {pkg}")
            if not which("npm"):
                missing.append("缺 npm（先装 Node.js）")
            return None, missing, notes
        cfg = {
            "command": command,
            "args": [f"-y", pkg] if not command else list(launch.get("args") or []),
        }
        # 直接调全局 bin 时不需要把包名塞进 args
        cfg["args"] = list(launch.get("args") or [])
        if launch.get("timeout"):
            cfg["timeout"] = launch["timeout"]
        if launch.get("env"):
            cfg["env"] = substitute(launch["env"], values)
        if srv.get("description"):
            cfg["description"] = srv["description"]
        if not command and deps_wanted:
            pass
        return cfg, missing, notes

    if ltype == "uvx":
        uvx = which("uvx")
        if not uvx:
            missing.append("缺 uvx：pip install uv（或 https://docs.astral.sh/uv/）")
            return None, missing, notes
        cfg = {
            "command": uvx,
            "args": [launch["pkg"]] + list(substitute(launch.get("args") or [], values)),
        }
        bindir = str(Path(uvx).parent)
        cfg["env"] = {"UV_TOOL_BIN_DIR": bindir}
        if launch.get("timeout"):
            cfg["timeout"] = launch["timeout"]
        if srv.get("description"):
            cfg["description"] = srv["description"]
        return cfg, missing, notes

    if ltype == "http":
        url = substitute(launch.get("url", ""), values)
        if PLACEHOLDER_RE.search(url or ""):
            missing.append(f"URL 里还有未解析的占位符：{url}")
            return None, missing, notes
        cfg = {"url": url}
        if launch.get("timeout"):
            cfg["timeout"] = launch["timeout"]
        if launch.get("headers"):
            cfg["headers"] = substitute(launch["headers"], values)
        if srv.get("description"):
            cfg["description"] = srv["description"]
        if url.startswith("http://127.0.0.1") or url.startswith("http://localhost"):
            notes.append("本地 HTTP 服务，需要先把服务端跑起来再连")
        return cfg, missing, notes

    if ltype == "static":
        cfg = {
            "command": substitute(launch["command"], values),
            "args": list(substitute(launch.get("args") or [], values)),
        }
        if PLACEHOLDER_RE.search(json.dumps(cfg, ensure_ascii=False)):
            missing.append("配置里还有未解析的占位符，见 --show 里的 requires.placeholders")
        if launch.get("timeout"):
            cfg["timeout"] = launch["timeout"]
        if launch.get("env"):
            cfg["env"] = substitute(launch["env"], values)
        if srv.get("description"):
            cfg["description"] = srv["description"]
        return cfg, missing, notes

    missing.append(f"未知 launch.type: {ltype!r}")
    return None, missing, notes


def check_paths(srv: dict, values: dict[str, str]) -> list[str]:
    missing = []
    for p in (srv.get("requires") or {}).get("paths") or []:
        real = substitute(p, values)
        if PLACEHOLDER_RE.search(real):
            missing.append(f"占位符未解析：{real}")
        elif not Path(real).exists():
            missing.append(f"路径不存在：{real}")
    return missing


def check_binaries(srv: dict) -> list[str]:
    missing = []
    for b in (srv.get("requires") or {}).get("bins") or []:
        if not which(b):
            missing.append(f"命令不在 PATH：{b}")
    return missing


def check_browsers(srv: dict) -> list[str]:
    """playwright 需要的浏览器：有系统 Chrome/Edge 就算过。"""
    cands = (srv.get("requires") or {}).get("browsers") or []
    if not cands:
        return []
    known = []
    if IS_WIN:
        known = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]
    else:
        known = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
            "/usr/bin/microsoft-edge",
        ]
    if any(Path(p).exists() for p in known):
        return []
    # playwright 自己的浏览器目录
    pw = HOME / ("AppData/Local/ms-playwright" if IS_WIN else ".cache/ms-playwright")
    if pw.is_dir() and any(pw.iterdir()):
        return []
    return ["没找到可用浏览器：装 Chrome/Edge，或 npx playwright install chromium"]


# ------------------------------------------------------------------- 配置合并

def load_config(path: Path) -> dict:
    if not path.is_file():
        return {"mcpServers": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        die(f"读不了 {path}：{e}")
    if not isinstance(data, dict):
        die(f"{path} 顶层不是对象")
    data.setdefault("mcpServers", {})
    return data


def main() -> None:
    global RESULT

    ap = argparse.ArgumentParser(description="从仓库还原 Pi MCP 服务")
    ap.add_argument("--server", "-s", action="append", default=[], help="只处理这些服务名（可多次）")
    ap.add_argument("--all", "-a", action="store_true", help="含 localOnly 的本机专属服务一起处理")
    ap.add_argument("--apply", action="store_true", help="真的写进 mcp.json（默认只预演）")
    ap.add_argument("--force", action="store_true", help="同名条目已存在时用仓库版本覆盖")
    ap.add_argument("--install-deps", action="store_true", help="缺 npm 全局包时自动安装")
    ap.add_argument("--var", action="append", default=[], metavar="NAME=VALUE", help="解析占位符")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG), help="目标 mcp.json 路径")
    ap.add_argument("--list", action="store_true", help="列清单后退出")
    ap.add_argument("--show", metavar="NAME", help="打印某个服务的配置片段后退出")
    ap.add_argument("--check", action="store_true", help="只体检")
    ap.add_argument("--json", action="store_true", help="机器可读报告")
    ap.add_argument("--quiet", "-q", action="store_true", help="只回一行结果")
    args = ap.parse_args()

    if not REGISTRY.is_file():
        die(f"找不到注册表 {REGISTRY}")

    try:
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except ValueError as e:
        die(f"注册表不是合法 JSON：{e}")

    servers = reg.get("servers") or []
    values: dict[str, str] = {k: v for k, v in os.environ.items() if PLACEHOLDER_RE.fullmatch("{" + k + "}")}
    for item in args.var:
        if "=" not in item:
            die(f"--var 需要 NAME=VALUE，收到 {item!r}")
        k, v = item.split("=", 1)
        values[k.strip()] = v

    if args.list:
        print(f"{'服务':<14}{'传输':<8}{'工具':>5}  {'可移植':<8}说明")
        for s in servers:
            portable = "是" if s.get("portable") else "本机专属"
            print(f"{s['name']:<14}{s['transport']:<8}{s.get('tools', 0):>5}  {portable:<8}"
                  f"{(s.get('description') or '')[:60]}")
        print(f"\n共 {len(servers)} 个服务。安装：python mcp/install.py --apply")
        print(f"{LOG_TAG} RESULT no-change")
        return

    if args.show:
        s = next((x for x in servers if x["name"] == args.show), None)
        if not s:
            die(f"没有服务 {args.show!r}，用 --list 看全部")
        cfg, missing, notes = resolve_launch(s, values, False)
        print(json.dumps({
            "name": s["name"],
            "config": cfg,
            "requires": s.get("requires") or {},
            "placeholders": (s.get("requires") or {}).get("placeholders") or {},
            "missing": missing + check_binaries(s) + check_paths(s, values) + check_browsers(s),
            "notes": notes + (s.get("notes") or []),
        }, indent=2, ensure_ascii=False))
        print(f"{LOG_TAG} RESULT no-change")
        return

    targets = servers
    if args.server:
        wanted = set(args.server)
        unknown = wanted - {s["name"] for s in servers}
        if unknown:
            die(f"未知服务：{', '.join(sorted(unknown))}")
        targets = [s for s in servers if s["name"] in wanted]
    elif not args.all:
        targets = [s for s in servers if not s.get("localOnly")]

    config_path = Path(args.config)
    existing = load_config(config_path)
    existing_names = set(existing["mcpServers"].keys())

    report, to_add, blocked = [], {}, []
    for s in targets:
        missing = check_binaries(s) + check_paths(s, values) + check_browsers(s)
        cfg, launch_missing, notes = resolve_launch(s, values, args.install_deps)
        missing += launch_missing
        status = "ready"
        if cfg is None or missing:
            status = "blocked"
        if s["name"] in existing_names and not args.force:
            status = status if cfg is None or missing else "exists"
        if status == "blocked":
            blocked.append(s["name"])
        elif status == "ready":
            to_add[s["name"]] = cfg
        report.append({
            "name": s["name"],
            "title": s.get("title", ""),
            "status": status,
            "tools": s.get("tools", 0),
            "missing": missing,
            "notes": notes + (s.get("notes") or []),
            "localOnly": bool(s.get("localOnly")),
            "config": cfg,
        })

    # 可选：自动装 npm 全局包
    if args.install_deps and not args.check:
        for s, r in zip(targets, report):
            if r["status"] != "blocked":
                continue
            launch = s.get("launch") or {}
            if launch.get("type") != "npm-global-bin":
                continue
            pkg = launch["pkg"]
            log(f"→ 安装 {pkg} …", args.quiet)
            code, out = run(["npm", "install", "-g", pkg], timeout=900)
            if code != 0:
                log(f"  失败：{out.strip()[:300]}", args.quiet)
                continue
            cfg, miss, notes = resolve_launch(s, values, True)
            if cfg and not miss:
                r.update(status="ready", missing=[], config=cfg)
                to_add[s["name"]] = cfg
                blocked = [b for b in blocked if b != s["name"]]

    # 落盘
    written, backed_up = [], None
    if args.apply and not args.check and to_add:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        if config_path.is_file():
            backed_up = config_path.with_name(
                config_path.name + ".bak-" + time.strftime("%Y%m%d-%H%M%S"))
            shutil.copy2(config_path, backed_up)
        for name, cfg in to_add.items():
            existing["mcpServers"][name] = cfg
            written.append(name)
        config_path.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 输出
    if args.json:
        print(json.dumps({
            "configPath": str(config_path),
            "applied": bool(args.apply and written),
            "backup": str(backed_up) if backed_up else None,
            "written": written,
            "blocked": blocked,
            "servers": report,
        }, indent=2, ensure_ascii=False))
    else:
        log("", args.quiet)
        log(f"目标配置：{config_path}", args.quiet)
        log("", args.quiet)
        for r in report:
            mark = {"ready": "✓ 可装", "exists": "• 已存在", "blocked": "✗ 缺依赖"}[r["status"]]
            log(f"  {mark}  {r['name']:<14}{r['tools']:>4} tools  {r['title']}", args.quiet)
            if r["missing"] and r["status"] == "blocked":
                for m in r["missing"]:
                    log(f"           - {m}", args.quiet)
            if r["status"] == "blocked" and r["localOnly"]:
                log("           - 本机专属：需先在本机准备源码/可执行文件，"
                    "用 --var 或环境变量给占位符赋值", args.quiet)
        if written:
            log("", args.quiet)
            log(f"已写入 {len(written)} 个服务：{', '.join(written)}", args.quiet)
            if backed_up:
                log(f"原配置已备份：{backed_up}", args.quiet)
            log("", args.quiet)
            log("下一步：在 pi 里 /reload（或重开会话），然后 pi mcp list 看连通性", args.quiet)
        elif not args.apply:
            log("", args.quiet)
            log("这是预演。加 --apply 才写文件。", args.quiet)
        if blocked:
            log("", args.quiet)
            log(f"装不上 {len(blocked)} 个：{', '.join(blocked)}（缺依赖见上）", args.quiet)

    if not args.apply and to_add:
        RESULT = "dry-run"
    elif written:
        RESULT = "applied"
    else:
        RESULT = "no-change"
    if blocked:
        RESULT = "applied" if written else ("dry-run" if not args.apply else "failed")
    print(f"{LOG_TAG} RESULT {RESULT}", flush=True)
    raise SystemExit(0 if not blocked or written else 1)


if __name__ == "__main__":
    main()
