"""Web 看板（Flask）"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict

from flask import Flask, jsonify, redirect, request, send_from_directory
from urllib.parse import quote

from . import db
from . import hub
from .config import REPORT_DIR, sources_cfg
from .collectors import all_names

app = Flask(__name__)

_run_lock = threading.Lock()
_run_state: Dict[str, Any] = {"running": False, "log": [], "started": "", "finished": ""}


def _log(msg: str) -> None:
    _run_state["log"].append(f"{time.strftime('%H:%M:%S')} {msg}")
    _run_state["log"] = _run_state["log"][-200:]


@app.route("/")
def index():
    f = REPORT_DIR / "index.html"
    if not f.exists():
        return redirect("/api/topics")
    return send_from_directory(REPORT_DIR, "index.html")


@app.route("/report/<path:name>")
def report_file(name: str):
    return send_from_directory(REPORT_DIR, name)


@app.route("/reports")
def reports_index():
    rows = "".join(
        f'<li><a href="/report/{quote(n)}">{n}</a></li>'
        for n in sorted((p.name for p in REPORT_DIR.iterdir() if p.is_file()), reverse=True)
    )
    return (
        "<meta charset='utf-8'><h3>需求雷达 · 历史报告</h3>"
        f"<ul style='line-height:1.9;font-family:system-ui'>{rows}</ul>"
        "<p><a href='/'>← 回看板</a></p>"
    )


@app.route("/api/stats")
def api_stats():
    con = db.connect()
    return jsonify(db.stats(con))


@app.route("/api/topics")
def api_topics():
    con = db.connect()
    limit = int(request.args.get("limit", 60))
    topics = db.load_topics(con, limit)
    for t in topics:
        t["evidence"] = []
        if request.args.get("with_evidence", "1") == "1":
            t["evidence"] = [dict(r) for r in db.topic_evidence(con, t["id"], 6)]
    return jsonify({"count": len(topics), "topics": topics})


@app.route("/api/items")
def api_items():
    con = db.connect()
    limit = min(500, int(request.args.get("limit", 100)))
    src = request.args.get("source")
    where, params = "1=1", ()
    if src:
        where, params = "source=?", (src,)
    rows = db.fetch_items(con, where, params, limit)
    return jsonify({"count": len(rows), "items": [dict(r) for r in rows]})


@app.route("/api/sources")
def api_sources():
    cfg = (sources_cfg().get("sources") or {})
    return jsonify({n: {"enabled": bool((cfg.get(n) or {}).get("enabled")),
                        "weight": (cfg.get(n) or {}).get("weight")} for n in all_names()})


@app.route("/api/phone")
def api_phone():
    return jsonify(hub.phone_status())


@app.route("/api/run", methods=["POST", "GET"])
def api_run():
    if _run_state["running"]:
        return jsonify({"ok": False, "msg": "任务正在运行", "state": _run_state})
    only = request.args.get("only")
    only_list = only.split(",") if only else None
    if request.args.get("collect", "1") != "1":
        only_list = []

    def job():
        _run_state.update({"running": True, "log": [], "started": time.strftime("%H:%M:%S"), "finished": ""})
        try:
            if only_list != []:
                _log("开始采集…")
                hub.collect(only_list, quiet=True)
                _log("采集完成")
            _log("开始分析…")
            topics = hub.analyze(quiet=True)
            from . import report as rp

            files = rp.write_reports(topics)
            _log(f"分析完成：{len(topics)} 个主题")
            _run_state["files"] = files
        except Exception as e:  # noqa: BLE001
            _log(f"出错：{type(e).__name__}: {e}")
        finally:
            _run_state["running"] = False
            _run_state["finished"] = time.strftime("%H:%M:%S")

    threading.Thread(target=job, daemon=True).start()
    return jsonify({"ok": True, "msg": "已启动"})


@app.route("/api/runstate")
def api_runstate():
    return jsonify(_run_state)


def main(port: int = 8787, host: str = "127.0.0.1") -> None:
    app.run(host=host, port=port, debug=False, threaded=True)
