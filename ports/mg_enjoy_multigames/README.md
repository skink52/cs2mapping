# mg_enjoy_multigames

| | |
|---|---|
| Status | Published |
| Workshop | [mg_enjoy_multigames_cs2](https://steamcommunity.com/sharedfiles/filedetails/?id=3817075436) |
| Imported | 2026-10-10 |
| Map last changed | 2026-10-11 |
| How | manual (Valve importer + post_import_cleanup.py) |

Has a separate 3D skybox map (`mg_enjoy_multigames_3dskybox.vmap`).

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 4

## History

- 2026-11-03: **z-fight fix undone where it was wrong** (skink52 spotted it): the 2 Nov polish had hidden 34 and moved 0 faces that only overlap a switched, moving, breakable or undrawn entity, or sit behind a see-through face. Restored from the pre-polish backup; zfight.py now leaves those alone. Needs a lighting build.
