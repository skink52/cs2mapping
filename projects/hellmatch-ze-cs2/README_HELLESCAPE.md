# Hellmatch ZE (mg_hellescape)

Zombie escape for Counter-Strike 2, built on Hellmatch: Freedoom levels rebuilt inside CS2, Doom rules run by a cs_script.

- **Two teams, two copies of the level.** T and CT each run their own copy of the same Freedoom level at the same time.
- **Stages.** Hold zones while gates open, kill the stage guardian, then hold the exit. The first team to escape wins.
- **Dying turns you.** A human who dies rises as a demon (serpentipede, flesh worm or deadflare) in the *other* team's
  copy, and hunts them alongside the level's own monsters.
- Levels (a different one each round until all have been played), four stages each (six on the two long levels):
  - **Hydroelectric Plant** (Freedoom MAP01): hold the floodgate, hold the pump station, the turbine guardian (pain lord), escape
    through the flooded cave.
  - **Outer Prison** (Freedoom E1M1): hold the south gate, hold the flooded hall, the cave slug (combat slug), drop into the pit
    and run through the blue wing to the exit.
  - **Land of the Lost** (Freedoom E3M1): hold the stairs out of the blood pit, hold the temple plaza, the cave spider
    (technospider), run south to the exit gate.
  - **Janus Terminal** (Freedoom MAP06): hold the east gate, hold the pillar hall, the assault tripod in the yard, then run back
    through the blue gate to the terminal exit.
  - **Supply Depot** (Freedoom E1M4, long): hold the entry hall, hold the pillar hall, a pain bringer in the sludge pit, hold
    the walkway over the nukage, a pain lord on the walkway, then run north through the blue door to the exit.
  - **Crude Processing Center** (Freedoom MAP03, long): hold the gallery, hold the pump room, a dark soldier among the pillars,
    hold the crossroads, ride down to the core and destroy the assault tripod, then hold the exit lift.
- Every finished hold refills ammo and health, and the stages hand out weapon upgrades as you go.

Controls: Hellmatch's (WASD, mouse, E/Space to use, R / Mouse 2 next weapon, F previous weapon). As a demon, Mouse 1 attacks
(claw / bite) and Mouse 2 or R uses the ability (fireball / lunge / dash, with a cooldown shown on the HUD).
Winning: the last team with humans alive wins; a team that escapes wins at once; at the time limit the team with more humans
alive wins (then the team further along).
Chat: !help !hud !spec !afk !back.

## Credits and licences

- Levels, textures, sprites, sounds and music: the Freedoom project, modified BSD licence (`FREEDOOM_LICENSE.txt`,
  `FREEDOOM_CREDITS.txt`). Level authors: Freedoom's `CREDITS-LEVELS`. This addon is not affiliated with or endorsed by
  the Freedoom project.
- Music: each level's Freedoom track (rendered with the addon's own OPL2 model and Freedoom's GENMIDI patches, checked by
  numbers for clipping, DC and silence), Freedoom boss tracks E1M8 / E2M8 / E3M8 (libADLMIDI, Nuked OPL3, DMXOPL3 bank),
  Hellmatch's four generated tracks and the theme by skink52 (`MUSIC_CREDITS.txt`).
- Code and original art: Hellmatch, PolyForm Noncommercial / CC BY-NC 4.0 (`LICENSE`, `LICENSE-CC-BY-NC-4.0.txt`).
- The code was written with AI assistance (Claude) under skink52's direction.
