# mg_insomnia_course

| | |
|---|---|
| Status | Published (27 Oct 2026) |
| Workshop | [3826811170](https://steamcommunity.com/sharedfiles/filedetails/?id=3826811170) |
| Original | mg_insomnia_course__v3 by Charon (from Briar's CS:GO minigames folder) |
| Imported | 2026-10-24 |
| Map last changed | 2026-10-24 |
| How | cs2port pipeline, run unattended (run_import_then_build.bat) |

## History

- 2026-10-25: 3 loading-screen images added (`panorama/images/map_icons/screenshots`), compile with `run_build.bat "assets mg_insomnia_course"`.
- 2026-10-24: stages A–C. Indoor map (sky_dust env_sky but no sky brushes; the sky_dust panorama was copied from mg_egypt_course). 6 displacements the importer dropped rebuilt with `disprestore.py` (4 rockwall006a, 1 blend_dirt_concrete_07_aztec, 1 cs_italy/black). Second pass the same day: the 6 kill lasers got `trigger_hurt` boxes along them (`laserhurt.py`, damage 42069, always on) because skink52 wants damaging lasers recreated even when the original had no trigger_hurt; 7 stock CS:GO materials rebuilt from the extracted CS:GO content (`<CS2>\csgo`), dev_water3/4 → nuke_water. Backups: `prefabs+backups\mg_insomnia_course_imported_2026-10-24.vmap`.

## What the cleanup did

- collapsed 6 prefabs; 3 dropped outputs restored (SetDamageFilter on trigger_multiples)
- 3 trigger_push (260/350/500) → script push zones; 2 trigger_gravity (0.2, 0.3) → script gravity zones
- point_servercommand + logic_auto (mp_freezetime 0, mp_roundtime 600); only T spawns (28) so a knife equip was added
- 6 env_laser → func_brush beams (white), plus trigger_hurts (second pass)
- visfit (24-unit voxels): 82 Low, 86 Lower, 1 Lowest; 21 of 208 lights made Stationary across 18 compartments, 2 new light_omni2 in unlit spawn/teleport rooms
- radar (400 floor faces) + `resource/overviews/mg_insomnia_course.txt`; loading text "Original map by Charon / Ported to CS2 by skink52"

## Open / to check

- 4 compartments only partly covered by stationary light (overlap cap): check weapons are lit
- model models/props_furniture/piano.mdl failed to import (1 prop missing)
- ambient_generic `sounds/evens - tell` is a stock CS:GO sound not in the addon (CS:GO VPK chunks not available)
- 10 blood/bombsite decal overlays not converted (no vmat in the addon); 3 func_dustmotes dropped by the importer
- vis: if anything pops where players stand, change the nearest Lower hint to Low

## Scripts

- [`scripts/mg_insomnia_course_io.js`](scripts/mg_insomnia_course_io.js) (push zones, gravity zones)
