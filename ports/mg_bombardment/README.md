# mg_bombardment

| | |
|---|---|
| Status | Published |
| Workshop | [mg_bombardment_cs2](https://steamcommunity.com/sharedfiles/filedetails/?id=3816918916) |
| Imported | 2026-10-10 |
| Map last changed | 2026-10-17 |
| How | manual (Valve importer + post_import_cleanup.py) |

Has a separate 3D skybox map (`mg_bombardment_3dskybox.vmap`).

## History

- 2026-11-14: water cut into ≤384-u pieces (`watersplit`) and rebuilt, then **undone the same day**: the compiler's func_water "Failed to create physics hulls" warning, which the cut was meant to remove, turned out to be harmless (water with it works in game). vmap restored from `.bak_watersplit_20261114_*` and rebuilt entities-only; the cut version is kept as `.bak_prerevert_*`.

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 2
