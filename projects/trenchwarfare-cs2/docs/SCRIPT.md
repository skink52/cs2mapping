# mg_trenchwarfare game script

`src/modules/NN_*.js` joined by the neutral `create/build_script.mjs` (settings `src/build.json`) into `src/mg_trenchwarfare.js`,
the file that ships (the addon copy is `content\...\maps\scripts\mg_trenchwarfare.js`, run by the map's `tw_script` point_script).
Names the script shares with the map and the HUD: [CONTRACT.md](CONTRACT.md). Review pass 1: [REVIEW_SCRIPT_1.md](REVIEW_SCRIPT_1.md).
AI-generated (Claude) for skink52.

Status: **simulated** (mock engine, `tscheck`, `api.py --strict`, 12 Nov 2026). Nothing in this version has run in CS2. See
"Simulated vs not yet tested in CS2".

## Structure

Build: `node ../../create/build_script.mjs src/build.json` (from the project folder) joins the modules in name order under ONE import
line from `cs_script/point_script` (imports: every const / enum of Valve's `point_script.d.ts` the modules use, found automatically) and
writes the header "generated, do not edit". A module must not import or export anything: they share one scope. `--check` reports a
shipped file older than its modules (exit 1); `test/mock.mjs` and `tools/check_contract.py` fail on a stale build. Never edit
`src/mg_trenchwarfare.js` by hand.

| File | Holds |
|---|---|
| `00_config.js` | the map-entity summary, the one `CONFIG` object, `T` / `CT`, `tagOf`, `enemyOf`, role names |
| `10_util.js` | small helpers (`live`, `byName`, `fire`, `say`, `pawnOf`, `creditOf`, `hurt`, `clock`), vectors and angles (`angleBasis`, `anglesNear`, `rotateToward`), `planeEnts`, `groundZ` |
| `20_points.js` | `points` (named map points, read on the first tick of a round), `parkMemo` / `parkCarry` (aircraft parks over a script reload), `placeProp` |
| `30_state.js` | player records `P(slot)` (with `gen`, a new number per record, for credit checks), mortar `crews`, `shells`, the `stats` counters, `globalThis.__twDebug` |
| `40_hud.js` | the HUD cache (`hText` / `hClass` / `hSwap`, only changes sent, nothing for bots), `hudReset`, toast, info card, role cards, banner |
| `50_roles.js` | crew seats, `chooseRole`, `airFree`, `requestRole` (deferred in the field), `leaveTeam`, `equip`, `pickTrench`, `deploy`, `uniform`, `sanitise`, `hidePawn`, `swapRifle` |
| `60_air.js` | aircraft: arcade flight (`tickAir`, `capHeading`, `boundsWeight`), guns, bombs, tracers, sights, cameras, crash, `hitPilot`, cockpit instruments |
| `70_mortar.js` | the sight map (`sightToWorld` / `worldToSight`), `fireMortar`, effect pool, `impact` (damage, loader share, credit), shells, the crew stations, the targeting HUD |
| `75_front.js` | areas blown open during the round (`CONFIG.UNLOCKS`), cosmetic no man's land bursts |
| `85_ai.js` | bots: `isBot`, `nearLock`, `tickBot` (the leash). **The seam for remaster step 4**: `aiThink(t, dt)` is called once per tick and is empty today |
| `90_main.js` | think loop (`SetNextThink` first, try/catch per player), `perfLine`, `dropPlayer`, `tickAfk`, `thinkPlayer`, engine events, the damage guard and `crewDeathLog`, chat, `radarSquare`, `OnScriptReload`, the test seam |

One think per tick: points (first tick of a round) -> shells, bombs, tracers, ambient, unlocks -> `aiThink` -> every slot 0..63
(team change, AFK, briefing room or role: flight / mortar stations / healing / leash, HUD) -> the per-minute perf line.

Things worth knowing:
- Credit: every shell, bomb and crash carries the firer's slot **and** `gen`; `creditOf(slot, team, gen)` gives the pawn only while that
  slot holds the same player on the same side. Otherwise the damage has no attacker (the damage guard then treats it as world damage).
- A shot-down plane: the shooter gets the pilot (`crashPilot`), the wreck's blast on the ground is the pilot's.
- The mortar loader's share of a hit is armour-piercing (`CSDamageFlags.IGNORE_ARMOR`) and at least `CONFIG.ASSIST_MIN` health damage
  when the victim can take it, so it can earn an assist (CS2's assist rule is assumed to be CS:GO's "more than 40").
- The damage guard (`OnModifyPlayerDamage`) drops any damage to a pilot in the air or a crewman within 320 u of his tube that does not
  come from an enemy player, and prints `[tw] blocked <n> damage to <pilot|mortar pit> (slot, types, flags, attacker, inflictor, distance)`.
  Every crewman's death prints `[tw] crew death: ... attacker ..., inflictor ..., weapon ..., own tube fired <s> ago`.
- Role commands in the briefing room change the role now (if open); in the field they become the preference for the next deploy.
- `uniform()` sets the soldier model only in the briefing room, before `deploy` issues the kit, and never on a shrunk pilot.
- `sanitise(p, pawn)` puts a pawn back to scale 1, `WALK`, camera off: on every `OnPlayerReset`, at round start for pilots and plotters,
  and on the first look at each pawn after the script (re)loads.
- AFK (humans): `CONFIG.AFK.PILOT` 60 s with no key, turn of the view or step -> the aircraft goes home and the pilot deploys as
  infantry; `CONFIG.AFK.CREW` 120 s -> the crew seat is freed.
- `!pos` prints the radar square from `CONFIG.RADAR` (= `out/radar_region.json` = the overview's pos_x / pos_y / scale x 1024), in
  `tools/make_radar.py`'s 16 x 16 grid (A-P across, 1-16 down). The mortar sight's GRID is a different, per-team square.
- Chat: `!infantry` / `!rifle`, `!mortar` / `!artillery`, `!air` / `!pilot`, `!roles`, `!swap` (also SHIFT+E), `!pos`, `!uniform`, `!random`.
- HUD: every id and class the script sends is in CONTRACT.md "HUD" and is checked against the restaged xml / css by both
  `tools/check_contract.py` and the mock. There are no optional "HUD additions" (monsoon's `hudnew=1` does not apply here).

## CONFIG guide

| Section | What to tune |
|---|---|
| `LOBBY_*`, `MORTAR_CHANCE`, `ROTATE_CHANCE`, `AIR_CHANCE` | briefing time; how players are drawn into the crews and the air |
| `INF_*`, `STREAK_UPGRADE`, `UPGRADE`, `*_NAME` | infantry kit per team (classes come from the addon's weapons.vdata), the streak weapon |
| `HEAL_*`, `STATION_RADIUS` | dressing stations; how close a crewman must be to the table / ammo box |
| `TARGET_EXT`, `TARGET_STEPS`, `SIGHT_*` | the sight map square and its marker steps (must match `render_top.py` and `tw_hud.py`: CONTRACT "Files") |
| `SHELL_*`, `TRENCH_COVER`, `SPREAD_*`, `FLIGHT_*`, `RELOAD_COOLDOWN`, `FRIENDLY_SPLASH`, `ASSIST_MIN` | mortar shells and the loader's assist share |
| `AIR`, `AIR_*` | flight feel, bounds, guns, bombs, camera, lives and slots |
| `UNIFORMS*` | soldier models per team (each needs its `tw_uniform_N` precache prop) |
| `UNLOCKS` | which blockers open, after how many kills or seconds |
| `BOTS`, `BOTS_ON` | the leash (`LEASH_AVOID`: the post it sends a bot to is that far from a closed blocker); bots off by default |
| `AFK`, `PERF_EVERY` | AFK times for pilots and crews; the console perf line's period |
| `CVARS`, `POOL`, `RADAR`, `HUD` | server settings; effect pool size (must match the map); radar region (must match the overview); HUD entity |

Decisions in review pass 1 (reasons in REVIEW_SCRIPT_1.md): field role changes wait for the next deploy (the role cards always said so);
the loader's share ignores armour; the wreck's blast belongs to the pilot. CONFIG numbers were not changed by the balance pass.

## Tests

From the project folder (`projects/trenchwarfare-cs2`), after `python tools/restage_out.py` has built `out/`:
```
node ../../create/build_script.mjs src/build.json          # build (and --check: fails when the shipped file is stale)
node test/mock.mjs 32 120                                  # quick run (about 2 s)
node test/mock.mjs 32 300                                  # coverage table: any feature at 0 fails (16+ players, 300+ s)
node test/mock.mjs 32 150 scenario=all                     # the six bug-class scenarios, each in its own process: pass / total
node test/mock.mjs 32 150 scenario=churn                   # one: round | churn | crew | air | reload | edge
node test/mock.mjs 64 300 humans=32 perf=1,8               # 64 players: fails over 1 ms/tick average or 8 ms max
node ../../create/sim_balance.mjs test/balance.json 50 32  # 50 seeded 10-minute windows (about 4 min: run under the watchdog)
python tools/check_contract.py                             # names vs the map, addon, HUD; stale build
```
Scenarios (each set piece fails without its fix; REVIEW_SCRIPT_1 lists which): `round` (three round restarts, both event orders,
with pilots in the air and crews in the sight), `churn` (disconnects of pilots in the air, plotters, carriers, firers with a shell in
flight; slot reuse with a stale HUD; team switches alive and dead; spectating), `crew` (world damage at the tube, own shell on own
pit, an enemy shell killing a crewman, the loader's assist through armour, a firer who changed sides before impact, damage before the
first think of a round), `air` (AFK pilot, `!uniform` and `!infantry` while flying, crash credit with the hitter present and gone,
two players asking for the last aircraft), `reload` (two script reloads mid-round with aircraft up: clock, kills, unlocks, parks, pawns),
`edge` (field role change deferred and applied, `!uniform` in the field, `!pos` against `out/radar_region.json`, chat from a spectator,
the leash post picker, a 1 s hitch).
Invariants every 16 ticks in every run: crew seats and aircraft point only at connected players of that side who hold them; no player
record for a disconnected slot; no live pawn out of an aircraft left shrunk or on a camera, none frozen outside the sight; no
non-finite position. The mock also fails on: a call outside the current API, an input at a missing entity or one its class lacks, an
unknown HUD id / class, a HUD call for a bot, `SetModel` on a shrunk pawn or after the kit was issued, a team kill credited.
Switches: `seed=`, `humans=`, `script=<file>` (another build, no stale check), `mode=balance json=1`, `engage=`, `ttk=`, `planep=`
(the rate model), `MOCK_LOG=1`.

The stand-in engine: map entities from `out/entities.json` (re-created each round); ground at z 0 except trench floors, pits and
stations (from their named points); a man is three 18-u spheres; armour halves bullet / blast damage unless `IGNORE_ARMOR`; the
pawn keeps its model scale and camera across a respawn (the worst case). Humans are driven through every role (crews walk the
ammo box -> tube -> table loop and aim at enemies through the sight; pilots fly an attack profile and put the crosshair on a man;
infantry swap rifles and walk to dressing stations); the infantry fight is a rate model.

## The gate, in order

From the project folder unless marked; anything over ~2 min under `python C:\source1\cs2port\autoport\watchdog.py`.
1. `python tools/restage_out.py` (when `out/` is missing or the map / addon changed; 8 s).
2. `node ../../create/build_script.mjs src/build.json` -> "11 modules".
3. Repo root: `python create/test/api.py --strict --check projects/trenchwarfare-cs2/src/mg_trenchwarfare.js` -> "0 problems (0 invalid,
   0 deprecated, 0 allowed)"; `sh create/test/tscheck.sh projects/trenchwarfare-cs2/src/mg_trenchwarfare.js` -> "tscheck: OK" (Git Bash).
4. `node test/mock.mjs 32 300` -> coverage with no 0 row, "RESULT: ok".
5. `node test/mock.mjs 32 150 scenario=all` -> "scenarios: 6 / 6 pass".
6. `node test/mock.mjs 64 300 humans=32 perf=1,8` -> "RESULT: ok".
7. `python tools/check_contract.py` -> exit 0 (1 known missing: `mortar_<tg>_K`).
8. When the script or CONFIG changed: `node ../../create/sim_balance.mjs test/balance.json 50 32` under the watchdog.
Then (not offline): copy `src/mg_trenchwarfare.js` to the addon, compile, the TESTING checklist.

## Simulated vs NOT YET TESTED IN CS2

Simulated (mock engine, 12 Nov 2026, review pass 1): role flow and briefing room, deploys, infantry kit and streak swap, dressing
stations, the whole mortar loop for both sides (sight steering, lock, load, fire, impacts, credit, assist share), flight (take-off,
bounds, attacks, guns, bombs, crash, AFK), unlocks, the leash, uniforms, round restarts, script reload, disconnects, slot reuse,
team switches and spectating, `!pos`, HUD ids and classes. `tscheck` and `api.py --strict` clean.

Not yet tested in CS2 (every item is an assumption):
- CS2's assist rule (assumed: more than 40 health damage) and whether `IGNORE_ARMOR` on `TakeDamage` behaves as declared.
- What kills mortar crews "when firing" in game: the script has no path that damages its own side (REVIEW_SCRIPT_1 #19); the
  `[tw] crew death` and `[tw] blocked` console lines will name the attacker / inflictor.
- Whether `SetModel` in the briefing room (before the kit) avoids the giant first-person weapon, and whether the pawn's model scale
  and custom camera survive a respawn (the mock assumes they do; `sanitise` covers both cases).
- `SwitchToWeapon` to the knife while plotting (MOUSE1 then swings the knife, harmless) and back.
- `OnScriptReload` in the tools: whether `before()` still reads the old module's state; the parks carried over.
- `CustomHudLayout.ResetForPlayer` clearing a slot's overrides for the next player.
- Flight feel after the turn-side fixes (the wall turn and reversals now commit to one side).
- Script time on a server: the mock measured it with its own stand-ins included; the `[tw] perf:` line once a minute is the real number.
- Balance with people: the mock's infantry stand still at their posts (bombs and shells do better than against people who move).
