# World review 3 (13 Nov 2026): every check_play failure of the deployed map, real or artefact

AI-generated (Claude) for skink52. Offline, so everything here is **simulated** unless it says **compiled**. The rebuilt shelter was
test-compiled in the scratch addon. Nothing was deployed, compiled into the map, opened in Hammer or played.
Starting point: the deployed map's gate (`out/step9/gate/check_play.log`, 12 Nov 23:41, chain `6_nav.vmap` CRC32 72f14e1d), which FAILED on
walkability, sightlines, clipping, water, T2 ct fire steps, T4 shelter x6, T7 plane_ct_2 / plane_ct_3 air spawn blocked and T8 t posts
spawns. (`routes` had already been fixed by REVIEW_WORLD_2's T9 sap probe: 0 unreachable, t/ct -> chamber 2744 / 2733.)
Reviews before this one: [REVIEW_WORLD_1.md](REVIEW_WORLD_1.md), [REVIEW_WORLD_2.md](REVIEW_WORLD_2.md).

Each finding below was first sorted into real or artefact with a probe on the exact triangles, a render or the real CS2 hull sizes (player
32 x 32, 72 u standing, 54 u crouched, 18-u steps, about 54-u jumps). Then:
- **Real, in generated content:** fixed by a guarded stage. The new `tools/patch_world_3.py` runs in the chain after the seams as
  `5_world_3`. The shelter was fixed as an asset (step 13).
- **Checker artefact:** the check was fixed, either in the trench adapter `tools/check_play.py` or in the neutral `create/check_play.py`.
- **The user's own objects** (`tw_user`, ungrouped) were not changed, only listed.

## Summary

| # | check_play item | Verdict | Evidence | Fix | Result |
|---|---|---|---|---|---|
| W2 | T4 shelter x6, walkability `heal_*` x6, clipping "6 candles inside shelter" | **real** (asset) | The arch is 42.3 u high inside (R0 46 x 0.92), so even a crouched player (54) cannot enter. The heal post's 72-u box goes through the arch (render `before_shelter_t_mouth`). The shelter collided as one solid hull over the whole mound (commit 2b09c9e: "the arch is too low to stand in") | Shelter rebuilt: corrugated iron on 44-u straight legs, 85.8 u inside at the crown. The hull is now **11 convex pieces** round a free inside (2 leg slabs, 8 arch-shell sectors, back wall). Step 13 deploy list. Test-compiled: **1 compiled, 0 failed** | T4: 6/6 walk-in ok, 75 u over the floor at every station; heal x6 joined; candles in free air |
| W2b | walkability `mortarcrew_t_2_a` | **real** | The stock shell rack (`ammo_artillery_small_01`, real LOD0 mesh) crosses the a -> b walk. A player box on the line hits 74-646 of its triangles. The gap to the plotting table is 15 u | The rack was turned 90 deg so it lies along the breastwork and moved 8 u out (patch_world_3) | pit_t_2 2/2 seats joined (305 cells) |
| T2 | T2 ct fire steps (5 at x 1575, y -576..-320, "eye clears by 2.1 u") | **artefact** | The stand point was the 16-u grid at the prop's box centre. On the CT side that lands on the user's clip stair (top -36), 12 u under the step's 16-u-deep top tier (-24). The eye render from the tier (`before_ct_step_eye`) looks over the parapet into no man's land. Review 1 (M6) and 2 (W6) said the same | `firesteps()` now picks the highest support under a 32 x 32 box that is free 72 u up, 16.5-40 u out from the wall, on the exact triangles. Reach is "a jump-world node within 40 u and 54 u under it" | clearance min 14 / median 14 (ct), 14 / 15 (t); 0 blind, 0 off-world |
| T8 | T8 t posts spawns (`trench_t_1` "18 u headroom") | **artefact** | The grid's blockers are widened 12 u, so barrel 1727 (31.3 u away) reads as over the post. A 32 x 32 x 72 box from 1 u over the floor touches only the duckboards under the feet (`out/review3` probe) | T8 asks the exact triangles (a standing box from step height to 72 u) whenever the grid says < 72 | 0 low posts |
| T7 | T7 plane_ct_2 / plane_ct_3 air spawn blocked | **real** (ct_3 everywhere, ct_2 and ct_5 within the wings); ct_2 on the centre line was an **artefact** | The checker stood stock trees in as a disc 0.3 x their bounds, at full height. The real crowns, LOD0 render meshes from pak01, are narrower. Along the lane centre, ct_2 actually clears by 344 u and ct_3 is 11 u short. Across the SPAD's wings (+-169 u) ct_2 is 74 u short, ct_3 15 and ct_5 6 (four `tree_poplar_mature_02` at scale 1.08-1.13, the tallest trees by either airfield; T has mature_01 at 0.94-1.0, 273+ u clear) | Checker: lanes as wide as the aircraft, crowns from the real meshes. Map: the four poplars scaled down by the minimum for 100 u of clearance (1.131 -> 1.045, 1.099 -> 1.039, 1.081 -> 1.055, 1.085 -> 1.069). They are not moved | ct_2 / ct_3 / ct_5 clear by 10 (the margin), ct_1 134, ct_4 80; T unchanged |
| W8 | water (184 points > 3 u over the ground, 30 places) | **80 artefact, 104 real (+2 the user's)** | 78-80 lips lie inside a revetment's hull at the trench pools' wall feet (the edge is 3 u into the 6-u siding: hidden). The rest are generated crater pools in no man's land, 12-gon prisms whose rim stands over lower ground (lips 3-22 u, worst 21.7) | Checker: a lip inside a solid prop's hull is not counted, and the user's sheets are listed. Map: **56 crater pool rims** set onto the ground (patch_world_3). Each rim vertex moves along its own ray, in or out, to the nearest spot where the ground is within 1 u of the water line, with the edges too. The rim stays convex. The level is lowered only when no such rim exists: 38 pools by 1-22 u, never to within 2 u of another sheet | 0 exposed, 0 z-fight; user's pool 53873 listed (2 points) |
| C1 | clipping: 16 buried + 3 floating `tl_bench` | **the user's** | tw_user: the user's seam bridges in the sap mouths (12 Nov decision) | Listed by check 6 (`Adapter.user_owned`), never counted | listed |
| C2 | clipping: 20 generated props "buried > 35 %" (log_fallen x8, shell_pile x4, sandbag_wall x4, wreck_wheel, crate_shells, wire x2) | **artefact** (by design) | Close-up renders `before_clip_*`: logs lie across flooded shell holes with their ends in the banks, pit breastwork courses are bedded where the mound dips, shell heaps and wire lie sunk in the mud. All come from the generator's scatter (zoff -2..-4, tilt 3-8 on the origin's ground). The bury metric is the mean ground height over the box, which overstates long or sloping props: the shell heaps have only 18-30 % of their vertices under the ground | The adapter tags them 'bury' (by design): logs anywhere; heaps; wheel, crates and wire in no man's land; sandbag courses within 260 u of a pit | 0 buried |
| C3 | clipping: `tunnel_set` 6274 "12.4 u under water" | **artefact** | The prop is in a gallery at z -259. The pool is on the surface 190 u over it | Neutral check: a prop whose top is under the terrain at its own spot is not in the pool over it | gone |
| C4 | clipping: `debris_metal_01b` 24.7 u and `_01f` under water | **artefact** (by design) | Debris sunk in a crater pool, out of sight (already 'bury' by design in the adapter) | `water_ok` + debris_metal | gone |
| C5 | clipping: `tree_poplar_mature_02` 4456 "8.7 u under water" | **real** | A living mature poplar stood in the middle of a generated crater pool, which was centred on its trunk (render `before_poplar_pool`). A shell crater cannot form under a standing tree | Moved straight out of the pool, 58 u, its trunk 8 u past the water's edge, set on the ground (patch_world_3). It now stands on the bank, 16 u from the rim, 19 u over the water | gone |
| W9 | sightlines: enemy fire steps -> mortar crews | **real, a design call** (not changed) | 13 / 380 and 54 / 380 pairs at 4,900-6,600 u (see "W9" below) | Proposal; prepared as `patch_world_3 --pit-sandbags` (OFF by default, the user's call): 4 / 380 a side when on | still FAILS: the one remaining check_play item |
| R1 | generated revetment 121040 (`revet_iron_128`, -1892, 144) faces backwards | **probably the user's edit: listed, not rotated** | The generator would place it at yaw -90 (270): `layout.walls()` gives the wall at x -1892 with n (1, 0), and `yaw_for` gives -90. The base z it computes, -89.18, matches exactly. The map has yaw **90.00001525878906**. That float is Hammer's re-save signature. Of the other 11 revetments with Hammer float noise, 9 are the user's own (`tw_user`, e.g. their niche irons 57810 / 57813 / 57816 at exactly 90.00001525878906) and 2 are the woodsopen blockers. The other 680 revetments have exact yaws (270.0 / 90.0 / 0.0 / 180.0) | For the user: rotate 180 deg in Hammer if it was not meant (render `before_revet_121040`: the earth backing faces the trench) | listed |

## W2: the shelter

**Before.** `models/tw/shelter` (generated by `tools/p_trench.py shelter()`, 26 Oct) is a corrugated half-arch, R0 46 with a vertical
factor of 0.92: 42.3 u high inside, 92 wide and 96 long. An earth mound over it is closed at the mouth and the back, and a sandbag
header sits over the mouth. Its physics was one convex hull over the whole mound. That hull came from commit 2b09c9e, when the shelter
had none and a convex hull of the mound was the simple fix. The dressing station `heal_<tg>_N` stands 24 u inside the mouth under the
arch, with two stretchers and a crate with candles. A player could not get in. Healing still worked: the script's HEAL_RADIUS 120
reaches the trench.

**After** (`tools/p_trench.py`: `SHELTER_LEG = 44`, `shelter_hulls()`).
- **Shape.** The same corrugated iron and the same arch. The arch now springs from straight corrugated legs 44 u high. Inside: 85.8 u
  at the crown and 83 u across a 32-u player box. That is 6 ft 6 in to 7 ft, a real elephant-iron shelter. It needs this much because
  the 30-u aisle between the two stretchers makes a player step 7-8 u up onto a stretcher's edge.
- **Mound, mouth, back.** The mound is lifted with the legs, so its top is about 30 u over the trench lip. That reads as a dugout's
  earth and sandbag roof inside the revetted niche. The mouth face follows the legs, the back plank wall runs up to the new arch, and
  the sandbag header is 44 u higher.
- **Physics.** 11 convex pieces, each a SingleHull file: two leg slabs, eight arch-shell sectors 14 u thick, and the back wall. A
  sector's chord stands at most 0.9 u inside the arc.
- **LODs.** `tools/lod_decimate.py --lightmapped-from` the map: lod0 15,354 tris (was 10,000), lod3d 6,095 (4,494), lod4d 2,752
  (1,939), at the same switch distances.
- **The builder.** `p_trench.shelter(leg=0)` still rebuilds the old geometry vertex for vertex: the toolchain reproduces the 26 Oct
  model, apart from tiling UVs that changed in the stock tools since.
- **Deploy and compile.** Staged in `out/addon/models/tw/shelter/`, with the deploy list `out/step13/deploy_files.txt` (15 files; the
  stock hessian materials build_prop rewrites are left out). Test compile in the scratch addon `tw_weapontest` (the staged files and the
  three hessian vmats with their two textures): `resourcecompiler -f -i shelter.vmdl` gave **OK: 1 compiled, 0 failed**, no warning
  (`out/step13/compile_shelter_watch.log`).

check_play cannot see the walk-in on its 16-u grid: blockers widened 12 u close the 30-u aisle. So T4 now walks a player box (31 x 31,
72 u, 18-u steps, 4-u steps along the axis) on the exact triangles. It starts 40 u out in the support trench and goes to the station.
Check 1 then joins the station to its world at the mouth, like T9 at the saps. Result: 6/6 walk-in ok, floor rise 0-5 u, 75 u over
the floor at the station.

## W9: mortar crews in sight of the enemy fire steps (design, not changed)

With the fire-step eyes now on the real tier (T2), **13 of 380** CT-eye -> T-crew pairs and **54 of 380** T-eye -> CT-crew pairs have
a clear line on the final map. The eyes are spread along the whole fire trench (y -2880..2752). The crews seen are the outer seat of
the pits: 7 of the 10 CT seats and 5 of the 10 T seats. The distances are 4,896-6,618 u, median about 5,050 u (125-170 m). The map's
cubemap fog (start 250, end 7500, exponent 1.25, max opacity 0.85) is about 49-72 % at that range. A crewman cannot step out of the
line: crews are teleported to their seats. The period scopes reach that far. So this is a real gameplay problem, and an asymmetric one:
the CT crews are about 4x more exposed.
**Proposal (for the user; layout not changed):** one more sandbag course (`sandbag_low_128`, about 16 u) on the enemy-facing arc of
the CT pits' breastworks, mirrored on T for parity. Or a low hedge or wreck screen 300-600 u in front of each pit row. Either would
take the line at about 5,000 u. Check 2 keeps failing until one is chosen.

### W9 option prepared: `--pit-sandbags` (13 Nov 2026; OFF by default, pending the user's decision)

**Why the CT crews were the more exposed.** The generator's breastwork is three courses (walls at r 194 / 192, a `sandbag_low` cap at
r 190, scale 1 1 1.1). The cap tops out at about +63 over the pit floor, and a standing crewman's eye is +64. So the breastwork stops
the line by a unit or two, or misses it by a unit or two. Which way it went came down to the terrain between the trenches, not to the
pits, and the result was the 13 / 54 split. One more course moves that margin to about 10-20 u on every line that crosses it.

**What the flag does** (`tools/patch_world_3.py --pit-sandbags [both|ct|t]`, passed through by `deploy_tw.py`; default off, and with
the flag off the stage output is byte-identical to before, CRC32 fe24aef1):
- It adds a fourth course in the generator's own pattern. The bags are `sandbag_low`, clones of the pit's own cap bag (model,
  scale 1 1 1.1, keyvalues, vis group `tw_gen`). They go at r 188, two units further in, like each earlier course. They sit half a bag
  round from the cap, with the generator's yaw and +-2 deg jitter (seeded from the input CRC: a second run gave the same bytes, 7ad97c26).
- Bags go only on the enemy-facing arc. A slot gets a bag when its span meets the arc where a line from any crew position (seat a,
  seat b, the tube) to any enemy fire step crosses the ring: about -80..+80 deg of the facing direction. That is **7 of the 17 slots per
  pit (8 at ct_2): 35 bags on T, 36 on CT, 71 in all.** The rear and flanks are unchanged.
- Each bag rests on the exact LOD0 triangles of the bags under it. Its z is set so that 3/4 of its bottom samples touch or bed into
  them. Contact is closer than the generator's own caps on their course: median gap 3.3 / 5.0 / 9.6 u (p50 / p75 / p90), against
  5.7 / 8.0 / 12.3 u for the 166 existing caps. Largest bedding is 7 u (one bag in t_4's dip: 15.5 u, into a tilted cap).
- The patch is refused (nothing written) if a bag would touch any other prop of the pit (tube, table, ammo box, stores, the turned rack)
  or a crew seat's 32 x 72 player box, or if the tube would have to fire under 30 deg to clear the course. **Measured:** no prop touched,
  no seat box touched. The muzzle stands 58-60 u over the floor (mortar_58mm / minenwerfer), and any elevation **over 7.5 deg** clears the
  course. Both tubes fire at 45 deg or more, and the shells are simulated by the script (no trace from the tube).
- **The crew at the table:** the course stands 71-83 u over the floor (median 77) on the front arc. The crew's seats, the table, the ammo
  box and the walks between them are unchanged. Every pit's two seats are still joined, and each pit lost 1-3 of its ~330 walkable
  cells at the foot of the wall. A crewman can no longer look out over the front arc from his seat. That is the point of the course;
  he aims on the board, not by sight.
- `ct` / `t` limit it to one side's pits. A course on the CT pits cannot change the T crews' lines (those run from x +1592 to x -3300,
  nowhere near the CT pits), so `ct` alone leaves T at 13 / 380 while CT drops to 4 / 380 (derived from the two measured runs, not
  run separately). That would turn the asymmetry round instead of removing it. In the same way, `t` alone would give CT 54 and T 4,
  since the T pits do not lie between the T fire steps and the CT crews either.

**Measured** on `out/step15/chain/` (4_seams = the 13 Nov chain's, CRC32 0ee969ec -> `5_world_3_both` 7ad97c26 -> `6_sounds` c5a7f74a ->
`7_nav` 05f6cb3c). Every stage passed `patch_guard --strict` (world_3: 133 declared targets, 0 violations; sounds 12; nav 684). Logs and
JSON are in `out/step15/gate/`.

| check_play 2 sightlines (eye -> eye) | off (13 Nov chain, `out/step9/gate`) | `--pit-sandbags both` |
|---|---|---|
| CT fire steps -> T mortar crews | 13 / 380 | **4 / 380** |
| T fire steps -> CT mortar crews | 54 / 380 | **4 / 380** |
| fire steps -> posts (both sides) | 0 / 760, 0 / 760 | 0 / 760, 0 / 760 |

| Check | Result with the flag |
|---|---|
| check_play T6 / walkability | 10 pits, both seats of each in one world (322 / 303 / 353 / 350 / 338 T, 329 / 335 / 358 / 372 / 345 CT cells; before 323 / 305 / 355 / 352 / 340, 330 / 338 / 360 / 374 / 346). Tube, table and ammo box present, no pit joined to a trench. All other worlds unchanged |
| check_play 6 clipping | 0 buried, 0 floating > 6 u, 0 inside solids (same as off). check_play still `FAILED: sightlines` (8 pairs left: the baseline has the item, so nothing new for the gate) |
| check_world | clean (prop_static 6,184) |
| check_seams `--no-sight` | clean (no new gaps) |
| patch_nav estimate | 342 NONAV boxes (off: 337), about 4,323 areas (off: 4,359). The bag tops are new walkable-looking ground outside play, so the box layout shifts a little |
| `tools/navtest.py out/step15/chain/7_nav.vmap s15_pitbags` (count only, 138 s, `out/nav2/s15_pitbags.log`) | **4,529 areas**, the same as the deployed map's compile 5 (4,529) under the same compiled shelter. The pits are not bot areas, so the nav does not change. The temp map in `_navtest` was removed |

**The 8 lines left** (4 per side) all go through one of two dips in the existing breastwork. At pit_t_4's south-east arc and
pit_ct_2's south-west arc the ground falls away. The generator laid the courses on it 40-60 u under the pit floor (ct_2 slots 10-11;
t_4 slots 13-15). The fourth course follows them down: those 5 bags top out at 7-45 u over the pit floor, so they close nothing there.
Seen: t_4 seat a from CT eye (1592, -2752), t_4 seat b from three eyes at y -448..192; ct_2 seat b from four eyes at y -2880..-1984. Closing the dips
would mean building them up two or three courses, which is a separate change. Left as found.

**Renders** (`out/step15/render_views.py`, a copy of review 3's renderer; `out/step15/views/before_*.png` from the 13 Nov chain's
`5_world_3`, `after_*.png` from `5_world_3_both`; contact sheets `out/step15/ba_t_enemy.png`, `ba_ct_enemy.png`, `ba_t_above.png`,
`ba_ct_above.png`; looked at). `pit_<side>_<k>_enemy`: 520 u out along the real line from the crew seat to an enemy fire-step eye that
saw it (or straight across), at that line's height, fov 34. `pit_<side>_<k>_above`: from behind the pit over the tube, onto the front
arc. Blue boxes are the crew seats' 32 x 72 player boxes.
- Before: on every pit the seats' boxes show their top over the cap, head and shoulders at that range.
- After: on 8 of 10 pits the boxes are hidden behind the new course, or show only a sliver of the top (the box top is 8 u over the eye
  the check uses). On ct_2 and t_4, viewed through their dips, they still stand clear. That matches the 8 lines left.
- From above: the course follows the cap round the front arc, seated on it, with no gaps, floating bags or bags into the tube, table or
  stores. In t_4's dip it steps down with the old courses.
The renders are our software renderer: placement and scale, not lighting.

**Recommendation.** If the user wants the crews covered, use `--pit-sandbags` (= `both`). It takes the asymmetry from 13 vs 54 to 4 vs 4
for 71 bags on the front arcs only. Do not use `ct` alone: it reverses the imbalance. The two dips (pit_ct_2 SW, pit_t_4 SE) are the
next step if 4 / 380 a side is still too many. check_play's sightline item will keep failing on those 8 pairs (`allowed` is 0) unless
the adapter is given an allowance. The option is not in the shipped chain: `deploy_tw.py --chain --pit-sandbags`, the gate and a map
compile are needed to ship it.

## Checker changes (both files read only; numbers above)

- `create/check_play.py` (neutral, a fork of monsoon's; nothing pushed with libsync):
  - `Adapter.user_owned(p)`: the map author's own props and sheets are listed in checks 6 and 7, never counted.
  - Check 6: a prop under the terrain at its own spot is not "under water".
  - Check 7: a lip inside a solid prop's hull is hidden. The JSON keeps up to 200 exposed points.
  - monsoon's origin `tools/check_play.py` could take the same three changes. That is for its own session: it has uncommitted edits.
- `tools/check_play.py` (trench adapter):
  - `user_owned` = tw_user or ungrouped.
  - `firesteps()`: the real standing tier (T2), plus the T2 reach test.
  - T4: the shelter walk-in probe, with `heal_point()` for check 1.
  - T7: lanes as wide as the aircraft, and stock tree crowns from their LOD0 meshes (`tree_mesh()`, cached in `out/review/cache`).
  - T8: the exact-box headroom.
  - by-design 'bury' tags for the generator's scatter dressing; `water_ok` + debris_metal.

## Chain, gate, nav, dry run (13 Nov 2026, 05:00-05:20)

| Step | Result |
|---|---|
| `python -u tools/deploy_tw.py --chain` (watchdog, `out/step9/deploy_tw_chain_r3.wd.log`) | 1,102 s. Every stage guard **PASS**: world_1 5043efe5 (18 s), models 56054f56 (17 s), terrain 69f1808d (81 s), seams 0ee969ec (218 s), **world_3 fe24aef1 (81 s, 62 declared targets: 4 poplars, the rack, the pool poplar, 56 pool meshes)**, sounds a252c86e (45 s), nav 56bff078 (120 s). Final `out/step9/chain/7_nav.vmap` **CRC32 56bff078**, 96,870,575 B. Radar re-made, check_radar clean |
| patch_world_3 determinism | a second run on the same `4_seams.vmap` gives the same bytes (fe24aef1) |
| gate (`out/step9/gate.json`) | **PASS**: check_world clean. check_play `FAILED: sightlines` only (W9; the baseline has it, nothing new). check_seams clean, contract 86/86, api 0 / 0 / 0, tscheck OK, mock 32 / bots ok, 13 / 13 scenarios |
| check_play on the final map | walkability (all 23 + 23 points, pits 2/2), routes (t/ct -> chamber 2744 / 2733, ratio 1.00), clipping (0; the user's 19 benches listed), water (0 exposed, 0 z-fight; 78 lips inside revetments, the user's pool listed), T2, T4 6/6, T7 10/10, T8: **clean**. Sightlines: W9 |
| patch_nav estimate | 337 NONAV boxes, about 4,359 areas |
| `tools/navtest.py out/step9/chain/7_nav.vmap chain_r3 --full` (watchdog, `out/nav2/run_r3full.txt`) | **4,394 nav areas** (was 4,397; target < 5,000), 289 s |
| `tools/navcheck.py out/nav2/chain_r3.nav` | Every post, both landings, the gallery and chamber points are in one piece (2,408 areas), and the woods in theirs (1,866). `heal_*_3` are 66-67 u from the nav, as before. The nav test compiles the map against the **game addon's compiled shelter** (the old solid hull). The stations get their nav only after the step 13 assets are compiled: run navcheck again after that compile |
| dry run | 203 files: 10 new, 7 changed, 186 the same, 98.3 MB to write. The changes are the map (replaces what the last deploy wrote, 72f14e1d, backed up first), the 15 shelter files (`shelter.vmdl`, lod0 / lod3d / lod4d, hull0..10) and the radar png |

**Renders** (`out/review3/render_views.py`, views in `out/review3/views.json`, `out/review3/views/before_*.png` from the 12 Nov chain
map with the old shelter and `after_*.png` from the final map with the staged shelter; contact sheets `out/review3/ba_*.png`, looked
at):
- **Shelters.** The heal post's player box goes through the old arch, and stands under the new one with room to spare. The mouth is
  now a 2 m arch. The mound rises about 30 u over the trench lip with the sandbag header on it.
- **pit_t_2.** The rack lies along the breastwork. Seats a and b are joined.
- **CT lanes.** The four poplars are a little shorter; nothing else moved.
- **Pools.** They meet their banks. Where the level had to drop most (pool 123498, 8 u; 123449, 15 u) the water now shows as a smaller
  pool or a puddle in the bottom of the crater.
- **The pool poplar.** It stands on the bank.
- **Unchanged, as evidence.** The CT fire-step eye (T2), post t_1 (T8) and the reversed revetment 121040.
The renders are our software renderer: placement and scale, not lighting.

## For the user

- **W9:** the mortar crews' exposure (proposal above) is a design choice. check_play keeps failing on it until one is chosen. The
  sandbag course is ready as `--pit-sandbags` (off by default; measured 13 / 54 -> 4 / 4 in "W9 option prepared").
- **Revetment 121040** (-1892, 144) carries Hammer's float signature and faces backwards. If that was not meant, turn it 180 deg in
  Hammer. Nothing here rotates it.
- **Shelters.** After the deploy, compile the assets (shelter.vmdl) before the map. In game, walk into a dressing station, standing
  (TESTING: dressing stations).
- Nothing was deployed or compiled into the map.
