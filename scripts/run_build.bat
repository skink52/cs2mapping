@echo off
rem ==== cs2port stage D: compile every map in build_queue.txt, one at a time, no Hammer needed ====
rem Close CS2/Hammer first. Logs go to C:\source1\cs2port\logs\
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\source1\cs2port\build_maps.ps1" %*
pause
