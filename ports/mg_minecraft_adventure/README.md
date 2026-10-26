# mg_minecraft_adventure

| | |
|---|---|
| Status | Published (27 Oct 2026) |
| Workshop | [3825226010](https://steamcommunity.com/sharedfiles/filedetails/?id=3825226010) |
| Original map | Salty |
| Imported | 2026-10-16 |
| Map last changed | 2026-10-18 |
| How | cs2port pipeline |

## History

- 2026-10-16: stages A–C in the second pipeline batch.
- 2026-10-18: vis pass (`visfit`) for compile time. Hints 1 Lowest, 45 Low, 3 Medium → 71 Low, 20 Lower, 1 Lowest; hint volume in billion cubic units Medium 0.4, Low 38.9, Lowest 1566.6 → Low 16.9, Lower 1.0, Lowest 539.9. Sky shells: 6 of 101 set to Exclude from Vis. Backup: `csgo_addons\prefabs+backups\pre_vis_2026-10-18`.

## What the cleanup did

(from the cleanup log in this folder)

- collapsed 6 prefabs into the map, world offsets kept: mg_minecraft_adventure_gameplay.vmap (288 nodes, 288 entities), mg_minecraft_adventure_environment_prefab.vmap (6020 nodes, 408 entities), mg_minecraft_adventure_lighting_prefab.vmap (3 nodes, 3 entities...
- outputs restored that the importer dropped: 10 (e.g. trigger_multiple  -> !activator.AddOutput(targetname Activator); trigger_multiple  -> !activator.AddOutput(targetname Default); trigger_multiple  -> !activator.AddOutput(targetname Activator); trigger_mul...
- 11 trigger_push (speeds [1500.0]; CS2 would keep accelerating) -> trigger_multiple + script push zones holding CS:GO speed (clamped to 3500); names/filters/Enable/Disable kept
- added point_servercommand port_servercommand + logic_auto port_logic_auto: OnMapSpawn -> mp_freezetime 0, mp_roundtime 600; only CT spawns (42), so game_player_equip port_knife_equip gives weapon_knife on spawn and OnMapSpawn (TriggerForAllPlayers)
- removed 6 game_score (not in CS2); 24 ApplyScore -> script Score_n
- env_sky materials/skybox/mclite.vmat: rebuilt from the six CS:GO faces
- restored 101 sky brushes (dropped by the importer) as moondome meshes using materials/skybox/mclite_moondome.vmat
- visibility hints: lowest 1 (whole map incl. void), low 45 (cells with geometry), medium 3 (densest cells only)
- 2 env_laser + 0 env_beam (CS2 cannot spawn them) -> 1 never-solid func_brush beams between their end points (mutual laser pairs drawn once), coloured self-illuminated laser materials materials/lasers/laser_<rgb>.vmat; 0 TurnOn/TurnOff/Toggle -> Enable/Disab...
- stationary lights: 12 of 328 lights switched Static -> Stationary (directlight 3) across 12 sealed compartments, ranges trimmed so no spot is inside more than 4; 2 compartments open to sky left to light_environment
- 22 materials were alpha-tested / translucent in CS:GO but imported opaque - fixed with a mask from the texture alpha: bed_front (translucent), bed_side (translucent), carrots_full (translucent), carrots_potatoes_1 (translucent), carrots_potatoes_2 (transluc...
- radar: rendered from geometry (1328 floor faces shaded by height, walls outlined) -> panorama/images/overheadmaps/mg_minecraft_adventure_radar_psd.png + game resource/overviews/mg_minecraft_adventure.txt (pos 4592 -4044, scale 8.95)

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 2

## Scripts

- [`scripts/mg_minecraft_adventure_io.js`](scripts/mg_minecraft_adventure_io.js)

## Open / to check

- Vis: if anything pops in or out of view where players stand, change the nearest Lower hint to Low (or Low to Medium).
- materials still missing: materials/ennergy/minecraft/mobs_heads/skeleton_wither_bottom.vmat (no CS:GO source and no similar stock CS2 material)
