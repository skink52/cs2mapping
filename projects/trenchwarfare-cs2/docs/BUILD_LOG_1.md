# mg_trenchwarfare build log 1: the remaster's first deploy and compile

AI-generated (Claude) for skink52. Filled from the logs themselves (remaster step 9; how to run each line: [BUILD.md](BUILD.md)). Level reached: **compiled**,
not loaded in CS2 or played.
Copy each compile log into `out/step9/logs/` before the next run overwrites it (`C:\source1\cs2port\logs\mg_trenchwarfare_*.log`).

## Before the compile (12 Nov 2026, filled)

Run on this PC, 15:24-15:50, no `cs2.exe` running, another session's `resourcecompiler.exe` compiling mg_monsoon throughout (the deploy
notes it and does not hold for another addon). Logs: `out/step9/deploy_tw_chain_run.log`, `deploy_tw_dryrun_run2.log`, `chain/*.log`, `gate/*.log`.

**Chain** (`deploy_tw.py --chain`, no opt-in flags, about 6 min including the radar; `out/step9/chain.json`):

| Stage | Input CRC32 | Output CRC32 | Time | Guard (`patch_guard --strict`) | Same bytes as the step's own output |
|---|---|---|---|---|---|
| base check | the addon map | `2e3f90d0`, 67,206,918 B | | = recorded base | |
| 1_world_1 | 2e3f90d0 | 923f5bf5 | 14 s | PASS, 24 targets, 0 violations | yes (`out/mg_trenchwarfare_patched.vmap`) |
| 2_models | 923f5bf5 | 6da14739 | 13 s | PASS, 1 target | yes (`out/mg_trenchwarfare_models.vmap`) |
| 3_terrain | 6da14739 | 5f297445 | 82 s | PASS, 350 targets | no: every terrain mesh identical, the 19 fx entities (6 smoke, 12 rain, relay) differ in one non-keyvalue attribute; step 7's map predates the last `patch_terrain.py` edit (15:14). `out/step9/chain/terrain_vs_step7.json` |
| 4_sounds | | | | skipped: `tools/patch_sounds.py` did not exist yet | |
| 5_nav | 5f297445 | **a109a678**, 89,816,070 B | 96 s | PASS, 178 targets (89 NONAV boxes + meshes) | (new) |
| radar | final map | | 129 s + 10 s | `make_radar` exit 0, `check_radar` RESULT: clean | |

**Gate** (second run, PASS, `out/step9/gate.json`): check_world `FAILED: singletons` (the known duplicate `info_map_parameters`, M2 opt-in:
baseline); check_play the 15 baseline failures and nothing new; check_contract 83 rows, 80 OK, 3 known missing; api 0 problems; tscheck OK;
mock 32 and the bot mock `RESULT: ok`; scenarios 12 / 12.
The first gate run, 10 minutes earlier, was REFUSED. Three causes, none from the delivery:
- check_play `separation` (t, ct and the woods one world while the blockers stand). It did not reproduce: check 1 on the same map then held
  all 15 pairs three times, and a fresh scene of the nav map matched the terrain map's exactly. The likely cause is a variant scene in
  `out/review/cache/play_scene_*.pkl` (keyed by file size and mtime second). Remember this if the gate ever shows `separation` again.
- check_contract `tw_rain_tin_<tg>_1..3` missing and mock `reload` "sound counters disagree": step 8's work in progress at that moment
  (CONTRACT rows ahead of `patch_sounds.py`, sound counters in the script). Both cleared once that work landed.

**Deploy dry run** (`out/step9/deploy_dryrun.json`): 110 files in the merged list (`out/step9/deploy_files.txt`, from steps 5, 6, 7, 8),
148.0 MB to write: 80 created, 28 replaced, 2 already the same; 70.0 MB backed up first. The map replaces the base (CRC32 2e3f90d0) and
would first be copied to `backups\deploy_<stamp>\maps\`. Free on C: 110 GB. Model -> material check: 29 references, all found.

| Part | Files | MB | |
|---|---|---|---|
| `maps/mg_trenchwarfare.vmap` | 1 replace | 85.7 | the chain's final map |
| `maps/scripts/mg_trenchwarfare.js` | 1 replace | 0.1 | step 8 (the built script) |
| `materials/models/...` | 3 create | 2.8 | Canon de 75 vmat + 2 textures |
| `models/tw/...` | 30 create, 8 replace | 32.4 | `_dyn` twins + anims, Canon de 75, LODs, `tw_de_a_body.dmx` |
| `panorama/images/...` | 17 create, 14 replace, 1 same | 8.5 | HUD pictures, slides, map icon, radar |
| `panorama/layout`, `styles` | 2 replace | < 0.1 | HUD xml, css |
| `soundevents/soundevents_addon.vsndevts` | 1 replace | < 0.1 | whole file (sounds.py already merged its block) |
| `sounds/tw/*.wav` | 30 create, 1 replace | 18.5 | step 8 sounds |
| game `resource/overviews/mg_trenchwarfare.txt` | 1 same | < 0.1 | radar overview unchanged |

Old route: all zips in `cs2port\assets\tw` are in the unpack bat's applied list (the bat is inert while that list stays).

## Commands and times (12 Nov 2026)

| # | What | Command | Time | Result |
|---|---|---|---|---|
| 1 | Chain + gate + dry run | `watchdog ... -- python -u tools/deploy_tw.py --chain` | 16:13-16:21 (442 s) | all 5 stages guarded PASS (sounds stage included); gate REFUSED on a check_play `separation` false alarm |
| 1b | Gate + dry run after the check_play cache fix | `watchdog ... -- python -u tools/deploy_tw.py` | 113 s | gate PASS; 117 files, 148.1 MB |
| 2 | Deploy | `python -u tools/deploy_tw.py --apply` | 16:33, 75 s | 86 created, 29 replaced, 2 same; map backup `backups\deploy_20261112_163314\`; record `out/step9/deploy/mg_trenchwarfare_deploy_20261112_163314.json` |
| 4 | Asset compile | `watchdog --label "tw assets" ... build_maps.ps1 assets mg_trenchwarfare` | ~16:35-16:50 (waited for mg_monsoon's compile) | wrapper "assets OK"; the log agrees: every block `0 failed`, 0 `RESOURCE COMPILE ERROR`; 13 models compiled (all `_dyn` twins, gm_canon75, gun_75mm, howitzer_bl8, plane_dr1 + dyn, plane_spad7 + dyn, tank_a7v, tw_de_a); 31 sound files; log `out/step9/mg_trenchwarfare_assets.log` |
| 5 | Forced xml / css / js / svg | `resourcecompiler -f -i ...` from `C:\source1\cs2port` | ~16:51 | 1 / 30 / 1 / 1 compiled, 0 failed each |
| 6 | Map compile | `watchdog --label "tw final" ... build_maps.ps1 final mg_trenchwarfare` | ~16:52-17:41 (49.7 min) | `OK in 49.7 min - mg_trenchwarfare.vpk moved`; 407 compiled, 0 failed; log `out/step9/mg_trenchwarfare_build.log` |
| 8 | Nav pass 2 deploy + map compile 2 | `deploy_tw.py --apply` (map only) then `build_maps.ps1 final` | 18:52 deploy; compile 34.2 min | 0 compile errors, 0 entity DELETED (2 Steam Audio cache-file lines only); **nav 4,376 areas**; same 24,718 meshes / 1.40 M charts; log `out/step9/mg_trenchwarfare_build_run2.log` |
| 9 | User decisions deploy + map compile 3 | `deploy_tw.py --apply` (map + script; js forced) then `build_maps.ps1 final` | 20:22 deploy; compile 33.1 min | 0 compile errors, 0 entity DELETED, nav 4,376 areas; check_world RESULT clean; log `out/step9/mg_trenchwarfare_build_run3.log` |
| 7 | Stale models | `resourcecompiler -f -i` wire_coil, wire_fence_a, wire_fence_b, ladder | after the map | 4 compiled, 0 failed; check_world check 7 now 0 stale |

CS2 tools mode closed throughout: yes (only the dedicated server `C:\cs2server` cs2.exe ran). Working folder `C:\source1\cs2port`: yes.

## Map compile figures (tw34 of 29 Oct for comparison)

| Figure | tw34 (29 Oct) | This build | Where in the log |
|---|---|---|---|
| Total time | 19 min | 49.7 min (another session's compile shared the CPU part of the time; charting alone 424 s) | `OK in N min` |
| Lightmap resolution | 2048 | 2048 (`final` preset; the packer did not ask for more) | packer lines |
| Charting N unique meshes | 24,754 | 24,718 | `Charting` |
| Packing N UV charts | 1.37 M | 1.40 M | `Packing` |
| Nav areas | 44,160 | run 1: 10,269; **run 2 (nav pass 2): 4,376** (target < 5,000 met) | `>>NAVGEN ... IslandRemoval` |
| DELETED entities | ? | 0 | `DELETED` |
| vpk size | 525 MB | 519.9 MB | game addon `maps/mg_trenchwarfare.vpk` |

## Errors and warnings

| Class | Count | Example / cause | Status |
|---|---|---|---|
| `RESOURCE COMPILE ERROR` (models) | 0 | | clean |
| missing material | 0 | | clean |
| `LODGroupList` single group | 0 | | clean |
| panorama layout / css / js not compiled | 0 | forced, all compiled | clean |
| sounds (wav -> vsnd) | 0 failed | 31 wavs + soundevents | clean |
| `DELETED` at map compile | 0 | mortars, blockers, smoke, rain all kept | clean |
| lightmap / vrad3 | 0 errors | 1.40 M charts in 2048 | clean |
| nav | `ClipPolysToHullClearanceInternal - too many non-reducing passes` (1) | run 1 10,269 areas; run 2 4,376 | fixed (patch_nav pass 2, height-aware NONAV) |
| wrapper exit status vs the log | agree | | |
| harmless noise | `scripts/detail_prop_types.vdata_c` not found | every build | ignore |

## Fixed

- check_play scene cache served a no-stage scene to a `--stage` run (false `separation` failure): `create/check_play.py` keys on path,
  mtime_ns, code, adapter, grid and model roots.
- Nav 10,269 -> 4,376 areas: patch_nav pass 2 (height-aware NONAV, measured first with tools/navtest.py).
- 4 stale model compiles (wire_coil, wire_fence_a/b, ladder) recompiled after the map compile.

## Remains

- Everything in [TESTING.md](TESTING.md): nothing has been loaded in CS2.

## Post-compile checks

- [x] nav area count recorded here (10,269)
- [x] lightmap at 2048, 1.40 M charts beside tw34's 1.37 M
- [x] `python tools/check_world.py` on the deployed map: check 7 `0 of ours not compiled`, 0 stale (after step 7)
- [x] no `DELETED`
- [x] `maps/scripts/mg_trenchwarfare.vjs_c` (16:50), `.vxml_c` / `.vcss_c` newer than the deploy
- [x] NOTES.md "Resume here" updated; level reached: **compiled** (not in-game verified)
