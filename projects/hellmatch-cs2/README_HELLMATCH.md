# Hellmatch CS2: setup

Hellmatch is a retro 90s-style deathmatch that runs inside one CS2 map, with no server plugins. The whole game runs in the map's cs_script (`maps/scripts/freedm.js`): movement, weapons, items, doors, lifts, teleporters, monsters and frags. The levels, textures, sprites, sounds, music and status bar graphics come from the Freedoom project's FreeDM (see Credits).

(Hellmatch was called "FreeDM Arena" before 17 Oct 2026. Internal file and entity names still say `freedm` / `fdm`; players never see them.)

## 1. Install

The addon folder is `mg_freedm`. Its map `maps/mg_hellmatch.vmap` already contains everything: the 32 levels, door and lift props, the lobby, the booth, sounds, music, the script, the HUD, sky and fog.

All other files (models, materials, HUD, sounds, script) go into the same addon folder, next to `maps/`.

## 2. Build the map

1. Open `maps/mg_hellmatch.vmap` in Hammer.
2. Build it. The first build compiles about 2,200 materials and 800 models, so it takes a while.

The map's main entities:

| Entity | Name | Setting |
|---|---|---|
| `point_script` | `fdm_script` | cs_script = `maps/scripts/freedm.vjs` |
| `custom_hud_layout` | `fdm_hud` | Layout = `panorama/layout/custom_game/freedm.vxml` |
| `point_template` | `fdm_tpl_prop` | Template01 = `fdm_src_prop` |
| `prop_dynamic` | `fdm_src_prop` | Model = `models/fdm/null.vmdl`, not solid |
| `info_target` | `fdm_booth` | Centre of the small sealed room (players' bodies wait here) |
| `point_soundevent` ×95 | `fdm_snd_<name>` | Sound Event Name = `fdm.<name>` |
| `point_soundevent` ×14 | `fdm_mus_<track>` | Sound Event Name = `fdm_music.<track>` (music) |
| `env_sky` | `fdm_sky` | `materials/fdm/sky/sky.vmat` |
| `env_gradient_fog` | `fdm_fog` | Black, 256 to 3000 units (the classic light fade) |

Everything else is plain props:
- `prop_static` for the 32 levels.
- `prop_dynamic` named `fdm_mXX_f/cNN` for doors and lifts.
- `fdm_cache_*` props that make every model available to the script.
- The lobby, with 32 T and 32 CT spawns, about 12,000 units below the levels.

## 3. How it plays

- Players spawn in the lobby. After freeze time everyone on T/CT goes into the arenas: one arena up to 15 players, two from 16 (8 + 8), four from 32 (8 each, up to 16 each), always split evenly. A round needs at least 2 players on T/CT (bots count); the lobby shows what it is waiting for and the time left in a running round.
- Each round has one mode, and every arena plays it (team modes only when every arena gets players from both sides). The players vote for it at the end of the round before (below); the first round of a map, or one nobody voted for, picks at random with these chances:

  | Mode | Rule | Chance |
  |---|---|---|
  | Free for all | First to 20 frags (fewer in small arenas) | 30% |
  | Team deathmatch | First team to 32 frags. T = red, CT = blue | 30% |
  | Boss Battle | Co-op: everyone in the arena against 4 waves of monsters, then a boss. 3 lives each. See below | 15% |
  | Team elimination | One life each, last team standing | 15% |
  | Last man standing | One life each, last player standing | 10% |

- **Next-mode vote.** When a round ends, a ballot shows on everyone's screen for 10 seconds (`VOTE_SECONDS`): Mouse 1 = free for all, Mouse 2 = team deathmatch, E = team elimination, R = last man standing, F = Boss Battle, or type `!ffa`, `!tdm`, `!elim`, `!lms`, `!boss` (or `!vote <mode>`). Press another key to change your vote; a `>` marks yours and the totals update live. Top fraggers count for more: a vote is worth 1 + 2 x (your frags / the most frags in your arena), so the arena's top fragger counts 3, someone on half the top score 2, someone with none 1 (the top right shows what yours is worth). No mode plays three rounds running: after two in a row it is left off the ballot. Only modes that can be played with the people there are offered (team modes need players on both sides; small groups don't get team modes), and if the winner can't be played when the next round starts (people left), the next-best choice is used. The result goes to chat and the centre of the screen; if CS2's break between rounds is shorter than the vote, the next round waits for it. Bots don't vote.
- **Boss Battle** (co-op). The arena's players (T and CT together, no damage between them) start with a real weapon and fight waves of Freedoom's creatures: zombies, serpentipedes and flesh worms first, then trilobites, pain bringers, dark soldiers, combat slugs, technospiders and flame bringers. Waves are sized to the number of players and the level. `MONSTERS.difficulty` in the settings (default 1.35; 1 = the original balance) scales wave size, how fast a wave arrives, boss health and the boss's escort. Boss Battle plays on the bigger half of the levels (the biggest quarter twice as often); `BOSS_MAP_BLACKLIST` in the settings removes levels from it. Monsters that lose track of the players for 20 seconds (stuck behind geometry, sniping from a ledge) come back through a teleporter near them, so a wave can't stall. Leaving the arena (`!spec`, AFK, team change) ends your entry for that round: you watch until the next one, like a one-life round. The 5th wave is the boss, with an escort: an assault tripod (the cyberdemon), twin assault tripods (each weaker; 6+ players), a large technospider (6+ players, where it fits), a summoner swarm (a few summoners, each spitting deadflares; Doom's cap of 20 flares per level applies) or a pack of pain lords. Only bosses that fit in the level are picked, and the kind the last Boss Battle arena got is much less likely next time. Everyone has 3 lives; out of lives means spectating. The arena wins when the boss dies, loses when everyone is out of lives or 8 minutes pass. The status bar's frag box counts your monster kills; the top-right lines show the wave, what is left to kill and your lives. For the CS2 round, a won Boss Battle arena counts for the side (T or CT) with more monster kills in it. Monster kills aren't CS2 kills (there is no pawn to kill), so the Kills column and rank plugins see none; at the end of the round the arena's top 3 monster killers get real CS2 kills: everyone else in the arena dies credited to them, shared 50% / 30% / 20% like Space Racer's podium (`MONSTER_PODIUM`, `MONSTER_PODIUM_SHARES`); each monster kill also adds 2 points to your CS2 Score (10 for a boss; `MONSTER_SCORE`, `MONSTER_SCORE_BOSS`), and `MONSTER_KILL_COMMAND` can send each kill to a server plugin as a console command (e.g. `hm_monster_kill {slot} {boss} {monster}`) if you have one that counts them. Dying to a monster is a CS2 death with no attacker. Boss Battle has its own music: the boss-level tracks of Freedoom's four episodes (E1M8 to E4M8).
- **Monsters in deathmatch**: each free-for-all, team deathmatch, elimination or last-man-standing arena has a 15% chance of having monsters loose in the level (a few, sized to the level; killed ones are replaced after a while). Doom's rules apply: killing a monster is not a frag, dying to one costs no frag (and no CS2 kill against anyone). Monsters fight back at whoever hurts them, players and other monsters alike, and they open doors and use teleporters.

- Every arena gets its own random level.
- Each arena has a small chance (12%) of a weapon start: everyone there spawns and respawns with a pump-action shotgun, double-barrelled shotgun, minigun, missile launcher, polaric energy weapon, ripsaw or (rarely) the SKAG 1337, plus extra ammo, as well as the pistol.
- When the first arena finishes, the others have 2 more minutes; then the leader wins.
- Someone joining mid-round goes into an arena with room; if every arena is full (or it is a one-life round) they take a bot's place, keeping the bot's team. In one-life rounds that is only for newcomers: anyone who was already in (knocked out, or gone to spectate, AFK or the other team) waits for the next round.
- Every frag is a real CS2 kill, credited to the killer, so the killfeed, scoreboard and rank plugins count it.
  - In respawn modes the CS2 kill happens about 1 second after the arena death, and CS2 respawns the player.
  - In elimination modes the kills are applied when the round ends, so eliminated players can keep watching.
- When an arena finishes, its players watch the arenas still fighting (so do players knocked out of a one-life round, and anyone who types `!spec`). Mouse 1 / mouse 2 change player, E or Space changes arena. Above the status bar a spectator sees who they are watching and either "TYPE !BACK TO PLAY" or "YOU PLAY NEXT ROUND".
- The CS2 round ends when every arena is done, or after 10 minutes.
- Music: the Hellmatch theme (the trailer track) opens the map's first round and its first Boss Battle round (once, if that is the same round), then the round plays the round's pool one track after another: respawn rounds (free for all, team deathmatch) play the longer tracks, one-life rounds play short ones, Boss Battle plays its boss tracks. `MUSIC_OPENER` in the settings: "first+boss" (default), "every" round, "first" round only, or "off". Everyone hears the same track; each player turns it up or down with the **Main Menu Music** volume slider (`snd_menumusic_volume` in the console). The in-game Music slider does not apply: CS2's music sound type looks up per-mode volume settings that don't exist and floods the console, so the map's music is tied to the menu-music setting instead.
- AFK: after 20 seconds idle you get a warning. At 30 seconds you are moved to spectating and skipped next round until you press a key or type `!back`. Both notices show on that player's own screen, not in chat.
- CS2 bots on the server play using the game's own bot AI. `bot_quota 6` fills a test server.

## Controls

| Key | Action |
|---|---|
| W A S D | move (always running) |
| Shift | walk |
| Mouse | turn and aim. Old-school autoaim; with no target the shot follows your crosshair up and down |
| Mouse 1 | fire |
| E or Space | use (doors, lifts, switches) |
| R or Mouse 2 | next weapon |
| F (inspect) | previous weapon |

During the end-of-round vote: Mouse 1 / Mouse 2 / E / R / F vote for free for all / team deathmatch / team elimination / last man standing / Boss Battle.

Chat (`!` or `/`): `!ffa` `!tdm` `!elim` `!lms` `!boss` (vote for the next mode while the ballot is up), `!help` (controls, shown on your own screen; `!controls` and `!hm` work too), `!spec` (watch other arenas), `!afk` (sit out), `!back` (rejoin), `!hud` (status bar size: normal, classic, small), `!text` (size of the red Doom-font text lines: normal, large, huge, small, tiny; `!text large` etc picks one), `!hud scores` (hide the game HUD while the scoreboard is open; off by default).

Frags during CS2 warmup are not sent to the scoreboard.

## Settings

Open `maps/scripts/freedm.js` and search for `const CONFIG`. The top of that block has the frag limits, mode chances (`MODE_WEIGHTS`, `boss` is Boss Battle; a mode set to 0 is also left off the vote), the vote (`VOTE`, `VOTE_SECONDS`, `VOTE_TOP_BONUS`, `VOTE_KEYS`), monster-kill scoring (`MONSTER_SCORE`, `MONSTER_SCORE_BOSS`, `MONSTER_SCORE_DEATHMATCH`, `MONSTER_KILL_COMMAND`), the monster settings (`MONSTER_CHANCE` for deathmatch rounds; `MONSTERS`: waves, lives and the alive cap of Boss Battle; `BOSS_SECONDS`), round length, kill-credit options, AFK times, bot skill, music (`MUSIC`, `MUSIC_OPENER`), and whether the map sets server cvars (`APPLY_CVARS`).

When `APPLY_CVARS` is on, the map sets these:
- `mp_ignore_round_win_conditions` while arenas are running.
- `mp_respawn_on_death_t/ct` (on for respawn modes, off for elimination).
- `mp_teammates_are_enemies` (1 in free-for-all rounds so same-side kills aren't teamkills).
- `mp_respawn_immunitytime 0`, `mp_death_drop_gun 0`, and the buy settings.
- No money: `mp_playercashawards 0`, `mp_teamcashawards 0`, `mp_startmoney 0`, `mp_maxmoney 0`.

## Credits

Hellmatch is an unofficial fan project. It is not affiliated with or endorsed by the Freedoom project, id Software, Bethesda or Valve; Freedoom is named only to credit its content.

The code (the cs_script and the build tools) was written by an AI coding agent (Claude, by Anthropic), directed and tested by skink52.

The levels, textures, sprites (players, items, monsters), sounds, level music and graphics are from the Freedoom project (freedoom.github.io, BSD licence, see `FREEDOOM_LICENSE.txt` and `FREEDOOM_CREDITS.txt`). The level music is rendered from Freedoom's MIDI files with an OPL3 FM synth and the DMXOPL3 instrument bank (MIT licence). The Hellmatch theme and the generated tracks are original music made for Hellmatch; track titles and sources are in `MUSIC_CREDITS.txt`. The game rules, including the monsters' behaviour, are a fresh implementation in cs_script.
