@echo off
rem Double-click to be asked which maps to port, or drop BSPs or a folder on this file. Close Hammer and CS2 first.
rem Anything missing, wrong or unknown goes in C:\source1\cs2port\logs\autoport\<date>.log. Maps with problems wait for Claude while the rest build.
start "autoport monitor" python "%~dp0monitor.py"
python "%~dp0autoport.py" %*
pause
