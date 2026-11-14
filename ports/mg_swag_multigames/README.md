# mg_swag_multigames

| | |
|---|---|
| Status | Built (in progress, slow progress) (27 Oct 2026) |
| Imported | 2026-10-13 |
| Map last changed | 2026-10-13 |
| How | manual, with a large generated map script |

`swag_io.js` replaces about 20 dead CS:GO mechanisms (see its header), including func_conveyor (CS2 conveyors don't carry players) and ball physics.

## History

- 2026-10-13, `convert_swag.py`: the same treatment as mg_yolo_multigames, plus 17 env_screenoverlays, 5 env_spritetrail → info_particle_system, 9 func_illusionary → non-solid func_brush, water → dev_water2 inside a func_water, and the star models (`slow`, `slow_2`) rebuilt from the pakfile. func_wall_toggle → func_brush.
- 2026-10-13 (afternoon): asked for the map check, the slide game, and an intro overlay limited to two rounds (`INTRO_ROUNDS = 2`).
- 2026-11-14: **water physics** (`watersplit`): 16 func_water meshes over 384 u cut into 274 closed pieces; CS2 gives a func_water mesh over ~500 u no physics hull, so that water could not be swum in. Entities-only rebuild: 0 func_water hull failures where the cut applied. Backup `mg_swag_multigames.vmap.bak_watersplit_20261114_*`. Compiled, not checked in game. Its water is flat sheets with no depth (the CS:GO brush depth was lost on import), so they compile but there is still no volume to swim in.

## Import report

(`post_import_cleanup.py` report in this folder)

- Models - failed to compile: 6
- Textures - fully missing, no source found anywhere: 3

## Scripts

- [`scripts/swag_io.js`](scripts/swag_io.js) - alpha/colour/origin AddOutputs, speedmod, game-picker teleporters, env_entity_maker moves, prop colours, overlays, weapon strip, pistol ammo, SlayAll, conveyor, ball physics

## Open / to check

- What happened with the map check and slide game isn't recorded.
