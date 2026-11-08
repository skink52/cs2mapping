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

- 2026-11-09: **ranged music resumes when you come back** (the fountain, right now (na na na), imperitum immediate, dark side of power): CS2 stopped a non-looping sound for good once the listener was out of range. `voice_culling_threshold = -1.0` keeps it playing silently (`tools/rangedmusic.py`). vsndevts compiled, backup `soundevents_addon.vsndevts.bak_20261109`; not yet heard in game or uploaded.
- 2026-11-03: **z-fight fix undone where it was wrong** (skink52 spotted it): the 2 Nov polish had hidden 34 and moved 0 faces that only overlap a switched, moving, breakable or undrawn entity, or sit behind a see-through face. Restored from the pre-polish backup; zfight.py now leaves those alone. Needs a lighting build.
