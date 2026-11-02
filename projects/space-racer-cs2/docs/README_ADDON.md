# Space Racer for CS2: setup and how it plays

A 32-car anti-gravity racer that runs inside this one CS2 map as the cs_script `maps/scripts/space_racer.js`, with
no server plugins. Up to 64 players in two arenas. Retro look and sound: pixel-art tracks, skies and HUD, chiptune
effects and music.

## 1. Install

The addon is `mg_space_racer`. Its map `maps/mg_space_racer.vmap` already contains everything: the eight tracks, the
lobby and booth rooms, the script, HUD, sky, sounds and templates. All other files (models, materials, HUD, sounds,
script) go into the same addon folder next to `maps/`.

## 2. Build the map

Open `maps/mg_space_racer.vmap` in Hammer and build it. Everything is unlit, so there is no light bake to wait for.

The map's main entities:

| Entity | Name | Setting |
|---|---|---|
| `point_script` | `spr_script` | cs_script = `maps/scripts/space_racer.vjs` |
| `custom_hud_layout` | `spr_hud` | Layout = `panorama/layout/custom_game/space_racer.vxml` |
| `point_template` | `spr_tpl_prop` | Template01 = `spr_src_prop` |
| `prop_dynamic` | `spr_src_prop` | Model = `models/spr/null.vmdl`, not solid |
| `info_target` | `spr_booth` | Centre of the sealed room where players' bodies wait |
| `info_map_parameters` | `spr_map_params` | The script ends each CS2 round through its FireWinCondition input |
| `point_soundevent` ×29 | `spr_snd_<name>` | Sound Event Name = `spr.<name>` (the four `mus_*` ones are the music) |
| `env_sky` | `spr_sky` | `materials/spr/sky/sky.vmat` |

Plus: `prop_static` for the eight tracks (one model each, two layers of 2 x 2 boxes, 13,800 units each) inside
moondome shells (each showing its track's own pixel-art sky), vis hints (Lowest over the whole map, Low in the lobby rooms),
`spr_cache_*` props that make every car and effect model available to the script, and the lobby with 32 T and
32 CT spawns about 12,000 units below the tracks.

Loading screen (four slides: `mg_space_racer.png`, `_1`, `_2`, `_3` - CS2 shows nothing when a map has only one),
radar and map icon are in `panorama/images/` and compile with the HUD. The radar's position file
`resource/overviews/mg_space_racer.txt` has to be copied into the **game** addon folder
(`game\csgo_addons\mg_space_racer\resource\overviews\`); content-folder text files are not compiled across.

## 3. How it plays

- Everyone spawns in the lobby; the view slowly circles the track of the next race, and the HUD shows the
  countdown, your car and NEXT TRACK (and the car picker until you have picked a car or raced once). Bodies are
  parked in the booth
  for the whole round; the view is a chase camera behind your car.
- About 2 seconds into each CS2 round (freeze time is set to 0), everyone on T or CT who is not AFK goes to a grid: 1-32 players race together, 33-64 are
  split evenly into two arenas (or, with `ARENA_LAYOUT '4x16'`, up to four arenas of 16) (each with the same share of Ts and CTs), on different tracks. 10-second countdown;
  you can still swap cars until 3 seconds before the lights (`!car`, then A / D).
- Rounds are locked: nobody joins a race in progress. Latecomers watch (Mouse 1 / 2 change car, E change arena)
  and race next round.
- Cars: HORNET (light, drift charge), METEOR (heavy, ram), COMET (afterburn), BASTION (tank, slipstream). The
  picker comes up by itself until you have chosen (A / D) or raced once; after that it stays away - it never covers
  the results - until `!car` (or `/car`, `!pick`) brings it back for 6 seconds. `!car 1-4` or a car's name picks
  straight away. The choice is remembered.
- Shield = health, Charge = boost. Boost pads give free speed; charge platforms (on the slower lines) refill charge
  and shield; drafting behind a car trickles charge; drifting fills it a little. Mouse 1 boosts, Mouse 2 is a spin
  attack (costs charge; it shoves anyone alongside across the road, harder from a heavier car), Space drifts. Shield 0 = wrecked and out. Falling off a rail-less section costs 15 shield
  and a reset. Jump ramps (Skyway) throw you over an open gap: hit them fast or drop in. Bends are banked (they
  grip harder). Once a lap the Pulse (a wave from the back of the field) tops up everyone it passes by 40.
- Turbo start (a secret - nothing in the game says so): press W on the third beep, or after it, and hold it for a
  launch; holding W from before the second beep stalls you briefly.
- Lap records per track are kept while the map runs and shown in the lobby.
- The race ends when everyone is in, 30 seconds after the winner, or at 5 minutes (ranked by distance).
- Results: the top 3 survive. Everyone else takes one CS2 death, credited as kills 50% to 1st, 30% to 2nd, 20% to
  3rd (32 cars: 15 / 9 / 5). A car wrecked by another player's attack is that player's kill at once. The CS2 round
  goes to the side with more cars in the top 8 (added over both arenas; under 8 cars the winner's side gets the
  point; ties go to the better single finish).
- Track vote: when a race ends, its top 3 vote the next track from a box of 4 on the left (W / S, or `!vote 1-4`):
  1st place's vote counts 3, 2nd's 2, 3rd's 1 (only those three vote; CS2 bots don't unless `BOTS_VOTE`). Votes
  can change until the next race is set up. Arenas are re-drawn every round, so each new arena counts the votes of
  the players who end up in it, wherever they voted; if two arenas want the same track, the one with more votes
  behind it gets it and the other takes its next choice. An arena with no voters gets the usual rotation. Everyone
  watching that race sees the box and the votes; the chat line at the next start says which tracks were VOTED.
- Colours: `!shade` changes your car's shade - six reds on T (orange, red, crimson, coral, rose, maroon), six blues
  on CT (blue, navy, cyan, teal, indigo, ice); `!shade 1-6` or a name picks one. It's remembered and changes your
  car at once.
- Winners' glow: last round's top 3 of each race drive the next race with a neon outline glow in their own colour.
- AFK: 20 s without input in a race = warning, 30 s = your car withdraws and you sit out until you press a key or
  type `!back`.
- CS2 bots race using the script's own driving AI (`bot_quota 31` fills a test grid).

## Controls

| Key | Action |
|---|---|
| W / S | accelerate / brake and reverse |
| A / D | steer; move through the cars while the car picker is up |
| E | the car's ability (Hornet Seeker Bolt, Meteor Shockwave, Comet Nova Burn, Bastion Aegis); confirms your car on the picker |
| R | brings the car picker back (when not driving) |
| Mouse 1 | boost (uses charge) |
| Mouse 2 | spin attack |
| Space | drift |
| Mouse | nothing while racing - the camera follows the car and turns a little into the bend ahead |
| Mouse 1 / 2, E (watching) | next car / previous car / next arena (E confirms instead while the picker is up; Space changes arena too) |
| W / S (after a race, top 3) | move your track vote up / down the box on the left |

Chat (`!` or `/`): `!car` (the car picker for 6 seconds; also `!pick`), `!car 1-4` or a name (pick straight away),
`!cam` (camera: high = default, far, near), `!tilt` (camera lean in corners on / off for you), `!crt` (CRT
scanlines on / off for you), `!shade` / `!shade 1-6` (your colour), `!vote` / `!vote 1-4` (the top 3 after a race),
`!music`, `!spec`, `!afk`, `!back`, `!help` or `!race` (controls on your own screen).

## Settings

`maps/scripts/space_racer.js`, search for `const CONFIG`: `ARENA_LAYOUT` ('2x32', '4x16', 'alternate'), laps, countdown, finish window, race cap,
podium size and kill shares, `KO_CREDIT_TO_ATTACKER`, tie-break, AFK times, bot skill, camera distance, and the
cvars the map applies, the camera presets (`CAMERAS`, `CAM_LOOKAHEAD`, `CAM_BANK`, `CAM_SHAKE`), `ENGINE_HUM`,
`MUSIC` (chiptune music for everyone; volume: `MUSIC_VOL` in `tools/sounds.py`), `MINIMAP_DOT_HZ` (how often the
other cars' minimap dots move; 4 instead of 8 halves the biggest share of HUD traffic), `VOTES` / `VOTE_WEIGHTS` /
`VOTE_CHOICES` / `BOTS_VOTE` (the track vote), `WINNER_GLOW` / `GLOW_PLACES` (the winners' glow), `PERF_LOG` (the once-a-minute
`script time` line in the console). The four cars and the physics rules are in `const CARS` / `const RULES` just below.

Joining: with `AUTO_TEAM` on (the default) nobody sees CS2's team menu: anyone on no team after a second is put on
the side with fewer players (the map also sets `mp_force_assign_teams 1` and `sv_disable_teamselect_menu 1`, so the
M menu is off; `!spec` still watches). No money is ever paid: kill and round rewards, start money and the money cap
are all 0.

When `APPLY_CVARS` is on the map sets: `mp_respawn_on_death_t/ct 1`, `mp_respawn_immunitytime 0`,
`mp_teammates_are_enemies 1` (no teamkill penalties for same-side kills), `mp_ignore_round_win_conditions 1`
while a race runs, `mp_death_drop_gun 0`, `mp_buy_anywhere 0`, `mp_buytime 0`, `sv_disable_radar 1`,
`mp_playercashawards 0`, `mp_teamcashawards 0`, `mp_startmoney 0`, `mp_maxmoney 0`, `mp_afterroundmoney 0`, and with
`AUTO_TEAM` `mp_force_assign_teams 1` and `sv_disable_teamselect_menu 1`.

## Servers with plugins (CounterStrikeSharp etc.)

Same risks as FreeDM. On this map, turn off or exempt:
- **AFK managers**: every racer's body stands frozen in a hidden booth, so position-based AFK plugins flag everyone.
  The map has its own AFK check (input while driving).
- **No-respawn / spawn-protection / godmode-on-spawn plugins**: the end-of-race kills need `mp_respawn_on_death_t/ct 1`
  and `mp_respawn_immunitytime 0`. If respawns are blocked, knock-out kills switch to the end of the race by themselves.
- **Teamkill punishment / plugins forcing `mp_teammates_are_enemies 0`**: same-side kills would count as teamkills.
- **Plugins that set round cvars on round start** (`mp_ignore_round_win_conditions`, round time) or end rounds.
- **Weapon / loadout / knife plugins**: parked bodies are stripped of weapons every round; a plugin re-giving them
  shows a viewmodel over the race.
- **Anti-stuck / noblock / third-person plugins** that move or unfreeze bodies or change the camera.
- **Chat commands** `!car !pick !cam !tilt !crt !shade !vote !music !spec !afk !back !help !race` may clash with plugin
  commands (map votes especially: `!vote` / `!rtv` plugins).
- **Team balancers**: balance at round start only; a mid-race team change takes the player out of the race.
