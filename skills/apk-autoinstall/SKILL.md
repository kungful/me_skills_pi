---
name: apk-autoinstall
description: 在没有 root 的国产手机（vivo/OPPO/小米/荣耀）上，用 adb 自动点掉"未知来源 APK"的安全守护弹窗，实现接近一键静默的安装。当用户说"装 apk 老要我点已了解/继续安装"、"能不能自动安装 apk"、"adb install 被拦了"、"INSTALL_FAILED_ABORTED: User rejected permissions"、"跳过安装确认"、"免手动点安装弹窗"时使用。配套一键安装脚本 + 坐标校准方法。
---

# 国产手机免手点安装 APK

## 问题

`adb install` / `pm install` 在 vivo、OPPO、小米、荣耀上会被系统拦一次，返回：

```
Failure [INSTALL_FAILED_ABORTED: User rejected permissions]
```

屏幕上是这样一个弹窗（不点就一直卡着装不上）：

```
安全守护提示您
外部来源应用
该应用来源于非 vivo 官方应用商店，未经 vivo 人工亲测

☐ 已了解应用的风险检测结果        ← 必须先勾
      [ 继续安装 ]               ← 未勾选时是灰的，点了没反应
```

普通非 root 手机**没有**系统级"永久跳过"开关。能做到最接近的方案就是：
一边装，一边用 adb 模拟点击。本技能把这套流程封装成脚本。

## 现成脚本

项目里已经有：`<项目>/tools/autoinstall.sh`

```bash
bash tools/autoinstall.sh app.apk            # 装 + 自动点掉弹窗
bash tools/autoinstall.sh app.apk --show     # 只装不点，人工确认
adb_watch=1 bash tools/autoinstall.sh app.apk # 打印命中的窗口名，调试用
```

把它接到构建脚本里，就是一条命令完成「编译→安装→启动」：

```bash
case "${1:-}" in
  -i|--install)
    bash tools/autoinstall.sh "$APK"
    adb shell am start -n com.xxx/.MainActivity
    ;;
esac
```

## 两个必踩的坑（照抄结论）

### 坑 1：不勾复选框，「继续安装」点不动

弹窗里「继续安装」初始是**禁用态**。直接点它什么都不会发生，
很容易误判成"adb 模拟点击没生效 / 无障碍没开"。
必须**先点复选框那一行**，等按钮变蓝，再点继续。

### 坑 2：`grep -m1 mCurrentFocus` 抓到的是 null

```bash
# ✗ 错的：永远拿到历史残留的 mCurrentFocus=null，永远判不出安装器
adb shell "dumpsys window | grep -m1 mCurrentFocus"

# ✓ 对的：过滤掉 null 取第一个有效窗口
adb shell "dumpsys window" | tr -d '\r' \
  | grep 'mCurrentFocus=' | grep -v 'mCurrentFocus=null' | head -1
```

`dumpsys window` 会输出**多行** `mCurrentFocus`（历史值 + 当前值），
第一行常常是 `mCurrentFocus=null`。这是整套脚本能跑通的关键。

## 弹窗认不出来？先确认它是谁

```bash
adb shell "dumpsys window" | grep 'mCurrentFocus=' | grep -v null
#  → mCurrentFocus=Window{... com.android.packageinstaller/com.android.packageinstaller.PackageInterceptActivity ...}

adb shell "dumpsys activity activities" | grep -m3 -iE 'topResumedActivity'
```

vivo 的弹窗虽然包名是 AOSP 的 `com.android.packageinstaller`，
但它是 `PackageInterceptActivity` **自绘**的，
`uiautomator dump` 里**拿不到**它的节点（dump 出来的是底下那个 App 的界面）。
所以**别浪费时间去按文本找控件**，直接按坐标点。

## 校准坐标

让弹窗停在屏幕上，一步步试：

```bash
adb shell input tap 395 2443              # 试勾选
adb exec-out screencap -p > s.png         # 看图确认勾上了（变蓝）
adb shell input tap 630 2620              # 点继续安装
```

正确定位后：
- 勾选框在 1260x2800 上是 **(395, 2443)**
- 「继续安装」在 **(630, 2620)**

脚本按 `wm size` 等比换算，换分辨率不用改。

## 想真·完全静默（不点任何东西）

只有这几条路，都要 root 或用系统权限：

| 方式 | 前提 | 效果 |
|---|---|---|
| `pm install` 走 shell uid | 无（就是本方案） | 仍需点一次弹窗 |
| 关掉安装校验 | **需要 root**：`settings put global verifier_verify_adb_installs 0` + 冻结安全中心 | 可静默 |
| Shizuku / 自建 Device Owner | 需一次性授权或恢复出厂 | 可静默 |
| 把 APK 预置到 `/system/priv-app` | 需 root | 完全静默 |
| GKD 等无障碍自动化 | 装一个 App + 开无障碍 | 自动点，仍会闪一下弹窗 |

如果确认机器已 root，可以先试：

```bash
adb shell settings put global verifier_verify_adb_installs 0
adb shell settings put global package_verifier_enable 0
# 再把厂商的安全中心 / 安装器校验冻结
adb shell pm disable-user --user 0 com.vivo...安全相关包
```

否则就用本技能脚本 —— 一条命令，看不到弹窗。

## 也适用于

- 每次改完 APK 要反复装、反复被弹窗打断的开发流程
- 批量给多台机器装同一个 APK
- CI / 自动测试里需要 unattended 安装
