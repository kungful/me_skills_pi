@echo off
cd /d "%~dp0"
set "PY="
if exist "%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe" set "PY=%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe"
if exist "C:\Users\hua\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" set "PY=C:\Users\hua\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
if not defined PY set "PY=python"
"%PY%" "%~dp0run_ui.py" %*
pause
