# Hellmatch ZE: status

**COMPLETE (19 Nov 2026), awaiting skink52's first playtest.** Every tracker row is done and checked as far as it can be without
CS2 (simulated / compiled). Handoff: `map mg_hellescape`, `bot_quota 16`, then `TESTING_HELLESCAPE.md` (all four levels, classes,
boss takeover, round rules). Playtest findings start the next round of work (new tracker rows; tune CONFIG.ZE first).
Before uploading to the Workshop: put the item ID into `docs/WORKSHOP_DESCRIPTION.txt`; art is in `out/workshop/`.

Design, findings and the phased plan: `projects/hellmatch-cs2/docs/ZE_DESIGN.md` (19 Nov 2026). Read it before any work.
Hellmatch (`projects/hellmatch-cs2`, addon `mg_freedm`) is never modified. skink52 gave full autonomy on 19 Nov 2026 ("you have total
control - do the problem solving independently ... AAA quality, with the hellmatch graphics").

## Resume here
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
