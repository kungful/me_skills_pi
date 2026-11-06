#!/usr/bin/env bash
# 取官方 magpie-cli-android-arm64，改名成 libmagpie.so 放进 payload/。
#   bash tools/fetch-binary.sh                 取 latest
#   bash tools/fetch-binary.sh v0.1.2287       取指定 tag
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$ROOT/payload"
TAG="${1:-latest}"
if [ "$TAG" = "latest" ]; then
  URL="https://github.com/yetone/magpie-releases/releases/latest/download/magpie-cli-android-arm64"
else
  URL="https://github.com/yetone/magpie-releases/releases/download/$TAG/magpie-cli-android-arm64"
fi

echo "downloading $URL"
curl -fL --retry 3 -o "$ROOT/payload/libmagpie.so" "$URL"
chmod +x "$ROOT/payload/libmagpie.so"

SIZE=$(stat -c %s "$ROOT/payload/libmagpie.so" 2>/dev/null || wc -c <"$ROOT/payload/libmagpie.so")
echo "size: $SIZE"
python - "$ROOT/payload/libmagpie.so" <<'PY'
import sys
p = sys.argv[1]
head = open(p, "rb").read(20)
if head[:4] != b"\x7fELF":
    sys.exit("不是 ELF：下载可能拿到了 404 页面")
machine = int.from_bytes(head[18:20], "little")
if machine != 0xB7:
    sys.exit("不是 aarch64 (e_machine=%#x)" % machine)
print("OK: aarch64 ELF")
PY
sha256sum "$ROOT/payload/libmagpie.so" 2>/dev/null || sha256 "$ROOT/payload/libmagpie.so"
