# ttt_island17_pezversion

| | |
|---|---|
| Status | Built with the TTT game mode, not tested in game or published |
| BSP | `ttt_island17_pezversion.bsp` |
| Original | Author not recorded yet |
| Imported | 2026-11-02 |
| How | [autoport](../../autoport/README.md) |

A CS2 Island17 is on the Workshop: [[TTT] Island17](https://steamcommunity.com/sharedfiles/filedetails/?id=3390290442), made for the EverGames server. It needs a dedicated server; this port plays from the map's own script, so it doesn't count as a duplicate.

## History

- 2026-11-08: **new radar and loading-screen text** for the upload as ttt_island. The 2 Nov radar was rendered before the 126
  displacements were restored, so it showed only the buildings and paths on white. Re-rendered with `tools/radar.py` from the
  current vmap (`radar.run(m, c, pct=0.5)` with `c.addon = 'ttt_island'`): terrain, water and buildings, pos -4392 3272, scale
  6.08, `slopes=True, open_water=True`. Fixed after skink52's check: the beaches showed as grass (the blend material
  `blendsandgrass008a` is sand in game, from `sandfloor009a.png`; radartex now reads the `.vmat`), and the water now starts where the
  ground rises above the water plane (z -528) per pixel, not per face. Steep ground fills the gaps between terrain levels. Content `ttt_island_radar_psd.png/.vtex` (the old
  ones are archived), compiled with resourcecompiler; game `resource/overviews/ttt_island.txt`. Loading text in
  `maps/ttt_island.txt`: the map, a one-line pitch with !ttt / !rules, "Ported to CS2 by skink52" (Island17's original author isn't
  recorded). Not yet seen in game.

- 2026-11-08: **renamed to ttt_island** before its first upload. First tried without a recompile (repacking the compiled vpk under
  the new name): it loaded, but the whole world had no collision when skink52 tested it from Hammer, so that repack is withdrawn
  (kept in the archive folder below, `broken_repack/`) and the map is recompiled as `maps/ttt_island.vmap` (skink52 renamed the
  content vmap; built 8 Nov 13:52, `maps/ttt_island.vpk` with its world under `maps/ttt_island/`, the old-name vpk gone). In the game addon, `maps/ttt_island.txt`, `_cameras.txt`, `_retakes.txt`,
  `resource/overviews/ttt_island.txt` and the radar `ttt_island_radar_psd.vtex_c` replace the old-name files, and the stub
  `cfg/maps/ttt_island17_pezversion.cfg` is gone; the skybox vpk, postprocess and lighting keep the old name (referenced by path).
  The originals are in `C:\source1\archive\ttt_island17_pezversion_before_rename\`. The addon folders and the content `.vmap`
  keep the old name. After the ttt_island build, delete `maps/ttt_island17_pezversion.vpk` from the game addon before uploading. Also has the 8 Nov ttt.js (echo channel).

- 2026-11-02: stage A–D through autoport: 126 dropped displacements restored, 3D skybox split, water pass, final `visfit`.
- Vis: 87.9 billion cubic units of play space, 17 Low, 1 Lower, 1 Lowest. About 13 minutes, collapsing 218,171 regions to 53,423. The whole map build takes about 15 minutes.

- 2026-11-02: TTT game mode through autoport's TTT profile, with the same HUD image fix as ttt_terrortrain. The HUD and script are built. No `ttt_*` entities, so no map data.
- 2026-11-02 (skink52's report: respawnable props, lwglass2 and ladder errors, props not imported, z-fighting):
  - **Props not imported:** the 23 `woodwall030b_window01a_bars` window bars and `door01_left` never compiled, because cs_mdl_import left their
    bodygroup choices unnamed. `tools/vmdlfix.py` names them, and both models now build.
  - **58 prop_physics_respawnable:** CS2 has no such class. In CS:GO they were physics props that came back at their spot RespawnTime seconds
    (45–60) after breaking, once the spot was clear. Now prop_physics + point_template + env_entity_maker do the same without script (`tools/respawnable.py`).
  - **lwglass2:** its OnBreak outputs aimed at `lwbars2_i` / `lwbars2_f`, which the map never had (the window it belongs to has unnamed bars), so they
    did nothing in CS:GO either. Removed. **4 info_ladder_dismount** removed (CS2 excludes the class; its ladders dismount on their own). **trigger_waterydeath**
    (CS:GO's leeches) → trigger_hurt in the same place.
  - **Water:** `nature/water_wasteland002a` → `anubis/anubis_water_canal` (the new default).
  - **Z-fighting:** 166 coplanar overlaps found. Once overlaps pressed against a back-facing face are ignored, 44 real ones remain: 8 faces moved
    0.25 units forward, and 0 visible ones are left (62 small or same-material overlaps remain).
  - **Ropes:** 4 cable_dynamic from the 5 keyframe_rope / move_rope (the fork's `ropes` step).
  - **Gibs:** 21 models given CS:GO's generic chunks, 40 gib models imported before the build.
  - **Vis:** the first build with the new sight corridors ran past autoport's 20-minute vis limit (about 13 minutes before), so autoport rebuilt with
    `visfit_lean`. Vis then took 8 minutes (206,528 → 48,900 regions); the whole build took 10 minutes.

## Open / to check

- Original author for the loading screen credit (`maps/ttt_island17_pezversion.txt`): none found in the map, on GameBanana or by search.
- Check the automatic skybox split: 26 nodes moved, box -6656 -5120 -8832 .. 3584 4608 -7424.
- 6 textures have no source (WHY MISSING in `maps/ttt_island17_pezversion_cleanup_report.txt`). Some meshes got no physics hull (build log).
- Overlay materials not converted: `decals/rubble01a`, `trashdecal01a`, `trashdecal03a`, `trashdecal04a`.
- env_fog_controller dropped by the importer.
- In game: break a respawnable prop and watch it come back; the window bars; the 8 moved faces; rope sag; underwater lights; seams on split floors;
  vis pop-in (lean hints); light brightness against CS:GO.
