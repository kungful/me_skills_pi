#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# autoinstall.sh —— 无 root 手机上的「半自动静默安装」
#
# 背景
#   vivo / OPPO / 小米装未知来源 APK 时会弹「安全守护提示」，
#   必须先勾「已了解应用的风险检测结果」（复选框），再点「继续安装」。
#   未勾选时「继续安装」是禁用状态，点了没反应 —— 这是最常见的坑。
#   这个弹窗属于系统安装器，普通 App 无权跳过；但 adb 能模拟点击。
#
# 用法
#   bash tools/autoinstall.sh 近聊.apk           # 装 + 自动点掉弹窗
#   bash tools/autoinstall.sh 近聊.apk --show    # 只装不点（人工确认）
#   adb_watch=1 bash tools/autoinstall.sh x.apk  # 打印每次命中的窗口
#
# 换机型：改下面 CB_X/CB_Y、OK_X/OK_Y 的基准值（都在 1260x2800 上量的），
#        脚本会按你实际的 wm size 自动等比换算。
# 校准技巧：让弹窗停在屏幕上，然后
#   adb shell input tap X Y     # 试探
#   adb exec-out screencap -p > s.png   # 看勾上了没
# ═══════════════════════════════════════════════════════════════════
set -uo pipefail

ADB="${ADB:-adb}"
APK="${1:?用法: autoinstall.sh <apk|手机上的路径> [--show]}"
MODE="${2:-auto}"

# 路径可能是本机文件，也可能是手机上已有的路径
REMOTE=0
if [ ! -f "$APK" ]; then
  if MSYS_NO_PATHCONV=1 "$ADB" shell "test -f $APK" >/dev/null 2>&1; then
    REMOTE=1
  else
    echo "✗ 本机和手机上都找不到 $APK"; exit 1
  fi
fi

# ── 屏幕尺寸，坐标按比例换算（基准 1260x2800）
SZ=$("$ADB" shell wm size 2>/dev/null | tr -d '\r' | awk -F': ' '{print $2}' | tail -1)
W=${SZ%x*}; H=${SZ#*x}
case "$W" in ''|*[!0-9]*) W=1260; H=2800;; esac
sc()  { python -c "print(int($1*$W/1260))"; }
scY() { python -c "print(int($1*$H/2800))"; }

# ── 基准坐标（1260x2800 实测，vivo OriginOS「安全守护提示」）
#   勾选框「已了解应用的风险检测结果」——必须先勾，否则「继续安装」是灰的
CB_X=$(sc 395);  CB_Y=$(scY 2443)
#   「继续安装」按钮
OK_X=$(sc 630);  OK_Y=$(scY 2620)
#   装完之后系统可能弹的「打开」按钮（仅 --open 时用）
OPEN_X=$(sc 630); OPEN_Y=$(scY 2600)

echo "屏幕 ${W}x${H}   勾选 (${CB_X},${CB_Y})   继续 (${OK_X},${OK_Y})"

wake() {
  "$ADB" shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1
  "$ADB" shell wm dismiss-keyguard >/dev/null 2>&1
}

# 坑：dumpsys window 会输出多行 mCurrentFocus，而且常带历史残留的 mCurrentFocus=null。
# 必须只取第一个「非 null」的那行，否则永远识别不出安装器窗口。
focus() {
  "$ADB" shell "dumpsys window" 2>/dev/null | tr -d '\r' \
    | grep 'mCurrentFocus=' | grep -v 'mCurrentFocus=null' | head -1
}

# 安装器窗口判定：vivo/OPPO/小米/AOSP 各有名字，全兜住
is_installer() {
  echo "$1" | grep -qiE 'packageinstaller|PackageInstaller|installui|InstallAppProgress|SecInstall|MiuiInstaller|oppo.*install|vivo.*install|PackageInstall'
}

install_cmd() {
  if [ "$REMOTE" = "1" ]; then
    MSYS_NO_PATHCONV=1 "$ADB" shell pm install -r -g "$APK" 2>&1
  else
    local dst="/data/local/tmp/_ai_$(basename "$APK")"
    MSYS_NO_PATHCONV=1 "$ADB" push "$APK" "$dst" >/dev/null 2>&1
    MSYS_NO_PATHCONV=1 "$ADB" shell pm install -r -g "$dst" 2>&1
  fi
}

click_installer() {
  [ -n "${adb_watch:-}" ] && echo "   → 命中安装器: $1"
  "$ADB" shell input tap "$CB_X" "$CB_Y" >/dev/null 2>&1   # 先勾同意
  sleep 0.4
  "$ADB" shell input tap "$OK_X" "$OK_Y" >/dev/null 2>&1   # 再点继续
}

watch_installer() {
  local rounds=$1
  for _ in $(seq 1 "$rounds"); do
    local f; f=$(focus)
    if is_installer "$f"; then
      click_installer "$f"
      sleep 1.2
      f2=$(focus)
      if is_installer "$f2"; then      # 有些机型点完还有二次确认
        "$ADB" shell input tap "$OK_X" "$OK_Y" >/dev/null 2>&1
        [ -n "${adb_watch:-}" ] && echo "   → 二次确认"
      fi
      sleep 1
    fi
    sleep 0.6
  done
}

wake

if [ "$MODE" = "--show" ]; then
  install_cmd | tail -2
  exit $?
fi

TMP=$(mktemp)
( install_cmd >"$TMP" 2>&1 ) &
INSTPID=$!
watch_installer 40 &
WATCHPID=$!

wait $INSTPID 2>/dev/null
OUT=$(tr -d '\r' <"$TMP" 2>/dev/null)
rm -f "$TMP"
wait $WATCHPID 2>/dev/null

if echo "$OUT" | grep -qi 'Success'; then
  echo "✓ 安装成功"
else
  echo "✗ 安装失败：${OUT:-无输出}"
  echo "  提示：若弹窗还停在屏幕上，先手动点一次「已了解…」看位置，"
  echo "        再用 --show 模式装了以后 adb shell input tap 校准坐标。"
fi
[ -n "${adb_verbose:-}" ] && echo "$OUT"
exit 0
