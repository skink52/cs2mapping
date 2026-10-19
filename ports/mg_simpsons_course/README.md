# mg_simpsons_course

| | |
|---|---|
| Status | Stage C done, vis optimised 18 Oct, queued for build |
| Original map | Joe101 & guilhermealegretti |
| Imported | 2026-10-16 |
| Map last changed | 2026-10-19 |
| How | cs2port pipeline |

kolkazadrot published a CS2 port in Nov 2023 (mg_simpsons_course_v2, Workshop 3070447697), but its commenters report crashes and that it can't be completed, so this one went ahead on request. The author credit comes from the map itself (not Struse).

## History

- 2026-10-16: stages A–C in the second pipeline batch. The slowest import of the batch: a tm_balkan prop made the importer convert the whole T animation set (2,654 animations).
- 2026-10-18: vis pass (`visfit`) for compile time. Hints 1 Lowest, 14 Low → 23 Low, 18 Lower, 1 Lowest; hint volume in billion cubic units Low 24.5, Lowest 213.8 → Low 10.3, Lower 0.9, Lowest 261.3. Sky shells: 2 of 27 set to Exclude from Vis. Backup: `csgo_addons\prefabs+backups\pre_vis_2026-10-18`.

- 2026-10-19: the 2 trigger_gravity (0.5, 1) → trigger_multiples firing script `Gravity_<scale>` on touch and `Gravity_1` on leaving (pipeline `gravity` pass, stage D). Backup: `prefabs+backups\mg_simpsons_course_pre_gravity_2026-10-19.vmap`.

## What the cleanup did

(from the cleanup log in this folder)

- collapsed 6 prefabs into the map, world offsets kept: mg_simpsons_course_gameplay.vmap (210 nodes, 210 entities), mg_simpsons_course_environment_prefab.vmap (958 nodes, 103 entities), mg_simpsons_course_lighting_prefab.vmap (3 nodes, 3 entities), mg_simpson...
- outputs restored that the importer dropped: 13 (e.g. func_button right -> !self.Kill(); trigger_multiple  -> !activator.AddOutput(targetname activator); trigger_multiple  -> !activator.AddOutput(targetname default); trigger_multiple  -> !activator.AddOutput...
- 1 trigger_push (speeds [450.0]; CS2 would keep accelerating) -> trigger_multiple + script push zones holding CS:GO speed (clamped to 3500); names/filters/Enable/Disable kept
- removed 1 point_servercommand; 26 Command outputs -> script Cmd_n (CS2 servers block point_servercommand)
- added point_servercommand port_servercommand + logic_auto port_logic_auto: OnMapSpawn -> mp_freezetime 0, mp_roundtime 600; only T spawns, but the map already has a game_player_equip giving weapon_knife on spawn (stripper), so no extra knife equip
- removed 2 game_score (not in CS2); 2 ApplyScore -> script Score_n
- env_sky materials/skybox/mpa52.vmat: rebuilt from the six CS:GO faces
- restored 27 sky brushes (dropped by the importer) as moondome meshes using materials/skybox/mpa52_moondome.vmat
- visibility hints: lowest 1 (whole map incl. void), low 14 (cells with geometry), medium 0 (densest cells only)
- 15 env_laser + 0 env_beam (CS2 cannot spawn them) -> 8 never-solid func_brush beams between their end points (mutual laser pairs drawn once), coloured self-illuminated laser materials materials/lasers/laser_<rgb>.vmat; 0 TurnOn/TurnOff/Toggle -> Enable/Disa...
- stationary lights: 6 of 76 lights switched Static -> Stationary (directlight 3) across 6 sealed compartments, ranges trimmed so no spot is inside more than 4; 3 compartments open to sky left to light_environment
- 11 materials were alpha-tested / translucent in CS:GO but imported opaque - fixed with a mask from the texture alpha: bart (translucent), homer (translucent), rosquinha (alpha test), selma (translucent), vovo (translucent), {99store (alpha test), {branch1 (...
- radar: rendered from geometry (673 floor faces shaded by height, walls outlined) -> panorama/images/overheadmaps/mg_simpsons_course_radar_psd.png + game resource/overviews/mg_simpsons_course.txt (pos -1546 4254, scale 14.06)

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 1

## Scripts

- [`scripts/mg_simpsons_course_io.js`](scripts/mg_simpsons_course_io.js)

## Open / to check

- Vis: if anything pops in or out of view where players stand, change the nearest Lower hint to Low (or Low to Medium).
- chat messages use "say" from cs_script ServerCommand - if a server blocks it the messages just will not show
- Gravity script (0.5 zone) untested in game.
- ambient_generic sounds not in the addon (stock CS:GO sounds or not packed in the BSP): sounds/porco.vsnd
- beams with no usable end point, removed: laser1.3
- materials still missing: materials/ryan_dev/dev_darker_blue1.vmat (no CS:GO source and no similar stock CS2 material)
