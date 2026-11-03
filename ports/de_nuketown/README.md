# de_nuketown

| | |
|---|---|
| Status | Published (quality is a bit low) (27 Oct 2026) |
| Workshop | [3825929040](https://steamcommunity.com/sharedfiles/filedetails/?id=3825929040) |
| Imported | 2026-10-16 |
| Map last changed | 2026-11-03 |
| How | cs2port pipeline |

The CS2 Nuketown maps on the Workshop (e.g. 3093088534) are remakes of the Call of Duty map, not ports of this one, so it went ahead after the duplicate check.

## History

- 2026-10-16: stages A–C in the second pipeline batch. Its sky is now the CS:GO jungle sky, with 10 moondomes.
- 2026-10-18: vis pass (`visfit`) for compile time. Hints 1 Lowest, 12 Low, 2 Medium → 46 Low, 1 Lowest; hint volume in billion cubic units Medium 0.3, Low 21.3, Lowest 88.6 → Low 24.6, Lowest 93.8. Sky shells: 5 of 10 set to Exclude from Vis. The 5 sky shells around the old 3D skybox (sky_camera 9837 -132 89) and 3 of its meshes are now Excluded from Vis. It is still ordinary geometry that CS2 ignores as a skybox: move it to a skybox map or delete it. Backup: `csgo_addons\prefabs+backups\pre_vis_2026-10-18`.
- 2026-10-24: 152 displacements were dropped at import ("Found a displacement missing a needed subkey."). The 122 in the playable map (grass, mud, gravel, roads, carpets, roofs) were rebuilt from the BSP with `tools/disprestore.py`; the 30 in the old CS:GO 3D skybox (x > 9500) were skipped, since `de_nuketown3dskty.vmap` is a rebuilt skybox. Eight custom materials they use were built from the BSP pakfile (custom/gravel03/04/07/08, realisticwallsandfloors asphault_01/mud_04/mud_06, textures/mygrass5; colour only). `de_train/blendgrassdirt002a` (stock CS:GO, no CS2 copy) → `textures/mygrass3`. Backup: `maps\de_nuketown_pre_disp_2026-10-24.vmap.bak`.
- 2026-11-03: the 6 overhead `path_particle_rope` cables (cablea/c/e/h/l/o, 16 nodes, `materials/cable/cable.vmat`, slack 0, radius 0.5) replaced with `cable_dynamic` ropes the way skink52's hand-made keimusho rope is built (`tools/ropes.py <vmap in> <vmap out>`, new): one CMapCable per path with `path_node_cable` children at the same positions, cable.vmat, radius 0.5 with the nodes' radius_scale 2 kept, no end caps. The particle ropes were removed, nothing else in the map changed (5,222 other nodes identical on reload). Backup: `maps\de_nuketown.vmap.bak_ropes_2026-11-03`. skink52 then sagged five of them by hand in Hammer (interpolation piecewise Bezier, the chord/3 handles dragged down: 32–43 u on the level 1,350 u spans, 14–30 u on the sloped 450–600 u ones; cablec left straight, cablea's tessellationSpacing left at 258). `ropes.py` now does the same from a rule (`1.2 * sqrt(length) * cos²(angle from level)`, none above 80°) and the map was regenerated with it from the pre-cable backup (all six sagged 12–44 u, tessellation 16; nothing else changed); the hand-sagged map is kept as `maps\de_nuketown.vmap.bak_handsag_2026-11-03`.
- 2026-11-03: Hammer's missing resources (skink52's list): the door_interior_112_01 gib, the four patio_chair parts and the two lamp_floor gibs are CS:GO content → `maps\de_nuketown_fix_refs.txt` for `run_fixrefs.bat de_nuketown`. refrigerator03 and stove02 (prop_static here) point at HL2 gibs CS:GO never shipped (refrigerator03_damaged_01-07, stove02_break01-06, in neither the CS:GO content nor the BSP): `gibfix.py --csgo` dropped those pieces and gave both the five generic metal chunks (`models/gibs/metal_gib1-5`, in the refs). The bus (`models/dinus/bus.vmdl`, custom, from the BSP pakfile) had three skins remapping bus.vmat to bus2/3/4.vmat that were never packed; the map uses the default skin, so the three skins now point at bus.vmat. Backups: `<vmdl>.bak_gibs_2026-11-03` beside each. Refs imported (`modelsfromrefs.py`, 12 models, 0 failures, 31 s; log `cs2port\logs\de_nuketown_fixrefs.log`). Not yet built.

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

- Gibs (3 Nov): build; the build log should show none of the listed resources missing. The fridge and stove are prop_static, so their metal chunks only matter if they are ever made physics.
- Cables (3 Nov): build and check the six sagged cable_dynamic ropes near the poles at x 5300..6600 / y -400..-2300 against the hand-sagged backup (the rule gives a little less sag on the sloped spans than skink52 dragged; raise `SAG_K` in ropes.py if they look too tight).
- Restored displacements: check seams, the mygrass3 stand-in for blendgrassdirt002a, and that the new terrain doesn't clash with anything added by hand since import.

- Vis: if anything pops in or out of view where players stand, change the nearest Lower hint to Low (or Low to Medium).
- the importer leaves these out (they're on its exclusion list, mostly cosmetic): 1 env_fog_controller (fog)
- the map had a CS:GO 3D skybox (sky_camera at 9837 -132 89, scale 16): its geometry is now ordinary geometry in the map and CS2 ignores sky_camera - move it to a separate skybox map + skybox_reference, or delete it
- check the substituted materials look right: materials/environment_maps/pipeset_metal.vmat -> materials/models/props_pipes/pipeset_metal.vmat
