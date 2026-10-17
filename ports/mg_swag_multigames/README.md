# mg_swag_multigames

| | |
|---|---|
| Status | In progress |
| Imported | 2026-10-13 |
| Map last changed | 2026-10-13 |
| How | manual, with a large generated map script |

`swag_io.js` replaces about 20 dead CS:GO mechanisms (see its header), including func_conveyor (CS2 conveyors don't carry players) and ball physics.

## Import report

(`post_import_cleanup.py` report in this folder)

- Models - failed to compile: 6
- Textures - fully missing, no source found anywhere: 3

## Scripts

- [`scripts/swag_io.js`](scripts/swag_io.js) - alpha/colour/origin AddOutputs, speedmod, game-picker teleporters, env_entity_maker moves, prop colours, overlays, weapon strip, pistol ammo, SlayAll, conveyor, ball physics
