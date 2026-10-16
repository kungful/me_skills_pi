#!/usr/bin/env bash
# 万物原理 —— 全离线 APK 构建（aapt2 + javac + d8 + zipalign + apksigner，不需要 Gradle）
# 注意：aapt2 不认非 ASCII 路径，所以先在纯英文目录里构建，最后把产物拷回来。
set -euo pipefail

ROOT="C:/Users/hua/Documents/备份代码/CosmosCodex"
WORK="C:/ccbuild"                       # 纯 ASCII 工作目录
SDK="C:/Users/hua/AppData/Local/Android/Sdk"
BT="$SDK/build-tools/35.0.0"
AJ="$SDK/platforms/android-34/android.jar"
export JAVA_HOME="C:/Users/hua/.gradle/jdks/eclipse_adoptium-21-amd64-windows.2"
export PATH="$JAVA_HOME/bin:$PATH"

NAME="万物原理"
OUT="$WORK/build"
DIST="$ROOT/dist"

rm -rf "$WORK"
mkdir -p "$WORK"
cp -r "$ROOT/app" "$WORK/app"
cp -r "$ROOT/tool" "$WORK/tool"
APP="$WORK/app"

mkdir -p "$OUT/compiled" "$OUT/classes" "$OUT/dex" "$OUT/gen"
mkdir -p "$DIST"

echo "[1/6] aapt2 compile 资源"
"$BT/aapt2.exe" compile --dir "$APP/res" -o "$OUT/compiled/res.zip"

echo "[2/6] aapt2 link (含 assets)"
"$BT/aapt2.exe" link \
  -o "$OUT/base.apk" \
  -I "$AJ" \
  --manifest "$APP/AndroidManifest.xml" \
  -A "$APP/assets" \
  --java "$OUT/gen" \
  --min-sdk-version 21 --target-sdk-version 34 \
  --version-code 1 --version-name 1.0 \
  "$OUT/compiled/res.zip"

echo "[3/6] javac"
find "$APP/java" "$OUT/gen" -name "*.java" > "$OUT/sources.txt"
javac -nowarn -source 8 -target 8 -bootclasspath "$AJ" -d "$OUT/classes" @"$OUT/sources.txt" 2>&1 \
  | grep -v "bootstrap\|-Xlint\|警告\|warning" || true

echo "[4/6] d8 (dex)"
find "$OUT/classes" -name "*.class" > "$OUT/classes.txt"
"$BT/d8.bat" --release --min-api 21 --lib "$AJ" --output "$OUT/dex" @"$OUT/classes.txt"

echo "[5/6] 打包 + 对齐"
python "$WORK/tool/mkzip.py" "$OUT/base.apk" "$OUT/dex/classes.dex" "$OUT/unsigned.apk"
"$BT/zipalign.exe" -f -p 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"

echo "[6/6] 签名"
"$BT/apksigner.bat" sign \
  --ks "$HOME/.android/debug.keystore" --ks-pass pass:android --key-pass pass:android \
  --ks-key-alias androiddebugkey \
  --out "$OUT/$NAME.apk" "$OUT/aligned.apk"
"$BT/apksigner.bat" verify "$OUT/$NAME.apk" >/dev/null

cp "$OUT/$NAME.apk" "$DIST/$NAME.apk"
SIZE=$(stat -c%s "$DIST/$NAME.apk")
echo "=========================================="
echo " 完成: $DIST/$NAME.apk  ($((SIZE/1024)) KB)"
echo "=========================================="
