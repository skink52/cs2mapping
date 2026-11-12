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
| 14 | low | `!uniform` in the field or in the air called `SetModel` on a shrunk pilot or with the issued weapons out. **Corrected 12 Nov by the user:** the giant first-person weapons were caused by a player set to an invalid / unloaded model (a CS2 model picked in Hammer whose assets Hammer lacked), not by `SetModel` timing or SetColor on armed pawns; this fix stays as a safety measure | the model changes only in the briefing room, before `deploy` issues the kit; `!uniform` out there waits for the next spawn. Against the real cause: `tools/check_contract.py` fails on any `SetModel` argument other than a `CONFIG.UNIFORMS` model (each must be compiled in the game addon, `.vmdl_c`, and precached) or the pawn's own model read back | `air` proved: "SetModel on a shrunk pawn (slot 1)"; the mock also fails any SetModel after the kit was issued and to a model missing from the addon |
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
- Bug 14's real cause was an unloadable model (the user, 12 Nov): with every SetModel target compiled in the addon (check_contract),
  confirm no giant first-person weapon; and whether a respawned pawn keeps model scale and camera (the mock assumes the worst;
  `sanitise` handles both).
- `SwitchToWeapon` to the knife at the table (bug 11); `ResetForPlayer` clearing a slot (bug 12); `OnScriptReload` in the tools (bug 9).
- Flight feel with the committed wall turn / reversal (bug 4); how long real pilots live (rifles against biplanes is a model here).
- The win rate and kill shares with people who move, take cover and spot for the mortars; script time on a server (`[tw] perf:` line).

## Files

`src/modules/00_config.js` ... `90_main.js` (new), `src/build.json` (new), `src/mg_trenchwarfare.js` (now generated);
`test/mock.mjs` (rewritten: current API only, scenarios, invariants, coverage, balance mode, perf), `test/balance.json` (new);
`create/build_script.mjs`, `create/sim_balance.mjs` (new, neutral); `tools/check_contract.py` (build freshness, new call names);
`docs/SCRIPT.md` (new), `docs/CONTRACT.md` (files, notes, known missing), this file; `create/test/api_allow.txt` (this script's 5 lines removed).

## Step 4: bots (12 Nov 2026, remaster step 4)

Bot AI for low population: `src/modules/85_ai.js` (new code), hooks in `50_roles.js` / `60_air.js` / `90_main.js`, `CONFIG.BOTS` / `CONFIG.AI`
in `00_config.js`; the map side in `tools/patch_nav.py`. Everything here is **simulated** (mock engine, `create/check_play.py`'s walk
graph); nothing has run in CS2 or been compiled. Design taken from monsoon's `85_ai.js` (read only) and fitted to the trenches.

### What the bots do

- **Quota.** `CONFIG.BOTS_ON` true: `bot_quota_mode fill`, `bot_quota 16` (`BOTS.FILL_PER_SIDE` 8): bots fill the server to 16 and
  leave as humans join; 0 bots from 16 humans. Monsoon's `!bots` was not ported (nothing checks who types it).
- **Infantry bots are placed, not pathed** (a script cannot path a CS2 bot). Each deploy: a fire-trench post (80 %) or a support-trench
  post, scored by crowding, never within 400 u of a closed blocker. Once an area is blown open, 35 % of bot deploys go to it (at most
  4 bots per side per area): half to the post nearest that area's blocker on their side (the sap head at the support trench / the
  ladder post at the north end of the fire trench), half to a point inside it (`CONFIG.BOTS.AREAS`: woods clearing, tunnel landing).
- **Leash.** Beside a still-closed blocker for 3 s (step 3's), and now also: in no man's land, back in the briefing room, or more than
  1500 u from every post of either side, every dressing station and every opened-area point (that one waits 6 s after the bot last hurt
  or was hurt by an enemy) for 3 s: teleported to a post. Checked once a second per bot. A raid on the enemy trench through an opened
  area is play and is not leashed. Monsoon's "idle 20 s" leash was left out: a bot standing on a fire step is holding the line.
- **Script roles** when a side has fewer than 4 active humans (counted from the controllers, AFK humans excluded): 1 AI pilot and 2 AI
  crews per side, at most half of the side's bots, a bot in the briefing room first. The AI pilot's stick (`aiSteer`) goes through the
  same `tickAir` a human flies with: patrol over the enemy line at 1000 u, gun and bomb runs on enemy infantry within 3600 u (reaction
  1.2 s, aim error 3 % of the range, the 3-degree gun gimbal still applies), pull up under 420 u. The AI crewman holds seat a of an
  empty crew, frozen at the table; every 13-15 s he plots the biggest cluster of enemy infantry (+-160 u), "loads" and fires
  (`fireMortar`, kill credit his). Both are slow and inaccurate on purpose (`AIM_CONE` was widened from 6 to 12 degrees after the first
  runs: at 6 the pilots fired 10-18 rounds in 63 attack runs).
- **Hand-over, in the same call.** A human who asked (preference / `!air` / `!mortar`) takes a script bot's aircraft at his deploy
  (`startFlight` -> `aiYieldAircraft`: the bot's flight ends, the aircraft goes home, the bot deploys as infantry, then the human's flight
  starts on it) or its pit when his role is set (`takeSeat` -> `aiYieldSeat`: the bot is unfrozen and redeployed, the crew's AI state
  cleared, the human gets seat a). A random posting never takes from a bot. A human never shares a tube with a script bot. A side that
  reaches 4 humans gets its bots back as infantry at once (pilots out of the air); below 4 again, the roles return.
- **Rules kept.** Round flow (round start clears AI state; roles resume on the next deploy), unlocks (deploy targets, leash), AFK (an AFK
  human does not keep the AI out), the field role rule for humans. Bots are exempt from that rule (it stops human teleports): when no
  bot waits in the briefing room, the director takes one from the field and redeploys it.

### BOTS_ON: on by default, and why

Evidence: tw35 (29 Oct) the user saw FPS 200 dropping to about 71 every 0.5 s on a listen server with bots, and `bot_kick` cured it; the
mock showed no periodic script load, so the cost was CS2's bots on the map's nav: 44,160 areas in the tw34 compile (NOTES tw34).
REVIEW_WORLD_1 H3 found why the nav is that big: four woods seeds outside the clearing fence flood 654,758 walk cells (the whole terrain,
no man's land, the airfields) against about 25,000 cells of play. Both causes are now handled on the map side: step 5 moves those seeds
inside the fence (`tools/patch_world_1.py`) and this step adds NONAV markup over everything out of play (`tools/patch_nav.py`, below).
The estimate is about 1,500 nav areas (step 5 + NONAV) or 4,000 (NONAV alone), against 44,160. The requirement (bots make the map
playable at low population) cannot be met with bots off, and the script's own cost with 58 bots and AI roles on both sides is small
(perf below). So `BOTS_ON` is **true**, quota capped at 16. **Condition:** it ships with the patched map. Deployed onto the current
compile (44k nav areas) the tw35 hitch would come back: set `BOTS_ON: false` for such a delivery. To see it in game, the once-a-minute
`[tw] perf:` line now also prints the longest wall-clock gap between two thinks (a server hitch shows there) and the AI role counts.

### Nav: `tools/patch_nav.py` (guarded delta patch)

Adds `func_nav_markup` NONAV boxes (navProperty_NavGen NONAV with a closed toolsnavattribute box child: the entity monsoon's
`mv_entities.nav_markup()` makes; copies of the map's own WALKABLESEED markup, vis group tw_nav, named `tw_nav_no_N`). Where: every
256-u square with walkable ground none of which a play world reaches in the open state (both trench systems, the 10 pits, the
briefing room, the woods clearing, the mine galleries; +96 u margin; seeds and posts protected), merged into rectangles of at most
8 x 8 squares. A square whose in-play ground lies 160+ u below its other ground (briefing room, galleries) gets a box starting 100 u
above that; one with in-play ground at the same level is left alone (the trench edges). Independent of step 5 (`--in` / `--out`, any
input; a re-run replaces its own boxes). Run on copies in `out/` (the user's map was only copied):

| input | NONAV boxes | squares cut / left at play level | in-play walk nodes | seed flood before -> after (cells) | walkable nodes outside NONAV | guard |
|---|---|---|---|---|---|---|
| user's map (`out/nav_input_user.vmap`) | 90 | 2305 / 381 | 25,250 | 654,758 -> **59,772** (-91 %) | 683,440 -> 83,934 (-88 %) | PASS --strict, 180 declared nodes |
| step 5's output (`out/nav_input_step5.vmap`) | 89 | 2307 / 379 | 25,333 | 21,764 -> **21,764** | 683,498 -> 83,480 (-88 %) | PASS --strict, 178 declared nodes |

`python tools/check_play.py out/nav_patched_step5.vmap --only 9`: clean (25 seeds on the walkable world, 89 NONAV boxes over 0
protected points, both ladder volumes with ground at both ends). Spot checks: no box over the woods ladders' ends, the sap-head and
ladder posts, the tunnel landing, the chamber or the woods deploy points.
**Estimate.** The flood (check 9's, with the NONAV nodes removed from the graph, seeded by the WALKABLESEED boxes and the spawns) is the
number of 16-u cells the nav generator would reach. The one measured pair is the tw34 compile: 44,160 areas for 654,758 cells, 0.067
areas per cell. Scaled: user's map + NONAV about 4,000 areas; step 5 (with or without NONAV) about 1,470. If the generator instead
covered every walkable surface, NONAV leaves 12 % of it (about 5,400 areas at the same ratio). Areas are merged rectangles of any size:
take these within a factor of 2. **Target recorded: under 5,000 nav areas after the next compile** (the compile log's nav line; NOTES
tw34 has the old one). With step 5's seeds, NONAV changes nothing in the flood: it is the backstop if the generator floods past a seed,
drops off a ledge into the forest, or seeds from somewhere this check does not model.
**Ladders (REVIEW_WORLD_1 M4, the user's, not patched).** Both woods climb volumes (x +-1716, y 2900-2912, z -72..22) have walk nodes
at the bottom (11 / 14; the volume starts 0.8 / -3.5 u from the floor) and at the top (5 / 5), and no NONAV near them. The compile's
"Unconnected ladder #1/#2 bottom" most likely comes from the bottom being a dead end beyond the `woodsopen` blocker when nav is built
(whether the generator treats that prop_dynamic as solid is unknown). What nav needs: a nav area under the bottom that joins the trench
nav: either the blocker not solid to nav generation (it is removed in play anyway), or the volume extended 16 u down and toward the trench
by the user, or a ladder link drawn with `nav_edit 1` after the compile. Bots do not need the ladder: the opened woods are a deploy
target and the leash anchors them there.

### Tests

New mock machinery: `fill=1` plays CS2's quota (bots = quota - humans in fill mode; a new bot joins the smaller side; humans and bots
in interleaved slots), `god` test subjects, `poll()` set pieces. Scenarios: **12 / 12** on seeds 7, 3, 19, 29 (6 from step 3, 6 new):

| scenario | what it checks |
|---|---|
| `bots` | 2 + 2 humans: exactly 12 bots, 6 a side; script pilot up and 2 crews frozen at their tables on both sides within 30 s; every deployed infantry bot at a post, none in no man's land or the briefing room; the no man's land / briefing room / far leash each bring a bot back to a post; woods opened: bots deploy into it, never more than AREA_MAX a side, each at a woods point or the ladder post; AI crews and pilots fire |
| `lopsided` | 4 humans all on T + 12 bots (T 4 + 4, CT 8 bots): CT runs its script roles, T (at the threshold) none; CT's crews fire |
| `full` | 32 v 32 humans: the script sets `bot_quota_mode fill` / `bot_quota 16`, no bot joins, no script role (at 5, 60 and 140 s) |
| `yield` | all 5 T aircraft script-flown: a human asks in the field, dies, and at his deploy takes a bot's aircraft in the same tick (the bot infantry at a post, scale 1, walking; 4 script pilots left; 1 hand-over counted); a script pilot is shot down while a human who asked waits: the human gets the bot's parked aircraft, the bot comes back as infantry; all 5 T pits script-run: a human asks, dies, and takes a pit in the same tick (bot unfrozen and redeployed, the crew's AI state cleared, no shared tube) |
| `threshold` | T and CT with 2 humans run script roles; 2 more T humans join (2 bots kicked): within a director tick T's pilot is out of the air, its pits free, no frozen bot left, CT keeps its roles; the 2 leave: T's roles return |
| `botround` | two restarts (both event orders) with script pilots up and crews at the tables: no flight or crew AI state survives; roles resume, a new sortie starts and the crews fire again |

Invariants added to every run (every 16 ticks): script roles only on bots; an AI crewman in seat a of his crew with seat b empty; an AI
pilot with the air role; no bot flying without the AI pilot role; no aircraft flown by two players; a deployed AI crewman is the only
pawn allowed frozen outside the sight. **Mutation check** (scratch builds with one rule undone, run with `script=`): 5 of 5 caught. No
aircraft hand-over: "yield: the human who asked for the air got no aircraft". No threshold: "threshold: T kept its script roles with 4
humans". No no-man's-land leash: "the nml leash left a bot out of play". No seat hand-over: "yield (seat): the human who asked never got
a seat". Humans joining script crews: "a player shares a tube with a script bot (crew t_1)".
Two step 3 set pieces were seed-fragile once the random stream moved (the crew piece's loader, the air piece's nose-down crash): fixed in
the mock (a stand-in loader when the firer has no mate; a 60-degree dive instead of straight down). The second showed a real edge in
`rotateToward` (10_util): with the nose exactly vertical and the aim exactly opposite, the side nudge was zero (a division by sin 0); it
now nudges along x. Flight holds the nose within 75 degrees of level, so play never reached it.

Coverage: `node test/mock.mjs 16 300 fill=1 humans=4` (bot and AI rows enforced, fail on 0): deploys to the fire trench 38, support
trench 4, opened areas 9; leash no man's land 1, briefing room 1, far 1, blocker 0 (the `edge` scenario covers the blocker); AI pilots
assigned 5, sorties 10, gun rounds 37, bombs 12; AI crews assigned 4, shots 79. `node test/mock.mjs 32 300`: every step 3 row non-zero,
bot rows 41 / 12 / 27 / 3 (no side under 4 humans there, so the AI rows are not enforced). "RESULT: ok" both.

### Balance with bots

`node ../../create/sim_balance.mjs test/balance.json 150 16 fill=1 humans=4` (4 humans, 2 a side, + 12 bots; 600 s windows; under the
watchdog, 154 s): **T 52 % (75 : 70 : 5, +-4 one SE)**, kills per window 45 / 45; by source rifle 52 % (the rate model), shot down 18 %,
bomb 13 %, mortar 12 %, plane gun 2 %, own crash 3 %; sortie median 59 s; 190 mortar shots per window. Plane guns at 2 % are under the
3 % band: the AI pilots are meant to be poor shots, and the band is a guide for weapons, not for bots; recorded, not tuned.
First, with T in the low slots, 150 runs gave T 61 % (+-4) and the mirror (CT low) 41 %: whichever side holds the low player slots wins
more of the mock's fights. The script treats the sides alike; the mock's fill mode put one side's humans and first bots in slots 0..n.
Fill now interleaves the slots like the default runs (and the rate model shoots in a random order), giving the 52 %. In game, slots go
by join order and mix the sides. The mechanism behind the slot advantage was not found (it is not the rate model's order: shuffling it
alone left 59 %); a candidate for the mock, worth a look if a lopsided result appears in game.
The 32-player balance (no AI roles: 11 humans a side) after step 4: `node ../../create/sim_balance.mjs test/balance.json 50 32` ->
T 51 % (25 : 24 : 1, +-7), kills 177 / 181, plane guns 4 %, bombs 26 %, mortar 7 % (step 3: 54 %).

### Performance with bots

Script time per think, `performance.now()` around `Instance._think()`, the stand-in engine included (as section 4). Budget: 1 ms average,
8 ms max (`perf=1,8`).

| run | PC | avg ms/tick | p99 | max | over 8 ms | result |
|---|---|---|---|---|---|---|
| 64 players, 32 human, 32 bots (no AI roles) | quiet | 0.175 | 0.40 | 3.74 | 0 | ok |
| 64 players, 6 human, 58 bots, AI roles on both sides | quiet | **0.091** | 0.30 | 4.22 | 0 | ok |
| 64 players, 64 human | quiet | 0.329 / 0.344 | 0.65 / 0.71 | 4.61 / 3.97 | 0 | ok (a third run: 71 ms max once, a one-off) |
| the same three, final build | busy: another session's `resourcecompiler` at 97 % CPU | 0.366 / 0.140 / 0.540 | 0.96 / 0.48 / 1.12 | 18.7 / 13.9 / 9.1 | 15 / 9 / 1 | max over 8 ms in all three, the no-bot run too |

Bots cost less than humans (no HUD): the 58-bot run with AI pilots and crews on both sides is the cheapest of the three. The AI's own
work is small by design: the director once a second, the leash once a second per bot (staggered), crew AI only at its state changes, an
AI pilot's target scan 4 times a second; the flight itself is the same `tickAir` a human pilot costs. The busy-PC maxima come with the
64-human run (no AI at all) as well, so they are the PC, not the bots; re-run the perf gate on a quiet PC. On a server the `[tw] perf:`
line gives the real number and now the longest gap between thinks.

### Open questions only CS2 can answer

- The nav area count after the next compile with step 5 + `patch_nav` (target under 5,000; the compile log's nav line), whether NONAV
  markup applies at all (monsoon: unverified too), and whether the tw35 frame hitch is gone with bots on (the perf line's think gap).
- Whether the woods ladders join the nav (M4) and whether nav generation treats the blocker prop_dynamics as solid.
- How CS2's bot brain behaves where the script puts it: fighting from fire steps and staying in the trench; a bot frozen (move type
  NONE) at a mortar table; a bot pawn shrunk, frozen and moved with an aircraft (does its brain fight it, or the knife it holds?).
- Whether `bot_quota_mode fill` with `bot_quota 16` keeps the sides even as humans come and go, and how bot takeover (a dead human
  controlling a bot, `IsControllingBot`) interacts with a script role: not modelled.
- How good (or bad) the AI pilots and crews feel; the AI tuning (`CONFIG.AI`) is a first guess.

### Files (step 4)

`src/modules/85_ai.js` (the bot AI), `00_config.js` (`BOTS_ON` true, `BOTS`, `AI`; `bot_quota_mode normal` out of `CVARS`), `10_util.js`
(`rotateToward` vertical nudge), `30_state.js` (bot fields, counters), `50_roles.js` (`aiCrew`, `seatFree` / `takeSeat` / `airFree` for
humans who ask, deploy targets), `60_air.js` (a steer input for `tickAir` / `gunAim`, no camera for bots), `90_main.js` (quota on activate,
round start, perf line, combat marks, AI pilot steering); `src/mg_trenchwarfare.js` (rebuilt); `test/mock.mjs` (fill mode, 6 bot
scenarios, invariants, bot coverage rows, shuffled rate model, two set pieces made robust); `tools/patch_nav.py` (new);
`tools/check_contract.py` (`--stage`, SetModel check, bot quota rows, mortar models); `docs/SCRIPT.md`, `docs/CONTRACT.md`, this section.
Outputs in `out/`: `nav_input_user.vmap` / `nav_input_step5.vmap` (copies), `nav_patched_user.*` / `nav_patched_step5.*` (map, targets,
guard report, nav report), `nav_check9_step5.json`, `nav_*_run.log`, `nav_gate_*.txt`.
