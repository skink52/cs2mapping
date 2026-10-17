# mg_yolo_multigames

| | |
|---|---|
| Status | Published |
| Workshop | [mg_yolo_multigames](https://steamcommunity.com/sharedfiles/filedetails/?id=3819030057) |
| Imported | 2026-10-12 |
| Map last changed | 2026-10-13 |
| How | manual, with a large generated map script |

Multigames map with a game-picker lobby. Has a separate 3D skybox map (`mg_yolo_multigames_3d_skybox.vmap`). `yolo_io.js` replaces about 20 dead CS:GO mechanisms (see the script's header).

## History

- 2026-10-13 (from 00:12), `convert_yolo.py`: restored the dropped `!activator` outputs; equips → `weapon0..N` slots and "use" → `TriggerForActivatedPlayer`; spawn teleporters' `AddOutput target` → script `SetDest_` / `Teleport_`, `AddOutput origin` → `MakerOrigin_`; env_sprite → particles; ambient_generic → point_soundevent; the two game_ui (remote-control cube, secret knife) → script; player_speedmod, trigger_gravity, player_weaponstrip and `sm_slay @all` → script; `head_ammo` (ammo_50ae) → `RefillPistolAmmo`; env_screenoverlay → custom_hud_layout; func_monitor, func_physbox_multiplayer, light_dynamic and color_correction swapped for CS2 classes; dropped sky faces → moondome; militiawater → dev_water2. At 01:18 func_wall_toggle → func_brush.
- 2026-10-13 (afternoon to 20:26), gameplay fixes: the map check removed (its physics barrel can't arrive in CS2, so four game buttons were being deleted), along with `phys_pushscale` and `cs_enable_player_physics_box`; the script pushes props for knife hits, shots and players running into them; football goal triggers set to Physics Objects; grenade holes tracked by script (`nade_hole1`–`30`, `NadeWin_T/CT`) with HE grenades from the rails; shot blocks fly toward the shooter; volleyballs nudged awake, `fb_playerclip` lets the ball through, and low gravity cancels 3/4 of the measured gravity; scores fixed by renaming 24 moved outputs from `OnStartTouch` to `OnTrigger`.
- 2026-10-13: arena vis hints went from Medium to Low, with one Lowest over the void.

## Import report

(`post_import_cleanup.py` report in this folder)

- Models - failed to compile: 5
- Textures - fully missing, no source found anywhere: 6

## Scripts

- [`scripts/yolo_io.js`](scripts/yolo_io.js) - alpha (creeper), speedmod, gravity, game-picker teleporters, env_entity_maker origin moves, ball colours, weapon strip, SlayAll (was sm_slay), pistol ammo refill, spawn overlay, game_ui remote-control cube and secret knife, grenade holes, ball/block physics (phys_pushscale), volleyball scoring

## Open / to check

- Volleyball scoring after the `OnTrigger` fix is untested in game.
- Grenade-hole buttons work through the script; the root cause in the original logic wasn't confirmed.
- The scripted prop-push strengths are guesses.
- Spawn buttons were silent after the import (their sounds were dropped); check.
- The wireframe "wallhack" walls are approximated.
