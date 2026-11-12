# World review 1 (12 Nov 2026): gameplay checks, missing content, fixes

Offline only ("simulated" in the words of `docs/reference/compatibility.md`): nothing here was compiled, opened in Hammer or played.
Tools: `tools/check_play.py` (new: 9 checks plus 1b routes), `tools/view_world.py` (new: plans and flat-shaded views with props),
`tools/check_world.py`, `tools/check_mesh.py`. Eight map builds in all; the eighth is the current `out/addon/maps/mg_monsoon.vmap`
(71.3 MB, 7489 entities, terrain 83 584 quads).

## Results on the final build (8th)

```
cd tools
python check_play.py ../out/addon/maps/mg_monsoon.vmap          # RESULT: clean (9 checks)
python check_world.py ../out/addon/maps/mg_monsoon.vmap         # RESULT: clean (0 off the ground, 0 overlaps, 0 bad spawns, 0 missing models)
python check_mesh.py ../out/addon/maps/mg_monsoon.vmap          # 1095 meshes 0 bad
python make_radar.py ../out/addon ../out/game ; python render_board.py ../out/addon
cd .. ; node tools/build_script.mjs && node test/mock.mjs 32 300 # PASS
```

| Check | Before (04:04 map) | Final (8th build) |
|---|---|---|
| 1 walkability: spawns in one world / targets unreachable | 32/32, 0 of 117 | 32/32, 0 of 120 (waypoints included) |
| 1 stuck pockets > 200 u2 (not escapable by a jump) | 7 (4), 57 088 u2 | 12 (0), 28 416 u2: pig pens, a garden, firebase pit corners; a jump gets out of every one |
| 1b CT/T route ratio, mirror balance (1.00 = even) | B 1.29 (first measured on build 1) | A-D 1.09, C-E 1.06, B 1.04 |
| 2 base spawn pairs with a line of sight | 0 | 0 |
| 3 head-height cover within 600 u, A/B/C/D/E (min 14) | 4 / 3 / 11 / 11 / 43 * | 14 / 17 / 20 / 20 / 42 |
| 4 pads with an obstacle in the rotor cylinder or < 3 lanes | 6 of 6 | 0 of 6 |
| 4 karst crowns without a flat clear landing disc | 3 of 3 (slope 23-33 deg) | 0 of 3 (2 deg) |
| 5 spawns in a mounted gun's line of fire < 900 u | 0 | 0 |
| 6 buried / floating / under water / crown in building / inside solid | 6 / 14 / 3 / 0 / 4 | 0 / 0 / 0 / 0 / 0 |
| 7 water edges above ground / z-fight cells | 159 / 24 | 0 / 0 |
| 8 road max slope / samples >= 20 deg / ground through floors | 38.2 deg / 92 / 3 | 16.1 deg / 0 / 0 |
| 9 nav seeds off walkable ground / NONAV over roads etc. | 0 / 4 | 0 / 0 |
| check_world ground / overlaps / spawns | clean (older check) | clean |

\* The old cover count never counted a sandbag wall (each course measured only its own 18 u). Fixed: a wall is measured as a column per
96 u. Other check fixes this pass: points past the grid edge wrapped into the next column (trees beyond the south edge read as
floating 170 u); floating used the merged walk layers (a bag on a karst crown read as floating 208 u); tree crowns are measured from the
model's own bounds; boulders are exempt from "buried"; check_world tests the parked Apache as cabin + tail boom (the boom is 80 u
and more over the ground, so a sandbag wall under it is no overlap) and no longer pairs an entity with itself.

## Issues (where, severity, fix)

Severity: **high** = a player can get stuck, a station is unreachable, a check fails; **mid** = visible clipping or a design item
missing; **low** = cosmetic or check noise.

### Walkability, routes, balance
| Issue | Where | Sev | Fixed how / left why |
|---|---|---|---|
| Tunnel chamber swallowed the stub's ramp (64-u drop, no way out) | T tunnels | high | Chamber moved 306 u out from the junction (layout.TUNNEL_CHAMBER), clear of every gallery |
| Deck cover closed the bridge: an ox cart beside a sandbag block left no lane, CT walked round by the north ramp (6661 u vs T 5160, ratio 1.29) | bridge deck | high | Blocks from alternate trusses at least 150 u apart, cart taken off the deck; B is now 5521 / 5253 (1.05). No flag or base moved |
| Flag A closed in by the field hut 18 u from the pole plus stacks and baskets (build 2 and 3) | flag A | high | Hut removed, a 70-u keep-out round the pole, baskets at 110-150 u. (build 4) |
| Farm nav seed under the re-fitted ox cart | farm | mid | The farm's yard is a 40-u gap between three huts: the seed moved to the open ground 300 u north (build 5) |
| Garden fences + hut wall made a pen (8192 u2 pocket, jump gets out) | village (329, 2631) | low | Gardens fenced on two sides; the pocket stays (a jump gets out), left |
| Pig pens are pockets (jump gets out) | farm | low | Left: a pen is a pen; a jump gets out |
| Firebase road switchback up to 38 deg | road 0 | high | The road comes down a filled spur (layout.SPUR), all roads grade-limited to 13 deg (roads_apply); max now 16.1 deg |
| Trails started inside paddy cells and cut them | trails A-E, A-bridge | mid | Trails start at the paddy edge; roads no longer reshape paddy cells |
| Route table | new check 1b | - | `check_play.py` 1b: walking distance on the walk graph from each spawn ring to each flag, mirror products A-D, C-E, B; warns over 15 % |

### Cover, sightlines
| Issue | Where | Sev | Fixed how |
|---|---|---|---|
| Flag A 4 head-height pieces | paddies | high | Threshing-floor island (layout.ISLAND), haystacks, a 4-high crate stack, straw stacks in the four cells round the junction, bamboo on the dike junctions |
| Flag B 3 pieces, the deck a 1200-u gallery | bridge | high | Four-course sandbag blocks, a CONEX, crate stacks on the deck; four-course fighting positions on both banks |

### Helicopters
| Issue | Where | Sev | Fixed how |
|---|---|---|---|
| Bunkers, gun pit, tents, conex, M151s, signs in the Apache rotor cylinders | firebase | high | Pads to r 680, bunkers and battery swung between them, a round keep-out per pad (keep_disc); a guard in `World.prop` drops anything over 24 u inside any cylinder and reports it |
| Wind sock pole (part of psp_pad) inside every cylinder | firebase | mid | psp_pad rebuilt without it (`p_base.windsock` is its own prop now, not yet placed: a spot outside the cylinder is left for a later pass) |
| Ground rose 28 / 112 u inside the T pad cylinders (karst talus) | camp pads 1, 3 | high | Pads moved (layout.camp: (-870, -430), (985, 174)) |
| T pads had 2-3 approach lanes, trees in them | camp | high | Lanes chosen per pad among the compass directions whose ground and karst stay under the 30-deg glide; trees kept off them only where they would break the glide (rotor_ok). Now 3 / 5 / 3 |
| Karst crowns: nest ringed the centre, bags past the rim in the air | karst 1, 4, 6 | high | Nest is a crescent at the rim on the valley side, the rest of the crown is the landing disc (slope 2 deg) |

### Clipping and props
| Issue | Where | Sev | Fixed how / left why |
|---|---|---|---|
| Ground through the floors of the C-123 (37 u), French bunker, checkpoint | crash, bridge | high | Flats under each (layout.FLATS), C-123 90 u north out of road 0's blend, checkpoint +2 u |
| Camp hut inside karst 1 (z 436, 270 u from its axis) | camp | high | Karst keep-outs registered before any place is dressed |
| Guard tower in the south bunker (build 1-2), then in the wall and pit 3's ring (build 3) | firebase | high | Tower at 244 deg r 975, the south-west blast wall shortened (build 6) |
| TOC tent over the north-west bunker and the M2 gunner's spot (check_world spawns) | firebase | high | TOC a 0.85 GP tent at (c - 460, c + 600) (build 6) |
| Karst nest crate in its own bags, kit round the crate overlapping | karst crowns | mid | Crate 120 u in from the rim, kit 84-112 u to the sides. (build 4) |
| Haystacks in the paddies touching dike bamboo | paddies | low | Stacks at the cell centres. (build 4) |
| Quad .50 ring around gun pit 1's ammo rack | firebase | mid | Quad .50 to 193 deg r 985 |
| Tree crowns through school, C-123, temple | jungle | mid | Trees refuse a spot whose crown core (0.8 x 0.3 x width) reaches a building (World.prop); roots are exempt (they grip the ruins) |
| Ferns on the river bed, reeds in fish traps, nypa in dead trees | temple, marsh | low | Water test for ferns; fish traps before reeds; nypa palms checked with a 36-u trunk footprint |
| C-123 wing half buried, M35 41 % buried | crash, road 0 | mid | Wing on the flattest free spot (relief < 12 u); wrecks need slope < 8 deg and relief <= 26 u. Build 3 used 14 u and lost all four road wrecks; from build 6 they try both sides of the road at two distances and all four stand |
| Floating banyans at y -5550 (130-170 u) | south map edge | low | Not real: check_play's grid wrapped points past its edge into the next column. Fixed in the check |
| One shell_105 half buried at the ammo point, one boulder at the temple foot | firebase, temple | low | Loose shells taken out of the ammo-point clutter; boulders are set into the ground on purpose (exempt in the check) |
| check_world ground: 62 trees 10-18 u under the field (build 3), 4 dike bamboo (build 4) | everywhere | mid | A mesh-height sink for trees, reverted; dike bamboo tagged as rooted in the crest. 0 now |
| Fish trap 7 u over the marsh bed, banyan in the river at the temple | marsh, temple | low | Traps tagged as staked in the water; no corner banyan or canopy tree below water + 8 / + 12 |
| Tower against the sally blast wall, TOC tent dropped by the rotor guard (build 4) | firebase | high | Blast wall of the south-west sally shortened; TOC a 0.85 GP tent at (c - 460, c + 600) |
| Apache tail over the outer wall (check_world) | firebase | low | Not a clip: the boom is 80 u and more up, the wall 57; check_world now tests cabin + boom |

### Water
| Issue | Where | Sev | Fixed how / left why |
|---|---|---|---|
| River / marsh sheets z-fighting at x 5000 | marsh | mid | River ends on a cell edge (MARSH_X0 - 8), a fitted strip is clipped at its square end: 0 z-fight cells |
| Paddy sheet edges 0.5-3 u over the ground | paddies | mid | Each side moves up the dike flank until the mesh (TER.mesh_low) is 6 u over the water; the paddy tiles are 16-u cells now (32-u cells cut the 36-u dikes): +15 k terrain quads, map 71 MB |
| Upper river edge over the south bank (46 points) | above the fall | mid | Strip widths fitted per vertex; still 46 points because the outer terrain is 128-u cells: the fit tests a 64-u cross: 0 points |
| Marsh south edge (8 points) | marsh | low | Marsh rectangle grows until its edges are over ground, one 64-u cell more: 0 points |
| Waterfall lip sheet edges in the air | waterfall | low | Rock curbs along both sides of the lip: 0 points |

### Content (brief B)
| Item | State |
|---|---|
| Village to 9 hooches | 9 (fitted on the terrace) |
| Gardens and fences | gardens with taro / greens where a 100 x 72 spot is free beside a hut (two fence sides) |
| Two roof-access huts | 1 drying platform at eave height with a ladder; the second finds no free spot with 9 huts on the terrace (left) |
| Waterfall back path | shelf behind the curtain (fall moved 112 u out from the cliff over a rock lip, 80 u headroom) |
| Temple collapsed gallery | roofed passage with a fallen roof slab on the west court (a bored tunnel under the knoll needs a terrain cut: later) |
| Vines / roots on the temple, ferns at the platform foot | done |
| Reeds along both banks | 230 |
| Rice in every paddy cell | 342 clumps, every cell |
| Debris round wrecks, smoke columns | done (C-123, wrecks, two craters, camp fire, burnt hut) |
| Firebase M113 | dropped: no room inside the wire; it stands at the bridge and on the roads |
| Culvert bunker | dropped: 266 x 201, no spot between the gate track, pits and pad 3's cylinder (40-u grid scan) |
| Antenna masts | dropped: guy anchors span 262 x 227; the converted comm stations at TOC and FDC carry the antennas |
| Water trailer | dropped: the guard tower now takes the only free corner (south-west) |
| FDC radios | comm stations placed (search 300 u, slope 11) |
| Ox cart | at the farm, the village and the road-1 wreck; the one on flag A's floor is kept off the flag |
| GP crew tents, second latrine, firebase jeeps | dropped inside the wire (no 422 x 282 spot left); one M151 parks by the spur road below the gate |
| Temple court | 3 balustrades and 1 lion fit (the gate, the tower, the DShK, the flag crate and the gallery take the court); fallen blocks only on the slope ring |
| Village shrine, market stalls, cook fires | placed before the extra huts; the shrine, one stall and two fires still find no spot (the three road keep-outs cross the yard): left for a yard re-plan |

## Changed files
`tools/layout.py`, `mv_places.py`, `mv_terrain.py`, `mv_entities.py`, `p_base.py` (psp_pad without the pole, new windsock),
`check_play.py` (new), `view_world.py` (new), `check_world.py` (Apache two-box test, no self pairs); radar, board, script rebuilt; props rebuilt: psp_pad, windsock (`out/props.json` 118). Entity contract unchanged
(`docs/CONTRACT.md` not edited); `out/world_sites.json` gained `waypoints` and `landing` (check_play reads them).

## Left (deliberate)
- Stuck pockets: 12, every one escapable by a jump (pig pens, one garden corner, firebase pit corners).
- Village yard: shrine, one market stall, two cook fires do not fit; second climbable platform does not fit; windsock prop built but
  not placed; temple court holds 3 balustrades and 1 lion (box footprints are too coarse for the court).
- Water trailer, culvert bunker, antenna masts, GP crew tents, second latrine, firebase M113 dropped inside the wire (reasons above).
- 160 walkable cells deeper than 60 u (the waterfall pool and the river channel; reported, not a failure).

## Next
1. Re-plan the village yard so the shrine and stalls get room (the road keep-outs are 70 u wide through it).
2. Place the windsock outside each pad's cylinder; true (hull) footprints for the temple court dressing.
3. Compile and look at it in Hammer.

## Pass 2 (12 Nov 2026): the leftovers, the temple, the dynamic shell

Offline only, as above. Five map builds (`out/logs/wd_map3.log`; the fifth was allowed by the coordinator); the fifth is the current
`out/addon/maps/mg_monsoon.vmap`. Numbers below are from the fifth build (table at the end).

### Stuck pockets (12 -> 0)
| Pocket (pass 1) | Cause found | Fix |
|---|---|---|
| Firebase pit corners, quad .50 ring (6) | The staggered courses leave an 18-u step at every wall end: players walked up onto the wall tops and dropped into the gaps between rings | `World.cap()`: a player clip over every sandbag wall (`bag_arc`, `bag_line`), from 16 u to 200 u over the ground, inside the bags' own footprint (a wider one closed gaps and made new pockets in build 1; a 70-u one let a latrine roof be the step onto the caps in build 2) |
| Rocket / AA pit berms at the camp (2) | Same thing on the berm crests (a crate or a rucksack as the step) | `berm_arc` gets the same clip over its crest |
| Pig pens at the farm and the village (3) | Step in over the trough, no way out | `World.clip_footprint()`: every `pig_pen` gets a clip box over its footprint (nobody goes in) |
| Tunnel stub at (-3176, 2280) (1) | Floor vertices took their height from the nearest gallery sample, so where the stub leaves the junction two galleries 32 u apart in depth met in one 16-u cell | `tunnel_plan`: the floor grade between neighbouring vertices is limited to 0.75 (min-plus relaxation, the chamber stays flat) |
| Garden corner at the village (pass 1 list) | Gone with the yard re-plan | - |
| Firebase south-west, builds 1-3: a 22 000 u2 yard between the quad .50 ring, pit 2 and the south-west bunker, three single cells | Entered only by dropping off the bunker's parapet; the way out was closed by a drum cluster (the clutter moved when the sign rings were randomised) | `POCKET_FILL` in `firebase()`: those cells (check_play's stuck cells of build 3, column runs inset 6 u) are clipped off. Build 4 left 5 small ones round the quad .50: the mount's 24-u base was the other drop-off point, so its top is clipped from 20 u up (the gunner works it from the seat behind) and the remnant cells were added to the fill. The firebase uses its own RandomState, so the cells stay put; re-derive after any change to `firebase()` |

### Village yard
Yard pieces now go in right after the designed huts and before the extra ones, at designed spots: the spirit house on the open
north side between the school and the west road, market stalls along the road edges (a market street on the temple road), the ox cart
by the west road; three cook fires in front of huts (one with a smoke column). The second climbable platform did not fit beside a hut:
the platform search now also tries free-standing spots on rings out to r 715 (slope up to 12 deg, posts follow the ground). Result:
9 huts, shrine, 2 market stalls (a third finds no spot), 3 cook fires, 2 platforms (waypoints `village platform 1/2` reachable). The
terrace radius was not changed.

### Temple
- Props (`p_temple.py`, rebuilt + `lod_decimate.py`): `guardian_statue` is a sculpted singha (ellipsoid haunches, rump, ribs, chest
  and shoulders, round forelegs, paws with toes, a turned head with muzzle, open jaw, tongue, brow, bulging eyes, ears, three rows of
  mane curls, a curled tail; fbm erosion over all of it) on a moulded pedestal; `naga_balustrade` is a smooth banded serpent (14-sided
  tube, scale ridges, belly flattening) on moulded posts rearing into a fan of seven petal lobes with sculpted cobra heads (the middle
  one larger). Hull boxes unchanged in size, so placement did not move.
- New props: `khmer_pillar` / `khmer_pillar_broken` (square gallery pillar, carved panels, stepped capital; the broken one snapped with
  splinters standing and its capital at its foot), `enclosure_wall` / `enclosure_wall_ruin` (laterite, coping, collapsed in steps with
  spilled blocks), `root_wall` (a wall split by a strangler fig: blocks pushed apart and tilted, roots over the top and down both faces,
  aerial roots), `paving_slabs` (worn slabs of uneven size and height, a few missing or tilted; walk-over, non-solid).
- Placement: paving over the court and the upper terrace (stretched to the strips round the tower terrace, never inside it: build 1
  read 14 tiles as buried), a pillared east gallery with an architrave, lions at the foot of the tower stair and at the foot of the
  north / east / west stairs (8 lions in all), naga balustrades flanking the north causeway, porticos of pillars with architraves at
  the three enclosure openings, laterite enclosure walls on the knoll top, rubble fields as clusters where walls fell, banyan root
  masses over the platform corners and the gate (as before).
- Left: the knoll falls at 26-40 deg beyond r 420 (measured), so an outer enclosure ring on the slope is not possible without a new
  terrace in layout; the enclosure stands on the knoll top only where it fits. `root_wall` and `enclosure_wall_ruin` are built but
  not placed: their roots and rubble reach over the court edge where the balustrades stand (build 3: roots through a portico pillar,
  check_world overlaps), and on the knoll foot no spot has under 44 u of relief for a 210 x 145 footprint. They need the outer terrace.

### Firebase
- Wind sock: placed by a scan round the pad cluster, outside every rotor cylinder and off the approach lanes (`rotor_ok`); check 4: 0 pads
  with an obstacle, every pad 3+ lanes.
- The six items world review 1 dropped, re-tried with `World.scan()` (the whole wire disc, 30-u grid, four yaws, vectorised slope): the
  water trailer fits; the second latrine fitted but its roof was the step onto the wall caps (build 2 pockets), so it is left out
  again; antenna mast, culvert bunker, GP crew tent and the M113 find no spot (no free 262 x 227 / 266 x 201 / 360 x 240 / 200 x 105 spot
  between the rotor cylinders, the pits and the track).
- Signs: the claymore / mines signs stood every 24 / 45 deg on exact rings; now uneven spacing, some missing, in / out and off square.

### Repetition and pattern review (zoomed view_world / vmap_preview renders, `out/review/p2/`)
| Seen | Where | Fix / left |
|---|---|---|
| Sign rings at exact angle steps | firebase | randomised (above) |
| Haystacks on the exact cell centres, a symmetric 8-point pattern | flag A cells | +-40 u jitter |
| Rubber trees in straight rows | crash site | left: a plantation is planted in rows (the slide cuts a swath through them) |
| Rice clumps on a 50-u lattice | paddies | left: jittered +-12 u and transplanted rice does stand in rows |
| Blocky lion / naga | temple | rebuilt (above) |
| Bare court and knoll | temple | paving, statuary, porticos, walls, root walls, rubble clusters (above) |

### shell_105 as a prop_dynamic (asset compile note)
`mv_shell_*` and the cache list used `shell_105` (a `static_prop_model`), which the map compile deletes on a prop_dynamic. New
`shell_105_dyn` (`p_arty.py`, spec `dynamic: True`: `model_archetype ""`, `primary_associated_entity "prop_dynamic"`), built; the
entities point at it. Audit of every prop_dynamic model the generator writes: 24 models, only shell_105 was wrong. `check_world.py`
check 7b now fails on any prop_dynamic of ours whose .vmdl archetype is not "" or `animated_model` (it caught shell_105 on the old map).

### Noticed, not changed
- The make_map "water" stage now takes ~180-300 s (was 7 s): `mv_terrain.mesh_low` calls `layout.height` point by point (14 k calls,
  20 ms each). Not caused by this pass's files; worth vectorising.

### Results on the fifth build
| Check | Pass 1 final | Pass 2 final |
|---|---|---|
| check_play 1 stuck pockets (no jump out) | 12 (0), 28 416 u2 | **0 (0)** |
| check_play 1 targets unreachable | 0 of 120 | 0 of 121 (both village platforms are waypoints) |
| check_play 1b mirror balance A-D / C-E / B | 1.09 / 1.06 / 1.04 | 1.15 / 1.10 / 1.06 (under the 15 % warning) |
| check_play 3 head-height cover A/B/C/D/E (min 14) | 14 / 17 / 20 / 20 / 42 | 14 / 17 / 21 / 31 / 42 |
| check_play 4 pads with an obstacle / < 3 lanes | 0 of 6 | 0 of 6 (wind sock placed) |
| check_play 6 buried / floating / under water / crowns / inside solids | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / 0 |
| check_play 7, 8, 9 | clean | clean |
| check_world (incl. new 7b archetypes) | clean | clean (24 prop_dynamic models, 0 wrong; 0 overlaps) |
| check_mesh | 1095 meshes 0 bad | 1184 meshes 0 bad |
| map | 71.3 MB, 7489 entities, 6826 prop_static | 72.4 MB, 7526 entities |

Builds: 1 caps 3 u wider than the bags (closed gaps: new pockets), paving read as buried, ferns in root walls; 2 a latrine roof stepped
onto the 70-u caps; 3 drums closed the way out of the south-west yard, root walls overlapped a pillar / balustrade; 4 quad .50 base
drop-offs; 5 clean.

### Changed files (pass 2)
`tools/mv_places.py` (caps, pen clips, scan, tunnel grade, firebase scans / wind sock / signs / pocket fill / quad .50 clip, village
yard, temple dressing, haystack jitter, vectorised slope in `park`), `tools/p_temple.py` (lion, naga, 6 new props), `tools/p_arty.py`
(`shell_105_dyn`), `tools/mv_entities.py` (shells and the cache list on the dynamic twin), `tools/check_world.py` (7b). Props built:
guardian_statue, naga_balustrade, khmer_pillar(_broken), enclosure_wall(_ruin), root_wall, paving_slabs (+ LODs), shell_105_dyn.
`docs/CONTRACT.md` not edited (entity names unchanged).

## Pass 3 (12 Nov 2026): bot nav cost, the leftovers, route balance

Offline, then compiled (record: [BUILD_LOG_1.md](BUILD_LOG_1.md) "Stage 3"). Six map builds (`out/logs/p3_map1..6.log`); the
sixth is the current `out/addon/maps/mg_monsoon.vmap`. Before / after renders in `out/review/p3/` (`*_before.png` from the stage 2
map, kept as `out/review/p3/mg_monsoon_s2.vmap`; `*_b1.png` and the final `village_after.png`, `temple_after.png`,
`firebase_after.png`, `temple_ghat_cam_after.png` and the other `*_cam_after.png` views).

### Bot nav (the most expensive thing in the compile)
The stage 2 compile made **33,661 nav areas**; "Compute Approach areas" alone took 26 min, and mg_trenchwarfare lost FPS with bots
at 44k. The old NONAV markup only covered steep cells, karst, deep river and a far band (94 boxes of 256 u).

- `mv_entities.nonav_boxes()` now keeps nav only where bots fight and walk (`nav_play_mask`): the two base plateaus (+100 / +150 u),
  a 820-u disc round flags B-E, the whole paddy field and a 650-u disc at A, the north-bank paddies, the farm, the C-123, the bridge
  and both bank heads, the three tunnel portals (420 u), every road and trail (+160 u beyond its half width), and two declared
  routes (`nav_corridors`): the west ford (camp trail to the paddies) and CT's walking route to the temple (out of the gate, down the
  north-west flank and the gully floodplain, across the river to the west stair, with a branch to the new ghat). Inside those, steep
  cells (except on a route), karst and deep river (except fords, the bridge and the routes) stay NONAV. Everything else, the outer
  valley sides, the marsh, the waterfall gorge, the jungle between the routes and the karst crowns (boxes now reach 320 u over each
  crown), is NONAV. 128-u cells merged into rectangles of up to 16 x 16: **243 boxes**. Over the tunnels a box starts 12 u over the
  gallery roof (cells where the roof is within 40 u of the ground stay open), so the galleries keep their nav.
- `check_play.py` check 9 measures it: the walk graph flooded from the WALKABLESEED boxes and base spawns with every node inside a
  NONAV box taken out (what island removal leaves), in 16-u cells and m2, projected to nav areas linearly from the stage 2 compile
  (first calibrated on the stage 2 flood, 378,891 cells = 33,661 areas; now on the pass 3 compile, 115,469 cells = 15,033 areas). It fails when any flag, spawn, flag spawn, kit, rack, board seat,
  mount seat or tunnel portal is off that nav, or a base cannot route to a flag and back on it; it warns over 15,000 areas or when a
  bot's nav route is over 1.35 x the walking route. `--nav-plan` runs it with the boxes the generator would write now, before a
  regenerate.

| | Stage 2 map | Pass 3 |
|---|---|---|
| NONAV boxes | 94 (256 u) | 243 (128 u) |
| nav flood (16-u cells) / m2 | 378,891 / 62,580 | 115,458 / 19,069 (30 %) |
| nav areas (compiled) | 33,661; Compute Approach areas 1,569 s | **15,033**; Compute Approach areas **348 s** (the estimate before the compile said ~10,260 on the stage 2 calibration: the kept ground is cut into smaller areas than the open valley taken out; check 9 is recalibrated on this compile, 0.130 areas per cell) |
| stations off the nav, routes lost | - | 0, 0 (waypoint "behind the waterfall" off the nav by design) |
| bot nav routes CT / T to A, B, C, D, E | - | 7028 / 4632, 6348 / 5712, 7798 / 3511, 4909 / 6904, 3598 / 7547 (walking: 7028 / 4632, 5632 / 5291, 7349 / 3511, 4799 / 6894, 3598 / 6797; worst detour 1.13) |

The first plan routed CT bots to D round by the bridge (9,009 u against 5,199 walking): the gully corridor ran from the base centre
up a 40-degree flank, and the river bank at the temple was steep. Fixed by the route above and by keeping steep cells on routes open
(nav generation itself skips what is too steep).

### Route balance
Pass 2 had moved the mirror balance to A-D **1.15**, C-E **1.10** (1.105), B 1.06 (not the 1.04 / 1.09 / 1.06 of pass 1). Every CT
route grew by about 105 u in pass 2: the clips over the sandbag walls (pass 2) stopped the walk graph shortcutting over gun pit 1's
ring, which stands just inside the gate. Real, so kept.
- **The temple ghat** (new): the south stair's lowest step hung 140 u over the river (the knoll's south face drops into the water): a
  grand stair that ended in a drop. A landing at its foot and two 25-step flights down to the water along the bank, west and east,
  built out from the cliff. The river approach from the CT side now climbs it through the gate: CT to D 5199 -> **4799**, A-D
  **1.06**.
- C-E stays **1.11** (C 7349 / 3511, E 3598 / 6797; my changes moved it by 0.004). The cause is the firebase: the CT spawn ring
  sits behind gun pit 1, so every CT route first walks round the pit to the gate (T's camp has no such detour; T reaches E almost
  in a straight line, 2 % over the beeline). Fixing it means moving the CT deploy point (rack + spawn ring) toward the gate or
  turning the battery, both `layout.firebase()` changes that re-derive the firebase's POCKET_FILL: left for a pass that can rebuild
  the firebase (below, "Left").

### The leftovers of pass 2 (what was actually still open)
Pass 2 had already placed the village shrine, 2 stalls, 3 cook fires, 2 platforms and the firebase wind sock. Still open were: a
third market stall, the temple court (3 balustrades, 1 lion), root_wall / enclosure_wall_ruin unplaced, five firebase items.
| Item | Pass 3 |
|---|---|
| Village market | Re-planned: the market lane on the temple road is laid out right after the designed huts, before the road-side huts (which had taken the lane edges): **3 stalls** in a row with baskets, water jars and fish traps round them; the spirit house gets its offerings (rice basket, water jar) in front |
| Village platforms | Both drying platforms (2 waypoints, reachable): hut-side spots beside the designed huts first, then the road-side huts, then a ring spot. The extra huts stay on the terrace except north and east (at 680-700 u south-west they had taken the knocked-out T-54's and a bamboo thicket's spots: both back) |
| Village huts | **8** (pass 2: 9). The market lane and the second platform take the room of one; extras are the small hooch only. Cover at C 25 / 7 (pass 2: 21 / 8) |
| Hut roofs | build 3 found a hut roof as a stuck pocket (no jump out): every hooch gets a player clip over its footprint (as the pig pens) |
| Temple court | The flag's supply crate stood at the head of the west stair and took a balustrade's and a lion's spot; it now goes in after the statuary (south-east corner by the DShK, kit station `mv_kit_d` moves with it). **4 balustrades, 4 lions** (both at the tower stair foot, 14 u further north clear of the pole; one at each side stair's head) |
| Temple ghat | New (above): landing + two flights, keep-outs on it |
| root_wall, enclosure_wall_ruin | On the knoll top they cannot stand (the knoll falls 26-40 deg past r 420: relief 62-77 u under the footprint on every edge). Placed at the knoll **foot** north and east (r 700-820, relief under 44 u), off the stair approaches and the west routes: **1 strangler-fig wall, 1 collapsed run** with its blocks spilled down the slope |
| Firebase: culvert bunker, M113 | **Outside the gate**, on the flat apron south of the road (z 620 runs 110-240 u past the wire there): the culvert bunker as the gate's guard bunker, the M113 parked beside it (a player clip over the APC: build 1 found its roof a stuck pocket). Placed last in `firebase()`, so its RandomState and POCKET_FILL are untouched |
| Firebase: antenna mast, GP crew tent, second latrine | Still no room inside the wire (scan of the whole disc, as pass 2); not placed outside (a mast and crew tents belong inside). Left |
| Wind sock | Already placed in pass 2 (scan outside the rotor cylinders); unchanged |

### Checks on the sixth build
| Check | Stage 2 map | Pass 3 (build 6) |
|---|---|---|
| check_play 1 stuck pockets (no jump out) | 0 (0) | 1 (0): 256 u2 at (-1064, 1976) in the village, a jump gets out |
| check_play 1b A-D / C-E / B | 1.15 / 1.10 / 1.06 | **1.06** / 1.11 / 1.06 |
| check_play 3 cover A-E | 14 / 17 / 21 / 31 / 42 | 14 / 17 / 25 / 38 / 42 |
| check_play 4, 5, 6, 7, 8 | clean | clean (check 4 now treats the nypa palm as a tree, as the placer does) |
| check_play 9 nav | 15 seeds, 94 boxes | 15 seeds, 243 boxes, ~10,260 areas, 0 stations off, 0 routes lost |
| check_world | clean | clean |
| check_mesh | 1165 meshes 0 bad | 0 bad |

Builds: 1 the M113 roof and a hut roof as pockets, one stall short, one platform short, the T-54 and a thicket lost to outer huts;
2 platforms first left only 5 huts; 3 a hut roof pocket (no jump out), 7 huts; 4 and 5 two dressing props on a turned platform deck overlapping
(check_world; the basket now stands at the ladder's foot); 6 clean.

### Left (pass 3)
- **Nav 15,033 areas**, at the 15,000 line rather than well under it (approach areas 26 -> 6 min). The next cut, measurable with
  check_play.py --nav-plan before a regenerate: flag discs 820 -> 650, roads + 160 -> + 110, the base discs to the wire; or fewer
  areas inside the bases (the firebase and camp clutter cut the nav into small pieces).
- **C-E route balance 1.11** (target 0.9-1.1): the CT deploy point behind gun pit 1 (above). Needs a `layout.firebase()` change (deploy
  ring toward the gate, or the battery turned) and the firebase's POCKET_FILL re-derived from check_play.
- Firebase antenna mast, GP crew tent, second latrine: no room inside the wire.
- Village 8 huts (design: 9); one jump-escapable 256-u2 pocket in the village at (-1064, 1976).
- Bots have no nav behind the waterfall, on the karst crowns, in the marsh or in the jungle off the routes (by design); a bot that
  ends up there is re-deployed by the script's leash (stood still 20 s).

### Changed files (pass 3)
`tools/mv_entities.py` (nav plan: `nav_play_mask`, `nav_corridors`, `tunnel_roof`, new `nonav_boxes`), `tools/check_play.py`
(check 9 estimate and bot routes, `--nav-plan`, nypa as a tree), `tools/mv_places.py` (temple ghat, court order, knoll-foot ruins;
village market lane, platforms, hut roof clips; firebase gate items). No props rebuilt, no layout change; `docs/CONTRACT.md`
unchanged.

## Pass 4 (12 Nov 2026): C-E balance, nav toward 12,000, the village, the firebase leftovers

Offline, then compiled (record: [BUILD_LOG_1.md](BUILD_LOG_1.md) "Stage 4"). Five map builds (`out/logs/p4_map1..5.log`); the fifth is
the current `out/addon/maps/mg_monsoon.vmap`. The pass 3 map is kept as `out/review/p4/mg_monsoon_p3.vmap` for the before renders.

### C-E route balance (the CT deploy point)
Every CT route started behind gun pit 1: the spawn ring (rack at base centre + (-20, -230)) lay south-east of the pit and the gate
north-west of it, so each route first walked round the pit's ring. Before moving anything, every candidate ring centre inside the wire
(60-u grid) was measured on the pass 3 walk graph (reverse Dijkstra from each flag, the min over the 16 ring points, the T side fixed).
Moving the ring toward the gate shortens every CT route by the same amount, so A-D and B move with C-E: a 500-u move (the open ground
north of the pit) would have made C-E 0.87 and A-D 0.87. The chosen point, 190 u west (rack at centre + (-200, -180)), takes 133 u off
each CT route. Further west the ring meets pit 2's sandbags, further north the FDC bunker. The battery was not turned: a pit at 280 deg
would stand in pad 1's rotor cylinder.

| check_play 1b | Pass 3 | Pass 4 (build 5) |
|---|---|---|
| CT / T to A | 7028 / 4632 | 6895 / 4632 |
| CT / T to B | 5632 / 5291 | 5499 / 5291 |
| CT / T to C | 7349 / 3511 | 7216 / 3513 |
| CT / T to D | 4799 / 6894 | 4626 / 6894 |
| CT / T to E | 3598 / 6797 | 3465 / 6797 |
| mirror balance A-D / C-E / B | 1.06 / **1.11** / 1.06 | **1.00 / 1.05 / 1.04** |

The firebase's `POCKET_FILL` was re-derived (a scratch probe takes the fill clips out of check_play's scene and lists the stuck cells
inside the wire; build 3 showed that the new cells alone reopen the pass 2 remnant pockets, so the fill is the union of both, plus
build 4's three remnant cells): 50 column runs, 139 cells. New ones: the ammo point's yard behind its crate stacks (19 cells, entered by dropping off the stacks), the foot of the
tower ladder, one cell by pit 3 and two by the east bunker.

### Nav toward 12,000 areas
Measured with `check_play.py --nav-plan` (and a scratch probe running several settings on one walk graph) before regenerating. Where
the pass 3 nav was: base discs 38,600 cells, the five flag discs 32,400, road margins 27,500 (14,200 of them in no other zone), the
corridors 10,100, the paddies 8,800.

| Setting (`mv_entities`) | Pass 3 | Pass 4 | Cells (estimate) |
|---|---|---|---|
| all as pass 3 | | | 115,469 (15,033 compiled) |
| `NAV_ZONES['flag']` | 820 | 600 (capture radius 350, flag spawns at 230, cover counted to 600) | 110,410 at 650 alone |
| `NAV_ZONES['flag_a']` | 650 | 600 (the paddy field stays whole) | |
| `NAV_MARGIN` (beyond a road's half width) | 160 | 64 | 111,645 at 110 alone |
| `NAV_ZONES['ct_base']` | plateau + 100 (1300) | plateau - 70 (1130: the wire at 1090 + 40) | |
| `NAV_ZONES['t_base']` | plateau + 150 (1400) | plateau - 50 (1200: pads, AA pits and hooches lie within r 1000) | |
| all four together | | | **90,815** on build 5 (~11,823 areas on the pass 3 calibration), 250 NONAV boxes |

Check 9 on build 5: 0 stations off the nav (waypoint "behind the waterfall" off by design), every flag routed from both spawn rings
and back; bot nav routes CT / T: A 6895 / 4632, B 6284 / 5712, C 7815 / 3513, D 4776 / 7054, E 3465 / 7622 (worst detour C 1.08 x the
walking route). The estimate is linear in cells; what was cut (base rims, road shoulders, flag rims) is open ground, which the compiler
covers with larger areas than the average kept cell, so the compile was expected somewhat above 11,800. **Compiled: 12,597 areas**
(stage 4; check 9 is recalibrated on it, 0.139 areas per cell). "Compute Approach areas" took 454 s (stage 3: 348 s): not
proportional to the count, the dense base and village nav is what costs there.

### Village
- **Pocket** (256 u2 at (-1064, 1976), a jump got out): a crater stone 20 u from the south-west hut's corner left one cell between them
  that a player dropped into off the stone. Crater stones now keep a 40-u pad from every prop (`roads_and_craters`); 0 pockets there.
- **9th hut**: a last ring of spots on the terrace edge (r 620-740, not 195-285 deg where the T-54 and a thicket stand), each at least
  300 u from every standing hut (they stand 300-400 apart) and fitted with a 24-u pad. One fits: `hooch_b` at (470, 2430), r 771, east,
  in its own clearing beyond the pig pen (no neighbour within 300 u). It took one hedge bank's spot on the outer ring (hedges /
  thickets 2 -> 1). 9 huts, 2 platforms, 3 stalls, 3 cook fires, the shrine.

### Firebase: antenna mast, crew tent, second latrine
The deploy point's move freed the strip between the FDC bunker, pit 3 and pad 1's rotor cylinder, but only 190 u wide between the
spawn ring and the wind sock. The antenna mast needs 248 u with its pad (guy anchors 262 x 228), a GP crew tent (0.85) 260 u: **no
room, left out**. Build 2 placed the **second latrine** there, against the FDC bunker's back wall (the scan takes the spot nearest the
centre); a latrine on the command bunker is not where one stands, so it now needs a 40-u pad and 450-810 u from the centre, and finds
**no spot: left out**. The water trailer (scan) took the freed strip by the FDC (it stood by the south wall in pass 3). The culvert bunker
and the M113 are no longer tried inside the wire: both stand at the gate since pass 3.

### Also fixed
- Build 2: a nypa palm 7.4 u over a slope (check 6): understorey nypa palms are sunk to the coarse terrain mesh's low side under their
  36-u trunk footprint (`TER.mesh_low`, minus 18 tan(slope)). Build 4: check_world then read 25 of them as more than 8 u under the
  smooth field; those are listed as exceptions (tag "rooted in slope"), as the dike bamboo are.

### Checks on build 5
| Check | Pass 3 (build 6) | Pass 4 (build 5) |
|---|---|---|
| check_play 1 stuck pockets (no jump out) | 1 (0): 256 u2 in the village | **0 (0)** |
| check_play 1 targets unreachable | 0 of 121 | 0 of 121 |
| check_play 1b A-D / C-E / B | 1.06 / 1.11 / 1.06 | **1.00 / 1.05 / 1.04** |
| check_play 3 cover A-E | 14 / 17 / 25 / 38 / 42 | 14 / 17 / 26 / 38 / 42 |
| check_play 4, 5, 6, 7, 8 | clean | clean |
| check_play 9 nav | 243 boxes, 115,469 cells, 15,033 areas (compiled) | 250 boxes, 90,815 cells, ~11,823 estimated, **12,597 compiled**; 0 stations off, 0 routes lost |
| check_world | clean | clean (6,841 prop_static, 0 overlaps, 0 off the ground) |
| check_mesh | 0 bad | 1,377 meshes 0 bad |
| map | 57.9 MB, 7,674 entities | 57.9 MB, 7,663 entities |

Builds: 1 the C-E move measured (1.05), the old fill no longer matched (4 pockets without a jump out, the ammo yard), the trailer took the
freed strip; 2 latrine against the FDC, a nypa palm floating, the 9th hut placed; 3 the derived fill alone reopened 4 pass 2 pockets;
4 three remnant cells, 25 sunk nypa palms read as buried by check_world; 5 clean.

Renders (`out/review/p4/`): `firebase_before.png` / `firebase_after.png` and `village_before.png` / `village_after.png`
(`tools/vmap_preview.py`, world meshes only: the changes here are props, so they show the same ground), and the plans with props and
the walk graph, `firebase_plan_before.png` / `firebase_plan_after.png`, `village_plan_before.png` / `village_plan_after.png`
(`view_world.py top`), looked at: the spawn ring now west of the FDC with open ground to the gate track, the water trailer in the strip
by the FDC, the ammo yard clipped (no magenta); the 9th hut east beyond the pig pen with its own yard, no pocket at the crater stones.

### Left (pass 4)
- Antenna mast, GP crew tent, second latrine: no clean room inside the wire (above).
- One hedge bank fewer at the village (the 9th hut stands on its spot).
- Nav 12,597 areas compiled; approach areas 454 s. Further cuts belong inside the bases (fewer, larger areas among the clutter), not
  on the outer rims.

### Changed files (pass 4)
`tools/layout.py` (CT rack and spawn ring), `tools/mv_entities.py` (`NAV_ZONES`, `NAV_MARGIN`), `tools/mv_places.py` (firebase scan
order and latrine rule, no inside culvert / M113 tries, `POCKET_FILL` re-derived; village 9th-hut ring; crater stones pad 40; nypa sink).
No props rebuilt; `docs/CONTRACT.md` unchanged. Repo: `create/check_play.py` gained the nav estimate and gate (`nonav_nodes`,
`nav_estimate`, `nav_gate`, Adapter `nav_cal` / `nav_target` / `nav_detour` / `nav_stations` / `nav_routes` / `nav_starts` /
`nav_seed_ok` / `planned_navboxes`, `--nav-plan`).
