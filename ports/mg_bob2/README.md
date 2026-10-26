# mg_bob2

| | |
|---|---|
| Status | Built (in progress; surf ramps limit playability) (27 Oct 2026) |
| Imported | 2026-10-16 |
| Map last changed | 2026-10-16 |
| How | cs2port pipeline |

## History

- 2026-10-16: stages A–C in the second pipeline batch. Its custom decal had been swapped for a sticker, which is why custom decals with no CS:GO source are now left alone and flagged. The extra knife equip was dropped because the map already gives one.
- 2026-10-18: built from the command line (30.2 min, OK; vis 1,624 s: 556,739 regions, 13,596 clusters after the list merge, 209 s final merge).

## What the cleanup did

(from the cleanup log in this folder)

- collapsed 6 prefabs into the map, world offsets kept: mg_bob2_gameplay.vmap (570 nodes, 570 entities), mg_bob2_environment_prefab.vmap (2613 nodes, 445 entities), mg_bob2_lighting_prefab.vmap (3 nodes, 3 entities), mg_bob2_cubemaps_prefab.vmap (192 nodes, 1...
- outputs restored that the importer dropped: 1 (e.g. trigger_multiple  -> !activator.SetDamageFilter(nodamage2))
- 17 trigger_push (speeds [350.0, 370.0, 400.0, 650.0, 900.0, 1000.0, 1100.0, 1750.0, 5000.0]; CS2 would keep accelerating) -> trigger_multiple + script push zones holding CS:GO speed (clamped to 3500); names/filters/Enable/Disable kept
- added point_servercommand port_servercommand + logic_auto port_logic_auto: OnMapSpawn -> mp_freezetime 0, mp_roundtime 600; only T spawns, but the map already has a game_player_equip giving weapon_knife on spawn (unnamed), so no extra knife equip
- visibility hints: lowest 1 (whole map incl. void), low 96 (cells with geometry), medium 0 (densest cells only)
- 27 env_laser + 0 env_beam (CS2 cannot spawn them) -> 19 never-solid func_brush beams between their end points (mutual laser pairs drawn once), coloured self-illuminated laser materials materials/lasers/laser_<rgb>.vmat; 12 TurnOn/TurnOff/Toggle -> Enable/Di...
- stationary lights: 42 of 312 lights switched Static -> Stationary (directlight 3) across 24 sealed compartments, ranges trimmed so no spot is inside more than 4
- 2 materials were alpha-tested / translucent in CS:GO but imported opaque - fixed with a mask from the texture alpha: hotel_glass001 (translucent), offwndwb (translucent)
- radar: rendered from geometry (1307 floor faces shaded by height, walls outlined) -> panorama/images/overheadmaps/mg_bob2_radar_psd.png + game resource/overviews/mg_bob2.txt (pos -4204 10616, scale 14.40)

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 8

## Scripts

- [`scripts/mg_bob2_io.js`](scripts/mg_bob2_io.js)

## Open / to check

- the importer leaves these out (they're on its exclusion list, mostly cosmetic): 142 point_spotlight (spotlight beams), 1 env_lightglow (light glows)
- the map had a CS:GO 3D skybox (sky_camera at -139 1480 659.5, scale 64): its geometry is now ordinary geometry in the map and CS2 ignores sky_camera - move it to a separate skybox map + skybox_reference, or delete it
- 7 trigger_gravity (-) - not converted automatically, needs a look
- ambient_generic sounds not in the addon (stock CS:GO sounds or not packed in the BSP): sounds/admin_plugin/in flames - man made god.vsnd
- overlay materials not converted: materials/decals/custom/bob2.vmat (vmat not in addon); materials/dev/dev_measuregeneric01.vmat (vmat not in addon)
- these lasers did damage in CS:GO but there is no trigger_hurt along them, so in CS2 they are only visual: L3sidep at 4911 3799 5165 (damage 100), Lvl8laserb at 811 4615 2061 (damage 100), lvl8lasera at 811 4615 2088.95 (damage 100)
- beams with no usable end point, removed: L1p
- 1 compartments only partly covered by stationary light (overlap cap) - check weapons are lit there
- check the substituted materials look right: materials/cs_italy/wallpaper02.vmat -> materials/cs_italy/brickwall01.vmat; materials/props/plasticexitsign001b.vmat -> materials/props/metalfan001a.vmat
- materials still missing: materials/decals/custom/bob2.vmat (custom decal with no CS:GO source - left as is rather than swapped for an unrelated decal)
