# mg_yolo_multigames

| | |
|---|---|
| Status | Published |
| Workshop | [mg_yolo_multigames](https://steamcommunity.com/sharedfiles/filedetails/?id=3819030057) |
| Imported | 2026-10-12 |
| Map last changed | 2026-10-13 |
| How | manual, with a large generated map script |

Multigames map with a game-picker lobby. Has a separate 3D skybox map (`mg_yolo_multigames_3d_skybox.vmap`). `yolo_io.js` replaces about 20 dead CS:GO mechanisms (see the script's header).

## Import report

(`post_import_cleanup.py` report in this folder)

- Models - failed to compile: 5
- Textures - fully missing, no source found anywhere: 6

## Scripts

- [`scripts/yolo_io.js`](scripts/yolo_io.js) - alpha (creeper), speedmod, gravity, game-picker teleporters, env_entity_maker origin moves, ball colours, weapon strip, SlayAll (was sm_slay), pistol ammo refill, spawn overlay, game_ui remote-control cube and secret knife, grenade holes, ball/block physics (phys_pushscale), volleyball scoring
