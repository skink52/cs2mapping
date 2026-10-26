@echo off
setlocal EnableDelayedExpansion
rem ==== cs2port stage B: Valve import + post_import_cleanup for every map in queue.txt ====
rem Claude prepares everything before this (decompile, rename, header fix, addon folders).
rem Materials/models for each map come as assets\<addon>.zip (+ .2/.3/.4.zip if large) and are unpacked into csgo\ here (existing files are never overwritten).
rem Just double-click this file. Logs go to C:\source1\cs2port\logs\

set "CS2=C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive"
set "PORT=C:\source1\cs2port"
set "SCRIPTS=%CS2%\game\csgo\import_scripts"
if not exist "%PORT%\logs" mkdir "%PORT%\logs"

rem vpk.signatures blocks the importer - rename it if Steam put it back
if exist "%CS2%\game\bin\win64\vpk.signatures" (
  if exist "%CS2%\game\bin\win64\vpk.signatures.aaa" del "%CS2%\game\bin\win64\vpk.signatures.aaa"
  ren "%CS2%\game\bin\win64\vpk.signatures" vpk.signatures.aaa
  echo Renamed vpk.signatures to vpk.signatures.aaa
)

copy /y "%PORT%\import_map_auto.py" "%SCRIPTS%\import_map_auto.py" >nul
cd /d "%SCRIPTS%"

for /f "usebackq tokens=1,2" %%a in ("%PORT%\queue.txt") do (
  set "ADDON=%%a"
  set "MAP=%%b"
  if "!MAP!"=="" set "MAP=%%a"
  echo.
  for %%z in ("%PORT%\assets\!ADDON!.zip" "%PORT%\assets\!ADDON!.2.zip" "%PORT%\assets\!ADDON!.3.zip" "%PORT%\assets\!ADDON!.4.zip") do if exist "%%~z" (
    echo ==== !ADDON! : unpacking %%~nxz into csgo ^(existing files kept^) ====
    "%SystemRoot%\System32\tar.exe" -xkf "%%~z" -C "%CS2%\csgo" >> "%PORT%\logs\!ADDON!_assets_unpack.log" 2>&1
  )
  echo ==== !ADDON! : importing maps\!MAP!.vmf ====
  python import_map_auto.py "%CS2%\csgo" "C:\source1" "%CS2%\game\csgo" !ADDON! !MAP! > "%PORT%\logs\!ADDON!_import.log" 2>&1
  set "IMPERR=!ERRORLEVEL!"
  echo      import exit code !IMPERR!   ^(log: logs\!ADDON!_import.log^)
  echo ==== !ADDON! : post_import_cleanup ====
  py post_import_cleanup.py !ADDON! > "%PORT%\logs\!ADDON!_cleanup.log" 2>&1
  echo      cleanup exit code !ERRORLEVEL!   ^(log: logs\!ADDON!_cleanup.log^)
  rem Valve's importer always exits 1 at its prefab_refs step, so a failed import is spotted by "Aborting" in its log
  set "IMPFAIL="
  findstr /c:"Aborting" "%PORT%\logs\!ADDON!_import.log" >nul 2>&1 && set "IMPFAIL=1"
  if defined IMPFAIL (
    echo      FAILED - the importer aborted, check the import log ^(an older vmap may still be there^)
    echo !ADDON! FAILED>> "%PORT%\logs\stage_b_done.txt"
  ) else if exist "%CS2%\content\csgo_addons\!ADDON!\maps\!MAP!.vmap" (
    echo      OK - !MAP!.vmap exists
    echo !ADDON! OK>> "%PORT%\logs\stage_b_done.txt"
  ) else (
    echo      FAILED - no vmap was written, check the import log
    echo !ADDON! FAILED>> "%PORT%\logs\stage_b_done.txt"
  )
)
echo.
echo All done. Tell Claude stage B finished - it reads the logs from C:\source1\cs2port\logs
pause
