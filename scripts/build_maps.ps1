# cs2port stage D: compile maps from the command line without Hammer, one at a time.
# Each map: compile the addon's materials/radar/sounds/scripts (Hammer normally does this when it loads a map),
# then compile into Hammer's temp outroot -> wait for the compiler to exit -> move the built .vpk
# into game\csgo_addons\<addon>\maps\ and check it landed -> only then start the next map.
#
#   run_build.bat                     builds every line of build_queue.txt  ("addon" or "addon mapname")
#   build_maps.ps1 mg_fred_all ...    builds just the addons given
#   a line "assets mg_x" compiles mg_x's materials/radar/HUD xml+css/sounds/scripts only, without rebuilding the map
#   a line "entities mg_x [map]" recompiles only the entities (Hammer's entity-only build: no world, vis or nav) - for entity edits
#   a line "lighting mg_x [map]" recompiles the world and lighting but not vis or nav - for texture / material changes with no brush moved
#   a line "final mg_x [map]" is a full build (world, vis, nav, audio) with release lighting: 2048 lightmaps, VRAD quality 2
#   entities / lighting need an earlier full build: they start from the map's current .vpk in game\, and fall back to a full build when there is none.
# Logs: C:\source1\cs2port\logs\<addon>_build.log and logs\stage_d_done.txt
# Successful builds are marked [in progress, built] in existing_ports.txt.

param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Maps)

$ErrorActionPreference = 'Continue'
$CS2     = 'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive'
$RC      = Join-Path $CS2 'game\bin\win64\resourcecompiler.exe'
$Port    = 'C:\source1\cs2port'
$OutRoot = Join-Path $env:LOCALAPPDATA 'Temp\valve\hammermapbuild\game'
$Logs    = Join-Path $Port 'logs'
$Ports   = Join-Path $Port 'existing_ports.txt'
New-Item -ItemType Directory -Force -Path $Logs | Out-Null

function Mark-Built([string]$name) {
    if (-not (Test-Path $Ports)) { return }
    $text  = [IO.File]::ReadAllText($Ports)
    $lines = [Collections.Generic.List[string]]($text -split "`r?`n")
    $pat   = '^\s*' + [regex]::Escape($name) + '(?=\s|\[|:|$)'
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match $pat) {
            $found = $true
            if ($lines[$i] -match '\[(ported|\*original\*|ext\. port)\]') { break }
            if ($lines[$i] -match '\[in progress[^\]]*\]') { $lines[$i] = $lines[$i] -replace '\[in progress[^\]]*\]', '[in progress, built]' }
            else { $lines[$i] = $lines[$i].TrimEnd() + ' [in progress, built]' }
            if ($lines[$i] -notmatch '\[skink\]|\[briar\]') { $lines[$i] += ' [skink]' }
            break
        }
    }
    while ($lines.Count -gt 0 -and $lines[$lines.Count - 1].Trim() -eq '') { $lines.RemoveAt($lines.Count - 1) }
    if (-not $found) { $lines.Add("$name [in progress, built] [skink]") }
    [IO.File]::WriteAllText($Ports, ($lines -join "`r`n"), (New-Object Text.UTF8Encoding $false))
}

if (-not (Test-Path $RC)) { Write-Host "resourcecompiler.exe not found at $RC" -ForegroundColor Red; exit 1 }

# queue: "addon", "addon mapname", or "assets addon" (compile the addon's assets only, no map build)
$queue = @()
# on the command line a mode word joins the addon after it: "final ba_jail_keimusho" is one entry, as on a queue line
$argLines = @(); $pend = ''
foreach ($m in @($Maps)) {
    if (-not $m) { continue }
    if ($m.ToLower() -in @('assets', 'entities', 'lighting', 'final')) { $pend = $m; continue }
    $argLines += $(if ($pend) { "$pend $m" } else { $m }); $pend = ''
}
$lines = $(if ($argLines.Count) { $argLines } else {
    $qf = Join-Path $Port 'build_queue.txt'
    if (-not (Test-Path $qf)) { Write-Host "No maps given and no $qf" -ForegroundColor Red; exit 1 }
    Get-Content $qf })
foreach ($ln in $lines) {
    $p = @(($ln -replace '#.*$', '').Trim() -split '\s+' | Where-Object { $_ })
    if (-not $p.Count) { continue }
    $assetsOnly = $false; $mode = 'full'
    if ($p[0] -ieq 'assets' -and $p.Count -gt 1) { $assetsOnly = $true; $p = @($p[1..($p.Count - 1)]) }
    elseif ($p[0] -in @('entities', 'lighting', 'final') -and $p.Count -gt 1) { $mode = $p[0].ToLower(); $p = @($p[1..($p.Count - 1)]) }
    $queue += ,@($p[0], $(if ($p.Count -gt 1) { $p[1] } else { $p[0] }), $assetsOnly, $mode)
}

# CS2 / Hammer holding a map open stops the vpk being replaced
# (only this install's cs2.exe: a dedicated server from another folder doesn't hold these files)
while (Get-Process -Name cs2 -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith($CS2, [StringComparison]::OrdinalIgnoreCase) }) {
    Write-Host 'CS2 / Hammer is running. Close it, then press Enter (the build cannot replace a map that is loaded).' -ForegroundColor Yellow
    Read-Host | Out-Null
}
while (Get-Process -Name resourcecompiler -ErrorAction SilentlyContinue) {
    Write-Host 'Another resourcecompiler is still running - waiting for it to finish...' -ForegroundColor Yellow
    Start-Sleep -Seconds 10
}

$summary = @()
foreach ($q in $queue) {
    $addon = $q[0]; $map = $q[1]; $assetsOnly = $q[2]; $mode = $q[3]
    $vmap  = Join-Path $CS2 "content\csgo_addons\$addon\maps\$map.vmap"
    $built = Join-Path $OutRoot "csgo_addons\$addon\maps\$map.vpk"
    $dest  = Join-Path $CS2 "game\csgo_addons\$addon\maps\$map.vpk"
    $log   = Join-Path $Logs "${addon}_build.log"
    Write-Host ''
    if ($mode -in @('entities', 'lighting') -and -not (Test-Path $dest)) {
        Write-Host "     no earlier build of $map.vpk in game\, so this is a full build instead of '$mode'" -ForegroundColor Yellow; $mode = 'full'
    }
    Write-Host "==== $addon : $(if ($assetsOnly) { 'assets only' } elseif ($mode -eq 'final') { "compiling $map.vmap (final: 2048 lightmaps, quality 2)" } elseif ($mode -ne 'full') { "compiling $map.vmap ($mode only)" } else { "compiling $map.vmap" }) ====" -ForegroundColor Cyan
    if (-not $assetsOnly -and -not (Test-Path $vmap)) {
        Write-Host "     FAILED - $vmap not found" -ForegroundColor Red
        $summary += "$addon FAILED (no vmap)"; continue
    }
    if (Test-Path $built) { Remove-Item $built -Force }   # stale vpk from an earlier build must never be copied

    # assets first: the command-line map build does not compile materials/textures Hammer never loaded
    $content = Join-Path $CS2 "content\csgo_addons\$addon"
    $alog = Join-Path $Logs "${addon}_assets.log"
    Set-Content -Path $alog -Value "asset pre-compile $(Get-Date)"
    Write-Host "     compiling addon assets (materials, radar, HUD, sounds, scripts)..."
    foreach ($spec in @('materials|*.vmat', 'models|*.vmdl', 'panorama|*.vtex', 'panorama|*.xml', 'panorama|*.css', 'soundevents|*.vsndevts', 'sounds|*.wav', 'sounds|*.mp3', 'maps\scripts|*.js')) {
        $d, $pat = $spec -split '\|'
        $dir = Join-Path $content $d
        if (-not (Get-ChildItem $dir -Recurse -Filter $pat -File -ErrorAction SilentlyContinue | Select-Object -First 1)) { continue }
        $spec_in = (($dir -replace '\\', '/') + '/' + $pat).ToLower()
        & $RC -r -i $spec_in -nop4 -quiet 2>&1 | ForEach-Object { "$_" } | Add-Content -Path $alog
    }
    $bad = @(); $unused = @(); $novmap = $false
    # only materials the map uses (or model materials) are fatal; leftovers nothing references are reported and skipped
    # the map being built plus the prefabs it still references (a collapsed import's old prefab files don't count)
    if (Test-Path $vmap) { $vtext = [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($vmap)).ToLower() } else { $vtext = ''; $novmap = $true }   # assets-only with no vmap: every uncompiled material counts
    foreach ($pf in ([regex]::Matches($vtext, 'maps/[a-z0-9_./\-]+\.vmap') | ForEach-Object { $_.Value } | Sort-Object -Unique)) {
        $pp = Join-Path $content ($pf -replace '/', '\')
        if (Test-Path $pp) { $vtext += [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($pp)).ToLower() }
    }
    Get-ChildItem (Join-Path $content 'materials') -Recurse -Filter *.vmat -File -ErrorAction SilentlyContinue | ForEach-Object {
        $rel = $_.FullName.Substring($content.Length).TrimStart('\')
        $c = Join-Path $CS2 "game\csgo_addons\$addon\${rel}_c"
        $key = ($rel -replace '\\', '/').ToLower()
        if (-not (Test-Path $c)) { if ($novmap -or $vtext.Contains($key) -or $key.StartsWith('materials/models/')) { $bad += $rel } else { $unused += $rel } }
        elseif ((Get-Item $c).LastWriteTime -lt $_.LastWriteTime) { Write-Host "     note: $rel compiled file is older than the source (compiler judged it up to date)" -ForegroundColor Yellow }
    }
    if ($unused.Count) {
        Write-Host "     note: not compiled but no vmap uses them (left out of the build):" -ForegroundColor Yellow
        $unused | ForEach-Object { Write-Host "        $_" -ForegroundColor Yellow }
    }
    if ($bad.Count) {
        Write-Host "     FAILED - these materials did not compile (see logs\${addon}_assets.log):" -ForegroundColor Red
        $bad | ForEach-Object { Write-Host "        $_" -ForegroundColor Red }
        $summary += "$addon FAILED (materials did not compile: $($bad -join ', '))"; continue
    }
    if ($assetsOnly) {
        Write-Host "     OK - assets compiled (no map build requested)" -ForegroundColor Green
        $summary += "$addon assets OK"; continue
    }

    $in = ($vmap -replace '\\', '/').ToLower()
    if ($mode -in @('full', 'final')) {
        $lmRes = $(if ($mode -eq 'final') { '2048' } else { '1024' }); $lmQ = $(if ($mode -eq 'final') { '2' } else { '1' })
        $rcArgs = @('-threads', '5', '-fshallow', '-maxtextureres', '256', '-quiet', '-unbufferedio', '-i', $in,
            '-noassert', '-world', '-rebake_surfacegraph', '-bakelighting', '-lightmapMaxResolution', $lmRes,
            '-lightmapVRadQuality', $lmQ, '-phys', '-vis', '-nav', '-sareverb', '-sareverb_threads', '6', '-sapaths',
            '-sareverb_threads', '6', '-sacustomdata', '-sacustomdata_threads', '6', '-breakpad', '-nop4',
            '-outroot', $OutRoot)
    } else {
        # skink52's Hammer arguments for an entity-only / lighting-only build. They update the map's existing build, so the current .vpk goes back
        # into the outroot first (the copy keeps its old date, so a compile that writes nothing still counts as failed below)
        $part = $(if ($mode -eq 'entities') { '-entities' } else { '-world' })
        $rcArgs = @('-threads', '5', '-fshallow', '-maxtextureres', '256', '-quiet', '-html', '-unbufferedio', '-i', $in,
            '-noassert', $part, '-rebake_surfacegraph', '-bakelighting', '-lightmapMaxResolution', '2048',
            '-lightmapVRadQuality', '2', '-breakpad', '-nop4', '-outroot', $OutRoot)
        New-Item -ItemType Directory -Force -Path (Split-Path $built) | Out-Null
        Copy-Item $dest $built -Force
    }
    $t0 = Get-Date
    & $RC @rcArgs 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath $log
    $code = $LASTEXITCODE
    $mins = [math]::Round(((Get-Date) - $t0).TotalMinutes, 1)

    # the outroot step: move the fresh vpk into the game addon before anything else runs
    if ((Test-Path $built) -and ((Get-Item $built).LastWriteTime -ge $t0.AddSeconds(-5))) {
        New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
        $size = (Get-Item $built).Length; $ok = $false
        for ($try = 1; $try -le 10 -and -not $ok; $try++) {
            try {
                Copy-Item $built $dest -Force -ErrorAction Stop
                if ((Get-Item $dest).Length -eq $size) { Remove-Item $built -Force; $ok = $true }
            } catch { Write-Host "     $dest is locked, retrying ($try/10)..." -ForegroundColor Yellow; Start-Sleep -Seconds 5 }
        }
        # anything else the compiler wrote for this addon goes to the same place in game\
        $addonOut = Join-Path $OutRoot "csgo_addons\$addon"
        Get-ChildItem $addonOut -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
            $rel = $_.FullName.Substring($addonOut.Length).TrimStart('\')
            $to = Join-Path $CS2 "game\csgo_addons\$addon\$rel"
            New-Item -ItemType Directory -Force -Path (Split-Path $to) | Out-Null
            Copy-Item $_.FullName $to -Force; Remove-Item $_.FullName -Force
        }
        if ($ok) {
            $warn = $(if ($code -ne 0) { " (compiler exit code $code - check the log)" } else { '' })
            Write-Host "     OK in $mins min - $map.vpk moved to game\csgo_addons\$addon\maps$warn" -ForegroundColor Green
            $summary += "$addon OK $mins min$warn"
            Mark-Built $addon
        } else {
            Write-Host "     FAILED - could not move $built to $dest (is CS2 open?)" -ForegroundColor Red
            $summary += "$addon FAILED (vpk built but not moved - it is still in the temp outroot)"
        }
    } else {
        Write-Host "     FAILED after $mins min - no new $map.vpk (exit code $code). See logs\${addon}_build.log" -ForegroundColor Red
        $summary += "$addon FAILED (exit code $code, no vpk)"
    }
}

$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm'
foreach ($s in $summary) { Add-Content -Path (Join-Path $Logs 'stage_d_done.txt') -Value "$stamp $s" }
Write-Host ''
Write-Host '==== Summary ====' -ForegroundColor Cyan
$summary | ForEach-Object { Write-Host "  $_" }
Write-Host ''
Write-Host 'All done. Tell Claude stage D finished - it reads the logs from C:\source1\cs2port\logs'
