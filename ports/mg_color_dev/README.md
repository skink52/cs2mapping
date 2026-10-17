# mg_color_dev

| | |
|---|---|
| Status | Published |
| Workshop | [mg_color_dev](https://steamcommunity.com/sharedfiles/filedetails/?id=3820639006) |
| Imported | 2026-10-16 |
| Map last changed | 2026-10-16 |
| How | cs2port pipeline (stages A-D) |

## What the cleanup did

(from the cleanup log in this folder)

- collapsed 6 prefabs into the map, world offsets kept: mg_color_dev_gameplay.vmap (308 nodes, 308 entities), mg_color_dev_environment_prefab.vmap (354 nodes, 67 entities), mg_color_dev_lighting_prefab.vmap (2 nodes, 2 entities), mg_color_dev_cubemaps_prefab....
- outputs restored that the importer dropped: 5 (e.g. weapon_hegrenade he1 -> l1.LightOff(); weapon_hegrenade he4 -> l4.LightOff(); trigger_multiple speed -> !activator.AddOutput(targetname speed); logic_case 1erlvl -> tri_once4.Enable(); logic_case 1erlvl ->...
- removed 2 game_score (not in CS2); 2 ApplyScore -> script Score_n
- removed 1 player_speedmod (dead in CS2); 1 ModifySpeed outputs -> script Speed_n (speeds [1.2])
- env_sky materials/skybox/sky_dust.vmat: rebuilt from the six CS:GO faces
- visibility hints: lowest 1 (whole map incl. void), low 15 (cells with geometry), medium 1 (densest cells only)
- 8 env_laser + 17 env_beam (CS2 cannot spawn them) -> 25 never-solid func_brush beams between their end points (mutual laser pairs drawn once), coloured self-illuminated laser materials materials/lasers/laser_<rgb>.vmat; 0 TurnOn/TurnOff/Toggle -> Enable/Dis...
- stationary lights: 10 of 41 lights switched Static -> Stationary (directlight 3) across 10 sealed compartments, ranges trimmed so no spot is inside more than 4
- radar: rendered from geometry (340 floor faces shaded by height, walls outlined) -> panorama/images/overheadmaps/mg_color_dev_radar_psd.png + game resource/overviews/mg_color_dev.txt (pos -1727 2399, scale 6.75)

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 1

## Scripts

- [`scripts/mg_color_dev_io.js`](scripts/mg_color_dev_io.js) - game_score and player_speedmod replacements

## Open / to check

- the importer leaves these out (they're on its exclusion list, mostly cosmetic): 79 point_spotlight (spotlight beams), 7 func_dustmotes (dust motes)
- these lasers did damage in CS:GO but there is no trigger_hurt along them, so in CS2 they are only visual: env_beam at 3353 -2020 815 (damage 9e+07)
- 1 compartments only partly covered by stationary light (overlap cap) - check weapons are lit there
