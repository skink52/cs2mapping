# World review 2 (12 Nov 2026): the chained map, independent second review

AI-generated (Claude) for skink52. Offline only, everything here is **simulated**: nothing compiled, opened in Hammer or played. The map
reviewed is the chain's output before nav, `out/mg_trenchwarfare_sounds.vmap` (89,407,102 B: the user's map + world_1 -> models ->
terrain -> sounds; `patch_nav` runs after it). It was only read; **nothing was patched**. Every fix below is a proposal for a guarded
delta patch (`tools/patch_guard.py --strict`, targets matched on element id + class + model + origin within 2 u) or for the user.
Review 1: [REVIEW_WORLD_1.md](REVIEW_WORLD_1.md); script side: [REVIEW_SCRIPT_2.md](REVIEW_SCRIPT_2.md).

## What was run

| Tool | Command (project folder) | Output |
|---|---|---|
| check_world | `python tools/check_world.py out/mg_trenchwarfare_sounds.vmap --stage out/addon --json out/review2/check_world_sounds.json` | `out/review2/check_world_sounds.log` (16 s) |
| check_play | `python tools/check_play.py out/mg_trenchwarfare_sounds.vmap --stage out/addon --json out/review2/check_play_sounds.json` (watchdog) | `out/review2/check_play_sounds.wd.log` |
| check_contract | `python tools/check_contract.py --vmap out/mg_trenchwarfare_sounds.vmap --stage out/addon` | 86 rows, 86 OK |
| mapdigest | `python ../../tools/mapdigest.py out/mg_trenchwarfare_sounds.vmap --summary` | 6,723 entities, 1,346 meshes |
| probes (new, read only) | `python out/review2/probe.py`: duplicate props, point entities against the terrain, lights inside props, what the chain added since step 5 | `out/review2/probe.json` |
| views (new, read only) | `python out/review2/render_views.py [--jobs N] [names]` (`NOTREE=1` drops stock tree boxes): the vmap's meshes (as `tools/vmap_preview.py`, tool materials skipped) + our props from their SMDs (the `tools/preview_scene.py` loader, a decimated LOD) + stock props as boxes from check_play's measured bounds (lilac; trees green); blue 32 x 32 x 72 boxes on every post, crew seat and dressing station; `tools/render.py` | `out/review2/views/*.png`, 31 views |

Review 1 used check_play's top-down grid plots (`--map`) and `tools/terrain_views.py` hillshades; neither shows props in 3D, so this
pass built the view script above from the project's own renderer and loaders. Its limits: stock props are boxes, no lightmaps or
materials beyond our baked colour maps, decimated LODs. It is good for placement, scale and gross clipping, not for seams under 4 u.

Views looked at: the T and CT fire trenches (north, middle, south), the fire-step eye at check_play's T2 eye points (`t_eye_step2`,
`ct_eye_step2`), both support-trench shelters, both pit rows and two pits close up, both sap mouths (from above and from the support
trench), both woods halves and the T ladder foot, no man's land north and south, both airfields (with and without tree boxes), the
briefing room and the galleries. The first two eye views (`t_eye_firestep`, `ct_eye_firestep`) had the camera inside the revetment
and are kept only as a record; `*_step2` replace them.

## Check results on the chained map

| Check | Result | Against review 1 |
|---|---|---|
| world 1 names | 352 expected, 0 wrong; 10 `mortar_<tg>_K` prop_dynamic with a `fire` sequence | H4 fixed: confirmed |
| world 2 singletons | **FAILED**: `info_map_parameters` x2 (id 7, ungrouped) | M2: the chain ran without `--user-m2`, still open |
| world 4 overlaps | 11 pairs (8 hangar + petrol_can artefacts, telephone into firestep, log into revet, wreck wheel) | unchanged |
| world 7 models | 0 missing; **10 compiled before their last .vmdl edit** (was 4); 5 staged (`_dyn` twins, `gm_canon75`) | 6 new stale (W3) |
| world 7b archetypes | 0 prop_dynamic on a static_prop_model | H2 fixed: confirmed |
| play 1 / 1b | heal x6 and `pit_t_2` not joined; **mines: 6 targets unreachable, chamber NO ROUTE** | H1 still open (W1) |
| play 6 clipping | 37 buried, 3 floating (the user's benches), 4 under water, 6 candles inside shelters | unchanged |
| play 7 water | 182 exposed edge points, **0 z-fight** | L5 z-fight fixed: confirmed |
| play 9 nav | 25 seeds, 0 off the walkable world, flood 21,764 cells | H3 fixed: confirmed (pre-nav map, 0 NONAV here by design) |
| play T2 | CT 5 steps "blind 2.1 u" at x 1575, y -576..-320 | M6 artefact: confirmed by the eye render (W6) |
| play T4 | 6 shelters, 0 enterable | M1 still open (W2) |
| play T7 / T8 | `plane_ct_2` lane fails; `trench_t_1` "18 u headroom" (detail only) | L7 one lane left; M3 fixed (W7) |
| check_play RESULT | 13 failing items: walkability, routes, sightlines, clipping, water, T2 ct, T4 x6, T7 plane_ct_2 | review 1's step 7 had 15 |

## Findings, ranked

| # | Sev | Finding | Evidence | Proposed patch / action | Owner | Status |
|---|---|---|---|---|---|---|
| W1 | high | **The mine galleries are still sealed, and the script now sends bots into them.** The chain ran with no opt-in, so the 24 benches (H1) still close both sap mouths: once `undergroundopen` fires ("THE MINE GALLERIES ARE OPEN", at 30 kills or 480 s) no human can get in. The bot code added in step 4 deploys `AREA_SHARE` of bot deploys into open areas, up to `AREA_MAX` 4 a side per area, at `CONFIG.BOTS.AREAS.undergroundopen` = (±2120, -3296, -252), which is check_play's "mines seed 20 / 23", unreachable from either trench. The galleries are one world inside (3 / 3 points), so up to 8 bots fight each other out of every human's reach, and the leash never brings them back (that point is an anchor) | check_play 1: `('mines seed 23 from ct', 'open', 'not reached by ct', [2120, -3296, -248])` and the five others; 1b: chamber NO ROUTE; `00_config.js` BOTS.AREAS | 1) The user's choice, in the chain: `patch_world_1.py --user-h1 unlock` (benches 70-81 / 7933-7944 become `prop_dynamic undergroundopen` on `tl_bench_dyn`) or `remove`; plus the generated sap roof row (mesh 1225, tw_gen) raised about 8 u so a standing player gets in (review 1: roof edge 65.7 u). 2) Until the saps open, take `undergroundopen` out of `CONFIG.BOTS.AREAS` (one line; script owner), and consider holding its headline | user (benches) / ours (roof, CONFIG) | open; not patched |
| W2 | mid | **Dressing stations inside solid shelters** (M1). `heal_<tg>_1..3` stand under the shelter arch, which compiles as one convex hull; 6 candle clusters and the stretchers inside cannot be reached. Healing still works because `HEAL_RADIUS` 120 reaches the trench 64 u away | check_play T4 x6, headroom 51 u; 6 candles inside solids; view `t_support_shelter.png` (the post box under the arch) | Asset fix (no map patch): rebuild `models/tw/shelter` with four convex hull pieces (walls, roof, back), as `hangar` has; recompile | ours | open (review 1 deferred it to step 6; not done) |
| W3 | mid | **Ten models compiled before their last edit** (review 1: four). New since review 1: `ext/plane_dr1` and its `_dyn`, `ext/plane_spad7` and its `_dyn`, `ext/tank_a7v`, `ext/howitzer_bl8`; still `wire_coil`, `wire_fence_a`, `wire_fence_b`, `ladder`. The map compile uses the old `.vmdl_c` (for the aircraft: the parked planes and the flying ones) | check_world 7 `stale ...` lines | Run the asset compile (BUILD_LOG_1 step 4) over these ten as well as the deploy list's new files; confirm `0 stale` from check_world before the map compile | ours | open |
| W4 | mid | **Two `info_map_parameters`** (M2): id 7 at (512, 328, 32), ungrouped, buying 0, next to `tw_params` (7305, tw_gen) | check_world 2 FAILED | `patch_world_1.py --user-m2` (drops id 7, matched on class + origin) | user | open; the chain did not pass the flag |
| W5 | low | **A duplicate bench** in the CT sap barricade: ids 71 and 72, both `tl_bench` at (2164, -2834, -15), 1.0 u apart, same angles: two copies of one prop, z-fighting. Not in review 1 | probe a) (`out/review2/probe.json`, the only duplicate outside the script's parked pools) | With W1's `unlock` both go at the unlock (harmless); otherwise drop id 72 (match id + class + model + origin). The benches are the user's: flag | user | open |
| W6 | low | **CT fire steps at x 1575, y -576..-320: the check's "2.1 u" is an artefact.** From check_play's own eye point (1575, -448, 28) the parapet does not block: no man's land, the wire and the far trench line are in view | view `ct_eye_step2.png` (and `t_eye_step2.png` for the T side) | No map change. check_play T2 should measure from the highest tier a player box fits on (review 1 said the same) | check_play owner | confirmed artefact |
| W7 | low | `trench_t_1` still "18 u headroom" in T8 | barrel 1727 now 31.3 u from the post (needs 27: 16 half width + 11 radius); 2811 is 33.2 u from `trench_ct_13` | none: a 16-u grid artefact, as review 1 said | | confirmed artefact |
| W8 | low | Water: 182 edge points stand more than 3 u over the ground in 29 places (worst (-1575, -1145) 28 points, (1826, -2192) 22); shattered trees stand in crater pools in no man's land | check_play 7; view `nml_n.png` | Leave (review 1: trimming pools is not a safe delta); look in Hammer at the two worst fire-step feet | ours | open, cosmetic |
| W9 | low | Enemy fire-step eyes see mortar crews: 60 / 380 pairs on the CT crews, 11 / 380 on the T crews, e.g. (-1592, -2880, 34) sees (3323, -1545, 49) | check_play 2 | Design call (L6): one more sandbag course on the enemy-facing breastwork of CT pits 1-2 would even it | design | open |
| W10 | low | `plane_ct_2`'s take-off lane passes poplar crowns (L7; the T lane now clears) | check_play T7 | Raise `AIR.SPAWN_ALT` to 1300 or remove the two poplars | design | open |
| W11 | info | The sound chain's emitters: `tw_whistle_attack` and `tw_plane_dive_1..4` stand in the briefing room (z -2700). The dive pool is moved to each aircraft by `SetSourceEntity`. The whistle fires in the same tick the briefing room empties, and its soundevent (`csgo_mega` with a distance curve) may not reach players already teleported out | probe d); `out/addon/soundevents/soundevents_addon.vsndevts` | In game: listen for it in the trench; if silent, make it 2D or fire it about 0.5 s earlier | ours | in-game check |
| W12 | info | Rain: 12 `tw_rain_*` particle tiles 700 u over both trench lines (start off, `tw_rain` relay) | probe b) | By design; look and FPS in game (`ent_fire tw_rain FireUser1`) | ours | in-game check |

Nothing else turned up in the probes: no light on a prop's origin, nothing the chain added (6 smoke, 12 rain, a relay, 11 sound
emitters) under the ground, no duplicate prop outside the script's parked pools except W5. The views showed no floating or sunken
dressing beyond what check_play lists and no prop through a revetment at the scale the renderer resolves; the T airfield's five
aircraft stand clear of each other and the hangar (check_play T7: ground relief 1-6 u under all ten); the seats in the two pits viewed
close up are clear of props. Many of the wide views are cluttered by stock tree boxes; a second pass with `NOTREE=1` was rendered only
for the six views that needed it. (`out/review2/scene_cache.pkl`, the views' 130k-polygon cache, was deleted afterwards; the script
rebuilds it in about 20 s.)

## Review 1 compared

- **Confirmed fixed:** H2 (blocker archetypes), H3 (woods seeds, flood 21,764), H4 (animated tubes), M3 (barrels 31.3 / 33.2 u from the
  posts), L5 z-fight (0). M6 and the `trench_t_1` T8 flag are check artefacts, as review 1 said (now also seen in an eye render).
- **Still open in the delivered chain:** H1 and M2 were opt-ins and the chain ran without them, so the map that would ship has sealed
  galleries and two `info_map_parameters`. M1 was deferred to step 6 and is not done.
- **Missed by review 1:** the script/map interplay in W1 (step 4's bots are sent to a gallery point that check_play already reported
  unreachable); the duplicate bench pair (W5); the growth of stale compiles from 4 to 10 (W3, after its step-7 table said "nothing new");
  the whistle emitter's placement (W11).

## Deploy notes for the other session

- The script changed in this pass (`src/mg_trenchwarfare.js`, 2032 lines): the deploy list's `maps/scripts/mg_trenchwarfare.js` must be
  taken from the current build, not from the dry run of 15:50.
- W1 and W4 are flags on the chain (`--user-h1 unlock|remove`, `--user-m2`); they need the user's word.
