# mg_monsoon: build, deploy, compile, first launch

AI-generated (Claude) for skink52. The terse command sheet is [../tools/build_monsoon.md](../tools/build_monsoon.md); this page says why
each step is there and what to look for.

**How far this is checked (12 Nov 2026).** Steps 1-8 (generation) have been run on this PC; their outputs are **simulated** or
checked offline only (mesh check, world check, mock engine, HUD layout check, numeric sound check). Step 9 (`deploy_monsoon.py`)
has been run as a dry run against the real addon folders and as a real copy into a temp folder (**unit tested** by hand, no test file).
Steps 10-12 (compile, launch) have **never been run for this map**: nothing here is compiled, Hammer verified or in-game verified.
Times for steps 10-11 are estimates from the sibling maps, not measurements.

## Before you start

- Python 3.13 with numpy, scipy, Pillow; Node 22+; TypeScript for `tsc`. SteamCMD at `C:\steamcmd` for the GMod fetch.
- All generator commands run from `projects/monsoon-cs2/tools` unless a line says otherwise. Outputs go to `out/` (git-ignored).
- One generator at a time writes `out/addon`: prop builds serialise on `out/build.lock`; the deploy refuses while it exists.
- Anything over about 2 minutes runs under the watchdog with an expected time, in the background:
  `python C:\source1\cs2port\autoport\watchdog.py --label "<what>" --expect <s> --heartbeat <s> --stall <s> --max <3 x expect> --log <its own file> -- <command>`.
  Its first output line states the policy ("hung after ..., killed after ..."); it is not a report of a hang. Use `python -u` for
  Python steps or the log stays empty until the end. Exit 124 = hung, 125 = over `--max`.
- Close Hammer before the map is regenerated or deployed. If CS2 is open in tools mode on `mg_monsoon`, do not deploy: the game
  reloads every changed file and restarts the script (the deploy tool checks and holds).

## Order

| # | Step | Command (from `tools/`) | Time | Check |
|---|---|---|---|---|
| 1 | Procedural props (117) | `MV_OUT=<abs>/out/addon python -u build_all_props.py [names]` | 10-95 s per prop; all of them about 40 min (estimate) | `out/props.json` has every name with a vmdl; turntables in `preview/` |
| 1b | Flag pole with skins | `MV_OUT=... python p_jungle.py` | seconds | after any rebuild of `flag_pole_n/_t/_ct` |
| 1c | LODs | `python lod_decimate.py ../out/addon ../out/addon mv/<name> ...` | 1-2 min | after any rebuild of the 15 props in the list below; prints charts per LOD |
| 2 | Apache (CC-BY, US helicopters) | `python apache_setup.py ../out/addon` | under 1 min | `out/apache.json`; 60 MB under `models/vehicles/apache` |
| 3 | GMod conversions | `python -I gmod_assets.py fetch`, `convert`, `view`, `report` | fetch: download speed (several GB); convert about 30 s per model, 53 models | `out/gmod_models.json`; `out/gmod/view/_sheet*.png` |
| 4 | Map | `python -u make_map.py <template or live .vmap> ../out/addon/maps/mg_monsoon.vmap ../out/addon [<previous generated .vmap>]` | 3-8 min (last run 181 s) | last line `vmap: N entities ...`; then `python check_mesh.py <vmap>` (0 bad) and `python check_world.py <vmap>` (exit 0) |
| 5 | Sounds | `python sounds.py ../out/addon "C:/source1/links/content_addons/addon_template/soundevents/soundevents_addon.vsndevts"` | 8 s | exit 0; `out/sounds_report.json` |
| 6 | Radar, board, slides, skybox | `python make_radar.py ../out/addon ../out/game`; `python render_board.py ../out/addon`; `python make_sky.py` | 1-2.5 min, 2 min, 1 min | `out/radar_preview.png`; `out/sky.json`, check_mesh 0 bad |
| 7 | HUD | `python mv_hud.py ../out/addon` | 1 min | exit 0 (contract + `hud_check.py` gate); `out/hud/hud_<state>.png` |
| 8 | Script + tests | from the project folder: `node tools/build_script.mjs`; `node test/mock.mjs 32 600`; `node test/mock.mjs 4 600`; `tsc -p test/tsconfig.json`; from `cs2mapping`: `python create/test/api.py --strict --check projects/monsoon-cs2/out/addon/maps/scripts/mg_monsoon.js` | under 2 min | both mock runs PASS, nothing invalid or deprecated |
| 9 | Deploy | from the project folder: `python -I tools/deploy_monsoon.py` then `--apply` | dry run seconds; first apply about 1.2 GB copied, 1-3 min | see "Deploy" |
| 10 | Compile assets, HUD, script | see "Compile" | first time 9 min (measured 12 Nov 2026) | `logs\mg_monsoon_assets.log` |
| 11 | Compile the map | `build_maps.ps1 final mg_monsoon` under the watchdog | 45-60 min (estimate) | see "What to read in the build log" |
| 12 | Launch | see "Local test with bots" | | TESTING_MONSOON.md |

Order matters in three places: the map (4) needs the props, Apache and `out/props.json`; the HUD (7) preloads the slides and the board
picture from step 6; the script build (8) bakes in `out/layout.json` (written by step 4), `out/hud.json` (step 7) and reads
`out/entities.json` (step 4). After any change to `tools/layout.py` re-run 4, 6, 7, 8.

Step 1c list (rebuilding one of these overwrites its vmdl, so re-run `lod_decimate.py` on it): bunker_large, bunker_small,
cargo_pallet, checkpoint, culvert_bunker, fdc_bunker, fuel_bladder, gp_tent, guard_tower, truss_span, sandbag_wall, sandbag_wall_b,
sandbag_wall_128, sandbag_low, sandbag_low_128.

Step 4, first run and later runs: the first run takes `out/template.vmap` (a copy of
`content\csgo_addons\addon_template\maps\xxx_mapname_xxx.vmap`). Once the map has been opened and edited in Hammer, pass the
**live** `content\csgo_addons\mg_monsoon\maps\mg_monsoon.vmap` as the first argument and the previous generated vmap as the
fourth, so Hammer edits survive (vis groups `mv_gen` / `mv_user`). Back the live map up first
(`python C:\source1\cs2port\tools\mapbackup.py`, or copy it).

Step 3 is optional for a rebuild: the conversions are already in `out/addon/models/mv/ext` (264 MB) and
`materials/models/mv/ext` (280 MB). As generated on 11 Nov 2026 the map references **none** of them (the deploy dry run prints the
list the vmap uses); they are a Workshop blocker if they ever are placed, see [WORKSHOP_COMPLIANCE.md](WORKSHOP_COMPLIANCE.md).

## Deploy (step 9)

```
cd C:\source1\cs2mapping\projects\monsoon-cs2
python -I tools/deploy_monsoon.py            # dry run: counts, sizes, gates; writes nothing
python -I tools/deploy_monsoon.py --apply    # copies; record in out/deploy/mg_monsoon_deploy_<stamp>.json
```

- `out/addon` -> `C:\source1\links\content_addons\mg_monsoon`, `out/game` -> `C:\source1\links\game_addons\mg_monsoon`.
- Only files whose bytes differ are written (size + sha256); nothing is deleted; replaced files are backed up first
  (`out/deploy/backups/<stamp>/`, a `.vmap` as `<map>.vmap.bak_<stamp>` next to it). `--rollback <manifest> --apply` undoes a run.
- Held with exit 3 while a `cs2.exe -tools ... mg_monsoon` is running; exit 4 while `out/build.lock` exists.
- A destination `.vmap` that changed since the last deploy (Hammer edits) is kept. Regenerate from it (step 4) and then deploy
  with `--overwrite-map`.
- The addon's `soundevents_addon.vsndevts` is merged: only the `mg_monsoon` block is replaced.
- A new addon also gets `postprocess/mg_monsoon.vpost` (the map's `post_processing_volume` names it) and
  `basic_linear_post.vpost` from `addon_template`, and an empty game-side `addoninfo.txt`.
- README_MONSOON.md, TESTING_MONSOON.md, CREDITS.md and both licence files go to both addon roots;
  `docs/WORKSHOP_DESCRIPTION.txt` becomes `mg_monsoon STEAM DESCRIPTION.txt` in the content addon (a hand-edited copy is kept).
- `--skip-ext` leaves the GMod conversions out (544 MB less); only safe while the vmap references none of them.

Dry run of 12 Nov 2026, 03:15 (addon not yet created): 2697 files to copy plus 3 written (sound events, `addoninfo.txt`, the
Steam description), 1157 MB, 0 to replace, 0 only in the destination; the largest parts are models about 540 MB and materials
about 515 MB. Free space on C: was 115 GB. The numbers move while generators are still writing `out/addon`: run the dry run
again before `--apply`. The compile adds a game-side tree whose size is unknown until the first build.

## Compile (steps 10 and 11)

Rules that have cost a build before:
- Run `build_maps.ps1` with the working folder `C:\source1\cs2port`, **never** `C:\source1` (its `gameinfo.txt` gets mounted and
  every material fails).
- The watchdog's `--log` must be a file of its own. `build_maps.ps1` tees into `logs\mg_monsoon_build.log`; pointing `--log` at
  that file locks it and the build fails at once. Use `--watch` for the build's log.
- CS2 may be open, but only if it was started before the build and stays open until the build ends; no map of this addon loaded.
- One compile at a time: `build_maps.ps1` waits while another `resourcecompiler.exe` runs.

### 10. Assets, then HUD and script by hand

```
cd /d C:\source1\cs2port
python C:\source1\cs2port\autoport\watchdog.py --label "mg_monsoon assets" --expect 1800 --heartbeat 120 --stall 600 --max 5400 ^
  --log C:\source1\cs2port\logs\mg_monsoon_assets_watch.log --watch C:\source1\cs2port\logs\mg_monsoon_assets.log -- ^
  powershell -NoProfile -ExecutionPolicy Bypass -File C:\source1\cs2port\build_maps.ps1 assets mg_monsoon
```

Measured 12 Nov 2026 ([BUILD_LOG_1.md](BUILD_LOG_1.md)): **9 min the first time** (332 materials 7 min, 193 models 1.5 min), about
30-45 s afterwards, because only changed sources are rebuilt. The wrapper says "assets OK" even when models failed: grep the log for
`RESOURCE COMPILE ERROR` and `compiled, N failed`. Progress: the heartbeat's CPU and MB-written numbers and
`logs\mg_monsoon_assets.log` growing. `build_maps.ps1 -DryRun assets mg_monsoon` lists what it would compile and changes nothing.

Then always, because a failed layout is ignored silently and the pre-pass has missed these before:

```
set RC="C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\bin\win64\resourcecompiler.exe"
set A=C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\content\csgo_addons\mg_monsoon
%RC% -f -i "%A%\panorama\layout\custom_game\mg_monsoon.xml"
%RC% -f -i "%A%\panorama\styles\custom_game\mg_monsoon.css"
%RC% -f -i "%A%\maps\scripts\mg_monsoon.js"
```

Each must print a "compiled" line and no error. Under a minute in total, so no watchdog. The compiled files land in
`game\csgo_addons\mg_monsoon\` as `.vxml_c`, `.vcss_c`, `.vjs_c`.

### 11. The map

```
cd /d C:\source1\cs2port
python C:\source1\cs2port\autoport\watchdog.py --label "mg_monsoon final" --expect 3600 --heartbeat 120 --stall 900 --max 10800 ^
  --log C:\source1\cs2port\logs\mg_monsoon_final_watch.log --watch C:\source1\cs2port\logs\mg_monsoon_build.log -- ^
  powershell -NoProfile -ExecutionPolicy Bypass -File C:\source1\cs2port\build_maps.ps1 final mg_monsoon
```

From Git Bash quote the script path in single quotes (`'C:\source1\cs2port\build_maps.ps1'`); unquoted backslashes are eaten.

- `final` = world, vis, nav, audio, lightmaps at `-lightmapMaxResolution 2048`, VRAD quality 2. A plain `mg_monsoon` line bakes at
  1024, quality 1: fine for a first "does it load" build (shorter), not for judging the look.
- **Lightmap resolution: 2048.** The sibling mg_trenchwarfare needed 2048 once its chart count was under control (29 Oct 2026: 1.37 M
  charts packed into 2048 x 2048 in 19 min with no out-of-memory; the same map at 5.6 M charts needed 4096 and then ran out of
  memory at "Welding seams"). mg_monsoon's play space is 12800 x 10240 with a lightmap shell only over the walkable band, so start
  at 2048 and do not raise it: if the packer asks for more, the fix is fewer charts (below), not a bigger atlas.
- **Probe-lit foliage.** `mv_places.py` writes `bakelighting 0` for foliage, wire, cards and every prop under 40 units (`probed()`),
  as the sibling does since its tw12 build stalled charting 26,669 meshes. If a build stalls in "Charting" or "Packing", the first
  thing to check is that foliage did not end up lightmapped.
- Expected time: 45-60 min. This is an estimate, never measured: mg_trenchwarfare final 19 min, mg_ironframe_dunes full builds
  22-37 min, and this map is larger (6,388 entities, 5,743 static props, 55 MB vmap, a 13 MB 3D skybox map). Threads default to
  logical cores minus 2.
- The 3D skybox map (`maps/mg_monsoon_3dskybox.vmap`) has no queue line of its own: the main map's `skybox_reference` pulls it in,
  as mg_trenchwarfare's did. Not yet confirmed for this map: check the log names it.
- Checking on it: report elapsed against 60 min, whether CPU or the build log moved since the last look, and the last log line.
  No CPU, disk or log movement for 15 minutes = hung: stop it (and after stopping, `taskkill /PID <pid> /T /F` any
  `resourcecompiler.exe` this build left behind; never another session's).

### What to read in the build log

`C:\source1\cs2port\logs\mg_monsoon_build.log` (map) and `logs\mg_monsoon_assets.log` (assets). The summary also goes to
`logs\stage_d_done.txt`. A wrapper exit code 0 proves nothing: read the log.

| Look for | Meaning | What to do |
|---|---|---|
| `OK in N min - mg_monsoon.vpk moved to game\csgo_addons\mg_monsoon\maps` | the build produced a vpk | note N in NOTES.md; this is level **compiled**, nothing more |
| `FAILED - these materials did not compile` | a `.vmat` the map or a model uses has no `.vmat_c` | open `mg_monsoon_assets.log` at that name; usually a missing texture png or a bad shader key |
| `DELETED` next to a prop or entity name | the compiler dropped it (a `prop_static` whose model has no static archetype, a model that failed to load, bad physics) | list every name; a dropped prop is a hole in cover or a missing script entity. The dynamic ones (`mv_heli_*`, `mv_tube_*`, `mv_mount_*`) must be `prop_dynamic` with `model_archetype ""` |
| `Error loading resource`, `failed to load`, `missing material`, `ERROR:` with a `.vmdl` or `.vmat` path | a model or material is missing or failed | models under `models/mv/ext/` and `models/vehicles/apache/` are the conversions: check the SMD material names (ASSETS.md "Open points") |
| `Charting N unique meshes` | lightmapped mesh count (LODs counted) | for comparison: trench 24,754 after its fix. Far above that = lightmapped props that should be probe-lit |
| `Packing N UV charts` | chart count | trench: 1.37 M fits 2048. Several million = sandbag / bunker LODs with a chart per triangle (run `lod_decimate.py`, step 1c) |
| `OUT OF MEMORY`, `FATAL ERROR` in vrad3, "Welding seams" as the last line | lightmap bake ran out of memory | reduce charts as above; do not raise the resolution |
| packer asks for a higher `lightmapMaxResolution`, or a very small packer scale | too many charts for 2048 | same |
| `no new mg_monsoon.vpk (exit code N)` | compile failed | the lines just above it in the build log |
| `could not move ... (is the map loaded in CS2 or Hammer?)` | the vpk is still in the temp outroot | close the map, build again |
| nav lines (`-nav`): area count | the nav mesh | mg_trenchwarfare lost FPS with 44k areas; the NONAV boxes are meant to keep this far lower. A count near that means `func_nav_markup` did not apply |

Record after the first compile, in NOTES.md and in this file: the CS2 build number (`version` in the console), the measured
times for steps 10 and 11, the chart counts, the nav area count.

## Local test with bots (step 12)

skink52 starts the game; an agent must not launch it (a game window takes focus, and windows opened by tools start minimised
and inactive). After the game is closed again, deploys are allowed.

1. Start CS2 in tools mode on the addon:
   `"...\game\bin\win64\cs2.exe" -addon mg_monsoon -tools -steam -retail -insecure -noassetbrowser -vulkan`
   (or pick `mg_monsoon` in the Workshop Tools launcher).
2. Console: `map mg_monsoon`.
3. Expect in the console, in this order (none of this has been seen yet):
   - `[mv] mg_monsoon script mv-0.1 (11 Nov 2026) - flags 5, bots on (quota 10)`
   - `[mv] round 1 start (mv-0.1 (11 Nov 2026))`
   - `[mv] points: spawns 16/16, helicopters 3/3, guns 4/3, mounts 8, uniforms cached N`
   - no `[mv] missing entity <name>` and no `[mv] error in ...` line
   - once a minute: `[mv] script time X ms/tick avg, Y max over N ticks, P players, errors 0`
4. Bots: the script sets `bot_quota_mode fill` and `bot_quota 10` when it activates. `!bots 14` in chat changes the quota
   (0 to 24), `!bots 0` removes them. With fewer than 4 humans on a team, bots are also put in a helicopter, on guns and on one
   battery crew.
5. Work through [TESTING_MONSOON.md](TESTING_MONSOON.md) in its order and report only what fails.

While the game is open in tools mode on `mg_monsoon`, do not deploy (the tool holds with exit 3). Script-only iteration then
goes: close the map, `node tools/build_script.mjs`, deploy, `resourcecompiler -f -i ...\mg_monsoon.js`, load the map again.
