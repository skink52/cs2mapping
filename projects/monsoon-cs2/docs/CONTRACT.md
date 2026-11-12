# mg_monsoon contract: names the map generator, the script, the HUD and the tests must agree on

Single source for entity names, model paths and files. Change it here first, then both sides. `tg` = `t` | `ct`.
Teams: T = 2, CT = 3. Coordinates/POIs come from `tools/layout.py` (`out/layout.json` for the script build).

## Files
- Script: `src/NN_*.js` joined by `tools/build_script.mjs` -> `out/addon/maps/scripts/mg_monsoon.js` (one import line from
  `cs_script/point_script`). Config data baked in: `const LAYOUT = <out/layout.json>`, `const HUDDATA = <out/hud.json>`.
- Tests: `test/mock.mjs [players] [seconds]` (real script on a stub engine, reads `out/entities.json`, HUD xml/css), `test/tsconfig.json`.
- HUD: `tools/mv_hud.py <addon>` -> `panorama/layout/custom_game/mg_monsoon.xml`, `panorama/styles/custom_game/mg_monsoon.css`,
  images `panorama/images/custom_game/mv/`, and `out/hud.json` (panel ids, step counts). Panel ids start `mv_`.
- Sounds: `tools/sounds.py <addon> <template vsndevts>` -> `sounds/mv/*.wav`, events `mv.*` merged into `soundevents/soundevents_addon.vsndevts`.
- Map: `tools/make_map.py` (stages in `mv_terrain.py`, `mv_places.py`, `mv_entities.py`); models `models/mv/<name>/<name>.vmdl`.
- US helicopter: the CC-BY Apache, copied to `models/vehicles/apache/apache.vmdl` (anims `idle`, `spin_slow`, `spin`, played with
  `SetAnimationLooping` + `SetIdleAnimationLooping` and spooled with `SetPlaybackRate`: CS2's prop_dynamic has no `SetAnimation`; origin on
  the ground under the mast; nose direction and scale recorded in `out/apache.json` by `tools/apache_setup.py`).
- Flag pole: `models/mv/flag_pole/flag_pole.vmdl` = p_jungle.py's pole with skins (0 neutral, 1 T, 2 CT), re-rigged by
  `tools/mv_flag_anim.py` (run after p_jungle.py): bones `root` + `flag`, 21 one-frame looping poses `flag_00` (cloth at the foot) ..
  `flag_20` (at the top), archetype `animated_model`.

## Entities (targetnames)
| Name | Class | Notes |
|---|---|---|
| `mv_script`, `mv_hud`, `mv_params` | point_script, custom_hud_layout, info_map_parameters | lobby |
| `mv_spawn_<tg>_1..16` | info_teleport_destination | base deploy points |
| `mv_flag_<a..e>` | info_target at the flag pole base | + `mv_flagspawn_<a..e>_1..8` info_teleport_destination |
| `mv_flagpole_<a..e>` | prop_dynamic `flag_pole` | Skin 0 neutral, 1 T, 2 CT (script fires `Skin`); the cloth's height: script fires `SetAnimationLooping` / `SetIdleAnimationLooping` `flag_00..20`. Optional map key `IdleAnim flag_00` |
| `mv_flag_snd_<a..e>` | point_soundevent `mv.capture` at the pole | script fires `StartSound` on capture |
| `mv_kit_<tg>` and `mv_kit_<a..e>` | info_target at each arms rack / flag supply crate | kit station (E within 80 u) |
| `mv_heli_<tg>_1..3` | prop_dynamic (`model_archetype ""`; the Apache's map key should be `IdleAnim idle`, not CS:GO's `DefaultAnim`) | CT: Apache x3. T: 1,2 = Mi-8 slick, 3 = Mi-8 gunship (models from `tools/mv_models.py`: converted `ext/hip_slick`, `ext/hip/hip_upper`; procedural `heli_hip`, `heli_hip_gun` when the conversions are absent) |
| `mv_rotor_t_1..3`, `mv_tail_t_1..3` | prop_dynamic `ext/hip/hip_rotor`, `ext/hip/hip_tail` (fallback `rotor_hip`, `tailrotor_hip`) | T only (the Apache animates its own rotors); placed on the hubs from the model table |
| `mv_pad_<tg>_1..3` | info_target | pad centre on the ground (park pose: pad yaw from layout) |
| `mv_heli_eng_<tg>_N`, `mv_heli_gun_<tg>_N`, `mv_heli_gun2_<tg>_N`, `mv_heli_rkt_<tg>_N` | point_soundevent | `mv.heli_rotor` loop, `mv.heli_gun`, `mv.rocket_launch` |
| `mv_heli_smoke_<tg>_N`, `mv_heli_dust_<tg>_N` | info_particle_system | damage smoke (parented by script Move), ground dust |
| `mv_wreck_<tg>_1..3` | prop_dynamic `ext/heli_wreck/heli_wreck_dyn` for both sides (fallback `wreck_hip` / `wreck_huey`) | parked at PARK_Z until a crash; put down at nose yaw + `models.wreck.yaw` |
| `mv_gun_<tg>_1..K` | prop_dynamic carriage: CT `ext/m101` (fallback `howitzer_m102`) K=3, T `rocket_tripod` K=4 | yawed by script |
| `mv_tube_<tg>_1..K` | prop_dynamic elevating part: `ext/m101_gun` (fallback `howitzer_m102_gun`) / `rocket_rail` | origin = trunnion (`models.howitzer.trunnion` / `models.rocket.trunnion` on the carriage) |
| `mv_round_t_1..K` | prop_dynamic `rocket_122` | shown on the rail when loaded, flies as the projectile |
| `mv_rack_<tg>_1..K` | info_target | ammo pick-up station per gun |
| `mv_board_<tg>` | info_target at the plotting table | sit point; `mv_boardseat_<tg>_1..K` info_teleport_destination |
| `mv_gun_snd_<tg>_N`, `mv_gun_fx_<tg>_N` | point_soundevent `mv.howitzer_fire` / `mv.rocket_fire`, info_particle_system | |
| `mv_mount_1..M` | prop_dynamic gun part (`ext/m2_gun`, `ext/dshk_gun`, `quad50_gun`; stands `ext/m2_tripod`, `ext/dshk_tripod`, `quad50_mount` are prop_static) | pivot = pintle; + `mv_mountseat_N` info_teleport_destination behind it, `mv_mount_snd_N` |
| `mv_mountinfo_N` | info_target | key `message` = `"<kind>:<team>"` kind m2/dshk/quad50, team t/ct/any |
| pools `mv_boom_fx_1..16`, `mv_dirt_fx_1..16`, `mv_boom_snd_1..16`, `mv_whistle_snd_1..16`, `mv_shake_1..16` | particles / soundevents / env_shake | impacts |
| `mv_tracer_1..24`, `mv_rocket_1..16`, `mv_marker_1..10`, `mv_smoke_fx_1..6`, `mv_pip_<slot 0..63>` not used: `mv_pip_1..12` | prop_dynamic fx models / particle | parked at PARK_Z |
| `mv_shell_1..12` | prop_dynamic `shell_105` | visible falling shell / carried round |
| `mv_cache_1..N` (N <= 16) | prop_dynamic | one per model the script SetModels: the crash hulks, rocket, shell, then the paths in `out/cache_models.json` (the four uniforms `models/player/gmod/{nva_soldier,vietcong_soldier,soldier2_woodland,us}`); the script reads each prop's model name |
| `mv_ambience` | point_soundevent `mv.amb.valley` startOnSpawn | |
| `mv_tunnel_<1..3>` | info_teleport_destination | tunnel portals (bot leash targets) |
| `mv_nav_*` | func_nav_markup | WALKABLESEED at bases/flags/roads (`mv_nav_seed_N`), NONAV over slopes, karst, deep river (`mv_nav_no_N`) |
| `mv_rain_1..7`, `mv_lightning` (+ `_flash`) | logic_relay + info_particle_system `mv_rain_N_0_0`; logic_timer + env_fade | rain over the flags and bases (FireUser1 / FireUser2 = start / stop), faint lightning flash |

layout.json (from `layout.export`, written by make_map to `out/layout.json`) also carries: `terrain` = `{x0, y0, cell, nx, ny, z[]}` (128-u ground
heights, `z[j * nx + i]` at `(x0 + i * cell, y0 + j * cell)`), `mountinfo` = `{"N": {n, kind, team, x, y, z, yaw}}` matching `mv_mount_N`
(the same entries as the list `mounts`), `tunnels`, `bridge` (`deck_z`: flag B stands on the deck), and `models` (from
`tools/mv_models.py`, the one table that says which model stands for what): `hip`, `hip_gun`, `apache` = `{variant, model, nose_yaw,
rotor_r, hub, tail_hub?, seats[{kind, off}], exits[], pods[], gun{muzzle, cam, yaw, cone, up, down}}` in the nose frame; `howitzer`,
`rocket` = `{trunnion, muzzle, rest_pitch}`; `m2`, `dshk`, `quad50` = `{pintle, muzzle, seat_back}`; `wreck` = `{t, ct, yaw}`;
`pads` = `{t: [model name per pad], ct: [...]}`. The script overwrites its CONFIG defaults with these.

## Models
`tools/mv_models.py` picks, per logical name, the converted GMod Workshop model under `models/mv/ext/` when its `.vmdl` is in the addon
and our procedural prop otherwise (`MV_NO_EXT=1` forces the procedural set, e.g. for a Steam Workshop build: docs/ASSETS.md, licence).
`check_world.py` check 7 fails when any entity names a model that is neither under `out/addon` nor in the pak01 index.

## Seats
- Apache: pilot (flies, rockets ATTACK), gunner (chin 30 mm, own aim), 2 wing riders (hang on the stub wings).
- Hip slick: pilot (fixed A-12.7 nose gun, MOUSE1), 1 door gunner (PK, left door), 4 riders. Hip gunship: pilot (rockets), 1 door
  gunner, 2 riders. The Apache pilot also fires the chin gun (MOUSE2) while the gunner seat is empty.
- Seat offsets come from `layout.json` `models` (model space, nose frame); the script CONFIG holds the same numbers as defaults.

## Roles and chat
`!help` `!commands` `!controls` `!infantry` `!artillery` `!air` `!rifle` `!mg` `!at` `!roles` `!swap` `!spawn <a-e|base|heli>` `!pos`
`!uniform` `!bots <n>` (`/` works as `!`; one line each in docs/SCRIPT.md).
Bots: infantry by default; when a team has fewer than `CONFIG.AI.MIN_HUMANS_FOR_ROLES` humans the script assigns bots to fly
(AI pilot), gun (AI door/mount gunner) and crew the batteries (AI crew). Bots never take a seat a human asks for.

## Sound events
`mv.heli_rotor` (loop), `mv.heli_turbine` (loop), `mv.heli_gun`, `mv.rocket_launch`, `mv.rocket_fly`, `mv.howitzer_fire`,
`mv.rocket_fire`, `mv.shell_whistle`, `mv.shell_impact`, `mv.mount_gun` (CS2's own M249 report, `sounds/weapons/m249/m249_01..03`, one per
round), `mv.capture`, `mv.flag_lost`, `mv.radio_blip`,
`mv.amb.valley` (soundscape parent: cicadas, birds, river, distant guns, thunder).
