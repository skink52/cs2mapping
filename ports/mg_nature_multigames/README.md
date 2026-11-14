# mg_nature_multigames

| | |
|---|---|
| Status | Built 9 Nov 2026, not yet tested in game or uploaded |
| Original map | Punky (from the map's own chat credit) |
| Source BSP | `mg_nature_multigames_v2.bsp` (from Briar's Dropbox, `CSGO/compiled maps/minigames`) |
| Imported | 2026-11-09 |
| How | autoport (one of five parallel workers) |

## History

- 2026-11-09: ported by autoport from Briar's v2 BSP (`--force`: `ports.check` matched `awp_multigames [briar]`, a different map).
- 2026-11-09: first stage C ran out of memory in `lighting.py` (one ~90M-voxel open exterior built as a 6 GB array while four other workers ran); the sampling now works in chunks with the same result (`tools/lighting.py`).
- 2026-11-09: 1 `game_round_end` (deathrun end: 4 EndRound_TerroristsWin / _CounterTerroristsWin) -> new `roundend` pass (script RoundEnd_0_T / _CT, FireWinCondition on `port_map_params`).
- 2026-11-09: the elevator's 3 `SetAnimationNoReset` outputs did nothing (CS2's prop_dynamic has only ...Looping / ...NotLooping): mapcheck `INPUT_RENAME` now makes them `SetAnimationNoResetNotLooping`.
- 2026-11-09: the 12 'missing' textures were all handled in stage C (11 rebuilt from CS:GO textures, inferno_water -> anubis_water_canal, mpa115 sky rebuilt).
- 2026-11-09: the first build spent over 20 min in vis while it overlapped another worker's build, so it was rebuilt with visfit_lean hints (look for pop-in). Held after it for `flower_barrel`'s gibs (HL2's flower_barrel_p1-p11, never in CS:GO): `gibfix.py --csgo` swapped in the generic wood chunks (backup `flower_barrel.vmdl.bak_gibfix`); entities rebuild 234 compiled, 0 failed.
- 2026-11-09: loading-screen and Steam description credit set to Punky.
- 2026-11-14: water cut into ≤384-u pieces (`watersplit`) and rebuilt, then **undone the same day**: the compiler's func_water "Failed to create physics hulls" warning, which the cut was meant to remove, turned out to be harmless (water with it works in game). vmap restored from `.bak_watersplit_20261114_*` and rebuilt entities-only; the cut version is kept as `.bak_prerevert_*`.

## What the cleanup did

(from the cleanup log in this folder)

- collapsed 6 prefabs into the map, world offsets kept: mg_nature_multigames_gameplay.vmap (329 nodes, 329 entities), mg_nature_multigames_environment_prefab.vmap (2877 nodes, 1224 entities), mg_nature_multigames_lighting_prefab.vmap (3 nodes, 3 entities), ...
- outputs restored that the importer dropped: 24 (e.g. trigger_multiple trapper_targetname_speed -> !activator.AddOutput(targetname trapper); trigger_multiple trapper_targetname_speed -> !self.Kill(); trigger_multiple runner_targetname -> !activator.AddOutp...
- 29 func_wall_toggle -> func_brush (Solidity Toggle, StartDisabled from "Starts Invisible"); 0 TurnOn/TurnOff inputs -> Enable/Disable
- game_player_equip negev_giver: CS:GO keys ['weapon_negev'] -> CS2 weapon0..weapon21 slots
- game_player_equip shotgun: CS:GO keys ['weapon_nova'] -> CS2 weapon0..weapon21 slots
- game_player_equip knife: CS:GO keys ['weapon_knife'] -> CS2 weapon0..weapon21 slots
- game_player_equip awp: CS:GO keys ['weapon_awp'] -> CS2 weapon0..weapon21 slots
- game_player_equip soccer_awp: CS:GO keys ['weapon_awp'] -> CS2 weapon0..weapon21 slots
- 3 Use inputs on game_player_equips -> TriggerForActivatedPlayer
- game_player_equip (unnamed) ran on every spawn in CS:GO (no "Use Only"): the io script now strips, then gives nothing on every spawn
- 3 trigger_push (speeds [600.0, 700.0, 999.0]; CS2 would keep accelerating) -> trigger_multiple + script push zones holding CS:GO speed (clamped to 3500); names/filters/Enable/Disable kept
- removed 1 point_servercommand; 36 Command outputs -> script Cmd_n (CS2 servers block point_servercommand)
- added point_servercommand port_servercommand + logic_auto port_logic_auto: OnMapSpawn -> mp_freezetime 0, mp_roundtime 10, sv_airaccelerate 2000, mp_solid_teammates 0
- removed 1 player_speedmod (dead in CS2); 2 ModifySpeed outputs -> script Speed_n (speeds [1.5, 3.0])
- removed env_sun '' (not in CS2; light_environment draws the sun)
- 51 func_physbox_multiplayer (gone in CS2) -> func_physbox
- trigsplit: 5 trigger_teleport/hurt/multiple spread over several meshes or pieces split into 9 extra single-mesh entities (same name, keyvalues and outputs)
- 1 entities had renderamt < 255 with rendermode Normal (ignored in CS:GO, see-through in CS2): renderamt 255
- fire: 33 env_fire -> 2 _fx particles (2 stock burning_fx, generated sizes -), 2 burn trigger_hurts (2/s); 0 skipped (unnamed, not Start On)
- fire: 2 env_spark -> 2 _fx spark particles (particles/port_spark/, vpcf66); env_sparks kept for their sound
- fire: 4 outputs added so the companions follow StartFire / Extinguish / Disable / Kill / spark inputs
- particles: 92 info_particle_system had a CS:GO particle system name; given CS2's particle of that name: explosion_c4_500 x2 -> particles/explosions_fx/explosion_c4_500.vpcf, water_splash_02_continuous x69 -> particles/water_impact/water_splash_02_continuo...
- 8 ambient_generics pointed at 8 new soundevents (naturemultigames.coolkids, naturemultigames.idols, naturemultigames.lala, naturemultigames.odesza, naturemultigames.pop, naturemultigames.teleport3, naturemultigames.waterfall_mediumloop05, naturemultigames...
- stock CS:GO sounds extracted from the CS:GO VPK into the addon: sounds/ambient/nature/waterfall_mediumloop05.wav
- looping sounds given a cue point (CS2 only loops wavs with markers; start taken from the smpl loop when there is one): sounds/ambient/nature/waterfall_mediumloop05.wav
- door sounds: 2 point_soundevents (naturemultigames.door_door_metal_thin_close2, naturemultigames.door_door_metal_thin_move1), started by the doors' OnOpen/OnClose (noise1) and OnFullyOpen/OnFullyClosed (noise2); 0 unnamed doors named port_door_N
- 6 static overlay materials -> csgo_static_overlay with translucency masks from the original alpha: assault_graf_decal01.vmat, assault_tres_decal01.vmat, train_security_decal_02.vmat, train_track_decal_a2.vmat, milleaves.vmat, offpapers02.vmat
- face texture scales: 7243 brush faces, 6742 matched to one VMF mapping; 9 matched: displacement (base face mapping); 18 matched: moved copy of a VMF brush (texture lock); 53 matched: rounded corner (<= 2.5u off the plane); 6660 matched: same plane; 2 matc...
- face texture scales: 8 sliver faces with no VMF side given their material's usual scale
- face texture mapping repaired: 6820 faces re-scaled / re-shifted from the VMF, 6561 faces with texture coordinates rewritten: baggage_concretefloora (48), cinderwall03b (3), concreteceiling003a (4), concretefloor001a (16), concretewall_handling01a (47), h...
- face texture scales: no known texture size (coordinates not checked): inferno_water
- splitfaces: 232 lit faces over 512x512 in 230 meshes cut into 2573 pieces on a 512 grid (one lightmap chart / probe sample per face: big floors baked blotchy)
- env_sky materials/skybox/mpa115.vmat: rebuilt from the six CS:GO faces
- restored 144 sky brushes (dropped by the importer) as toolsskybox meshes using materials/tools/toolsskybox.vmat
- visfit (48-unit voxels): 343.5 billion cubic units of playable air, 20.4 of it walkable band; hints 72 Medium, 75 Low, 54 Lower, 1 Lowest
- visfit: 48 of 144 sky shell meshes set to Exclude from Vis, 96 kept because they close playable air
- visfit: 200 Medium cells along 46568 long sight lines across gaps, so nothing pops out of view at the far end
- 0 env_laser + 1 env_beam (CS2 cannot spawn them) -> 1 never-solid func_brush beams between their end points (mutual laser pairs drawn once), coloured self-illuminated laser materials materials/lasers/laser_<rgb>.vmat; 0 TurnOn/TurnOff/Toggle -> Enable/Dis...
- relight: deleted 61 imported lights; rebuilt from the VMF 52 light -> light_omni2, 9 light_spot -> light_barn (colour, HDR intensity, range, cone); 0 Dynamic (start dark / switched / style)
- light_environment: Static -> Stationary (directlight 3), so the sun lights players and weapons
- added 2 stationary light_omni2 to sealed rooms with spawns / teleport destinations that had no light at all
- stationary lights: 5 of 61 lights switched Static -> Stationary (directlight 3) across 5 sealed compartments, ranges trimmed so no spot is inside more than 4; 4 of the compartments are open to sky (one stationary light each, on top of light_environment)
- 13 materials were alpha-tested / translucent in CS:GO but imported opaque - fixed with a mask from the texture alpha: metalbar001c (translucent), metalrail011a (translucent), awp_text (translucent), battleslider_text (translucent), deathrun_text (transluc...
- radar water (share of each water face drawn): inferno_water z-6118 0%, inferno_water z-4410 80%, inferno_water z-4376 86%, inferno_water z-4376 91%, waterfallfull_512_nrm_clear z-4024 0%, waterfallfull_512_nrm_clear z-4024 0%, waterfallfull_512_clear z-40...
- radar: rendered from geometry (2304 floor faces shaded by height, walls outlined) -> panorama/images/overheadmaps/mg_nature_multigames_radar_psd.png + game resource/overviews/mg_nature_multigames.txt (pos -13735 11299, scale 27.43)
- built 11 missing materials from the original CS:GO textures: carving01_cheap, carving03b_cheap, rockwall_blend, blendgrassdirt001a, valuesand20, citadel_metalwall060a, citadel_tilefloor016a, hr_metal_wood_a, metal_treadplate-ssbump, blendrocksgrass006a, i...
- CS:GO water materials (no CS2 equivalent shader) -> stock: materials/liquids/inferno_water.vmat -> materials/anubis/anubis_water_canal.vmat; materials/watersource/waterfall/waterfallfull_512_nrm_clear.vmat -> materials/anubis/anubis_water_canal.vmat
- $nocull materials -> F_RENDER_BACKFACES: foam
- added point_script mg_nature_multigames_io_script (maps/scripts/mg_nature_multigames_io.js)
- dropped I/O report (maps/mg_nature_multigames_dropped_io.txt): 54 .vmf owners with 335 outputs, 54 matched; 0 outputs missing with the target still there (probable losses), 0 with the target gone, 0 to !special targets; 41 handled by our own steps (script...
- static overlays: projection depth set to 8 on 33 overlays
- water: 19 water meshes -> 17 func_water; 6 underwater post_processing_volumes (lighting/postprocessing/postprocess_filmic_underwater.vpost, top 80 u below the surface); master post_processing_volume already there
- water: 60 underwater light_omni2 (map median brightness, range 512, no shadows) in water with no light inside
- probecover: added 20 light probe volumes around 63 static func_breakable / func_brush meshes that no volume fully covered: func_brush slider_3rd_stage_wall, func_brush deathrun_pit_blocker, func_brush spawn_pick_lag_block, func_brush battleslider_floor_cl...
- removed 1 game_round_end (not in CS2); 4 EndRound_* inputs -> script RoundEnd_<n>_<mode> (FireWinCondition, forced end as fallback)
- added info_map_parameters port_map_params (FireWinCondition target for the round ends)
- probes: every static func_breakable / func_brush is inside a light probe volume

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 12

## Scripts

- [`scripts/mg_nature_multigames_io.js`](scripts/mg_nature_multigames_io.js)

## Open / to check

- the importer leaves these out (they're on its exclusion list, mostly cosmetic): 9 point_spotlight (spotlight beams)
- trigsplit: split triggers keep their outputs on every piece; a counter fed by OnStartTouch/OnTrigger can now count once per piece touched
- env_fire without Don't Drop (CS:GO dropped it onto the floor below; CS2 flames/hurt stay where placed): cave_fire, battleslider_fire, battleslider_fire, battleslider_fire, battleslider_fire, battleslider_fire, battleslider_fire, battleslider_fire, battleslider_fire, battleslider_fire, battleslide...
- env_fire Enable inputs (CS:GO ignored StartFire while disabled; the particle/hurt start on every StartFire): battleslider_fire
- overlay materials not converted: materials/de_train/decalgraffiti042a.vmat (vmat not in addon); materials/de_train/train_security_decal_01.vmat (vmat not in addon); materials/decals/blacknumber1.vmat (vmat not in addon); materials/decals/blacknumber2.vmat (vmat not in addon); materials/decals/dec...
- 33 static overlays have a projection depth >= 32 (can show as a box with the overlay invisible) - stage_d overlaydepth sets them to 8
- faces still with an absurd texture scale (<0.01 or >8), left as imported: rockwall01 x628 (VMF: 0.0078x0.0078/0.0098x0.0048/0.0117x0.0056), metaltruss017a x2 (VMF: 0.0312x0.2969/0.125x0.2969/2.625x0.0039)
- face scales fixed but texture coordinates not rewritten (no CS:GO texture size): materials/liquids/inferno_water.vmat
- splitfaces: check the cut floors / ramps for seams after the bake
- vis: 1096 long sight lines got no Medium corridor (over the 200 cell limit): look for props popping out across long gaps
- vis: if anything pops in or out of view where players stand, change the nearest Lower hint to Low (or Low to Medium)
- relight: brightness scale (1000 lumens per 265 _light) is not checked against a real CS2 bake - compare a few rooms with CS:GO
- 63 static func_breakable / func_brush meshes are not fully inside an env_combined_light_probe_volume, so their lighting will be wrong (stage_d.py ... probecover adds volumes): func_brush slider_3rd_stage_wall, func_brush deathrun_pit_blocker, func_brush spawn_pick_lag_block, func_brush battleslid...
- the map has 61 physics props: if player pushes on them feel wrong in game (too easy or too hard for the prop's size), run the physpush step (run_pass.py ... physpush)
- vis: 1391 long sight lines got no Medium corridor (over the 200 cell limit): look for props popping out across long gaps
- underwater lights are a heuristic (Source water was lightmap-lit, CS2 water needs lights): check the water areas after the bake
- probecover: check the new probe volumes look right next to the existing ones
- roundend: check a scripted round end in game (FireWinCondition, then the forced fallback if a server blocks it)
- vis: 1437 long sight lines got no Medium corridor (over the 200 cell limit): look for props popping out across long gaps
- Entity check (mg_nature_multigames): 3 entities, inputs or switched lights converted to their CS2 equivalent: func_button elevator_button: OnPressed -> elevator_door_1.SetAnimationNoReset became SetAnimationNoResetNotLooping; trigger_once elevator_lucky: OnStartTouch -> elevator_door_2.SetAnimati...
- Lights (mg_nature_multigames): 2 moved off walls they would have blown out.
- Z-fighting (mg_nature_multigames): 265 small or same-material overlaps left (first: materials/de_cbble/grassfloor01.vmat | materials/de_cbble/grassfloor01.vmat at 2305 -3840 -1589, 61905 sq units overlap (minor) | materials/de_cbble/grassfloor01.vmat | materials/de_cbble/grassfloor01.vmat at 2305...
- Loading screen images: add at least two (autoport does not make them; docs/porting/pipeline.md, Loading-screen background images).
- Gib check: 0 models given generic CS:GO chunks, 5 missing gib models imported before the build.
- Some meshes got no physics hull: look for missing collisions. See logs\mg_nature_multigames_build.log
