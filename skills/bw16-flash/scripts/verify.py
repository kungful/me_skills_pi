#!/usr/bin/env python3
"""复位 BW16 并读启动日志，判断当前固件状态。

用法:
    python verify.py [COM口] [读秒数]
    python verify.py COM3 10
    python verify.py COM3 8 --no-reset     # 不复位，只看它在说什么

退出码: 0=固件正常  1=有问题(砖/AP起不来)  2=读不到设备
"""
import sys
import time

# Windows 控制台默认 GBK，直接把输出强制成 UTF-8，否则中文/符号会报 UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("!! 缺 pyserial，先跑 setup.sh")
    sys.exit(2)

BAUD = 115200

args = [a for a in sys.argv[1:] if not a.startswith("--")]
NO_RESET = "--no-reset" in sys.argv
port = args[0] if args else None
secs = float(args[1]) if len(args) > 1 else 8.0

if not port:
    cands = [p.device for p in serial.tools.list_ports.comports()
             if (p.vid == 0x1A86) or (p.description and "CH340" in p.description)]
    if not cands:
        cands = [p.device for p in serial.tools.list_ports.comports()]
    if not cands:
        print("!! 没找到任何串口")
        sys.exit(2)
    port = cands[0]

print("== 串口 %s @%d" % (port, BAUD))
try:
    s = serial.Serial(port, BAUD, timeout=0.2, rtscts=False, dsrdtr=False)
except Exception as e:
    print("!! 打不开 %s: %s（是不是被别的程序占着？）" % (port, e))
    sys.exit(2)

s.rts = False
s.dtr = False
time.sleep(0.2)
s.reset_input_buffer()

if not NO_RESET:
    # RTS = EN，拉低 0.35s 再放开 = 一次干净复位
    s.rts = True
    time.sleep(0.35)
    s.rts = False

buf = bytearray()
t0 = time.time()
while time.time() - t0 < secs:
    d = s.read(4096)
    if d:
        buf += d

# 再读一轮，确保 WiFi 初始化那段（约 1.5s）能抓全
if buf and not NO_RESET:
    t1 = time.time()
    while time.time() - t1 < 3.0:
        d = s.read(4096)
        if d:
            buf += d
s.close()

txt = buf.decode("utf-8", "replace")
print("=" * 58)
print(txt)
print("=" * 58)

has_banner = "BW16 WiFi Deauther" in txt or "#calibration_ok" in txt
ap_err = "SSID can't be empty" in txt
ap_ok = ("AP模式启动成功" in txt) or ("AP已重新拉起" in txt)
rearmed = "AP已重新拉起" in txt
bricked = (not has_banner) and (0 < len(buf) <= 8)

print()
print("抓到 %d 字节" % len(buf))
print("  固件启动?          %s" % ("是" if has_banner else "否"))
print("  AP 报错(空SSID)?   %s" % ("[已修复]" if not ap_err else "[仍是空 SSID]"))
print("  AP 启动成功?       %s" % ("是" if ap_ok else "否"))
print("  扫描后重拉AP?      %s" % ("有（修复已生效）" if rearmed else "没有"))

if bricked:
    print()
    print(">>> 判定：半写砖头（boot 镜像损坏）")
    print(">>> 处理：bash flash.sh    —— Enable 模式会先整片擦除再写")
    sys.exit(1)
if not buf:
    print()
    print(">>> 判定：完全静默 —— 芯片可能在 ROM 下载模式，或被 EN 拉在复位态")
    print(">>> 直接 bash flash.sh 即可（Enable 模式会自己处理）")
    sys.exit(0)
if has_banner and (ap_err or not ap_ok):
    print()
    print(">>> 判定：固件能跑但 AP 有问题，建议重新编译烧录带修复的固件")
    sys.exit(1)
print()
print(">>> 判定：固件正常 [OK]")
sys.exit(0)
