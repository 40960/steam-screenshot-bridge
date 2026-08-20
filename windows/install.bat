@echo off
REM Double-click me. Runs install.ps1 without touching the machine's
REM execution policy -- the bypass applies to this one process only.
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
echo.
pause
