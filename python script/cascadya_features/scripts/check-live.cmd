@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0check-live.ps1" %*
endlocal
