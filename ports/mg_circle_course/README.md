# mg_circle_course

| | |
|---|---|
| Status | Published |
| Workshop | [mg_circle_course_cs2](https://steamcommunity.com/sharedfiles/filedetails/?id=3817732135) |
| Imported | 2026-10-11 |
| Map last changed | 2026-10-11 |
| How | manual (Valve importer + post_import_cleanup.py) |

## History

- 2026-10-11: VIS ran 18+ min ("Generated clusters for 307557 regions… 2453840 clusters"). The big open centre gives vis little to cull. Iterate without full vis and keep the sealed volume small.
- 2026-11-03: **respawn window** (`respawnwindow.py`, skink52): players who die before the spawn AFK killer `spawn` switches on (60 s) respawn; `port_respawn_window` turns `mp_respawn_on_death_t/ct` off 55 s in. Needs a build.
- 2026-11-03: **music** (`coursemusic.py`): the map had none. Seven songs shuffled from round start, the next when one ends: ba_jail_skylight's four (skink52's favourites) and Nightcall (Kavinsky), In the Navy, jb_lightsout's disco2. Each is named after the map it came from (`sounds/port_music/`), since several maps call different songs disco1-3.
- 2026-11-14: water cut into ≤384-u pieces (`watersplit`) and rebuilt, then **undone the same day**: the compiler's func_water "Failed to create physics hulls" warning, which the cut was meant to remove, turned out to be harmless (water with it works in game). vmap restored from `.bak_watersplit_20261114_*` and rebuilt entities-only; the cut version is kept as `.bak_prerevert_*`.

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 3
