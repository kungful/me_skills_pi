@echo off
chcp 65001 >nul
setlocal
rem ============================================================
rem  需求雷达 Android 版 一键构建（+ 可选安装到手机）
rem  用法：
rem    build.bat            只构建，产出 app-debug.apk
rem    build.bat install    构建完直接装到已连接的手机
rem ============================================================

set "PROJ=%~dp0"
set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr"
set "GRADLE=C:\Users\hua\tools\gradle-8.9\bin\gradle.bat"
set "ADB=C:\Users\hua\Documents\platform-tools\adb.exe"
set "APK=%PROJ%app\build\outputs\apk\debug\app-debug.apk"

if not exist "%GRADLE%" set "GRADLE=gradle"

echo.
echo [1/3] 用 JDK 21 编译...
cd /d "%PROJ%"
call "%GRADLE%" :app:assembleDebug --console=plain
if errorlevel 1 (
  echo.
  echo ❌ 构建失败。常见原因：
  echo    - local.properties 里的 sdk.dir 不对（必须是正斜杠或双反斜杠）
  echo    - 工程路径含中文 / 空格（Gradle 会报非 ASCII 路径）
  goto :eof
)

echo.
echo [2/3] 产出：%APK%
for %%F in ("%APK%") do echo      大小 %%~zF 字节，时间 %%~tF

if /i not "%~1"=="install" (
  echo.
  echo [3/3] 跳过安装。要装到手机请用：build.bat install
  goto :eof
)

echo.
echo [3/3] 安装到手机...
"%ADB%" devices
echo.
echo   注意：vivo/OPPO 等机型弹「安装确认」框时必须点「允许 / 继续安装」，
echo         否则会报 INSTALL_FAILED_ABORTED: User rejected permissions。
echo.
"%ADB%" install -r "%APK%"
if errorlevel 1 (
  echo.
  echo ❌ 安装失败。若提示被拒：
  echo    - 先解锁手机屏幕，保持亮屏，再重跑本命令，在手机上点「允许」
  echo    - 或在手机上：设置 → 系统管理 → 开发者选项 → 打开「USB 安装」
) else (
  echo.
  echo ✅ 装好了。在手机上打开「需求雷达」App：
  echo    点「① 开启无障碍读屏权限」→ 已下载的服务 → 需求雷达 → 打开
  echo    然后正常刷小红书 / 闲鱼 / 转转，回 App 点「重新分析」看机会榜
)
endlocal
