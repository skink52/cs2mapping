# The mg_monsoon standard, extracted for the mg_trenchwarfare remaster

Research note, 12 Nov 2026. AI-generated (Claude) for skink52. Read-only survey of `projects/monsoon-cs2/` (NOTES.md "Resume here" and
agent reports, docs/CONTRACT, SCRIPT, REVIEW_WORLD_1, REVIEW_SCRIPT_1, BUILD, BUILD_LOG_1, ASSETS, IMAGE_TERRAIN, WORKSHOP_COMPLIANCE, HUD)
and its `tools/`, `src/`, `test/`. Paths below are relative to `projects/monsoon-cs2/` unless they start `create/`, `docs/` or `projects/`.
Level words are those of `docs/reference/compatibility.md`: monsoon is **simulated** throughout, assets **compiled** (BUILD_LOG_1); the map
itself has never been compiled, Hammer verified or played. Its standard is the offline rigour, not proven in-game behaviour.

Trenchwarfare today (for the gap): one 1305-line `src/mg_trenchwarfare.js` with 41 `Instance.*` calls and no `Entities.*` (old API);
`test/mock.mjs` 15 KB; no CONTRACT / SCRIPT / BUILD / ASSETS docs; no check_world / check_play / deploy tool; deliveries were numbered zips
applied by `unpack_mg_trenchwarfare.bat`; the user's Hammer-edited vmap is the source of truth (NOTES.md, `docs/REMASTER_PROMPT.md`).

## 1. Contract

**Monsoon has.** `docs/CONTRACT.md` (76 lines): the one source for every name the map, script, HUD and tests share. Sections: Files (script
build, tests, HUD outputs, sounds, map stages, licensed model), Entities (a table: targetname pattern, class, notes; `<tg>` = t|ct, pools with
counts such as `mv_boom_fx_1..16`), what `out/layout.json` carries (terrain grid, mountinfo, tunnels, bridge, `models` block of pivots / seats /
muzzles), Models (`tools/mv_models.py`: logical name -> converted or procedural model; `MV_NO_EXT=1` forces procedural), Seats, Roles and
chat, Sound events. Rule: change the contract first, then both sides. Prefix `mv_` everywhere (entities, HUD ids, sound events `mv.*`).
- Enforced by: `tools/check_world.py` check 1 (every CONTRACT name present, right class and count; `expected()` builds the list in code);
  `test/mock.mjs` (an input fired at a missing entity or one its class lacks fails); the HUD contract tables in `docs/SCRIPT.md` (machine-read).
- Pattern worth copying: the script cannot read entity keyvalues, so per-entity data the script needs (mount kind/team, seat offsets, pivots)
  goes through `out/layout.json`, baked into the script by the build step.

**Generic?** The document shape is generic; content is 100 % monsoon. **Port:** write `docs/CONTRACT.md` fresh for `tw_` from the
current map (`python tools/mapdigest.py <user vmap> --summary/--class/--name`) and the script's `FindByName` calls; keep the `tw_` prefix
the user's map already uses. Copy-and-adapt; no create/ step.

## 2. Script hardening

**Monsoon has.**
- Modules `src/00_config.js` ... `90_main.js` (config, util + HUD cache, players/roles/kits, heli, arty, mounted, conquest, hud, ambient,
  `85_ai`, main loop) joined by `tools/build_script.mjs` (73 lines): name order, ONE import line from `cs_script/point_script`, refuses a
  source with its own import, bakes `const LAYOUT = out/layout.json` (required) and `const HUDDATA = out/hud.json` (or `{}`), header
  "generated, do not edit". Output `out/addon/maps/scripts/mg_monsoon.js`.
- One CONFIG object; `docs/SCRIPT.md` has a CONFIG guide table and a "departures from DESIGN, on purpose" paragraph with the reason for each.
- Think loop with try/catch per player and per vehicle, `SetNextThink` first; per-minute `perf:` console line (ms avg/max, HUD calls per tick,
  errors); `globalThis.__mvDebug`; `OnScriptReload` carries tickets, clock, owners, per-player prefs; `sanitise()` restores any pawn left
  shrunk/frozen/on a camera; HUD writes cached per player (`hText`/`hClass`/`hSwap`, only changes sent; skipped for bots).
- `test/mock.mjs` (125 KB): runs the BUILT script on a stand-in engine where only current API names exist (any other `Instance.*` throws),
  world from `out/entities.json` (or synthesised from layout.json). Usage `node test/mock.mjs [players] [seconds] key=value`: `humans=`,
  `seed=`, `scenario=churn|restart|edge|reload`, `piece=<set piece>`, `hudnew=1`, `mode=balance`, `cfg.<path>=<json>`, `move.<flag>=dx,dy`,
  env `MOCK_NORESTART=1`, `MOCK_TICKETS`, `MOCK_LOG=1`. Invariants every 16 ticks: no seat/crew/gun/vehicle pointing at a missing or
  other-side player, no non-finite position/angle/health, no pawn left shrunk/frozen/on a seat camera, HUD ids/classes only from the contract.
- Feature-coverage table: 600 s runs with 16+ players play scripted set pieces and print feature -> count; **any feature at 0 fails**
  (REVIEW_SCRIPT_1 section 2 lists 46 rows). One scenario per bug class; each bug in the review table names the scenario that fails without its fix.
- `test/sim_balance.mjs`: `node test/sim_balance.mjs [seeds=40] [players=32] set=bots|mixed|both cfg.<path>=...` spawns many
  `mock.mjs mode=balance json=1` rounds with the real CONFIG, infantry fight as a rate model; reports round length median/p25-p75, T win rate,
  flag hold shares, kills by source, vehicle life, AI uptime against targets (round 12-20 min, win 45-55 %, each source 3-40 %, vehicle life
  60-180 s, AI uptime >= 50 %). One SE over 40 seeds ~ 8 points: decide on 40-60 seeds, not 20.
- Perf: `node --cpu-prof test/mock.mjs 64 300 humans=32`; table avg / p99 / max / ticks over 8 ms (monsoon 0.089 avg, 0 over 8 ms).
- Static: `npx tsc -p test/tsconfig.json` (allowJs/checkJs against `test/point_script.d.ts`), from repo root
  `python create/test/api.py --strict --check <abs path to built js>` (0 invalid, 0 deprecated), `sh create/test/tscheck.sh <same>`.

**Generic?** `build_script.mjs` is ~95 % generic (map name, IMPORTS list, mountinfo special case). The mock's engine stand-in is
project-specific in drivers and set pieces; the neutral one is `create/test/mock_point_script.mjs` (libsync master; monsoon has a copy).
sim_balance is a thin generic runner over `mode=balance`. **Port:** copy `build_script.mjs` (rename, adjust IMPORTS from api.py);
split `mg_trenchwarfare.js` into `src/NN_*.js` (config, util, players/roles, plane, mortar, conquest/objectives, hud, ai, main); move every
`Instance.*` to current calls (`python tools/jsapi.py <js>` reports them); grow `test/mock.mjs` with drivers for pilot / mortar crew / infantry,
scenarios churn/restart/edge/reload, coverage table, invariants; copy sim_balance.mjs nearly verbatim (change SRC kill sources to
rifle/mg/mortar/plane-gun/bomb). Known trench issues to cover with set pieces: radar alignment, mortar crew death on firing, mortar assist credit.

## 3. Bot AI (low population)

**Monsoon has** (`src/85_ai.js`, CONFIG.AI in `00_config.js`, DESIGN 3.5):
- Infantry bots are **placed, not pathed** (a script cannot path a CS2 bot): they deploy at the held flag nearest the flag their team most
  needs. **Leash**: every `LEASH_CHECK` 1 s; a bot that moved < `LEASH_MOVE` 60 u in `LEASH_IDLE` 20 s, or left the playable band
  (`BAND_MARGIN` 80, `BAND_Z_UNDER` 260 under water), is redeployed unless in combat (`COMBAT_GRACE` 10). Tunnel portals `mv_tunnel_N` are leash targets.
- Script-driven roles when a team has fewer than `MIN_HUMANS_FOR_ROLES` 4 humans: `PILOTS 1, GUNNERS 2, CREWS 1` per team, at most
  `MAX_ROLE_SHARE` 0.5 of a team's bots. The bot pawn is parked in the seat; the script flies (patrol between flags, strafe runs with
  `STRAFE_*`, RTB under `RTB_HP`), aims guns (`GUN_REACT`, `GUN_SPREAD`), crews batteries (answers fire missions, marks clusters,
  `CREW_EXTRA_SIGMA` 30). Slow and inaccurate on purpose. `aiRelease()` yields any seat a human asks for; the hand-over toast only after the
  role is granted. Bot AT man: the script fires the launcher for bots at helicopters (CS2's bot brain would not).
- Server: `bot_quota_mode fill`, quota 10, `!bots <n>` 0-24; every CVAR checked against Valve's Workshop allow list
  (`scripts/workshop_cvar_whitelist.txt` read from pak01, 556 names).
- **NONAV markup** (`tools/mv_entities.py` `nav_markup()` / `nonav_boxes()`): `func_nav_markup` with key `navProperty_NavGen` =
  WALKABLESEED (15 seeds, 80 x 80 x 32 boxes at bases, flags, roads, `mv_nav_seed_N`) and NONAV boxes (85-94, `mv_nav_no_N`) over steep slopes,
  karst, deep river except fords, outside the band. `check_play.py` check 9: seeds on walkable ground, no NONAV over a road, flag, spawn or
  station. BUILD.md: read the nav area count after compile; trench's 44k areas cost FPS. NONAV is **unverified in engine**.
- Tested by `node test/mock.mjs 4 600` (4 humans, `!bots 14`: AI pilot / gunner / crew must act and yield seats) and sim_balance `set=bots`.

**Generic?** The design (placed bots + leash + script-run vehicle roles that yield) is generic; the code is tied to monsoon's flags,
helicopters and arty. **Port:** adapt `85_ai.js` directly: AI pilot -> biplane patrol / strafe / bomb run over the trench line; AI crew ->
mortar crew answering marks; infantry deploy targets = trench sectors / objectives; leash band = the trench system. NONAV: copy
`nav_markup()` into the trench generator or a `patch_vmap.py` patch (no man's land craters, wire belts, the out-of-bounds woods), keep
WALKABLESEED in trenches, shelters, airfields. Trench's NOTES tw27/tw35 history (bots added, then off by default for FPS) is the baseline.

## 4. World checks

**Monsoon has.**
- `tools/check_world.py <vmap> [--plot out.png [x0,y0,x1,y1]]` (290 lines), exit 1 on failure, "RESULT: clean (7 checks)":
  1 contract names/classes/counts; 2 no prop origin > 8 u under / 6 u over a surface (exceptions listed by the placer in `out/world_sites.json`);
  3 placer overlap audit of solid props -> `out/overlaps.json` (`OK_PAIR` list of by-design touches); 4 spawn / seat points: 80 u headroom, on a
  surface, not inside a footprint; 5 every flag reachable (slope < 40 deg from the nearest road); 6 counts per class; 7 every entity model exists
  (ours as `.vmdl` under out/addon, stock as `<path>_c` in the pak01 index) and 7b every prop_dynamic of ours has archetype `""` or `animated_model`.
- `tools/check_play.py <vmap> [--json] [--only 1,2] [--verbose]` (1142 lines), "RESULT: clean (9 checks)", numbers to `out/check_play.json`.
  Rebuilds the scene **from the vmap** (terrain, world meshes, clips, water, each solid prop's compiled hull SMDs; stock trees = trunk
  cylinders), rasterises on a 16-u grid (surfaces + blockers widened 12 u), walk graph (step 18, jump 54, body 18-68 u). Checks: 1 walkability
  (both spawn rings one component; every flag, station, seat, pad, portal reachable and back; stuck pockets > 200 u2 with/without jump);
  1b routes (walk distance base -> each flag, mirror ratios, warn > 15 %); 2 sightlines (no enemy spawn-to-spawn LOS, per-flag exposure);
  3 cover (>= 14 head-height pieces within 600 u of each flag; a sandbag wall counts per 96 u column); 4 helicopters (rotor cylinder clear
  > 24 u, >= 3 of 8 approach lanes at 30-deg glide, flat landing crowns); 5 spawn safety (no spawn in a mounted gun's LOS < 900 u);
  6 clipping (buried > 35 %, floating > 6 u, crowns in buildings, non-solid inside solid, props under water); 7 water (edges above ground,
  z-fight, deep spots); 8 terrain (road slope < 20 deg, ramps meet banks within 4 u, no ground through walk-in floors, holes covered);
  9 nav (above).
- `tools/view_world.py <vmap> top x0,y0,x1,y1 out.png` and views: plans with walkable / blocked cells and props, to look at each area.
- `tools/check_mesh.py <vmap>` (libsync copy of `create/check_mesh.py`): "N meshes 0 bad".
- Process: REVIEW_WORLD_1 = 8 map builds, a before/after table per check, an issue table per area (where, severity high/mid/low,
  fixed how or left why), a "Left (deliberate)" list. Placer guards record why a large optional prop was skipped (`W.big_skips`).

**Generic?** check_mesh is generic (shared). check_world is ~70 % monsoon (contract list, OK_PAIR, `mv_stock` / `mv_models` / `layout`
imports). check_play's grid / walk graph / pockets / sightlines / cover / clipping / water are generic in method; checks 4-5 and the
scene builders' model tables are monsoon. Neither has a `create/` copy. **Port:** first make a neutral `create/check_play.py` (scene from the
vmap + hull SMDs, walk graph, checks 1/1b/2/3/6/7/8/9 parameterised by a small project module giving spawn rings, targets, stock bounds,
exceptions), then a trench adapter: trench depth / fire-step walkability, exit ladders (ladder volumes as edges), no man's land exposure,
cover per sector, aerodrome runway clear + take-off lanes in place of rotor cylinders, mortar pits safe from enemy direct LOS. check_world:
copy-and-adapt (contract list from the new CONTRACT.md; check 7/7b as is). Needs the trench equivalent of `mv_stock.py` (stock bounds measured
with `create/s2/bounds_batch.mjs`) and a `world_sites.json` from the generator. Run on the **user's latest vmap**, not a fresh generation.

## 5. Assets

**Monsoon has.**
- 117 procedural props via the shared prop pipeline (`build_all_props.py`, `build_prop.py`, `bake.py`, `geo.py`, `shaders.py`, `stock.py`,
  all libsync copies trench already has) + project spec modules `p_*.py`, `mv_geo.py`, `mv_shaders.py`. Every prop has a turntable
  `preview/<name>.png` that was looked at; weaknesses listed honestly (NOTES "Known visual weaknesses"). LODs by
  `lod_decimate.py ../out/addon ../out/addon mv/<name>` on the heavy list (BUILD step 1c). `build_prop` spec key `dynamic` writes
  `model_archetype ""` for props the script moves. Builds serialise on `out/build.lock`.
- GMod Workshop route `tools/gmod_assets.py` (473 lines, always `python -I`): `fetch` (SteamCMD anonymous, own `force_install_dir` and acf),
  `list`, `convert` (`create/mdl2cs2.py` + split/pivot onto bones, `parts` welded from lua offsets read as text, `ground`, `hulls N`,
  `matsub_of`, `dynamic`), `view` (4-view render, contact sheets), `report` (`out/gmod_models.json`), `prune`. Catalog `tools/gmod_assets.json`
  (id, author, licence note, rip, status, items). `docs/ASSETS.md`: per model bounds, tris, origin/pivot, source id, rip key; every candidate
  looked at with status; rejected-after-looking list; "not found, stays procedural" list.
- `tools/mv_models.py`: one table logical name -> converted model if its .vmdl exists, else procedural fallback; pivots, seats, muzzles exported
  to layout.json; `ensure_dyn()` writes a prop_dynamic twin; `UNUSED` with reasons. `MV_NO_EXT=1` = Workshop-safe build.
- `docs/WORKSHOP_COMPLIANCE.md` (from `docs/creation/templates/`): verdict, every pack with source / licence / replacement, steps for a
  Workshop build (`deploy --skip-ext`, remove ext folders from both addon roots by hand), what to avoid on the page, residual risk.

**Generic?** gmod_assets.py is nearly generic (4 monsoon refs: docstring, `SUB = models/mv/ext`); catalog is per project. mv_models
pattern is generic, content not. **Port:** make neutral `create/gmod_assets.py` first (prefix and paths from toolkit.json or args), add it to
`create/libsync.json`, then a trench catalog (biplanes, tanks, field guns, trench props, soldiers) + `tools/tw_models.py` with procedural
fallbacks; ASSETS.md and WORKSHOP_COMPLIANCE.md per the monsoon shape. Rip risk recorded per pack before anything is placed.

## 6. Terrain and geometry

**Monsoon has.** `tools/layout.py` (single source of positions; `export()` -> out/layout.json); `mv_terrain.py` (tiles 16/32/64/128 u by
need), `mv_places.py` (each place its own seeded RandomState, so adding to one never reshuffles another), `mv_entities.py`, `make_map.py
<template or live vmap> <out vmap> <addon> [<previous generated vmap>]` (vmapgen + EditKeeper, vis groups `mv_gen` / `mv_user`).
Image detail (`docs/IMAGE_TERRAIN.md`): `tools/make_detail.py` exports `layout.height_base`, runs `terrain_img.run_detail` (gullies, droplet
erosion, scree, outcrops), writes `tools/data/detail.png` + splat / density images; protect mask (flags r 500, bases, roads, water, portals,
terrain edge) must print `max |detail| there: 0.000000` at 400k off-grid samples; `layout.height = height_base + detail`; tiles with
|detail| > 10 go to 64 u; paint and foliage density sampled from the images. Acceptance = open both hillshades. create/ used: `primitives`
(box, wedge, stairs, sweep, cylinder, arch), `meshedit` (subdivide, noise), `fxkit` (weather_tiles rain, lightning). Not used: gen_light,
gen_buildings, matkit.

**Generic?** create/ libs generic; layout/terrain/places are monsoon. **Port:** trench has `layout.py`, `make_map.py` (92 KB), `p_trench.py`;
the remaster must not regenerate over user edits: EditKeeper with the previous generated map (`out/gen_twN.vmap`) or delta patches
(`create/patch_vmap.py`, forked from trench's own). Terrain detail: libsync-add `create/terrain_img.py` to trench, a `make_detail.py` with a
protect mask over every trench, sap, shelter, pit, spawn, runway (exact 0), detail only on no man's land / rear slopes. Weather: fxkit
local rain, **no fog particles** (tw32 moved fog off particles for FPS). gen_light only if a preset is wanted; it writes a whole sun/sky set.

## 7. Presentation

**Monsoon has** (`docs/HUD.md`):
- HUD contract in `docs/SCRIPT.md` between `<!-- HUD-CONTRACT-BEGIN -->` / `END` (`| id | kind | classes | meaning |`, kinds text/class/swap,
  stepped classes like `p0..p20`, `a0..a71` rotation, board markers as `x0..x159` / `y0..y159` nested panels) and a separate
  `HUD-ADDITIONS` table the script uses only when `out/hud.json` lists the id (`hudHas()`). 103 ids (limit 1024).
- `tools/mv_hud.py <addon>`: art + xml + css + `out/hud.json` (ids, step counts); exits 1 on a contract break, a missing picture or a failed
  `hud_check.py` gate. No `overflow: clip`, no child wider than its parent: every stepped read-out is one picture per step.
- `tools/hud_check.py` (copy of `create/hud_check.py`): `--addon ../out/addon --name mg_monsoon --states ../out/hud_states.json --out
  ../out/hud/hud`, lays out like Panorama at 1920 / 2333 (and `--check-widths 1440,1920,2333`), draws 8 states -> 0 problems.
- `tools/sounds.py <addon> <template vsndevts>`: 41 synthesised wavs, 21 `mv.*` events merged into the `mg_monsoon` block only
  (`sndevents.py` / `merge_snd.py`); numeric listen-check `out/sounds_report.json`, exit 1 on clipping (peaks -0.72 dBFS), a loop seam that
  would click (wrap step and slope kink under the file's own 99.9th-percentile step; loops built from periodic noise, whole cycles, smpl + cue
  markers, no crossfade) or a wrong spectrum.
- `tools/make_radar.py <addon> <game>` (1024 px, square +-6400, `resource/overviews/<map>.txt`, terrain raster cached by layout hash,
  `MV_RADAR_STALE=1` only while iterating); `render_board.py` (board, 3 loading slides inside CS2's safe area, `map_icon_<map>.svg`);
  `make_sky.py` (3D skybox via `make_skybox.build` in plain mode, on a copy of mg_trenchwarfare's skybox map; check_mesh 0 bad).

**Generic?** hud_check, panorama, loading, make_skybox, sndevents, merge_snd: neutral create/ masters. mv_hud.py (212 monsoon refs), sounds.py
recipes, make_radar layers: project-specific, method generic. **Port:** libsync-add hud_check / panorama / loading / sndevents / merge_snd to
trench; write the trench HUD contract into a SCRIPT.md, then rebuild `tw_hud.py` (+ `tw_cockpit.py` dials) against it with the gate; extend
trench `sounds.py` (8 KB) with the numeric check (copy monsoon's check functions; `create/sndkit.py` has loop markers); radar already exists
(make it read layout and fix alignment), mortar sight pictures = monsoon's board method; slides via `create/loading.py`.

## 8. Delivery / build

**Monsoon has.**
- `tools/deploy_monsoon.py` (515 lines, `python -I`): dry run by default; `--list`, `--apply`, `--rollback <manifest> --apply`, `--skip-ext`,
  `--overwrite-map`, `--allow-open`, `--ignore-lock`. Writes only files whose bytes differ (size + sha256), deletes nothing, backs up before
  replace (`.vmap` as `<map>.vmap.bak_<stamp>`), no writes through links; exit 3 while `cs2.exe -tools` has the addon, 4 while `out/build.lock`;
  keeps a destination vmap edited in Hammer; merges only its block of `soundevents_addon.vsndevts`; creates postprocess `.vpost` and
  `addoninfo.txt` for a new addon; ships README / TESTING / CREDITS / licences to both roots and `<addon> STEAM DESCRIPTION.txt` (kept if
  hand-edited). Manifest `out/deploy/<map>_deploy_<stamp>.json`. Reports how many ext models the map references.
- `docs/BUILD.md` (order table steps 1-12 with commands, times, checks; "what to read in the build log" table), `tools/build_monsoon.md`
  (terse sheet), `docs/BUILD_LOG_1.md` (commands and times, errors before/after by class, fixed, remains), `docs/TESTING_MONSOON.md`
  (A build log ... N engine questions, "Known unknowns"), README_MONSOON, CREDITS, WORKSHOP_DESCRIPTION.txt.
- Compile: `build_maps.ps1 assets <map>` then forced `resourcecompiler -f -i` on the xml, css, js; then `build_maps.ps1 final <map>`
  (lightmap 2048, VRAD 2), all under the watchdog from `C:\source1\cs2port`.

**Generic?** deploy_monsoon is ~90 % generic (21 refs: map name, doc names, `mg_monsoon` sound block). **Port:** copy to
`tools/deploy_trench.py` (or a neutral `create/deploy_addon.py` first, then a 10-line wrapper; better, since the next project needs it too).
It replaces the zip + `unpack_mg_trenchwarfare.bat` route; its "keep a Hammer-edited vmap" rule matches trench's history. Docs from
`docs/creation/templates/` (CREDITS, HANDOVER, README, README_ADDON, SERVER_ISSUES, TESTING, WORKSHOP_CHANGELOG, WORKSHOP_COMPLIANCE).

## 9. Neutral create/ tools named in the brief

| Tool | Exists | Note |
|---|---|---|
| `create/terrain_img.py` | yes | monsoon has a libsync copy; trench none yet |
| `create/primitives.py`, `meshedit.py`, `fxkit.py`, `gen_light.py` | yes | cs2-map-mcp ports; imported from create/, not copied |
| `create/hud_check.py` | yes | fork of space-racer `preview/hud_render.py`; copy in monsoon |
| `create/vmapgen.py` (`EditKeeper`, line 460) | yes | fork of space-racer `tools/vmap.py`; copy in monsoon |
| `create/patch_vmap.py` | yes | fork of trench's own `tools/patch_vmap.py` |
| `create/libsync.py` (+ `libsync.json`) | yes | `check` / `push` / `pull` / `ack` / `add` |
| `create/test/api.py`, `create/test/tscheck.sh` | yes | plus `mock_point_script.mjs`, `point_script.d.ts`, `api_allow.txt` |
| check_world / check_play / gmod_assets / deploy / build_script / sim_balance | **no** neutral copy | monsoon-only today |

`docs/creation/templates/`: CREDITS.md, HANDOVER.md, README.md, README_ADDON.md, SERVER_ISSUES.md, TESTING.md, WORKSHOP_CHANGELOG.md,
WORKSHOP_COMPLIANCE.md. Libsync copies trench lacks that monsoon has: hud_check, loading, merge_snd, panorama, sndevents, split_parts,
terrain_img, vmapgen, mock_point_script (trench has patch_vmap and split_props as the origins of two forks).

## 10. "All offline checks green" gate, in order

From `tools/` unless marked; anything over ~2 min under `C:\source1\cs2port\autoport\watchdog.py` with `--expect`, `python -u`.
1. `python make_detail.py` (only if designed ground moved; 27 s) -> `max |detail| there: 0.000000`.
2. `python -u make_map.py <template or live vmap> ../out/addon/maps/mg_monsoon.vmap ../out/addon [<prev generated>]` (4.5-8.5 min, watchdog).
3. `python check_mesh.py ../out/addon/maps/mg_monsoon.vmap` -> `N meshes 0 bad`.
4. `python check_world.py <vmap>` -> `RESULT: clean`, exit 0.
5. `python check_play.py <vmap>` -> `RESULT: clean (9 checks)`, exit 0.
6. `python sounds.py ../out/addon "<content_addons>/addon_template/soundevents/soundevents_addon.vsndevts"` -> exit 0.
7. `python make_radar.py ../out/addon ../out/game`; `python render_board.py ../out/addon`; `python make_sky.py` (check_mesh 0 bad).
8. `python mv_hud.py ../out/addon` -> exit 0 (contract + `hud_check.py` gate, 0 problems).
9. Project folder: `node tools/build_script.mjs`; `node test/mock.mjs 32 600` (coverage, no 0 rows); `node test/mock.mjs 4 600` (AI);
   scenarios `32 300 scenario=churn|restart|edge|reload`; `node test/mock.mjs 64 600 humans=32`; `npx tsc -p test/tsconfig.json` -> 0 errors.
10. Repo root: `python create/test/api.py --strict --check <abs>/out/addon/maps/scripts/mg_monsoon.js` and `sh create/test/tscheck.sh <same>`.
11. Balance / perf when the script or CONFIG changed: `node test/sim_balance.mjs 60 32` (1.5-5 min, watchdog); `node --cpu-prof test/mock.mjs 64 300 humans=32`.
12. `python -I tools/deploy_monsoon.py` (dry run: no gate holds, "the map references N of the models").
13. `python create/libsync.py check`; `python ci/check_repo.py`; `python ci/check_links.py --anchors --baseline ci/known_broken_links.txt`.
Then (not offline): deploy `--apply`, asset compile, forced xml/css/js compiles, map compile, TESTING checklist.

## 11. Lessons and gotchas a remaster must not repeat

Build / compile (BUILD.md, BUILD_LOG_1):
- `build_maps.ps1` says "assets OK" with failed **models**: only uncompiled materials are fatal. Grep the log for `RESOURCE COMPILE ERROR`
  and `compiled, N failed`; a wrapper exit 0 proves nothing.
- A failed panorama layout is ignored silently: always `resourcecompiler -f -i` the xml, css and js and look for "compiled".
- A `prop_dynamic` on a `static_prop_model` vmdl is DELETED at map compile: spec `dynamic` / archetype `""`; one model used both static and
  dynamic needs a `_dyn` twin (monsoon's `shell_105` is still open). check_world 7b catches it.
- Props using stock materials need `stock.ensure()` (5 sandbag models failed because `export_custom` was never called).
- `lod_decimate` must not write a one-group `LODGroupList`; rebuilding a prop overwrites its vmdl, so rerun `lod_decimate` after.
- `vtexread.py` default VPK path was a cloud path: exporters could not run on the PC until fixed.
- One transient `shaders_pc.vpk ... invalid` fatal: rerun before chasing it; Steam "verify" if it repeats.
- Working folder `C:\source1\cs2port`, never `C:\source1` (its gameinfo gets mounted, every material fails). Watchdog `--log` must be its own
  file; use `--watch` for the build log (pointing `--log` at it locks it). `python -u` or the watched log stays empty.
- Lightmap: stay at 2048; too many charts -> fewer charts (probe-lit foliage and props < 40 u, `bakelighting 0`; LODs), never a bigger atlas
  (trench tw34 ran out of memory at 4096 "Welding seams"). Nav area count near 44k = NONAV did not apply.
- First asset compile estimate (20-40 min) was 9 min: measure, then record times in BUILD.md.
- Never deploy while `cs2.exe -tools` has the addon open; never launch the game (focus); after stopping a chain, `taskkill /T` its tree.

World (REVIEW_WORLD_1, NOTES):
- Cover pieces closed a route: deck props on the bridge made CT walk 1500 u further (ratio 1.29). Measure routes after every dressing pass.
- Dressing inside rotor cylinders / on pads, huts inside karst, towers in walls: register keep-outs (rotor, karst, flag 70 u) **before**
  dressing; a guard in `World.prop` drops and reports violators.
- Props on slopes sink uphill; floors need flats under them; trees need crown-vs-building tests; foliage converted with one convex hull must
  be non-solid (trunk clips instead); boxes with negative sizes came out inside-out (`mv_geo.box` sorts corners now).
- Check false positives cost builds: grid points past the edge wrapped into the next column; sandbag walls counted per course; an
  entity paired with itself. Validate a new check on a known-good case before trusting its count.
- Water sheets: end on cell edges, fit widths per vertex, no two sheets at one height (trench already fixed pools z-fighting in tw4).
- Roads graded (13 deg) and switchbacks removed; "Left (deliberate)" items written down, not silently dropped.
- Cache props named by model were never found by the script: names come from CONTRACT, the script reads the model name off the prop.

Script (REVIEW_SCRIPT_1): stow the rifle on any seat that reads MOUSE1; leaving a seat must not re-issue a fresh kit; role change in the
field waits for the next deploy (no free teleport); AFK pilot in the air is let down and freed; `OnScriptReload` + `sanitise()`; leaving a team
while dead clears crews; `hudReset` when a slot changes hands; credit checks slot owner and side (`creditOf`); no stacking of disable timers
+ repair grace; abandoned vehicle fetched back; water is the floor (ditching); `resetRound` clears every per-round field; dt capped at 1 s;
ticket underflow ends the round once; deploy cover 3 s; HUD calls skip bots; HUD cache with one record per id (string keys were 23 % of CPU).
Mock gotcha: once `out/hud.json` lists the HUD additions, the plain mock needs `hudnew=1` (HUD.md vs NOTES disagree on this; check before
calling a run red). Balance: 20-seed results are noise; geometry (who reaches the key flag first) decided the bots-only win rate, not script asymmetry.

Assets / process: conversions are game rips: keep a procedural fallback for every placed ext model and a Workshop switch; `-I` for anything
parsing downloads, lua read as text only; SteamCMD with its own install dir. Never claim more than the level reached ("simulated" vs
"compiled"); keep NOTES "Resume here" current; libsync check before commit (4 shared tools drifted during monsoon's build); one generator at
a time writes out/addon (`build.lock`).
