# mg_trenchwarfare build log 1: the remaster's first deploy and compile

AI-generated (Claude) for skink52. **Template, to fill in from the logs themselves after the real compile** (remaster step 9;
how to run each line: [BUILD.md](BUILD.md)). Until it is filled, the remaster is offline only: nothing deployed, compiled or played.
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

## Commands and times (fill in)

| # | What | Command | Time | Result |
|---|---|---|---|---|
| 1 | Chain + gate + dry run | `watchdog ... -- python -u tools/deploy_tw.py --chain` | | chain CRC32s, gate PASS/REFUSED |
| 2 | Deploy | `python -u tools/deploy_tw.py --apply` | | N created, N replaced; map backup `backups\deploy_<stamp>\`; record `out/step9/deploy/mg_trenchwarfare_deploy_<stamp>.json` |
| 3 | Asset dry run | `build_maps.ps1 -DryRun assets mg_trenchwarfare` | | N assets |
| 4 | Asset compile, run 1 | `watchdog --label "tw assets" ... build_maps.ps1 assets mg_trenchwarfare` | | wrapper says ...; `RESOURCE COMPILE ERROR` count ...; log `out/step9/logs/assets_run1.log` |
| 5 | Forced xml / css / js / svg | `resourcecompiler -f -i ...` | | each `N compiled, 0 failed`? |
| 6 | Map compile | `watchdog --label "tw final" ... build_maps.ps1 final mg_trenchwarfare` | | `OK in N min`? log `out/step9/logs/build_run1.log` |

CS2 build number (console `version`): ...   CS2 tools mode closed throughout: yes / no   Working folder `C:\source1\cs2port`: yes / no

## Map compile figures (fill in; tw34 of 29 Oct for comparison)

| Figure | tw34 (29 Oct) | This build | Where in the log |
|---|---|---|---|
| Total time | 19 min | | `OK in N min` |
| Lightmap resolution | 2048 | | `-lightmapMaxResolution`, the packer lines |
| Charting N unique meshes | 24,754 | | `Charting` |
| Packing N UV charts | 1.37 M | | `Packing` |
| Nav areas | 44,160 | | the nav generation line (target < 5,000; patch_nav estimate about 1,470, factor ~2) |
| DELETED entities | ? | | `DELETED` (must not name `mortar_*`, the 4 unlock blockers, `tw_crater_smoke_*`, `tw_rain*`) |
| vpk size | ? | | `game\csgo_addons\mg_trenchwarfare\maps\mg_trenchwarfare.vpk` |

## Errors and warnings, before and after (fill in, one row per class, from the log)

| Class | Run 1 | Last run | Example line | Cause | Status |
|---|---|---|---|---|---|
| `RESOURCE COMPILE ERROR` (models) | | | | | |
| missing material (`referencing missing material`) | | | | | |
| `LODGroupList` single group | | | | | |
| panorama layout / css / js not compiled | | | | | |
| sounds (wav -> vsnd) | | | | | |
| `DELETED` at map compile | | | | | |
| lightmap / vrad3 (out of memory, charts) | | | | | |
| nav (area count, ladders) | | | | | |
| wrapper exit status vs the log | | | | "assets OK" with failed models is the known lie | |

## Fixed (fill in: tool changed, assets rebuilt, redeployed, recompiled)

- ...

## Remains (fill in)

- ...

## Post-compile checks (fill in)

- [ ] nav area count recorded here and in REVIEW_SCRIPT_1 "Step 4"
- [ ] lightmap at 2048, packer content, chart counts beside tw34's
- [ ] `python tools/check_world.py` on the deployed map: check 7 `0 of ours not compiled`, no `stale`
- [ ] no `DELETED` for our entities
- [ ] `maps/scripts/mg_trenchwarfare.vjs_c`, `.vxml_c`, `.vcss_c` newer than the deploy
- [ ] NOTES.md "Resume here" and REMASTER_PLAN progress updated; level reached: **compiled** (not in-game verified)
