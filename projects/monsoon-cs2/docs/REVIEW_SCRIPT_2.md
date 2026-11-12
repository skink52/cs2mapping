# mg_monsoon script: review pass 2 (12 Nov 2026, independent second review)

AI-generated (Claude) for skink52. Everything here is **simulated** (mock engine `test/mock.mjs`, `tscheck`, `api.py --strict`): nothing
in this version has run in CS2. Nothing is committed. Review 1: [REVIEW_SCRIPT_1.md](REVIEW_SCRIPT_1.md). VERSION `mv-0.4`.

## Method

- Read CONTRACT.md, SCRIPT.md and every module of `src/` before review 1, then review 1, then mg_trenchwarfare's review 2 (slot
  hand-over, `say` injection, departed controllers, HUD left up), and the repo's `cs2-gotchas.md` / `cs_script-notes.md` entries on
  slots and HUD resets. Every new call looked up with `create/test/api.py` (`IsConnected`, `OnPlayerActivate`, `OnBotControl`,
  `OnPlayerChat`, `OnPlayerDisconnect`, `ResetForPlayer`).
- The build before this pass is kept as `out/review2/before_review2.js` (sources `out/review2/src_before/`, the mock as
  `out/review2/mock_before_review2.mjs`). The mock gained `script=<file>` to run a prebuilt script, so every new set piece was run
  against the old build: **each bug below fails there and passes now** (the "Before" column is the old build's failure text).
- New scenario `review2` (`node test/mock.mjs 32 450 scenario=review2 humans=4`: two humans a side, so the AI holds seats; the river
  bed is cut below the water, `river=1`). One set piece per bug class; `piece=` runs one alone. Passes on seeds 3, 7, 19, 29, 41, 53,
  61, 71.

## 1. Bugs found and fixed

Severity as review 1: **high** = breaks a match or gives a free exploit; **medium** = visible wrong behaviour in a normal match;
**low** = rare, cosmetic or defensive.

| # | Sev | Bug | Fix (file) | Covered by | Before |
|---|---|---|---|---|---|
| 1 | high | **A departed player's controller left in its slot kept playing.** CS2 can leave the controller with `IsConnected()` false, often with no disconnect event (a bot kicked by `bot_quota_mode fill` for a joining human; hellmatch, cs21.6, Space Racer, cs2mapTTT and trenchwarfare all skip such controllers). `buildRoster` only dropped a record when the slot was empty or the controller object changed, so the ghost kept its AI role, its gun crew seat and its helicopter: the director counted it (no replacement AI pilot / crew for the rest of the round, in low population when they matter), its gun idled, its helicopter had a ghost owner, and a departed human still counted toward `humansOn`, kit limits and `!roles` | a slot whose pawn is not alive is checked with `IsConnected()`; a departed controller is treated as an empty slot (`forgetPlayer`, `stats.departed`). Live pawns are not checked (one native call per dead slot, not 64 a tick) (90_main) | `review2` "departed controller": an AI pilot's and an AI crewman's controllers left behind with no event; the role must pass to another bot. Invariant: no record, seat, crew or helicopter may point at a departed controller | "slot 5 (departed, controller left behind) still has the AI pilot role", "the script still plays slot 5 after its player left", "helicopter t_3 is owned by slot 4 who is gone" |
| 2 | medium | **One human could call every AI helicopter home.** `takeHeli` set `yieldTo` on the first AI helicopter without one, and did not look for one already coming for him: a second `!air`, or any respawn with the air preference while waiting, sent a second (and third) AI helicopter home; each AI pilot after the first landed and quit for nobody | `takeHeli` returns "wait" when a helicopter is already coming for him, never takes over one coming for someone else, and clears his wait when he gets a free one (20_players) | `review2` "one yield per human, withdrawn" | "2 AI helicopters were called home for one human" |
| 3 | medium | **A withdrawn helicopter request was still forced on the player.** `!infantry` / `!artillery` after `!air` left `waitRole` and `yieldTo` set (and `!infantry` while infantry only toasted "already"): when the AI landed, the director moved him into the air role and teleported him to the pad, out of whatever he was doing. Also `ai.release` stayed set once a human had been waited for, so an AI pilot whose human left or changed his mind still went home and quit | a request for another role cancels the wait (`cancelAirWait`, toast "Helicopter request cancelled"); the AI's release is recomputed every think from the director's `quit` and a live `yieldTo` (20_players, 85_ai) | same piece, second half: after `!infantry` nobody waits for him and 90 s later he is still on foot | the old build stops at #2; the final build with only #3 reverted (`out/review2/variant_no3.js`): "!infantry did not withdraw the helicopter request" |
| 4 | medium | **A helicopter coming home for a human was locked for the round when its AI pilot left** (kicked, quota cut, team switch). The owner went to -1 but `yieldTo` stayed; the director only hands out or AI-crews helicopters with no `yieldTo`, and `takeHeli` skipped them too: the human waited for ever and the helicopter stood unused | a helicopter with no owner whose `yieldTo` is this human counts as free for him (`takeHeli` and the director's waiting-human pass) (20_players, 85_ai) | `review2` "waiting human, AI pilot gone": every CT helicopter held, the AI ones in the air, a human asks, then the AI pilot coming for him quits | "timed out waiting for: the waiting human to get a helicopter after its AI pilot left" |
| 5 | medium | **A pilot gone over the river drowned his riders.** A helicopter nobody flies (pilot disconnected, killed, kicked, switched sides) let straight down at `AUTOLAND_VS`; over the river touching the water is a ditching, so it was destroyed with everyone aboard. Only the AFK pilot (review 1 #4) had the "hold height, creep to the bank" logic | one `letDown(h)` stick for every unflown helicopter, AFK or empty seat: over water it holds height and creeps toward its pad, over land it settles (30_heli) | `review2` "pilot gone over the river": a pilot quits at 290 u over the river bed | "the pilotless helicopter ditched in the river (dead)" |
| 6 | medium | **A pilot killed in the air got his helicopter back only by dying again.** He redeploys on his pad while the empty airframe is still letting itself down; it lands in the field, and because it still has an owner the abandon recall (review 1 #12) never fetched it: he stood on his pad for the rest of that life | a helicopter standing empty in the field whose owner is alive, on foot and on his own pad is fetched home after `HELI.FETCH` (3 s) (30_heli, 00_config) | `review2` "pilot back on his pad": a pilot killed 2600 u up, the airframe lands after he has redeployed | "timed out waiting for: the helicopter back with its pilot (pilot deployed)" |
| 7 | medium | **An AI gunner kept an abandoned helicopter in the field all round.** The abandon recall needed `crewCount(h) === 0`; an AI gunner never leaves his seat, so a helicopter whose human pilot quit in the field with an AI gunner aboard was lost to its side until the round ended | the recall counts **humans** aboard; a recalled helicopter carries any AI gunner with it (`placeRiders` in `recallHeli`) (30_heli) | `review2` "AI gunner in an abandoned helicopter" (no AI pilot allowed meanwhile, the side's humans on infantry) | "the abandoned helicopter is not on its pad (parked, owner -1, 3000 u from it, recalls 0, aboard - bot9 - -)" |
| 8 | low | **A round restart left empty panels on screen.** `hudReset` (round start, slot change) clears the texts but not `toastUntil` / `bannerUntil` / `infoUntil`, so the round-end banner (12 s, the restart comes after 6 + 4) and any toast came back as empty boxes in the new round | `hudReset` zeroes the three timers (10_util) | new invariant in every run: a shown banner / toast / info card must have its text | `scenario=restart` and every run with a round end: "player 4 sees an empty mv_toast (round 1, t 85)" |
| 9 | low | **Control characters reached the server console.** `say()` stripped `;`, `"`, `\n`, `\r` only; a player name with NUL, ESC or TAB went into `say` through `!pos` | strips `;`, `"` and every control character, caps 200 characters (10_util) | `review2` "say: control characters in a name"; the mock now fails any control character in a server command | "unsafe characters in a server command: \"say [mv] Tom  quit  \u001b[2J\u0000\tx at x ...\"" |
| 10 | low (defensive) | **HUD sent while a joining client was still loading was lost, and never re-sent** (cs2-gotchas: "HUD class changes sent before a joining client is ready are lost"; the per-player cache believes they are on screen) | `Instance.OnPlayerActivate` resets the player's HUD cache, so everything is sent again once the client has loaded (90_main) | mock models the loss window (HUD calls for a loading slot are dropped) in "late join": the briefing card must be up | "the late joiner sees no briefing card (HUD sent while his client loaded was lost)" |

**Test fixes, not script bugs** (the gate's `64 300` and `32 600` failed at HEAD before this pass, with the old mock and the old
sources): "spawn modes" asked for an enemy right after a round restart had put everyone in the briefing room (64 x 300, t 220); "afk"
started its 40 s wait 6 s before round 2 respawned the actor (32 x 600, t 307); "fast-rope" waited for a walker with a looser test than
`actor()` uses (seeds 3, 5, 11). Each now waits out a restart or uses the same test.

## 2. Reviewed, not changed

| Area | Finding | Why not changed / proposal |
|---|---|---|
| AI crew and a human on one gun | A human who joins a gun an AI crewman runs (only when every other gun is full) leaves the bot frozen at it doing nothing, and the director still counts it as the side's AI crew | Rare (`takeCrew` prefers half-crewed and empty guns). Release the bot in `takeCrew` if it matters |
| `!bots` | Any player can set the bot quota or `!bots 0` (kicks every bot, and with them the AI pilots / crews) | Design (`CONFIG.BOTS_CHAT`); switch it off on public servers |
| Waiting human teleported | When the AI brings a helicopter home, `requestRole(force)` deploys the waiting human to the pad from wherever he is (review 1 #3 stops that for requests made in the field, but not for a wait started in the briefing room) | Design: it is what he asked for. Option: give him the helicopter but let him walk / take it at the next deploy |
| Bot takeover | `Instance.OnBotControl` exists; a human taking over an AI pilot / gunner / crew bot would drive a shrunk or frozen pawn | Not demonstrable in the mock (as trenchwarfare review 2). Option: `bot_controllable 0` after checking the cvar exists and is on the Workshop allow list, or `aiRelease` the bot in `OnBotControl` |
| Events between ticks | `OnPlayerReset` / `OnPlayerKill` / `OnPlayerChat` use `P(slot)` without comparing the controller; a hand-over is caught by `buildRoster` at the next tick, and the mock's `swap-slot` churn shows no state surviving it | No visible effect found; trenchwarfare's `claim()` pattern if one appears |
| Stale team in `OnPlayerReset` | cs2-gotchas: it can fire on a team change with the old team. `chooseRole` then runs for the old side, and `thinkPlayer`'s team check undoes it (`leaveTeam`) on the next tick | Self-healing within a tick |
| AI pilot released while crashing | When the director releases a pilot bot whose helicopter is crashing, the bot jumps clear | Cosmetic; the crash credit for one bot is lost |
| Team switch death | The ticket for the switch's suicide goes to whatever team the pawn reports at the kill event | CS2's order of events decides; recorded |

Checked and fine: seat entry / exit / death in every helicopter seat, emplaced gun and the board (cameras restored, weapons stowed and
returned, frozen / shrunk flags cleared on reset); a pilot disconnecting mid-flight over land (review 1's "pilot quits mid-air");
team switch alive and dead from every seat (`churn`); round end with helicopters in the air and shells in flight, CS2 restart and
the script's own (`restart`: arrays cleared, map handles re-found by name through the cleared entity cache, helicopters / guns /
mounts rebuilt by `loadPoints`); AI seat hand-over to a human exactly once (emplaced gun, door gun, crew; helicopters now too);
division by zero / NaN in flight, rockets, ballistics, board and AI aim (every divisor guarded or constant; `vnorm` of a zero
vector returns zero, not NaN); tickets: underflow clamped, one round end, simultaneous zero is a draw unless flags differ, contested
flags frozen, capture rate capped; HUD writes skipped for bots and for slots without a record.

## 3. Review 1 compared

**Missed by review 1:** all ten above. #1 is guarded in five sibling projects; #10 is a cs2-gotchas entry. #2 to #7 are interactions
between features review 1 tested one at a time (the AFK let-down existed but only for AFK; the abandon recall existed but only for an
empty, ownerless airframe).

**Claimed fixed, only partly:**
- Review 1 #4 "AFK pilot in the air" and #13 "touching the water is a ditching": together they made every *other* pilotless
  helicopter over the river a death trap (#5 here).
- Review 1 #12 "a helicopter abandoned in the field is fetched": not when an AI gunner sat in it or its owner was waiting on his pad
  (#6, #7 here).
- Review 1 "AI hand-over: toast only after the role is granted" (#23): the hand-over could be triggered more than once per human
  and could not be withdrawn (#2, #3).

**Confirmed:** review 1's scenarios (`churn`, `restart`, `edge`, `reload`) pass; its fixes are in the code.

**Docs drift (not this pass's files):** `docs/SCRIPT.md` "Tests" should list `scenario=review2`, `script=`, `river=1`; the CONFIG
guide's `HELI` row should mention `FETCH`.

## 4. Gate (12 Nov 2026, final build: 3397 lines)

| Step | Result |
|---|---|
| `node tools/build_script.mjs` | 11 files, 3397 lines, 254,755 bytes |
| `api.py --strict --check` / `tscheck.sh` | 0 problems (0 invalid, 0 deprecated) / OK |
| `node test/mock.mjs 32 300` / `4 600` / `64 300` | PASS / PASS / PASS |
| `32 600` (every set piece, coverage table) / `64 600 humans=32` | PASS / PASS (also `32 600` seeds 3, 5, 11; `64 300` seeds 3, 5) |
| `32 300 scenario=churn` / `restart` / `edge` / `reload` | PASS x 4 |
| `32 450 scenario=review2 humans=4` | PASS (seeds 3, 7, 19, 29, 41, 53, 61, 71); every piece FAILS on the pre-pass build |
| `MOCK_NORESTART=1 node test/mock.mjs 32 600` | PASS |

Script time, one run at a time on an idle machine (the stand-in engine's own calls included), before / after this pass:
`64 600 humans=32` 0.093 / 0.093 ms/tick avg, p99 0.29 / 0.30, max 6.1 / 5.7 ms; `64 300` 0.116 / 0.113 avg, max 6.3 / 9.0 (one
tick over 8 ms: a round start). The departed-controller check costs one `IsConnected()` per dead slot per tick. Runs made ten at a
time in parallel show 50-70 ms maxima: that is the machine, not the script.

## 5. Balance

`node test/sim_balance.mjs` (40 seeds x bots + mixed, 32 players, real CONFIG; under the watchdog: 1:10, log
`out/review2/sim_balance.log`). No CONFIG number changed in this pass; the fixes touch hand-overs, departures and empty helicopters,
which these rounds seldom hit, so the figures sit inside review 1's noise (one standard error of a win rate over 40 seeds is about
8 points).

| | bots (review 1 after) | bots now | mixed (review 1 after) | mixed now | target |
|---|---|---|---|---|---|
| round length median (p25-p75) | 11:36 | 11:53 (10:43-13:06) | 17:30 | 17:43 (15:35-18:39) | 12-20 min |
| T : CT wins, T win rate (decided) | 77 % | 30 : 10, **75 %** | 50 % | 19 : 21, **48 %** | 45-55 % |
| dead flags | c | c (T holds it 92 %) | none | none | none |
| kills: rifle / mg (model) | 60 / 26 % | 60 / 25 % | 63 / 17 % | 62 / 17 % | 3-40 % each |
| kills: at / heligun / helirocket / arty / mount | 1 / 3 / 6 / 3 / 2 % | 0 / 3 / 6 / 4 / 2 % | 1 / 2 / 9 / 3 / 4 % | 1 / 2 / 9 / 3 / 5 % | 3-40 % each |
| helicopter life median (p25-p75) | 63 s | 55 s (27-124) | 113 s | 111 s (35-243) | 60-180 s |
| helicopters lost per round, T : CT over 40 rounds | 4.4 : 3.9 | 170 : 154 (8.1 / round) | 7.8 : 4.5 | 328 : 189 (12.9 / round) | |
| AI uptime pilot / gunner / crew | 50 / 99 / 98 % | 50 / 98 / 98 % | n/a | n/a | >= 50 % |

The mixed set meets every target except the per-source band for rifle (the rate model), AT and the door / chin guns (review 1 explains
why that band does not fit an infantry-first mode). The bot-only T bias (75 %, flag B nearer the T base, flag C dead) is review 1's
open map question, unchanged.

## 6. What only CS2 can confirm

- **#1**: that a departed player's controller really stays with `IsConnected()` false (the five sibling projects assume it), and that
  a dead bot between lives reports `IsConnected()` true (if it reported false, every dead bot would lose its record each life: watch the
  `departed` counter in `__mvDebug.stats` / the AI roles in a bot match).
- **#10**: that `OnPlayerActivate` fires after the client's HUD layout is ready, and that `ResetForPlayer` also clears dialog
  variables (the empty-panel fix #8 assumes it does).
- **#5**: the over-water test is "the ground trace ends below `water_z`". If the river is a water volume the trace stops on, the
  helicopter never knows it is over water (and review 1's ditching never triggers either): look once at a helicopter put down in the
  river in game.
- **#6**: the fetch rule ("owner alive, on foot, within 600 u of his pad") against what pilots actually do between lives.
- Everything in SCRIPT.md "Not yet tested in CS2" and review 1 section 5 still stands.

## Files

`src/00_config.js` (VERSION mv-0.4, `HELI.FETCH`), `src/10_util.js` (`say`, `hudReset`), `src/20_players.js` (`takeHeli`,
`cancelAirWait`, `requestRole`), `src/30_heli.js` (`letDown`, `humansAboard`, the field recall, `recallHeli`), `src/85_ai.js` (`quit` /
`release`, the waiting-human pass), `src/90_main.js` (`buildRoster` departed controllers, `OnPlayerActivate`, stats);
`test/mock.mjs` (`review2` scenario, `script=`, `river=1`, `IsConnected` / `depart()`, `OnPlayerActivate` and the loading window,
the empty-panel and departed-controller invariants, control characters in server commands, the three set-piece fixes); this file.
`out/review2/` holds the pre-pass build, sources and mock, and the balance log.
