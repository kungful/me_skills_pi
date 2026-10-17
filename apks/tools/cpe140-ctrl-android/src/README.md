# CPE140 控制台（安卓版）

易阔 **CPE140** / BHU BXO2000n-2S-Lite 中继器的手机控制台。
**免登录**，因为走的是设备自己的两个未认证通道（Web API + `timectrl` 命令注入）。

```
package   com.picpe.cpe140
version   1.1.0
minSdk    24 (Android 7.0)      targetSdk 37
签名      cpe140.jks (alias cpe140 / cpe140123)   ← 自签名
```

## 编译

```bash
# 需要 JDK 17+（本机用 JDK 24）与 Android SDK（compileSdk 37）
./gradlew assembleRelease
# 产物：app/build/outputs/apk/release/app-release.apk
```

> 本项目放在含中文的路径下，`gradle.properties` 里加了 `android.overridePathCheck=true`。
> 如果 aapt2 在中文路径下抽风，把工程挪到纯英文路径再编。

## 功能

| 标签 | 能干什么 |
|---|---|
| **概览** | 设备信息 / 上游链路（SSID·信道·RSSI）/ WAN / LAN / 无线配置 / **系统自检**（一键验漏洞） |
| **客户端** | DHCP 客户端列表 / ARP 表 / 周边 WiFi 扫描 / 信道 |
| **配置** | 读全量 79 项配置（含明文口令）/ 导出备份到文件 / 按 KEY 写值（危险键二次确认） |
| **终端** | **以 root 执行任意命令**；**命令手册/教程**（每条命令一句人话，点一下自动填入）；7 个快捷 chip（点=直接跑，长按=只填入）；历史 ↑ |
| **维护** | **断网看门狗**（断网 N 分钟自动重启防卡机）/ 备份整片 8MB Flash（救砖）/ 上传·下载文件 / 改 Web 口令 / 清理临时文件 / 重启 / 恢复出厂 / 定时重启读写 |

界面是自绘深色风格（自写 drawable + 自写底部导航，不用 Material），
5 个标签有图标和选中态。

### 断网看门狗（自动重启）

设备上跑 `/etc/netguard.sh`（每 2 分钟由 cron 巡检一次）：

* 探测 `223.5.5.5` / `114.114.114.114`，任一通 → 计数清零；
* 连续 `N/2` 次全不通（默认 10 分钟）→ `sync; sleep 3; reboot`；
* **30 分钟冷却**：上游光猫真坏了也不会无限重启；
* **和「定时重启」互不干扰**：脚本名与命令行都不含 `reboot` 子串，
  不会被 `/etc/init.d/autoreboot` 的 `sed -i '/reboot/d'` 误删；
* 计数与日志放 `/tmp`（内存盘，零 flash 磨损，重启自然归零）。

App 里点「**干跑测试**」只算一遍并告诉你「现在断网的话会做什么」，**绝不重启**。
默认装机时脚本已放好但 **cron 未启用**，由你点「开启看门狗」才真正生效。

首次打开会自动连 `192.168.188.254`（可改）。**手机要能路由到设备**：
连设备自己的 WiFi，或连它后级的网络。

## 实现要点

* **HTTP 免代理**：直接 `HttpURLConnection`，不走系统代理。
* **回显通道**：`cmd > /tmp/.cpeout` + `/www/.cpeout` 符号链接 → `GET /.cpeout`。
  载荷自身不输出字符，写回的 uci 值与原值相同 —— 不污染定时重启规则，无需还原。
* **权限补刀**：`cp` 会带来源文件权限（如 `/etc/shadow` 的 600），uhttpd 对 600 回 403，
  所以注入载荷末尾统一 `chmod 644`。
* **载荷字符限制**：不能出现 `` ` `` `"` `\` `{` `}`（前三个会把双引号值括断，
  大括号会被 CGI 拒掉）。含这些字符的命令自动改走"上传脚本 + `sh` 执行"。
  单次内联载荷 ≤ 620 字节，注入总长 ≤ 880（设备上限约 960）。
* 文件读写走 SAF（`CreateDocument` / `OpenDocument`），**不需要存储权限**。
* 边到边（targetSdk 35+ 强制）已在 `MainActivity` 里手动补系统栏内边距。

## 安全边界

* **绝不修改** `WLAN0_VAP0_*`（本机 AP，手机就是连它管的）与 `WLAN0_VAP5_*`（上游 STA）——
  改了就失联，得靠网线 + U-Boot 救。写这两组键会弹二次确认。
* `Cpe.clean()` 在退出时清掉设备端 `/tmp/.cpeout`、`/www/.cpeout`、`/tmp/.cpesh`、`/tmp/upload.img`。
* 恢复出厂 / 重启 / 升级都会断网或清配置，弹窗里写了后果。

## 合规

只对**自己拥有或已授权**的设备使用。详见同仓库 `cpe140-ctrl/README.md` 与报告。
