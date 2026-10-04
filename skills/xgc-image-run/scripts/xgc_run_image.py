#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仙宫云跑图一条龙：开机 -> 出图 -> 拉回本地 -> 立刻销毁。

省钱设计（这是本脚本存在的全部理由）：
  1. 开工前先查有没有实例在跑。在跑就是在烧钱，除非显式 --allow-parallel 否则直接退出。
  2. 出图并下载完成的下一行代码就是销毁，不是"稍后再说"。
  3. try/finally 兜底：出图失败、下载失败、Ctrl-C、异常退出，都会走到销毁。
     想故意留着机器调试才用 --keep。
  4. 结束时打印真实花费 = 在线秒数 x 单价，让你对"省钱"有数字概念。

所有花钱/破坏性动作都转交给 xgc-api 的 xgc.py 执行，那里面有 --yes 双重确认和
~/.xgc_history.jsonl 审计日志。本脚本不直接调花钱接口。

镜像永不被删除（Hard Rule 0）。

用法
----
  python xgc_run_image.py --status                      # 只看看现在有没有在烧钱
  python xgc_run_image.py --prompt "..." --dry-run      # 打印将要发送的 payload
  python xgc_run_image.py --prompt "..." --yes          # 真跑
  python xgc_run_image.py --prompt "..." --size 1536x1024 --steps 8 --yes
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HOME = os.path.expanduser("~")
XGC_PY = os.path.join(HOME, ".pi", "agent", "skills", "xgc-api", "scripts", "xgc.py")
TOKEN_FILES = [os.path.join(HOME, ".xgc_token"),
               os.path.join(HOME, ".config", "xgc", "token")]
DEFAULT_TOKEN_FILE = os.path.join(HOME, ".xgc_token")
DEFAULTS_FILE = os.path.join(HOME, ".xgc_defaults.json")
API = "https://api.xiangongyun.com"

DEFAULTS = {
    "default_image": "f0cbf8c7-96c7-4010-a645-1898927c33ea",
    "default_gpu": "NVIDIA GeForce RTX 4090 D",
    "ssh_private_key": "~/.ssh/piwebui.pem",
    "workflow_txt2img": "/root/ComfyUI/user/default/workflows/Krea2_Turbo_文生图.json",
    "submit_script": "",
    "comfy_port": 8188,
}

SENSITIVE = {"password", "ssh_port", "jupyter_token", "xgcos_token", "xgcos_url", "jupyter_url"}


# --------------------------------------------------------------------------- 基础

def die(msg, code=1):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(code)


def load_defaults():
    d = dict(DEFAULTS)
    if os.path.exists(DEFAULTS_FILE):
        try:
            with open(DEFAULTS_FILE, encoding="utf-8") as f:
                d.update(json.load(f))
        except Exception as e:
            print("warning: 读不了 %s (%s)，用内置默认值" % (DEFAULTS_FILE, e), file=sys.stderr)
    return d


def load_token():
    t = (os.environ.get("XGC_TOKEN") or "").strip()
    if t:
        return t
    for p in TOKEN_FILES:
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                t = f.read().strip()
            if t:
                return t
    die("没找到访问令牌。\n"
        "  echo -n '<访问令牌>' > ~/.xgc_token     # 从控制台 accesstoken 页拿")


def api(path, method="GET", body=None):
    req = urllib.request.Request(
        API + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + load_token(),
                 "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        die("HTTP %s from %s\n%s" % (e.code, path, e.read().decode("utf-8", "replace")[:2000]))


def scrub(o):
    if isinstance(o, dict):
        return {k: ("<hidden>" if k in SENSITIVE else scrub(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [scrub(i) for i in o]
    return o


def instances():
    d = api("/open/instances")
    data = d.get("data") or {}
    return data.get("list") if isinstance(data, dict) else (data or [])


def balance():
    try:
        return float((api("/open/balance").get("data") or {}).get("balance") or 0)
    except Exception:
        return None


def xgc(*args):
    """把所有写操作转交给 xgc.py（它自带 --yes 确认与审计日志）。"""
    cmd = [sys.executable, XGC_PY] + [str(a) for a in args]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    try:
        j = json.loads(out[out.index("{"):out.rindex("}") + 1])
    except Exception:
        j = None
    return p.returncode, out.strip(), j


# --------------------------------------------------------------------------- 远端

class Remote:
    """通过 OpenSSH 客户端执行远端命令；密钥走不通时自动回退到容器密码(paramiko)。"""

    def __init__(self, host, port, user, keyfile, password):
        self.host, self.port, self.user = host, port, user
        self.keyfile, self.password = keyfile, password
        self.mode = "key"
        self._pk = None
        self.base = [
            "ssh", "-i", keyfile, "-p", str(port),
            "-o", "IdentitiesOnly=yes",
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ConnectTimeout=15",
            "-o", "LogLevel=ERROR",
            "%s@%s" % (user, host),
        ]

    # ---- paramiko 回退
    def _paramiko(self):
        if self._pk is None:
            try:
                import paramiko
            except ImportError:
                die("密钥登录失败，且没装 paramiko 不能回退到密码登录。\n"
                    "  pip install paramiko")
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(self.host, port=self.port, username=self.user,
                      password=self.password, look_for_keys=False, allow_agent=False, timeout=20)
            self._pk = c
        return self._pk

    def _via_paramiko(self, cmd, timeout):
        c = self._paramiko()
        _in, out, err = c.exec_command(cmd, timeout=timeout)
        o = out.read().decode("utf-8", "replace")
        e = err.read().decode("utf-8", "replace")
        return 0, o, e

    # ---- 统一入口
    def run(self, cmd=None, stdin=None, timeout=180, check=True):
        """stdin 不为空时把内容喂给远端 python3 -（绕开一切 shell 转义地狱）。"""
        if self.mode == "password":
            if stdin is not None:
                # 密码模式改用 base64 传脚本，同样避开引号问题
                b64 = base64.b64encode(stdin.encode("utf-8")).decode()
                remote_cmd = "echo %s | base64 -d | python3 -" % b64
            else:
                remote_cmd = cmd
            rc, o, e = self._via_paramiko(remote_cmd, timeout)
            if check and rc != 0:
                raise RuntimeError("remote failed rc=%s\n%s%s" % (rc, o, e))
            return o

        if stdin is not None:
            argv = self.base + ["python3", "-"]
            payload = stdin.encode("utf-8")
        else:
            argv = self.base + [cmd]
            payload = None
        p = subprocess.run(argv, input=payload, capture_output=True, timeout=timeout)
        o = p.stdout.decode("utf-8", "replace")
        e = p.stderr.decode("utf-8", "replace")

        if p.returncode == 255 and ("Permission denied" in e or "no such identity" in e
                                    or "Permission denied" in o):
            if self.mode == "key":
                self.mode = "password"
                print("  (密钥登录不通，回退到容器密码登录)")
                return self.run(cmd=cmd, stdin=stdin, timeout=timeout, check=check)
        if check and p.returncode != 0:
            raise RuntimeError("remote failed rc=%s\n%s%s" % (p.returncode, o, e))
        return o

    def wait_ready(self, timeout=300):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                out = self.run("echo READY", timeout=25, check=False)
                if "READY" in out:
                    return True
            except Exception:
                pass
            time.sleep(5)
        return False


# --------------------------------------------------------------------------- 远端出图脚本

REMOTE_PY = r'''
import base64, json, os, sys, time, uuid, urllib.request

CFG = json.loads(base64.b64decode("__CFG_B64__").decode("utf-8"))
HOST = "http://127.0.0.1:8188"


def get(path):
    return json.loads(urllib.request.urlopen(HOST + path, timeout=60).read())


def post(path, data):
    req = urllib.request.Request(HOST + path, data=json.dumps(data).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError("HTTP %s\n%s" % (e.code, e.read().decode("utf-8", "replace")[:3000]))


# UI 工作流 -> API 格式。widgets_values 的位置映射在下面这张表里。
WIDGETS = {
    "UNETLoader":      lambda i, w: {"unet_name": w[0], "weight_dtype": w[1]},
    "CLIPLoader":      lambda i, w: {"clip_name": w[0], "type": w[1], "device": w[2]},
    "VAELoader":       lambda i, w: {"vae_name": w[0]},
    "CLIPTextEncode":  lambda i, w: {"text": w[0]},
    "ConditioningZeroOut": lambda i, w: {},
    "ReferenceLatent": lambda i, w: {},
    "VAEEncode":       lambda i, w: {},
    "LoadImage":       lambda i, w: {"image": w[0]},
    "FluxKontextMultiReferenceLatentMethod": lambda i, w: {"reference_latents_method": w[1]},
    "EmptyLatentImage": lambda i, w: {"width": w[0], "height": w[1], "batch_size": w[2]},
    "KSampler":        lambda i, w: {"seed": w[0], "steps": w[2], "cfg": w[3],
                                     "sampler_name": w[4], "scheduler": w[5], "denoise": w[6]},
    "VAEDecode":       lambda i, w: {},
    "SaveImage":       lambda i, w: {"filename_prefix": w[0]},
}
SKIP = ("Note", "Reroute", "PrimitiveNode", "Bookmark")


def ui_to_api(wf):
    link_src = {}
    for l in wf.get("links", []):
        if isinstance(l, list) and len(l) >= 5:
            link_src[l[0]] = (l[1], l[2])
    prompt = {}
    for n in wf["nodes"]:
        t = n.get("type")
        if not t or t.endswith(SKIP) or t == "MarkdownNote":
            continue
        inputs = {}
        for inp in n.get("inputs") or []:
            lk = inp.get("link")
            if lk is not None and lk in link_src:
                src = link_src[lk]
                inputs[inp["name"]] = [str(src[0]), src[1]]
        wv = n.get("widgets_values") or []
        fn = WIDGETS.get(t)
        if fn:
            try:
                inputs.update(fn(inputs, wv))
            except Exception:
                pass
        prompt[str(n["id"])] = {"class_type": t, "inputs": inputs}
    return prompt


def main():
    wf = json.load(open(CFG["workflow"], encoding="utf-8"))
    n_text = n_size = n_save = n_sampler = 0
    for n in wf["nodes"]:
        t = n.get("type")
        if t == "CLIPTextEncode":
            n["widgets_values"] = [CFG["prompt"]]
            n_text += 1
        elif t == "EmptyLatentImage":
            n["widgets_values"] = [CFG["width"], CFG["height"], CFG["batch"]]
            n_size += 1
        elif t == "SaveImage":
            n["widgets_values"] = [CFG["prefix"]]
            n_save += 1
        elif t == "KSampler":
            wv = list(n.get("widgets_values") or [])
            while len(wv) < 7:
                wv.append("")
            if CFG.get("seed") is not None:
                wv[0] = CFG["seed"]
            wv[2], wv[3] = CFG["steps"], CFG["cfg"]
            n["widgets_values"] = wv
            n_sampler += 1
    if not (n_text and n_size and n_save and n_sampler):
        raise RuntimeError("工作流里没找到需要的节点 text=%s size=%s save=%s sampler=%s"
                           % (n_text, n_size, n_save, n_sampler))

    graph = ui_to_api(wf)
    r = post("/prompt", {"prompt": graph, "client_id": str(uuid.uuid4())})
    pid = r["prompt_id"]
    t0 = time.time()
    while time.time() - t0 < 1800:
        time.sleep(3)
        h = get("/history/" + pid)
        if pid in h:
            out = h[pid]
            st = out.get("status", {})
            if st.get("status_str") == "error":
                raise RuntimeError("ComfyUI 执行出错: " +
                                   json.dumps(st, ensure_ascii=False)[:2500])
            imgs = []
            for _nid, o in (out.get("outputs") or {}).items():
                for im in o.get("images", []):
                    imgs.append(im)
            if imgs:
                im = imgs[0]
                q = urllib.request.urlopen(
                    HOST + "/view?filename=%s&type=%s&subfolder=%s"
                    % (urllib.parse.quote(im["filename"]), im.get("type", "output"),
                       urllib.parse.quote(im.get("subfolder") or "")), timeout=120).read()
                sys.stdout.write("\n__XGC_RESULT__" + json.dumps({
                    "ok": True, "filename": im["filename"], "seconds": round(time.time() - t0, 1),
                    "png_b64": base64.b64encode(q).decode(), "nodes": len(graph),
                }) + "\n")
                return
    raise RuntimeError("等待出图超时 (1800s)")


import urllib.parse  # noqa: E402

try:
    main()
except Exception as e:
    sys.stdout.write("\n__XGC_RESULT__" + json.dumps(
        {"ok": False, "error": str(e)[:3000]}) + "\n")
    sys.exit(1)
'''


# --------------------------------------------------------------------------- 主流程

def cmd_status(d):
    print("=== 当前实例 ===")
    lst = instances()
    if not lst:
        print("  (空) 什么都没在跑，安全。")
    total = 0.0
    for i in lst:
        run = int(time.time()) - (i.get("start_timestamp") or 0)
        rate = float(i.get("price_per_hour") or 0)
        if i.get("status") == "running":
            total += rate
        print("  %s | %s | %s | CNY %s/h | 已开 %dm%d s | 已花 CNY %.3f"
              % (i["id"], i["status"], i.get("gpu_model"), rate,
                 run // 60, run % 60, run / 3600 * rate if i.get("status") == "running" else 0))
    b = balance()
    print("\n余额 CNY %s | 正在烧钱 CNY %.2f/h" % (b if b is not None else "?", total))
    return lst


def main():
    ap = argparse.ArgumentParser(description="仙宫云跑图一条龙（开机-出图-拉图-销毁）")
    ap.add_argument("--prompt", help="提示词")
    ap.add_argument("--size", default="1024x1024", help="宽x高，如 1536x1024（默认 1024x1024）")
    ap.add_argument("--steps", type=int, default=8, help="采样步数（Krea2 Turbo 用 8）")
    ap.add_argument("--cfg", type=float, default=1.0, help="CFG（Turbo 用 1.0）")
    ap.add_argument("--seed", type=int, default=None, help="固定种子（默认随机）")
    ap.add_argument("--batch", type=int, default=1, help="一次出几张")
    ap.add_argument("--prefix", default="xgc_run", help="输出文件名前缀")
    ap.add_argument("--gpu", default=None, help="GPU 型号，默认读配置")
    ap.add_argument("--image", default=None, help="镜像 ID，默认读配置")
    ap.add_argument("--image-type", default="private", help="镜像类型（默认 private）")
    ap.add_argument("--workflow", default=None, help="远端工作流 json 路径")
    ap.add_argument("--out", default=".", help="本地保存目录")
    ap.add_argument("--keep", action="store_true", help="跑完不销毁（调试用，会继续烧钱！）")
    ap.add_argument("--allow-parallel", action="store_true", help="已有实例在跑时也继续")
    ap.add_argument("--open", dest="do_open", action="store_true", help="跑完用系统看图器打开")
    ap.add_argument("--dry-run", action="store_true", help="只打印将要发的 payload，不开机")
    ap.add_argument("--yes", action="store_true", help="确认花钱（不加就只做演练）")
    ap.add_argument("--status", action="store_true", help="只看实例状态然后退出")
    a = ap.parse_args()

    d = load_defaults()

    if a.status:
        cmd_status(d)
        return

    if not a.prompt:
        die("必须给 --prompt（或用 --status 只看状态）")

    # 1) 省钱守门员：先看有没有在烧钱的机器
    running = [i for i in instances() if i.get("status") == "running"]
    if running:
        print("!! 已有实例正在运行（在烧钱）：")
        for i in running:
            print("   %s | %s | CNY %s/h" % (i["id"], i.get("gpu_model"), i.get("price_per_hour")))
        if not a.allow_parallel:
            print("\n先处理掉它们，或者加 --allow-parallel 硬上。")
            print("  销毁: python %s destroy <id> --yes" % XGC_PY)
            sys.exit(2)

    try:
        w, h = (int(x) for x in a.size.lower().split("x"))
    except Exception:
        die("--size 格式不对，要像 1024x1024")

    gpu = a.gpu or d["default_gpu"]
    image = a.image or d["default_image"]
    workflow = a.workflow or d.get("workflow_txt2img")
    keyfile = os.path.expanduser(d.get("ssh_private_key") or "~/.ssh/piwebui.pem")

    print("=== 本次任务 ===")
    print("  提示词 : %s" % (a.prompt if len(a.prompt) <= 100 else a.prompt[:100] + "..."))
    print("  尺寸   : %dx%d  batch=%d  steps=%d  cfg=%s" % (w, h, a.batch, a.steps, a.cfg))
    print("  GPU    : %s" % gpu)
    print("  镜像   : %s" % image)
    print("  工作流 : %s" % workflow)
    print("  本地   : %s" % os.path.abspath(a.out))

    if a.dry_run or not a.yes:
        print("\n=== DRY-RUN：将要执行的 deploy（不会发送）===")
        rc, out, _ = xgc("deploy", "--gpu", gpu, "--count", "1",
                         "--image", image, "--image-type", a.image_type,
                         "--name", "xgc-runpic", "--dry-run")
        print(out)
        if not a.yes:
            print("\n加了 --yes 才真的开机花钱。")
        return

    before = {i["id"] for i in instances()}
    inst_id = None
    t_start = time.time()
    rate = 0.0
    local_png = None

    try:
        # 2) 开机
        print("\n[1/6] 开机 ...")
        rc, out, _ = xgc("deploy", "--gpu", gpu, "--count", "1",
                         "--image", image, "--image-type", a.image_type,
                         "--name", "xgc-runpic", "--yes")
        if rc != 0:
            die("部署失败，没有重试（重试可能重复扣费）：\n" + out)
        for _ in range(20):
            time.sleep(3)
            new = [i for i in instances() if i["id"] not in before]
            if new:
                inst_id = new[0]["id"]
                break
        if not inst_id:
            die("部署提交了但没看到新实例，去控制台确认，别盲目重试")
        print("      实例 ID = %s" % inst_id)

        # 3) 等运行中
        print("[2/6] 等待运行中 ...")
        info = None
        for _ in range(180):
            time.sleep(5)
            me = [i for i in instances() if i["id"] == inst_id]
            if me and me[0].get("status") == "running":
                info = me[0]
                break
        if not info:
            die("实例迟迟没到 running，放弃")
        rate = float(info.get("price_per_hour") or 0)
        print("      运行中 | %s | CNY %s/h" % (info.get("gpu_model"), rate))

        # 4) 连进去
        print("[3/6] 建立 SSH ...")
        host = info.get("ssh_domain") or "%s-22.container.x-gpu.com" % inst_id
        port = int(info["ssh_port"])
        user = info.get("ssh_user") or "root"
        rm = Remote(host, port, user, keyfile, info.get("password"))
        if not rm.wait_ready(360):
            die("SSH 连不上（360s）。实例会照常销毁。")
        print("      %s@%s:%s | 认证方式 %s" % (user, host, port, rm.mode))

        # 5) 出图
        print("[4/6] 提交出图 ...")
        cfg = {"prompt": a.prompt, "width": w, "height": h, "batch": a.batch,
               "steps": a.steps, "cfg": a.cfg, "seed": a.seed,
               "prefix": a.prefix, "workflow": workflow}
        code = REMOTE_PY.replace(
            "__CFG_B64__", base64.b64encode(json.dumps(cfg).encode("utf-8")).decode())
        out = rm.run(stdin=code, timeout=1900)
        res = None
        for line in out.splitlines():
            if line.startswith("__XGC_RESULT__"):
                res = json.loads(line[len("__XGC_RESULT__"):])
        if not res or not res.get("ok"):
            raise RuntimeError("远端出图失败: %s" % (res or {}).get("error", out[-1500:]))
        print("      出图 OK: %s  耗时 %ss  图节点 %s 个"
              % (res["filename"], res["seconds"], res["nodes"]))

        # 6) 拉回本地
        print("[5/6] 下载到本地 ...")
        os.makedirs(a.out, exist_ok=True)
        local_png = os.path.join(os.path.abspath(a.out), res["filename"])
        with open(local_png, "wb") as f:
            f.write(base64.b64decode(res["png_b64"]))
        print("      %s  (%.1f MB)" % (local_png, os.path.getsize(local_png) / 2 ** 20))

    finally:
        # 7) 无论如何都要关掉这个烧钱的东西
        if inst_id and not a.keep:
            print("[6/6] 销毁实例 ...")
            rc, out, _ = xgc("destroy", inst_id, "--yes")
            print("      " + ("已销毁" if rc == 0 else "销毁失败！去看日志: " + out))
        elif inst_id and a.keep:
            print("\n!! --keep 生效，实例 %s 还在跑，CNY %s/h 继续烧！" % (inst_id, rate))
            print("!! 手动销毁: python %s destroy %s --yes" % (XGC_PY, inst_id))

        if inst_id:
            secs = int(time.time() - t_start)
            cost = secs / 3600 * rate
            print("\n=== 本次花费 ===")
            print("  在线 %d 分 %d 秒 x CNY %s/h = CNY %.3f" % (secs // 60, secs % 60, rate, cost))
            b = balance()
            if b is not None:
                print("  余额 CNY %.2f" % b)

    if local_png:
        print("\n图在这儿: %s" % local_png)
        if a.do_open:
            try:
                if sys.platform == "win32":
                    os.startfile(local_png)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", local_png])
                else:
                    subprocess.Popen(["xdg-open", local_png])
                print("已用系统看图器打开。")
            except Exception as e:
                print("自动打开失败（文件是好的）: %s" % e)


if __name__ == "__main__":
    main()
