# jb_sides_cs2

| | |
|---|---|
| Status | Imported and worked on (jailbreak map, Aug-Sep 2026) |
| Source BSP | `jb_sides_v1a.bsp` |
| Imported | - |
| Map last changed | 2026-10-24 (radar/loading screen/credits only) |
| How | manual (Valve importer) |

Radar made with RadGen (`jb_sides_cs2.radgen` is its config).

## History

- 2026-11-09: **ranged music resumes when you come back** (disco1-3): CS2 stopped a non-looping sound for good once the listener was out of range. `voice_culling_threshold = -1.0` keeps it playing silently (`tools/rangedmusic.py`). vsndevts compiled, backup `soundevents_addon.vsndevts.bak_20261109`; not yet heard in game or uploaded.
- 2026-10-25: radar re-rendered with textured floors (`radar.py` + `radartex.py`).
- 2026-10-24: RadGen radar was broken: replaced by a `radar.py` one (`pct=0`, the west corridor was clipped otherwise). Old `jb_sides_cs2_radar.tga/.png/_tga.vtex` left in `panorama/images/overheadmaps` (harmless, delete by hand). 4 loading-screen images, credits (JJ and ab). Assets compile with `run_build.bat "assets jb_sides_cs2"`.
- 2026-11-03: **switched lights** (`mapcheck.py`): 24 lights the map switches are no longer baked: Stationary (Dynamic only if it rides a parent or was already Dynamic; shadows off where more than 4 shadowed stationary lights would overlap), bounce light off, so their light no longer stays on the walls when they are off. Needs a lighting build.
- 2026-11-03: **disco floor** (`mapcheck.py`, skink52): its 24 coloured switched lights have shadows off, so the changing colours look right; switched lights get no baked bounce. Needs a lighting build.
- 2026-11-14: water cut into ≤384-u pieces (`watersplit`) and rebuilt, then **undone the same day**: the compiler's func_water "Failed to create physics hulls" warning, which the cut was meant to remove, turned out to be harmless (water with it works in game). vmap restored from `.bak_watersplit_20261114_*` and rebuilt entities-only; the cut version is kept as `.bak_prerevert_*`.
