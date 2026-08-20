@echo off
REM Double-click me. Runs uninstall.ps1 without touching the machine's
REM execution policy -- the bypass applies to this one process only.
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1"
echo.
pause
