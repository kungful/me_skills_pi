#!/usr/bin/env bash
# 三角力学计算器 —— 全离线 APK 构建
# aapt2 + javac + d8 + zipalign + apksigner，不需要 Gradle、不联网。
# 注意：aapt2 不认非 ASCII 路径，所以先在纯英文目录 C:/tmcbuild 里构建，最后把产物拷回来。
set -euo pipefail

ROOT="C:/Users/hua/Documents/备份代码/TrigMech-Android"
WORK="C:/tmcbuild"
SDK="C:/Users/hua/AppData/Local/Android/Sdk"
NAME="三角力学计算器"

BT="$SDK/build-tools/36.0.0"
[ -d "$BT" ] || BT="$(ls -d "$SDK"/build-tools/* | sort -V | tail -1)"
AJ="$SDK/platforms/android-34/android.jar"
[ -f "$AJ" ] || AJ="$(ls -d "$SDK"/platforms/android-3[4-9]/android.jar | sort -V | tail -1)"

# JDK 21（javac 需支持 --release 8；JDK 24 已移除）
for J in "C:/Users/hua/.gradle/jdks/eclipse_adoptium-21-amd64-windows.2" \
         "C:/Program Files/Android/Android Studio/jbr"; do
  if [ -x "$J/bin/javac.exe" ]; then export JAVA_HOME="$J"; break; fi
done
export PATH="$(cygpath -u "$JAVA_HOME")/bin:$PATH"
command -v javac >/dev/null || { echo "找不到 javac"; exit 1; }
echo "JDK         : $JAVA_HOME"
echo "platform    : $AJ"
echo "build-tools : $BT"

OUT="$WORK/build"
DIST="$ROOT/dist"

rm -rf "$WORK"
mkdir -p "$WORK" "$OUT/classes" "$OUT/dex" "$OUT/gen" "$DIST"

echo "[0/6] 生成图标"
python "$ROOT/tool/make_icon.py"

cp -r "$ROOT/app" "$WORK/app"
cp -r "$ROOT/tool" "$WORK/tool"
APP="$WORK/app"

echo "[1/6] aapt2 compile 资源"
"$BT/aapt2.exe" compile --dir "$APP/res" -o "$OUT/res.zip"

echo "[2/6] aapt2 link (含 assets)"
"$BT/aapt2.exe" link \
  -o "$OUT/base.apk" \
  -I "$AJ" \
  --manifest "$APP/AndroidManifest.xml" \
  -A "$APP/assets" \
  --java "$OUT/gen" \
  --min-sdk-version 21 --target-sdk-version 34 \
  --version-code 1 --version-name 1.0 \
  --auto-add-overlay "$OUT/res.zip"

echo "[3/6] javac"
find "$APP/java" "$OUT/gen" -name "*.java" > "$OUT/sources.txt"
javac -nowarn -encoding UTF-8 --release 8 -classpath "$AJ" \
  -d "$OUT/classes" @"$OUT/sources.txt" 2>&1 | grep -v "bootstrap\|-Xlint\|警告\|warning" || true

echo "[4/6] d8 (dex)"
find "$OUT/classes" -name "*.class" > "$OUT/classes.txt"
"$BT/d8.bat" --release --min-api 21 --lib "$AJ" --output "$OUT/dex" @"$OUT/classes.txt"

echo "[5/6] 打包 + 对齐"
python - "$OUT/base.apk" "$OUT/dex/classes.dex" "$OUT/unsigned.apk" <<'PY'
import shutil, sys, zipfile
src, dex, dst = sys.argv[1], sys.argv[2], sys.argv[3]
shutil.copyfile(src, dst)
with zipfile.ZipFile(dst, "a", zipfile.ZIP_DEFLATED) as z:
    z.write(dex, "classes.dex")
PY
"$BT/zipalign.exe" -f -p 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"

echo "[6/6] 签名"
KS="$ROOT/debug.keystore"
if [ ! -f "$KS" ]; then
  keytool -genkeypair -keystore "$KS" -alias trigmech -keyalg RSA -keysize 2048 \
    -validity 10000 -storepass android -keypass android \
    -dname "CN=TrigMech,O=Hua,C=CN" >/dev/null
fi
"$BT/apksigner.bat" sign --ks "$KS" --ks-pass pass:android --key-pass pass:android \
  --ks-key-alias trigmech \
  --v1-signing-enabled true --v2-signing-enabled true \
  --out "$WORK/$NAME.apk" "$OUT/aligned.apk"
"$BT/apksigner.bat" verify "$WORK/$NAME.apk" >/dev/null

cp "$WORK/$NAME.apk" "$DIST/$NAME.apk"

python - "$DIST/$NAME.apk" <<'PY'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1]); n = z.namelist()
need = ["assets/index.html", "assets/app.js", "assets/trig.js", "assets/mech.js",
        "assets/data.js", "assets/style.css", "classes.dex", "AndroidManifest.xml"]
print("APK 文件数:", len(n))
print("缺失:", [x for x in need if x not in n] or "无")
PY
ls -la "$DIST/$NAME.apk"
echo "OK -> $DIST/$NAME.apk"
