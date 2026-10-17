# ba_jail_seaside

| | |
|---|---|
| Status | Ported, with added scripted features (jailbreak map) |
| Imported | 2026-08-24 |
| Map last changed | 2026-10-01 |
| How | manual (Valve importer + post_import_cleanup.py) |

Jailbreak map with cs_script additions: a knife dodgeball minigame (balls `Dball_1..3`, armed by button `Dball1` and live 4.5 s later, cancelled by `Dball2`), plus copies of the bumper car and weapon buff scripts from ba_jail_skylight. Separate 3D skybox map (`ba_jail_seaside3dskybox.vmap`).

## Import report

(`post_import_cleanup.py` report in this folder)

- Models - failed to import: 1
- Models - failed to compile: 7
- Textures - fully missing, no source found anywhere: 32

## Scripts

- [`scripts/buff_new.js`](scripts/buff_new.js) - weapon buffs tracked by who picks up the named map weapon
- [`scripts/bumper_cars.js`](scripts/bumper_cars.js) - game_ui replacement driving the cars' phys_thrusters
- [`scripts/dodgeball.js`](scripts/dodgeball.js) - knife-launched dodgeball that kills on contact until the ball settles
