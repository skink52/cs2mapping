# Working notes (AI session log)

Read this first when resuming. Newest state at the top. Design: [docs/DESIGN.md](docs/DESIGN.md).

## Resume here (12 Nov 2026, after build stage 3: nav cut, world pass 3, recompiled)

**State in one line:** `mg_monsoon.vpk` **recompiled** (41.5 min, 0 failed, 0 DELETED) with **15,033 nav areas** (was 33,661;
"Compute Approach areas" 348 s, was 1,569 s) and the script mv-0.5 compiled; **never launched, not opened in Hammer**. Not committed.
Records: [docs/BUILD_LOG_1.md](docs/BUILD_LOG_1.md) "Stage 3", [docs/REVIEW_WORLD_1.md](docs/REVIEW_WORLD_1.md) "Pass 3".

- Nav: `mv_entities.nonav_boxes()` keeps nav only on the bases, flags, roads / trails, two declared routes (west ford; CT's route
  to the temple) and the tunnels (243 NONAV boxes). `check_play.py` check 9 now estimates the nav (flood with NONAV nodes removed,
  calibrated on this compile: 0.130 areas per 16-u cell), fails when a station is off the nav or a base cannot route to a flag on it,
  and `--nav-plan` measures a markup change before regenerating. 15,033 is at the 15,000 line, not well under: next cut in REVIEW Pass 3 "Left".
- World: temple ghat (river stair landing + two flights; CT to D 5199 -> 4799, A-D balance 1.15 -> 1.06), temple court 4 balustrades
  + 4 lions (crate moved to the SE corner), a strangler-fig wall and a collapsed enclosure run at the knoll foot, village market lane
  (3 stalls), 2 platforms, spirit-house offerings, hut-roof clips, 8 huts (was 9), culvert bunker + M113 outside the firebase gate.
- Left: **C-E balance 1.11** (CT deploy point behind gun pit 1; needs a `layout.firebase()` change and POCKET_FILL re-derived),
  antenna mast / crew tent / second latrine (no room in the wire), one jump-escapable village pocket.
- Checks on the compiled vmap: check_mesh 0 bad, check_world clean, check_play clean (9), mock 32 x 300 PASS; radar and board rebuilt.

## Earlier: after build stage 2 (12 Nov 2026, the map compiled)

**State in one line:** `mg_monsoon.vpk` is **compiled** (final build, 65.8 min, 0 failed, 0 DELETED) and in
`game\csgo_addons\mg_monsoon\maps\` with the 3D skybox's own `mg_monsoon_3dskybox.vpk`; **never launched, not opened in Hammer**.
Not committed. Full record: [docs/BUILD_LOG_1.md](docs/BUILD_LOG_1.md) "Stage 2".

- Two generator faults made the compiler spin for ever on one core (no error, no log line); both fixed and now caught offline by
  `tools/check_mesh.py`:
  1. map load hung on the tunnel mesh's 6 "pinch" vertices (two open cells meeting at a corner): `vmesh.split_pinches()`;
  2. lightmap charting crawled on the 47,912-face `toolslightmapres` shell: `mv_terrain.build_lmres` now 256-u cells, 3,170 faces.
- Stats: vis 4,096 clusters (19 min); lightmap 2048 x 2048, 270,837 charts, no OOM (lighting 14.5 min); **nav 33,661 areas**
  ("Compute Approach areas" alone 26 min); vpk 183 MB.
- The skybox map needs its own build line: `build_maps.ps1 final "mg_monsoon mg_monsoon_3dskybox"` (one quoted argument).
- Offline checks after the fixes: check_mesh 0 bad, check_world clean, check_play clean (9), mock 32 x 300 PASS.

- **Script round 3 (12 Nov, simulated only, mv-0.5)**: bot-only T win 70 -> 49 % and mixed 56 -> 49 % over 80 seeds (team plan for bot
  deploys, AI pilot uptime 50 -> 75 %), plus AI crew hand-over, `!bots` vote, no teleport for a waiting human in the field, bot takeover
  (`OnBotControl`). Record and what is still short (flag D, perf +4 %): [docs/REVIEW_SCRIPT_2.md](docs/REVIEW_SCRIPT_2.md) "Round 3".
- **Script review pass 2 (12 Nov, simulated only)**: 10 bugs fixed in `src/` (1 high: a departed player's controller left in its slot
  kept its AI role / gun crew / helicopter; 6 medium: AI helicopter hand-over called more than once, not withdrawable, locked when its AI
  pilot left; pilotless helicopter ditched in the river; pilot back on his pad without his helicopter; AI gunner kept an abandoned one in
  the field; 3 low: empty panels after a restart, control characters in `say`, HUD lost while a client loads). VERSION `mv-0.4`.
  New `node test/mock.mjs 32 450 scenario=review2 humans=4` (each piece fails on `out/review2/before_review2.js`). Full record and
  what only CS2 can confirm: [docs/REVIEW_SCRIPT_2.md](docs/REVIEW_SCRIPT_2.md). SCRIPT.md "Tests" / CONFIG guide not yet updated for it.

**Next:** skink52 launches it (docs/BUILD.md "Local test with bots": tools mode, `map mg_monsoon`, `version`) and works through
TESTING_MONSOON.md. Watch FPS with bots (nav area count near the sibling's 44k that cost FPS) and VRAM (elephant grass is 109 MB of
206 MB aggregate vertex data; the 3D skybox is 16.2 M triangles and a 420 MB vpk, bigger than the map: likely the first thing to thin). Before committing: `create/libsync.py pull` for `vmesh.py` and `check_mesh.py` (the only two it lists as DIFFERS).

## Earlier: after world review pass 2 (12 Nov 2026)

**State in one line:** world review pass 2 is done and every offline check is clean (check_play 0 stuck pockets, check_world incl.
the new prop_dynamic archetype check, check_mesh, mock PASS); **nothing compiled from this pass, not opened in Hammer, not run in CS2**.
Not committed. Full record: [docs/REVIEW_WORLD_1.md](docs/REVIEW_WORLD_1.md) "Pass 2".

- Map `out/addon/maps/mg_monsoon.vmap`: 72.4 MB, 7526 entities, 1184 meshes (5 builds this pass; a build takes ~9 min, of which the
  "water" stage is now 3-5 min: `mv_terrain.mesh_low` calls `layout.height` per point, worth vectorising).
- Stuck pockets 12 -> 0: player clips over every sandbag wall and berm crest (`World.cap`, 16..200 u, inside the bags' footprint), pig
  pens clipped, tunnel floor grade limited, `POCKET_FILL` + a clip over the quad .50 base in `firebase()` (derived from check_play
  cells; the firebase uses its own RandomState, so re-derive them after any change to `firebase()`).
- Village: yard pieces right after the designed huts; 9 huts, shrine, 2 stalls, 3 cook fires, 2 climbable platforms.
- Temple: sculpted lion and naga rebuilt; new khmer_pillar(_broken), enclosure_wall(_ruin), root_wall, paving_slabs; paving, 8 lions,
  causeway nagas, porticos with architraves, east gallery, 5 enclosure walls, rubble clusters. root_wall / enclosure_wall_ruin built but
  not placed (no room clear of the court-edge balustrades; the knoll falls 26-40 deg past r 420: needs an outer terrace in layout).
- Firebase: wind sock placed clear of the rotor cylinders and lanes; water trailer placed; antenna mast, culvert bunker, crew tent,
  M113 still find no spot; a second latrine fitted but made a pocket (its roof stepped onto the wall caps), so it stays out.
- `shell_105_dyn` (dynamic twin, archetype "") for `mv_shell_*` and the cache list; `check_world.py` 7b fails on any prop_dynamic of ours
  with a static_prop_model .vmdl.

Checks (from `tools/`): `check_play.py`, `check_world.py`, `check_mesh.py` on `../out/addon/maps/mg_monsoon.vmap`: clean / clean / 0 bad;
`make_radar.py`, `render_board.py` rerun; `node tools/build_script.mjs && node test/mock.mjs 32 300` (project folder): PASS.

**Next:** redeploy (dry run first; the deploy + asset compile record is the next section and `docs/BUILD_LOG_1.md`), compile the new and
rebuilt props (guardian_statue, naga_balustrade, khmer_pillar(_broken), enclosure_wall(_ruin), root_wall, paving_slabs, shell_105_dyn),
then the map compile (step 11); look at the temple and the clips in Hammer; vectorise `mesh_low`. The shell_105 open point below is done.

## Earlier: after build stage 1, deploy + asset compile (12 Nov 2026)

**Deployed and assets compiled; the map is not compiled yet.** `deploy_monsoon.py --apply` created both addon folders (3114 files,
1242 MB). `build_maps.ps1 assets mg_monsoon` took 9 min the first time; run 1 had 5 sandbag models failing (missing stock hessian
materials: nothing called `stock.export_custom`), 3 single-LOD warnings and one transient shader-pack error; after generator fixes
(`stock.ensure`, `vtexread` PC default, `lod_decimate` one-group, `build_prop` spec `dynamic` for quad50_gun / rocket_122 / _rail /
_tripod) run 4 is 0 errors, 0 warnings, and the forced xml / css / js / svg compiles pass. Open: `shell_105` is both prop_static and
prop_dynamic (`mv_shell_*`) and needs a `_dyn` twin in `mv_entities.py`; libsync lists 4 changed shared tools to pull into `create/`.
Next: redeploy the polished vmap, then step 11 (map compile). Full record: [docs/BUILD_LOG_1.md](docs/BUILD_LOG_1.md).

## Earlier: after world review 1 (12 Nov 2026)

**State in one line:** the map is regenerated after a gameplay / clipping review and passes every offline check, including the new
`tools/check_play.py`; **nothing has been compiled, opened in Hammer or run in CS2**. Nothing is committed or deployed.
Full record: [docs/REVIEW_WORLD_1.md](docs/REVIEW_WORLD_1.md) (issues, fixes, before / after numbers, what was dropped and why).

- Map `out/addon/maps/mg_monsoon.vmap`: 71.3 MB, 7489 entities, 1095 meshes, terrain 83 584 quads (paddy tiles are 16-u cells now),
  6826 prop_static. Radar, board, script (`mg_monsoon.js`, 3341 lines) rebuilt from it.
- New tools: `tools/check_play.py <vmap>` (walk graph on a 16-u grid: reachability and stuck pockets, 1b walking routes base -> flag
  with mirror balance, sightlines, cover, rotor cylinders / approach lanes / karst landing discs, spawn safety, prop clipping, water
  edges, road grades / floors / holes, nav markup; writes `out/check_play.json`) and `tools/view_world.py` (plans and views with props).
- Balance: B was 1500 u nearer for T (deck cover closed the bridge for CT); now CT/T 5521 / 5281 (1.04), A-D 1.09, C-E 1.06.
- Layout moves: T pads 1 and 3 off the karst talus, C-123 90 u north, firebase tower / quad .50 / TOC, trail A-bridge 150 u east of
  the paddies, `ISLAND` threshing floor at flag A, `SPUR` road to the firebase, all roads graded to 13 deg. Contract names unchanged.
- psp_pad rebuilt without its wind-sock pole; `windsock` is its own prop (built, not placed yet).
- Left (documented in the review): village shrine / one stall / two cook fires and a second platform do not fit; temple court only
  3 balustrades + 1 lion; water trailer, culvert, antenna masts, crew tents dropped inside the wire; 12 jump-escapable pockets.

Checks (from `tools/`): `check_play.py`, `check_world.py`, `check_mesh.py` on `../out/addon/maps/mg_monsoon.vmap`: clean / clean /
0 bad; `node tools/build_script.mjs && node test/mock.mjs 32 300` (project folder): PASS. A map build takes about 8.5 min now.

## Earlier: after the integration pass (12 Nov 2026)

**State in one line:** the whole addon is generated and passes every offline check; **nothing has been compiled, opened in Hammer
or run in CS2**. Every "works" below means generated / simulated (words of `docs/reference/compatibility.md`). Nothing is committed
or deployed (`tools/deploy_monsoon.py` is a dry run; do not `--apply` without being asked).

**What exists** (all under `out/`, gitignored; `out/addon` is the content tree):
- Map `out/addon/maps/mg_monsoon.vmap` (63.5 MB, 6965 entities, 1090 meshes): terrain 672 tiles / 68k quads with the **image detail
  layer** (ravines down both valley sides; `layout.height = height_base + detail`, images in `tools/data/`, `docs/IMAGE_TERRAIN.md`),
  8 karst towers, water, lobby, firebase, camp, tunnels, 5 flags, village, temple, crash site, bridge, marsh, jungle
  (6307 prop_static, 146 models), 130 script prop_dynamic, nav markup (15 seeds, 94 NONAV boxes), rain, lightning.
- 3D skybox map `mg_monsoon_3dskybox.vmap` (11 Nov, not rebuilt: it uses `layout.ground_low`, which this pass did not change).
- Script `out/addon/maps/scripts/mg_monsoon.js` (3034 lines, VERSION mv-0.2), HUD xml / css / 100 pictures, radar, board, 3 loading
  slides, 41 sounds, 4 fx models (`models/mv/fx/mv_{tracer,mission_ring,gunpip,rocket}`), 117 procedural props, the Apache, 53
  converted GMod models (`models/mv/ext`), 4 GMod player models (`models/player/gmod/{nva_soldier,vietcong_soldier,soldier2_woodland,us}`
  + `shared`), `out/cache_models.json`.

**What changed on 12 Nov (integration pass)**
- **Model table `tools/mv_models.py`**: logical name -> converted model (when its .vmdl is in the addon) or procedural fallback
  (`MV_NO_EXT=1` forces the fallbacks, e.g. for a Steam Workshop build: the conversions are game rips, `docs/ASSETS.md`). Used by
  `mv_places.py` (`W.sprop`, `W.park`, `W.mount`), `mv_entities.py` and `layout.export()` (`models` block of `out/layout.json`).
  The script takes seats, exits, pods, hubs, gun muzzle / camera, trunnions, mount muzzle length, pad list and the hulk's yaw from
  `LAYOUT.models` (`heliModel`, `heliKind`, `wreckYaw`, `mountMuzzle`); CONFIG holds the same numbers as defaults.
  In use: Mi-8 `hip_slick` x2 + `hip_upper` gunship with `hip_rotor` / `hip_tail` on their hubs, `m101` + `m101_gun`, `m2_tripod` +
  `m2_gun`, `dshk_tripod` + `dshk_gun`, `heli_wreck_dyn` (crash hulk, both sides; `mv_models.ensure_dyn()` writes the prop_dynamic
  twin), `sandbag_cover` at the M2 / DShK nests, `m113` (bridge, two roads), `m35` (bridge, road 0), `ural`, `bm21`, `zpu4`, `gaz69` x2
  (camp), `m151` x2 (firebase), `t54` (road north of the bridge, smoking), `pbr` (afloat at the marsh), `comm_station` (CT TOC),
  `nva_ammo_case*` (camp ammo point), `rs_*` foliage (46 bamboo groves, ~100 slim trees and ~20 palms with trunk clips, bushes,
  ferns, taro, nypa, 70 mangroves / nypa at the marsh, tall grass, 586 ferns / bushes along the ravines, 1 hedge bank and 4 bamboo thickets
  at the village).
  **Converted models not used** (files left in `out/addon`; reasons in `mv_models.UNUSED`): hind, huey, lssc_boat, m114_howitzer,
  m40_rr, m60_gun, mortar_m1, pbr_mcv, rocket_grad, sandbag_fort (one convex hull: its inside would be an invisible solid),
  skyraider, tent_gp (our gp_tent kept), wood_tower (our guard_tower kept), w_ak47, w_m14, w_m60, w_m79, w_rpg7.
  Procedural props the map no longer uses while the conversions are present: heli_hip, heli_hip_gun, rotor_hip, tailrotor_hip,
  wreck_hip, wreck_huey, howitzer_m102(+_gun), m3_tripod, m2_gun, dshk_mount, dshk_gun, truck_wreck, m113_hulk, pbr_wreck.
- **Camp re-laid out** (`layout.camp()`): the Mi-8's rotor disc is 836 across, so `T_PLATEAU_R` 1000 -> 1250 (`T_FOOT_R` 2050),
  pads at 870+ between masts with wheels on flat ground, no camouflage nets over pads, battery in the middle, hooches north-west,
  gully 1 now starts below the plateau. `make_detail.py` was rerun for it.
- **Guard tower**: parapet rows lie along the platform edges (four courses, a gap at the ladder), hulls = platform slab 260..266,
  parapet, roof 350..353, four legs: 84 u of headroom. Rebuilt + `lod_decimate.py`.
- **Uniforms**: `CONFIG.UNIFORMS` = the four GMod models; cache props are `mv_cache_1..7` (the map used to name them by model,
  which the script never found).
- **`check_world.py` check 7**: every entity model must exist (ours as a .vmdl under `out/addon`, stock as `<path>_c` in the pak01
  index); it also lists unused conversions. `W.big_skips` prints every large optional prop that did not fit and what blocked it.
- `create/terrain_img.py` is a libsync copy in `tools/`; `libsync.py push` also refreshed `hud_check.py`, `lod_decimate.py`,
  `panorama.py`, `test/mock_point_script.mjs` here and `lod_decimate.py` in trenchwarfare-cs2 from their masters.

**Checks, all green on 12 Nov** (run from `tools/` unless a path says otherwise)
```
python make_detail.py                                   # 27 s; "max |detail| there: 0.000000" in the protected masks
python make_map.py ../out/template.vmap ../out/addon/maps/mg_monsoon.vmap ../out/addon     # 4.5-5 min, under the watchdog
python check_mesh.py ../out/addon/maps/mg_monsoon.vmap  # 1090 meshes 0 bad
python check_world.py ../out/addon/maps/mg_monsoon.vmap [--plot out.png [x0,y0,x1,y1]]     # RESULT: clean (7 checks)
python make_radar.py ../out/addon ../out/game ; python render_board.py ../out/addon ; python mv_hud.py ../out/addon
python hud_check.py --addon ../out/addon --name mg_monsoon --states ../out/hud_states.json --out ../out/hud/hud   # 0 problems
node tools/build_script.mjs ; node test/mock.mjs 32 600 ; node test/mock.mjs 4 600 ; npx tsc -p test/tsconfig.json   # PASS, PASS, 0 errors
python create/test/api.py --strict --check projects/monsoon-cs2/out/addon/maps/scripts/mg_monsoon.js   # from cs2mapping: 0 problems
python create/libsync.py check ; python ci/check_repo.py ; python ci/check_links.py --anchors --baseline ci/known_broken_links.txt
```
Order after a layout change: `make_detail.py` (if designed ground moved) -> `make_map.py` -> checks -> radar, board -> script build
(it bakes `out/layout.json`) -> mock. Props: `MV_OUT=<abs out/addon> python build_all_props.py <names>` then `lod_decimate.py`.

**Known open points**
- Never compiled: SMD material names ending `.vmat`, multi-hull physics of the conversions, the prop_dynamic twin of `heli_wreck`,
  terrain holes, nav markup, the blend paint in the ravine beds, ravine depth at player scale (cuts up to 49 u).
- Mi-8 seat, door-gun and pod positions are measured from the SMDs but not seen with a player in them; the door gunner sits at
  the left door (x 119), the pilot in the left seat. The hulk is a small burnt light helicopter, used for both sides.
- The converted foliage and trees are placed non-solid (their hull is one convex blob); slim trees and palms get a 6-sided player
  clip round the trunk (bullets pass). `m35` has no wheels (stripped hulk). The M113s are intact, not wrecks.
- Did not fit and is missing: firebase culvert guard post, 3 antenna masts, water trailer, an M113 inside the wire, the radios at
  the two FDCs (only the CT TOC has one); `ox_cart` on road 1. The firebase interior is full: pads, pits and keep-outs cover it.
- T pad 2: the tail boom overhangs lower ground (wheels are level). Hooches on the north-west side sit on the karst skirt (sunk
  uphill, listed as `slope`).
- Older open points still stand: bunkers are solid, no bicycles, gunner ammo read-out absent by contract, double-sided sheets to
  look at in Hammer (flags, parachute_silk, gp_tent, vine_curtain; camo_net is no longer used).
- `tools/_dry.py` was never tracked and nothing imports it; `git status` shows no deleted file.

**Next steps:** 1 compile under the watchdog when the PC is free (build flow: `docs/BUILD.md`, `tools/build_monsoon.md`, deploy
dry run first); 2 Hammer pass over the list above; 3 in-game checklist (`docs/TESTING_MONSOON.md`), starting with helicopter seats
and the rotor / tail props, the M101 tube on its trunnion, the mounted guns behind their sandbags; 4 weapons (`w_*`), statuary.

**Decisions that still hold:** project name mg_monsoon, prefix mv, vis groups mv_gen / mv_user, 40 u per metre, river water z -30,
CT firebase SE on a z 620 plateau, T camp NW at z 300 under karst, 5 flags (Paddies, Bridge, Village, Temple, Crash Site), Conquest
tickets, bots as infantry with script AI for vehicle roles (DESIGN 3.5), the CC-BY Apache for CT. Shared tool files are libsync
copies. Outputs live in `out/` (gitignored); turntables in `preview/`.

## Session 1 (9 Nov 2026): research, design, generator stage 1-3, first props

- Research briefs (toolkit, cs_script API, assets, gotchas) read; design written (docs/DESIGN.md). Stock asset survey done.
- Terrain/karst/water generation working; karst reshaped from mushroom blobs to fluted pillars (side-view check `out/karst_side.png`).
- Procedural helicopters built; paint `chip` semantics are "rust above this noise level" (0.05 = nearly uniform paint); slid-back
  doors made as hull-following panels (`hull_panel`). geo.decal takes UNIT axis vectors (sizes go in the size tuple).

## Props agent report (11 Nov)

Offline only: every prop was baked and looked at in its turntable (`preview/<name>.png`); nothing has been compiled or seen in CS2.
`out/props.json` holds 117 entries, all with a vmdl. Build: `cd tools; export MV_OUT=$(pwd)/../out/addon; python build_all_props.py <names>`
(serialise with `out/build.lock`; use `python -u` under the watchdog or its log stays empty until the end).

**Fixed**
- `arms_rack_*` dropped the ammo crate's decal image (KeyError 'st'): composed props now merge child images (`dict(imgs, sign=SIGN)`).
- `mv_geo.box` gave inside-out boxes when a mirrored call passed `s * a, s * b` (negative size): corners are sorted now. It was in
  fdc_bunker, conex, dshk_mount, quad50_mount/gun, school, ox_cart, howitzer_m102(+gun), rocket_tripod/rail, heli_hip(+gun), wreck_*: all rebuilt.
- Olive drab baked rust brown on boxy props (the baker's edge mask saturates at ~0.9 on ribbed boxes): `aircraft_paint` keeps only the
  top 15 % as edges when the mean is over 0.5. Rebuilt conex, howitzer, quad50, water_trailer, fdc_bunker, drums, cans, radio, guns.
- school roof (rafters were full-height fins), arms rack sign (floated above the frame), dshk wheels (stood in mid air), ox cart wheel
  (black disc over the spokes), sampan boards (poked through the hull), wattle and wicker shaders (checkerboard -> woven strips),
  `punji_stakes` no longer gets a bounding-box hull.

**Apache** (`tools/apache_setup.py` -> `out/apache.json`): `C:\source2\projects\apache\cs2_apache` holds only README/CREDITS/preview on
this PC; the converted trees are in `content\csgo_addons\mapgames`, which the script uses as its fallback source. Copied to
`out/addon/models/vehicles/apache` + `materials/models/vehicles/apache` (60 MB). vmdl archetype is `animated_model`, so it works as
prop_dynamic and no `apache_dyn.vmdl` was needed. Measured from LOD0: nose along model +y -> `nose_yaw -90`; body 592 u, 706 with the
rotor disc; rotor radius 303, hub (0, 0, 156.5); two pylons a side at y +-64 and +-95; chin gun muzzle 153 u ahead at z 27. Seats and
muzzles are heuristics from the geometry (`*_fwd` twins are in the nose frame): check them in game. `--scale` rewrites import_scale.
`heli_huey` and `heli_huey_gun` are removed (specs, models, materials, props.json, previews); `rotor_huey` / `tailrotor_huey` are
still built (unused), `wreck_huey` stays as the hulk.

**New modules** (names as asked unless noted)
- `p_jungle`: elephant_grass_a/b/c, rice_clump_a/b, reeds, bamboo_clump, rubber_tree, log_fallen, dead_tree, vine_curtain,
  root_tangle, supply_crate, flag_pole_n / flag_pole_t / flag_pole_ct **and** `flag_pole` (written by `python p_jungle.py` after the
  three are built: flag_pole_n's meshes, archetype "", material groups t and ct -> Skin 0 neutral, 1 T, 2 CT; rerun it after any
  rebuild of the three). Grass, rice, reeds, vines: no collision. vine_curtain's origin is on the GROUND under a sagging liana at 200 u.
- `p_bridge`: truss_span (origin = deck top centre, span along x, steel 22 below, truss 158 above), bridge_pier (origin = TOP bearing
  seat: place at span end, span z - 22; 280 deep), checkpoint (road along x), french_bunker (slit +x, door -x behind a blast wall).
- `p_temple`: khmer_gate, khmer_tower (chamber 140 x 140 x 150, door +x), naga_balustrade, guardian_statue, fallen_blocks,
  stone_stairs (origin at the foot, rises 80 over 140 toward +x, ramp hull), lintel_fallen. Shader `mv_shaders.khmer_stone` (+ `laterite`).
- `p_wreck`: c123_fuselage (floor 12 u up, open ends, cargo door +y, 7 hull pieces), c123_wing, c123_engine, pbr_wreck (origin on
  the river bed, lists 17 deg), truck_wreck, m113_hulk, cargo_pallet, parachute_silk (no collision).
- Helpers added to `mv_geo` (card, sheet, vloft, rect_loop, slab_wall -> mesh + one hull per wall piece, wedge_pts, drape, limb) and
  `mv_shaders` (khmer_stone, laterite, jungle_bark, sea_camo, stripes, flag_cloth, silk, ash, cardboard; bamboo takes `live`).

**LODs**: `python lod_decimate.py ../out/addon ../out/addon mv/<name> ...` (thresholds 20/60/120/240, no vmap option used) on
bunker_large, bunker_small, cargo_pallet, checkpoint, culvert_bunker, fdc_bunker, fuel_bladder, gp_tent, guard_tower, truss_span and
the five sandbag walls. Sandbag-heavy props skip LOD1 (under 20 % saving) and get LOD2-4 (about 78 / 45 / 14 % of LOD0).
Rebuilding one of these with build_all_props overwrites its vmdl: rerun lod_decimate on it afterwards.

**Known visual weaknesses**
- The turntable z-fights on double-sided sheets (flags, tarps, parachute_silk look speckled black there); in game each side is culled.
  parachute_silk, the flag cloth and supply_crate's tarp are the ones to check first in Hammer.
- guardian_statue is blocky (reads as a stylised lion, not a sculpt); naga_balustrade's heads are plain blocks; carving everywhere is
  a baked normal relief, not geometry.
- p_guns are simple box-and-cylinder guns; howitzer_m102's trail still bakes brown; water_jar and haystack are faceted.
- Foliage cards have straight bottom edges 2 u under the origin: they show on steep slopes. rubber_tree's crown is 46 flat cards.
- truss_span's paint is mostly rust (same edge-mask effect, left as "rusty"); french_bunker's roof aggregate is coarse.
- c123_wing's flap and pitot lie loose beside it; c123_engine's cowling is a black half shell.
- Hulls are boxes: c123_fuselage's rounded upper corners, the truss diagonals above 44 u and the tower's tier steps are approximated.

## Presentation agent report (11 Nov)

Details, regenerate commands and the in-game checklist: [docs/HUD.md](docs/HUD.md). Everything below is **simulated** only.

- `tools/sounds.py`: 41 synthesised wavs, 21 `mv.*` events merged into `soundevents_addon.vsndevts` (block `mg_monsoon`). Numeric
  listen-check clean (`out/sounds_report.json`): all peaks -0.72 dBFS, the 4 loops wrap with a step below their own 99.9th percentile
  sample step. Stingers (`mv.capture`, `mv.flag_lost`, `mv.radio_blip`) are flat events: everyone hears them. `mv.rocket_fly` is a 4 s one-shot.
- `tools/make_radar.py`: radar 1024 px from layout.py, square +-6400 (pos -6400 / 6400, scale 12.5), vtex + `out/game/resource/overviews/mg_monsoon.txt`.
  Also the map renderer (`render_sat`, `render_topo`) the board and slides use. Terrain raster cached in `out/cache` by layout.py's hash.
- `tools/render_board.py`: `mv/board.png` (north up, 640 px on screen, 4 px per step), 3 loading slides, helicopter map icon.
- `tools/make_sky.py`: `maps/mg_monsoon_3dskybox.vmap` (64 terrain sheets, 33 far karst towers, 2212 trees), check_mesh 0 bad.
- `tools/mv_hud.py`: 103 panel ids = docs/SCRIPT.md's HUD contract exactly; `hud_check.py` clean over 8 states at 1920 and 2333;
  `node test/mock.mjs 32 300` PASS with the xml / css / `out/hud.json`.
- Differences from the brief, all because the contract has no id for them: no gunner ammo read-out; the board is one north-up
  picture for both teams (`board_t.png` / `board_ct.png` are written but unused); `mv_status` sits under CS2's radar, not bottom
  left (that is the chat box).
- layout.py changed under this work (bases re-laid out): the radar, board and slides were re-run at the end; re-run them after any later change.
- Not done: nothing compiled with resourcecompiler; the horizon and heading-tape constructions have no in-game precedent in this repo.

## World agent report (11 Nov)

Offline only (generated, checked with `check_mesh.py`, `check_world.py`, top-down plots, the mock): nothing compiled or seen in CS2.

**Files**: `tools/mv_places.py` (stage 4), `tools/mv_entities.py` (stage 5), `tools/mv_stock.py` (stock model table, measured bounds,
fallbacks), `tools/check_world.py` (validation + `--plot out.png [x0,y0,x1,y1]`), edits in `layout.py`, `mv_terrain.py` (32-u tiles round
the tunnel portals and the farm), `make_map.py` (entities.json / layout.json now go to `out/`). Build 7-8 min (terrain 105 s, places
~150 s: `layout.height` per prop is the cost). `python check_world.py ../out/addon/maps/mg_monsoon.vmap` -> clean.

**Layout changes (needed, real prop sizes)**: CT plateau 760 -> 1200 (foot 2250), T plateau 700 -> 1000 (foot 1800); `firebase()` and
`camp()` laid out again (pads, pits, bunkers, FDC, tower, fuel, hooches, spawns; gate where road 0 crosses the wall); camp tunnel
portal moved to the east edge (the old one sat on rocket pit 1), galleries + chamber follow; flag A moved 50 u onto a dike junction;
flag B stands on the bridge deck (`BRIDGE_DECK_Z` 56, `flag_z()`), its spawns at both bridge heads; temple DShK moved to the east side
of the courtyard; `FLATS` (farm terrace); craters and gully 0 kept off the plateaus. `export()` adds `terrain` (128-u height grid),
`mountinfo` / `mounts` (from `out/mounts.json`, written by mv_entities), `tunnels`, `bridge`.

**What exists** (5743 prop_static, 123 models; 1620 optional props skipped by the placer):
- Firebase: 3-layer sandbag perimeter (57 u) with a player clip above, open at the gate and two sally gaps (blast wall inside each),
  6 dug-in bunkers (terrain cut out under their floors), 3 M2 nests on the wall, 3 howitzer pits (2-layer rings r 232, racks + shells
  outside the entrance), FDC bunker + plot table, ammo point, 3 PSP pads (scale 0.72), TOC tent + 2 masts, tower with an invisible
  ladder volume, quad-50 ring, fuel bladder + drums, culvert guard post, signs, latrines, water trailer.
- T camp: 3 Hip stands under scaled camo nets, 4 rocket pits and 2 DShK pits in swept earth berms (world geometry), FDC hut + table,
  5 hooches, ammo stacks, 3 cook fires (particles), propaganda boards, punji patches beside the approaches.
- Tunnels: one closed 16-u grid mesh (1060 cells), floor ~150 under the ground, 25-degree ramps in open cuts at the 3 portals
  (110 terrain cells removed, a 6-u step at each mouth), chamber with caches, arches where the roof starts, 13 unshadowed lamps,
  probe volume, Low hint.
- Flags: A dike junction + farm terrace (3 hooches, pens, well, cart, fence), sunken sampan in the oxbow; B two truss spans, pier,
  concrete abutments + 200-u earth ramps (world geometry, 12 degrees), checkpoint north, French bunker + neutral M2 south; C school,
  6 hooches, well, shrine, stalls, fences, palms, fires; D two stone terraces + 6 stairs (world geometry), tower, gate, DShK, nagas,
  lions, rubble, banyans; E C-123 fuselage / wing / engine (fire, smoke), 69 rubber trees in rows, pallets, parachutes.
- Waterfall (water_wall sheets, 8 noise-deformed boulders with rock/moss paint, foam particles, clip), marsh (330 reeds, 30 dead
  trees, PBR, sampan), sniper nests on the 3 landable karst tops, clip cylinders round all 8 towers, wrecks / logs along the roads,
  crater stones. Jungle: 977 banyans, 50 palms, 8 bamboo, 1310 understorey, 807 ferns, 1338 elephant grass, 178 rice clumps.
- Weather (fxkit): 7 rain particle systems (flags + bases, `mv_rain_N`), `mv_lightning` timer + faint env_fade.
- Entities: every CONTRACT name (401 checked) + `mv_flag_snd_<a..e>`; 8 mounts (3 M2 + quad-50 CT, 2 DShK T, bridge M2 and temple
  DShK neutral); 15 WALKABLESEED seeds, 85 NONAV boxes (steep, karst, deep river except fords at the bridge / A / marsh, outside the band).
- create/ tools used: primitives (box, wedge, stairs, sweep, cylinder, arch), meshedit (subdivide, noise), fxkit (weather_tiles,
  lightning). Not used: gen_buildings (the buildings are props), gen_world, gen_kits, matkit (stock materials sufficed), gen_light
  (it writes a whole sun / sky preset; the combined probe volumes already bake cubemaps), no painted detail heightmap.

**Known weak spots / for the Hammer pass**
- guard_tower: its hull platform top is z 300 under a roof hull at 350 (50 u headroom: a player cannot get in), and the platform
  sandbag rows stick out radially (bounds +-166). The ladder volume reaches 314. Needs a props fix (platform hull 260..266, rows turned).
- Bunkers are solid hull boxes: nobody enters; the M2s are on tripods in nests beside them. khmer_tower chamber / C-123 interior /
  French bunker rely on the props' hulls.
- truck_wreck is 135 wide on a 160 deck, so it stands beside the south ramp, not on the bridge. No bicycles (stock bike is loose
  parts). No path behind the waterfall, no gallery through the temple knoll, no roof access in the village, village has 6 of 9 hooches
  (road and spawn keep-outs), camp has no sampans.
- Double-sided sheets to look at in Hammer: flag_pole flags, camo_net (scaled 1.6 x 1.6 x 1.6), parachute_silk, gp_tent, vine_curtain.
- Props on slopes use the lowest ground under their footprint (uphill side buried); 893 props are listed as deliberately off the
  ground (stacked bags, platform / deck / karst / tunnel props, sunk trees) in `out/world_sites.json`.
- Valley-floor woodland is thin by design of `layout.jungle()` (a 30 % fill was added); only trunks are in the placer, crowns overlap.
- Unverified in engine: func_nav_markup NONAV boxes (key `navProperty_NavGen NONAV`), the ladder material volume, rain particle
  cost, lightning env_fade (alpha 26, also seen in the lobby and tunnels), terrain holes under bunkers.
- `mv_cache_*` holds 4 models (wrecks, rocket, shell): add uniform model paths to `out/cache_models.json` (a list) when they exist.
- `layout.mountinfo` is an object keyed "1".."8" (the script indexes it by mount number); the same entries are the list `mounts`.
