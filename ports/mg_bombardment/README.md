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

- 2026-11-14: **water physics** (`watersplit`): 26 func_water meshes over 384 u cut into 144 closed pieces; CS2 gives a func_water mesh over ~500 u no physics hull (16 had none), so that water could not be swum in. Entities-only rebuild: 0 func_water hull failures. Backup `mg_bombardment.vmap.bak_watersplit_20261114_*`. Compiled, not checked in game.

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 2
