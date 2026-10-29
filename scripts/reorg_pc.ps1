# Tidies skink52's CS2 folders on the PC (30 Oct 2026 layout, see docs/porting/setup.md "PC folders").
# Dry run by default: lists every move. Run with -Apply to do it.
#   powershell -ExecutionPolicy Bypass -File reorg_pc.ps1           (preview)
#   powershell -ExecutionPolicy Bypass -File reorg_pc.ps1 -Apply    (move)
# Only moves; never overwrites (an existing destination is skipped and reported) and deletes nothing except empty folders and a
# byte-identical duplicate shortcut. Everything the port runners use stays where it is: C:\source1\cs2port, C:\source1\maps,
# C:\source1\bspsrc-windows, C:\source1\gameinfo.txt, pak01_dir.vpk, sound\, expressions\, C:\cscontent, C:\VTF, the CS2 install.
# Each move is logged to C:\source2\reorg_log.csv and C:\source2\reorg_undo.ps1 puts everything back.
param([switch]$Apply)

$ErrorActionPreference = 'Stop'
$S1 = 'C:\source1'; $S2 = 'C:\source2'
$D  = Join-Path $env:USERPROFILE 'OneDrive\Desktop\CS2'
$A1 = "$S1\archive"; $A2 = "$S2\archive"; $W = "$S2\workshop"; $P = "$S2\projects"

$busy = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^(hammer|cs2|resourcecompiler|Source2Viewer.*|RadGen|MapPacker|Crowbar)$' }
if ($busy) { Write-Host ('Close these first: ' + (($busy | Select-Object -ExpandProperty ProcessName -Unique) -join ', ')) -ForegroundColor Red; exit 1 }

$moves = @(
  # ---- C:\source1: porting. Input BSPs together, tools together, the rest archived
  @("$S1\STORE\jb_sides_v1a.bsp",                          "$S1\bspsrc-windows\bsp's\jb_sides_v1a.bsp"),
  @("$S1\bspsrc-windows\ba_jail_ds_arctic_summer_v1.bsp",  "$S1\bspsrc-windows\bsp's\ba_jail_ds_arctic_summer_v1.bsp"),
  @("$S1\mappacker",                                       "$S1\tools\mappacker"),
  @("$S1\source2converter",                                "$S1\tools\source2converter"),
  @("$S1\disk_report",                                     "$S1\tools\disk_report"),
  @("$S1\crowbarassets\Crowbar.exe",                       "$S1\tools\crowbar\Crowbar.exe"),
  @("$S1\crowbarassets\decompiled",                        "$A1\crowbar\decompiled"),
  @("$S1\crowbarassets\working",                           "$A1\crowbar\working"),
  @("$S1\Blender Source1 Assets",                          "$A1\blender"),
  @("$S1\modelbackups",                                    "$A1\modelbackups"),
  @("$S1\bgoomba.vmdl",                                    "$A1\loose\bgoomba.vmdl"),
  @("$S1\banmdls.res",                                     "$A1\loose\banmdls.res"),
  @("$S1\console.log",                                     "$A1\loose\console.log"),
  @("$S1\makealpha.py",                                    "$A1\loose\makealpha.py"),
  @("$S1\mdltovmdl.py",                                    "$A1\loose\mdltovmdl.py"),
  @("$S1\newcheck.py",                                     "$A1\loose\newcheck.py"),
  @("$S1\slime.png",                                       "$W\slime-servers\slime.png"),
  @("$S1\slime_mask.png",                                  "$W\slime-servers\slime_mask.png"),
  @("$S1\slime.vmat",                                      "$W\slime-servers\slime.vmat"),

  # ---- C:\source2: creation. Programs, projects, workshop material, archive
  @("$S2\RadGen.exe",                                      "$S2\apps\RadGen.exe"),
  @("$S2\Source2Viewer (1).exe",                           "$S2\apps\Source2Viewer.exe"),
  @("$S2\Hammer5Tools.lnk",                                "$S2\apps\Hammer5Tools.lnk"),
  @("$S2\trenchwarfare assets",                            "$P\trenchwarfare"),
  @("$S2\wooden__spike__barricad_3d_model_free.glb",       "$P\trenchwarfare\wooden__spike__barricad_3d_model_free.glb"),
  @("$S2\dogfight",                                        "$P\dogfight"),
  @("$S2\freedoom-0.13.0",                                 "$P\hellmatch\freedoom-0.13.0"),
  @("$S2\ah-64e_apache_guardian",                          "$P\apache"),
  @("$S2\kz_infinite_water_template-bdc1b9a9b0672da3",     "$P\reference\kz_infinite_water_template"),
  @("$S2\arcade_break_loop.wav",                           "$P\space-racer\arcade_break_loop.wav"),
  @("$S2\demo videos\hellmatch",                           "$W\hellmatch\video"),
  @("$S2\demo videos\space racer",                         "$W\space-racer\video"),
  @("$S2\ttt description.txt",                             "$W\ttt\ttt description.txt"),
  @("$S2\neon racer assets",                               "$A2\neon-racer-tripo"),
  @("$S2\dogfight.rar",                                    "$A2\dogfight.rar"),
  @("$S2\jb_clouds.vpk",                                   "$A2\vpk\jb_clouds.vpk"),
  @("$S2\files",                                           "$A2\textures-misc\files"),
  @("$S2\output",                                          "$A2\textures-misc\output"),

  # ---- Desktop\CS2 (OneDrive): workshop images and descriptions, notes, archive
  @("$D\freeDM.png",                                       "$W\hellmatch\freeDM.png"),
  @("$D\Hellmatch - Workshop gallery.jpg",                 "$W\hellmatch\Hellmatch - Workshop gallery.jpg"),
  @("$D\HELLMATCH STEAM DESCRIPTION.txt",                  "$W\hellmatch\HELLMATCH STEAM DESCRIPTION.txt"),
  @("$D\hellmatch_reddit_2mb.gif",                         "$W\hellmatch\hellmatch_reddit_2mb.gif"),
  @("$D\space racer.png",                                  "$W\space-racer\space racer.png"),
  @("$D\SPACE RACER STEAM DESCRIPTION.txt",                "$W\space-racer\SPACE RACER STEAM DESCRIPTION.txt"),
  @("$D\ballistic.png",                                    "$W\ports\ballistic.png"),
  @("$D\bombardment.png",                                  "$W\ports\bombardment.png"),
  @("$D\circle course.png",                                "$W\ports\circle course.png"),
  @("$D\draw_course.png",                                  "$W\ports\draw_course.png"),
  @("$D\egypt.png",                                        "$W\ports\egypt.png"),
  @("$D\enjoy.png",                                        "$W\ports\enjoy.png"),
  @("$D\faohu.png",                                        "$W\ports\faohu.png"),
  @("$D\fred all.png",                                     "$W\ports\fred all.png"),
  @("$D\galaxy.png",                                       "$W\ports\galaxy.png"),
  @("$D\goldeneye.png",                                    "$W\ports\goldeneye.png"),
  @("$D\lego course.png",                                  "$W\ports\lego course.png"),
  @("$D\mario party.png",                                  "$W\ports\mario party.png"),
  @("$D\metalcourse.png",                                  "$W\ports\metalcourse.png"),
  @("$D\minecraft.png",                                    "$W\ports\minecraft.png"),
  @("$D\smee_tower.png",                                   "$W\ports\smee_tower.png"),
  @("$D\submarine.png",                                    "$W\ports\submarine.png"),
  @("$D\heli1.png",                                        "$W\ports\heli1.png"),
  @("$D\heli2.png",                                        "$W\ports\heli2.png"),
  @("$D\50arenas.png",                                     "$W\unsorted\50arenas.png"),
  @("$D\banner.png",                                       "$W\unsorted\banner.png"),
  @("$D\preview.png",                                      "$W\unsorted\preview.png"),
  @("$D\workshop_wide.jpg",                                "$W\unsorted\workshop_wide.jpg"),
  @("$D\mg_trenchwarfare.txt",                             "$P\trenchwarfare\design notes.txt"),
  @("$D\server.txt",                                       "$S2\notes\server.txt"),
  @("$D\Map changes.txt",                                  "$S2\notes\Map changes.txt"),
  @("$D\regedit change.txt",                               "$S2\notes\regedit change.txt"),
  @("$D\disco_addons.txt",                                 "$S2\notes\disco_addons.txt"),
  @("$D\dodgeball.js",                                     "$S2\notes\dodgeball.js"),
  @("$D\freedm_cs2_status.md",                             "$S2\notes\freedm_cs2_status.md"),
  @("$D\Hammer5Tools.lnk",                                 "$S2\apps\Hammer5Tools.lnk"),
  @("$D\importscripts",                                    "$A1\importscripts"),
  @("$D\mariopartycleanup",                                "$A1\screenshots\mariopartycleanup"),
  @("$D\sss",                                              "$A1\screenshots\sss"),
  @("$D\ba_jail_dr_downview.vpk",                          "$A1\vpk\ba_jail_dr_downview.vpk")
)

$log = "$S2\reorg_log.csv"; $undo = "$S2\reorg_undo.ps1"
$done = 0; $skip = 0
if ($Apply -and -not (Test-Path -LiteralPath $undo)) { "# undoes reorg_pc.ps1 (newest move first)`r`n`$ErrorActionPreference = 'Continue'" | Set-Content -LiteralPath $undo -Encoding UTF8 }
$undoLines = New-Object System.Collections.Generic.List[string]

foreach ($m in $moves) {
  $src, $dst = $m
  if (-not (Test-Path -LiteralPath $src)) { continue }
  if (Test-Path -LiteralPath $dst) {
    if ((Split-Path $src -Leaf) -eq 'Hammer5Tools.lnk' -and (Get-FileHash -LiteralPath $src).Hash -eq (Get-FileHash -LiteralPath $dst).Hash) {
      Write-Host "dup     $src (same as $dst)" -ForegroundColor DarkGray
      if ($Apply) { Remove-Item -LiteralPath $src }
      continue
    }
    Write-Host "SKIP    $src -> $dst (destination exists)" -ForegroundColor Yellow; $skip++; continue
  }
  Write-Host "move    $src -> $dst"
  if ($Apply) {
    New-Item -ItemType Directory -Force -Path (Split-Path $dst -Parent) | Out-Null
    Move-Item -LiteralPath $src -Destination $dst
    '"{0}","{1}","{2}"' -f (Get-Date -Format s), $src, $dst | Add-Content -LiteralPath $log -Encoding UTF8
    $undoLines.Insert(0, "New-Item -ItemType Directory -Force -Path '$((Split-Path $src -Parent) -replace "'", "''")' | Out-Null; Move-Item -LiteralPath '$($dst -replace "'", "''")' -Destination '$($src -replace "'", "''")'")
  }
  $done++
}

if ($Apply) {
  # the WW1 weapon builder's configs name their own folder
  $old = 'C:/source2/trenchwarfare assets'; $new = 'C:/source2/projects/trenchwarfare'; $enc = New-Object Text.UTF8Encoding $false
  $fixed = @(Get-ChildItem -LiteralPath "$P\trenchwarfare\tools" -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -in '.json', '.py' } |
    Where-Object { [IO.File]::ReadAllText($_.FullName).Contains($old) })
  foreach ($f in $fixed) {
    [IO.File]::WriteAllText($f.FullName, [IO.File]::ReadAllText($f.FullName).Replace($old, $new), $enc); Write-Host "paths   $($f.FullName)"
  }
  if ($fixed) {
    $undoLines.Insert(0, "foreach (`$f in @('" + (($fixed | ForEach-Object { $_.FullName -replace "'", "''" }) -join "','") +
      "')) { [IO.File]::WriteAllText(`$f, [IO.File]::ReadAllText(`$f).Replace('$new', '$old'), (New-Object Text.UTF8Encoding `$false)) }")
  }
  $undoLines | Add-Content -LiteralPath $undo -Encoding UTF8
  foreach ($e in @("$S1\STORE\maps", "$S1\STORE", "$S1\crowbarassets", "$S1\Blender Assets", "$S2\demo videos", $D)) {
    if ((Test-Path -LiteralPath $e) -and -not (Get-ChildItem -LiteralPath $e -Force)) { Remove-Item -LiteralPath $e; Write-Host "removed empty $e" -ForegroundColor DarkGray }
  }
}
Write-Host ''
if ($Apply) { Write-Host "$done moved, $skip skipped. Log: $log  Undo: $undo" -ForegroundColor Green }
else {
  Write-Host "$done to move, $skip would be skipped. Nothing changed yet." -ForegroundColor Cyan
  if ($done -and (Read-Host 'Do these moves now? (y/n)') -eq 'y') { & $PSCommandPath -Apply; exit }
}
