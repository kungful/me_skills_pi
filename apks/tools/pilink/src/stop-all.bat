@echo off
REM Stop every process of this link (supervisor + watchdog + console + cloudflared).
REM Run this before double-clicking run-link.bat again: the console/watchdog have
REM single-instance locks, so a leftover old process makes the new one exit with
REM "already running (pid=...)" which is easy to misread as a failed start.
REM NOTE: this file name is deliberately ASCII. The project path contains Chinese
REM characters and cmd resolves files in the ANSI code page, so a non-ASCII file
REM name (or %%~dp0 here) gets mangled and the script never runs.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-all.ps1"
pause
