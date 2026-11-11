# mg_monsoon script: review pass 1 (12 Nov 2026)

Adversarial review, coverage, balance and performance pass over `src/*.js` (VERSION `mv-0.3`). AI-generated (Claude) for skink52.
Everything here is **simulated** (mock engine `test/mock.mjs`, `tsc`, `tscheck`, `api.py --strict`): nothing has run in CS2.
Two sessions did this pass; the second finished it. Nothing is committed.

## 1. Bugs found and fixed

Severity: **high** = breaks a match or gives a free exploit; **medium** = visible wrong behaviour in a normal match; **low** = rare or
cosmetic. "Covered by" is the mock scenario / set piece that fails without the fix (`node test/mock.mjs 32 300 scenario=edge piece="..."`
runs one alone).

| # | Sev | Bug | Fix | Covered by |
|---|---|---|---|---|
| 1 | high | On an emplaced gun or at the plotting board the pawn kept its rifle: MOUSE1 fired the gun and the rifle together | `stow()` on every seat that reads MOUSE1; weapons come back on leaving | mounts, board, `deaths in seats` |
| 2 | high | Leaving any seat re-issued the kit "fresh": a reloaded AT launcher and new armour every time (exploit) | `equip(p, pawn, fresh)`: only deploys and arms racks issue fresh | `at + counter-battery` (launcher not reloaded by a seat) |
| 3 | high | `!air` / `!artillery` out in the field re-deployed the player at once: a free teleport out of any fight | role changes are immediate only in the briefing room or at the base; elsewhere they wait for the next deploy | `two on one seat` (role deferred) |
| 4 | high | A pilot who went AFK in the air: nothing happened, the helicopter hovered forever with its seats taken | AFK (120 s, no key / look / step): the stick is released, the helicopter lets down (creeps off the river first), the pilot is put out and the seat freed; AFK gunners / crews / board users lose their seat | `afk`, `afk pilot` |
| 5 | high | Script reload in the tools: the new script never thought again and every pawn stayed as the old script left it (shrunk, frozen, on a seat camera) | `OnScriptReload`: tickets, clock, flag owners, each player's role / kit / spawn preference and the counters carry over; `sanitise()` puts any unknown pawn back on its feet | `scenario=reload` |
| 6 | medium | Team switch or spectate while dead left the player in his gun crew, as helicopter owner, with fire missions on the board | `leaveTeam()` from `buildRoster` for dead / spectating players as well as live ones | `scenario=churn` |
| 7 | medium | A slot changing hands kept the old player's HUD classes on the newcomer's screen | `hudReset` when a slot gets a new controller | `scenario=churn` |
| 8 | medium | Kill / assist credit went to a slot that had changed hands or sides since the shot (and could be a team kill) | `creditOf(slot, team)`; the crash killer, FO assist and crew hit counts check the side | `scenario=churn`, `shot down full` |
| 9 | medium | A gun hit again while disabled had its timer reset and the attacker re-credited; a repaired gun could be silenced on the spot | no stacking; 15 s `REPAIR_GRACE` after a repair | `at + counter-battery` (repair grace) |
| 10 | medium | Beehive fired a level cone: men coming up the slope below the gun were never hit | the cone points at the locked target | `beehive` |
| 11 | medium | Smoke stopped every round at 600 u whatever the smoke's distance (gunners behind smoke were safe at any range, near ones not at all) | the round stops where the line enters the smoke | `smoke` |
| 12 | medium | A helicopter abandoned in the field (pilot quit / changed role) stayed there all round | after `HELI.ABANDON` 45 s with no owner and nobody aboard it is fetched back to its pad | `pilot quits mid-air` |
| 13 | medium | The river surface counted as ground under the bed: a helicopter "landed" under water | the water is the floor; touching it is a ditching (destroyed) | flight envelope |
| 14 | medium | Leaving a crashing helicopter low and slow gave a safe fast-rope | no rope while crashing (you jump) | `shot down full` |
| 15 | medium | Deploying at a flag with enemies inside put reinforcements on top of the attackers (captures froze; no flag changed hands twice in the balance runs) | a flag is a deploy point only while no enemy is inside its circle; the briefing card says why | `spawn modes` |
| 16 | medium | `resetRound` did not clear `board`, `mount`, the deploy cover, AT timers, AFK or the per-round counters: a player could start a round "at the board" | cleared | `scenario=restart` |
| 17 | medium | A pawn could wait in the briefing room shrunk or frozen (seat state from a previous life) | the lobby restores scale and move type | `shot down full`, `scenario=churn` |
| 18 | low | Crash victims whose kill is refused (a server plugin, god mode) were left frozen in mid-air | survivors are put on the ground, unfrozen and re-armed | code review |
| 19 | low | Flag progress after a long hitch jumped by the whole gap | the flag tick's dt is capped at 1 s | code review |
| 20 | low | `loseTicket` with 0 / NaN / negative amounts; ticket underflow below 0 and a double round end | guarded; underflow clamps and ends the round once | `flags and tickets` |
| 21 | low | The pilot of a parked helicopter could be killed by spawn campers before reaching it, and a new helicopter shot on its pad at once | 3 s deploy cover for every deploy (ends with the first shot), 3 s guard on a new helicopter | `spawn modes`, flight envelope (pad guard) |
| 22 | low | `takeHeli` handed a human the first free helicopter even when an armed one stood on the pad | armed and parked first | default run |
| 23 | low | The 4-player AI hand-over toasted "free for you" even when the role then failed | toast only after the role is granted | `node test/mock.mjs 4 600` |
| 24 | low | Bots were sent HUD updates (and charged script time for it) | HUD calls skip bots | perf |

Not bugs, checked: every server command in `CONFIG.CVARS` and `bot_quota*` / `bot_kick` / `say` is on Valve's Workshop command allow list
(`scripts/workshop_cvar_whitelist.txt` read from pak01 with the `vpk` module, 556 names, 12 Nov 2026). Simultaneous E on one seat:
one player gets it (`two on one seat`). Contested capture: frozen; capture rate capped at 3 (`flags and tickets`). Helicopter destroyed
with every seat taken: everyone dies once, the killer gets every kill, the crew's tickets are paid, nobody comes back shrunk or frozen.

New in this pass (polish): gunner belt read-out and R to change belts (`mv_gun_ammo` only when `out/hud.json` lists it, else on
`mv_gun_name` in steps of 5); flag events as toasts (the `mv_feed_*` event feed when the HUD has it, see SCRIPT.md "HUD additions
(pass 1)"); deploy cover; pad guard; AFK; late join (HUD reset, briefing, counted); the per-minute `perf:` console line (ms avg / max,
HUD calls per tick, players, flying, rockets, shells, tickets, errors); shorter, plainer HUD and toast strings; the bot AT man fires
the launcher at helicopters (CS2's bot brain would only use the Zeus as a Zeus); bots carry the MG / AT kits within the limits.

## 2. Coverage

`node test/mock.mjs 32 600` plays the set pieces and prints this table; any line at 0 fails the run (12 Nov, final run):

| Feature | Times | Feature | Times |
|---|---|---|---|
| kit limit refusals | 1 | marksman kit | 1 |
| Beehive hits | 2 | smoke blocks gunners | 3 |
| smoke shells | 10 | AT rocket hits a helicopter | 1 |
| counter-battery: AT knocks a gun out | 1 | counter-battery: shell knocks a gun out | 1 |
| human gun repair | 1 | repair grace | 1 |
| fire missions at once | 4 | board: missions shown and cycled | 3 |
| flash marks | 2 | board: second flash marker | 1 |
| FO assist credit | 3 | kills by artillery | 4 |
| landing: soft | 14 | landing: hard (damage, bounce) | 1 |
| landing: crash (destroyed) | 1 | bounds: soft wall | 1 |
| bounds: ceiling | 68 | wreck lifetime | 1 |
| pad repair | 9 | pad re-arm (rocket pairs) | 17 |
| pad guard (new helicopter) | 1 | helicopter rockets kill | 1 |
| helicopter gun kills | 1 | emplaced gun kills | 1 |
| helicopter lost with riders (crash kills) | 24 | fast-rope (set piece) | 1 |
| !spawn at a held flag | 1 | spawn aboard a helicopter | 1 |
| deploy cover | 1 | late join | 1 |
| AFK seat release | 1 | AFK pilot let down and taken out | 1 |
| two E on one seat: one gets it | 1 | role change deferred to the next deploy | 1 |
| belt reload (manual) | 1 | belt changes | 43 |
| event feed lines | 85 | per-minute perf line | 9 |

The bug-class scenarios: `scenario=churn` (disconnects, slots changing hands, team switches, spectating, suicides from every seat,
including a pilot in the air, a rider, a crewman), `restart` (round ends while flying; CS2's restart and the script's own alternate),
`edge` (`shot down full`, `pilot quits mid-air`, `deaths in seats` = board / emplaced gun / round in hand, `flags and tickets` =
contested, capture cap, ticket underflow), `reload`. Invariants checked every 16 ticks in every run: no seat, crew, board, gun or
helicopter points at a player who is not there or is on the other side; no non-finite position, angle or health; no pawn left shrunk,
frozen or on a seat camera once out of a seat; HUD ids and classes only from the contract.

## 3. Balance (`test/sim_balance.mjs`)

**Method.** Each match is one full round of the real script with the real CONFIG on the mock engine, seeded. Helicopters (flight,
guns, rockets, AI pilots), artillery (AI crews and the test's human crews), emplaced guns, AT rockets, flags, tickets and every AI role
are the script's own code. The infantry fight is a **rate model** (CS2's bots and players can't run here): an infantryman with an enemy
within 1300 u kills him after about 9 s (faster close, the MG 35 % faster); with no man in reach he puts 0.8 rounds/s into a flying
enemy helicopter within 2000 u; a human AT man fires the launcher at a low helicopter or a man 400+ u away. Bots walk straight to the
nearest flag they don't hold. Two sets: **bots** (32 bots, the AI runs every vehicle) and **mixed** (22 humans driven by the test in
every role + 10 bots). Numbers that mostly reflect the model: rifle / MG shares, deaths per minute, bot-set geometry effects.
Noise: one standard error of a win rate over 40 seeds is about 8 points.

**Before / after**, 60 seeds per set. "Before" = the CONFIG at HEAD (DESIGN numbers) on the reviewed code (3 mixed seeds lost to a test
file edited during the run: 57). "After" = the CONFIG now.

| | bots before | bots after | mixed before | mixed after | target |
|---|---|---|---|---|---|
| round length median (p25-p75) | 8:03 (7:27-8:38) | 11:36 (11:02-12:58) | 8:36 (7:13-11:09) | **17:30** (15:35-18:51) | 12-20 min |
| T win rate (decided) | 62 % | 77 % | 26 % | **50 %** | 45-55 % |
| flag held T/CT a, b, c, d, e | 42/44 62/28 88/6 33/56 19/75 | 59/31 74/19 94/2 44/49 16/80 | 34/49 35/55 73/21 9/82 4/90 | 59/33 60/35 84/12 16/78 11/86 | no dead flag |
| dead flags | none | c (T holds it 94 %) | none | none | none |
| kills: rifle / mg (model) | 63 / 27 % | 60 / 26 % | 62 / 19 % | 63 / 17 % | each 3-40 % |
| kills: at / heli gun / heli rocket / artillery / mount | 1 / 2 / 5 / 1 / 1 % | 1 / 3 / 6 / 3 / 2 % | 3 / 3 / 10 / 2 / 1 % | 1 / 2 / 9 / 3 / 4 % | each 3-40 % |
| helicopter life median (p25-p75) | 27 s (19-73) | 63 s (28-122) | 51 s (18-103) | **113 s** (34-286) | 60-180 s |
| helicopters lost per round T : CT | 4.4 : 3.5 | 4.4 : 3.9 | 3.9 : 3.0 | 7.8 : 4.5 | |
| tickets lost to deaths T / CT, to bleed T / CT | 268/236, 78/119 | 363/355, 40/123 | 172/147, 198/78 | 313/289, 123/129 | |
| AI uptime pilot flying / gunner seated / crew at gun | 41 / 98 / 98 % | 50 / 99 / 98 % | n/a | n/a | ≥ 50 % |
| script ms/tick (mock, 10 matches in parallel) | | 0.06 avg | | 0.2 avg | |

Earlier in the pass (the first session's CONFIG, 40 seeds, before the stand-in AT men): bots T 75 %, 11:34; mixed T 33 %, 16:05.

**Experiments** (bots / mixed T win rate; 20 seeds unless marked):

| Change | Bots | Mixed | Kept? |
|---|---|---|---|
| Mi-8 health 170 / 160 | 80 % | 55 % (40 seeds: 45 %) | yes |
| Mi-8 health 200 / 180 | | 35 % (40 seeds) | no: noise, not a trend |
| Apache 12 rockets, 30 mm damage 22 | 65 % | 40 % | 24 damage instead |
| Mi-8 170 / 160 + Apache 12 rockets + 30 mm 24 | | 50 % (40 seeds), 50 % (60 seeds) | **adopted** |
| `NEUTRAL_FIRST` (flags go neutral first) | 90 % | 55 % | no |
| cyclic `ACCEL` 0.45 (DESIGN) | 50 % | 25 %; heli life 41 / 83 s, more losses | no |
| flag B moved 251 u south (`move.b=0,-251`) | 35 % (from 70 %) | | map question, below |

What moved the numbers: tickets 400 -> 500 and bleed 3 -> 6 s per flag (8-minute rounds became 16-18); helicopter health per model,
AT 60 -> 45 to a helicopter and rifle / MG hits on a helicopter 1.5 / 4 -> 1.2 / 3 (median life 51 -> 113 s); the Apache's 30 mm
(34 -> 24, 6 -> 2.5 to helicopters) and pods (28 -> 12) against the Mi-8s, which carry the riders and land at flags (T win 26 -> 50 %
in mixed); belts on every gun; tighter artillery spread and a larger HE radius (artillery 1-2 -> 3 % of kills); deploy points closed
while a flag is under attack (no dead flag in mixed).

**Still outside a target, and why:**
- **Bots-only T win rate 77 %.** Deaths are even (363 / 355); the bleed decides, and the bleed is decided by flag B: T holds it 74 % of
  the round. In the stand-in, bots walk in straight lines, and B (on the bridge, y 251) is about 300 u nearer the T base than the CT
  base; CT's base also sits on a 620-u plateau. Moving B 251 u south flipped the result to 35 %. This is geometry plus a crude walk
  model, not a script asymmetry: the real answer is CS2's nav-mesh travel time from each base to B. **For the map**: compare the two
  bases' walking time to B in game; if T is clearly nearer, move B (or its deploy points) toward the middle. Flag c is "dead" in bot
  matches for the same reason (CT bots never get past B). With humans in the mix every flag changes hands.
- **Rifle share 60 %+, AT / helicopter gun / mount 1-4 %.** The 3-40 % per-source band does not fit an infantry-first mode with a rate
  model doing the rifle fighting: rifle and MG together are about 80 % of kills in both sets (Battlefield-style games sit around
  60-70 % small arms). The AT rocket is the anti-helicopter weapon (helicopters lost to AT: the largest single source) with a 25 s
  reload, so few infantry kills; the gun seats' share follows how many players sit in them (one human gunner per team in the mixed
  set). Pushing vehicles to 20 %+ each would make infantry the prey. Recorded, not tuned; in-game kill feeds will tell.
- **Bots-only round length 11:36** (mixed 17:30 is in the band). The stand-in kills faster when every player is an infantry bot
  (1.9 deaths per player-minute against 1.1 in mixed); real CS2 bots on the real map are slower to find each other.

**Departures reconsidered** (also in SCRIPT.md): `ACCEL` 0.7 stays (0.45 halves helicopter life); flags flip straight to the capturer
(neutral-first entrenches whoever wins the race to B); occupants stay immune to pawn damage (the airframe takes the hits: a rider can't
be traced inside a moving prop, and the crash kills everyone aboard anyway).

## 4. Performance

`node --cpu-prof test/mock.mjs 64 300 humans=32` (32 humans in every role + 32 bots), idle PC:

| | avg ms/tick | p99 | max | over 8 ms |
|---|---|---|---|---|
| before (start of the second session) | 0.147 | 0.445 | 7.08 | 0 |
| after the HUD cache change | 0.094-0.108 | 0.28-0.35 | 6.1-7.4 | 0 |
| `node test/mock.mjs 64 600 humans=32` | 0.089 | 0.253 | 5.81 | 0 |
| `node test/mock.mjs 32 600` / `4 600` | 0.070 / 0.037 | 0.21 / 0.12 | 5.9 / 4.6 | 0 |

Hot spot: the HUD cache. A no-op `hClass` built a key string (`id + "#" + cls`) and hashed it about a thousand times a tick at 64
players (hClass + hText + hSwap were 23 % of all profile time, more than the rest of the script). Now one record per panel id with
plain properties per class / group: script self time 2071 -> 1443 ms over the run. The first session had already cut the status box
to every 16 ticks and dropped HUD calls for bots. The max (5.8-7.4 ms) is a single tick (round start / GC); p99.9 is under 1 ms.
The figures include the stand-in engine's trace and move calls; CS2's own cost per call is unknown, so the per-minute `perf:` line on a
real server is the number that counts (it also prints HUD calls per tick: 3.5-4.8 here).

## 5. What only the game can settle

- Everything in SCRIPT.md "Not yet tested in CS2": parked pawns under seat cameras, `OnBulletImpact` on the helicopter props,
  `TerminateRound` / `FireWinCondition`, `SetAnimation`, `OnGunFire` for the Zeus, `pawn.Reset()`.
- `OnScriptReload` in the tools: whether `before()` runs with the old module still able to read its state, and whether pawns really
  keep the old script's scale / move type (the sanitise path assumes they do).
- Whether CS2 bots parked in a seat or frozen at a gun stay put, and what their own brain does with the MG / AT kit (the script only
  fires the AT launcher for them, at helicopters).
- The AFK let-down over real terrain and water (the mock's ground is the layout height grid).
- T/CT fairness with real navigation (flag B, section 3), the infantry kill rate, rifle against vehicle shares, round length with
  people who hide, flank and talk.
- The deploy cover against real spawn camping (3 s, ends with the first shot), the pad guard (3 s).
- HUD cost per call on a server (`perf:` line), and how the belt read-out on `mv_gun_name` reads until `mv_gun_ammo` exists.

## Files

`src/00_config.js`, `10_util.js`, `20_players.js`, `30_heli.js`, `40_arty.js`, `50_mounted.js`, `60_conquest.js`, `70_hud.js`,
`85_ai.js`, `90_main.js`; `test/mock.mjs` (scenarios, set pieces, coverage table, invariants, `mode=balance`, `piece=`, `spawnflip.`),
`test/sim_balance.mjs` (new); `docs/SCRIPT.md` (CONFIG guide, departures, tests, status, HUD additions). The world generator, `out/`
and NOTES.md were not touched.
