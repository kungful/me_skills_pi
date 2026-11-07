# -*- coding: utf-8 -*-
"""外部视觉模型审图（只做事实核对，不做审美判断）。
用法：python _审图.py 图1.png 图2.png ...  [--q "自定义问题"]
"""
import base64, importlib.util, io, json, os, sys, urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("kan", os.path.join(ROOT, "看爆款.py"))
K = importlib.util.module_from_spec(spec)
spec.loader.exec_module(K)

DEF = """这是一套少儿美术课件（4-6岁）要发小红书的图片。请你只做「事实核对」，不要评价好不好看。
按图片顺序逐张回答：
1) 有没有手/手指？如果有，手指数量对不对、有没有畸形、有没有多出一只手或一条手臂？
2) 画面里有没有出现文字/字母/数字？如果有，是不是乱码、错字、糊字？
3) 画面主体（画/物体）有没有崩坏、断裂、结构错乱、重复多余的部分？
4) 有没有别的明显 AI 瑕疵（多根线、器物融合、影子方向乱、边缘脏）？
每张最后给一个结论：[可用] 或 [不可用] + 一句话原因。
最后再给一个总的：这套图能不能直接发出去？"""


def main():
    argv = list(sys.argv[1:])
    q = DEF
    if "--q" in argv:
        i = argv.index("--q")
        q = argv[i + 1]
        del argv[i:i + 2]
    args = [a for a in argv if not a.startswith("--")]
    cfg = K.vcfg()
    if not cfg:
        sys.exit("没有可用视觉模型")
    base, key, model = cfg
    print("模型:", model)
    for p in args:
        print("·", os.path.basename(p))
    print("-" * 60)
    from PIL import Image
    content = [{"type": "text", "text": q}]
    for pth in args:
        im = Image.open(pth).convert("RGB")
        im.thumbnail((896, 896))
        b = io.BytesIO()
        im.save(b, "JPEG", quality=82)
        content.append({"type": "image_url", "image_url": {
            "url": "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()}})
    body = json.dumps({"model": model, "max_tokens": 8000,
                       "messages": [{"role": "user", "content": content}]}).encode()
    req = urllib.request.Request(base + "/chat/completions", data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + key,
        "Accept": "application/json", "User-Agent": K.UA})
    j = json.loads(urllib.request.urlopen(req, timeout=600).read().decode())
    m = j["choices"][0]["message"]
    print(m.get("content") or m.get("reasoning_content") or "(空回复)")


if __name__ == "__main__":
    main()
