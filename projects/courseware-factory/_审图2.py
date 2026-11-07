# -*- coding: utf-8 -*-
"""_审图2.py —— 短问法审图，只输出一行结论。用法：python _审图2.py 图.png [图.png ...]"""
import base64
import importlib.util
import io
import json
import os
import re
import sys
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("kan", os.path.join(ROOT, "看爆款.py"))
K = importlib.util.module_from_spec(spec)
spec.loader.exec_module(K)

Q = ("这是4-6岁少儿美术课件要发小红书的封面图，请只做事实核对。逐条回答，每条不超过18个字：\n"
     "1) 图里有几只手？手指有没有畸形、粘连、多指、多出手臂？\n"
     "2) 画面里有没有文字、字母、数字？有没有乱码糊字？\n"
     "3) 画面主体有没有崩坏、断裂、重复多余、器物融合？\n"
     "4) 还有别的明显AI瑕疵吗？\n"
     "最后单独一行，只写 [可用] 或 [不可用]。")


def one(base, key, model, pth):
    from PIL import Image
    im = Image.open(pth).convert("RGB")
    im.thumbnail((896, 896))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=82)
    content = [{"type": "text", "text": Q},
               {"type": "image_url", "image_url": {
                   "url": "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()}}]
    body = json.dumps({"model": model, "max_tokens": 16000,
                       "messages": [{"role": "user", "content": content}]}).encode()
    req = urllib.request.Request(base + "/chat/completions", data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + key,
        "Accept": "application/json", "User-Agent": K.UA})
    j = json.loads(urllib.request.urlopen(req, timeout=900).read().decode())
    m = j["choices"][0]["message"]
    txt = (m.get("content") or "").strip()
    if not txt:
        txt = (m.get("reasoning_content") or "").strip()
    return txt


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cfg = K.vcfg()
    if not cfg:
        sys.exit("没有可用视觉模型")
    base, key, model = cfg
    for pth in args:
        name = os.path.basename(os.path.dirname(pth)) + "/" + os.path.basename(pth)
        try:
            txt = one(base, key, model, pth)
        except Exception as e:
            print("%-28s [取数失败] %s" % (name, str(e)[:60]), flush=True)
            continue
        hits = re.findall(r"\[(可用|不可用)\]", txt)
        verdict = ("[%s]" % hits[-1]) if hits else "[未解析]"
        # 抓几条关键短句
        short = [s.strip() for s in re.split(r"[\n。]", txt)
                 if s.strip() and not s.strip().startswith(("我们", "但", "如果", "也许", "等等", "让我"))]
        trace = " | ".join(short[:5])[:300]
        print("%-28s %s   %s" % (name, verdict, trace), flush=True)


if __name__ == "__main__":
    main()
