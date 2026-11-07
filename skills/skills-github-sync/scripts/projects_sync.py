# -*- coding: utf-8 -*-
"""projects_sync.py —— 把本机开发项目（源码 + 文档 + 小数据）镜像到仓库的 projects/。

和 skills-github-sync / apk-github-sync 是同一套设计：
    镜像 · 幂等 · 无空提交 · 共用一把锁 · 共用同一个仓库

为什么不用 skills 那条链路：skills 只收 `skills/<名字>/`，而项目要完整源码树、
且必须排除几百 MB 的图片/PPT/交付物。这里用「白名单式排除」：默认只挡掉
二进制大资产，代码和文档全部保留 —— 目标是换台电脑 clone 下来就能继续干。

用法：
    python projects_sync.py                # 镜像 + 提交 + 推送（最常用）
    python projects_sync.py --status       # 看配置、会同步哪些项目、将跳过什么
    python projects_sync.py --dry-run      # 只算不写
    python projects_sync.py --no-push      # 只提交到本地仓库
    python projects_sync.py --only <slug>  # 只同步一个项目
    python projects_sync.py --quiet        # stdout 只留一行 RESULT

配置：~/.pi/agent/projects-sync.json
    远端/分支/仓库目录留空时，自动继承 skills-sync.json（两套共用一个仓库）。
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = Path.home()
AGENT = HOME / ".pi" / "agent"
CFG_PATH = AGENT / "projects-sync.json"
SKILLS_CFG = AGENT / "skills-sync.json"
LOCK = AGENT / "skills-sync.lock"          # ★ 与 skills 同步共用，避免并发 git
LOG = AGENT / "projects-sync.log"
LOCK_STALE = 15 * 60

# 默认跳过：这些是构建/运行产物，进仓库没意义还撑体积
EXCLUDE_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "node_modules", ".idea", ".vscode",
    "logs", "log", "dist", "build", "target", "选题", ".pick_profile",
    ".pytest_cache", ".mypy_cache", ".gradle", "out", "img", "img_sell",
}
EXCLUDE_EXT = {
    ".pyc", ".pyo", ".log", ".tmp", ".swp", ".swo", ".bak",
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".ico", ".svgz",
    ".mp4", ".mov", ".avi", ".mkv", ".mp3", ".wav",
    ".zip", ".7z", ".rar", ".tar", ".gz",
    ".pptx", ".ppt", ".pdf", ".docx", ".xlsx",
    ".psd", ".ai", ".sketch", ".fig",
    ".apk", ".aab", ".bin", ".img", ".iso",
    ".so", ".dll", ".dylib", ".exe",
}
MAX_FILE_MB = 8


# ------------------------------------------------------------------ 基础设施
def log(msg: str, quiet: bool = False):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    if not quiet:
        print(line, flush=True)


def emit(state: str):
    print("[projects-sync] RESULT %s" % state, flush=True)


def _hidden():
    """所有子进程不弹控制台窗口（Windows 下 python 无控制台时 git 会自己开一个）。"""
    if os.name != "nt":
        return {}
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0), "startupinfo": si}


def run(cmd, cwd=None, timeout=600):
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=timeout, **_hidden())
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def git(args, cwd, check=True, timeout=600):
    cmd = ["git", "-c", "credential.interactive=false"] + list(args)
    code, out, err = run(cmd, cwd, timeout)
    if check and code != 0:
        raise RuntimeError("git %s 失败: %s" % (" ".join(args), err or out))
    return code, out, err


class Lock:
    def __init__(self, path: Path):
        self.path = path
        self.ok = False

    def __enter__(self):
        if self.path.exists():
            try:
                age = time.time() - self.path.stat().st_mtime
            except OSError:
                age = 0
            if age <= LOCK_STALE:
                return self              # 别的同步正在跑，静默让路
            try:
                self.path.unlink()
            except OSError:
                pass
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(str(os.getpid()), encoding="utf-8")
            self.ok = True
        except OSError:
            pass
        return self

    def __exit__(self, *exc):
        if self.ok:
            try:
                self.path.unlink()
            except OSError:
                pass
        return False


# ------------------------------------------------------------------ 配置
def load_cfg() -> dict:
    if not CFG_PATH.exists():
        sys.exit("没有配置：%s" % CFG_PATH)
    cfg = json.loads(CFG_PATH.read_text(encoding="utf-8"))
    # 远端/仓库缺省时继承 skills 同步的配置（同一个仓库）
    if SKILLS_CFG.exists():
        base = json.loads(SKILLS_CFG.read_text(encoding="utf-8"))
        for k in ("remote", "branch", "repoDir"):
            if not cfg.get(k):
                cfg[k] = base.get(k)
    cfg.setdefault("branch", "main")
    cfg.setdefault("commitPrefix", "projects")
    cfg.setdefault("projects", [])
    if not cfg.get("repoDir"):
        cfg["repoDir"] = str(HOME / ".pi" / "skills-repo")
    return cfg


# ------------------------------------------------------------------ 扫描
def scan_project(proj: dict):
    """返回 (files{rel: abs}, skipped{reason: [rel]}, total_bytes)"""
    src = Path(proj["source"])
    if not src.is_dir():
        raise RuntimeError("源目录不存在：%s" % src)

    extra_dirs = set(proj.get("excludeDirs") or [])
    globs = list(proj.get("excludeGlobs") or [])
    max_mb = float(proj.get("maxFileMB") or MAX_FILE_MB)
    max_bytes = max_mb * 1024 * 1024

    files, skipped = {}, {"byExt": [], "bySize": [], "byName": []}
    for root, dirs, names in os.walk(src):
        rel_root = os.path.relpath(root, src).replace("\\", "/")
        rel_root = "" if rel_root == "." else rel_root

        keep = []
        for d in sorted(dirs):
            rel = (rel_root + "/" + d).lstrip("/")
            if d in EXCLUDE_DIRS or rel in extra_dirs:
                continue
            if any(fnmatch.fnmatch(rel, g) for g in globs):
                continue
            keep.append(d)
        dirs[:] = keep

        for n in sorted(names):
            rel = (rel_root + "/" + n).lstrip("/")
            if n.endswith((".pyc", ".pyo")) or n == ".DS_Store":
                skipped["byName"].append(rel)
                continue
            if any(fnmatch.fnmatch(rel, g) for g in globs):
                skipped["byName"].append(rel)
                continue
            if Path(n).suffix.lower() in EXCLUDE_EXT:
                skipped["byExt"].append(rel)
                continue
            ap = os.path.join(root, n)
            try:
                size = os.path.getsize(ap)
            except OSError:
                continue
            if size > max_bytes:
                skipped["bySize"].append("%s (%.1fMB)" % (rel, size / 1048576))
                continue
            files[rel] = ap
    total = sum(os.path.getsize(p) for p in files.values())
    return files, skipped, total


def mirror(src: Path, dst: Path, files: dict, dry: bool) -> tuple[list, list]:
    """把 files 镜像进 dst：多退少补，未变化的文件不重写（保证幂等）。"""
    added, removed = [], []
    wanted = set(files)

    if dst.exists():
        for root, dirs, names in os.walk(dst):
            for n in names:
                ap = os.path.join(root, n)
                rel = os.path.relpath(ap, dst).replace("\\", "/")
                if rel not in wanted and rel != "_mirror.json":
                    removed.append(rel)
                    if not dry:
                        os.remove(ap)
        if not dry:
            for root, dirs, names in os.walk(dst, topdown=False):
                if root != str(dst) and not os.listdir(root):
                    os.rmdir(root)

    for rel, ap in files.items():
        dp = dst / rel
        if dp.exists():
            try:
                a, b = os.stat(ap), os.stat(dp)
                if a.st_size == b.st_size and int(a.st_mtime) == int(b.st_mtime):
                    continue
            except OSError:
                pass
        added.append(rel)
        if not dry:
            dp.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ap, dp)
    return added, removed


# ------------------------------------------------------------------ 主流程
def sync_one(cfg: dict, proj: dict, repo: Path, args) -> dict:
    slug = proj["slug"]
    src = Path(proj["source"])
    dst = repo / "projects" / slug
    print("") if not args.quiet else None
    log("→ %s  %s" % (slug, src), args.quiet)

    files, skipped, total = scan_project(proj)
    log("   %d 个文件 / %.1f MB  跳过：扩展名 %d、超限 %d、规则 %d"
        % (len(files), total / 1048576, len(skipped["byExt"]),
           len(skipped["bySize"]), len(skipped["byName"])), args.quiet)

    added, removed = mirror(src, dst, files, args.dry_run)
    if args.dry_run:
        for r in added[:40]:
            log("   + %s" % r, args.quiet)
        for r in removed[:20]:
            log("   - %s" % r, args.quiet)
    else:
        meta_path = dst / "_mirror.json"
        # ★ 只在真有变化时重写 _mirror.json。否则每次都会因 synced_at 变而
        #    产生一个只有时间戳的空提交（实际踩到）。
        if added or removed or not meta_path.exists():
            meta = {
                "slug": slug,
                "title": proj.get("title") or slug,
                "source": str(src),
                "synced_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "files": len(files),
                "bytes": total,
                "skipped": {k: len(v) for k, v in skipped.items()},
                "skippedDetail": {k: v[:50] for k, v in skipped.items() if v},
            }
            dst.mkdir(parents=True, exist_ok=True)
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    log("   变更：+%d / -%d" % (len(added), len(removed)), args.quiet)
    return {"slug": slug, "added": len(added), "removed": len(removed),
            "files": len(files), "bytes": total}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args(argv)

    cfg = load_cfg()
    repo = Path(cfg["repoDir"])

    projs = [p for p in cfg["projects"] if not a.only or p["slug"] == a.only]
    if not projs:
        log("没有匹配的项目", a.quiet)
        emit("no-projects")
        return 0

    if a.status:
        log("仓库 %s  (%s)" % (repo, cfg.get("remote") or "无远端"), a.quiet)
        for p in cfg["projects"]:
            src = Path(p["source"])
            n = sum(len(f) for _, _, f in os.walk(src)) if src.is_dir() else 0
            log("  %-22s %s  %s" % (p["slug"], "✓" if src.is_dir() else "✗ 缺源", src), a.quiet)
        return 0

    if not repo.is_dir() or not (repo / ".git").exists():
        log("本地仓库不存在：%s（先用 skills-github-sync 的 sync.py --init）" % repo, a.quiet)
        emit("unconfigured")
        return 2

    with Lock(LOCK) as lk:
        if not lk.ok and LOCK.exists():
            log("已有同步在跑，本次跳过", a.quiet)
            emit("busy")
            return 0

        stats = [sync_one(cfg, p, repo, a) for p in projs]

        if a.dry_run:
            emit("dry-run")
            return 0

        git(["add", "-A", "projects"], repo)
        code, out, _ = git(["diff", "--cached", "--quiet"], repo, check=False)
        if code == 0:
            log("无变化，不产生空提交", a.quiet)
            emit("no-change")
            return 0

        msg = "%s: 更新 %s\n\nAuto-synced by projects-github-sync at %s" % (
            cfg["commitPrefix"], ", ".join(s["slug"] for s in stats),
            time.strftime("%Y-%m-%d %H:%M:%S"))
        git(["commit", "-m", msg], repo)
        log("已提交：%s" % msg.splitlines()[0], a.quiet)

        if a.no_push:
            emit("committed")
            return 0

        code, out, err = git(["push", "origin", cfg["branch"]], repo, check=False)
        if code != 0:
            log("推送失败，尝试 rebase 重试：%s" % (err or out), a.quiet)
            git(["pull", "--rebase", "--autostash", "origin", cfg["branch"]], repo, check=False)
            code, out, err = git(["push", "origin", cfg["branch"]], repo, check=False)
            if code != 0:
                log("推送仍然失败：%s" % (err or out), a.quiet)
                emit("failed")
                return 1
        log("已推送 → %s (%s)" % (cfg.get("remote") or "origin", cfg["branch"]), a.quiet)
        emit("pushed")
        return 0


if __name__ == "__main__":
    sys.exit(main())
