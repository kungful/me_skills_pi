#!/usr/bin/env bash
# 只靠 Android SDK build-tools 打出「茶叶军师」APK（不用 Gradle、不联网）。
#   bash build.sh          只打包
#   bash build.sh -i       打包 + 装到手机 + 启动
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
AAPT2="$BT/aapt2.exe"; ZIPALIGN="$BT/zipalign.exe"; D8="$BT/d8.bat"
ADB="${ADB:-$LOCALAPPDATA/Android/Sdk/platform-tools/adb.exe}"

# JDK：默认的 java 是 24，apksigner 在 24 上会因 native-access 限制崩；
# 用 Gradle 缓存里的 Adoptium 21（AutoCut 那套同理）。
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
# apksigner 不用 .bat：在 git-bash 下它的参数重建会把 --out 弄成目录，导致“拒绝访问”。
# 直接跑 jar 就没这问题。
APKSIGNER_JAR="$BT/lib/apksigner.jar"
[ -f "$APKSIGNER_JAR" ] || APKSIGNER_JAR="$BT/apksigner.jar"
sign() { "$JAVA_BIN" -jar "$APKSIGNER_JAR" "$@"; }
echo "JAVA_HOME   : ${JAVA_HOME:-<系统默认>}"

echo "SDK         : $SDK"
echo "platform    : $PLATFORM"
echo "build-tools : $BT"

# ---- 图标 -------------------------------------------------------------------
if [ ! -f res/mipmap-xxhdpi/ic_launcher.png ]; then
  python tools/make_icon.py
fi

OUT="build"; APK="茶叶军师.apk"
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
  "$KEYTOOL" -genkeypair -keystore "$KS" -alias teastrategist -keyalg RSA -keysize 2048 \
    -validity 10000 -storepass android -keypass android \
    -dname "CN=TeaStrategist,O=Hua,C=CN" >/dev/null
fi
# 先写临时名再 mv，绕开 Windows 对刚生成文件的锁。
# ⚠ 千万别把这个变量叫 TMP/TEMP：它们是 Windows/JVM 的临时目录环境变量，
#   bash 给已导出的变量赋值会保持导出，apksigner 拿到 TMP=<输出路径> 后会
#   先把它建成目录，再往目录里写文件 → FileNotFoundException「拒绝访问」。
SIGNED_PKG="$OUT/pkg-signed.apk"
rm -rf "$SIGNED_PKG"
sign sign --ks "$KS" --ks-pass pass:android --key-pass pass:android \
  --v1-signing-enabled true --v2-signing-enabled true \
  --out "$SIGNED_PKG" "$OUT/aligned.apk"
[ -f "$SIGNED_PKG" ] || { echo "✗ 签名没产出文件" >&2; exit 1; }
rm -f "$ROOT/$APK"
mv -f "$SIGNED_PKG" "$ROOT/$APK"
sign verify --print-certs "$ROOT/$APK" | head -3 || true

python - "$ROOT/$APK" <<'PY'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
names = z.namelist()
need = ["assets/index.html", "assets/app.js", "assets/style.css",
        "assets/transport.js", "assets/kb.js", "classes.dex"]
print("APK 内文件数:", len(names))
print("缺失:", [n for n in need if n not in names] or "无")
for n in need:
    if n in names:
        print("   %-24s %8d B" % (n, z.getinfo(n).file_size))
PY

ls -la "$ROOT/$APK"
echo "OK -> $ROOT/$APK"

case "${1:-}" in
  -i|--install)
    "$ADB" install -r -g "$ROOT/$APK"
    "$ADB" shell am start -n com.hua.teastrategist/.MainActivity >/dev/null
    echo "已启动 茶叶军师"
    ;;
esac
