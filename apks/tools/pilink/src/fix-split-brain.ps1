#Requires -Version 5.1
<#
  一键诊断 / 修复 pi-web 双实例脑裂。

  背景：同一个端口上可能同时存在两个 pi-web —— 老的绑 127.0.0.1、新的绑 0.0.0.0。
  两个 listener 都能建连（127.0.0.1 比 0.0.0.0 更具体所以优先匹配），于是：
    电脑浏览器开 localhost        -> 老实例
    手机开 192.168.1.100           -> 新实例
  两者是两套独立的内存状态（runningSessionIds 不同），会话文件却是同一个目录。
  后果：看门狗的判定基准变成错的那一半，会对正在跑的会话误报"异常中断"。

  双击 fix-split-brain.bat 运行；报告写入同目录 fix-split-brain-report.txt。

  参数：
    -DryRun      只诊断，不停止任何进程
    -Force       不询问，直接执行
    -StartPiWeb  若清理后一个实例都不剩，顺手启动 run-pi-web.bat
    -LogPath     报告路径
    -NoStart     只清理，不自动启动 pi-web
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Force,
    [switch]$StartPiWeb,   # 兼容旧写法；默认已经会启动，这个参数现在没作用
    [switch]$NoStart,
    [string]$LogPath
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
if (-not $LogPath) { $LogPath = Join-Path $Root 'fix-split-brain-report.txt' }

Start-Transcript -Path $LogPath -Force | Out-Null

$script:ExitCode = 0

function Line { param([string]$Char = '=', [int]$Count = 68)
    Write-Host ($Char * $Count)
}
function Step { param([string]$Text, [int]$Index, [int]$Total = 6)
    Write-Host ''
    Write-Host "[$Index/$Total] $Text" -ForegroundColor Cyan
}
function Ok   { param([string]$Text) Write-Host "  [OK]   $Text" -ForegroundColor Green }
function Warn { param([string]$Text) Write-Host "  [!]    $Text" -ForegroundColor Yellow }
function Bad  { param([string]$Text) Write-Host "  [X]    $Text" -ForegroundColor Red }
function Info { param([string]$Text) Write-Host "         $Text" }

function Get-IsLoopbackAddress {
    param([string]$Address)
    return @('127.0.0.1', '::1', 'localhost') -contains $Address
}
function Get-IsAllInterfacesAddress {
    param([string]$Address)
    return @('0.0.0.0', '::') -contains $Address
}

<#
  用 .NET 直接发 GET，而不是 Invoke-WebRequest。
  原因：Invoke-WebRequest 失败时会把错误记录写进 transcript，报告里就会混进
  一行 `PS>TerminatingError(Invoke-WebRequest): "远程服务器返回错误: (401)..."`
  这种噪声（而 401 恰好是我们**期望**看到的结果）。用 .NET 异常不会进错误流。
  返回 @{ Status = <int>; Body = <string>; Error = <string|null> }
#>
function Invoke-HttpProbe {    param([string]$Url, [hashtable]$Headers, [int]$TimeoutSec = 10)
    try {
        $req = [System.Net.HttpWebRequest]::Create($Url)
        $req.Method = 'GET'
        $req.Timeout = $TimeoutSec * 1000
        $req.AllowAutoRedirect = $false
        if ($Headers) { foreach ($k in $Headers.Keys) { $req.Headers.Add($k, $Headers[$k]) } }
        $resp = $req.GetResponse()
        $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
        $body = $reader.ReadToEnd()
        $reader.Close()
        $code = [int]$resp.StatusCode
        $resp.Close()
        return @{ Status = $code; Body = $body; Error = $null }
    } catch [System.Net.WebException] {
        $webResp = $_.Exception.Response
        if ($webResp) {
            $code = [int]$webResp.StatusCode
            $body = ''
            try {
                $reader = New-Object System.IO.StreamReader($webResp.GetResponseStream())
                $body = $reader.ReadToEnd()
                $reader.Close()
            } catch { }
            $webResp.Close()
            return @{ Status = $code; Body = $body; Error = $null }
        }
        return @{ Status = 0; Body = ''; Error = $_.Exception.Message }
    } catch {
        return @{ Status = 0; Body = ''; Error = $_.Exception.Message }
    }
}

try {
    Line
    Write-Host ' pi-web 双实例 / 绑定诊断与修复' -ForegroundColor White
    Write-Host (" 时间 {0}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
    Write-Host (" 报告 {0}" -f $LogPath)
    Line

    # ── 1. 读配置 ──────────────────────────────────────────────────────
    Step '读取链路配置' 1
    $LocalJson = Join-Path $env:USERPROFILE '.pi\android-link\local.json'
    $Port = 30141
    $ConsolePort = 8787
    $LanHost = '127.0.0.1'
    $Password = ''
    $ConsoleToken = ''
    $Wan = $null
    $Root = Split-Path -Parent $PSCommandPath

    if (Test-Path $LocalJson) {
        # PowerShell 5.1 的 Set-Content -Encoding UTF8 会写 BOM，ConvertFrom-Json 会炸，先剥掉
        $raw = [System.IO.File]::ReadAllText($LocalJson).TrimStart([char]0xFEFF)
        $cfg = $raw | ConvertFrom-Json
        if ($cfg.lan.host)        { $LanHost = $cfg.lan.host }
        if ($cfg.lan.piWebPort)   { $Port = [int]$cfg.lan.piWebPort }
        if ($cfg.lan.consolePort) { $ConsolePort = [int]$cfg.lan.consolePort }
        if ($cfg.piWeb.password)  { $Password = $cfg.piWeb.password }
        if ($cfg.lan.consoleToken){ $ConsoleToken = $cfg.lan.consoleToken }
        if ($cfg.wan)             { $Wan = $cfg.wan }
        Ok "local.json 已读取"
        Info "路径      : $LocalJson"
        Info "局域网地址: $LanHost   pi-web 端口: $Port"
        Info "密码      : $(if ($Password) { "已配置（$($Password.Length) 位）" } else { '未配置  ← 手机连不上且没有鉴权' })"
        Info "中转/派发台: http://127.0.0.1:$ConsolePort"
        Info "派发台令牌: $(if ($ConsoleToken) { '已配置' } else { '未配置  ← 派发台无法鉴权' })"
    } else {
        Warn "找不到 $LocalJson"
        Info "回退用默认端口 $Port。先跑一次 setup.ps1 生成配置。"
    }

    # ── 2. 当前监听者 ──────────────────────────────────────────────────
    Step "当前监听 $Port 端口的进程" 2
    $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    $entries = @()
    foreach ($l in $listeners) {
        $p = Get-CimInstance Win32_Process -Filter "ProcessId = $($l.OwningProcess)" -ErrorAction SilentlyContinue
        $entries += [pscustomobject]@{
            Address   = $l.LocalAddress
            Pid       = $l.OwningProcess
            ParentPid = if ($p) { $p.ParentProcessId } else { 0 }
            Cmd       = if ($p) { $p.CommandLine } else { '(进程已退出)' }
            IsLoopback = Get-IsLoopbackAddress $l.LocalAddress
            IsLan      = Get-IsAllInterfacesAddress $l.LocalAddress
        }
    }

    if ($entries.Count -eq 0) {
        Warn "端口 $Port 上没有任何监听者 —— pi-web 没在跑"
        Info "下一步：双击 run-pi-web.bat 启动（它会绑 0.0.0.0 并带密码）"
    } else {
        foreach ($e in $entries) {
            $tag = if ($e.IsLoopback) { '仅回环 → 手机连不上 但电脑能连' }
                   elseif ($e.IsLan)  { '全网卡 → 手机能连' }
                   else               { '指定网卡' }
            Info ("{0,-16} pid {1,-7} {2}" -f "$($e.Address):$Port", $e.Pid, $tag)
            $short = $e.Cmd; if ($short.Length -gt 96) { $short = $short.Substring(0, 96) + '...' }
            Info ("                 $short")
        }
    }

    $loopbackEntries = @($entries | Where-Object { $_.IsLoopback })
    $lanEntries      = @($entries | Where-Object { -not $_.IsLoopback })

    # 顺便探测：无凭据访问 API 应当被拒（401）。返回 200 说明这个实例根本没设密码。
    # 实测踩过：用户双击了一个裸 pi-web（不带参数）→ 默认绑 127.0.0.1 且无密码。
    $passwordEnforced = $false
    # local.json 里到底配没配密码。没配 = 用户主动选择的"局域网免密码模式"，
    # 那是合法状态，不该判成故障。
    $passwordExpected = [bool]$Password
    if ($entries.Count -ge 1) {
        $anon = Invoke-HttpProbe -Url "http://127.0.0.1:$Port/api/agent/running" -TimeoutSec 8
        $passwordEnforced = ($anon.Status -eq 401)
    }

    Write-Host ''
    if ($entries.Count -eq 0) {
        $verdict = 'NO_INSTANCE'
        Warn '判定：没有实例在跑'
    } elseif ($entries.Count -ge 2 -and $loopbackEntries.Count -ge 1 -and $lanEntries.Count -ge 1) {
        $verdict = 'SPLIT_BRAIN'
        Bad ("判定：★ 双实例脑裂 —— 端口上 {0} 个监听者，电脑和手机各连到了不同的实例" -f $entries.Count)
        Info '两套独立内存状态 + 同一个会话目录 => 看门狗会对正在跑的会话误报"异常中断"'
    } elseif ($entries.Count -ge 2) {
        $verdict = 'MULTI'
        Bad ("判定：★ 端口上有 {0} 个监听者（非典型组合），只能保留一个" -f $entries.Count)
    } elseif ($loopbackEntries.Count -eq 1) {
        $verdict = 'LOOPBACK_ONLY'
        Warn '判定：只绑了 127.0.0.1 —— 手机连不上（但电脑正常）'
    } elseif ($passwordExpected -and -not $passwordEnforced) {
        $verdict = 'NO_PASSWORD'
        Bad '判定：★ local.json 里配了密码，但 pi-web 没启用鉴权 —— 重启 pi-web 让它读到同一个 PI_WEB_PASSWORD'
    } else {
        $verdict = 'HEALTHY'
        Ok '判定：只有一个实例、已绑局域网、密码生效 ✓ 不用动'
    }

    Step '处置计划' 3
    # 只要不是 HEALTHY，就一律【全停 + 重启一个正确的】。
    # 比起逐个分辨哪个该留，这样更简单也更不容易错 —— 反正会话都在磁盘上。
    $toKill = @()

    if ($verdict -ne 'HEALTHY' -and $verdict -ne 'NO_INSTANCE') {
        foreach ($e in $entries) {
            $toKill += [pscustomobject]@{ Pid = $e.Pid; Why = "持有 $($e.Address):$Port 监听" }
            # 顺手收掉它的启动器外壳（pi-web.js / run-pi-web.bat），免得余渣再拉起来
            if ($e.ParentPid -gt 0) {
                $par = Get-CimInstance Win32_Process -Filter "ProcessId = $($e.ParentPid)" -ErrorAction SilentlyContinue
                if ($par -and $par.CommandLine -match 'pi-web') {
                    $toKill += [pscustomobject]@{ Pid = $par.ProcessId; Why = '该实例的启动器外壳' }
                }
            }
        }
    }

    $toKill = @($toKill | Sort-Object Pid -Unique)

    if ($toKill.Count -eq 0) {
        Ok '不需要停止任何进程'
        if ($verdict -eq 'NO_INSTANCE' -and $StartPiWeb) {
            Info '按 -StartPiWeb：即将启动 run-pi-web.bat'
        }
    } else {
        Info '将停止：'
        foreach ($k in $toKill) {
            $p = Get-CimInstance Win32_Process -Filter "ProcessId = $($k.Pid)" -ErrorAction SilentlyContinue
            $c = if ($p) { $p.CommandLine } else { '(进程已退出)' }
            if ($c.Length -gt 90) { $c = $c.Substring(0, 90) + '...' }
            Info ("  pid {0,-7} {1}" -f $k.Pid, $k.Why)
            Info ("           $c")
        }
        $keep = @($entries | Where-Object { $toKill.Pid -notcontains $_.Pid })
        if ($keep.Count -gt 0) {
            Info '保留：'
            foreach ($e in $keep) { Info ("  pid {0,-7} $($e.Address):$Port" -f $e.Pid) }
        }
        if ($verdict -eq 'LOOPBACK_ONLY') {
            Info '停止后端口会空出来，需要用 run-pi-web.bat 重新以 0.0.0.0 启动'
        }
    }

    # ── 4. 确认 ────────────────────────────────────────────────────────
    Step '确认' 4
    $doKill = $false
    if ($toKill.Count -eq 0) {
        Info '无事可做，跳过'
    } elseif ($DryRun) {
        Warn '按 -DryRun：只诊断，不执行停止'
    } elseif ($Force) {
        Warn '按 -Force：不询问，直接执行'
        $doKill = $true
    } else {
        Info '⚠ 停止老实例会掐断挂在它上面的会话（包括你正在对话的那个）。'
        Info '  会话已落盘，之后从会话列表 / /resume 接回来即可。'
        Write-Host ''
        $answer = Read-Host '  确认停止上面列出的进程吗？输入 YES 继续'
        if ($answer -eq 'YES' -or $answer -eq 'yes') { $doKill = $true } else { Warn '用户取消，什么都没做' }
    }

    # ── 5. 执行 ────────────────────────────────────────────────────────
    Step '执行' 5
    if ($doKill) {
        foreach ($k in $toKill) {
            try {
                Stop-Process -Id $k.Pid -Force -ErrorAction Stop
                Ok "已停止 pid $($k.Pid)"
            } catch {
                Warn "停止 pid $($k.Pid) 失败：$($_.Exception.Message)"
            }
        }
        Start-Sleep -Seconds 2
        # 万一子进程先死、父进程还赖着，再补一刀
        foreach ($k in $toKill) {
            $still = Get-Process -Id $k.Pid -ErrorAction SilentlyContinue
            if ($still) {
                try { Stop-Process -Id $k.Pid -Force -ErrorAction Stop; Ok "补刀 pid $($k.Pid)" }
                catch { Warn "pid $($k.Pid) 仍在：$($_.Exception.Message)" }
            }
        }
    } elseif ($toKill.Count -gt 0) {
        Info '（未执行停止）'
    } else {
        Info '（无需执行）'
    }

    # ── 6. 复查 ────────────────────────────────────────────────────────
    Step '复查' 6
    Start-Sleep -Seconds 2
    $after = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    $afterLoop = @($after | Where-Object { Get-IsLoopbackAddress $_.LocalAddress })
    $afterLan  = @($after | Where-Object { -not (Get-IsLoopbackAddress $_.LocalAddress) })

    if ($after.Count -eq 0) {
        Warn "端口 $Port 上已无监听者"
    } else {
        foreach ($a in $after) { Info ("{0,-16} pid {1}" -f "$($a.LocalAddress):$Port", $a.OwningProcess) }
    }

    if ($after.Count -eq 1 -and $afterLan.Count -eq 1) {
        Ok '只剩一个实例，且已绑局域网 ✓ 可以过关'
    } elseif ($after.Count -eq 1 -and $afterLoop.Count -eq 1) {
        Warn '只剩一个实例，但仍只绑 127.0.0.1 —— 手机还是连不上'
        if (-not $DryRun) { Info '下一步：双击 run-pi-web.bat' }
    } elseif ($after.Count -ge 2) {
        Bad '仍有多个监听者，说明还有别的实例'
    } elseif ($after.Count -eq 0 -and -not $DryRun) {
        if (-not $NoStart) {
            $launcher = Join-Path $Root 'run-pi-web.bat'
            if (Test-Path $launcher) {
                Info '正在启动 run-pi-web.bat（隐藏窗口，不会被人手滑关掉）...'
                # -WindowStyle Hidden 很关键：pi-web 由这个 cmd 前台托管，
                # 窗口被关掉 = pi-web 死掉（实测踩过这个坑）
                Start-Process -FilePath 'cmd.exe' -ArgumentList "/c `"$launcher`"" -WorkingDirectory $Root -WindowStyle Hidden
                Start-Sleep -Seconds 12
                $after2 = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
                if ($after2.Count -ge 1) { Ok "已启动：$($after2[0].LocalAddress):$Port" }
                else { Warn '启动了但端口还没起来，稍等再看' }
            } else {
                Warn "找不到 $launcher"
            }
        } else {
            Info '按 -NoStart：没有自动启动。手动双击 run-pi-web.bat'
        }
    }

    # ── 附带健康检查 ───────────────────────────────────────────────────
    Write-Host ''
    Line '-' 68
    Write-Host ' 链路健康检查' -ForegroundColor Cyan
    Line '-' 68

    # 消息中转（就在派发台里，没有独立的中转进程）
    $brokerProbe = Invoke-HttpProbe -Url "http://127.0.0.1:$ConsolePort/api/state?t=$ConsoleToken" -TimeoutSec 8
    if ($brokerProbe.Status -eq 200) {
        Ok '消息中转（派发台 /api/state）正常'
    } else {
        Bad "派发台 :$ConsolePort 连不上，中转也就没了（双击 run-link.bat 启动）"
    }

    # 派发台：无令牌必须 401
    $consoleProbe = Invoke-HttpProbe -Url "http://127.0.0.1:$ConsolePort/api/state" -TimeoutSec 8
    if ($consoleProbe.Status -eq 401) {
        Ok "派发台 :$ConsolePort 在跑且要求令牌 (401)"
    } elseif ($consoleProbe.Status -eq 200) {
        Bad "派发台 :$ConsolePort 无令牌也能访问 —— 鉴权没生效（检查 local.json 的 consoleToken）"
    } else {
        Bad "派发台 :$ConsolePort 连不上（双击 run-link.bat 启动）$(if ($consoleProbe.Error) { " — $($consoleProbe.Error)" })"
    }

    # 看门狗：锁文件 + PID 存活
    $lockFile = Join-Path $env:USERPROFILE '.pi\android-link\watchdog.lock'
    if (Test-Path $lockFile) {
        $wdPid = 0
        [int]::TryParse(([System.IO.File]::ReadAllText($lockFile)).Trim(), [ref]$wdPid) | Out-Null
        $alive = $false
        if ($wdPid -gt 0) {
            try { $null = Get-Process -Id $wdPid -ErrorAction Stop; $alive = $true } catch { $alive = $false }
        }
        if ($alive) { Ok "看门狗在跑 (pid $wdPid)" } else { Bad "看门狗锁文件在但 pid $wdPid 已死 —— 双击 run-link.bat" }
    } else {
        Bad '看门狗没在跑（没有 watchdog.lock）—— 双击 run-link.bat'
    }

    # 防火墙：重点不是"有没有封禁"，而是"有没有东西误伤 30141"。
    # 本机局域网被 Windows 归类为 Public（实测），所以按 profile 封禁会把手机也挡掉。
    $netCat = (Get-NetConnectionProfile -ErrorAction SilentlyContinue | Select-Object -First 1).NetworkCategory
    Info "网络类别      : $netCat（本机局域网实测为 Public，属正常）"
    $blockers = @(Get-NetFirewallRule -Direction Inbound -Action Block -Enabled True -ErrorAction SilentlyContinue | Where-Object {
        $pf = $_ | Get-NetFirewallPortFilter -ErrorAction SilentlyContinue
        $pf -and ($pf.LocalPort -contains '$Port')
    })
    if ($blockers.Count -eq 0) {
        Ok "防火墙：没有 Block 规则命中 $Port ✓ 手机可达"
    } else {
        Bad ("防火墙：有 " + $blockers.Count + " 条 Block 规则命中 $Port —— 手机可能连不上！")
        foreach ($bl in $blockers) { Info ("  " + $bl.DisplayName + "  (Profile: " + $bl.Profile + ")") }
    }

    # pi-web 鉴权（只在有监听者时试；失败会计入 pi-web 的限流，一次无所谓）
    #
    # 【新增】先做一次「不带任何凭据」的探测：配了密码却答 200 = pi-web 实际在裸奔。
    # 这个坑非常隐蔽：启动器窗口里明明打印「认证：密码保护（用户名 pi）」，
    # 但因为批处理里没写 call pi-web（npm 的 .cmd 里有 endLocal，
    # 会把调用方 setlocal 的作用域一起关掉），set 好的 PI_WEB_PASSWORD 就丢了，
    # pi-web 收不到这个变量 → 真的不鉴权。
    # 而这台机器上的 pi-web 能执行任意命令，裸奔等于把整台机器交给局域网。
    if ($after.Count -ge 1 -and $Password) {
        $anon = Invoke-HttpProbe -Url "http://127.0.0.1:$Port/api/agent/running" -TimeoutSec 10
        if ($anon.Status -eq 200) {
            Bad '★ 配了密码但 pi-web 并没有鉴权（不带凭据也能调 API）—— agent 正在局域网裸奔'
            Info '多半是启动器里写成了 "pi-web ..." 而不是 "call pi-web ..."'
            Info '修法：setup.ps1 -ScriptsOnly 重新生成 run-pi-web.bat，然后双击它重启 pi-web'
        } elseif ($anon.Status -eq 401) {
            Ok 'pi-web 确实在鉴权（不带凭据被 401 拒掉）'
        }
    }

    if ($after.Count -ge 1) {
        if (-not $Password) {
            Ok 'pi-web 鉴权：免密码模式（local.json 未配密码）—— 局域网内直接可访问'
        } else {
            $token = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("pi:$Password"))
            $authProbe = Invoke-HttpProbe -Url "http://127.0.0.1:$Port/api/agent/running" `
                -Headers @{ Authorization = "Basic $token" } -TimeoutSec 15
            if ($authProbe.Status -eq 200) {
                $running = 0
                try { $running = @(($authProbe.Body | ConvertFrom-Json).runningSessionIds).Count } catch { }
                Ok "pi-web Basic 认证通过（当前在跑 $running 个会话）"
            } elseif ($authProbe.Status -eq 401) {
                Bad 'pi-web 拒绝了这个密码 —— local.json 的 piWeb.password 与 pi-web 启动时的 PI_WEB_PASSWORD 不一致'
                Info '修法：双击 run-pi-web.bat 重启 pi-web（它从 local.json 取同一个密码）'
            } elseif ($authProbe.Status -eq 429) {
                Warn 'pi-web 正在限流（429）—— 稍等 1 分钟再试。看门狗的鉴权安全阀会因此自动停手'
            } else {
                Warn "pi-web 探测失败：$(if ($authProbe.Error) { $authProbe.Error } else { "HTTP $($authProbe.Status)" })"
            }
        }
    }

    # ── 异地（公网）通知体检 ───────────────────────────────────────────
    # 出门在外能不能收到通知，取决于「统一出口 + 至少一条公网地址」。
    # 这一段只读不改：真正的体检在 wan-report.mjs（它还会逐个自检候选地址）。
    Write-Host ''
    Step '异地通知（不用服务器、不用账号）' 7 7
    $gatewayPort = 8788
    if ($Wan) { $gatewayPort = $Wan.gatewayPort }
    $gw = Invoke-HttpProbe -Url "http://127.0.0.1:$gatewayPort/pi/ping?t=$ConsoleToken" -TimeoutSec 5
    if ($gw.Status -eq 200) {
        Ok "统一出口 http://0.0.0.0:$gatewayPort 在监听（派发台路由 + pi-web 反代）"
    } else {
        Bad "统一出口 :$gatewayPort 没响应（HTTP $(if ($gw.Error) { $gw.Error } else { $gw.Status })）"
        Info '手机在外面将收不到通知。最常见原因：pi-web 没配密码（安全阀会拒绝开公网入口）'
        Info '修法：给 local.json 的 piWeb.password 填上密码 → 双击 run-pi-web.bat → 再双击本脚本'
    }
    $wanReport = Join-Path $Root 'wan-report.mjs'
    if (Test-Path $wanReport) {
        $wanText = (& node $wanReport 2>&1) -join "`n"
        foreach ($line in ($wanText -split "`n")) {
            if ($line -match '公网 IPv4|公网 IPv6|隧道\s|首选公网地址') { Info $line.Trim() }
        }
    }

    Write-Host ''
    Line
    if ($verdict -eq 'HEALTHY' -and $after.Count -eq 1 -and $afterLan.Count -eq 1) {
        Write-Host ' 结论：拓扑正常，无需修复。' -ForegroundColor Green
        $script:ExitCode = 0
    } elseif ($DryRun) {
        Write-Host ' 结论：DRY RUN 结束，什么都没改动。去掉 -DryRun 或直接双击即可执行。' -ForegroundColor Yellow
        $script:ExitCode = 1
    } elseif ($after.Count -eq 1 -and $afterLan.Count -eq 1) {
        Write-Host ' 结论：已修好，端口上只剩一个绑局域网的实例。' -ForegroundColor Green
        Write-Host '       浏览器开 http://<本机IP>:' -NoNewline
        Write-Host $Port -ForegroundColor White
        Write-Host '       复查：cd C:\pi-link && node verify.mjs   （E3 应为 PASS）'
        $script:ExitCode = 0
    } else {
        Write-Host ' 结论：还没到理想状态，按上面 [OK]/[!]/[X] 逐条处理。' -ForegroundColor Yellow
        $script:ExitCode = 2
    }
    Write-Host ''
    Write-Host (" 报告已写入：{0}" -f $LogPath) -ForegroundColor White
    Line

Write-Host ''
    Line
    Write-Host ' 登录 pi-web 用的凭据' -ForegroundColor Cyan
    Line
    Info "地址  : http://${LanHost}:$Port   （本机也可 http://localhost:$Port）"
    Info '用户名: pi'
    if ($Password) {
        Info "密码  : $Password"
    } else {
        Info "密码  : （无）—— 局域网免密码模式，打开就要用，不会弹认证框"
    }
    Info '浏览器弹的那个框是 HTTP Basic 对话框（Chrome 中文界面就显示"用户名/密码"）。'
    Info "不想用它就直接开 http://${LanHost}:$Port/login —— 那个页面只要填密码。"
    Info '这份报告含密码，别外传（.gitignore 已排除）。'
    Line
}
catch {
    Write-Host ''
    Bad "脚本异常：$($_.Exception.Message)"
    Write-Host $_.ScriptStackTrace
    $script:ExitCode = 99
}

finally {
    Stop-Transcript | Out-Null
}

exit $script:ExitCode
