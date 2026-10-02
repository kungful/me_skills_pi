#!/usr/bin/env python3
"""webbrowse.py - dependency-light web browsing CLI for the web-browse skill.

Commands
  fetch <url>        Fetch a page and print clean text/markdown (+ metadata, links)
  search <query>     Web search (Bing -> 360/so.com -> DuckDuckGo), prints ranked results
  shot <url>         Headless-Chrome screenshot (PNG) - then Read the image
  dump <url>         Save the raw HTML to disk for offline inspection

Design notes
  * Only needs: requests + lxml (both usually present). urllib fallback if requests is missing.
  * JavaScript-heavy pages: --render drives headless Chrome/Edge and parses the post-JS DOM.
  * Everything is printed UTF-8 so CJK pages survive the Windows console.
"""

from __future__ import annotations

import argparse
import base64
import html as htmllib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse as urlparse

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    import requests
except ImportError:
    requests = None

try:
    from lxml import html as lxml_html
except ImportError:
    lxml_html = None

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

DEFAULT_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}

# ---------------------------------------------------------------- cache

CACHE_DIR = os.path.join(tempfile.gettempdir(), "webbrowse-cache")
MIN_INTERVAL = float(os.environ.get("WEB_BROWSE_MIN_INTERVAL", "1.0"))
_last_request = [0.0]


def _throttle():
    """Be polite: never fire two network requests back to back."""
    import time
    gap = time.time() - _last_request[0]
    if gap < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - gap)
    _last_request[0] = time.time()


def cache_path(key: str) -> str:
    import hashlib
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    return os.path.join(CACHE_DIR, h + ".txt")


def cache_get(key: str, ttl: int) -> str | None:
    if ttl <= 0:
        return None
    p = cache_path(key)
    try:
        if time.time() - os.path.getmtime(p) < ttl:
            with open(p, encoding="utf-8") as f:
                return f.read()
    except OSError:
        return None
    return None


def cache_drop(key: str):
    try:
        os.remove(cache_path(key))
    except OSError:
        pass


def cache_put(key: str, value: str):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cache_path(key), "w", encoding="utf-8") as f:
            f.write(value)
    except OSError:
        pass


import time  # noqa: E402  (used by cache helpers)

# ---------------------------------------------------------------- utilities

def die(msg: str, code: int = 1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def normalize_url(u: str) -> str:
    u = u.strip().strip('"').strip("'")
    if not urlparse.urlparse(u).scheme:
        u = "https://" + u
    return u


def decode_bytes(raw: bytes, ctype: str = "") -> str:
    """Decode bytes, honouring <meta charset> before falling back to heuristics."""
    head = raw[:4096].decode("ascii", "ignore")
    m = re.search(r'charset=["\']?([\w-]+)', head, re.I) or \
        re.search(r'charset=([\w-]+)', ctype, re.I)
    encs = []
    if m:
        encs.append(m.group(1))
    m2 = re.search(r'content=["\']?[\w-]+;\s*charset=([\w-]+)', head, re.I)
    if m2:
        encs.append(m2.group(1))
    encs += ["utf-8", "gb18030", "latin-1"]
    for enc in encs:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace")


def parse_headers(pairs: str | None) -> dict:
    out = dict(DEFAULT_HEADERS)
    if not pairs:
        return out
    for item in pairs.split("||"):
        if ":" in item:
            k, v = item.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def find_chrome() -> str | None:
    env = os.environ.get("WEB_BROWSE_CHROME")
    if env and os.path.exists(env):
        return env
    for name in ("chrome", "msedge", "chromium", "google-chrome", "chromium-browser"):
        p = shutil.which(name)
        if p:
            return p
    cands = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    for c in cands:
        if os.path.exists(c):
            return c
    return None


CHROME_FLAGS = [
    "--headless=new",
    "--disable-gpu",
    "--no-sandbox",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "--disable-sync",
    "--disable-background-networking",
    "--hide-scrollbars",
    "--mute-audio",
]


def run_chrome(args: list[str], timeout: int, binary: str | None = None) -> subprocess.CompletedProcess:
    """Run headless Chrome/Edge once with an isolated temp profile. Returns the process."""
    chrome = binary or find_chrome()
    if not chrome:
        die("no Chrome/Edge/Chromium found. Set WEB_BROWSE_CHROME=/path/to/chrome")
    profile = tempfile.mkdtemp(prefix="webbrowse-profile-")
    cmd = [chrome, *CHROME_FLAGS, f"--user-data-dir={profile}", *args]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        die(f"chrome timed out after {timeout}s (try a larger --timeout, or --no-render)")
    finally:
        shutil.rmtree(profile, ignore_errors=True)


# ---------------------------------------------------------------- fetching

def http_get(url: str, headers: dict, timeout: int, cookie: str | None = None) -> tuple[str, int, str]:
    hdrs = dict(headers)
    if cookie:
        hdrs["Cookie"] = cookie
    if requests:
        try:
            _throttle()
            r = requests.get(url, headers=hdrs, timeout=timeout, allow_redirects=True)
            return decode_bytes(r.content, r.headers.get("Content-Type", "")), r.status_code, r.url
        except requests.RequestException as e:
            die(f"request failed: {e}")
    import urllib.request
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return decode_bytes(resp.read(), resp.headers.get("Content-Type", "")), resp.status, resp.url
    except Exception as e:  # noqa: BLE001
        die(f"request failed: {e}")


def get_html(url: str, args) -> tuple[str, str]:
    """Return (final_url, html). Uses headless Chrome when --render is enabled."""
    key = f"{url}|render={not args.no_render}|wait={getattr(args, 'wait', 0)}|h={args.headers or ''}"
    if args.cache_ttl > 0:
        hit = cache_get(key, args.cache_ttl)
        if hit is not None:
            sys.stderr.write(f"[cache hit {args.cache_ttl}s] {url}\n")
            return hit.split("\n", 1)[0], hit.split("\n", 1)[1]
    if not args.no_render:
        html = ""
        url2 = url
        try:
            html, url2, code = render_html(url, args.timeout, args.wait)
            if code == 200 and len(html) > 500:
                if args.cache_ttl > 0:
                    cache_put(key, url2 + "\n" + html)
                return url2, html
            sys.stderr.write(f"[warn] render returned HTTP {code} / {len(html)} bytes; "
                             f"falling back to plain HTTP\n")
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[warn] render failed ({e}); falling back to plain HTTP\n")
    headers = parse_headers(args.headers)
    body, code, final = http_get(url, headers, args.timeout, args.cookie)
    if code >= 400:
        die(f"HTTP {code} for {url}")
    if args.cache_ttl > 0:
        cache_put(key, final + "\n" + body)
    return final, body


def render_html(url: str, timeout: int, wait: int) -> tuple[str, str, int]:
    """Return (rendered_dom, final_url, pseudo_status) using headless Chrome."""
    proc = run_chrome([f"--timeout={timeout * 1000}",
                       f"--virtual-time-budget={max(wait, 500)}",
                       "--dump-dom", url], timeout + 30)
    dom = proc.stdout
    return decode_bytes(dom), url, (200 if dom else 0)


# ---------------------------------------------------------------- html -> text

DROP_TAGS = {"script", "style", "noscript", "svg", "canvas", "iframe", "template",
             "form", "button", "input", "select", "textarea", "nav", "footer", "aside",
             "picture", "source", "link", "meta"}

BLOCK_TAGS = {"p", "div", "section", "article", "main", "header", "ul", "ol", "dl",
              "table", "tr", "blockquote", "pre", "figure", "hr"}

# tags that must start on a new line even when nested inside a <p>/<span>/<label>
BLOCKISH = BLOCK_TAGS | {"li", "dt", "dd", "label", "form", "fieldset", "footer", "aside",
                         "nav", "figcaption", "caption", "address", "details", "summary",
                         "tbody", "thead", "tfoot", "h1", "h2", "h3", "h4", "h5", "h6"}


def _cells(tr):
    """Return the direct cell texts of a table row."""
    out = []
    for cell in tr:
        if not isinstance(cell.tag, str):
            continue
        if cell.tag.lower() in ("td", "th"):
            t = re.sub(r"\s*\n\s*", " ", _inline(cell, "", False)).strip()
            out.append(t)
    return out


def _table_to_md(table, base_url, keep_links) -> list[str]:
    rows = []
    for tr in table.xpath(".//tr"):
        cells = _cells(tr)
        if cells:
            rows.append(cells)
    if not rows:
        return []
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    has_header = bool(table.xpath(".//th"))
    lines = ["| " + " | ".join(rows[0]) + " |",
             "|" + "|".join([" --- "] * width) + "|"]
    body = rows[1:] if has_header else rows
    if not has_header:
        lines = ["| " + " | ".join([""] * width) + " |", "|" + "|".join([" --- "] * width) + "|"]
    for r in body:
        lines.append("| " + " | ".join(c.replace("|", "\\|") for c in r) + " |")
    return ["\n"] + lines + [""]


def _txt(node) -> str:
    return re.sub(r"\s+", " ", "".join(node.itertext())).strip()


def split_selectors(spec: str) -> tuple[str, ...]:
    """Split a --drop spec into xpath expressions.

    Primary separator is ';' or newline. A bare comma is only treated as a separator when the
    spec has no parentheses/brackets, so that contains(@class,'x') survives intact.
    """
    spec = (spec or "").strip()
    if not spec:
        return ()
    parts = [p.strip() for chunk in re.split(r"[;\n\r]+", spec) for p in [chunk] if p.strip()]
    if len(parts) == 1 and "," in parts[0] and "(" not in parts[0] and "[" not in parts[0]:
        parts = [p.strip() for p in parts[0].split(",") if p.strip()]
    return tuple(parts)


def html_to_markdown(raw_html: str, base_url: str = "", keep_links: bool = True,
                     drop_selectors: tuple[str, ...] = ()) -> str:
    if lxml_html is None:
        body = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw_html)
        body = re.sub(r"(?s)<[^>]+>", " ", body)
        return re.sub(r"\n{3,}", "\n\n", htmllib.unescape(re.sub(r"[ \t]+", " ", body))).strip()
    doc = lxml_html.fromstring(raw_html)
    for bad in doc.xpath("//comment()"):
        bad.getparent().remove(bad)
    for xp in drop_selectors:
        try:
            for el in doc.xpath(xp):
                _drop(el)
        except Exception as e:  # noqa: BLE001 - a bad xpath must not kill the fetch
            sys.stderr.write(f"[warn] bad drop xpath {xp!r}: {e}\n")
    for el in list(doc.iter()):
        tag = el.tag if isinstance(el.tag, str) else ""
        if tag.lower() in DROP_TAGS:
            _drop(el)
    for bad in doc.xpath("//h1"):
        _drop(bad)

    out: list[str] = []
    root = doc.find("body") if doc.find("body") is not None else doc
    _walk(root, out, base_url, keep_links, 0)
    md = "\n".join(out)
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


def _drop(el):
    p = el.getparent()
    if p is not None:
        p.remove(el)


def _walk(el, out, base_url, keep_links, depth):
    for child in el:
        if not isinstance(child.tag, str):
            continue
        tag = child.tag.lower()
        if tag in DROP_TAGS:
            continue
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            t = _txt(child)
            if t:
                out.append("\n" + "#" * int(tag[1]) + " " + t + "\n")
            continue
        if tag == "p":
            t = _inline(child, base_url, keep_links)
            if t.strip():
                out.append(t.strip())
                out.append("")
            continue
        if tag == "br":
            out.append("\n")
            continue
        if tag == "hr":
            out.append("\n---\n")
            continue
        if tag == "img":
            alt = (child.get("alt") or "").strip()
            src = urlparse.urljoin(base_url, child.get("src") or child.get("data-src") or "")
            if alt or src:
                out.append(f"\n[image: {alt or 'no alt'}] {src}\n")
            continue
        if tag == "a":
            t = _inline(child, base_url, keep_links)
            href = child.get("href") or ""
            if href and not href.startswith(("#", "javascript:", "mailto:")):
                full = urlparse.urljoin(base_url, href)
                out.append(f"{t.strip()} <{full}>" if t.strip() else f"<{full}>")
            else:
                out.append(t)
            continue
        if tag == "li":
            t = _inline(child, base_url, keep_links).strip()
            if t:
                out.append("- " + re.sub(r"\s*\n\s*", " ", t))
            continue
        if tag in ("pre",):
            # docs sites sometimes wrap real markup (tables, divs) in <pre>; only emit a
            # code fence when the pre holds genuine text
            nested_blocks = child.xpath(".//table|.//ul|.//ol|.//div|.//p")
            if nested_blocks:
                _walk(child, out, base_url, keep_links, depth)
                continue
            out.append("\n```\n" + child.text_content().strip("\n") + "\n```\n")
            continue
        if tag == "code" and el.getparent() is not None and \
                (el.getparent().tag or "").lower() != "pre":
            out.append("`" + _txt(child) + "`")
            continue
        if tag in ("td", "th"):
            out.append(_inline(child, base_url, keep_links).strip() + " | ")
            continue
        if tag in ("tr",):
            out.append("\n")
            continue
        if tag in ("table",):
            out += _table_to_md(child, base_url, keep_links)
            continue
        if tag in ("tbody", "thead", "tfoot"):
            _walk(child, out, base_url, keep_links, depth)
            continue
        if tag in ("ul", "ol", "dl"):
            _walk(child, out, base_url, keep_links, depth)
            out.append("")
            continue
        if tag in BLOCK_TAGS:
            _walk(child, out, base_url, keep_links, depth + 1)
            out.append("")
            continue
        # unknown tag: keep its text but do not let siblings glue together
        before = len(out)
        _walk(child, out, base_url, keep_links, depth)
        if len(out) > before and out[-1] not in ("", "\n"):
            out.append("\n" if tag in BLOCKISH else " ")


def _inline(el, base_url, keep_links):
    parts = []
    if el.text:
        parts.append(htmllib.unescape(el.text))
    for child in el:
        if not isinstance(child.tag, str):
            continue
        tag = child.tag.lower()
        if tag == "br":
            parts.append("\n")
        elif tag in DROP_TAGS:
            pass
        elif tag == "img":
            alt = (child.get("alt") or "").strip()
            if alt:
                parts.append(alt)
        elif tag == "a":
            sub = _inline(child, base_url, keep_links).strip()
            href = (child.get("href") or "").strip()
            if keep_links and href and not href.startswith(("#", "javascript:", "mailto:")):
                full = urlparse.urljoin(base_url, href)
                parts.append(f"{sub} <{full}>" if sub else f"<{full}>")
            else:
                parts.append(sub)
        else:
            sub = _inline(child, base_url, keep_links)
            if tag in BLOCKISH:
                sub = sub.rstrip() + "\n"
            if tag in ("strong", "b") and sub.strip():
                sub = f"**{sub.strip()}**"
            elif tag in ("em", "i") and sub.strip():
                sub = f"*{sub.strip()}*"
            parts.append(sub)
        if child.tail:
            parts.append(htmllib.unescape(child.tail))
    return re.sub(r"[ \t]+", " ", "".join(parts))


def page_meta(raw_html: str, final_url: str) -> dict:
    meta = {"url": final_url}
    if lxml_html is None:
        m = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw_html)
        meta["title"] = htmllib.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else ""
        return meta
    doc = lxml_html.fromstring(raw_html)
    t = doc.xpath("//title/text()")
    meta["title"] = re.sub(r"\s+", " ", t[0]).strip() if t else ""
    for el in doc.xpath("//meta[@name or @property]"):
        key = (el.get("name") or el.get("property") or "").lower()
        if key in ("description", "og:title", "og:description", "og:site_name",
                   "author", "keywords", "og:type"):
            meta.setdefault(key, (el.get("content") or "").strip())
    canon = doc.xpath("//link[@rel='canonical']/@href")
    if canon:
        meta["canonical"] = urlparse.urljoin(final_url, canon[0])
    return meta


def extract_links(raw_html: str, base_url: str, same_host: bool = False, limit: int = 200) -> list[tuple[str, str]]:
    if lxml_html is None:
        return []
    doc = lxml_html.fromstring(raw_html)
    host = urlparse.urlparse(base_url).netloc
    seen, out = set(), []
    for a in doc.xpath("//a[@href]"):
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("javascript:", "mailto:", "#")):
            continue
        full = urlparse.urljoin(base_url, href)
        if not full.startswith("http"):
            continue
        if same_host and urlparse.urlparse(full).netloc != host:
            continue
        key = full.split("#")[0]
        if key in seen:
            continue
        seen.add(key)
        out.append((_txt(a) or key, key))
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------- search

def unwrap_bing(href: str) -> str:
    if "bing.com/ck/a" not in href:
        return href
    q = urlparse.parse_qs(urlparse.urlparse(href).query)
    for key in ("u", "a1"):
        for val in q.get(key, []):
            s = val[2:] if val.startswith("a1") else val
            s += "=" * (-len(s) % 4)
            try:
                return base64.urlsafe_b64decode(s).decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                pass
    return href


def search_bing(query: str, limit: int, headers: dict, timeout: int, site: str | None) -> list[dict]:
    q = f"{query} site:{site}" if site else query
    headers = dict(headers, **{"Accept": "text/html,*/*;q=0.8"})
    body, code, _ = http_get("https://www.bing.com/search?q=" + urlparse.quote(q) + "&setlang=zh-CN",
                             headers, timeout)
    if lxml_html is None:
        return []
    doc = lxml_html.fromstring(body)
    res = []
    for li in doc.xpath("//li[contains(@class,'b_algo')]"):
        a = li.xpath(".//h2/a")
        if not a:
            continue
        cap = li.xpath(".//div[contains(@class,'b_caption')]//p")
        res.append({
            "title": _txt(a[0]),
            "url": unwrap_bing(a[0].get("href") or ""),
            "snippet": _txt(cap[0]) if cap else "",
        })
        if len(res) >= limit:
            break
    return res


def search_so(query: str, limit: int, headers: dict, timeout: int, site: str | None) -> list[dict]:
    """360 搜索 - good Chinese-web coverage, no API key, real URL in data-mdurl."""
    q = f"{query} site:{site}" if site else query
    headers = dict(headers, **{"Accept": "text/html,*/*;q=0.8"})
    body, code, _ = http_get("https://www.so.com/s?q=" + urlparse.quote(q), headers, timeout)
    if lxml_html is None:
        return []
    doc = lxml_html.fromstring(body)
    res = []
    for li in doc.xpath("//li[contains(@class,'res-list')]"):
        a = li.xpath(".//h3//a")
        if not a:
            continue
        desc = li.xpath(".//p[contains(@class,'res-desc')]")
        res.append({
            "title": _txt(a[0]),
            "url": a[0].get("data-mdurl") or a[0].get("href") or "",
            "snippet": _txt(desc[0]) if desc else "",
        })
        if len(res) >= limit:
            break
    return res


def search_ddg(query: str, limit: int, headers: dict, timeout: int, site: str | None) -> list[dict]:
    """DuckDuckGo lite. Frequently serves a 202 anti-bot challenge; last resort only."""
    q = f"{query} site:{site}" if site else query
    body, code, _ = http_get("https://lite.duckduckgo.com/lite/?q=" + urlparse.quote(q),
                             headers, timeout)
    if lxml_html is None:
        return []
    doc = lxml_html.fromstring(body)
    res, seen = [], set()
    for a in doc.xpath("//a[@href]"):
        href = a.get("href") or ""
        if "duckduckgo.com/l/?" in href:
            full = "https:" + href if href.startswith("//") else href
            target = urlparse.parse_qs(urlparse.urlparse(full).query).get("uddg", [""])[0]
            if target and target not in seen:
                seen.add(target)
                res.append({"title": _txt(a), "url": target, "snippet": ""})
        if len(res) >= limit:
            break
    return res


ENGINES = {"bing": search_bing, "so": search_so, "ddg": search_ddg}
AUTO_ORDER = ["bing", "so", "ddg"]


STOPWORDS = {"的", "了", "和", "与", "及", "在", "是", "什么", "怎么", "如何", "为什么",
             "请问", "一个", "the", "a", "an", "of", "to", "in", "on", "for", "and", "or",
             "is", "are", "what", "how", "why", "when", "which", "who", "with", "do", "does",
             "can", "i", "you", "it", "that", "this", "be", "as", "at", "by", "from"}


def query_terms(query: str) -> list[str]:
    """Significant tokens: latin words + CJK runs (as a whole if short, else bigrams)."""
    terms = []
    for tok in re.findall(r"[A-Za-z0-9.+#-]{2,}", query):
        low = tok.lower()
        if low not in STOPWORDS:
            terms.append(low)
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", query):
        if run in STOPWORDS:
            continue
        if len(run) <= 4:
            terms.append(run)
        else:
            terms += [run[i:i + 2] for i in range(len(run) - 1)]
    return terms


def looks_blocked(results: list[dict], query: str = "", site_host: str = "") -> str | None:
    """Search engines soft-block by serving unrelated results. Two tells:
    (a) nearly every hit shares one host (e.g. everything is a translator page),
    (b) almost no hit mentions any term from the query.
    """
    if not results:
        return None
    hosts = {}
    for r in results:
        host = urlparse.urlparse(r.get("url", "")).netloc
        hosts[host] = hosts.get(host, 0) + 1
    top, n = max(hosts.items(), key=lambda kv: kv[1])
    if len(results) >= 3 and n / len(results) >= 0.7 and \
            not (site_host and top and site_host in top):
        return f"{n}/{len(results)} results share host {top!r} - soft block suspected"
    terms = query_terms(query)
    if terms and len(results) >= 3:
        hits = 0
        for r in results:
            blob = (r.get("title", "") + " " + r.get("url", "") + " " +
                    r.get("snippet", "")).lower()
            if any(t in blob for t in terms):
                hits += 1
        if hits / len(results) < 0.34:
            return (f"only {hits}/{len(results)} results match the query terms "
                    f"{terms[:4]} - soft block suspected")
    return None


def cmd_search(args):
    headers = parse_headers(args.headers)
    order = AUTO_ORDER if args.engine == "auto" else [args.engine]
    if args.engine == "auto" and args.site:
        # ddg honours site: best; bing/so often ignore it
        order = ["ddg", "bing", "so"]
    results, notes = [], []
    site_host = (args.site or "").lower().lstrip(".")
    for name in order:
        key = f"search|{name}|{args.query}|{args.site}|{args.limit}"
        cached = cache_get(key, args.cache_ttl)
        if cached is not None:
            sys.stderr.write(f"[cache hit] search {name}: {args.query}\n")
            import json
            try:
                results = json.loads(cached)
            except Exception:  # noqa: BLE001
                results = []
        else:
            for attempt in (1, 2):
                try:
                    results = ENGINES[name](args.query, args.limit, headers, args.timeout, args.site)
                except SystemExit as e:
                    notes.append(f"{name}: {e}")
                    break
                except Exception as e:  # noqa: BLE001
                    notes.append(f"{name}: {type(e).__name__} {e}")
                    break
                warn = looks_blocked(results, args.query, site_host)
                if warn and attempt == 1:
                    notes.append(f"{name}: {warn}; retrying")
                    time.sleep(3.0)
                    continue
                if warn:
                    notes.append(f"{name}: {warn}")
                    results = []
                break
            if results and not looks_blocked(results, args.query, site_host) and args.cache_ttl > 0:
                import json
                cache_put(key, json.dumps(results, ensure_ascii=False))
        if results and site_host:
            # engines largely ignore "site:" syntax, so enforce it locally and say so
            kept = [r for r in results if site_host in urlparse.urlparse(r["url"]).netloc.lower()]
            if kept:
                results = kept
            else:
                notes.append(f"{name}: engine ignored site:{args.site}; no result actually on that host")
                results = []
        if results and not looks_blocked(results, args.query, site_host):
            break
        if results:
            cache_drop(key)  # cached copy was garbage; do not serve it again
        results = []
    if args.json:
        import json
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return
    if not results:
        print(f"No usable results for {args.query!r}. Tried: {', '.join(order)}.", file=sys.stderr)
        for n in notes:
            print(f"  - {n}", file=sys.stderr)
        print("Fallbacks: wait ~1 min (engines rate-limit bursts), try --engine so, "
              "narrow the query, or - for --site - fetch the site index directly "
              "(`fetch https://<site>/ --format links`) and pick from the link list.", file=sys.stderr)
        return
    for i, r in enumerate(results, 1):
        print(f"\n{i}. {r['title']}\n   {r['url']}")
        if r.get("snippet"):
            print(f"   {r['snippet'][:300]}")


# ---------------------------------------------------------------- commands

def cmd_fetch(args):
    url = normalize_url(args.url)
    final, raw = get_html(url, args)
    if args.format == "html":
        print(raw)
        return
    meta = page_meta(raw, final)
    if args.format == "meta":
        for k, v in meta.items():
            print(f"{k}: {v}")
        return
    if args.format == "links":
        for text, href in extract_links(raw, final, args.same_host, args.limit):
            print(f"{text}\t{href}")
        return
    body = html_to_markdown(raw, final, keep_links=not args.no_links,
                            drop_selectors=split_selectors(args.drop))
    desc = meta.get("description", "")
    if len(desc) > 300:
        desc = desc[:300] + "..."
    header = "" if args.bare else (
        f"# {meta.get('title', '')}\n"
        f"URL: {final}\n"
        + (f"Description: {desc}\n" if desc else "")
        + "\n")
    text = header + body
    if args.max_chars and len(text) > args.max_chars:
        cut = text[:args.max_chars]
        text = cut + (f"\n\n[truncated at {args.max_chars} chars - rerun with "
                      f"--max-chars {args.max_chars * 4} for more]")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"saved {len(text)} chars -> {args.out}")
    else:
        print(text)


def cmd_shot(args):
    url = normalize_url(args.url)
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    if os.path.exists(out) and not args.force:
        die(f"{out} already exists (pass --force to overwrite)")
    flags = [f"--window-size={args.width},{args.height}",
             f"--virtual-time-budget={args.wait}",
             f"--screenshot={out}"]
    if args.full_page:
        flags.append("--hide-scrollbars")
        flags.append(f"--window-size={args.width},{args.height * 3}")
    proc = run_chrome(flags + [url], args.timeout + 30)
    if os.path.exists(out) and os.path.getsize(out) > 0:
        print(f"screenshot -> {out} ({os.path.getsize(out)} bytes)")
    else:
        sys.stderr.write(proc.stderr.decode("utf-8", "replace")[-800:])
        die("screenshot failed")


def cmd_dump(args):
    url = normalize_url(args.url)
    final, raw = get_html(url, args)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(raw)
    print(f"saved {len(raw)} chars of HTML from {final} -> {args.out}")


def main():
    ap = argparse.ArgumentParser(prog="webbrowse.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, render=True):
        p.add_argument("url")
        p.add_argument("--timeout", type=int, default=30)
        p.add_argument("--headers", help='extra headers, "K:V||K2:V2"')
        p.add_argument("--cookie")
        p.add_argument("--no-render", action="store_true",
                       help="skip headless Chrome even if it is available (faster)")
        p.add_argument("--cache-ttl", type=int, default=3600,
                       help="reuse a cached copy for N seconds (0 disables)")
        if render:
            p.add_argument("--wait", type=int, default=3000,
                           help="ms of virtual time budget for JS rendering (default 3000)")

    f = sub.add_parser("fetch", help="fetch and clean a page")
    common(f)
    f.add_argument("--format", choices=["text", "html", "meta", "links"], default="text")
    f.add_argument("--max-chars", type=int, default=20000)
    f.add_argument("--out")
    f.add_argument("--same-host", action="store_true", help="links: keep only this host")
    f.add_argument("--no-links", action="store_true", help="strip link targets, keep anchor text")
    f.add_argument("--drop", help="lxml xpaths to remove, separated by ';' or newline, "
                                  "e.g. '//div[@class=\"ad\"]; //footer'")
    f.add_argument("--bare", action="store_true", help="no title/URL header")
    f.add_argument("--limit", type=int, default=200, help="links: max count")
    f.set_defaults(func=cmd_fetch)

    s = sub.add_parser("search", help="web search")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=8)
    s.add_argument("--site")
    s.add_argument("--engine", choices=["auto", "bing", "so", "ddg"], default="auto",
                   help="auto = bing, then 360 (so.com), then ddg")
    s.add_argument("--json", action="store_true")
    s.add_argument("--timeout", type=int, default=25)
    s.add_argument("--headers")
    s.add_argument("--cache-ttl", type=int, default=1800)
    s.set_defaults(func=cmd_search)

    sh = sub.add_parser("shot", help="screenshot with headless Chrome")
    sh.add_argument("url")
    sh.add_argument("--out", default="shot.png")
    sh.add_argument("--width", type=int, default=1280)
    sh.add_argument("--height", type=int, default=900)
    sh.add_argument("--wait", type=int, default=4000)
    sh.add_argument("--timeout", type=int, default=40)
    sh.add_argument("--full-page", action="store_true",
                    help="taller window to capture more of the page")
    sh.add_argument("--force", action="store_true", help="overwrite an existing file")
    sh.set_defaults(func=cmd_shot)

    d = sub.add_parser("dump", help="save raw HTML")
    common(d)
    d.add_argument("--out", default="page.html")
    d.set_defaults(func=cmd_dump)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()