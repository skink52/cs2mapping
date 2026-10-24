@echo off
rem Unattended stage B + D: runs run_import.bat, then waits for Claude to finish stage C
rem (Claude writes C:\source1\cs2port\build_go.txt when the vmaps are ready), then runs run_build.bat.
rem Close Hammer and CS2 before launching. Delete build_go.txt to re-arm. Ctrl+C to stop waiting.
set "PORT=C:\source1\cs2port"
if exist "%PORT%\build_go.txt" del "%PORT%\build_go.txt"
echo [%time%] stage B: run_import.bat >> "%PORT%\logs\unattended.log"
call "%PORT%\run_import.bat" < nul
echo [%time%] stage B finished, waiting for build_go.txt >> "%PORT%\logs\unattended.log"
echo.
echo ==== Import done. Waiting for Claude to finish stage C (build_go.txt) ... ====
:wait
if not exist "%PORT%\build_go.txt" (
  timeout /t 60 /nobreak >nul
  goto wait
)
echo [%time%] build_go.txt found, stage D: run_build.bat >> "%PORT%\logs\unattended.log"
call "%PORT%\run_build.bat" < nul
echo [%time%] stage D finished >> "%PORT%\logs\unattended.log"
del "%PORT%\build_go.txt"
echo ==== All done ====
pause
