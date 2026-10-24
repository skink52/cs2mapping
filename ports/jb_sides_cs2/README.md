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

- 2026-10-24: RadGen radar was broken: replaced by a `radar.py` one (`pct=0`, the west corridor was clipped otherwise). Old `jb_sides_cs2_radar.tga/.png/_tga.vtex` left in `panorama/images/overheadmaps` (harmless, delete by hand). 4 loading-screen images, credits (JJ and ab). Assets compile with `run_build.bat "assets jb_sides_cs2"`.
