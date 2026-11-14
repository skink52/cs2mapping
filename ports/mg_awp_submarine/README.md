# mg_awp_submarine

| | |
|---|---|
| Status | Published |
| Workshop | [mg_awp_submarine_cs2](https://steamcommunity.com/sharedfiles/filedetails/?id=3817816213) |
| Imported | 2026-10-11 |
| Map last changed | 2026-10-11 |
| How | manual (Valve importer + post_import_cleanup.py) |

Has a separate 3D skybox map (`mg_awp_submarine_3dskybox.vmap`) referenced from the main map.

## History

- 2026-10-11: the `launch` soundevent was silent. Most of the map's wavs had never compiled to `.vsnd_c` (fix: Full Recompile of the wavs, re-save the `.vsndevts`, restart the tools), and `soundspawna3` / `soundspawna17` had `sounds/launch.vsnd` / `launch.vsnd` as their sound name, where the event name `launch` belongs.
- 2026-11-14: water cut into ≤384-u pieces (`watersplit`) and rebuilt, then **undone the same day**: the compiler's func_water "Failed to create physics hulls" warning, which the cut was meant to remove, turned out to be harmless (water with it works in game). vmap restored from `.bak_watersplit_20261114_*` and rebuilt entities-only; the cut version is kept as `.bak_prerevert_*`.

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 3

## Open / to check

- The `disco1` / `disco2` wavs are missing.
- Check that `soundspawna3` and `soundspawna17` use the event name `launch`.
