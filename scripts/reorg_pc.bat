@echo off
rem Previews the folder tidy (reorg_pc.ps1), then asks before moving anything.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0reorg_pc.ps1"
pause
