#!/usr/bin/env python3
"""cdp.py - minimal Chrome DevTools Protocol client (pure stdlib, no pip installs).

Provides: headless Chrome launch with a reusable debugging session, page open/navigate,
Runtime.evaluate (the workhorse: probe elements, click them, scrape), real mouse clicks,
screenshots, back/forward, and clean shutdown.

Used by webbrowse.py's `browse` commands.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# --------------------------------------------------------------- websocket

class WSError(RuntimeError):
    pass


class WebSocket:
    """Tiny RFC6455 text-frame client. Enough for CDP on localhost."""

    def __init__(self, url: str, timeout: float = 30.0):
        if not url.startswith("ws://"):
            raise WSError(f"only ws:// supported, got {url!r}")
        rest = url[len("ws://"):]
        netloc, _, path = rest.partition("/")
        path = "/" + path
        host, _, port = netloc.partition(":")
        self.sock = socket.create_connection((host, int(port or 80)), timeout=timeout)
        self.sock.settimeout(timeout)
        self.buf = b""
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {netloc}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        self.sock.sendall(req.encode())
        head = self._read_until(b"\r\n\r\n")
        if b"101" not in head.split(b"\r\n")[0]:
            raise WSError(f"handshake failed: {head[:200]!r}")
        expect = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        ).decode()
        if expect.encode() not in head:
            raise WSError("bad Sec-WebSocket-Accept")

    def _read_until(self, marker: bytes) -> bytes:
        while marker not in self.buf:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise WSError("connection closed during handshake")
            self.buf += chunk
        idx = self.buf.index(marker) + len(marker)
        head, self.buf = self.buf[:idx], self.buf[idx:]
        return head

    def _read(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(max(65536, n - len(self.buf)))
            if not chunk:
                raise WSError("connection closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, text: str):
        payload = text.encode("utf-8")
        header = bytearray([0x81])
        n = len(payload)
        mask = os.urandom(4)
        if n < 126:
            header.append(0x80 | n)
        elif n < (1 << 16):
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        header += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    def recv(self) -> str:
        while True:
            b0, b1 = self._read(2)
            opcode = b0 & 0x0F
            masked = b1 & 0x80
            n = b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            mask = self._read(4) if masked else None
            data = self._read(n) if n else b""
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if opcode == 0x8:
                raise WSError("server closed the websocket")
            if opcode == 0x9:      # ping -> pong
                self.sock.sendall(bytes([0x8A, 0x80]) + os.urandom(4))
                continue
            if opcode in (0x1, 0x2):
                return data.decode("utf-8", "replace")

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


# --------------------------------------------------------------- CDP

class CDPError(RuntimeError):
    pass


class CDP:
    def __init__(self, ws_url: str, timeout: float = 30.0):
        self.ws = WebSocket(ws_url, timeout=timeout)
        self._id = 0
        self.events: list[dict] = []

    def call(self, method: str, params: dict | None = None, session: str | None = None,
             timeout: float = 30.0):
        self._id += 1
        msg_id = self._id
        msg = {"id": msg_id, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        self.ws.send(json.dumps(msg))
        deadline = time.time() + timeout
        while time.time() < deadline:
            raw = self.ws.recv()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == msg_id:
                if "error" in msg:
                    raise CDPError(f"{method}: {msg['error'].get('message')} "
                                   f"({msg['error'].get('type')})")
                return msg.get("result", {})
            if "method" in msg:
                self.events.append(msg)
                if len(self.events) > 4000:
                    del self.events[:2000]
        raise CDPError(f"timeout waiting for {method}")

    def wait_event(self, name: str, timeout: float = 15.0) -> dict | None:
        for ev in self.events:
            if ev.get("method") == name:
                return ev
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                msg = json.loads(self.ws.recv())
            except (WSError, json.JSONDecodeError):
                return None
            if msg.get("method") == name:
                return msg
            if "method" in msg:
                self.events.append(msg)
        return None

    def close(self):
        self.ws.close()


# --------------------------------------------------------------- browser session

CHROME_FLAGS = [
    "--headless=new",
    "--disable-gpu",
    "--no-sandbox",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "--disable-sync",
    "--disable-background-networking",
    "--disable-features=Translate,MediaRouter",
    "--hide-scrollbars",
    "--mute-audio",
    "--window-size=1440,1000",
]


def find_chrome() -> str | None:
    env = os.environ.get("WEB_BROWSE_CHROME")
    if env and os.path.exists(env):
        return env
    for name in ("chrome", "msedge", "chromium", "google-chrome", "chromium-browser"):
        p = shutil.which(name)
        if p:
            return p
    for c in [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"]:
        if os.path.exists(c):
            return c
    return None


def pid_alive(pid: int) -> bool:
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                             capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class Browser:
    """A long-lived headless Chrome that survives across CLI invocations."""

    def __init__(self, name: str = "default"):
        self.name = name
        root = os.path.join(tempfile.gettempdir(), "webbrowse-browse")
        os.makedirs(root, exist_ok=True)
        self.state_file = os.path.join(root, f"{name}.json")
        self.profile = os.path.join(root, f"{name}-profile")
        self.client: CDP | None = None
        self.port: int | None = None
        self.pid: int | None = None
        self.pages: dict[str, dict] = {}

    # -- lifecycle ------------------------------------------------------
    def load(self) -> bool:
        try:
            with open(self.state_file, encoding="utf-8") as f:
                st = json.load(f)
        except (OSError, json.JSONDecodeError):
            return False
        if not st.get("pid") or not pid_alive(int(st["pid"])):
            self.cleanup()
            return False
        self.port, self.pid, self.pages = st["port"], int(st["pid"]), st.get("pages", {})
        try:
            self.client = CDP(st["ws"], timeout=60)
            self.client.call("Browser.getVersion", timeout=10)
        except Exception:  # noqa: BLE001
            self.client = None
            self.cleanup()
            return False
        # sessionIds are per-websocket, so re-attach to the still-open targets
        for label, info in list(self.pages.items()):
            try:
                att = self.client.call("Target.attachToTarget",
                                       {"targetId": info["targetId"], "flatten": True})
                info["sessionId"] = att["sessionId"]
                for dom in ("Page", "Runtime", "Network"):
                    self.client.call(f"{dom}.enable", {}, info["sessionId"])
            except Exception:  # noqa: BLE001
                self.pages.pop(label, None)
        self.save()
        return True

    def save(self):
        if self.client is None or self.port is None:
            return
        version = self._http_json(f"http://127.0.0.1:{self.port}/json/version")
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump({"port": self.port, "pid": self.pid, "ws": version["webSocketDebuggerUrl"],
                       "pages": self.pages, "started": time.time()}, f)

    def start(self, fresh: bool = False):
        if fresh:
            self.cleanup()
        elif self.load():
            return
        chrome = find_chrome()
        if not chrome:
            raise CDPError("no Chrome/Edge/Chromium found; set WEB_BROWSE_CHROME")
        os.makedirs(self.profile, exist_ok=True)
        # DevToolsActivePort is written by Chrome itself -> no port guessing
        port_file = os.path.join(self.profile, "DevToolsActivePort")
        if os.path.exists(port_file):
            try:
                os.remove(port_file)
            except OSError:
                pass
        proc = subprocess.Popen(
            [chrome, *CHROME_FLAGS, "--remote-debugging-port=0",
             f"--user-data-dir={self.profile}", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.pid = proc.pid
        deadline = time.time() + 30
        while time.time() < deadline:
            if os.path.exists(port_file):
                try:
                    with open(port_file, encoding="utf-8") as f:
                        self.port = int(f.readline().strip())
                    break
                except (OSError, ValueError):
                    pass
            if proc.poll() is not None:
                raise CDPError(f"chrome exited immediately (code {proc.returncode})")
            time.sleep(0.25)
        if not self.port:
            raise CDPError("chrome did not report a debugging port")
        version = self._http_json(f"http://127.0.0.1:{self.port}/json/version")
        self.client = CDP(version["webSocketDebuggerUrl"], timeout=60)
        self.pages = {}
        # drop Chrome's own blank tab so probe() only sees our page
        try:
            for t in self.client.call("Target.getTargets")["targetInfos"]:
                if t["type"] == "page" and t["url"] in ("about:blank", "chrome://newtab/"):
                    self.client.call("Target.closeTarget", {"targetId": t["targetId"]})
        except Exception:  # noqa: BLE001
            pass
        self.save()

    @staticmethod
    def _http_json(url: str) -> dict:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read().decode("utf-8", "replace"))

    def cleanup(self):
        if self.client:
            try:
                self.client.call("Browser.close", timeout=5)
            except Exception:  # noqa: BLE001
                pass
            self.client.close()
            self.client = None
        if self.pid and pid_alive(self.pid):
            try:
                if os.name == "nt":
                    # /T = kill the whole process tree (renderer/utility children)
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.pid)],
                                   capture_output=True)
                else:
                    os.kill(self.pid, 9)
            except OSError:
                pass
        self.pid = self.port = None
        self.pages = {}
        for p in (self.state_file,):
            try:
                os.remove(p)
            except OSError:
                pass
        shutil.rmtree(self.profile, ignore_errors=True)

    # -- pages ----------------------------------------------------------
    def open(self, url: str, label: str = "main", wait: float = 3.0) -> str:
        """Create a tab, attach, navigate. Returns the CDP session id."""
        assert self.client
        target = self.client.call("Target.createTarget", {"url": "about:blank"})
        tid = target["targetId"]
        att = self.client.call("Target.attachToTarget", {"targetId": tid, "flatten": True})
        sid = att["sessionId"]
        self.client.call("Page.enable", {}, sid)
        self.client.call("Runtime.enable", {}, sid)
        self.client.call("Network.enable", {}, sid)
        self.pages[label] = {"targetId": tid, "sessionId": sid}
        self.save()
        self.goto(url, sid, wait)
        return sid

    def session(self, label: str | None) -> str:
        assert self.client
        if label and label in self.pages:
            return self.pages[label]["sessionId"]
        if "main" in self.pages:
            return self.pages["main"]["sessionId"]
        if self.pages:
            return next(iter(self.pages.values()))["sessionId"]
        raise CDPError("no page open yet - run:  webbrowse.py browse open <url>")

    def goto(self, url: str, sid: str, wait: float = 3.0):
        assert self.client
        if not url.startswith(("http://", "https://", "about:", "data:")):
            url = "https://" + url
        self.client.call("Page.navigate", {"url": url}, sid, timeout=60)
        self.wait_ready(sid, wait)

    def eval(self, sid: str, expression: str, await_promise: bool = False):
        assert self.client
        res = self.client.call("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": await_promise,
            "userGesture": True,
        }, sid, timeout=60)
        if res.get("exceptionDetails"):
            det = res["exceptionDetails"]
            desc = (det.get("exception") or {}).get("description") or det.get("text")
            raise CDPError(f"JS error: {desc}")
        return res.get("result", {}).get("value")

    def wait_ready(self, sid: str, wait: float = 3.0):
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                state = self.eval(sid, "document.readyState")
            except CDPError:
                time.sleep(0.3)
                continue
            if state in ("interactive", "complete"):
                break
            time.sleep(0.2)
        self.wait_settle(sid, quiet_ms=int(max(wait, 0.5) * 1000))

    def wait_settle(self, sid: str, quiet_ms: int = 1200, timeout: float = 20.0):
        """Wait until the DOM stops changing (SPAs keep mutating while loading)."""
        deadline = time.time() + timeout
        last, stable_since = None, time.time()
        while time.time() < deadline:
            try:
                sig = self.eval(sid, "document.documentElement.outerHTML.length + '|' + "
                                     "document.body.innerText.length")
            except CDPError:
                time.sleep(0.3)
                continue
            if sig == last:
                if (time.time() - stable_since) * 1000 >= quiet_ms:
                    return
            else:
                last, stable_since = sig, time.time()
            time.sleep(0.3)

    def info(self, sid: str) -> dict:
        return {
            "url": self.eval(sid, "location.href"),
            "title": self.eval(sid, "document.title"),
        }

    def html(self, sid: str) -> str:
        return self.eval(sid, "document.documentElement.outerHTML") or ""

    def click_xy(self, sid: str, x: float, y: float):
        for ev in ("mousePressed", "mouseReleased"):
            self.client.call("Input.dispatchMouseEvent", {
                "type": ev, "x": x, "y": y, "button": "left", "clickCount": 1}, sid)

    def mouse_click_selector(self, sid: str, selector: str):
        box = self.eval(sid, f"""(() => {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) return null;
            el.scrollIntoView({{block:'center', inline:'center'}});
            const r = el.getBoundingClientRect();
            return {{x: r.left + r.width/2, y: r.top + r.height/2, w: r.width, h: r.height}};
        }})()""")
        if not box:
            raise CDPError(f"no element matches {selector!r}")
        if box["w"] == 0 or box["h"] == 0:
            raise CDPError(f"element {selector!r} has zero size (hidden?)")
        self.click_xy(sid, box["x"], box["y"])

    def screenshot(self, sid: str, path: str, full_page: bool = False):
        assert self.client
        params = {"format": "png"}
        if full_page:
            params["captureBeyondViewport"] = True
        data = self.client.call("Page.captureScreenshot", params, sid, timeout=60)["data"]
        with open(path, "wb") as f:
            f.write(base64.b64decode(data))
        return path

    def scroll(self, sid: str, y: int | None = None, pages: float = 0.0):
        if y is not None:
            self.eval(sid, f"window.scrollTo(0,{int(y)})")
        else:
            self.eval(sid, f"window.scrollBy(0,{int(pages * window.innerHeight)})")
        time.sleep(0.4)
        self.wait_settle(sid, quiet_ms=800, timeout=10)

    def history(self, sid: str, back: bool = True):
        self.eval(sid, "history.go(-1)" if back else "history.go(1)")
        time.sleep(0.5)
        self.wait_ready(sid, 1.5)