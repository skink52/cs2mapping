# mg_arcs_multigames

| | |
|---|---|
| Status | Built 9 Nov 2026, not yet tested in game or uploaded |
| Original map | Arcaninesy (from the map's own chat credit) |
| Source BSP | `mg_arcs_multigames_csgo_v2_nc3.bsp (identical to the copy already in bspsrc-windows/mg maps/multigames)` (from Briar's Dropbox, `CSGO/compiled maps/minigames`) |
| Imported | 2026-11-09 |
| How | autoport (one of five parallel workers) |

## History

- 2026-11-09: ported by autoport from Briar's csgo_v2_nc3 BSP (`--force`: `ports.check` matched `awp_multigames [briar]`, a different map).
- 2026-11-09: 52 'missing' textures: the BSP packs the game-picker screenshots and signs with spaces in their names (`materials/MISC/128x128 arena screenie.vmt`) and the importer asked for underscore names. `pclocal.py root` now adds underscore copies of such embedded files; the `assets` pass then rebuilt 41, 3 already existed, and 8 were never packed at all (music-credits board, six quote signs, a skull) and now show `materials/effects/black.vmat` (backup `.vmap.bak_unpacked_*`).
- 2026-11-09: 8 display props on CS:GO weapon world models (7 models cs_mdl_import couldn't compile) -> CS2 weapon models (`weaponmodels`, with CS:GO -> CS2 renames: w_pist_223 -> usp_silencer, w_rif_m4a1 -> m4a4).
- 2026-11-09: 43 `env_global` + 43 logic_autos reading them give each mini-game a 3-round cooldown (play it: its button locks for the next three rounds). CS2 has no env_global, so nothing ever locked: new pass `envglobal` (`tools/envglobal.py`) keeps the states in the io script (Global_On/Off/Toggle_<n>, 100 inputs) and triggers the logic_autos, now logic_relays `port_globalauto_<k>`, at round start.
- 2026-11-09: removed 4 outputs that did nothing in CS:GO either (OnMapSpawn on an ambient_generic, a light/env_sprite carrying the godlike negev's OnPlayerPickup by copy-paste, ShowSprite on a func_breakable). The negev itself kept its outputs.
- 2026-11-09: the first build spent over 20 min in vis, so it was rebuilt with visfit_lean hints: 555 compiled, 0 failed (29 min 19 s). Loading-screen and Steam description credit set to Arcaninesy.

## What the cleanup did

(from the cleanup log in this folder)

- collapsed 6 prefabs into the map, world offsets kept: mg_arcs_multigames_gameplay.vmap (696 nodes, 696 entities), mg_arcs_multigames_environment_prefab.vmap (4224 nodes, 1114 entities), mg_arcs_multigames_lighting_prefab.vmap (3 nodes, 3 entities), mg_arc...
- outputs restored that the importer dropped: 135 (e.g. trigger_multiple  -> skatemovelinear.Open(); trigger_multiple  -> skatemovelinear.Close(); trigger_multiple  -> !activator.AddOutput(targetname Activator); trigger_multiple  -> !activator.AddOutput(tar...
- output targets fixed to the exact entity name (case): GIVE_ak->GIVE_AK, Spawnroomspotlight->spawnroomspotlight, give_ak->GIVE_AK, give_awp->GIVE_AWP, give_elite->GIVE_ELITE, give_knife2->GIVE_KNIFE2, give_m4a1->GIVE_M4A1, give_tmp->GIVE_TMP, give_usp->GIV...
- 17 func_wall_toggle -> func_brush (Solidity Toggle, StartDisabled from "Starts Invisible"); 0 TurnOn/TurnOff inputs -> Enable/Disable
- game_player_equip GIVE_AWP: CS:GO keys ['weapon_awp', 'weapon_knife'] -> CS2 weapon0..weapon21 slots
- game_player_equip GIVE_KNIFE2: CS:GO keys ['weapon_knife'] -> CS2 weapon0..weapon21 slots
- game_player_equip GIVE_SHOTGUN: CS:GO keys ['weapon_hegrenade', 'weapon_knife', 'weapon_nova'] -> CS2 weapon0..weapon21 slots
- game_player_equip GIVE_DEAGLE: CS:GO keys ['weapon_deagle', 'weapon_hegrenade', 'weapon_knife'] -> CS2 weapon0..weapon21 slots
- game_player_equip shotgun_boostknife: CS:GO keys ['weapon_nova'] -> CS2 weapon0..weapon21 slots
- game_player_equip GIVE_TMP: CS:GO keys ['weapon_fiveseven', 'weapon_hegrenade', 'weapon_knife', 'weapon_mp7'] -> CS2 weapon0..weapon21 slots
- game_player_equip GIVE_M4A1: CS:GO keys ['weapon_deagle', 'weapon_hegrenade', 'weapon_knife', 'weapon_m4a1'] -> CS2 weapon0..weapon21 slots
- game_player_equip GIVE_ELITE: CS:GO keys ['weapon_elite', 'weapon_hegrenade', 'weapon_knife'] -> CS2 weapon0..weapon21 slots
- game_player_equip GIVE_SCOUT: CS:GO keys ['weapon_hegrenade', 'weapon_knife', 'weapon_ssg08'] -> CS2 weapon0..weapon21 slots
- game_player_equip GIVE_USP: CS:GO keys ['weapon_hegrenade', 'weapon_knife', 'weapon_usp_silencer'] -> CS2 weapon0..weapon21 slots
- game_player_equip GIVE_KNIFE3: CS:GO keys ['weapon_hegrenade', 'weapon_knife'] -> CS2 weapon0..weapon21 slots
- game_player_equip GIVE_P90: CS:GO keys ['weapon_hegrenade', 'weapon_knife', 'weapon_p90'] -> CS2 weapon0..weapon21 slots
- game_player_equip GIVE_AK: CS:GO keys ['weapon_ak47', 'weapon_deagle', 'weapon_hegrenade', 'weapon_knife'] -> CS2 weapon0..weapon21 slots
- game_player_equip GIVE_DEAGLE_only: CS:GO keys ['weapon_deagle', 'weapon_hegrenade'] -> CS2 weapon0..weapon21 slots
- game_player_equip GIVE_KevlarHelmet: CS:GO keys ['item_assaultsuit'] -> CS2 weapon0..weapon21 slots
- 79 Use inputs on game_player_equips -> TriggerForActivatedPlayer
- item_* taken out of game_player_equip weapon slots (CS2 crashes on map load with them there), given by the io script instead: GIVE_KevlarHelmet (item_assaultsuit)
- game_player_equip (unnamed) ran on every spawn in CS:GO (no "Use Only"): the io script now strips, then gives nothing on every spawn
- 41 trigger_push (speeds [300.0, 500.0, 777.0, 800.0, 900.0, 2000.0]; CS2 would keep accelerating) -> trigger_multiple + script push zones holding CS:GO speed (clamped to 3500); names/filters/Enable/Disable kept
- 1 up trigger_push over a forward push kept as real trigger_push at 0.0571429 x the CS:GO speed
- removed 1 point_servercommand; 144 Command outputs -> script Cmd_n (CS2 servers block point_servercommand)
- added point_servercommand port_servercommand + logic_auto port_logic_auto: OnMapSpawn -> mp_freezetime 0, mp_roundtime 10, sv_airaccelerate 2000, mp_solid_teammates 0
- removed 1 player_speedmod (dead in CS2); 4 ModifySpeed outputs -> script Speed_n (speeds [1.5])
- trigsplit: 31 trigger_teleport/hurt/multiple spread over several meshes or pieces split into 63 extra single-mesh entities (same name, keyvalues and outputs)
- rendermode: 4 entities given CS2 render mode names (CS2 has only kRenderNormal / kRenderTransAlpha / kRenderNone): env_spritetrail 5 -> kRenderTransAlpha x4
- 15 ambient_generics pointed at 15 new soundevents (arcsmultigames.alan_walker___faded, arcsmultigames.bell1, arcsmultigames.body_medium_break2, arcsmultigames.calvin_harris_feel_so_close, arcsmultigames.come_out_and_fight_like_a_man, arcsmultigames.godlik...
- stock CS:GO sounds extracted from the CS:GO VPK into the addon: sounds/player/orch_hit_csharp_short.wav
- wavs re-encoded to 16-bit PCM: come_out_and_fight_like_a_man.wav (PCM 8-bit -> 16-bit PCM)
- 1 Source 1 soundscript names used by entities defined as same-named soundevents: DoorSound.DefaultMove
- soundscript waves copied into the addon from the map's packed files / CS:GO VPK: sounds/doors/default_move.wav
- door sounds: 19 point_soundevents (DoorSound.DefaultMove), started by the doors' OnOpen/OnClose (noise1) and OnFullyOpen/OnFullyClosed (noise2); 2 unnamed doors named port_door_N
- door sounds: 19 CS:GO doors had no move sound and played CS:GO's default (DoorSound.DefaultMove / RotDoorSound.DefaultMove: doors/default_move.wav at volume 0.2); they get it too
- 6 static overlay materials -> csgo_static_overlay with translucency masks from the original alpha: train_abombsite_02.vmat, train_bbombsite_02.vmat, train_bombsite_arrow_02.vmat, 256x128 lastthanks.vmat, 256x128 name wall.vmat, 256x256 special thanks.vmat
- face texture scales: 19486 brush faces, 19426 matched to one VMF mapping; 24 matched: moved copy of a VMF brush (texture lock); 1 matched: rounded corner (<= 2.5u off the plane); 19401 matched: same plane; 55 no VMF side on the same plane + material; 5 ov...
- face texture mapping repaired: 19431 faces re-scaled / re-shifted from the VMF, 19154 faces with texture coordinates rewritten: arcy_blue_a-03 (48), arcy_blue_a-05 (117), arcy_blue_a-06 (42), arcy_blue_b-02 (28), arcy_blue_c-05 (145), arcy_blue_c-06 (182)...
- face texture scales: no known texture size (coordinates not checked): 128x128_orange_coral_tile, 128x128_random_text, 128x16_arena_text2, 128x16_arena_text3, 128x16_blinddeagle_text, 128x16_boosterknife_text, 128x16_breakbox_text, 128x16_bunnyhop_text, 12...
- displaybrush: 2 never-solid, never-changing func_brush/func_illusionary flush in a world surface -> world meshes with Physics Type None (bake with the surface)
- splitfaces: 358 lit faces over 512x512 in 261 meshes cut into 3200 pieces on a 512 grid (one lightmap chart / probe sample per face: big floors baked blotchy)
- env_sky materials/skybox/mpa110.vmat: rebuilt from the six CS:GO faces
- restored 76 sky brushes (dropped by the importer) as toolsskybox meshes using materials/tools/toolsskybox.vmat
- visfit (24-unit voxels): 157.7 billion cubic units of playable air, 23.7 of it walkable band; hints 147 Medium, 262 Low, 209 Lower, 1 Lowest
- visfit: 28 of 76 sky shell meshes set to Exclude from Vis, 48 kept because they close playable air
- visfit: 200 Medium cells along 241520 long sight lines across gaps, so nothing pops out of view at the far end
- 30 move_rope / keyframe_rope (CS2 drops them) -> 29 cable_dynamic (rope_braid_1 for ropes, cable.vmat for cables, radius = Width / 4, Bezier sag from Slack or the default rule, up to 43 u) + 0 rope end caps
- relight: deleted 867 imported lights; rebuilt from the VMF 859 light -> light_omni2, 8 light_spot -> light_barn (colour, HDR intensity, range, cone); 0 Dynamic (start dark / switched / style)
- light_environment: Static -> Stationary (directlight 3), so the sun lights players and weapons
- added 13 stationary light_omni2 to sealed rooms with spawns / teleport destinations that had no light at all
- stationary lights: 21 of 867 lights switched Static -> Stationary (directlight 3) across 17 sealed compartments, ranges trimmed so no spot is inside more than 4; 12 of the compartments are open to sky (one stationary light each, on top of light_environment)
- 2 materials were alpha-tested / translucent in CS:GO but imported opaque - fixed with a mask from the texture alpha: unbreakable (translucent), arrows_cross (translucent)
- radar: rendered from geometry (4754 floor faces shaded by height, walls outlined) -> panorama/images/overheadmaps/mg_arcs_multigames_radar_psd.png + game resource/overviews/mg_arcs_multigames.txt (pos -4067 11240, scale 19.13)
- built 6 missing materials from the original CS:GO textures: arcy_checked_magenta, arcy_magenta_a-05, arcy_magenta_b-01, arcy_magenta_b-07, arcy_magenta_c-04, arcy_magenta_d-01
- materials missing everywhere swapped for the closest stock CS2 ones: materials/course_map/black.vmat -> materials/effects/black.vmat; materials/misc/arcanine.vmat -> materials/particle/rain.vmat
- $additive materials moved to csgo_unlitgeneric (F_BLEND_MODE 4, additive): 32x32_sprite_replicant_texture
- $nocull materials -> F_RENDER_BACKFACES: 32x32_sprite_replicant_texture
- added point_script mg_arcs_multigames_io_script (maps/scripts/mg_arcs_multigames_io.js)
- dropped I/O report (maps/mg_arcs_multigames_dropped_io.txt): 285 .vmf owners with 1307 outputs, 284 matched; 1 outputs missing with the target still there (probable losses), 4 with the target gone, 2 to !special targets; 227 handled by our own steps (scri...
- static overlays: projection depth set to 8 on 35 overlays
- probecover: added 20 light probe volumes around 23 static func_breakable / func_brush meshes that no volume fully covered: func_brush nope, func_brush nope, func_brush nope, func_brush nope, func_brush nope, func_brush nope, func_brush nope, func_brush no...
- built 41 missing materials from the original CS:GO textures: 128x128_awp_screenie, 128x128_knife_screenie, 128x128_orange_coral_tile, 128x128_arena_screenie, 128x128_blinddeagle_screenshot, 128x128_boosterknife_screenie, 128x128_breakbox_screenie, 128x128...
- weaponmodels: 6 props on CS:GO weapon models -> CS2 weapon models (models/weapons/w_pist_elite.vmdl x1 -> weapons/models/elite/weapon_pist_elite.vmdl, models/weapons/w_rif_ak47.vmdl x1 -> weapons/models/ak47/weapon_rif_ak47.vmdl, models/weapons/w_smg_mp7....
- envglobal: removed 43 env_global (not in CS2); 100 TurnOn/TurnOff/Toggle -> script Global_<op>_<n>; 43 logic_autos reading a global state -> logic_relays port_globalauto_<k> the script triggers at round start while the state is on (43 states)
- probes: every static func_breakable / func_brush is inside a light probe volume

## Import report

(`post_import_cleanup.py` report in this folder)

- Models - failed to compile: 7
- Textures - fully missing, no source found anywhere: 52

## Scripts

- [`scripts/mg_arcs_multigames_io.js`](scripts/mg_arcs_multigames_io.js)

## Open / to check

- **Music rights:** the map packs commercial songs (Alan Walker, Calvin Harris, Halsey, Imagine Dragons, Marshmello, Rich Edwards, The Script, Vicetone) as ambient_generic music. Decide before a Workshop upload whether to keep, replace or drop them (copyright takedown risk).
- 8 signs were never packed in the BSP (music credits, six quotes, a skull) and are black panels: ask the author or Briar for the textures if they matter.

- 3 VMF entities with outputs could not be matched 1:1 in the vmap - their outputs were not checked
- the importer leaves these out (they're on its exclusion list, mostly cosmetic): 56 point_spotlight (spotlight beams), 1 func_dustmotes (dust motes)
- 1 up pushes over forward pushes are real trigger_push, scaled from the one case tuned by hand (ba_jail_keimusho 700 -> 40): check the jumps work in game
- chat messages use "say" from cs_script ServerCommand - if a server blocks it the messages just will not show
- 4 env_spritetrail (gone in CS2, cosmetic trails) - left out; a trail particle would replace them
- trigsplit: split triggers keep their outputs on every piece; a counter fed by OnStartTouch/OnTrigger can now count once per piece touched
- ambient_generic music8 is set to loop but sounds/blogger/maps/arcs/music/calvin_harris_feel_so_close.mp3 has no loop cue points, so it will play once in CS2
- ambient_generic music7 is set to loop but sounds/blogger/maps/arcs/music/vicetone_-_nevada_feat._cozi_zuehlsdorff_.mp3 has no loop cue points, so it will play once in CS2
- ambient_generic music6 is set to loop but sounds/blogger/maps/arcs/music/imagine_dragons_-_radioactive.mp3 has no loop cue points, so it will play once in CS2
- ambient_generic music1 is set to loop but sounds/blogger/maps/arcs/music/alan_walker_-_faded.mp3 has no loop cue points, so it will play once in CS2
- ambient_generic music5 is set to loop but sounds/blogger/maps/arcs/music/rich_edwards_-_where_i_ll_be_waiting.mp3 has no loop cue points, so it will play once in CS2
- ambient_generic music4 is set to loop but sounds/blogger/maps/arcs/music/the_script_-_hall_of_fame_lyric_ft._will.i.am.mp3 has no loop cue points, so it will play once in CS2
- ambient_generic music3 is set to loop but sounds/blogger/maps/arcs/music/marshmello_-_alone_official_music_video_.mp3 has no loop cue points, so it will play once in CS2
- ambient_generic music2 is set to loop but sounds/blogger/maps/arcs/music/halsey_-_new_americana_olwik_deep_house_remix_.mp3 has no loop cue points, so it will play once in CS2
- overlay materials not converted: materials/misc/256x256 music credits.vmat (vmat not in addon); materials/misc/64x64 saying_helen_keller.vmat (vmat not in addon); materials/misc/64x64 saying_henry_thoreau.vmat (vmat not in addon); materials/misc/64x64 saying_lucille_ball.vmat (vmat not in addon);...
- 35 static overlays have a projection depth >= 32 (can show as a box with the overlay invisible) - stage_d overlaydepth sets them to 8
- placeholder static overlays left alone, no CS:GO texture size: materials/misc/256x256 music credits.vmat, materials/misc/64x64 saying_helen_keller.vmat, materials/misc/64x64 saying_henry_thoreau.vmat, materials/misc/64x64 saying_lucille_ball.vmat, materials/misc/64x64 saying_mark_twain.vmat, mate...
- faces still with an absurd texture scale (<0.01 or >8), left as imported: 32x32_sprite_replicant_texture x172 (VMF: 10x10), arcy_greyscale_24 x14 (VMF: 0.25x0.25/10x10/0.2498x0.25), arcy_checked_orange x4 (VMF: 0.25x0.25), arcy_cblue_a-04 x2 (VMF: 0.25x0.25/0.125x0.125)
- face scales fixed but texture coordinates not rewritten (no CS:GO texture size): materials/course_map/black.vmat, materials/grids/128x128_orange_coral_tile.vmat, materials/misc/128x128_random_text.vmat, materials/misc/128x16_arena_text2.vmat, materials/misc/128x16_arena_text3.vmat, materials/misc...
- splitfaces: check the cut floors / ramps for seams after the bake
- 21 non-box sky brushes in the VMF were not rebuilt as moondomes
- vis: 4030 long sight lines got no Medium corridor (over the 200 cell limit): look for props popping out across long gaps
- vis: if anything pops in or out of view where players stand, change the nearest Lower hint to Low (or Low to Medium)
- ropes rebuilt as cable_dynamic (29): check the sag, and that each end cap sits where the rope meets a surface
- ropes whose NextKey target is missing, not rebuilt: keyframe27
- relight: brightness scale (1000 lumens per 265 _light) is not checked against a real CS2 bake - compare a few rooms with CS:GO
- 23 static func_breakable / func_brush meshes are not fully inside an env_combined_light_probe_volume, so their lighting will be wrong (stage_d.py ... probecover adds volumes): func_brush nope, func_brush nope, func_brush nope, func_brush nope, func_brush nope, func_brush nope, func_brush nope, fu...
- check the substituted materials look right: materials/course_map/black.vmat -> materials/effects/black.vmat; materials/misc/arcanine.vmat -> materials/particle/rain.vmat
- materials still missing: materials/grids/128x128_awp_screenie.vmat (no CS:GO source and no similar stock CS2 material); materials/grids/128x128_knife_screenie.vmat (no CS:GO source and no similar stock CS2 material); materials/grids/128x128_orange_coral_tile.vmat (no CS:GO source and no similar s...
- 3 outputs from the .vmf are missing in the vmap while their target is still there (OnPlayerPickup->Enable x1, OnPlayerPickup->AddOutput x1, OnPlayerPickup->Alpha x1): see maps/mg_arcs_multigames_dropped_io.txt
- 1 placeholder static overlays had no infodecal/info_overlay of the same material within 40 units in the VMF - size them by hand (scale = size/2)
- vis: 4003 long sight lines got no Medium corridor (over the 200 cell limit): look for props popping out across long gaps
- probecover: check the new probe volumes look right next to the existing ones
- materials still missing: materials/misc/256x256 music credits.vmat (no CS:GO source and no similar stock CS2 material); materials/misc/64x64 saying_helen_keller.vmat (no CS:GO source and no similar stock CS2 material); materials/misc/64x64 saying_henry_thoreau.vmat (no CS:GO source and no similar...
- weaponmodels: CS2 weapon models are a different size/pivot from CS:GO's: check the repointed display props sit right
- weaponmodels: no CS2 weapon model for models/weapons/w_pist_223.vmdl, models/weapons/w_rif_m4a1.vmdl
- envglobal: check the global-state logic over a few rounds in game (states kept by the io script across round restarts)
- 11 placeholder static overlays had no infodecal/info_overlay of the same material within 40 units in the VMF - size them by hand (scale = size/2)
- vis: 4004 long sight lines got no Medium corridor (over the 200 cell limit): look for props popping out across long gaps
- vmdlfix.py named 33 empty bodygroup choices, so those models compile now. See C:\source1\cs2port_w4\work\autoport_runs\20261109_014723\mg_arcs_multigames_vmdlfix.log
- Lights (mg_arcs_multigames): 12 moved off walls they would have blown out.
- Lights (mg_arcs_multigames): 41 sit close to a wall but couldn't move without crossing a face: look for bright spots.
- Z-fighting (mg_arcs_multigames): 27 small or same-material overlaps left (first: materials/arcy_tiles/arcy_cyan_c-04.vmat | materials/arcy_tiles/arcy_cyan_c-04.vmat at 7040 2400 64, 28672 sq units overlap (minor) | materials/arcy_tiles/arcy_yellow_b-01.vmat | materials/arcy_tiles/arcy_yellow_b-01...
- Loading screen images: add at least two (autoport does not make them; docs/porting/pipeline.md, Loading-screen background images).
- Gib check: 1 models given generic CS:GO chunks, 5 missing gib models imported before the build.
- The first build spent over 20 minutes in vis, so vis hints were replaced with visfit_lean and it was rebuilt: look for pop-in.
- Some meshes got no physics hull: look for missing collisions. See logs\mg_arcs_multigames_build.log
