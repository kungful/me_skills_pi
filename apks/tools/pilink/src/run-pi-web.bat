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
@echo off
setlocal enabledelayedexpansion
REM pi-web 启动器（局域网模式）—— 日常就用这一个。
REM 本文件由 setup.ps1 生成：地址/密码在生成时就写好了，运行时不再读 local.json。
REM 必须带 -H 0.0.0.0：不带只绑 127.0.0.1，手机连不上。
REM 先杀旧实例：30141 上两个 listener（127.0.0.1 + 0.0.0.0）= 两套内存状态（脑裂），
REM 看门狗会把正在跑的会话误报成异常中断。
set "NODE_OPTIONS=%NODE_OPTIONS% --network-family-autoselection-attempt-timeout=2000 --require=%~dp0pi-web-env.cjs"
REM pi-subagents uses this to identify the Pi package that owns pi-web.
set "PI_SUBAGENTS_PI_CODING_AGENT_PACKAGE_ROOT=C:\Users\hua\AppData\Roaming\npm\node_modules\@agegr\pi-web\node_modules\@earendil-works\pi-coding-agent"
title pi-web 局域网版 (0.0.0.0:30141)
set "SILENT="
if /i "%~1"=="--silent" set "SILENT=1"
set "LANIP=192.168.31.77"
set "PI_WEB_PASSWORD=5d3263b10d10ba546d9e2e28499a56d4"
set "AUTHMODE=无密码（局域网可信模式）"
if defined PI_WEB_PASSWORD set "AUTHMODE=密码保护（用户名 pi）"
echo.
echo [pi-web] 检查 30141 端口上是否已有实例在跑...
set "PORT_PID="
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":30141" ^| findstr "LISTENING"') do set "PORT_PID=%%a"
if not defined PORT_PID goto start
echo [pi-web] 端口被占用，先停掉旧实例（防止双实例脑裂）...
taskkill /PID !PORT_PID! /T /F >nul 2>&1
timeout /t 2 /nobreak >nul
:start
echo.
echo [pi-web] 启动中...
echo.
echo   [OK] 这台电脑请打开   http://localhost:30141
echo   [OK] 手机/别的设备请开 http://!LANIP!:30141
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
call pi-web -H 0.0.0.0 -p 30141
echo.
echo [pi-web] 服务已退出。
if not defined SILENT pause
