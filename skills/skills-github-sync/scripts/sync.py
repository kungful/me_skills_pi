#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pi-skills-sync  —  把本机 Pi 的 skills 镜像到 GitHub 仓库并自动提交/推送。

设计要点
  * 镜像式：源目录（~/.pi/agent/skills、~/.agents/skills ...）只读，仓库里保存副本。
    仓库里也包含本技能自身（skills-github-sync），所以是"自己传自己"。
  * 幂等：内容没变时不产生 commit，不会刷空提交。
  * 无感：token 不写进 remote URL / .git/config，只在 push 时用临时 http header 传。
  * 通用：可被扩展（Pi / pi-web）调用，也可被定时任务/手动调用。

用法
  python sync.py                 # 同步 + 提交 + 推送
  python sync.py --dry-run       # 只显示会做什么，不改任何东西
  python sync.py --no-push       # 只提交到本地仓库
  python sync.py --status        # 显示当前状态
  python sync.py --init          # 用配置里的 remote 初始化本地仓库并推送
  python sync.py --init --repo kungful/pi-skills --token ghp_xxx
                                 # 顺便通过 GitHub API 创建远端仓库
  python sync.py --config <path> # 指定配置文件
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
import urllib.error
import urllib.request
from datetime import datetime
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
SKILLS_DIR = AGENT_DIR / "skills"
AGENTS_SKILLS_DIR = HOME / ".agents" / "skills"

DEFAULT_CONFIG_PATH = AGENT_DIR / "skills-sync.json"
DEFAULT_REPO_DIR = HOME / ".pi" / "skills-repo"
LOG_PATH = AGENT_DIR / "skills-sync.log"
LOCK_PATH = AGENT_DIR / "skills-sync.lock"
LOCK_STALE_SECONDS = 15 * 60

IGNORE_DIRS = {
    "__pycache__", ".git", ".svn", ".hg", "node_modules", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".idea", ".vscode",
    ".DS_Store", "$RECYCLE.BIN", "System Volume Information",
}
IGNORE_FILE_SUFFIXES = (".pyc", ".pyo", ".log", ".tmp", ".swp", ".swo", ".bak", "~")

README_NAME = "README.md"
INDEX_NAME = "index.json"

TEMPLATE_CONFIG = {
    "remote": "https://github.com/<你的用户名>/pi-skills.git",
    "branch": "main",
    "repoDir": str(DEFAULT_REPO_DIR).replace("\\", "/"),
    "sources": [
        str(SKILLS_DIR).replace("\\", "/"),
        str(AGENTS_SKILLS_DIR).replace("\\", "/"),
    ],
    "token": "",
    "tokenEnv": "GITHUB_TOKEN",
    "proxy": "",
    "commitPrefix": "skills",
    "autoCreateRemote": True,
}


# ----------------------------------------------------------------------------- 日志

QUIET = False


def log(msg: str, console: bool | None = None) -> None:
    """写日志。console=None 时跟随 --quiet：静默模式下只写文件。"""
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
    print(f"[skills-sync] RESULT {state}", flush=True)
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
    cfg = json.loads(json.dumps(TEMPLATE_CONFIG))
    return cfg


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

def run(cmd, cwd=None, env=None, check=False, timeout=300):
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    full_env.setdefault("GIT_TERMINAL_PROMPT", "0")
    full_env.setdefault("GCM_INTERACTIVE", "never")
    proc = subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, env=full_env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
    )
    out = proc.stdout.decode("utf-8", "replace").strip()
    err = proc.stderr.decode("utf-8", "replace").strip()
    if check and proc.returncode != 0:
        raise RuntimeError(f"{' '.join(map(str, cmd))} 失败({proc.returncode}): {err or out}")
    return proc.returncode, out, err


def git(args, cwd, check=True, token: str | None = None, timeout=300):
    cmd = ["git"]
    if token:
        # 只在本次命令里注入鉴权，不落盘
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


# ----------------------------------------------------------------------------- skill 扫描

FM_RE = re.compile(r"^---\s*$")


def read_frontmatter(skill_md: Path) -> dict:
    """极简 YAML frontmatter 解析：只取 name / description（支持单行和块标量）。"""
    meta: dict = {}
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return meta
    lines = text.splitlines()
    if not lines or not FM_RE.match(lines[0]):
        return meta
    end = None
    for i in range(1, len(lines)):
        if FM_RE.match(lines[i]):
            end = i
            break
    if end is None:
        return meta

    key = None
    buf: list[str] = []
    block_indent = None

    def flush():
        nonlocal key, buf, block_indent
        if key:
            val = "\n".join(buf).strip() if block_indent is not None else " ".join(buf).strip()
            meta[key] = re.sub(r"\s*\n\s*", " ", val).strip()
        key, buf, block_indent = None, [], None

    for raw in lines[1:end]:
        if block_indent is not None:
            if raw.strip() == "" or raw.startswith(" " * block_indent):
                buf.append(raw.strip())
                continue
            flush()
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+)\s*:\s*(.*)$", raw)
        if not m:
            continue
        flush()
        k, v = m.group(1), m.group(2).strip()
        if v in (">", ">-", "|", "|-", ">+", "|+"):
            key = k
            block_indent = len(raw) - len(raw.lstrip()) + 2
            buf = []
        elif v.startswith('"') and v.endswith('"') and len(v) >= 2:
            meta[k] = v[1:-1]
        elif v.startswith("'") and v.endswith("'") and len(v) >= 2:
            meta[k] = v[1:-1]
        else:
            meta[k] = v
    flush()
    return meta


def slug_source(path: Path) -> str:
    p = str(path).replace("\\", "/").rstrip("/")
    if "/.agents/" in p:
        return "agents"
    if "/.pi/" in p:
        return "pi"
    return re.sub(r"[^A-Za-z0-9]+", "-", path.parent.name or "src").strip("-").lower() or "src"


def discover_skills(sources: list[str]) -> tuple[dict, list[str]]:
    """返回 ({dest_name: {"src":Path,"meta":dict,"source":str}}, warnings)"""
    found: dict[str, dict] = {}
    warnings: list[str] = []

    for raw in sources:
        src = Path(os.path.expanduser(str(raw)))
        if not src.exists():
            warnings.append(f"源目录不存在，已跳过: {src}")
            continue

        candidates: list[Path] = []
        if (src / "SKILL.md").is_file():          # 源本身就是单个 skill
            candidates.append(src)
        else:                                      # 源下面一层就是各 skill
            for child in sorted(src.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    if (child / "SKILL.md").is_file():
                        candidates.append(child)

        tag = slug_source(src)
        for skill in candidates:
            if (skill / ".nosync").exists():
                warnings.append(f"按 .nosync 跳过: {skill}")
                log(f"  跳过（.nosync）: {skill.name}")
                continue
            meta = read_frontmatter(skill / "SKILL.md")
            name = (meta.get("name") or skill.name).strip()
            dest = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or skill.name
            if dest in found and Path(found[dest]["src"]) != skill:
                dest = f"{dest}-{tag}"          # 跨源重名加后缀
            n = 2
            while dest in found and Path(found[dest]["src"]) != skill:
                dest = f"{dest}-{n}"
                n += 1
            found[dest] = {
                "src": skill,
                "meta": meta,
                "source": str(src).replace("\\", "/"),
                "tag": tag,
            }

    return found, warnings


def sha_of_tree(root: Path) -> str:
    """对目录内容做指纹（用于快速判断是否需要提交）。"""
    h = hashlib.sha1()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORE_DIRS)
        for fn in sorted(filenames):
            if fn.endswith(IGNORE_FILE_SUFFIXES):
                continue
            fp = Path(dirpath) / fn
            rel = fp.relative_to(root).as_posix()
            h.update(rel.encode("utf-8", "replace"))
            try:
                h.update(fp.read_bytes())
            except OSError:
                h.update(b"<unreadable>")
    return h.hexdigest()


# ----------------------------------------------------------------------------- 镜像

def ignore_for_copy(dirpath, names):
    ignored = set()
    for n in names:
        if n in IGNORE_DIRS:
            ignored.add(n)
        elif n.endswith(IGNORE_FILE_SUFFIXES):
            ignored.add(n)
    return ignored


def mirror_skills(repo_dir: Path, skills: dict, dry_run: bool = False) -> tuple[list[str], list[str], list[str]]:
    """把 skills 镜像到 repo_dir/skills/。返回 (added, changed, removed)。"""
    dest_root = repo_dir / "skills"
    added, changed, removed = [], [], []

    if not dry_run:
        dest_root.mkdir(parents=True, exist_ok=True)

    # 1) 删除仓库中已经不存在于源里的 skill 目录（git 历史仍保留）
    if dest_root.exists():
        for child in sorted(dest_root.iterdir()):
            if child.is_dir() and child.name not in skills:
                log(f"  - 移除已删除的 skill: {child.name}")
                removed.append(child.name)
                if not dry_run:
                    shutil.rmtree(child, ignore_errors=True)

    # 2) 逐个拷贝
    for dest_name, info in sorted(skills.items()):
        src: Path = info["src"]
        dst = dest_root / dest_name
        is_new = not dst.exists()
        old_sha = "" if is_new else sha_of_tree(dst)
        if not dry_run:
            if dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst, ignore=ignore_for_copy,
                            symlinks=True, ignore_dangling_symlinks=True)
        new_sha = sha_of_tree(src)
        if is_new:
            added.append(dest_name)
            log(f"  + {dest_name}")
        elif old_sha != new_sha:
            changed.append(dest_name)
            log(f"  ~ {dest_name}")
    return added, changed, removed


def write_readme(repo_dir: Path, skills: dict, warnings: list[str]) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# Pi Skills",
        "",
        f"本仓库由 [`skills-github-sync`](skills/skills-github-sync/) 自动从本机 Pi 镜像同步。",
        f"最后同步：**{now}**",
        "",
        f"共 **{len(skills)}** 个 skill。",
        "",
        "## 安装",
        "",
        "```bash",
        "# 全部 skills 复制到本机 Pi",
        "git clone <repo-url> /tmp/pi-skills",
        "cp -r /tmp/pi-skills/skills/* ~/.pi/agent/skills/",
        "```",
        "",
        "## 清单",
        "",
        "| Skill | 说明 | 源 |",
        "|---|---|---|",
    ]
    for dest, info in sorted(skills.items()):
        desc = (info["meta"].get("description") or "").replace("|", "\\|").replace("\n", " ").strip()
        if len(desc) > 160:
            desc = desc[:157] + "..."
        lines.append(f"| [`{dest}`](skills/{dest}/) | {desc} | {info['tag']} |")
    lines.append("")

    if warnings:
        lines += ["## 警告", ""]
        lines += [f"- {w}" for w in warnings]
        lines.append("")

    (repo_dir / README_NAME).write_text("\n".join(lines), encoding="utf-8")

    index = {
        "generatedAt": now,
        "count": len(skills),
        "skills": [
            {
                "name": dest,
                "description": info["meta"].get("description", ""),
                "source": info["source"],
            }
            for dest, info in sorted(skills.items())
        ],
    }
    (repo_dir / INDEX_NAME).write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def write_repo_support_files(repo_dir: Path) -> None:
    gi = repo_dir / ".gitignore"
    if not gi.exists():
        gi.write_text("# 同步工具产生的临时文件\n*.log\n*.tmp\n.DS_Store\nThumbs.db\n", encoding="utf-8")
    ga = repo_dir / ".gitattributes"
    if not ga.exists():
        # -text：完全不做换行转换，保证镜像字节一致、不产生假 diff
        ga.write_text("* -text\n", encoding="utf-8")
    # 让 clone 出来的人不会因为 CRLF 看到全量 diff
    _, _, _ = git(["config", "core.autocrlf", "false"], cwd=repo_dir, check=False)
    _, _, _ = git(["config", "core.safecrlf", "false"], cwd=repo_dir, check=False)


# ----------------------------------------------------------------------------- git 仓库

def remote_slug(remote: str) -> str:
    m = re.search(r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?/?$", remote)
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


def current_branch(repo_dir: Path, fallback: str) -> str:
    code, out, _ = git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir, check=False)
    if code == 0 and out.strip() and out.strip() != "HEAD":
        return out.strip()
    return fallback


def has_remote(repo_dir: Path) -> bool:
    code, out, _ = git(["remote"], cwd=repo_dir, check=False)
    return code == 0 and bool(out.strip())


def align_with_remote(repo_dir: Path, branch: str, token: str | None = None) -> bool:
    """本地还没有任何提交，而远端已经有历史时，把本地对齐到远端，
    避免第一次推送被 non-fast-forward 拒掉。"""
    code, _, _ = git(["rev-parse", "--verify", "HEAD"], cwd=repo_dir, check=False)
    if code == 0:
        return False  # 本地已有历史，交给 commit_and_push 里的 pull --rebase 处理
    code, out, err = git(["fetch", "origin", branch], cwd=repo_dir, check=False, token=token)
    if code != 0:
        log(f"拉取远端失败（可能是空仓库或网络问题，继续尝试）: {err or out}")
        return False
    code, _, _ = git(["rev-parse", "--verify", f"origin/{branch}"], cwd=repo_dir, check=False)
    if code != 0:
        return False  # 远端是空仓库
    git(["reset", "--mixed", f"origin/{branch}"], cwd=repo_dir)
    log(f"远端已有历史，本地已对齐到 origin/{branch}")
    return True


def commit_and_push(repo_dir: Path, cfg: dict, token: str, added: list[str],
                    changed: list[str], removed: list[str], branch: str, no_push: bool) -> str:
    """返回 'no-change' | 'committed' | 'pushed' | 'failed'。"""
    code, out, _ = git(["status", "--porcelain"], cwd=repo_dir, check=False)
    if not out.strip():
        log("没有变化，跳过提交。")
        return "no-change"

    git(["add", "-A"], cwd=repo_dir)
    code, staged, _ = git(["diff", "--cached", "--name-only"], cwd=repo_dir, check=False)
    if not staged.strip():
        log("暂存区为空，跳过提交。")
        return "no-change"

    prefix = cfg.get("commitPrefix") or "skills"
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
    body = f"Auto-synced by skills-github-sync at {stamp}\n\n" + "\n".join(
        f"- {f}" for f in staged.splitlines()[:60]
    )

    git(["commit", "-m", subject, "-m", body], cwd=repo_dir)
    log(f"已提交: {subject}")

    if no_push:
        log("--no-push 已指定，跳过推送。")
        return "committed"

    if not has_remote(repo_dir):
        log("没有配置 remote，跳过推送。")
        return "committed"

    push = ["push", "-u", "origin", f"HEAD:{branch}"]
    code, out, err = git(push, cwd=repo_dir, check=False, token=token or None, timeout=600)
    if code != 0:
        log(f"推送失败，尝试 pull --rebase 后重试: {err or out}")
        git(["pull", "--rebase", "--autostash", "origin", branch],
            cwd=repo_dir, check=False, token=token or None, timeout=600)
        code, out, err = git(push, cwd=repo_dir, check=False, token=token or None, timeout=600)
        if code != 0:
            log(f"ERROR: 推送最终失败: {err or out}", console=True)
            return "failed"

    log("推送成功。")
    return "pushed"


# ----------------------------------------------------------------------------- 远端创建

def github_api(path: str, token: str, payload: dict | None, proxy: str = ""):
    url = f"https://api.github.com{path}"
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=data, method="POST" if payload else "GET")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "pi-skills-sync")
    if data:
        req.add_header("Content-Type", "application/json")
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})
    )
    try:
        with opener.open(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(body or "{}")
        except json.JSONDecodeError:
            return exc.code, {"message": body}
    except Exception as exc:  # noqa: BLE001
        return 0, {"message": str(exc)}


def create_remote_repo(slug: str, token: str, proxy: str = "", private: bool = False) -> bool:
    if not slug:
        return False
    status, body = github_api("/user/repos", token, {
        "name": slug.split("/", 1)[1],
        "description": "My Pi agent skills (auto-synced)",
        "private": private,
        "auto_init": False,
    }, proxy=proxy)
    if status == 201:
        log(f"已在 GitHub 创建仓库: {slug}")
        return True
    if status == 422:
        log(f"远端仓库已存在，直接使用: {slug}")
        return True
    if status == 404:
        msg = body.get("message", "")
        log(f"创建仓库失败(404)：{msg}。若要把仓库建在组织下或想改用户名，"
            f"请手动在 GitHub 建好空仓库后重试。")
        return False
    log(f"创建仓库失败({status}): {body.get('message', body)}")
    return False


# ----------------------------------------------------------------------------- 命令

def cmd_status(cfg: dict, repo_dir: Path) -> int:
    print(f"配置文件 : {DEFAULT_CONFIG_PATH}")
    print(f"仓库目录 : {repo_dir}  {'(已初始化)' if (repo_dir / '.git').is_dir() else '(未初始化)'}")
    print(f"远端     : {cfg.get('remote') or '(未配置)'}")
    print(f"分支     : {cfg.get('branch')}")
    print(f"token    : {'已配置' if resolve_token(cfg) else '未配置'}")
    print("源目录   :")
    for s in cfg.get("sources", []):
        p = Path(os.path.expanduser(str(s)))
        print(f"  - {s}  {'OK' if p.exists() else '不存在'}")
    skills, warnings = discover_skills(cfg.get("sources", []))
    print(f"发现 skill: {len(skills)}")
    for name in sorted(skills):
        print(f"  * {name}")
    for w in warnings:
        print(f"  ! {w}")
    if (repo_dir / ".git").is_dir():
        _, out, _ = git(["status", "--porcelain"], cwd=repo_dir, check=False)
        print(f"仓库未提交变更: {len(out.splitlines())} 个文件")
    return 0


def cmd_sync(cfg: dict, repo_dir: Path, args) -> int:
    sources = cfg.get("sources", [])
    token = resolve_token(cfg)
    branch = cfg.get("branch") or "main"
    remote = cfg.get("remote") or ""
    if not remote or "<你的用户名>" in str(remote):
        log("还没配置远端仓库地址。请运行: "
            "python sync.py --init --repo <用户名>/<仓库名> --token <PAT>"
            f"（配置文件: {DEFAULT_CONFIG_PATH}）", console=True)
        emit_result("unconfigured")
        return 2 if not args.dry_run else 0

    skills, warnings = discover_skills(sources)
    for w in warnings:
        log(f"  ! {w}")
    if not skills:
        log("没有发现任何 skill，结束。", console=True)
        emit_result("no-skills")
        return 0
    log(f"发现 {len(skills)} 个 skill，来源 {len(sources)} 个目录")

    if args.dry_run:
        log("--dry-run：只展示，不写文件/不改 git", console=True)
        for name in sorted(skills):
            print(f"  * {name}  <-  {skills[name]['src']}")
        for w in warnings:
            print(f"  ! {w}")
        emit_result("dry-run")
        return 0

    ensure_repo(repo_dir, remote, branch)
    write_repo_support_files(repo_dir)

    added, changed, removed = mirror_skills(repo_dir, skills, dry_run=False)

    # 内容没变就不重写 README/索引（否则每次都会因为时间戳而产生空提交）
    content_changed = bool(added or changed or removed)
    if content_changed or not (repo_dir / README_NAME).exists():
        write_readme(repo_dir, skills, warnings)
    else:
        log("skills 内容无变化，跳过 README/索引重写。")

    ok = commit_and_push(repo_dir, cfg, token, added, changed, removed, branch, args.no_push)
    emit_result(ok)
    return 0 if ok != "failed" else 1


def cmd_init(cfg: dict, repo_dir: Path, args, cfg_path: Path) -> int:
    token = resolve_token(cfg)
    branch = cfg.get("branch") or "main"
    remote = args.remote or cfg.get("remote") or ""

    repo_arg = args.repo or ""
    if repo_arg:
        slug = repo_arg.replace("https://github.com/", "").replace("http://github.com/", "")
        slug = re.sub(r"\.git$", "", slug).strip("/")
        remote = args.remote or f"https://github.com/{slug}.git"
        cfg["remote"] = remote

    if not remote or "<你的用户名>" in str(remote):
        die("请提供仓库地址：python sync.py --init --repo <用户名>/<仓库名> [--token <PAT>]")

    if not token and args.repo:
        log("提示：没有 token，无法自动创建远端仓库。将直接尝试推送（本地已有凭据时可行）。")

    if token and args.repo and cfg.get("autoCreateRemote", True):
        create_remote_repo(remote_slug(remote), token, cfg.get("proxy", ""))

    save_config(cfg, cfg_path)
    log(f"已写入配置: {cfg_path}")

    ensure_repo(repo_dir, remote, branch)
    write_repo_support_files(repo_dir)
    align_with_remote(repo_dir, branch, token or None)

    skills, warnings = discover_skills(cfg.get("sources", []))
    for w in warnings:
        log(f"  ! {w}")
    log(f"发现 {len(skills)} 个 skill")
    added, changed, removed = mirror_skills(repo_dir, skills)
    if added or changed or removed or not (repo_dir / README_NAME).exists():
        write_readme(repo_dir, skills, warnings)

    # 统一走 commit+push（无变化时会自己跳过）
    state = commit_and_push(repo_dir, cfg, token, added, changed, removed, branch, args.no_push)
    if state == "failed":
        emit_result("failed")
        return 1
    log(f"初始化完成: {remote}")
    emit_result(state)
    return 0


# ----------------------------------------------------------------------------- main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="把本机 Pi skills 镜像同步到 GitHub")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    ap.add_argument("--repo", default="", help="GitHub 仓库，如 kungful/pi-skills（仅 --init）")
    ap.add_argument("--remote", default="", help="完整远端地址（覆盖配置）")
    ap.add_argument("--token", default="", help="GitHub PAT（仅本次使用，不写入配置）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--init", action="store_true")
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

    # 同一时刻只允许一个同步进程
    with SyncLock(LOCK_PATH) as lock:
        if not lock.acquired and lock.enabled and LOCK_PATH.exists():
            log("已有同步在进行中，本次跳过。", console=True)
            emit_result("busy")
            return 0
        if args.init:
            return cmd_init(cfg, repo_dir, args, cfg_path)
        return cmd_sync(cfg, repo_dir, args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001
        log(f"未处理异常: {exc}")
        sys.exit(1)
