# Working notes (AI session log)

Read this first when resuming. Newest state at the top. Design: [docs/DESIGN.md](docs/DESIGN.md).

## Resume here (paused 9 Nov 2026, ~03:40 ACDT, usage budget ran out)

**What exists and works (verified offline only, nothing has been in CS2 yet):**
- `tools/layout.py`: the whole valley as functions (river, terraces, bases, karst, paddies, roads, gullies, oxbow, craters, flags,
  POIs, masks for jungle/grass/clearings/paint, `export()` -> `out/layout.json`). `tools/preview_layout.py out.png [cell]` draws it.
- `tools/mv_terrain.py` + `tools/make_map.py` stage 1-3: terrain tiles (672 tiles, 52k quads, vertex-painted Ancient mud/grass blend),
  8 karst towers (fluted pillars, rock/moss blend), river / upper river / marsh / oxbow / paddy water sheets, sky shell, edge clips,
  lightmap shells, environment (sun, sky, fog, probes, soundscape, 3D skybox reference, hints), lobby + banner + 64 spawns +
  script/HUD/params entities. Output `out/addon/maps/mg_monsoon.vmap` (48 MB), `check_mesh.py`: 0 bad meshes.
  Run: `cd tools && python make_map.py ../out/template.vmap ../out/addon/maps/mg_monsoon.vmap ../out/addon`
  (`out/template.vmap` = a copy of `content\csgo_addons\addon_template\maps\xxx_mapname_xxx.vmap`; 55 s).
  `mv_places.py` (stage 4) and `mv_entities.py` (stage 5) are stubs: no dressing, no gameplay entities yet.
- Props (`MV_OUT=<abs path to out/addon> python build_all_props.py <names>`; list = toolkit.json modules; specs are lazy callables):
  - `p_heli.py`: heli_huey, heli_huey_gun, heli_hip, heli_hip_gun, rotor_huey, rotor_hip, tailrotor_huey, tailrotor_hip, wreck_huey,
    wreck_hip: built and reviewed (turntables in `preview/`). **User decision: reuse the CC-BY Apache instead of the procedural Huey
    for the US side** (`C:\source2\projects\apache\cs2_apache`: vmdl, 5 LODs, rotor bones with idle/spin_slow/spin anims, 2 hulls,
    3 materials; credit text in its CREDITS.txt). Reason the Huey was made: the design is 1968 and a procedural model is original IP;
    not a dire reason, so: Apache for the CT helicopters (SetAnimation spin / spin_slow instead of the split rotor props; its origin
    is on the ground under the mast, ~710 u long, rotor ~605 u; use `import_scale` ~0.8 in the vmdl if it dwarfs the pads), keep
    the procedural Hip for T unless a CC-BY Mi-8/Mi-24 GLB turns up (then `glb2cs2_multi.py`). Drop heli_huey* from toolkit/props.
  - `p_arty.py`: howitzer_m102 + howitzer_m102_gun (elevating part, origin = trunnion), rocket_tripod + rocket_rail + rocket_122,
    shell_105, ammo_rack_105, rocket_crate, plot_table, plot_table_t: built, not yet reviewed in turntables.
  - `p_guns.py`: m2_gun, m3_tripod, dshk_gun, dshk_mount, quad50_mount, quad50_gun, m60_gun, pk_gun: meshes smoke-tested, NOT built.
  - `p_base.py`: 27 props (bunkers, fdc_bunker, psp_pad, gp_tent, conex, guard_tower, fuel_bladder, drums, water_trailer, latrine,
    antenna_mast, cans, crates, radio, jerry can, rucksack, arms racks, signs, culvert_bunker, cot): a background build was running
    when we stopped (25 of 27 written, `out/logs/build_base.log`; `ammo_crate` failed with `KeyError: 'st'`: its decal image dict is
    returned by `ammo_crate()` but `arms_rack` calls it and drops the dict -> give `_two` the images or inline the decal; same
    pattern to check in `arms_rack_*`). Re-run `build_all_props.py ammo_crate arms_rack_ct arms_rack_t` after the fix.
  - `p_village.py`: 23 props written; hooch_a/b/c smoke-tested; the rest untested (a seed-overflow bug in `bamboo_pole` was fixed
    last thing, re-run the smoke test: `python -c "import p_village; [f() for f in p_village.specs().values()]"`).
  - `p_jungle.py`, `p_wreck.py`, `p_bridge.py`, `p_temple.py`: empty stubs (`specs()` returns {}). Design lists what they hold.
- `mv_shaders.py` (aircraft paint, glass, rubber, aluminium, interior, tarp, concrete, thatch, bamboo, PSP with alpha holes, foliage
  cards), `mv_geo.py` (lofts through rounded sections, hull-following panels, cylinders, plates, decal text/star images).
- `create/build_all_props.py` master now accepts callable (lazy) specs; pushed to monsoon-cs2 and trenchwarfare-cs2 copies.
- `out/vpk_index/cs2_index.pkl`: pickled index of `game\csgo\pak01_dir.vpk` (tools/vpkdir.py). Map VPKs hold only compiled world
  nodes; all shared props/materials are in pak01 (Aztec banyans/ferns, Anubis palms, 80 hr_ancient blend materials).

**Not started:** places (stage 4: firebase, camp, flags, village, temple, crash site, bridge, paddies dressing, jungle scatter,
tunnels, nav seeds/NONAV markup), script entities (stage 5), the cs_script (`src/`), HUD, sounds, radar, FDC board render,
3D skybox map, mock + tsc tests, docs (README_ADDON, TESTING, CREDITS, compliance), player-model copies, weapons.

**Bots (user requirement, 9 Nov):** low-pop play needs AI. Plan recorded in DESIGN.md section 3.5 to be written: CS2 bots as
infantry on a nav confined with `func_nav_markup` NONAV volumes (the FGD has WALKABLESEED / NONAV / NONAVNONSOLID / NONAVSPACE and
`func_nav_blocker`) over jungle slopes and karst, seeds at bases/flags/roads; script-driven AI for the vehicle roles (bot pilots fly
patrol/strafe routes, bot door gunners shoot, bot crews auto-lay and fire at marks), bots drawn into roles when a team has fewer than
N humans; mg_trenchwarfare's FPS drop with a 44k-area nav is the risk, hence the NONAV confinement.

**Other decisions this session:** project name mg_monsoon, prefix mv, vis groups mv_gen/mv_user, 40 u per metre, river water z -30,
CT firebase SE on a z 620 plateau, T camp NW at z 300 under karst, 5 flags (Paddies, Bridge, Village, Temple, Crash Site), Conquest
tickets. Shared tool files are libsync copies (`python create/libsync.py check`).

**Where things are on the PC:** repo `C:\source1\cs2mapping\projects\monsoon-cs2` (this folder); outputs in `out/` (gitignored):
`out/addon` (content tree), `out/props.json`, `out/logs`, `out/entities.json`, `out/layout.json`, `preview/` turntables. Nothing
copied to `content\csgo_addons` yet. The cs2port worker folders that cluttered `C:\source1` were moved to
`C:\source1\archive\cs2port_workers_20261109\` (cs2port_w2..w5, untouched otherwise).

**Next steps in order:** 1 fix ammo_crate/arms_rack decal dict, finish p_base + p_village builds, review turntables; 2 swap the CT
helicopter to the Apache, remove heli_huey*; 3 p_jungle (grass/rice/bamboo cards), p_bridge, p_temple, p_wreck; 4 mv_places.py
(start with the firebase and one flag, check with vmap_preview.py); 5 mv_entities.py + the script skeleton from mg_trenchwarfare's
(roles, spawn flow, HUD cache, pools), then heli flight (DESIGN 3.2), artillery (3.3), conquest (3.4); 6 mock/tsc; 7 compile
under the watchdog when the PC is free (mg_trenchwarfare's build_maps.ps1 flow), in-game TESTING checklist.

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
