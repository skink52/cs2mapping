# Prompt: remaster mg_trenchwarfare to the mg_monsoon standard

Paste everything below the line into a new Claude Code session started in `C:\source1` (model: Opus).

---

Work out of cs2mapping; we're remastering mg_trenchwarfare (`projects/trenchwarfare-cs2/`) to the standard its sibling mg_monsoon
(`projects/monsoon-cs2/`) was built to in Nov 2026. Same game, same roles (infantry, mortar crews, biplane pilots), same WW1 Western Front
identity: this is a quality and robustness remaster, not a redesign. The bar: AAA detail, no world or clipping errors, fun, reviewed several times.

**Start (research first, cheaply):**
1. `git pull`, then `python create/context.py trenchwarfare-cs2` and `python create/context.py monsoon-cs2`.
2. Read `projects/trenchwarfare-cs2/NOTES.md` (its whole history: user edits, delivery zips, known open issues) and `README.md`.
3. Read how monsoon was done, as the standard to copy: `projects/monsoon-cs2/NOTES.md` "Resume here" and the agent reports, `docs/CONTRACT.md`,
   `docs/SCRIPT.md`, `docs/REVIEW_WORLD_1.md`, `docs/REVIEW_SCRIPT_1.md`, `docs/BUILD.md`, `docs/BUILD_LOG_1.md`, `docs/ASSETS.md`, `docs/IMAGE_TERRAIN.md`.
4. Write `projects/trenchwarfare-cs2/docs/REMASTER_PLAN.md`: a gap list (monsoon standard vs trenchwarfare today) and the ordered plan below adapted to it.
   Show me the plan's top section before big work starts, then continue without waiting.

**Hard constraints:**
- **The user has edited mg_trenchwarfare in Hammer.** Their latest `.vmap` in `content\csgo_addons\mg_trenchwarfare\maps\` is the source of truth.
  Back it up first (`docs/reference/file-safety.md`). Never regenerate over it blindly: either keep edits with `vmapgen.EditKeeper`
  (previous generated map vs their save) or apply delta patches (`create/patch_vmap.py` style). NOTES.md explains why full regenerations
  reshuffled their edits (rng cascade) and how deliveries were applied (numbered zips, `unpack_mg_trenchwarfare.bat`, applied list).
- Never deploy into an addon a running `cs2.exe -tools` has open. Copy only changed files.
- Long commands (> 2 min) under `C:\source1\cs2port\autoport\watchdog.py` with `--expect` and `--heartbeat`; never point `--log` at the build's own log.
  Never run resourcecompiler or `build_maps.ps1` with `C:\source1` as the working directory.
- **Usage:** at most two agents at a time, Opus. Finish a task, integrate it, commit, then start the next. Keep your own context small:
  delegate heavy reading and building to agents with complete briefs (each agent knows only its brief). Give each agent its own files so
  two never edit the same file.
- cs_script: look every call up with `python create/test/api.py <word>`; current API only (`Entities.*`, `Console.*`, `GameRules.*`); a script is
  finished only when `api.py --strict --check` and `create/test/tscheck.sh` pass, then the mock. Say "simulated", never "works in game".
- Shared tools are libsync copies (`create/libsync.json`): fix in `create/` (or `pull`), then `push`; `python create/libsync.py check` before committing.
  Commit with `[trenchwarfare]` prefixes; do not push without asking.

**What to bring over from monsoon (adapt each to WW1):**
1. **Contract doc** (`docs/CONTRACT.md`): every entity name, model, sound event and HUD id the map, script, HUD and tests share.
2. **Script hardening**, as `REVIEW_SCRIPT_1.md` did: split the 1300-line script into modules joined by a build step; move to the current
   API; one mock scenario per bug class (rounds, disconnects, team switch, seat/crew state, reload); a feature-coverage table that fails on
   0; `sim_balance.mjs` over many seeds (round length, kills by source, both sides 45-55%); perf at 64 players. Known open issues from NOTES:
   radar alignment, mortar crew death on firing, mortar assist credit, giant first-person weapons history.
3. **Bot AI for low population** (a hard requirement): bots useful as infantry with deploy targets and a leash, and script-driven bot
   pilots and mortar crews when a team has few humans, always yielding a role to a human. Keep the nav cheap: NONAV markup over unwalkable
   ground (the 44k-area nav caused the FPS drops that made trenchwarfare turn bots off).
4. **World review with programmatic checks**: port `projects/monsoon-cs2/tools/check_world.py` and `check_play.py` (walkability flood-fill,
   stuck pockets, spawn sightlines, cover counts, clipping, water edges, terrain gaps, nav markup, every entity model exists, every
   prop_dynamic has a dynamic archetype). Fix everything they find, plus zoomed `tools/vmap_preview.py` renders of every area, looked at.
5. **Better assets**: GMod Workshop models through `projects/monsoon-cs2/tools/gmod_assets.py` (make a neutral `create/` copy first; WW1 packs:
   biplanes, tanks, artillery, trench props, soldiers); compare with the procedural props and keep the better. Record rip risk per pack
   (`docs/ASSETS.md`, `docs/WORKSHOP_COMPLIANCE.md`). Review every prop turntable; rebuild weak ones.
6. **Terrain and geometry**: `create/terrain_img.py` erosion/detail with protected masks (trenches, pits, spawns stay exact);
   `create/primitives.py`, `meshedit.py`, `fxkit.py` (cheap local weather, no fog particles), `gen_light.py`.
7. **Presentation**: HUD built from the script's HUD contract and gated by `create/hud_check.py`; synthesised sounds with loop checks; radar,
   board/sight pictures, loading slides, skybox regenerated from layout.
8. **Delivery**: a deploy tool like `projects/monsoon-cs2/tools/deploy_monsoon.py` (dry run by default, changed files only, keeps a Hammer-edited
   vmap), `docs/BUILD.md`, an asset compile then a map compile under the watchdog, triaged in `docs/BUILD_LOG_1.md` (read the log, not the
   wrapper's summary), and README / TESTING / CREDITS / WORKSHOP docs from `docs/creation/templates/`.

**Finish:** keep `NOTES.md` "Resume here" current after every step, commit each finished step, and end with an in-game TESTING checklist
for the user covering everything only CS2 can confirm.
