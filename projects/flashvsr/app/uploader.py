#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FlashVSR+ 分片续传上传台（端口 7861）

为什么需要它：仙宫云的公网 HTTP 代理对 7860 的吞吐只有 ~0.3 MB/s，而且**单次请求时间过长
会被掐断**——Gradio 自带的一整块 multipart 上传，传几十 MB 的片子就会返回空 body，
浏览器报 `Unexpected end of JSON input`。

这里把文件切成 2 MB 一片，一片一个请求（每片几秒），断了就重试，重试还不行刷新页面从
已上传的偏移继续，不丢字节。

用法：浏览器打开 https://<实例ID>-7861.container.x-gpu.com/
上传完去 7860 的 WebUI，点「刷新列表」选中它即可。
"""
import json
import os
import re
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

UP = "/root/uploads"
PORT = 7861
FILENAME_OK = re.compile(r"^[^/\\\x00]{1,180}$")
_locals = {}
_glock = threading.Lock()

PAGE = """<!doctype html>
<html lang="zh"><head><meta charset="utf-8"><title>FlashVSR+ 上传台</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
 :root{color-scheme:dark}
 body{margin:0;background:#0f1115;color:#e6e6e6;font:15px/1.6 system-ui,"Microsoft YaHei",sans-serif;
      display:flex;justify-content:center;padding:40px 16px}
 .card{width:100%;max-width:760px}
 h1{font-size:20px;margin:0 0 6px}
 .sub{color:#8b95a5;font-size:13px;margin-bottom:22px}
 #drop{border:2px dashed #2c3441;border-radius:14px;padding:46px 20px;text-align:center;
       background:#151922;transition:.15s;cursor:pointer}
 #drop.hot{border-color:#4f8cff;background:#182031}
 .btn{display:inline-block;background:#2a6ff5;color:#fff;border:0;border-radius:9px;
      padding:10px 18px;font-size:14px;cursor:pointer}
 .btn:disabled{background:#333c4a;cursor:default}
 .row{margin-top:20px}
 .bar{height:12px;background:#1c222d;border-radius:99px;overflow:hidden}
 .bar>i{display:block;height:100%;width:0;background:linear-gradient(90deg,#2a6ff5,#5ad1ff);
        transition:width .2s}
 .meta{display:flex;justify-content:space-between;color:#8b95a5;font-size:13px;margin-top:8px}
 ul{list-style:none;padding:0;margin:8px 0 0}
 li{display:flex;justify-content:space-between;padding:9px 12px;background:#151922;
    border-radius:9px;margin-bottom:6px;font-size:13px}
 li span:last-child{color:#8b95a5}
 code{background:#1c222d;padding:2px 6px;border-radius:5px}
</style></head><body><div class="card">
 <h1>FlashVSR+ 分片续传上传台</h1>
 <div class="sub">切成 2 MB 一片、每片一个短请求，断了自动重试、刷新页面可续传。
   传完去 <a href="/" style="color:#5ad1ff">WebUI</a>
   点「刷新列表」选中它。</div>
 <div id="drop">拖视频到这里，或点击选择文件<br><span class="sub">建议 ≤ 2 GB</span>
   <input id="file" type="file" accept="video/*" hidden></div>
 <div class="row">
   <div class="bar"><i id="bar"></i></div>
   <div class="meta"><span id="state">待上传</span><span id="speed"></span></div>
 </div>
 <div class="row"><b>服务器 /root/uploads 里已有的文件</b><ul id="list"></ul></div>
</div>
<script>
const BASE = '/up', CHUNK = 2 * 1024 * 1024, RETRY = 8;
const $ = id => document.getElementById(id);
const sleep = ms => new Promise(r => setTimeout(r, ms));
const fmt = n => n > 1e9 ? (n/1e9).toFixed(2)+' GB' : n > 1e6 ? (n/1e6).toFixed(1)+' MB' : (n/1e3).toFixed(0)+' KB';

async function refresh() {
  try {
    const r = await fetch(BASE + '/list'); const j = await r.json();
    $('list').innerHTML = j.files.length
      ? j.files.map(f => `<li><span>${f.name}</span><span>${fmt(f.size)}</span></li>`).join('')
      : '<li><span>（空）</span></li>';
  } catch (e) {}
}
refresh();

const drop = $('drop'), input = $('file');
drop.onclick = () => input.click();
input.onchange = () => input.files[0] && upload(input.files[0]);
['dragenter','dragover'].forEach(e => drop.addEventListener(e, ev => {
  ev.preventDefault(); drop.classList.add('hot'); }));
['dragleave','drop'].forEach(e => drop.addEventListener(e, ev => {
  ev.preventDefault(); drop.classList.remove('hot'); }));
drop.addEventListener('drop', ev => {
  const f = ev.dataTransfer.files[0]; if (f) upload(f); });

async function upload(file) {
  const name = file.name;
  $('state').textContent = '检查断点…';
  let off = 0;
  try {
    const r = await fetch(BASE + '/status?name=' + encodeURIComponent(name));
    const j = await r.json();
    if (j.size > 0 && j.size <= file.size) off = j.size;
  } catch (e) {}
  const t0 = Date.now(), startOff = off;
  while (off < file.size) {
    const end = Math.min(off + CHUNK, file.size);
    let ok = false;
    for (let i = 0; i < RETRY && !ok; i++) {
      try {
        const r = await fetch(BASE + '/chunk?name=' + encodeURIComponent(name) + '&off=' + off,
                              { method: 'PUT', body: file.slice(off, end) });
        if (r.ok) { const j = await r.json(); off = j.size; ok = true; }
        else { $('state').textContent = '片失败 HTTP ' + r.status + '，重试 ' + (i+1); }
      } catch (e) { $('state').textContent = '网络抖动，重试 ' + (i+1); }
      if (!ok) await sleep(800 * (i + 1));
    }
    if (!ok) { $('state').textContent = '中断，刷新页面可从这里续传（已传 ' + fmt(off) + '）'; return; }
    const pct = off / file.size * 100;
    $('bar').style.width = pct.toFixed(1) + '%';
    $('state').textContent = fmt(off) + ' / ' + fmt(file.size) + '（' + pct.toFixed(1) + '%）';
    const sp = (off - startOff) / 1e6 / ((Date.now() - t0) / 1000);
    $('speed').textContent = sp.toFixed(2) + ' MB/s';
  }
  $('state').textContent = '✅ 上传完成：/root/uploads/' + name;
  $('bar').style.width = '100%';
  refresh();
}
</script></body></html>"""


def safe_name(q):
    name = unquote(q.get("name", [""])[0])
    name = os.path.basename(name)
    if not FILENAME_OK.match(name) or name in (".", ".."):
        raise ValueError("bad name")
    return name


def lock_for(path):
    with _glock:
        return _locals.setdefault(path, threading.Lock())


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "FlashVSRUploader/1.0"

    def log_message(self, fmt, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/", "/index.html"):
            b = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
            return
        if u.path == "/list":
            files = []
            try:
                for n in sorted(os.listdir(UP)):
                    p = os.path.join(UP, n)
                    if os.path.isfile(p):
                        files.append({"name": n, "size": os.path.getsize(p)})
            except Exception:
                pass
            return self._json({"files": files})
        if u.path == "/status":
            try:
                p = os.path.join(UP, safe_name(q))
            except ValueError:
                return self._json({"error": "bad name"}, 400)
            return self._json({"size": os.path.getsize(p) if os.path.exists(p) else 0})
        self._json({"error": "not found"}, 404)

    def do_PUT(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path != "/chunk":
            return self._json({"error": "not found"}, 404)
        try:
            name = safe_name(q)
            off = int(q.get("off", ["0"])[0])
            n = int(self.headers.get("Content-Length") or 0)
        except Exception as e:
            return self._json({"error": repr(e)}, 400)
        os.makedirs(UP, exist_ok=True)
        p = os.path.join(UP, name)
        lk = lock_for(p)
        with lk:
            cur = os.path.getsize(p) if os.path.exists(p) else 0
            if off > cur:
                return self._json({"error": "offset gap", "size": cur}, 409)
            if off < cur:                      # 重复片，直接忽略
                self.rfile.read(n)
                return self._json({"ok": True, "size": cur, "dup": True})
            mode = "r+b" if os.path.exists(p) else "wb"
            with open(p, mode) as f:
                f.seek(off)
                left = n
                while left > 0:
                    b = self.rfile.read(min(1 << 20, left))
                    if not b:
                        break
                    f.write(b)
                    left -= len(b)
                f.flush()
                os.fsync(f.fileno())
            return self._json({"ok": True, "size": os.path.getsize(p)})


# ---------------------------------------------------------------- 可复用核心
def up_list():
    files = []
    VG = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".flv", ".ts", ".mxf")
    try:
        for n in sorted(os.listdir(UP)):
            p = os.path.join(UP, n)
            if os.path.isfile(p):
                files.append({"name": n, "size": os.path.getsize(p),
                              "kind": "video" if n.lower().endswith(VG) else "other"})
    except Exception:
        pass
    return {"files": files}


def up_status(name):
    try:
        p = os.path.join(UP, safe_name({"name": [name]}))
    except ValueError:
        return {"error": "bad name"}
    return {"size": os.path.getsize(p) if os.path.exists(p) else 0}


def up_chunk(name, off, data):
    """把 data 写到 /root/uploads/name 的 off 偏移；返回 {ok, size}"""
    p = os.path.join(UP, safe_name({"name": [name]}))
    os.makedirs(UP, exist_ok=True)
    with lock_for(p):
        cur = os.path.getsize(p) if os.path.exists(p) else 0
        if off > cur:
            return {"error": "offset gap", "size": cur}
        if off < cur:
            return {"ok": True, "size": cur, "dup": True}
        mode = "r+b" if os.path.exists(p) else "wb"
        with open(p, mode) as f:
            f.seek(off)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        return {"ok": True, "size": os.path.getsize(p)}


if __name__ == "__main__":
    os.makedirs(UP, exist_ok=True)
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), H)
    print("uploader on 0.0.0.0:%d -> %s" % (PORT, UP), flush=True)
    srv.serve_forever()
