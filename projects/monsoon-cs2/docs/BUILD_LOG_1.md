# mg_monsoon build log 1: first deploy and asset compile (12 Nov 2026)

AI-generated (Claude) for skink52. Stage 1 of the first real CS2 build: deploy, then compile every addon asset **except the map**
(a polish pass was rewriting `out/addon/maps/mg_monsoon.vmap` at the same time). Level reached: assets **compiled** (resourcecompiler,
no errors, no warnings). Nothing here is Hammer verified or in-game verified; the map itself has not been compiled.

CS2 tools mode was closed throughout (the only `cs2.exe` running was the dedicated server from `C:\cs2server`). Every compile ran with
`C:\source1\cs2port` as the working folder. Logs of each run are kept in `out/logs/` (the build script overwrites
`C:\source1\cs2port\logs\mg_monsoon_assets.log` on every run).

## Commands and times

| # | What | Command | Time | Result |
|---|---|---|---|---|
| 1 | Deploy dry run | `python -I tools/deploy_monsoon.py` | seconds | 3114 files to create (1242 MB) + 3 written, 0 replaced; content and game addon folders do not exist yet |
| 2 | Deploy | `watchdog ... -- python -I -u tools/deploy_monsoon.py --apply` | about 1 min | 3114 created, 0 replaced; 3 written (sound events, `addoninfo.txt`, Steam description); `out/deploy/mg_monsoon_deploy_20261112_112209.json` |
| 3 | Asset dry run | `build_maps.ps1 -DryRun assets mg_monsoon` | seconds | up to 571 assets |
| 4 | Asset compile, run 1 | `watchdog --label "mg_monsoon assets" --expect 1800 ... -- powershell ... build_maps.ps1 assets mg_monsoon` | **9 min 19 s** (11:24:22-11:33:41); materials 431 s, models 97 s | wrapper "assets OK", but 5 models failed (below); log `out/logs/mg_monsoon_assets_run1.log` |
| 5 | Fixes, redeploys (5 + 3 + 8 files) | see "Fixed" | | |
| 6 | Asset compile, runs 2-4 | same line | 46 s, 31 s, 31 s | run 4: 0 errors, 0 warnings; `out/logs/mg_monsoon_assets_run4.log` |
| 7 | Forced HUD / script / icon | `resourcecompiler -f -i` on `mg_monsoon.xml`, `.css`, `maps/scripts/mg_monsoon.js`, `map_icon_mg_monsoon.svg` | about 20 s | each `OK: N compiled, 0 failed` (css pulls in 306 images); `out/logs/mg_monsoon_force_compile.log` |

The BUILD.md estimate for the first asset compile (20-40 min) was far too high: 9 min on this PC (332 materials, 193 models).

What is compiled in `game\csgo_addons\mg_monsoon` now: 335 `.vmat_c`, 193 `.vmdl_c`, `mg_monsoon.vxml_c`, `.vcss_c`, `.vjs_c`,
`soundevents_addon.vsndevts_c`, 41 sounds, 302 HUD pictures, 3 loading slides (`mg_monsoon_png`, `_1_png`, `_2_png`), the radar
(`overheadmaps/mg_monsoon_radar_psd.vtex_c`), the map icon (`.vsvg_c`). The four player models compiled with their `csgo_character`
materials with no message.

## Errors and warnings, before and after

| Class | Run 1 | Run 4 | Example | Cause | Status |
|---|---|---|---|---|---|
| Model fails: missing material | 5 models failed (60 `RESOURCE COMPILE ERROR` lines, each also a `content_consider_missing_materials_fatal` note) | 0 | `sandbag_wall_lod0 referencing missing material materials/models/mv/stock/hessian_c.vmat` | the sandbag props (`sandbag_wall`, `_b`, `_128`, `sandbag_low`, `_128`) use the stock hessian materials, which `stock.export_custom` writes, and nothing ever called it | **fixed** |
| `LODGroupList : Only a single LOD group specified, ignoring` | 3 warnings | 0 | `models/mv/ext/rs_bamboo_wall`, `rs_grass_set`, `rs_jungle_bush` | `lod_decimate.vmdl_rewrite` wrote a one-group list when no LOD was worth keeping | **fixed** |
| `FATAL ERROR: ...game\csgo\shaders_pc.vpk Failed to load file (invalid)!` | 1 (the `panorama\*.vtex` pass died before its summary; the radar was not compiled) | 0 | `overheadmaps/mg_monsoon_radar_psd.vtex` | not ours: the compiler failed to open Valve's shader pack once. The same file compiled on run 2 with no change | **gone on rerun**; if it comes back, check the install (Steam "verify") |
| Wrapper exit status | "assets OK" with 5 failed models | "assets OK" | | `build_maps.ps1` only treats uncompiled **materials** as fatal; a failed model is only in the log | documented: read the log, not the wrapper |
| HUD pictures not compiled | 2 | 2 | `board_t.png`, `board_ct.png` | written by `render_board.py`, referenced by nothing (docs/HUD.md) | harmless, by design |
| prop_dynamic on a `static_prop_model` model (would be DELETED at map compile, BUILD.md) | 5 models (checked against the vmap, not a compiler message) | 1 | `quad50_gun`, `rocket_122`, `rocket_rail`, `rocket_tripod`, `shell_105` | `build_prop` always wrote `static_prop_model` | 4 **fixed**; `shell_105` remains (below) |
| Texture size / alpha / power-of-two, bad vmdl keys, physics hulls, sound, script compile | 0 | 0 | | | none seen |

`Leaked KeyValues blocks: 605` after each pass is the compiler's own shutdown note, not about our files.

## Fixed (generators changed, assets rebuilt, redeployed, recompiled)

- `tools/stock.py`: new `ensure(outdir, vmats)` writes the missing stock copies (`export_custom(only=...)` / `export_bark`);
  `tools/build_prop.py` calls it for every prop that uses a stock material. Wrote `materials/models/mv/stock/hessian{,_b,_c}.vmat`
  + `default_cloth001_{color,normal}.png` (decoded from the game's `pbr_defaults` cloth). The sandbag vmdls did not change.
- `tools/vtexread.py`: with no `CS2_VPK_DIR` it now reads the install's `game\csgo\pak01_dir.vpk` (the old default was a
  cloud-workspace path, so the exporters could not run on the PC).
- `tools/lod_decimate.py`: no `LODGroupList` when only one mesh is kept. The three affected vmdls had the block removed in `out/addon`
  (the same text the fixed tool writes) rather than re-running the conversions.
- `tools/build_prop.py` + spec key `dynamic`: `model_archetype ""`, `primary_associated_entity "prop_dynamic"`. Set on
  `quad50_gun` (`p_guns.py`) and `rocket_122`, `rocket_rail`, `rocket_tripod` (`p_arty.py`), which the vmap places only as
  `prop_dynamic`; those four props were rebuilt (`build_all_props.py quad50_gun rocket_122 rocket_rail rocket_tripod`, 46 s).

## Remains

- **`shell_105` is used both ways**: 2 `prop_static` (dressing) and 13 `prop_dynamic` (`mv_shell_1` ..., the script's shells). One vmdl cannot
  have both archetypes. Fix for the owner of `mv_entities.py` / `mv_places.py`: a `shell_105_dyn` twin like
  `mv_models.ensure_dyn()` does for the crash hulk, and the prop_dynamic entities pointed at it. Until then, look for `DELETED` next to
  the shell entities in the map build log.
- Not yet known whether a `prop_dynamic` on a `static_prop_model` is really dropped by this compiler version; BUILD.md says so and the
  fix follows it. The map compile (step 11) will tell.
- `create/libsync.py check` lists `build_prop.py`, `stock.py`, `lod_decimate.py` and `vtexread.py` in this project as differing from
  their `create/` masters: pull the changes into `create/` (and push) before committing.
- The map (`maps/mg_monsoon.vmap`, `mg_monsoon_3dskybox.vmap`) was deployed as generated at 11:22; the polish pass will change it.
  Deploy again before the map compile.

## Stage 2: map (12 Nov 2026, 13:19-17:00)

Level reached: the map and its 3D skybox map are **compiled** (resourcecompiler `OK ... 0 failed`, vpks in
`game\csgo_addons\mg_monsoon\maps\`). Not Hammer verified, not in-game verified. CS2 was not running during any of it (no `cs2.exe`
at all). Every compile ran from `C:\source1\cs2port` under the watchdog; logs kept in `out/logs/`
(`mg_monsoon_build_run1_hung.log`, `_run2_hung_charting.log`, `_run3_ok.log`, `mg_monsoon_3dskybox_build.log`,
`bake_test_lm256.log`, `make_map_s2*.log`, `check_*_s2*.log`).

Stage 1's open points: `shell_105_dyn` (polish pass 2) compiled clean and the map build reports **no `DELETED` entity at all**, so
the 13 `mv_shell_*` props survive. Whether a `prop_dynamic` on a `static_prop_model` would really be dropped is still untested
(nothing in the map does that any more).

### Commands and times

| # | What | Command | Time | Result |
|---|---|---|---|---|
| 1 | Deploy | `python -I tools/deploy_monsoon.py` (dry run), then `--apply` | seconds | 10 created (`shell_105_dyn` vmdl/smd/vmat/png), 1 replaced (`mg_monsoon.vmap`); `out/deploy/mg_monsoon_deploy_20261112_131926.json`. The temple props of pass 2 were already in the addon and compiled in stage 1 |
| 2 | Assets | `watchdog ... -- powershell ... build_maps.ps1 assets mg_monsoon` | under 1 min | materials 4 compiled / 335 skipped, models 1 / 193, 0 failed, no warnings (`out/logs/mg_monsoon_assets_s2.log`) |
| 3 | Map, run 1 | `watchdog --label "mg_monsoon final" --expect 3600 --stall 900 --max 10800 ... -- powershell ... build_maps.ps1 final mg_monsoon` | stopped after 46 min | **hung in the map load**, see "Fault 1" |
| 4 | Find it | test `.vmap` files with a subset of world meshes, `resourcecompiler -world` with its own `-outroot`, 4 at a time | 23 min | the tunnel mesh alone hangs; every other subset loads in 6 s |
| 5 | Fix 1, regenerate, check, deploy | `make_map.py ../out/template.vmap ../out/addon/maps/mg_monsoon.vmap ../out/addon` (watchdog); check_mesh, check_world, check_play, `build_script.mjs` + `mock.mjs 32 300`; deploy | 13.7 min + 3 min | all clean; deploy `..._142545.json` |
| 6 | Map, run 2 | same line | stopped after 34 min | vis fine (20.5 min), then **stalled in lightmap charting**, see "Fault 2" |
| 7 | Find it | bake tests `-world -bakelighting` on subsets, one at a time | 15 min | world meshes chart in 0.21 s without the `toolslightmapres` shell, never finish with it |
| 8 | Fix 2, regenerate, check, deploy | as row 5 | 9.8 min + 3 min | all clean; vmap 72.4 -> 57.0 MB; deploy `..._152208.json` |
| 9 | Full bake test | test copy of the map, `-world -bakelighting -lightmapMaxResolution 2048 -lightmapVRadQuality 2 -phys` | 15.5 min | `OK`, no out-of-memory (before spending an hour on the real build) |
| 10 | Map, run 3 | same line as row 3 | **65.8 min** (15:25-16:31) | `OK in 65.8 min - mg_monsoon.vpk moved to game\csgo_addons\mg_monsoon\maps`, compiler `OK: 347 compiled, 0 failed` |
| 11 | 3D skybox map | `watchdog --label "mg_monsoon_3dskybox final" --expect 900 ... -- powershell ... build_maps.ps1 final "mg_monsoon mg_monsoon_3dskybox"` | **15.1 min** (16:33-16:49) | `OK in 15.1 min - mg_monsoon_3dskybox.vpk moved`, `OK: 576 compiled, 0 failed`; vis 0.04 s; 3,962 unique meshes charted in 3 s, 1,252,624 charts at 2048 x 2048, lightmapping 642 s; **16,153,860 triangles** in render clusters; vpk 419,778,244 bytes |

The skybox map is **not** built by the main map's compile (BUILD.md said it was): the main vpk holds no skybox world and the log
never names it; mg_trenchwarfare has its own `mg_trenchwarfare_3dskybox.vpk` too. From the command line the addon and map must be
one quoted argument, or `build_maps.ps1` takes the map name for a second addon.

### Fault 1: the map load never finished (tunnel mesh with pinch vertices)

Run 1's log stopped at `Forced dmxconvert - Finished [...mg_monsoon.vmap] in 0.69 secs`; one core at 100 % in one 0x200-byte
loop of `resourcecompiler.dll` (instruction pointer sampled), memory flat at 2 GB, no disk I/O, for 46 minutes. Sibling maps reach
"Settling physics objects" in seconds. Entities alone loaded in 20 s, the 1,052 world meshes alone hung; halving them pinned it on
**one mesh: the tunnel** (`mv_places.tunnels()`, 2,237 faces, nodeID 941). It was the only mesh in the map with non-manifold
vertices: 6 corners where two open cells (or roof holes) meet only diagonally. `vmesh.polymesh_open` gave each such vertex's two
boundary half-edges the same `next` (its `out_b` table keeps one outgoing boundary edge per vertex), so `edgeNextIndices` was not a
permutation, and circling that vertex never returns. `check_mesh.py` passed it: its checks never test that `next` is a permutation.

Fix: `tools/vmesh.py` `split_pinches()` (called by `polymesh_open`) gives each face fan around a vertex its own vertex (same
position; the tunnel gets 6 copies); `tools/check_mesh.py` now fails `next-not-permutation` and `pinch vertex`. The old vmap fails
the new check (`out/mg_monsoon_pre_pinchfix.vmap`), the new one passes; three hand cases (diagonal pair, L of three, full grid)
pass after the split and the unsplit diagonal pair fails.

### Fault 2: lightmap charting crawled (lightmap shell of 47,912 faces)

Run 2 passed the load and vis, then sat in `Charting N unique meshes` (the line never got its "Done") for 10+ minutes on one core
in another tight `resourcecompiler.dll` loop, memory flat at 5.3 GB. Bake tests: entities alone chart in 2 s; the world meshes chart
in 0.21 s **without** the `toolslightmapres` shell and never finish with it (one quarter of them took 136 s). The shell
(`mv_terrain.build_lmres`, 64-u cells over the walkable band) was one closed mesh of 47,912 faces; mg_trenchwarfare's is 15,422.

Fix: `build_lmres` now uses 256-u cells, sampling the ground every 32 u for each cell's height range: 1,465 cells, **3,170 faces**.
World meshes then chart in 13.7 s, and the whole map in 120 s. `check_mesh.py` fails a `toolslightmapres` mesh over 8,000 faces.
Only 2 % of triangles end up more than 240 u from the shell (log line), the same idea as before. The vmap shrank from 72.4 to 57.0 MB.

### Stats of the compiled map (run 3)

| | |
|---|---|
| Time | 65.8 min, 10 threads: vis 1,165 s, lighting 14 min 30 s, nav + CSGO AI data about 28 min ("Compute Approach areas" 1,569 s on one core), Steam Audio + bomb damage about 3 min |
| Vis | 4 Low hints; 802,137 voxel nodes; 121,116 regions; 152,878 clusters generated, merged to 36,687, then to the 4,096 cap (merge 480 s); 4,091 clusters see the sky; vis resource 2.81 MB |
| Lightmap | 2048 x 2048, VRAD quality 2; charting 1,830 unique meshes in 120 s; **270,837 UV charts** (mg_trenchwarfare 1.37 M); packer scale 0.084; lightmapping 602 s on the GPU (Arc B580, 2.2 of 11.9 GB); welding seams 16 s, no out-of-memory; 26,017 fireflies removed |
| Nav | 513,472 source triangles; 42,052 polys before island removal, **33,661 nav areas** after; nav file 8.79 MB; bomb damage bake sampled 2.38 M points (sites A and B) |
| Render | 189 aggregates, 17,773 fragments, 206 MB vertex data; **elephant grass (`rs_elephant_grass`) is 1,412 unique fragments and 109 MB of it** |
| Output | `maps/mg_monsoon.vpk` 182,976,678 bytes, 16:31; 349 files (331 `vmdl_c` aggregates, world, vis, nav, lightmaps) |

### Errors and warnings, before and after

| Class | Run 1 | Run 2 | Run 3 | Example | Status |
|---|---|---|---|---|---|
| Compile never ends in the map load | 1 | 0 | 0 | log stops at `Forced dmxconvert` | **fixed** (Fault 1) |
| Compile never ends in lightmap charting | - | 1 | 0 | `Charting N unique meshes` without "Done" | **fixed** (Fault 2) |
| `DELETED` props / entities | - | - | 0 | | none |
| Missing or failed model / material of ours | - | - | 0 | | none |
| Entities dropped by short vector keys | - | - | 0 | | offline scan of both vmaps: no numeric key with fewer than 3 numbers where 3 are expected |
| Out of memory, packer asking for more | - | - | 0 | | none |
| `Failed loading resource "materials/models/props/hr_massive/liquids/survival_river_0{2,4}_..._tga_....vtex_c"` + 14 `Falling back to error texture` + 2 `returning error texture` | - | 3 + 14 | 3 + 16 | | harmless: Valve's compiled `materials/de_nuke/hr_nuke/hr_river_water_001.vmat_c` (our river) names `_tga_` textures the pak does not ship (it has the `_psd_` ones). Only the baker's albedo for the water falls back; the water meshes are not lightmapped |
| `Failed loading resource "scripts/detail_prop_types.vdata_c"` | 1 | 1 | 1 | | harmless, every CS2 build (cs2-gotchas.md) |
| `TestBoxHullForClipDir - polyBack is empty` | - | - | 1 | nav generation | harmless: nav finished with 33,661 areas |
| `Found 8731/419473 triangles outside of vis, 1699/419473 with too many overlaps` | - | - | 1 | | information: these go into 3 vis-less render clusters |
| `58306 / 2606990 (02%) of triangles are at least 240 units away from lightmap resolution volumes` | - | - | 1 | | expected: geometry outside the walkable band (karst tops, far slopes) gets the default texel density |
| `Couldn't load public key ... will not sign`, `Not signing; keys not set` | - | - | 1 | | normal for a local build |
| `Steam Audio: Bake set to cleanup` | - | - | 2 | | normal |
| `Leaked KeyValues blocks: 605` | - | - | 1 | | the compiler's own shutdown note |
| Skybox map: `WARNING! No lightmap resolution volumes set for this geometry!` | | | 1 | | harmless for a skybox map (seen only from far away) |

### Compiled outputs, checked after run 3

`game\csgo_addons\mg_monsoon\`: `maps/mg_monsoon.vpk` 182,976,678 bytes (16:31), `maps/mg_monsoon_3dskybox.vpk` 419,778,244 bytes (16:48);
`maps/scripts/mg_monsoon.vjs_c` 250,871 bytes, `panorama/layout/custom_game/mg_monsoon.vxml_c`, `panorama/styles/custom_game/mg_monsoon.vcss_c`,
`soundevents/soundevents_addon.vsndevts_c`, the radar `.vtex_c` and the map icon `.vsvg_c` all from 11:33-11:37 (stage 1). Their
sources have not changed since 11:22-11:23 (the deploys of stage 2 found them identical; `mg_monsoon.js` in `out/addon` and in the
addon have the same sha256), so they are current.

### Remains

- **Nav area count 33,661** is near mg_trenchwarfare's 44,160, which cost FPS with bots (tw35), and makes "Compute Approach areas"
  take 26 min. The NONAV boxes removed only about 4,000 polys. Watch FPS with bots at the first launch; if it drops, more
  `func_nav_markup` NONAV over the karst slopes, paddies and jungle bots never use.
- **The 3D skybox is heavier than the map**: 16.2 M triangles in 3,962 meshes (2,212 props, palms and the like among them), a 420 MB
  vpk against the map's 183 MB, and 1.25 M lightmap charts. It is drawn all the time; at the first launch check FPS and VRAM with
  `r_draw3dskybox 0` against 1 (if that command exists in this build), and if it costs, thin or simplify the skybox props in
  `make_sky.py` / `make_skybox.py` (cheaper models, no lightmap: `bakelighting 0`).
- **Elephant grass** is 109 MB of the map's 206 MB of aggregate vertex data (1,412 unique, not instanced, fragments). Worth a look at
  the first launch (VRAM, FPS); an LOD or fewer instances in `mv_places.py` would cut it.
- `vmesh.py` and `check_mesh.py` are libsync copies of `create/`: `create/libsync.py check` now lists exactly these two as DIFFERS
  (stage 1's four tools are no longer listed). Pull the fixes into `create/` (and push to mg_trenchwarfare) before committing.
- The PC copy of `build_maps.ps1` (`C:\source1\cs2port`) differs from `scripts/build_maps.ps1` in the repo: it bakes plain `full`
  builds at 2048 instead of 1024. Not touched; reconcile one way or the other.
- Not launched: step 12 (BUILD.md "Local test with bots") is the next step, for skink52.

## Stage 3: nav cut, world pass 3, recompile (12 Nov 2026, 16:50-20:15)

Level reached: the map is **compiled** again (resourcecompiler `OK: 501 compiled, 0 failed`, vpk in `game\csgo_addons\mg_monsoon\maps\`).
Not Hammer verified, not in-game verified. No `cs2.exe` ran at any point (checked before the deploy and before the compile). The
3D skybox map was not rebuilt: nothing that feeds it (`layout.ground_low`, the sky, far terrain) changed. What changed in the world
and why: [REVIEW_WORLD_1.md](REVIEW_WORLD_1.md) "Pass 3".

### Commands and times
| # | What | Command | Time | Result |
|---|---|---|---|---|
| 1 | Map, 6 builds | `watchdog ... -- python -u make_map.py ../out/template.vmap ../out/addon/maps/mg_monsoon.vmap ../out/addon` (logs `out/logs/p3_map1..6.log`) | 9.5-18 min each (the slow ones ran beside mg_trenchwarfare's compile) | build 6: 7,674 entities, 258 `func_nav_markup` (15 seeds, 243 NONAV) |
| 2 | Offline checks on build 6 | `check_mesh.py`, `check_world.py`, `check_play.py` on the vmap; `make_radar.py ../out/addon ../out/game`, `render_board.py ../out/addon`; project folder: `node tools/build_script.mjs && node test/mock.mjs 32 300` | 1.5 min, 1 min, 1.5 min, 4 min, 2 min | 0 bad / clean / clean (9) / done / mock PASS (script mv-0.5, commit 07a5d7b, 3,597 lines) |
| 3 | Deploy | `python -I tools/deploy_monsoon.py` (dry run), then `--apply` | seconds | 2 replaced (`mg_monsoon.vmap`, `mg_monsoon.js`), 3,125 unchanged; `out/deploy/mg_monsoon_deploy_20261112_191225.json` |
| 4 | Map | from `C:\source1\cs2port`: `watchdog --label "mg_monsoon map" --expect 3600 --heartbeat 300 --stall 900 --max 10800 --log logs\mg_monsoon_p3_watch.log --watch logs\mg_monsoon_build.log -- powershell ... build_maps.ps1 final mg_monsoon` | 16 min queued behind mg_trenchwarfare's compile, then **41.5 min** (19:28-20:09) | `OK in 41.5 min - mg_monsoon.vpk moved`; logs kept as `out/logs/mg_monsoon_build_p3.log`, `mg_monsoon_p3_watch.log` |
| 5 | Script | `resourcecompiler -f -i ...\maps\scripts\mg_monsoon.js` | 3 s | `OK: 1 compiled`, `mg_monsoon.vjs_c` 268,417 bytes (mv-0.5); a second dry run finds nothing left to deploy |

`build_maps.ps1` printed "Another resourcecompiler is still running - waiting" every few seconds while it queued, so the watchdog saw
log activity and did not count the wait as a stall.

### Before / after
| | Stage 2 (run 3) | Stage 3 |
|---|---|---|
| Whole compile | 65.8 min | **41.5 min** |
| Nav polys: Recast / after NONAV / merged / before island removal | 65,461 / 61,438 / 43,528 / 42,052 | 43,638 / 31,386 / 20,882 / 20,163 |
| **Nav areas** (`Nav mesh (v36/1) loaded with N nav areas`) | **33,661** | **15,033** |
| CSGO: early occupy / hiding / encounter / **approach areas** | 31 s / 20 s / 63 s / **1,569 s** | 14 s / 7 s / 22 s / **348 s** |
| Vis | 152,878 clusters merged to 4,096 | 152,931 merged to 4,096 |
| Lightmap | 1,830 meshes charted in 120 s, 270,837 charts, lightmapping 602 s | 1,893 meshes in 118 s, 290,597 charts, lightmapping 608 s, no out-of-memory |
| Bomb damage bake | - | 53 s |
| vpk | 182,976,678 bytes | 176,247,792 bytes |
| `DELETED` props / entities | 0 | 0 (the two `DELETED`-like lines are Steam Audio's "baked data file will be deleted") |
| Missing models / materials of ours | 0 | 0 (only the known `survival_river_0{2,4}_..._tga_...` water textures and `detail_prop_types.vdata_c`, harmless, see Stage 2) |
| Other lines | | `TestBoxHullForClipDir - polyBack is empty` (nav, harmless as before); 8,307 / 423,478 triangles outside vis; 2 % of triangles 240+ u from lightmap volumes |

The offline estimate before the compile said ~10,260 areas (the flood fell from 378,891 to 115,469 cells, x 0.30, applied to
33,661). The compile made 15,033 (x 0.45): the ground bots keep (bases, the village, props, roads) is cut into smaller areas than
the open valley sides that were taken out. `check_play.py` check 9 is recalibrated on this compile (0.130 areas per 16-u cell).

### Remains
- **Nav at 15,033**: the target was well under 15,000. Approach areas fell from 26 to 6 min; FPS with bots is to be seen at the first
  launch (mg_trenchwarfare lost FPS at 44k). Next cut, measured with `check_play.py --nav-plan` before regenerating: smaller flag and
  road margins in `mv_entities.NAV_ZONES` / `NAV_MARGIN`, or fewer nav pieces inside the bases.
- C-E route balance 1.11 (REVIEW_WORLD_1 "Pass 3", Left).
- The 3D skybox and the elephant grass VRAM points of Stage 2 are unchanged.
- Not launched: BUILD.md step 12 is the next step, for skink52.

## Stage 4: world pass 4, recompile (12 Nov 2026, compile 21:40-22:22)

Level reached: the map is **compiled** again (resourcecompiler `OK: 506 compiled, 0 failed, 0 skipped, 41m:59s`, vpk in
`game\csgo_addons\mg_monsoon\maps\`). Not Hammer verified, not in-game verified. No `cs2.exe` ran (checked before the deploy and the
compile); the skybox agent's skybox compile had finished before this one started, and the 3D skybox map was not touched here (the deploy
dry run did not list it). What changed in the world and why: [REVIEW_WORLD_1.md](REVIEW_WORLD_1.md) "Pass 4".

### Commands and times
| # | What | Command | Time | Result |
|---|---|---|---|---|
| 1 | Map, 5 builds | `watchdog ... -- python -u make_map.py ../out/template.vmap ../out/addon/maps/mg_monsoon.vmap ../out/addon` (logs `out/logs/p4_map1..5.log`) | 9-10 min each (540-615 s) | build 5: 7,663 entities, 1,377 meshes, 267 `func_nav_markup` (15 seeds, 250 NONAV) |
| 2 | Offline checks on build 5 | `check_mesh.py`, `check_world.py`, `check_play.py`; `make_radar.py ../out/addon ../out/game`, `render_board.py ../out/addon`, `mv_hud.py ../out/addon`; project folder: `node tools/build_script.mjs`, `node test/mock.mjs 32 300` | about 6 min in all | 0 bad / clean / clean (9) / done / HUD 0 problems / mock PASS (mv-0.5, 3,597 lines) |
| 3 | Deploy | `python -I tools/deploy_monsoon.py --list` (dry run), then `--apply` | seconds | 9 replaced (`mg_monsoon.vmap`, backed up as `mg_monsoon.vmap.bak_20261112_213946`; README / TESTING / CREDITS / LICENSE in both addon roots, the committed release docs), 3,118 unchanged, skybox vmap not listed; `out/deploy/mg_monsoon_deploy_20261112_213946.json` |
| 4 | Map | from `C:\source1\cs2port`: `watchdog --label "mg_monsoon map p4" --expect 2500 --heartbeat 300 --stall 900 --max 7500 --log logs\mg_monsoon_p4_watch.log --watch logs\mg_monsoon_build.log -- powershell ... build_maps.ps1 final mg_monsoon` | **42.0 min** (21:40-22:22) | `OK in 42 min - mg_monsoon.vpk moved`; logs kept as `out/logs/mg_monsoon_build_p4.log`, `mg_monsoon_p4_watch.log` |

The script (`mg_monsoon.js`) was unchanged by this pass (the deploy found it identical), so it was not recompiled.

### Before / after
| | Stage 3 | Stage 4 |
|---|---|---|
| Whole compile | 41.5 min | 42.0 min |
| Nav polys: Recast / after NONAV / merged / before island removal | 43,638 / 31,386 / 20,882 / 20,163 | 40,191 / 27,485 / 18,149 / 17,576 |
| **Nav areas** (`Nav mesh (v36/1) loaded with N nav areas`) | **15,033** | **12,597** |
| CSGO: early occupy / hiding / encounter / **approach areas** | 14 s / 7 s / 22 s / **348 s** | 11 s / 6 s / 17 s / **454 s** |
| nav file | | 2,928,009 bytes |
| Vis | 152,931 clusters merged to 4,096 | 152,931 clusters generated, merged to the 4,096 cap |
| Lightmap | 1,893 meshes charted in 118 s, 290,597 charts | 1,883 meshes in 118 s, 291,230 charts, no out-of-memory |
| Bomb damage bake | 53 s | 569,670 nav points sampled |
| vpk | 176,247,792 bytes | 170,748,319 bytes |
| `DELETED` props / entities | 0 | 0 (the only "deleted" lines are Steam Audio's "baked data file will be deleted") |
| Missing models / materials of ours | 0 | 0 (only the known `survival_river_0{2,4}_..._tga_...` water textures, 16 error-texture fallbacks for them, and `detail_prop_types.vdata_c`, harmless, see Stage 2) |

The nav estimate before the compile said ~11,823 (pass 3 calibration); the compile made 12,597 (the cut rims were open ground, cut into
larger areas than the average kept cell). `check_play.py` is recalibrated on this compile (90,815 cells = 12,597 areas, 0.139 per
cell). "Compute Approach areas" took **longer** than in stage 3 (454 s against 348 s) with 16 % fewer areas: its cost is not
proportional to the area count here (the areas taken out were large open ones; what is left is the dense base, village and road nav).
Whole compile time is unchanged.

### Remains
- Approach areas 454 s: the next lever, if it matters, is fewer small areas inside the bases (the firebase and camp clutter cut the nav
  into small pieces), not the outer rims.
- FPS with bots at 12,597 areas is to be seen at the first launch (mg_trenchwarfare lost FPS at 44k, runs 4,376).
- Not launched: BUILD.md step 12 is the next step, for skink52.

## Stage 5 (playtest 1 build): batches S, W, G, P integrated, recompiled (13 Nov 2026, 02:30-06:18)

Level reached: the map is **compiled** (resourcecompiler `OK: 1024 compiled, 0 failed, 0 skipped, 53m:06s`, `mg_monsoon OK 53.1 min`,
vpk in `game\csgo_addons\mg_monsoon\maps\`), and every asset this build changed is compiled. Not Hammer verified, not in-game verified.
No `cs2.exe` or Hammer ran (checked before both deploys and before every compile). The 3D skybox was not recompiled: `make_sky.py`,
`make_skybox.py` and toolkit.json `skybox` are unchanged, and the only layout function it reads, `ground_low` (= `base_terrain`), was not
touched by batch W (the river carve is in `carved()`). Batches S, G and P had compiled their own assets; this stage built, deployed and
compiled batch W's map and assets, and the shared-code rebuild of W's props. Fix records: FIX_PT1_S/W/G/P.md; what to test: TESTING_MONSOON.md
"Playtest 2 checklist".

### Commands and times
| # | What | Command | Time | Result |
|---|---|---|---|---|
| 1 | Shared tools | from `cs2mapping`: port batch S's inward-normals fix (`orient_normals`, `smooth_normals`, `fix_normals`, `normals` subcommand) into `create/gmod_assets.py`; `python create/libsync.py ack create/gmod_assets.py`; `check` | minutes | `libsync: all in step` (checked again at the end, after `ack create/check_play.py` for this stage's monsoon-only nav calibration) |
| 2 | W's props with P's UV / atlas code | `watchdog ... -- python -u build_all_props.py <16 p_jungle props> <8 sandbag walls>` (vine_curtain left out: no longer placed); `python p_jungle.py`, then at once `python mv_flag_anim.py ../out/addon`; `lod_decimate.py` on the 8 walls; `prop_lint.py` | 6.5 min + seconds | 24 built, 0 failed; `flag_pole.vmdl` lists `flag_00..flag_20` (21), archetype `animated_model`; prop_lint **134 props, 0 bad** (after the two fixes below) |
| 3 | Map, 5 builds | `watchdog ... -- python -u make_map.py ../out/template.vmap ../out/addon/maps/mg_monsoon.vmap ../out/addon` (logs `out/logs/pt1_map5..9.log`) | 601-929 s each | build 9 (final): 7,620 entities, 1,843 meshes (477 water prisms), 6,774 prop_static, 259 `func_nav_markup` (244 NONAV), 67-69 MB |
| 4 | Offline checks on build 9 | `check_mesh.py`, `check_world.py`, `check_play.py`; `make_radar.py ../out/addon ../out/game`, `render_board.py`, `mv_hud.py`; project folder: `node tools/build_script.mjs`, `node test/mock.mjs 32 300`, `12 240 scenario=pt1 humans=4`, `14 300 scenario=weapons humans=6`; `api.py --strict --check` | about 10 min | 1,862 meshes 0 bad / clean (8) / clean (10) / done / HUD gate 0 problems / mv-0.7, 4,112 lines / PASS / PASS / PASS / 0 problems |
| 5 | Deploy 1 | `python -I tools/deploy_monsoon.py --list`, then `--apply` | seconds | 70 created, 92 replaced, 3,171 unchanged (177 MB); vmap backed up as `mg_monsoon.vmap.bak_20261113_034503` (the stage 4 map); `out/deploy/mg_monsoon_deploy_20261113_034503.json` |
| 6 | Assets | scratchpad script, one `resourcecompiler -f [-r] -i <file> -nop4` at a time from `C:\source1\cs2port`, waiting for any other resourcecompiler (log `C:\source1\cs2port\logs\pt1_build_assets.log`) | 5 min (03:46-03:51) | 45 jobs, each `OK ... 0 failed`, no error or warning line: 16 material folders (rebuilt jungle props, vine_drape), 25 vmdls (8 walls, vine_drape, 15 jungle props, flag_pole), `postprocess_filmic_underwater.vpost`, the radar `.vtex`, HUD css (308 compiled, with the board and loading-slide PNGs) and xml. The script was byte-identical to batch G's deploy: not recompiled |
| 7 | Map, run 1 | from `C:\source1\cs2port`: `watchdog --label "mg_monsoon final pt1" --expect 3000 --heartbeat 300 --stall 900 --max 9000 --log logs\mg_monsoon_pt1_watch.log --watch logs\mg_monsoon_build.log -- powershell ... build_maps.ps1 final mg_monsoon` | 56.8 min (03:52-04:48) | `OK: 547 compiled, 0 failed`, but 4 `func_water`s without a physics hull (below); log kept as `out/logs/mg_monsoon_build_pt1_run1.log` |
| 8 | Water fix, test compiles, regenerate, checks, deploy 2 | three world + phys test maps (below); `mv_terrain.water_volume(pieces=True)`; steps 3-4 again; deploy | 1 h | deploy 2: 3 replaced (the vmap, TESTING_MONSOON.md in both roots), backup `mg_monsoon.vmap.bak_20261113_052359`; `out/deploy/mg_monsoon_deploy_20261113_052359.json` |
| 9 | Map, run 2 | as 7 (`--expect 3500 --max 10500 --log logs\mg_monsoon_pt1b_watch.log`) | **53.1 min** (05:25-06:18) | `OK: 1024 compiled, 0 failed, 0 skipped, 53m:06s`; log kept as `out/logs/mg_monsoon_build_pt1.log`, watchdog log `out/logs/mg_monsoon_pt1_watch.log` |

### Fixed along the way
- **Sandbag walls: 838-2,255 zero-area triangles per LOD0** (prop_lint). The bag's superellipsoid poles sat at `cos(pi/2)` = 6e-17, which
  the 0.34 power spread into rings about 1e-5 u wide: their faces had a float area over build_prop's zero-area cut and collapsed when the
  SMD rounds to 1e-4. `p_sandbag_mv.bag` snaps the poles to the axis; LOD0 9,576-23,981 tris (was 10,877-27,335), LOD2-4 unchanged.
  The generic fix (measure the area on the rounded positions in `create/build_prop.write_multi_smd`) is not made: build_prop is shared
  with mg_trenchwarfare.
- **prop_lint stopped on the rigged flag pole**: `flag_pole.vmdl` names 21 animation SMDs (skeleton only). `tools/prop_lint.py` skips an
  SMD with a skeleton and no triangles.
- **Flag A cover 14 -> 12 head-height pieces** (check_play 3 wants 14): batch P's rice-straw stack (100 u across, was 92) no longer fitted on
  the threshing floor (1 of 4) and its ox cart (190 u long, was 164) found no spot in the farm yard. `mv_places.paddies`: farm cart search
  260 -> 360, island stacks at scale 0.92 (the old footprint, 96 u tall; `W.fit` now passes `scale` to its footprint pre-test). A 15 / 2.
  Two attempts that did not help: a wider search, and letting the stacks onto the island's shoulder (too steep for `fit`).
- **The river, upper reach, marsh and oxbow had no water physics.** Run 1 logged, for exactly these four `func_water`s (nodes 807-813;
  find the entity behind `unnamed_<id>` by its node id with `vmapedit.Map`):
  `ExtrudeReplaceHull failed to build new convex hull with extrusion 0.007812` / `Encountered issues while adding mesh from node 808 to
  entity model maps/mg_monsoon/entities/unnamed_807.vmdl` / `Warning: Failed to create physics hulls for one or more meshes.` Their PHYS
  blocks were 2.0-4.2 KB against 4.7 KB for one small paddy box: no volume to swim in. Test maps (template + water only, `resourcecompiler
  -world -phys`, 8-12 s each, written to the scratchpad and removed): failed: the marsh as built (512 grid), the same footprint as one box at
  170 u and at 13 u deep, a single 512 box, three 512 boxes in one entity, a 96 x 1200 box, the marsh footprint on a 256 grid, a curved
  2-column strip; passed: 256 and 384 boxes, a 96 x 600 box, a 512 box on a 256 grid, the paddy control, the curved strip and the marsh as
  **one prism per top face**. `mv_terrain.water_volume(pieces=True)` (strips and rect sheets; marsh grid 512 -> 256; a non-convex quad split in
  two): the map's real water then test-compiled with 0 hull issues, and in run 2 none either; the river's PHYS is 506 KB, the upper reach,
  marsh and oxbow 107 / 47 / 19 KB. The paddies (small boxes) passed as they were. cs2-gotchas.md has the rule.

### Before / after
| | Stage 4 | Stage 5 (run 2) |
|---|---|---|
| Whole compile | 42.0 min | **53.1 min** (run 1: 56.8) |
| Entities / meshes / prop_static | 7,663 / 1,377 / 6,841 | 7,620 / 1,843 (477 water prisms) / 6,774 |
| Vis | 152,931 clusters merged to 4,096 | 157,476 clusters (36,481 after the first merges) merged to 4,096; vis 1,065 s |
| Lightmap | 1,883 meshes charted in 118 s, 291,230 charts | **2,585 meshes** in 94 s, **390,604 charts** into 2048 x 2048, lightmapping 672 s on the GPU (2.5 of 11.9 GB), seams welded in 15 s, no out-of-memory |
| Nav polys: Recast / after NONAV / merged | 40,191 / 27,485 / 18,149 | 40,841 / 28,546 / 19,273 |
| **Nav areas** (`Nav mesh (v36/1) loaded with N nav areas`) | **12,597** | **13,739** (run 1: 13,733); check_play estimated ~12,645 |
| CSGO: early occupy / hiding / encounter / **approach areas** | 11 s / 6 s / 17 s / **454 s** | 13 s / 7 s / 29 s / **1,044 s** (run 1: 1,248 s) |
| nav file | 2,928,009 bytes | 3,275,946 bytes |
| vpk | 170,748,319 bytes | 266,511,224 bytes (the tunnel field, 390 k lightmap charts, the new props) |
| Triangles outside vis | | 2,362 / 512,666; 1 % of 4.08 M triangles 240+ u from lightmap volumes (expected: karst tops, far slopes) |
| `DELETED` props / entities | 0 | 0 (only Steam Audio's "baked data file will be deleted") |
| Missing models / materials of ours | 0 | 0 |
| Known harmless | | `survival_river_0{2,4}_..._tga_...` (18 lines, 16 error-texture fallbacks: the baker's albedo for the stock river vmat) and `detail_prop_types.vdata_c` (1), as in Stage 2 |
| Physics hull warnings | 0 | 0 (run 1: 4, the water volumes) |
| Water | open sheets of a non-water material | 20 `func_water` volumes in `rush_water_river_01a` / `hr_aztec_water_shallow`, compiled with hulls; 482 water render nodes (`nomerge`, one per prism top; about 24 before the prisms) |
| Tunnel mesh | voxel mesh | compiled into the world aggregates (ceiling wood 40,008 tris, dirt 29,822, mud 10,158, timber 2,998); no tunnel-specific line, no T-junction or pinch error |

`check_play.py` is recalibrated on this compile (91,163 cells = 13,739 areas, 0.151 per cell): the organic tunnel floors and the bank and
ford slopes are cut into small areas. The nav rose 9 % over stage 4 and "Compute Approach areas" more than doubled (454 -> 1,044 s): the
compile is 11 min longer, nearly all of it there.

### Remains
- **Nav 13,739 areas, approach areas 17 min.** Still a third of mg_trenchwarfare's 44k; FPS with bots is to be seen in playtest 2. If it
  costs, the lever is NONAV over the deep channel and the tunnel side galleries (`mv_entities.NAV_ZONES`), measured with `check_play.py --nav-plan`.
- **482 water draw calls.** One translucent node per prism top. Same pixels as before; watch FPS looking along the river in playtest 2. If it
  costs, try one render-only top sheet per body with nodraw prisms for the physics (untested: the sheet itself would then log a hull warning).
- `create/build_prop.write_multi_smd` should drop zero-area faces measured on the rounded positions (generic form of the sandbag fix; shared
  with mg_trenchwarfare, not changed here). `tools/watervol.py` (stage D `water`) merges touching water meshes into one func_water and may
  hit the same hull limit on ported maps.
- Lightmap charts rose to 390,604 (tunnel field, new props): fits 2048 with room (trench: 1.37 M).
- Not launched: BUILD.md step 12, then TESTING_MONSOON.md "Playtest 2 checklist", for skink52.
