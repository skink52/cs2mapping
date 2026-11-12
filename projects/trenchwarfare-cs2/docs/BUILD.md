# mg_trenchwarfare: chain, deploy, compile

AI-generated (Claude) for skink52. Remaster step 9 ([REMASTER_PLAN.md](REMASTER_PLAN.md)). The same shape as monsoon's
[BUILD.md](../../monsoon-cs2/docs/BUILD.md); the difference is that trench never regenerates the map: the user's Hammer map is patched.

**How far this is checked (12 Nov 2026).** The chain, the merged list, the gate and the deploy **dry run** have been run on this PC against
the real addon folders (results in "Dry run of 12 Nov" below). `create/deploy_addon.py --apply` has been run into temp folders only.
Nothing of the remaster has been deployed, compiled, Hammer verified or played. The compile commands below are monsoon's and the old
tw34 build's, not yet run for this delivery; times are from tw34 (29 Oct) and monsoon (12 Nov).

## Before you start

- Close Hammer and any `cs2.exe -tools` on `mg_trenchwarfare`. The deploy checks and holds (exit 3); the dedicated server in
  `C:\cs2server` does not count. The deploy also holds while a `resourcecompiler.exe` is compiling this addon.
- The user's map must still be the **base**: `content\csgo_addons\mg_trenchwarfare\maps\mg_trenchwarfare.vmap`, CRC32 `2e3f90d0`,
  67,206,918 bytes (the tw34 delivery, not saved in Hammer since 29 Oct; copy in `backups\remaster_20261112\`). Every patch matches its
  targets by element id, and ids change on a Hammer save. After a save the chain stops at stage 1 and says so: the patches' target
  tables have to be re-read from the new map's digest (`python ../../tools/mapdigest.py <map> --summary` ...) and `BASE` in
  `tools/deploy_tw.py` updated. Never deploy over a newer Hammer save; the tool will not.
- Anything over about 2 minutes runs under the watchdog, in the background, with its own log:
  `python C:\source1\cs2port\autoport\watchdog.py --label "<what>" --expect <s> --heartbeat <s> --stall <s> --max <3 x expect> --log <its own file> -- <command>`.
  Its first line states the policy; it is not a hang. `python -u` or the log stays empty. Exit 124 hung, 125 over `--max`.

## Order

| # | Step | Command | Time | Check |
|---|---|---|---|---|
| 1 | Chain + gate + dry run | from the project folder: `python -u tools/deploy_tw.py --chain` (watchdog) | about 18 min (13 Nov: 1,102 s with seams 3.6 min, world_3 1.4 min, gate 4 min) | `out/step9/chain.json` `ok`, every stage `guard: RESULT: PASS`; `out/step9/gate.json` `ok`; the dry-run table |
| 2 | Deploy | `python -u tools/deploy_tw.py --apply` (runs the gate again) | gate 3-5 min, copy under a minute | `deployed: ...`; record `out/step9/deploy/mg_trenchwarfare_deploy_<stamp>.json` |
| 3 | Compile assets | `build_maps.ps1 assets mg_trenchwarfare` (watchdog, from `C:\source1\cs2port`) | monsoon's first: 9 min; trench has fewer new files: a few minutes (estimate) | the log, not the wrapper: see "What to read" |
| 4 | Force HUD / script / icon | `resourcecompiler -f -i` on the xml, css, js | under a minute | each `compiled`, `0 failed` |
| 5 | Compile the map | `build_maps.ps1 final mg_trenchwarfare` (watchdog) | tw34: 19 min (29 Oct); the terrain patch added 80k triangles: 20-35 min (estimate) | "What to read"; nav area count; lightmap 2048 |
| 6 | Record | [BUILD_LOG_1.md](BUILD_LOG_1.md) | | errors before / after, times, nav count |
| 7 | Launch | skink52 starts the game (an agent never does: focus) | | TESTING checklist (step 10) |

## 1. The chain

```
cd C:\source1\cs2mapping\projects\trenchwarfare-cs2
python C:\source1\cs2port\autoport\watchdog.py --label "tw chain" --expect 1000 --heartbeat 120 --stall 600 --max 3000 ^
  --log out\step9\deploy_tw_chain_run.log -- python -u tools/deploy_tw.py --chain
```

`out/step9/chain/0_user.vmap` (a copy of the user's map, checked against the base) -> `1_world_1` (`patch_world_1.py`, step 5) ->
`2_models` (`patch_models.py`, step 6) -> `3_terrain` (`patch_terrain.py`, step 7) -> `4_seams` (`patch_seams.py`: ground caps over the
slot behind every generated revetment top, parapet sheet edges lowered onto the terrain, the sap mouths' floor ramp, lintel and ground
cap; [REVIEW_WORLD_2.md](REVIEW_WORLD_2.md) "Seams") -> `5_world_3` (`patch_world_3.py`: the four CT air-lane poplars scaled down by the
minimum, pit_t_2's shell rack turned along the breastwork, the poplar out of its crater pool, 56 crater pool rims set onto the ground;
[REVIEW_WORLD_3.md](REVIEW_WORLD_3.md)) -> `6_sounds` (`patch_sounds.py`, step 8: the sound entities; skipped with a note while the tool
does not exist) -> `7_nav` (`patch_nav.py --estimate --stage out/addon`, step 4: it reads the staged models like the gate, so the rebuilt
shelter of step 13 is walkable to it) = the map that ships. (Before 13 Nov the stages after the seams were `5_sounds`, `6_nav`; before
12 Nov 22:00 there was no seams stage and they were `4_sounds`, `5_nav`. Old files of those names in `out/step9/chain/` are stale.)
Each stage: its input must be the byte-exact output of the stage before; its output goes through `tools/patch_guard.py --strict` (only
the declared nodes changed). With no opt-in flags the outputs are compared with the earlier steps' own maps
(`out/mg_trenchwarfare_patched.vmap`, `_models`, `_terrain`): the same bytes means the patches are deterministic.
Then the radar is re-made from the final map (`make_radar.py --vmap <final>`, `check_radar.py`; step 8's staging).

The patch tools also rewrite records in `out/step5..7/` (deploy lists, targets, the terrain report and layers); the chain keeps this
run's copies in `out/step9/chain/side/` and puts the step folders back as they were.

User-object flags (decided by the user 12 Nov 2026; [REVIEW_WORLD_1.md](REVIEW_WORLD_1.md) H1, M2): `--user-m2` (delete the duplicate
`info_map_parameters` id 7, Hammer defaults) and `--user-w5` (drop bench 72, an exact duplicate of 71 1 u above it) are **on by
default** (`--no-user-m2` / `--no-user-w5` to turn off). `--user-h1` must **not** be used for this map: the sap benches are the user's
bridges over the trench-to-tunnel seam.
A deploy refuses flags that differ from the last chain's.

`--pit-sandbags [both|ct|t]` (**OFF by default, pending the user's decision**; [REVIEW_WORLD_3.md](REVIEW_WORLD_3.md) W9): passed to
`patch_world_3.py`, which then adds one more course of `sandbag_low` (clones of each pit's own cap bag) on the enemy-facing arc of the
generated mortar pits' breastworks (a bare flag = `both`; `ct` / `t` = one side's pits only). It is recorded in `chain.json`'s flags only
when on, so `python -u tools/deploy_tw.py --chain --pit-sandbags` must be followed by deploys with the same flag. To try it without
touching `out/step9/`, run the stages by hand on copies (as in `out/step15/`, REVIEW_WORLD_3 W9).

## 2. The deploy

```
python -u tools/deploy_tw.py              # merge + gate + dry run (writes only out/step9/)
python -u tools/deploy_tw.py --show       # the same, every file listed
python -u tools/deploy_tw.py --apply      # copy (held while Hammer / cs2 -tools / a compile of this addon is running)
```

- **List**: `out/step9/deploy_files.txt`, merged from `out/step5..8/deploy_files.txt`, `out/step10/deploy_files.txt` (CREDITS, Steam
  description, licence files), `out/step11/deploy_files.txt` (weapon replacements), `out/step13/deploy_files.txt` (the rebuilt shelter: 44-u legs, 11 hull
  pieces, walkable dressing stations; [REVIEW_WORLD_3.md](REVIEW_WORLD_3.md) W2) and `out/step12/deploy_files.txt` (licence-replacement
  assets) and `out/step14/deploy_files.txt` (prop rebuilds, staged by another session; same format as step 13), each when staged (5-7 from the chain run's side copies, 8 and 10-13 as written, their `# GAME addon` section to the game addon). One line per file; a later step wins. Every step's map line is replaced by the
  chain's final map. The radar files the chain re-made are in it. A model -> material check runs on it: a material a listed model names
  must be in the list, in the addon or in the game's pak01 (the `stock.ensure` lesson: 5 monsoon props failed for stock copies nobody wrote).
- **Gate** on the final map (`out/step9/gate.json`, logs in `out/step9/gate/`): `check_world` and `check_play` may not have a failure the
  step 7 baseline did not have (`out/step9/gate_baseline.json`, frozen from `out/step7/check_*_after.log` on first use); `check_seams
  <final> --no-sight` must report `RESULT: clean` (no open seam in the generated geometry; user-owned ones are listed only); `check_contract
  --vmap <final> --stage out/addon` exit 0; the script gate of [SCRIPT.md](SCRIPT.md) without perf (`api.py --strict --check`, `tscheck`,
  mock 32 300, mock 16 300 fill=1 humans=4, mock scenario=all). A new failure refuses `--apply` (exit 6).
- **Copy**: `python -I ../../create/deploy_addon.py --addon mg_trenchwarfare --list out/step9/deploy_files.txt --record-dir out/step9/deploy
  --vmap-base <base sha256> --vmap-base 2e3f90d0 --strict-vmap`. Only files whose bytes differ; nothing deleted; replaced files backed up
  and checked (`out/step9/deploy/backups/<stamp>/`). The map is replaced only while the addon's copy is still the base or what the last
  deploy wrote, and is copied first to `content\...\mg_trenchwarfare\backups\deploy_<stamp>\maps\mg_trenchwarfare.vmap`. Record:
  `out/step9/deploy/mg_trenchwarfare_deploy_<stamp>.json` and a line in `mg_trenchwarfare_applied.txt`.
  Undo: `python -I ../../create/deploy_addon.py --addon mg_trenchwarfare --record-dir out/step9/deploy --rollback <manifest> --apply`.
- `soundevents_addon.vsndevts` is copied whole, not merged: `tools/sounds.py` already merged its block into the addon's own file
  (it strips the old tw1-tw35 block, whose start marker sat on the root brace line, which `--merge-sndevents` would refuse as a clash).
- Files that are only in the live addon are left alone (step 8's list names the old HUD pictures and wavs that are now unused).

## Old route (retired 12 Nov 2026)

Deliveries tw2-tw34 were numbered zips in `C:\source1\cs2port\assets\tw\` applied by `C:\source1\cs2port\unpack_mg_trenchwarfare.bat`:
refuse while any `cs2.exe` runs; back up both vmaps to `content\csgo_addons\prefabs+backups\` (on E:); `tar -xf` each `twN_*` zip not yet in
`logs\mg_trenchwarfare_applied.txt` (tw2..tw99 in order) over the content addon (`twN_game.zip` over the game addon); append it to the
list; `resourcecompiler -r` the HUD xml / css; offer `build_maps.ps1`.

**Do not run it any more**, and keep it from doing harm:
- Keep `logs\mg_trenchwarfare_applied.txt` as it is. It is what stops the bat re-extracting `tw34_map_main.zip` (the 29 Oct map) over the
  deployed remaster map. `deploy_tw.py` prints whether the bat is inert (every zip in `assets\tw` listed) on every run.
- Never put a new `twN_*.zip` in `assets\tw`: the bat would apply it. Deliveries now go through `deploy_tw.py` only.
- Its backups in `prefabs+backups` and the new ones in `mg_trenchwarfare\backups\deploy_<stamp>\` are both kept; nothing deletes either.
- What it did that the new route keeps: a backup of the map before every write, apply-once records (now sha256 per file, with rollback),
  the HUD compile (now forced, step 4). What it did not do and the new route does: refuse a map saved in Hammer since the delivery
  was made (the bat overwrote it with the zip's map), refuse only the tools instance (not the dedicated server), copy only changed files.

## 3-5. Compile

Rules that have cost a build before ([MONSOON_STANDARD.md](research/MONSOON_STANDARD.md) section 11):
- Working folder `C:\source1\cs2port`, **never** `C:\source1` (its `gameinfo.txt` gets mounted and every material fails).
- The watchdog's `--log` is a file of its own; follow the build's log with `--watch` (pointing `--log` at `logs\mg_trenchwarfare_build.log`
  locks it and the build fails at once).
- One compile at a time (`build_maps.ps1` waits for another `resourcecompiler.exe`); CS2 may be open only if started before the build
  and kept open until it ends, with no map of this addon loaded.
- From Git Bash quote the script path in single quotes; unquoted backslashes are eaten.

### 3. Assets

```
cd /d C:\source1\cs2port
python C:\source1\cs2port\autoport\watchdog.py --label "tw assets" --expect 600 --heartbeat 60 --stall 600 --max 1800 ^
  --log C:\source1\cs2port\logs\mg_trenchwarfare_assets_watch.log --watch C:\source1\cs2port\logs\mg_trenchwarfare_assets.log -- ^
  powershell -NoProfile -ExecutionPolicy Bypass -File C:\source1\cs2port\build_maps.ps1 assets mg_trenchwarfare
```

13 Nov (step 13): `models/tw/shelter/shelter.vmdl` and its SMDs changed (taller iron, 11 hull pieces): the asset pass compiles it; check
`shelter.vmdl` in the log (`1 compiled`), or force it with `resourcecompiler -f -i` on it. Test-compiled in the scratch addon
`tw_weapontest`: 1 compiled, 0 failed. Compile assets **before** the map: the map's physics and nav take the shelter's compiled hulls.

New this delivery: the `_dyn` mortar and blocker twins (with idle / fire anims), the Canon de 75, LOD rewrites of 7 models,
`tw_de_a_body.dmx` (the T player model **must** recompile: a player model that fails to load gave the giant first-person weapons),
step 8's wavs, HUD pictures, slides, radar. `build_maps.ps1 -DryRun assets mg_trenchwarfare` lists what it would compile.

### 4. HUD, script, icon: always forced

A broken panorama layout is ignored silently, and the asset pass has missed these before:

```
set RC="C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\bin\win64\resourcecompiler.exe"
set A=C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\content\csgo_addons\mg_trenchwarfare
%RC% -f -i "%A%\panorama\layout\custom_game\mg_trenchwarfare.xml"
%RC% -f -i "%A%\panorama\styles\custom_game\mg_trenchwarfare.css"
%RC% -f -i "%A%\maps\scripts\mg_trenchwarfare.js"
%RC% -f -i "%A%\panorama\images\map_icons\map_icon_mg_trenchwarfare.svg"
```

Each must print `compiled` and `0 failed`. The css preloads the slides and HUD pictures, so they compile with it.

### 5. The map

```
cd /d C:\source1\cs2port
python C:\source1\cs2port\autoport\watchdog.py --label "tw final" --expect 1800 --heartbeat 120 --stall 900 --max 5400 ^
  --log C:\source1\cs2port\logs\mg_trenchwarfare_final_watch.log --watch C:\source1\cs2port\logs\mg_trenchwarfare_build.log -- ^
  powershell -NoProfile -ExecutionPolicy Bypass -File C:\source1\cs2port\build_maps.ps1 final mg_trenchwarfare
```

- `final` = world, vis, nav, audio, lightmaps at `-lightmapMaxResolution 2048`, VRAD quality 2. **Stay at 2048.** tw34 packed 1.37 M charts
  into 2048 in 19 min; the same map at 5.6 M charts needed 4096 and ran out of memory at "Welding seams". Too many charts -> fewer charts
  (probe-lit props, `bakelighting 0`, LODs), never a bigger atlas.
- The 3D skybox map comes in through `skybox_reference`; it has no queue line of its own.
- Checking on it: elapsed against 30 min, whether CPU or the build log moved since the last look, the last log line. No CPU, disk or
  log movement for 15 min = hung: stop it and `taskkill /PID <pid> /T /F` the `resourcecompiler.exe` this build left (never another session's).

### What to read in the log

`C:\source1\cs2port\logs\mg_trenchwarfare_assets.log` (assets) and `mg_trenchwarfare_build.log` (map); summary in `logs\stage_d_done.txt`.
**The wrapper's "assets OK" proves nothing**: `build_maps.ps1` treats only uncompiled materials as fatal; a failed model is only in the log.
Save a copy of each log into `out/step9/logs/` (the build overwrites them).

| grep for | Meaning | What to do |
|---|---|---|
| `RESOURCE COMPILE ERROR`, `compiled, N failed` (N > 0) | an asset failed (monsoon run 1: 5 models, wrapper still "assets OK") | the line names the file; usually a missing material (`stock.ensure`) or texture |
| `referencing missing material` | a model's material is not in the addon or the game | deploy it; the deploy's material check should have caught it |
| `DELETED` | the map compile dropped an entity: a `prop_dynamic` on a `static_prop_model` vmdl, a model that failed to load | every name: `mortar_<tg>_K` and the 4 unlock blockers must NOT be here (H4/H2 put them on `_dyn` twins); a dropped blocker opens an area at round start |
| `Error loading resource`, `failed to load`, `missing material`, `ERROR:` with a path | missing or broken asset | fix, redeploy, recompile assets |
| `LODGroupList : Only a single LOD group` | a one-group LOD list | `lod_decimate` fix (monsoon) |
| `FAILED - these materials did not compile` | a `.vmat` has no `.vmat_c` | the assets log at that name |
| `shaders_pc.vpk ... invalid` FATAL | Valve's shader pack failed to open once (monsoon) | rerun before chasing; Steam verify if it repeats |
| `Charting N unique meshes`, `Packing N UV charts` | lightmap load | tw34: 24,754 meshes, 1.37 M charts in 2048. The terrain patch re-gridded 47 tiles (+80k tris): expect more; several million = stop and cut charts |
| `OUT OF MEMORY`, vrad3 `FATAL`, "Welding seams" as the last line | bake out of memory | fewer charts; never raise the resolution |
| nav: the generated area count | the nav mesh | tw34: 44,160 (the hitch every 0.5 s). Target < 5,000; first compile 10,269; nav pass 2 measured 4,377 with `tools/navtest.py` (3-min nav-only test compile). Near 44k = the NONAV boxes did not apply |
| `OK in N min - mg_trenchwarfare.vpk moved` | a vpk was built | level **compiled**, nothing more; record N |
| `no new mg_trenchwarfare.vpk (exit code N)` | compile failed | the lines above it |

### Post-compile checks

- Nav area count from the build log (line with the generated areas); write it in BUILD_LOG_1 and REVIEW_SCRIPT_1 "Step 4".
- Lightmap: the log's lightmap resolution must be 2048 and the packer must not ask for more; chart counts beside tw34's.
- `python tools/check_world.py` on the deployed map: check 7 (`0 of ours not compiled`, no `stale`) now that the models are compiled.
- `DELETED` list empty for our entities; every `RESOURCE COMPILE ERROR` triaged in BUILD_LOG_1.
- The game addon has `maps/mg_trenchwarfare.vpk`, `maps/scripts/mg_trenchwarfare.vjs_c` newer than the deploy, the `.vxml_c` / `.vcss_c`.

## Dry run of 12 Nov 2026

Chain about 6 min (stages 14 + 13 + 82 + 96 s, guards 15-30 s each, radar 140 s); merge + gate + dry run about 2.5 min. Final map
CRC32 `a109a678` (89.8 MB); gate PASS; 110 files, 148 MB to write (80 new, 28 replaced, 2 unchanged), 70 MB backed up first.
Details, the per-folder table and the first, refused gate run in [BUILD_LOG_1.md](BUILD_LOG_1.md) "Before the compile".
Re-run the chain whenever a patch tool, the user's map or step 8's radar inputs change; the dry run says when the radar is stale.

## Dry run of 13 Nov 2026 (REVIEW_WORLD_3)

Chain 1,102 s with the gate and the dry run (stages 18 + 17 + 81 + 218 + 81 + 45 + 120 s, a guard of 19-28 s each, then the radar).
The final map `out/step9/chain/7_nav.vmap` is CRC32 `56bff078` (96.9 MB). Gate **PASS**. check_play fails only on `sightlines`
(REVIEW_WORLD_3 W9, a design call; the baseline has it). Nav test 4,394 areas.
Dry run: 203 files, 98.3 MB to write (10 new, 7 changed, 186 the same). It changes the map, the 15 rebuilt shelter files and the radar
png. After an `--apply`: compile the assets first (the shelter), then the map, then run `tools/navcheck.py` on the new nav (the
dressing stations should be on the nav once the shelter's new hulls are compiled).
