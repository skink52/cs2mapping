# mg_monsoon: Garry's Mod Workshop models

Models taken from the GMod Workshop where they beat the procedural props of DESIGN.md 4.1. Catalog: `tools/gmod_assets.json`;
tool: `tools/gmod_assets.py`; machine-readable result: `out/gmod_models.json` (`{name: {model, bounds, tris, replaces, credit,
pivot, attach, ...}}`). **Wired into the map on 12 Nov 2026 through `tools/mv_models.py`** (one table: logical name -> converted
model or procedural fallback, pivots, seats; exported to `layout.json` `models` for the script). In use: `hip_slick`, `hip_upper`,
`hip_rotor`, `hip_tail`, `m101` + `m101_gun`, `m2_tripod` + `m2_gun`, `dshk_tripod` + `dshk_gun`, `heli_wreck` (as the prop_dynamic
twin `heli_wreck_dyn.vmdl` that `mv_models.ensure_dyn()` writes), `m113`, `m35`, `ural`, `pbr`, `m151`, `gaz69`, `bm21`, `zpu4`, `t54`,
`comm_station`, `nva_ammo_case`, `nva_ammo_case_open`, `sandbag_cover`, and the `rs_*` foliage except the rejected two. Not used
(reasons in `mv_models.UNUSED`): `hind`, `huey`, `lssc_boat`, `pbr_mcv`, `m114_howitzer`, `m40_rr`, `m60_gun`, `mortar_m1`,
`rocket_grad`, `skyraider`, `tent_gp` (our `gp_tent` kept), `wood_tower` (our `guard_tower` kept), `sandbag_fort` (one convex hull:
its roofed inside would be an invisible solid), `w_*`. Seat, door-gun, pod and hub numbers of the Mi-8 were measured from the
converted SMDs and are in `mv_models.HELIS`.

**How far this was checked:** converted and looked at in a software render of the written SMDs and vmats (`out/gmod/view/<name>.png`,
contact sheets `out/gmod/view/_sheet1..3.png`). Not compiled with resourcecompiler, not seen in Hammer or in game.

**Licence position:** almost everything good on the Workshop for this theme is a port from a commercial game. That is acceptable
for the private server; it is a blocker for a Steam Workshop release of the map. The "rip" column says which. Only the
Neiremberg props (tent, tower) and the small helicopter wreck have no stated commercial source, and none of them carries an
explicit licence. For a Workshop release keep the procedural props, or ask the authors.

## Pipeline

```
python -I tools/gmod_assets.py fetch   [--only id,id]     SteamCMD anonymous, workshop_download_item 4000 <id> -> out/gmod/<id>/x/
python -I tools/gmod_assets.py list    <id> [--grep rx] [--stats | --bones]
python -I tools/gmod_assets.py convert [--only name,..] [--force]
python -I tools/gmod_assets.py view    [--only name,..]   out/gmod/view/<name>.png (front-left, rear-right, side, top)
python -I tools/gmod_assets.py report                     out/gmod_models.json
python -I tools/gmod_assets.py prune   [--gma]            frees disk (unused extracts, unused model files, rejected outputs)
```

- Download: SteamCMD with `+force_install_dir out/gmod/_steam` (its own `appworkshop_4000.acf`, deleted before each item, so the
  "Success, then the files vanish" re-download trap of `docs/creation/gmod-playermodels.md` cannot bite). The archive (`.gma`, or
  the legacy LZMA `.bin`) is extracted with `create/playermodels/gma.py` (`models/` and `materials/` only) and then deleted.
- Convert: `create/mdl2cs2.py` per item (bind pose, `csgo_complex` vmats with colour / normal / roughness / alpha test, PNGs up to
  2048, LOD1-4 from `lod_decimate.py`, one convex hull, `--plain-mat` so the source textures are kept as they are). Output:
  `out/addon/models/mv/ext/<name>/` and `out/addon/materials/models/mv/ext/<name>/`.
- Added by `gmod_assets.py` on top of mdl2cs2:
  - `split` + `pivot`: one model per bone group, a group's origin moved onto its bone (rotor hubs), the old position recorded as `pivot`.
  - `origin_xy_bone`: whole model's origin put under a bone (the rotor mast), z on the ground.
  - `parts`: MDLs the GMod addon assembles in lua (carriage + wheels + traverse ring) welded into one model at the lua offsets;
    hull and LODs rebuilt. The lua was read as text only (`ENT.YawPos`, `ENT.TurretPos`).
  - `ground`: origin kept in x/y where the addon has it (the pivot), lowest point on z 0; `source_origin_z` says how far it was lifted.
  - `hulls N`: N convex hulls (slabs along the long side) instead of one, for fuselages and vehicles.
  - `matsub_of`: a variant shares another item's materials.
- Downloaded files are untrusted: every Python step that parses them runs with `-I`, nothing in the download folders is run, lua is
  only read as text.
- Re-converting an addon whose extract was pruned: `fetch --only <id>` first.

## Conventions of every converted model

- Scale 40 units per metre (true size; the addon's inch scale x 1.016, others by a real length). `+X` is the nose / muzzle / front,
  `+Z` up. Origin on the ground (z 0) under the model unless stated. Bounds below are mins..maxs in units.
- Vehicles and props are `static_prop_model` (prop_static); helicopter parts, gun parts and the rocket are written `--dynamic`
  (no archetype, prop_dynamic).
- Foliage (`rs_*`) carries a convex hull like everything else: place it non-solid.

## The T helicopter: `hip` (Mi-8, Gredwitch pack 2165664559)

Origin: on the ground under the main rotor mast, nose +X (same convention as `p_heli.py`). Fuselage 741 u long (18.5 m), 163 u
to the cabin roof, wheels on z 0. The cabin door is open on the left (+Y) side with a door gun in it.

| Model | Replaces | Bounds | LOD0 tris | Place at (in the body's space) |
|---|---|---|---|---|
| `hip_upper` | `heli_hip_gun` | -517,-134,0 .. 224,136,163 | 24663 | origin; gunship: 6 UB-16 rocket pods on outriggers, 2 door guns + tail gun |
| `hip_slick` | `heli_hip` | -517,-96,0 .. 224,98,163 | 13827 | origin; no pods / outriggers, left door gun only; shares `hip` materials |
| `hip_rotor` | `rotor_hip` | -383,-372,-6 .. 416,418,36 | 2136 | **(0, 0, 149.5)**: origin on the hub, spin about Z. 5 blades, radius about 420 u, static droop |
| `hip_tail` | `tailrotor_hip` | -65,0,-75 .. 74,8,50 | 659 | **(-513.2, 22.2, 157.3)**: origin on the hub, spin about Y. On the left (+Y) side of the fin, radius about 75 u |

Source bones (kept in `models/mv/ext/hip/hip_skeleton.json`, positions in the body's space): `main_rotor`, `tail_rotor`, `door_l`
/ `door_r` (84, +-46, 32), `gun_l` (119, 47, 62), `gun_r` (118, -43, 62), `gun_b` (-117, 1, 57) tail gun, `left_rockets` /
`right_rockets` (16, +105 / -102, 34), `wheel_f` (128, 1, 12), `wheel_l` / `wheel_r` (-45, +84 / -82, 22). Rounded; the json is exact.
Source body groups (chosen at convert time, catalog `bodygroups`): Rotor (0 blades, 1 blurred disc, 2 off), RightMG / LeftMG /
BackMG, RightPil / LeftPil (outriggers), RightRocket1-3 / LeftRocket1-3, RightVZU / LeftVZU, Number1 / Number2 (tactical number
digits), doors. The procedural `heli_hip` is longer (871 u, HIP_K scaled): seat offsets in the script CONFIG need re-measuring.

Also converted, same layout: `huey_upper` (UH-1 gunship with M60s, rocket pods and nose turret, USMC medevac markings; 89980 tris,
heavy) with `huey_rotor` at (0, 0, 98.7) and `huey_tail` at (-281.0, 5.2, 119.5); `hind_upper` (Mi-24A, 124040 tris, desert
camouflage, not in theatre in period: optional) with `hind_rotor` at (0, 0, 180.0) and `hind_tail` at (-494.7, -24.6, 197.0).

## Converted models and what each should replace

Rip key: BC2V = Battlefield Bad Company 2 Vietnam, RS = Rising Storm, CoD4 = Call of Duty 4, MCV = Military Conflict: Vietnam,
mixed = pack of ports from several commercial games.

| Model (`models/mv/ext/<name>/<name>.vmdl`) | Replaces (DESIGN 4.1) | Bounds (units) | Real size | LOD0 tris | Origin / notes | Source id | Rip |
|---|---|---|---|---|---|---|---|
| `m101` | `howitzer_m102` (carriage) | -150,-69,0 .. 42,66,71 | 4.8 m trails spread | 5701 | M2A1 / M101 105 mm: split trails, wheels, top carriage, shield. Origin = traverse pivot on the ground. Trails to -X | 1391460275 | mixed |
| `m101_gun` | `howitzer_m102_gun` | -40,-9,-17 .. 99,9,18 | 3.5 m | 1376 | cradle + barrel, origin = trunnion; goes at **(-18.7, 0, 40.2)** on `m101`; pitch about Y | 1391460275 | mixed |
| `m2_tripod` | `m3_tripod` | -31,-23,0 .. 33,28,63 | 1.6 m high | 984 | tall AA-style tripod; pintle top at z 62.9 | 1391460275 | mixed |
| `m2_gun` | `m2_gun` | -29,-7,-5 .. 45,20,6 | 1.83 m | 4562 | M2HB with ammo box and belt, origin = pintle; goes at **(0, 0, 62.9)** on `m2_tripod` | 1391460275 | mixed |
| `dshk_tripod` | `dshk_mount` (was `dshk_wheeled`) | -27,-31,0 .. 18,31,50 | 1.25 m high | 766 | welded angle-iron stand with traverse head (improvised mount, not the wheeled Kolesnikov) | 1391460275 | mixed |
| `dshk_gun` | `dshk_gun` | -25,-4,-5 .. 48,15,15 | 1.83 m | 5991 | DShK with ammo can, origin = pintle; goes at **(-4.1, 0, 48.8)** on `dshk_tripod` | 1391460275 | mixed |
| `m60_gun` | `m60_gun` (door mount) | -45,-3,-6 .. 4,8,6 | 1.2 m | 21111 | origin at the bipod near the muzzle, not mid-gun: for a pintle offset it by about (+22, 0, 0). Heavy for its size | 1391460275 | mixed |
| `mortar_m1` | new | -17,-24,0 .. 17,13,50 | 1.25 m | 2413 | 81 mm mortar, baseplate + bipod + tube; tube leans to -Y?: check the view before placing | 1391460275 | mixed |
| `rocket_grad` | `rocket_122` | -58,-2,-2 .. 58,2,2 | 2.9 m | 48 | full-length 9M22 (ours is the 1.9 m Grad-P round); low poly, origin at the centre, nose +X | 127682564 | CoD4 |
| `bm21` | new (rocket battery dressing) | -135,-48,0 .. 160,48,120 | 7.4 m | 16872 | Ural-375 BM-21, launcher fixed forward. Out of period for 1968 (fine as a parked hulk) | 127682564 | CoD4 |
| `ural` | `truck_wreck` (T side) | -154,-49,0 .. 141,49,98 | 7.4 m | 13208 | Ural cargo truck | 127682564 | CoD4 |
| `zpu4` | new (T AA position; could stand in for `quad50_mount`) | -97,-37,0 .. 70,37,75 | 4.2 m | 6848 | ZPU-4 on its carriage, one piece (no separate gun part) | 127682564 | CoD4 |
| `m35` | `truck_wreck` (CT side) | -138,-57,0 .. 141,57,122 | 7.0 m | 14419 | M35 2.5 t, body only: **wheels are separate MDLs and were not merged (no offsets in the addon)**; use as a hulk on blocks or add wheels | 1671748726 | CoD BO / BC2V |
| `m113` | `m113_hulk` | -99,-51,0 .. 95,53,130 | 4.9 m | 26544 | intact M113 with antennas and M2; two glass materials came out flat grey | 3366544842 | likely |
| `pbr` | `pbr_wreck` | -183,-70,0 .. 196,70,159 | 9.5 m | 24200 | PBR Mk II with twin .50 tub and canopy, intact | 740797619 | BC2V |
| `pbr_mcv` | `pbr_wreck` (alternative) | -235,-86,0 .. 266,86,190 | 12.5 m | 23974 | larger, more detailed PBR; about 30 % over real length: rescale with `scale` 0.78 if used | 3677941897 | MCV |
| `lssc_boat` | new (river boat) | -210,-82,0 .. 197,82,195 | 10.2 m | 8650 | Light SEAL Support Craft | 3677941897 | MCV |
| `t54` | new (PAVN camp) | -134,-73,0 .. 250,73,137 | 9.6 m with gun | 23129 | T-54 with DShK, NVA markings | 740797619 | BC2V |
| `m151` | new (firebase) | -80,-41,0 .. 63,42,60 | 3.6 m | 8535 | M151 MUTT | 740797619 | BC2V |
| `gaz69` | new (PAVN camp) | -85,-38,0 .. 74,38,78 | 4.0 m | 10827 | GAZ-69 | 740797619 | BC2V |
| `skyraider` | new (crashed aircraft; no C-123 exists on the Workshop) | -274,-305,0 .. 198,305,213 | span 15.3 m | 66306 | A-1J, gear down, intact, SEA camouflage; heavy | 1923196118 | likely |
| `heli_wreck` | `wreck_huey` | -217,-270,0 .. 217,309,147 | 14 m scatter | 3939 | burnt light-helicopter hulk with scattered boom pieces; long axis is Y | 887209835 | unknown |
| `m114_howitzer` | new (battery dressing) | -135,-103,0 .. 120,103,171 | 6.4 m | 25756 | M114 155 mm, barrel elevated, one piece | 3677941897 | MCV |
| `m40_rr` | new (bunker / perimeter) | -53,-29,0 .. 91,29,52 | 3.6 m | 8810 | M40 106 mm recoilless rifle on its mount | 3677941897 | MCV |
| `comm_station` | `radio_prc25` at the TOC / `plot_table` radio | -42,-23,0 .. 42,22,81 | 2.1 m | 7486 | crate with radio sets and whip antenna | 740797619 | BC2V |
| `nva_ammo_case` | `ammo_crate` (T) | -16,-35,0 .. 15,36,15 | 1.8 m | 636 | long axis is Y | 740797619 | BC2V |
| `nva_ammo_case_open` | `rocket_crate` (T) | -28,-35,0 .. 15,35,40 | 1.8 m | 860 | lid open, empty | 740797619 | BC2V |
| `tent_gp` | `gp_tent` | -230,-195,0 .. 230,195,176 | 11.5 x 9.7 m with guy ropes | 1592 | closed GP tent, one window; ours has an interior, this one does not | 933819302 | unknown |
| `wood_tower` | `guard_tower` | -134,-84,0 .. 195,81,380 | 9.5 m high | 1825 | log palisade tower with thatch-plank roof; low texture resolution, reads medieval: second choice | 944539940 | unknown |
| `sandbag_fort` | new (fighting position) | -65,-52,0 .. 65,57,101 | 3.2 m | 17000 | sandbag walls on a timber frame with a sandbagged roof | 1920174934 | mod |
| `sandbag_cover` | new (curved low wall) | -70,-43,0 .. 72,42,46 | 3.5 m | 9280 | horseshoe of sandbags | 1920174934 | mod |
| `rs_elephant_grass` | `elephant_grass_a` | 4 m patch, 1.2 m high | | 3551 | short for elephant grass: scale 2-2.5 x when placing | 1978220591 | RS |
| `rs_grass_set` | `elephant_grass_b` (or ground cover) | 2.9 m patch, 0.8 m high | | 1219 | | 1978220591 | RS |
| `rs_bamboo_bundle` | `bamboo_clump` | 7.6 m wide, 8.1 m high | | 11230 | the best foliage piece | 1978220591 | RS |
| `rs_bamboo_wall` | `bamboo_fence` (as a thicket, not a fence) | 3.5 m wide, 3.1 m high | | 935 | dense bamboo screen | 1978220591 | RS |
| `rs_jungle_tree` | `rubber_tree` | 7.4 m high | | 579 | | 1978220591 | RS |
| `rs_mangrove` | `root_tangle` | 6.5 m wide, 5.4 m high | | 3302 | stilt roots, for the river bank | 1978220591 | RS |
| `rs_jungle_palm`, `rs_coconut_palm`, `rs_nypa_palm` | new | 7.9 m / 6.8 m / 2.7 m high | | 974 / 1416 / 5964 | | 1978220591 | RS |
| `rs_taro`, `rs_ferns`, `rs_jungle_bush`, `rs_hedge` | new (undergrowth) | 5.4 m row / 3.4 m patch / 2.4 m / 9.1 m bank | | 2576 / 2048 / 454 / 1421 | `rs_hedge` includes an earth bank | 1978220591 | RS |
| `w_ak47`, `w_rpg7`, `w_m14`, `w_m79`, `w_m60` | new (arms racks; later weapon work) | 0.95 / 1.27 / 1.19 / 0.71 / 1.04 m long | | 9252 / 6778 / 7369 / 5649 / 9595 | origin at the centre, muzzle +X (`--yaw long`: check each before use), world models with magazines | 740797619 | BC2V |

Exact bounds, LOD triangle counts and credits: `out/gmod_models.json`. Per-model report (materials, warnings, hit spheres):
`out/gmod/reports/<name>.json`.

### Rejected after looking

- `rs_lianas` (three hanging wires with a few leaves) and `rs_undergrowth` (leaf-litter cards that read as paper scraps).
- The Gredwitch parts piled at one origin (first attempt at the howitzer, M2, DShK): fixed by reading the lua offsets, see `parts`.
- `[LVS] - DShK 12,7MM` (3477505306): 134,616 triangles for one gun. `Functional DSHK` (942347951): one fused animated mesh.
- `Fortification Props Model Pack` (422672588): Day of Defeat: Source sandbags, lower quality than `p_sandbag`.
- `World of Tanks Asian Buildings Pack` (1432385076): Chinese / Japanese houses, bridges and torii built for tank-scale viewing
  (a temple is 762 triangles). Not Khmer, not better than `p_temple.py` / `p_village.py`.

## Not found on the Workshop (stays procedural)

- **Khmer / Angkor temple pieces, guardian statues, naga balustrades**: nothing. Searches for naga, guardian lion, Buddha, temple,
  shrine, Angkor, Khmer, Cambodia and ruins returned maps, player models and unrelated statues (Roman, Battlefield 1, Lenin).
  The nearest is "Yukon's Predator Ruins+Foliage Prop Pack" (2563105503, 1.75 GB, not downloaded: more than a third of the disk
  budget for unknown content). Statuary is better sourced as CC-BY scans (Sketchfab has photogrammetry of Khmer lions, nagas
  and devatas) through `create/glb2cs2_multi.py`, which this task did not cover.
- **Vietnamese hooches / stilt huts, sampan, steel truss bridge, C-123 / C-130 hulk, Grad-P single-rail launcher, M102, wheeled
  DShK, bamboo fence, camo net, oil drums better than ours**: nothing usable found. Keep `hooch_*`, `sampan`, `truss_span`,
  `c123_*`, `rocket_rail` / `rocket_tripod`, `drum_*`.
- **Crashed Mi-8 / UH-1 wrecks**: only the small generic `heli_wreck`. `wreck_hip` stays procedural (or burn `hip_slick` with
  `mdl2cs2 --damage-skins`).

## Every candidate looked at

Status: converted = items taken; fetched = downloaded, inspected, nothing taken (extract deleted); candidate = Workshop page only.

| Id | Title | Author | Status / what we took | Quality notes | Rip risk |
|---|---|---|---|---|---|
| 2165664559 | [LFS] Vietnam Helicopter Pack #2 | Gredwitch | converted: `hip*`, `huey*` | best Mi-8 found: 2K camouflage, interior, rotor / door / gun / pod bones and body groups | RIP (author: "I did not make the models, the sounds, or the textures") |
| 2125035846 | [LFS] Vietnam Helicopter Pack | Gredwitch | converted: `hind*`; also has AH-1G, OH-6 | very high poly (170k) | RIP, same statement |
| 1735519742 | [LFS] Mi-8T Hip | merydian | fetched | 12k triangles, lower texture quality than Gredwitch's | Project Reality mod assets |
| 1391460275 | Gredwitch's Emplacement Pack | Gredwitch | converted: `m101*`, `m2_*`, `dshk_*`, `m60_gun`, `mortar_m1` | consistent, good 1-2K textures, parts already separated at their pivots; also has ZPU-4, Nebelwerfer, M1919, mortars | RIP, mixed games |
| 127682564 | COD4 Vehicle props | Kally | converted: `bm21`, `ural`, `zpu4`, `rocket_grad` | 2007 game assets, 1K textures, clean | RIP: Call of Duty 4 |
| 740797619 | Bad Company 2 models: Vietnam pack | Moon. | converted: `pbr`, `t54`, `m151`, `gaz69`, `comm_station`, `nva_ammo_case*`, `w_*`; also has UH-1, M48, tuk-tuk, 30 weapons | good, period-correct, moderate poly | RIP: Battlefield Bad Company 2 Vietnam |
| 3677941897 | Military Conflict: Vietnam - Boat and Emplacement Props | GenericName | converted: `m114_howitzer`, `m40_rr`, `pbr_mcv`, `lssc_boat`; also M107, ZiS-3, 52-K | high detail | RIP: Military Conflict: Vietnam |
| 1671748726 | [simfphys] Vietnam Vehicles Pack | Zackrovich | converted: `m35`; also GAZ-63, BTR-40, MUTT | bodies and wheels are separate files | RIP: CoD Black Ops + BC2V |
| 3366544842 | [LVS] M113 pack | Ryuunosuke | converted: `m113`; also M163, M901, M1064 | detailed, rigged tracks | likely RIP |
| 1978220591 | Rising Storm Jungle Props | Hugh Tamlin (Piggo) | converted: 13 `rs_*` foliage models of 60 | card foliage with good alpha, right species | RIP: Rising Storm |
| 1920174934 | Firebrand - Fortifications | Hugh Tamlin (Piggo) | converted: `sandbag_fort`, `sandbag_cover`; also HESCO | high poly sandbags, 4 skins | mod assets, credited port |
| 1923196118 | Vietnam War USAF Planes | huan.bb | converted: `skyraider`; also F-4D, F-100, F-105, B-52, F-111 (flyover dressing) | detailed, correct liveries | likely RIP |
| 933819302 | Tent Army V2 | Neiremberg | converted: `tent_gp` | simple, decent canvas texture | unknown |
| 944539940 | Wooden Defense V2 / Wooden Tower | Neiremberg | converted: `wood_tower`; also palisades | low resolution | unknown |
| 887209835 | Helicopter Wreck Model | ☣Quarantine☣ | converted: `heli_wreck` | small, serviceable | unknown |
| 939768444 | Defensive Camp / Wooden Defense | Neiremberg | fetched | palisades only | unknown |
| 3477505306 | [LVS] - DShK 12,7MM | NetiPL | fetched, rejected (134k triangles) | | unknown |
| 942347951 | Functional DSHK Machine Gun | Black Tea Za rebel1324 | fetched, rejected (fused mesh) | | unknown |
| 422672588 | Fortification Props Model Pack | Sal | fetched, rejected | | Valve (DoD:S) |
| 309931181 | Blue_Skies's Vietnam War Weapons | LUKEY D FRESH | fetched: w_ak47, w_m14, w_rpk, w_svd, m79 world models (not converted; BC2V's are better) | | unknown |
| 1432385076 | World of Tanks Asian Buildings Pack | Professor Heavy | fetched, rejected | | RIP: World of Tanks |
| 3455190009 | PRL MI-8 replaces combine dropship | GhostLynx | candidate | Mi-8 from Workers & Resources | RIP |
| 2152057074 | [LFS] MI-8 | DarkLord20172002 | candidate (332 MB, several Mi-8 variants) | | likely RIP |
| 2946457417 | [LVS] MI-24 Pack | DarkLord20172002 | candidate | | likely RIP |
| 3225269297 | [LVS] UH-1H Huey | Faris9696 | candidate (slick UH-1H) | | likely RIP |
| 1891152773 / 2714325529 / 207649675 | M113 packs | Hank Hill / DarkLord20172002 / Kally | candidates | | RIP |
| 3325498766 | [LVS] C-130 pack | Ryuunosuke | candidate (nearest to a C-123) | | likely RIP |
| 2939995792 | Spawnable Left 4 Dead Plane Crash | ChimiChamo | candidate (airliner wreck pieces) | | Valve (L4D) |
| 3675338219 / 3670689680 / 3687312379 / 3688404743 | Military Conflict: Vietnam - Ground Vehicle / Air Vehicle / Weapon Props / Character Models | GenericName | candidates (831 / 546 / 479 / 1369 MB): the richest untapped source; weapons pack is the first stop for M16A1, M60, RPD, RPG-7, M72 | high | RIP: Military Conflict: Vietnam |
| 2563105503 | Yukon's Predator Ruins+Foliage Prop Pack | Hugh Tamlin (Piggo) | candidate (1.75 GB) | | RIP |
| 3509225954 | Yukon and Rusty's Call of Duty Military Props | Yukon | candidate (813 MB base props: tents, towers, radios) | | RIP: Call of Duty |
| 3001644625 / 3003120061 | [Props] Military Models Part 1 / 2 | DarkLord20172002 | candidates (319 / 690 MB) | | likely RIP |
| 2999806686 | Squad Deployables (props) | robert | candidate (sandbags, HESCO, bunkers) | modern | RIP: Squad |
| 724953514 | Verdun Props | The Devils Own | candidate (sandbags, trench props) | | RIP: Verdun |
| 2843645033 | BM-21 [Gredwich Emplacement Base] | spaceengieer | candidate (launcher in parts) | | likely RIP |
| 2471952707 | Call of Duty World At War Artillery Pack (Props) | Stefano (BackToGetCommissions) | candidate | | RIP: CoD WaW |
| 2926430936 | [ARC9] Rising Storm 2: Vietnam Weapons (WIP) | DeadSnake | candidate: M16A1, M60, AK, RPD, RPG-7, M72 | high | RIP: Rising Storm 2 |
| 2377172653 / 2798978081 / 2607952352 | [TFA] RS2 Rifles 1 / RS2 RPG-7 / M72 LAW | Commzard / NeoLin / Haer | candidates | | RIP: Rising Storm 2 (M72: unknown) |
| 205952723 / 108432322 | M60 Machine Gun PROP / Black Ops M16A1/M16A2 Pack | Kally | candidates | | RIP |
| 2618422747 / 1243825019 | HD Oil Drum Remaster / Military Cases PROPS | frugbug / Kally | candidates | | Valve-derived / likely RIP |

### Soldier player models (not converted here: `create/playermodels` owns that route)

Already converted there: `nva_soldier`, `vietcong_soldier`, `soldier2_woodland`, `us`. Further candidates:

| Id | Title | Author | Side | Rip risk |
|---|---|---|---|---|
| 2118087970 | Rising Storm 2 Vietnam GI Playermodels (666 MB) | Fritz | US | RIP: Rising Storm 2 |
| 2385459724 | Rising Storm 2 Vietcong Playermodel Pack (443 MB) | Sleeping Sootman | VC | RIP: Rising Storm 2 |
| 189078975 | COD BO NVA and Vietcong NPCs and Playermodels | Professor Heavy | NVA / VC | RIP: CoD Black Ops |
| 1915494812 | [VJ] Military SNPCs - US Vietnam Soldiers (NPCs & PMs) | Mendes | US | likely RIP |
| 146299217 | Vietnam era US Soldiers | TomeKK 2Shae | US | unknown (kitbash) |
| 129903045 | Vietnam Player Models (8.7 MB) | Blue_Skies | US / NVA | unknown |
| 1628727750 | Men of War: Vietnam Playermodels | Archer | US / NVA / VC | RIP: Men of War: Vietnam |
| 3688404743 | Military Conflict: Vietnam - Character Models & Headwear (1.4 GB) | GenericName | all | RIP: Military Conflict: Vietnam |

## Open points for whoever wires these in

- Nothing is compiled. First compile will show whether SMD material names ending in `.vmat` and the multi-hull physics behave
  (IRONFRAME uses the same mdl2cs2 output, so the single-hull case is known to compile).
- `hip_upper` / `hip_slick` are shorter and lower than the procedural Hip (741 vs 871 u; rotor hub at z 149.5 vs 174): pads, seat
  offsets and the rotor blur disc size need the new numbers.
- `m101_gun` trunnion height (40.2 u) and barrel length (99 u ahead of the trunnion) differ from `howitzer_m102_gun` (-52..152).
- `m35` has no wheels; `mortar_m1`, `heli_wreck` and the `w_*` weapons were not checked for which way they face.
- Authors shown are current Steam profile names read on 11 Nov 2026. Vmat comment lines written before the catalog had names say
  "by ?" for some packs; `out/gmod_models.json` has the right credit.
- Disk: `out/gmod` holds the kept extracts (materials of every converted addon) so a re-convert works; `prune` after the catalog
  settles, or delete `out/gmod/<id>/x` by hand to reclaim it.
