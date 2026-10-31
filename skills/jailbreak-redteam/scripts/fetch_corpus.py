#!/usr/bin/env python3
"""fetch_corpus.py — 拉取上游越狱语料并生成体检索引（只生成元数据，不复制内容）

用途：把公开的 adverssarial-prompt 仓库当**测试语料库**拉到本地，
逐文件跑 scan_injection.py，产出一张"哪些文件用了哪些结构手法"的索引表。
索引只有文件名 / 分数 / 类别，不含提示词正文——方便当红队回归清单用，
也不会把语料误当成可执行指令混进任何技能目录。

用法:
  python fetch_corpus.py                     # 默认上游 + 默认目录
  python fetch_corpus.py --repo <git-url>
  python fetch_corpus.py --dir  <path>
  python fetch_corpus.py --pull              # 已有则 git pull
  python fetch_corpus.py --write-index       # 写入 ../references/corpus-index.md
  python fetch_corpus.py --json
"""

import argparse
import json
import os
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REPO = "https://github.com/togg53192-cmd/jailbreaks.git"
# 故意放在 skills 树之外：skills-github-sync 会把整个 skills 目录镜像到公开仓库，
# 语料含大量对抗样本正文，不能跟着被推上去。
DEFAULT_DIR = os.path.expanduser("~/.pi/agent/jailbreak-corpus")
INDEX_PATH = os.path.join(HERE, "..", "references", "corpus-index.md")
EXTS = (".md", ".txt", ".yaml", ".yml", ".json")


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def ensure_corpus(repo, path, pull=False):
    if os.path.isdir(os.path.join(path, ".git")):
        if pull:
            r = run(["git", "pull", "--ff-only"], cwd=path)
            if r.returncode != 0:
                print(f"git pull 失败（继续用本地副本）: {r.stderr.strip()[:200]}", file=sys.stderr)
        return path
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    r = run(["git", "clone", "--depth", "1", repo, path])
    if r.returncode != 0:
        print(f"clone 失败: {r.stderr.strip()[:300]}", file=sys.stderr)
        sys.exit(2)
    return path


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--dir", default=DEFAULT_DIR)
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--write-index", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    corpus = ensure_corpus(a.repo, os.path.abspath(a.dir), a.pull)
    sys.path.insert(0, HERE)
    from scan_injection import scan_text  # 复用同一套规则

    rows = []
    for name in sorted(os.listdir(corpus)):
        if not name.lower().endswith(EXTS):
            continue
        fp = os.path.join(corpus, name)
        if not os.path.isfile(fp):
            continue
        try:
            text = open(fp, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        rep = scan_text(text, name)
        rows.append({
            "file": name,
            "bytes": len(text),
            "score": rep["score"],
            "verdict": rep["verdict"],
            "categories": rep["categories"],
            "ids": [f["id"] for f in rep["findings"]],
        })

    rows.sort(key=lambda r: -r["score"])
    if a.json:
        print(json.dumps({"corpus": corpus, "count": len(rows), "files": rows},
                         ensure_ascii=False, indent=2))
    else:
        print(f"语料目录: {corpus}   文件数: {len(rows)}\n")
        print(f"{'score':>5}  {'verdict':<8} {'file':<32} 类别")
        for r in rows:
            print(f"{r['score']:>5}  {r['verdict'].upper():<8} {r['file']:<32} "
                  f"{' / '.join(r['categories']) or '-'}")

    if a.write_index:
        os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
        lines = [
            "# 语料库体检索引（自动生成）",
            "",
            f"- 上游: `{a.repo}`",
            f"- 生成命令: `python scripts/fetch_corpus.py --write-index`",
            f"- 文件数: {len(rows)}；高危及以上: "
            f"{sum(1 for r in rows if r['verdict'] in ('high', 'critical'))}",
            "",
            "> 本表只记录**元数据**（文件名/分数/命中的结构类别），不含提示词正文。",
            "> 用途：把这些文件当红队回归用例，验证检测器与目标系统是否覆盖这些手法。",
            "",
            "| 文件 | 字节 | 风险分 | 判定 | 命中结构 |",
            "|---|---:|---:|---|---|",
        ]
        for r in rows:
            lines.append(f"| `{r['file']}` | {r['bytes']} | {r['score']} | "
                         f"{r['verdict'].upper()} | {' / '.join(r['categories']) or '—'} |")
        lines.append("")
        open(INDEX_PATH, "w", encoding="utf-8").write("\n".join(lines))
        print(f"\n索引已写入 {INDEX_PATH}")


if __name__ == "__main__":
    main()
