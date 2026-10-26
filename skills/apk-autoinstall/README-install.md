# 一键安装（免手点）

```bash
bash build.sh -i          # 编译 + 安装 + 自动点掉「安全守护提示」+ 启动
bash tools/autoinstall.sh 近聊.apk   # 只装（自动点弹窗）
bash tools/autoinstall.sh 近聊.apk --show  # 只装不点，人工确认
```

## 为什么需要它

vivo / OPPO / 小米 在装未知来源 APK 时会插入一个系统弹窗：

```
安全守护提示您
外部来源应用
该应用来源于非 vivo 官方应用商店，未经 vivo 人工亲测

☐ 已了解应用的风险检测结果      ← 必须先勾这个
     [ 继续安装 ]              ← 没勾就是灰的，点了没反应
```

这个弹窗**不在** `uiautomator dump` 的节点树里（vivo 定制实现，走的是
`com.android.packageinstaller.PackageInterceptActivity` 自绘），
所以没法用文案找控件，只能按坐标点。

## 两个真坑

1. **必须先勾复选框**。不勾的时候「继续安装」是禁用态，点上去像"没反应"，
   很容易误判成"无障碍没生效"。
2. **`dumpsys window | grep -m1 mCurrentFocus` 抓的是残留 null 行**。
   dumpsys 会输出多行，第一行往往是历史值 `mCurrentFocus=null`，
   真正的窗口在后面。必须 `grep mCurrentFocus= | grep -v null | head -1`。

## 校准坐标（换机型）

让弹窗停在屏幕上，然后：

```bash
adb shell input tap 395 2443            # 试探勾选
adb exec-out screencap -p > s.png       # 看勾上了没
adb shell input tap 630 2620            # 点继续
```

脚本里的坐标是 1260x2800 基准值，会按 `wm size` 自动等比换算。
