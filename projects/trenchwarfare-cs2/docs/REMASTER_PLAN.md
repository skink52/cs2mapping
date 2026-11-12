# mg_trenchwarfare remaster plan (to the mg_monsoon standard)

Started 12 Nov 2026. Goal and rules: [REMASTER_PROMPT.md](REMASTER_PROMPT.md). Evidence: [research/TW_STATE.md](research/TW_STATE.md)
(trenchwarfare today), [research/MONSOON_STANDARD.md](research/MONSOON_STANDARD.md) (what monsoon did, how generic each piece is).
Same game, same roles (infantry, mortar crews, biplane pilots), same WW1 Western Front identity: quality and robustness, not a redesign.

## Top section: decisions and order

**Source of truth.** The user's `content\csgo_addons\mg_trenchwarfare\maps\mg_trenchwarfare.vmap` (29 Oct, byte-identical to delivery tw34,
not saved in Hammer since). Backed up 12 Nov to `mg_trenchwarfare\backups\remaster_20261112\` (hash checked), with the 3D skybox map.

**How the map is changed: delta patches only, never a regeneration.** There is no exact generated baseline for `vmapgen.EditKeeper`
(the generated vmaps were lost with `out/` on 27 Oct), `make_map.py` draws from one global rng, and user edits to generated objects carry
no tag. So every map change is a `patch_vmap.py`-style patch that names its targets (by id, name or class+position), and a new
`tools/patch_guard.py` diffs the digest before/after: everything not targeted must come out identical. User systems that must survive:
the random-explosion setup (timer, case, 13 env_explosions), skirmish ladders and their ladder volumes, the two area blockers,
`skybox_reference`, the `tw_user` visgroup and the 45 ungrouped objects.

**Order** (at most two Opus agents at once, each owning its own files; integrate, commit `[trenchwarfare]`, then the next):

| # | Step | Owner files | Done when |
|---|---|---|---|
| 1 | Restage lost `out/` from the current vmap + addon (`tools/restage_out.py`); revive the mock (Windows paths); `docs/CONTRACT.md` from digest + script + HUD | `tools/restage_out.py`, `test/`, `docs/CONTRACT.md` | `node test/mock.mjs 32 120` green from the repo; every contract name resolves in the digest |
| 2 | World review tooling: neutral `create/check_play.py` (from monsoon), trench `tools/check_world.py` + `check_play.py` adapter (trench depth, ladders, no man's land, runway, pits); run on the current vmap | `create/check_play.py`, `tools/check_*.py`, `docs/REVIEW_WORLD_1.md` | Checks validated on a known-good case; findings list with ids and positions |
| 3 | Script hardening: split into `src/modules/NN_*.js` + neutral `create/build_script.mjs`; current API (`Entities.*`, `Console.*`); one mock scenario per bug class (rounds, disconnect, team switch, seat/crew, reload); coverage table that fails on 0; neutral `create/sim_balance.mjs` 40-60 seeds; perf at 64 | `src/`, `test/`, `create/build_script.mjs`, `create/sim_balance.mjs`, `docs/SCRIPT.md`, `docs/REVIEW_SCRIPT_1.md` | `api.py --strict --check`, `tscheck.sh`, mock scenarios, balance 45-55 %, perf budget: all green (simulated) |
| 4 | Bot AI for low population: infantry deploy targets + leash; script-driven pilots and mortar crews that yield to humans; NONAV markup to cut the 44k-area nav; ladder nav links | `src/modules/85_ai.js`, `tools/patch_nav.py` | Mock scenarios for 2v2, 4v12, 32v32 with bots; nav area count target recorded |
| 5 | World fixes from step 2 as guarded patches: mortars as `prop_dynamic` (dynamic archetype) so fire anims and `mortar_<tg>_K` resolve; drop the duplicate `info_map_parameters`; clipping/stuck pockets/cover; zoomed `vmap_preview.py` renders of every area, looked at | `tools/patch_world_*.py` | `check_world` + `check_play` clean; `patch_guard` shows only targeted changes |
| 6 | Assets: neutral `create/gmod_assets.py`; WW1 Workshop packs (biplanes, tanks, artillery, trench props, soldiers) vs procedural, keep the better; replace the BF1-ripped Gewehr 98; fix `tw_de_a` open edges, LODs; turntable review | `tools/tw_models.py`, `docs/ASSETS.md`, `docs/WORKSHOP_COMPLIANCE.md` | Every model reviewed with a turntable; rip risk per pack recorded |
| 7 | Terrain and geometry: `terrain_img.py` erosion/detail with a protect mask (trenches, pits, spawns, runway exact), applied as a patch; `fxkit` cheap local weather (no fog particles); `gen_light.py` | `tools/patch_terrain.py` | Protected cells unchanged to the unit; `check_play` still clean |
| 8 | Presentation: HUD contract + `create/hud_check.py` gate (libsync); synthesised sounds with loop checks; radar, board/sight pictures, loading slides, skybox regenerated from layout | `tools/tw_hud.py`, `tools/sounds.py`, radar/loading tools | `hud_check` green; sound loop check green; radar dot matches `!pos` math |
| 9 | Delivery: neutral `create/deploy_addon.py` + `tools/deploy_tw.py` (dry run default, changed files only, keeps the Hammer vmap); `docs/BUILD.md`; asset compile then map compile under the watchdog; `docs/BUILD_LOG_1.md` triaged from the log itself | `tools/deploy_tw.py`, `docs/BUILD*.md` | 0 errors in the compile log; deploy dry run lists only changed files |
| 10 | Second review (world + script), README / TESTING / CREDITS / WORKSHOP docs from `docs/creation/templates/`; in-game TESTING checklist | `docs/` | Checklist covers everything only CS2 can confirm |

Steps 1+2 run together, then 3 alone (it owns `src/`), then 4+5, 6+7, 8+9, 10.

## Gap list: monsoon standard vs trenchwarfare today

| Area | mg_monsoon | mg_trenchwarfare today | Step |
|---|---|---|---|
| Contract | `docs/CONTRACT.md`: every name, model, sound, HUD id | none; names live in the script and generator | 1 |
| Script | modules + build step, current API, 24 bug classes fixed | one 1305-line file, 41 `Instance.*` calls (allow-listed) | 3 |
| Tests | 125 KB mock, scenarios per bug class, coverage table, `sim_balance`, perf | `mock.mjs` broken on Windows and needs the lost `out/`; ran clean once restaged in scratch | 1, 3 |
| Bots | deploy targets, leash, script crews yielding to humans, NONAV | bots off by default (tw35, never compiled); 44k nav areas hitch every 0.5 s; woods ladders unlinked | 4 |
| World checks | `check_world.py`, `check_play.py` (walk graph, pockets, sightlines, cover, clipping, water, terrain, nav) | none; mortars are `prop_static` (fire anim goes nowhere), duplicate `info_map_parameters` | 2, 5 |
| Assets | GMod pack swap with fallbacks, ASSETS + WORKSHOP_COMPLIANCE, turntables | procedural + Sketchfab without LODs; Gewehr 98 is a BF1 rip; `tw_de_a` 199 open edges; 3 custom sounds | 6 |
| Terrain | eroded image terrain with protect masks, fxkit weather | generator terrain; fog particles removed for FPS | 7 |
| Presentation | HUD contract + `hud_check`, synthesised sounds, generated radar/loading/sky | HUD role cards, radar alignment unconfirmed (`radar_region.json` lost) | 8 |
| Delivery | `deploy_monsoon.py`, BUILD.md, BUILD_LOG triage | numbered zips + `unpack_mg_trenchwarfare.bat`; vjs_c/vpk older than tw35 | 9 |
| Environment | Windows paths | tools hardcode Linux container paths (vtexread, preview_scene, toolkit.json, sync_repo.sh) | 1 (paths), as touched |

## Known open issues carried in

- Radar alignment: unconfirmed; needs the restaged `radar_region.json` and a `!pos` check in game.
- Mortar crew dying on firing: cause unknown; user explosions ruled out (> 2300 u from pits). Step 3 adds a scenario; in-game needs the `[tw] blocked` console line.
- Mortar assist credit: in the script, unconfirmed in game.
- Giant first-person weapons: cause confirmed by the user (12 Nov): the player was set to an invalid/unloaded model (a CS2 model chosen
  in Hammer, which lacked the game assets). Every player model the map or script sets must be compiled in the addon (or stock and
  loaded); check_contract covers the script's models. Still a TESTING item.
- Monsoon's own lesson: its map has never been compiled or played; copy its offline rigour, and say "simulated" until CS2 confirms.

## Progress

- 12 Nov: reminders set for each usage reset to Sat 13:00; vmap backed up; research done (TW_STATE, MONSOON_STANDARD); this plan.
- 12 Nov: step 1 done (restage_out.py, mock green on Windows, CONTRACT.md + check_contract.py 76/77, 1 known missing).
- 12 Nov: step 2 done (create/check_play.py + trench adapter, check_world.py, REVIEW_WORLD_1.md: 4 high, 6 mid, 11 low).
- 12 Nov: step 8 done offline (HUD contract + hud_check 0, new HUD look, 28 synthesised sounds, radar check 0 u; 3 sounds await wiring).
- 12 Nov: step 7 done offline (patch_terrain: craters, ruts, erosion under a protect mask; smoke + rain fx; light unchanged).
- 12 Nov: step 4 done (bots placed + leashed, AI pilots/crews yield to humans, BOTS_ON with fill 16, patch_nav ~1,470 areas est.; perf max to re-run on a quiet PC).
- 12 Nov: step 6 done offline (Canon de 75 swap, LODs, tw_de_a holes, ASSETS + WORKSHOP_COMPLIANCE; Gewehr 98/Luger licence work for the user).
- 12 Nov: step 5 done offline (patch_world_1 + patch_guard + dyn_models; H2/H3/H4/M3/L5 fixed in out/, H1/M2 opt-in), not deployed.
- 12 Nov: step 3 done (11 modules + create/build_script.mjs, current API, 6/6 scenarios, balance T 54 %, 0.37 ms/tick at 64, 18 bugs fixed).
