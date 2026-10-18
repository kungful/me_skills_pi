---
name: bw16-flash
description: Ai-Thinker BW16 / RTL8720DN (Realtek AmebaD) 设备的识别、编译、烧录与救砖。含环境一键搭建、串口自动识别、源码编译、擦除+写入+校验全流程，以及「半写砖头」救援、SoftAP 不广播、抓包误报等已知坑的修法。当用户说「烧录/刷 BW16」「RTL8720DN 刷机」「抓包器/渗透机器重刷固件」「AmebaD 编译」「设备插上了找不到」「esp 渗透工具刷机」时使用。⚠️ BW16 是 Realtek 芯片，**esptool 永远连不上**，别走 ESP 那条路。
license: MIT
compatibility: Windows + Git-Bash/PowerShell；Python 3.9+（pyserial）；arduino-cli；磁盘约 1GB。需要 CH340 驱动（设备侧）。
allowed-tools: Bash, Read, Grep, Edit, Write
---

# BW16 / RTL8720DN 烧录与救援

BW16 是 **Realtek AmebaD (RTL8720DN)**，不是 ESP 系。两条铁律先记住：

1. **绝不要用 esptool** —— 芯片不归它管，只会浪费半小时。
2. **烧录参数必须是 `Enable Enable`** —— `auto_mode=Enable` 让工具自动进下载模式（**不用按 BURN**），
   `erase_flash=Enable` 先整片擦除。用 `Disable Disable` 会写出**半写砖头**。

## 30 秒速查

```bash
S=~/.pi/agent/skills/bw16-flash/scripts

bash "$S/setup.sh"       # 首次：装工具链（幂等，已装则秒过）
bash "$S/detect.sh"      # 找设备：COM 口 / 芯片 / 当前固件状态
bash "$S/build.sh"       # 编译 sketch -> build/km0_km4_image2.bin
bash "$S/flash.sh"       # 烧录（擦除+写入+校验，全自动）
bash "$S/go.sh"          # 一条龙：检测 -> 编译 -> 烧录 -> 验证
python "$S/verify.py"    # 复位并读启动日志，判断固件是否正常
```

## 工作根目录

所有产物落在 `$BW16_HOME`（默认 `~/Documents/备份代码/bw16`，可用环境变量覆盖）：

```
$BW16_HOME/
  toolchain/          arduino-cli + AmebaD 3.1.7 内核 + 4 个依赖库 + sketchbook/BW16-Tools/
  flashtool/          卖家烧录器（upload_image_tool_windows.exe / upload_image.exe / 镜像）
  build/              编译产物 km0_km4_image2.bin
  恢复报告.md          踩坑全记录
```

---

## 1. 识别设备

```bash
bash "$S/detect.sh"
```
会列出 CH340 (`VID_1A86:PID_7523`) 的串口、判断是不是 BW16、并复位读一次启动日志给出状态。

手工排查要点：

| 现象 | 含义 |
|---|---|
| `USB-SERIAL CH340 (COMx)` | BW16 开发板的桥接芯片，正常 |
| `ACPI\PNP0501` 的 COM1 | 主板自带串口，**不是**设备 |
| esptool 报 `No serial data received` | 正常 —— 这芯片不吃 esptool |
| 复位后只吐 `\r#` 就死 | **半写砖头**，boot 镜像坏了 → 立刻 `flash.sh` |
| 复位后完全 0 字节 | 芯片在 ROM 下载模式（或 EN 被拉住） |

**串口引脚测绘**（实测 CH340 板）：`RTS → EN`，**DTR 空接（没接 IO0）**。
所以任何软件复位只能靠 RTS；进 bootloader 平时必须物理按 BURN，但用 `Enable` 模式就不需要。

## 2. 编译

```bash
bash "$S/build.sh"
```

硬性约束（错了就编译不过 / 刷进去不跑）：

| 项 | 值 | 说明 |
|---|---|---|
| 内核版本 | **AmebaD 3.1.7-build20240216** | 用 3.2.0 会因 sketch 自带的 `SDK/` 与内核不兼容而报错 |
| FQBN | `realtek:AmebaD:Ai-Thinker_BW16` | 内核自带 BW16 定义 |
| 依赖库 | Adafruit_BusIO / Adafruit_GFX_Library / Adafruit_SSD1306 / U8g2_for_Adafruit_GFX | 版本见 `toolchain/sketchbook/libraries/` |

产物位置：`%LOCALAPPDATA%/arduino/sketches/<hash>/km0_km4_image2.bin`
（`arduino-cli --output-dir` 对 AmebaD 无效，`build.sh` 已自动去拷）。

## 3. 烧录（核心）

```bash
bash "$S/flash.sh"
```

它做两件事，顺序不能反：

```bash
cd "$BW16_HOME/flashtool"
./upload_image_tool_windows.exe ./ COM3 Ai-Thinker_BW16 Enable Enable 1500000   # 擦除 + 送 download bootloader 进 RAM
./upload_image.exe ./ COM3                                                      # 真正写入 + 校验
```

成功的标志（第二条命令）：

```
enter download flash mode.
km0 bootloader has been sent successfully.
km4 bootloader has been sent successfully.
app has been sent successfully.
verifying km0 km4 and app blocks....ok.      ← 必须看到 ok
hard resetting via RTS pin..
done.
```

> 整个过程**不需要按任何按键**。看到 `Please enter the upload mode manually(wait 5s)` 说明你在用
> `Disable`（错误），立刻改用 `Enable`。

## 4. 救砖

设备只吐 `\r#`、或根本不启动 —— 属于半写砖头，**ROM bootloader 在 mask ROM 里不会坏**，直接：

```bash
bash "$S/flash.sh"     # Enable Enable 会先整片擦除再写，一次搞定
```

## 5. 已知坑（都踩过）

### 5.1 GitHub 被墙
`github.com` 不通，但 `api.github.com` / `downloads.arduino.cc` / 这些镜像通：

```
https://ghfast.top/<原始 github url>          ✅ 可用
https://ghproxy.net/<原始 github url>         ✅ 可用
https://gh-proxy.com/<原始 github url>        ✅ 可用
https://gitee.com  https://gitclone.com       ✅ 可用
```

`arduino-cli` 的包索引指向 GitHub 会下载失败 —— **绕法**：把索引 json 放到
`$ARDUINO_DIRECTORIES_DATA/<basename>.json`，并把各归档按**索引里的文件名**预置到
`$ARDUINO_DIRECTORIES_DATA/staging/packages/`，校验和一致时 arduino-cli 就不去下载了。
（`setup.sh` 已实现。）

### 5.2 `arduino-cli lib install --zip-path` 被禁用
v1.5+ 默认关掉，需先 `arduino-cli config set library.enable_unsafe_install true`。

### 5.3 抓包「假包」误报
症状：正常环境里监控界面疯狂报 `Attack frame detected: Deauth/Disassoc`。

根因：`promiscDetectCallback()` / `promiscPacketDetectCallback()` 里用
`const int tryOffsets[] = {0,4,8,24,32,36,40};` **对每一帧把 7 个偏移全解析一遍**。
- 管理帧计数虚高约 7 倍
- 随机载荷被当帧控制字：单偏移误报率 ≈ 3.1%，7 个叠加 ≈ **20%**

修法：**偏移恒为 0**（AmebaD promisc 回调的 buf 直接就是 802.11 MAC 头，无前置头；
参照 `Cancro29/RTL8720dn-Handshake-Capture`：`fc = packet[0] | (packet[1] << 8)`），
再加：`version==0`、`type==0`、Deauth/Disassoc 定长 `len==26 || len==30`。

### 5.4 SoftAP 起了但扫不到 / 连不上
症状：串口打印 `Starting AP ... / <SSID> started / AP模式启动成功`，但手机电脑都搜不到。
**SDK 谎报成功。**

根因：`setup()` 里启动 AP 后立刻 `scanNetworks()`，而 AmebaD 的 `wifi_scan_networks()`
会让射频离开 AP 信道 → SoftAP beacon 停止。

修法：扫完重置射频并重新拉起 AP：
```c
wifi_off(); delay(200);
wifi_on(RTW_MODE_AP); delay(200);
WiFi.apbegin(ssid, pass, (char *)channelStr.c_str());
```

### 5.5 WebUI 地址连不上
正常现象：固件只在**在设备上进入「WebUI」菜单后**才 `web_server.begin()`，开机默认不启。
地址固定 `http://192.168.1.1`。

### 5.6 开机串口只打一段就静默
**不是死机**。`loop()` 在主菜单状态本来就不往串口输出，界面在 OLED 上。

---

## 6. 上游源码与固件

| 项目 | 用途 |
|---|---|
| `FlyingIceyyds/BW16-Tools` | 中文 BW16 固件源码（OLED + 4 键 + WebUI + 抓包），本 skill 的默认 sketch |
| `tesa-klebeband/RTL8720dn-Deauther` | 英文 deauther（531★） |
| `Cancro29/RTL8720dn-Handshake-Capture` | 抓包/握手固件，**解析偏移的权威参照** |
| `xwd0/bw16-flash-tool` | 卖家同款烧录工具（`BW16一键烧录命令行版本.bat` 是关键情报） |
| `Ameba-AIoT/ameba-arduino-d` | 官方 AmebaD Arduino 内核（原 `ambiot/ambd_arduino`） |

> 换固件：把新 sketch 放进 `$ARDUINO_DIRECTORIES_USER/<名字>/`，改 `scripts/_env.sh` 里的
> `SKETCH`，或者直接重跑 `setup.sh` 换成目标仓库。

---

## 7. 无线电合规

deauth / beacon flood / 信道干扰都是**实打实的无线电干扰**。
只在自己设备或**有书面授权**的靶场使用；对着他人 AP 使用在国内属违法。
