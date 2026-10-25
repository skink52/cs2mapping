# jb_water_prison_cs2

| | |
|---|---|
| Status | Ported, with added scripted features (jailbreak map) |
| Source BSP | `jb_water_prison_go_v3n.bsp` |
| Imported | 2026-09-20 |
| Map last changed | 2026-10-24 (radar/loading screen/credits only) |
| How | manual (Valve importer + post_import_cleanup.py) |

Drivable car (`vehicle_base5` physbox + four thrusters, +use on `vehicle_button5` to get in and out; the driver rides along) replacing a dead game_ui. A `waterhurt` trigger_hurt (acid damage) with `waterfilter`: players who came through the vent are immune until they first leave the water.

## History

- 2026-10-25: radar re-rendered with textured floors (`radar.py` + `radartex.py`).
- 2026-10-24: Radar, 1 loading-screen image, credits (TomGreen, CS:GO port JJ). Assets compile with `run_build.bat "assets jb_water_prison_cs2"`.
- 2026-09-29 (file date): CS2's AddOutput can't rename entities ("AddOutput fired with bad string"), so `water_immunity.js` calls `SetEntityName`. `waterfilter` needed `negated 1`, added as a raw keyvalue with Smart Edit off.

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 12

## Scripts

- [`scripts/vehicles.js`](scripts/vehicles.js) - game_ui replacement for the car
- [`scripts/water_immunity.js`](scripts/water_immunity.js) - names the player so `waterfilter` exempts them
