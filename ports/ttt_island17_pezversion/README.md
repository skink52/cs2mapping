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
