#!/usr/bin/env python3
"""browse.py - interactive browsing CLI: probe tabs/buttons, click into them, read what loads.

Backed by cdp.py (headless Chrome over the DevTools Protocol, stdlib only), so a session
survives across separate CLI calls: open a page, probe it, click a tab, read the new content.

  python browse.py open  <url>              open/reuse session, print page + clickable elements
  python browse.py probe [--text 关键词]    list tabs/buttons/links with indexes
  python browse.py click <index> [--text T] [--selector CSS] [--shot out.png]
  python browse.py read  [--max-chars N] [--out f.md]
  python browse.py goto <url> | back | forward | reload
  python browse.py scroll [--pages N]
  python browse.py shot  [--out f.png] [--full]
  python browse.py hover <index>            open hover menus / dropdowns
  python browse.py type  <index> <text>     fill an input, then Enter
  python browse.py eval  '<javascript>'
  python browse.py pages | close [--all]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import cdp  # noqa: E402
from webbrowse import html_to_markdown, page_meta, extract_links  # noqa: E402

# ------------------------------------------------------------------ JS

JS_CSS_PATH = r"""
function safeQuery(sel){ try { return document.querySelectorAll(sel); } catch(e){ return null; } }
function segFor(el){
  let seg = el.tagName.toLowerCase();
  const sibs = el.parentNode ? [].filter.call(el.parentNode.children, c => c.tagName === el.tagName) : [];
  if (sibs.length > 1) return seg + ':nth-of-type(' + (sibs.indexOf(el) + 1) + ')';
  const cls = (el.getAttribute('class') || '').trim().split(/\s+/)
              .filter(c => c && !/^(ng|css|sc|jsx|emotion)-?[a-z0-9]{4,}$/i.test(c) && !/\d{4,}/.test(c))
              .slice(0, 2);
  if (cls.length) {
    const cand = seg + '.' + cls.map(c => CSS.escape(c)).join('.');
    if (safeQuery(cand)) return cand;
  }
  return seg;
}
function cssPath(el){
  if (el.id) { const s = '#' + CSS.escape(el.id);
               if (safeQuery(s) && safeQuery(s).length === 1) return s; }
  const parts = [];
  let cur = el, depth = 0;
  while (cur && cur.nodeType === 1 && cur.tagName !== 'HTML' && depth < 12) {
    if (cur.id && !/[\\]/.test(cur.id)) {
      const s = '#' + CSS.escape(cur.id);
      parts.unshift(s);
      const cand = parts.join(' > ');
      if (safeQuery(cand) && safeQuery(cand).length === 1) return cand;
    } else {
      parts.unshift(segFor(cur));
    }
    cur = cur.parentNode; depth++;
    const cand = parts.join(' > ');
    if (safeQuery(cand) && safeQuery(cand).length === 1 && depth > 2) return cand;
  }
  return parts.join(' > ');
}
"""

JS_CLICKABLE = r"""
function hasReactClick(el){
  for (const k of Object.keys(el)) {
    if (/^__reactProps\$|__reactEventHandlers\$/.test(k)) {
      const p = el[k];
      if (p && (typeof p.onClick === 'function' || typeof p.onMouseDown === 'function' ||
                typeof p.onMouseUp === 'function' || typeof p.onPointerDown === 'function'))
        return true;
    }
  }
  return false;
}
function looksClickable(el){
  if (hasReactClick(el)) return true;
  const cs = getComputedStyle(el);
  if (cs.cursor === 'pointer') return true;
  if (el.tagName === 'SUMMARY' || el.tagName === 'BUTTON' || el.tagName === 'A') return true;
  if (el.hasAttribute('onclick')) return true;
  return false;
}
function isLeafLabel(el){
  for (const c of el.children) {
    if (c.nodeType !== 1) continue;
    if ((c.innerText || '').trim().length > 45) return false;
  }
  return true;
}
"""

JS_PROBE = r"""
(() => {
  %s
  %s
  const SEL = 'a[href], button, [role=tab], [role=button], [role=menuitem], [role=option], ' +
    '[onclick], summary, label[for], select, input[type=submit], input[type=button], ' +
    '[class*=tab], [class*=Tab], [class*=menu-item], [class*=MenuItem], [class*=nav-item], ' +
    '[class*=dropdown], [class*=Dropdown], [class*=collapse], [class*=Collapse], ' +
    '[class*=accordion], [class*=step], [class*=switch], [class*=toggle], ' +
    '[data-testid], [data-index], [aria-controls], .ant-tabs-tab, .el-tabs__item, .ant-menu-item';
  const out = [], seen = new Set();
  function add(el, tag) {
    if (!el.offsetParent && getComputedStyle(el).position !== 'fixed') return;
    const r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) return;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.opacity === '0' || cs.pointerEvents === 'none') return;
    const text = (el.innerText || el.value || el.getAttribute('aria-label') ||
                  el.getAttribute('title') || el.getAttribute('placeholder') || '')
                 .replace(/\s+/g, ' ').trim().slice(0, 90);
    const href = el.tagName === 'A' ? (el.getAttribute('href') || '') : '';
    if (!text && !href) return;
    const key = cssPath(el);
    if (seen.has(key)) return;
    seen.add(key);
    out.push({ sel: key, text, tag, role: el.getAttribute('role') || '',
               href: href.slice(0, 200),
               on: el.getAttribute('aria-selected') || el.getAttribute('aria-expanded') || '',
               y: Math.round(r.top + window.scrollY), x: Math.round(r.left) });
  }
  for (const el of document.querySelectorAll(SEL)) add(el, el.tagName.toLowerCase());
  // second pass: framework-rendered tabs / divs / spans with click handlers or pointer cursor
  for (const el of document.querySelectorAll('div, span, li, p, td, th, label, a, span[class*=item]')) {
    if (seen.has(el)) continue;
    const text = (el.innerText || '').replace(/\s+/g, ' ').trim();
    if (!text || text.length > 60 || !isLeafLabel(el) || !looksClickable(el)) continue;
    add(el, el.tagName.toLowerCase());
  }
  out.sort((a, b) => (a.y - b.y) || (a.x - b.x));
  // drop containers that merely wrap another listed element
  return out.filter(e => !out.some(o => o !== e && o.sel.startsWith(e.sel + ' > ')));
})()
""" % (JS_CSS_PATH, JS_CLICKABLE)

JS_RECT = r"""
(() => { const el = document.querySelector(%s);
  if (!el) return null;
  el.scrollIntoView({block:'center', inline:'center'});
  const r = el.getBoundingClientRect();
  return {x: r.left + r.width/2, y: r.top + r.height/2, w: r.width, h: r.height,
          tag: el.tagName.toLowerCase(),
          text: (el.innerText || el.value || '').replace(/\s+/g,' ').trim().slice(0,90)};
})()
"""

JS_TEXT = "document.body ? document.body.innerText : ''"
JS_HTML = "document.documentElement.outerHTML"


# ------------------------------------------------------------------ helpers

def browser_for(args) -> cdp.Browser:
    b = cdp.Browser(args.session)
    b.start(fresh=args.fresh)
    return b


def page_body(b, sid, max_chars, out=None, bare=False, drop=""):
    raw = b.html(sid)
    meta = page_meta(raw, b.eval(sid, "location.href") or "")
    body = html_to_markdown(
        raw, meta.get("url", ""), drop_selectors=tuple(s.strip() for s in drop.split(",") if s.strip()))
    if bare:
        text = body
    else:
        desc = (meta.get("description") or "")[:300]
        text = (f"# {meta.get('title','')}\nURL: {meta.get('url','')}\n"
                + (f"Description: {desc}\n" if desc else "") + "\n" + body)
    if max_chars and len(text) > max_chars:
        text = text[:max_chars] + f"\n\n[truncated at {max_chars} chars]"
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"saved {len(text)} chars -> {out}")
    else:
        print(text)


def print_state(b, sid, note=""):
    info = b.info(sid)
    if note:
        print(note)
    print(f"URL: {info['url']}")
    print(f"TITLE: {info['title']}")


def probe(b, sid, limit, contains=None, show_selector=False):
    items = b.eval(sid, JS_PROBE)
    if not isinstance(items, list):
        print("probe failed: unexpected result")
        return []
    if contains:
        key = contains.lower()
        items = [i for i in items if key in (i["text"] or "").lower()
                 or key in (i["href"] or "").lower()]
    shown = items[:limit] if limit else items
    print(f"{len(items)} clickable element(s)" + (f", showing {len(shown)}" if limit and len(items) > len(shown) else ""))
    for i, el in enumerate(shown, 1):
        flags = []
        if el["role"]:
            flags.append(el["role"])
        if el["on"]:
            flags.append(f"state={el['on']}")
        if el["href"]:
            flags.append("link")
        tail = ("  [" + ", ".join(flags) + "]") if flags else ""
        print(f"[{i}] <{el['tag']}> {el['text']!r}{tail}")
        if show_selector:
            print(f"      {el['sel']}")
    return items


def resolve_target(b, sid, args) -> tuple[str, dict]:
    """Return (selector, info) for --selector / --text / positional index."""
    if args.selector:
        return args.selector, {"text": args.selector, "tag": "?"}
    if args.text:
        items = b.eval(sid, JS_PROBE) or []
        exact = [i for i in items if (i["text"] or "").strip() == args.text]
        loose = [i for i in items if args.text.lower() in (i["text"] or "").lower()]
        pick = (exact or loose)
        if not pick:
            raise SystemExit(f"ERROR: no clickable element whose text matches {args.text!r}. "
                             f"Run `probe` to see the list.")
        pick.sort(key=lambda e: len(e["text"] or ""))
        return pick[0]["sel"], pick[0]
    if args.index is None:
        raise SystemExit("ERROR: give an index (from `probe`), --text, or --selector")
    items = b.eval(sid, JS_PROBE) or []
    if not 1 <= args.index <= len(items):
        raise SystemExit(f"ERROR: index {args.index} out of range (1..{len(items)}). Re-run `probe`.")
    return items[args.index - 1]["sel"], items[args.index - 1]


def act_on(b, sid, selector, click=True):
    """Scroll into view, then dispatch a real mouse click (falls back to el.click())."""
    rect = b.eval(sid, JS_RECT % json.dumps(selector))
    if rect and rect.get("w", 0) > 0:
        b.eval(sid, "window.scrollBy(0,0)")
        time.sleep(0.25)
        rect = b.eval(sid, JS_RECT % json.dumps(selector)) or rect
        b.client.call("Input.dispatchMouseEvent",
                      {"type": "mouseMoved", "x": rect["x"], "y": rect["y"]}, sid)
        b.click_xy(sid, rect["x"], rect["y"])
        return rect
    if not click:
        return None
    ok = b.eval(sid, f"(() => {{const e=document.querySelector({json.dumps(selector)});"
                     f"if(!e) return false; e.click(); return true;}})()")
    if not ok:
        raise SystemExit(f"ERROR: could not activate {selector!r}")
    return {"text": selector, "tag": "?", "w": 0, "h": 0}


# ------------------------------------------------------------------ commands

def cmd_open(args):
    b = browser_for(args)
    sid = b.open(args.url, wait=args.wait)
    print_state(b, sid, note=f"[session {args.session}] opened")
    print()
    page_body(b, sid, args.max_chars)
    print("\n--- clickable elements ---")
    probe(b, sid, args.probe_limit, show_selector=args.show_selectors)


def cmd_probe(args):
    b = browser_for(args)
    sid = b.session(args.label)
    probe(b, sid, args.limit, args.text, args.show_selectors)


def cmd_click(args):
    b = browser_for(args)
    sid = b.session(args.label)
    before = b.info(sid)
    selector, info = resolve_target(b, sid, args)
    rect = act_on(b, sid, selector)
    if args.hover:
        b.wait_settle(sid, quiet_ms=args.quiet, timeout=args.timeout)
    else:
        time.sleep(0.3)
        b.wait_settle(sid, quiet_ms=args.quiet, timeout=args.timeout)
    after = b.info(sid)
    print(f"clicked [{info.get('tag','?')}] {info.get('text','')!r}  "
          f"(y={info.get('y','?')})")
    print(f"URL: {after['url']}" + ("" if after["url"] == before["url"] else
                                    f"   (was {before['url']})"))
    print(f"TITLE: {after['title']}")
    if args.shot:
        b.screenshot(sid, os.path.abspath(args.shot), full_page=args.full)
        print(f"screenshot -> {os.path.abspath(args.shot)}")
    if args.links:
        print("\n--- links ---")
        for text, href in extract_links(b.html(sid), after["url"])[:args.links]:
            print(f"{text}\t{href}")
    else:
        print()
        page_body(b, sid, args.max_chars, out=args.out, bare=args.bare, drop=args.drop)
    if not args.keep_quiet:
        print("\n--- clickable elements (new page) ---")
        probe(b, sid, args.probe_limit)


def cmd_read(args):
    b = browser_for(args)
    sid = b.session(args.label)
    print_state(b, sid)
    print()
    page_body(b, sid, args.max_chars, out=args.out, bare=args.bare, drop=args.drop)


def cmd_goto(args):
    b = browser_for(args)
    sid = b.session(args.label)
    b.goto(args.url, wait=args.wait)
    print_state(b, sid)
    print()
    page_body(b, sid, args.max_chars)


def cmd_back(args):
    b = browser_for(args)
    sid = b.session(args.label)
    b.history(sid, back=True)
    print_state(b, sid)
    print()
    page_body(b, sid, args.max_chars)


def cmd_reload(args):
    b = browser_for(args)
    sid = b.session(args.label)
    b.eval(sid, "location.reload()")
    b.wait_ready(sid, args.wait)
    print_state(b, sid)
    print()
    page_body(b, sid, args.max_chars)


def cmd_scroll(args):
    b = browser_for(args)
    sid = b.session(args.label)
    b.scroll(sid, pages=args.pages)
    pos = b.eval(sid, "Math.round(window.scrollY)")
    height = b.eval(sid, "document.body.scrollHeight")
    print(f"scrolled to y={pos} of {height}")
    if args.shot:
        b.screenshot(sid, os.path.abspath(args.shot), full_page=args.full)
        print(f"screenshot -> {os.path.abspath(args.shot)}")


def cmd_shot(args):
    b = browser_for(args)
    sid = b.session(args.label)
    out = os.path.abspath(args.out)
    b.screenshot(sid, out, full_page=args.full)
    print(f"screenshot -> {out} ({os.path.getsize(out)} bytes)")


def cmd_hover(args):
    b = browser_for(args)
    sid = b.session(args.label)
    selector, info = resolve_target(b, sid, args)
    rect = b.eval(sid, JS_RECT % json.dumps(selector))
    if not rect:
        raise SystemExit(f"ERROR: no element for {selector!r}")
    b.client.call("Input.dispatchMouseEvent",
                  {"type": "mouseMoved", "x": rect["x"], "y": rect["y"]}, sid)
    time.sleep(0.5)
    b.wait_settle(sid, quiet_ms=args.quiet, timeout=10)
    print(f"hovered {info.get('text','')!r}")
    probe(b, sid, args.limit)


def cmd_type(args):
    b = browser_for(args)
    sid = b.session(args.label)
    selector, info = resolve_target(b, sid, args)
    rect = b.eval(sid, JS_RECT % json.dumps(selector))
    if not rect:
        raise SystemExit(f"ERROR: no element for {selector!r}")
    b.click_xy(sid, rect["x"], rect["y"])
    b.eval(sid, "(() => {const e=document.querySelector(" + json.dumps(selector) +
                 "); if(e){e.focus(); e.select && e.select();}})()")
    for ch in args.value:
        b.client.call("Input.dispatchKeyEvent", {"type": "keyDown", "text": ch}, sid)
        b.client.call("Input.dispatchKeyEvent", {"type": "keyUp"}, sid)
    if args.enter:
        for ev in ("rawKeyDown", "char", "keyUp"):
            b.client.call("Input.dispatchKeyEvent",
                          {"type": ev, "key": "Enter", "code": "Enter",
                           "windowsVirtualKeyCode": 13, "text": "\r"}, sid)
    time.sleep(0.6)
    b.wait_settle(sid, quiet_ms=args.quiet, timeout=args.timeout)
    print_state(b, sid, note=f"typed {args.value!r} into {info.get('text','')!r}")
    print()
    page_body(b, sid, args.max_chars)


def cmd_eval(args):
    b = browser_for(args)
    sid = b.session(args.label)
    val = b.eval(sid, args.js, await_promise=args.await_promise)
    print(json.dumps(val, ensure_ascii=False, indent=2) if isinstance(val, (dict, list))
          else (val if val is not None else "(undefined)"))


def cmd_pages(args):
    b = browser_for(args)
    print(f"session {args.session}: browser pid={b.pid} port={b.port}")
    for label, info in b.pages.items():
        sid = info["sessionId"]
        try:
            print(f"  [{label}] {b.eval(sid, 'location.href')}")
        except cdp.CDPError as e:
            print(f"  [{label}] <dead: {e}>")


def cmd_close(args):
    if args.all:
        import glob
        root = os.path.join(os.sys_temp if hasattr(os, "sys_temp") else
                            __import__("tempfile").gettempdir(), "webbrowse-browse")
        for f in glob.glob(os.path.join(root, "*.json")):
            name = os.path.splitext(os.path.basename(f))[0]
            cdp.Browser(name).cleanup()
            print(f"closed session {name}")
        return
    b = cdp.Browser(args.session)
    b.start()
    b.cleanup()
    print(f"closed session {args.session}")


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(prog="browse.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", default="default", help="browser session name (default)")
    ap.add_argument("--label", help="which page (default: main)")
    ap.add_argument("--fresh", action="store_true", help="start a brand-new browser")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def page_opts(p, chars=6000, probe_limit=40):
        p.add_argument("--max-chars", type=int, default=chars)
        p.add_argument("--out")
        p.add_argument("--bare", action="store_true")
        p.add_argument("--drop", default="")

    def target_opts(p):
        p.add_argument("index", type=int, nargs="?", help="element index from `probe`")
        p.add_argument("--text", help="click the element whose text equals/contains this")
        p.add_argument("--selector", help="raw CSS selector")
        p.add_argument("--quiet", type=int, default=1000, help="ms of DOM quiet to wait for")
        p.add_argument("--timeout", type=float, default=25)

    o = sub.add_parser("open", help="open a URL in a reusable session")
    o.add_argument("url")
    o.add_argument("--wait", type=float, default=3.0)
    o.add_argument("--probe-limit", type=int, default=40)
    o.add_argument("--show-selectors", action="store_true")
    page_opts(o)
    o.set_defaults(func=cmd_open)

    p = sub.add_parser("probe", help="list clickable elements")
    p.add_argument("--limit", type=int, default=60)
    p.add_argument("--text", help="only elements matching this text")
    p.add_argument("--show-selectors", action="store_true")
    p.set_defaults(func=cmd_probe)

    c = sub.add_parser("click", help="click a tab/button/element and read the result")
    target_opts(c)
    c.add_argument("--wait", type=float, default=1.0)
    c.add_argument("--shot", help="also save a screenshot here")
    c.add_argument("--full", action="store_true")
    c.add_argument("--links", type=int, nargs="?", const=40, default=0,
                   help="print links instead of page text")
    c.add_argument("--probe-limit", type=int, default=40)
    c.add_argument("--hover", action="store_true", help="do not click, just hover")
    c.add_argument("--keep-quiet", action="store_true", help="skip the element list afterwards")
    page_opts(c)
    c.set_defaults(func=cmd_click)

    r = sub.add_parser("read", help="dump the current page as markdown")
    page_opts(r, chars=12000)
    r.set_defaults(func=cmd_read)

    g = sub.add_parser("goto", help="navigate to another URL")
    g.add_argument("url")
    g.add_argument("--wait", type=float, default=3.0)
    page_opts(g)
    g.set_defaults(func=cmd_goto)

    for name, fn in (("back", cmd_back), ("reload", cmd_reload)):
        s = sub.add_parser(name)
        s.add_argument("--wait", type=float, default=3.0)
        page_opts(s, chars=8000)
        s.set_defaults(func=fn)

    sc = sub.add_parser("scroll", help="scroll the page")
    sc.add_argument("--pages", type=float, default=1.0)
    sc.add_argument("--shot")
    sc.add_argument("--full", action="store_true")
    sc.set_defaults(func=cmd_scroll)

    sh = sub.add_parser("shot", help="screenshot the current page")
    sh.add_argument("--out", default="page.png")
    sh.add_argument("--full", action="store_true")
    sh.set_defaults(func=cmd_shot)

    h = sub.add_parser("hover", help="hover an element (dropdown menus)")
    h.add_argument("index", type=int, nargs="?")
    h.add_argument("--text")
    h.add_argument("--selector")
    h.add_argument("--limit", type=int, default=40)
    h.add_argument("--quiet", type=int, default=800)
    h.set_defaults(func=cmd_hover)

    t = sub.add_parser("type", help="type text into an input and press Enter")
    t.add_argument("index", type=int, nargs="?")
    t.add_argument("value")
    t.add_argument("--text")
    t.add_argument("--selector")
    t.add_argument("--enter", action="store_true", default=True)
    t.add_argument("--quiet", type=int, default=1200)
    t.add_argument("--timeout", type=float, default=25)
    page_opts(t, chars=6000)
    t.set_defaults(func=cmd_type)

    e = sub.add_parser("eval", help="run JavaScript in the page")
    e.add_argument("js")
    e.add_argument("--await-promise", action="store_true")
    e.set_defaults(func=cmd_eval)

    pa = sub.add_parser("pages", help="list open pages")
    pa.set_defaults(func=cmd_pages)

    cl = sub.add_parser("close", help="close the browser session")
    cl.add_argument("--all", action="store_true")
    cl.set_defaults(func=cmd_close)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()