# Hellmatch ZE (mg_hellescape)

Zombie escape for Counter-Strike 2, built on Hellmatch: Freedoom levels rebuilt inside CS2, Doom rules run by a cs_script.

- **Two teams, two copies of the level.** T and CT each run their own copy of the same Freedoom level at the same time.
- **Stages.** Hold zones while gates open, kill the stage guardian, then hold the exit. The first team to escape wins.
- **Dying turns you.** A human who dies rises as a demon (serpentipede, flesh worm or deadflare) in the *other* team's
  copy, and hunts them alongside the level's own monsters.
- v1 level: Freedoom MAP01 "Hydroelectric Plant".

Controls: Hellmatch's (WASD, mouse, E/Space to use, R / Mouse 2 next weapon, F previous weapon). As a demon, Mouse 1 attacks
(claw / bite) and Mouse 2 or R uses the ability (fireball / lunge / dash, with a cooldown shown on the HUD).
Winning: the last team with humans alive wins; a team that escapes wins at once; at the time limit the team with more humans
alive wins (then the team further along).
Chat: !help !hud !spec !afk !back.

## Credits and licences

- Levels, textures, sprites, sounds and music: the Freedoom project, modified BSD licence (`FREEDOOM_LICENSE.txt`,
  `FREEDOOM_CREDITS.txt`). Level authors: Freedoom's `CREDITS-LEVELS`. This addon is not affiliated with or endorsed by
  the Freedoom project.
- Music renders: libADLMIDI (Nuked OPL3, DMXOPL3 bank) or the addon's own OPL2 model with Freedoom's GENMIDI patches; theme
  by skink52 (`MUSIC_CREDITS.txt`).
- Code and original art: Hellmatch, PolyForm Noncommercial / CC BY-NC 4.0 (`LICENSE`, `LICENSE-CC-BY-NC-4.0.txt`).
- The code was written with AI assistance (Claude) under skink52's direction.
