# mg_balistic_course

| | |
|---|---|
| Status | Published |
| Workshop | [mg_ballistic_course_cs2](https://steamcommunity.com/sharedfiles/filedetails/?id=3816960127) |
| Imported | 2026-10-10 |
| Map last changed | 2026-10-10 |
| How | manual (Valve importer + post_import_cleanup.py) |

## History

- 2026-10-10: neon laser materials (red, green, cyan, magenta: colour, translucency and self-illum textures) made in `materials\lasers`. Later ports copied them. Decals converted to `csgo_static_overlay` with `vmat_to_overlay.py`.
- 2026-11-03: **respawn window** (`respawnwindow.py`, skink52): players who die before the spawn AFK killer `afk` switches on (60 s) respawn; `port_respawn_window` turns `mp_respawn_on_death_t/ct` off 55 s in. Needs a build.
- 2026-11-03: **music** (`coursemusic.py`): the map had none. Eight songs shuffled from round start, the next when one ends: ba_jail_skylight's four (skink52's favourites) and Majestic (Wax Fang), jb_lightsout's disco1, jb_seaside's disco2, Sandstorm (Darude). Each is named after the map it came from (`sounds/port_music/`), since several maps call different songs disco1-3.
