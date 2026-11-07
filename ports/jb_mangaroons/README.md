# jb_mangaroons

| | |
|---|---|
| Status | Imported and worked on (jailbreak map, Aug-Sep 2026) |
| Imported | 2026-08-22 |
| Map last changed | 2026-11-07 (watermelon model swap) |
| How | manual (Valve importer) |

## History

- 2026-11-07: watermelons now break into gibs: all 202 `prop_physics_multiplayer` watermelons moved from stock `models/food/fruits/watermelon01a.vmdl` (its break pieces point at `props_junk/watermelon01_chunk*`, which CS2 never shipped) to the imported CS:GO `models/props_junk/watermelon01.vmdl` with its six chunks, copied from ba_jail_seaside along with `materials/models/props_junk/fruit_objects01`. Backup `maps/jb_mangaroons.vmap.bak_watermelon_20261107`. Entity-only rebuild.
- 2026-10-25: radar re-rendered with textured floors (`radar.py` + `radartex.py`).
- 2026-10-24: Radar, 4 loading-screen images (`Mangaroons.png` 1080p + 3 thumbnails), credits (gReeN). Assets compile with `run_build.bat "assets jb_mangaroons"`.
