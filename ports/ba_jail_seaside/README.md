# ba_jail_seaside

| | |
|---|---|
| Status | Ported, with added scripted features (jailbreak map) |
| Imported | 2026-08-24 |
| Map last changed | 2026-10-24 (radar/loading screen/credits only) |
| How | manual (Valve importer + post_import_cleanup.py) |

Jailbreak map with cs_script additions: a knife dodgeball minigame (balls `Dball_1..3`, armed by button `Dball1` and live 4.5 s later, cancelled by `Dball2`), plus copies of the bumper car and weapon buff scripts from ba_jail_skylight. Separate 3D skybox map (`ba_jail_seaside3dskybox.vmap`).

## History

- 2026-10-25: radar re-rendered with textured floors (`radar.py` + `radartex.py`).
- 2026-10-24: Radar (`radar.py`; the earlier RadGen one was never in the content folder). Loading screen already existed. Credits file rewritten with the `COMMUNITYMAPCREDITS:` header it was missing (hyphen). Assets compile with `run_build.bat "assets ba_jail_seaside"`.
- 2026-08: `post_import_cleanup.py` was written for this map, because Valve's importer stopped at the first asset it couldn't handle. Its models also exposed the `cs_mdl_import` crashes: `-r` with `*.mdl` scanned about 12,164 stock models and crashed (253 of 255 failed), and an explicit file list got 152 through before one mdl/vtx checksum mismatch crashed it.
- Undated: func_brush beams parented to a func_rotating wouldn't Enable, so they stay unparented and get `SetParent` at runtime. Water reflections come from a baked cubemap. Radar made with RadGen (the selection set must be named `radgen_path`). BreakFloor respawn through a counter (to 104) and a point_template. `movingwall_stop` was missing a Disable on `movingwall_timer3`.

## Import report

(`post_import_cleanup.py` report in this folder)

- Models - failed to import: 1
- Models - failed to compile: 7
- Textures - fully missing, no source found anywhere: 32

## Scripts

- [`scripts/buff_new.js`](scripts/buff_new.js) - weapon buffs tracked by who picks up the named map weapon
- [`scripts/bumper_cars.js`](scripts/bumper_cars.js) - game_ui replacement driving the cars' phys_thrusters
- [`scripts/dodgeball.js`](scripts/dodgeball.js) - knife-launched dodgeball that kills on contact until the ball settles
