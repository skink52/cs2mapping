# mg_trenchwarfare contract: names the map, the script, the HUD and the tests must agree on

Single list of the entity names, models, sound events, HUD ids and commands that the script (`src/modules/`, shipped as `src/mg_trenchwarfare.js`) relies on, with where each
comes from and whether the current map and addon have it. Change a name here first, then on both sides. `tg` = `t` | `ct` (T = 2, CT = 3);
`N` numbers an aircraft or post from 1, `K` a mortar crew 1..`CONFIG.CREWS`.

**Checked by** `python tools/check_contract.py` (from the project folder): it reads the script, the map digest (`out/digest.json` from
`tools/restage_out.py`, or a fresh `tools/mapdigest.py` read of the vmap) and the content + game addon folders, and exits 1 on any
MISSING row not listed under [Known missing](#known-missing), on a script lookup that no row covers (UNLISTED), on a row whose name has
left the script (STALE), or on a shipped script older than its modules (STALE build), and on a `SetModel` whose argument is not a
`CONFIG.UNIFORMS` model or the pawn's own (UNCHECKED SetModel). `--markdown` prints the tables below. The tables were generated on 12 Nov 2026 from the user's vmap (tw34
delivery, 67,206,918 B, CRC32 2e3f90d0) and the addon as it stood that day; rows changed by remaster steps 4 (bots) and 5 (world patch)
were updated the same day. Level: a read of the files; nothing here is in-game verified.

**Two states.** By default the check reads the deployed map (`out/digest.json` from `tools/restage_out.py`): 77 of 78 rows OK, the
known missing `mortar_<tg>_K`. Step 5's patched map: `python tools/check_contract.py --vmap out/mg_trenchwarfare_patched.vmap --stage out/addon`
(also `out/nav_patched_step5.vmap`, step 5 + `tools/patch_nav.py`): 80 of 80 OK. `--stage` lets a model on a map entity that is only
staged (`out/addon`, not compiled yet) count as OK, "staged, not compiled yet"; never a model the script sets on a pawn.

## Files
- Script: `src/modules/NN_*.js`, joined by `node ../../create/build_script.mjs src/build.json` into `src/mg_trenchwarfare.js` (the
  shipped file; module map in [SCRIPT.md](SCRIPT.md)). The addon copy is `content\...\maps\scripts\mg_trenchwarfare.js`; the map's
  `tw_script` runs `maps/scripts/mg_trenchwarfare.vjs`.
- Map: the user's `content\csgo_addons\mg_trenchwarfare\maps\mg_trenchwarfare.vmap` (source of truth; delta patches only, REMASTER_PLAN).
  Most names were placed by `tools/make_map.py` (vis group `tw_gen`); later ones by the `tools/patch_*.py` delta patches.
- HUD: `tools/tw_hud.py` + `tools/tw_cockpit.py` -> `panorama/layout/custom_game/mg_trenchwarfare.xml`, `panorama/styles/custom_game/mg_trenchwarfare.css`,
  pictures `panorama/images/custom_game/tw/`. Panel ids start `tw_`. Text goes through the dialog variable `v`.
- Sounds: `tools/sounds.py` -> `sounds/tw/*.wav`, events `tw.*` in `soundevents/soundevents_addon.vsndevts`.
- Tests: `node test/mock.mjs [players] [seconds]` reads `out/entities.json` and `out/addon/panorama/...xml|css` and `out/addon/<model>`
  for SetModel (all restaged by `tools/restage_out.py`).
- Shared constants (`tools/restage_out.py` fails if they disagree): radar region `x0 -4300, y0 4700, span 8601.6` = `make_radar.py`
  X0/Y0/SCALE x 1024 = the shipped overview `pos_x/pos_y/scale` = `CONFIG.RADAR`; sight square `CONFIG.TARGET_EXT 4600` = `render_top.py EXT`;
  sight steps `CONFIG.TARGET_STEPS 192` = `tw_hud.py STEPS` (the `.x0..x191` / `.y0..y191` classes).

## Entities (targetnames)
What the script looks up by name (`Entities.FindByName` through `byName` / `findList`, `Entities.FireInput` through `fire`, `ent.FireInput`),
plus the few entities it depends on without looking them up. "Count" is how many of the expected names exist with that class.

| Name | Class | Count in the vmap | Made by | Status | Notes |
|---|---|---|---|---|---|
| `trench_<tg>_N` | info_teleport_destination | 20 / 20 (t / ct; script reads 1..64) | make_map.py | OK | infantry posts (deploy, and the bot leash: a post 400+ u from a closed blocker). Bots: \|x\| < 1900 = fire trench (1..15), else support trench (16..20); the post within 600 u of an opened blocker is that area's sap head / ladder post |
| `heal_<tg>_N` | info_target | 3 / 3 (t / ct; script reads 1..16) | make_map.py | OK | dressing stations |
| `plane_<tg>_N` | info_teleport_destination | 5 / 5 (t / ct; script reads 1..16) | make_map.py | OK | air-spawn points |
| `tw_plane_<tg>_N` | prop_dynamic | 5 / 5 (t / ct; script reads 1..16) | make_map.py | OK | the aircraft (CT SPAD VII, T Dr.I) |
| `tw_prop_<tg>_N` | prop_dynamic | 10 of 10 | patch_vmap.py (make_map.py since) | OK | propeller, one per aircraft |
| `tw_bomb_<tg>_N_1..2` | prop_dynamic | 20 of 20 | make_map.py | OK | 2 per aircraft |
| `tw_tracer_<tg>_N_1..6` | prop_dynamic | 60 of 60 | make_map.py | OK | 6 per aircraft |
| `tw_bombsight_<tg>_N` | prop_dynamic | 10 of 10 | make_map.py | OK |  |
| `tw_gunsight_<tg>_N` | prop_dynamic | 10 of 10 | make_map.py | OK |  |
| `tw_plane_eng_<tg>_N` | point_soundevent | 10 of 10 | make_map.py | OK | SetSourceEntity to the aircraft; StartSound/StopSound (engine loop) |
| `tw_plane_gun_<tg>_N` | point_soundevent | 10 of 10 | make_map.py | OK | SetSourceEntity to the aircraft; StartSound per burst |
| `tw_plane_gun2_<tg>_N` | point_soundevent | 10 of 10 | make_map.py | OK | SetSourceEntity to the aircraft; StartSound per burst |
| `tw_plane_gun3_<tg>_N` | point_soundevent | 10 of 10 | make_map.py | OK | SetSourceEntity to the aircraft; StartSound per burst |
| `tw_plane_smoke_<tg>_N` | info_particle_system | 10 of 10 | make_map.py | OK | damage smoke Start/Stop |
| `mortarpit_<tg>_K` | info_target | 10 of 10 | make_map.py | OK | tube position, K = 1..CREWS (5) |
| `mortarcrew_<tg>_K_a` | info_teleport_destination | 10 of 10 | make_map.py | OK | seat a: plotting table |
| `mortarcrew_<tg>_K_b` | info_teleport_destination | 10 of 10 | make_map.py | OK | seat b: ammunition box |
| `tw_launch_snd_<tg>_K` | point_soundevent | 10 of 10 | make_map.py | OK | StartSound on firing |
| `tw_launch_fx_<tg>_K` | info_particle_system | 10 of 10 | make_map.py | OK | Stop/Start on firing |
| `mortar_<tg>_K` | prop_dynamic | 0 of 10 deployed; 10 of 10 in step 5's patched map | patch_world_1.py (step 5; prop_static in the deployed map) | MISSING (known) in the deployed map; OK patched | looked up per round; SetAnimation fire by ent.FireInput when present (fireMortar), and the fallback for a missing mortarpit_. Patched: on `minenwerfer_dyn.vmdl` / `mortar_58mm_dyn.vmdl` (anims idle + fire = CONFIG.MORTAR_FIRE_ANIM) |
| `tw_boom_fx_1..12` | info_particle_system | 12 of 12 | make_map.py | OK | effect pool (POOL 12), Teleport + Stop/Start |
| `tw_dirt_fx_1..12` | info_particle_system | 12 of 12 | make_map.py | OK | effect pool (POOL 12), Teleport + Stop/Start |
| `tw_boom_snd_1..12` | point_soundevent | 12 of 12 | make_map.py | OK | effect pool (POOL 12), Teleport + StartSound |
| `tw_whistle_snd_1..12` | point_soundevent | 12 of 12 | make_map.py | OK | effect pool (POOL 12), Teleport + StartSound |
| `tw_shake_1..12` | env_shake | 12 of 12 | make_map.py | OK | effect pool (POOL 12), Teleport + StartShake |
| `tw_hud` | custom_hud_layout | 1 of 1 | make_map.py | OK | CONFIG.HUD |
| `woodsopen` | prop_dynamic | 1 of 1 (2 entities) | the user (blockers), made prop_dynamic by patch_unlocks.py | OK | Entities.FindByName (both); Remove + effects when the area opens (CONFIG.UNLOCKS); positions: the bot leash and the bots' ladder post. Step 5: model `revet_planks_broken_128_dyn.vmdl` |
| `undergroundopen` | prop_dynamic | 1 of 1 (2 entities) | the user (blockers), made prop_dynamic by patch_unlocks.py | OK | Entities.FindByName (both); Remove + effects when the area opens (CONFIG.UNLOCKS); positions: the bot leash and the bots' sap-head post. Step 5: model `revet_planks_broken_dyn.vmdl` |
| `tw_script` | point_script | 1 of 1 | make_map.py | OK | runs the script (not looked up by it) |
| `tw_uniform_1..4` | prop_dynamic | 4 of 4 | patch_uniforms.py | OK | hidden precache props for the uniform models (not looked up by the script) |
| `info_player_terrorist / _counterterrorist` | spawns | 32 / 32 | make_map.py | OK | lobby spawns (the script teleports from there; not looked up) |

## Models
Models the script sets (`SetModel`; each also needs a precache prop in the map), then the models on the prop_dynamics the script moves.
On `!uniform` the script sets the player's own stock agent model back (read from the pawn, not listed). Rule (12 Nov, from the user):
the giant first-person weapons came from a pawn set to a model the game could not load (picked in Hammer without its assets), so
every model the script sets on a pawn must be compiled in the game addon (`.vmdl_c`) or be the pawn's own; `check_contract.py` fails
on any other `SetModel` argument and on a uniform model without its `.vmdl_c` (a compile older than the `.vmdl` is noted).

| Model | Use | Made by | Status | Notes |
|---|---|---|---|---|
| `models/tw/players/tw_de_a/tw_de_a.vmdl` | SetModel (CONFIG.UNIFORMS) | tools/soldiers.py (+ arms tools) | OK | content yes, game vmdl_c yes, precache tw_uniform_1 |
| `models/tw/players/tw_de_b/tw_de_b.vmdl` | SetModel (CONFIG.UNIFORMS) | tools/soldiers.py (+ arms tools) | OK | content yes, game vmdl_c yes, precache tw_uniform_2 |
| `models/tw/players/tw_gb_a/tw_gb_a.vmdl` | SetModel (CONFIG.UNIFORMS) | tools/soldiers.py (+ arms tools) | OK | content yes, game vmdl_c yes, precache tw_uniform_3 |
| `models/tw/players/tw_gb_b/tw_gb_b.vmdl` | SetModel (CONFIG.UNIFORMS) | tools/soldiers.py (+ arms tools) | OK | content yes, game vmdl_c yes, precache tw_uniform_4 |
| `models/tw/ext/plane_dr1/plane_dr1_dyn.vmdl` | on tw_plane_<tg>_N | map (prop_dynamic model key) | OK | content yes, game vmdl_c yes |
| `models/tw/ext/plane_dr1/plane_dr1_prop.vmdl` | on tw_prop_<tg>_N | map (prop_dynamic model key) | OK | content yes, game vmdl_c yes |
| `models/tw/ext/plane_spad7/plane_spad7_dyn.vmdl` | on tw_plane_<tg>_N | map (prop_dynamic model key) | OK | content yes, game vmdl_c yes |
| `models/tw/ext/plane_spad7/plane_spad7_prop.vmdl` | on tw_prop_<tg>_N | map (prop_dynamic model key) | OK | content yes, game vmdl_c yes |
| `models/tw/fx/tw_bomb/tw_bomb.vmdl` | on tw_bomb_<tg>_N | map (prop_dynamic model key) | OK | content yes, game vmdl_c yes |
| `models/tw/fx/tw_bombsight/tw_bombsight.vmdl` | on tw_bombsight_<tg>_N | map (prop_dynamic model key) | OK | content yes, game vmdl_c yes |
| `models/tw/fx/tw_gunsight/tw_gunsight.vmdl` | on tw_gunsight_<tg>_N | map (prop_dynamic model key) | OK | content yes, game vmdl_c yes |
| `models/tw/fx/tw_tracer/tw_tracer.vmdl` | on tw_tracer_<tg>_N | map (prop_dynamic model key) | OK | content yes, game vmdl_c yes |
| `models/tw/revet_planks_broken/revet_planks_broken.vmdl` | on undergroundopen | map (prop_dynamic model key) | OK | content yes, game vmdl_c yes |
| `models/tw/revet_planks_broken_128/revet_planks_broken_128.vmdl` | on woodsopen | map (prop_dynamic model key) | OK | content yes, game vmdl_c yes |

In step 5's patched map (`--vmap out/mg_trenchwarfare_patched.vmap --stage out/addon`), staged by `tools/dyn_models.py`, not compiled yet:

| Model | Use | Made by | Status | Notes |
|---|---|---|---|---|
| `models/tw/minenwerfer/minenwerfer_dyn.vmdl` | on mortar_t_K | tools/dyn_models.py, patch_world_1.py | OK (staged) | anims idle + fire |
| `models/tw/ext/mortar_58mm/mortar_58mm_dyn.vmdl` | on mortar_ct_K | tools/dyn_models.py, patch_world_1.py | OK (staged) | anims idle + fire |
| `models/tw/revet_planks_broken/revet_planks_broken_dyn.vmdl` | on undergroundopen | tools/dyn_models.py, patch_world_1.py | OK (staged) | dynamic archetype twin (REVIEW_WORLD_1 H2) |
| `models/tw/revet_planks_broken_128/revet_planks_broken_128_dyn.vmdl` | on woodsopen | tools/dyn_models.py, patch_world_1.py | OK (staged) | dynamic archetype twin (H2) |

## Sound events
The script plays no sound by name: it fires `StartSound` / `StopSound` at named `point_soundevent`s, whose `soundName` is listed here.
Stock `.vsnd` files inside an event are not checked offline (they live in the game's pak01).

| Sound event | Made by | Status | Notes |
|---|---|---|---|
| `tw.mortar_impact` | tools/sounds.py | OK | on tw_boom_snd_N; own files none; 3 stock vsnd (not checked offline) |
| `tw.mortar_launch` | tools/sounds.py | OK | on tw_launch_snd_N; own files mortar_launch.vsnd; 1 stock vsnd (not checked offline) |
| `tw.mortar_whistle` | tools/sounds.py | OK | on tw_whistle_snd_N; own files mortar_whistle.vsnd |
| `tw.plane_engine` | tools/sounds.py | OK | on tw_plane_eng_N; own files plane_engine.vsnd |
| `tw.plane_gun` | tools/sounds.py | OK | on tw_plane_gun2_N, tw_plane_gun3_N, tw_plane_gun_N; own files none; 3 stock vsnd (not checked offline) |

## HUD (custom_hud_layout `tw_hud`)
Ids the script sends (`SetDialogVariableStringForPlayer` via `hText`, `SetHasClassForPlayer` via `hClass` / `hSwap` / `placeMarker`;
`placeMarker(id)` also drives `<id>y`) and the classes it toggles, against the content xml / css.

| HUD item | Count | Made by | Status | Notes |
|---|---|---|---|---|
| `panel ids the script sends (56)` | 56 of 56 in the xml | tools/tw_hud.py + tw_cockpit.py | OK | tw_alt_drum, tw_ammo_txt, tw_banner, tw_banner_sub, tw_banner_title, tw_bomb1, tw_bomb2, tw_brief, tw_brief_count, tw_brief_l1, tw_brief_l2, tw_brief_l3, tw_brief_role, tw_card, tw_fly, tw_fly_info, tw_hdg_txt, tw_imp0, tw_imp0y, tw_imp1, tw_imp1y, tw_imp2, tw_imp2y, tw_info, tw_info_foot, tw_info_l1, tw_info_l2, tw_info_l3, tw_info_l4, tw_info_l5, tw_info_title, tw_lock, tw_locky, tw_n_alt, tw_n_asi, tw_n_bank, tw_n_rpm, tw_pit, tw_pity, tw_prompt, tw_prompt_text, tw_ret, tw_rety, tw_st_l1, tw_st_l2, tw_st_l3, tw_st_role, tw_status, tw_t_grid, tw_t_range, tw_t_state, tw_t_tube, tw_target, tw_tmap, tw_toast, tw_toast_text |
| `class .mct` |  | tools/tw_hud.py | OK | in the css |
| `class .mt` |  | tools/tw_hud.py | OK | in the css |
| `class .on` |  | tools/tw_hud.py | OK | in the css |
| `class .show` |  | tools/tw_hud.py | OK | in the css |
| `classes .a0 .. .a71` | 72 of 72 | tools/tw_hud.py | OK | NEEDLE: dial rotation in 5-degree steps |
| `classes .x0 .. .x191` | 192 of 192 | tools/tw_hud.py | OK | marker x position (TARGET_STEPS) |
| `classes .y0 .. .y191` | 192 of 192 | tools/tw_hud.py | OK | marker y position (TARGET_STEPS) |

## Files the map points at

| File | Made by | Status | Notes |
|---|---|---|---|
| `soundevents/soundevents_addon.vsndevts` | tools/sounds.py | OK | content yes, game vsndevts_c yes |
| `panorama/layout/custom_game/mg_trenchwarfare.vxml` | tools/tw_hud.py | OK | tw_hud layout key panorama/layout/custom_game/mg_trenchwarfare.vxml; content xml yes, css yes; game vxml_c yes, vcss_c yes |
| `maps/scripts/mg_trenchwarfare.vjs` | src/mg_trenchwarfare.js (build of src/modules) | OK | tw_script cs_script key; content .js yes (same as src/), game vjs_c yes |

## Console commands and convars
Sent with `ServerCommand` on activate (and `say` for chat). Nothing in the addon backs these, so they are OK by construction; the names
are not validated offline.

| Command | Sent by | Status | Notes |
|---|---|---|---|
| `mp_respawn_on_death_t 1` | script OnActivate | OK | CONFIG.CVARS |
| `mp_respawn_on_death_ct 1` | script OnActivate | OK | CONFIG.CVARS |
| `mp_respawn_immunitytime 0` | script OnActivate | OK | CONFIG.CVARS |
| `mp_freezetime 0` | script OnActivate | OK | CONFIG.CVARS |
| `mp_roundtime 60` | script OnActivate | OK | CONFIG.CVARS |
| `mp_buy_anywhere 0` | script OnActivate | OK | CONFIG.CVARS |
| `mp_buytime 0` | script OnActivate | OK | CONFIG.CVARS |
| `mp_death_drop_gun 0` | script OnActivate | OK | CONFIG.CVARS |
| `mp_weapons_allow_map_placed 1` | script OnActivate | OK | CONFIG.CVARS |
| `mp_free_armor 0` | script OnActivate | OK | CONFIG.CVARS |
| `mp_solid_teammates 1` | script OnActivate | OK | CONFIG.CVARS |
| `mp_give_player_c4 0` | script OnActivate | OK | CONFIG.CVARS |
| `bot_quota_mode fill` | script OnActivate | OK | when CONFIG.BOTS_ON (default true, step 4): bots fill the server and leave as humans join (was `bot_quota_mode normal` in CONFIG.CVARS) |
| `bot_quota <2 x FILL_PER_SIDE>` | script OnActivate | OK | when CONFIG.BOTS_ON: 16 (CONFIG.BOTS.FILL_PER_SIDE 8) |
| `bot_quota 0` | script OnActivate | OK | only when CONFIG.BOTS_ON is false |
| `bot_kick` | script OnActivate | OK | only when CONFIG.BOTS_ON is false |
| `say <text>` | script say() | OK | chat announcements (unlocks, roles) |

## Known missing
Rows that are MISSING on purpose or until a later remaster step; `tools/check_contract.py` lets exactly these through.
- `mortar_<tg>_K`: in the deployed map the 10 mortars are `prop_static` (`models/tw/ext/mortar_58mm` x5 CT, `models/tw/minenwerfer` x5 T).
  Since step 3 the script looks the name up once per round (`points.mortar`) and fires `SetAnimation fire` at the entity only when it
  exists, so nothing is fired at a missing name. The lookup is also the fallback when `mortarpit_<tg>_K` is missing, which it is not.
  Step 5 (`tools/patch_world_1.py`, in `out/` until deployed) makes them `prop_dynamic` `mortar_<tg>_K` on the `_dyn` twins with idle
  + fire: with `--vmap out/mg_trenchwarfare_patched.vmap --stage out/addon` the row is OK. Drop this entry once that map is deployed.

## Bots (remaster step 4)
No new entity names: bots use the posts, the blockers, the crew seats and the aircraft above. CONFIG names the script and the map share:
- `CONFIG.BOTS.AREAS`: points inside the opened areas (CT side; T mirrors x): woods clearing (605, 3930), (1110, 3700), (1110, 4150)
  at `tools/layout.py` ground + 8 (the last two = step 5's moved woods seeds), tunnel landing (2120, -3296, -252) (`layout.TUN_LANDING`,
  `TUN_FLOOR` + 8). Moved geometry there needs these moved too.
- `CONFIG.BOTS.NML_*` = `tools/check_play.py` `NML_X / NML_Y / NML_ZMIN` (no man's land box), `LOBBY_Z` -1500 (the briefing room is at z -2892).
- Map: `func_nav_markup` `tw_nav_no_N` (navProperty_NavGen NONAV, vis group tw_nav), made by `tools/patch_nav.py`; the WALKABLESEED
  markup of vis group tw_nav (made by `tools/patch_bots.py`, the woods four moved by step 5) is its template. Re-running the old
  `patch_bots.py` would delete every tw_nav node, the NONAV boxes too.

## Chat commands (script, not checked by the tool)
`!infantry` / `!rifle`, `!mortar` / `!artillery`, `!air` / `!pilot`, `!roles`, `!swap` (also SHIFT+E), `!pos`, `!uniform`, `!random`.
