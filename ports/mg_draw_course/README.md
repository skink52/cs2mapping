# mg_draw_course

| | |
|---|---|
| Status | Published (27 Oct 2026) |
| Workshop | [3820723954](https://steamcommunity.com/sharedfiles/filedetails/?id=3820723954) |
| Original map | PatatoR (Team-Furaxx) |
| Imported | 2026-10-16 |
| Map last changed | 2026-10-16 |
| How | cs2port pipeline (stages A-D), daylight pass |

The first map to get the `daylight` pass. It was too dark indoors with only stationary lights. Kolkazadrot has also ported this map to CS2.

## History

- 2026-10-16: stage C restored 2 logic_auto outputs, turned 4 trigger_push (3000/4000) into script push zones, kept the 3 chat messages through the script ("Map By PatatoR For Team-Furaxx.com", "Good Game !"), made 3 music soundevents, rebuilt the dust sky and added 6 moondomes. Re-imported after the func_illusionary fix. 20 env_laser → 10 beams; `{sewerladder` alpha-tested.
- 2026-10-16 16:35, "really dark": the first `daylight` pass. A stationary light_environment at 70° pitch / yaw 90 (the best of 16 angles), 87 ceiling and roof meshes set to Disable Shadows, 5 light probe volumes, maxexposure 1.25 → 2. Rebuilt at 18:13 (56.6 min).

## What the cleanup did

(from the cleanup log in this folder)

- collapsed 6 prefabs into the map, world offsets kept: mg_draw_course_gameplay.vmap (111 nodes, 111 entities), mg_draw_course_environment_prefab.vmap (428 nodes, 47 entities), mg_draw_course_lighting_prefab.vmap (2 nodes, 2 entities), mg_draw_course_cubemaps...
- outputs restored that the importer dropped: 2 (e.g. logic_auto  -> clow22.PickRandomShuffle(); logic_auto  -> clow3.PickRandomShuffle())
- 4 trigger_push (speeds [3000.0, 4000.0]; CS2 would keep accelerating) -> trigger_multiple + script push zones holding CS:GO speed (clamped to 3500); names/filters/Enable/Disable kept
- removed 1 point_servercommand; 3 Command outputs -> script Cmd_n (CS2 servers block point_servercommand)
- removed 1 game_score (not in CS2); 1 ApplyScore -> script Score_n
- env_sky materials/skybox/sky_dust.vmat: rebuilt from the six CS:GO faces
- restored 6 sky brushes (dropped by the importer) as moondome meshes using materials/skybox/sky_dust_moondome.vmat
- visibility hints: lowest 1 (whole map incl. void), low 6 (cells with geometry), medium 0 (densest cells only)
- 20 env_laser + 0 env_beam (CS2 cannot spawn them) -> 10 never-solid func_brush beams between their end points (mutual laser pairs drawn once), coloured self-illuminated laser materials materials/lasers/laser_<rgb>.vmat; 0 TurnOn/TurnOff/Toggle -> Enable/Dis...
- stationary lights: 4 of 25 lights switched Static -> Stationary (directlight 3) across 1 sealed compartments, ranges trimmed so no spot is inside more than 4
- 1 materials were alpha-tested / translucent in CS:GO but imported opaque - fixed with a mask from the texture alpha: {sewerladder (alpha test)
- radar: rendered from geometry (214 floor faces shaded by height, walls outlined) -> panorama/images/overheadmaps/mg_draw_course_radar_psd.png + game resource/overviews/mg_draw_course.txt (pos -9875 5386, scale 10.02)
- daylight: 2498 floor sample points in the playable space; 87 ceiling / roof meshes between them and the sky set to cast no shadows (23 inside entities)
- daylight: with those ceilings open, 79% of floor points see the sky towards the sun and 100% straight up
- daylight: added a stationary light_environment (sun pitch 70 yaw 90, brightness 1.5, sky ambient 1.25 from env_sky "default_sky")
- daylight: map had no light probe volumes (players and weapons get no indirect light without them) - added 5 env_combined_light_probe_volume over the playable space
- daylight: post_processing_volume maxexposure 1.25 -> 2.0 so auto exposure can brighten dark rooms

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 2

## Scripts

- [`scripts/mg_draw_course_io.js`](scripts/mg_draw_course_io.js) - trigger_push, point_servercommand and game_score replacements

## Open / to check

- chat messages use "say" from cs_script ServerCommand - if a server blocks it the messages just will not show
- daylight: check the course in game - ceilings no longer cast shadows, so indoor floors get sun and sky light; adjust the light_environment brightness / angle if it looks too bright
