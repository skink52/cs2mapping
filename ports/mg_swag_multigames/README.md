# mg_swag_multigames

| | |
|---|---|
| Status | In progress |
| Imported | 2026-10-13 |
| Map last changed | 2026-10-13 |
| How | manual, with a large generated map script |

`swag_io.js` replaces about 20 dead CS:GO mechanisms (see its header), including func_conveyor (CS2 conveyors don't carry players) and ball physics.

## History

- 2026-10-13, `convert_swag.py`: the same treatment as mg_yolo_multigames, plus 17 env_screenoverlays, 5 env_spritetrail → info_particle_system, 9 func_illusionary → non-solid func_brush, water → dev_water2 inside a func_water, and the star models (`slow`, `slow_2`) rebuilt from the pakfile. func_wall_toggle → func_brush.
- 2026-10-13 (afternoon): asked for the map check, the slide game, and an intro overlay limited to two rounds (`INTRO_ROUNDS = 2`).

## Import report

(`post_import_cleanup.py` report in this folder)

- Models - failed to compile: 6
- Textures - fully missing, no source found anywhere: 3

## Scripts

- [`scripts/swag_io.js`](scripts/swag_io.js) - alpha/colour/origin AddOutputs, speedmod, game-picker teleporters, env_entity_maker moves, prop colours, overlays, weapon strip, pistol ammo, SlayAll, conveyor, ball physics

## Open / to check

- What happened with the map check and slide game isn't recorded.
