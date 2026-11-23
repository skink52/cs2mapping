# Ideas taken from CS2-Porter and Hammer5Tools (Nov 2026)

Tracker for the round started 23 Nov 2026: every idea from the review of
[bcanusar/CS2-Porter](https://github.com/bcanusar/CS2-Porter) (MIT) and [dertwist/Hammer5Tools](https://github.com/dertwist/Hammer5Tools) (MIT)
that skink52 asked to add. [sarim-hk/cs2-map-importer](https://github.com/sarim-hk/cs2-map-importer) had nothing new.
The repos are read through the GitHub API (`gh api repos/<owner>/<repo>/contents/<path>`), never cloned or saved locally.
Code adapted from them says so in its header (`from CS2-Porter <module>.py, MIT, copyright bcanusar`), like the cs2-slop-porting borrowings.

Status words: `todo`, `doing`, `done` (with how far it was checked, in the words of [compatibility.md](../reference/compatibility.md)),
`skipped` (with the reason). Nothing here is in-game verified until skink52 plays a map with it.

Each batch keeps its own progress file next to this one (`borrowed-2026-11/<batch>.progress.md`), updated after every item, so a reset
loses at most one item. Shared files (`tools/stage_c.py`, `tools/run_pass.py`, `docs/porting/pipeline.md`, `tools/README.md`,
`CAPABILITIES.md`, `CHANGELOG.md`, `docs/reference/external-tools.md`) are edited only by the integrating session, from the snippets each
progress file proposes.

**Rule from 14 Nov 2026 ([compile-warning-not-proof]):** a fix that changes many maps (thickening triggers, moving spawns) ships as a
report or an opt-in step until a map skink52 has played shows the problem.

## Batch A: lighting and materials (agent)

| # | Item | Where | Status |
|---|---|---|---|
| A1 | Texture lights: `lights.rad` surfaces (BSP texinfo SURF_LIGHT + worldlights lumps) → self-illum on their CS2 materials, rect lights where the material can't glow | new `tools/texlights.py` | done: `texlights` (opt-in); unit tested, glow vmat compiled; real data only on mg_jahoukarail_2015, ba_jail_ds_arctic_summer_v1 |
| A2 | Light brightness calibrated against Source 1 falloff with BSP line traces (CS2-Porter `lighting.py`); compare with ours, adopt what is better | `tools/lighting.py` | done: `lightcal` (report) / `lightcal_apply`; relight unchanged; found fifty-percent lights ~8x too bright (TO CHECK note); unit tested + report runs on 3 maps |
| A3 | Fully-bright maps (no lightmaps / all black) detected; kept fully bright, sun added for players and weapons | `tools/lighting.py` / `tools/daylight.py` | done: `fullbright` (opt-in, stage C reports); unit tested only (no fully-bright map on the PC) |
| A4 | `color_correction` → `.vpost` Curves + Saturation layers (check CS2-Porter's claim that the LUT layer can't be filled from a file; fix gotcha row if so); underwater `.vpost` per water fog colour | new `tools/postfx.py`, `docs/reference/cs2-gotchas.md` | done: `colorcorrect`, `underwaterfog` (opt-in); inline LUT compiled and decoded, exact within 1/255; gotcha row corrected |
| A5 | Materials the map didn't pack recovered from the compiler's copies in the BSP (`maps/<map>/name_x_y_z`, `_wvt_patch`) | `tools/assets.py` / `prep.py` | done: `assets` reads vbsp copies; unit tested + pakfile scan (2 recoverable materials across 57 BSPs) |
| A6 | Importer 8192-wide texture scale for materials missing at import time: check `facescale` catches it, extend if not | `tools/texfix.py` | done: `facescale` fixes 8192-wide scales the VMF missed; unit tested + real geometry copy (pokemon: 154 more faces) |

## Batch B: map fixes and effects (agent)

| # | Item | Where | Status |
|---|---|---|---|
| B1 | Blend (WorldVertexTransition) displacements: VMF alphas → `VertexPaintBlendParams` on the imported faces | new `tools/blendpaint.py` | done: `disprestore` keeps paint, `blendpaint` (D); unit tested + real copies; two-layer vmat rebuild moved to D1 |
| B2 | Thin boost / gravity triggers: report (opt-in thicken) | `tools/repair.py` | done: `thintrig` report (default), `thintrigfix` opt-in; unit tested (arcs: 33 of 52 boosts 1-4 u) |
| B3 | Spawns stuck in the floor: lift (mapsanity already reports) | `tools/mapsanity.py` / `tools/repair.py` | done: `spawnlift` report (default), `spawnliftfix` opt-in; unit tested (island17: 22 of 23 lifted on a copy) |
| B4 | Entity names like `1.01` kept as exact text through the importer | check importer output; `tools/repair.py` | done: `numnames` (runs with `io`); unit tested + antique copy (9 values, train output restored) |
| B5 | `env_smokestack` (and other effects CS2-Porter templates: smoke volume, dust motes, spotlight, embers) where we have nothing | new `tools/smokestack.py` or `tools/steam.py` | done: `smoke` (default); unit tested, 68 generated vpcf parse, none compiled; beam_spotlight moved to D2 |
| B6 | 3D skybox room found from BSP areas / area portals; compare with `skysplit.py` | `tools/skysplit.py` | done: `skysplit --bsp / --room` (option); same room as the auto box on 4 maps |
| B7 | Momentum Mod triggers (teleport, speed threshold, slide, push) → script, for bhop/surf ports | new `tools/momentum.py` | done: `momentum` (default; acts only on Momentum triggers); simulated only |
| B8 | Evaluate: fake Source 1 game folder (`s1stub.py`) and the Python MDL decompiler (`mdl.py`) against how prep / import / cs_mdl_import work now; adopt or write down why not | report in the progress file | skipped: evaluated, removes no logged failure; smaller proposals moved to D3 |

## Batch C: Hammer5Tools (integrating session)

| # | Item | Where | Status |
|---|---|---|---|
| C1 | Batch compile through resourcecompiler `-filelist` | `tools/rcompile.py` | done: `asset` takes globs and `--list`, 2+ inputs go as one `-filelist` run; unit tested, compiled (2 test vmats in scratch addon `zz_borrowed_test`) |
| C2 | SmartProp: `.vsmart` read/lint + authoring notes (element and modifier vocabulary, the linear-kit shape) | `create/`, `docs/creation/` | done: `create/vsmart.py` (tree, lint), `docs/creation/smartprops.md`; unit tested, no SmartProp compiled yet |
| C3 | Radar from the compiled nav mesh, as an option beside the floor-based radar | `tools/radar.py` or new tool | done: `tools/navradar.py` (CLI option); unit tested, all 91 PC navs parse; better on mg_trenchwarfare, worse on mg_nanite_temple |
| C4 | Guards from its test list: `vpk.signatures`, error-material remap, tool-material fallback — check ours, add what's missing | `scripts/`, `tools/` | done, nothing to add: `vpk.signatures` renamed and restored by `run_import.bat` / `run_fixrefs.bat` (a killed run leaves `.aaa` until the next run restores it); no imported `.vmat` on `error.vfx` in any of the 92 content addons (23 Nov); tool-material fallback not checked separately |
| C5 | Credit and summary rows | `docs/reference/external-tools.md`, `CAPABILITIES.md`, `CHANGELOG.md` | done |

## Batch D: follow-ons (agent)

| # | Item | Where | Status |
|---|---|---|---|
| D1 | Two-layer WorldVertexTransition vmats in `assets` | `tools/assets.py` | done (D.progress.md) |
| D2 | beam_spotlight → spotlight cone (+ func_rotating) | `tools/spotbeam.py` | done (D.progress.md) |
| D3 | cs_mdl_import error line kept in the report; stock remap for chicken / hostage / agent models | `scripts/post_import_cleanup.py`, `tools/stockmodels.py` | done (D.progress.md) |

## Integration

| Step | Status |
|---|---|
| Register new steps in `stage_c.py` / `run_pass.py`; pipeline.md and tools/README.md rows | done 24 Nov |
| `python ci/check_repo.py`, `check_links.py`, `unittest discover -s tools/tests` (311) and `-s autoport/tests` (91), api check | done 24 Nov, all pass |
| Copy changed tools to `C:\source1\cs2port\tools`, check sizes | done 24 Nov, byte for byte |
| Commit (no push without asking) | done 24 Nov, not pushed |
