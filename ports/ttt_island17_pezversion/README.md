# ttt_island17_pezversion

| | |
|---|---|
| Status | Built, not tested in game or published |
| BSP | `ttt_island17_pezversion.bsp` |
| Original | Author not recorded yet |
| Imported | 2026-11-02 |
| How | [autoport](../../autoport/README.md) |

Map port only: the TTT game mode (cs2mapTTT) hasn't been applied.

A CS2 Island17 is on the Workshop: [[TTT] Island17](https://steamcommunity.com/sharedfiles/filedetails/?id=3390290442), made for the EverGames server. Whether this `pezversion` differs from it hasn't been checked. skink52 chose to port it anyway.

## History

- 2026-11-02: stage A–D through autoport: 126 dropped displacements restored, 3D skybox split, water pass, final `visfit`.
- Vis: 87.9 billion cubic units of play space, 17 Low, 1 Lower, 1 Lowest. About 13 minutes, collapsing 218,171 regions to 53,423. The whole map build takes about 15 minutes.

## Open / to check

- Original author for the loading screen credit (`maps/ttt_island17_pezversion.txt`).
- Check the automatic skybox split: 26 nodes moved, box -6656 -5120 -8832 .. 3584 4608 -7424.
- `models/props_wasteland/woodwall030b_window01a_bars` fails to compile, and 1 more model failed in the import (WHY MISSING in `maps/ttt_island17_pezversion_cleanup_report.txt`). 6 textures have no source.
- Overlay materials not converted: `decals/rubble01a`, `trashdecal01a`, `trashdecal03a`, `trashdecal04a`.
- env_fog_controller dropped by the importer.
- In game: underwater lights, seams on split floors, vis pop-in, light brightness against CS:GO.
