<#
.SYNOPSIS
  pi 安卓链路一键部署（Windows）。

  生成配置和手动启动脚本，不注册开机自启：
    1. run-link.bat（一个终端同时跑 watchdog + 派发台 :8787，任一崩溃自动重启）
       watchdog = 会话完成/异常中断的判定与推送（进程外守护）
       派发台   = 手机派发台 UI + 消息中转 /pi/*（自研）
    2. run-pi-web.bat（pi-web :30141，-H 0.0.0.0，手机可达）

  另外生成 ~/.pi/android-link/local.json（密码/topic/令牌的唯一来源）
  和 run-pi-web.bat（把 pi-web 改绑 0.0.0.0 并带上密码）。

.PARAMETER SkipTasks
  兼容旧参数；当前版本不注册任何开机自启。仍可用于跳过防火墙规则。

.PARAMETER Force
  重新生成 local.json（会换掉密码和 topic，手机上要重新订阅）。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File setup.ps1
#>
#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$SkipTasks,
    [switch]$ScriptsOnly,
    [switch]$NoPassword,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$Root      = $PSScriptRoot
$StateDir  = Join-Path $env:USERPROFILE '.pi\android-link'
$LocalJson = Join-Path $StateDir 'local.json'
$ConsolePort = 8787
$PiWebPort = 30141
# 异地（公网）统一出口：派发台路由 + pi-web 反代都在它身上。
# 公网上的隧道 / IPv6 / 端口映射全部指向这一个端口（见 README「异地通知」）。
$GatewayPort = 8788
$PiWebAgentRoot = Join-Path ((& npm root -g).Trim()) '@agegr\pi-web\node_modules\@earendil-works\pi-coding-agent'

function Say($msg, $color = 'Gray') { Write-Host $msg -ForegroundColor $color }
function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "  [!]  $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Host "  [X]  $msg" -ForegroundColor Red }

function New-RandomToken([int]$Bytes = 24) {
    $buf = New-Object byte[] $Bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($buf)
    return ($buf | ForEach-Object { $_.ToString('x2') }) -join ''
}

<#
  .bat 用 UTF-8 无 BOM + 首行 chcp 65001（和桌面 Pi Web.bat / Restart-PiWeb.bat 同一套写法）。

  为什么不用 .cmd + 纯 ASCII：2026-09-24 之前试过，.cmd 按 OEM 代码页解析，
  中文注释会被解成乱码并把一行拆成两条命令（报 'API' is not recognized），
  所以 .cmd 里被迫只能写英文。现在统一用 .bat + chcp 65001，中文照常写。

  坑：Set-Content -Encoding OEM / UTF-8 会写 BOM 或转码。必须用显式字节写入
  （无 BOM 的 UTF-8），不依赖 Set-Content -Encoding。
#>
function Write-BatFile([string]$Path, [string]$Text) {
    # ── 1. 无 BOM ────────────────────────────────────────────────────────
    # 有 BOM 会被 cmd 当成第一条命令的一部分（直接报「'锟斤拷' 不是内部或外部命令」）。
    if ($Text.Length -gt 0 -and $Text[0] -eq [char]0xFEFF) {
        throw "$Path 开头带 BOM，cmd 会解析失败，拒绝写入。"
    }

    # ── 2. 换行归一化：全部 CRLF ──────────────────────────────────────────
    # cmd 按字节读 .bat；遇到【只有 LF 没有 CR】的行，它会算错下一条命令的
    # 起始字节位置，于是从那一行往后整段都解析坏。实测生成出来的 run-link.bat
    # 只有最后一行是 LF-only（34 行里就这一行），症状却是整窗乱码。
    $normalized = ($Text -replace "`r`n", "`n") -replace "`r", "`n"
    $normalized = $normalized -replace "`n", "`r`n"
    if (-not $normalized.EndsWith("`r`n")) { $normalized += "`r`n" }

    # ── 3. 代码页：chcp 之后【重新调用自己】 ──────────────────────────────
    # 这是本项目踩过最久的一个坑，必须写清楚：
    #   cmd 读 .bat 是按【当前代码页】逐块读的。开头 @echo off 是 ASCII，没问题；
    #   但 chcp 65001 只对【之后】读到的字节生效，而 cmd 是分块读的 ——
    #   块边界一旦正好切在某个多字节汉字中间，那一行会被解成 U+FFFD，
    #   cmd 就把它当成一条命令去执行，屏幕上全是
    #     「xxx.bat 不是内部或外部命令」/「xxx is not recognized」
    #   迷惑性极强：node 其实已经起来了、端口也监听了，只是整窗文字乱掉，
    #   很容易误判成「脚本坏了 / 环境有问题」。
    #   单行测试全过、逐行 probe 也定位不到（因为它只在整文件分块读时才炸）。
    # 修法：用 chcp 换完代码页之后重新调用自己，让整个文件从头就在 UTF-8 下被读。
    # 只对【含非 ASCII 字符】的文件注入：纯英文脚本不需要，多一层壳反而添乱。
    $hasNonAscii = $normalized -cmatch '[^\x00-\x7F]'
    if ($hasNonAscii -and $normalized -notmatch '__cp65001_body__') {
        # [ASCII-ONLY ON PURPOSE] This block runs BEFORE the chcp, so cmd is
        # still using the system ANSI code page while reading it. One CJK
        # character here decodes to garbage and the line gets executed as a
        # command (chicken-and-egg). Hence: English comments + two-stage start.
        $preamble = @"
@echo off
REM ==============================================================
REM DO NOT DELETE THIS BLOCK, and do not move the chcp line below.
REM Why (full story in setup.ps1 / Write-BatFile):
REM   cmd reads a .bat in blocks using the CURRENT code page, and
REM   "chcp 65001" only affects bytes read AFTER it runs. A block
REM   boundary landing inside a multi-byte CJK char decodes that line
REM   into U+FFFD, and cmd then tries to EXECUTE it:
REM     'xxx.bat' is not recognized as an internal or external command
REM   Very confusing: the program already started, only the text is garbage.
REM
REM Two details that are easy to get wrong:
REM   1) The second stage must be a NEW cmd process (cmd /c), not "call".
REM      "call" re-reads the same file handle from the current offset, so
REM      the block-boundary bug comes right back (it did, in testing).
REM   2) The stage-2 marker is an ENVIRONMENT VARIABLE, not an argument:
REM      cmd's %* is NOT affected by shift, so a sentinel passed as %1
REM      would still be inside %* and leak into the real arguments
REM      (it ended up as fix-split-brain.ps1's -LogPath value).
REM
REM This preamble MUST stay ASCII-only: it runs before the chcp.
if defined PI_LINK_CP65001 goto __cp65001_body__
chcp 65001 >nul
set "PI_LINK_CP65001=1"
cmd /c ""%~f0" %*"
exit /b
:__cp65001_body__
REM ==============================================================
"@
        $preamble = ($preamble -replace "`r`n", "`n") -replace "`n", "`r`n"
        # 去掉正文里重复的那行独立 chcp（避免执行两次，虽然无害但会多刷一行）
        $rest = $normalized -replace '(?m)^chcp 65001 >nul\r\n', ''
        # 这里的换行不能省：PowerShell 的 here-string 结尾【不带】换行，
        # 直接拼起来会让 preamble 最后一行和正文第一行粘成一行
        # （实测粘成 "REM ====…@echo off" —— 于是 @echo off 被注释掉了）
        $normalized = $preamble + "`r`n" + $rest
    }

    # ── 3b. 自检：生成物里不允许出现反引号 ──────────────────────────────
    # PowerShell 的双引号 here-string 会吃掉反引号（反引号加 n 甚至会变成换行），
    # 而 .bat 里的反引号是 cmd 的转义符、还得写成双写形式 —— 两套转义规则打架，
    # 生成出来必然是坏的（实测：把 for /f 那两行切成了四行，窗口里全是
    # 「'ks' 不是内部或外部命令」）。现在模板里一个反引号都不需要，
    # 所以直接把「出现反引号」当成硬错误挡在落盘之前。
    if ($normalized.Contains([char]0x60)) {
        throw "$Path 生成物里出现了反引号 —— here-string 会吃掉它、cmd 又需要它，转义会打架。请改用不含反引号的写法。"
    }

    # ── 4. 落盘前自检：换行必须是纯 CRLF ─────────────────────────────────
    $badLf = 0
    foreach ($line in ($normalized -split "`n")) {
        if ($line.Length -gt 0 -and -not $line.EndsWith("`r")) { $badLf++ }
    }
    if ($badLf -gt 0) {
        throw "$Path 还有 $badLf 行不是 CRLF，拒绝写入（cmd 会从那一行起解析坏）。"
    }
    # 有非 ASCII 就必须有那段重入头，否则一定会乱码
    if (($normalized -cmatch '[^\x00-\x7F]') -and ($normalized -notmatch '__cp65001_body__')) {
        throw "$Path 含中文/非 ASCII 但缺少代码页重入头，拒绝写入。"
    }

    [System.IO.File]::WriteAllText($Path, $normalized, (New-Object System.Text.UTF8Encoding($false)))
    $extra = if ($hasNonAscii) { ' + 代码页重入头' } else { '' }
    Ok "已写 $([System.IO.Path]::GetFileName($Path))（UTF-8 无 BOM + 全 CRLF$extra / $($normalized.Length) 字节）"
}

function Get-LanIPv4 {
    try {
        $route = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction Stop |
                 Sort-Object RouteMetric | Select-Object -First 1
        $candidate = (Get-NetIPAddress -InterfaceIndex $route.InterfaceIndex -AddressFamily IPv4 -ErrorAction Stop |
                      Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' } |
                      Select-Object -First 1).IPAddress
        if ($candidate) { return $candidate }
    } catch { }
    $fallback = (Get-NetIPAddress -AddressFamily IPv4 |
                 Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' } |
                 Select-Object -First 1).IPAddress
    if ($fallback) { return $fallback }
    throw '找不到局域网 IPv4 地址'
}

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    return (New-Object Security.Principal.WindowsPrincipal $id).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

Write-Host @"
+----------------------------------------------------------------+
|  pi-android-link  部署                                          |
|  watchdog  +  派发台:8787（含消息中转）                          |
+----------------------------------------------------------------+
"@ -ForegroundColor DarkCyan

Say "项目目录 : $Root"
Say "状态目录 : $StateDir"

# ── 1. Node ────────────────────────────────────────────────────────────
Step '1/5 检查运行环境'
$node = (Get-Command node -ErrorAction SilentlyContinue).Source
if (-not $node) { Fail '找不到 node，请先安装 Node.js 22+'; exit 1 }
$nodeVersion = (& $node -v)
Ok "node $nodeVersion  ($node)"
if ([int]($nodeVersion.TrimStart('v').Split('.')[0]) -lt 22) {
    Warn 'Node 版本低于 22，pi-web 与 fetch/AbortSignal.timeout 可能不可用'
}

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

# ── 2. 生成 local.json ─────────────────────────────────────────────────
Step '2/5 生成配置'
if ((Test-Path $LocalJson) -and -not $Force) {
    # 【不能用 Get-Content -Raw】PowerShell 5.1 会按 ANSI(GBK) 解码无 BOM 的 UTF-8，
    # 结果中文字段变乱码 → ConvertFrom-Json 直接抛 ArgumentException。
    # 症状是“第一次 setup 好好的，第二次就报错退出”，而报的行号指向这里。
    # local.json 是 Node 写的无 BOM UTF-8，所以要显式按 UTF-8 读，并先剥掉可能存在的 BOM。
    $existing = [System.IO.File]::ReadAllText($LocalJson, [System.Text.Encoding]::UTF8).TrimStart([char]0xFEFF) | ConvertFrom-Json
    Ok "已存在，沿用现有配置（要换掉用 -Force）：$LocalJson"
    $password = if ($NoPassword) { '' } else { $existing.piWeb.password }
    $token    = $existing.lan.consoleToken
    $lanHost  = $existing.lan.host

    # 复用分支原本不回写 local.json，于是 -NoPassword 只影响 run-pi-web.bat、
    # 不影响配置本身。这里显式落盘，让"免密码模式"真的持久化。
    if ($NoPassword -and $existing.piWeb.password) {
        $existing.piWeb.password = ''
        [System.IO.File]::WriteAllText($LocalJson, ($existing | ConvertTo-Json -Depth 6), (New-Object System.Text.UTF8Encoding($false)))
        Ok '已清空 local.json 里的密码（局域网免密码模式）'
    }
} else {
    # -NoPassword = 局域网免密码模式。pi-web 在非回环绑定且无密码时只会警告一句：
    #   "listening on 0.0.0.0 without authentication. Only use this on a trusted network."
    # 注意：CSRF 防护（Origin / Sec-Fetch-Site 检查）在 proxy.ts 里排在密码检查之前，
    # 所以无密码不会变成"任意网页都能 POST 过来"。
    $password = if ($NoPassword) { '' } else { New-RandomToken 16 }
    $token    = New-RandomToken 16
    $lanHost  = Get-LanIPv4

    $config = [ordered]@{
        piWeb = [ordered]@{ base = "http://127.0.0.1:$PiWebPort"; password = $password }
        broker = [ordered]@{ base = "http://127.0.0.1:$ConsolePort"; token = $token }
        lan   = [ordered]@{
            host = $lanHost; piWebPort = $PiWebPort
            consolePort = $ConsolePort; consoleToken = $token
        }
        defaultCwd = (Get-Location).Path
        wan = [ordered]@{
            _说明 = '异地（出门在外也能收通知）。不需要买/租服务器、不需要注册账号。enabled=false 可完全关掉（不查公网 IP、不起隧道、不开网关端口）。tunnel=auto 时会在 PATH 里找 cloudflared（免账号 Quick Tunnel）；找不到就只用 IPv6 / 端口映射 / 手填地址。'
            enabled = $true
            gatewayPort = $GatewayPort
            tunnel = 'auto'
            extraBases = @()
        }
        quickCommands = @(
            [ordered]@{ name = 'status'; label = '看看现在在跑什么'; cwd = $Root
                        prompt = '列出当前机器上正在运行的 pi 会话和它们的状态，用中文简述。' }
            [ordered]@{ name = 'resume'; label = '继续上一个没跑完的事'; cwd = $Root
                        prompt = '看一下最近的会话状态，把没跑完的事情接着做完并汇报结果。' }
        )
    }
    # ConvertTo-Json + Set-Content -Encoding UTF8 在 PowerShell 5.1 下会写 BOM，
    # Node 的 JSON.parse 会直接报 "Unexpected token '﻿'"，所以显式写无 BOM 的 UTF-8
    $json = $config | ConvertTo-Json -Depth 6
    [System.IO.File]::WriteAllText($LocalJson, $json, (New-Object System.Text.UTF8Encoding($false)))
    Ok "已生成 $LocalJson"
    Warn '这个文件是本机唯一秘密来源，别提交到仓库'
}

# 收紧权限：只有当前用户可读
try {
    icacls $LocalJson /inheritance:r /grant:r "$($env:USERNAME):(R,W)" | Out-Null
    Ok '已把 local.json 权限限制为当前用户'
} catch { Warn "设置权限失败（不影响运行）：$_" }

Say ""
Say "  局域网地址 : $lanHost" -ForegroundColor White
Say "  派发台令牌 : $token" -ForegroundColor White

Step '3/5 生成启动脚本'

# 启动器统一用 .bat（UTF-8 无 BOM + chcp 65001，和桌面 Pi Web.bat 同一套写法）。
# run-link.bat = 一个终端同时跑 watchdog + 派发台（经 link-supervisor.mjs 监管）。
# watchdog.mjs / console-server.mjs 本体一行不改，各自的锁/日志/协议都不变。
# 调试单组件时直接前台跑 node watchdog.mjs / node console-server.mjs 即可。
$runLink = Join-Path $Root 'run-link.bat'
Write-BatFile $runLink @"
@echo off
setlocal
REM pi 链路启动器 —— 日常手动启动 watchdog + 派发台。
REM watchdog + 派发台 :$ConsolePort（经 link-supervisor.mjs 监管）。
REM pi-web 保持独立：它死了要靠 watchdog 报警，绝不能合进来。
REM 本文件只负责前台显示窗口；不创建开机自启。
title pi 链路 (watchdog + 派发台 :$ConsolePort)
set "NODE_EXE=$node"
if exist "%NODE_EXE%" goto node_found
set "NODE_EXE=node"
where node >nul 2>&1
if errorlevel 1 (
    echo.
    echo [错误] 找不到 Node.js。
    echo        请安装 Node.js 22+，或安装 Volta。
    echo.
    pause
    exit /b 1
)
:node_found
echo.
echo [pi-link] 启动中：watchdog + 派发台（一个终端）...
echo [pi-link] 日志：$StateDir\link.out.log
echo [pi-link] 按 Ctrl+C 停止（会连带停掉两个子服务）。
echo.
cd /d "%~dp0"
"%NODE_EXE%" "%~dp0link-supervisor.mjs"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo [pi-link] link-supervisor 已退出，错误码：%EXIT_CODE%
echo [pi-link] 如果不是手动停止，请查看上面的错误和 link.out.log。
pause
exit /b %EXIT_CODE%
"@

# 免密码模式下不输出 set PI_WEB_PASSWORD（否则 pi-web 会以为要鉴权）
if ($password) {
    $passwordLine = "set PI_WEB_PASSWORD=$password"
} else {
    $passwordLine = "REM 无 PI_WEB_PASSWORD：局域网可信模式（pi-web 会警告一行，无害）"
}

$runPiWeb = Join-Path $Root 'run-pi-web.bat'
# 每次都重新生成。为什么不再「已存在就保留」：
#   旧做法把 lan.host / piWeb.password 交给 bat 在运行时用 node 去读 local.json，
#   于是模板里出现了 `\`node -p "..."\`` 这种写法 —— 而 PowerShell 的双引号 here-string
#   里反引号是转义符，`` `n `` 被吃掉变成了【换行】，生成出来的 bat 于是断成两行：
#       for /f "usebackq delims=" %%i in (#       ode -p "..."\) do set "LANIP=%%i"
#   症状是窗口里一堆「'ks' 不是内部或外部命令」「'UTF-8' 不是…」——
#   看起来像乱码，其实是 bat 结构被切坏了。旧做法靠「不覆盖手维护的旧文件」
#   才碰巧没炸，一旦重新生成就坏。
# 现在改成：LANIP 和密码在生成时直接写进去（和 run-link.bat 里的密码一样），
# 运行时不再读文件，模板里也就没有反引号、没有 for /f 的转义地雷。
$piWebPasswordLine = if ($password) { "set `"PI_WEB_PASSWORD=$password`"" } else { "set `"PI_WEB_PASSWORD=`"" }
Write-BatFile $runPiWeb @"
@echo off
setlocal enabledelayedexpansion
REM pi-web 启动器（局域网模式）—— 日常就用这一个。
REM 本文件由 setup.ps1 生成：地址/密码在生成时就写好了，运行时不再读 local.json。
REM 必须带 -H 0.0.0.0：不带只绑 127.0.0.1，手机连不上。
REM 先杀旧实例：$PiWebPort 上两个 listener（127.0.0.1 + 0.0.0.0）= 两套内存状态（脑裂），
REM 看门狗会把正在跑的会话误报成异常中断。
set "NODE_OPTIONS=%NODE_OPTIONS% --network-family-autoselection-attempt-timeout=2000 --require=%~dp0pi-web-env.cjs"
REM pi-subagents uses this to identify the Pi package that owns pi-web.
set "PI_SUBAGENTS_PI_CODING_AGENT_PACKAGE_ROOT=$PiWebAgentRoot"
title pi-web 局域网版 (0.0.0.0:$PiWebPort)
set "SILENT="
if /i "%~1"=="--silent" set "SILENT=1"
set "LANIP=$lanHost"
$piWebPasswordLine
set "AUTHMODE=无密码（局域网可信模式）"
if defined PI_WEB_PASSWORD set "AUTHMODE=密码保护（用户名 pi）"
echo.
echo [pi-web] 检查 $PiWebPort 端口上是否已有实例在跑...
set "PORT_PID="
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":$PiWebPort" ^| findstr "LISTENING"') do set "PORT_PID=%%a"
if not defined PORT_PID goto start
echo [pi-web] 端口被占用，先停掉旧实例（防止双实例脑裂）...
taskkill /PID !PORT_PID! /T /F >nul 2>&1
timeout /t 2 /nobreak >nul
:start
echo.
echo [pi-web] 启动中...
echo.
echo   [OK] 这台电脑请打开   http://localhost:$PiWebPort
echo   [OK] 手机/别的设备请开 http://!LANIP!:$PiWebPort
echo.
echo   [!] 不要用 0.0.0.0 —— 那是"监听所有网卡"的绑定地址，不是网址，
echo       浏览器打开它必然失败（pi-web 自己会打印 Network: http://0.0.0.0:端口，
echo       那是它在报告监听范围，不是让你点的链接）。
echo.
echo [pi-web] 认证：!AUTHMODE!
echo.
cd /d "%~dp0"
if defined SILENT set "PI_WEB_NO_OPEN=1"
REM 【必须写 call pi-web，不能只写 pi-web】—— 这是个真会出事的安全坑：
REM   本文件用了 setlocal，而 npm 生成的 pi-web.cmd 里有 endLocal。
REM   批处理里【不】带 call 直接执行另一个 .cmd 时，控制权是转移过去的，
REM   于是 shim 的 endLocal 把【调用方】的 setlocal 作用域一起关掉了 ——
REM   本文件里 set "PI_WEB_PASSWORD=…" 就这么丢了。实测：
REM     pi-web -H 0.0.0.0 …        -> pi-web: "without authentication"（裸奔！）
REM     call pi-web -H 0.0.0.0 …   -> pi-web: "with password authentication"
REM   症状极其隐蔽：窗口里照样打印「认证：密码保护（用户名 pi）」，
REM   但 pi-web 其实没鉴权，等于把能执行任意命令的 agent 裸奔到局域网。
REM   fix-split-brain.ps1 里有一条断言专门盯这个（配了密码却不鉴权 = 报红）。
call pi-web -H 0.0.0.0 -p $PiWebPort
echo.
echo [pi-web] 服务已退出。
if not defined SILENT pause
"@

if ($ScriptsOnly) {
    Say ''
    Say '按 -ScriptsOnly 只生成配置与启动脚本，到此结束。' -ForegroundColor Yellow
    exit 0
}

# ── 5. 防火墙 ──────────────────────────────────────────────────────────
Step '4/5 防火墙规则'
if ($SkipTasks) {
    Warn '按参数跳过'
} elseif (-not (Test-Admin)) {
    Warn '当前不是管理员，跳过防火墙规则。请用管理员 PowerShell 重跑，或手动执行：'
    Say "    New-NetFirewallRule -DisplayName 'pi-android-link console' -Direction Inbound -Protocol TCP -LocalPort $ConsolePort -Action Allow -Profile Private"
    Say "    New-NetFirewallRule -DisplayName 'pi-android-link gateway'  -Direction Inbound -Protocol TCP -LocalPort $GatewayPort  -Action Allow -Profile Private"
} else {
    # 关于防火墙：这里**故意不加任何端口级封禁规则**。
    # 很多机器的局域网被 Windows 判成了 Public（不是 Private）：
    #   Get-NetConnectionProfile -> NetworkCategory = Public
    # 所以"在 Public 下封禁 30141"会把自己的手机一起挡在外面。
    # 手机能通通常靠的是 Node.js 自带的入站规则（Profile = Private, Public 都 Allow）。
    $netCat = (Get-NetConnectionProfile -ErrorAction SilentlyContinue |
               Select-Object -First 1).NetworkCategory
    if ($netCat) {
        Warn "当前局域网被 Windows 归类为 $netCat —— 故意不按 profile 加封禁规则（会误伤自己的手机）"
    }

    foreach ($item in @(@{ n = 'pi-android-link console'; p = $ConsolePort },
                        @{ n = 'pi-android-link gateway'; p = $GatewayPort })) {
        $existing = Get-NetFirewallRule -DisplayName $item.n -ErrorAction SilentlyContinue
        if ($existing) {
            Ok "规则已存在：$($item.n)"
        } else {
            New-NetFirewallRule -DisplayName $item.n -Direction Inbound -Protocol TCP `
                -LocalPort $item.p -Action Allow -Profile Private | Out-Null
            Ok "已放行 TCP $($item.p)（仅专用网络）"
        }
    }
}

# ── 6. 手动启动（不注册开机自启） ────────────────────────────────────────
Step '5/5 启动方式'
Say '按当前要求，不注册计划任务，也不写入 Startup\pi-android-link.vbs。'
Say '手动启动 watchdog + 派发台：双击 run-link.bat'
Say '手动启动 pi-web：双击 run-pi-web.bat'
Say ''
Warn 'run-link.bat 和 run-pi-web.bat 都是前台窗口；关闭对应窗口会停止对应服务。'

# ── 收集结果 ───────────────────────────────────────────────────────────
Step '部署完成，自检'
Start-Sleep -Seconds 4

# 消息中转并进派发台了，所以这里只探派发台本身（它同时是中转）
$brokerOk = $false
try {
    $probe = Invoke-RestMethod -Uri "http://127.0.0.1:$ConsolePort/api/state?t=$token" -TimeoutSec 8
    if ($probe.running -ne $null) { $brokerOk = $true; Ok '消息中转（派发台 /api/state）正常' }
} catch { }
if (-not $brokerOk) { Warn '中转还没起来，稍后手动确认（看 ' + (Join-Path $StateDir 'console.log') + '）' }

try {
} catch { }

$consoleOk = $false
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$ConsolePort/?t=$token" -TimeoutSec 10 -UseBasicParsing
    if ($r.StatusCode -eq 200) { $consoleOk = $true; Ok '派发台可访问' }
} catch { }
if (-not $consoleOk) { Warn '派发台还没起来，看 ' + (Join-Path $StateDir 'console.out.log') }

Say ''
& $node (Join-Path $Root 'verify.mjs') --quiet

Write-Host @"

+----------------------------------------------------------------+
|  还差两步：                                                     |
+----------------------------------------------------------------+

  [1] 用带密码的方式重启 pi-web（否则手机连不上，也没有鉴权）
      双击 run-pi-web.bat
      —— 或者手动：
        set PI_WEB_PASSWORD=$password
        pi-web -H 0.0.0.0 -p $PiWebPort

      ⚠ 之所以必须带密码：pi-web 能执行任意命令，无密码绑 0.0.0.0
        等于把整台机器交给同一 WiFi 上的任何人。

  [2] 手机装「Pi 通知」App，并授权电池白名单
      1. 手机浏览器打开 http://$lanHost`:$ConsolePort/app
      2. 点「下载 APK」安装；再点「一键配置并启动」（自动写好地址+令牌+回执）
      3. 弹「电池白名单」就点「去设置」并允许 —— 不白名单，息屏闲置会被系统断网
      4. ColorOS：应用管理 → Pi 通知 → 耗电管理 → 允许后台活动 / 自启动 / 最近任务加锁

  手机派发台：
      http://$lanHost`:$ConsolePort/?t=$token
      （第一次带 ?t= 打开，之后写 cookie，可以加书签）

  手机看会话（pi-web 本体）：
      http://$lanHost`:$PiWebPort

  异地通知（出门在外也能收，不需要买/租服务器、不需要账号）：
      node wan-report.mjs          # 体检：公网 IP / IPv6 / 隧道 / 端口映射 各是什么状态
      手机 App 会自己在一份候选地址清单里切换（设置页里能看到清单与探测结果）
      出门前在家点一次 http://$lanHost`:$ConsolePort/app 的「一键配置」即可预置

  验证推送链路：
      node watchdog.mjs --simulate model_error   # 把某一种判定走一遍真实发布

  日志：
      $StateDir\watchdog.out.log
      $StateDir\messages.jsonl  （消息缓存）
      $StateDir\console.out.log
      $StateDir\watchdog.log        （判定与通知的结构化记录）

  卸载：
      Get-ScheduledTask -TaskName 'pi-android-link-*' | Unregister-ScheduledTask -Confirm:`$false

"@ -ForegroundColor DarkCyan
