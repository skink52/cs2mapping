# ba_jail_lightsout

| | |
|---|---|
| Status | Ported, with added scripted features (jailbreak map) |
| Imported | 2026-10-01 |
| Map last changed | 2026-10-24 (radar/loading screen/credits only) |
| How | manual; the environment prefab was too heavy to collapse in Hammer, so its contents were pasted in with Paste Special |

Separate 3D skybox map (`ba_jail_lightsout_3dskybox.vmap`, referenced by a `skybox_reference`). It didn't render until **Editor only** was unticked on its `sky_camera`.

## History

- 2026-10-25: radar re-rendered with textured floors (`radar.py` + `radartex.py`).
- 2026-10-24: Radar (`radar.py`), 3 loading-screen images (Workshop thumbnails, upscaled). Credits file already existed (Dom). Assets compile with `run_build.bat "assets ba_jail_lightsout"`.
- Around its import (10-01): the importer needed the content root `C:\source1` (where the VMF is), not the CS:GO content folder. The environment prefab (about 15 MB, 1,457 entities) was pasted in with Paste Special. Alpha masks for glow and blood decals; static overlays toned down with `g_fTextureColorBrightness` 0.3. Its compile log: 123 light_omni2 asked for shadow slots and 102 failed; the vis boundary pass took about 1,018 s.

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 59

## Scripts

- [`scripts/buff_new.js`](scripts/buff_new.js) - weapon buffs
- [`scripts/dodgeball.js`](scripts/dodgeball.js) - dodgeball minigame
