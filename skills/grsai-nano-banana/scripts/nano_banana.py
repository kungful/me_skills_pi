#!/usr/bin/env python3
"""grsai Nano Banana image client (legacy /v1/draw/nano-banana API).

Usage:
  python nano_banana.py gen -p "a cute cat" --model nano-banana-fast --out cat.png
  python nano_banana.py gen -p prompt.txt -r ref_view.png ref_massing.png \
      --model nano-banana-pro-4k-vip --size 4K --aspect 16:9 --out house.png
  python nano_banana.py gen -p prompt.txt -r https://a.png --model nano-banana-2 --aspect 8:1 --out strip.png
  python nano_banana.py poll --id 1f0e3dad-... --out out.png
  python nano_banana.py models

Key resolution order: --key, $GRSAI_API_KEY, ./.grsai_key, %USERPROFILE%/.grsai_key
"""
import argparse
import base64
import json
import mimetypes
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

HOSTS = {
    "domestic": "https://grsai.dakka.com.cn",
    "overseas": "https://grsaiapi.com",
}

# model -> documented imageSize options (advisory: the API may accept others).
# price = CNY per call, credits = grsai points (both refunded on failure / violation).
MODELS = {
    "nano-banana-2-lite": {"sizes": ["1K"], "price": 0.022, "credits": 440,
                           "note": "gemini-3.1-flash-lite-image; cheapest tier"},
    "nano-banana-fast": {"sizes": ["1K"], "price": 0.022, "credits": 440,
                         "note": "promo tier, strong editing; nano-banana = same model with image-format wrapper"},
    "nano-banana": {"sizes": ["1K"], "price": None, "credits": None, "note": "base tier"},
    "nano-banana-2": {"sizes": ["1K", "2K", "4K"], "price": 0.06, "credits": 1200,
                      "note": "gemini-3.1-flash-image-preview; same price at all sizes"},
    "nano-banana-2-cl": {"sizes": ["1K"], "price": None, "credits": None, "note": "nano-banana-2, 1K only"},
    "nano-banana-2-2k-cl": {"sizes": ["2K"], "price": None, "credits": None, "note": "nano-banana-2, 2K only"},
    "nano-banana-2-4k-cl": {"sizes": ["4K"], "price": None, "credits": None, "note": "nano-banana-2, 4K only"},
    "nano-banana-pro": {"sizes": ["1K", "2K", "4K"], "price": 0.09, "credits": 1800,
                        "note": "gemini-3-pro-image-preview; same price at all sizes, stable"},
    "nano-banana-pro-vt": {"sizes": ["1K", "2K", "4K"], "price": None, "credits": None, "note": ""},
    "nano-banana-pro-cl": {"sizes": ["1K"], "price": None, "credits": None, "note": "nano-banana-pro, 1K only"},
    "nano-banana-pro-vip": {"sizes": ["1K", "2K"], "price": None, "credits": None, "note": "nano-banana-pro, no 4K"},
    "nano-banana-pro-4k-vip": {"sizes": ["4K"], "price": None, "credits": None, "note": "nano-banana-pro, 4K only"},
}

RATIOS = ["auto", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "5:4", "4:5", "21:9"]
EXTREME_RATIOS = ["1:4", "4:1", "1:8", "8:1"]
EXTREME_MODELS = [
    "nano-banana-2",
    "nano-banana-2-cl",
    "nano-banana-2-2k-cl",
    "nano-banana-2-4k-cl",
]


def load_key(explicit=None):
    if explicit:
        return explicit
    env = os.environ.get("GRSAI_API_KEY")
    if env:
        return env.strip()
    for p in (pathlib.Path("./.grsai_key"), pathlib.Path.home() / ".grsai_key"):
        if p.is_file():
            return p.read_text(encoding="utf-8").strip()
    sys.exit("no API key: pass --key, set GRSAI_API_KEY, or write .grsai_key")


def resolve_host(host):
    return HOSTS.get(host, host)


def post(host, path, payload, key, timeout=900):
    req = urllib.request.Request(
        host.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
    )
    try:
        raw = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:600]}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(f"non-JSON response: {raw[:600]}")


def to_ref(ref):
    """http(s) URL passes through; local file becomes a data URI."""
    if ref.startswith(("http://", "https://", "data:")):
        return ref
    p = pathlib.Path(ref)
    if not p.is_file():
        sys.exit(f"reference not found: {ref}")
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def read_prompt(value):
    p = pathlib.Path(value)
    if "\n" not in value and len(value) < 260 and p.is_file():
        return p.read_text(encoding="utf-8").strip()
    return value


def download(url, out):
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    data = urllib.request.urlopen(url, timeout=300).read()
    out.write_bytes(data)
    out.with_suffix(out.suffix + ".url.txt").write_text(url, encoding="utf-8")
    return out, len(data)


def poll(host, tid, key, interval, timeout, quiet=False):
    t0 = time.time()
    last = None
    while True:
        r = post(host, "/v1/draw/result", {"id": tid}, key)
        if r.get("code") == -22:
            sys.exit(f"task not found (code -22): {tid}")
        d = r.get("data") or {}
        if not quiet:
            line = f"[poll] {d.get('status')} {d.get('progress')}%"
            if line != last:
                print(line, flush=True)
                last = line
        if d.get("status") in ("succeeded", "failed"):
            return d
        if timeout and time.time() - t0 > timeout:
            sys.exit(f"timeout after {timeout}s (task {tid} still running; resume with: nano_banana.py poll --id {tid})")
        time.sleep(interval)


def cmd_gen(a):
    model = a.model
    spec = MODELS.get(model)
    if spec is None:
        sys.exit(f"unknown model {model}; known: {', '.join(MODELS)}")
    if a.aspect in EXTREME_RATIOS and model not in EXTREME_MODELS:
        sys.exit(f"error: ratio {a.aspect} is only supported by: {', '.join(EXTREME_MODELS)}")
    key = load_key(a.key)
    host = resolve_host(a.host)
    size = a.size or spec["sizes"][0]
    if size not in spec["sizes"]:
        msg = f"note: {model} documents imageSize {spec['sizes']}, sending '{size}' anyway"
        if a.strict_size:
            sys.exit(msg.replace("note: ", "error: "))
        print(msg, file=sys.stderr, flush=True)

    payload = {
        "model": model,
        "prompt": read_prompt(a.prompt),
        "aspectRatio": a.aspect,
        "imageSize": size,
        "webHook": "-1",  # immediate id, then poll /v1/draw/result
        "shutProgress": bool(a.shut_progress),
    }
    if a.refs:
        payload["urls"] = [to_ref(r) for r in a.refs]

    attempt = 0
    while True:
        attempt += 1
        r = post(host, "/v1/draw/nano-banana", payload, key)
        if r.get("code") != 0:
            sys.exit(f"submit failed: {json.dumps(r, ensure_ascii=False)[:500]}")
        tid = r["data"]["id"]
        print(f"[submit] model={model} size={size} aspect={a.aspect} refs={len(a.refs or [])} id={tid}", flush=True)
        d = poll(host, tid, key, a.interval, a.timeout, quiet=a.quiet)
        if d.get("status") == "succeeded" and d.get("results"):
            print(f"[result] {d['results'][0]['url']}", flush=True)
            if a.out:
                out, n = download(d["results"][0]["url"], a.out)
                print(f"[saved] {out} ({n/1024:.0f} KB)")
            return 0
        reason = d.get("failure_reason")
        print(f"[failed] reason={reason} error={d.get('error')}", flush=True)
        if reason == "error" and attempt <= a.retries:
            print(f"[retry] attempt {attempt}/{a.retries + 1}", flush=True)
            time.sleep(3)
            continue
        return 2


def cmd_poll(a):
    key = load_key(a.key)
    host = resolve_host(a.host)
    d = poll(host, a.id, key, a.interval, a.timeout, quiet=a.quiet)
    print(json.dumps(d, ensure_ascii=False)[:1200])
    if d.get("status") == "succeeded" and d.get("results"):
        print("[result]", d["results"][0]["url"])
        if a.out:
            out, n = download(d["results"][0]["url"], a.out)
            print(f"[saved] {out} ({n/1024:.0f} KB)")
    return 0 if d.get("status") == "succeeded" else 2


def cmd_models(_a):
    print(f"{'model':24s} {'imageSize':12s} {'CNY/call':>8s} {'credits':>8s}  extraRatios  note")
    for m, spec in MODELS.items():
        price = f"{spec['price']:.3f}" if spec.get("price") else "-"
        creds = str(spec["credits"]) if spec.get("credits") else "-"
        print(f"{m:24s} {','.join(spec['sizes']):12s} {price:>8s} {creds:>8s}  "
              f"{'yes' if m in EXTREME_MODELS else 'no':12s}  {spec.get('note', '')}")
    print("\naspectRatio:", ", ".join(RATIOS))
    print("extra (nano-banana-2* only):", ", ".join(EXTREME_RATIOS))
    return 0


def main():
    ap = argparse.ArgumentParser(description="grsai Nano Banana image client (legacy API)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--key", help="API key (else env/.grsai_key)")
        sp.add_argument("--host", default="domestic", help="domestic | overseas | full URL")
        sp.add_argument("--interval", type=float, default=5, help="poll seconds (default 5)")
        sp.add_argument("--timeout", type=float, default=900, help="overall seconds (0=wait forever)")
        sp.add_argument("--quiet", action="store_true")

    g = sub.add_parser("gen", help="submit and wait")
    common(g)
    g.add_argument("-p", "--prompt", required=True, help="prompt text or path to a .txt")
    g.add_argument("-r", "--refs", nargs="*", help="reference images: local paths or URLs")
    g.add_argument("--model", default="nano-banana-fast", choices=list(MODELS))
    g.add_argument("--size", choices=["1K", "2K", "4K"], help="default: model's first documented size")
    g.add_argument("--aspect", default="auto")
    g.add_argument("--shut-progress", action="store_true", help="suppress progress frames")
    g.add_argument("--out", default="result.png")
    g.add_argument("--retries", type=int, default=2, help="retry on failure_reason=error")
    g.add_argument("--strict-size", action="store_true", help="fail instead of warning on undocumented imageSize")
    g.set_defaults(func=cmd_gen)

    pl = sub.add_parser("poll", help="resume an existing task id")
    common(pl)
    pl.add_argument("--id", required=True)
    pl.add_argument("--out")
    pl.set_defaults(func=cmd_poll)

    m = sub.add_parser("models", help="list models/sizes/ratios")
    m.set_defaults(func=cmd_models)

    a = ap.parse_args()
    sys.exit(a.func(a) or 0)


if __name__ == "__main__":
    main()
