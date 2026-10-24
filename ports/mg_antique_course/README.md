# mg_antique_course

| | |
|---|---|
| Status | Stage C done 24 Oct 2026, queued for build |
| Original | mg_antique_course3 by ScHoOuFi |
| Imported | 2026-10-24 |
| Map last changed | 2026-10-24 |
| How | cs2port pipeline, run unattended (run_import_then_build.bat) |

## History

- 2026-10-24: stages A–C (147 MB BSP, 4 asset zips). Custom sky `sky_cerulean` rebuilt from the six faces embedded in the BSP and 10 sky brushes restored as moondomes. 24 dropped displacements (lb_text/toile1) rebuilt with `disprestore.py`. 22 parented env_particle_glows (on func_rotating / func_tanktrain movers) converted with `glowfix.py`; no weapon parents, so no script follow. Second pass: `trigger_hurt` boxes along the 3 distinct kill lasers l5/l7/l9 (l6/l8 are their mirror pairs), damage 1000, start off, with the beams' Enable/Disable I/O copied; `matnames.py` pointed 19 `schooufi_texture/…` refs back at the addon's `schooufi texture/…` files (the first assets run had swapped them for random stock materials); boathouse_water and ringel_waterfall → nuke_water. Backups: `prefabs+backups\mg_antique_course_imported_2026-10-24.vmap`.

## What the cleanup did

- collapsed 6 prefabs; 2 trigger_push (250) → script push zones; 1 point_servercommand → script Cmd_n; 6 game_score / 28 ApplyScore → script Score_n
- knife equip already in the map; point_servercommand + logic_auto added (mp_freezetime 0, mp_roundtime 600)
- 85 ambient_generics → 20 soundevents (the map's own mp3s, cleaned names)
- 22 env_laser → func_brush beams (3 colours), 22 TurnOn/Off → Enable/Disable; 5 beams with no usable end point removed (l14, l2, l4, la2, la4)
- visfit (16-unit voxels): 15 Low, 3 Lower, 1 Lowest, all 10 sky shells kept; 6 of 138 lights made Stationary (6 compartments), 2 open to sky
- radar (569 floor faces); loading text "Original map by ScHoOuFi / Ported to CS2 by skink52"

## Open / to check

- `game_ui` game1 is dead in CS2 (needs a script, like the jail maps' vehicles) — not converted
- point_viewcontrol cam1: check it still works
- the map had a CS:GO 3D skybox (sky_camera at 450 -3523 144, scale 64): its geometry is now in the main map, CS2 ignores sky_camera — move to a skybox map or delete
- 10 looping ambient_generics use mp3s with no cue points, so they play once
- 3 stock CS:GO ambient sounds not in the addon (ambience_base, cs_metalscrapeverb04, water_streamloop3)
- models missing: models/player/slow/zombie_package/slow_1 (failed to import, x2)
- 1 VMF entity with outputs couldn't be matched 1:1; 106 func_dustmotes and 1 point_spotlight dropped by the importer
- CS:GO info_particle_system "toy*" effects use CS:GO particles that don't exist in CS2

## Scripts

- [`scripts/mg_antique_course_io.js`](scripts/mg_antique_course_io.js)
