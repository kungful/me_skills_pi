#!/usr/bin/env bash
# 端到端交互测试：把 assets 拷到临时目录，用无头 Chrome 真点一遍界面，读回断言结果。
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${TMPDIR:-/tmp}/trigmech-e2e"
CHROME="${CHROME:-/c/Program Files/Google/Chrome/Application/chrome.exe}"
[ -x "$CHROME" ] || CHROME="$(command -v google-chrome || command -v chromium || true)"
rm -rf "$WORK"; mkdir -p "$WORK"
cp -r "$ROOT/app/assets/." "$WORK/"
cp "$ROOT/tool/e2e.html" "$WORK/"
URL="file:///$(cd "$WORK" && pwd -W 2>/dev/null || pwd)/e2e.html"
"$CHROME" --headless=new --disable-gpu --no-sandbox --allow-file-access-from-files \
  --user-data-dir="$WORK/profile" --window-size=600,1200 --virtual-time-budget=15000 \
  --dump-dom "$URL" 2>/dev/null |
python -c "
import sys, re, html
s = sys.stdin.read()
m = re.search(r'<pre id=\"out\">([\s\S]*?)</pre>', s)
if not m:
    print('拿不到测试输出（Chrome 路径对吗？）'); sys.exit(1)
out = html.unescape(m.group(1))
lines = [l for l in out.splitlines() if l.strip()]
bad = [l for l in lines if not l.startswith('PASS')]
for l in bad: print(l)
print(('[OK] 端到端 %d 项全部通过' % len(lines)) if not bad else ('[FAIL] %d / %d 项失败' % (len(bad), len(lines))))
sys.exit(1 if bad else 0)
"
