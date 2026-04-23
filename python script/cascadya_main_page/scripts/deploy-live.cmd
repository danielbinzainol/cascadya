@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0deploy-live.ps1" %*
