# create/test: script checks without CS2

| File | What it does |
|---|---|
| `point_script.d.ts` | Valve's declarations for `cs_script/point_script`: the API both tools below check against. |
| `tscheck.sh` | Type-checks scripts against the `.d.ts`: `sh tscheck.sh <script.js> [more.js ...]` (needs `npm i -g typescript`). |
| `mock_point_script.mjs` | Runs a real script against a stand-in engine with simulated players and rounds, and fails on errors and known CS2 pitfalls. |

## mock_point_script.mjs

```
node create/test/mock_point_script.mjs <script.js> [entities.json] [players=8] [seconds=120] [seed=N] [option ...]
```

Needs Node 18 or newer and nothing else. It loads the script as an ES module (just as CS2 does) with its `cs_script/point_script` import
pointed at the stand-in. It then simulates `seconds` of 64-tick server time: players joining, held or random keys, guns and knives
firing their events, damage and kills, respawns, rounds ending and restarting, chat, every `OnScriptInput` name fired now
and then, and one player reconnecting halfway. It exits 0 with `OK: no errors`, or 1 with `ERRORS` (exceptions in the script's
callbacks) and/or `PROBLEMS` (flagged CS2 pitfalls).

Option order doesn't matter. A bare word is the same as `word=1`. An unknown option prints a warning.

### Options

| Option | Default | Effect |
|---|---|---|
| `entities.json` | none | Map entities, so `FindEntityByName` finds the map's names. Make it with `python3 create/dump_entities.py <map.vmap> entities.json`. `[{name, cls, origin, angles}]`; `targetname`/`classname` keys are accepted too. Without it every lookup finds nothing (see `autoents`). |
| `players=N` | 8 | Players at the start (max 64); every 4th is a bot. Odd slots are CT, even slots T. |
| `seconds=N` | 120 | Simulated time. |
| `round=N` | seconds/3, min 20 | Round length before time runs out (a script's `mp_roundtime` overrides it). |
| `seed=N` | 1 | Fixes `Math.random`, and gives the script `Date.now` and `performance.now` on game time: the same seed and options give the same run. |
| `inputs=a,b` | every registered name | `RunScriptInput` names to fire (one per second, random activator). |
| `chat=!x,!y` | none | Chat lines players type now and then. |
| `models=<dir>[,<dir>]` | off | The addon content folder(s). `SetModel` to a path that isn't there (as `.vmdl` or `.vmdl_c`) throws. CS2 silently shows nothing for a model it hasn't loaded. |
| `hud=<layout.xml>[,<css>]` / `css=<file>` | off | The custom HUD. The css defaults to the matching `panorama/styles/...css`. Turns on the HUD checks below; if the map has no `custom_hud_layout` in `entities.json`, one named `hud` is added. |
| `trace=<file>` / `trace` | off | Writes what changed on screen each tick, plus an FNV hash (`trace` alone prints only the hash). See [Trace](#trace-did-a-refactor-change-anything). |
| `calls` | off | Counts the script's engine calls: per tick, per method, and the hottest script lines (sampled). |
| `warm=S` | seconds/4, max 240 | Timing percentiles skip the first S seconds (V8 compiling the script). |
| `autoents` | off | Any name the script looks up exists: a prop, or a template/HUD if the name contains `templ`/`tpl`/`hud`. Use it when there's no `entities.json`. It reaches more code but finds fewer real problems. |
| `MOCK_VERBOSE=1` (env) | off | Prints the script's `Instance.Msg` lines. |

### Scenarios

These are the multiplayer edge cases that have broken script games on real servers. They are opt-in and can be combined.

| Scenario | What happens |
|---|---|
| `held` | Players hold keys for seconds at a time and tap the rest, as people do, instead of random single keys (F / LOOK_AT_WEAPON included). Use it for timing. |
| `churn` | From 15 s, every 5 s: a join (CS2 kicks a bot and the newcomer reuses its slot; they connect with no team and pick one 2 s later), a team swap or a leaver. |
| `silent` | Churn with no `OnPlayerConnect`/`OnPlayerDisconnect`: a slot changes hands unannounced and the newcomer is already on a team with a pawn. |
| `norespawn` | CS2 never respawns killed players (a no-respawn plugin), whatever the script's `mp_respawn_on_death_*` says. |
| `warmup` | The whole run is warmup: `IsWarmupPeriod()` is true, `FireWinCondition` and time running out end nothing, and the dead respawn. |
| `unassigned` | Every other human starts with no team and no pawn (the team menu at map load). Anyone still unassigned at 10 s picks a team. |
| `resetfirst` | On team changes `OnPlayerReset` fires before `OnPlayerTeamChanged`, with the new team already set (a CS2 ordering seen on servers). |
| `hudwipe` | Churn, and a joining client drops every HUD change sent before it picks a team. |
| `maskall` | `IsInputPressed(A \| B)` means A and B both held. The default is either of them; CS2's real behaviour is unconfirmed (see cs_script-notes). |

### What it checks

Always on (pure correctness):

- An exception in any callback (think, timers, `Delay` promises, hooks, script inputs, hooked outputs).
- An `Instance.X` that isn't in `point_script.d.ts` (a typo or a newer API). Entity methods that are declared but not modelled return a default for their declared type; they are counted under "entity methods not modelled".
- Calling a method on an entity that has gone away throws `Invalid entity`, as CS2 does. That covers `Kill`/`Remove`, a `KillHierarchy` input, the old controller and pawn after a slot changes hands, a weapon after death, and map entities after a round restart.
- `Teleport`/`Move` with a non-finite position, velocity or angle, or a position beyond ±16384. Non-finite `SetHealth`, `SetModelScale`, `SetColor`, `SetNextThink`, `Delay`, `TakeDamage` and trace start/end throw too.
- A prop (any model entity except pawns) whose position or angles are `Teleport`ed 3 or more ticks in a row fails the run. CS2 doesn't draw it; use `Move`. A velocity-only `Teleport` doesn't count.
- A non-integer `SetHealth`/`SetMaxHealth`/`SetArmor`/`SetClipAmmo`/`SetReserveAmmo` is flagged. This is the mock's own rule; CS2 hasn't been seen to reject a fraction.
- `GiveNamedItem` of a weapon the player already has is flagged (CS2 gives a duplicate). Flashbangs and healthshots stack, so they're allowed.

With `hud=`:

- An unknown panel id throws (any `SetHasClass*`/`SetDialogVariable*` call).
- A non-string dialog variable throws.
- Switched classes missing from the css are listed.
- A switched class with a lone css rule of its own (`.stOn { }` rather than `.Panel.stOn { }`) fails the run: the panel takes on that rule's layout.

With `models=`, a missing model throws.

### Engine behaviour modelled

- **Rounds**: time runs out → `OnRoundEnd` (draw, or `mp_default_team_winner_no_objective`). The same happens when one team is wiped out
  (both teams present), or on `FireWinCondition` (by `EntFireAtName` on an `info_map_parameters`; on any target when there's no `entities.json`),
  unless `mp_ignore_round_win_conditions 1`. Then `mp_round_restart_delay` (3 s) later: `OnBeginRoundRestart`. Map entities
  are re-created as new objects (the old ones go invalid), and spawned props, grenades and dropped weapons are removed. Every
  player on a team gets a fresh life and an `OnPlayerReset`, then `OnRoundStart`. `mp_restartgame N` does the same N seconds later.
- **Players**: `OnPlayerConnect` → `OnPlayerActivate` → `OnPlayerReset`. A pawn is kept across lives, just as CS2 keeps it.
  `JoinTeam` (and churn swaps) kill the pawn and fire `OnPlayerTeamChanged({ player: pawn, oldTeam })`; the player respawns 1 s later.
  `GetAllPlayerControllers` includes disconnected players; `GetPlayerController(slot)` doesn't.
- **Damage**: `TakeDamage` on a pawn runs `OnBeforePlayerDamage`/`OnModifyPlayerDamage` (`abort` and changed `damage`/flags are honoured,
  unless `SUPPRESS_DAMAGE_MODIFICATION`), then `OnPlayerDamage`. `FORCE_DEATH` always kills and `PREVENT_DEATH` leaves 1 hp. A kill
  fires `OnPlayerKill` credited to the attacker (pawn or controller).
- **Scoreboard**: a kill scores +1, or −1 for a teamkill unless `mp_teammates_are_enemies 1`. Killed players respawn after 2 s only if the script set
  `mp_respawn_on_death_t`/`_ct 1` (or in warmup). Cvars come from `ServerCommand`; `;`-separated commands are split.
- **Weapons**: each life gets a knife and a pistol. Pressing ATTACK fires `OnKnifeAttack`, `OnGunFire` + `OnBulletImpact`, or `OnGrenadeThrow`
  (by weapon type), and RELOAD fires `OnGunReload`. `CSWeaponData` answers by class name.
- **Entity inputs** from `EntFireAtName`/`EntFireAtTarget` (with `delay`): `Kill`/`KillHierarchy`, `Skin`, `Alpha`, `Color`, `FireWinCondition`, and
  `RunScriptInput` on a `point_script`. Every input is counted under "EntFire".
- **Not modelled**: physics, collisions and triggers (traces return random hits), bomb events, observer pawns, money. Entity outputs hooked with
  `ConnectOutput` fire at random every 2 s while their entity exists.

### Output

```
ran 60s with 8 players [churn held]; hooks: ...; 4 script inputs (...)
Instance calls: ...                      most-called Instance methods
EntFire: name.Input xN ...               inputs the script fired
rounds ended 2 (reasons {...}), restarts 2; kills 5 (scoreboard 3, teamkill penalties 1), script TakeDamage 4, respawns 6, team changes 3, churn {...}
script time after 15s: avg 0.31 ms/tick, p50 ..., p90 ..., p99 ..., p99.9 ..., max ...; ticks over 16 ms: N (time:ms ...)
engine calls: 179 per tick; top: ...     (calls)
hot script lines (sampled): fn:line N    (calls)
trace: 5500 ticks with changes, hash e505068e -> a.txt   (trace)
```

Script time covers every callback the script runs in a tick. It is measured on this machine in Node, so compare builds with it rather than
reading it as CS2 server time. Mock figures are not CS2 figures; say "mock engine" when quoting them.

### Trace: did a refactor change anything?

A trace lists, per tick (`t<tick>`), every observable value that changed: entity position/angles/model/skin/colour/glow/scale and pawn
health (`e <name> = ...`), HUD classes per slot (`h <slot>|<panel> = ...`) and dialog variables (`v <slot>|<panel>.<var> = ...`).
After those come events (`! ...`): kills, inputs fired, server and client commands, log lines, team changes and disconnects. Engine calls that
change nothing on screen (re-sending the same class, moving a prop to where it already is) leave no line, so an optimisation that only removes
redundant calls gives an identical trace.

Before/after method for a performance refactor:

```
node create/test/mock_point_script.mjs old.js map.json players=32 seconds=600 seed=7 held churn calls trace=/tmp/a.txt
node create/test/mock_point_script.mjs new.js map.json players=32 seconds=600 seed=7 held churn calls trace=/tmp/b.txt
diff /tmp/a.txt /tmp/b.txt | head      # must be empty (same hash)
```

1. Keep the same seed, options, players and seconds for both runs. Use `held` for realistic input and `churn` so joins and leaves are covered.
2. The traces must be identical. If they aren't, the first differing tick shows what changed on screen.
3. Compare `engine calls` per tick and the `script time` percentiles after warm-up (p99 and max matter most for hitches).
   Repeat the timing runs 2–3 times: timing noise is ±10–20%, but the trace and call counts don't vary.
4. If a script picks something at random and the refactor changes how often it calls `Math.random`, the traces drift apart. Check that part
   separately, or keep the order of random calls.

### Examples

```
# smoke test, as run on every port script
for f in ports/*/scripts/*.js; do node create/test/mock_point_script.mjs $f players=8 seconds=60 || echo "FAIL $f"; done

# an original addon with its map, models and HUD
python3 create/dump_entities.py out/addon/maps/mg_x.vmap /tmp/ents.json
node create/test/mock_point_script.mjs out/addon/maps/scripts/x.js /tmp/ents.json players=32 seconds=300 \
     models=out/addon hud=out/addon/panorama/layout/custom_game/x.xml

# multiplayer edge cases
node create/test/mock_point_script.mjs x.js /tmp/ents.json players=24 seconds=300 churn resetfirst
node create/test/mock_point_script.mjs x.js /tmp/ents.json silent unassigned
node create/test/mock_point_script.mjs x.js /tmp/ents.json warmup norespawn maskall

# where the time goes
node create/test/mock_point_script.mjs x.js /tmp/ents.json players=64 seconds=600 held calls
node --cpu-prof create/test/mock_point_script.mjs x.js /tmp/ents.json players=64 seconds=300 held   # open the .cpuprofile in Chrome DevTools
```

### Limits

- It is a stand-in. Passing means the script survives the modelled engine; it doesn't prove CS2 behaves the same. In-game testing still decides.
- Without `entities.json`, `FindEntityByName` returns nothing, so code that needs map entities never runs (`autoents` helps).
- Game-specific assertions belong in the project's own test, written as a wrapper or a copy: picker over results, music pools, ballots on every
  screen. The project mocks in Space Racer (`test/mock_cs2.mjs`), Hellmatch (`test/mock_cs2.mjs`) and Puppet Brawl (`test/sim_cs2.mjs`)
  are examples.
