# install-autostart.ps1
# 注册 / 卸载 Windows 计划任务：定时运行 pi-skills-sync
# 这样即使 Pi / pi-web 没开着，新增的 skill 也会被自动传到 GitHub。
#
# 安装（每 30 分钟 + 每次登录时）：
#   powershell -ExecutionPolicy Bypass -File install-autostart.ps1 -EveryMinutes 30
#
# 卸载：
#   powershell -ExecutionPolicy Bypass -File install-autostart.ps1 -Uninstall
#
# 查看：
#   Get-ScheduledTask -TaskName PiSkillsGitHubSync* | Get-ScheduledTaskInfo
#   Start-ScheduledTask -TaskName PiSkillsGitHubSync      # 立即跑一次

[CmdletBinding()]
param(
    [int]$EveryMinutes = 30,
    [switch]$Uninstall,
    [string]$TaskName = "PiSkillsGitHubSync",
    [string]$PythonExe = "",          # 可选：手动指定 python 解释器
    [switch]$NoLogonTrigger           # 可选：不要"登录时"触发器
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SyncPy    = Join-Path $ScriptDir "sync.py"
$LogonName = "$TaskName-AtLogon"

function Remove-Task([string]$name) {
    $t = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($t) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false
        Write-Host "已卸载计划任务: $name"
    } else {
        Write-Host "计划任务不存在: $name"
    }
}

if ($Uninstall) {
    Remove-Task $TaskName
    Remove-Task $LogonName
    exit 0
}

# ---------------------------------------------------------------- 找 python
function Resolve-Python {
    param([string]$Explicit)

    if ($Explicit) {
        if (-not (Test-Path $Explicit)) { throw "指定的 PythonExe 不存在: $Explicit" }
        $dir = Split-Path -Parent $Explicit
        $pw = Join-Path $dir "pythonw.exe"
        return @{ Exe = $(if (Test-Path $pw) { $pw } else { $Explicit }); Prefix = @() }
    }

    # 1) py 启动器（任何正规 Python 安装都会装，最稳）
    foreach ($launcher in @("$env:WINDIR\pyw.exe", "$env:WINDIR\py.exe")) {
        if (Test-Path $launcher) {
            return @{ Exe = $launcher; Prefix = @("-3") }
        }
    }

    # 2) LOCALAPPDATA\Programs\Python\Python3xx\pythonw.exe（取版本号最大的）
    $globs = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python3*\pythonw.exe"),
        "C:\Python3*\pythonw.exe",
        "C:\Program Files\Python3*\pythonw.exe"
    )
    $found = @()
    foreach ($g in $globs) { $found += @(Get-ChildItem -Path $g -ErrorAction SilentlyContinue) }
    if ($found.Count -gt 0) {
        $best = $found | Sort-Object -Property FullName -Descending | Select-Object -First 1
        return @{ Exe = $best.FullName; Prefix = @() }
    }

    # 3) PATH 里的 pythonw / python
    foreach ($n in @("pythonw", "python", "python3")) {
        $c = Get-Command $n -ErrorAction SilentlyContinue
        if ($c) { return @{ Exe = $c.Source; Prefix = @() } }
    }

    throw "找不到 Python。请安装 Python 3 并加入 PATH，或用 -PythonExe 指定解释器路径。"
}

if (-not (Test-Path $SyncPy)) { throw "找不到同步脚本: $SyncPy" }
if ($EveryMinutes -lt 1) { throw "-EveryMinutes 必须 >= 1" }

$py     = Resolve-Python -Explicit $PythonExe
$exe    = $py.Exe
$prefix = $py.Prefix
$argList = @($prefix) + @("`"$SyncPy`"", "--quiet")

# ---------------------------------------------------------------- 建任务
$action = New-ScheduledTaskAction -Execute $exe -Argument ($argList -join " ") -WorkingDirectory $ScriptDir

$interval = New-TimeSpan -Minutes $EveryMinutes
$repeat   = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval $interval -RepetitionDuration ([TimeSpan]::FromDays(3650))

$triggers = @()
if (-not $NoLogonTrigger) {
    # 必须带 -User，否则创建"任意用户"登录触发器需要管理员权限（Access denied）
    $triggers += (New-ScheduledTaskTrigger -AtLogOn -User "$env:USERNAME")
}
$triggers += $repeat

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20) `
    -Hidden

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited

Remove-Task $TaskName | Out-Null

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $triggers `
    -Settings $settings `
    -Principal $principal `
    -Force | Out-Null

$logonNote = if ($NoLogonTrigger) { "无" } else { "登录时" }
Write-Host ""
Write-Host "已注册计划任务: $TaskName"
Write-Host "  解释器 : $exe $($prefix -join ' ')"
Write-Host "  命令   : $exe $($argList -join ' ')"
Write-Host "  触发   : $logonNote + 每 $EveryMinutes 分钟（最长 10 年，到期重跑本脚本即可）"
Write-Host ""
Write-Host "立即执行 : Start-ScheduledTask -TaskName $TaskName"
Write-Host "查看状态 : Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo"
Write-Host "卸载     : powershell -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Uninstall"
