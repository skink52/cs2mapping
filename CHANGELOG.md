# Changelog

Newest first. Dates are Adelaide time. Entries before this repo existed are rebuilt from file dates on the PC, the cleanup logs, and
earlier working sessions. Dates taken from file timestamps say "(file date)".

## 2026-10-17

- **Repo created** (this repo): pipeline tools, PC runners, a per-map record of every port, the CS2 gotchas list, cs_script notes, and this changelog.
  The pipeline's references to a real name became the handle. `scripts/make_import_map_auto.py` replaces shipping a copy of Valve's importer.
- **Pipeline: `skyvis` pass** (`tools/skyvis.py`, stage C and `stage_d.py ... skyvis`). Moondome and tools/skybox shells around rooms that
  are already sealed by their own walls get "Exclude from Vis". Each shell is checked with a 16-unit voxel flood fill from outside the
  room, and shells a room needs to stay sealed are left alone. Tested on Mario Party (all 64 shells excluded) and on a copy with Platform
  Peril's hull removed (its 2 shells correctly kept).
- **mg_mario_party: vis.** The first rebuild took 103 s to voxelise (19,173,961 nodes) plus 62 s of outside detection. The 64 sky shells
  were about half of all vis surface, so they're now excluded from vis. The 32 Low vis hints were all copies of the whole-map box, and each
  now covers one room. (A first copy of this change didn't reach the PC: the rebuild after it showed the identical node count, and the file was re-sent and verified.)
- **mg_mario_party: gameplay and visual fixes** reported from in-game testing against the CS:GO v3_5 version. See
  [ports/mg_mario_party](ports/mg_mario_party/README.md): flags, A/B buttons, light probe volumes, torch fire, lava and water floors, the Platform
  Peril laser, the arrow decal, Speed SMGs speed, weapon-trigger duplicates, thwomp sounds and bullet bill cannons.
- mg_smee_tower_cs2 and mg_bombardment `.vmap` files were edited (file date). That was a separate session, and its changes aren't recorded here.

## 2026-10-16

- **cs2port pipeline built** (file dates 10:53–18:34): `prep.py` (stage A), `run_import.bat` (stage B), `stage_c.py` and its passes,
  `run_build.bat` / `build_maps.ps1` (stage D, command-line builds with the outroot copy), `stage_d.py` follow-up passes, `daylight.py`, the
  missing-material pass (`assets.py`) and `ports.py` (duplicate check against existing_ports.txt).
- Pipeline ports: **mg_color_dev**, **mg_draw_course**, **mg_fred_all** (stage C, built). mg_draw_course got the first `daylight` pass, and
  mg_fred_all got an enemy-damage gate script. **mg_color_dev** published as 3820639006.
- **mg_ski_mountain** imported, then deleted because a CS2 port already existed. Duplicate checks now come first.
- Batch of nine through stages A–C: **mg_bob2, mg_egypt_course, mg_faohu_course, mg_galaxy_course, mg_kohztec_course, mg_minecraft_adventure,
  de_nuketown, mg_metal_course_level_2, mg_simpsons_course**. All are queued in `build_queue.txt`.

## 2026-10-14 – 15

- **de_rats_1337, mg_lego_course, mg_super_tower**: the first ports cleaned with scripted fixes (the start of stage C): `<map>_io.js` scripts for
  trigger_push / point_servercommand / game_score, restored dropped outputs, moondomes for dropped sky brushes, rebuilt skies.
  The loading-screen credit rule "original map by &lt;author&gt; cs2 port by skink52" starts here. de_rats_1337 published as 3820105155 and
  mg_lego_course as 3820524232.

## 2026-10-09 – 13: the first mg ports (manual flow)

- **mg_smee_tower_cs2** (imported 10-09, published 3816892618), **mg_bombardment** (10-10, 3816918916), **mg_balistic_course** (10-10, 3816960127),
  **mg_enjoy_multigames** (10-10, 3817075436), **mg_awp_submarine** (10-11, 3817816213), **mg_circle_course** (10-11, 3817732135).
  3D skyboxes moved to separate skybox maps for awp_submarine, bombardment and enjoy_multigames.
- **mg_mario_party** (10-11, 3818267169): `mario_io.js` plus overlay, teleport, model and health scripts.
- **mg_n64_goldeneye** (10-12, 3818260481): kept as a reference port.
- **mg_yolo_multigames** (10-12, 3819030057) and **mg_swag_multigames** (10-13): big generated scripts (`yolo_io.js`, `swag_io.js`) replacing about 20 dead mechanisms each.
- Also published in this period: **mg_kirbys_brawl** (3819068027) and **awp_multigames** (3819078634).

## 2026-10-01 – 07

- **ba_jail_lightsout** imported 10-01. The environment prefab was too heavy to collapse in Hammer, so its contents were pasted in with Paste Special.
  The 3D skybox didn't render until "Editor only" was unticked on its `sky_camera`.
- **ba_jail_keimusho** import started 10-07.

## 2026-09 (jailbreak features)

- **jb_water_prison_cs2** imported 09-20: `vehicles.js` (drivable car replacing game_ui; file date 09-20) and `water_immunity.js` (09-29).
- **ba_jail_seaside**: `dodgeball.js` (09-19), `bumper_cars.js` / `buff_new.js` copies (09-24).
- **ba_jail_skylight**: `bumper_cars.js` (09-25), `helicopter.js` (09-25), `keypad.js` (09-28), `buff_new.js` (10-01). The buff script was rewritten
  to track who picks up the named map weapon, after it turned out CS2 doesn't keep a weapon's targetname through a pickup.
- **jb_sides_cs2** radar made with RadGen (09-30).

## 2026-08 (first CS2 ports: jailbreak maps)

- **jb_mangaroons** (08-22), **ba_jail_seaside** (08-24), **jb_yeetnam** (08-28), **jb_renegade** and **ba_jail_skylight** (08-30) imported with Valve's importer.
- Import helpers written as problems came up: `findmissingtextures.py` (08-24), `findmissingmodels.py`, `mdltovmdl.py`, `newcheck.py` (08-26),
  `makealpha.py` (08-27), `modelsfromrefs.py` and **`post_import_cleanup.py`** (08-28). Valve's importer kills the whole run on its first bad model, and
  post_import_cleanup became the standard second step.
