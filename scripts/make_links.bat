@echo off
rem Makes the C:\source1\links\ junctions Claude Code uses (see docs/porting/setup.md). Safe to re-run.
setlocal
set CS2=C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive
set L=C:\source1\links
if not exist "%L%" mkdir "%L%"
call :link VTF "C:\VTF"
call :link source2 "C:\source2"
call :link cs2_root "%CS2%"
call :link content_addons "%CS2%\content\csgo_addons"
call :link game_addons "%CS2%\game\csgo_addons"
call :link csgo "%CS2%\csgo"
call :link bin_win64 "%CS2%\game\bin\win64"
call :link import_scripts "%CS2%\game\csgo\import_scripts"
findstr /x /c:"links/" "C:\source1\.git\info\exclude" >nul 2>&1 || (if exist "C:\source1\.git\info" echo links/>>"C:\source1\.git\info\exclude")
echo done
pause
goto :eof
:link
if exist "%L%\%~1" (echo exists: links\%~1 & goto :eof)
if not exist "%~2" (echo missing target, skipped: %~2 & goto :eof)
mklink /J "%L%\%~1" "%~2"
goto :eof
