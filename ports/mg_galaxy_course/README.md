# mg_galaxy_course

| | |
|---|---|
| Status | Stage C done, vis optimised 18 Oct, gravity triggers scripted 19 Oct, queued for build |
| Original map | xGrandx |
| Imported | 2026-10-16 |
| Map last changed | 2026-10-19 |
| How | cs2port pipeline |

## History

- 2026-10-16: stages A–C in the second pipeline batch.
- 2026-10-18: vis pass (`visfit`) for compile time. Hints 1 Lowest, 22 Low → 33 Low, 14 Lower, 1 Lowest; hint volume in billion cubic units Low 26.0, Lowest 108.1 → Low 7.9, Lower 2.9, Lowest 118.8. In vis terms the map is open: it is enclosed only by toolsnodraw meshes, which vis ignores. Not changed; if vis culling turns out poor, the enclosure needs toolsskybox faces. Backup: `csgo_addons\prefabs+backups\pre_vis_2026-10-18`.
- 2026-10-19: the 6 trigger_gravity (scales 0.2, 0.3, 0.5, 1) the clean had left as TO CHECK → trigger_multiples firing script `Gravity_<scale>` (new pipeline `gravity` pass, run as a stage D follow-up). Backup: `prefabs+backups\mg_galaxy_course_pre_gravity_2026-10-19.vmap`.

## What the cleanup did

(from the cleanup log in this folder)

- collapsed 6 prefabs into the map, world offsets kept: mg_galaxy_course_gameplay.vmap (367 nodes, 367 entities), mg_galaxy_course_environment_prefab.vmap (967 nodes, 314 entities), mg_galaxy_course_lighting_prefab.vmap (3 nodes, 3 entities), mg_galaxy_course...
- outputs restored that the importer dropped: 0
- removed 1 point_servercommand; 4 Command outputs -> script Cmd_n (CS2 servers block point_servercommand)
- added point_servercommand port_servercommand + logic_auto port_logic_auto: OnMapSpawn -> mp_freezetime 0, mp_roundtime 600; only T spawns (56), so game_player_equip port_knife_equip gives weapon_knife on spawn and OnMapSpawn (TriggerForAllPlayers)
- env_sky materials/skybox/space.vmat: rebuilt from the six CS:GO faces
- visibility hints: lowest 1 (whole map incl. void), low 22 (cells with geometry), medium 0 (densest cells only)
- 15 env_laser + 0 env_beam (CS2 cannot spawn them) -> 15 never-solid func_brush beams between their end points (mutual laser pairs drawn once), coloured self-illuminated laser materials materials/lasers/laser_<rgb>.vmat; 2 TurnOn/TurnOff/Toggle -> Enable/Dis...
- stationary lights: 6 of 291 lights switched Static -> Stationary (directlight 3) across 3 sealed compartments, ranges trimmed so no spot is inside more than 4
- 3 materials were alpha-tested / translucent in CS:GO but imported opaque - fixed with a mask from the texture alpha: glasswindow007a (translucent), unbreakable (translucent), unbreakable_glass_a_01 (translucent)
- radar: rendered from geometry (251 floor faces shaded by height, walls outlined) -> panorama/images/overheadmaps/mg_galaxy_course_radar_psd.png + game resource/overviews/mg_galaxy_course.txt (pos 713 3486, scale 6.56)

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 14

## Scripts

- [`scripts/mg_galaxy_course_io.js`](scripts/mg_galaxy_course_io.js) - chat messages (`Cmd_n`) and per-player gravity (`Gravity_<scale>`)

## Open / to check

- Vis: if anything pops in or out of view where players stand, change the nearest Lower hint to Low (or Low to Medium).
- the importer leaves these out (they're on its exclusion list, mostly cosmetic): 8 point_spotlight (spotlight beams)
- chat messages use "say" from cs_script ServerCommand - if a server blocks it the messages just will not show
- Gravity script untested in game: the big 0.2 zone (2304..5104 x 2192..3472) should feel like low gravity; the 0.3/1 pair at x 5112-5128 are entry/exit doorways.
- overlay materials not converted: materials/props/decal_prison04b.vmat (vmat not in addon); materials/realworldtextures2/decals/dirt_decal_02.vmat (vmat not in addon); materials/realworldtextures2/decals/dirt_decal_03.vmat (vmat not in addon)
- check the substituted materials look right: materials/environment_maps/pipemetal001a.vmat -> models/generic/pipe01/pipe_metal01a.vmat; materials/realworldtextures2/decals/dirt_decal_02.vmat -> materials/de_train/train_dirt_decal_07.vmat; materials/realworldtextures2/decals/dirt_decal_03.vmat -> materials/de_train/train_dirt_decal_07.vmat
- materials still missing: materials/props/decal_prison04b.vmat (decal with no CS:GO source; closest stock match materials/props/metalfan001a.vmat is not a decal, so left as is)
