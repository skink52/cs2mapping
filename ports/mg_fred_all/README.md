# mg_fred_all

| | |
|---|---|
| Status | Built (in progress) |
| Imported | 2026-10-16 |
| Map last changed | 2026-10-16 |
| How | cs2port pipeline (stages A-D) |

Has a map-specific script gate: damage between enemies is off until the Fin room's `fintrigger` fires `EnableDamage` (every round starts with it off).

## What the cleanup did

(from the cleanup log in this folder)

- collapsed 6 prefabs into the map, world offsets kept: mg_fred_all_gameplay.vmap (292 nodes, 292 entities), mg_fred_all_environment_prefab.vmap (2842 nodes, 693 entities), mg_fred_all_lighting_prefab.vmap (2 nodes, 2 entities), mg_fred_all_cubemaps_prefab.vm...
- outputs restored that the importer dropped: 0
- 15 trigger_push (speeds [800.0, 9999.0, 10000.0]; CS2 would keep accelerating) -> trigger_multiple + script push zones holding CS:GO speed (clamped to 3500); names/filters/Enable/Disable kept
- visibility hints: lowest 1 (whole map incl. void), low 30 (cells with geometry), medium 0 (densest cells only)
- stationary lights: 112 of 599 lights switched Static -> Stationary (directlight 3) across 102 sealed compartments, ranges trimmed so no spot is inside more than 4
- radar: rendered from geometry (1349 floor faces shaded by height, walls outlined) -> panorama/images/overheadmaps/mg_fred_all_radar_psd.png + game resource/overviews/mg_fred_all.txt (pos -2866 7056, scale 10.28)

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 6

## Scripts

- [`scripts/mg_fred_all_io.js`](scripts/mg_fred_all_io.js) - trigger_push replacement and the EnableDamage / DisableDamage gate (`OnBeforePlayerDamage`)

## Open / to check

- check the substituted materials look right: materials/sprites/combineball_glow_red_1.vmat -> materials/sprites/blueglow1.vmat
- the waterfall brushes now use liquids/nuke_water (CS2 has no CS:GO waterfall shader) - swap in a stock waterfall/foam material if they look wrong
- 5 compartments could not get a stationary light without going over 4 overlapping - check them
- 32 compartments only partly covered by stationary light (overlap cap) - check weapons are lit there
