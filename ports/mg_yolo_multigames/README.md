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
- 2026-10-29, fixes from Ninja-Chris's CS:GO/CS2 comparison screenshots:
  - Cut-out textures drew opaque: their vmats had `F_TRANSLUCENT 1` but no `TextureTranslucency`, and csgo_complex doesn't use the colour alpha. Masks
    (`*_trans.png`) from the CS:GO VTF alpha for random (random button), sgip, twitch_test, pushscale (spawn banners), kaynenumbers number_0/1,
    combineglass001a; `{ladder2` alpha-tested.
  - Wallhack game: `white.vmat` (wireframe stand-in) was `csgo_unlitgeneric` with `F_TRANSLUCENT`, which that shader ignores → `F_BLEND_MODE 1` +
    `TextureTranslucency` + back faces. hacks_relay's 13 `Toggle`s per func_brush became explicit Enable/Disable in the same order, ending as in CS:GO
    (hacks_toggle_main shown, hacks_toggle hidden).
  - Sprites (env_sprite → particle) were sized texture width × 1: buyzone 512 u across (aim tower), kaboom 1024 u and the countdown numbers 256 u
    (creeper). CS:GO sprites with no `scale` key drew about texture width × 0.25, so radius = width/2 × 0.25 (buyzone 128 u, numbers 64 u, kaboom 256 u).
    Non-square sprite textures (kaboom, sname, paulname) padded to square so the particle quad doesn't stretch them.
  - Scouts "drugged" game: the post_processing_volume LUT copies of weed_co_1..3 showed nothing. Replaced with a full-screen HUD overlay (custom_hud_layout
    panels `weed_1..3`, colour-swirl images, breathing scale animation) driven by `Weed_1/2/3/Weed_Off` script inputs from weed_relay / weed_random /
    kill_smoke, cleared at round start and end. Global like the CS:GO color_correction, so nobody is left stuck with it. The PP volumes are left in place.
  - Aim tower secret camera room: its teleport (target `Secret`) is StartDisabled; the room's func_monitor can't work in CS2.
  - `compile_yolo_fixes.bat` in the addon compiles the particles, vmats, panorama and script that the command-line build skips, then runs `run_build.bat`.

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
- The wireframe "wallhack" walls are approximated (face borders, not triangle edges).
- 29 Oct fixes untested in game: sprite sizes (0.25 is estimated from the screenshots), weed overlay look/animation, wallhack walls showing.
