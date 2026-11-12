# mg_monsoon for CS2: setup and how it plays

Conquest in a monsoon river valley, 1968. Two teams fight over five flags with infantry kits, helicopters you fly and ride,
a howitzer battery against a rocket battery, and emplaced heavy machine guns. Bots fill the empty roles when few people play.
Up to 64 players. Runs entirely inside the map's own script (`cs_script`): no plugins.

AI-generated (Claude) for skink52. Version `mv-0.5 (12 Nov 2026, review pass 3: bot balance)`.

**Status: compiled, not yet loaded in CS2.** The map, its 3D skybox and the assets compiled without errors on 12 Nov 2026; nobody
has opened them in Hammer or played them. Everything below describes what the script and map are written to do. The rules were run
on a mock engine (**simulated**); the map, models, HUD and sounds were checked offline and compiled. Nothing in this file is in-game
verified. The checklist that turns "written" into "verified" is `TESTING_MONSOON.md`.

**Which build is this?** A private-server build contains models converted from Garry's Mod Workshop packs and four GMod player
models (`CREDITS.md`); those must not be uploaded to the public Steam Workshop. A public build uses only this project's own models,
the credited Apache and CS2 stock, and players wear CS2 agents.

## 1. Install

Copy the content folders into `content\csgo_addons\mg_monsoon\` (maps, models, materials, panorama, sounds, soundevents,
postprocess) and the game folder into `game\csgo_addons\mg_monsoon\` (`resource\overviews\mg_monsoon.txt`). Close Hammer first
and back up `maps\mg_monsoon.vmap` if it exists. On skink52's PC `python -I tools/deploy_monsoon.py --apply` does this
(changed files only, with backups); see `docs/BUILD.md` in the source repository.

## 2. Build the map

1. Open `maps/mg_monsoon.vmap` in Hammer. The `point_script` `mv_script` (`cs_script` = `maps/scripts/mg_monsoon.vjs`) and the
   `custom_hud_layout` `mv_hud` (`panorama/layout/custom_game/mg_monsoon.vxml`) fields must not be red.
2. Build with lightmaps at 2048 (command line: `build_maps.ps1 final mg_monsoon`), then the 3D skybox map with its own line
   (`build_maps.ps1 final "mg_monsoon mg_monsoon_3dskybox"`, one quoted argument). Foliage and small props are probe-lit on
   purpose; do not switch them to baked lighting (the lightmap bake runs out of memory on charts). The full map build took 42-66 min
   on skink52's PC.
3. Compile these directly as well, every time they change (a failed layout is ignored silently):
   `game\bin\win64\resourcecompiler.exe -f -i content\csgo_addons\mg_monsoon\<file>` for
   `panorama/layout/custom_game/mg_monsoon.xml`, `panorama/styles/custom_game/mg_monsoon.css`, `maps/scripts/mg_monsoon.js`.
4. `map mg_monsoon`. The console should print `[mv] mg_monsoon script mv-0.5 (12 Nov 2026, review pass 3: bot balance) - flags 5,
   bots on (quota 10)`, then `[mv] points: spawns 16/16, helicopters 3/3, guns 4/3, mounts 8, uniforms cached N` (N = 4 in a
   private-server build, 0 in a public one), and no `[mv] missing entity` line.

## 3. How it plays

Teams: CT = US airmobile, firebase on the south-east hill. T = PAVN, jungle camp in the north-west.

- **Flags.** Five: A Paddies, B Bridge, C Village, D Temple, E Crash Site. Stand within 350 units of a flag pole, on foot, to
  capture: 15 seconds for one player, faster with up to three. Both teams inside = frozen. A held flag is a spawn point and
  its supply crate is a kit station.
- **Tickets.** 400 each. A death costs one. A team holding three or more flags bleeds the other side: one ticket every 3
  seconds per flag over two. Zero tickets or the 20-minute clock ends the round.
- **Deploying.** Everyone spawns in the briefing room. A card shows your role and a countdown (10 s the first time, 5 s
  after). Infantry press R during the countdown to cycle the deploy point (base or a held flag), or type `!spawn a` .. `!spawn e`,
  `!spawn base`.

### Roles

Type the command to ask for a role; you get it at once if a place is open, otherwise on your next respawn. With no preference
the script sometimes draws you into a battery seat or an air slot (more often after kills and good fire missions).

| Role | Command | Places per team | What you do |
|---|---|---|---|
| Infantry | `!infantry` | everyone else | take flags, call fire missions, ride helicopters, man the heavy guns |
| Artillery | `!artillery` | CT 3 howitzers, T 4 rocket launchers, 2 crew each | answer fire missions from the plotting board; silence the enemy battery |
| Aircrew | `!air` | 3 helicopters | fly: carry infantry to flags and karst tops, rocket runs with the gunships |

### Infantry kits

At your base arms rack or a held flag's supply crate press E to cycle, or type the command.

| Kit | CT | T | Limit |
|---|---|---|---|
| Rifleman `!rifle` | M16A1 (CS2 M4A1) + pistol | AK-47 + pistol | none |
| Machine gunner `!mg` | M60 (M249) | RPD (Negev) | 1 in 4 |
| Anti-tank `!at` | M72 LAW | RPG-7 | 1 in 4. The Zeus is the trigger: firing it launches a rocket (blast 180 units, 120 damage, 60 to a helicopter). 25 s reload |
| Marksman (flag crates only) | M21 (G3SG1) | SVD (SCAR-20) | 1 per 8 players |

The weapons are the stock CS2 ones under period names; no custom weapon models ship in this version.

## Controls

**Infantry**

| Key | Does |
|---|---|
| E at an arms rack / supply crate | next kit |
| Hold E about 1.2 s looking at open ground 400+ units away | call a fire mission there (one of yours at a time, five per team, 45 s). An enemy killed near your mark by the battery credits you |
| E at a friendly helicopter that is landed or hovering low | board (gunner seat first, then rider seats) |
| E behind an M2 / DShK / quad-50 | man the gun |
| Hold E 6 s at a silenced friendly gun | repair it |

**Helicopter, pilot**

| Key | Does |
|---|---|
| SPACE / CTRL | climb / descend. Hands off holds the altitude |
| Mouse | turns the nose |
| W S A D | tilt forward / back / sideways: the helicopter accelerates that way |
| MOUSE1 | rocket pairs (Apache, Mi-8 gunship). The home pad repairs in 8 s and re-arms |
| E | get out, only when landed. Land level and slower than about 3 m/s; a hard or tilted touchdown is a crash |

Instruments: horizon, airspeed, radar altimeter, vertical speed, heading tape, airframe bar, RTB lamp, rocket count, crew list.
Leaving the map's air space turns you back; far outside destroys the helicopter. A destroyed helicopter is replaced on its pad
after 45 s. Nobody aboard is hurt by bullets: hits cost the airframe, and a crash kills everyone aboard.

**Helicopter, gunner and riders**

| Key | Does |
|---|---|
| MOUSE1 (gunner) | fire (Apache chin gun, Mi-8 door gun). The gun overheats: watch the heat bar |
| E | leave. Below about 11 m with the helicopter slow you fast-rope and take no fall damage; higher, you fall |
| `!swap` | move to the next free seat |

Seats: Apache = pilot, gunner, two riders on the stub wings. Mi-8 transport = pilot, door gunner, four riders. Mi-8 gunship =
pilot, door gunner, two riders.

**Artillery**

| Key | Does |
|---|---|
| E at the ammo rack | take a round. MOUSE2 at the rack picks the type (CT: HE, WP smoke, Beehive). Carrying slows you |
| E at the breech | load. T crews can load up to four rockets, fired as a salvo |
| E at the plotting board | sit at the board (a top-down map) |
| W A S D on the board (SHIFT = fine) | move the reticle |
| R | cycle the team's fire missions and enemy gun flashes |
| MOUSE1 | lock the target: the gun turns and elevates (LAYING, then LAID) |
| SPACE on the board, or E / SPACE at the gun | fire when LAID and loaded |

One person can run a gun alone at about half the rate. HE: 330-unit blast. WP: a 25 s smoke screen. Beehive (CT, target inside
900 units): a direct-fire cone for base defence. A shell or rocket within 260 units of an enemy gun silences it for 40 s; any
teammate can repair it early.

**Mounted guns** (3 M2 and a quad-50 at the firebase, 2 DShK at the camp, an M2 at the bridge and a DShK at the temple for
whoever gets there): E to man, mouse aims inside a cone, MOUSE1 fires, E leaves. About 6 s of fire overheats, 4 s to cool.

### Chat commands (`!` or `/`)

`!infantry` `!artillery` `!air` `!rifle` `!mg` `!at` `!roles` (the role card, also `!help`) `!swap` `!spawn <a-e|base>`
`!pos` (prints your position and map grid square) `!uniform` (toggle the team uniform model, when the build has one) `!bots <0-24>`
(a vote: more than half of the humans on the server must ask for the same number within 30 s; alone you decide).

### Bots

CS2 bots play as infantry: the script places them at a deploy point and brings back one that leaves the playable band or stands
idle too long. When a team has fewer than 4 humans the script also puts bots in the vehicle roles and runs those itself: one AI
pilot (patrol, rocket runs on the gunship, back to the pad when damaged), up to two AI gunners, one AI battery crew that
fires at marks and clusters. A bot always gives its seat to a human who asks for the role. The navigation mesh is confined with
NONAV volumes to the valley floor, roads and bases. How CS2 bots behave on this nav, and while parked in a seat, is untested.

## Settings

One `CONFIG` object at the top of the script (`src/00_config.js` in the source; rebuild with `node tools/build_script.mjs`,
then recompile the `.js`). The ones a mapper or server is likely to change:

| Key | Default | What |
|---|---|---|
| `CVARS` | list | server settings sent when the map activates (see "Servers with plugins"). Empty the list to keep your own |
| `BOTS_ON`, `BOT_QUOTA`, `BOT_QUOTA_MAX`, `BOTS_CHAT` | true, 10, 24, true | bots on the map, default and largest quota, whether `!bots` works |
| `AI.MIN_HUMANS_FOR_ROLES`, `AI.PILOTS`, `AI.GUNNERS`, `AI.CREWS` | 4, 1, 2, 1 | when bots take vehicle roles, and how many |
| `CONQUEST.TICKETS`, `ROUND_SECONDS`, `CAPTURE_SECONDS`, `BLEED_FLAGS`, `BLEED_SECONDS` | 400, 1200, 15, 3, 3 | round length and pace |
| `LOBBY_FIRST`, `LOBBY_RESPAWN` | 10, 5 | seconds in the briefing room |
| `ROLES.ARTY_CHANCE`, `AIR_CHANCE` | 0.18, 0.08 | chance of being drawn into a battery or air slot without asking |
| `KITS`, `AT` | | weapon class per kit and team, kit shares, the anti-tank rocket |
| `HELI` | | flight feel (`V_FWD` 900, `VS_MAX` 380, `ACCEL` 0.7, tilt), health 100, respawn 45 s, pad repair 8 s / re-arm 40 s, rope height 450 |
| `HELI_MODELS`, `HELI_KINDS` | | seats, gun and rocket positions per model; which model is on which pad |
| `ARTY`, `BOARD` | | shell damage and radius, spread, flight time, laying speed, silence / repair times, mission limits |
| `MOUNT` | | heavy gun damage, cone, heat |
| `UNIFORMS_ON`, `UNIFORMS` | true | team uniform player models; only used when the map caches the model (a private-server build ships four GMod player models; a public build ships none, so players keep CS2 agents: set `UNIFORMS_ON` false there) |
| `POOL` | | effect pool sizes; must match the map |
| `PERF_LOG` | 60 | seconds between script-time lines in the console |

## Servers with plugins

- Cvars the map sets on activation: `mp_respawn_on_death_t 1`, `mp_respawn_on_death_ct 1`, `mp_respawn_immunitytime 0`,
  `mp_respawnwavetime_t 0`, `mp_respawnwavetime_ct 0`, `mp_freezetime 0`, `mp_roundtime 21`, `mp_ignore_round_win_conditions 1`,
  `mp_buy_anywhere 0`, `mp_buytime 0`, `mp_death_drop_gun 0`, `mp_weapons_allow_map_placed 1`, `mp_free_armor 0`,
  `mp_solid_teammates 1`, `mp_give_player_c4 0`, the money cvars to 0, `mp_autoteambalance 1`, and `bot_quota_mode fill` /
  `bot_quota 10`.
- The script parks players (frozen, hidden, tiny) while they sit in a helicopter, on a mounted gun or at the plotting board,
  moves them every tick, and gives them a custom camera. AFK managers that look at position, anti-stuck, noblock, third-person
  and loadout plugins are the likely conflicts. `SERVER_ISSUES.md` in the source repository lists them.
- Script time: about 0.1 ms per tick at 32 to 64 players **on the mock engine** (its traces are stand-ins). No server measurement
  exists. Once a minute the console prints `[mv] perf: X ms/tick avg, Y ms max, N ticks, H HUD calls/tick, P players (h human),
  F flying, R rockets, S shells, tickets T/CT, errors E`.
- Size: the compiled map is about 176 MB (`mg_monsoon.vpk`) plus the 3D skybox (`mg_monsoon_3dskybox.vpk`, about 56 MB). The content
  addon of a private-server build is about 1.2 GB of sources, over 500 MB of which are the converted third-party models.
- Bots: navigation is kept to the bases, flags, roads and two walking routes (15,033 nav areas); a bot that wanders off it is
  re-deployed after standing still 20 s. A human can take over a bot (CS2's bot takeover): the bot gives up any helicopter, gun or
  battery seat first.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Console prints an old version | old compiled script or HUD: recompile the `.js`, `.xml`, `.css` (step 3), `disconnect`, load again |
| `[mv] missing entity <name>` | the map and script disagree on a name (`docs/CONTRACT.md`): regenerate the map and the script from the same `out/` |
| `[mv] error in <where>: ...` | a script exception (caught, printed at most every 2 s): send the line |
| Pink checkerboard / ERROR model | that model or material did not compile: see the build log |
| No HUD | `mv_hud` must point at `panorama/layout/custom_game/mg_monsoon.vxml`; a layout that fails to compile is ignored |
| Silent helicopters or guns | events missing from `soundevents_addon.vsndevts` (block `mg_monsoon`), or the `point_soundevent` is missing |
| Script not running | `mv_script` must use `maps/scripts/mg_monsoon.vjs`; look for a JavaScript error line |
| Round never ends / never restarts | see the three console lines in TESTING_MONSOON.md section H |
| FPS drops with bots | nav mesh too large: check the NONAV volumes took effect (nav area count in the build log: 15,033 on 12 Nov 2026) |

## Credits

See `CREDITS.md`. The US helicopter is "AH-64E Apache "Guardian"" by Jeyhun1985, CC-BY-4.0. A private-server build also contains
converted Garry's Mod Workshop models and player models, credited there by pack, author and Workshop id.
