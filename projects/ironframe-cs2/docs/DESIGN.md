# IRONFRAME: design

A 64-player third-person mech combat game for CS2 in the Armored Core mould: fast boosting mechs, four hard-points, lock-on,
stagger, modular garages and a pilot career that is saved on the Slime Servers minigame server. Several arena maps share one
script; the server plugin (SlimeMG `IronFrame` module) keeps every pilot's rank, credits, parts and loadouts.

Status words used in this folder: **designed** (this page), **written** (code exists), **verified offline** (sims, mock engine,
type check), **tested in game** (on a CS2 server). Everything in this document is *designed* unless `docs/STATUS.md` says more.

## 1. Pillars

1. **Feel first.** A mech must feel heavy and fast at once: instant quick-boost dodges, momentum, hover, a hard landing. The
   flight model is grown from Dogfight's jets (which players called "very pleasant") and mg_trenchwarfare's biplanes.
2. **64 players, up to 22 per arena.** Each map holds 3 identical arena copies (`ifr_arena_2..3`); humans are dealt over the copies
   at 22 per copy (`IFR_SPLIT_AT`, skink52 10 Nov 2026: 32 per arena was too many; AI fill stops at 22 humans). Huge terrain arenas with vertical play; everything scripted scales linearly and is budgeted per
   tick like Dogfight (which runs 64 jets): about 4 engine calls per mech per tick plus pooled effects.
3. **Builds, not power.** Progression unlocks breadth (parts, frames, paint) and small tuned upgrades. Hard caps keep a maxed
   pilot within about +5 % of a fresh one (AP +5 %, DPS +3 %, docs/BALANCE.md); a weight/energy budget everybody shares makes strong parts cost mobility.
4. **Never an empty server.** Below a population floor the script fills both teams with its own AI mechs and switches to co-op
   sorties against AI squads and bosses. AI is first-class: it uses the same frames, weapons and movement as players.
5. **AAA presentation.** Real mech models (Armored Core 4/For Answer, Titanfall, Gundam, Mass Effect ports from the GMod
   Workshop, decimated with LODs), baked lighting with volumetric fog, particle boosters and tracers, a clean Panorama HUD
   (AP, EN, stagger, lock reticle, radar), synthesised SFX, dramatic skies. Every visual is previewed offline before CS2.
6. **Bug-free by construction.** Core rules run in Node (sims, soak tests, balance tables); the real script runs on the mock
   engine with 64 players before it touches CS2; the plugin has a harness test. Anything not tested in game says so.

## 2. The player's loop

1. Join; a short intro slate (`IRONFRAME`, arena name, mode) while the pawn is parked.
2. **Garage** (first join, between lives at will, `!garage`): pick a loadout slot (3), change frame, four weapons, generator,
   booster, FCS, paint. The garage shows weight and EN budgets (red = can't sortie). Buy parts and upgrades with credits.
   On the server everything is persisted by the plugin; stand-alone (no plugin) every part is unlocked and nothing is saved.
3. **Sortie:** the mech drops from 1500 u above its team's drop zone with thrusters firing, 3 s of spawn protection.
4. Fight: WASD, Shift boost, Ctrl quick-boost (in the WASD direction), Space jump / hover, Mouse1 / Mouse2 arm weapons,
   R / E shoulder weapons, F target cycle (nearest in the FCS cone, then next). Lock-on and stagger decide fights.
5. Die: death camera orbits the wreck 3 s; respawn timer 6 s; garage open meanwhile (change loadout for the next life).
6. Round end (time or score): podium, XP and credit tally per player ("+1 240 XP, +860 credits"), next-mode vote.
7. Between maps the career continues: `!garage`, `!rank`, `!top mech` on the server.

## 3. Mechs

A **loadout** = frame + right arm + left arm + right shoulder + left shoulder + generator + booster + FCS + paint.
Part data is the single source of truth in [`data/parts.json`](../data/parts.json) (stable integer ids; read by the core,
the HUD generator, the garage and the server plugin). `tools/parts_check.py` validates it and prints the balance tables.

### Frames
A frame is the visible chassis (legs + core + arms + head as two props: legs and upper body) and sets AP, weight class,
load limit, base speeds, hit spheres and the leg type. Three weight classes and three leg types:

| Class | AP | Walk | Boost | Quick boost | Load limit | Stagger cap | Role |
|---|---|---|---|---|---|---|---|
| Light | 7 000 | 520 u/s | 1 500 | 2 800 burst | 3 200 | 1 000 | flanker, missile boat, hit and run |
| Medium | 9 000 | 440 | 1 300 | 2 500 | 4 600 | 1 400 | all-rounder |
| Heavy | 12 000 | 360 | 1 100 | 2 200 | 6 400 | 1 900 | line breaker, cannons, shields |

| Leg type | Trait |
|---|---|
| Biped | balanced; can fire cannons while moving at 60 % accuracy |
| Reverse-joint | +40 % jump thrust, hover drain −25 %, landing lag ×0.5 |
| Quad | cannons fire on the move at full accuracy; can't quick-boost in the air; +15 % stagger cap |

Frame roster (v1, model source in brackets; ids in parts.json):
Light: **Krasnaya** (AC4A Hari, 03-AALIYAH chassis), **Stryder** (Titanfall), **Lisa** (AC4A Old King).
Medium: **White Glint** (AC4A), **Atlas** (Titanfall), **Supplice** (AC4 Berlioz), **RX-78** (Gundam).
Heavy: **Ogre** (Titanfall), **Noblesse Oblige** (AC4A), **Legion** (Titanfall 2), **Barbatos** (Gundam, medium-heavy).
Quad: **Mule** (F.E.A.R. 3 Mech Mule). PvE only: **Normal** (AC4 enemy ACs), **MOA** (AC3 MT, reverse-joint), **Loki** (drone
infantry mech), **002-B** (elite), **00-ARETHA** (boss).
All frames are scaled to a class height: light 240 u, medium 288 u, heavy 336 u, boss 700 u (CS2 units; a human is 72 u).

### Internals
- **Generator:** EN capacity, EN regen per second, regen stall after an empty tank. Four: Standard, High-output, Capacitor, Ignition.
- **Booster:** boost thrust, quick-boost impulse and EN cost, hover thrust, boost EN drain. Four: Standard, Agile, Heavy, Assault.
- **FCS:** lock cone half-angle, lock range, soft-lock time, hard-lock (missile) time, gun assist gimbal. Four: Standard,
  Long-range, Close-combat, Missile.

### Budgets
- `weight(parts) <= frame.load` else the loadout can't sortie.
- `enLoad(weapons, booster, fcs) <= generator.output` else EN regen is scaled by `output / enLoad` (over-drawn, shown amber).
Every part has weight and EN load; strong parts are heavy or hungry.

## 4. Movement (core `20_mech.js`)

Simulated by the script at 64 Hz in world units. Gravity 800 u/s², terminal fall 1 800 u/s. Each mech is a capsule
(radius 70/90/110 by class, height = class height) tested with one ground `TraceLine` and one `TraceSphere` sweep per tick
only while moving (Dogfight's budget: 1.3 traces per mech per tick at 64).

- **Walk:** WASD relative to the camera yaw; acceleration 2 400 u/s², friction 6/s; legs turn toward the move direction at
  360°/s; the upper body always faces the camera yaw (torso twist is unlimited, pitch ±20° for the gun line).
- **Boost (Shift):** ground skate / air glide at the class boost speed. Skating on the ground costs no EN (regen runs at half
  rate meanwhile, AC4/AC6); gliding in the air drains 180 EN/s (booster-scaled). Boost does not need a key tap: AC4-style
  continuous gliding with boost particles. Hold W+Shift in the air for assault boost (×1.25 speed, drain ×2, flies nearly level).
- **Quick boost (Ctrl):** a 0.18 s jet at the class QB speed in the held direction (or backwards with none), then 0.25 s of 50 %
  steering; cost 600 EN; reload 0.38 / 0.45 / 0.55 s by class, up to ×1.6 for a loadout above 70 % of the load limit (which also
  costs up to 10 % boost speed). One two-step chain QB inside the reload (60° off the first line, ×1.25 EN). The main dodge.
  Not in the air for quads. QB in the last 0.25 s of a stagger breaks out of it. Numbers and sources: docs/AC_FEEL.md.
- **Jump / hover (Space):** vertical thrust 900 u/s² (reverse-joint ×1.4) while held and EN lasts, drain 500 EN/s.
- **EN:** capacity by generator; regen pauses 0.9 s after any spend; an empty tank stalls regen for 2.5 s (the classic
  "redline": the HUD bar turns red), then 20 % of the tank comes back at once. Recovery is faster on the ground.
- **Landing:** falling above 1 200 u/s causes landing lag: 0.35 s (light) to 0.6 s (heavy) of no boost and 50 % speed.
- **Collision:** mechs are not solid to each other (64 players; shoving is a griefing vector) but a soft separation pushes
  overlapping mechs apart at 200 u/s. World collision: sweep stops at the hit, slides along the normal.
- **Arena box:** soft push back inside from 400 u before the wall, hard clamp at the wall; ceiling the same. Leaving the map
  is impossible.

Numbers live in `CONFIG.move` and the frame/booster/generator rows; `test/sim.cjs` prints time-to-cross, QB chains and EN
cycles per class so changes are checked against the targets above.

## 5. Combat

### Hard-points and weapon families
Arm weapons (Mouse1 right, Mouse2 left; both arms may carry the same family):

| Family | Type | Damage | Rate | Range (eff.) | Impact | Note |
|---|---|---|---|---|---|---|
| Rifle | projectile 9 000 u/s | 155 | 7/s | 4 500 | low | 30-round mag, 2 s reload; gun assist; full damage to 2 250 u, 55 % at 4 500 |
| Gatling | projectile | 80 | 25/s | 3 000 | low | heat: 4 s continuous, 3 s cool-down |
| Shotgun | 12 pellets | 12 × 112 | 1.1/s | 1 500 | high | spread 8°, stagger tool; fall-off past 750 u to 50 % |
| Laser rifle | hitscan beam | 650 (charge ×2.4) | 0.8/s | 6 000 | medium | EN cost 270 per shot, charge 1.2 s; 70 % at max range |
| Bazooka | projectile 3 500 u/s | 2 000 | 0.5/s | 3 500 | very high | splash 250 u, 4 rounds, 3.5 s reload |
| Grenade launcher | lobbed 2 200 u/s | 1 200 | 1/s | 3 000 | high | splash 400 u, bounces once |
| Pulse blade | melee lunge 600 u in 0.2 s | 2 600 | 1 s cd | 600 | very high | EN 240, hit radius 240; with a lock the lunge homes on a target anywhere under 900 u |
| Plasma rifle | slow orb 2 800 u/s | 780 | 1.6/s | 2 500 | medium | splash 200, EN 60 |
| Rail gun | hitscan | 950 | 0.6/s | 9 000 | high | 0.5 s wind-up; tracer line |
| Hand missiles | 4 homing | 4 × 350 | 2 s cd | 5 000 | medium | needs soft lock |
| Shield (left only) | hold | blocks 60 % frontal | — | — | — | drains 150 EN/s while raised |
| Pile bunker 113 (r14) | melee lunge 260 u (homing to 900 u locked) | 5 200 | 3 s cd | 360 | instant stagger | EN 350, hit radius 220; `stagger_force` fills the meter on a hit |
| Sniper cannon 114 (r21) | hitscan | 1 800 | 0.4/s | 12 000 | very high | 1 s charge; cannot fire while boosting (boost spoils the shot, round refunded) |
| Burst rifle 115 (r3) | projectile 10 000 u/s | 3 × 135 | 2.2 bursts/s | 4 800 | low | 3 rounds 0.07 s apart, spread 0.15° |
| Flamethrower 116 (r8) | hitscan cone 24° | 140 + burn | 9/s | 1 400 | very low | burn: 400 AP/s for 4 s (`burnT`, refreshed by each hit), 720 fuel |
| Energy shotgun 117 (r16) | 10 pellets | 10 × 100 | 1.5/s | 1 500 | high | no ammo, EN 90 per shot, spread 8° |
| Laser blade, heavy 118 (r28) | melee lunge 650 u in 0.38 s | 3 600 | 0.45/s | 800 | very high | EN 520, hit sphere 300 u (Moonlight 180) |

Shoulder weapons (R right, E left):

| Family | Type | Damage | Rate | Note |
|---|---|---|---|---|
| Vertical missiles VM-6 | 6 homing, lofted, 4 300 u/s, turn 120°/s | 6 × 470 | 5 s cd | hard lock; proportional navigation (Dogfight `mslGuide`) |
| Dual missiles | 2 fast homing | 2 × 900 | 3.5 s cd | hard lock |
| Laser cannon | hitscan | 3 000 | 1.2 s charge, 4 s cd | brace 0.4 s unless quad |
| Grenade cannon | artillery arc | 3 500 splash 500 | 6 s cd | the HUD shows the predicted landing ring |
| Autocannon | projectile | 300 | 4/s | 20-round drum; a shoulder cannon: bipeds and reverse joints brace 0.2 s per shot (quads fire on the move) |
| Flak | air-burst | 900 splash 350 | 2 s cd | detonates near airborne targets; a shoulder cannon: braced 0.3 s unless quad |
| Pulse shield | ability | 4 000-HP bubble, 6 s | 20 s cd | protects allies inside too |
| Repair kit | ability | heals 2 400 AP over 6 s, self or aimed ally | 3 charges, 15 s cd | |
| Decoy launcher | ability | breaks every missile lock, 2.5 s immunity | 2 charges, 15 s cd | Dogfight flares logic |
| Mine layer 211 (r10) | ability | drops a proximity mine: 1 400, splash 350, trigger 250 u | 3 s cd, 4 live max, 40 s life | armed after 1 s; effects `mine` |
| Orbit drones 212 (r17) | ability | 2 drones for 10 s, 45 per shot at the soft-locked target | 22 s cd | 1.5 shots/s each, one LOS trace per shot; effects `drone` |
| Multi-lock missiles 213 (r22) | 8 homing, lofted | 8 × 380 | 6 s cd | hold to lock up to 4 targets in the FCS cone (each takes the hard-lock time), release fires, salvo split across them |
| Cluster artillery 214 (r26) | artillery arc | 6 bomblets × 650, splash 260 | 5 s cd | the shell opens at its apex, bomblets spread about 250 u/s |

### Damage model
- AP (hull) per frame; upgrades add at most +15 %. No hit locations; every sphere of a mech is the mech (AC convention).
- **Impact / stagger:** every hit adds its impact to the stagger meter (cap by class). The meter decays 450/s after 2 s
  without hits. At cap the mech is **staggered** for 2 s: speed 40 %, no boost or quick boost, damage taken × the weapon's
  direct-hit multiplier `dha` (1.2-2.0, default 1.5; AC6 direct hit), meter resets afterwards. Shotguns, bazookas and blades are stagger tools; rifles and gatlings finish.
- Splash: linear fall-off from full at 40 % radius to 25 % at the edge; self-damage 50 %.
- Spawn protection 3 s (ends early on firing). Friendly fire off.
- **Kill credit:** every hit calls `pawn.TakeDamage` with the damage scaled to the pawn's 100 health
  (`IGNORE_ARMOR | SUPPRESS_EFFECTS | SUPPRESS_PHYSICS_FORCE`, attacker = shooter's pawn, inflictor = their upper-body prop),
  so the pawn's health tracks AP %, CS2 counts assists and the killfeed and rank plugins see real kills; the fatal hit adds
  `FORCE_DEATH`. `OnModifyPlayerDamage` lets only our damage through (fall damage, grenades and anything else are aborted).
  Kills are queued and processed at the start of the next tick (Dogfight).
- Mech wrecks: the props fall with the leg prop tilting, explosion particles, then park after 3 s.

### Lock-on (FCS)
- The FCS cone sits on the crosshair. The nearest enemy inside the cone with line of sight becomes the **soft lock** after
  the FCS soft time (0.3 s standard); F cycles to the next candidate. Soft lock gives the HUD box, the range read-out and
  **gun assist**: projectile and hitscan rounds are steered toward the target's nearest hit sphere within the FCS gimbal
  (6° standard), like Dogfight's 8° convergence. Lock is kept while the target stays within 1.25 × the cone and LOS holds
  (0.5 s grace).
- **Hard lock** (missiles): soft lock held for the FCS hard time (0.9 s standard, three beeps); the target hears a lock warning
  and sees the threat arrow; missiles can't fire without it (hand missiles need only soft lock).
- Decoys break every lock on the user for 2.5 s; quick-boosting perpendicular to a missile within 0.5 s of impact makes it
  miss (missile turn limits set the dodge window).

### Projectiles and hitscan
- Bullets are a typed-array pool (Dogfight `BULLETS`), swept against enemy hit spheres each tick with a broad phase against the
  mech centre; shooters' rounds are tested against the victim's pose now and 6 ticks ago (lag mercy). World hits come from
  one `TraceLine` per shot at fire time (the distance the round may travel), so a bullet costs no trace per tick.
- Hitscan weapons: one `TraceLine` plus the sphere test along the ray, instant.
- Missiles are pooled props (128), proportional navigation with turn and acceleration caps, proximity fuse (swept segment
  against the target's spheres), lofted launch for vertical packs.
- Melee: a lunge that moves the mech 600 u toward the target over 0.25 s then tests a 180 u sphere.
- Tracers are scaled emissive fx props (rifle, rail), particles for muzzle flashes and impacts.

## 6. Modes and population

The script picks the mode per round from the human count (bots don't count), configurable in `CONFIG.modes`:

| Humans | Mode | AI |
|---|---|---|
| 1–5 | **Sortie** (co-op): humans + AI allies vs waves of AI squads; a boss every third wave; survive and hold the beacon | fills allies to 8, enemies 8–16 by wave |
| 6–23 | **Team Battle** or **Conquest** (voted) | fills both teams to 16 total, dropped one by one as humans join |
| 24–64 | **Team Battle**, **Conquest** | none by default (`CONFIG.ai.floor`) |
| any, ≤ 16 and voted | **Skirmish** (free for all) | fills to 8 |

- **Team Battle:** first to the kill target (humans × 6, min 40, max 150) or most kills at time-out. 10-minute rounds.
- **Conquest:** three capture points (A/B/C, radius 700 u, capture 8 s, faster with more mechs); the team holding more points bleeds
  the other's 300 tickets by (difference) per second (majority rule since 10 Nov 2026: every held point used to bleed, so 16-bot rounds
  ended in 2.5 min); kills cost 2 tickets. The classic large-scale mode.
- **King of the Hill** (kh): one point at a time, moving every 120 s (warned 15 s before); the owner scores 1/s only while one of its
  mechs stands on it and it is not contested; first to 150. **Capture the Flag** (ctf): flags on the map's stands (`ifr_flag_t/ct`),
  3 captures, the carrier's own flag must be home.
- **Objectives in the world** (10 Nov 2026 playtest: modes and zones were hard to read): map dressing per zone (lit ring inlay, dais,
  letter mast) and per flag stand (`tools/arenas/objectives.py`); live script markers (`src/cs2/45_features.js` objTick: owner-colour
  ring, progress arc, a column whose height is the progress, the turning letter; flags with a column over the carrier): at most 4 pooled
  props per zone and 3 per flag (about 20 per arena copy, change-only Moves); on the server the plugin's beams take over rings and
  columns (SERVER_CONTRACT.md section 7).
- **Sortie:** waves with escalating AI tiers; the beacon (one point) must stay held; AI bosses (ARETHA) have phases and
  weak-point spheres (×3 damage). Rewards XP and `mech_pve_kills` / `mech_boss_kills`.
- **Skirmish:** 8–16 players, first to 25 kills.
- **Rounds:** the script runs them (`mp_ignore_round_win_conditions 1`), ends with `FireWinCondition` after the podium,
  CS2 clock 15 s longer than ours; 20 s fallback restart. Next-mode ballot with the keys that don't move you (Hellmatch rule).
- **Spawning:** team drop zones at opposite arena ends plus forward drops at held Conquest points; a drop point is rejected
  if an enemy is within 2 500 u; the mech falls in from 1 500 u with thrusters.
- **Team balance by rating:** at round start the plugin (or the script stand-alone) re-sorts teams by IronFrame rating so the
  two sides are within 5 %; bots balance the remainder.

### AI (core `50_ai.js`)
The same `input` struct humans fill (Dogfight pattern). Reused from Dogfight: target choice by cost (distance + turn), lead
with turn prediction, burst discipline, evade on lock by time-to-impact, boost reserve policy, anti-circling, quota fill.
New for ground mechs: a **nav grid** per arena baked by the map generator (256-u cells, walkable flag, height, cover value)
with flow-field pathing to objectives; cover-seeking when staggered or under 40 % AP; quick-boost dodge on incoming bazooka
or missile threats; weapon choice by range band; squad behaviour (2–4 mechs share a target and a point). Three difficulty
tiers; the fill tier follows the lobby's average rating. Bots carry real loadouts from a per-tier list, so PvE enemies
show the full visual variety.
**Aim model** (Nov 2026 playtest: "AI seem to have very good aim"; the FCS gimbal used to erase every bot error, so bots hit 99 %):
a reaction delay on a target switch and when a target comes back into sight (no turn, no fire for `react` s); a lagging turn (`gain`);
the target's velocity is a low-passed estimate (`velLag`), so a quick boost or a reversal throws the lead off; a fresh target QB adds
`qbErr` deg fading over `qbBlind` s; a smooth wandering error (an Ornstein-Uhlenbeck walk) of E deg, E = `aimErr` x (1 + `rangeErr` per
1 500 u past 1 500) x (1 + `settle`, fading over `settleT` s of tracking) + `moveErr` x the target's lateral angular speed, all scaled by the
target's width (radius / 90: a pilot aims finer at a small frame). A bot's FCS assist steers toward this perceived point, not the true
lead. Measured (two rifles on a 1e9-AP medium, hits / shots): hard 93 % standing at 2 000 u, 85 % strafing at 1 500, 64 % strafing at
3 500, 28 % in the 0.6 s after a target QB; normal 73 / 69 / 38 / 23 %; easy 34 / 43 / 19 / 14 % (all were 89-100 % / 69-92 % before).
Tier numbers: `cfg.ai.tiers` in `src/core/00_defs.js`; tests in `test/mechanics.cjs` ("AI aim").

## 7. Progression (shared `70_progress.js` + plugin)

- **XP → rank 1–50.** XP per round: 100 participation + 40 per kill + 15 per assist + 60 per capture + 300 win bonus +
  survival time × 1/s, × 2 for the first round of the day (plugin). Rank N needs `600 + 180·N^1.5` XP.
- **Credits:** 50 % of XP as credits, plus bounties. Parts cost 1 500–12 000, upgrades `base × level`.
- **Unlocks:** a part needs rank R and credits; the starter garage has one frame per class (Krasnaya, White Glint, Ogre),
  rifle, shotgun, VM-6, Standard internals. Every two ranks unlock something; all frames by rank 30.
- **Upgrades:** every part has one track of 5 levels (frame AP +1 %/lvl, generator capacity +1 %, weapon damage +0.6 %,
  booster EN efficiency +0.6 %, FCS lock time -1 %, shield block / repair / bubble +1 %). Caps in `data/parts.json#caps`, enforced by the core and the plugin.
- **Anti-stomp:**
  - A fully upgraded loadout is at most +5 % AP and +3 % DPS over stock (`parts_check.py` asserts it; was +15 / +10 % until the 10 Nov 2026
    AC feel pass, when longer duels let a maxed bot win 84-89 % of mirror duels; now about 67-70 % against a 56 % no-upgrade noise floor).
  - *Rookie shield:* rank < 5 takes −20 % from rank ≥ 15; rank < 10 takes −10 % (shown as a HUD badge).
  - *Bounty:* a 5-kill streak marks the player on every radar and doubles the XP for killing them; 8+ triples it.
  - *Catch-up XP:* ×1.5 XP below the lobby's median rank.
  - Rating-balanced teams (above) and AI fill at low population.
- **Cosmetics** are the aspirational tail: paints (tints), camo skins, emblems on the HUD name plate, titles at rank 10/20/30/50.
- **Stand-alone** (no plugin): all parts unlocked at level 0, nothing saved, no ranks (every HUD element still works).

## 8. Arenas

Three maps (each holding 3 arena copies of at most 22 players), each its own Workshop addon built from one source tree (`IF_ARENA=dunes|sprawl|orbital`, Space Racer's theme
pattern). Each is a 14 000 × 14 000 u play area (world ±16 384 hard limit), 0–5 000 u of air, inside a moondome.

| Arena | Theme | Layout |
|---|---|---|
| **Dunes** `mg_ironframe_dunes` | desert canyon at dusk, a wrecked megastructure and refinery | terrain mesa ring, central canyon, three plateaus (A/B/C), giant pipe bridges |
| **Sprawl** `mg_ironframe_sprawl` | ruined night city, neon, rain fog | city blocks of generated towers (box buildings with emissive windows, LOD), avenues, a flooded plaza, rooftop play |
| **Orbital** `mg_ironframe_orbital` | industrial platforms over a cloud sea, space elevator | platforms at three heights joined by gantries; falling off = death; strong vertical play |

Generated by `tools/vmap.py` with `vmapgen` (terrain, moondome, hints, probe volumes, lightmap-res shells, cache room,
template pool, booth, drop zones, capture points, spawns, `info_map_parameters`), lit by one `light_environment` plus
baked `light_omni2` accents, `env_cubemap_fog` + `env_volumetric_fog_controller`, post-processing. The same tool writes
`out/addon/_gen/arena_<id>.json` (bounds, drop zones, points, nav grid, cover) which the build bakes into the script.
Skies: 4096 × 2048 procedural panoramas (`tools/sky.py`: gradient, sun, clouds, stars/nebula, a planet for Orbital).

## 9. Technical architecture (CS2 script)

- One script per map build: `maps/scripts/ironframe.js` = core (pure) + baked data (parts, arena, HUD, sounds) + adapter,
  assembled by `create/build/build.mjs` (`build.json`). Entity prefix `ifr_`, point_script `ifr_script`, HUD `ifr_hud`.
- **Pawn ride** (Dogfight): the real pawn is invisible (`SetColor a 0` after `DestroyWeapons`), `FLYGRAVITY` with
  `sv_gravity 0`, carried by velocity toward the mech each tick with a snap `Teleport` beyond 400 u; it holds the health,
  takes the damage and produces the kills. Camera: `CustomPlayerCamera` `FOLLOW_POSITION` on the upper-body prop
  (`cameraOffset` back 520 / up 180 by class, `clipCameraOffset`), config re-sent only when it changes (boost pull-back).
  The eye angles aim; the crosshair ray is rebuilt in script (the upper prop's origin + hip, the offset turned by the eye angles, the
  wall pull-in traced) and traced to the point under the reticle; every round flies from its muzzle to that point (core `IF_reticle`).
  Spectators and the dead use `CONTROLLED` orbit cameras.
- **Clips and sky:** mech movement also sweeps a player hull (`Instance.TracePlayer`) so clip brushes block mechs (learned per cell,
  core `IF_clipStep`); the sky height is measured at load and rounds cruise under it and vanish at it without a blast (`IF_capZ`, `IF_atSky`).
- **IFF markers:** a pilot's own diamond is lifted 8 degrees clear of their reticle, and not drawn at all with no other human in the
  arena copy (props have no per-client visibility).
- **Rendering:** pooled `prop_dynamic`s from `point_template ifr_tpl_prop` (null model), `SetModel` to models cached in the
  cache room. Per mech: legs prop + upper prop (`Move` each tick; `SetParent`ed weapon props follow for free), two booster
  particle entities parented at claim time. Legs play gait clips (`SetAnimationLooping` idle/walk/boost/land) where a rig
  exists, otherwise skate. Wrecks are the same props falling. Budget: ≤ 4 engine calls per mech per tick plus effects, and
  far mechs (> 9 000 u from every human) move every 2nd tick.
- **FX:** pools with hard caps: 128 missiles, 24 explosion rings, 16 impact sparks, 8 big booms, 32 tracers, 16 beams;
  per-mech muzzle particles pulsed; sounds through `point_soundevent`s with `SetSourceEntity` and anchor rings; 14 pilot-only
  tones (lock stages, stagger, low AP, EN empty, kill confirm) via `StartSoundOnSingleClient`. Entity I/O is queued, so a
  Start and its Stop never land in the same tick (Dogfight `FX_EM`).
- **HUD:** Panorama layout generated by `tools/hud.py` (`create/panorama.py`), checked by `create/hud_check.py`: AP bar,
  EN bar (red when stalled), stagger meter, four weapon boxes (ammo/heat/cooldown ladders), lock reticle and range, target
  AP, threat arrows, radar (8 Hz dot transforms), mode panel (score, tickets, points), kill confirm, stagger/bounty badges,
  garage pages, intro and podium slates, spectator bar. Driver with a per-slot mirror, change-only writes, a governor of
  900 class changes per tick and odd/even player halves (Space Racer).
- **Garage UI:** key-driven while parked (W/S rows, A/D values, Space confirm, Ctrl back, F compare), with `<Button>`s and
  `OnCustomHudClicked` as the mouse path when the engine supports it. Part pictures are HUD images rendered offline.
- **Chat:** `!garage !loadout 1-6 !cam !help !ironframe !spec !afk !back !vote !mode !pilot !hints !od !bots`; replies as per-player HUD lines.
- **Robustness:** every player, projectile and module ticks in its own try/catch; slot ownership verified every 8 ticks;
  AFK on input only; full HUD reset on activate/team change/spawn; version banner `[ironframe] v0.1.0 ready: ...` with
  `MISSING` for absent entities; script time logged once a minute; `OnPlayerReset`/`OnPlayerTeamChanged` both re-read teams.
- **Plugin channel:** see [SERVER_CONTRACT.md](SERVER_CONTRACT.md). Map → server with `echo mgstat`/`echo ifr_srv` lines;
  server → map with `RunScriptInput` names plus per-slot mailbox entities whose targetname carries the payload.

## 10. Assets

- **Mech models** from the GMod Workshop via SteamCMD (`create/playermodels/fetch.py` style; the catalog is
  `data/frames.json`), converted with the new project-neutral `create/mdl2cs2.py` (Source 1 MDL/VVD/VTX + VTF → CS2 prop:
  bind-pose mesh, split into bone groups (legs / upper / weapons) by bone-name rules, uniform scale to the class height,
  VTF → PNG, `csgo_complex` vmats with normal/rough from the VMT where present, convex hulls, LODs with `lod_decimate.py`,
  a turntable preview). Mech-pack weapons (AC rifles, cannons, Titan weapons) convert the same way as weapon props.
- **Procedural weapon props** for families without a source model (`create/build_prop.py` specs in `tools/weapon_props.py`).
- **Effects:** `create/fx_models.py` emissive tracers/beams/rings; particles reused from Dogfight (`particles/dogfight/*`)
  and stock CS2 (`explosion_c4_500`, muzzle flashes, smoke); boosters are stock jet-flame-like particles tinted.
- **Sounds:** synthesised (`create/synth.py`, `create/chiptune.py`): boosters (filtered noise loops), weapons per family,
  impacts, stagger clang, lock tones, UI; music via `csgo_music` volume convar.
- **Licences:** project code PolyForm Noncommercial; our assets CC BY-NC 4.0. Workshop mech ports are other people's
  ports of commercial game assets: credited per item in `docs/CREDITS.md`, and the Workshop description says so.
  Private-server use only until each porter's permission is recorded (`data/frames.json` has a `permission` field);
  frames without permission are kept in the build only while `IF_ALL_FRAMES=1`.
- **Disk:** the PC has about 8 GB free; sources are downloaded one item at a time, converted, and the SteamCMD copy and
  extract deleted (`tools/frames.py --prune`). Converted output stays small (textures ≤ 2048, LODs).

## 11. Build and test

```
sh tools/build_all.sh            # IF_ARENA=dunes|sprawl|orbital, IF_CURRENT_VMAP=<Hammer save>
sh tools/deploy.sh               # into content/game csgo_addons/mg_ironframe_<arena>
node test/sim.cjs 64 300         # core soak: 64 AI mechs, every mode, no NaNs / stuck / unfinished rounds
node test/balance.cjs            # weapon and frame matchups, anti-stomp cap check (writes docs/BALANCE.md)
python tools/parts_check.py      # parts.json schema, caps, budgets
```
Build order: parts check → frames (convert if missing) → weapon props → fx models → HUD + hud_check → sounds + merge_snd →
sky → arena vmap + check_mesh → script build → tscheck → mock run (64 players, churn, held, hudwipe, `fire=ifr_server@5`) →
docs and licences into out/.

Plugin: `dotnet build` in slime-mg-gm, `python server/setup.py build`, `python tests/run.py --only ironframe` (RCON drives
`ifr_srv` lines and checks the DB rows and the mailbox payloads in the log).

## 12. Milestones

| # | Milestone | Done when |
|---|---|---|
| M1 | Design, parts catalog, server contract, skeleton | this folder, `parts_check` passes |
| M2 | Core sim: movement, weapons, damage, lock, AI, modes, progression | `sim.cjs` 64 × 300 s clean, balance table |
| M3 | Asset pipeline: `mdl2cs2.py`, 3 frames converted, weapon props, fx, sounds, sky | previews rendered, compiled by resourcecompiler |
| M4 | CS2 adapter + HUD on the mock | mock 64 players clean, HUD check passes, tscheck passes |
| M5 | Dunes arena map generated and compiled | map builds, loads in CS2 with the script banner |
| M6 | Plugin module: DB, garage, contract, mode cfg, test | `tests/run.py --only ironframe` passes |
| M7 | In-game test on the local server (skink52), fixes | TESTING.md checklist |
| M8 | Sprawl and Orbital, all frames, polish, Workshop descriptions | three uploads |
