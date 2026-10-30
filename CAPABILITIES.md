# What this toolkit can do

A plain-language list of everything skink52 and Claude (an AI agent) can do for Counter-Strike 2 maps with the tools and methods in this repo and the
project repos it links (Hellmatch, Space Racer, mg_trenchwarfare, Puppet Brawl). Lines marked *(by hand)* are done by Claude per map rather than by a tool;
lines marked *(project repos)* use tools that live in one of those projects, with the method written up here.
No coding knowledge needed to read it. Each line links to the detailed write-up for whoever does the work.

**How it works in practice:** you keep Hammer and CS2 on your PC; Claude works in the cloud, reads and writes your map folders through the Claude desktop
app, and hands you batch files to double-click for the steps that need Valve's tools (importing, compiling). You test in game and say what's wrong.

---

## Porting CS:GO maps to CS2

**Before starting**
- Check whether a CS2 port of the map already exists (our list, the Steam Workshop, GameBanana) and tell you before doing anything.
- Name the CS2 addon cleanly (strips `_v2`, `_final`, `_fix` and similar).
- Keep a running list of which maps are ported, in progress, or ported by someone else.

**Getting the map into CS2**
- Decompile the CS:GO map file (BSP) with its packed-in textures, models and sounds.
- Fix the decompiled map so Valve's importer accepts it, without opening CS:GO's Hammer.
- Run the import and the leftover model/material conversion unattended from one double-click, and even chain it straight into the build while you're away. Models that freeze the importer are stopped and skipped instead of hanging the run, and the report says where each missing file was used and where a file with the same name exists.

**Automatic fixes after import** ([details](docs/porting/pipeline.md))
- Put back map logic (outputs) the importer silently drops.
- Merge the importer's separate prefab pieces back into one map.
- Replace things CS2 no longer has, with scripts that behave like the original:
  push triggers (CS:GO-style speed), low-gravity zones, player speed changers, scoreboard points, server commands, weapon givers (with the right slots),
  toggling walls, hallucination props, breakable glass, multiplayer physics boxes.
- Controls that take over the player's movement keys ("game_ui": steering a boat, aiming a cannon) rebuilt in script with the same outputs *(follow-up step)*.
- Screen overlays rebuilt as on-screen HUD overlays *(by hand per map, e.g. Mario Party)*.
- Lasers and beams (which CS2 can't create) redrawn as glowing beams in the right colour; lasers that did damage get a damage zone along them (a separate step right after the automatic fixes).
- Missing skies rebuilt from the original six sky pictures; sky brushes the importer dropped rebuilt as sky shells.
- Old 3D skyboxes (the miniature scenery CS:GO drew in the distance) moved into their own CS2 skybox map and linked back in *(follow-up step)*; the map's water
  faded into the skybox's water so the sea has no visible edge *(follow-up step)*.
- Cannons that fire physics balls made to fire again.
- Breakable props given back the pieces they break into (and the materials imported models were missing).
- Vents behind breakable grates given their own light; props the old engine drew solid but CS2 draws see-through fixed.
- Valve's own compiled materials turned back into editable ones, so a stock material can be copied and tuned.
- Missing textures rebuilt from CS:GO's own files, water swapped for CS2 water, anything unrecoverable swapped for the closest CS2 texture and flagged.
- CS2 textures that Valve shipped broken (they show the pink error texture) replaced with the map's original CS:GO version.
- Transparent textures (fences, glass, decals) that came through solid made transparent again; glowing/additive and double-sided textures restored.
- Decals and overlays: correct size, position and orientation on the wall, with transparent backgrounds.
- Texture alignment and scale on brushes repaired where the importer got it wrong.
- Displacements (terrain) the importer dropped rebuilt from the original map.
- Lighting so players and weapons aren't black: the right number of lights switched to Stationary per room; for dark indoor maps a follow-up daylight step
  adds sunlight and light probe volumes so props and players match the world; breakables and brush walls that don't move are checked to sit fully
  inside a light probe volume, and volumes are added where they don't.
- Door sounds, ambient sounds and looping sounds converted to CS2 sound events, including stock CS:GO sounds; sound files in formats CS2 can't play re-encoded.
- Named CS:GO sounds ("sound scripts", e.g. a grate clang used by a button) recreated under the same names so they play again.
- Every light rebuilt from the original map: real colours, brightness, spotlight cones and aim, flickering and switchable lights, plus lights under water so it isn't pitch black.
- Steam jets and heat-shimmer effects (gone in CS2) rebuilt as particle effects that switch on and off the same way.
- Physics props (crates, balls) pushed by players according to how heavy they are *(optional step)*.
- Material names the importer mangled (spaces in folder names) pointed back at the real files.
- Glows attached to moving objects (e.g. thrown grenades) made to follow them again.
- Visibility hints placed for fast compiles, and huge sky shells taken out of the visibility calculation.
- A minimap (radar) drawn from the map's own floors with their real textures (tower maps split into levels *(by hand)*).
- Loading-screen credit to the original author ("original map by … / Ported to CS2 by skink52") and loading-screen pictures *(by hand, from the Workshop images you save on the PC)*.
- Round settings (no freeze time, long rounds, a knife on spawn for one-team maps).
- A report of everything that still needs a human look.

**Building and checking**
- Compile maps from the command line one at a time, compiling textures/models/sounds/scripts first and copying the result into the game folder safely.
- Read the build logs and fix compile errors.
- Preview the map as pictures (top-down and from each corner) without opening Hammer.
- Test the map's scripts against a stand-in for CS2 before you load the map.
- Keep a record of every port: what was fixed, what's still open, the Workshop link.

---

## Creating new CS2 addons

**Whole games inside one map, no server plugins** ([guide](docs/creation/guide.md))
- Script-driven minigames where the map itself runs the game: deathmatch arenas, racing, fighting, grid bomb arenas, platform/KZ courses with monsters,
  team battles with mortars and aircraft.
- A drop-in game mode for any existing map: Trouble in Terrorist Town (hidden traitors, carryable bodies to search, a shop, karma, its own Tab scoreboard
  and a panel that hides the killfeed) added to a map with one script and a few entities ([cs2mapTTT](https://github.com/skink52/cs2mapTTT)).
- Several arenas in one map for big servers (e.g. 4 × 16 players), with automatic arena sizing, modes that change each round, spectating, AFK handling,
  bots, chat commands, and round results.
- Real CS2 kills and scores from script, so server ranking plugins count them; podium/kill-share systems for games without shooting.
- Custom cameras (chase cams, fixed fight cameras), players driving vehicles or characters instead of walking.
- Physics games the CS:GO way: pushable props and balls hit by bullets and knives, low-gravity balls, chasing enemies that slide along walls,
  thrown-grenade tracking, vehicles steered with the movement keys.
- Balance and bug testing by simulating thousands of rounds before you ever load the map *(project repos: each game's own simulator; the shared test engine is in this repo)*.

**Maps built by the tools**
- Write a whole map (rooms, terrain, trenches, tracks, lobbies, spawns, lights, sky shells, visibility hints, all the entities the script needs) straight into your
  Hammer map, keeping your own edits; or apply small changes to your latest save without regenerating anything else.
- 3D skyboxes (distant terrain and forests), several different skies in one map, lightmap resolution and light probe setup.
- Check every generated mesh for errors and render previews before you open it.

**Models** ([details](docs/creation/models.md))
- Convert downloaded 3D models (GLB/glTF, e.g. from Sketchfab) into CS2 props with materials, collision and credits.
- Generate original props from scratch with realistic baked textures (wood, rust, cloth, mud, paint), detail levels and collision, or with CS2's own textures.
- Low-poly creatures, voxel characters and objects built from 2D sprites, animated textures (voxel builder in the toolkit; creatures *(project repos)*).
- Turn old CS:GO custom player models (e.g. Octodad) into working CS2 player models with proper animations, hitboxes, ragdolls and first-person arms.
- Animated characters driven by script, with hand-keyed and motion-capture animation retargeted onto the CS2 skeleton (toolkit: mocap retarget, joint checks, rig model writer; game-specific animation *(project repos)*).
- Read and preview CS2's built-in textures and models to reuse them.

**Weapons** ([details](docs/creation/custom-weapons.md))
- New weapons without plugins by replacing a stock weapon's entry: new model, magazine size, spare ammo, zoom, scope.
- Rig a weapon model (FBX/GLB) onto a stock weapon's skeleton so the bolt, trigger and magazine animate; build period scopes; weathered textures.
- Give different weapons per team from script.

**HUD and screens** ([details](docs/creation/hud.md))
- Custom on-screen HUDs: health bars, scores, timers, minimaps with your position, menus with clickable buttons, messages per player, pixel-font or retro styles
  (pixel-font and retro-look generators in the toolkit).
- Full-screen overlays (the CS2 replacement for CS:GO screen overlays).
- Loading-screen slideshows, map icons, minimaps (radar), Workshop preview images, and alignment checks.
- Layout checking at widescreen, ultrawide and 4:3 against where CS2 draws its own HUD, before testing in game.

**Sound and music** ([details](docs/creation/sound.md))
- Sound events (3D sounds with range, looping sounds, music heard everywhere).
- Original synthesised sound effects and music (chiptune and synth generators in the toolkit; Hellmatch's metal soundtrack *(project repos)*), so there's nothing to licence.
- Adding a game's sound events to the addon's sound file without disturbing the ones already there, safe to re-run.

**Publishing** ([details](docs/creation/workshop.md))
- Workshop images; trailers and GIFs with original music *(project repos)*.
- Keeping an addon safe to publish: no copyrighted names, art or ripped models; credits and licences in place.

**Keeping the projects in step** ([details](create/README.md#keeping-the-repos-in-step))
- A fix to a shared tool reaches every game that uses it: one master copy here, checked and copied out to each game's repo, and a warning when a game's own version of a tool changes and the shared one hasn't caught up.

---

## Reference for anyone

- [What breaks in CS2 and how it was fixed](docs/reference/cs2-gotchas.md) — a long list of real problems from these projects.
- [Scripting notes](docs/reference/cs_script-notes.md) — how map logic is done in CS2's JavaScript.
- [Working with Claude](docs/reference/ai-workflow.md) — how the work is split, the house rules, and the practical limits.
- [Outside tools](docs/reference/external-tools.md) — the non-Valve and Valve tools used alongside this repo, and their traps.

## What it can't do

- Run Valve's tools on your PC by itself: you double-click the import/build batch files and play-test.
- Move parts of CS2's own HUD (it can only be hidden all at once), read number keys from script, or change the camera's near clipping.
- Guarantee anything untested in game: every write-up marks what was confirmed in CS2 and what wasn't.
