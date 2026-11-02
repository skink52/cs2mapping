@echo off
rem BSPSource's command line on the PC (bspsrc-windows\bspsrc.bat opens the GUI). prep.py calls this through BSPSRC=.
"C:\source1\bspsrc-windows\bin\java.exe" -m info.ata4.bspsrc.app/info.ata4.bspsrc.app.src.cli.BspSourceCli %* > "%TEMP%\autoport_bspsrc.log" 2>&1
