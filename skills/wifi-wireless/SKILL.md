---
name: wifi-wireless
description: Wi-Fi / 无线安全评估与取证（仅授权）：监听模式抓包、WPA/WPA2/WPA3 握手与 PMKID 采集、离线口令强度评估、流氓 AP / 钓鱼热点检测、企业无线隔离与 Captive Portal 绕过测试、去认证（deauth）实验室验证。当用户说 "wifi 渗透 / 无线渗透 / 抓握手 / 破解 wifi 密码 / PMKID / aircrack / hashcat 跑握手 / 流氓 AP / 钓鱼热点 / 无线安全评估 / 无线审计" 时使用。不做非授权的邻居网络扫描。
license: MIT
compatibility: 需要支持 monitor mode + packet injection 的无线网卡（如 Alfa AWUS036 series、MT7612U、RTL8812AU）；Linux/Kali 原生，Windows 下 WiFi 抓包与注入需 WSL2+USB 直通 或 直接跑 Kali Live/VM 挂 USB 网卡。
---

# Wi-Fi / Wireless Security（来自 reverse-skill · R29）

上游仓库：`C:\Users\hua\.pi\repos\reverse-skill`（clone 于 `https://github.com/zhaoxuya520/reverse-skill`，v1.0.1）
同族技能（本地未安装，需要时直接去仓库读）：
- `skills/radio-sdr/` — 非 Wi-Fi 的 RF/SDR
- `skills/attack-chain/` — Playbook 3「近源渗透 → 内网」
- `skills/pentest-tools/` — 工具清单与 payload 库
- `skills/field-journal/precedent-auth.md` — 授权门（先读再动手）

## ACTION REQUIRED（读完后立刻执行）

1. `NOW`: 读 `C:\Users\hua\.pi\repos\reverse-skill\skills\field-journal\precedent-auth.md`；**无线攻击法律风险高**，必须有对目标 SSID/BSSID 的书面授权，写明物理场地与时间窗
2. `NOW`: scope 写明目标 SSID / BSSID / 场地；**禁止扫邻居网络**、禁止扫全信道打着玩
3. `NEXT`: 确认适配器是否支持 monitor mode + 注入（`iw list | grep -A8 "Supported interface modes"`）
4. `ACT`: 侦察 → 采集 → 脱机分析（实验室 / 自有 AP 优先）

## 本机环境说明（Windows）

本机（Windows + Git Bash）**没有** `airmon-ng` / `airodump-ng` / `hashcat` / `hcxdumptool`，也不支持在 Windows 原生跑 monitor mode。

可行路径，按推荐度排：

| 方式 | 说明 |
|---|---|
| Kali Live USB / Kali VM + USB 网卡直通 | 最省事，工具全 |
| WSL2 + usbipd 直通无线网卡 | 能做，但 monitor mode 驱动在 WSL 内核里常要自己编 |
| 一台树莓派 / 小主机跑 Kali | 远程 SSH，适合现场 |
| Windows 上只做**离线**分析 | 握手/PMKID 文件拷回来，用 WSL 里的 hashcat 跑 |

没有可用网卡时：**不要编造扫描结果**，直接告诉用户缺硬件，给出采购建议（Alfa AWUS036ACH / AWUS036NHA 等）。

## 适用场景

- 授权 Wi-Fi 安全评估（自有办公网 / 客户合约内）
- WPA/WPA2 握手采集与离线口令策略评估
- PMKID 无客户端采集（比 deauth 温和，先试这个）
- 流氓 AP / 邪恶双子 / 钓鱼热点**检测**研究
- 企业无线隔离（client isolation）、Captive Portal 绕过测试
- 无线取证：管理帧、探测请求、设备指纹分析

## 工作流

```text
□ 1. 授权确认：目标 SSID/BSSID 列表 + 场地 + 时间窗，落到 scope 文件
□ 2. 网卡就绪：iw dev → airmon-ng start wlan0（先 airmon-ng check kill）
□ 3. 侦察：airodump-ng wlan0mon  → 锁定目标 BSSID + 信道
□ 4. 定向：airodump-ng -c <ch> --bssid <BSSID> -w cap wlan0mon
□ 5. 采集（阶梯，从最温和开始）：
     a. 被动等待自然握手（最安全，可能很久）
     b. PMKID：hcxdumptool -i wlan0mon -o pmkid.pcapng --enable_status=1
     c. 主动握手：aireplay-ng -0 3 -a <BSSID> -c <CLIENT> wlan0mon
        ← 只在授权范围内、且已确认会影响业务时取得同意后才做
□ 6. 转 hash：hcxpcapngtool -o hash.hc22000 cap.pcapng
□ 7. 离线评估：hashcat -m 22000 hash.hc22000 wordlist.txt（-m 2500 = WPA*4way 老格式）
□ 8. 报告：加密类型（WPA2-PSK/WPA3-SAE/OWE）、是否开 802.11w(PMF)、
      WPS 状态、client isolation、portal 绕过链、口令策略结论、加固建议
```

## 工具链

| 工具 | 用途 |
|------|------|
| `aircrack-ng` suite | `airmon-ng` 切模式、`airodump-ng` 采集、`aireplay-ng` 注入、`aircrack-ng` 评估 |
| `hcxdumptool` / `hcxtools` | PMKID 采集、pcapng → hc22000 转换（比 aircrack 流程现代） |
| `hashcat` | GPU 离线口令评估（-m 22000） |
| `wifite` | 自动化（学习用，别在客户现场无脑跑） |
| `bettercap` | wifi.recon / wifi.deauth 交互式，模块化 |
| `kismet` | 被动嗅探 + 无线 IDS，取证友好 |
| `Wireshark` / `tshark` | 802.11 管理帧、EAPOL 四步握手分析 |
| `hostapd-mana` / `eaphammer` | 邪恶双子（仅授权研究） |
| `reaver` / `bully` | WPS PIN（多数现代 AP 已关闭或锁死） |

## WPA3 / 现代网络注意

- WPA3-SAE **不能**用抓握手离线爆破的方式打；看到 SAE 就转向：降级攻击（transition mode 的 WPA2 混合模式）、Dragonblood 类侧信道、或直接评估配置
- 开了 802.11w (PMF) 的网络，deauth 会被保护，别浪费时间反复 `-0`
- 企业网 (802.1X/EAP) 的方向是 evil twin + 假 RADIUS 收凭据，不是抓握手

## 参考

- `references/wireless-lab-rules.md` — 无线实验规则
- 上游：`skills/MASTER-ROUTING.md` R29 路由上下文
- 上游：`skills/pentest-tools/references/awesome-pentest-digest.md` 无线章节
- 上游：`skills/attack-chain/references/attack-playbooks.md` Playbook 3（拿到网络接入之后怎么走）

## 路由上下文

**上游**: reverse-skill MASTER R29
**MUST NOT**: 未授权 deauth、对非目标客户网络操作、对邻居网络做任何主动行为、在报告里保留真实客户 MAC（外传需打码）

## 任务完成自检

- [ ] 是否严格锁定目标 BSSID / 信道？
- [ ] 每次主动注入（deauth）前是否确认过在授权范围内、且已告知用户影响？
- [ ] 是否在报告中给出加固建议（WPA3、PMF、关 WPS、client isolation、强口令）？
- [ ] 证据文件（pcap / hash）是否按约定存放、脱敏？
