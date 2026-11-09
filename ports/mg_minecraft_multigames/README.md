# mg_minecraft_multigames

| | |
|---|---|
| Status | Built 9 Nov 2026, not yet tested in game or uploaded |
| Original map | Blogger(Dog), with a level by DexKekcuk (from the map's own chat credits) |
| Source BSP | `mg_minecraft_multigames_v4_nc2.bsp` (from Briar's Dropbox, `CSGO/compiled maps/minigames`) |
| Imported | 2026-11-09 |
| How | autoport (one of five parallel workers) |

## History

- 2026-11-09: ported by autoport from Briar's v4_nc2 BSP. Prep first refused it: `ports.check` matched `awp_multigames [briar]` ("multigames" is a substring), a different map, so it ran with `--force`.
- 2026-11-09: held for 2 `game_round_end` (EndRound_Draw from a math_counter; the other unnamed and never fired) and a `player_weaponstrip` (no CS2 class): new stage D pass `roundend` (`tools/roundend.py`) moved them into the io script (RoundEnd_0_Draw, WeaponStrip) and added `info_map_parameters port_map_params` for FireWinCondition.
- 2026-11-09: 3 display props used CS:GO's w_snip_awp / w_pist_deagle, which cs_mdl_import can't compile: new pass `weaponmodels` points them at CS2's weapons/models/awp and deagle models and fixes Hammer's asset list.
- 2026-11-09: the 2 'missing textures' were stale (lava_moving.vmat was built in stage C, the minecraft sky rebuilt as a panorama).
- 2026-11-09: first build lacked the wood gibs (the parallel worker folder had no run_fixrefs.bat); rebuilt with them: 365 compiled, 0 failed (12 min 24 s).
- 2026-11-09: loading-screen credit set to the original authors (`game/csgo_addons/mg_minecraft_multigames/maps/mg_minecraft_multigames.txt`).

## What the cleanup did

(from the cleanup log in this folder)

- collapsed 6 prefabs into the map, world offsets kept: mg_minecraft_multigames_gameplay.vmap (672 nodes, 672 entities), mg_minecraft_multigames_environment_prefab.vmap (3155 nodes, 260 entities), mg_minecraft_multigames_lighting_prefab.vmap (3 nodes, 3 ent...
- outputs restored that the importer dropped: 105 (e.g. trigger_teleport  -> !activator.SetDamageFilter(dmgdef); trigger_multiple  -> !activator.SetDamageFilter(damage_filter_zero); trigger_multiple  -> !activator.SetDamageFilter(damage_filter_zero); trigge...
- 8 func_wall_toggle -> func_brush (Solidity Toggle, StartDisabled from "Starts Invisible"); 0 TurnOn/TurnOff inputs -> Enable/Disable
- game_player_equip weapon_fiveseven: CS:GO keys ['weapon_fiveseven'] -> CS2 weapon0..weapon21 slots
- game_player_equip weapon_p90: CS:GO keys ['weapon_p90'] -> CS2 weapon0..weapon21 slots
- game_player_equip longjump_give: CS:GO keys ['weapon_awp', 'weapon_deagle', 'weapon_knife'] -> CS2 weapon0..weapon21 slots
- game_player_equip weapon_nova: CS:GO keys ['weapon_nova'] -> CS2 weapon0..weapon21 slots
- game_player_equip weapon_awp: CS:GO keys ['weapon_awp'] -> CS2 weapon0..weapon21 slots
- game_player_equip weapon_deagle: CS:GO keys ['weapon_deagle'] -> CS2 weapon0..weapon21 slots
- game_player_equip weapon_m4: CS:GO keys ['weapon_m4a1'] -> CS2 weapon0..weapon21 slots
- game_player_equip weapon_knife: CS:GO keys ['weapon_knife'] -> CS2 weapon0..weapon21 slots
- 32 Use inputs on game_player_equips -> TriggerForActivatedPlayer
- game_player_equip (unnamed) ran on every spawn in CS:GO (no "Use Only"): the io script now strips, then gives nothing on every spawn
- 3 trigger_push (speeds [500.0, 700.0]; CS2 would keep accelerating) -> trigger_multiple + script push zones holding CS:GO speed (clamped to 3500); names/filters/Enable/Disable kept
- removed 1 point_servercommand; 85 Command outputs -> script Cmd_n (CS2 servers block point_servercommand)
- added point_servercommand port_servercommand + logic_auto port_logic_auto: OnMapSpawn -> mp_freezetime 0, mp_roundtime 10, sv_airaccelerate 2000, mp_solid_teammates 0
- removed 2 game_score (not in CS2); 2 ApplyScore -> script Score_n
- 5 func_physbox_multiplayer (gone in CS2) -> func_physbox
- trigsplit: 45 trigger_teleport/hurt/multiple spread over several meshes or pieces split into 51 extra single-mesh entities (same name, keyvalues and outputs)
- rendermode: 16 entities given CS2 render mode names (CS2 has only kRenderNormal / kRenderTransAlpha / kRenderNone): env_explosion 5 -> kRenderTransAlpha x16
- 17 ambient_generics pointed at 15 new soundevents (minecraftmultigames.aero_chord___4u, minecraftmultigames.creeperboom, minecraftmultigames.death, minecraftmultigames.eminence_supermans, minecraftmultigames.explode1, minecraftmultigames.explode3, minecra...
- door sounds: 1 point_soundevents (minecraftmultigames.door_metal_door_open_01), started by the doors' OnOpen/OnClose (noise1) and OnFullyOpen/OnFullyClosed (noise2); 1 unnamed doors named port_door_N
- face texture scales: 13449 brush faces, 13114 matched to one VMF mapping; 13114 matched: same plane; 7 no VMF side on the same plane + material; 328 overlapping VMF brushes with different mappings (left as imported)
- face texture mapping repaired: 13442 faces re-scaled / re-shifted from the VMF, 13442 faces with texture coordinates rewritten: blogbymap (2), shot3 (12), shot5 (36), dev_measurewall01a (6), dev_water2 (4), bedrock (4), chest_back (23), chest_front (11), ...
- splitfaces: 73 lit faces over 512x512 in 63 meshes cut into 718 pieces on a 512 grid (one lightmap chart / probe sample per face: big floors baked blotchy)
- env_sky materials/skybox/minecraft.vmat: rebuilt from the six CS:GO faces
- visfit (48-unit voxels): 30.5 billion cubic units of playable air, 6.3 of it walkable band; hints 57 Medium, 79 Low, 48 Lower, 1 Lowest
- visfit: 200 Medium cells along 72566 long sight lines across gaps, so nothing pops out of view at the far end
- relight: deleted 192 imported lights; rebuilt from the VMF 192 light -> light_omni2, 0 light_spot -> light_barn (colour, HDR intensity, range, cone); 0 Dynamic (start dark / switched / style)
- light_environment: Static -> Stationary (directlight 3), so the sun lights players and weapons
- added 3 stationary light_omni2 to sealed rooms with spawns / teleport destinations that had no light at all
- stationary lights: 16 of 192 lights switched Static -> Stationary (directlight 3) across 12 sealed compartments, ranges trimmed so no spot is inside more than 4
- 8 materials were alpha-tested / translucent in CS:GO but imported opaque - fixed with a mask from the texture alpha: blogbymap (translucent), fire (alpha test), glass (alpha test), ladder (alpha test), portal (alpha test), rail (alpha test), trapdoor (alp...
- radar water (share of each water face drawn): dev_water2 z-871 58%
- radar: rendered from geometry (1924 floor faces shaded by height, walls outlined) -> panorama/images/overheadmaps/mg_minecraft_multigames_radar_psd.png + game resource/overviews/mg_minecraft_multigames.txt (pos -5192 12171, scale 21.29)
- built 4 missing materials from the original CS:GO textures: dev_measurewall01a, cobblestone_mossy, lava_moving, stonebricks_mossy
- %compilewater materials (CS:GO water, see-through) -> F_TRANSLUCENT, opacity 0.55, back faces drawn: lava, lava_moving
- $selfillum materials -> F_SELF_ILLUM (mask from the texture alpha): tnt_bottom_explode, tnt_side_explode, tnt_top_explode
- added point_script mg_minecraft_multigames_io_script (maps/scripts/mg_minecraft_multigames_io.js)
- dropped I/O report (maps/mg_minecraft_multigames_dropped_io.txt): 174 .vmf owners with 1065 outputs, 174 matched; 0 outputs missing with the target still there (probable losses), 0 with the target gone, 0 to !special targets; 119 handled by our own steps ...
- probecover: added 28 light probe volumes around 33 static func_breakable / func_brush meshes that no volume fully covered: func_brush toggle_breadge_awp, func_brush boss_toggle, func_brush nope, func_brush nope, func_brush nope, func_brush toggel_spawn_fi...
- removed 2 game_round_end (not in CS2); 2 EndRound_* inputs -> script RoundEnd_<n>_<mode> (FireWinCondition, forced end as fallback); never triggered, dropped: (unnamed)
- added info_map_parameters port_map_params (FireWinCondition target for the round ends)
- removed 1 player_weaponstrip (not in CS2); 1 Strip inputs -> script WeaponStrip (strips the activator)
- weaponmodels: 3 props on CS:GO weapon models -> CS2 weapon models (models/weapons/w_pist_deagle.vmdl x2 -> weapons/models/deagle/weapon_pist_deagle.vmdl, models/weapons/w_snip_awp.vmdl x1 -> weapons/models/awp/weapon_snip_awp.vmdl)

## Import report

(`post_import_cleanup.py` report in this folder)

- Models - failed to compile: 2
- Textures - fully missing, no source found anywhere: 2

## Scripts

- [`scripts/mg_minecraft_multigames_io.js`](scripts/mg_minecraft_multigames_io.js)

## Open / to check

- chat messages use "say" from cs_script ServerCommand - if a server blocks it the messages just will not show
- trigsplit: split triggers keep their outputs on every piece; a counter fed by OnStartTouch/OnTrigger can now count once per piece touched
- ambient_generic sounds not in the addon (stock CS:GO sounds or not packed in the BSP): sounds/mc_sound_multi/boss/scream2.vsnd, sounds/mc_sound_multi/boss/scream5.vsnd
- splitfaces: check the cut floors / ramps for seams after the bake
- vis: 221 long sight lines got no Medium corridor (over the 200 cell limit): look for props popping out across long gaps
- vis: if anything pops in or out of view where players stand, change the nearest Lower hint to Low (or Low to Medium)
- relight: brightness scale (1000 lumens per 265 _light) is not checked against a real CS2 bake - compare a few rooms with CS:GO
- 33 static func_breakable / func_brush meshes are not fully inside an env_combined_light_probe_volume, so their lighting will be wrong (stage_d.py ... probecover adds volumes): func_brush toggle_breadge_awp, func_brush boss_toggle, func_brush nope, func_brush nope, func_brush nope, func_brush togg...
- the map has 23 physics props: if player pushes on them feel wrong in game (too easy or too hard for the prop's size), run the physpush step (run_pass.py ... physpush)
- probecover: check the new probe volumes look right next to the existing ones
- roundend: check a scripted round end in game (FireWinCondition, then the forced fallback if a server blocks it)
- weaponmodels: CS2 weapon models are a different size/pivot from CS:GO's: check the repointed display props sit right
- weaponmodels: no CS2 weapon model for models/weapons/w_knife_m9_bay.vmdl
- vmdlfix.py named 8 empty bodygroup choices, so those models compile now. See C:\source1\cs2port_w2\work\autoport_runs\20261109_014625\mg_minecraft_multigames_vmdlfix.log
- Entity check (mg_minecraft_multigames): 124 outputs to names nothing has (removed: they did nothing in CS:GO either): logic_case case3: OnCase11 -> start_tel43.Enable, but nothing is called start_tel43 (removed); logic_case surv_case: OnCase01 -> surv_relay_door_close.Trigger, but nothing is call...
- Z-fighting (mg_minecraft_multigames): 89 fully covered faces set to toolsnodraw, as vbsp would have dropped them; 5 smaller faces moved 0.25 units forward where two materials overlapped.
- Z-fighting (mg_minecraft_multigames): 5 faces were moved 0.25 units to stop flicker; look at them in game (tools/zfight.py lists where).
- Lights (mg_minecraft_multigames): 32 moved off walls they would have blown out.
- Z-fighting (mg_minecraft_multigames): 96 small or same-material overlaps left (first: materials/ennergy/minecraft/stone_slab.vmat | materials/ennergy/minecraft/stone_slab.vmat at 4800 2287 3925, 16384 sq units overlap (minor) | materials/ennergy/minecraft/stone_slab.vmat | materials/ennergy/minec...
- Loading screen images: add at least two (autoport does not make them; docs/porting/pipeline.md, Loading-screen background images).
- Gib check: 0 models given generic CS:GO chunks, 5 missing gib models imported before the build.
- Some meshes got no physics hull: look for missing collisions. See logs\mg_minecraft_multigames_build.log
