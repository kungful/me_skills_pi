#!/usr/bin/env python3
"""xgc.py - XGC (仙宫云 / xiangongyun.com) OpenAPI client.

Base URL : https://api.xiangongyun.com
Auth     : Authorization: Bearer <访问令牌>

Safety model
  * every command is READ-ONLY by default
  * any command that spends money or destroys data (deploy / destroy / shutdown / boot /
    recharge / saveimage) refuses to run without --yes, and prints the exact request first
  * --dry-run prints the request body without sending anything
  * the token is never printed, only a masked fingerprint
  * every write is appended to ~/.xgc_history.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.environ.get("XGC_API_BASE", "https://api.xiangongyun.com")
TOKEN_FILES = [os.path.expanduser(p) for p in
               ("~/.xgc_token", "~/.config/xgc/token", ".xgc_token")]
HISTORY = os.path.expanduser("~/.xgc_history.jsonl")
DOC_URL = "https://api-playground.xiangongyun.com/instance/3"

WRITE_CMDS = {"deploy", "destroy", "shutdown", "boot", "saveimage", "saveimage_destroy",
              "recharge", "image_destroy"}


def die(msg: str, code: int = 1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def token() -> str:
    t = (os.environ.get("XGC_TOKEN") or "").strip()
    if t:
        return t
    for p in TOKEN_FILES:
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                t = f.read().strip()
            if t:
                return t
    die("no access token found.\n"
        "  1. get it from https://www.xiangongyun.com/console/user/accesstoken\n"
        "  2. store it OUTSIDE the repo:   echo -n '<token>' > ~/.xgc_token\n"
        "  or export XGC_TOKEN=<token>   (never paste it into chat or commit it)")


def fingerprint(tok: str) -> str:
    return f"{tok[:4]}...{tok[-4:]}" if len(tok) > 10 else "***"


def api(path: str, method: str = "GET", body: dict | None = None, timeout: int = 40) -> dict:
    url = BASE + path if path.startswith("/") else path
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token())
    req.add_header("Accept", "application/json")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        die(f"HTTP {e.code} {method} {path}\n{raw[:500]}")
    except urllib.error.URLError as e:
        die(f"network error: {e.reason}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        die(f"non-JSON response from {url}:\n{raw[:400]}")


def ok(resp: dict) -> bool:
    if resp.get("success") is True:
        return True
    if resp.get("success") is False:
        return False
    return resp.get("code") in (0, 200, "0", "200")


def emit(resp: dict, cmd: str, args):
    """Print the API envelope, or the useful payload when it looks like a list/object."""
    if args.json:
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return
    payload = None
    for key in ("data", "result", "results", "list"):
        if isinstance(resp.get(key), (dict, list)):
            payload = resp[key]
            break
    if not ok(resp):
        print(f"API said failure: code={resp.get('code')} msg={resp.get('msg')}")
        if payload is not None:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        sys.exit(2)
    if payload is None:
        print(json.dumps(resp, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def guard(args, body: dict | None, what: str, spend: str | None = None):
    """Refuse to send a state-changing request without explicit --yes."""
    print(f"⚠️  {what}")
    if spend:
        print(f"   cost: {spend}")
    if body is not None:
        print("   request: " + json.dumps(body, ensure_ascii=False))
    if getattr(args, "dry_run", False):
        print("   --dry-run: nothing was sent.")
        sys.exit(0)
    if not getattr(args, "yes", False):
        print("\n   This changes your account and spends money. Re-run with --yes to send it,")
        print("   or --dry-run to only inspect the payload.")
        sys.exit(2)
    log_event(what, body)


def log_event(what: str, body):
    try:
        os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
        with open(HISTORY, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                                "action": what, "body": body}, ensure_ascii=False) + "\n")
    except OSError:
        pass


# ------------------------------------------------------------------ read-only

def cmd_whoami(args):
    emit(api("/open/whoami"), "whoami", args)


def cmd_balance(args):
    r = api("/open/balance")
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    data = r.get("data") or r
    bal = data.get("balance") if isinstance(data, dict) else None
    if bal is None:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(f"balance: {bal}")
        if bal <= 0:
            print("⚠️  balance is zero - a deploy would overdraw and the platform auto-destroys "
                  "the container when the account goes negative.", file=sys.stderr)


def _instances(args):
    r = api("/open/instances")
    data = r.get("data") or r.get("result") or []
    return data if isinstance(data, list) else [data]


def cmd_instances(args):
    rows = _instances(args)
    if args.running:
        rows = [i for i in rows if str(i.get("status", "")).lower()
                in ("running", "runninging", "运行中", "1", "true")]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        print("no instances (good - nothing is being billed)")
        return
    print(f"{'ID':<14}{'STATUS':<10}{'NAME':<16}{'GPU':<26}{'¥/h':<10}CREATED")
    for i in rows:
        gpu = f"{i.get('gpu_model','?')}x{i.get('gpu_used','?')}"
        print(f"{str(i.get('id','?'))[:12]:<14}{str(i.get('status','?'))[:9]:<10}"
              f"{str(i.get('name',''))[:15]:<16}{gpu[:25]:<26}"
              f"{str(i.get('price_per_hour','?'))[:9]:<10}{i.get('create_timestamp','?')}")
    running = [i for i in rows if str(i.get("status", "")).lower() in
               ("running", "运行中", "starting", "1", "true")]
    if running:
        print(f"\n⚠️  {len(running)} instance(s) are running and BILLING BY THE SECOND. "
              f"Destroy them when finished:  xgc.py destroy <id> --yes", file=sys.stderr)


def cmd_instance(args):
    emit(api(f"/open/instance/{args.id}"), "instance", args)


def cmd_images(args):
    emit(api("/open/images"), "images", args)


def cmd_image(args):
    emit(api(f"/open/image/{args.id}"), "image", args)


def cmd_token(args):
    t = token()
    print(f"token loaded: {fingerprint(t)}  (len={len(t)}, never printed in full)")
    r = api("/open/balance")
    print(f"auth check: {'OK' if ok(r) else 'FAILED - ' + str(r.get('msg'))}")
    sys.exit(0 if ok(r) else 2)


def _docs_html() -> str:
    """The docs page is client-rendered, so fall back to headless Chrome if plain
    HTTP returns no table. Reuses the web-browse skill's cdp.py when available."""
    req = urllib.request.Request(DOC_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        html = r.read().decode("utf-8", "replace")
    if html.count("<tr") >= 5:
        return html
    import glob
    hits = (glob.glob(os.path.expanduser("~/.pi/agent/skills/web-browse/scripts/cdp.py")) +
            glob.glob(os.path.expanduser("~/.agents/skills/web-browse/scripts/cdp.py")))
    if not hits:
        return html
    sys.path.insert(0, os.path.dirname(hits[0]))
    try:
        import cdp
        b = cdp.Browser("xgc-docs")
        b.start()
        try:
            sid = b.open(DOC_URL, wait=4)
            return b.html(sid)
        finally:
            b.cleanup()
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] headless render failed ({e}); using plain fetch\n")
        return html


def cmd_docs_images(args):
    """Scrape the public image table straight out of the API docs (needs no token)."""
    import re
    html = _docs_html()
    rows = []
    for tr in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", html):
        cells = [re.sub(r"<[^>]+>", "", c).strip()
                 for c in re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", tr)]
        if len(cells) == 2 and re.fullmatch(r"[0-9a-f-]{36}", cells[1]):
            rows.append(cells)
    if not rows:
        die("could not parse the 公共镜像列表 table (layout may have changed). Read it here: "
            + DOC_URL + "  - or use the web-browse skill: "
            "python ~/.pi/agent/skills/web-browse/scripts/browse.py --session x "
            "open '" + DOC_URL + "' --bare --drop \"//div[contains(@class,'min-w-[300px]')]\"")
    if args.json:
        print(json.dumps([{"name": n, "id": i} for n, i in rows], ensure_ascii=False, indent=2))
        return
    print(f"{len(rows)} public image(s) from {DOC_URL}")
    for n, i in rows:
        print(f"  {n:<52}{i}")


def cmd_url(args):
    iid = args.id
    port = args.port
    print(f"public   https://{iid}-{port}.container.x-gpu.com")
    print(f"in-container http://{iid}-{port}.c.x-gpu.com")
    print(f"loopback http://127.0.0.1:{port}   (from inside the container)")
    if not args.json:
        print("\nComfyUI 8188 | SD WebUI 7860 | Jupyter 8888 | SSH 22 "
              "(confirm with: xgc.py instance <id> --json)")


# ------------------------------------------------------------------ writes

def cmd_deploy(args):
    body = {
        "gpu_model": args.gpu,
        "gpu_count": args.count,
        "data_center_id": args.datacenter,
        "image": args.image,
        "image_type": args.image_type,
    }
    for flag, key in (("ssh_key", "ssh_key"), ("name", "name"),
                      ("disk_size", "system_disk_expand_size")):
        v = getattr(args, flag)
        if v not in (None, False):
            body[key] = v
    if args.storage:
        body["storage"] = True
        body["storage_mount_path"] = args.storage_path
    if args.disk_size:
        body["system_disk_expand"] = True
    guard(args, body,
          what=f"DEPLOY {args.count}x {args.gpu} using image {args.image} ({args.image_type})",
          spend=f"billed per second from the moment it reaches 运行中, until destroyed. "
                f"GPU rate is whatever the console shows for {args.gpu} (check first with "
                f"'xgc.py instances' after the first run, or the site's pricing page).")
    emit(api("/open/instance/deploy", "POST", body), "deploy", args)


def _life(args, path: str, what: str):
    body = {"id": args.id}
    guard(args, body, what=what)
    emit(api(path, "POST", body), what, args)


def cmd_destroy(args):
    _life(args, "/open/instance/destroy", f"DESTROY instance {args.id} (data on it is gone)")


def cmd_shutdown(args):
    if args.and_destroy:
        _life(args, "/open/instance/shutdown_destroy", f"SHUTDOWN+DESTROY {args.id}")
    elif args.release_gpu:
        _life(args, "/open/instance/shutdown_release_gpu",
              f"SHUTDOWN {args.id} and release the GPU (stops GPU billing; the system disk "
              f"still bills ¥0.00003/GB/h until destroyed)")
    else:
        _life(args, "/open/instance/shutdown", f"SHUTDOWN {args.id}, keeping the GPU (keeps billing)")


def cmd_boot(args):
    _life(args, "/open/instance/boot", f"BOOT instance {args.id} (starts billing again)")


def cmd_saveimage(args):
    body = {"id": args.id, "name": args.name, "description": args.description or ""}
    if args.image_type:
        body["image_type"] = args.image_type
    guard(args, body, what=f"SAVE instance {args.id} as image {args.name!r}")
    emit(api("/open/instance/saveimage", "POST", body), "saveimage", args)


def cmd_recharge(args):
    guard(args, {"amount": args.amount, "payment": args.payment},
          what=f"CREATE A RECHARGE ORDER for ¥{args.amount} via {args.payment}",
          spend="real money; the order must then be paid.")
    emit(api("/open/recharge/order", "POST",
             {"amount": args.amount, "payment": args.payment}), "recharge", args)


def cmd_history(args):
    if not os.path.exists(HISTORY):
        print("no local history yet")
        return
    with open(HISTORY, encoding="utf-8") as f:
        for line in f:
            print(line.rstrip())


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(prog="xgc.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="always print raw JSON")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def wr(p):
        p.add_argument("--yes", action="store_true", help="actually send the request")
        p.add_argument("--dry-run", action="store_true", help="print the payload, send nothing")

    sub.add_parser("whoami", help="GET /open/whoami (read-only)").set_defaults(func=cmd_whoami)
    sub.add_parser("balance", help="GET /open/balance (read-only)").set_defaults(func=cmd_balance)
    sub.add_parser("token", help="check that a token is loaded and valid").set_defaults(func=cmd_token)

    i = sub.add_parser("instances", help="GET /open/instances (read-only)")
    i.add_argument("--running", action="store_true", help="only running/billing ones")
    i.set_defaults(func=cmd_instances)

    d = sub.add_parser("instance", help="GET /open/instance/{id} (read-only)")
    d.add_argument("id")
    d.set_defaults(func=cmd_instance)

    sub.add_parser("images", help="GET /open/images (read-only)").set_defaults(func=cmd_images)
    im = sub.add_parser("image", help="GET /open/image/{id} (read-only)")
    im.add_argument("id")
    im.set_defaults(func=cmd_image)

    doc = sub.add_parser("docs-images", help="public image table from the API docs (no token)")
    doc.set_defaults(func=cmd_docs_images)

    u = sub.add_parser("url", help="print the public/in-container URLs for an instance+port")
    u.add_argument("id")
    u.add_argument("port", type=int, nargs="?", default=8188)
    u.set_defaults(func=cmd_url)

    p = sub.add_parser("deploy", help="POST /open/instance/deploy  (SPENDS MONEY)")
    p.add_argument("--gpu", default="NVIDIA GeForce RTX 4090",
                   help="RTX 4090 | RTX 4090 D | RTX 4090 D 48G")
    p.add_argument("--count", type=int, default=1)
    p.add_argument("--image", required=True, help="image id - see `docs-images`")
    p.add_argument("--image-type", default="public", choices=["public", "community", "private"])
    p.add_argument("--datacenter", type=int, default=1)
    p.add_argument("--storage", action="store_true")
    p.add_argument("--storage-path", default="/root/cloud")
    p.add_argument("--ssh-key")
    p.add_argument("--name")
    p.add_argument("--disk-size", type=int, help="system disk expand size in bytes")
    wr(p)
    p.set_defaults(func=cmd_deploy)

    de = sub.add_parser("destroy", help="POST /open/instance/destroy  (DESTRUCTIVE)")
    de.add_argument("id")
    wr(de)
    de.set_defaults(func=cmd_destroy)

    sh = sub.add_parser("shutdown", help="POST /open/instance/shutdown[_release_gpu|_destroy]")
    sh.add_argument("id")
    sh.add_argument("--release-gpu", action="store_true")
    sh.add_argument("--and-destroy", action="store_true")
    wr(sh)
    sh.set_defaults(func=cmd_shutdown)

    bo = sub.add_parser("boot", help="POST /open/instance/boot")
    bo.add_argument("id")
    wr(bo)
    bo.set_defaults(func=cmd_boot)

    sv = sub.add_parser("saveimage", help="POST /open/instance/saveimage")
    sv.add_argument("id")
    sv.add_argument("--name", required=True)
    sv.add_argument("--description")
    sv.add_argument("--image-type")
    wr(sv)
    sv.set_defaults(func=cmd_saveimage)

    rc = sub.add_parser("recharge", help="POST /open/recharge/order  (SPENDS MONEY)")
    rc.add_argument("amount", type=float)
    rc.add_argument("payment", choices=["alipay", "wechat"])
    wr(rc)
    rc.set_defaults(func=cmd_recharge)

    sub.add_parser("history", help="local log of every write this tool sent").set_defaults(
        func=cmd_history)

    args = ap.parse_args()
    if args.cmd in WRITE_CMDS and args.cmd != "history":
        pass  # guard() enforces --yes inside the command
    args.func(args)


if __name__ == "__main__":
    main()