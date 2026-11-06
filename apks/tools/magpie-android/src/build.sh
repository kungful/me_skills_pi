#!/usr/bin/env bash
# 只靠 Android SDK build-tools 打 Magpie 手机版 APK（不用 Gradle、不联网编译）。
#   bash build.sh            只打包
#   bash build.sh -i         打包 + 装到手机 + 启动
#
# 关键：magpie 的 Go 二进制放在 lib/arm64-v8a/libmagpie.so，应用里从
# nativeLibraryDir 直接 exec（Android 10+ 只允许执行那里面的可执行文件，
# 所以 manifest 里 extractNativeLibs 必须是 true）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# ---- SDK / build-tools ------------------------------------------------------
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
ADB="${ADB:-$SDK/platform-tools/adb.exe}"

# JDK：系统 java 可能是 24，apksigner 在 24 上会崩 → 优先用 Gradle 下载的 21
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

echo "SDK         : $SDK"
echo "platform    : $PLATFORM"
echo "build-tools : $BT"

# ---- 图标 + 二进制 -----------------------------------------------------------
if [ ! -f res/mipmap-xxhdpi/ic_launcher.png ]; then
  python tools/make_icon.py
fi
if [ ! -f payload/libmagpie.so ]; then
  echo "payload/libmagpie.so 不存在，先跑 bash tools/fetch-binary.sh" >&2
  exit 1
fi
PAYLOAD_SIZE=$(wc -c <payload/libmagpie.so)
echo "payload     : $((PAYLOAD_SIZE/1048576)) MB"

OUT="build"; APK="Magpie.apk"
rm -rf "$OUT"; mkdir -p "$OUT/classes" "$OUT/dex" "$OUT/gen"

# ---- 资源 -------------------------------------------------------------------
if [ -f res/mipmap-xxhdpi/ic_launcher.png ]; then
  "$AAPT2" compile --dir res -o "$OUT/res.zip"
  "$AAPT2" link \
    -o "$OUT/base.apk" \
    -I "$PLATFORM" \
    --manifest AndroidManifest.xml \
    -R "$OUT/res.zip" \
    --java "$OUT/gen" \
    --min-sdk-version 26 \
    --target-sdk-version 28 \
    --version-code 8 --version-name 1.7 --auto-add-overlay
else
  echo "缺图标" >&2; exit 1
fi

# ---- Java → dex -------------------------------------------------------------
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

"$D8" --release --min-api 26 --lib "$PLATFORM" --output "$OUT/dex" "$OUT/classes.jar"

# ---- 打进 dex + Go 二进制 ----------------------------------------------------
python - "$OUT/base.apk" "$OUT/dex/classes.dex" "payload/libmagpie.so" "$OUT/unsigned.apk" <<'PY'
import shutil, sys, zipfile
base, dex, so, dst = sys.argv[1:5]
shutil.copyfile(base, dst)
with zipfile.ZipFile(dst, "a", zipfile.ZIP_DEFLATED) as z:
    z.write(dex, "classes.dex")
    # 放在 lib/arm64-v8a/ 下，安装器会把它解到 nativeLibraryDir 并给 0755
    z.write(so, "lib/arm64-v8a/libmagpie.so", zipfile.ZIP_DEFLATED)
PY

"$ZIPALIGN" -f -p 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"

# ---- 签名 -------------------------------------------------------------------
KS="$ROOT/debug.keystore"
if [ ! -f "$KS" ]; then
  "$KEYTOOL" -genkeypair -keystore "$KS" -alias magpie -keyalg RSA -keysize 2048 \
    -validity 10000 -storepass android -keypass android \
    -dname "CN=Magpie,O=Hua,C=CN" >/dev/null
fi
SIGNED="$OUT/pkg-signed.apk"
rm -rf "$SIGNED"
sign sign --ks "$KS" --ks-pass pass:android --key-pass pass:android \
  --v1-signing-enabled true --v2-signing-enabled true \
  --out "$SIGNED" "$OUT/aligned.apk"
[ -f "$SIGNED" ] || { echo "✗ 签名没产出文件" >&2; exit 1; }
rm -f "$ROOT/$APK"
mv -f "$SIGNED" "$ROOT/$APK"

python - "$ROOT/$APK" <<'PY'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
names = set(z.namelist())
need = ["classes.dex", "lib/arm64-v8a/libmagpie.so", "AndroidManifest.xml"]
missing = [n for n in need if n not in names]
print("APK 条目数:", len(names), "· 缺失:", missing or "无")
info = z.getinfo("lib/arm64-v8a/libmagpie.so")
print("libmagpie.so 未压缩 %d MB / 压缩后 %d MB" % (info.file_size / 1048576, info.compress_size / 1048576))
if missing:
    sys.exit(1)
PY

ls -la "$ROOT/$APK"
echo "OK -> $ROOT/$APK"

case "${1:-}" in
  -i|--install)
    "$ADB" install -r "$ROOT/$APK"
    "$ADB" shell am start -n com.hua.magpie/.MainActivity >/dev/null
    echo "已启动 Magpie"
    ;;
esac
