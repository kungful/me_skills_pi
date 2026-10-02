#!/usr/bin/env python3
"""grsai image generation client (gpt-image-2 / 2.5 family).

Usage:
  # basic
  python grsai.py gen -p "a cat" --out cat.png
  # with prompt file + local reference images (auto -> base64 data URI)
  python grsai.py gen -p prompt.txt -r view.png massing.png --model gpt-image-2.5 --quality high --aspect 1536x1024 --out house.png
  # remote references
  python grsai.py gen -p prompt.txt -r https://a.png https://b.png --out out.png
  # poll an existing task / re-download (URLs live ~2h)
  python grsai.py poll --id 11-xxxx --out out.png
  # list models
  python grsai.py models

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

# model -> documented options. "qualities" is advisory only: the API silently accepts
# undocumented values (verified: gpt-image-2.5 with quality=high returns a high-detail image),
# so a mismatch warns instead of failing unless --strict-quality is passed.
MODELS = {
    "gpt-image-2": {"qualities": ["auto"], "background": False},
    "gpt-image-2-vip": {"qualities": ["medium"], "background": True},
    "gpt-image-2.5": {"qualities": ["auto"], "background": False},
    "gpt-image-2.5-flare": {"qualities": ["low", "medium", "high"], "background": True},
    "gpt-image-2.5-sunburst": {"qualities": ["low", "medium", "high", "xhigh", "max"], "background": True},
}

VERIFIED_ASPECTS = ["1024x1024", "1536x1024", "1024x1536"]


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


def cmd_gen(a):
    key = load_key(a.key)
    host = resolve_host(a.host)
    model = a.model
    spec = MODELS.get(model)
    if spec is None:
        sys.exit(f"unknown model {model}; known: {', '.join(MODELS)}")
    quality = a.quality or spec["qualities"][0]
    if quality not in spec["qualities"]:
        msg = f"note: {model} documents quality {spec['qualities']}, sending '{quality}' anyway (API tolerates it)"
        if a.strict_quality:
            sys.exit(msg.replace("note: ", "error: "))
        print(msg, file=sys.stderr, flush=True)
    if a.background and not spec["background"]:
        msg = f"note: {model} does not document background support; sending '{a.background}' anyway"
        if a.strict_quality:
            sys.exit(msg.replace("note: ", "error: "))
        print(msg, file=sys.stderr, flush=True)

    payload = {
        "model": model,
        "prompt": read_prompt(a.prompt),
        "aspectRatio": a.aspect,
        "quality": quality,
        "webHook": "-1",  # immediate id, then poll /v1/draw/result
    }
    if a.refs:
        payload["urls"] = [to_ref(r) for r in a.refs]
    if a.background:
        payload["background"] = a.background
    if a.mask:
        payload["mask"] = to_ref(a.mask)

    attempt = 0
    while True:
        attempt += 1
        r = post(host, "/v1/draw/completions", payload, key)
        if r.get("code") != 0:
            sys.exit(f"submit failed: {json.dumps(r)[:500]}")
        tid = r["data"]["id"]
        print(f"[submit] model={model} quality={quality} aspect={a.aspect} refs={len(a.refs or [])} id={tid}", flush=True)
        d = poll(host, tid, key, a.interval, a.timeout, quiet=a.quiet)
        status = d.get("status")
        if status == "succeeded" and d.get("results"):
            url = d["results"][0]["url"]
            print(f"[result] {url}", flush=True)
            if a.out:
                out, n = download(url, a.out)
                print(f"[saved] {out} ({n/1024:.0f} KB)")
            return 0
        reason = d.get("failure_reason")
        print(f"[failed] reason={reason} error={d.get('error')}", flush=True)
        if reason == "error" and attempt <= a.retries:
            print(f"[retry] attempt {attempt}/{a.retries + 1}", flush=True)
            time.sleep(3)
            continue
        return 2


def poll(host, tid, key, interval, timeout, quiet=False):
    t0 = time.time()
    last = None
    while True:
        d = (post(host, "/v1/draw/result", {"id": tid}, key).get("data") or {})
        if not quiet:
            line = f"[poll] {d.get('status')} {d.get('progress')}%"
            if line != last:
                print(line, flush=True)
                last = line
        if d.get("status") in ("succeeded", "failed"):
            return d
        if timeout and time.time() - t0 > timeout:
            sys.exit(f"timeout after {timeout}s (task {tid} still running; resume with: grsai.py poll --id {tid})")
        time.sleep(interval)


def cmd_poll(a):
    key = load_key(a.key)
    host = resolve_host(a.host)
    d = poll(host, a.id, key, a.interval, a.timeout, quiet=a.quiet)
    print(json.dumps(d, ensure_ascii=False)[:1200])
    if d.get("status") == "succeeded" and d.get("results"):
        url = d["results"][0]["url"]
        print("[result]", url)
        if a.out:
            out, n = download(url, a.out)
            print(f"[saved] {out} ({n/1024:.0f} KB)")
    return 0 if d.get("status") == "succeeded" else 2


def cmd_models(_a):
    for m, spec in MODELS.items():
        print(f"{m:26s} quality={','.join(spec['qualities'])}  background={spec['background']}")
    print("\nverified aspectRatio:", ", ".join(VERIFIED_ASPECTS))
    return 0


def main():
    ap = argparse.ArgumentParser(description="grsai image client (gpt-image-2 / 2.5)")
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
    g.add_argument("--model", default="gpt-image-2.5", choices=list(MODELS))
    g.add_argument("--quality", help="default: model's only/first option")
    g.add_argument("--aspect", default="1536x1024")
    g.add_argument("--background", help="transparent (only 2-vip / 2.5-flare / 2.5-sunburst)")
    g.add_argument("--mask", help="mask image path or URL")
    g.add_argument("--out", default="result.png")
    g.add_argument("--retries", type=int, default=2, help="retry on failure_reason=error")
    g.add_argument("--strict-quality", action="store_true", help="fail instead of warning on undocumented quality/background")
    g.set_defaults(func=cmd_gen)

    pl = sub.add_parser("poll", help="resume an existing task id")
    common(pl)
    pl.add_argument("--id", required=True)
    pl.add_argument("--out")
    pl.set_defaults(func=cmd_poll)

    m = sub.add_parser("models", help="list models/qualities")
    m.set_defaults(func=cmd_models)

    a = ap.parse_args()
    sys.exit(a.func(a) or 0)


if __name__ == "__main__":
    main()
