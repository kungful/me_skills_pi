# CPE140 控制台（PC 版）

易阔 **CPE140**（OEM 真身 **BHU BXO2000n-2S-Lite**，Atheros AR9341，OpenWrt 19.07）
中继器的**完全控制**工具：命令行 + 图形界面，**只用 Python 标准库，零第三方依赖**。

> 用途：管自己的路由器 —— 看链路、看客户端、改无线、备份整片 flash 救砖。
> 顺带把两个**未认证漏洞**做成了通道（这是它不需要密码的原因）。

---

## 为什么不需要登录

设备 Web 端有三个洞，本工具把它们当通道用：

| # | 洞 | 通道 |
|---|---|---|
| 1 | `/cgi-bin/*` 全部**不校验 Cookie** | 读全量配置（含明文口令/PSK）、改配置、改管理员口令、重启、恢复出厂、升级 |
| 2 | `/cgi-bin/timectrl` 的字段值**未转义拼进 shell** | **以 root 执行任意命令**（`sh` / `cat` / 上传下载 / 备份 flash） |
| 3 | 出厂 root 口令硬编码（见报告） | 需要交互式 root shell 时可走 SSH（本工具不依赖它） |

命令注入细节：值被塞进
`sh -c "uci -c /etc/config set administrator.reboot.week=<你传入的值>"`，
值外层是**双引号**，所以 `;` `&&` 无效，但 **反引号 `` ` `` 和 `$()` 会展开**。
单次载荷上限约 960 字节（超出被截断）。

**回显通道**：命令输出重定向到 `/tmp/.cpeout`（tmpfs），
再让 `/www/.cpeout` 指向它，用 `GET /.cpeout` 取回。
工具注入的载荷**自身不产生任何输出**，所以写回 uci 的值与原值一致 ——
不会污染定时重启规则，也不需要"用完还原"。

---

## 快速开始

```bash
# 0) 依赖：Python 3.8+，只用标准库
python cpe140.py doctor                # 自检：连通性 / 免认证 / RCE / root

python cpe140.py info                  # 设备信息
python cpe140.py status                # 上游链路 + WAN/LAN
python cpe140.py clients               # DHCP 客户端
python cpe140.py arp                   # ARP 表
python cpe140.py scan                  # 周边 WiFi 扫描
python cpe140.py wifi                  # 本机 AP + 上行 STA 配置
python cpe140.py backup cfg.json       # 备份全量配置（含口令，注意保管）
python cpe140.py dump-flash full.bin   # 整片 8MB flash 备份（救砖底牌）

python cpe140.py sh 'ps w; df -h'      # 以 root 执行（多命令用引号）
python cpe140.py cat /etc/config/wireless
python cpe140.py shell                 # 交互式 root shell
python cpe140.py gui                   # 图形界面（tkinter）

cp cpe140.py /usr/local/bin/ && chmod +x /usr/local/bin/cpe140.py   # 想当命令用
```

默认设备 `192.168.188.254`，可用 `--host` 改；`-v` 看 HTTP 往返，`--json` 出原始 JSON。

### 全部子命令

```
info status clients arp channels wifi sessions doctor gui shell uci clean reboot scan
sh cat cfg set backup restore push pull dump-flash password schedule mode
factory-reset upgrade
```

`mode`（切工作模式）、`factory-reset`、`upgrade` 是**危险操作**，`factory-reset` 需额外 `--yes`。

---

## 图形界面

`python cpe140.py gui` —— 五个标签页：**概览 / 客户端·扫描 / 配置 / 终端(root) / 维护**
（备份 flash、改 Web 口令、定时重启、重启、恢复出厂）。

---

## 安全边界（重要）

**不要碰这两组键**（改了会**立刻失联**，得靠网线 + U-Boot 救）：

* `WLAN0_VAP0_*` —— 本机 AP（你的电脑/手机就是连它管的）
* `WLAN0_VAP5_*` —— 上游 STA 接入（中继的命脉）

工具里这两组进了 `DANGEROUS` 名单，写之前要显式 `--force`。

**同样别乱点的 opcode**：`devmanage` opcode 3（恢复出厂）、4（升级）、5（重启）——
不是不能用，是**要清楚代价**（断网数十秒 / 配置清空）。

**设备端会短暂出现这些文件，退出时自动清理**：

| 路径 | 用途 |
|---|---|
| `/tmp/.cpeout` | 命令输出（tmpfs，零 flash 写入）|
| `/www/.cpeout` | 指向上面那个的符号链接（HTTP 取回用）|
| `/tmp/.cpesh` | 超长/含特殊字符的命令落成的临时脚本 |
| `/tmp/upload.img` | `push` 的中转文件 |

---

## 已知坑

* **系统代理**：本工具用 `build_opener(ProxyHandler({}))` 显式绕过系统代理。
  局域网设备不该走 Clash 之类（否则每个请求白等 4~5 秒）。
* **Git Bash (MSYS2) 会改写参数**：`/tmp/x` 会被翻译成 Windows 路径。
  本地文件参数请写 Windows 路径（`C:/tmp/x.bin`），或在命令前加 `MSYS_NO_PATHCONV=1`。
* **`strings` 在 Git Bash 里没有**：离线分析 CGI 请用 Python。
* 读含中文的 JSON 请 `encoding='utf-8'`，控制台请 `PYTHONIOENCODING=utf-8`。
* 设备没有 `base64` / `od` / `curl` / `openssl`；有 `gzip/tar/dd/wc/printf/hexdump/awk/sed`。

---

## 出厂口令

源码里**故意不硬编码**（这仓库是公开的，写进去等于替所有同型号设备开后门）。
需要时本机自己放：

```bash
echo '你的口令' > ~/.cpe140pw     # 或 export CPE140_PW='你的口令'
```

`doctor` 会读它；没配就只提示，不报错。**请尽快改掉出厂口令**（`ssh root@设备` → `passwd`）。

---

## 合规

只对你**自己拥有或已获书面授权**的设备使用。
把命令注入和硬编码口令做成"免密管理通道"这件事本身就是漏洞利用 ——
请勿对他人设备使用，并在条件允许时关闭/加固这些入口。
