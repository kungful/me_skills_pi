# -*- coding: utf-8 -*-
import json, os, sys, time, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
KEY = open(os.path.join(os.path.expanduser("~"), ".grsai_key")).read().strip()
HOST = "https://grsai.dakka.com.cn"

def post(path, payload):
    req = urllib.request.Request(HOST + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + KEY})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=180).read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        return {"HTTP": e.code, "body": e.read().decode("utf-8", "ignore")[:900]}

p = {"model": "gpt-image-2", "prompt": "a single red apple on a plain white table, flat children's book illustration",
     "aspectRatio": "1536x1024", "quality": "high", "webHook": "-1"}
r = post("/v1/draw/completions", p)
print("SUBMIT:", json.dumps(r, ensure_ascii=False)[:500])
tid = (r.get("data") or {}).get("id")
if not tid:
    sys.exit(1)
for i in range(50):
    d = (post("/v1/draw/result", {"id": tid}).get("data") or {})
    print("[%02d] %s %s%%  %s" % (i, d.get("status"), d.get("progress"), json.dumps(d, ensure_ascii=False)[:400]))
    if d.get("status") in ("succeeded", "failed"):
        break
    time.sleep(5)
