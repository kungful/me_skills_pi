#!/usr/bin/env bash
# 「棚架受力分析」—— 只靠 Android SDK build-tools 打包（无 Gradle、不联网）。
#   bash build.sh          只打包
#   bash build.sh -i       打包 + 装到手机 + 启动
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [ -z "${ANDROID_HOME:-}" ]; then
  SDK="$(cygpath -u "${LOCALAPPDATA}" 2>/dev/null || echo "${LOCALAPPDATA}")/Android/Sdk"
  SDK="${SDK//\\//}"
else
  SDK="$ANDROID_HOME"
fi
BT="$SDK/build-tools/36.0.0"
[ -d "$BT" ] || BT="$(ls -d "$SDK"/build-tools/* | sort -V | tail -1)"
if [ -f "$SDK/platforms/android-36/android.jar" ]; then
  PLATFORM="$SDK/platforms/android-36/android.jar"
else
  PLATFORM="$(ls -d "$SDK"/platforms/android-3[4-9]/android.jar 2>/dev/null | sort -V | tail -1)"
fi
AAPT2="$BT/aapt2.exe"; ZIPALIGN="$BT/zipalign.exe"; D8="$BT/d8.bat"
ADB="${ADB:-$LOCALAPPDATA/Android/Sdk/platform-tools/adb.exe}"

JDK21="$(ls -d "$HOME"/.gradle/jdks/eclipse_adoptium-21-* 2>/dev/null | head -1)"
if [ -n "$JDK21" ]; then
  export JAVA_HOME="$(cygpath -w "$JDK21")"
  JAVA_BIN="$JDK21/bin/java.exe"
  JAVAC="${JAVAC:-$JDK21/bin/javac.exe}"
  KEYTOOL="${KEYTOOL:-$JDK21/bin/keytool.exe}"
else
  JAVA_BIN="${JAVA_BIN:-java}"
  JAVAC="${JAVAC:-javac}"; KEYTOOL="${KEYTOOL:-keytool}"
fi
APKSIGNER_JAR="$BT/lib/apksigner.jar"
[ -f "$APKSIGNER_JAR" ] || APKSIGNER_JAR="$BT/apksigner.jar"
sign() { "$JAVA_BIN" -jar "$APKSIGNER_JAR" "$@"; }

echo "JAVA_HOME   : ${JAVA_HOME:-<系统默认>}"
echo "platform    : $PLATFORM"
echo "build-tools : $BT"

if [ ! -f res/mipmap-xxhdpi/ic_launcher.png ]; then
  python tools/make_icon.py
fi

OUT="build"; APK="棚架受力分析.apk"
rm -rf "$OUT"; mkdir -p "$OUT/classes" "$OUT/dex" "$OUT/gen"

if command -v node >/dev/null 2>&1; then
  node tools/selftest.js || { echo "✗ 力学自测没过，中止" >&2; exit 1; }
else
  echo "· 没装 node，跳过力学自测"
fi

"$AAPT2" compile --dir res -o "$OUT/res.zip"
"$AAPT2" link \
  -o "$OUT/base.apk" \
  -I "$PLATFORM" \
  -A assets \
  --manifest AndroidManifest.xml \
  -R "$OUT/res.zip" \
  --java "$OUT/gen" \
  --min-sdk-version 29 \
  --target-sdk-version 34 \
  --version-code 1 --version-name 1.0 \
  --auto-add-overlay

mapfile -t SRC < <(find src -name '*.java')
"$JAVAC" --release 11 -encoding UTF-8 -nowarn -Xlint:-options \
  -classpath "$PLATFORM" -d "$OUT/classes" "${SRC[@]}"

python - "$OUT/classes" "$OUT/classes.jar" <<'PY'
import os, sys, zipfile
src, dst = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
    for root, _d, files in os.walk(src):
        for f in files:
            if f.endswith(".class"):
                full = os.path.join(root, f)
                z.write(full, os.path.relpath(full, src).replace(os.sep, "/"))
PY

"$D8" --release --min-api 29 --lib "$PLATFORM" --output "$OUT/dex" "$OUT/classes.jar"

python - "$OUT/base.apk" "$OUT/dex/classes.dex" "$OUT/unsigned.apk" <<'PY'
import shutil, sys, zipfile
src, dex, dst = sys.argv[1], sys.argv[2], sys.argv[3]
shutil.copyfile(src, dst)
with zipfile.ZipFile(dst, "a", zipfile.ZIP_DEFLATED) as z:
    z.write(dex, "classes.dex")
PY

"$ZIPALIGN" -f -p 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"

KS="$ROOT/debug.keystore"
if [ ! -f "$KS" ]; then
  "$KEYTOOL" -genkeypair -keystore "$KS" -alias canopystruct -keyalg RSA -keysize 2048 \
    -validity 10000 -storepass android -keypass android \
    -dname "CN=CanopyStruct,O=Hua,C=CN" >/dev/null
fi
# 别把临时变量叫 TMP/TEMP（apksigner 会把它当临时目录建目录 → 拒绝访问）
SIGNED_PKG="$OUT/pkg-signed.apk"
rm -rf "$SIGNED_PKG"
sign sign --ks "$KS" --ks-pass pass:android --key-pass pass:android \
  --v1-signing-enabled true --v2-signing-enabled true \
  --out "$SIGNED_PKG" "$OUT/aligned.apk"
[ -f "$SIGNED_PKG" ] || { echo "✗ 签名没产出文件" >&2; exit 1; }
rm -f "$ROOT/$APK"
mv -f "$SIGNED_PKG" "$ROOT/$APK"
sign verify --print-certs "$ROOT/$APK" | head -3 || true

mkdir -p dist
rm -f "dist/$APK"
cp -f "$ROOT/$APK" "dist/$APK"

python - "$ROOT/$APK" <<'PY'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
names = z.namelist()
need = ["assets/index.html", "assets/app.js", "assets/style.css", "assets/solver.js",
        "assets/three.min.js", "classes.dex"]
print("APK 内文件数:", len(names))
print("缺失:", [n for n in need if n not in names] or "无")
for n in need:
    if n in names: print("   %-26s %9d B" % (n, z.getinfo(n).file_size))
PY

ls -la "$ROOT/$APK"
echo "OK -> $ROOT/$APK"

case "${1:-}" in
  -i|--install)
    "$ADB" install -r -g "$ROOT/$APK"
    "$ADB" shell am start -n com.hua.canopystruct/.MainActivity >/dev/null
    echo "已启动 棚架受力分析"
    ;;
esac
