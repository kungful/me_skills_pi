#!/usr/bin/env python3
"""Tiny remote helper for the FlashVSR+ build: paramiko password login on the XGC box.

usage:
  python xr.py run "cmd"            # run shell command, print stdout/stderr
  python xr.py runbg "cmd" logname  # run detached with nohup, log to /root/logs/<name>.log
  python xr.py log <name> [n]       # tail log
  python xr.py put <local> <remote>
  python xr.py get <remote> <local>
"""
import json, os, subprocess, sys, time
import urllib.request

API = "https://api.xiangongyun.com"
INST = os.environ.get("XGC_INST", "15nfp4tydm76nnt0")


def token():
    p = os.path.expanduser("~/.xgc_token")
    return open(p).read().strip()


def info():
    req = urllib.request.Request(API + "/open/instances",
                                 headers={"Authorization": "Bearer " + token()})
    d = json.loads(urllib.request.urlopen(req, timeout=60).read())
    for i in d["data"]["list"]:
        if i.get("id") == INST:
            return i
    raise SystemExit("instance %s not found" % INST)


_c = None


def conn():
    global _c
    if _c is None:
        import paramiko
        i = info()
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(i["ssh_domain"], port=int(i["ssh_port"]),
                  username=i.get("ssh_user") or "root", password=i["password"],
                  look_for_keys=False, allow_agent=False, timeout=25)
        c.get_transport().set_keepalive(30)
        _c = c
    return _c


def run(cmd, timeout=3600):
    c = conn()
    _in, out, err = c.exec_command(cmd, timeout=timeout, get_pty=False)
    o = out.read().decode("utf-8", "replace")
    e = err.read().decode("utf-8", "replace")
    rc = out.channel.recv_exit_status()
    return rc, o, e


def sftp():
    return conn().open_sftp()


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    if a[0] == "run":
        rc, o, e = run(a[1], int(a[2]) if len(a) > 2 else 3600)
        sys.stdout.write(o)
        if e.strip():
            sys.stderr.write("\n--- stderr ---\n" + e)
        raise SystemExit(rc)
    if a[0] == "runbg":
        # a[1] = script path on remote, a[2] = log name
        cmd = ("mkdir -p /root/logs && cd /root && "
               "nohup setsid bash %s > /root/logs/%s.log 2>&1 < /dev/null & echo started" % (a[1], a[2]))
        print(run(cmd)[1])
        raise SystemExit(0)
    if a[0] == "log":
        n = int(a[2]) if len(a) > 2 else 60
        print(run("tail -n %d /root/logs/%s.log" % (n, a[1]))[1])
        raise SystemExit(0)
    if a[0] == "put":
        sftp().put(a[1], a[2])
        print("ok", a[2])
        raise SystemExit(0)
    if a[0] == "get":
        sftp().get(a[1], a[2])
        print("ok", a[2])
        raise SystemExit(0)
    raise SystemExit(__doc__)
