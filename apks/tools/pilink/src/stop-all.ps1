<#
    停掉这条链路的全部进程（监管进程 + 看门狗 + 派发台 + 隧道子进程）。

    为什么要它：派发台和看门狗都有【单实例锁】。旧的还在跑时，新的会直接退出
    并打印「已有实例在跑(pid=…)」—— 很容易被误读成启动失败。
    所以：想重新双击 run-link.bat 之前，先双击 stop-all.bat。

    为什么正文放在 .ps1 里：这个目录的约定是 .ps1 用 UTF-8 带 BOM、.bat 用纯 ASCII。
    .bat 里放中文在部分 Windows 上会因代码页把整行解析坏（表现是莫名其妙的
    "xxx.bat 不是内部或外部命令"），所以 .bat 只留一行转发。
#>
$ErrorActionPreference = 'SilentlyContinue'

# 隧道子进程（cloudflared 由派发台拉起，改端口或改域名时先杀掉旧的）
Get-Process cloudflared -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "  停掉 cloudflared pid $($_.Id)"
    Stop-Process -Id $_.Id -Force
}

# 只杀跑着本项目三个脚本的 node 进程。
# 注意：只按脚本名匹配，**不**按目录名匹配 —— 监管进程可能是用相对路径
# （node link-supervisor.mjs）启动的，命令行里根本没有目录名，按目录匹配会漏掉它，
# 结果就是「杀掉了子进程，监管进程又把子进程拉起来」，看起来像没停干净。
#
# 而且必须【多轮】：监管进程被 kill 的瞬间可能正好在重启子进程，
# 于是会出现「这一轮杀完了，下一轮又冒出来一个新的」。实测叠了 5 个监管进程时
# 单轮杀不干净 —— 端口一直被占着，看起来就像 stop-all 失灵了。
$scriptPattern = 'link-supervisor\.mjs|console-server\.mjs|watchdog\.mjs'

function Get-LinkProcesses {
    Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq 'node.exe' -and
        $_.CommandLine -match $scriptPattern -and
        $_.CommandLine -notmatch 'node_modules'
    }
}

$passes = 0
do {
    $targets = @(Get-LinkProcesses)
    if ($targets.Count -eq 0) { break }
    $passes++
    foreach ($p in $targets) {
        $what = if ($p.CommandLine -match 'link-supervisor') { 'supervisor' }
                elseif ($p.CommandLine -match 'console-server') { 'console' }
                else { 'watchdog' }
        Write-Host "  [第 $passes 轮] 停掉 $what pid $($p.ProcessId)"
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 700
} while ($passes -lt 8)

$still = @(Get-LinkProcesses)
if ($still.Count) {
    Write-Host "  还有 $($still.Count) 个没停掉，用管理员 PowerShell 再试一次" -ForegroundColor Yellow
    $still | ForEach-Object { Write-Host "    pid $($_.ProcessId)" }
} else {
    Write-Host "  已全部停掉（共 $passes 轮）" -ForegroundColor Green
}
Write-Host ''
Write-Host '现在可以双击 run-link.bat 了（它会同时拉起看门狗 + 派发台 + 异地发现）。'
