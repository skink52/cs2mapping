# mg_super_tower

| | |
|---|---|
| Status | In progress |
| Imported | 2026-10-14 |
| Map last changed | 2026-10-15 |
| How | first cleanup with the scripted fixes that became stage C |

## What the cleanup did

(from the cleanup log in this folder)

- env_sky: sky_cs15_daylight03_hdr (missing) -> rebuilt materials/skybox/sky_cs15_daylight03.vmat
- restored 5 sky brushes (dropped by the importer) as moondome meshes using materials/skybox/sky_cs15_daylight03_moondome.vmat
- restored the output the importer dropped: top trigger_multiple OnStartTouch -> !activator SetDamageFilter no_fall_damage_filter
- 16 trigger_push (speed 3650, CS2 would keep accelerating) -> trigger_multiple + script push zones holding CS:GO speed (clamped to 3500 like sv_maxvelocity)
- visibility hints: {'lowest': 1, 'low': 28, 'medium': 1} (lowest box over whole map incl. void, low over gameplay, medium only in the densest cells)
- radar: rendered from geometry

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 7

## Scripts

- [`scripts/mg_super_tower_io.js`](scripts/mg_super_tower_io.js) - the 16 trigger_push corridors
