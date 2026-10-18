# mg_faohu_course

| | |
|---|---|
| Status | Stage C done, vis optimised 18 Oct, queued for build |
| Imported | 2026-10-16 |
| Map last changed | 2026-10-18 |
| How | cs2port pipeline |

## History

- 2026-10-16: stages A–C in the second pipeline batch. The extra knife equip was dropped because the map already gives one.
- 2026-10-18: vis pass (`visfit`) for compile time. Hints 1 Lowest, 10 Low → 34 Low, 26 Lower, 1 Lowest; hint volume in billion cubic units Low 20.3, Lowest 111.0 → Low 7.8, Lower 1.2, Lowest 142.5. Backup: `csgo_addons\prefabs+backups\pre_vis_2026-10-18`.

## What the cleanup did

(from the cleanup log in this folder)

- collapsed 6 prefabs into the map, world offsets kept: mg_faohu_course_gameplay.vmap (188 nodes, 188 entities), mg_faohu_course_environment_prefab.vmap (591 nodes, 213 entities), mg_faohu_course_lighting_prefab.vmap (2 nodes, 2 entities), mg_faohu_course_cub...
- outputs restored that the importer dropped: 0
- 4 trigger_push (speeds [300.0, 500.0, 1000.0, 1500.0]; CS2 would keep accelerating) -> trigger_multiple + script push zones holding CS:GO speed (clamped to 3500); names/filters/Enable/Disable kept
- added point_servercommand port_servercommand + logic_auto port_logic_auto: OnMapSpawn -> mp_freezetime 0, mp_roundtime 600; only T spawns, but the map already has a game_player_equip giving weapon_knife on spawn (unnamed), so no extra knife equip
- removed 1 game_score (not in CS2); 1 ApplyScore -> script Score_n
- env_sky materials/skybox/sky_dust.vmat: rebuilt from the six CS:GO faces
- visibility hints: lowest 1 (whole map incl. void), low 10 (cells with geometry), medium 0 (densest cells only)
- 61 env_laser + 0 env_beam (CS2 cannot spawn them) -> 33 never-solid func_brush beams between their end points (mutual laser pairs drawn once), coloured self-illuminated laser materials materials/lasers/laser_<rgb>.vmat; 0 TurnOn/TurnOff/Toggle -> Enable/Dis...
- stationary lights: 11 of 104 lights switched Static -> Stationary (directlight 3) across 11 sealed compartments, ranges trimmed so no spot is inside more than 4
- 19 materials were alpha-tested / translucent in CS:GO but imported opaque - fixed with a mask from the texture alpha: hotel_glass001 (translucent), chitoge (translucent), ending (translucent), ending1 (translucent), finalstage (translucent), mapper (translu...
- radar: rendered from geometry (387 floor faces shaded by height, walls outlined) -> panorama/images/overheadmaps/mg_faohu_course_radar_psd.png + game resource/overviews/mg_faohu_course.txt (pos -1333 1417, scale 5.41)

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 2

## Scripts

- [`scripts/mg_faohu_course_io.js`](scripts/mg_faohu_course_io.js)

## Open / to check

- Vis: if anything pops in or out of view where players stand, change the nearest Lower hint to Low (or Low to Medium).
- the importer leaves these out (they're on its exclusion list, mostly cosmetic): 10 point_spotlight (spotlight beams)
- these lasers did damage in CS:GO but there is no trigger_hurt along them, so in CS2 they are only visual: stage5_t_laser13 at -1056 -1216 416 (damage 500), stage5_t_laser15 at -672 -1216 416 (damage 500), stage5_t_laser17 at -672 -1216 320 (damage 500), stage5_t_laser19 at -672 -1216 336 (damage 500), stage5_t_laser21 at -672 -1216 352 (damage 500), stage5_t_laser23 at -672 -1216 368 (damage 500), stage5_t_laser25 at -672 -1216 384 (damage 500), stage5_t_laser27 at -672 -1216 400 (damage 500), stage5_t_laser31 at -711.542 -1216 244 (damage 500), stage5_t_laser33 at -752.45 -1216 264 (damage 500)
- beams with no usable end point, removed: finalaser6
