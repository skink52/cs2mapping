@echo off
setlocal EnableDelayedExpansion
rem ==== Import the models / materials listed in maps\<addon>_fix_refs.txt (missing gibs and model materials, from tools/gibfix.py) ====
rem Usage: run_fixrefs.bat <addon> [<addon> ...]   (Hammer and CS2 closed). Then run_build.bat. Logs: C:\source1\cs2port\logs\<addon>_fixrefs.log

set "CS2=C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive"
set "PORT=C:\source1\cs2port"
set "SCRIPTS=%CS2%\game\csgo\import_scripts"
set "PATH=%CS2%\game\bin\win64;%PATH%"
if not exist "%PORT%\logs" mkdir "%PORT%\logs"
if "%~1"=="" ( echo usage: run_fixrefs.bat ^<addon^> [^<addon^> ...] & pause & exit /b 1 )

if exist "%CS2%\game\bin\win64\vpk.signatures" (
  if exist "%CS2%\game\bin\win64\vpk.signatures.aaa" del "%CS2%\game\bin\win64\vpk.signatures.aaa"
  ren "%CS2%\game\bin\win64\vpk.signatures" vpk.signatures.aaa
)
copy /y "%PORT%\modelsfromrefs.py" "%SCRIPTS%\modelsfromrefs.py" >nul
cd /d "%SCRIPTS%"

for %%a in (%*) do (
  set "REFS=%CS2%\content\csgo_addons\%%a\maps\%%a_fix_refs.txt"
  if exist "!REFS!" (
    echo ==== %%a : importing %%a_fix_refs.txt ====
    py modelsfromrefs.py %%a "!REFS!" > "%PORT%\logs\%%a_fixrefs.log" 2>&1
    echo      exit code !ERRORLEVEL!   ^(log: logs\%%a_fixrefs.log^)
  ) else (
    echo ==== %%a : no maps\%%a_fix_refs.txt, skipped ====
  )
)
echo.
echo Done. Now run run_build.bat for these maps.
pause
