# mg_crash_bandicoot_course

| | |
|---|---|
| Status | Published (27 Oct 2026) |
| Workshop | [3826776791](https://steamcommunity.com/sharedfiles/filedetails/?id=3826776791) |
| Original | mg_crash_bandicoot_course_v1 (author not recorded in the map; music folder "gogaming") |
| Imported | 2026-10-24 |
| Map last changed | 2026-10-24 |
| How | cs2port pipeline, run unattended (run_import_then_build.bat) |

## History

- 2026-10-25: 2 loading-screen images added (`panorama/images/map_icons/screenshots`), compile with `run_build.bat "assets mg_crash_bandicoot_course"`.
- 2026-10-24: stages A–C. **118 displacements** (all the terrain, roots, aztec stone, beams, grass) were dropped by the importer, so the first visfit found no playable air at all; stage C was run in two halves: merge/entities/sounds/sky/beams, then `disprestore.py`, then `stage_d.py visfit,lights,radar`. The 37 sky brushes came back as moondomes with the **jungle sky copied from mg_kohztec_course** (the CS:GO VPK chunks for the sky faces aren't on the PC). Second pass: 21 materials rebuilt from the extracted CS:GO content and the BSP's own textures (aztec stone, dirt/grass blends, the custom crate textures). The importer had sanitised `materials/crash bandicoot/…` and `silkroad/asia minor/…` to underscores while post_import_cleanup kept the real names; `matnames.py` points the vmap back at the real files. Backups: `prefabs+backups\mg_crash_bandicoot_course_imported_2026-10-24.vmap`.

## What the cleanup did

- collapsed 6 prefabs; game_player_equip (knife) mapped to CS2 slots, so no extra knife equip
- point_servercommand + logic_auto (mp_freezetime 0, mp_roundtime 600)
- 1 game_score → script Score_n; 1 player_speedmod (0.1) → script Speed_n; 1 trigger_gravity (-2, i.e. upward pull) → script gravity zone
- 2 ambient_generics (gogaming chariot / crash music) → soundevents
- 37 moondomes (jungle); visfit (32-unit voxels): 108 Low, 81 Lower, 1 Lowest, 1 of 37 shells excluded from vis
- 1 of 105 lights made Stationary (1 compartment), 1 compartment open to sky, 1 new light_omni2
- radar (4467 floor faces) — the terrain at the bottom runs off the image, redo if it matters; loading text credits "Original CS:GO map mg_crash_bandicoot_course (author unknown)"

## Open / to check

- 1 non-box sky brush not rebuilt; 1 func_dustmotes and 2 func_precipitation (rain) dropped by the importer
- overlay materials/realworldtextures2/ground/grass_07 not converted
- displacements have no vertex-paint blending (disprestore limitation)
- vis: if anything pops where players stand, change the nearest Lower hint to Low

## Scripts

- [`scripts/mg_crash_bandicoot_course_io.js`](scripts/mg_crash_bandicoot_course_io.js)
