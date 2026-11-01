#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FlashVSR+ WebUI —— 后台任务 + 轮询版（抗代理连接中断）

设计要点：所有 HTTP 事件都是「提交/查询」这种瞬时请求，真正的推理跑在独立线程里，
前端用 gr.Timer 每 2 秒轮询状态。这样即使云厂商的反向代理会掐掉长连接（SSE 超时），
页面也不会出现 "Connection to the server was lost"，任务在服务端照样跑完。
"""
import os
import re
import hashlib
import shutil
import signal
import subprocess
import sys
import threading
import time
from urllib.parse import quote, urlparse

import gradio as gr

REPO = "/root/FlashVSR_Plus"
OUT = "/root/outputs"
TMP = "/root/uploads"
PY = "/root/miniconda3/bin/python" if os.path.exists("/root/miniconda3/bin/python") else sys.executable
LOG_DIR = "/root/logs"

# 宽高必须都是 128 的倍数（项目硬要求），所以没有 1920x1080 / 1280x720 这种「标准」尺寸
PRESETS = {
    "保持原比例（自动 2 倍，推荐）": None,
    "快速预览 896×512（~10 GB 显存）": (896, 512),
    "1080p 级 2048×1152（~12 GB）": (2048, 1152),
    "2K 级 2560×1408（~15 GB，推荐上限）": (2560, 1408),
    "4K 级 3840×2176（~23.4 GB，极限）": (3840, 2176),
}

STATE = {"job": None}
LOCK = threading.Lock()


# ---------------------------------------------------------------- 参数解析
# Gradio 版传中文标签，精简版传 2560x1408 这种短名，两边都得认
PRESET_ALIAS = {
    "auto": None, "896x512": (896, 512), "2048x1152": (2048, 1152),
    "2560x1408": (2560, 1408), "3840x2176": (3840, 2176),
    "preview": (896, 512), "1080p": (2048, 1152), "2k": (2560, 1408), "4k": (3840, 2176),
}


def resolve_preset(preset):
    """把前端传来的预设解成 (宽, 高)；None = 保持原比例自动 2 倍"""
    if preset in PRESETS:
        return PRESETS[preset]
    s = str(preset or "auto").strip().lower().replace("×", "x").replace(" ", "")
    if s in PRESET_ALIAS:
        return PRESET_ALIAS[s]
    m = re.match(r"^(\d{3,4})x(\d{3,4})$", s)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        if w % 128 == 0 and h % 128 == 0:
            return (w, h)
    return None


def video_guard(src):
    """没真视频流就拒掉。以前图片也会被当视频跑，产出「只有一帧」的废片。

    注意：ffprobe 会把 .jpg 当成 1 帧的 mjpeg 流（宽高/时长都有），所以光看宽高不构，
    必须同时查扩展名、帧数、时长。
    """
    ext = os.path.splitext(src)[1].lower()
    if ext in IMG_EXT:
        return ("⚠️ 这是图片（%s），图片不能做视频超分 —— 之前就是这种文件被当视频跑，"
                "出来只有一帧。请在「服务器上的文件」里选一个视频。" % ext)
    ow, oh, dur, fps, nf, size = probe(src)
    if not (ow and oh):
        return ("⚠️ 这个文件没有视频流（%s），图片/音频做不了超分。请选一个视频"
                "（.mp4/.mov/.mkv 等）。" % (ext or "未知类型"))
    if nf <= 1 or dur <= 0:
        return ("⚠️ 这个文件只有 %d 帧 / 时长 %.2f 秒 —— 像是单张图片或损坏的文件，"
                "跑出来也只会是一帧。请换一个正常的视频。" % (nf, dur))
    return None


def probe(path):
    """ffprobe 读时长/分辨率/帧率/帧数（失败返回空）"""
    try:
        p = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
             "-show_entries", "format=duration,size",
             "-of", "default=noprint_wrappers=1", path],
            capture_output=True, text=True, timeout=30)
        kv = dict(l.split("=", 1) for l in p.stdout.strip().splitlines() if "=" in l)
        w = int(kv.get("width", 0) or 0)
        h = int(kv.get("height", 0) or 0)
        dur = float(kv.get("duration", 0) or 0)
        fps = kv.get("r_frame_rate", "0/1")
        try:
            n, d = fps.split("/")
            fps = float(n) / float(d or 1)
        except Exception:
            fps = 0.0
        size = int(kv.get("size", 0) or 0)
        nf = kv.get("nb_frames", "")
        nf = int(nf) if str(nf).isdigit() else int(dur * fps) if dur and fps else 0
        return w, h, dur, fps, nf, size
    except Exception:
        return 0, 0, 0.0, 0.0, 0, 0


def auto_target(w, h):
    """按原比例把最短边放大到 ~2 倍，并保证宽高都是 128 的倍数"""
    if not w or not h:
        return 1280, 768
    cap = max(2560, 128 * int((max(w, h) + 127) // 128))     # 长边上限 2560，但绝不缩小原片
    k = min(2.0, cap / float(max(w, h)))
    tw, th = w * k, h * k
    best = None
    for a in (int(tw // 128), int(tw // 128) + 1):
        for b in (int(th // 128), int(th // 128) + 1):
            W, H = a * 128, b * 128
            if W < 128 or H < 128 or max(W, H) > cap:
                continue
            err = abs(W / H - w / h) / (w / h)      # 挑比例最接近原片的合法尺寸
            if best is None or err < best[0]:
                best = (err, W, H)
    return best[1], best[2]


def slug(p):
    base = os.path.splitext(os.path.basename(p))[0]
    return re.sub(r"[^0-9A-Za-z_-]+", "_", base)[:32] or "video"



VIDEO_EXT = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".flv", ".ts", ".mxf")
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")
THUMB_DIR = "/root/thumbs"
_META = {}


# ---------------------------------------------------------------- 文件库（缩略图 / 预览 / 下载）
def _lib_dir(which="out"):
    return TMP if str(which).lower() in ("up", "uploads", "tmp") else OUT


def _safe_path(base, name):
    name = os.path.basename((name or "").strip())
    if not name:
        return None
    p = os.path.join(base, name)
    return p if os.path.isfile(p) else None


def _meta_of(path):
    """带缓存的 ffprobe（文件变了自动重算）"""
    try:
        st = os.stat(path)
    except Exception:
        return {}
    key = (path, int(st.st_mtime), st.st_size)
    if key in _META:
        return _META[key]
    w, h, dur, fps, nf, size = probe(path)
    meta = {"w": w, "h": h, "dur": round(dur, 2), "fps": round(fps, 2), "frames": nf}
    if len(_META) > 400:
        _META.clear()
    _META[key] = meta
    return meta


def lib_list(which="out"):
    """列文件库。每个条目自带缩略图 / 预览 / 下载地址，前端不需要再拼路径。"""
    d = _lib_dir(which)
    rows = []
    try:
        names = os.listdir(d)
    except Exception:
        names = []
    for n in names:
        if n.startswith("."):
            continue
        p = os.path.join(d, n)
        if not os.path.isfile(p):
            continue
        ext = os.path.splitext(n)[1].lower()
        kind = "video" if ext in VIDEO_EXT else "image" if ext in IMG_EXT else "other"
        try:
            st = os.stat(p)
        except Exception:
            continue
        q = "which=%s&name=%s" % (which, quote(n))
        row = {"name": n, "size": st.st_size, "mtime": int(st.st_mtime), "kind": kind,
               "which": which,
               "url": "/api/file?" + q, "dl": "/api/file?" + q + "&dl=1"}
        if kind == "video":
            row.update(_meta_of(p))
        if kind in ("video", "image"):
            row["thumb"] = "/thumb?" + q
        rows.append(row)
    rows.sort(key=lambda r: -r["mtime"])
    return {"dir": d, "which": which, "files": rows}


def _thumb_tag(path):
    st = os.stat(path)
    return hashlib.md5(("%s|%d|%d" % (path, st.st_mtime, st.st_size)).encode()).hexdigest()[:16]


def ensure_thumb(which, name):
    """生成（并缓存）缩略图。视频取第 1 秒的帧，图直接缩。"""
    src = _safe_path(_lib_dir(which), name)
    if not src:
        return None
    try:
        st = os.stat(src)
    except Exception:
        return None
    tag = _thumb_tag(src)
    os.makedirs(THUMB_DIR, exist_ok=True)
    # 缓存不会无限长：超过 5000 张就清掉最旧的 1000 张（删了文件也不会洩留）
    try:
        if len(os.listdir(THUMB_DIR)) > 5000:
            old = sorted((os.path.getmtime(os.path.join(THUMB_DIR, n)), n)
                         for n in os.listdir(THUMB_DIR))[:1000]
            for _t, n in old:
                os.unlink(os.path.join(THUMB_DIR, n))
    except Exception:
        pass
    dst = os.path.join(THUMB_DIR, tag + ".jpg")
    if os.path.exists(dst) and os.path.getsize(dst) > 800:
        return dst
    vf = "scale=420:420:force_original_aspect_ratio=decrease"
    for ss in ((["-ss", "1"], ["-ss", "0"]) if src.lower().endswith(VIDEO_EXT) else ([],)):
        cmd = ["ffmpeg", "-v", "error", "-y"] + ss + [
            "-i", src, "-frames:v", "1", "-vf", vf, "-q:v", "6", dst]
        try:
            subprocess.run(cmd, capture_output=True, timeout=90)
        except Exception:
            pass
        if os.path.exists(dst) and os.path.getsize(dst) > 800:
            return dst
    return None


try:
    os.makedirs(THUMB_DIR, exist_ok=True)
except Exception:
    pass


def delete_file(which="out", name=""):
    """删文件（只限 outputs / uploads 两个目录，顺带把它的缩略图缓存清掉）"""
    p = _safe_path(_lib_dir(which), name)
    if not p:
        return {"ok": False, "msg": "文件不存在（可能已经被删了）"}
    j = STATE["job"]
    if j and j.status == "running":
        busy = [x for x in (j.src, j.out) if x]
        if any(os.path.abspath(x) == os.path.abspath(p) for x in busy):
            return {"ok": False, "msg": "这个文件正在被当前任务使用，等它跑完再删"}
    try:
        tag = _thumb_tag(p)
    except Exception:
        tag = None
    try:
        os.unlink(p)
    except Exception as e:  # noqa
        return {"ok": False, "msg": "删不掉：%r" % (e,)}
    if tag:
        try:
            os.unlink(os.path.join(THUMB_DIR, tag + ".jpg"))
        except Exception:
            pass
    _META.clear()
    return {"ok": True, "msg": "已删除 %s" % os.path.basename(p)}


def list_uploads():
    """列出 /root/uploads 里可以直接拿来跑的视频"""
    rows, names = [], []
    try:
        for n in sorted(os.listdir(TMP)):
            p = os.path.join(TMP, n)
            if os.path.isfile(p) and n.lower().endswith(VIDEO_EXT):
                sz = os.path.getsize(p) / 1e6
                rows.append("%-52s %8.1f MB" % (n, sz))
                names.append(p)
    except Exception:
        pass
    body = chr(10).join(rows)
    text = ("```" + chr(10) + body + chr(10) + "```") if rows else "（`/root/uploads` 里还没有视频）"
    return text, gr.update(choices=names, value=(names[0] if names else None))


def download_url(url, maxh):
    """服务端直接下片（比浏览器上传快一个数量级）"""
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        return "⚠️ 填一个 http(s) 链接", gr.update()
    with LOCK:
        j = STATE["job"]
        if j and j.status == "running":
            return "⚠️ 有任务在跑，先等它结束", gr.update()
        os.makedirs(TMP, exist_ok=True)
        base = os.path.basename(urlparse(url).path) or "video.mp4"
        if base.lower().endswith(VIDEO_EXT):
            # 直链：走多线程断点续传，比 yt-dlp 单连接快得多
            cmd = [PY, "-u", os.path.join(os.path.dirname(os.path.abspath(__file__)), "dl.py"),
                   url, os.path.join(TMP, base), "8"]
        else:
            cmd = [PY, "-m", "yt_dlp", "--no-playlist", "--newline",
                   "-f", "bv*[height<=%d]+ba/b[height<=%d]/b" % (maxh, maxh),
                   "--merge-output-format", "mp4",
                   "-o", os.path.join(TMP, "%(title).60s.%(ext)s"), url]
        job = Job(cmd, "", url, "下载 %s" % url[:60])
        job.kind = "download"
        STATE["job"] = job
        threading.Thread(target=_run, args=(job,), daemon=True).start()
    return "⏳ 已开始服务端下载：%s" % url[:120], gr.update()


class Job:
    def __init__(self, cmd, outpath, src, label):
        self.kind = "infer"
        self.cmd = cmd
        self.out = outpath
        self.src = src
        self.label = label
        self.log = []          # 最近若干行
        self.proc = None
        self.status = "running"
        self.rc = None
        self.t0 = time.time()
        self.t1 = None
        self.pct = -1
        self.err = ""
        self.user_cancelled = False
        self.tries = 0
        self.plan = ""

    def add(self, line):
        line = line.rstrip()
        if not line:
            return
        self.log.append(line)
        if len(self.log) > 400:
            del self.log[:100]
        m = re.search(r"(\d{1,3})%\|", line)
        if m:
            try:
                self.pct = int(m.group(1))
            except Exception:
                pass

    def elapsed(self):
        return (self.t1 or time.time()) - self.t0


def _reader(job):
    fd = job.proc.stdout.fileno()
    buf = b""
    while True:
        try:
            d = os.read(fd, 8192)
        except Exception:
            break
        if not d:
            break
        buf += d
        while True:
            m = re.search(rb"[\r\n]", buf)
            if not m:
                break
            job.add(buf[: m.start()].decode("utf-8", "replace"))
            buf = buf[m.end():]
        # 防止超长行堆积
        if len(buf) > 1 << 20:
            buf = buf[-4096:]


def _run(job):
    """跑任务：失败时如果是内存/分段问题，自动降级重试一次。"""
    os.makedirs(LOG_DIR, exist_ok=True)
    fh = open(os.path.join(LOG_DIR, "job_%s.log" % time.strftime("%m%d-%H%M%S")), "wb")
    try:
        return _run_attempts(job, fh)
    finally:
        job.t1 = time.time()
        try:
            fh.write(("\n\n".join(job.log) + "\n").encode())
            fh.close()
        except Exception:
            pass


def _run_attempts(job, fh):
    while True:
        job.tries += 1
        fh.write(("\n=== attempt #%d ===\n" % job.tries).encode())
        fh.write((" ".join(job.cmd) + "\n\n").encode())
        fh.flush()
        try:
            rc = _run_once(job, fh)
        except Exception as e:  # noqa
            job.status = "failed"
            job.err = repr(e)
            job.add("!! 异常：%r" % (e,))
            return
        ok = rc == 0 and (job.kind != "infer" or os.path.exists(job.out))
        if ok:
            job.status = "done"
            return
        if job.user_cancelled:
            job.status = "cancelled"
            return
        hint = _oom_hint(job, rc)
        nxt = retry_cmd(job.cmd) if hint else None
        if nxt:
            job.add("↻ %s —— 自动改成「%s」重跑一次" % (hint, _flag_str(nxt, "--decode-every")))
            job.cmd = nxt
            job.pct = -1
            continue
        job.status = "failed"
        job.err = ((hint + "；") if hint else "") + "退出码 %s，看下面日志最后几行" % rc
        return


def _run_once(job, fh):
    env = dict(os.environ)
    env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    env.setdefault("PATH", "/root/miniconda3/bin:/usr/bin:/bin")
    job.proc = subprocess.Popen(
        job.cmd, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        start_new_session=True, bufsize=0, env=env)
    th = threading.Thread(target=_reader, args=(job,), daemon=True)
    th.start()
    job.rc = job.proc.wait()
    th.join(timeout=5)
    return job.rc


def _flag_str(cmd, flag):
    if flag in cmd and cmd.index(flag) + 1 < len(cmd):
        return "%s %s" % (flag, cmd[cmd.index(flag) + 1])
    return "（整条解码）"


def _set_flag(cmd, flag, value):
    cmd = list(cmd)
    if flag in cmd:
        cmd[cmd.index(flag) + 1] = str(value)
    else:
        cmd += [flag, str(value)]
    return cmd


def retry_cmd(cmd):
    """内存类失败后的降级方案：整条解码 -> 分片 8 -> 分片 4。到 4 就不再试了。"""
    if "--decode-every" not in cmd:
        return _set_flag(cmd, "--decode-every", 8)
    try:
        cur = int(cmd[cmd.index("--decode-every") + 1])
    except Exception:
        return None
    if cur > 4:
        return _set_flag(cmd, "--decode-every", 4)
    return None


def _oom_hint(job, rc):
    """把「静默死掉」翻译成人话：SIGKILL 一般是内核 OOM，SIGSEGV 是算子崩"""
    txt = "\n".join(job.log[-80:]).lower()
    if rc == -9:
        return "进程被内核 OOM 杀掉（系统内存不够，日志里不会有 traceback）"
    if rc == -11:
        return "进程段错误（CUDA / 注意力算子崩了）"
    if "cuda out of memory" in txt or "outofmemoryerror" in txt:
        return "显存不够（CUDA out of memory）"
    if "out of memory" in txt:
        return "内存不够（out of memory）"
    return ""


def ram_total_mb():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) // 1024
    except Exception:
        pass
    return 8192


def plan_decode_every(nf, w, h, requested="auto"):
    """决定要不要分片解码。

    decode_every=auto（整条解码）会把整条片子做成 float32 常驻内存，再加上时间维展开
    和输出句柄，实测 594 帧 2560x1408 直接顶满 57 GB 被内核 OOM 杀掉 —— SIGKILL，
    日志里停在 `Running inference...` 一行 traceback 都没有。所以按内存预算提前切分片。
    返回 (decode_every 或 None, 说明文字)
    """
    de = str(requested or "auto").strip().lower()
    if de and de != "auto":
        return de, "分片解码 decode-every=%s（用户指定）" % de
    budget_mb = int(ram_total_mb() * 0.35)
    if not nf:
        return "8", "读不到帧数，保守用分片解码 decode-every=8"
    est_mb = nf * float(w * h) * 3 * 4 / 1048576.0      # 一份 float32 视频
    est_mb *= 2.5                                       # 实测要 2~3 份同时在内存里
    if est_mb <= budget_mb:
        return None, "整条解码（预估 %.1f GB / 预算 %.1f GB）" % (est_mb / 1024, budget_mb / 1024)
    return "8", ("自动分片解码 decode-every=8（整条要 %.1f GB，超预算 %.1f GB，会 OOM）"
                 % (est_mb / 1024, budget_mb / 1024))


def build_cmd(src, w, h, mode, tcomp, max_frames, decode_every, colorfix, vpreset, mem):
    """统一的命令行构造（Gradio 版和精简版共用）。返回 (cmd, 输出路径, 内存说明, 源片信息)"""
    ow, oh, dur, fps, nf, size = probe(src)
    de, plan = plan_decode_every(nf, w, h, decode_every)
    os.makedirs(OUT, exist_ok=True)
    outpath = os.path.join(
        OUT, "vsr_%s_%s_%dx%d.mp4" % (time.strftime("%m%d-%H%M%S"), slug(src)[:20], w, h))
    cmd = [PY, "-u", "-m", "inference.run_stream",
           "--input", src, "--output", outpath,
           "--mode", mode, "--height", str(h), "--width", str(w),
           "--temporal-compression", str(int(tcomp)),
           "--video-preset", vpreset]
    try:
        mf = int(max_frames or 0)
        if mf > 0:
            cmd += ["--max-frames", str(mf)]
    except Exception:
        pass
    if de:
        cmd += ["--decode-every", str(de)]
    if colorfix:
        cmd += ["--cf"]
    cmd += mem_flags(mem, w, h, chunked=bool(de))
    return cmd, outpath, plan, (ow, oh, dur, fps, nf, size)


def cleanup_partials():
    """上一次被 SIGKILL 时留下的隐藏临时文件（增量写入的 .xxx.mp4）"""
    try:
        for n in os.listdir(OUT):
            if n.startswith(".") and n.lower().endswith(".mp4"):
                p = os.path.join(OUT, n)
                if time.time() - os.path.getmtime(p) > 60:
                    os.unlink(p)
    except Exception:
        pass


# ---------------------------------------------------------------- 交互逻辑
def mem_flags(mem, w, h, chunked=False):
    """显存策略 -> 额外 CLI 参数（4K 在 24G 上非常贴边，必须 offload）"""
    px = w * h
    if mem == "省显存（慢约 1 倍）":
        return ["--cache-offload-mode", "always", "--tiny-decoder-mode", "serial"]
    if mem == "高性能（关 offload）":
        return ["--cache-offload-mode", "never"]
    # 自动：分片解码时每次只算 32 帧，2K 用默认就够（实测 2560x1408 峰值 15.2 GB）；
    # 只有 4K 级（>= 6 MP）才上 offload（3840x2176 默认会爆 23032/24564 MiB）
    if px >= (6_000_000 if chunked else 3_000_000):
        return ["--cache-offload-mode", "always", "--tiny-decoder-mode", "serial"]
    return []


def submit(video_file, path_txt, picked, mode, preset, width, height, tcomp,
           max_frames, decode_every, colorfix, vpreset, mem):
    idle = (gr.update(), gr.update())
    with LOCK:
        j = STATE["job"]
        if j and j.status == "running":
            return ("⚠️ 已有任务在跑（%s）· 已用 %.0fs，先点「取消」或等它结束"
                    % (j.label, j.elapsed()), "\n".join(j.log)) + idle

        src = (path_txt or "").strip()
        if not src and picked:
            src = picked if str(picked).startswith("/") else os.path.join(TMP, str(picked))
        if not src:
            v = video_file
            if isinstance(v, dict):
                v = v.get("path") or v.get("video")
            src = v or ""
        if not src or not os.path.exists(src):
            return ("⚠️ 还没选视频：上传一个，或者在「容器内路径」里填绝对路径"
                    "（大文件强烈建议走路径，别走浏览器上传）", "") + idle

        w, h = int(width), int(height)
        rp = resolve_preset(preset)
        if rp:
            w, h = rp
        elif preset in PRESETS:            # 中文标签里的「保持原比例」
            ow, oh, _, _, _, _ = probe(src)
            w, h = auto_target(ow, oh)

        if w % 128 or h % 128:
            return ("⚠️ 宽高必须是 128 的倍数：现在 %d×%d" % (w, h), "") + idle
        bad = video_guard(src)
        if bad:
            return (bad, "") + idle

        cleanup_partials()
        cmd, outpath, plan, info = build_cmd(src, w, h, mode, tcomp, max_frames,
                                           decode_every, colorfix, vpreset, mem)

        job = Job(cmd, outpath, src, "%s · %d×%d" % (mode, w, h))
        job.plan = plan
        STATE["job"] = job
        job.add("内存规划：%s" % plan)
        threading.Thread(target=_run, args=(job,), daemon=True).start()

        ow, oh, dur, fps, nf, size = info
        head = ("✅ 已提交（后台跑，可以关页面，任务不会断）\n\n"
                "- 输入：`%s` — %d×%d · %.1fs · %d 帧 · %.3g fps · %.1f MB\n"
                "- 输出目标：%d×%d（%s）\n- 内存规划：%s\n- 日志：`%s`\n\n```\n%s\n```"
                % (os.path.basename(src), ow, oh, dur, nf, fps, size / 1048576.0,
                   w, h, mode + " · 显存策略 " + mem, plan,
                   os.path.join(LOG_DIR, "job_*.log"),
                   " ".join(cmd)))
        return head, "任务已启动…", gr.update(), gr.update(visible=False)


def poll():
    j = STATE["job"]
    if not j:
        return "空闲 · 还没有任务", "", gr.update(), gr.update()

    el = j.elapsed()
    icon = {"running": "⏳", "done": "✅", "failed": "❌", "cancelled": "⛔"}.get(j.status, "•")
    line = "%s **%s** · 已用 %.0fs" % (icon, j.status, el)
    if j.status == "running" and j.pct >= 0:
        line += " · 进度 %d%%" % j.pct
    if j.status == "done" and j.kind == "infer":
        ow, oh, dur, fps, nf, size = probe(j.out)
        sp = (nf / el) if (nf and el) else 0
        line += ("\n\n输出：`%s`\n%d×%d · %.1fs · %d 帧 · %.1f MB · 平均 %.2f 帧/秒"
                 % (j.out, ow, oh, dur, nf, size / 1048576.0, sp))
    if j.status == "failed":
        line += "\n\n%s\n\n日志文件：`%s`" % (j.err or "失败", os.path.join(LOG_DIR, "job_*.log"))
    if j.status == "cancelled":
        line += "\n\n已取消。"

    log = "\n".join(j.log[-200:])
    if j.kind == "download":
        if j.status == "done":
            return line + chr(10) + chr(10) + "下载完成，点「刷新列表」选它。", log, gr.update(), gr.update(visible=False)
        return line, log, gr.update(), gr.update(visible=False)
    if j.status == "done":
        return line, log, gr.update(value=j.out), gr.update(value=j.out, visible=True)
    return line, log, gr.update(), gr.update(visible=False)


def cancel():
    j = STATE["job"]
    if not j or j.status != "running" or not j.proc:
        return "没有正在跑的任务", gr.update()
    j.user_cancelled = True
    try:
        os.killpg(os.getpgid(j.proc.pid), signal.SIGINT)
        for _ in range(20):
            if j.proc.poll() is not None:
                break
            time.sleep(0.25)
        if j.proc.poll() is None:
            os.killpg(os.getpgid(j.proc.pid), signal.SIGKILL)
        j.add("!! 用户取消")
    except Exception as e:  # noqa
        return "取消失败：%r" % (e,), gr.update()
    return "⛔ 已发送取消信号，等进程退出…", gr.update()


def env_report():
    def sh(c):
        try:
            return subprocess.run(c, shell=True, capture_output=True, text=True,
                                  timeout=25).stdout.strip()
        except Exception as e:  # noqa
            return "ERR %r" % (e,)
    lines = ["```", sh("nvidia-smi --query-gpu=name,memory.total,memory.used,driver_version "
                       "--format=csv"), ""]
    lines.append(sh("%s -c \"import torch,flash_attn,flashvsr_attn;"
                    "print('torch',torch.__version__,torch.version.cuda,torch.cuda.is_available());"
                    "print('flash_attn',flash_attn.__version__)\"" % PY))
    lines.append("")
    for d in ("TCDecoder.ckpt", "Wan2.1_VAE.pth", "turbo/dit.safetensors",
              "turbo/lq_proj_in.safetensors", "base/dit.safetensors",
              "base/lq_proj_in.safetensors"):
        p = os.path.join(REPO, "ckpts", d)
        lines.append("%-32s %s" % (d, ("%.2f GB" % (os.path.getsize(p) / 1e9))
                                   if os.path.exists(p) else "缺失！"))
    lines.append("")
    lines.append(sh("ls -1 %s | tail -5" % OUT))
    lines.append("```")
    return "\n".join(lines)



# ---------------------------------------------------------------- 纯 JSON API 用的核心逻辑
MEM_MAP = {"auto": "自动", "save": "省显存（慢约 1 倍）", "fast": "高性能（关 offload）"}


def core_start(src, preset, mode, mem, tcomp, max_frames, decode_every="auto",
               colorfix=False, vpreset="veryfast"):
    """给精简版页面用的启动逻辑（不经过 gradio）"""
    with LOCK:
        j = STATE["job"]
        if j and j.status == "running":
            return None, "已有任务在跑（%s），先取消或等它结束" % j.label
        if not src or not os.path.exists(src):
            return None, "找不到文件：%s" % src
        bad = video_guard(src)
        if bad:
            return None, bad
        rp = resolve_preset(preset)
        if rp:
            w, h = rp
        else:
            ow, oh, _, _, _, _ = probe(src)
            if not ow:
                return None, "这个文件读不出视频流（格式不支持？）"
            w, h = auto_target(ow, oh)
        if w % 128 or h % 128:
            return None, "宽高必须是 128 的倍数：%d×%d" % (w, h)
        cleanup_partials()
        cmd, outpath, plan, _info = build_cmd(src, w, h, mode, tcomp, max_frames,
                                              decode_every, colorfix, vpreset,
                                              MEM_MAP.get(mem, mem))
        job = Job(cmd, outpath, src, "%s · %d×%d" % (mode, w, h))
        job.plan = plan
        STATE["job"] = job
        job.add("内存规划：%s" % plan)
        threading.Thread(target=_run, args=(job,), daemon=True).start()
        return job, ""


def core_download(url, maxh=2160):
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        return None, "只支持 http(s) 链接"
    with LOCK:
        j = STATE["job"]
        if j and j.status == "running":
            return None, "已有任务在跑（%s）" % j.label
        os.makedirs(TMP, exist_ok=True)
        base = os.path.basename(urlparse(url).path) or "video.mp4"
        if base.lower().endswith(VIDEO_EXT):
            cmd = [PY, "-u", os.path.join(os.path.dirname(os.path.abspath(__file__)), "dl.py"),
                   url, os.path.join(TMP, base), "8"]
        else:
            cmd = [PY, "-m", "yt_dlp", "--no-playlist", "--newline",
                   "-f", "bv*[height<=%d]+ba/b[height<=%d]/b" % (maxh, maxh),
                   "--merge-output-format", "mp4",
                   "-o", os.path.join(TMP, "%(title).60s.%(ext)s"), url]
        job = Job(cmd, "", url, "下载 " + url[:60])
        job.kind = "download"
        STATE["job"] = job
        threading.Thread(target=_run, args=(job,), daemon=True).start()
        return job, ""


def core_status():
    j = STATE["job"]
    if not j:
        return {"status": "idle", "log": "", "elapsed": 0, "pct": -1, "label": "",
                "out": "", "plan": "", "tries": 0}
    d = {"status": j.status, "log": chr(10).join(j.log[-200:]),
         "elapsed": round(j.elapsed(), 1), "pct": j.pct, "label": j.label, "out": "", "info": "",
         "plan": j.plan, "tries": j.tries}
    if j.kind == "download":
        d["label"] = "服务器下载"
        if j.status == "done":
            d["out"] = ""
        return d
    if j.status == "done":
        d["out"] = j.out
        ow, oh, dur, fps, nf, size = probe(j.out)
        d["info"] = "%d×%d · %.1f 秒 · %d 帧 · %.1f MB" % (ow, oh, dur, nf, size / 1048576.0)
    if j.status == "failed" and j.err:
        d["log"] = (d["log"] + chr(10) + j.err).strip()
    return d


# ---------------------------------------------------------------- 界面
with gr.Blocks(title="FlashVSR+ 视频超分") as demo:
    gr.HTML("<style>.logbox textarea{font-family:ui-monospace,Consolas,monospace;font-size:12px}</style>"
            "<div style='background:#1f6feb22;border:1px solid #1f6feb55;border-radius:10px;"
            "padding:10px 14px;margin:6px 0 4px'>"
            "<b>⚡ 网络不稳 / 上传传不动？</b> 用精简版页面："
            "<a href='/g' style='color:#7fb0ff;font-weight:600'>本地址 + /g</a>"
            "（不依赖长连接，请求自带重试，分片续传上传）· "
            "<a href='/s#files' style='color:#7fb0ff;font-weight:600'>📁 文件库</a>"
            "（缩略图 / 预览 / 下载，关页面也能回来看）</div>")
    gr.Markdown(
        "## FlashVSR+ 视频超分 / 高清放大\n"
        "后台任务模式：点「开始」后推理在服务端跑，**页面断开也不影响**，回来看结果就行。\n"
        "> ⚠️ 这里的内置上传走公网代理，实测只有 **0.3 MB/s** 且长请求会被掐断（报 "
        "`Unexpected end of JSON input`）。**超过几十 MB 的片子请用下面两种方式**：" + chr(10) +
        "> ① 本页地址加 `/up` → 分片续传上传台；② 在「服务器下载」里贴视频链接，让机房直接拉。"
    )
    with gr.Row():
        with gr.Column(scale=3):
            video_in = gr.Video(label="上传视频（≤ 几百 MB）", sources=["upload"])
            path_in = gr.Textbox(
                label="或者填容器内路径（优先级最高）",
                placeholder="/root/uploads/我的视频.mp4")
            with gr.Row():
                pick = gr.Dropdown(choices=[], value=None, label="/root/uploads 里的视频（选中即用）",
                                   interactive=True, scale=4)
                refresh_btn = gr.Button("刷新列表", scale=1)
            with gr.Row():
                mode = gr.Radio(["turbo", "base"], value="turbo",
                                label="模型预设（turbo 最快，官方推荐 / base 另一套权重）")
                tcomp = gr.Radio([4, 2, 1], value=4, label="时间压缩（1 最慢最稳）")
            preset = gr.Dropdown(list(PRESETS), value="保持原比例（自动 2 倍，推荐）",
                                 label="分辨率预设")
            with gr.Row():
                width = gr.Slider(128, 4096, value=2048, step=128, label="宽（128 的倍数）")
                height = gr.Slider(128, 4096, value=1152, step=128, label="高（128 的倍数）")
            mem = gr.Radio(["自动", "省显存（慢约 1 倍）", "高性能（关 offload）"], value="自动",
                           label="显存策略（自动：≥3MP 自动开 offload，否则 4K 会 OOM）")
            with gr.Accordion("网速慢传不上来？用这两条路（比浏览器上传快）", open=False):
                gr.Markdown(chr(10).join([
                    "**① 分片续传上传台（推荐，同一个 7860 端口）**：本页地址后面加 `/up`",
                    "→ `https://<实例ID>-7860.container.x-gpu.com/up`"
                    "（2 MB 一片、每片一个短请求，断了自动重试，刷新还能续传）",
                    "",
                    "**② 服务器直接把片子拉下来**（最快，机房下载 15 MB/s）",
                    "填直链 / B 站 / YouTube 等链接，服务器下到 `/root/uploads`，下完在左边下拉里选。"]))
                with gr.Row():
                    url_in = gr.Textbox(label="视频链接", placeholder="https://...", scale=3)
                    url_maxh = gr.Dropdown([720, 1080, 1440, 2160], value=2160,
                                           label="最高分辨率", scale=1)
                    dl_btn = gr.Button("服务器下载", scale=1)
            with gr.Accordion("更多参数", open=False):
                max_frames = gr.Number(value=0, label="只跑前 N 帧（0=整条，试参数用）", precision=0)
                decode_every = gr.Textbox(value="auto", label="decode-every（auto 或 4 的倍数，长视频可省内存）")
                colorfix = gr.Checkbox(value=False, label="低频色彩校正 --cf")
                vpreset = gr.Dropdown(["veryfast", "fast", "medium", "slow"],
                                      value="veryfast", label="x264 编码速度")
            uploads_md = gr.Markdown()
            with gr.Row():
                go = gr.Button("开始放大", variant="primary", scale=3)
                stop = gr.Button("取消", scale=1)
        with gr.Column(scale=4):
            status = gr.Markdown("空闲 · 还没有任务")
            logbox = gr.Textbox(label="实时日志", lines=16, max_lines=16,
                                autoscroll=True, interactive=False)
            video_out = gr.Video(label="结果预览", interactive=False)
            dl = gr.DownloadButton(label="下载结果", visible=False)

    with gr.Accordion("自检（显存 / 依赖 / 权重）", open=False):
        btn_env = gr.Button("跑一次自检")
        envbox = gr.Markdown()

    refresh_btn.click(list_uploads, outputs=[uploads_md, pick])
    dl_btn.click(download_url, inputs=[url_in, url_maxh], outputs=[status, pick])

    timer = gr.Timer(2.0)
    timer.tick(poll, outputs=[status, logbox, video_out, dl])

    go.click(submit,
             inputs=[video_in, path_in, pick, mode, preset, width, height, tcomp,
                     max_frames, decode_every, colorfix, vpreset, mem],
             outputs=[status, logbox, video_out, dl])
    stop.click(cancel, outputs=[status, dl])
    btn_env.click(env_report, outputs=[envbox])

if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import uploader as U

    os.makedirs(OUT, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    api = FastAPI(title="FlashVSR+")

    # 分片续传上传台（挂在同一个 7860 上，因为平台代理只放行 7860 / 8888）
    @api.get("/up", response_class=HTMLResponse)
    def _up_page():
        return U.PAGE

    @api.get("/up/list")
    def _up_list():
        return U.up_list()

    @api.get("/up/status")
    def _up_status(name: str = ""):
        return U.up_status(name)

    @api.put("/up/chunk")
    async def _up_chunk(request: Request, name: str = "", off: int = 0):
        body = await request.body()
        return U.up_chunk(name, off, body)

    from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response

    HERE = os.path.dirname(os.path.abspath(__file__))

    @api.get("/s", response_class=HTMLResponse)
    def _simple():
        with open(os.path.join(HERE, "simple.html"), encoding="utf-8") as f:
            return f.read()

    @api.get("/api/uploads")
    def _api_uploads():
        return U.up_list()

    @api.post("/api/submit")
    async def _api_submit(request: Request):
        p = await request.json()
        src = (p.get("src") or "").strip()
        if src and not src.startswith("/"):
            src = os.path.join(TMP, os.path.basename(src))
        job, msg = core_start(src, p.get("preset") or "auto", p.get("mode") or "turbo",
                              p.get("mem") or "auto", p.get("tcomp") or 4,
                              p.get("max_frames") or 0, p.get("decode_every") or "auto",
                              bool(p.get("colorfix")), p.get("vpreset") or "veryfast")
        return {"ok": job is not None, "msg": msg}

    @api.post("/api/download")
    async def _api_download(request: Request):
        p = await request.json()
        job, msg = core_download(p.get("url"), int(p.get("maxh") or 2160))
        return {"ok": job is not None, "msg": msg}

    @api.post("/api/delete")
    async def _api_delete(request: Request):
        p = await request.json()
        return delete_file(p.get("which") or "out", p.get("name") or "")

    @api.get("/api/status")
    def _api_status():
        return core_status()

    @api.post("/api/cancel")
    def _api_cancel():
        cancel()
        return {"ok": True}

    @api.get("/api/file")
    def _api_file(name: str = "", which: str = "out", dl: int = 0):
        """取原始文件。dl=1 强制下载，否则 inline（<video> 才能边下边播、能拖进度）。

        FileResponse 支持 Range（实测 206 Partial Content），所以网络差也能拖进度。
        """
        path = _safe_path(_lib_dir(which), name)
        if not path:
            return JSONResponse({"error": "not found", "name": name}, status_code=404)
        ext = os.path.splitext(path)[1].lower()
        mt = {".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime",
              ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
              ".webp": "image/webp", ".gif": "image/gif"}.get(ext)
        kw = {}
        if dl:
            kw["filename"] = os.path.basename(path)
        return FileResponse(path, media_type=mt, headers={
            "Accept-Ranges": "bytes", "Cache-Control": "public, max-age=86400"}, **kw)

    @api.get("/api/files")
    def _api_files(which: str = "out"):
        """文件库列表：缩略图 / 时长 / 尺寸 / 下载地址都在里面"""
        return lib_list(which)

    @api.get("/thumb")
    def _api_thumb(which: str = "out", name: str = ""):
        p = ensure_thumb(which, name)
        if not p:
            return Response(status_code=404)
        return FileResponse(p, media_type="image/jpeg",
                            headers={"Cache-Control": "public, max-age=604800"})

    @api.get("/")
    def _root():
        # 默认落到精简版（不依赖 SSE，抗代理掐连接）；Gradio 版挪到 /g
        return RedirectResponse(url="/s")

    demo.queue(default_concurrency_limit=4, max_size=32)
    app = gr.mount_gradio_app(api, demo, path="/g", allowed_paths=[OUT, TMP],
                              show_error=True, max_file_size="2gb", root_path="/g")
    uvicorn.run(app, host="0.0.0.0", port=7860, log_level="warning")
