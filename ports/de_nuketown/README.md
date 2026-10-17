# de_nuketown

| | |
|---|---|
| Status | Stage C done, queued for build |
| Imported | 2026-10-16 |
| Map last changed | 2026-10-16 |
| How | cs2port pipeline |

The CS2 Nuketown maps on the Workshop (e.g. 3093088534) are remakes of the Call of Duty map, not ports of this one, so it went ahead after the duplicate check.

## History

- 2026-10-16: stages A–C in the second pipeline batch. Its sky is now the CS:GO jungle sky, with 10 moondomes.

## What the cleanup did

(from the cleanup log in this folder)

- collapsed 6 prefabs into the map, world offsets kept: de_nuketown_gameplay.vmap (38 nodes, 38 entities), de_nuketown_environment_prefab.vmap (3004 nodes, 1026 entities), de_nuketown_lighting_prefab.vmap (4 nodes, 4 entities), de_nuketown_cubemaps_prefab.vma...
- outputs restored that the importer dropped: 0
- added point_servercommand port_servercommand + logic_auto port_logic_auto: OnMapSpawn -> mp_freezetime 0, mp_roundtime 600
- env_sky materials/skybox/jungle.vmat: rebuilt from the six CS:GO faces
- restored 10 sky brushes (dropped by the importer) as moondome meshes using materials/skybox/jungle_moondome.vmat
- visibility hints: lowest 1 (whole map incl. void), low 12 (cells with geometry), medium 2 (densest cells only)
- stationary lights: 0 of 18 lights switched Static -> Stationary (directlight 3) across 0 sealed compartments, ranges trimmed so no spot is inside more than 4; 1 compartments open to sky left to light_environment
- 7 materials were alpha-tested / translucent in CS:GO but imported opaque - fixed with a mask from the texture alpha: hotel_glass001 (translucent), offlightcover (translucent), offlightcover_off (translucent), metalfence003a (translucent), metalfence007a (tr...
- radar: rendered from geometry (886 floor faces shaded by height, walls outlined) -> panorama/images/overheadmaps/de_nuketown_radar_psd.png + game resource/overviews/de_nuketown.txt (pos 2570 1774, scale 5.86)

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 11

## Open / to check

- the importer leaves these out (they're on its exclusion list, mostly cosmetic): 1 env_fog_controller (fog)
- the map had a CS:GO 3D skybox (sky_camera at 9837 -132 89, scale 16): its geometry is now ordinary geometry in the map and CS2 ignores sky_camera - move it to a separate skybox map + skybox_reference, or delete it
- check the substituted materials look right: materials/environment_maps/pipeset_metal.vmat -> materials/models/props_pipes/pipeset_metal.vmat
