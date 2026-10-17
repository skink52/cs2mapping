# mg_kohztec_course

| | |
|---|---|
| Status | Stage C done, queued for build |
| Imported | 2026-10-16 |
| Map last changed | 2026-10-16 |
| How | cs2port pipeline |

## What the cleanup did

(from the cleanup log in this folder)

- collapsed 6 prefabs into the map, world offsets kept: mg_kohztec_course_gameplay.vmap (313 nodes, 313 entities), mg_kohztec_course_environment_prefab.vmap (2761 nodes, 558 entities), mg_kohztec_course_lighting_prefab.vmap (3 nodes, 3 entities), mg_kohztec_c...
- outputs restored that the importer dropped: 88 (e.g. trigger_multiple  -> !activator.AddOutput(targetname platform); trigger_multiple  -> !activator.AddOutput(targetname normal); trigger_multiple  -> !activator.AddOutput(targetname normal); trigger_teleport...
- 6 trigger_push (speeds [100.0, 1000.0]; CS2 would keep accelerating) -> trigger_multiple + script push zones holding CS:GO speed (clamped to 3500); names/filters/Enable/Disable kept
- added point_servercommand port_servercommand + logic_auto port_logic_auto: OnMapSpawn -> mp_freezetime 0, mp_roundtime 600; only T spawns, but the map already has a game_player_equip giving weapon_knife on spawn (unnamed), so no extra knife equip
- removed 1 game_score (not in CS2); 1 ApplyScore -> script Score_n
- env_sky materials/skybox/jungle.vmat: rebuilt from the six CS:GO faces
- restored 35 sky brushes (dropped by the importer) as moondome meshes using materials/skybox/jungle_moondome.vmat
- visibility hints: lowest 1 (whole map incl. void), low 48 (cells with geometry), medium 0 (densest cells only)
- stationary lights: 5 of 157 lights switched Static -> Stationary (directlight 3) across 5 sealed compartments, ranges trimmed so no spot is inside more than 4; 3 compartments open to sky left to light_environment
- 5 materials were alpha-tested / translucent in CS:GO but imported opaque - fixed with a mask from the texture alpha: miltree003 (translucent), miltree005 (translucent), treeline001a (translucent), waterfallfull_1024_clear (translucent), waterfallfull_512_cl...
- radar: rendered from geometry (1247 floor faces shaded by height, walls outlined) -> panorama/images/overheadmaps/mg_kohztec_course_radar_psd.png + game resource/overviews/mg_kohztec_course.txt (pos -6734 4308, scale 9.19)

## Import report

(`post_import_cleanup.py` report in this folder)

- Models - failed to compile: 1
- Textures - fully missing, no source found anywhere: 10

## Scripts

- [`scripts/mg_kohztec_course_io.js`](scripts/mg_kohztec_course_io.js)

## Open / to check

- the importer leaves these out (they're on its exclusion list, mostly cosmetic): 1 point_spotlight (spotlight beams), 2 func_precipitation (rain/snow)
- 1 env_screenoverlay (mg_kohztec_course_overlay_2) - not converted automatically, needs a look
- 1 point_clientcommand (clcmd) - not converted automatically, needs a look
- ambient_generic mg_kohztec_course_secret_music_1_sound is set to loop but sounds/megaman/06-metal-man.mp3 has no loop cue points, so it will play once in CS2
- overlay materials not converted: materials/decals/blood4.vmat (texture has no alpha); materials/decals/blood4model.vmat (vmat not in addon); materials/decals/bloodstain_003.vmat (texture has no alpha); materials/decals/flesh/blood3.vmat (texture has no alpha); materials/decals/ivy02.vmat (vmat not in addon)
- 1 compartments only partly covered by stationary light (overlap cap) - check weapons are lit there
- materials still missing: materials/decals/blood4model.vmat (custom decal with no CS:GO source - left as is rather than swapped for an unrelated decal); materials/decals/ivy02.vmat (custom decal with no CS:GO source - left as is rather than swapped for an unrelated decal)
