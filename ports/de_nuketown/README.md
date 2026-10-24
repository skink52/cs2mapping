# de_nuketown

| | |
|---|---|
| Status | Stage C done, vis optimised 18 Oct, queued for build |
| Imported | 2026-10-16 |
| Map last changed | 2026-10-24 |
| How | cs2port pipeline |

The CS2 Nuketown maps on the Workshop (e.g. 3093088534) are remakes of the Call of Duty map, not ports of this one, so it went ahead after the duplicate check.

## History

- 2026-10-16: stages A–C in the second pipeline batch. Its sky is now the CS:GO jungle sky, with 10 moondomes.
- 2026-10-18: vis pass (`visfit`) for compile time. Hints 1 Lowest, 12 Low, 2 Medium → 46 Low, 1 Lowest; hint volume in billion cubic units Medium 0.3, Low 21.3, Lowest 88.6 → Low 24.6, Lowest 93.8. Sky shells: 5 of 10 set to Exclude from Vis. The 5 sky shells around the old 3D skybox (sky_camera 9837 -132 89) and 3 of its meshes are now Excluded from Vis. It is still ordinary geometry that CS2 ignores as a skybox: move it to a skybox map or delete it. Backup: `csgo_addons\prefabs+backups\pre_vis_2026-10-18`.
- 2026-10-24: 152 displacements were dropped at import ("Found a displacement missing a needed subkey."). The 122 in the playable map (grass, mud, gravel, roads, carpets, roofs) were rebuilt from the BSP with `tools/disprestore.py`; the 30 in the old CS:GO 3D skybox (x > 9500) were skipped, since `de_nuketown3dskty.vmap` is a rebuilt skybox. Eight custom materials they use were built from the BSP pakfile (custom/gravel03/04/07/08, realisticwallsandfloors asphault_01/mud_04/mud_06, textures/mygrass5; colour only). `de_train/blendgrassdirt002a` (stock CS:GO, no CS2 copy) → `textures/mygrass3`. Backup: `maps\de_nuketown_pre_disp_2026-10-24.vmap.bak`.

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

- Restored displacements: check seams, the mygrass3 stand-in for blendgrassdirt002a, and that the new terrain doesn't clash with anything added by hand since import.

- Vis: if anything pops in or out of view where players stand, change the nearest Lower hint to Low (or Low to Medium).
- the importer leaves these out (they're on its exclusion list, mostly cosmetic): 1 env_fog_controller (fog)
- the map had a CS:GO 3D skybox (sky_camera at 9837 -132 89, scale 16): its geometry is now ordinary geometry in the map and CS2 ignores sky_camera - move it to a separate skybox map + skybox_reference, or delete it
- check the substituted materials look right: materials/environment_maps/pipeset_metal.vmat -> materials/models/props_pipes/pipeset_metal.vmat
