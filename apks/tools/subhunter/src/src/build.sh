#!/usr/bin/env bash
# 订阅猎手 SubHunter —— 纯 Android SDK 构建（不依赖 Gradle / Android Studio / 网络）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SDK="${ANDROID_SDK_ROOT:-/home/hua/toolchain/android-sdk}"
BT="$SDK/build-tools/36.0.0"
[ -x "$BT/d8" ] || BT="$SDK/build-tools/34.0.0"
[ -x "$BT/d8" ] || BT="$SDK/build-tools/37.0.0"
PLATFORM="$SDK/platforms/android-34/android.jar"
JDK="${JAVA_HOME:-/home/hua/toolchain/jdkroot/usr/lib/jvm/java-21-openjdk}"

APP_NAME="subhunter"
VERSION_NAME="1.0.3"
VERSION_CODE="${VERSION_CODE:-4}"
MIN_SDK=21
TARGET_SDK=34

KS="${KEYSTORE:-$ROOT/.keystore/subhunter.keystore}"
KEY_ALIAS="subhunter"

BUILD="$ROOT/build"
OUT="$ROOT/dist"

[ -x "$BT/aapt2" ] || { echo "找不到 aapt2: $BT"; exit 1; }
[ -x "$JDK/bin/javac" ] || { echo "找不到 javac: $JDK"; exit 1; }

rm -rf "$BUILD"
mkdir -p "$BUILD"/{compiled,gen,classes,dex} "$OUT"

echo "==> [1/6] aapt2 compile"
"$BT/aapt2" compile --dir "$ROOT/res" -o "$BUILD/compiled/res.zip"

echo "==> [2/6] aapt2 link"
"$BT/aapt2" link \
  -o "$BUILD/base.apk" \
  -I "$PLATFORM" \
  --manifest "$ROOT/AndroidManifest.xml" \
  --java "$BUILD/gen" \
  -A "$ROOT/assets" \
  --min-sdk-version "$MIN_SDK" \
  --target-sdk-version "$TARGET_SDK" \
  --version-code "$VERSION_CODE" \
  --version-name "$VERSION_NAME" \
  "$BUILD/compiled/res.zip"

echo "==> [3/6] javac"
find "$ROOT/src" "$BUILD/gen" -name '*.java' > "$BUILD/sources.txt"
set +e
"$JDK/bin/javac" \
  -encoding UTF-8 -source 8 -target 8 -nowarn \
  -bootclasspath "$PLATFORM" -classpath "$PLATFORM" \
  -d "$BUILD/classes" @"$BUILD/sources.txt" 2>&1 | grep -v "bootstrap class path" | grep -v "^Note:" | tee "$BUILD/javac.log"
JC=${PIPESTATUS[0]}
set -e
[ "$JC" = "0" ] || { echo "javac 失败"; exit 1; }
[ -f "$BUILD/classes/com/hua/subhunter/MainActivity.class" ] || { echo "javac 没产出 MainActivity"; exit 1; }

echo "==> [4/6] d8 -> dex"
find "$BUILD/classes" -name '*.class' > "$BUILD/classes.txt"
"$BT/d8" --release --lib "$PLATFORM" --min-api "$MIN_SDK" \
  --output "$BUILD/dex" @"$BUILD/classes.txt"

echo "==> [5/6] package + zipalign"
( cd "$BUILD/dex" && zip -q -X "$BUILD/base.apk" classes.dex )
"$BT/zipalign" -f -p 4 "$BUILD/base.apk" "$BUILD/aligned.apk"

echo "==> [6/6] sign"
if [ ! -f "$KS" ]; then
  mkdir -p "$(dirname "$KS")"
  keytool -genkeypair -v \
    -keystore "$KS" -alias "$KEY_ALIAS" -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass android -keypass android \
    -dname "CN=SubHunter, OU=Mobile, O=SubHunter, L=Shenzhen, ST=Guangdong, C=CN" >/dev/null 2>&1
fi

"$BT/apksigner" sign \
  --ks "$KS" --ks-key-alias "$KEY_ALIAS" \
  --ks-pass pass:android --key-pass pass:android \
  --v1-signing-enabled true --v2-signing-enabled true \
  --out "$OUT/$APP_NAME-$VERSION_NAME.apk" \
  "$BUILD/aligned.apk"

"$BT/apksigner" verify --print-certs "$OUT/$APP_NAME-$VERSION_NAME.apk" | head -3

echo
echo "==> APK: $OUT/$APP_NAME-$VERSION_NAME.apk"
ls -la "$OUT"
"$BT/aapt2" dump badging "$OUT/$APP_NAME-$VERSION_NAME.apk" 2>/dev/null | grep -E "^(package|application-label|uses-permission|launchable)" || true
