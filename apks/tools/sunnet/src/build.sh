#!/usr/bin/env bash
# 只靠 Android SDK build-tools 打出 SunNet.apk（不用 Gradle、不联网）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# ---- 找 SDK -----------------------------------------------------------------
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
AAPT2="$BT/aapt2.exe"; ZIPALIGN="$BT/zipalign.exe"; APKSIGNER="$BT/apksigner.bat"; D8="$BT/d8.bat"
JAVAC="${JAVAC:-javac}"; KEYTOOL="${KEYTOOL:-keytool}"
for cand in "/c/Program Files/Java/jdk-24/bin/keytool.exe" \
            "/c/Program Files/Android/Android Studio/jbr/bin/keytool.exe" \
            "/c/Program Files/Common Files/Oracle/Java/javapath/keytool.exe"; do
  if ! command -v "$KEYTOOL" >/dev/null 2>&1 && [ -x "$cand" ]; then KEYTOOL="$cand"; fi
done

echo "SDK         : $SDK"
echo "platform    : $PLATFORM"
echo "build-tools : $BT"

# ---- 图标 -------------------------------------------------------------------
if [ ! -f res/mipmap-xxhdpi/ic_launcher.png ]; then
  python tools/make_icon.py
fi

OUT="build"; APK="SunNet.apk"
rm -rf "$OUT"; mkdir -p "$OUT/classes" "$OUT/dex" "$OUT/gen"

# ---- 资源 + 资产 -------------------------------------------------------------
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

# ---- Java（javac 编译 → jar → d8 dex）---------------------------------------
mapfile -t SRC < <(find src -name '*.java')
"$JAVAC" --release 11 -encoding UTF-8 -nowarn -Xlint:-options \
  -classpath "$PLATFORM" -d "$OUT/classes" "${SRC[@]}"

python - "$OUT/classes" "$OUT/classes.jar" <<'PY'
import os, sys, zipfile
src, dst = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
    for root, _dirs, files in os.walk(src):
        for f in files:
            if f.endswith(".class"):
                full = os.path.join(root, f)
                z.write(full, os.path.relpath(full, src).replace(os.sep, "/"))
PY

"$D8" --release --min-api 29 --lib "$PLATFORM" --output "$OUT/dex" "$OUT/classes.jar"

# ---- 打包 + 对齐 + 签名 ------------------------------------------------------
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
  "$KEYTOOL" -genkeypair -keystore "$KS" -alias sunnet -keyalg RSA -keysize 2048 \
    -validity 10000 -storepass android -keypass android \
    -dname "CN=SunNet,O=Hua,C=CN" >/dev/null
fi
"$APKSIGNER" sign --ks "$KS" --ks-pass pass:android --key-pass pass:android \
  --v1-signing-enabled true --v2-signing-enabled true \
  --out "$ROOT/$APK" "$OUT/aligned.apk"
"$APKSIGNER" verify --print-certs "$ROOT/$APK" | head -4

python - "$ROOT/$APK" <<'PY'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
names = z.namelist()
need = ["assets/index.html", "assets/app.js", "assets/style.css", "assets/transport.js", "classes.dex"]
print("APK 内文件数:", len(names))
print("缺失:", [n for n in need if n not in names] or "无")
PY

ls -la "$ROOT/$APK"
echo "OK -> $ROOT/$APK"
