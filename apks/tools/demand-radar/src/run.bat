@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "VENV_PY=C:\Users\hua\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
set "PY=python"
if exist "%VENV_PY%" set "PY=%VENV_PY%"

"%PY%" -c "import jieba, yaml, requests, flask" 2>nul
if errorlevel 1 (
  echo [i] 检测到依赖缺失，正在安装...
  "%PY%" -m pip install -r requirements.txt
)

if not "%~1"=="" goto direct

:menu
echo ============================================
echo   需求雷达 demand-radar
echo ============================================
echo   1. 一键全流程（采集+分析+看板）
echo   2. 只看机会榜（终端）
echo   3. 监听手机屏幕（可先插手机）
echo   4. 抓手机当前一屏（测试）
echo   5. 检查手机连接
echo   6. 启动 Web 看板
echo   7. 查看数据状态
echo   8. 无线 ADB（插一次线，以后不用插）
echo   9. 手机掉线了，扫网段找回来
echo  10. 构建手机 App（APK）
echo  11. 构建并安装手机 App
echo   0. 退出
echo ============================================
set "c="
set /p c=请选择: 
if "%c%"=="1" "%PY%" -m demand_radar run --open
if "%c%"=="2" "%PY%" -m demand_radar top -n 25
if "%c%"=="3" "%PY%" -m demand_radar watch
if "%c%"=="4" "%PY%" -m demand_radar capture
if "%c%"=="5" "%PY%" -m demand_radar phone
if "%c%"=="6" "%PY%" -m demand_radar serve --open
if "%c%"=="7" "%PY%" -m demand_radar status
if "%c%"=="8" "%PY%" -m demand_radar wireless
if "%c%"=="9" "%PY%" -m demand_radar wireless --scan
if "%c%"=="10" call "%~dp0android\build.bat"
if "%c%"=="11" call "%~dp0android\build.bat" install
if "%c%"=="0" goto end
echo.
pause
goto menu

:direct
"%PY%" -m demand_radar %*

:end
endlocal
