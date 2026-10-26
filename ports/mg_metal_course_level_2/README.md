# mg_metal_course_level_2

| | |
|---|---|
| Status | Stage C done, vis optimised 18 Oct, queued for build |
| Original map | ScHoOuFi |
| Imported | 2026-10-16 |
| Map last changed | 2026-10-18 |
| How | cs2port pipeline |

kolkazadrot published a CS2 port as mg_metal_course_2_v2 (Workshop 3070464801, credited to ScHoOuFi). This one went ahead on request.

## History

- 2026-10-16: stages A–C in the second pipeline batch. Its panda spray overlay showed that overlays rebuilt later in the same stage C run weren't being converted; fixed in the pipeline.
- 2026-10-18: vis pass (`visfit`) for compile time. Hints 1 Lowest, 17 Low → 34 Low, 7 Lower, 1 Lowest; hint volume in billion cubic units Low 19.4, Lowest 98.9 → Low 5.8, Lower 0.2, Lowest 131.0. Backup: `csgo_addons\prefabs+backups\pre_vis_2026-10-18`.
- 2026-10-24: the 48 glows on the HE grenades he2–he13 (4 per grenade) didn't follow the player who picked one up. env_particle_glow can't move once drawn (see cs2-gotchas). skink52 swapped them to info_particle_system; `glowfix.py` logic gave each a per-colour following glow (`particles/heglow/heglow_<rrggbb>.vpcf`, 30 colours from the old `colortint`, texture `materials/heglow/heglow.png`) and named them `heglow_heN_<k>`. `mg_metal_course_level_2_io.js` gained a glow follow section: glows are unparented and moved every tick, on the grenade, at the carrier's chest (+40), then on the thrown `hegrenade_projectile`, and removed when it detonates; re-found every round. Backup `maps/mg_metal_course_level_2.vmap.bak_glow`. Awaiting in-game test.

## What the cleanup did

(from the cleanup log in this folder)

- collapsed 6 prefabs into the map, world offsets kept: mg_metal_course_level_2_gameplay.vmap (142 nodes, 142 entities), mg_metal_course_level_2_environment_prefab.vmap (762 nodes, 177 entities), mg_metal_course_level_2_lighting_prefab.vmap (2 nodes, 2 entiti...
- outputs restored that the importer dropped: 0
- 13 trigger_push (speeds [70.0, 100.0, 250.0, 700.0, 1200.0]; CS2 would keep accelerating) -> trigger_multiple + script push zones holding CS:GO speed (clamped to 3500); names/filters/Enable/Disable kept
- removed 2 point_servercommand; 5 Command outputs -> script Cmd_n (CS2 servers block point_servercommand)
- added point_servercommand port_servercommand + logic_auto port_logic_auto: OnMapSpawn -> mp_freezetime 0, mp_roundtime 600; only CT spawns, but the map already has a game_player_equip giving weapon_knife on spawn (unnamed), so no extra knife equip
- removed 1 game_score (not in CS2); 1 ApplyScore -> script Score_n
- env_sky materials/skybox/mpa123.vmat: rebuilt from the six CS:GO faces
- visibility hints: lowest 1 (whole map incl. void), low 17 (cells with geometry), medium 0 (densest cells only)
- 7 env_laser + 0 env_beam (CS2 cannot spawn them) -> 7 never-solid func_brush beams between their end points (mutual laser pairs drawn once), coloured self-illuminated laser materials materials/lasers/laser_<rgb>.vmat; 0 TurnOn/TurnOff/Toggle -> Enable/Disab...
- stationary lights: 2 of 84 lights switched Static -> Stationary (directlight 3) across 1 sealed compartments, ranges trimmed so no spot is inside more than 4
- 2 materials were alpha-tested / translucent in CS:GO but imported opaque - fixed with a mask from the texture alpha: train_cautionstripe (translucent), fin (translucent)
- radar: rendered from geometry (261 floor faces shaded by height, walls outlined) -> panorama/images/overheadmaps/mg_metal_course_level_2_radar_psd.png + game resource/overviews/mg_metal_course_level_2.txt (pos -2830 9476, scale 10.41)

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 1

## Scripts

- [`scripts/mg_metal_course_level_2_io.js`](scripts/mg_metal_course_level_2_io.js)

## Open / to check

- 2026-10-27 (mock engine): `heMove()` teleports the `heglow_*` particle systems every tick. The not-drawn rule is known for props; watch the grenade glows in game.

- Vis: if anything pops in or out of view where players stand, change the nearest Lower hint to Low (or Low to Medium).
- the importer leaves these out (they're on its exclusion list, mostly cosmetic): 13 point_spotlight (spotlight beams), 13 func_dustmotes (dust motes)
- chat messages use "say" from cs_script ServerCommand - if a server blocks it the messages just will not show
- these lasers did damage in CS:GO but there is no trigger_hurt along them, so in CS2 they are only visual: la3 at 2496 4812 256 (damage 10000), la4 at 2496 4864 308 (damage 10000), la5 at 2496 5056 308 (damage 10000)
