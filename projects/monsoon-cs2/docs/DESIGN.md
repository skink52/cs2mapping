# mg_monsoon - design

Second map of the series that started with mg_trenchwarfare. Same three roles (ground, artillery, air), a different war, a
different shape of battle: a Southeast Asian river valley in the monsoon season, 1968. Helicopters you fly and ride, a hill
firebase with a howitzer battery that answers fire missions called in from the field, a jungle camp with a rocket battery
hidden under the canopy, and five objectives across paddies, a river, a village and a ruined temple.

Everything is generated: terrain, water, props, models, textures, HUD, sounds, radar and the script, from this folder's
tools (see [../README.md](../README.md)). Stock CS2 jungle assets (Aztec banyans, ferns, Anubis palms, Ancient blend
ground materials) fill the vegetation and ruins; the vehicles, guns, bunkers, huts and clutter are procedural props.

## 1. What makes it different from mg_trenchwarfare

| | mg_trenchwarfare | mg_monsoon |
|---|---|---|
| Shape | two straight trench lines, flat mud, no man's land | a valley: river, paddies, hills, jungle, karst towers; 5 capture points |
| Objective | kill streaks + areas that unlock | Conquest: tickets, hold 3 of 5 flags to bleed the enemy |
| Infantry | fixed trench posts, scoped rifles | free movement, kits (rifle / MG / anti-tank), ride helicopters, call fire missions |
| Air | biplanes spawned in the air, bombs and guns | helicopters: hover, land, carry 2 door gunners + 2 riders, fast-rope, rockets on the gunships; shot down by rifles slowly, by heavy MGs and rockets quickly |
| Artillery | mortar: aim on a map, load, fire | fire missions from the field, a laying gun that actually traverses and elevates, shell types, counter-battery, repair; T side fires rocket salvoes |
| Verticality | trench floor vs parapet | helicopter-only karst tops, hill firebase, temple knoll, tunnels under the camp |
| Light | overcast, flat | humid late afternoon, low sun through haze, volumetric fog in the valley |

Series ties: same role model (chat `!infantry` / `!artillery` / `!air`, role cards, banner), same HUD language (brass-dial
instruments become green-glass military gauges), same generator toolkit, the same `!roles` / `!swap` commands.

## 2. The valley

World: x -6400..6400, y -5120..5120 play space; air box x +-7000, y +-5700, z <= 4200 (soft walls, hard +600);
sky shell at x +-7424, y +-6144, z -900..5600 (toolsskybox). 3D skybox ring of karst hills and jungle at 1/16 beyond the edge.

Teams: CT = US airmobile (firebase, south-east). T = PAVN (camp, north-west). The layout is point-symmetric about the origin
for distances; the terrain and dressing are not mirrored, so the two sides look and play differently.

```
          y+ (north)
   +-------------------------------------------------+
   | karst   T CAMP (-3900,2900)        karst    karst|
   |  tower  tunnels, rocket pits,      (1400,3900)   |
   |         heli clearing, DShK                      |
   |                                                  |
   |                 C VILLAGE (-300,2400)            |
   |  A PADDIES                        D TEMPLE       |
   |  (-2600,-900) ~~~~ B BRIDGE (0,0) ~~ (2600,900)~~|
   |  waterfall gorge (west)   river W->E   marsh (E) |
   |                 E CRASH SITE (300,-2400)         |
   |    karst                                         |
   |  (-1500,-4100)              CT FIREBASE (3900,-2900)
   |                             hill z 620, 3 guns,  |
   |                             3 pads, bunkers, wire|
   +-------------------------------------------------+
```

Heights: river water z -30 across the valley (walkable ford depth, no swimming needed), floodplain z 0..60, terraces z 60..200,
slopes to z 250 at |y| 3000, CT hill plateau z 620 (radius 800), T saddle z 300 with karst walls behind it (towers z 1100..1500),
other karst towers at (1400, 3900), (4900, 3200), (-1500, -4100), (-5300, -2200). Karst tops are flat enough to stand on
(300-400 u across), reachable only by helicopter: sniper nests with a supply crate, no cover from the air.

Zones:
- **A Paddies** (west floodplain): terraced rice paddies (water 6 u deep, 24-u dikes = cover lanes), a farm hooch cluster,
  water buffalo pen, irrigation wheel, a sunken sampan.
- **B Bridge** (centre): steel truss bridge over the river, a French-era concrete bunker at the south end (neutral mounted
  MG), a shot-up checkpoint, a ford 200 u downstream. Burnt truck on the bridge, sandbag checkpoint.
- **C Village** (north terrace): 9 hooches, a well, a small school with a bell, pig pens, haystacks, a shrine, drying racks,
  a market stall, bomb damage on the east side. Cover at head height everywhere, narrow alleys, roof access on two huts.
- **D Temple** (east knoll z 160): overgrown stone ruin (Aztec stone kits + banyan roots), a central tower you can climb,
  a courtyard with a neutral DShK, a collapsed gallery as a tunnel through the knoll.
- **E Crash site** (south terrace): a rubber plantation in rows, a downed C-123 fuselage and wing (procedural wreck) you
  can walk through, drop-zone parachute silk in the trees, cargo pallets.
- **CT firebase** (south-east hill): perimeter of triple concertina wire and sandbag walls, 4 log-and-sandbag bunkers
  (2 with M2 .50 cal), a quad-50 tower, 3 howitzer pits with 105 mm M102s, the FDC bunker (plotting table), ammo bunker,
  TOC with antennas, 3 PSP helipads with Hueys, fuel bladders and drums, GP tents, water trailer, latrine, a switchback road
  down to the valley, "FSB" sign, claymore signs on the wire.
- **T camp** (north-west jungle): thatch hooches under triple canopy, 4 rocket pits (122 mm single-rail launchers), 2 DShK
  AA pits, a camouflaged heli clearing with 3 Mi-8s under netting, tunnel complex (entrance in the camp, exits toward
  the paddies and the village; lamps, timber sets, a chamber with caches), bicycles, sampans at the bank, cooking fires,
  propaganda boards, punji stakes on the approaches.
- **Waterfall gorge** (west end): the river enters over a 110-u fall into a pool; steep rock walls; a path behind the fall.
- **Marsh** (east end): reeds, dead trees, a wrecked PBR, mist.

Roads: a dirt road (flattened band, dirt paint) firebase -> E -> B -> C -> T camp, with a spur to D. Trails link A to C
and A to E along the dikes.

Vegetation: banyans (large/medium/small + roots, vines) on slopes and around the camp; palms along the river and in the
village; tropical foliage and ferns as understorey; elephant grass fields (procedural cards, 90 u tall) on the floodplain =
infantry cover from the air; rubber trees in rows at E (procedural straight trunks + Aztec medium crowns); dead trees and
reeds in the marsh. Density is tiered by distance from the flags; everything foliage is probe-lit (`bakelighting 0`).

Light and weather: `light_environment` low in the west (pitch -22, yaw 200), warm colour 255 236 200, sky overcast-bright
(stock `sky_overcast_01` recoloured to a warm haze if possible, else the stock overcast), `env_cubemap_fog` start 300, end
9000, height fog 0..1800 (thick in the valley floor, clear on the hills), volumetric fog 0.7 with god rays through the
canopy where the sun hits. No fog particles (mg_trenchwarfare lesson): the few smoke columns are `ambient_smokestack`.

## 3. Roles

Every player spawns in the briefing room (lobby) and deploys to their team's base or to a held flag. Roles are chosen by
chat (`!infantry`, `!artillery`, `!air`) or drawn like mg_trenchwarfare (air by chance + merit; artillery seats fill from
preference first). Bots are infantry only.

### 3.1 Ground (infantry)

Kits picked at the base arms rack or at any held flag's supply crate (E on the crate, or `!rifle` / `!mg` / `!at`):

| Kit | CT (US) | T (PAVN) | Notes |
|---|---|---|---|
| Rifleman | M16A1 (`weapon_m4a1`) + M1911 (`weapon_hkp2000`, the mg_trenchwarfare Colt) | AK-47 (`weapon_ak47`, stock) + Tokarev TT-33 (`weapon_glock`) | default |
| Machine gunner | M60 (`weapon_m249`) | RPD (`weapon_negev`) | 1 in 4 of the team |
| Anti-tank | M72 LAW (`weapon_taser` as the trigger, scripted rocket) + M1911 | RPG-7 (`weapon_taser`, scripted rocket) + TT-33 | 1 in 4; the rocket is a script projectile: 2200 u/s, 180-u blast, 120 damage, 60 to a helicopter; 25 s to reload (the Zeus is re-given) |
| Marksman (held flag crates only) | M21 (`weapon_g3sg1`) | SVD / Mosin (`weapon_scar20`) | 1 per team per 8 players |

Custom weapon models come through `tools/weapons` (cs2mapping) from GLB/FBX, or from GMod workshop MDLs through the new
`mdl` input added for this map (a `WEAPONS.md` for it is not written yet). Until a model is built, the stock CS2 weapon stands in; the
loadout logic never depends on a model existing.

Infantry extras:
- **Capture**: stand within 350 u of a flag (not in a vehicle). 15 s per player, up to 3 counting. Contested = frozen.
- **Call a fire mission**: hold USE 1.2 s while looking at open ground beyond 400 u (not at a station or a prop you can
  use). A smoke-marker ring appears at the traced point and a mission with your name and the grid reference appears on
  your artillery crews' board for 45 s. One per player; 5 per team. If an enemy dies within 320 u of your mark within 15 s
  of a shell landing there, you get the assist and a merit point (merit raises your chance of an air slot).
- **Ride**: E on a friendly helicopter's open door while it sits or hovers within 90 u of the ground takes a seat
  (gunner seats first, then rider seats). E again leaves. Leaving below 450 u with the helicopter slower than 300 u/s =
  fast-rope: you are placed 60 u below the door with a capped fall speed and no fall damage for 3 s. Higher = you jump
  (fall damage applies: don't).
- **Mounted guns**: E behind an M2 / DShK / quad-50 / the bridge MG takes it (pawn hidden and parked, FOLLOW_POSITION
  camera behind the gun, mouse aims inside a 60 deg cone, ATTACK fires hitscan with tracers, overheats after 6 s of fire,
  cools in 4 s). 40 damage to infantry, 7 to a helicopter per round. E or moving away leaves.
- **Repair**: hold E 6 s on a disabled friendly gun to bring it back early.

### 3.2 Air (pilots, gunners, riders)

Per team 3 helicopters at the base pads: 2 transports (slicks) and 1 gunship. CT: UH-1H slick, UH-1C gunship (rocket
pods + nose minigun). T: Mi-8 slick, Mi-8 gunship (rocket pods). All procedural models; main and tail rotors are split
props spun by the script; skids/wheels, open doors, door guns modelled. 3 pilot slots per team.

Flight model (`CONFIG.HELI`, see the script):
- Collective: SPACE climbs, CTRL (DUCK) descends: a target vertical speed (+-380 u/s) eased in 0.4 s. Nothing pressed = hold
  altitude (the model settles to zero vertical speed in 1.5 s).
- Cyclic: the mouse sets the nose direction (yaw follows the eye yaw with a 70 deg/s rate limit = pedals), W/S push the
  body forward/back (to +-900 u/s forward, 350 back), A/D strafe (+-380 u/s). Speed eases to the target (accel 0.45/s);
  the body tilts into the acceleration (pitch up to 18 deg forward, roll up to 14 deg sideways) and levels in hover.
- Ground effect: within 120 u of the ground descending faster than 120 u/s is softened to 120 u/s; touching down with
  tilt < 8 deg at < 140 u/s = landed (skids), else crash damage = 15 + speed/12, > 60 at speed destroys it.
- Collisions: a trace along the velocity each tick (ignoring every helicopter and players) and a rotor disc check
  (4 traces around the mast at rotor radius); a hit does damage proportional to speed. Trees are solid.
- Health 100. Rifle round 1.5, MG round 4, heavy MG 7, rocket 60, artillery shell within 260 u 70. Below 35 the engine
  smokes; at 0 the helicopter spins down over 2.5 s and falls with gravity, then explodes (pilot and everyone aboard die,
  credited to the last attacker within 10 s, as mg_trenchwarfare's crash credit). Wreck prop + smoke stays 40 s. A new
  helicopter appears on the pad 45 s later.
- Camera: chase view (FOLLOW_POSITION, back 420 up 110, eases back with speed) for the pilot and riders; gunners get a
  camera at the door looking along their aim. Instruments bottom-centre: artificial horizon, airspeed, altimeter (radar
  altitude), vertical speed, heading tape, rotor/health bar, seat list, rocket count and the "RTB" low-health lamp.
- Gunship pilot: ATTACK fires rocket pairs (14 per side, 0.6 s between pairs, re-arm 40 s at the pad), ATTACK2 (UH-1C
  only) the nose minigun for 3 s bursts (6 s cooldown). Rockets are script projectiles (2600 u/s, gravity 120, blast 300,
  150 damage, 90 to a helicopter).
- Door gunners (slicks: 2, gunships: 1): mounted-gun code on a moving mount: the aim cone is the door's side (120 deg
  wide, -60..+25 deg pitch). M60 / PK door guns: 25 damage to infantry, 4 to a helicopter, overheat 8 s.
- Landing zones: any flat ground; the pad at the base re-arms and repairs (8 s on the pad = full health).
- Bounds: soft box blends the aim toward home as mg_trenchwarfare's planes; the hard wall +600 destroys.
- Pilots never take friendly or world damage inside the helicopter (`OnModifyPlayerDamage` guard, as mg_trenchwarfare);
  enemy rifle fire that hits the helicopter prop hits the helicopter (health), not the pawn.

Why helicopters work here where mg_trenchwarfare dropped them: the whole thing is a script-moved `prop_dynamic` like the
biplanes (no physics, no thrusters), the pawn is parked at `MOVETYPE_NONE` and `Move`d with the prop, and riders are
parked pawns too. Nothing new in the engine, only in the script.

### 3.3 Artillery

CT: three 105 mm howitzers (M102) in sandbag pits around the firebase FDC. T: four 122 mm single-rail rocket launchers in
jungle pits around a camp FDC hooch. Crew of up to 2 per gun (gunner + loader); one person can run a gun alone at half
the rate. 6 / 8 artillery seats per team.

The loop:
1. **Missions arrive**: fire-mission marks from the field (3.1), counter-battery flashes (an enemy gun that fires shows a
   fading flash mark on the board 3 s later, for 12 s) and the gunner's own free aim all appear on the **board** (the
   plotting table at the FDC: E to sit at it, like mg_trenchwarfare's sight: a top-down map, a reticle moved with WASD,
   Shift for fine). RELOAD cycles the active mission marks; ATTACK locks the target for your gun.
2. **Laying**: the gun turns and elevates to the solution over 0.5..3 s (proportional to the angle change); the board shows
   LAYING then LAID with the predicted 50 % circle (spread grows with range: sigma = 40 + 0.03 range).
3. **Loading**: E at the ammo rack picks up a round (the loader walks slower, 0.75), E at the breech loads it. Shell type
   at the rack cycles with ATTACK2: **HE** (radius 330, 170 damage, cover halves it), **WP smoke** (a 25 s smoke screen, 400
   u wide, blocks door gunners' and the enemy board's view of the area), **Illumination** is not possible (baked light), so
   instead **Beehive** (CT only: direct fire; when the target is within 900 u the gun fires a cone of flechettes: 60 damage
   to everything in a 25 deg cone to 900 u, hitscan) for base defence. T rockets: **HE rocket** only, but the loader can load
   1..4 rockets and the aimer fires them as a salvo 0.8 s apart; each rocket has a big spread (sigma 90 + 0.05 range).
4. **Fire**: ATTACK at the board (or JUMP at the gun) fires when LAID and loaded. Recoil animation (the barrel/cradle prop
   slides back 26 u and returns), muzzle blast, dust ring, the shot heard across the map (3D event, range 14000), whistle
   2 s before impact, impact effects, the mark on the board and on the FO's HUD ("SPLASH").
5. **Credit**: the gunner gets the kill, the loader the assist (the mg_trenchwarfare share rule), the FO the assist when the
   mission was theirs. Crews see their rounds fired / hits / missions on the HUD.
6. **Counter-battery**: a shell or rocket within 260 u of an enemy gun disables it for 40 s (smoke, crew thrown out of the
   seats, board shows DISABLED); any teammate holding E on it for 6 s repairs it early. Helicopter rockets do the same.
   The guns are therefore targets for everyone: pilots hunt the enemy battery, the battery hunts the helicopters' pads
   and the enemy guns.

Why this is more engaging than the mortar: the targets come from teammates (a reason to talk), the gun visibly moves,
there is a choice of shell, a salvo mechanic on one side and a direct-fire mode on the other, and the enemy shoots back
at you.

### 3.4 Conquest rules

- 5 flags, 400 tickets each. A team holding 3+ flags bleeds the other 1 ticket per 3 s per flag over 2 (3 flags = 1/3 s,
  4 = 2/3 s, 5 = 1/s). A death costs 1 ticket. 0 tickets or the 20 min clock = round over (`FireWinCondition`).
- Flags start neutral except none; capture 15 s / player (max 3). Owned flags are spawn points (the base always is).
- Spawn choice at deploy: base (default), any held flag (`!spawn a..e` or the HUD prompt cycled with RELOAD during the
  deploy countdown), or aboard a friendly slick waiting at the pad with a free seat.
- The HUD objective bar (top centre, under CS2's round timer) shows A..E ownership, capture progress and both tickets.
- Round start: 10 s freeze in the lobby with the briefing card; helicopters and guns reset.

## 4. Assets

### 4.1 Procedural props (tools/p_*.py), all original, baked PBR + stock Valve textures where they fit

- `p_heli.py`: `heli_huey` (UH-1H slick, open doors, M60 door mounts), `heli_huey_gun` (UH-1C, pods + minigun), `heli_hip`
  (Mi-8 slick), `heli_hip_gun` (+ pods); `rotor_huey`, `rotor_hip`, `tailrotor_*` as separate props (origin on the hub);
  `wreck_huey`, `wreck_hip` burnt hulks. ~9-14k tris LOD0, decimated LODs.
- `p_arty.py`: `howitzer_m102` carriage (static) + `howitzer_m102_gun` (cradle + barrel, traverse/elevate/recoil by script),
  `rocket_rail` (DKB single-rail launcher: tripod + rail; the rail prop elevates), `rocket_122` (the round, flies as a prop),
  `shell_105` (carried round), ammo racks, `plot_table` (FDC board with map, protractor, radio, lamp), `fdc_bunker`.
- `p_guns.py`: `m2_tripod`, `dshk_wheeled`, `quad50_mount`, `m60_doormount` (the gun part pivots: `*_gun` props), `pk_doormount`.
- `p_base.py`: bunkers (log/sandbag, 2 sizes, roof PSP), `psp_pad` (pierced steel planking helipad with H), `fuel_bladder`,
  `drum_55` (+ stacks), `gp_tent`, `toc_antenna`, `water_trailer`, `latrine`, `conex`, `guard_tower`, `claymore_sign`,
  `fsb_sign`, `ammo_can`, `c_ration_box`, `cot`, `radio_prc25`, `jerry_can`, `rucksack`, `m16_rack` (arms rack = kit station).
- `p_village.py`: `hooch_a/b/c` (bamboo + thatch, 2 with a loft), `school`, `shrine`, `well`, `bamboo_fence_*`, `rice_basket`,
  `water_jar`, `drying_rack`, `haystack`, `pig_pen`, `ox_cart`, `sampan`, `fish_trap`, `market_stall`, `propaganda_board`,
  `punji_stakes`, `cook_fire` (logs + pot; fire particle on top), `bicycle` is stock.
- `p_jungle.py`: `elephant_grass_a/b/c` (card clusters, alpha), `rice_clump_*`, `reeds`, `bamboo_clump`, `rubber_tree`,
  `log_fallen`, `dead_tree`, `vine_curtain`, `camo_net_*` (alpha lattice), `root_tangle`.
- `p_wreck.py`: `c123_fuselage`, `c123_wing`, `pbr_wreck`, `truck_wreck`, `m113_hulk`, `cargo_pallet`, `parachute_silk`.
- `p_bridge.py`: `truss_span` (x2), `bridge_pier`, `checkpoint`, `french_bunker`.
- `p_temple.py`: `khmer_gate`, `khmer_tower` (climbable), `lintel`, `naga_balustrade`, `guardian_statue`, `fallen_blocks`.
- `p_karst.py` is not a prop: karst towers are world meshes (section 5).
- From mg_trenchwarfare / create: `p_sandbag` (walls, low walls), `p_wire` (concertina, posts), crates, signs via `geo.decal`.
- `fx_models.py`: tracer, rocket (finned), marker ring (fire mission), gun pip, smoke marker (WP), rotor blur disc (alpha).

### 4.2 Stock CS2 assets used

Foliage: `models/props/de_aztec/hr_aztec/aztec_foliage/*` (banyan large/medium/small + roots + vines, tropical foliage
large/medium/small, fern a/b/c, yucca), `models/de_anubis/foliage/palm_tree_*`, `models/foliage/weeds/*`, `models/foliage/
ground/ground_leaves_*`, `models/cs_italy/foliage/taro|hosta|fern`. Ruins: `models/props/de_aztec/hr_aztec/aztec_walls/*`
(stone walls, rubble, rocks), Anubis pillars/statue. Vehicles: `models/vehicles/bicycle_01/*`. Terrain: `materials/de_ancient/
hr_ancient_blend_*` (mud/grass/dirt/rock/moss blends with vertex paint), `materials/de_nuke/hr_nuke/hr_river_water_001` or
`hr_aztec_water_shallow` for the river and paddies, `models/de_anubis/unique/water_wall02` + `water_falling02` for the fall.
Particles: `copter_land_loop_1_dust_low`, `copter_takeoff_1_dust_low`, `explosion_basic`, `impact_dirt`, `env_fire_small`,
`barrel_burning_engine_smoke_dark`, `ambient_smokestack`. Sounds: stock weapon sounds for the M60/minigun bursts as
mg_trenchwarfare did, everything else synthesised (rotor slap, turbine, howitzer, rockets, whistles, jungle ambience).

### 4.3 Player models

GMod ports already converted in `create/playermodels` (local/server use; author permission needed before the Workshop):
T `nva_soldier`, `vietcong_soldier`; CT `soldier2_woodland`, `us`. Applied as mg_trenchwarfare's uniforms (`CONFIG.UNIFORMS`,
`!uniform` opt-out, cache props). If first-person issues appear, `UNIFORMS_ON false` falls back to stock agents.

## 5. Terrain and world construction (tools/make_map.py)

- `layout.py`: every coordinate above, `height(x, y)` (valley profile + river carve + terraces + hill + karst bases +
  roads + craters), `river_y(x)`, the paddies grid, zone outlines, POIs (flags, pits, pads, stations, spawns), the
  `karst` list. Shared with the radar, the FDC board render and the script config (exported to `out/layout.json`).
- Terrain: `vmapgen.Terrain`, 512 tiles, cells 32 within 900 u of a flag/base, 64 in the valley, 128 on the outer slopes.
  Paint: blend weight by slope/wetness (mud near water, grass on terraces, dirt on roads, rock on steep ground), tint
  darker under canopy. Holes under karst footprints and the tunnel portal.
- Karst towers: separate open meshes (polar grid, radial fBm, overhangs, flat tops), rock/moss blend with vertex paint.
- Water: river sheet (one open sheet following `river_y`, never overlapping the paddies), paddy sheets per cell, the fall
  pool. All at most 6 u over their floors. `func_water` is not used (no swimming: the river is a ford).
- Clips: `toolsplayerclip` slabs on the firebase wire, karst side walls (keep players from scaling), map edge walls;
  `toolsinvisibleladder` for the temple tower and the guard tower ladders.
- Tunnels: as mg_trenchwarfare's saps (closed 16-u grid meshes), 3 portals, lamps unshadowed.
- Lightmap volumes over the walkable band; probe volumes: valley 64, bases 48, tunnels/bunkers 32, far slopes 108.
- Vis: Lowest over all, Lower over the valley floor, Low in the tunnels, bunkers and the temple gallery.
- Lobby room below the map with the banner, 32+32 spawns, nav seed.
- Entities for the script: `mv_heli_<t|ct>_1..3`, `mv_rotor_*`, `mv_tail_*`, `mv_gun_<t|ct>_1..4` (+ `_tube`), stations
  (`mv_rack_*`, `mv_board_*`, `mv_breech_*`), `mv_mount_N` (+ `_gun`), `mv_flag_a..e`, `mv_cap_*` spawn points, pools of
  particles / sounds / shakes / tracers / rockets / markers, cache props, HUD, soundscape.
- Edit preservation and delta patches exactly as mg_trenchwarfare (vis groups `mv_gen`, `mv_user`), per-section seeded rng
  from the start so user obstacles never cascade.

## 6. Script (src/*.js -> maps/scripts/mg_monsoon.js)

Modules joined by `create/build/build.mjs`: `00_config`, `10_util` (vectors, angles, hud cache, pools), `20_players`
(roles, spawn flow, kits, uniforms), `30_heli` (flight, seats, door guns, rockets, damage, wrecks), `40_arty` (board,
missions, laying, loading, shells, counter-battery, repair), `50_mounted` (emplaced guns), `60_conquest` (flags, tickets,
spawns, round end), `70_hud` (role cards, instruments, board, objective bar), `80_ambient` (smoke columns, distant fire,
birds), `90_main` (think, events, chat, damage guard, bots). Mock: `test/mock.mjs` (from mg_trenchwarfare's, with seats,
flags and guns), `tsc` types. Performance budget: < 2 ms per tick at 32 players on the mock.

## 7. Verification plan (before CS2)

1. `check_mesh.py` on the vmap; `Placer.audit()` overlaps; a top-down render with zones, roads and props; first-person
   software views of each zone (`smd_view.py`).
2. Turntables for every prop; stock-material previews; LOD deviation report.
3. `hud_check.py` on the HUD in every state; `mock.mjs 32 600` clean with pilots, gunners, riders, crews and FOs driven;
   `tsc` clean; script time on the mock.
4. Entity contract check: every name the script looks for exists in `entities.json` (a test).
5. Review passes: world (holes, floating props, clip gaps, unreachable spots), gameplay (distances, sightlines, times),
   docs. Each pass recorded in NOTES.md.
6. In CS2 (when the PC is free): compile under the watchdog, then the TESTING checklist.
