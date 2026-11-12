# mg_trenchwarfare script: review pass 2 (12 Nov 2026, independent second review)

AI-generated (Claude) for skink52. Everything here is **simulated** (mock engine `test/mock.mjs`, `tscheck`, `api.py --strict`): nothing in
this version has run in CS2. Nothing is committed. Review 1: [REVIEW_SCRIPT_1.md](REVIEW_SCRIPT_1.md); world side: [REVIEW_WORLD_2.md](REVIEW_WORLD_2.md).

## Method

- All eleven modules of `src/modules/` were read before review 1 was opened. Every suspect got a mock scenario or a check that **fails
  on the build as it stood before this pass** (kept as `out/review2/before_review2.js`, its modules in `out/review2/modules_before/`,
  the mock as `out/review2/mock_before_review2.mjs`; run with `script=out/review2/before_review2.js`). Only bugs that failed there were
  fixed, each in its owning module; then the build and the whole gate (below).
- Every new call was looked up with `create/test/api.py` (`IsConnected`, `GetPlayerController`, `OnBotControl`, `TraceLine`).

## 1. Bugs found and fixed

Severity as review 1: **high** = breaks a match, a free exploit or a server risk; **medium** = visible wrong behaviour in a normal
match; **low** = rare, cosmetic or diagnostic. "Before" is the failure text of the scenario on the pre-pass build.

| # | Sev | Bug | Fix (module) | Scenario | Before |
|---|---|---|---|---|---|
| 1 | high | **A slot that changes hands with no disconnect event keeps the last holder's record.** CS2 kicks a bot to make room for a joining human without `OnPlayerDisconnect` (the repo's own `cs2-gotchas.md` and `cs_script-notes.md`; with `bot_quota_mode fill`, the bot kicked is usually on the side the human joins). The script keyed records by slot only. The human who takes an **AI crewman's** slot inherits `aiRole "crew"`: every deploy freezes him (move type NONE) at the plotting table and `tickAICrew` fires his tube. The human who takes an **AI pilot's** slot flies with `aiSteer` holding the stick (his mouse ignored) for the rest of his lives. Any newcomer also inherits kills, air lives, preferences, `!uniform` choice, the HUD classes on screen and the `gen` that shells / bombs in flight are credited by | the record keeps its controller (`p.ctl`); `claim(slot, ctl)` drops the last holder's record (`dropPlayer`: aircraft home, seat freed, AI role dropped, `ResetForPlayer`) when the controller differs, and the newcomer starts fresh. Used by `thinkPlayer`, `OnPlayerReset`, `OnPlayerKill` (victim and attacker), `OnPlayerChat` (90_main; `p.ctl` in 30_state, `ctlOfPawn` in 10_util). cs2mapTTT (played) and monsoon compare the controller object the same way | `handover` (new, fill, 2 + 2 humans): an AI crewman's, an AI pilot's and a human's slot are each taken over with no disconnect event | "a human has a script role (crew, slot 7)", "a human has a script role (pilot, slot 5)", "the newcomer in slot 0 plays on the last holder's record", "the newcomer inherited 7 kills", "the newcomer kept the last holder's HUD" (13 failures) |
| 2 | high | **Server command injection through `!pos`.** It sends `say [tw] <player name> at x ...` with `Console.ServerCommand`; a name containing `;` ends the `say` and runs the rest as a server command (`quit`, `mp_restartgame 1`, `exec ...`), and `"` breaks the quoting. `cs_script-notes.md` already says to strip both (Hellmatch, Space Racer) | `say()` strips `;`, `"` and control characters from everything it sends (10_util), so every present and future `say` is covered | `edge` (g): `!pos` from a player named `Tommy";quit;"`. The mock now also fails a `"` or `\r` in a `say` | `unsafe characters in a server command: say [tw] Tommy";quit;" at x -3323 y 1655 z -23  radar square B6` |
| 3 | medium | **A disconnected player's controller left in the slot counts as a human.** CS2 can keep the controller with `IsConnected()` false (hellmatch, cs21.6 and Space Racer all skip such controllers; this script did not). `thinkPlayer` kept a record for the slot, and `humansOn` counted the departed player: a side whose humans left kept counting them, so its AI pilots and crews never came back (low population is when they matter) | `isOn(c)` (10_util: controller present and `IsConnected()`) in `thinkPlayer` (90_main, drops the record) and `humansOn` (85_ai) | `threshold`: the two humans who leave now leave their controllers behind, as CS2 may | "player record kept for disconnected slot 16", "threshold: the script roles did not come back after the humans left" |
| 4 | medium | **Spectating leaves the HUD up.** With no live pawn on a side only the sight and the prompt were hidden: a player who went to spectate from the briefing room kept the orders sheet ("Moving up in 0s") over the spectator view, a spectator kept his role card, and the toast / banner timers froze while dead (a toast shown at death stayed up until the respawn) | `hudIdle(p, t)` (90_main) for a dead or side-less pawn: sight, prompt and orders sheet down; role card and cockpit down without a side; toast and banner keep their timers | `edge` (d) and (h) | "a spectator kept the role card / orders sheet on screen (slot 1)", "spectating from the briefing room left the orders sheet up (slot 3)" |
| 5 | low | **The damage guard floods the console.** One `[tw] blocked` line per blocked hit; the guard exists for props grinding a hidden pilot or a crewman, which hit every tick: 64 lines a second per player, all of them `Console.Log` on the server | one line per player per 2 s, with "N more blocked since the last line"; `stats.blocked` still counts every hit (90_main; `blockedLogAt` / `blockedQuiet` in 30_state) | `crew` (g): 64 grinding hits on a crewman at his tube in one second | `the damage guard printed 64 "[tw] blocked" lines for one crewman in one second` |

Mutation check: each of the five scenario pieces fails on the pre-pass build (quoted above) and passes on this one; the `threshold`
failure for #3 also shows on the build with #1, #2, #4 and #5 fixed, before `isOn` went in.

## 2. Reviewed, not changed

| Area | Finding | Why not changed / proposal |
|---|---|---|
| Air lives | `setRole("air")` re-arms `AIR_LIVES` every time. A pilot shot down twice is infantry for one life and then, with his standing `air` preference, flies again with 2 lives; typing `!air` in the 1.5 s briefing window after the last death skips even that life. The role card says "2 lives, back to ground" | A design call. If the lives should bind: keep `p.lives` until N infantry deaths or a time, and set lives only when they are spent |
| AI crew release | `aiDrop` clears the crew's AI state but not `c.loaded` / `c.target`: the next human crew in that pit starts with a loaded, targeted tube (one free shell) | Harmless; clear both in `aiDrop` if it matters |
| AFK crewman | made infantry where he stands, with the mortar kit (pistol, armour 100), until his next death; the card says "Rifle: Gewehr 98" | Design (no teleport on AFK); `deploy()` there would fix both |
| Bot takeover | `Instance.OnBotControl` exists ("a player takes or releases control of a bot"). A human taking over an AI crewman would control a pawn the script freezes, an AI pilot's pawn is shrunk inside an aircraft. Review 1 listed it as not modelled | Not demonstrable in the mock. Option: add `bot_controllable 0` to the bot commands in `OnActivate` (passes the mock's `bot_` rule), after checking in game that the cvar exists in CS2 |
| Script reload (tools only) | aircraft flying under the old script go home on reload, but their engine loop and smoke (started by the old script) are not stopped | Fire `StopSound` / `Stop` for each aircraft in `loadPoints` when `parkCarry` is set |
| Wreck position | a pilot killed in the air (not crashed): the wreck's blast (`endFlight` crashed) goes off where the aircraft is, in the air | Cosmetic; it harms nobody unless near |
| Credit when the firer left | a shell or bomb whose firer left or changed sides has no attacker; the guard then blocks it on crewmen at their pits and on pilots (they only take enemy-player damage) while infantry take it | Consistent with review 1's design, asymmetric; recorded |
| Deploy wave cost | at a round start about 30 deploys a side happen in one tick; `pickTrench` loops 20 posts x the deployed infantry with three engine calls each (about 6,000 native calls). Mock max 4.5 ms; the engine's call cost is unknown | The `[tw] perf:` line's max and think gap will show it in game; stagger `deployAt` by slot if it does |
| HUD entity per round | `OnRoundStart` clears the HUD cache on the assumption that `tw_hud` is re-created; if it survives a restart, `hSwap` groups (gauge needles, sight markers) could keep last round's class next to the new one | Assumption recorded (review 1 shares it); `hudReset` per player at round start would remove the doubt |
| Whistle | `tw_whistle_attack` (patch_sounds) stands in the briefing room and fires in the tick everyone deploys from it; its soundevent is `csgo_mega` with a distance curve | In game: confirm the deployed players hear it (if not, make it 2D or fire it a moment earlier) |

Checked and fine: think rescheduled first and per-player try/catch; seat and aircraft invariants through team switches, deaths in
the briefing room, AFK, yields and restarts; `creditOf` gen and team checks; the loader's armour-piercing share; `points` null guards
in every event; HUD writes skipped for bots (now also for records an event creates, because `claim` reads `IsBot` from the controller).

## 3. Review 1 compared

**Missed by review 1:** all five bugs above. #1 and #2 contradict the repo's own notes (`cs2-gotchas.md` "a slot can change hands with no
disconnect event"; `cs_script-notes.md` "strip `;` and `"` from anything sent with `ServerCommand("say ...")`"). #3 is guarded in three
sibling projects.

**Claimed fixed, only partly:**
- Review 1 #12 "a slot that changed hands kept the last player's HUD classes" and #6 credit "a slot that changed hands": both only held
  when `OnPlayerDisconnect` fired first. The `churn` scenario always sent the event before reusing a slot, so it could not see the
  case the gotcha describes. Now fixed by `claim` (#1 here).
- Review 1 #16 "HUD writes for bots skipped": `p.bot` was set only by `thinkPlayer` / `chooseRole`, so a record an event created first
  (a bot's kill in its first tick: `toast` on the attacker) could still write to a bot's HUD. `claim` now sets `p.bot` from the controller.
- Review 1 step 4 lists bot takeover as not modelled: right, and `OnBotControl` now exists in the API (section 2).

**Confirmed:** review 1 #1-5, 7-11, 13-15, 17, 18 are in the code and their scenarios pass; the balance and performance numbers reproduce.

**Docs drift (not this pass's files):** `docs/SCRIPT.md` says "scenarios: 12 / 12" and "check_contract -> 1 known missing"; now
13 / 13 (`handover` added) and 4 known missing on the deployed map (`mortar_<tg>_K`, `tw_whistle_attack`, `tw_plane_dive_1..4`,
`tw_rain_tin_<tg>_1..3`; against the chained map 0 missing). Its scenario list needs `handover`.

## 4. Gate (12 Nov 2026, final build: 2032 lines)

| Step | Result |
|---|---|
| `node ../../create/build_script.mjs src/build.json` | 11 modules, 2032 lines; `--check` up to date |
| `api.py --strict --check` / `tscheck.sh` | 0 problems (0 invalid, 0 deprecated, 0 allowed) / OK |
| `node test/mock.mjs 32 300` | RESULT: ok, no coverage row at 0 |
| `node test/mock.mjs 16 300 fill=1 humans=4` | RESULT: ok, bot and AI rows non-zero |
| `node test/mock.mjs 32 150 scenario=all` | **13 / 13** on seeds 7, 3, 19, 29 |
| `node test/mock.mjs 64 300 humans=32 perf=1,8` | ok: 0.218 ms/tick avg, 4.33 max |
| `node test/mock.mjs 64 300 humans=6 perf=1,8` | ok: 0.081 ms/tick avg, 4.48 max |
| `python tools/check_contract.py` | exit 0: 81 rows, 77 OK, 4 known missing (deployed map) |
| `check_contract.py --vmap out/mg_trenchwarfare_sounds.vmap --stage out/addon` | 86 rows, 86 OK, 0 missing |
| `sim_balance 50 32` (watchdog) | T 51 % (25 : 24 : 1), kills 177 / 181; rifle 46 % (the rate model, the known MISS), mortar 7, plane gun 4, bomb 26, shot down 12 % |
| `sim_balance 150 16 fill=1 humans=4` (watchdog) | T 52 % (75 : 70 : 5), kills 45 / 45; rifle 52 % (model), plane gun 2 % (AI pilots, as review 1) |

The perf runs passed while another session's `resourcecompiler.exe` (mg_monsoon) was running. The balance numbers equal review 1's:
none of the fixes changes a seeded run that has no slot hand-over, spectator or departed controller. Logs: `out/review2/`.

## Files

`src/modules/10_util.js` (`say` strips, `ctlOfPawn`, `isOn`), `30_state.js` (`ctl`, the guard's log throttle fields), `85_ai.js`
(`humansOn` skips departed controllers), `90_main.js` (`claim`, `hudIdle`, the throttled guard line, the event hooks); `src/mg_trenchwarfare.js`
(rebuilt); `test/mock.mjs` (`handover` scenario, `edge` (g) / (h) and the spectator check, `crew` (g), lingering controllers in `threshold`
and the engine's `GetPlayerController`, `"` / `\r` in a `say` fail); this file.
