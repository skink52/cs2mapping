# mg_trenchwarfare script: review pass 1 (12 Nov 2026, remaster step 3)

Split, API move, adversarial review, tests, balance and performance for `src/modules/*.js` (shipped as `src/mg_trenchwarfare.js`).
AI-generated (Claude) for skink52. Everything here is **simulated** (mock engine `test/mock.mjs`, `tscheck`, `api.py --strict`):
nothing in this version has run in CS2. Nothing is committed.

## 0. Split and API move, behaviour unchanged

The 1305-line script was cut into 11 modules by line ranges (every line used once, the import line dropped) and joined again by
`create/build_script.mjs`. With the step-1 mock (fixed seed, its own counters) the joined file gave **identical output** to the
original at 32 players / 120 s (50 kills, 32,344 HUD class calls, 25,430 text calls, 78,171 teleports, 55,410 moves, 79 SetModel,
7,786 fire attempts, 0 errors), 16 / 300 and 48 / 150. The same identity held after moving the five deprecated calls
(`Instance.Msg` / `ServerCommand` / `FindEntityByName` / `FindEntitiesByName` / `EntFireAtName` -> `Console.Log`, `Console.ServerCommand`,
`Entities.FindByName` via `byName()`, `Entities.FireInput`). Their five `create/test/api_allow.txt` lines are gone:
`api.py --strict --check` reports 0 invalid, 0 deprecated, 0 allowed; `tscheck` OK. The same old mock already failed at 16, 48 and
64 players ("bot left at the undergroundopen blocker") on the original file as well: that was bug 13 below.

## 1. Bugs found and fixed

Severity: **high** = breaks a match or gives a free exploit; **medium** = visible wrong behaviour in a normal match; **low** = rare,
cosmetic or diagnostic. "Covered by" is the mock scenario (`node test/mock.mjs 32 150 scenario=<name>`) whose set piece or invariant
fails without the fix. **Proved** = the fix was undone in a scratch copy of the build (`script=<file>`) and that scenario failed; the
failure text is quoted.

| # | Sev | Bug | Fix | Covered by |
|---|---|---|---|---|
| 1 | high | A pilot who disconnected in the air left his aircraft hanging there for the rest of the round with its engine loop playing; the side had one aircraft fewer, and the next player in that slot inherited it | `OnPlayerDisconnect` -> `dropPlayer` -> `leaveTeam` -> `endFlight` (home, sounds off), seat freed, HUD reset | `churn` proved: "a pilot who disconnected mid-air still holds his aircraft" |
| 2 | high | Deaths under a shot-down plane were credited to whoever last hit it, a team-mate of the victims: **every such death was a team kill** (pre-existing code) | the wreck's blast is the pilot's; the shooter still gets the pilot (`crashPilot`) | `air` proved (a man stands under the wreck): "team kill credited: slot 1 killed team-mate 5"; seen first in a default 300 s run |
| 3 | high | `!infantry` / `!mortar` / `!air` in the field switched at once: a free teleport out of any fight with a fresh kit and armour; the role cards (the user's text) always said "when you next deploy" | the request is the preference; it changes the role now only in the briefing room, otherwise at the next respawn (a pilot with lives left too) | `edge` proved: "!mortar in the field switched at once (teleport / fresh kit)"; `air` (`!infantry` while flying, applied after the next death) |
| 4 | medium | Flight: flying straight out at the soft wall, the turn home changed side as the plane crossed the line to the map centre, undid itself and carried the aircraft past `BOUNDS.FAR` (destroyed). With the aim almost behind, `capHeading` could also flip side tick to tick and hold a dive into the ground | the wall turn keeps its side (`a.wallSide`) while home is nearly behind; a reversal keeps its side (`a.revSide`) until done | `air` proved for the wall turn ("the AFK piece did not run": the AFK plane flew out of the box); the reversal fix is defensive (no scenario fails without it once the wall fix is in) |
| 5 | medium | No AFK handling: an AFK pilot kept one of five aircraft for the round (the box turns him round for ever); an AFK crewman blocked a seat | AFK (no key, no turn of the view, no step): pilot 60 s -> aircraft home, pilot deploys as infantry; crewman 120 s -> seat freed | `air` proved: "an AFK pilot was still flying 63 s into an AFK sortie"; coverage row "AFK pilot taken home" |
| 6 | medium | Kill / assist credit went to whoever held the slot at impact: a slot that changed hands, or a firer who had changed sides (a team kill) | shells, bombs and loads carry slot + `gen`; `creditOf(slot, team, gen)` | `crew` proved (firer switches sides before impact): "team kill credited: slot 12 killed team-mate 3" |
| 7 | medium | The mortar loader's assist share (55) went through armour as blast damage: about half reached health, under CS2's assist line (assumed "more than 40" as in CS:GO), so a loader with an armoured victim got no assist. The likely cause of "mortar assist credit unconfirmed" | the share is armour-piercing (`CSDamageFlags.IGNORE_ARMOR`), at least `CONFIG.ASSIST_MIN` 41 when the victim can take it, still non-lethal | `crew` proved: "the loader's share was 30 health damage through armour (assist needs 41)" |
| 8 | medium | Switching sides or spectating while dead kept the crew seat and the air-role count (`airFree` counted him): seats and aircraft lost for the round | the side is read from the controller every tick, alive or dead; `leaveTeam` | `churn` proved: "crew ct_1 seat held by a player now on the other side" |
| 9 | medium | Script reload in the tools: no `OnScriptReload`. The new script's round clock started at 0 (both areas opened at once), aircraft parks were read where the old script had flown them, and pawns stayed shrunk / frozen / on a camera | `OnScriptReload` carries clock, kill count, unlocks, aircraft parks, preferences and counters; parks re-applied; `sanitise` on the first look at every pawn | `reload` proved: "the script registers no OnScriptReload before()" |
| 10 | medium | Round restart with pilots up or crews in the sight: `p.air` was dropped without touching the pawn (move type NONE, camera following a deleted aircraft, maybe shrunk) | `sanitise` at round start for pilots / plotters and on every `OnPlayerReset` | `round` (three restarts, both event orders; checks scale, move type, camera). Two paths: undoing only the reset one is not caught |
| 11 | medium | At the map table MOUSE1 locks the target, and also fired the crewman's pistol | the knife is drawn while plotting, the previous weapon comes back on leaving | coverage row "pistol stowed at the table" (counted, no failing check) |
| 12 | low | A slot that changed hands kept the last player's HUD classes (`hudReset` existed but was never called) | `ResetForPlayer` on a new player record and on drop | `churn` proved (both removed): "slot reuse: the newcomer in slot 26 kept the last player HUD" |
| 13 | low | The bot leash could send a bot to `trench_ct_16`, 206 u from the still-closed `undergroundopen` blocker (also posts about 215 u from `woodsopen`), where it wanders back | leash posts at least `BOTS.LEASH_AVOID` 400 u from a closed blocker | `edge` proved: "the leash picked a post 226 u from the woodsopen blocker" |
| 14 | low | `!uniform` in the field or in the air called `SetModel` on a shrunk pilot or with the issued weapons out: the script's only route to the "giant first-person weapon" report | the model changes only in the briefing room, before `deploy` issues the kit; `!uniform` out there waits for the next spawn | `air` proved: "SetModel on a shrunk pawn (slot 1)"; the mock also fails any SetModel after the kit was issued |
| 15 | low | The damage guard threw (`points` null) in the first tick of a round, so it failed open | guarded | `crew` proved: "TypeError: Cannot read properties of null (reading 'pit')" |
| 16 | low | HUD writes for bots every tick (script time) | skipped | every run proved (default): "1078 HUD calls for bots" |
| 17 | low | Dying in the briefing room before take-off cost an air life | a life is spent only by a death in this life's sortie | code review |
| 18 | low | `SetAnimation` fired every shot at `mortar_<tg>_K`, which does not exist (prop_static mortars) | looked up once per round, fired only when present | the mock fails any input at a missing entity |
| 19 | diag | **Mortar crew dying when firing** (open issue): no script path damages a crew's own side. `impact` skips the shell's own team; nothing at the tube deals damage; the only TakeDamage calls are shells, bombs, crashes, plane guns and `hitPilot`. Non-enemy damage within 320 u of the tube is already dropped by the guard. In the mock every crew death came from an enemy shell (counter-battery). In game the cause must be named by the server console | `[tw] blocked ...` now prints damage types, flags, attacker, inflictor and distance to the tube; new `[tw] crew death: ... attacker, inflictor, weapon, own tube fired <s> ago` line per crew death | `crew`: world damage at the tube blocked and logged; own shell on own pit hurts nobody; an enemy shell's kill is credited to the enemy firer and logged |

Reviewed, not bugs: **radar math**. `!pos` (now `radarSquare`) uses `CONFIG.RADAR` x0 -4300, y0 4700, span 8601.6 = `out/radar_region.json` =
the overview (pos -4300 4700, scale 8.40 x 1024), columns A-P from x0, rows 1-16 down from y0, the same grid `make_radar.py` draws;
`edge` checks six points, including the corners and off-map, against radar_region.json. The mortar sight mapping matches
`render_top.py` (CT picture rotated -90, T +90): derived by hand, both orientations agree with `sightToWorld` / `worldToSight`.
Monsoon's other classes checked and not present here: no vehicles to abandon, no water, no tickets, no deploy points to camp.
Not fixed, recorded: shells in flight at round end still land in the post-round time (harmless with respawns); `pickTrench` counts use.

## 2. Coverage

`node test/mock.mjs 32 300` prints this table; any row at 0 fails (12 Nov, seed 7):

| Feature | Times | Feature | Times |
|---|---|---|---|
| deploys: infantry / mortar crew / aircraft | 181 / 44 / 50 | mortar: target locked at the table | 339 |
| mortar: pistol stowed at the table | 259 | mortar: bombs loaded / shots / impacts | 125 / 122 / 271 |
| mortar: kills | 4 | mortar: loader assist shares (41+ hp) | 15 |
| mortar: assists credited (mock rule) | 21 | air: flights | 50 |
| air: gun rounds / hits on men | 1548 / 171 | air: bombs dropped / bomb kills | 109 / 63 |
| air: rifle hits on aircraft | 101 | air: pilots shot down / crashes | 28 / 41 |
| air: AFK pilot taken home | 1 | rifle kills (rate model) | 131 |
| areas opened (unlocks) | 2 | dressing station heals | 2029 |
| streak upgrades / rifle swaps | 17 / 150 | uniforms set | 267 |
| ambient bursts | 33 | damage blocked at the pit / pilot | 1 |
| field role requests deferred | 9 | !pos / !roles / !uniform | 11 |
| per-minute perf line | 4 | | |

Scenarios: `node test/mock.mjs 32 150 scenario=all` -> **6 / 6 pass** (seeds 7, 3, 19, 29). Mutation check (scratch copies of the build
with one fix undone, run with `script=`): **14 of 16** undone fixes make their scenario fail (quoted in section 1); the two that do not
are the reversal side (defensive once the wall turn keeps its side) and the reset-path `sanitise` (the round-start path covers it).
The knife at the table is counted in the coverage table, not checked. Three scenario checks were made stricter during the pass after
they missed a mutant (a man under the wreck; a stale-HUD marker on slot reuse; the leash post picker drawn 300 times).

## 3. Balance (`create/sim_balance.mjs test/balance.json`)

**Method.** Each run is one 15-minute window of the real script with the real CONFIG on the mock engine (seeded; 32 players, 22
humans driven by the test in every role, 10 infantry bots, the same mix on each side). Mortars (crews aim at enemies through the sight), aircraft (an attack
profile: cruise ~1000 u, shallow dive, guns with the crosshair on a man, bombs when the bomb-sight is on him), unlocks, healing and
credit are the script's own code. The infantry fight is a **rate model**: an infantryman kills the nearest enemy on the ground within
4200 u after 30 s on average at 3300 u (no man's land), and hits an enemy aircraft within 2600 u at 0.024 per second. The round itself
runs to `mp_roundtime 60` (the script has no win condition), so the "winner" is the side with more kills in the window.

Two 50-seed runs (`node ../../create/sim_balance.mjs test/balance.json 50 32`, each under the watchdog):

| | run 1 (900 s windows) | run 2 (600 s windows, final) | target |
|---|---|---|---|
| test mix per side | T 11 humans + 5 bots, CT 10 + 6 (21 humans: odd) | 11 humans + 5 bots each | |
| rate model mean time to kill at 3300 u | 18 s (1.8 deaths per player-minute) | 30 s (1.4) | |
| T wins : CT wins | 20 : 30, **T 40 %** (+-7 one SE) | 27 : 23, **T 54 %** (+-7) | 45-55 % |
| kills per window T / CT (mean) | 422 / 430 | 217 / 215 | |
| kills by source | rifle 55 % (model), bomb 22 %, shot down 11 %, mortar 5 %, plane gun 4 %, own crash 3 % | rifle 49 % (model), bomb 25 %, shot down 12 %, mortar 7 %, plane gun 4 %, own crash 3 % | each weapon 3-40 % |
| T by source (mean per window) | | rifle 111, bomb 54, shot down 28, mortar 15, plane gun 10, own crash 6 | |
| CT by source (mean per window) | | rifle 108, bomb 56, shot down 27, mortar 15, plane gun 10, own crash 7 | |
| aircraft sortie median (p25-p75) | 38 s (22-56) | 35 s (21-53) | |
| mortar shots / assists per window | 466 / 104 | 316 / 69 | |
| areas opened at, median | 25 s | 36 s | (CONFIG: 15 / 30 kills or 240 / 480 s) |
| script ms/tick (10 runs in parallel) | 1.33 avg, 88 max | 1.10 avg, 91 max | see section 4 |

**Win rate: in the band; nothing tuned.** Run 1's 40 % came with an uneven test mix (one more human, so one more crew / pilot driver, on
T, and noise of 7 points); with an even mix the two sides' kills by every source agree within one kill per window (run 2), so the script
has no side asymmetry: the map is mirrored and the code treats both sides the same (sight orientation, spawn headings, aircraft
model aside). Round length: the script ends no round; `mp_roundtime 60` does, so every round is an hour; the window is what was simulated.
**Rifle share 49-55 %** is the rate model, outside the 3-40 % band by construction (an infantry-first mode). **Recorded, not tuned:**
bombs at 22-25 % of kills look high, but the mock's infantry stand still at their posts and bunch at them (a 420-u blast on a crowded
post); with people who move and spread that falls, so it is an in-game question, not a clear script imbalance. Plane guns at 4 % need
about seven hits per kill (16 damage) and are inside the band. Sorties last about 35 s against the model's rifles (0.024 hits per
second per rifleman within 2600 u); the real figure decides whether `AIR.HIT_SCALE` needs a change. The areas open within the first
minute because a full server reaches 15 / 30 kills that fast (the time fallbacks 240 / 480 s never matter at 32 players): a design
question for the user, not changed.

## 4. Performance

Script time per think (one tick), from `performance.now()` around `Instance._think()`, single process, idle PC. The figures include
the stand-in engine's own trace / HUD / move calls; a CPU profile puts the script's own share at 0.14-0.19 ms/tick at 64 players.
Budget: a 64-tick server has 15.6 ms per tick for everything; the gate (`perf=1,8`) fails over 1 ms average or 8 ms max.

| run | avg ms/tick | p99 | max | over 1 ms | over 8 ms | HUD calls / traces per tick |
|---|---|---|---|---|---|---|
| 64 players, 32 human, 300 s (before) | 0.469 | 1.10 | 3.83 | 343 | 0 | 9.4 / 14.1 |
| 64 players, 64 human, 300 s (before) | 0.954 | 2.05 | 5.90 | 7285 | 0 | 15.6 / 27.3 |
| 64 players, 32 human, 300 s (after) | **0.204** | 0.48 | 3.63 | 10 | 0 | 9.4 / 14.1 |
| 64 players, 64 human, 300 s (after) | **0.370** | 0.80 | 3.82 | 44 | 0 | 15.6 / 27.3 |
| 32 players, 22 human, 300 s (after) | 0.208 | 0.47 | 2.48 | 10 | 0 | 9.3 / 21.8 |

Hot spot: the HUD cache built a key string (`id + "#" + cls`) for every call; with 64 humans `hText` / `hClass` / `hSwap` were 40 % of
the script's own time. Now one record per panel id per player (`hrec`), and nothing is sent or cached for bots. (The mock's own plane
lookup was also cached; that only changes the stand-in's share.) The max (3-4 ms) is one tick (a round start, a GC). The `[tw] perf:`
console line once a minute gives the real number on a server.

## 5. What only the game can settle

- What kills mortar crews in game: read the `[tw] crew death` / `[tw] blocked` console lines (bug 19).
- CS2's assist rule and `IGNORE_ARMOR` on `TakeDamage` (bug 7); whether the kill feed shows the loader's assist.
- Whether the giant first-person weapon is gone with the model set only in the briefing room before the kit (bug 14), and whether a
  respawned pawn keeps model scale and camera (the mock assumes the worst; `sanitise` handles both).
- `SwitchToWeapon` to the knife at the table (bug 11); `ResetForPlayer` clearing a slot (bug 12); `OnScriptReload` in the tools (bug 9).
- Flight feel with the committed wall turn / reversal (bug 4); how long real pilots live (rifles against biplanes is a model here).
- The win rate and kill shares with people who move, take cover and spot for the mortars; script time on a server (`[tw] perf:` line).

## Files

`src/modules/00_config.js` ... `90_main.js` (new), `src/build.json` (new), `src/mg_trenchwarfare.js` (now generated);
`test/mock.mjs` (rewritten: current API only, scenarios, invariants, coverage, balance mode, perf), `test/balance.json` (new);
`create/build_script.mjs`, `create/sim_balance.mjs` (new, neutral); `tools/check_contract.py` (build freshness, new call names);
`docs/SCRIPT.md` (new), `docs/CONTRACT.md` (files, notes, known missing), this file; `create/test/api_allow.txt` (this script's 5 lines removed).
