# mg_pokemon_adventure

| | |
|---|---|
| Status | Built 9 Nov 2026, not yet tested in game or uploaded |
| Original map | unknown (no credit in the map, nothing found online) - fill in before upload |
| Source BSP | `mg_pokemon_adventure_v2_hdr.bsp` (from Briar's Dropbox, `CSGO/compiled maps/minigames`) |
| Imported | 2026-11-09 |
| How | autoport (one of five parallel workers) |

## History

- 2026-11-09: ported by autoport from Briar's v2_hdr BSP (main worker). Stage C ran 4 times (79 min) as each pass found more CS:GO files it needed (shack_water, soundscripts, door default sound).
- 2026-11-09: held for 6 textures with no source; all handled in stage C: canalswater_cheap / shack_water -> anubis_water_canal, mountainwall_scrolling rebuilt from CS:GO textures, sky138a rebuilt as a panorama, feebas / green_cloud (packed nowhere) -> stock models/sprays/weeds and effects/fire_cloud2.
- 2026-11-09: the first build spent over 20 min in vis, partly because it overlapped other workers' builds (the main worker's build_maps.ps1 doesn't take the parallel build lock), so autoport rebuilt it with visfit_lean hints: 317 compiled, 0 failed, 86 min 18 s, vis alone 85 min. Look for pop-in; a full-hint rebuild on an idle PC may be worth it.
- 2026-11-09: **music** (skink52's request): the map had none. Eight Pokemon FireRed & LeafGreen tracks from skink52's own files (`E:\offload\source1_sound_extra\pokemon-firered-leafgreen.zip` (moved from C:\source1\sound on 10 Nov 2026), 14 WAVs), shuffled from round start with the next when one ends (`coursemusic.py`). Pokemon Center, Pallet Town and Surf Theme were asked for; Route 1, Viridian City, Cerulean City, Celadon City and Bicycle Theme were picked as upbeat overworld tracks (left out: Lavender Town, Team Rocket Hideout, Mt. Moon, Professor Oak, Cinnabar, Fuchsia), to keep the addon smaller. Encoded to 128 kbps mp3 with `lameenc` (no ffmpeg on the PC): 14 MB, `sounds/port_music/pkmn_*.mp3`. The Steam description lists them. Entities-only build on top of skink52's own Hammer edits of the same day (fire materials, metal gibs). Backups: `mg_pokemon_adventure.vmap.bak_music_20261109`, `soundevents_addon.vsndevts.bak_music`, `... STEAM DESCRIPTION.txt.bak_music`.
- 2026-11-14: **water physics** (`watersplit`): 10 func_water meshes over 384 u cut into 58 closed pieces; CS2 gives a func_water mesh over ~500 u no physics hull, so that water could not be swum in. Entities-only rebuild: 0 func_water hull failures where the cut applied. Backup `mg_pokemon_adventure.vmap.bak_watersplit_20261114_*`. Compiled, not checked in game.

## What the cleanup did

(from the cleanup log in this folder)

- collapsed 6 prefabs into the map, world offsets kept: mg_pokemon_adventure_gameplay.vmap (213 nodes, 213 entities), mg_pokemon_adventure_environment_prefab.vmap (1154 nodes, 311 entities), mg_pokemon_adventure_lighting_prefab.vmap (3 nodes, 3 entities), m...
- outputs restored that the importer dropped: 0
- 27 trigger_push (speeds [40.0, 800.0, 1200.0, 1500.0, 2000.0]; CS2 would keep accelerating) -> trigger_multiple + script push zones holding CS:GO speed (clamped to 3500); names/filters/Enable/Disable kept
- added point_servercommand port_servercommand + logic_auto port_logic_auto: OnMapSpawn -> mp_freezetime 0, mp_roundtime 10, sv_airaccelerate 2000, mp_limitteams 0, mp_solid_teammates 0 (only T spawns); only T spawns (30), so game_player_equip port_knife_eq...
- 10 entities had renderamt < 255 with rendermode Normal (ignored in CS:GO, see-through in CS2): renderamt 255
- 1 Source 1 soundscript names used by entities defined as same-named soundevents: RotDoorSound.DefaultMove
- soundscript waves copied into the addon from the map's packed files / CS:GO VPK: sounds/doors/default_move.wav
- door sounds: 2 point_soundevents (RotDoorSound.DefaultMove), started by the doors' OnOpen/OnClose (noise1) and OnFullyOpen/OnFullyClosed (noise2); 2 unnamed doors named port_door_N
- door sounds: 2 CS:GO doors had no move sound and played CS:GO's default (DoorSound.DefaultMove / RotDoorSound.DefaultMove: doors/default_move.wav at volume 0.2); they get it too
- 1 static overlay materials -> csgo_static_overlay with translucency masks from the original alpha: mrstrugen.vmat
- face texture scales: 4830 brush faces, 4663 matched to one VMF mapping; 4663 matched: same plane; 8 no VMF side on the same plane + material; 159 overlapping VMF brushes with different mappings (left as imported)
- face texture mapping repaired: 4635 faces re-scaled / re-shifted from the VMF, 4711 faces with texture coordinates rewritten: pwood1 (1), canalswater_cheap (31), shack_water (41), fire (42), house_rug (27), housedoor (10), labdoor (6), labouterwall (102),...
- face texture scales: no known texture size (coordinates not checked): canalswater_cheap
- splitfaces: 1204 lit faces over 512x512 in 311 meshes cut into 11366 pieces on a 512 grid (one lightmap chart / probe sample per face: big floors baked blotchy)
- env_sky materials/skybox/sky138a.vmat: rebuilt from the six CS:GO faces
- restored 19 sky brushes (dropped by the importer) as toolsskybox meshes using materials/tools/toolsskybox.vmat
- visfit (48-unit voxels): 3905.8 billion cubic units of playable air, 25.9 of it walkable band; hints 162 Medium, 309 Low, 624 Lower, 1 Lowest
- visfit: 0 of 19 sky shell meshes set to Exclude from Vis, 19 kept because they close playable air
- visfit: 200 Medium cells along 203206 long sight lines across gaps, so nothing pops out of view at the far end
- 10 env_laser + 0 env_beam (CS2 cannot spawn them) -> 10 never-solid func_brush beams between their end points (mutual laser pairs drawn once), coloured self-illuminated laser materials materials/lasers/laser_<rgb>.vmat; 0 TurnOn/TurnOff/Toggle -> Enable/D...
- relight: deleted 239 imported lights; rebuilt from the VMF 239 light -> light_omni2, 0 light_spot -> light_barn (colour, HDR intensity, range, cone); 0 Dynamic (start dark / switched / style)
- light_environment: Static -> Stationary (directlight 3), so the sun lights players and weapons
- added 5 stationary light_omni2 to sealed rooms with spawns / teleport destinations that had no light at all
- stationary lights: 9 of 239 lights switched Static -> Stationary (directlight 3) across 5 sealed compartments, ranges trimmed so no spot is inside more than 4; 1 of the compartments are open to sky (one stationary light each, on top of light_environment)
- 17 materials were alpha-tested / translucent in CS:GO but imported opaque - fixed with a mask from the texture alpha: fire (translucent), brock (alpha test), gary (alpha test), misty (alpha test), professor_oak (alpha test), pkmn_docks (alpha test), pokeb...
- radar water (share of each water face drawn): shack_water z-3776 16%, shack_water z-3776 73%, shack_water z-3744 0%, shack_water z-3744 13%, shack_water z-3744 8%, shack_water z-3744 52%, shack_water z-3552 0%, canalswater_cheap z-832 76%, canalswater_che...
- radar: rendered from geometry (1652 floor faces shaded by height, walls outlined) -> panorama/images/overheadmaps/mg_pokemon_adventure_radar_psd.png + game resource/overviews/mg_pokemon_adventure.txt (pos -4926 13916, scale 16.69)
- built 1 missing materials from the original CS:GO textures: mountainwall_scrolling
- CS:GO water materials (no CS2 equivalent shader) -> stock: materials/liquids/canalswater_cheap.vmat -> materials/anubis/anubis_water_canal.vmat; materials/liquids/shack_water.vmat -> materials/anubis/anubis_water_canal.vmat
- materials missing everywhere swapped for the closest stock CS2 ones: materials/pkmn/strugen/feebas.vmat -> materials/models/sprays/weeds.vmat; materials/pkmn/strugen/green_cloud.vmat -> materials/effects/fire_cloud2.vmat
- %compilewater materials (CS:GO water, see-through) -> F_TRANSLUCENT, opacity 0.55, back faces drawn: pkmn_water_animated
- added point_script mg_pokemon_adventure_io_script (maps/scripts/mg_pokemon_adventure_io.js)
- dropped I/O report (maps/mg_pokemon_adventure_dropped_io.txt): 0 .vmf owners with 0 outputs, 0 matched; 0 outputs missing with the target still there (probable losses), 0 with the target gone, 0 to !special targets; 0 handled by our own steps (script / co...
- static overlays: projection depth set to 8 on 2 overlays
- water: 13 water meshes -> 5 func_water; 4 underwater post_processing_volumes (lighting/postprocessing/postprocess_filmic_underwater.vpost, top 80 u below the surface); master post_processing_volume already there
- water: 23 underwater light_omni2 (map median brightness, range 512, no shadows) in water with no light inside
- probecover: added 45 light probe volumes around 60 static func_breakable / func_brush meshes that no volume fully covered: func_brush (unnamed), func_brush (unnamed), func_brush (unnamed), func_brush (unnamed), func_brush (unnamed), func_brush (unnamed), ...

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 6

## Scripts

- [`scripts/mg_pokemon_adventure_io.js`](scripts/mg_pokemon_adventure_io.js)

## Open / to check

- overlay materials not converted: materials/pkmn/strugen/feebas.vmat (vmat not in addon)
- 2 static overlays have a projection depth >= 32 (can show as a box with the overlay invisible) - stage_d overlaydepth sets them to 8
- placeholder static overlays left alone, no CS:GO texture size: materials/pkmn/strugen/feebas.vmat
- faces still with an absurd texture scale (<0.01 or >8), left as imported: labwindow x28 (VMF: 0.25x0.25/1.5x13/0.5x13), professor_oak x5 (VMF: 0.002x0.2187/0.2187x0.2187), labdoor x4 (VMF: 0.375x0.375/0.0078x0.375/0.0078x0.1875), path_straight x4 (VMF: 0.002x0.375/0.002x1.0002/0.3751x1.0002), pat...
- face scales fixed but texture coordinates not rewritten (no CS:GO texture size): materials/liquids/canalswater_cheap.vmat
- splitfaces: check the cut floors / ramps for seams after the bake
- vis: 14114 long sight lines got no Medium corridor (over the 200 cell limit): look for props popping out across long gaps
- vis: if anything pops in or out of view where players stand, change the nearest Lower hint to Low (or Low to Medium)
- these lasers did damage in CS:GO but there is no trigger_hurt along them, so in CS2 they are only visual: F3T2L1 at -1215.79 11104 164 (damage 100), torn11 at -1215.44 11424 544 (damage 100)
- relight: brightness scale (1000 lumens per 265 _light) is not checked against a real CS2 bake - compare a few rooms with CS:GO
- 1 compartments could not get a stationary light without going over 4 overlapping - check them
- 3 compartments only partly covered by stationary light (overlap cap) - check weapons are lit there
- 60 static func_breakable / func_brush meshes are not fully inside an env_combined_light_probe_volume, so their lighting will be wrong (stage_d.py ... probecover adds volumes): func_brush (unnamed), func_brush (unnamed), func_brush (unnamed), func_brush (unnamed), func_brush (unnamed), func_brush ...
- check the substituted materials look right: materials/pkmn/strugen/feebas.vmat -> materials/models/sprays/weeds.vmat; materials/pkmn/strugen/green_cloud.vmat -> materials/effects/fire_cloud2.vmat
- the map has 8 physics props: if player pushes on them feel wrong in game (too easy or too hard for the prop's size), run the physpush step (run_pass.py ... physpush)
- 1 placeholder static overlays had no infodecal/info_overlay of the same material within 40 units in the VMF - size them by hand (scale = size/2)
- vis: 14179 long sight lines got no Medium corridor (over the 200 cell limit): look for props popping out across long gaps
- underwater lights are a heuristic (Source water was lightmap-lit, CS2 water needs lights): check the water areas after the bake
- probecover: check the new probe volumes look right next to the existing ones
- Existing CS2 port online: ze_pokemon_kanto_v1 (Steam, 4969 subscribers): https://steamcommunity.com/sharedfiles/filedetails/?id=3100100976
- Existing CS2 port online: Pokemon battle PVP (Steam, 1259 subscribers): https://steamcommunity.com/sharedfiles/filedetails/?id=3071527605
- Existing CS2 port online: ze_pokemon_kanto_v1 (Steam, 5829 subscribers): https://steamcommunity.com/sharedfiles/filedetails/?id=3182833713
- Existing CS2 port online: ze_pokemon_johto (Steam, 1163 subscribers): https://steamcommunity.com/sharedfiles/filedetails/?id=3552907522
- Existing CS2 port online: am_pokemon_acs (Steam, 47 subscribers): https://steamcommunity.com/sharedfiles/filedetails/?id=3523810191
- Z-fighting (mg_pokemon_adventure): 52 fully covered faces set to toolsnodraw, as vbsp would have dropped them; 2 smaller faces moved 0.25 units forward where two materials overlapped.
- Z-fighting (mg_pokemon_adventure): 2 faces were moved 0.25 units to stop flicker; look at them in game (tools/zfight.py lists where).
- Lights (mg_pokemon_adventure): 10 moved off walls they would have blown out.
- Lights (mg_pokemon_adventure): 2 sit close to a wall but couldn't move without crossing a face: look for bright spots.
- Z-fighting (mg_pokemon_adventure): 188 small or same-material overlaps left (first: materials/pkmn/environment/cavewall.vmat | materials/pkmn/environment/cavewall.vmat at 1737 12326 -256, 140708 sq units overlap (minor) | materials/pkmn/environment/cavewall.vmat | materials/pkmn/environment/cavew...
- Loading screen credit has no original author yet: add "Original map by <author>" to game\csgo_addons\mg_pokemon_adventure\maps\mg_pokemon_adventure.txt.
- Loading screen images: add at least two (autoport does not make them; docs/porting/pipeline.md, Loading-screen background images).
- Gib check: 1 models given generic CS:GO chunks, 5 missing gib models imported before the build.
- The first build spent over 20 minutes in vis, so vis hints were replaced with visfit_lean and it was rebuilt: look for pop-in.
- Steam description says [ORIGINAL AUTHOR]: fill in the original mapper in C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\content\csgo_addons\mg_pokemon_adventure\mg_pokemon_adventure STEAM DESCRIPTION.txt (and the loading screen credit).
