# World review 1 (12 Nov 2026): gameplay and world checks on the user's map

Remaster plan step 2. Offline only: everything here is **simulated** (`docs/reference/compatibility.md`). Nothing was compiled, opened in
Hammer or played. The map is the user's `content\csgo_addons\mg_trenchwarfare\maps\mg_trenchwarfare.vmap` (29 Oct, 67.2 MB, = tw34). It was
only read. Every fix below is a **proposed guarded delta patch** for step 5. Nothing was patched.

## Tools

| Tool | What it does | Runtime |
|---|---|---|
| `create/check_play.py` (new, a neutral fork of monsoon's `check_play.py`, registered in `create/libsync.json`) | Rebuilds the scene from the vmap and walks it on a 16-u grid. Checks: walkability, routes, sightlines, cover, clipping, water, terrain and nav. Project specifics come from an `Adapter` subclass | (through the adapter) |
| `tools/check_play.py` (new): the trench adapter | Defines the trench worlds and the round-start / unlocked states. Adds T1 depth, T2 fire steps, T3 ladders, T4 dugouts, T5 no man's land, T6 mortar pits, T7 runways and plane lanes, T8 spawns | 40 s cold (scene build), about 20 s with the scene cache |
| `tools/check_world.py` (new, adapted from monsoon) | Covers: the names the script looks up and their classes; the mortar fire target; singletons; entities outside the sky shell or lobby; hull-box overlaps; I/O wiring; class counts; models (content `.vmdl` + game `.vmdl_c` + pak01 VPK, stale compiles); `prop_dynamic` archetypes | 5 s |

```
cd projects/trenchwarfare-cs2
python tools/check_play.py [--only 1,6,T2] [--map out/review/x.png x0,y0,x1,y1]   # -> out/review/check_play.json
python tools/check_world.py                                                       # -> out/review/check_world.json
```

How the grid models the map:
- **Two states.** "Closed" is the round start: the `woodsopen` / `undergroundopen` props block. "Open" is with them removed.
- **Worlds.** `t` and `ct` are the 20 posts plus 3 dressing stations of each side. There are 10 mortar pits, the lobby, the woods clearing
  and the mine galleries.
- **Physics hulls.** Each `PhysicsHullFile` is modelled as a convex hull: all 96 of ours use `SingleHull`, and that is what the compiler
  builds. Monsoon's original reads the raw hull triangles instead (see "Notes for monsoon").
- **Stock props.** Their bounds were measured from pak01 with `create/s2/bounds_batch.mjs`. Trees collide as trunks, foliage does not
  collide, everything else is a box at 80 % of its bounds.

## Validation before trusting the counts

1. **Synthetic known-good map.** I built it with `vmapgen` from `tools/box_template.vmap`; the scratch builder is not in the repo. It has a
   ground slab, a dividing wall, a ramp onto a platform beside a walled 128 x 128 pit, a tower with a ladder volume, a water slab 8 u over
   the ground, and three sandbag props: on the ground, 40 u up, and 30 u under. The check found exactly what was built:
   - both sides whole and kept apart; the tower top reached by the ladder (route 520 u);
   - one pocket of 16 128 u2 with no way out by a jump;
   - 0 of 4 sightlines through the wall;
   - floating 39.9 u, buried 1.0 (one each);
   - the water slab's whole edge exposed (52 points).
2. **False positives found on the real map and fixed in the tools before the counts below:**
   - Raw hull triangles let players walk into a SingleHull arch. Now convex.
   - A 16-u cell misses thin supports: a sandbag resting on a 4-u plank lip read as 77 u floating; 249 such cases. Props the grid flags
     are now re-tested on 5 x 5 exact terrain samples plus the other props under them. 249 dropped to 3, and those 3 are real.
   - The lobby 2900 u below gave stumps a "support" there. Supports are now limited to 400 u below the prop.
   - Ground over a prop's top (a sap roof) counted as burying it. It no longer does, unless nothing is under the prop.
   - Water edges 1-3 u over the wall foot, behind revetments, were counted. They now need more than 3 u (2566 points became 183).
   - The fire-step line test hit tree trunks and traverse corners. It now takes the best of five straight lines forward.
   - Path slopes were measured on the shelter roofs. Paths now use the terrain.
3. **Checked by hand:**
   - The sap barricade and the shelters, in top-down renders (below) and column probes.
   - The blocker and mortar archetypes, by reading their `.vmdl`.
   - The woods seed positions against the fence cells.
   - The post/barrel distances from entity origins.

## Results

| Check | Result |
|---|---|
| 1 worlds (closed state) | `t` 20/23 and `ct` 20/23 points together. The 3 dressing stations per side are inside the solid shelters (M1). `pit_t_2` is split (L1). Lobby 64/64, woods and mines whole |
| 1 separation | Held: t/ct, t/ct vs woods, t/ct vs mines, each side vs every enemy pit |
| 1 targets (open state) | Woods reached by both sides. **Mine galleries reached by neither** (H1) |
| 1 pockets | 1, at (-1640, 2880, -73), 1536 u2. A jump gets out (L11) |
| 1b routes | t / ct to the woods 1825 / 1834 (ratio 0.99); to the enemy woods half 3039 / 3048 (1.00). To the chamber: no route (H1) |
| 2 sightlines | Enemy fire-step eyes to deploy posts: 0/760 both ways. To mortar crews: 60/380 (CT crews), 11/380 (T crews) (L6) |
| 3 cover | Woods T half 5 head-height pieces, CT half 10 (M5) |
| 6 clipping | 38 buried (17 are user benches, H1), 3 floating (user benches, H1), 4 under water, 6 candles inside shelters (M1). 81 buried and 7 floating are by design (stumps, helmets, debris, rocks; ladders, lanterns, propellers) |
| 7 water | 183 edge points more than 3 u over the ground, in 29 places; 15 z-fight cells (L5) |
| 8 terrain | Trench floors max 1.3 deg; 8 terrain hole cells, all covered |
| 9 nav | 25 seeds, **4 off the walkable world, and the seeds flood 654 758 cells** (H3); 0 NONAV; 2 ladder volumes with ground at both ends |
| T1 depth | Floor-to-cover median 105 u, minimum 85 u; no floor spot seen from an enemy fire-step eye |
| T2 fire steps | 150 checked, all reached from the floor with a jump. Eye over the parapet: T median 15 u (minimum 8), CT median 9 u (minimum 2) (M7) |
| T3 ladders | 2 woods climb volumes, ground at the bottom and top. 12 fire-bay ladder props are decorative (L9) |
| T4 dugouts | 6 shelters, 0 enterable (M1) |
| T5 no man's land | 0 walkable cells for either side in either state; 223 wire props in no man's land, 0 on a trench floor |
| T6 mortar pits | 10 pits, each closed off from its trench (crews are teleported); tube, table and ammo box present; tubes are `prop_static` (H4) |
| T7 air | 10 air spawns clear within 300 u; 2 lanes cross poplar crowns (L7). Nothing above z 2900 (the script's ground trace starts at 3000). Parked planes on flat ground (relief 1-6 u), no solid prop inside them |
| T8 spawns | Lobby 64 fine. 2 posts stand in a barrel (M3) |
| world 1 names | 352 expected, 10 wrong: `mortar_<tg>_1..5` missing (H4) |
| world 2 singletons | `info_map_parameters` x2 (M2) |
| world 3 bounds | 0 entities outside the sky shell and lobby (the script pools under the lobby are expected) |
| world 4 overlaps | 2919 solid props with hulls; 11 pairs outside the by-design list (L8) |
| world 5 wiring | 0 dangling outputs |
| world 7 models | 97 ours + 44 stock, 0 missing, 0 uncompiled; 4 compiled before their last `.vmdl` edit (L10) |
| world 7b archetypes | **4 `prop_dynamic` on `static_prop_model`: all four unlock blockers** (H2) |

## Findings, by severity

Severity:
- **high**: a feature does not work, or a check fails at its root.
- **mid**: a player can get stuck, or something is visibly or measurably wrong.
- **low**: cosmetic, a check approximation, or by design.

"Owner" says who made the object, from its vis group:
- `tw_gen`: ours; it may be auto-fixed by a guarded patch.
- `tw_user` / ungrouped: **the user's**; flagged for the user, never auto-fixed.

Ids are element indices (`mapdigest` "i"). They hold until the next Hammer save, so every patch also matches on class, model and origin
within 2 u.

### High

**H1. The mine galleries never open: a bench barricade in both sap mouths outlives the unlock.**
- **Where.** Twelve `tl_bench` props per side, each side as a low row and a stacked upper row. Ids 56-63 and 6615-6624. They fill x ±2107..2204,
  y -2810..-2839, z -99..+16, right behind the `undergroundopen` planks.
- **What the script does.** It removes only the entities named `undergroundopen`.
- **Result.**
  - Once open, neither side reaches the landing or chamber seeds; there is no route to the chamber.
  - The low row is 17-20 u high, over the 18-u step. Standing on it leaves about 57 u under the upper row, so only a crouch-jump might
    get through.
  - Renders: `01_sap_t_benches.png`, `02_sap_ct_benches.png`. The trench world stops at the benches, and the galleries world starts beyond them.
- **Owner.** `tw_user`: **flag for the user.**
- **Proposed patch (the user chooses).** Either
  - set `targetname undergroundopen` on the 24 benches (match id + `tl_bench` + origin), so the unlock removes them too; or
  - drop the low row (12 ids).
- **In-game check.** After "THE MINE GALLERIES ARE OPEN", walk and crouch-jump into each sap.

**H2. Every unlock blocker is a `prop_dynamic` on a `static_prop_model` model.**
- **Where.** `models/tw/revet_planks_broken.vmdl` and `revet_planks_broken_128.vmdl` both say `model_archetype = "static_prop_model"`.
  - Ids 7979 (-2144, -2808, -96) and 7980 (2146, -2806, -112): `undergroundopen`, ungrouped (the user's).
  - Ids 7982 (1784, 2792, -72) and 7983 (-1800, 2792, -88): `woodsopen`, vis group woodsopen (made by `patch_unlocks.py`).
- **Why it matters.** Monsoon's BUILD.md says such props are DELETED at map compile. BUILD_LOG_1 calls that unconfirmed for this compiler.
  If it is true, both areas are open from round start.
- **Evidence.** None either way: the only trench build log (27 Oct, UTF-16, a failed lightmap pass) has no DELETED lines.
- **Proposed patch.** Add `_dyn` twin vmdls with archetype `""` (as the planes have), then set `model` on the 4 ids (match on name, class
  and origin).
- **Owner.** Ours for the woodsopen pair; **flag the undergroundopen pair** for the user.
- **Check.** Grep the next compile log for `DELETED`; in game, confirm the planks stand at round start.

**H3. Four woods nav seeds are outside the clearing fence. Likely cause of the 44 160 nav areas.**
- **Where.** `WALKABLESEED` boxes in tw_nav at x -1226..-1194 and 1194..1226, y 3684..3716 and 4134..4166.
- **What is wrong.** The fence's blocked cells are at |x| 1160..1192. The clearing's walkable cells start at |x| 1144. So the seeds lie
  30-50 u out, in the open forest.
- **Size.** From the seeds, the walk graph floods 654 758 cells: the whole terrain, no man's land, the airfields. Every play world together
  (both trench systems, the pits, the lobby, the woods and the mines) is about 25 000 cells.
- **Caveat.** If the nav generator, like this check, treats player clips as walls, these four seeds alone explain the nav size. Then the
  question is not whether NONAV applied.
- **Proposed patch.** Move the 4 seed meshes inward to |x| 1110 (match the markup mesh by its bounds).
- **Owner.** Ours.
- **Check.** Nav area count after the next compile. Renders: `03_woods_seeds_t.png`, `04_woods_seeds_ct.png`.

**H4. The mortar tubes cannot play the fire animation.**
- **Where.** There is no `mortar_<tg>_1..5` in the map. The 10 tubes are unnamed `prop_static`:
  - minenwerfer for T, ids 3651, 3718, 3786, 3853, 3921;
  - mortar_58mm for CT, ids 3989, 4056, 4124, 4191, 4258;
  - all at x ±3200, y -1600 / -800 / 0 / 800 / 1600.
- **What is wrong.** Both models are `static_prop_model` with no animation at all, so even a `prop_dynamic` has no `fire` sequence to play.
- **Proposed patch.** Step 6: a `_dyn` twin of each tube with a short recoil `fire` sequence. Step 5: re-class the 10 ids to `prop_dynamic`
  named `mortar_<tg>_K` (match class + model + origin). Until then the script's `SetAnimation` (src:921) goes nowhere. That is harmless,
  but no recoil shows.
- **Owner.** Ours.

### Mid

**M1. The shelters are solid lumps: dugouts cannot be entered.**
- **Where.** `models/tw/shelter` has one hull file (`SingleHull`) shaped as an arch. The compiler wraps it in one convex hull, so the inside is
  solid. Six shelters: ids 1688, 1693, 1698, 2729, 2734, 2739, at x ±2238, y -1056 / 576 / 2304.
- **What is wrong.**
  - `heal_<tg>_1..3` (x ±2214) lie inside the hull (headroom 0, or 51 u even with the raw arch).
  - The stretchers and 6 candle clusters inside cannot be reached.
- **What still works.** Healing, because HEAL_RADIUS 120 reaches the support trench 64 u away.
- **Proposed fix.** Rebuild the shelter hull as separate convex pieces (left wall, right wall, roof, back), as `hangar` does with 5. That is
  an asset change in step 6. No map patch is needed.
- **Owner.** Ours.
- **Check.** In game, walk into the dugout at `heal_t_1`. Render: `05_shelter_t_1.png`.

**M2. Duplicate `info_map_parameters`.**
- **Where.** Id 7 at (512, 328, 32) is ungrouped, with no name and buying 0. The other is `tw_params` (tw_gen).
- **Proposed patch.** Drop id 7 (match class + origin).
- **Owner.** Ungrouped, probably the template's leftover: **flag for the user before dropping.**

**M3. Two deploy posts stand inside a barrel.**
- **Where.**
  - `trench_t_1` (7182, at -1649, -2752) has `tl_barrel` 1727 at 22 u.
  - `trench_ct_13` (7217, at 1649, 1856) has `tl_barrel` 2811 at 15 u.
- **What is wrong.** The barrel radius is about 11 and the player half width 16, so a teleported player overlaps the barrel by 5-12 u.
- **Proposed patch.** Move each barrel 40 u along the bay, away from the post (match id + model + origin).
- **Owner.** Ours.
- **Renders.** `06_post_t_1_barrel.png`, `07_post_ct_13_barrel.png`.

**M4. The woods ladders' nav bottom (the compile's "Unconnected ladder #1/#2 bottom").**
- **Where.** The climb volumes at x ±1716, y 2900-2912, z -72..22 are ungrouped (the user's).
- **What the check found.** Each has 17 walkable floor nodes at its bottom (floor -73 / -68; the volume starts within 1-4 u of it) and ground
  at the top.
- **Probable cause.** The bottom sits beyond the woodsopen blocker at y 2792, so at nav-generation time it is a dead end the generator does
  not join. There is also a one-way drop pocket beside it (L11).
- **Proposed fix.** Step 4: a nav ladder link, or extend the volume 16 u down and toward the trench. The volumes are the user's: **flag.**
- **Render.** `10_woods_ladder_t.png`.

**M5. Woods cover is uneven.**
- **Where.** Within 600 u of each half's centre (x ±605, y 3930): T has 5 head-height pieces, CT has 10. The walking routes are even (0.99).
- **Proposed fix.** Step 5: mirror the CT half's cover pieces into the T half (tw_gen props, by id). First check whether the two trees the
  user moved (NOTES tw6) are the difference.

**M6. The CT fire steps see less than the T fire steps.**
- **What the check found.**
  - The eye clears the parapet by a median of 9 u on CT and 15 u on T. The CT step tops are at about -36, the T ones at about -30.
  - Five CT steps at x 1575, y -576..-320 clear by 2.1 u: a player there can barely see over.
- **Proposed patch.** Raise those 5 firestep props 6 u (tw_gen; match id + model + origin), or all 75 CT steps for parity. Re-run T2.
- **Render.** `09_ct_firesteps_low.png`.

### Low

**L1. `pit_t_2`: the seats are not joined on the grid.**
- **Where.** Stock `ammo_artillery_small_01` (id 3723, at -3361, -789) lies between seat a and the breastwork.
- **Why it may be the check.** The gap is 35-43 u for a 32-u player, and the stock prop is approximated as a box.
- **Check.** In game, walk from `mortarcrew_t_2_a` to `_b`. If it is blocked, move the shells 20 u west.
- **Render.** `08_pit_t_2.png`.

**L2. Upper bench row floating 56 u.** The user's ids 56, 62 and 63, part of H1.

**L3. Buried more than 35 %.** Cosmetic (tw_gen); lift or leave:
- `log_fallen` x8, worst id 2270 at (802, -1572) 72 %;
- `sandbag_wall_b` x3 in the T pits, id 2609 (-3159, 610) 72 %;
- `shell_pile` x5, `crate_shells` 2324, `wreck_wheel` 1956, `wire_fence_a` 6515, `wire_coil` 1929, `sandbag_wall_a` 2543.

**L4. Props under water.** Lift or move: debris 2376 (829, -3135) and 2383 (386, -1610); poplar 4458 (-637, -3582) 8.7 u; `tunnel_set` 6276
(-1297, -3272, -259) stands in 12 u of water inside a gallery.

**L5. Water edges and z-fight.**
- 183 edge points stand more than 3 u over the ground. The worst places are the fire-step foot at (-1575, -1145) and (1827, -2192).
- 15 z-fight cells in 3 no man's land places: (904..936, -1928..-1960), (1128..1144, -3352..-3384), (1240..1288, -920..-936).
- Proposed patch: lower one sheet of each overlapping pair by 1 u (tw_gen mesh, matched by bounds).
- Render: `11_nml_zfight.png`.

**L6. Mortar crews in the enemy's direct line at about 4800 u.** 60/380 eye pairs for the CT crews and 11/380 for the T crews.
- Option: one more sandbag course on the enemy-facing breastwork.
- This is a game-design call; script cover (TRENCH_COVER) already applies to shells, not rifles.

**L7. Air-spawn lanes on CT spawns 2 and 3.**
- Poplar crowns (`tree_poplar_mature_02`, tops 1034 and 1090 at x ≈ 4040-4160, y -360 / 0) stand 1400-1500 u ahead at spawn height 1106-1110.
- Crowns probably have no collision, so the risk is only PULL UP warnings.
- Option: remove those trees, or raise AIR.SPAWN_ALT to 1300.

**L8. Overlap pairs.**
- `field_telephone` 13 (the user's) is into firestep 2559: flag.
- `log_fallen` 3356 is into revet 2300.
- `wreck_wheel` 3043 is into `wreck_fieldgun` 3041 (by design).
- 8 `petrol_can` inside the hangar's 5-hull union box: a check artefact, not a finding.

**L9. 12 fire-bay ladder props without climb volumes.** By design: the clips keep infantry in the trench.

**L10. Stale compiles.** `wire_coil`, `wire_fence_a`, `wire_fence_b` and `ladder` have a `.vmdl` newer than their `.vmdl_c`. Recompile in step 9.

**L11. Pocket at the woods ladder foot** (-1640, 2880, -73), 1536 u2. It is a one-way drop and a jump gets out.

## Patch list for step 5 (guarded, via `tools/patch_guard.py`)

| Patch | Targets (match on) | Ours or flag |
|---|---|---|
| Woods seeds inward | 4 `func_nav_markup` meshes by bounds | ours |
| Blocker models to `_dyn` twins | ids 7982, 7983 (name, class, origin); 7979, 7980 | ours / **flag** |
| Mortar tubes to `prop_dynamic mortar_<tg>_K` (after step 6 makes `_dyn` + fire) | 10 ids by class + model + origin | ours |
| Barrels off the posts | ids 1727, 2811 | ours |
| CT fire steps +6 u | 5 (or 75) firestep ids | ours |
| Sap benches | 24 `tl_bench` ids | **flag** (H1) |
| Second `info_map_parameters` | id 7 | **flag** |
| Water z-fight, buried / under-water props | as listed | ours |

## Notes for monsoon (not changed: another session owns `projects/monsoon-cs2`)

- Monsoon's `check_play.py` reads hull SMDs as raw triangles. The compiler wraps each `SingleHull` file in one convex hull. A concave hull
  file (an arch, an L) would be walkable in the check but solid in game. The neutral `create/check_play.py` models the convex hull.
- Monsoon's own map is affected only if one of its hull files is concave; re-run its `check_play` through the neutral fork to see.

## Step 5 results (12 Nov 2026): guarded patch `tools/patch_world_1.py`

Offline only, so everything is **simulated**. No model was compiled, no map was opened in Hammer, nothing was played. The input map was
only read (CRC 2e3f90d0 before and after). The addon was not written to.

```
cd projects/trenchwarfare-cs2
python tools/dyn_models.py                         # dynamic twins -> out/addon/models/tw/... (list: out/step5_models.txt)
python tools/patch_world_1.py [--user-m2] [--user-w5] [--render]   # -> out/mg_trenchwarfare_patched.vmap (--user-h1: not for this map)
python tools/patch_guard.py <input.vmap> out/mg_trenchwarfare_patched.vmap out/step5/patch_world_1.targets.json --strict
python tools/check_world.py out/mg_trenchwarfare_patched.vmap --stage out/addon
python tools/check_play.py  out/mg_trenchwarfare_patched.vmap --stage out/addon
```

- **`tools/patch_guard.py`** compares two maps node by node, keyed by nodeID. It covers:
  - for every node: type, parent, class, each keyvalue, origin, angles, scales, vis group, I/O, a hash of the mesh data and of every
    other attribute;
  - the root attributes and the prefix (asset references, class counts).

  It fails on any change, addition or removal that the patch's `targets.json` does not declare, down to the field.
  - Validated with `--selftest`: it plants nine undeclared changes in memory (move 0.5 u, keyvalue changed, keyvalue added, entity
    removed, node added, one mesh vertex 1 u, vis group, asset list, I/O delay). All nine are caught and an unchanged copy passes.
  - Validated on the real output: with one declaration dropped (barrel 2811) and one narrowed (seed mesh 8377 to `angles`), it fails
    and names both.
- **`tools/dyn_models.py`** makes new files only, from the addon's sources:
  - the dynamic-archetype twins: `revet_planks_broken_dyn`, `revet_planks_broken_128_dyn`, `tl_bench_dyn`;
  - the animated mortars `minenwerfer_dyn` and `mortar_58mm_dyn`. Each has a root, body and barrel skeleton, `idle` (the default,
    looping) and `fire` (0.8 s, ends in the rest pose).
    - Minenwerfer: the tube and breech slide 4.5 u back along the bore and run out again; the carriage thumps.
    - 58 mm: the bed thumps 1.4 u with a 0.7° rock; the tube flips 1.5° about its trunnion axle.
    - `fire` is the script's `CONFIG.MORTAR_FIRE_ANIM` (`src/modules/00_config.js`).
  - Barrel weights and poses were checked in renders of frames 0 / 2 / 8 / 23.
- **Matching.** Every target is matched on id + class + model + origin within 2 u; meshes on id, parent class and bounds. The patch
  verifies all of them before it changes anything. A mismatch stops it before anything is written.
- **Id correction.** The tl_bench ids in H1 (56-63, 6615-6624) are check_play prop-list indices, and so are the ids in the L3 / L4
  lists. The element ids of the 24 benches are **70-81 and 7933-7944**.

### Each finding

| Finding | Result | What was done, or why not |
|---|---|---|
| H1 sap benches | **resolved 12 Nov: kept, not a blocker** (see "Resolution of H1 and M2" below; the opt-in text that follows is superseded) | `--user-h1 unlock`: the 24 benches (the user's) become `prop_dynamic undergroundopen` on `tl_bench_dyn`, so the barricade stands until the unlock and goes with the planks. Cost: the script runs `effects()` 26 times instead of 2. `--user-h1 remove` deletes them instead. **Also found:** each sap portal's roof edge is 65.7 u over the trench floor, so a standing player (68 u in the check) must crouch for the first step in. With the opt-in and a crouched player (check body top 50), both sides reach the chamber: 6 unreachable targets become 0, routes 2740 / 2733 u. Without the opt-in, 6 stay unreachable. A standing walk-in needs the generated roof row at y ±2816 (mesh 1225, tw_gen) raised about 8 u, right under the terrain lip (+5..+7): left for a Hammer look |
| H2 blockers | **fixed** (model key only) | 7982 and 7983 (woodsopen) and 7979 and 7980 (undergroundopen, the user's; only their `model` changed, same geometry) now use the `_dyn` twins (archetype ""). check_world 7b: 4 → 0 |
| H3 woods nav seeds | **fixed** | The 4 WALKABLESEED meshes moved to centre \|x\| 1110 (inside the fence), bottom 8 u under the lowest ground of the new footprint (dz -13..-15). Seeds off the walkable world 4 → 0; seed flood 654 758 → 21 764 cells (108 140 → 3 595 m²). Nav area count still to read from the next compile |
| H4 mortar fire target | **fixed** | The 10 tubes are now `prop_dynamic mortar_<tg>_K` (K from the `mortarpit_` on each) on the animated twins. Keys: Hammer's prop_dynamic set taken from 7979, `use_animgraph 0`, Starting/Idle anim `idle` looping, `solid 6`. check_world 1: 10 wrong → 0, fire animation True ×10. Lighting is now from probes (was lightmapped) |
| M1 shelters | left | Asset fix (separate convex hull pieces): step 6 |
| M2 duplicate info_map_parameters | **resolved 12 Nov: deleted** (`--user-m2`, on by default in deploy_tw) | `--user-m2` deletes id 7 (ungrouped); `tw_params` stays. With it, check_world comes out clean |
| M3 posts in barrels | **fixed** | 1727 moved +10 u (the minimum is 9.7), its tins 1728 +10 u with it, 2811 moved -20.5 u (minimum 20.1). The minimum is what keeps a 32×32 box on the post 2 u clear of the barrel hull. T8: trench_ct_13 clean. trench_t_1 is still flagged because of the 16-u grid: the post sits exactly on a cell edge, so the check would need 19.7 u where the hull needs 9.7 (render `after_06`) |
| M4 woods ladder nav | left | The user's volumes; nav ladder links in step 4 |
| M5 woods cover | left | Adding cover is a design change, and the two trees the user moved (tw6) are not checked yet |
| M6 low CT fire steps | left: **check artefact** | A probe of the 5 steps (x 1575, y -576..-320) shows a 16-u top tier at -23.9, a 12-u step up from the user's clip stair (top -36). A player at the wall stands on the tier: eye clearance about 14 u. T2 measures from the clip-stair top (2.1 u). Raising the props 6 u would make that step 18 u (the step limit) and open a 5-u gap under the step front. T2 should measure from the highest tier a player box fits on (check_play owner) |
| L1 pit_t_2 | left | In-game walk check |
| L2 | see H1 | |
| L3 buried props | left | Sunk into the mud by design or not: ambiguous, and lifting risks floating props |
| L4 props under water | left | Debris and a tree in crater pools read as intended. The tunnel_set in gallery water is worth a look in Hammer |
| L5 water | z-fight **fixed**, edges left | Sheets 3450, 3459 and 3466 lowered 0.54 / 1.92 / 0.59 u, so each overlapping pair is 2 u apart: z-fight cells 15 → 0. Exposed edges 183 → 182: trimming pools is not a safe delta |
| L6 sightlines to crews, L7 air lanes | left | Design calls |
| L8 overlaps | left | The telephone is the user's; log into revet is cosmetic |
| L9, L11 | by design | |
| L10 stale compiles | left | Step 9 recompiles |

### Checks before → after (default patch; opt-in in brackets)

| Check | Before | After |
|---|---|---|
| patch_guard --strict | n/a | **PASS**: 24 declared nodes changed + 4 prefix keys, nothing else (opt-in: PASS, 48 + 1 removal) |
| check_world | FAILED: script names (10), singletons, archetypes (4) | FAILED: singletons only (opt-in: **clean**); warnings: 11 overlaps (unchanged), 4 (5) staged models to deploy + compile |
| check_play 1 / 1b | heal ×6 and pit_t_2 split; mines unreachable; chamber no route | Same, standing. Crouched + opt-in: 0 unreachable, chamber 2740 / 2733 |
| check_play 7 water | 183 exposed, 15 z-fight | 182 exposed, **0 z-fight** |
| check_play 9 nav | 4 seeds off, flood 654 758 cells | **0 off, flood 21 764** (passes) |
| check_play T6 | tubes prop_static unnamed | `prop_dynamic mortar_<tg>_K` ×10 |
| check_play T8 | t_1, ct_13 low | t_1 (grid artefact, above) |
| check_play overall | 17 failing items | 15: walkability, routes, sightlines, clipping, water edges, T2 (M6 artefact), T4 ×6 (step 6), T7 ×2 (L7), T8 t_1 |

`restage_out.py --vmap out/mg_trenchwarfare_patched.vmap --out out/step5/restage` passes its cross-checks, and its `entities.json`
holds `mortar_t_1..5` / `mortar_ct_1..5` as prop_dynamic. The mock's `out/` is untouched.

### Deploy (not done: Hammer may be open)

The list is in `out/step5/deploy_files.txt` (with the opt-ins: `deploy_files_optin.txt`), all addon-relative:
- `maps/mg_trenchwarfare.vmap` ← `out/mg_trenchwarfare_patched.vmap`;
- 11 files from `out/addon/`, all new: the 4 `_dyn.vmdl`, the mortar `_dyn` SMDs and `anims/*.smd`; with the opt-ins, also
  `models/tw/tl_bench/tl_bench_dyn.vmdl`.

Before and after:
- Back up the vmap and close Hammer first.
- Then compile the models: they are uncompiled, and check_world reports them as "staged".
- `docs/CONTRACT.md` still lists `mortar_<tg>_K` as 0 of 10 / MISSING, and the blocker models without `_dyn`. Its owner updates
  both after deploy.

In game, confirm:
- the planks and benches stand at round start (and grep the compile log for `DELETED`);
- the mortar recoils on fire;
- nothing pushes the crew.

## Step 7: terrain (12 Nov 2026): guarded patch `tools/patch_terrain.py`

Offline only, so everything is **simulated**: nothing was compiled, opened in Hammer or played. The input map was only read, and the
addon folders were not written to.

```
cd projects/trenchwarfare-cs2
python tools/patch_terrain.py [--in out/mg_trenchwarfare_models.vmap] [--out out/mg_trenchwarfare_terrain.vmap] [--no-fx] [--no-dense]   # 65 s
python tools/patch_guard.py out/mg_trenchwarfare_models.vmap out/mg_trenchwarfare_terrain.vmap out/step7/patch_terrain.targets.json --strict
python tools/check_world.py out/mg_trenchwarfare_terrain.vmap --stage out/addon
python tools/check_play.py  out/mg_trenchwarfare_terrain.vmap --stage out/addon
python tools/terrain_views.py          # out/review/terrain_*.png from out/step7/terrain_layers.npz
```
Chain: world_1 -> models -> **terrain** -> nav (`patch_nav.py --in out/mg_trenchwarfare_terrain.vmap`). Outputs in `out/step7/`:
`patch_terrain.targets.json`, `patch_terrain.report.json` (every number below, the crater / track / rut lists), `patch_terrain.guard.json`,
`check_*_before/after.log`, `terrain_layers.npz`, `deploy_files.txt`.

### What the terrain is and what changed

- **Targets.** The 672 generated terrain tiles: CMapMesh under the world, vis group `tw_gen`, one Valve blend material, 512 x 512 on a
  32 / 64 / 128-u grid (172 / 152 / 348 tiles). The tool verifies every one before it changes anything (vis group, no transform, every
  vertex on its grid, no extra faces); a mismatch writes nothing. User-owned meshes (`tw_user`, ungrouped: 2 water sheets, 13 clips,
  2 ladder volumes) and the 16 parapet sheets are not touched.
- **Detail layer** on a 16-u lattice, added to the vertex heights:
  - 367 fresh shell craters (330 in no man's land, r 24-64; 30 in the rears, r 30-90, mostly near the mortar line; 7 on the flanks),
    each a bowl, a raised lip and ejecta;
  - mud ruts: the tracks of the 4 tanks in no man's land (two A7V-gauge treads, 100 u apart; the Renault 60 u), each chosen from 40
    candidate curves as the one crossing the least protected ground, fading out behind the tank;
  - lorry ruts along both edges of both airfields (|y| 1100, x 4700-6580, twin grooves 64 u apart, puddled in places);
  - 9 puddle basins (shallow, flat-bottomed, in the low spots);
  - subtle noise (churn in the battle zone, long swells in the woods);
  - then erosion with `create/terrain_img.detail()` (2 gully passes, 414 k droplets, scree relaxation), its protect input being the
    same mask.
  - Soft limits: cut 16 u, fill 9 u. Layer -15.1 .. +8.3 u, rms 2.1 u where free; largest vertex move 13.4 u.
- **Paint** follows (VertexPaintBlendParams / TintColor): fresh mud and darker wet ground in craters, tracks and basins; dirt in the
  airfield ruts (forest blend). Normals are recomputed per face; texcoords stay planar x / y (the stored texture axes).
- **Re-gridded tiles.** The 47 tiles the ruts cross, and the no man's land tiles with at least 40 % unprotected ground, are rebuilt at
  16 u (same node, element and nodeID; the old surface is reproduced exactly under the 00-11 split, then the layer is added). Every
  other changed tile keeps its topology. Edges against coarser tiles follow the coarse vertices (no cracks).
- **Lightmap.** The battlefield `toolslightmapres` shell (mesh 7910, tw_gen) follows the change: 2293 floor vertices go down by the
  deepest cut within 64 u (max 12.1 u), and 2373 roof vertices go up by the highest fill. Lightmap stays at 2048 (compile setting);
  nothing adds charts.

### Protect mask (hard; 48.4 % of the lattice)

| What | Margin | Share |
|---|---|---|
| Trenches + banks (layout trench distance < 170) | | 6.5 % |
| Parapet sheets | | 3.9 % |
| Saps and galleries | +112 | 1.5 % |
| Mortar pits, round each `mortarpit_*` | r 340 | 2.1 % |
| Spawns / deploy posts / heal points / seats / nav markup | r 112 | 1.7 % |
| The user's 13 env_explosions | r 200 | 0.9 % |
| Runways (\|x\| 4236-7014, \|y\| <= 940) and plane lanes (\|x\| 3200-4300, \|y\| <= 900) | | 8.1 % |
| Ladder volumes (+128) and ladder props (+64) | | 0.2 % |
| Every prop footprint | +12 | 14.6 % |
| Tree trunks | r 48 x scale + 16 | 14.8 % |
| Water sheets (faces) | +48 | 4.9 % |
| Clips | +24 | 3.2 % |
| The gallery mesh | | 0.9 % |
| The user's objects | | 0.7 % |
| Ground effects | | 0.2 % |
| The woods skirmish (track, fence, clearing) | | 3.2 % |
| The terrain edge | 192 u | 6.2 % |

- **Rule.** Any face that touches the mask keeps every vertex bit for bit (on a seam with a coarser tile, the whole coarse segment).
  The layer then fades in over 64 u.
- **Coverage.** Frozen: 80.6 % of the terrain; fully free 6.5 %. The map is densely dressed, so the detail lives in the gaps of no
  man's land, the rears and the airfield edges. The woods are almost all frozen (trunks) and get nothing.
- **Read back.** The patched map's own vertices, sampled exactly, change by at most **0.000000 u**: at 333 698 lattice points on the
  mask, on the whole frozen region, and at 397 959 random off-lattice points on the mask.

### Counts and checks, before -> after

| | Before | After |
|---|---|---|
| terrain tiles: vertices / faces / triangles | 70 714 / 59 312 / 118 624 | 112 538 / 99 248 / 198 496 (+67 %, all from the 47 re-gridded tiles) |
| map file | 67.2 MB | 89.4 MB |
| faces newly steeper than 40 deg (mud stretch) | - | 48 (crater walls) |
| patch_guard --strict | - | **PASS**: 331 declared nodes changed (330 tiles + the lightmap shell, field `mesh` only), 19 added (6 smoke + 12 rain + relay), 4 prefix keys |
| check_world | FAILED: singletons (M2, the user's opt-in) | same; nothing new |
| check_play | 15 failing items (step 5 list) | the same 15: same walk graph (t 2213 cells), routes 1825 / 1834, nav flood 21 764 cells |
| check_play 6 clipping | 38 buried, 3 floating, 4 under water | 37 / 3 / 4. The one change (shell_pile 2331, 43 % -> under 35 %) stands on frozen ground that the read-back proves identical: a raster artefact of the finer triangles in a re-gridded tile |
| check_play 7 water | 182 exposed edge points, 0 z-fight | 182, **0 z-fight**; two cluster centres moved 2-8 u (the same artefact). No water was added |
| check_play 8 terrain, T5-T7 | clean | clean; parked planes on unchanged ground |

No prop moved: every prop footprint is protected, so nothing needed re-seating and no user prop is affected.

### Weather and light

- **Smoke** (`create/fxkit.effect`, stock `particles/burning_fx/barrel_burning_engine_smoke_cheap.vpcf`, start on) at 6 fresh no man's
  land shell holes, `tw_crater_smoke_1..6`: (-270, -1260), (1148, 340), (-64, -2603), (-1073, 711), (-46, 1316), (957, 2261).
  Each is more than 520 u from the 7 existing smoke / fire systems and from the user's explosions, and more than 1100 u from the others.
- **Rain.** fxkit has no camera-local rain (only `weather_tiles`, a fixed grid).
  - Added: 12 `particles/rain_fx/rain.vpcf` tiles over the two trench systems, **start off**, under one relay `tw_rain`
    (`ent_fire tw_rain FireUser1` / `FireUser2`). They cost nothing until fired.
  - Whether a placed `rain.vpcf` looks right is unverified in game.
  - **No fog particles** (the tw32 FPS lesson).
- **Light**: unchanged, recorded before = after.
  - Sun 55 / 145, 196 202 210 x 1.6; sky 150 160 175 x 1.6, sky_overcast_01.
  - Cubemap fog 250-7500, height fog 300-2600; post-process exposure 0.6-1.8.
  - 15 probe volumes, 23 lightmap-res meshes.
  - Nothing is broken, and `create/gen_light.py` would replace the whole tuned set with a preset, so it was not used.

### Images looked at (`out/review/`)

- Hillshades, before | after (mud / wet tint) | mask and frozen faces: `terrain_whole`, `_nml_north`, `_nml_south`, `_t_rear`,
  `_ct_rear`, `_t_airfield`, `_ct_airfield`, `_north_flank`, `_south_flank`.
- Eye level, before above after (terrain only): `terrain_eye_t_firestep_east`, `_ct_firestep_west`, `_nml_overview_n/_s`,
  `_ct_rear_mortars`, `_t_rear`, `_track_1..4_*` (beside each tank track), `_ruts_t_north/_south`.
- They show new shell holes and churn between the old craters, tank treads running away from the wrecks, and twin lorry ruts along
  the airfield edges.
- Fixed while looking:
  - the ruts first came out as one smeared band (grooves narrower than the 16-u lattice): widened to sigma 11, 64 u apart;
  - the tank tracks first ran under protected pools and props: path choice added;
  - the lightmap shell first jumped 58 u (it was compared with the ground instead of with the change).
- No steps, spikes or seams at mask edges or tile edges. One faint straight line in the whole-map hillshade at y +-1100 is the airfield
  ruts.
- Left: the T north rut fades where it crosses a protected shell hole at about (-5300, 1100).

### For the user / open

- **Budget.** +80 k terrain triangles and +22 MB of vmap, all from the 16-u tiles. `--no-dense` gives heights and paint only, with no
  grid change; in that mode no man's land keeps 32-u detail and the ruts cannot form.
- **In game, check:**
  - mud stretch on the 48 steep crater faces;
  - the ruts and treads at player scale;
  - that the 6 smoke columns read as smouldering;
  - `ent_fire tw_rain FireUser1` (look and FPS);
  - the lightmap at 2048 over the re-gridded tiles.
- **Deploy list:** `out/step7/deploy_files.txt`. It holds the map only, because every particle is stock. If patch_nav runs after this
  step, deploy its output instead.

## Resolution of H1 and M2 (12 Nov 2026, the user's decisions)

- **H1: resolved, the benches stay.** The user: the 24 benches are seam bridges they placed between the trench and tunnel meshes (steps
  down and a cover over the mouth), not blockers, and players got in with them. `--user-h1` is not used on this map. The "never open"
  finding came from check_play's 16-u grid, which could not resolve the stepped seam; the adapter now proves each mouth on a fine grid
  (T9) and both sides reach the chamber crouched once `undergroundopen` fires; standing they do not (tallest box through: 56.9 / 55.6 u,
  set by the upper bench row, not by the roof, so the roof was not raised). Details, numbers and a proposed seam patch:
  [REVIEW_WORLD_2.md](REVIEW_WORLD_2.md) "W1 / W4 / W5 resolved".
- **M2: resolved, id 7 deleted** (`--user-m2`, on by default in `tools/deploy_tw.py`). Id 7 held Hammer's defaults; `tw_params` keeps
  the map's values (buying 3, generated DM spawns off, normal spawns for DM), unchanged.
- The doubled bench of review 2 (W5, ids 71 / 72, an exact copy 1 u apart) goes with `--user-w5` (default).
