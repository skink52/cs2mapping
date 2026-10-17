# mg_egypt_course

| | |
|---|---|
| Status | Stage C done, queued for build |
| Imported | 2026-10-16 |
| Map last changed | 2026-10-16 |
| How | cs2port pipeline |

## What the cleanup did

(from the cleanup log in this folder)

- collapsed 6 prefabs into the map, world offsets kept: mg_egypt_course_gameplay.vmap (758 nodes, 758 entities), mg_egypt_course_environment_prefab.vmap (1454 nodes, 268 entities), mg_egypt_course_lighting_prefab.vmap (2 nodes, 2 entities), mg_egypt_course_cu...
- outputs restored that the importer dropped: 2 (e.g. trigger_multiple  -> !activator.SetDamageFilter(disable_dmg); trigger_multiple  -> !activator.SetDamageFilter(enable_dmg))
- added point_servercommand port_servercommand + logic_auto port_logic_auto: OnMapSpawn -> mp_freezetime 0, mp_roundtime 600; only T spawns (32), so game_player_equip port_knife_equip gives weapon_knife on spawn and OnMapSpawn (TriggerForAllPlayers)
- removed 1 game_score (not in CS2); 3 ApplyScore -> script Score_n
- env_sky materials/skybox/sky_dust.vmat: rebuilt from the six CS:GO faces
- restored 1 sky brushes (dropped by the importer) as moondome meshes using materials/skybox/sky_dust_moondome.vmat
- visibility hints: lowest 1 (whole map incl. void), low 12 (cells with geometry), medium 1 (densest cells only)
- 33 env_laser + 0 env_beam (CS2 cannot spawn them) -> 33 never-solid func_brush beams between their end points (mutual laser pairs drawn once), coloured self-illuminated laser materials materials/lasers/laser_<rgb>.vmat; 0 TurnOn/TurnOff/Toggle -> Enable/Dis...
- stationary lights: 6 of 216 lights switched Static -> Stationary (directlight 3) across 2 sealed compartments, ranges trimmed so no spot is inside more than 4
- radar: rendered from geometry (1360 floor faces shaded by height, walls outlined) -> panorama/images/overheadmaps/mg_egypt_course_radar_psd.png + game resource/overviews/mg_egypt_course.txt (pos -6512 6759, scale 13.17)

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 4

## Scripts

- [`scripts/mg_egypt_course_io.js`](scripts/mg_egypt_course_io.js)

## Open / to check

- ambient_generic themesong is set to loop but sounds/ongrid_001/ancient_egyptian_music_-_desert_mercenaries.mp3 has no loop cue points, so it will play once in CS2
- these lasers did damage in CS:GO but there is no trigger_hurt along them, so in CS2 they are only visual: laser50 at 5873.12 -1872 834.47 (damage 100), laser50 at 6152.12 -2036 833.5 (damage 100), laser50 at 6404.12 -1873 834.53 (damage 100)
