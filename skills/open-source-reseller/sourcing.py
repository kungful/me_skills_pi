#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sourcing.py —— 开源项目选品 / License 审计 / 封装骨架 / 多平台分发素材

只做四件事，全都是纯本地 + GitHub 公开 API，不登录任何卖货平台、不碰任何反检测：
  search  找候选开源项目并打分（需求度 / 活跃度 / License 能否变现 / 成品化难度）
  audit   单个项目深度审计：License 能不能卖、能怎么卖、坑在哪
  pack    生成商品骨架（部署脚本 + 中文文档 + 定价 + 售后模板）
  kit     生成各渠道文案素材包（小红书/抖音/B站/闲鱼/QQ群/X），每个渠道版本不同

⚠ License 判定是「能不能拿去卖」的生死线。本脚本给结论，最终责任在你：
   - 没 LICENSE 的仓库 = 保留所有权利 = 不能卖
   - GPL：分发要开源你的改动；AGPL/SSPL/BUSL：连托管服务都受限
   - 一律不能用原项目名/商标作为你的商品名

用法见 SKILL.md。可选环境变量 GITHUB_TOKEN 提高 API 配额（60/h → 5000/h）。
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache")
LISTINGS = os.path.join(HERE, "listings")
CHANNELS = json.load(open(os.path.join(HERE, "channels.json"), encoding="utf-8"))
API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

PERMISSIVE = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC",
              "Unlicense", "0BSD", "Zlib", "WTFPL", "CC0-1.0", "PostgreSQL"}
WEAK = {"MPL-2.0", "LGPL-2.1", "LGPL-3.0", "EPL-2.0", "CDDL-1.0"}
STRONG = {"GPL-2.0", "GPL-3.0", "GPL-2.0-only", "GPL-3.0-only", "OFL-1.1"}
NETWORK = {"AGPL-3.0", "AGPL-3.0-only", "SSPL-1.0", "Elastic-2.0", "BUSL-1.1", "Commons-Clause"}

STACK_MARK = {
    "docker-compose.yml": "compose", "docker-compose.yaml": "compose",
    "docker-compose.yml.example": "compose", "Dockerfile": "dockerfile",
    "package.json": "node", "requirements.txt": "python", "pyproject.toml": "python",
    "go.mod": "go", "Cargo.toml": "rust", "pom.xml": "java", "composer.json": "php",
    "Gemfile": "ruby", "app.py": "python", "manage.py": "django",
}
UI_MARK = ["web", "frontend", "ui", "admin", "dashboard", "static", "public", "templates", "app"]


# ---------------------------------------------------------------- 基础
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def cache_path(key):
    os.makedirs(CACHE, exist_ok=True)
    return os.path.join(CACHE, hashlib.sha1(key.encode()).hexdigest() + ".json")


def gh(path, params=None, ttl=21600, raw=False):
    """GET GitHub API，带磁盘缓存。未登录 60 次/小时，够跑一轮选品。"""
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    cp = cache_path(url)
    if os.path.exists(cp) and time.time() - os.path.getmtime(cp) < ttl:
        with open(cp, "r", encoding="utf-8") as f:
            return json.load(f)
    req = urllib.request.Request(url, headers={
        "User-Agent": "pi-open-source-reseller",
        "Accept": "application/vnd.github+json",
    })
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r) if not raw else {"_text": r.read().decode("utf-8", "replace")}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        if e.code == 403 and "rate limit" in body.lower():
            raise SystemExit("GitHub API 限流。设 GITHUB_TOKEN 环境变量（60/h → 5000/h）后重试。")
        if e.code == 404:
            return {"_404": True}
        raise SystemExit("GitHub API %s: %s" % (e.code, body))
    with open(cp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return data


def days_since(iso):
    if not iso:
        return 9999
    t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - t).days


def fmt_stars(n):
    return "%.1fk" % (n / 1000.0) if n >= 1000 else str(n)


# ---------------------------------------------------------------- License 判定

RESTRICT_KW = [
    ("commercial license must be obtained", "需向作者购买商业授权"),
    ("must obtain a commercial license", "需向作者购买商业授权"),
    ("multi-tenant", "多租户 SaaS 受限"),
    ("multi tenant", "多租户 SaaS 受限"),
    ("commons clause", "Commons Clause：禁止销售其功能"),
    ("non-commercial", "禁止商业使用"),
    ("noncommercial", "禁止商业使用"),
    ("may not resell", "禁止转售"),
    ("may not sell", "禁止转售"),
    ("additional condition", "附加限制条款"),
    ("remove or hide", "禁止去除品牌/版权标识"),
    ("logo and copyright", "品牌标识条款"),
    ("field of use", "用途限制"),
    ("business source license", "BUSL：生产用途受限"),
    ("server side public license", "SSPL：托管服务须开源"),
    ("elastic license", "Elastic：禁止托管服务"),
]


def scan_restrictions(text):
    """在许可证原文里找『限制条款』。这才是能不能拿去卖的关键。"""
    if not text:
        return []
    low = text.lower()
    hits = []
    for kw, why in RESTRICT_KW:
        i = low.find(kw)
        if i < 0:
            continue
        seg = re.sub(r"\s+", " ", text[max(0, i - 90):i + 130]).strip()
        hits.append({"kw": kw, "why": why, "quote": seg})
    return hits


def classify_license(spdx, text=""):
    spdx = (spdx or "").strip()
    # 宽松/未识别许可证也要查限制条款：改过的 Apache（如 dify）在 GitHub 上就是 NOASSERTION
    if spdx in ("", "NOASSERTION", "other", "Apache-2.0", "MIT", "BSD-3-Clause"):
        if scan_restrictions(text):
            return "RESTRICTED", "许可证带附加限制条款，默认不能当普通开源项目拿去卖"
    if not spdx:
        return "NONE", "仓库没有 LICENSE 文件 = 默认保留所有权利，不能卖、不能改"
    if spdx in ("NOASSERTION", "other"):
        low = (text or "").lower()
        if "commons clause" in low:
            return "CUSTOM", "Commons Clause：禁止『销售该软件的功能』，不能直接卖成品"
        if "business source license" in low or "bsl" in low[:2000]:
            return "NETWORK", "BUSL：生产用途受限，通常几年后才转开源"
        if "server side public license" in low or "sspl" in low:
            return "NETWORK", "SSPL：提供托管服务必须开源整个栈"
        if "elastic license" in low:
            return "NETWORK", "Elastic License：禁止提供托管服务"
        if "agpl" in low:
            return "NETWORK", "AGPL：网络服务也触发开源义务"
        if "gnu general public license" in low or " gpl" in low:
            return "STRONG", "GPL：分发衍生作品必须开源"
        if "apache" in low:
            return "PERMISSIVE", "Apache 变体（文本里有限制条款，人工再读一遍）"
        return "UNKNOWN", "GitHub 未识别该许可证（很可能是改过的 Apache），必须读原文才能定"
    if spdx in PERMISSIVE:
        return "PERMISSIVE", "%s：可商用、可闭源，保留版权声明与 LICENSE 即可" % spdx
    if spdx in WEAK:
        return "WEAK", "%s：可商用；你改动的那些文件需开源，别把改动藏起来" % spdx
    if spdx in STRONG:
        return "STRONG", "%s：可卖成品，但分发时必须按 GPL 提供源码；卖远程服务通常不触发" % spdx
    if spdx in NETWORK:
        return "NETWORK", "%s：连托管/在线服务都可能触发开源义务，不适合闭源变现" % spdx
    return "CUSTOM", "未归档许可证 %s，人工读原文" % spdx


def monetize_verdict(kind, note):
    """把 License 分类翻译成『这项目能不能卖、能怎么卖』。"""
    table = {
        "PERMISSIVE": ("可以卖成品", "自助包 / 代部署 / 定制封装 / 托管，四条线都能做。附上 LICENSE 与原作者署名。"),
        "WEAK": ("可以卖成品", "改动文件的开源义务要守住；纯部署、纯汉化文案不改源码则无义务。"),
        "STRONG": ("可以卖成品或服务", "分发二进制/源码时须提供对应源码与你自己的改动；只做远程代部署通常不构成分发。"),
        "NETWORK": ("不建议卖成品", "托管服务也触发开源义务。能做的只有：卖部署服务（客户自己持有）、卖教程、卖技术支持。"),
        "NONE": ("不能卖", "没有许可证 = 保留所有权利。想商业化只能：联系作者拿授权，或自己重写实现（不抄代码）。"),
        "RESTRICTED": ("先拿授权", "自用/内部部署一般可以；对外做多租户服务、去掉品牌、转售，通常需要作者商业授权。"),
        "UNKNOWN": ("先审许可证", "GitHub 没识别出来，通常是改过的 Apache/大厂自定义条款。读原文，别当成宽松许可证用。"),
        "CUSTOM": ("先人工审", "许可证文本里有额外限制，读懂再动手；拿不准就问作者，一封邮件比一次纠纷便宜。"),
    }
    label, advice = table[kind]
    return label, advice + "（" + note + "）"


# ---------------------------------------------------------------- 搜索
SELLABLE_HINT = ["平台", "系统", "工具", "助手", "面板", "管理", "分析", "生成", "自动化",
                 "saas", "tool", "platform", "dashboard", "studio", "app", "agent", "bot"]


def repo_score(r):
    """0–100：是不是一个『值得封装去卖』的项目。分数只是排序，最终看 audit。"""
    s, why = 0, []
    stars = r.get("stargazers_count", 0)
    s += min(20, int(math.log10(max(stars, 10)) * 5))
    if stars > 200:
        why.append("star=%s" % fmt_stars(stars))

    d = days_since(r.get("pushed_at"))
    if d <= 30:
        s += 20; why.append("30天内活跃")
    elif d <= 120:
        s += 12; why.append("季度内活跃")
    elif d <= 400:
        s += 4
    if d > 700:
        s -= 15; why.append("两年没动")

    lic = (r.get("license") or {}).get("spdx_id") or ""
    kind, _ = classify_license(lic)
    if kind == "PERMISSIVE":
        s += 25; why.append("License 宽松")
    elif kind == "WEAK":
        s += 15; why.append("弱 copyleft")
    elif kind == "STRONG":
        s += 8; why.append("GPL")
    elif kind == "NETWORK":
        s -= 10; why.append("网络 copyleft")
    elif kind == "UNKNOWN":
        s -= 15; why.append("许可证需人工审")
    else:
        s -= 30; why.append("无/自定义许可证")

    if r.get("archived"):
        s -= 40; why.append("已归档")
    if r.get("language") in ("Python", "TypeScript", "JavaScript", "Go", "Vue", "Svelte"):
        s += 6; why.append("技术栈好封装")
    txt = ((r.get("description") or "") + " " + " ".join(r.get("topics") or [])).lower()
    if any(h in txt for h in SELLABLE_HINT):
        s += 8; why.append("成品形态")
    if (r.get("size") or 0) < 80000:
        s += 4
    if r.get("open_issues_count", 0) > 2000:
        s -= 6; why.append("issue 很多")
    return max(0, min(100, s)), why


def cmd_search(a):
    q = a.q
    if a.min_stars and "stars:" not in q:
        q += " stars:>=%d" % a.min_stars
    if "archived:" not in q:
        q += " archived:false"
    data = gh("/search/repositories", {"q": q, "sort": a.sort,
                                      "order": "desc", "per_page": min(a.limit * 2, 100)},
              ttl=3600)
    items = data.get("items") or []
    rows = []
    for r in items:
        sc, why = repo_score(r)
        rows.append((sc, r, why))
    rows.sort(key=lambda x: x[0], reverse=True)
    rows = rows[:a.limit]

    print("查询: %s   命中 %d，展示前 %d\n" % (q, data.get("total_count", 0), len(rows)))
    print("%3s %-42s %6s %5s %-14s %s" % ("分", "repo", "star", "活跃", "License", "判读"))
    for sc, r, why in rows:
        kind, _ = classify_license((r.get("license") or {}).get("spdx_id"))
        tag = {"PERMISSIVE": "✅可卖", "WEAK": "✅可卖*", "STRONG": "△需开源",
               "NETWORK": "✗托管受限", "NONE": "✗无证", "CUSTOM": "?人工审",
               "RESTRICTED": "⚠需授权", "UNKNOWN": "?需审证"}.get(kind, "?须审")
        print("%3d %-42s %6s %5s %-14s %s"
              % (sc, r["full_name"][:42], fmt_stars(r.get("stargazers_count", 0)),
                 "%dd" % days_since(r.get("pushed_at")),
                 ((r.get("license") or {}).get("spdx_id") or "-")[:14], tag))
        if a.verbose:
            print("     " + (r.get("description") or "")[:110])
            print("     " + " · ".join(why))
    if rows:
        print("\n下一步: python sourcing.py audit %s" % rows[0][1]["full_name"])
    return rows


# ---------------------------------------------------------------- 审计
def repo_files(repo):
    data = gh("/repos/%s/contents/" % repo, ttl=21600)
    if isinstance(data, dict):
        return []
    return [(x["name"], x["type"]) for x in data if isinstance(x, dict)]


def cmd_audit(a):
    repo = a.repo.strip("/")
    r = gh("/repos/" + repo)
    if r.get("_404"):
        raise SystemExit("仓库不存在或拼错了: " + repo)

    lic = gh("/repos/%s/license" % repo, ttl=21600)
    lic_text, lic_path, spdx = "", None, (r.get("license") or {}).get("spdx_id")
    if not lic.get("_404") and lic.get("content"):
        import base64
        lic_path = lic.get("path")
        lic_text = base64.b64decode(lic["content"]).decode("utf-8", "replace")
        spdx = lic.get("license", {}).get("spdx_id") or spdx
    kind, note = classify_license(spdx, lic_text)
    label, advice = monetize_verdict(kind, note)
    restr = scan_restrictions(lic_text)

    files = repo_files(repo)
    names = [n for n, t in files]
    stack = sorted({v for n, v in STACK_MARK.items() if n in names})
    has_ui = any(n.lower() in UI_MARK for n in names) or any(
        n.lower().endswith((".tsx", ".vue", ".svelte")) for n in names)
    has_docs = any(n.lower().startswith(("docs", "readme", "部署", "文档")) for n in names)
    has_i18n = any("i18n" in n.lower() or "locale" in n.lower() for n in names)

    # 近 90 天提交数（翻页太贵，取一页 100 条封顶）
    since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 90 * 86400))
    commits = gh("/repos/%s/commits" % repo, {"since": since, "per_page": 100}, ttl=21600)
    nc = len(commits) if isinstance(commits, list) else 0

    release = gh("/repos/%s/releases/latest" % repo, ttl=21600)
    rel = None if release.get("_404") else release.get("tag_name")

    # 成品化难度
    if "compose" in stack and has_ui:
        difficulty, dnote = "低（半天到 1 天）", "有 compose + 有界面，能直接做成『一键部署包』"
    elif stack:
        difficulty, dnote = "中（1–3 天）", "有容器/包管理痕迹，需要写 compose 与环境文档"
    else:
        difficulty, dnote = "高（3 天+）", "纯库/纯 CLI，只能卖教程、脚本或定制开发"

    print("═" * 70)
    print("%s   %s ★  %s" % (repo, fmt_stars(r.get("stargazers_count", 0)),
                             r.get("language") or "-"))
    print((r.get("description") or "")[:160])
    print("主页: %s   License 文件: %s" % (r.get("html_url"), lic_path or "无"))
    print("最后提交: %s（%d 天前）   仓库体积: %.1f MB   fork: %s"
          % ((r.get("pushed_at") or "")[:10], days_since(r.get("pushed_at")),
             (r.get("size") or 0) / 1024.0, r.get("forks_count")))
    print("近 90 天提交: %d（%s）   issue: %s   最新 release: %s"
          % (nc, "健康" if nc >= 5 else ("偏冷" if nc >= 1 else "停滞"),
             r.get("open_issues_count"), rel or "无"))
    print("技术栈: %s   有界面: %s   有文档: %s   多语言: %s"
          % (", ".join(stack) or "-", "是" if has_ui else "否",
             "是" if has_docs else "否", "是" if has_i18n else "否"))
    print("\n【License 结论】%s" % label)
    print("  %s" % note)
    if restr:
        print("  ⚠ 许可证原文里的限制条款：")
        for h in restr[:5]:
            print("    · %s ← %s" % (h["why"], h["quote"][:110]))
        print("    原文: https://github.com/%s/blob/HEAD/%s" % (repo, lic_path or "LICENSE"))
    print("  → %s" % advice)
    print("\n【成品化难度】%s —— %s" % (difficulty, dnote))
    if has_i18n:
        print("  提示：项目自带 i18n，汉化的边际成本很低，是最容易卖钱的增值项之一。")

    risk = []
    if kind == "RESTRICTED":
        risk.append("有附加限制条款：卖之前确认『你的卖法』在不在限制范围内，拿不准就发邮件问作者")
    if kind in ("NONE", "CUSTOM", "NETWORK"):
        risk.append("License 是这条项目的最大风险，先解决它再谈包装")
    if days_since(r.get("pushed_at")) > 365:
        risk.append("一年没更新：卖出去以后客户遇到新版本问题你得自己扛")
    if r.get("open_issues_count", 0) > 800:
        risk.append("issue 积压严重：说明坑多，售后成本会超预期")
    if not has_docs:
        risk.append("没有文档：你要自己写，这就是你的附加值，也是你的工时")
    risk.append("商标：商品名不能直接用『%s』，要做成『基于 %s 的 XX 部署服务』"
                % (repo.split("/")[-1], repo.split("/")[-1]))
    print("\n【风险】")
    for x in risk:
        print("  · " + x)

    print("\n【能卖什么】")
    for t in CHANNELS["pricing"]["tiers"]:
        print("  · %-8s %s–%s 元  %s（%s）"
              % (t["name"], t["price"][0], t["price"][1], t["含"], t["售后"]))
    if kind == "NETWORK":
        print("  ⚠ 这个 License 只能卖『部署服务/培训』，不要卖镜像或托管。")

    print("\n下一步: python sourcing.py pack %s" % repo)
    return {"repo": repo, "meta": r, "license_kind": kind, "license_note": note,
            "label": label, "advice": advice, "stack": stack, "has_ui": has_ui,
            "has_i18n": has_i18n, "difficulty": difficulty,
            "commits90": nc, "release": rel, "risk": risk, "lic_path": lic_path}


# ---------------------------------------------------------------- 生成骨架
def slugify(repo):
    return re.sub(r"[^a-z0-9]+", "-", repo.lower().replace("/", "-")).strip("-")


def cmd_pack(a):
    info = cmd_audit(argparse.Namespace(repo=a.repo))
    r, meta = info["meta"], info
    if info["license_kind"] == "NONE" and not a.force:
        raise SystemExit("这个仓库没有 LICENSE = 保留所有权利，不能打包去卖。\n"
                         "想商业化只有两条路：找作者要授权，或自己重写实现。"
                         "\n（确实只是自用/学习，加 --force 仍可生成骨架，但不要上架。）")
    if info["license_kind"] in ("RESTRICTED", "NETWORK") and not a.force:
        raise SystemExit("License 是 %s，先确认你的卖法在不在限制范围内（见上面审计）。\n"
                         "确认后加 --force 生成骨架。" % info["label"])
    slug = a.slug or slugify(a.repo)
    out = os.path.join(LISTINGS, slug)
    for sub in ("deploy", "docs", "kit"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)

    name = a.name or (r.get("name") or slug).replace("-", " ").title()
    desc = (r.get("description") or "").strip() or "（项目自述为空，自己去 README 里抠卖点）"
    license_line = ("基于 %s（%s）。本项目版权归原作者所有，本商品为部署/汉化/文档/售后等增值服务。"
                    % (info["repo"], info["lic_path"] or "无 LICENSE"))

    readme = """# {name} · 一键部署与中文使用包

> {license_line}

## 这是什么
{desc}

一句话：**你自己去折腾大概要花 {days} 天，我这里给的是当天就能跑起来的东西。**

## 你会拿到
- `deploy/` 一键部署脚本（Docker 为主，附手动步骤）
- `docs/quickstart.md` 中文说明书（安装 / 首次配置 / 常见报错 / 备份）
- 15 分钟语音或视频讲解（代部署档）
- 1 次免费修改（与原始需求一致的部分）

## 适合谁
- 想用 {name} 但被环境、依赖、英文文档卡住的人
- 需要在自己服务器/内网部署，又不想踩坑的人
- 想二次开发但需要有人先把地基铺好的人

## 环境要求
- 系统：Linux（Ubuntu 22.04 验证）/ Windows + WSL2 / macOS
- Docker 20.10+ 与 docker compose v2（或按 `docs/quickstart.md` 手动装）
- 内存 ≥ 2G，磁盘 ≥ 5G（实际按你的数据量）
- 仅自备服务器：**不含服务器费用、不含第三方 API 费用**

## 价格
| 档位 | 价格 | 内容 |
|---|---|---|
| 自助包 | 待定（建议 29–99） | 部署脚本 + 中文文档 + 安装录屏 |
| 代部署 | 待定（建议 199–599） | 远程装到你机器并跑通 + 15 分钟讲解 + 7 天环境问题免费修 |
| 定制封装 | 待定（建议 599 起） | 改名/改界面/接你的数据/加功能，1 次修改 |

## 常见问题
**Q：这跟我自己去 GitHub 下载有什么区别？**
A：代码是一样的、免费的。你买的是：能跑起来的环境、踩过的坑、中文文档、以及出问题时有人接。
**Q：会开源吗？**
A：上游是 {license_spdx}，按它的许可证执行 —— {license_short}
**Q：能便宜点吗？**
A：价格对应的是工时，不是代码。预算紧可以先买自助包。

## 售后与边界
- 含 1 次修改；超出范围另报价
- 不承诺「永久可用」：上游大版本变更、第三方接口改动不在此列
- 不为违反上游许可证或平台规则的用途提供支持
""".format(name=name, license_line=license_line, desc=desc,
           days={"低（半天到 1 天）": "1–3", "中（1–3 天）": "3–7"}.get(info["difficulty"], "5–15"),
           license_spdx=(r.get("license") or {}).get("spdx_id") or "未声明",
           license_short=info["license_note"])

    compose = """# 由 sourcing.py 生成，务必按项目真实情况改镜像/端口/卷
services:
  app:
    build: .            # 或 image: <上游官方镜像>
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      - TZ=Asia/Shanghai
    env_file:
      - .env
    volumes:
      - ./data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:8080/"]
      interval: 30s
      timeout: 5s
      retries: 3
"""
    install = """#!/usr/bin/env bash
# 一键部署（Ubuntu/Debian 验证）。失败就照 docs/quickstart.md 手动做。
set -euo pipefail
cd "$(dirname "$0")"

command -v docker >/dev/null || { echo "先装 Docker: https://docs.docker.com/engine/install/"; exit 1; }
[ -f .env ] || cp .env.example .env
echo "→ 启动服务…"
docker compose up -d --build
sleep 5
docker compose ps
echo "→ 打开 http://127.0.0.1:8080 自检；日志：docker compose logs -f"
"""
    envx = """# 复制为 .env 后按需修改
TZ=Asia/Shanghai
# 端口
PORT=8080
# 数据目录
DATA_DIR=./data
# 上游项目常用密钥（按 README 填）
# API_KEY=
# ADMIN_PASSWORD=
"""
    quickstart = """# {name} 中文快速上手

## 0. 前置
Docker + docker compose v2。检查：`docker compose version`

## 1. 三步启动
```bash
cd deploy
cp .env.example .env      # 按需改端口/密钥
./install.sh
```

## 2. 验证
浏览器打开 `http://<你的IP>:8080`，能出界面即成功。

## 3. 常见报错
| 现象 | 原因 | 处理 |
|---|---|---|
| 端口被占用 | 8080 被别的服务占了 | 改 `.env` 的 PORT |
| 容器起不来 | 内存不足/架构不匹配 | `docker compose logs` 看第一行错误 |
| 页面 502 | 服务还在初始化 | 等 30–60 秒再看日志 |
| 拉镜像失败 | 网络/代理 | 配镜像加速或手动导入 |

## 4. 备份
`docker compose down` 前把 `data/` 整个目录复制走即可；恢复反过来。

## 5. 升级
```bash
docker compose pull && docker compose up -d
```
升级前先备份；大版本升级看上游 CHANGELOG。
""".format(name=name)

    files = {
        os.path.join(out, "README.md"): readme,
        os.path.join(out, "deploy", "docker-compose.yml"): compose,
        os.path.join(out, "deploy", "install.sh"): install,
        os.path.join(out, "deploy", ".env.example"): envx,
        os.path.join(out, "docs", "quickstart.md"): quickstart,
    }
    for p, c in files.items():
        with open(p, "w", encoding="utf-8") as f:
            f.write(c)
    try:
        os.chmod(os.path.join(out, "deploy", "install.sh"), 0o755)
    except Exception:
        pass

    meta_out = {
        "slug": slug, "repo": info["repo"], "name": name, "created": now(),
        "stars": r.get("stargazers_count"), "license": (r.get("license") or {}).get("spdx_id"),
        "license_kind": info["license_kind"], "monetize": info["label"],
        "license_advice": info["advice"], "difficulty": info["difficulty"],
        "stack": info["stack"], "has_ui": info["has_ui"], "has_i18n": info["has_i18n"],
        "risk": info["risk"], "channels": {}, "status": "draft",
    }
    with open(os.path.join(out, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta_out, f, ensure_ascii=False, indent=2)

    print("\n已生成商品骨架: %s" % out)
    for p in files:
        print("  " + os.path.relpath(p, HERE))
    print("\n注意: docker-compose.yml 和 install.sh 是模板，必须按项目真实情况改到能跑通。")
    print("改完再跑: python sourcing.py kit %s" % slug)
    return slug


# ---------------------------------------------------------------- 多渠道素材
def kit_xhs(m):
    return """# 小红书（1–2 篇/天，同内容别多号发）

## 标题（选一个，≤20 字，别堆关键词）
- 白嫖党别划走：这个开源工具我汉化+一键部署了
- 折腾两天没跑起来？我把它打包成一键部署了
- {name} 中文版，装完就能用（附踩坑记录）

## 正文
最近一直在用 {name}，功能是真的猛，但装起来的坑也是真的多：
依赖冲突、文档全英文、配置项一大串，我前后折腾了两天才跑通。

索性把过程整理成了一套能直接用的东西 👇
① 一键部署脚本（Docker，三条命令）
② 中文说明书：安装 / 首次配置 / 常见报错 / 备份
③ 15 分钟讲解，装完我带你过一遍

它不是「又一个软件」，是省掉你两天的周末。
源码本来就是开源的（{license}），我收的是部署和答疑的工时，这个我写在商品页里，不装原创。

有想在自己服务器上部署的，评论区说一下你的场景（自用/团队/给客户），我看能不能跑得动。

## 标签
#开源 #自部署 #效率工具 #{slug_tag} #程序员日常

## 评论区自己置顶
补充：支持 Ubuntu / WSL2；不含服务器费用；含 1 次免费修改。
""".format(name=m["name"], license=m["license"], slug_tag=m["slug"].replace("-", ""))


def kit_douyin(m):
    return """# 抖音（1–3 条/天，每条都要自己录屏）

## 口播脚本（30 秒，前 3 秒必须出结果）
[0–3s 画面：成品界面在跑]
"这东西开源免费，但 90% 的人装不上。"

[3–12s 画面：终端报错、红字一堆]
"依赖冲突、全英文文档、配置项一大堆，我折腾了两天。"

[12–25s 画面：docker compose up 成功、界面打开]
"现在三条命令：改配置、跑脚本、开浏览器，十分钟跑起来。"

[25–30s 画面：页面 + 引导]
"开源项目我做了中文部署包，需要的话评论区留『部署』，我一条条回。"

## 标题
开源免费，但装不上的那个人可能就是你（{name} 中文部署包）

## 注意
- 不要在口播里念微信/QQ，会限流
- 每个视频自己录屏，别搬运
- 评论区引导词固定成『部署』，方便你筛真实需求
""".format(name=m["name"])


def kit_bilibili(m):
    return """# B 站（1–2 条/天，教程类吃长尾）

## 标题
【开源】{name} 从 0 部署到能用｜中文配置 + 踩坑记录

## 分区
科技 → 计算机技术

## 简介
这个项目我自己用了很久，部署踩了不少坑，这期把完整过程录下来：
00:00 这东西能干什么（先看效果）
01:20 环境准备
03:40 部署（三条命令）
07:10 首次配置
10:30 常见报错
13:00 备份与升级

源码是开源的（{license}），我做的是中文部署包和讲解，需要的看评论区置顶。
不含服务器费用；商用请自行确认许可证义务。

标签：开源 自部署 {slug_tag} 教程

## 注意
- 商业推广要标「含推广」，这反而加分
- 做成系列合集，长尾比爆款值钱
""".format(name=m["name"], license=m["license"], slug_tag=m["slug"].replace("-", ""))


def kit_xianyu(m):
    return """# 闲鱼（3–5 条/天，一人一号，别多号铺同款）

## 标题（≤30 字，塞真实搜索词）
{name}中文部署包 一键安装 附教程 远程协助

## 详情
【你拿到什么】
· 一键部署脚本（Docker，三条命令跑起来）
· 中文说明书：安装 / 配置 / 报错 / 备份
· 远程协助装到你的服务器或电脑，跑通再确认收货
· 含 1 次免费修改

【说明白，不玩虚的】
· 软件本身开源免费（{license}），我卖的是部署、汉化、答疑的工时
· 不含服务器费用、不含第三方接口费用
· 不承诺永久可用：上游更新/接口变更不在此列
· 支持 Ubuntu / WSL2 / macOS

【交付】
拍下后我发部署包 + 约时间远程；跑通你验收再确认。

## 自动回复（第一条别秒回模板，先问场景）
在的，先确认下：你是要装在自己服务器还是本机？系统是 Linux 还是 Windows？
我按你的环境给方案，能跑通再拍。

## 风控注意
- 详情和聊天里不要出现微信/QQ/加V（虚拟商品判定最敏感）
- 不要写"包过/保证永久"
- 同款不要换号重铺；价格改动直接改，不要删了重发
- 客户纠纷优先退款换好评，一条差评比一单利润贵
""".format(name=m["name"], license=m["license"])


def kit_qq(m):
    return """# QQ 群 / 频道（1–2 条/天/群，先潜水再谈）

## 群里（只在允许发需求的群，且只发一次）
最近在折腾 {name}，把部署和中文文档整理成了一套一键包，有人在群里问过部署问题的可以直接找我，我按你的环境说方案，跑通再说钱。

## 私聊开场（必须提到对方的具体需求，模板群发一眼就被识破）
看到你在群里说『对方的那句原话』。这块我刚好踩过：
· 一般是（写清根因）
· 处理方式（写清你实际做的两步）
我可以远程给你装好并跑通，装完你验收，不跑通不要钱。

## 安全线
- 不群发、不 @ 全体、不在群里刷
- 私聊频率受 qq-desktop-control 的 Guard 限制（3s / 20 每小时 / 120 每天），别改
- 被踢或被举报就停手换群，不要硬顶
""".format(name=m["name"])


def kit_twitter(m):
    return """# X / Twitter（只做选题与存在感，不刷 DM）

## 单条推文（英文）
Open-sourced {name} is genuinely useful — but self-hosting it is a weekend of pain.
I packaged it: one-command Docker deploy, Chinese docs, gotcha list.
Code is free ({license}); what I sell is the hours. No affiliation.

## thread 大纲（讲你怎么做成产品，比广告有效）
1/ 我为什么选这个项目（一个具体痛点，不要泛泛）
2/ 部署踩了哪三个坑（截图）
3/ 我怎么把它变成可交付的包（一键脚本 + 文档）
4/ 定价逻辑：我卖工时，不卖代码
5/ 问一句：你想优先支持哪个系统？

## 纪律
- 每天 DM ≤5，且只在对方公开求推荐时
- 不做自动关注/取关、不批量 DM 带链接 —— X 封号最快的就是这个
- 用搜索/趋势找选题，不要搬运别人的内容
""".format(name=m["name"], license=m["license"])


def cmd_kit(a):
    slug = a.slug
    d = os.path.join(LISTINGS, slug)
    mp = os.path.join(d, "meta.json")
    if not os.path.exists(mp):
        raise SystemExit("没有这个商品: %s（先跑 pack）" % slug)
    m = json.load(open(mp, encoding="utf-8"))
    kit_dir = os.path.join(d, "kit")
    os.makedirs(kit_dir, exist_ok=True)
    files = {
        "xiaohongshu.md": kit_xhs(m), "douyin.md": kit_douyin(m),
        "bilibili.md": kit_bilibili(m), "xianyu.md": kit_xianyu(m),
        "qq_group.md": kit_qq(m), "twitter.md": kit_twitter(m),
    }
    for fn, content in files.items():
        with open(os.path.join(kit_dir, fn), "w", encoding="utf-8") as f:
            f.write(content)
    m.setdefault("channels", {})
    for ch in ("xiaohongshu", "douyin", "bilibili", "xianyu", "qq_group", "twitter"):
        m["channels"].setdefault(ch, "draft")
    with open(mp, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
    print("已生成 6 个渠道素材: %s" % kit_dir)
    for fn in files:
        print("  " + fn)
    print("""
⚠ 三件事，不做就别发：
1. 六个渠道的文案是**不同版本**，别复制粘贴同一段（查重/同质化会直接降权）
2. 每个渠道对照 channels.json 的 ban_triggers 自查一遍
3. 平台安全靠行为，不靠工具：官方登录态 > 人工节奏 > GUI；不做指纹伪装/多开/群控""")


# ---------------------------------------------------------------- 台账
def ledger_path():
    return os.path.join(LISTINGS, "ledger.json")


def cmd_ledger(a):
    os.makedirs(LISTINGS, exist_ok=True)
    led = {}
    if os.path.exists(ledger_path()):
        led = json.load(open(ledger_path(), encoding="utf-8"))
    if a.action == "list":
        if not led:
            print("（空）先 pack + kit，再 ledger set <slug> <channel> live")
            return
        print("%-26s %-10s %s" % ("slug", "status", "channels"))
        for k, v in sorted(led.items()):
            chs = ", ".join("%s=%s" % (c, s) for c, s in (v.get("channels") or {}).items())
            print("%-26s %-10s %s" % (k, v.get("status", "-"), chs or "-"))
        return
    if a.action == "set":
        if not (a.slug and a.channel):
            raise SystemExit("用法: ledger set <slug> <channel> <status>")
        e = led.setdefault(a.slug, {"status": "draft", "channels": {}})
        e["channels"][a.channel] = a.status
        if a.status in ("live", "selling"):
            e["status"] = "live"
        e["updated"] = now()
        json.dump(led, open(ledger_path(), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("%s / %s → %s" % (a.slug, a.channel, a.status))


# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description="开源项目选品 / License 审计 / 封装 / 分发素材")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("search", help="搜候选项目并打分")
    p.add_argument("--q", default="topic:self-hosted", help="GitHub 搜索语法")
    p.add_argument("--min-stars", type=int, default=500)
    p.add_argument("--limit", type=int, default=12)
    p.add_argument("--sort", default="stars", choices=["stars", "updated", "forks"])
    p.add_argument("-v", "--verbose", action="store_true")

    p = sub.add_parser("audit", help="License + 活性 + 变现路径审计")
    p.add_argument("repo", help="owner/repo")

    p = sub.add_parser("pack", help="生成商品骨架（README/部署/文档）")
    p.add_argument("repo")
    p.add_argument("--slug")
    p.add_argument("--name", help="商品名（不要用上游商标）")
    p.add_argument("--force", action="store_true", help="License 有风险时强制生成")

    p = sub.add_parser("kit", help="生成 6 个渠道的文案素材")
    p.add_argument("slug")

    p = sub.add_parser("ledger", help="在售台账")
    p.add_argument("action", choices=["list", "set"])
    p.add_argument("slug", nargs="?")
    p.add_argument("channel", nargs="?")
    p.add_argument("status", nargs="?", default="live")

    a = ap.parse_args()
    {"search": cmd_search, "audit": cmd_audit, "pack": cmd_pack,
     "kit": cmd_kit, "ledger": cmd_ledger}[a.cmd](a)


if __name__ == "__main__":
    main()
