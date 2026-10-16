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
setlocal
cd /d "%~dp0"

REM pi-web 双实例脑裂 体检/修复器。真正逻辑在 fix-split-brain.ps1。
REM 编码：UTF-8 无 BOM + chcp 65001（和桌面 Pi Web.bat 同一套写法），
REM 中文照常写——write 工具落盘的已是无 BOM UTF-8。

echo 正在体检 pi-web 双实例 / 绑定...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0fix-split-brain.ps1" %*
set RC=%ERRORLEVEL%
echo.
echo ------------------------------------------------------------
if exist "%~dp0fix-split-brain-report.txt" (
  echo 报告: %~dp0fix-split-brain-report.txt
)
echo 退出码: %RC%
echo.
echo 按任意键关闭本窗口。
pause >nul
exit /b %RC%
