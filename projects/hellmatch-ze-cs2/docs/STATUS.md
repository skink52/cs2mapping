# Hellmatch ZE: status

**COMPLETE (19 Nov 2026), awaiting skink52's first playtest.** Every tracker row is done and checked as far as it can be without
CS2 (simulated / compiled). Handoff: `map mg_hellescape`, `bot_quota 16`, then `TESTING_HELLESCAPE.md` (all four levels, classes,
boss takeover, round rules). Playtest findings start the next round of work (new tracker rows; tune CONFIG.ZE first).
Before uploading to the Workshop: put the item ID into `docs/WORKSHOP_DESCRIPTION.txt`; art is in `out/workshop/`.

Design, findings and the phased plan: `projects/hellmatch-cs2/docs/ZE_DESIGN.md` (19 Nov 2026). Read it before any work.
Hellmatch (`projects/hellmatch-cs2`, addon `mg_freedm`) is never modified. skink52 gave full autonomy on 19 Nov 2026 ("you have total
control - do the problem solving independently ... AAA quality, with the hellmatch graphics").

## Resume here
**Round 4 done 21 Nov 2026 (simulated, deployed, compiled): floating lost soul, connected zombie respawns + door use, softer damage
tint, no zombie-zombie collision, escape finale in DM03. Awaiting skink52's playtest (`TESTING_HELLESCAPE.md` Round 4 section);
the horde is stronger now (tune CONFIG.ZE AI_DAMAGE / AI_PER_HUMAN first).**
**Phase 2-4 built 19 Nov 2026 (afternoon): 4 levels (MAP01, E1M1, E3M1, MAP06), class choice, balance pass, player boss
takeover, loading screens, Workshop art/description (`out/workshop/`, `docs/WORKSHOP_*`). Simulated only; not yet run in CS2.**
Open after the playtest: E1M1 stage 2 (bots rarely climb the lift to the flooded hall even with the lift made perpetual; humans can
ride it); E3M1 escape run long for bots; bot rounds run 2-3 min (humans should last longer: tune CONFIG.ZE after the test);
2v2 / 4v4 arenas reach the boss about half the time; Workshop description needs the real item ID; level music renders unheard.
Earlier: **v1 (Phase 1) built, deployed and compiled (19 Nov 2026 morning).** skink52 tests with `TESTING_HELLESCAPE.md`
(`map mg_hellescape`, `bot_quota 16`). Any findings from that test go first, ahead of the Phase 2 rows below.
After a map build, build_maps.ps1 adds `mg_hellescape [in progress, built] [skink]` to `C:\source1\cs2port\existing_ports.txt`: back the
file up before and restore it after (it is a port list; this is not a port).
Rebuild: `PYTHON=python sh tools/build_all.sh` (~1 min with music cached; under the watchdog), then `python tools/deploy.py`.
Workstreams (disjoint files, each with its own progress file):
- **Pipeline** (owns `tools/`, `ze/`, `music/`, `ref/`, `preview/`, `out/`, `build/`): `docs/progress_pipeline.md`
- **Game** (owns `src/`, `test/`): `docs/progress_game.md`
Coordinator (STATUS.md, README, root docs, deploys, map compile) is the main session or the scheduled task `hellmatch-ze-resume`.
Read both progress files; continue the first unfinished row of each.

## Gates
- Freedoom checkout: **approved and done** 19 Nov 2026: `C:\source1\freedoom` (depth 1, 50.7 MB). All 68 Phase 1/2 WADs have built nodes.
- Access granted 19 Nov 2026: content `...\content\csgo_addons\mg_hellescape`, game `...\game\csgo_addons\mg_hellescape` (both created), `C:\source2`.
  cs2.exe was not running. Before any deploy check `Get-Process cs2` and never write into an addon open in `cs2 -tools`.
- Push: never without asking. In-game playtest: skink52.

## Round 4: playtest findings (queued 20 Nov 2026; skink52's own test; do when usage resets, 21 Nov 13:30)
Done 21 Nov 2026 (scheduled run): 29/29 mock scenarios incl. float/respawn/collide and finale escape/fight/clock/none; boss_check 6/6; perf 64 players avg 1.5-1.8 ms, p99 4.8-6.8 (was 1.31 / 3.48); api/tsc clean; final build deployed + compiled (0 failed, 1.1 min), existing_ports.txt restored. Finale arena FreeDM DM03 (`dm03f`). Order was: game = src/test, pipeline = tools/ze; rebuild, mock scenarios, deploy, compile, commit locally.
| Step | What | Owner | State |
|---|---|---|---|
| 4.1 | Lost soul zombie player body doesn't float: the player-driven SKUL must hover like the monster (MF_FLOAT/NOGRAVITY height, bob), view height to match | game | done 21 Nov (simulated) |
| 4.2 | Zombies can respawn somewhere cut off from the live humans (seen on MAP06 Janus Terminal, maybe behind a press-E door that didn't open): zombie spawn spots only in sectors connected to the humans' current area by the current open/blocked state (reuse the progress map), and zombie players get door use (or doors in their way open) | game (+ pipeline if a map06 sidecar block/door is wrong) | done 21 Nov (simulated) |
| 4.3 | Damage red screen overlay too intense: tone it down (lower max alpha / shorter fade; maybe CONFIG value), keep the pickup/berserk tints | game (src/cs2/30_hud.js + CSS via tools/hud.py) | done 21 Nov (simulated) |
| 4.4 | Zombie players have no collision with each other (and with AI zombies) so packs don't jam; still solid to humans and walls; keep shootable | game | done 21 Nov (simulated) |
| 4.5 | Escape finale: a side that escapes is teleported to a small deathmatch arena (new compact arena; pick a FreeDM-style small level or a closed room of an existing map; placed once, inside world bounds) with "T'S ESCAPED - BUT WILL THE CTS BE HOT ON THEIR TRAIL?"; if the other side escapes too, they join: "CTS TRACKED DOWN THE REMAINING TS - FIGHT TO BE THE FINAL SURVIVORS"; last side standing wins the CS2 round (if the other side is wiped instead, the escaped side wins as now). Kills are real CS2 kills; stats: ze_escapes as now + `ze_finale_wins`. Update SERVER_STATS_NOTE.md, TESTING, README, Workshop text | game + pipeline | done 21 Nov (simulated) |

Round 4 contract (21 Nov 2026, coordinator; change only by editing here first):
- **Finale level record** (pipeline): `out/addon/_gen/levels.json` gets exactly one extra record with `finale: true`, `side: "f"`,
  id `<base>f` (e.g. `dm07f`), `base`, `title`, `author`, its own `off` (placed once, inside +-16000, clear of the 12 ZE placements
  and the lobby/booth/cache keep-out), own mover/anim names `fdm_<id>_...`, all THINGS kept with WAD index, and **no `ze` field**.
  The level is small (fits 2-16 players), one connected walkable area with no key doors, and has at least 8 deathmatch starts
  (thing type 11) all reachable from each other; weapons/ammo/health pickups stay. Its geometry goes into the vmap and copy plan
  like the other levels. A build without it (fixtures, `HZE_LEVELS` lists) must still work.
- **Finale rules** (game): the game finds the record by `finale: true` and builds it as a third arena (no AI horde, no stages; the
  level's monsters removed, its items kept). Side A escapes -> its live humans are moved there (spawn at type-11 starts, then 1-4),
  keep weapons/ammo/health, centre "T'S ESCAPED - BUT WILL THE CTS BE HOT ON THEIR TRAIL?" (CT form "CT'S ESCAPED - BUT WILL THE TS
  BE HOT ON THEIR TRAIL?") to everyone; `ze_escapes` as now. Side B wiped -> A wins (as now). Side B escapes -> moved in too, centre
  "CTS TRACKED DOWN THE REMAINING TS - FIGHT TO BE THE FINAL SURVIVORS" (or the T form); T vs CT damage on, same-side off; a finale
  death is final for the round (spectate, no zombie). Last side standing wins the CS2 round; `ze_finale_wins` to every human on the
  winning side who reached the finale (alive or not), humans only, not warmup. Clock end during the finale: more live humans wins,
  tie -> the side that escaped first. No finale record -> escape wins as before. New fixed HUD strings in `src/core/zz_hud_strings.json`.

## Round 3 (19 Nov 2026, skink52: "weapons run out of ammo", "not enough enemies to feel like a horde, scale with playercount",
## "any larger maps?", "server stat-tracking for the interesting stats")
Contract for this round (game = src/test, pipeline = tools/ze/docs):
- **Ammo and upgrades** (game, defaults in CONFIG.ZE; sidecar actions override per stage):
  - AI zombie deaths drop ammo: `DROP_CHANCE` 0.35, the type weighted by what live humans in that arena carry (clips / shells
    mostly, rockets / cells rarer), Doom dropped items (no respawn), removed after `DROP_SECONDS` 30 if not picked up.
  - Sidecar action `{"resupply": {"ammo": 0.5, "health": 25, "armor": 0}}`: every live human gets that share of max ammo for each
    ammo type they can use, plus health / armour up to 100. A completed hold with no `resupply` action gets `HOLD_RESUPPLY`
    (same shape, default ammo 0.5, health 25).
  - Sidecar action `{"give": ["chaingun", "ssg"]}`: every live human gets these weapons (with a start load of ammo), HUD
    "UPGRADE: CHAINGUN". A sidecar with no `give` anywhere gets the default ladder: stage 1 done -> ssg + chaingun, stage 2 done ->
    rocket, boss stage start -> plasma (`UPGRADE_LADDER`). Weapon ids: pistol shotgun ssg chaingun rocket plasma bfg chainsaw.
  - `AMMO_FLOOR`: a human's bullets refill 1 per second while below 50, so nobody is ever left with fists only.
- **Horde scaling** (game): per-arena cap = clamp(`CAP_BASE` 24 + `CAP_PER_PLAYER` 4 x players placed in that arena at round
  start, `CAP_MIN` 32, `CAP_MAX` 96); a sidecar `zombies.cap` is now a maximum. AI wanted = `AI_BASE` 8 + `AI_PER_HUMAN` 5 x live
  humans, counting awake AI only (under the cap less zombie players); the level's own sleeping monsters take at most 30% of the cap;
  `AI_DAMAGE` 0.5. All six sidecars set `zombies.cap` 96 (a maximum), so the formula decides. Sidecar action `{"surge": {"group": "<spawn group>", "count": "auto"}}` and an
  automatic surge at every hold start, boss start and escape start: 6 + 3 x live humans from the stage's spawn groups, HUD
  "HERE THEY COME". Budget: mock at 64 players avg < 3 ms, p99 < 8 ms; far AI (no human within 2000 units) think every 4th tic.
- **Server stats** (game; names fixed, plugin note `docs/SERVER_STATS_NOTE.md`): `ze_escapes`, `ze_survivor_wins`, `ze_holds`,
  `ze_infections`, `ze_zombie_kills`, `ze_boss_takeovers`, `ze_boss_player_kills`, `best_ze_stage` (n = stage number), plus the
  existing `pve_kills`, `boss_kills`. Sent through `echo mgstat <slot> <stat> [n]`, humans only (no bots), not in warmup.
- **Larger maps** (pipeline): two larger, mostly linear maps with 5-6 stages, rounds ~8-10 min, placed twice and inside +-16000 with
  the four existing levels; `resupply` / `give` / `surge` actions added to every sidecar (validator `tools/ze_sidecar.py` and
  `tools/zereach.py` accept them).

## Contract between the workstreams (change only by editing here first)
- Sidecar `lower_lift` options: `stay` (lowers for good), `perpetual` (Doom's perpetual platform: keeps cycling; used by E1M1's
  lift 103 so nobody needs its switch), `speed` "fast".
- Addon folder / map: `mg_hellescape` (`tools/names.py`: NAME "Hellmatch ZE", MAP "mg_hellescape"). Script file `maps/scripts/hellescape.js`.
- Entity names, model and material paths, sound events keep Hellmatch's `fdm_` / `models/fdm/...` / `fdm.*` names, so the compiled
  sprite, HUD and sound files can be copied from the Hellmatch game addon without recompiling (decision 19 Nov: replaces the `hze_` idea).
- Level records (`out/addon/_gen/levels.json`): each ZE level is converted once and **placed twice**: ids `<map>t` (T arena) and
  `<map>c` (CT arena), e.g. `e1m1t`, `e1m1c`, each with its own `off` and its own mover/anim entity names (`fdm_e1m1t_f12`), sharing the
  model files. Extra fields: `base` ("e1m1"), `side` ("t"|"c"), `ze` (the validated sidecar object, below), `title`, `author`.
- Sidecar: `ze/<map>.json`, format in ZE_DESIGN.md section 3; indices are WAD indices; the converter validates and embeds it as `L.ze`.
  The level record keeps ALL things (monsters, keys, players starts 1-4) with their WAD index so the game side can apply the sidecar.
- Zombie first-person view frames (HUD `WSpr` classes `w_<spr>_<frame>`), drawn by the pipeline in the Doom palette from the
  creatures' own art, 4x scale like the weapons:
  `ZIMP` A-D imp claw (A idle, B wind-up, C swipe, D follow-through); `ZIMF` A-C imp fireball (A cupped hands, B bright fireball, C release);
  `ZDMN` A-D demon (A idle jaws, B open, C bite, D lunge/charge); `ZSKL` A-C lost soul (A idle, B flare, C dash). The game side uses
  exactly these sprite names/frames in its psprite states.
- HUD text: new fixed strings the game side shows (stage names come from sidecars) are added to `build/hud_strings.json` by the
  build; game side lists any new fixed strings in `src/core/zz_hud_strings.json` (array of strings), the build merges it.
- Music (pipeline, 19 Nov 2026, row 2.4): `_gen/music.json` boss-pool tracks carry `level` = the ZE level ids they belong to,
  comma-separated (`e1m8` -> "e1m1", `e2m8` -> "map01,map06", `e3m8` -> "e3m1"). Requested from the game side (optional):
  `musicBoss` prefers boss tracks whose `level` list holds the round's level, else the whole boss pool (today it shuffles the
  whole pool, which also works).
- cs_script: the current API only (`Entities.*`, `ent.FireInput`, `Console.Log`, `GameRules.*`); `create/test/api.py --strict --check`
  and `sh create/test/tscheck.sh` clean on the built `hellescape.js`.

## Coordinator notes
- Map compile without Hammer: `powershell -NoProfile -ExecutionPolicy Bypass -File C:\source1\cs2port\build_maps.ps1 mg_hellescape`
  (stage D builder: addon assets, then resourcecompiler with Hammer's full-build arguments). Check first whether it writes to
  `existing_ports.txt` for a non-port addon and keep that file clean. Hellmatch's full build with vis took 30+ minutes: run under the
  watchdog with `--expect 2400 --max 7200`, CS2 closed or not in tools mode on this addon.
- Workstreams launched 19 Nov 2026 as two background agents of the main session (pipeline, game).

## Tracker (coarse; detail in the progress files)
| Step | What | Owner | State |
|---|---|---|---|
| 0.1 | Copy hellmatch src/test/tools/music into this project | coordinator | done 19 Nov |
| 0.2 | Current cs_script API, checks clean | game | done 19 Nov (simulated) |
| 0.3 | Mock run of the copy unchanged in behaviour | game | done 19 Nov (simulated) |
| 1.1 | Converter: Phase 1/2 names, two placements, all things kept, sidecar loader + validator | pipeline | done 19 Nov (simulated) |
| 1.2 | Pick + convert one short linear map; author its sidecar; preview render | pipeline | done 19 Nov (simulated) |
| 1.3 | ZeRound + ZeDirector: two arenas, swap on death, win rules, stage engine, AI horde, cap 48 | game | done 19 Nov (simulated) |
| 1.4 | Zombie classes imp + demon (+ lost soul if time), view states, monsters ignore zombie players | game | done 19 Nov (simulated) |
| 1.5 | Scripted boss stage | game | done 19 Nov (simulated) |
| 1.6 | Bots: human stage-following, zombie chase | game | done 19 Nov (simulated) |
| 1.7 | HUD lines + renderer distance cull | game | done 19 Nov (simulated) |
| 1.8 | Zombie view art, HUD art, loading screens, music, vmap with lobby/booth/cache | pipeline | done 19 Nov (simulated) |
| 1.9 | Tests: sim + mock scenarios + perf at 32/64 | game | done 19 Nov (simulated) |
| 1.10 | Assemble addon, copy compiled Hellmatch assets, compile map (resourcecompiler), deliver, test checklist | coordinator | done 19 Nov: deployed (tools/deploy.py, manifest build/deploy/), compiled with build_maps.ps1 in 1.7 min, 0 failed, vpk 2.4 MB, all new assets compiled; existing_ports.txt restored |
| 2.1 | Class choice on respawn (keys while dead) + class HUD; lost soul polish | game | done 19 Nov (simulated) |
| 2.2 | 3-5 more maps with sidecars (candidates from the 19 Nov survey: E1M1, E2M1, E3M1, MAP02, MAP06; fit two placements each, check world bounds) + map rotation/vote | pipeline+game | done 19 Nov (simulated) |
| 2.3 | Knockback/balance tuning per class from sim runs; zombie "rage" pickup at stage starts | game | done 19 Nov (simulated) |
| 2.4 | Hear-check alternative for level music: if the OPL render is doubtful, keep Hellmatch tracks only (no new downloads without skink52) | pipeline | done 19 Nov (simulated) |
| 3.1 | Player boss takeover (Use at the boss spawn or most human kills); AI resumes on death/leave | game | done 19 Nov (simulated) |
| 4.1 | Loading screens per map, Workshop art + description (Freedoom licence text), WORKSHOP_CHANGELOG, mgstat hooks | pipeline | done 19 Nov (simulated) |
| 4.2 | Rebuild, deploy, compile, update TESTING_HELLESCAPE.md; then COMPLETE (awaiting skink52's playtest) | coordinator | done 19 Nov: deployed + compiled (0 failed, vpk 2.5 MB, all 4 levels), tracker restored |
