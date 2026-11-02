# ttt_terrortrain

| | |
|---|---|
| Status | Built, not tested in game or published |
| BSP | `ttt_terrortrain_v1_csgo.bsp` |
| Original | Author not recorded yet |
| Imported | 2026-11-02 |
| How | [autoport](../../autoport/README.md) (first end-to-end test map) |

Map port only: the TTT game mode (cs2mapTTT) hasn't been applied.

Another CS2 port is on the Workshop: [[TTT]TerrorTrain](https://steamcommunity.com/sharedfiles/filedetails/?id=3360009792) by Z46 (`ttt_cs2_terrortrain_v1`). skink52 chose to port it anyway.

## History

- 2026-11-02: stage A–D through autoport, including the 3D skybox split, overlaydepth and probecover.
- 2026-11-02: plain `visfit` found almost no play space (0.0 billion cubic units, 1 Lowest hint), because the map is open to the void. `visfit_detail` found 1.1 billion: 7 Medium, 11 Low, 1 Lower, 1 Lowest. Vis took 29 s and collapsed 1,164,619 regions to 12,543.

## Open / to check

- Original author for the loading screen credit (`maps/ttt_terrortrain.txt`).
- Check the automatic skybox split: 30 nodes moved, box 995 23 -440.5 .. 1362 975 -308.5.
- 1 texture has no source (WHY MISSING in `maps/ttt_terrortrain_cleanup_report.txt`).
- Overlay materials not converted: `de_train/train_security_decal_01`, `decals/milswitch001`–`003`. Two `train_security_decal_01` overlays sit on func_doors and won't show.
- 7 non-box sky brushes weren't rebuilt as moondomes.
- Face scales fixed but texture coordinates not rewritten for `nature/water_canals_water2`.
- In game: vis pop-in, 1 flickering light style, light brightness against CS:GO, 151 physics props (`physpush` if pushes feel wrong), split triggers feeding counters.
