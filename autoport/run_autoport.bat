@echo off
rem Port every BSP dropped on this file, or passed as arguments, with nobody watching. Close Hammer and CS2 first.
rem The result is logged under C:\source1\cs2port\work\autoport_runs, including cleanup_list.md for whatever is left to do.
start "autoport monitor" python "%~dp0monitor.py"
python "%~dp0autoport.py" %*
