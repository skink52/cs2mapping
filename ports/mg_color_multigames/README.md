# mg_color_multigames

| | |
|---|---|
| Status | Built 9 Nov 2026, not yet tested in game or uploaded |
| Original map | xGrandx (from the map's own chat credit) |
| Source BSP | `mg_color_multigames_rc.bsp` (from Briar's Dropbox, `CSGO/compiled maps/minigames`) |
| Imported | 2026-11-09 |
| How | autoport (one of five parallel workers) |

## History

- 2026-11-09: ported by autoport from Briar's rc BSP (`--force`: `ports.check` matched `awp_multigames [briar]`, a different map; `mg_color_dev`, already ported, is a different map too).
- 2026-11-09: env_sky `mikis_hdr`: its six faces were never packed in the BSP, so the sky couldn't be rebuilt; set to CS2's stock `materials/skybox/sky_cs15_daylight01_hdr.vmat` (the map's sun is plain white at pitch -55). Backup `mg_color_multigames.vmap.bak_sky_*`.
- 2026-11-09: the importer dropped 3 of the 23 `!activator Color` team-tint outputs on the spawn triggers: new stage D pass `playercolor` (`tools/playercolor.py`) re-adds them as script `Color_<r>_<g>_<b>` (SetColor). Its first run also doubled the 20 the importer kept; fixed and the duplicates removed.
- 2026-11-09: `env_cascade_light` and 6 `env_spritetrail` (blue trails on `knife_spinner`) have no CS2 class and drew nothing: mapcheck now removes them (`SAFE_REMOVE` covers classes no CS2 fgd defines). `postprocess_controller` (CS:GO bloom/vignette) is known-gone.
- 2026-11-09: built: 906 compiled, 0 failed (14 min 39 s). Loading-screen and Steam description credit set to xGrandx.

## What the cleanup did

(from the cleanup log in this folder)

- collapsed 6 prefabs into the map, world offsets kept: mg_color_multigames_gameplay.vmap (376 nodes, 376 entities), mg_color_multigames_environment_prefab.vmap (4092 nodes, 677 entities), mg_color_multigames_lighting_prefab.vmap (3 nodes, 3 entities), mg_c...
- outputs restored that the importer dropped: 102 (e.g. logic_auto  -> tonemap.SetAutoExposureMin(0.8); logic_auto  -> tonemap.SetAutoExposureMax(1.5); logic_auto  -> tonemap.SetTonemapRate(0.35); logic_timer skate -> player.AddOutput(basevelocity 0 0 800);...
- output targets fixed to the exact entity name (case): Squash_case->squash_case, squash_timer->Squash_timer
- 2 func_wall_toggle -> func_brush (Solidity Toggle, StartDisabled from "Starts Invisible"); 0 TurnOn/TurnOff inputs -> Enable/Disable
- game_player_equip (unnamed): CS:GO keys ['item_kevlar'] -> CS2 weapon0..weapon21 slots
- game_player_equip weapon_awp_gpe: CS:GO keys ['weapon_awp'] -> CS2 weapon0..weapon21 slots
- game_player_equip weapon_knife_gpe: CS:GO keys ['weapon_knife'] -> CS2 weapon0..weapon21 slots
- game_player_equip weapon_m3_gpe: CS:GO keys ['weapon_nova'] -> CS2 weapon0..weapon21 slots
- game_player_equip weapon_m249_gpe: CS:GO keys ['weapon_negev'] -> CS2 weapon0..weapon21 slots
- game_player_equip weapon_hegrenade_gpe: CS:GO keys ['weapon_hegrenade'] -> CS2 weapon0..weapon21 slots
- game_player_equip weapon_deagle_gpe: CS:GO keys ['weapon_deagle'] -> CS2 weapon0..weapon21 slots
- 30 Use inputs on game_player_equips -> TriggerForActivatedPlayer
- item_* taken out of game_player_equip weapon slots (CS2 crashes on map load with them there), given by the io script instead: unnamed (item_kevlar)
- game_player_equip (unnamed) ran on every spawn in CS:GO (no "Use Only"): the io script now gives item_kevlar on every spawn
- 16 trigger_push (speeds [400.0, 500.0, 600.0, 1000.0, 2000.0]; CS2 would keep accelerating) -> trigger_multiple + script push zones holding CS:GO speed (clamped to 3500); names/filters/Enable/Disable kept
- removed 1 point_servercommand; 64 Command outputs -> script Cmd_n (CS2 servers block point_servercommand)
- added point_servercommand port_servercommand + logic_auto port_logic_auto: OnMapSpawn -> mp_freezetime 0, mp_roundtime 10, sv_airaccelerate 2000, mp_solid_teammates 0
- removed 1 player_speedmod (dead in CS2); 25 ModifySpeed outputs -> script Speed_n (speeds [1.0, 2.0, 3.0])
- 25 trigger_gravity (does nothing to players in CS2) -> trigger_multiple firing script Gravity_<scale> on touch and Gravity_1 on leaving (scales [0.3, 1.0]); names/filters/Enable/Disable kept
- trigsplit: 6 trigger_teleport/hurt/multiple spread over several meshes or pieces split into 63 extra single-mesh entities (same name, keyvalues and outputs)
- rendermode: 6 entities given CS2 render mode names (CS2 has only kRenderNormal / kRenderTransAlpha / kRenderNone): env_spritetrail 5 -> kRenderTransAlpha x6
- 20 entities had renderamt < 255 with rendermode Normal (ignored in CS:GO, see-through in CS2): renderamt 255
- 6 ambient_generics pointed at 6 new soundevents (colormultigames.gerudo_valley, colormultigames.lost_woods, colormultigames.my_horse_is_amazing, colormultigames.nyan_cat1, colormultigames.song_of_storms_remix, colormultigames.tetris1) instead of raw .vsnd...
- face texture scales: 14257 brush faces, 14247 matched to one VMF mapping; 4 matched: moved copy of a VMF brush (texture lock); 14243 matched: same plane; 6 no VMF side on the same plane + material; 4 overlapping VMF brushes with different mappings (left a...
- face texture mapping repaired: 14235 faces re-scaled / re-shifted from the VMF, 13963 faces with texture coordinates rewritten: blue (342), gray (29), green (460), pink (8), purple (262), red (395), yello (236), white (1951), black (2160), blue_neon (176)...
- splitfaces: 129 lit faces over 512x512 in 103 meshes cut into 822 pieces on a 512 grid (one lightmap chart / probe sample per face: big floors baked blotchy)
- visfit (32-unit voxels): 26.9 billion cubic units of playable air, 9.7 of it walkable band; hints 139 Medium, 95 Low, 65 Lower, 1 Lowest
- visfit: 200 Medium cells along 153110 long sight lines across gaps, so nothing pops out of view at the far end
- 8 env_laser + 0 env_beam (CS2 cannot spawn them) -> 8 never-solid func_brush beams between their end points (mutual laser pairs drawn once), coloured self-illuminated laser materials materials/lasers/laser_<rgb>.vmat; 1 TurnOn/TurnOff/Toggle -> Enable/Dis...
- relight: deleted 393 imported lights; rebuilt from the VMF 393 light -> light_omni2, 0 light_spot -> light_barn (colour, HDR intensity, range, cone); 0 Dynamic (start dark / switched / style)
- light_environment: Static -> Stationary (directlight 3), so the sun lights players and weapons
- added 10 stationary light_omni2 to sealed rooms with spawns / teleport destinations that had no light at all
- stationary lights: 12 of 393 lights switched Static -> Stationary (directlight 3) across 11 sealed compartments, ranges trimmed so no spot is inside more than 4
- 8 materials were alpha-tested / translucent in CS:GO but imported opaque - fixed with a mask from the texture alpha: unbreakable (translucent), xenox_glass_green (translucent), xenox_glass_lightblue (translucent), xenox_glass_red (translucent), xenox_bhop...
- probes: every static func_breakable / func_brush is inside a light probe volume
- radar: rendered from geometry (2745 floor faces shaded by height, walls outlined) -> panorama/images/overheadmaps/mg_color_multigames_radar_psd.png + game resource/overviews/mg_color_multigames.txt (pos -4365 6453, scale 12.85)
- built 15 missing materials from the original CS:GO textures: blue_neon, green_neon, grey_dev_neon, orange_neon, pink_neon, purple_neon, red_neon, white_dev_neon, white_neon, yellow_neon, xenox_bhop_glass_midblue, xenox_bhop_tile_midblue, xenox_bhop_tile_m...
- $additive materials moved to csgo_unlitgeneric (F_BLEND_MODE 4, additive): glasswindow070c
- $selfillum materials -> F_SELF_ILLUM (mask from the texture alpha): blue_neon, green_neon, grey_dev_neon, orange_neon, pink_neon, purple_neon, red_neon, white_dev_neon, white_neon, yellow_neon
- added point_script mg_color_multigames_io_script (maps/scripts/mg_color_multigames_io.js)
- dropped I/O report (maps/mg_color_multigames_dropped_io.txt): 103 .vmf owners with 430 outputs, 103 matched; 0 outputs missing with the target still there (probable losses), 0 with the target gone, 3 to !special targets; 120 handled by our own steps (scri...
- playercolor: 23 !activator Color outputs (dropped by the importer) -> script Color_<r>_<g>_<b> (SetColor on the activator)
- playercolor: removed 20 script Color_ outputs an earlier run added next to outputs the importer kept

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 1

## Scripts

- [`scripts/mg_color_multigames_io.js`](scripts/mg_color_multigames_io.js)

## Open / to check

- the importer leaves these out (they're on its exclusion list, mostly cosmetic): 145 point_spotlight (spotlight beams)
- chat messages use "say" from cs_script ServerCommand - if a server blocks it the messages just will not show
- 6 env_spritetrail (gone in CS2, cosmetic trails) - left out; a trail particle would replace them
- trigsplit: split triggers keep their outputs on every piece; a counter fed by OnStartTouch/OnTrigger can now count once per piece touched
- ambient_generic sounds not in the addon (stock CS:GO sounds or not packed in the BSP): sounds/ambient/explosions/explode_5.vsnd, sounds/plats/elevbell1.vsnd
- faces still with an absurd texture scale (<0.01 or >8), left as imported: xenox_bhop_tile_white x256 (VMF: 0.25x0.25/1000x8.25/10000x10000), xenox_bhop_tile_blue x4 (VMF: 0.25x0.25/0.25x100), xenox_bhop_tile_red x4 (VMF: 0.25x0.25/0.25x100), xenox_bhop_tile_green x4 (VMF: 0.25x0.25/0.25x100), xen...
- splitfaces: check the cut floors / ramps for seams after the bake
- env_sky materials/skybox/mikis_hdr.vmat: could not rebuild (no CS:GO sky face materials/skybox/mikisrt.vmt) - pick a stock CS2 sky
- vis: 7426 long sight lines got no Medium corridor (over the 200 cell limit): look for props popping out across long gaps
- vis: if anything pops in or out of view where players stand, change the nearest Lower hint to Low (or Low to Medium)
- beams with no usable end point, removed: env_laser, env_laser, env_laser, env_laser, env_laser, env_laser, env_laser, env_laser, env_laser, env_laser, env_laser, env_laser
- relight: brightness scale (1000 lumens per 265 _light) is not checked against a real CS2 bake - compare a few rooms with CS:GO
- 2 compartments only partly covered by stationary light (overlap cap) - check weapons are lit there
- 3 outputs from the .vmf are missing in the vmap while their target is still there (OnStartTouch->Color x3): see maps/mg_color_multigames_dropped_io.txt
- vis: 7442 long sight lines got no Medium corridor (over the 200 cell limit): look for props popping out across long gaps
- Lights (mg_color_multigames): 75 moved off walls they would have blown out.
- Z-fighting (mg_color_multigames): 1 small or same-material overlaps left (first: materials/xenoxtile/xenox_bhop_tile_white.vmat | materials/xenoxtile/xenox_bhop_tile_white.vmat at -768 5088 -1776, 14336 sq units overlap (minor)).
- Loading screen images: add at least two (autoport does not make them; docs/porting/pipeline.md, Loading-screen background images).
- Some meshes got no physics hull: look for missing collisions. See logs\mg_color_multigames_build.log
