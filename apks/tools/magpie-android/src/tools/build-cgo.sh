#!/usr/bin/env bash
# 用 Go + Android NDK 编一个带 cgo 的 android/arm64 版 magpie，替换 payload/libmagpie.so。
#
# 为什么必须 cgo：官方 release 的 magpie-cli-android-arm64 是 CGO_ENABLED=0 编的，
# Go 的纯 Go 解析器在 Android 上解析不了域名（net/conf.go: "DNS requests don't work on
# Android"，issue #10714 —— 它要读 /etc/resolv.conf，Android 没有）。
# 开了 cgo 才走 bionic 的 getaddrinfo，DNS 才正常。
#
#   bash tools/build-cgo.sh                 # 用默认工具链路径
#   GO=... NDK=... bash tools/build-cgo.sh  # 自定义
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO_BIN="${GO:-/c/mbuild/toolchain/go/go/bin}"
NDK="${NDK:-/c/mbuild/toolchain/ndk/android-ndk-r28c}"
SRC="${SRC:-/tmp/magpie-src}"
API="${API:-26}"

export PATH="$GO_BIN:$PATH"
export GOTOOLCHAIN=local
export GOPROXY="${GOPROXY:-https://goproxy.cn,direct}"
export GOSUMDB="${GOSUMDB:-sum.golang.google.cn}"
export CGO_ENABLED=1 GOOS=android GOARCH=arm64
export CC="$NDK/toolchains/llvm/prebuilt/windows-x86_64/bin/aarch64-linux-android${API}-clang.cmd"

[ -d "$SRC" ] || { echo "先 clone 源码: git clone --depth 1 https://github.com/yetone/magpie.git $SRC" >&2; exit 1; }
[ -x "$GO_BIN/go.exe" ] || { echo "没找到 go: $GO_BIN" >&2; exit 1; }
[ -f "$CC" ] || { echo "没找到 NDK clang: $CC" >&2; exit 1; }

echo "go          : $($GO_BIN/go.exe version)"
echo "cc          : $CC"
echo "src         : $SRC"

cd "$SRC"
"$GO_BIN/go.exe" mod download
"$GO_BIN/go.exe" build -tags nogui -trimpath -ldflags="-s -w" -o "$ROOT/payload/libmagpie.so" .
chmod +x "$ROOT/payload/libmagpie.so"

python - "$ROOT/payload/libmagpie.so" <<'PY'
import sys, struct
p = sys.argv[1]
d = open(p, "rb").read()
assert d[:4] == b"\x7fELF", "不是 ELF"
assert struct.unpack_from("<H", d, 18)[0] == 0xB7, "不是 aarch64"
print("OK aarch64 ELF, %.1f MB, getaddrinfo=%s libc=%s" % (
    len(d) / 1048576, d.find(b"getaddrinfo") > 0, d.find(b"libc.so") > 0))
PY

echo "好了：payload/libmagpie.so 已是 cgo(NDK) 版，接着跑 bash build.sh 重新打包"
