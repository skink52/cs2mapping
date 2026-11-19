# Note for the server project (slime-mg-gm / SlimeMG): Hellmatch ZE (`mg_hellescape`)

Copy this into the server project (e.g. `docs/add-a-map.md` or a task note) and apply it there. Written 19 Nov 2026 from the
map side (cs2mapping `projects/hellmatch-ze-cs2`). Nothing in it has been tested against SlimeMG yet.

## What the map does
- Hellmatch ZE is a separate Workshop map built on Hellmatch's engine. Its point_script is still named **`fdm_script`**, so SlimeMG's
  existing `MapScriptInputs` entry (`"fdm_script": ["mgstat_on"]`) already switches its stats on. Nothing to add there.
- Stats go out as server commands **`echo mgstat <slot> <stat> [n]`**, the same channel Hellmatch uses (`echo`, so a
  dedicated server's Workshop command filter lets them through). Humans only: never for bots, never during warmup. Stat names
  are `[a-z0-9_]`.
- Kills and deaths between players are real CS2 kills (zombie players stay on their own CS2 team), so the plugin keeps
  counting those from game events as now.

## Stats the map sends
| Stat | n | When |
|---|---|---|
| `pve_kills` | count | AI monsters killed by the player (batched, at most once a second) |
| `boss_kills` | count | a stage boss killed by the player (also counted in pve_kills) |
| `ze_escapes` | 1 | the player was a live human in the escape zone when the escape completed |
| `ze_survivor_wins` | 1 | the player was a live human on the winning side when the round ended (escape, wipe of the other side or time) |
| `ze_holds` | 1 | the player was a live human when a timed hold completed |
| `ze_infections` | 1 | as a zombie player, killed a human (that human rises as a zombie) |
| `ze_zombie_kills` | 1 | as a human, killed a zombie *player* (AI zombies are pve_kills) |
| `ze_boss_takeovers` | 1 | took control of a stage boss |
| `ze_boss_player_kills` | 1 | killed a human while driving a boss |
| `best_ze_stage` | stage number | furthest stage reached as a live human this round (keep the max: `best_*` rule) |

`ze_survivor_wins` ends in `_wins`, so SlimeMG's existing rule also records it in `stat_events`.

## What to add on the server
1. **Map catalog / mode**: add `mg_hellescape` (its Workshop ID once uploaded) as its own mode, e.g. "Zombie Escape", so its
   stats are kept apart from Hellmatch's (mgstat adds to the *current mode*).
2. **Per-map cfg** `server/csgo/cfg/slime/maps/mg_hellescape.cfg`: copy `mg_hellmatch.cfg` (same cvars: no money, radar off, no gun
   drop, respawn immunity 0, `mp_ignore_round_win_conditions 1`, `mp_roundtime 60` as the map's own value, `slime_join_spawn 1`).
   Differences: the script sets `mp_freezetime 0` and the round clock itself (ROUND_SECONDS 660; a ZE round has a 10 minute limit);
   it ends each CS2 round with `FireWinCondition` (T or CT wins, or a draw). Never force round cvars, respawn or
   `mp_teammates_are_enemies` for this map: the script switches respawn on per side and must keep zombie players respawning.
   Bots: the script drives them (human bots follow the stages, zombie bots hunt); `bot_quota 8` with `bot_quota_mode fill` is a
   reasonable start (bots fill both sides' arenas and both hordes).
3. **ChangeAtTimeLimitMaps**: add `mg_hellescape`, like `mg_hellmatch` (the map's rounds run under its own control).
4. **Stats display** (optional): show `ze_escapes`, `ze_survivor_wins`, `ze_infections`, `best_ze_stage` on the stats page or `!stats`
   for this mode.
5. **Test** on the server once the map is uploaded: console shows `[hellmatch] ... server stats on (mgstat)` after map start;
   escape a round and check `ze_escapes` / `ze_survivor_wins` rows for the right players; die to a zombie player and check
   `ze_infections` for them.
