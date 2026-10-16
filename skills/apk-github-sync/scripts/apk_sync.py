#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apk-sync  —  把本机 Pi 开发出来的 APK 软件包 + 源代码镜像到 GitHub 仓库。

和 skills-github-sync 是同一套思路（镜像 / 幂等 / 无感 / 自动触发），
但管理的是 `apks/` 目录，并且按分类（category）分文件夹存放：

    <repo>/apks/
      README.md
      index.json
      <category>/
        <slug>/
          <slug>.apk        # 编译产物
          meta.json         # 版本 / 体积 / sha256 / 来源路径
          src/              # 源代码快照（已剔除 build/缓存等）

仓库里的 `apks/` 完全由本脚本的配置（~/.pi/agent/apk-sync.json）驱动：
配置里删掉一个 app，仓库里对应目录也会删掉（git 历史仍保留）。

用法
  python apk_sync.py                 # 同步 + 提交 + 推送
  python apk_sync.py --dry-run       # 只显示会做什么，不改任何东西
  python apk_sync.py --no-push       # 只提交到本地仓库
  python apk_sync.py --status        # 显示配置 / 发现的 app / 仓库状态
  python apk_sync.py --quiet         # 静默：stdout 只输出 RESULT 行
  python apk_sync.py --config <path> # 指定配置文件
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path

# Windows 控制台默认 GBK，强制 UTF-8 输出，避免中文日志乱码
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# ----------------------------------------------------------------------------- 常量

HOME = Path(os.path.expanduser("~"))
AGENT_DIR = HOME / ".pi" / "agent"

DEFAULT_CONFIG_PATH = AGENT_DIR / "apk-sync.json"
DEFAULT_REPO_DIR = HOME / ".pi" / "skills-repo"
LOG_PATH = AGENT_DIR / "apk-sync.log"
# 和 skills 同步共用同一把仓库锁：同一时刻只有一个人能提交这个仓库
LOCK_PATH = AGENT_DIR / "skills-sync.lock"
LOCK_STALE_SECONDS = 15 * 60

# 永远忽略的目录（构建产物 / 缓存 / VCS）
IGNORE_DIRS = {
    ".git", ".svn", ".hg",
    "build", "out", ".gradle", ".kotlin", ".idea",
    "node_modules", ".venv", "venv", "env",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".cache",
    "intermediates", "generated", ".cxx", ".externalNativeBuild",
    "$RECYCLE.BIN", "System Volume Information",
}
# 永远忽略的文件后缀
IGNORE_FILE_SUFFIXES = (
    ".apk", ".idsig", ".aab", ".ap_", ".pyc", ".pyo", ".log", ".tmp", ".swp",
    ".swo", ".bak", "~", ".hprof", ".class", ".dex", ".jar.bak",
    ".db-wal", ".db-shm",
)
# 永远忽略的文件名
IGNORE_FILE_NAMES = {"local.properties", ".DS_Store", "Thumbs.db", "nul", "local.json", "secrets.json", ".env"}

README_NAME = "README.md"
INDEX_NAME = "index.json"
DEFAULT_SUBDIR = "apks"

TEMPLATE_CONFIG = {
    "remote": "https://github.com/<你的用户名>/me_skills_pi.git",
    "branch": "main",
    "repoDir": str(DEFAULT_REPO_DIR).replace("\\", "/"),
    "subdir": DEFAULT_SUBDIR,
    "commitPrefix": "apks",
    "token": "",
    "tokenEnv": "GITHUB_TOKEN",
    "proxy": "",
    "autoCreateRemote": False,
    # 额外排除的目录名（相对项目根，任意层级都生效）
    "excludeDirs": ["data", "logs", "screens"],
    # app 注册表：slug 是仓库里的目录名，source 是项目根，apk 是产物路径或 glob
    "apps": [],
    # 可选：自动发现没注册的 APK（按 glob 扫），放进 <subdir>/<scanCategory>/
    "scan": {
        "enabled": False,
        "category": "_auto",
        "globs": [],
        "excludeGlobs": [],
    },
}


# ----------------------------------------------------------------------------- 日志

QUIET = False


def log(msg: str, console: bool | None = None) -> None:
    if console is None:
        console = not QUIET
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    if console:
        print(line, flush=True)
    try:
        AGENT_DIR.mkdir(parents=True, exist_ok=True)
        if LOG_PATH.exists() and LOG_PATH.stat().st_size > 512 * 1024:
            LOG_PATH.write_text("", encoding="utf-8")
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def emit_result(state: str) -> None:
    """给调用方（扩展 / 定时任务）解析的机器可读结果，始终输出到 stdout。"""
    print(f"[apk-sync] RESULT {state}", flush=True)
    try:
        AGENT_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] RESULT {state}\n")
    except OSError:
        pass


def die(msg: str, code: int = 1) -> "None":
    log(f"ERROR: {msg}", console=True)
    sys.exit(code)


# ----------------------------------------------------------------------------- 配置

def default_config() -> dict:
    return json.loads(json.dumps(TEMPLATE_CONFIG, ensure_ascii=False))


def load_config(path: Path) -> dict:
    cfg = default_config()
    if path.exists():
        try:
            user = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            die(f"配置文件不是合法 JSON: {path} ({exc})")
        if not isinstance(user, dict):
            die(f"配置文件顶层必须是对象: {path}")
        cfg.update(user)
    return cfg


def save_config(cfg: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resolve_token(cfg: dict) -> str:
    env_name = cfg.get("tokenEnv") or "GITHUB_TOKEN"
    token = os.environ.get(env_name, "").strip()
    if token:
        return token
    return str(cfg.get("token") or "").strip()


# ----------------------------------------------------------------------------- 进程工具

_CREATE_NO_WINDOW = 0x08000000


def _hidden_process_kwargs() -> dict:
    """让子进程绝不出现在屏幕上（Windows）。非 Windows 返回空。"""
    if os.name != "nt":
        return {}
    kwargs = {"creationflags": _CREATE_NO_WINDOW}
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = si
    except AttributeError:  # pragma: no cover
        pass
    return kwargs


def run(cmd, cwd=None, env=None, check=False, timeout=300):
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    full_env.setdefault("GIT_TERMINAL_PROMPT", "0")
    full_env.setdefault("GCM_INTERACTIVE", "never")
    proc = subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, env=full_env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        **_hidden_process_kwargs(),
    )
    out = proc.stdout.decode("utf-8", "replace").strip()
    err = proc.stderr.decode("utf-8", "replace").strip()
    if check and proc.returncode != 0:
        raise RuntimeError(f"{' '.join(map(str, cmd))} 失败({proc.returncode}): {err or out}")
    return proc.returncode, out, err


def git(args, cwd, check=True, token: str | None = None, timeout=600):
    cmd = ["git", "-c", "credential.interactive=false"]
    if token:
        blob = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        cmd += ["-c", f"http.extraheader=Authorization: Basic {blob}"]
    cmd += list(args)
    code, out, err = run(cmd, cwd=cwd, timeout=timeout)
    if check and code != 0:
        raise RuntimeError(f"git {' '.join(map(str, args))} 失败: {err or out}")
    return code, out, err


# ----------------------------------------------------------------------------- 锁

class SyncLock:
    def __init__(self, path: Path, enabled: bool = True):
        self.path = path
        self.enabled = enabled
        self.acquired = False

    def __enter__(self):
        if not self.enabled:
            return self
        if self.path.exists():
            try:
                age = time.time() - self.path.stat().st_mtime
            except OSError:
                age = 0
            if age > LOCK_STALE_SECONDS:
                log(f"清理过期锁({int(age)}s): {self.path}")
                try:
                    self.path.unlink()
                except OSError:
                    pass
            else:
                return self  # 已有同步在跑，静默跳过
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(f"{os.getpid()}\n", encoding="utf-8")
            self.acquired = True
        except OSError:
            pass
        return self

    def __exit__(self, *exc):
        if self.acquired:
            try:
                self.path.unlink()
            except OSError:
                pass
        return False


# ----------------------------------------------------------------------------- 工具

def norm(p) -> str:
    return str(p).replace("\\", "/")


def expand(p: str) -> Path:
    return Path(os.path.expanduser(str(p)))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha_of_tree(root: Path, extra_dirs: set[str]) -> str:
    """对目录内容做指纹（路径 + 内容），用于判断是否需要重新拷贝。"""
    ignore_dirs = IGNORE_DIRS | set(extra_dirs or ())
    h = hashlib.sha1()
    if not root.exists():
        return h.hexdigest()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in ignore_dirs)
        for fn in sorted(filenames):
            if fn in IGNORE_FILE_NAMES or fn.endswith(IGNORE_FILE_SUFFIXES):
                continue
            fp = Path(dirpath) / fn
            rel = fp.relative_to(root).as_posix()
            h.update(rel.encode("utf-8", "replace"))
            try:
                h.update(fp.read_bytes())
            except OSError:
                h.update(b"<unreadable>")
    return h.hexdigest()


def slugify(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", str(name)).strip("-")
    return s or "app"


def human_size(n: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    f = float(n)
    i = 0
    while f >= 1024 and i < len(units) - 1:
        f /= 1024
        i += 1
    return f"{f:.1f} {units[i]}" if i else f"{int(f)} B"


def find_apk(pattern: str) -> Path | None:
    """pattern 可以是具体文件，也可以带通配符。多个匹配时取 mtime 最新那个。"""
    raw = str(pattern)
    if any(ch in raw for ch in "*?["):
        base = Path(raw)
        parent = base.parent
        # 通配符可能出现在任何一层，做一次受限递归匹配
        parent_str = str(parent)
        wildcard_at = min(
            [parent_str.find(c) for c in "*?[" if c in parent_str] or [len(parent_str)]
        )
        root_str = parent_str[: wildcard_at]
        root = Path(root_str).parent if root_str.endswith(("/", os.sep)) else Path(root_str)
        root = Path(root_str)
        if not root.exists():
            return None
        matches = [p for p in root.rglob("*") if p.is_file() and fnmatch(norm(p), norm(raw))]
        if not matches:
            return None
        return max(matches, key=lambda p: p.stat().st_mtime)
    p = expand(raw)
    return p if p.is_file() else None


def parse_version(explicit: str, apk_name: str, manifest: Path | None) -> str:
    if explicit:
        return str(explicit)
    m = re.search(r"[vV]?(\d+(?:\.\d+){1,3})", Path(apk_name).stem)
    if m:
        return m.group(1)
    if manifest and manifest.is_file():
        try:
            text = manifest.read_text(encoding="utf-8", errors="replace")
            m = re.search(r'android:versionName\s*=\s*"([^"]+)"', text)
            if m:
                return m.group(1)
        except OSError:
            pass
    return ""


# ----------------------------------------------------------------------------- 扫描

def scan_apps(cfg: dict) -> list[dict]:
    """把配置里的 apps 解析成实际要同步的条目，跳过不存在的。"""
    out: list[dict] = []
    for raw in cfg.get("apps", []):
        if not isinstance(raw, dict):
            continue
        slug = slugify(raw.get("slug") or raw.get("title") or "")
        title = str(raw.get("title") or slug)
        category = slugify(raw.get("category") or "misc")
        src = expand(raw["source"]) if raw.get("source") else None
        apk = find_apk(raw["apk"]) if raw.get("apk") else None
        if src is None and apk is None:
            log(f"  ! 跳过 {slug}: source/apk 都不存在")
            continue
        if raw.get("apk") and apk is None:
            log(f"  ! {slug}: 找不到 APK（{raw.get('apk')}），只同步源码")
        if src and not src.is_dir():
            log(f"  ! {slug}: 源码目录不存在（{src}），只同步 APK")
            src = None
        out.append({
            "slug": slug,
            "title": title,
            "category": category,
            "categoryTitle": str(raw.get("categoryTitle") or raw.get("category") or category),
            "package": str(raw.get("package") or ""),
            "version": str(raw.get("version") or ""),
            "notes": str(raw.get("notes") or ""),
            "source": src,
            "apk": apk,
            "auto": False,
        })

    scan = cfg.get("scan") or {}
    if scan.get("enabled"):
        known = {sha256_file(a["apk"]) for a in out if a["apk"]}
        excludes = [str(g) for g in (scan.get("excludeGlobs") or [])]
        cat = slugify(scan.get("category") or "_auto")
        for g in scan.get("globs", []):
            gp = expand(g)
            root = gp
            while any(ch in str(root) for ch in "*?[") and str(root) != str(root.parent):
                root = root.parent
            if not root.exists():
                continue
            for p in root.rglob("*.apk"):
                np = norm(p)
                if not fnmatch(np, norm(gp)):
                    continue
                if any(fnmatch(np, e) for e in excludes):
                    continue
                sh = sha256_file(p)
                if sh in known:
                    continue
                known.add(sh)
                slug = slugify(p.stem)
                out.append({
                    "slug": slug, "title": p.stem, "category": cat,
                    "categoryTitle": "自动收录（未登记）", "package": "",
                    "version": parse_version("", p.name, None), "notes": "由 scan 规则自动发现，建议登记到 apps",
                    "source": None, "apk": p, "auto": True,
                })
    return out


# ----------------------------------------------------------------------------- 镜像

def ignore_for_copy(dirpath, names, extra_dirs: set[str]):
    ignored = set()
    for n in names:
        if n in IGNORE_DIRS or n in extra_dirs:
            ignored.add(n)
        elif n in IGNORE_FILE_NAMES or n.endswith(IGNORE_FILE_SUFFIXES):
            ignored.add(n)
    return ignored


def mirror_apps(repo_dir: Path, subdir: str, apps: list[dict], cfg: dict,
                dry_run: bool = False) -> tuple[list[str], list[str], list[str]]:
    """返回 (added, changed, removed)。"""
    dest_root = repo_dir / subdir
    extra_dirs = set(cfg.get("excludeDirs") or [])
    added, changed, removed = [], [], []
    desired: set[str] = set()

    if not dry_run:
        dest_root.mkdir(parents=True, exist_ok=True)

    for app in apps:
        rel = f"{app['category']}/{app['slug']}"
        desired.add(rel)
        dst = dest_root / app["category"] / app["slug"]
        meta_path = dst / "meta.json"
        is_new = not dst.exists()

        # 计算内容指纹，没变就跳过拷贝（省 IO）
        apk_sha = sha256_file(app["apk"]) if app["apk"] else ""
        src_sha = sha_of_tree(app["source"], extra_dirs) if app["source"] else ""
        new_fp = f"{apk_sha}:{src_sha}"
        old_fp = ""
        old_meta = {}
        if meta_path.is_file():
            try:
                old_meta = json.loads(meta_path.read_text(encoding="utf-8"))
                old_fp = f"{old_meta.get('apkSha256', '')}:{old_meta.get('srcSha', '')}"
            except (OSError, json.JSONDecodeError):
                old_meta = {}

        if not is_new and old_fp == new_fp and not app.get("auto"):
            continue  # 完全没变

        if is_new:
            added.append(rel)
            log(f"  + {rel}")
        else:
            changed.append(rel)
            log(f"  ~ {rel}")

        if dry_run:
            continue

        # 重建该 app 目录
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)
        dst.mkdir(parents=True, exist_ok=True)

        if app["apk"]:
            shutil.copy2(app["apk"], dst / f"{app['slug']}.apk")

        if app["source"]:
            shutil.copytree(
                app["source"], dst / "src",
                ignore=lambda d, n: ignore_for_copy(d, n, extra_dirs),
                symlinks=True, ignore_dangling_symlinks=True,
            )

        manifest = None
        if app["source"]:
            for cand in ("AndroidManifest.xml", "app/src/main/AndroidManifest.xml"):
                if (app["source"] / cand).is_file():
                    manifest = app["source"] / cand
                    break
        apk_stat = app["apk"].stat() if app["apk"] else None
        meta = {
            "slug": app["slug"],
            "title": app["title"],
            "category": app["category"],
            "categoryTitle": app["categoryTitle"],
            "package": app["package"],
            "version": parse_version(app["version"], app["apk"].name if app["apk"] else "", manifest),
            "notes": app["notes"],
            "apk": f"{app['slug']}.apk" if app["apk"] else "",
            "apkName": app["apk"].name if app["apk"] else "",
            "apkSize": apk_stat.st_size if apk_stat else 0,
            "apkSha256": apk_sha,
            "srcSha": src_sha,
            "hasSource": bool(app["source"]),
            "sourcePath": norm(app["source"]) if app["source"] else "",
            "builtAt": datetime.fromtimestamp(apk_stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S") if apk_stat else "",
            "syncedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "auto": bool(app.get("auto")),
        }
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 删除仓库里已经不存在的 app 目录
    if dest_root.exists():
        for cat_dir in sorted(p for p in dest_root.iterdir() if p.is_dir()):
            for app_dir in sorted(p for p in cat_dir.iterdir() if p.is_dir()):
                rel = f"{cat_dir.name}/{app_dir.name}"
                if rel not in desired:
                    log(f"  - 移除已删除的 app: {rel}")
                    removed.append(rel)
                    if not dry_run:
                        shutil.rmtree(app_dir, ignore_errors=True)
            if not dry_run and cat_dir.is_dir() and not any(cat_dir.iterdir()):
                shutil.rmtree(cat_dir, ignore_errors=True)
    return added, changed, removed


def write_readme(repo_dir: Path, subdir: str, apps: list[dict]) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = sum((a["apk"].stat().st_size if a and a["apk"] else 0) for a in apps)
    lines = [
        "# Pi 开发的 APK 软件包",
        "",
        f"本目录由 [`apk-github-sync`](../skills/apk-github-sync/) 自动从本机镜像同步。",
        f"最后同步：**{now}**　|　共 **{len(apps)}** 个应用　|　APK 合计 **{human_size(total)}**",
        "",
        "每个应用一个子目录，里面有编译好的 APK 和对应的源代码：",
        "",
        "```",
        f"{subdir}/<分类>/<应用>/",
        "  <slug>.apk     # 编译产物",
        "  meta.json      # 版本 / 体积 / sha256 / 来源",
        "  src/           # 源代码快照（已剔除 build、缓存等）",
        "```",
        "",
        "> ⚠️ 本仓库是**公开**的，源代码里可能带有本地签名用的 keystore。",
        "> 如果不想公开，请把仓库改成 private，或在本机 `apk-sync.json` 里加排除规则。",
        "",
    ]

    # 按分类分组
    cats: dict[str, list[dict]] = {}
    for a in apps:
        cats.setdefault(a["category"], []).append(a)
    cat_titles = {a["category"]: a["categoryTitle"] for a in apps}

    for cat in sorted(cats):
        lines += [f"## {cat_titles.get(cat, cat)}", ""]
        lines += ["| 应用 | 版本 | APK | 源码 | 体积 | 说明 |", "|---|---|---|---|---|---|"]
        for a in sorted(cats[cat], key=lambda x: x["title"]):
            apk_meta = read_meta(repo_dir, subdir, a)
            ver = apk_meta.get("version") or "-"
            apk_size = human_size(apk_meta.get("apkSize", 0)) if apk_meta else "-"
            if apk_meta and apk_meta.get("apk"):
                apk_cell = f"[`{a['slug']}.apk`]({cat}/{a['slug']}/{a['slug']}.apk)"
            else:
                apk_cell = "-"
            src_cell = f"[`src/`]({cat}/{a['slug']}/src/)" if (apk_meta or {}).get("hasSource") or a["source"] else "-"
            note = (a["notes"] or "").replace("|", "\\|").replace("\n", " ").strip()
            lines.append(f"| **{a['title']}** | {ver} | {apk_cell} | {src_cell} | {apk_size} | {note} |")
        lines.append("")

    (repo_dir / subdir / README_NAME).write_text("\n".join(lines), encoding="utf-8")

    index = {
        "generatedAt": now,
        "count": len(apps),
        "totalApkBytes": total,
        "categories": [
            {
                "id": cat,
                "title": cat_titles.get(cat, cat),
                "apps": [
                    {
                        "slug": a["slug"],
                        "title": a["title"],
                        "version": read_meta(repo_dir, subdir, a).get("version", ""),
                        "apk": f"{cat}/{a['slug']}/{a['slug']}.apk" if a["apk"] else "",
                        "source": f"{cat}/{a['slug']}/src/" if a["source"] else "",
                        "size": read_meta(repo_dir, subdir, a).get("apkSize", 0),
                        "sha256": read_meta(repo_dir, subdir, a).get("apkSha256", ""),
                        "builtAt": read_meta(repo_dir, subdir, a).get("builtAt", ""),
                        "notes": a["notes"],
                    }
                    for a in sorted(cats[cat], key=lambda x: x["title"])
                ],
            }
            for cat in sorted(cats)
        ],
    }
    (repo_dir / subdir / INDEX_NAME).write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


_META_CACHE: dict[str, dict] = {}


def read_meta(repo_dir: Path, subdir: str, app: dict) -> dict:
    key = f"{app['category']}/{app['slug']}"
    if key in _META_CACHE:
        return _META_CACHE[key]
    p = repo_dir / subdir / app["category"] / app["slug"] / "meta.json"
    data = {}
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    _META_CACHE[key] = data
    return data


# ----------------------------------------------------------------------------- git 仓库

def remote_slug(remote: str) -> str:
    m = re.search(r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?/?$", str(remote))
    return f"{m.group(1)}/{m.group(2)}" if m else ""


def ensure_repo(repo_dir: Path, remote: str, branch: str) -> None:
    if not (repo_dir / ".git").is_dir():
        log(f"初始化本地仓库: {repo_dir}")
        repo_dir.mkdir(parents=True, exist_ok=True)
        git(["init", "-b", branch], cwd=repo_dir, check=False)
        git(["config", "core.autocrlf", "false"], cwd=repo_dir, check=False)
    code, out, _ = git(["remote", "get-url", "origin"], cwd=repo_dir, check=False)
    if remote:
        if code != 0 or out.strip() != remote:
            git(["remote", "remove", "origin"], cwd=repo_dir, check=False)
            git(["remote", "add", "origin", remote], cwd=repo_dir)


def has_remote(repo_dir: Path) -> bool:
    code, out, _ = git(["remote"], cwd=repo_dir, check=False)
    return code == 0 and bool(out.strip())


def commit_and_push(repo_dir: Path, cfg: dict, token: str, added: list[str], changed: list[str],
                    removed: list[str], branch: str, no_push: bool) -> str:
    code, out, _ = git(["status", "--porcelain"], cwd=repo_dir, check=False)
    if not out.strip():
        log("没有变化，跳过提交。")
        return "no-change"

    git(["add", "-A"], cwd=repo_dir)
    code, staged, _ = git(["diff", "--cached", "--name-only"], cwd=repo_dir, check=False)
    if not staged.strip():
        log("暂存区为空，跳过提交。")
        return "no-change"

    prefix = cfg.get("commitPrefix") or "apks"
    parts = []
    if added:
        parts.append("新增 " + ", ".join(added[:8]) + ("…" if len(added) > 8 else ""))
    if changed:
        parts.append("更新 " + ", ".join(changed[:8]) + ("…" if len(changed) > 8 else ""))
    if removed:
        parts.append("删除 " + ", ".join(removed[:8]) + ("…" if len(removed) > 8 else ""))
    if not parts:
        parts.append(f"同步 {len(staged.splitlines())} 个文件")
    subject = f"{prefix}: " + "；".join(parts)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body = f"Auto-synced by apk-github-sync at {stamp}\n\n" + "\n".join(
        f"- {f}" for f in staged.splitlines()[:60]
    )

    git(["commit", "-m", subject, "-m", body], cwd=repo_dir)
    log(f"已提交: {subject}")

    if no_push:
        return "committed"
    if not has_remote(repo_dir):
        log("没有配置 remote，跳过推送。")
        return "committed"

    # 先拉一下，减少和 skills 同步抢仓库导致的 non-fast-forward
    git(["fetch", "origin", branch], cwd=repo_dir, check=False, token=token or None)
    git(["pull", "--rebase", "--autostash", "origin", branch],
        cwd=repo_dir, check=False, token=token or None)

    push = ["push", "-u", "origin", f"HEAD:{branch}"]
    code, out, err = git(push, cwd=repo_dir, check=False, token=token or None)
    if code != 0:
        log(f"推送失败，尝试 pull --rebase 后重试: {err or out}")
        git(["pull", "--rebase", "--autostash", "origin", branch],
            cwd=repo_dir, check=False, token=token or None)
        code, out, err = git(push, cwd=repo_dir, check=False, token=token or None)
        if code != 0:
            log(f"ERROR: 推送最终失败: {err or out}", console=True)
            return "failed"
    log("推送成功。")
    return "pushed"


# ----------------------------------------------------------------------------- 命令

def cmd_status(cfg: dict, repo_dir: Path) -> int:
    subdir = cfg.get("subdir") or DEFAULT_SUBDIR
    print(f"配置文件 : {DEFAULT_CONFIG_PATH}")
    print(f"仓库目录 : {repo_dir}  {'(已初始化)' if (repo_dir / '.git').is_dir() else '(未初始化)'}")
    print(f"远端     : {cfg.get('remote') or '(未配置)'}")
    print(f"分支     : {cfg.get('branch')}")
    print(f"子目录   : {subdir}")
    print(f"token    : {'已配置' if resolve_token(cfg) else '未配置'}")
    apps = scan_apps(cfg)
    print(f"登记应用 : {len(apps)}")
    for a in apps:
        apk = a["apk"].name if a["apk"] else "(无)"
        ver = parse_version(a["version"], a["apk"].name if a["apk"] else "", None)
        print(f"  * [{a['category']}] {a['slug']:16s} {a['title']}  v{ver or '?'}  apk={apk}  "
              f"src={'有' if a['source'] else '无'}")
    if (repo_dir / ".git").is_dir():
        _, out, _ = git(["status", "--porcelain"], cwd=repo_dir, check=False)
        print(f"仓库未提交变更: {len(out.splitlines())} 个文件")
    return 0


def cmd_sync(cfg: dict, repo_dir: Path, args) -> int:
    token = resolve_token(cfg)
    branch = cfg.get("branch") or "main"
    remote = cfg.get("remote") or ""
    subdir = cfg.get("subdir") or DEFAULT_SUBDIR
    if not remote or "<你的用户名>" in str(remote):
        log("还没配置远端仓库地址。请先编辑 ~/.pi/agent/apk-sync.json 的 remote。", console=True)
        emit_result("unconfigured")
        return 2 if not args.dry_run else 0

    apps = scan_apps(cfg)
    if not apps:
        log("没有登记任何 app，结束。", console=True)
        emit_result("no-apps")
        return 0
    log(f"登记 {len(apps)} 个 app")

    if args.dry_run:
        log("--dry-run：只展示，不写文件/不改 git", console=True)
        for a in apps:
            print(f"  * [{a['category']}] {a['slug']}  apk={a['apk']}  src={a['source']}")
        emit_result("dry-run")
        return 0

    ensure_repo(repo_dir, remote, branch)

    added, changed, removed = mirror_apps(repo_dir, subdir, apps, cfg, dry_run=False)

    content_changed = bool(added or changed or removed)
    if content_changed or not (repo_dir / subdir / README_NAME).exists():
        _META_CACHE.clear()
        write_readme(repo_dir, subdir, apps)
    else:
        log("app 内容无变化，跳过 README/索引重写。")

    state = commit_and_push(repo_dir, cfg, token, added, changed, removed, branch, args.no_push)
    emit_result(state)
    return 0 if state != "failed" else 1


# ----------------------------------------------------------------------------- main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="把本机 Pi 开发的 APK + 源码镜像同步到 GitHub")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    ap.add_argument("--remote", default="", help="完整远端地址（覆盖配置）")
    ap.add_argument("--token", default="", help="GitHub PAT（仅本次使用）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--quiet", action="store_true",
                    help="静默模式：进度只进日志文件，stdout 仅输出 RESULT 行")
    args = ap.parse_args(argv)

    global QUIET
    QUIET = bool(args.quiet)

    cfg_path = Path(os.path.expanduser(args.config))
    cfg = load_config(cfg_path)
    if args.token:
        cfg["token"] = args.token
    if args.remote:
        cfg["remote"] = args.remote

    repo_dir = Path(os.path.expanduser(str(cfg.get("repoDir") or DEFAULT_REPO_DIR)))

    if args.status:
        return cmd_status(cfg, repo_dir)

    # 和 skills 同步共用一把仓库锁：同一时刻只允许一个同步进程
    with SyncLock(LOCK_PATH) as lock:
        if not lock.acquired and lock.enabled and LOCK_PATH.exists():
            log("已有同步在进行中（skills 或 apk），本次跳过。", console=True)
            emit_result("busy")
            return 0
        return cmd_sync(cfg, repo_dir, args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001
        log(f"未处理异常: {exc}")
        sys.exit(1)
