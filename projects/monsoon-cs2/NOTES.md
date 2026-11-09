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
