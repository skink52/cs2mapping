# ba_jail_lightsout

| | |
|---|---|
| Status | Ported, with added scripted features (jailbreak map) |
| Imported | 2026-10-01 |
| Map last changed | 2026-10-06 |
| How | manual; the environment prefab was too heavy to collapse in Hammer, so its contents were pasted in with Paste Special |

Separate 3D skybox map (`ba_jail_lightsout_3dskybox.vmap`, referenced by a `skybox_reference`). It didn't render until **Editor only** was unticked on its `sky_camera`.

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 59

## Scripts

- [`scripts/buff_new.js`](scripts/buff_new.js) - weapon buffs
- [`scripts/dodgeball.js`](scripts/dodgeball.js) - dodgeball minigame
