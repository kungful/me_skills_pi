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
setlocal
REM pi 链路启动器 —— 日常手动启动 watchdog + 派发台。
REM watchdog + 派发台 :8787（经 link-supervisor.mjs 监管）。
REM pi-web 保持独立：它死了要靠 watchdog 报警，绝不能合进来。
REM 本文件只负责前台显示窗口；不创建开机自启。
title pi 链路 (watchdog + 派发台 :8787)
set "NODE_EXE=C:\Program Files\nodejs\node.exe"
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
echo [pi-link] 日志：C:\Users\hua\.pi\android-link\link.out.log
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
