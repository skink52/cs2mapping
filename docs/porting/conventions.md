# House rules for ports

These are the standing rules every port follows. The pipeline applies most of them automatically. The rest are checked by hand.

## Before starting a map

- **Check for an existing CS2 port first.** Look in `existing_ports.txt` (`tools/ports.py check`, which ignores prefixes, `_cs2` and
  version suffixes) and search the Steam Workshop and GameBanana. If a port already exists, report it and don't port the map unless asked.
  (mg_ski_mountain was ported and then deleted because a CS2 port already existed, and mg_50arenas was ported before an existing one turned up.)
  mg_simpsons_course, mg_metal_course_level_2 and de_nuketown were reported first and then ported on request: commenters say the existing
  simpsons port crashes and can't be completed, and the CS2 Nuketown maps are Call of Duty remakes rather than ports.
- **Workshop pages: never report an item as "removed" or "incompatible" from the page text.** Every Workshop page's HTML carries that
  wording as hidden template text, and page fetchers pick it up. A page that shows visitor and subscriber stats is live.
- **Addon name = map name with version and bloat stripped.** `_v2`, `_v1_2`, `_b3`, `_rc1`, `_final`, `_fix`, `_beta`, `_csgo`, `_hdr`, `_ws`...
  (`mg_x_v2_final` → `mg_x`). Use `bspname=addonname` to force a different name.
- **Log it.** Add the map to `existing_ports.txt` as `<addon> [in progress] [skink]`. A successful command-line build changes it to
  `[in progress, built]`. Lines tagged `[briar]` belong to another porter and are maintained by hand. `[ported]`, `[*original*]` and
  `[ext. port]` lines are never changed by the tools.

## In every port

- **Credit the original mapper** in the loading-screen text: `original map by <author> cs2 port by skink52`. Credit a CS:GO porter
  too when the map names one (mg_smee_tower_cs2: "Original map by Mathijs / CS:GO port by WriteX / Ported to CS2 by skink52"). The text
  lives in `game\csgo_addons\<addon>\maps\<map>.txt`, first line `COMMUNITYMAPCREDITS:` (the file Hammer5Tools' Loading Editor writes),
  and needs no rebuild. Find the author in the map's own credits, its GameBanana page or the BSP's embedded files.
  Chat credits that the map printed through `point_servercommand` keep working through the map's script, with "Ported to CS2 by skink52" added.
- **Round setup.** A `point_servercommand` driven by a `logic_auto` sets `mp_freezetime 0` and `mp_roundtime 600` on map spawn.
  If the map only has one team's spawns, a `game_player_equip` gives a knife on spawn (unless the map already does that).
  Two caveats: community servers block `point_servercommand` by default, and 600 is probably above the round-time limit (CS:GO capped it at 60 minutes).
- **Weapons and players must not be black.** CS:GO lights import as Static (baked only), which leaves weapons and player models unlit.
  Switch enough lights to **Stationary** (`directlight 3`): at least one per sealed compartment, spaced so no spot is inside more than
  four stationary lights, and no more than needed. Compartments open to a `light_environment` are fine as they are.
- **Light probe volumes.** Without an `env_combined_light_probe_volume`, brush entities, props, players and weapons don't get the baked
  lighting, so they look different from the world (Mario Party's platforms were brighter than the walls). One per room is enough.
- **Lasers.** CS2 can't spawn `env_laser` / `env_beam`. Replace each with a never-solid `func_brush` drawn between its end points with a
  self-illuminated laser material in the beam's colour. Add damage only where a `trigger_hurt` already exists. If a laser did damage
  with no `trigger_hurt` along it, flag it rather than inventing one. If a trigger_hurt moves (parented to a door / mover), parent the beam to the same mover.
- **Loading screen.** Every map gets a background image (Workshop preview) in `panorama/images/map_icons/screenshots/<res>/<map>_png.png` + `.vtex` (see pipeline.md).
- **Radar.** Every map gets a minimap: `panorama/images/overheadmaps/<map>_radar_psd.png` + `.vtex`, and `resource/overviews/<map>.txt` in game.
  Stacked maps (one spawn above another) get vertical sections, one image per level.
- **Sky.** Sky brushes the importer dropped come back as moondome boxes using the map's `env_sky` (rebuilt from the six CS:GO faces
  if CS2 doesn't have that sky).
- **Vis hints.** One `visibility_hint` set to Lowest covering the whole map, including the void. Low where players stand (the walkable
  band, up to 160 units above a floor), Lower over the rest of the playable air near geometry (high ceilings, shafts). Medium only
  sparingly, where the playable space has very complicated meshes. `visfit.py` builds this from the map.
- **Sky shells out of vis.** Moondome and tools/skybox shells around a room that is already sealed by its own walls get
  "Exclude from Vis". They're huge surfaces and otherwise dominate the vis compile.

## Multi-arena maps (original minigame addons)

**New in the late-October 2026 CS2 update:** a `toolsskyboxocclude` tool material that does the job of the moondome shells (a surface that shows the sky and closes off the void). Reported by skink52; not yet tested in our maps or wired into the pipeline, which still writes `csgo_moondome` shells. Check the exact material path in Hammer's tools materials before scripting it.

Enclose each arena in a moondome (sky-material shell) with a tools/skybox shell 1 unit inside it, so the environment lighting works.
Use one box per arena rather than one big shell (mg_50arenas has 53), and keep each box close to its arena: the vis compile pays for every unit of volume.
Vis hints as above: Lowest for the void between arenas, Low throughout the arenas, Medium sparingly. If the arenas add up to a huge volume,
use Lower (`hintType` 8) instead of Low. Never Lowest alone: with only 256-unit regions, walls vanish a few steps back.

## Working on the files

- **Hammer stays closed** while Claude edits a map. Back up the `.vmap` before editing it.
- **Send only changed files** back to the PC.
- **Build from the command line, one map at a time.** Run `run_build.bat` (`resourcecompiler` with Hammer's full-build arguments), with Hammer and CS2 closed.
  Copy the built `.vpk` out of the temp outroot into `game\csgo_addons\<addon>\maps\` **before** the next compile starts. Builds that
  skipped this step clashed. `build_maps.ps1` does it and checks the copy.
- **Assets compile before the map.** A command-line map build doesn't compile materials Hammer never loaded, and a missing material
  makes its meshes fail. `build_maps.ps1` compiles the addon's materials, models, radar, sounds and scripts first.
- **Workshop uploads** use game mode **Custom**. The mapper manages Workshop titles and descriptions.
- Public repos and READMEs carry the short "AI-generated code" disclaimer.
