# ba_jail_lightsout

| | |
|---|---|
| Status | Ported, with added scripted features (jailbreak map) |
| Imported | 2026-10-01 |
| Map last changed | 2026-10-24 (radar/loading screen/credits only) |
| How | manual; the environment prefab was too heavy to collapse in Hammer, so its contents were pasted in with Paste Special |

Separate 3D skybox map (`ba_jail_lightsout_3dskybox.vmap`, referenced by a `skybox_reference`). It didn't render until **Editor only** was unticked on its `sky_camera`.

## History

- 2026-11-09: **ranged music resumes when you come back** (disco1-3): CS2 stopped a non-looping sound for good once the listener was out of range. `voice_culling_threshold = -1.0` keeps it playing silently (`tools/rangedmusic.py`). vsndevts compiled, backup `soundevents_addon.vsndevts.bak_20261109`; not yet heard in game or uploaded.
- 2026-10-25: radar re-rendered with textured floors (`radar.py` + `radartex.py`).
- 2026-10-24: Radar (`radar.py`), 3 loading-screen images (Workshop thumbnails, upscaled). Credits file already existed (Dom). Assets compile with `run_build.bat "assets ba_jail_lightsout"`.
- Around its import (10-01): the importer needed the content root `C:\source1` (where the VMF is), not the CS:GO content folder. The environment prefab (about 15 MB, 1,457 entities) was pasted in with Paste Special. Alpha masks for glow and blood decals; static overlays toned down with `g_fTextureColorBrightness` 0.3. Its compile log: 123 light_omni2 asked for shadow slots and 102 failed; the vis boundary pass took about 1,018 s.
- 2026-11-03: **switched lights** (`mapcheck.py`): 147 lights the map switches are no longer baked: Stationary (Dynamic only if it rides a parent or was already Dynamic; shadows off where more than 4 shadowed stationary lights would overlap), bounce light off, so their light no longer stays on the walls when they are off. Needs a lighting build.
- 2026-11-03: light_environment brightness 0.15 -> 0.1875 (+25%, skink52 had turned it down too far).
- 2026-11-03: the build failed on two unused stray materials, `models/props/de_nuke/emergency_lightb_glow_color.vmat` and `..._glow_off_color.vmat`: they pointed at `.tga` sources that had been replaced by `.png` in January. Repointed to the `.png` (backups `*.vmat.bak_tga`).
- 2026-11-14: **water physics** (`watersplit`): 2 func_water meshes over 384 u cut into 10 closed pieces; CS2 gives a func_water mesh over ~500 u no physics hull, so that water could not be swum in. Entities-only rebuild: 0 func_water hull failures where the cut applied. Backup `ba_jail_lightsout.vmap.bak_watersplit_20261114_*`. Compiled, not checked in game.

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 59

## Scripts

- [`scripts/buff_new.js`](scripts/buff_new.js) - weapon buffs
- [`scripts/dodgeball.js`](scripts/dodgeball.js) - dodgeball minigame
