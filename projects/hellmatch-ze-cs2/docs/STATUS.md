# Hellmatch ZE: status

Design, findings and the phased plan: `projects/hellmatch-cs2/docs/ZE_DESIGN.md` (19 Nov 2026). Read it before any work.
Hellmatch (`projects/hellmatch-cs2`, addon `mg_freedm`) is never modified. skink52 gave full autonomy on 19 Nov 2026 ("you have total
control - do the problem solving independently ... AAA quality, with the hellmatch graphics").

## Resume here
19 Nov 2026: both workstreams finished (see their progress files); addon deployed into mg_hellescape (content + game) with
`python tools/deploy.py`; map compile via build_maps.ps1 (log build/compile_wrap.log). After the compile: restore
`C:\source1\cs2port\existing_ports.txt` from build/existing_ports.before_compile.txt if build_maps.ps1 added an mg_hellescape line,
check the vpk in the game addon, then hand over TESTING_HELLESCAPE.md to skink52 for the first in-game test.
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
| 1.10 | Assemble addon, copy compiled Hellmatch assets, compile map (resourcecompiler), deliver, test checklist | coordinator | deployed 19 Nov (tools/deploy.py, manifest build/deploy/); map compile running |
